import re

from agents.tools.preconditions import BaseTool, SecurityTier


class WebScraper(BaseTool):
    """Fetches web pages and performs targeted extraction of semantic HTML tags (paragraphs, headers, lists)

    to prevent LLM context window blowout[cite: 15].
    """

    def __init__(self):
        self.name = "web_scraper"
        self.description = "Fetches a URL and returns clean text content. Use this to read documentation or search the live web."
        self.security_tier = SecurityTier.READ
        self.preconditions = [self._check_dependencies]
        # Reduced from 15,000 to 5,000 to prevent LLM "Lost in the Middle" amnesia[cite: 15]
        self.max_chars = 5000

    def _check_dependencies(self) -> bool:
        """Sensor: Verifies HTTP and parsing libraries are available[cite: 15]."""
        try:
            import requests
            from bs4 import BeautifulSoup

            return True
        except ImportError:
            return False

    def get_schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "The exact URL to scrape.",
                        }
                    },
                    "required": ["url"],
                },
            },
        }

    def execute(self, url: str) -> str:
        """The extraction pipeline: Request -> Parse -> Smart Extraction -> Truncate[cite: 15]."""
        import requests
        from bs4 import BeautifulSoup

        try:
            # We spoof a standard browser header. Many modern firewalls instantly
            # block requests that say "Python-urllib"[cite: 15].
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # Load the HTML into BeautifulSoup[cite: 15]
            soup = BeautifulSoup(response.text, "html.parser")

            # SMART EXTRACTION: Only grab semantic content tags.
            # This ignores weird nested spans, hidden UI text, and broken CSS remnants[cite: 15].
            content_tags = soup.find_all(["h1", "h2", "h3", "p", "li"])

            extracted_text = []
            for tag in content_tags:
                tag_text = tag.get_text(separator=" ", strip=True)
                if tag_text:
                    extracted_text.append(tag_text)

            # Join it all together cleanly[cite: 15]
            text = "\n\n".join(extracted_text)

            # Truncate to the new, safer max limit[cite: 15]
            if len(text) > self.max_chars:
                return (
                    text[: self.max_chars]
                    + f"\n\n...[SYSTEM WARNING: Webpage truncated at {self.max_chars} chars to preserve memory.]"
                )

            return (
                text
                if text
                else "SYSTEM_ERROR: Page was fetched but no readable text was found."
            )

        except requests.exceptions.Timeout:
            return "SYSTEM_ERROR: Web request timed out after 10 seconds."
        except Exception as e:
            return f"SYSTEM_ERROR: Failed to scrape URL: {str(e)}"