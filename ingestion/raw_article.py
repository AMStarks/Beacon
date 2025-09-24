from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class RawArticle:
    url: str
    source: str
    title: str
    raw_html: str = ""
    raw_text: str = ""
    meta: Dict[str, str] = field(default_factory=dict)
    summary_hint: str = ""
    published_at: Optional[datetime] = None
    fetched_at: datetime = field(default_factory=datetime.utcnow)
