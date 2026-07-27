#!/usr/bin/env python3
"""BookStack MCP Server — ให้ OpenClaw Agent อ่าน/เขียน BookStack ได้โดยตรง."""

import json
import os
import sys
import requests
from typing import Any

BS_URL = os.environ.get("BOOKSTACK_URL", "http://89.167.82.205:54515")
BS_TOKEN_ID = os.environ.get("BOOKSTACK_TOKEN_ID", "uZTNikZA8fqWiFIUWqPfWtDdjneoQ6qO")
BS_TOKEN_SECRET = os.environ.get("BOOKSTACK_TOKEN_SECRET", "loc2XsVH5CcHzifBTROQq8YvKa5oVtyV")


class BookStackClient:
    """Thin REST client for BookStack API."""

    def __init__(self):
        self.base = BS_URL.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token {BS_TOKEN_ID}:{BS_TOKEN_SECRET}",
            "Content-Type": "application/json",
        })

    def _get(self, path: str, **params) -> dict:
        r = self.session.get(f"{self.base}{path}", params=params, timeout=15)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, body: dict) -> dict:
        r = self.session.post(f"{self.base}{path}", json=body, timeout=15)
        r.raise_for_status()
        return r.json()

    def _put(self, path: str, body: dict) -> dict:
        r = self.session.put(f"{self.base}{path}", json=body, timeout=15)
        r.raise_for_status()
        return r.json()

    def _delete(self, path: str) -> None:
        r = self.session.delete(f"{self.base}{path}", timeout=15)
        r.raise_for_status()

    # ── Shelves ──
    def list_shelves(self) -> list[dict]:
        return self._get("/api/shelves").get("data", [])

    def create_shelf(self, name: str, description: str = "") -> dict:
        return self._post("/api/shelves", {"name": name, "description": description})

    # ── Books ──
    def list_books(self, shelf_id: int = None) -> list[dict]:
        params = {}
        if shelf_id:
            params["filter[shelf_id]"] = shelf_id
        return self._get("/api/books", **params).get("data", [])

    def create_book(self, name: str, description: str = "", shelf_id: int = None) -> dict:
        body = {"name": name, "description": description}
        if shelf_id:
            body["shelf_id"] = shelf_id
        return self._post("/api/books", body)

    # ── Chapters ──
    def list_chapters(self, book_id: int) -> list[dict]:
        return self._get(f"/api/books/{book_id}/chapters").get("data", [])

    def create_chapter(self, book_id: int, name: str, description: str = "") -> dict:
        return self._post(f"/api/books/{book_id}/chapters", {
            "name": name, "description": description,
        })

    # ── Pages ──
    def list_pages(self, book_id: int = None, chapter_id: int = None) -> list[dict]:
        params = {}
        if book_id:
            params["filter[book_id]"] = book_id
        if chapter_id:
            params["filter[chapter_id]"] = chapter_id
        return self._get("/api/pages", **params).get("data", [])

    def get_page(self, page_id: int) -> dict:
        return self._get(f"/api/pages/{page_id}")

    def create_page(self, book_id: int, chapter_id: int, name: str,
                    html: str = "", markdown: str = "") -> dict:
        body = {"book_id": book_id, "name": name}
        if chapter_id:
            body["chapter_id"] = chapter_id
        if html:
            body["html"] = html
        if markdown:
            body["markdown"] = markdown
        return self._post("/api/pages", body)

    def update_page(self, page_id: int, name: str = None,
                    html: str = None, markdown: str = None) -> dict:
        body = {}
        if name is not None:
            body["name"] = name
        if html is not None:
            body["html"] = html
        if markdown is not None:
            body["markdown"] = markdown
        return self._put(f"/api/pages/{page_id}", body)

    def delete_page(self, page_id: int) -> None:
        self._delete(f"/api/pages/{page_id}")

    # ── Search ──
    def search(self, query: str) -> list[dict]:
        return self._get("/api/pages", **{"filter[search]": query}).get("data", [])

    # ── Health ──
    def health(self) -> dict:
        try:
            self._get("/api/books")
            return {"status": "ok", "url": self.base}
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ── Stdio MCP Protocol ──

client = BookStackClient()


