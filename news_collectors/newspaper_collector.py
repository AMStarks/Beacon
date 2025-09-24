from __future__ import annotations

import logging
from typing import List
from datetime import datetime

from newspaper import Article as NPArticle

from news_collectors.base_collector import BaseCollector, Article

logger = logging.getLogger(__name__)


class NewspaperCollector(BaseCollector):
    """Fetch and parse articles using newspaper3k for a list of URLs."""

    def __init__(self, urls: List[str]):
        self.urls = urls

    async def collect(self) -> List[Article]:
        articles: List[Article] = []
        for url in self.urls:
            try:
                article = NPArticle(url)
                article.download()
                article.parse()
                article.nlp()
                published = article.publish_date or datetime.utcnow()

                articles.append(
                    Article(
                        title=article.title,
                        url=url,
                        source=article.source_url or url,
                        content=article.text,
                        summary=getattr(article, "summary", ""),
                        published_at=published,
                    )
                )
            except Exception as exc:
                logger.warning("newspaper3k failed for %s: %s", url, exc)
        return articles
