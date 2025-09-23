import json
import os
import time
from typing import Optional, Dict, Any


class CacheStore:
    """Very small JSON file cache for ETag/Last-Modified and simple responses.

    Not meant for large payloads. Keeps a single file on disk.
    """

    def __init__(self, path: str = "cache_etags.json"):
        self.path = path
        self._data: Dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self.path):
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception:
                self._data = {}

    def _save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f)
        except Exception:
            pass

    def get_headers(self, url: str) -> Dict[str, str]:
        entry = self._data.get(url, {})
        headers: Dict[str, str] = {}
        etag = entry.get("etag")
        last_modified = entry.get("last_modified")
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        return headers

    def set_headers(self, url: str, etag: Optional[str], last_modified: Optional[str]) -> None:
        self._data[url] = {
            "etag": etag,
            "last_modified": last_modified,
            "ts": int(time.time())
        }
        self._save()


