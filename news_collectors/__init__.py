from .base_collector import Article, BaseCollector
from .newsplease_collector import NewsPleaseCollector
from .gdelt_collector import GDELTCollector
from .rss_collector import RSSCollector, DomainSourceConfig

try:
    from .newspaper_collector import NewspaperCollector
except Exception as exc:  # pragma: no cover
    class NewspaperCollector:  # type: ignore
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "newspaper3k is unavailable in this environment"
            ) from exc

__all__ = [
    "Article",
    "BaseCollector",
    "NewsPleaseCollector",
    "GDELTCollector",
    "RSSCollector",
    "DomainSourceConfig",
    "NewspaperCollector",
]
