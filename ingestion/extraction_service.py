from __future__ import annotations

import logging
from typing import Optional

from bs4 import BeautifulSoup
from newspaper import Article as NPArticle
from readability import Document
import trafilatura

from ingestion.raw_article import RawArticle

logger = logging.getLogger(__name__)


class ExtractionService:
    def __init__(self, min_length: int = 400):
        self.min_length = min_length

    def extract(self, raw: RawArticle) -> RawArticle:
        text = raw.raw_text or ""

        if len(text) < self.min_length and raw.raw_html:
            readability_text = self._readability_extract(raw.raw_html)
            if len(readability_text) > len(text):
                text = readability_text

        if len(text) < self.min_length and raw.url:
            newspaper_text = self._newspaper_extract(raw.url)
            if len(newspaper_text) > len(text):
                text = newspaper_text

        if len(text) < self.min_length and raw.raw_html:
            trafilatura_text = self._trafilatura_extract(raw.raw_html)
            if len(trafilatura_text) > len(text):
                text = trafilatura_text

        raw.raw_text = text
        return raw

    def _readability_extract(self, html: str) -> str:
        try:
            doc = Document(html)
            summary_html = doc.summary(html_partial=True)
            return BeautifulSoup(summary_html, 'html.parser').get_text(separator=' ').strip()
        except Exception:
            return ""

    def _newspaper_extract(self, url: str) -> str:
        try:
            article = NPArticle(url)
            article.download()
            article.parse()
            return article.text
        except Exception as exc:
            logger.debug("newspaper failed for %s: %s", url, exc)
            return ""

    def _trafilatura_extract(self, html: str) -> str:
        try:
            result = trafilatura.extract(html)
            return result or ""
        except Exception as exc:
            logger.debug("trafilatura failed: %s", exc)
            return ""
