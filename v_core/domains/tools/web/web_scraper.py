import re
from v_core.domains.tools.preconditions import BaseTool, SecurityTier

class WebScraper(BaseTool):
    """
    Fetches web pages and extracts the raw text payload, 
    stripping away the HTML DOM, CSS, and Javascript.
    """
    def __init__(self):
        self.name = "web_scraper"
        self.description = "Fetches a URL and returns clean text content. Use this to read documentation or search the live web."
        self.security_tier = SecurityTier.READ
        self.preconditions = [self._check_dependencies]
        # Generous buffer for articles and documentation
        self.max_chars = 15000 

    def _check_dependencies(self) -> bool:
        """Sensor: Verifies HTTP and parsing libraries are available."""
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
                            "description": "The exact URL to scrape."
                        }
                    },
                    "required": ["url"]
                }
            }
        }

    def execute(self, url: str) -> str:
        """
        The extraction pipeline: Request -> Parse -> Strip -> Truncate.
        """
        import requests
        from bs4 import BeautifulSoup

        try:
            # We spoof a standard browser header. Many modern firewalls instantly 
            # block requests that say "Python-urllib".
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            # The Filter: Load the HTML into BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')

            # Annihilate the structural garbage (scripts, styles, headers, footers)
            for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
                element.decompose()

            # Extract pure text with line breaks
            text = soup.get_text(separator='\n', strip=True)

            # Clean up massive gaps of whitespace left by deleted elements
            text = re.sub(r'\n\s*\n', '\n\n', text)

            if len(text) > self.max_chars:
                return text[:self.max_chars] + f"\n\n...[SYSTEM WARNING: Webpage truncated at {self.max_chars} chars.]"

            return text if text else "SYSTEM_ERROR: Page was fetched but no readable text was found."

        except requests.exceptions.Timeout:
            return "SYSTEM_ERROR: Web request timed out after 10 seconds."
        except Exception as e:
             return f"SYSTEM_ERROR: Failed to scrape URL: {str(e)}"