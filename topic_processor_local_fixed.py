"""
Topic Processing Layer - Heuristic Version
Groups articles by TF-IDF similarity and produces aggregate stories
"""

import asyncio
import hashlib
from typing import List, Dict, Any
from datetime import datetime

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

from enhanced_title_generator import enhanced_title_generator
from news_collectors.base_collector import Article


class TopicProcessor:
    """Processes articles into stories using TF-IDF clustering and heuristic summaries."""

    def __init__(self, similarity_threshold: float = 0.7):
        self.vectorizer = TfidfVectorizer(max_features=4096, stop_words="english")
        self.similarity_threshold = similarity_threshold

    async def process_articles(self, articles: List[Article]) -> List[Dict[str, Any]]:
        if not articles:
            return []

        print(f"🧠 Processing {len(articles)} articles using TF-IDF clustering...")
        loop = asyncio.get_running_loop()
        combined_text = [self._article_text(article) for article in articles]

        def _encode():
            return self.vectorizer.fit_transform(combined_text)

        matrix = await loop.run_in_executor(None, _encode)
        sims = cosine_similarity(matrix)

        clusters = self._density_cluster(sims)
        topics: List[Dict[str, Any]] = []
        for cluster_indices in clusters:
            cluster_articles = [articles[idx] for idx in cluster_indices]
            topic = self._create_story(cluster_articles)
            if topic:
                topics.append(topic)

        print(f"✅ Created {len(topics)} stories from {len(articles)} articles")
        return topics

    def _density_cluster(self, similarity_matrix: np.ndarray) -> List[List[int]]:
        n = similarity_matrix.shape[0]
        visited = set()
        clusters: List[List[int]] = []
        for idx in range(n):
            if idx in visited:
                continue
            cluster = [idx]
            visited.add(idx)
            neighbours = np.where(similarity_matrix[idx] >= self.similarity_threshold)[0]
            for neighbour in neighbours:
                if neighbour not in visited:
                    cluster.append(neighbour)
                    visited.add(neighbour)
            clusters.append(cluster)
        return clusters

    def _article_text(self, article: Article) -> str:
        parts = [getattr(article, 'title', '') or '']
        body = getattr(article, 'content', '') or ''
        if body:
            parts.append(body)
        return ' '.join(parts)

    def _create_story(self, articles: List[Article]) -> Dict[str, Any]:
        if not articles:
            return {}

        titles = [getattr(article, 'title', 'News Update') for article in articles]
        summaries = [enhanced_title_generator.summarize_article(getattr(article, 'title', ''), getattr(article, 'content', '')) for article in articles]
        title = enhanced_title_generator.choose_title(titles, [getattr(article, 'content', '') for article in articles])
        recap = enhanced_title_generator.build_topic_summary(title, summaries)
        topic_id = self._generate_topic_id(titles, articles)

        sources = []
        for article, summary in zip(articles, summaries):
            sources.append({
                "title": getattr(article, 'title', 'News Update'),
                "url": getattr(article, 'url', ''),
                "source": getattr(article, 'source', 'Unknown'),
                "summary": summary,
                "published_at": getattr(article, 'published_at', datetime.utcnow()).isoformat(),
            })

        return {
            "id": topic_id,
            "title": title,
            "canonical_title": title,
            "summary": recap,
            "sources": sources,
            "source_names": sorted({src["source"] for src in sources}),
            "article_count": len(sources),
            "status": "active",
            "confidence_score": min(0.9, 0.5 + 0.05 * len(sources)),
            "created_at": sources[0]["published_at"],
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _generate_topic_id(self, titles: List[str], articles: List[Article]) -> str:
        key = '::'.join(sorted(titles)) + ''.join(sorted(getattr(article, 'url', '') for article in articles))
        return hashlib.sha256(key.encode()).hexdigest()[:12]

    async def generate_llm_summary(self, topic: Dict[str, Any]) -> str:
        summaries = [source.get('summary', '') for source in topic.get('sources', [])]
        return enhanced_title_generator.build_topic_summary(topic.get('title', ''), summaries)
