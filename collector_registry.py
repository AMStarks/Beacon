from news_collectors import (
    NewspaperCollector,
    NewsPleaseCollector,
    GDELTCollector,
)

COLLECTOR_REGISTRY = {
    "news_api": {
        "type": "api",
        "class": "rate_limited_collector.NewsAPIBridge",
    },
    "newsdata": {
        "type": "api",
        "class": "rate_limited_collector.NewsDataBridge",
    },
    "newsplease_seed": {
        "type": "crawler",
        "factory": NewsPleaseCollector,
    },
    "newspaper": {
        "type": "extractor",
        "factory": NewspaperCollector,
    },
    "gdelt": {
        "type": "dataset",
        "factory": GDELTCollector,
    },
}
