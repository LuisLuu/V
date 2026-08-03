from socket import timeout
from typing import Any, Dict, List

import aiohttp
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup

from agents.tools.preconditions import BaseTool, SecurityTier


class SearchAPI(BaseTool):
    """Perplexity-style Lightweight Snippet Engine.

    Queries the web and returns top 3 snippets + metadata instead of full web page scraping.
    Prevents context rot, high latency, and LLM context window choking[cite: 14].
    """

    name: str = "search_api"
    description: str = (
        "Searches the web for real-time information, technical docs, or factual references. "
        "Returns up to 3 short snippets with source URLs."
    )
    security_tier: SecurityTier = SecurityTier.READ

    # Computational sensors: e.g., ensure basic internet connectivity or valid parameters
    preconditions = [lambda: True]

    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The targeted search query (e.g., 'ESP32-S3 TWAI driver syntax github')",
                    }
                },
                "required": ["query"],
            },
        }

    async def execute(self, query: str) -> List[Dict[str, str]]:
        """Executes a zero-heavy-deps DuckDuckGo Lite snippet extraction.

        Strictly enforces MAX_RESULTS = 3[cite: 14].
        """
        url = "https://html.duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) V-Core/1.0"
        }
        timeout = ClientTimeout(total=5)

        try:
            async with aiohttp.ClientSession() as session:
                # Pass the object instead of the integer[cite: 14]
                async with session.post(
                    url, data={"q": query}, headers=headers, timeout=timeout
                ) as resp:
                    if resp.status != 200:
                        return [
                            {
                                "error": f"Search backend returned HTTP {resp.status}"
                            }
                        ]

                    html = await resp.text()
                    soup = BeautifulSoup(html, "html.parser")

                    results = []

                    # Enforce strict hard cap (MAX_RESULTS = 3)[cite: 14]
                    for row in soup.find_all("div", class_="result")[:3]:
                        title_elem = row.find("a", class_="result__a")
                        snippet_elem = row.find("a", class_="result__snippet")

                        if title_elem and snippet_elem:
                            results.append(
                                {
                                    "title": title_elem.text.strip(),
                                    "url": title_elem.get("href", ""),
                                    "snippet": snippet_elem.text.strip(),
                                }
                            )

                    # Format as a rigid string so the LLM cannot ignore the URL[cite: 14]
                    if results:
                        formatted_text = "\n\n".join(
                            [
                                f"SOURCE TITLE: {r['title']}\nURL: {r['url']}\nFACTS: {r['snippet']}"
                                for r in results
                            ]
                        )
                        return [{"status": "success", "data": formatted_text}]
                    else:
                        return [
                            {
                                "status": "failed",
                                "error": "Search failed. Do not hallucinate URLs.",
                            }
                        ]

        except Exception as e:
            return [{"error": f"Search execution failed: {str(e)}"}]