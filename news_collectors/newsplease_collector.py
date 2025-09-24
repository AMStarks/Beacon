from __future__ import annotations

import logging
from datetime import datetime
from typing import List

from newsplease import NewsPlease

from news_collectors.base_collector import BaseCollector, Article

logger = logging.getLogger(__name__)


class NewsPleaseCollector(BaseCollector):
    """Collect articles via news-please for a list of URLs."""

    def __init__(self, urls: List[str]):
        self.urls = urls

    async def collect(self) -> List[Article]:
        articles: List[Article] = []
        for url in self.urls:
            try:
                result = NewsPlease.from_url(url)
                if not result or not result.title:
                    continue
                published = result.date_publish or datetime.utcnow()
                articles.append(
                    Article(
                        title=result.title,
                        url=url,
                        source=result.source_domain or url,
                        content=result.maintext or "",
                        summary=result.summary or "",
                        published_at=published,
                        language=result.language or "en"
                    )
                )
            except Exception as exc:
                logger.warning("news-please failed for %s: %s", url, exc)
        return articles
