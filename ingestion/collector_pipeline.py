from __future__ import annotations

import logging
from typing import Iterable, List

from ingestion.raw_article import RawArticle
from ingestion.extraction_service import ExtractionService
from news_collectors import (
    NewsPleaseCollector,
    NewspaperCollector,
    GDELTCollector,
)
from storage.database import get_session
from storage.models import Article

logger = logging.getLogger(__name__)


class CollectorPipeline:
    def __init__(self):
        self.extractor = ExtractionService()

    async def run(self):
        raw_articles: List[RawArticle] = []
        raw_articles.extend(await self._collect_seed_articles())
        raw_articles.extend(await self._collect_gdelt_articles())

        logger.info("Pipeline fetched %d raw articles", len(raw_articles))

        processed = [self.extractor.extract(raw) for raw in raw_articles]
        self._persist_articles(processed)

    async def _collect_seed_articles(self) -> List[RawArticle]:
        urls = [
            "https://www.reuters.com/world/us/",
            "https://apnews.com/hub/ap-top-news",
            "https://www.npr.org/sections/news/",
        ]
        collector = NewsPleaseCollector(urls)
        articles = await collector.collect()
        return [self._convert_to_raw(article) for article in articles]

    async def _collect_gdelt_articles(self) -> List[RawArticle]:
        collector = GDELTCollector(limit=200)
        feeds = await collector.collect()
        detailed = await NewspaperCollector([article.url for article in feeds]).collect()
        all_articles = feeds + detailed
        return [self._convert_to_raw(article) for article in all_articles]

    def _convert_to_raw(self, article) -> RawArticle:
        return RawArticle(
            url=article.url,
            source=article.source,
            title=article.title,
            raw_text=getattr(article, 'content', '') or getattr(article, 'raw_text', ''),
            published_at=getattr(article, 'published_at', None),
            raw_html=getattr(article, 'raw_html', '')
        )

    def _persist_articles(self, articles: Iterable[RawArticle]):
        with get_session() as session:
            for raw in articles:
                if not raw.url or not raw.title:
                    continue

                exists = session.query(Article).filter(Article.url == raw.url).first()
                if exists:
                    continue

                article = Article(
                    url=raw.url,
                    source=raw.source,
                    title=raw.title,
                    body_text=raw.raw_text,
                    raw_html=raw.raw_html,
                    published_at=raw.published_at,
                )
                session.add(article)
        logger.info("Persisted articles")
