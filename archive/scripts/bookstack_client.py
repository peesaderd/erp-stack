"""BookStackClient — knowledge base integration for Brain Server."""

import logging
import requests

log = logging.getLogger("brain.bookstack")


class BookStackClient:
    """Client for BookStack API (shelves, books, pages)."""

    def __init__(self, base_url: str, token_id: str, token_secret: str):
        self.base_url = base_url.rstrip("/")
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Token {token_id}:{token_secret}",
            "Content-Type": "application/json",
        })
        self._available = True
        try:
            resp = self._session.get(f"{self.base_url}/api/books", timeout=5)
            resp.raise_for_status()
        except requests.RequestException:
            log.warning("BookStack not reachable at %s", base_url)
            self._available = False

    def search_pages(self, query: str) -> list:
        """Search pages by query."""
        if not self._available:
            return []
        try:
            resp = self._session.get(
                f"{self.base_url}/api/pages",
                params={"filter[search]": query},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except requests.RequestException as e:
            log.warning("BookStack search failed: %s", e)
            return []

    def list_books(self) -> list:
        """List all books."""
        if not self._available:
            return []
        try:
            resp = self._session.get(f"{self.base_url}/api/books", timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", [])
        except requests.RequestException as e:
            log.warning("BookStack list books failed: %s", e)
            return []

    def create_page(self, book_id: int, title: str, content: str) -> dict:
        """Create a new page in a book."""
        if not self._available:
            return {"error": "BookStack not available"}
        try:
            resp = self._session.post(
                f"{self.base_url}/api/pages",
                json={
                    "book_id": book_id,
                    "name": title,
                    "html": content,
                },
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            log.warning("BookStack create page failed: %s", e)
            return {"error": str(e)}
