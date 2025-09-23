import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
from cache_store import CacheStore


class ProviderBase:
    def __init__(self, client: httpx.AsyncClient, cache: CacheStore):
        self.client = client
        self.cache = cache

    def _norm(self, text: Optional[str]) -> str:
        return (text or "").strip()


class NewsAPIProvider(ProviderBase):
    def __init__(self, client: httpx.AsyncClient, cache: CacheStore, api_key: str):
        super().__init__(client, cache)
        self.api_key = api_key

    async def fetch(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = "https://newsapi.org/v2/top-headlines"
        p = {"apiKey": self.api_key, "language": "en", "pageSize": 50}
        p.update(params)

        headers = self.cache.get_headers(url)
        r = await self.client.get(url, params=p, headers=headers)
        if r.status_code == 304:
            return []
        r.raise_for_status()
        etag = r.headers.get("ETag")
        lm = r.headers.get("Last-Modified")
        self.cache.set_headers(url, etag, lm)
        data = r.json()
        out: List[Dict[str, Any]] = []
        for it in data.get("articles", []):
            if not it.get("title") or not it.get("url"):
                continue
            out.append({
                "title": self._norm(it.get("title")),
                "content": self._norm(it.get("description") or it.get("content")),
                "url": it["url"],
                "source": (it.get("source") or {}).get("name", "NewsAPI"),
                "published_at": it.get("publishedAt"),
            })
        return out


class NewsDataProvider(ProviderBase):
    def __init__(self, client: httpx.AsyncClient, cache: CacheStore, api_key: str):
        super().__init__(client, cache)
        self.api_key = api_key

    async def fetch(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = "https://newsdata.io/api/1/news"
        p = {"apikey": self.api_key, "language": "en", "size": 50}
        p.update(params)
        headers = self.cache.get_headers(url)
        r = await self.client.get(url, params=p, headers=headers)
        if r.status_code == 304:
            return []
        r.raise_for_status()
        etag = r.headers.get("ETag")
        lm = r.headers.get("Last-Modified")
        self.cache.set_headers(url, etag, lm)
        data = r.json()
        out: List[Dict[str, Any]] = []
        for it in data.get("results", []):
            if not it.get("title") or not it.get("link"):
                continue
            out.append({
                "title": self._norm(it.get("title")),
                "content": self._norm(it.get("description") or it.get("content")),
                "url": it["link"],
                "source": it.get("source_id", "NewsData"),
                "published_at": it.get("pubDate"),
            })
        return out


class GuardianProvider(ProviderBase):
    def __init__(self, client: httpx.AsyncClient, cache: CacheStore, api_key: str):
        super().__init__(client, cache)
        self.api_key = api_key

    async def fetch(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = "https://content.guardianapis.com/search"
        p = {"api-key": self.api_key, "page-size": 50, "show-fields": "trailText"}
        if params.get("country"):
            p["q"] = params.get("country")
        if params.get("category"):
            p["section"] = params.get("category")
        headers = self.cache.get_headers(url)
        r = await self.client.get(url, params=p, headers=headers)
        if r.status_code == 304:
            return []
        r.raise_for_status()
        etag = r.headers.get("ETag"); lm = r.headers.get("Last-Modified")
        self.cache.set_headers(url, etag, lm)
        data = r.json().get("response", {})
        out: List[Dict[str, Any]] = []
        for it in data.get("results", []):
            out.append({
                "title": self._norm(it.get("webTitle")),
                "content": self._norm(((it.get("fields") or {}).get("trailText"))),
                "url": it.get("webUrl"),
                "source": "The Guardian",
                "published_at": it.get("webPublicationDate"),
            })
        return out


class GNewsProvider(ProviderBase):
    def __init__(self, client: httpx.AsyncClient, cache: CacheStore, api_key: str):
        super().__init__(client, cache)
        self.api_key = api_key

    async def fetch(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        url = "https://gnews.io/api/v4/top-headlines"
        p = {"token": self.api_key, "lang": "en", "max": 50}
        if params.get("country"):
            p["country"] = params["country"]
        if params.get("category"):
            p["topic"] = params["category"]
        headers = self.cache.get_headers(url)
        r = await self.client.get(url, params=p, headers=headers)
        if r.status_code == 304:
            return []
        r.raise_for_status()
        etag = r.headers.get("ETag"); lm = r.headers.get("Last-Modified")
        self.cache.set_headers(url, etag, lm)
        data = r.json()
        out: List[Dict[str, Any]] = []
        for it in data.get("articles", []):
            out.append({
                "title": self._norm(it.get("title")),
                "content": self._norm(it.get("description")),
                "url": it.get("url"),
                "source": (it.get("source") or {}).get("name", "GNews"),
                "published_at": it.get("publishedAt"),
            })
        return out


