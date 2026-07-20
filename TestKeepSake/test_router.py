import sqlite3
import re

def setup_mock_db():
    """Creates a temporary in-memory FTS5 DB and seeds it with compacted memory."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    
    # Create the FTS5 virtual table, using Porter stemming (like your ROM)
    cursor.execute('''
        CREATE VIRTUAL TABLE rom_memory USING fts5(
            content, 
            tags,
            tokenize='porter'
        )
    ''')
    
    # Insert Turn 10 Recap: Simulated compacted memory
    cursor.execute('''
        INSERT INTO rom_memory (content, tags) 
        VALUES (
            'User is building a custom hardware enclosure. Recommended material is high-temperature PETG due to heat constraints. Assembly requires specific tolerances.', 
            '3dprint hardware enclosure petg'
        )
    ''')
    conn.commit()
    return conn

def extract_keywords(prompt):
    """A zero-latency, native Python keyword extractor to act as our Router."""
    # A brutalist list of stop words to filter out conversational noise
    stop_words = {"will", "the", "in", "that", "a", "is", "it", "to", "and", "or", "my", "do", "does", "can", "on", "we", "you", "think"}
    
    # Strip punctuation and force lowercase
    clean_text = re.sub(r'[^\w\s]', '', prompt.lower())
    words = clean_text.split()
    
    # Return only the meat of the prompt
    return [w for w in words if w not in stop_words]

def test_prompt_routing(conn, prompt):
    cursor = conn.cursor()
    print(f"\n[+] User Prompt: '{prompt}'")
    
    # ---------------------------------------------------------
    # TEST 1: THE RAW PROMPT APPROACH (What happens if we don't filter?)
    # ---------------------------------------------------------
    print("  -> TEST 1: Raw Prompt Search")
    # FTS5 crashes on raw conversational text with punctuation. We must split it.
    raw_words = re.sub(r'[^\w\s]', '', prompt).split()
    raw_query = " OR ".join(raw_words)
    
    try:
        cursor.execute("SELECT content FROM rom_memory WHERE rom_memory MATCH ?", (raw_query,))
        raw_result = cursor.fetchall()
        print(f"     Query: MATCH '{raw_query}'")
        print(f"     Result: {len(raw_result)} hits. (Warning: High risk of false positives from common words)")
    except Exception as e:
         print(f"     Result: FAILED - {e}")

    # ---------------------------------------------------------
    # TEST 2: THE EXTRACTED KEYWORD APPROACH (The Router Engine)
    # ---------------------------------------------------------
    print("\n  -> TEST 2: Extracted Keyword Search")
    keywords = extract_keywords(prompt)
    
    # If the user just says "Hello" or "Do you think so?", keywords will be empty.
    if not keywords:
        print("     Result: Fast-Fail (No actionable keywords). Bypassing DB entirely to save VRAM.")
        return

    clean_query = " OR ".join(keywords)
    cursor.execute("SELECT content FROM rom_memory WHERE rom_memory MATCH ?", (clean_query,))
    clean_result = cursor.fetchall()
    
    print(f"     Query: MATCH '{clean_query}'")
    if clean_result:
         print(f"     Result: SUCCESS - V intercepts and injects Context: '{clean_result[0][0]}'")
    else:
         print("     Result: Zero matches in ROM. Bypassing DB injection.")

if __name__ == "__main__":
    db_conn = setup_mock_db()
    print("=== V CORE: MEMORY ROUTING PROTOTYPE ===")
    
    # Scenario A: The lazy, implicit user prompt
    test_prompt_routing(db_conn, "Will the PETG warp?")
    
    # Scenario B: Pure conversational noise (Checking our fast-fail logic)
    test_prompt_routing(db_conn, "Do you think it will rain today?")
    
    db_conn.close()

    # python -m TestKeepSake.test_router