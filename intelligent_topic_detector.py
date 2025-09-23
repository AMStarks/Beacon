import re
import hashlib
import json
from typing import List, Dict, Set, Optional
from collections import Counter
import spacy
from dataclasses import dataclass
from datetime import datetime

from news_service import NewsArticle
from llm_service import LLMService

@dataclass
class IntelligentTopic:
    id: str
    title: str
    summary: str
    articles: List[NewsArticle]
    source_count: int
    source_names: List[str]
    is_hot_update: bool
    confidence_score: float
    last_updated: datetime
    created_at: datetime
    status: str = "active"

class IntelligentTopicDetector:
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        self.nlp = None
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("⚠️ SpaCy model 'en_core_web_sm' not found. Please run 'python -m spacy download en_core_web_sm'")
        
        self.source_tiers = {
            # Tier 1: Major news outlets (highest weight)
            'bbc': 1.0, 'ap': 1.0, 'reuters': 1.0, 'guardian': 1.0, 'npr': 1.0,
            'associated press': 1.0, 'the guardian': 1.0,
            
            # Tier 2: Secondary outlets (medium weight)
            'cnn': 0.8, 'fox': 0.8, 'abc': 0.8, 'cbs': 0.8, 'nbc': 0.8,
            'espn': 0.8, 'bloomberg': 0.8, 'wall street journal': 0.8,
            
            # Tier 3: Specialized/niche outlets (lower weight)
            'techcrunch': 0.6, 'wired': 0.6, 'ars technica': 0.6,
            'politico': 0.6, 'the hill': 0.6, 'axios': 0.6,
            
            # Default for unknown sources
            'default': 0.5
        }

    async def detect_topics(self, articles: List[NewsArticle]) -> List[IntelligentTopic]:
        """Use intelligent grouping to group articles by story."""
        print(f"🔍 INTELLIGENT DETECTOR: Processing {len(articles)} articles")
        
        if not articles:
            print("❌ ERROR: No articles provided")
            raise ValueError("No articles provided for intelligent topic detection")
        
        # Process articles in batches to avoid overwhelming the LLM
        batch_size = 20
        all_topics = []
        
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            print(f"📦 Processing batch {i//batch_size + 1}: {len(batch)} articles")
            
            batch_topics = await self._analyze_article_batch(batch)
            all_topics.extend(batch_topics)
        
        # Merge similar topics across batches
        merged_topics = await self._merge_similar_topics(all_topics)
        
        print(f"✅ INTELLIGENT DETECTION COMPLETE: {len(merged_topics)} topics from {len(articles)} articles")
        return merged_topics
    
    async def _analyze_article_batch(self, articles: List[NewsArticle]) -> List[IntelligentTopic]:
        """Analyze a batch of articles using intelligent grouping."""
        print(f"🔍 INTELLIGENT GROUPING: Analyzing {len(articles)} articles...")
        
        if not articles:
            print("❌ ERROR: No articles in batch")
            raise ValueError("No articles in batch for intelligent grouping")
        
        # Use keyword-based intelligent grouping (NO FALLBACKS)
        try:
            print("🧠 Using intelligent keyword-based grouping...")
            groups = self._intelligent_keyword_grouping(articles)
            
            print(f"📋 Generated {len(groups)} topic groups")
            
            # Convert groups to IntelligentTopic objects
            topics = []
            for group in groups:
                if not group.get("article_indices"):
                    print(f"⚠️ Skipping group with no article indices: {group}")
                    continue
                    
                # Get articles for this group
                group_articles = [articles[i] for i in group["article_indices"] if i < len(articles)]
                if not group_articles:
                    print(f"⚠️ Skipping group with no valid articles: {group}")
                    continue
                
                # Calculate source weights and names
                source_names = list(set([article.source for article in group_articles]))
                source_weights = [self._get_source_weight(source) for source in source_names]
                avg_confidence = sum(source_weights) / len(source_weights) if source_weights else 0.5
                
                # Create topic
                topic = IntelligentTopic(
                    id=hashlib.sha256(group["title"].encode()).hexdigest()[:12],
                    title=group["title"],
                    summary=group["summary"],
                    articles=group_articles,
                    source_count=len(group_articles),
                    source_names=source_names,
                    is_hot_update=group.get("is_hot_update", False),
                    confidence_score=avg_confidence * group.get("confidence", 0.8),
                    last_updated=datetime.now(),
                    created_at=datetime.now()
                )
                
                topics.append(topic)
                print(f"✅ Created topic: {topic.title} ({len(group_articles)} articles, {len(source_names)} sources)")
            
            return topics
            
        except Exception as e:
            print(f"❌ INTELLIGENT GROUPING FAILED: {e}")
            print(f"❌ NO FALLBACK - RAISING ERROR")
            raise RuntimeError(f"Intelligent topic grouping failed: {e}")
    
    def _intelligent_keyword_grouping(self, articles: List[NewsArticle]) -> List[Dict]:
        """Intelligent keyword-based grouping with NO FALLBACKS."""
        print(f"🧠 INTELLIGENT KEYWORD GROUPING: Processing {len(articles)} articles")
        
        if not articles:
            print("❌ ERROR: No articles for keyword grouping")
            raise ValueError("No articles provided for keyword grouping")
        
        groups = []
        used_articles = set()
        
        for i, article in enumerate(articles):
            if i in used_articles:
                continue
                
            print(f"🔍 Analyzing article {i+1}/{len(articles)}: {article.title[:50]}...")
            
            # Find similar articles based on intelligent keyword analysis
            similar_indices = [i]
            article_keywords = self._extract_meaningful_keywords(article.title)
            
            for j, other_article in enumerate(articles[i+1:], i+1):
                if j in used_articles:
                    continue
                    
                other_keywords = self._extract_meaningful_keywords(other_article.title)
                
                if not article_keywords or not other_keywords:
                    continue
                
                # Calculate intelligent similarity
                similarity = self._calculate_semantic_similarity(article_keywords, other_keywords)
                
                # If similar enough, group together
                if similarity > 0.4:  # 40% semantic similarity threshold
                    similar_indices.append(j)
                    used_articles.add(j)
                    print(f"  ✅ Grouped with article {j+1}: {other_article.title[:50]}... (similarity: {similarity:.2f})")
            
            used_articles.add(i)
            
            # Create intelligent group
            group_articles = [articles[idx] for idx in similar_indices]
            group_title = self._create_intelligent_title(group_articles)
            group_summary = self._create_intelligent_summary(group_articles)
            
            groups.append({
                "title": group_title,
                "summary": group_summary,
                "article_indices": similar_indices,
                "is_hot_update": False,
                "confidence": 0.8
            })
            
            print(f"  📋 Created group: {group_title} ({len(group_articles)} articles)")
        
        print(f"✅ INTELLIGENT KEYWORD GROUPING COMPLETE: {len(groups)} groups from {len(articles)} articles")
        return groups
    
    def _extract_meaningful_keywords(self, title: str) -> Set[str]:
        """Extract meaningful keywords from a title."""
        if not title:
            return set()
        
        # Convert to lowercase and split
        words = title.lower().split()
        
        # Remove common words that don't add meaning
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those',
            'into', 'onto', 'upon', 'over', 'under', 'above', 'below', 'between', 'among', 'through', 'during',
            'before', 'after', 'since', 'until', 'within', 'without', 'against', 'from', 'up', 'down', 'out',
            'off', 'away', 'back', 'here', 'there', 'where', 'when', 'why', 'how', 'what', 'who', 'which'
        }
        
        # Filter out stop words and short words
        meaningful_words = {word for word in words if len(word) > 2 and word not in stop_words}
        
        return meaningful_words
    
    def _calculate_semantic_similarity(self, keywords1: Set[str], keywords2: Set[str]) -> float:
        """Calculate semantic similarity between two sets of keywords."""
        if not keywords1 or not keywords2:
            return 0.0
        
        # Calculate Jaccard similarity
        intersection = len(keywords1.intersection(keywords2))
        union = len(keywords1.union(keywords2))
        
        if union == 0:
            return 0.0
        
        jaccard_similarity = intersection / union
        
        # Boost similarity for important keywords (names, places, etc.)
        important_keywords = {'trump', 'biden', 'china', 'russia', 'ukraine', 'israel', 'palestine', 'nfl', 'nba', 'mlb', 'nhl'}
        important_intersection = len(keywords1.intersection(keywords2).intersection(important_keywords))
        
        if important_intersection > 0:
            jaccard_similarity += 0.2  # Boost for important keywords
        
        return min(1.0, jaccard_similarity)
    
    def _create_intelligent_title(self, articles: List[NewsArticle]) -> str:
        """Create an intelligent title for a group of articles."""
        if not articles:
            return "Unknown Topic"
        
        # Use the first article's title as base
        base_title = articles[0].title
        
        # Clean up the title
        title = base_title.strip()
        
        # Remove common suffixes that don't add value
        suffixes_to_remove = [
            ' - cbs sports', ' - espn', ' - nfl', ' - nba', ' - mlb', ' - nhl',
            ' - fox news', ' - cnn', ' - abc news', ' - nbc news', ' - reuters',
            ' - associated press', ' - the guardian', ' - bbc news', ' - npr'
        ]
        
        for suffix in suffixes_to_remove:
            if title.lower().endswith(suffix.lower()):
                title = title[:-len(suffix)].strip()
                break
        
        # Ensure title is not too long
        if len(title) > 80:
            title = title[:77] + "..."
        
        return title
    
    def _create_intelligent_summary(self, articles: List[NewsArticle]) -> str:
        """Create an intelligent summary for a group of articles."""
        if not articles:
            return "No summary available"
        
        source_count = len(set(article.source for article in articles))
        return f"Coverage from {source_count} sources on this developing story."
    
    async def _merge_similar_topics(self, topics: List[IntelligentTopic]) -> List[IntelligentTopic]:
        """Merge similar topics to prevent duplicates."""
        print(f"🔄 MERGING SIMILAR TOPICS: {len(topics)} topics to analyze")
        
        if not topics:
            return []
        
        merged_topics = []
        used_topics = set()
        
        for i, topic in enumerate(topics):
            if i in used_topics:
                continue
            
            # Find similar topics to merge
            similar_indices = [i]
            topic_keywords = self._extract_meaningful_keywords(topic.title)
            
            for j, other_topic in enumerate(topics[i+1:], i+1):
                if j in used_topics:
                    continue
                
                other_keywords = self._extract_meaningful_keywords(other_topic.title)
                similarity = self._calculate_semantic_similarity(topic_keywords, other_keywords)
                
                if similarity > 0.6:  # 60% similarity for merging
                    similar_indices.append(j)
                    used_topics.add(j)
                    print(f"  🔗 Merging topics: {topic.title} + {other_topic.title} (similarity: {similarity:.2f})")
            
            used_topics.add(i)
            
            # Create merged topic
            if len(similar_indices) > 1:
                # Merge multiple topics
                all_articles = []
                all_sources = set()
                for idx in similar_indices:
                    all_articles.extend(topics[idx].articles)
                    all_sources.update(topics[idx].source_names)
                
                merged_topic = IntelligentTopic(
                    id=hashlib.sha256(topic.title.encode()).hexdigest()[:12],
                    title=topic.title,  # Use the first topic's title
                    summary=f"Comprehensive coverage from {len(all_sources)} sources",
                    articles=all_articles,
                    source_count=len(all_articles),
                    source_names=list(all_sources),
                    is_hot_update=topic.is_hot_update,
                    confidence_score=topic.confidence_score,
                    last_updated=datetime.now(),
                    created_at=topic.created_at
                )
                
                merged_topics.append(merged_topic)
                print(f"  ✅ Merged {len(similar_indices)} topics into: {merged_topic.title}")
            else:
                # Keep single topic as-is
                merged_topics.append(topic)
                print(f"  ✅ Kept single topic: {topic.title}")
        
        print(f"✅ TOPIC MERGING COMPLETE: {len(merged_topics)} final topics")
        return merged_topics
    
    def _get_source_weight(self, source: str) -> float:
        """Get weight for a source based on hierarchy."""
        source_lower = source.lower()
        
        # Check for exact matches first
        if source_lower in self.source_tiers:
            return self.source_tiers[source_lower]
        
        # Check for partial matches
        for known_source, weight in self.source_tiers.items():
            if known_source in source_lower or source_lower in known_source:
                return weight
        
        # Default weight for unknown sources
        return self.source_tiers['default']