def handle_call(name: str, arguments: dict[str, Any]) -> dict:
    """Dispatch tool calls."""
    try:
        if name == "bookstack_health":
            return {"content": [{"type": "text", "text": json.dumps(client.health(), ensure_ascii=False)}]}

        elif name == "bookstack_list_shelves":
            data = client.list_shelves()
            return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}

        elif name == "bookstack_create_shelf":
            r = client.create_shelf(arguments["name"], arguments.get("description", ""))
            return {"content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False, indent=2)}]}

        elif name == "bookstack_list_books":
            data = client.list_books(arguments.get("shelf_id"))
            return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}

        elif name == "bookstack_create_book":
            r = client.create_book(arguments["name"], arguments.get("description", ""),
                                   arguments.get("shelf_id"))
            return {"content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False, indent=2)}]}

        elif name == "bookstack_list_chapters":
            data = client.list_chapters(arguments["book_id"])
            return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}

        elif name == "bookstack_create_chapter":
            r = client.create_chapter(arguments["book_id"], arguments["name"],
                                      arguments.get("description", ""))
            return {"content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False, indent=2)}]}

        elif name == "bookstack_list_pages":
            data = client.list_pages(arguments.get("book_id"), arguments.get("chapter_id"))
            return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}

        elif name == "bookstack_get_page":
            r = client.get_page(arguments["page_id"])
            return {"content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False, indent=2)}]}

        elif name == "bookstack_create_page":
            r = client.create_page(arguments["book_id"], arguments.get("chapter_id", 0),
                                   arguments["name"], arguments.get("html", ""),
                                   arguments.get("markdown", ""))
            return {"content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False, indent=2)}]}

        elif name == "bookstack_update_page":
            r = client.update_page(arguments["page_id"], arguments.get("name"),
                                   arguments.get("html"), arguments.get("markdown"))
            return {"content": [{"type": "text", "text": json.dumps(r, ensure_ascii=False, indent=2)}]}

        elif name == "bookstack_search":
            data = client.search(arguments["query"])
            return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}

        elif name == "bookstack_delete_page":
            client.delete_page(arguments["page_id"])
            return {"content": [{"type": "text", "text": json.dumps({"ok": True})}]}

        else:
            return {"content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                    "isError": True}
    except Exception as e:
        return {"content": [{"type": "text", "text": json.dumps({"error": str(e)}, ensure_ascii=False)}],
                "isError": True}


# ── Tool Definitions ──
TOOLS = [
    {
        "name": "bookstack_health",
        "description": "Check BookStack API connection status.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "bookstack_list_shelves",
        "description": "List all shelves in BookStack.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "bookstack_create_shelf",
        "description": "Create a new shelf in BookStack.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Shelf name"},
                "description": {"type": "string", "description": "Shelf description"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "bookstack_list_books",
        "description": "List all books, optionally filtered by shelf.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "shelf_id": {"type": "integer", "description": "Filter by shelf ID (optional)"},
            },
        },
    },
    {
        "name": "bookstack_create_book",
        "description": "Create a new book in BookStack.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Book name"},
                "description": {"type": "string", "description": "Book description"},
                "shelf_id": {"type": "integer", "description": "Shelf ID to place book in"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "bookstack_list_chapters",
        "description": "List chapters in a book.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "book_id": {"type": "integer", "description": "Book ID"},
            },
            "required": ["book_id"],
        },
    },
    {
        "name": "bookstack_create_chapter",
        "description": "Create a chapter in a book.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "book_id": {"type": "integer", "description": "Book ID"},
                "name": {"type": "string", "description": "Chapter name"},
                "description": {"type": "string", "description": "Chapter description"},
            },
            "required": ["book_id", "name"],
        },
    },
    {
        "name": "bookstack_list_pages",
        "description": "List pages, optionally filtered by book or chapter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "book_id": {"type": "integer", "description": "Filter by book ID (optional)"},
                "chapter_id": {"type": "integer", "description": "Filter by chapter ID (optional)"},
            },
        },
    },
    {
        "name": "bookstack_get_page",
        "description": "Get full content of a BookStack page by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "integer", "description": "Page ID"},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "bookstack_create_page",
        "description": "Create a new page in a book/chapter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "book_id": {"type": "integer", "description": "Book ID"},
                "chapter_id": {"type": "integer", "description": "Chapter ID (0 = root of book)"},
                "name": {"type": "string", "description": "Page name/title"},
                "html": {"type": "string", "description": "Page content in HTML"},
                "markdown": {"type": "string", "description": "Page content in Markdown"},
            },
            "required": ["book_id", "name"],
        },
    },
    {
        "name": "bookstack_update_page",
        "description": "Update an existing BookStack page.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "integer", "description": "Page ID"},
                "name": {"type": "string", "description": "New page name"},
                "html": {"type": "string", "description": "New HTML content"},
                "markdown": {"type": "string", "description": "New Markdown content"},
            },
            "required": ["page_id"],
        },
    },
    {
        "name": "bookstack_search",
        "description": "Search pages in BookStack by keyword.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or phrase"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "bookstack_delete_page",
        "description": "Delete a page from BookStack.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "page_id": {"type": "integer", "description": "Page ID to delete"},
            },
            "required": ["page_id"],
        },
    },
]


def main():
    """Read JSON-RPC from stdin, write results to stdout (stdio MCP)."""
    # Send initial server info
    init_msg = {
        "jsonrpc": "2.0",
        "method": "initialized",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "bookstack-mcp", "version": "1.0.0"},
        },
    }
    sys.stdout.write(json.dumps(init_msg) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        msg_id = msg.get("id")
        method = msg.get("method")

        if method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
        elif method == "tools/call":
            result = handle_call(msg["params"]["name"], msg["params"].get("arguments", {}))
            resp = {"jsonrpc": "2.0", "id": msg_id, "result": result}
        elif method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "bookstack-mcp", "version": "1.0.0"},
                },
            }
        else:
            resp = {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
