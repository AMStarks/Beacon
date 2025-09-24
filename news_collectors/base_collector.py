"""Common interfaces and helpers for news collectors"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List

logger = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    url: str
    source: str
    content: str = ""
    published_at: datetime | None = None
    summary: str = ""
    language: str = "en"
    category: str = "general"
    raw_html: str = ""
    meta: dict | None = None


class BaseCollector:
    """Abstract base class for all news collectors."""

    async def collect(self) -> List[Article]:
        raise NotImplementedError

    async def _with_timeout(self, coro, timeout: float = 30.0):
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("Collector task timed out")
            return None
