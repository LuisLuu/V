import re
import sqlite3
import logging

# 1. Import the centralized absolute path from your new memory module
from memory.sqlite_rom import ABSOLUTE_DB_PATH

# Standard NLP Stop Words (O(1) lookup time)
STOP_WORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
    "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", 
    "herself", "it", "its", "itself", "they", "them", "their", "theirs", "themselves", 
    "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are", 
    "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does", 
    "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until", 
    "while", "of", "at", "by", "for", "with", "about", "against", "between", "into", 
    "through", "during", "before", "after", "above", "below", "to", "from", "up", "down", 
    "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here", 
    "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more", 
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so", 
    "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now", "think"
}

class MemoryRouter:
    # 2. Make db_path optional to avoid breaking whatever calls it
    def __init__(self, db_path: str | None = None):
        self.db_path = ABSOLUTE_DB_PATH
        self.logger = logging.getLogger(__name__)

    def _extract_keywords(self, prompt: str) -> list[str]:
        """Strips punctuation, forces lowercase, and drops conversational filler."""
        clean_text = re.sub(r'[^\w\s]', '', prompt.lower())
        return [w for w in clean_text.split() if w not in STOP_WORDS]

    # FIX: Lowered the threshold to -12.0 to block weak conversational noise
    def evaluate_and_fetch(self, prompt: str, dropoff_tolerance: float = 0.5) -> str | None:
        """
        Evaluates a prompt and fetches high-confidence context using dynamic relative thresholding.
        Instead of a magic number, it establishes a baseline from the best match.
        """
        keywords = self._extract_keywords(prompt)
        
        if not keywords:
            self.logger.debug("Router Fast-Fail: No actionable keywords extracted.")
            return None

        query = " OR ".join(keywords)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # FTS5 ranks are negative; more negative is better.
                cursor.execute('''
                    SELECT content, rank 
                    FROM chat_search_idx 
                    WHERE chat_search_idx MATCH ? 
                    ORDER BY rank 
                    LIMIT 3;
                ''', (query,))
                
                results = cursor.fetchall()
                
                if not results:
                    return None

                # 1. Establish the baseline from the top hit
                best_score = results[0][1]
                
                # 2. Calculate the dynamic cliff (e.g., 50% worse than the best score)
                # Since scores are negative, multiplying by 0.5 moves it closer to 0 (worse)
                dynamic_threshold = best_score * dropoff_tolerance
                
                # 3. Filter using the dynamic threshold
                valid_contexts = [row[0] for row in results if row[1] <= dynamic_threshold]
                
                if valid_contexts:
                    self.logger.info(f"Router injected context based on keywords: {keywords} (Best Score: {best_score:.2f})")
                    return "\n---\n".join(valid_contexts)
                
                return None

        except sqlite3.OperationalError as e:
            self.logger.error(f"FTS5 Query Error (Likely bad keyword syntax): {e}")
            return None