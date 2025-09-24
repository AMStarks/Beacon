from news_collectors import (
    NewspaperCollector,
    NewsPleaseCollector,
    GDELTCollector,
    RSSCollector,
    DomainSourceConfig,
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
    "domain_feeds": {
        "type": "rss",
        "domains": {
            "guardian": DomainSourceConfig(
                name="guardian",
                feed_url="https://www.theguardian.com/world/rss",
                source_name="The Guardian",
                article_limit=20,
            ),
            "smh": DomainSourceConfig(
                name="smh",
                feed_url="https://www.smh.com.au/rss/feed.xml",
                source_name="Sydney Morning Herald",
                article_limit=20,
            ),
            "abc_au": DomainSourceConfig(
                name="abc_au",
                feed_url="https://www.abc.net.au/news/feed/51120/rss.xml",
                source_name="ABC News (AU)",
                article_limit=20,
            ),
            "bbc": DomainSourceConfig(
                name="bbc",
                feed_url="https://feeds.bbci.co.uk/news/world/rss.xml",
                source_name="BBC News",
                article_limit=20,
            ),
        },
    },
}
