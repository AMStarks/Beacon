from __future__ import annotations

import dataclasses
import threading
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class DomainIngestionStats:
    fetched: int = 0
    successes: int = 0
    failures: int = 0
    last_error: Optional[str] = None
    cumulative_bytes: int = 0
    last_fetch_at: Optional[datetime] = None

    def record_fetch(self, success: bool, content_length: int = 0, error: str | None = None):
        self.fetched += 1
        if success:
            self.successes += 1
            self.cumulative_bytes += max(content_length, 0)
        else:
            self.failures += 1
            self.last_error = error
        self.last_fetch_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, object]:
        return {
            "fetched": self.fetched,
            "successes": self.successes,
            "failures": self.failures,
            "last_error": self.last_error,
            "cumulative_bytes": self.cumulative_bytes,
            "last_fetch_at": self.last_fetch_at.isoformat() if self.last_fetch_at else None,
            "avg_bytes": self.cumulative_bytes // self.successes if self.successes else 0,
        }


@dataclass
class IngestionMetrics:
    domain_stats: Dict[str, DomainIngestionStats] = field(default_factory=lambda: defaultdict(DomainIngestionStats))
    total_articles: int = 0
    last_cycle_articles: int = 0
    last_cycle_started_at: Optional[datetime] = None
    last_cycle_completed_at: Optional[datetime] = None
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def start_cycle(self):
        with self.lock:
            self.last_cycle_started_at = datetime.utcnow()
            self.last_cycle_articles = 0

    def record_article(self, domain: str, content_length: int):
        with self.lock:
            stats = self.domain_stats[domain]
            stats.record_fetch(True, content_length=content_length)
            self.total_articles += 1
            self.last_cycle_articles += 1

    def record_failure(self, domain: str, error: str | None = None):
        with self.lock:
            stats = self.domain_stats[domain]
            stats.record_fetch(False, error=error)

    def complete_cycle(self):
        with self.lock:
            self.last_cycle_completed_at = datetime.utcnow()

    def snapshot(self) -> Dict[str, object]:
        with self.lock:
            return {
                "total_articles": self.total_articles,
                "last_cycle_articles": self.last_cycle_articles,
                "last_cycle_started_at": self.last_cycle_started_at.isoformat() if self.last_cycle_started_at else None,
                "last_cycle_completed_at": self.last_cycle_completed_at.isoformat() if self.last_cycle_completed_at else None,
                "domains": {domain: stats.to_dict() for domain, stats in self.domain_stats.items()},
            }


ingestion_metrics = IngestionMetrics()

