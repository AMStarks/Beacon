"""
Enhanced Title Generator (heuristic version)
Provides lightweight headline/summary helpers without requiring a local LLM
"""

import re
from difflib import SequenceMatcher
from collections import Counter
from typing import List

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
WORD_SPLIT = re.compile(r"[^a-zA-Z0-9']+")
STOP_WORDS = {
    'the','a','an','and','or','but','in','on','at','to','for','of','with','by','is','are','was','were',
    'be','been','has','have','had','do','does','did','will','would','could','should','may','might','can',
    'must','shall','this','that','these','those','from','about','into','as','over','after','before','new'
}


def _split_sentences(text: str) -> List[str]:
    text = (text or '').strip()
    if not text:
        return []
    sentences = SENTENCE_SPLIT.split(text)
    return [s.strip() for s in sentences if s.strip()]


def summarize_article(title: str, body: str, max_sentences: int = 2, max_chars: int = 320) -> str:
    """Return a short summary by taking the first informative sentences."""
    candidates = _split_sentences(body) or _split_sentences(title) or [body or title]
    summary_parts: List[str] = []
    for sentence in candidates:
        if len(summary_parts) >= max_sentences:
            break
        if len(sentence) < 20 and len(candidates) > 1:
            continue
        summary_parts.append(sentence)
    summary = ' '.join(summary_parts)[:max_chars]
    return summary.strip()


def _tokenize(text: str) -> List[str]:
    return [token.lower() for token in WORD_SPLIT.split(text or '') if token and token.lower() not in STOP_WORDS]


def select_representative_title(titles: List[str]) -> str:
    """Pick the title that is most similar to all others (central headline)."""
    titles = [t.strip() for t in titles if t and t.strip()]
    if not titles:
        return "News Update"
    if len(titles) == 1:
        return titles[0]
    best_title = titles[0]
    best_score = -1.0
    for idx, title in enumerate(titles):
        score = 0.0
        for jdx, other in enumerate(titles):
            if idx == jdx:
                continue
            score += SequenceMatcher(None, title, other).ratio()
        if score > best_score:
            best_score = score
            best_title = title
    return best_title


def generate_keyword_glance(titles: List[str], contents: List[str], top_k: int = 4) -> str:
    """Fallback headline formed from most frequent keywords across titles/contents."""
    counter: Counter[str] = Counter()
    for text in titles + contents:
        counter.update(_tokenize(text))
    top_tokens = [token.capitalize() for token, _ in counter.most_common(top_k)]
    return ' '.join(top_tokens) if top_tokens else "News Update"


def generate_topic_title(titles: List[str], contents: List[str]) -> str:
    rep = select_representative_title(titles)
    if rep:
        return rep
    return generate_keyword_glance(titles, contents)


def generate_topic_summary(topic_title: str, article_summaries: List[str], max_sentences: int = 3) -> str:
    """Combine article summaries into a concise recap."""
    combined = ' '.join(summary for summary in article_summaries if summary)
    sentences = _split_sentences(combined)
    if not sentences:
        return topic_title
    selected: List[str] = []
    for sentence in sentences:
        if len(selected) >= max_sentences:
            break
        if sentence in selected:
            continue
        selected.append(sentence)
    return ' '.join(selected)[:480]


def clean_headline(headline: str) -> str:
    headline = ' '.join(headline.split())
    if not headline:
        return "News Update"
    if len(headline) > 80:
        headline = headline[:77] + '...'
    return headline


class EnhancedTitleGenerator:
    """Facade to keep compatibility with previous code."""

    def summarize_article(self, title: str, body: str) -> str:
        return summarize_article(title, body)

    def choose_title(self, titles: List[str], contents: List[str]) -> str:
        return clean_headline(generate_topic_title(titles, contents))

    def generate_topic_summary(self, topic_title: str, article_summaries: List[str]) -> str:
        return generate_topic_summary(topic_title, article_summaries)

    def build_topic_summary(self, topic_title: str, article_summaries: List[str]) -> str:
        return generate_topic_summary(topic_title, article_summaries)


enhanced_title_generator = EnhancedTitleGenerator()
