"""
Topic Processing Layer - Local LLM Version
Implements the second layer of the Beacon architecture using local GPT-2 for topic detection and grouping
"""

import asyncio
import json
import hashlib
from typing import List, Dict, Any
from datetime import datetime
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from enhanced_title_generator import enhanced_title_generator

class TopicProcessor:
    """Processes articles into topics using local LLM intelligence"""
    
    def __init__(self):
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.similarity_threshold = 0.78
        self.source_tiers = {
            'bbc': 1.0, 'ap': 1.0, 'reuters': 1.0, 'guardian': 1.0, 'npr': 1.0,
            'associated press': 1.0, 'the guardian': 1.0,
            'cnn': 0.8, 'fox': 0.8, 'abc': 0.8, 'cbs': 0.8, 'nbc': 0.8,
            'espn': 0.8, 'bloomberg': 0.8, 'wall street journal': 0.8,
            'techcrunch': 0.6, 'wired': 0.6, 'politico': 0.6,
            'default': 0.5
        }
    
    async def process_articles(self, articles: List) -> List[Dict[str, Any]]:
        if not articles:
            return []

        print(f"🧠 Processing {len(articles)} articles with embedding clustering...")

        embeddings = self.embedding_model.encode([getattr(a, 'title', '') + " " + getattr(a, 'content', '') for a in articles])
        clusters = self._cluster_embeddings(embeddings)

        topics = []
        for cluster_indices in clusters:
            cluster_articles = [articles[i] for i in cluster_indices]
            topic = await self._create_topic_from_group(cluster_articles)
            if topic:
                topics.append(topic)

        print(f"✅ Created {len(topics)} topics from {len(articles)} articles")
        return topics

    def _cluster_embeddings(self, embeddings: List[np.ndarray]) -> List[List[int]]:
        clusters = []
        visited = set()

        for idx, emb in enumerate(embeddings):
            if idx in visited:
                continue

            cluster = [idx]
            visited.add(idx)
            sims = cosine_similarity([emb], embeddings)[0]
            related_indices = np.where(sims >= self.similarity_threshold)[0]
            for r_idx in related_indices:
                if r_idx not in visited:
                    cluster.append(r_idx)
                    visited.add(r_idx)

            clusters.append(cluster)

        return clusters

    async def _create_topic_from_group(self, articles: List) -> Dict[str, Any]:
        if not articles:
            return None

        try:
            article_entries = []
            article_summaries = []

            for article in articles:
                title = getattr(article, 'title', 'No Title')
                body = getattr(article, 'content', '')
                metadata = await enhanced_title_generator.generate_topic_metadata(title, body)
                article_entries.append({
                    'title': title,
                    'url': getattr(article, 'url', ''),
                    'source': getattr(article, 'source', 'Unknown'),
                    'summary': metadata['article_summary'],
                    'published_at': getattr(article, 'published_at', datetime.now().isoformat())
                })
                article_summaries.append(metadata['article_summary'])

            topic_title = enhanced_title_generator.clean_headline(metadata['topic_title'])
            topic_summary = await enhanced_title_generator.generate_topic_summary(topic_title, article_summaries)

            source_names = list({entry['source'] for entry in article_entries})
            confidence = self._average_confidence(source_names)

            topic_id = self._generate_topic_id(topic_title, article_entries)

            return {
                'id': topic_id,
                'title': topic_title,
                'canonical_title': topic_title,
                'summary': topic_summary,
                'sources': article_entries,
                'source_names': source_names,
                'article_count': len(article_entries),
                'status': 'active',
                'confidence_score': confidence,
                'created_at': article_entries[0]['published_at'],
                'last_updated': datetime.now().isoformat()
            }

        except Exception as e:
            print(f"❌ Error creating topic: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _average_confidence(self, source_names: List[str]) -> float:
        weights = [self._get_source_weight(name) for name in source_names]
        return sum(weights) / len(weights) if weights else 0.5

    def _generate_topic_id(self, title: str, entries: List[Dict[str, Any]]) -> str:
        key = title + ''.join(sorted(entry['url'] for entry in entries))
        return hashlib.sha256(key.encode()).hexdigest()[:12]

    def _get_source_weight(self, source: str) -> float:
        source_lower = (source or '').lower()
        if source_lower in self.source_tiers:
            return self.source_tiers[source_lower]

        for known_source, weight in self.source_tiers.items():
            if known_source in source_lower or source_lower in known_source:
                return weight

        return self.source_tiers['default']

    async def generate_llm_summary(self, topic: Dict[str, Any]) -> str:
        try:
            summaries = [source.get('summary', '') for source in topic.get('sources', [])]
            return await enhanced_title_generator.generate_topic_summary(topic.get('title', ''), summaries)
        except Exception as e:
            print(f"❌ Error generating LLM summary: {e}")
            return f"Summary generation failed: {e}"
