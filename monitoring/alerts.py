from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, List, Literal


@dataclass
class AlertRecord:
    timestamp: datetime
    level: Literal["info", "warning", "error"]
    message: str
    source: str

    def as_dict(self) -> Dict[str, str]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "message": self.message,
            "source": self.source,
        }


class AlertManager:
    def __init__(self, max_entries: int = 50, cooldown_seconds: int = 300):
        self.logger = logging.getLogger("alerts")
        self.max_entries = max_entries
        self.cooldown_seconds = cooldown_seconds
        self._recent_alerts: Deque[AlertRecord] = deque(maxlen=max_entries)
        self._last_emitted: Dict[str, float] = {}

    def _should_emit(self, key: str) -> bool:
        now = time.monotonic()
        last = self._last_emitted.get(key, 0.0)
        if now - last >= self.cooldown_seconds:
            self._last_emitted[key] = now
            return True
        return False

    def record_failure(self, source: str, message: str):
        key = f"failure:{source}"
        if self._should_emit(key):
            text = f"{source} failure: {message}"
            self.logger.warning(text)
            self._append("warning", text, source)

    def record_low_volume(self, count: int, minimum_expected: int):
        key = "low_volume"
        if count >= minimum_expected:
            return
        if self._should_emit(f"{key}:{minimum_expected}"):
            text = f"Low article volume detected: {count} articles collected (expected ≥ {minimum_expected})"
            self.logger.warning(text)
            self._append("warning", text, "ingestion")

    def record_info(self, source: str, message: str):
        text = f"{source}: {message}"
        self.logger.info(text)
        self._append("info", text, source)

    def _append(self, level: str, message: str, source: str):
        self._recent_alerts.appendleft(
            AlertRecord(
                timestamp=datetime.utcnow(),
                level=level,
                message=message,
                source=source,
            )
        )

    def get_recent_alerts(self) -> List[Dict[str, str]]:
        return [record.as_dict() for record in list(self._recent_alerts)]


alert_manager = AlertManager()

