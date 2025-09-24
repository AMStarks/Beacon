from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

import feedparser
import httpx

from news_collectors.base_collector import Article, BaseCollector

logger = logging.getLogger(__name__)


DEFAULT_HEADERS = {
    "User-Agent": "BeaconCollector/1.0 (+https://beacon)",
    "Accept": "application/rss+xml, application/xml;q=0.9, */*;q=0.8",
}


@dataclass(frozen=True)
class DomainSourceConfig:
    name: str
    feed_url: str
    source_name: str
    article_limit: int = 15
    fetch_html: bool = True
    request_timeout: float = 15.0
    concurrency: int = 5
    headers: Optional[Dict[str, str]] = None


class RSSCollector(BaseCollector):
    """Fetch articles for a domain using its RSS feed and optional HTML fetch."""

    def __init__(self, config: DomainSourceConfig):
        self.config = config
        headers = DEFAULT_HEADERS.copy()
        if config.headers:
            headers.update(config.headers)
        self.headers = headers
        self._semaphore = asyncio.Semaphore(config.concurrency)

    async def collect(self) -> List[Article]:
        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True) as client:
            try:
                feed_response = await client.get(
                    self.config.feed_url,
                    timeout=self.config.request_timeout,
                )
                feed_response.raise_for_status()
            except Exception as exc:
                logger.warning(
                    "RSSCollector(%s) failed to fetch feed: %s",
                    self.config.name,
                    exc,
                )
                return []

            parsed = feedparser.parse(feed_response.content)
            entries = parsed.entries[: self.config.article_limit]

            tasks = [self._process_entry(entry, client) for entry in entries]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        articles: List[Article] = []
        for result in results:
            if isinstance(result, Article):
                articles.append(result)
            elif isinstance(result, Exception):
                logger.debug(
                    "RSSCollector(%s) gather error: %s",
                    self.config.name,
                    result,
                )
        logger.info(
            "RSSCollector(%s) produced %d articles",
            self.config.name,
            len(articles),
        )
        return articles

    async def _process_entry(self, entry, client: httpx.AsyncClient) -> Optional[Article]:
        async with self._semaphore:
            url = entry.get("link")
            title = entry.get("title", "").strip()
            if not url or not title:
                return None

            published = self._parse_timestamp(entry)
            summary = entry.get("summary", entry.get("description", "")) or ""
            article_html = ""
            article_text = summary

            if self.config.fetch_html:
                try:
                    article_response = await client.get(
                        url,
                        timeout=self.config.request_timeout,
                    )
                    article_response.raise_for_status()
                    article_html = article_response.text
                except Exception as exc:
                    logger.debug(
                        "RSSCollector(%s) failed to fetch article %s: %s",
                        self.config.name,
                        url,
                        exc,
                    )

            meta: Dict[str, str] = {
                "feed_url": self.config.feed_url,
            }
            if entry.get("id"):
                meta["entry_id"] = entry.get("id")
            if entry.get("tags"):
                meta["tags"] = ",".join(tag.get("term", "") for tag in entry.get("tags", []))

            source_domain = self.config.source_name or self._infer_domain(url)

            return Article(
                title=title,
                url=url,
                source=source_domain,
                content=article_text,
                published_at=published,
                summary=summary,
                raw_html=article_html,
                meta=meta,
            )

    def _parse_timestamp(self, entry) -> datetime | None:
        published = entry.get("published") or entry.get("updated")
        if published:
            try:
                dt = parsedate_to_datetime(published)
                if dt and dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass

        if entry.get("published_parsed"):
            try:
                ts = time.mktime(entry.published_parsed)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except Exception:
                return None
        return None

    def _infer_domain(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            return parsed.netloc or url
        except Exception:
            return url

