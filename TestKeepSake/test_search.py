import asyncio
from v_core.domains.tools.web.search_api import SearchAPI

async def test_snippet_strike():
    print("Initializing SearchAPI...")
    search_tool = SearchAPI()
    
    query = "ESP32-S3 TWAI driver syntax github"
    print(f"Executing query: '{query}'")
    
    results = await search_tool.execute(query=query)
    
    print("\n--- RESULTS ---")
    for idx, result in enumerate(results, 1):
        print(f"\nResult {idx}:")
        print(f"Title:   {result.get('title')}")
        print(f"URL:     {result.get('url')}")
        print(f"Snippet: {result.get('snippet')}")

if __name__ == "__main__":
    asyncio.run(test_snippet_strike())