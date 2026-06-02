"""
Prompt Studio — Prompt Loader Abstraction Layer

Current (MODE=file): load from local filesystem
Future (MODE=url):    load from external URL / CDN

Switch by env:
  PROMPT_MODE=file          (default)
  PROMPT_MODE=url           (future)
  PROMPT_BASE_PATH=prompts/
  PROMPT_BASE_URL=...       (future CDN)
"""

import os
import json
import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("prompt-studio.loader")


class PromptLoader:
    MODE_FILE = "file"
    MODE_URL = "url"

    def __init__(self):
        self.mode = os.environ.get("PROMPT_MODE", self.MODE_FILE)
        self.base_path = os.environ.get("PROMPT_BASE_PATH", str(Path(__file__).parent / "prompts"))
        self.base_url = os.environ.get("PROMPT_BASE_URL", "")
        self._cache = {}
        logger.info(f"PromptLoader: mode={self.mode} base={self.base_path or self.base_url}")

    def load(self, module: str, name: str) -> Optional[str]:
        cache_key = f"{module}/{name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        content = None
        if self.mode == self.MODE_FILE:
            content = self._load_file(module, name)
        elif self.mode == self.MODE_URL:
            content = self._load_url(module, name)
        if content is not None:
            self._cache[cache_key] = content
        return content

    def load_json(self, module: str, name: str) -> Optional[dict]:
        c = self.load(module, name)
        if c:
            try:
                return json.loads(c)
            except json.JSONDecodeError:
                pass
        return None

    def list_module(self, module: str) -> list[dict]:
        if self.mode == self.MODE_FILE:
            return self._list_file(module)
        return []

    def fill_template(self, template: str, data: dict) -> str:
        def replacer(m):
            key = m.group(1)
            v = data.get(key)
            return str(v) if v is not None else ""
        return re.sub(r'\{\{(\w+)\}\}', replacer, template)

    def _load_file(self, module: str, name: str) -> Optional[str]:
        path = Path(self.base_path) / module / name
        if not path.exists():
            logger.warning(f"Prompt not found: {path}")
            return None
        try:
            return path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Read error {path}: {e}")
            return None

    def _load_url(self, module: str, name: str) -> Optional[str]:
        """Future: load from external CDN/API"""
        if not self.base_url:
            logger.error("PROMPT_MODE=url but no PROMPT_BASE_URL")
            return None
        try:
            import requests
            url = f"{self.base_url.rstrip('/')}/{module}/{name}"
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                return None
            return resp.text
        except Exception as e:
            logger.error(f"URL load error: {e}")
            return None

    def _list_file(self, module: str) -> list[dict]:
        path = Path(self.base_path) / module
        if not path.exists():
            return []
        files = []
        for f in sorted(path.iterdir()):
            if f.is_file() and f.suffix in (".txt", ".json", ".prompt"):
                files.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "path": str(f.relative_to(self.base_path)),
                })
        return files

    def clear_cache(self):
        self._cache.clear()


_loader: Optional[PromptLoader] = None


def get_loader() -> PromptLoader:
    global _loader
    if _loader is None:
        _loader = PromptLoader()
    return _loader


def load_prompt(module: str, name: str) -> Optional[str]:
    return get_loader().load(module, name)
