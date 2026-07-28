import re
import sqlite3
import logging

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
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.logger = logging.getLogger(__name__)

    def _extract_keywords(self, prompt: str) -> list[str]:
        """Strips punctuation, forces lowercase, and drops conversational filler."""
        clean_text = re.sub(r'[^\w\s]', '', prompt.lower())
        return [w for w in clean_text.split() if w not in STOP_WORDS]

    # FIX: Lowered the threshold to -12.0 to block weak conversational noise
    def evaluate_and_fetch(self, prompt: str, threshold: float = 0.0) -> str | None:
        """
        Evaluates a prompt for keywords and fetches high-confidence context from ROM.
        Returns the context string if found, or None if fast-fail.
        """
        keywords = self._extract_keywords(prompt)
        
        if not keywords:
            self.logger.debug("Router Fast-Fail: No actionable keywords extracted.")
            return None

        query = " OR ".join(keywords)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT content, rank 
                    FROM chat_search_idx 
                    WHERE chat_search_idx MATCH ? 
                    ORDER BY rank 
                    LIMIT 3;
                ''', (query,))
                
                results = cursor.fetchall()
                
                for row in results:
                    print(f"DEBUG - Match Score: {row[1]} | Content: {row[0][:30]}...")
                
                if not results:
                    return None
                    
                # FIX: Simply filter out any non-matches (score >= 0.0) and trust the LIMIT 3 sorting
                valid_contexts = [row[0] for row in results if row[1] < threshold]
                
                if valid_contexts:
                    self.logger.info(f"Router injected context based on keywords: {keywords}")
                    return "\n---\n".join(valid_contexts)
                
                self.logger.debug("Router found matches, but they failed the baseline threshold.")
                return None

        except sqlite3.OperationalError as e:
            self.logger.error(f"FTS5 Query Error (Likely bad keyword syntax): {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected Router Error: {e}")
            return None