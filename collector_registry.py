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
        "config": {
            "seed_urls": [
                "https://www.reuters.com/world/us/",
                "https://apnews.com/hub/ap-top-news",
                "https://www.npr.org/sections/news/",
                "https://www.politico.com/",
                "https://www.axios.com/",
                "https://www.ft.com/world/us",
            ]
        }
    },
    "newspaper": {
        "type": "extractor",
        "factory": NewspaperCollector,
    },
    "gdelt": {
        "type": "dataset",
        "factory": GDELTCollector,
        "config": {"limit": 300}
    },
}
