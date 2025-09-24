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
                article = NewsPlease.from_url(url)
                if not article or not article.title:
                    continue
                published = article.date_publish or datetime.utcnow()
                articles.append(
                    Article(
                        title=article.title,
                        url=url,
                        source=article.source_domain or url,
                        content=article.maintext or "",
                        summary=article.summary or "",
                        published_at=published,
                        language=article.language or "en",
                    )
                )
            except Exception as exc:
                logger.warning("news-please failed for %s: %s", url, exc)
        return articles
