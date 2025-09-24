from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Float,
    ForeignKey,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(1024), unique=True, nullable=False)
    source = Column(String(255), index=True)
    title = Column(String(1024), nullable=False)
    body_text = Column(Text)
    raw_html = Column(Text)
    summary = Column(Text)
    language = Column(String(32), default="en")
    category = Column(String(64), default="general")
    author = Column(String(255))
    extra_metadata = Column(JSON, default=dict)
    published_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=datetime.utcnow)

    story_links = relationship("StoryArticle", back_populates="article")


class Story(Base):
    __tablename__ = "stories"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False)
    summary = Column(Text)
    topic_key = Column(String(255), unique=True)
    key_entities = Column(JSON, default=list)
    centroid = Column(JSON, default=list)
    status = Column(String(32), default="active")
    confidence_score = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    articles = relationship("StoryArticle", back_populates="story")


class StoryArticle(Base):
    __tablename__ = "story_articles"
    __table_args__ = (UniqueConstraint('story_id', 'article_id', name='_story_article_uc'),)

    id = Column(Integer, primary_key=True)
    story_id = Column(Integer, ForeignKey('stories.id'), nullable=False)
    article_id = Column(Integer, ForeignKey('articles.id'), nullable=False)
    relevance = Column(Float, default=0.0)

    story = relationship("Story", back_populates="articles")
    article = relationship("Article", back_populates="story_links")
