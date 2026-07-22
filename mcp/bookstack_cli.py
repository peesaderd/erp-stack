#!/usr/bin/env python3
"""BookStack CLI — ใช้ exec tool อ่าน/เขียน BookStack ได้จาก agent.

Usage:
  ./bookstack_cli.py health
  ./bookstack_cli.py shelves
  ./bookstack_cli.py books [--shelf SHELF_ID]
  ./bookstack_cli.py create-shelf --name "..." [--desc "..."]
  ./bookstack_cli.py create-book --name "..." [--desc "..."] [--shelf SHELF_ID]
  ./bookstack_cli.py chapters --book BOOK_ID
  ./bookstack_cli.py create-chapter --book BOOK_ID --name "..." [--desc "..."]
  ./bookstack_cli.py pages [--book BOOK_ID] [--chapter CHAPTER_ID]
  ./bookstack_cli.py page --id PAGE_ID
  ./bookstack_cli.py create-page --book BOOK_ID [--chapter CHAPTER_ID] --name "..." [--md "..." --html "..."]
  ./bookstack_cli.py update-page --id PAGE_ID [--name "..."] [--md "..."] [--html "..."]
  ./bookstack_cli.py search --query "..."
  ./bookstack_cli.py delete-page --id PAGE_ID
"""

import json, os, sys, argparse, requests

BS_URL = os.environ.get("BOOKSTACK_URL", "http://89.167.82.205:54515")
BS_TOKEN_ID = os.environ.get("BOOKSTACK_TOKEN_ID", "uZTNikZA8fqWiFIUWqPfWtDdjneoQ6qO")
BS_TOKEN_SECRET = os.environ.get("BOOKSTACK_TOKEN_SECRET", "loc2XsVH5CcHzifBTROQq8YvKa5oVtyV")


def api(method: str, path: str, body: dict = None) -> dict:
    url = f"{BS_URL}{path}"
    h = {"Authorization": f"Token {BS_TOKEN_ID}:{BS_TOKEN_SECRET}", "Content-Type": "application/json"}
    r = requests.request(method, url, headers=h, json=body, timeout=15)
    r.raise_for_status()
    return r.json() if r.text else {}


def main():
    p = argparse.ArgumentParser(prog="bookstack")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("health")
    sub.add_parser("shelves", aliases=["list-shelves"])
    
    bp = sub.add_parser("books", aliases=["list-books"])
    bp.add_argument("--shelf", type=int)

    csp = sub.add_parser("create-shelf")
    csp.add_argument("--name", required=True)
    csp.add_argument("--desc", default="")

    cbp = sub.add_parser("create-book")
    cbp.add_argument("--name", required=True)
    cbp.add_argument("--desc", default="")
    cbp.add_argument("--shelf", type=int)

    chp = sub.add_parser("chapters", aliases=["list-chapters"])
    chp.add_argument("--book", type=int, required=True)

    cchp = sub.add_parser("create-chapter")
    cchp.add_argument("--book", type=int, required=True)
    cchp.add_argument("--name", required=True)
    cchp.add_argument("--desc", default="")

    pp = sub.add_parser("pages", aliases=["list-pages"])
    pp.add_argument("--book", type=int)
    pp.add_argument("--chapter", type=int)

    gp = sub.add_parser("page", aliases=["get-page"])
    gp.add_argument("--id", type=int, required=True)

    cpp = sub.add_parser("create-page")
    cpp.add_argument("--book", type=int, required=True)
    cpp.add_argument("--chapter", type=int)
    cpp.add_argument("--name", required=True)
    cpp.add_argument("--md", default="")
    cpp.add_argument("--html", default="")

    upp = sub.add_parser("update-page")
    upp.add_argument("--id", type=int, required=True)
    upp.add_argument("--name")
    upp.add_argument("--md")
    upp.add_argument("--html")

    sp = sub.add_parser("search")
    sp.add_argument("--query", required=True)

    dp = sub.add_parser("delete-page")
    dp.add_argument("--id", type=int, required=True)

    args = p.parse_args()
    cmd = args.cmd

    try:
        if cmd == "health":
            api("GET", "/api/books")
            print(json.dumps({"status": "ok", "url": BS_URL}, ensure_ascii=False))

        elif cmd in ("shelves", "list-shelves"):
            print(json.dumps(api("GET", "/api/shelves").get("data", []), ensure_ascii=False, indent=2))

        elif cmd == "create-shelf":
            print(json.dumps(api("POST", "/api/shelves", {"name": args.name, "description": args.desc}), ensure_ascii=False, indent=2))

        elif cmd in ("books", "list-books"):
            params = {}
            if args.shelf: params["filter[shelf_id]"] = args.shelf
            print(json.dumps(api("GET", "/api/books", params if params else None).get("data", []), ensure_ascii=False, indent=2))

        elif cmd == "create-book":
            body = {"name": args.name, "description": args.desc}
            if args.shelf: body["shelf_id"] = args.shelf
            print(json.dumps(api("POST", "/api/books", body), ensure_ascii=False, indent=2))

        elif cmd in ("chapters", "list-chapters"):
            print(json.dumps(api("GET", f"/api/books/{args.book}/chapters").get("data", []), ensure_ascii=False, indent=2))

        elif cmd == "create-chapter":
            print(json.dumps(api("POST", f"/api/books/{args.book}/chapters", {"name": args.name, "description": args.desc}), ensure_ascii=False, indent=2))

        elif cmd in ("pages", "list-pages"):
            params = {}
            if args.book: params["filter[book_id]"] = args.book
            if args.chapter: params["filter[chapter_id]"] = args.chapter
            print(json.dumps(api("GET", "/api/pages", params if params else None).get("data", []), ensure_ascii=False, indent=2))

        elif cmd in ("page", "get-page"):
            print(json.dumps(api("GET", f"/api/pages/{args.id}"), ensure_ascii=False, indent=2))

        elif cmd == "create-page":
            body = {"book_id": args.book, "name": args.name}
            if args.chapter: body["chapter_id"] = args.chapter
            if args.md: body["markdown"] = args.md
            if args.html: body["html"] = args.html
            print(json.dumps(api("POST", "/api/pages", body), ensure_ascii=False, indent=2))

        elif cmd == "update-page":
            body = {}
            if args.name: body["name"] = args.name
            if args.md: body["markdown"] = args.md
            if args.html: body["html"] = args.html
            print(json.dumps(api("PUT", f"/api/pages/{args.id}", body), ensure_ascii=False, indent=2))

        elif cmd == "search":
            print(json.dumps(api("GET", "/api/pages", {"filter[search]": args.query}).get("data", []), ensure_ascii=False, indent=2))

        elif cmd == "delete-page":
            api("DELETE", f"/api/pages/{args.id}")
            print(json.dumps({"ok": True}))

        else:
            p.print_help()

    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
