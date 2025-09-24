from __future__ import annotations

import logging
from datetime import datetime
from typing import List

import pandas as pd

from news_collectors.base_collector import BaseCollector, Article

logger = logging.getLogger(__name__)


class GDELTCollector(BaseCollector):
    """Fetch latest events from GDELT v2 and return Article objects."""

    def __init__(self, limit: int = 200):
        self.limit = limit

    async def collect(self) -> List[Article]:
        try:
            df = pd.read_csv(
                "http://data.gdeltproject.org/gdeltv2/lastupdate.txt",
                sep=" ",
                names=["datetime", "url"],
                engine="python"
            )
            if df.empty:
                return []
            latest_url = df.iloc[0]["url"]
            events = pd.read_csv(latest_url, sep="\t", header=None)
        except Exception as exc:
            logger.warning("Failed to download GDELT feed: %s", exc)
            return []

        articles: List[Article] = []
        for _, row in events.head(self.limit).iterrows():
            try:
                url = row[60]
                title = row[62]
                lang = row[14]
                if lang != "EN" or not url or not title:
                    continue
                articles.append(
                    Article(
                        title=title,
                        url=url,
                        source=row[60].split('/')[2] if '//' in row[60] else url,
                        content="",
                        summary=row[64] if len(row) > 64 else "",
                        published_at=datetime.utcnow(),
                        language="en"
                    )
                )
            except Exception:
                continue
        return articles
