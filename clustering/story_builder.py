from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import List, Sequence

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from storage.database import get_session
from storage.models import Article, Story, StoryArticle
from summarization.llm_story_builder import build_story_headline, build_story_summary


class StoryBuilder:
    def __init__(self, similarity_threshold: float = 0.78):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.threshold = similarity_threshold

    async def run(self):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._process_articles)

    def _process_articles(self):
        with get_session() as session:
            articles: List[Article] = session.query(Article).filter(Article.body_text != None).all()  # noqa: E711

            embeddings = self.model.encode(
                [self._article_text(article) for article in articles],
                convert_to_numpy=True
            )

            for idx, article in enumerate(articles):
                embedding = embeddings[idx]
                story = self._find_matching_story(session, embedding)
                if story is None:
                    story = Story(
                        title=article.title,
                        summary=article.summary or article.body_text[:280],
                        topic_key=f"story-{article.id}",
                        centroid=embedding.tolist(),
                        created_at=datetime.utcnow(),
                    )
                    session.add(story)
                    session.flush()

                if not any(link.article_id == article.id for link in story.articles):
                    session.add(StoryArticle(story_id=story.id, article_id=article.id, relevance=1.0))
                    story.centroid = self._update_centroid(story.centroid, embedding)
                    story.updated_at = datetime.utcnow()

            session.flush()
            self._update_story_metadata(session)

    def _article_text(self, article: Article) -> str:
        return f"{article.title}\n{article.body_text}" if article.body_text else article.title

    def _find_matching_story(self, session, embedding: np.ndarray) -> Story | None:
        stories: Sequence[Story] = session.query(Story).all()
        if not stories:
            return None
        story_embeddings = np.array([story.centroid for story in stories])
        sims = cosine_similarity([embedding], story_embeddings)[0]
        best_idx = np.argmax(sims)
        if sims[best_idx] >= self.threshold:
            return stories[best_idx]
        return None

    def _update_centroid(self, centroid: List[float], new_embedding: np.ndarray) -> List[float]:
        centroid_vec = np.array(centroid)
        updated = (centroid_vec + new_embedding) / 2
        return updated.tolist()

    def _update_story_metadata(self, session):
        stories: List[Story] = session.query(Story).all()
        for story in stories:
            linked_articles = [link.article for link in story.articles]
            summaries = [article.summary or article.body_text[:280] for article in linked_articles if article.body_text]
            headline = asyncio.run(build_story_headline(story.title, summaries)) if summaries else story.title
            summary = asyncio.run(build_story_summary(headline, summaries)) if summaries else story.summary
            story.title = headline
            story.summary = summary
            story.updated_at = datetime.utcnow()
