from __future__ import annotations

import logging
from typing import Iterable, List

from ingestion.raw_article import RawArticle
from ingestion.extraction_service import ExtractionService
from monitoring import ingestion_metrics
from news_collectors import (
    NewsPleaseCollector,
    GDELTCollector,
    RSSCollector,
    DomainSourceConfig,
    Article as CollectorArticle,
)
from storage.database import get_session
from storage.models import Article
from collector_registry import COLLECTOR_REGISTRY

logger = logging.getLogger(__name__)


class CollectorPipeline:
    def __init__(self):
        self.extractor = ExtractionService()

    async def run(self):
        ingestion_metrics.start_cycle()

        raw_articles: List[RawArticle] = []
        raw_articles.extend(await self._collect_seed_articles())
        raw_articles.extend(await self._collect_gdelt_articles())
        raw_articles.extend(await self._collect_domain_feeds())

        logger.info("Pipeline fetched %d raw articles", len(raw_articles))

        processed = [self.extractor.extract(raw) for raw in raw_articles]
        self._persist_articles(processed)
        ingestion_metrics.complete_cycle()

    async def _collect_seed_articles(self) -> List[RawArticle]:
        config = COLLECTOR_REGISTRY.get("newsplease_seed", {})
        urls = config.get("config", {}).get("seed_urls", [])
        collector = NewsPleaseCollector(urls)
        articles = await collector.collect()
        return [self._convert_to_raw(article) for article in articles]

    async def _collect_gdelt_articles(self) -> List[RawArticle]:
        config = COLLECTOR_REGISTRY.get("gdelt", {})
        limit = config.get("config", {}).get("limit", 200)
        collector = GDELTCollector(limit=limit)
        gdelt_articles = await collector.collect()
        return [self._convert_to_raw(article) for article in gdelt_articles]

    async def _collect_domain_feeds(self) -> List[RawArticle]:
        config = COLLECTOR_REGISTRY.get("domain_feeds", {})
        domains: dict[str, DomainSourceConfig] = config.get("domains", {})
        raw_articles: List[RawArticle] = []

        for name, domain_config in domains.items():
            try:
                collector = RSSCollector(domain_config)
                collector_articles = await collector.collect()
                logger.info(
                    "Domain feed %s yielded %d articles",
                    name,
                    len(collector_articles),
                )
                raw_articles.extend(
                    self._convert_to_raw(article) for article in collector_articles
                )
            except Exception as exc:
                logger.warning("Domain feed %s failed: %s", name, exc)

        return raw_articles

    def _convert_to_raw(self, article: CollectorArticle) -> RawArticle:
        return RawArticle(
            url=article.url,
            source=article.source,
            title=article.title,
            raw_text=getattr(article, 'content', ''),
            raw_html=getattr(article, 'raw_html', ''),
            meta=getattr(article, 'meta', {}) or {},
            published_at=getattr(article, 'published_at', None),
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
                    published_at=raw.published_at,
                )
                session.add(article)
                ingestion_metrics.record_article(raw.source, len(raw.raw_text))
        logger.info("Persisted articles")
