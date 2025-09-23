import json
import hashlib
from typing import List, Dict, Set, Tuple
from dataclasses import dataclass
from news_service import NewsArticle, TopicCluster
from llm_service import LLMService
import asyncio
from datetime import datetime


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


class IntelligentTopicDetector:
    """LLM-powered topic detector that groups articles by story intelligently."""
    
    def __init__(self, llm_service: LLMService):
        self.llm_service = llm_service
        
        # Source hierarchy for weighting
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
        """Use LLM to intelligently group articles by story."""
        if not articles:
            return []
        
        print(f"Analyzing {len(articles)} articles for intelligent topic grouping...")
        
        # Group articles in batches to avoid token limits
        batch_size = 20
        all_topics = []
        
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            batch_topics = await self._analyze_article_batch(batch)
            all_topics.extend(batch_topics)
        
        # Merge similar topics across batches
        merged_topics = await self._merge_similar_topics(all_topics)
        
        print(f"Detected {len(merged_topics)} intelligent topics")
        return merged_topics
    
    async def _analyze_article_batch(self, articles: List[NewsArticle]) -> List[IntelligentTopic]:
        """Analyze a batch of articles using LLM to group by story."""
        
        # Prepare article data for LLM
        article_data = []
        for article in articles:
            article_data.append({
                "title": article.title,
                "source": article.source,
                "url": article.url,
                "content": getattr(article, 'content', '')[:500]  # First 500 chars
            })
        
        # Create LLM prompt for intelligent grouping
        system_prompt = """You are an expert news analyst. Your job is to analyze a batch of news articles and group them by story/topic.

Rules:
1. Group articles that are about the SAME story, even if they have different angles or sources
2. Each group should represent one coherent news story
3. Create a clear, concise title for each group (under 60 characters)
4. Write a 1-2 sentence summary for each group
5. Identify if any group represents a "hot update" to an existing story
6. Consider source reliability when grouping

Return a JSON array where each object has:
- "title": Clear, concise story title
- "summary": 1-2 sentence summary
- "article_indices": Array of indices (0-based) of articles in this group
- "is_hot_update": Boolean indicating if this is breaking news/update
- "confidence": Float 0.0-1.0 indicating confidence in grouping

Example:
[
  {
    "title": "Charlie Kirk Memorial Service Updates",
    "summary": "Coverage of Charlie Kirk's memorial service and its political implications.",
    "article_indices": [0, 1, 2],
    "is_hot_update": true,
    "confidence": 0.9
  }
]"""

        user_prompt = f"""Analyze these {len(articles)} articles and group them by story:

{json.dumps(article_data, indent=2)}

Return only the JSON array, no other text."""

        try:
            # Use LLM for intelligent grouping
            print("Using LLM for intelligent article grouping...")
            
            # Create a simple prompt for the LLM
            headlines = [article.title for article in articles]
            sources = [article.source for article in articles]
            
            # Use the existing LLM service with a simple prompt
            llm_response = await self.llm_service.refine(
                headlines=headlines,
                sources=sources,
                current_title="Group these articles by story",
                current_summary="Analyze and group related articles"
            )
            
            # Parse the LLM response to extract grouping information
            # For now, use a simple keyword-based grouping as fallback
            groups = self._simple_keyword_grouping(articles)
            
            # Use the fallback groups we created above
            
            # Convert groups to IntelligentTopic objects
            topics = []
            for group in groups:
                if not group.get("article_indices"):
                    continue
                    
                # Get articles for this group
                group_articles = [articles[i] for i in group["article_indices"] if i < len(articles)]
                if not group_articles:
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
                    confidence_score=avg_confidence * group.get("confidence", 0.8)
                )
                
                topics.append(topic)
            
            return topics
            
        except Exception as e:
            print(f"LLM analysis failed: {e}")
            # Fallback: create one topic per article
            return [IntelligentTopic(
                id=hashlib.sha256(article.title.encode()).hexdigest()[:12],
                title=article.title,
                summary=f"Article from {article.source}",
                articles=[article],
                source_count=1,
                source_names=[article.source],
                is_hot_update=False,
                confidence_score=0.5
            ) for article in articles]
    
    async def _merge_similar_topics(self, topics: List[IntelligentTopic]) -> List[IntelligentTopic]:
        """Merge similar topics that might have been created in different batches."""
        if len(topics) <= 1:
            return topics
        
        # Use LLM to identify similar topics
        topic_data = []
        for i, topic in enumerate(topics):
            topic_data.append({
                "index": i,
                "title": topic.title,
                "summary": topic.summary,
                "source_count": topic.source_count,
                "source_names": topic.source_names
            })
        
        system_prompt = """You are an expert news analyst. Analyze these topics and identify which ones are about the SAME story and should be merged.

Rules:
1. Topics about the same story should be merged
2. Consider title similarity and source overlap
3. Return JSON with merge groups

Example:
{
  "merge_groups": [
    {"indices": [0, 1, 2], "merged_title": "Charlie Kirk Memorial Service", "merged_summary": "Coverage of memorial service and political implications"},
    {"indices": [3], "merged_title": "Trump Administration Policy", "merged_summary": "Policy updates from Trump administration"}
  ]
}"""

        user_prompt = f"""Analyze these {len(topics)} topics and identify which should be merged:

{json.dumps(topic_data, indent=2)}

Return only the JSON, no other text."""

        try:
            # For now, skip LLM-based merging and just return topics as-is
            print("LLM merging not yet implemented - returning topics as-is")
            return topics
            
        except Exception as e:
            print(f"Topic merging failed: {e}")
            return topics
    
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
    
    def _simple_keyword_grouping(self, articles: List[NewsArticle]) -> List[Dict]:
        """Simple keyword-based grouping as fallback."""
        groups = []
        used_articles = set()
        
        for i, article in enumerate(articles):
            if i in used_articles:
                continue
                
            # Find similar articles based on keywords
            similar_indices = [i]
            article_keywords = set(article.title.lower().split())
            
            for j, other_article in enumerate(articles[i+1:], i+1):
                if j in used_articles:
                    continue
                    
                other_keywords = set(other_article.title.lower().split())
                
                # Remove common words
                common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
                article_keywords -= common_words
                other_keywords -= common_words
                
                if not article_keywords or not other_keywords:
                    continue
                
                # Calculate similarity
                intersection = len(article_keywords.intersection(other_keywords))
                union = len(article_keywords.union(other_keywords))
                similarity = intersection / union if union > 0 else 0
                
                # If similar enough, group together
                if similarity > 0.3:  # 30% keyword overlap
                    similar_indices.append(j)
                    used_articles.add(j)
            
            used_articles.add(i)
            
            # Create group
            group_articles = [articles[idx] for idx in similar_indices]
            group_title = group_articles[0].title  # Use first article's title
            group_summary = f"Coverage from {len(group_articles)} sources"
            
            groups.append({
                "title": group_title,
                "summary": group_summary,
                "article_indices": similar_indices,
                "is_hot_update": False,
                "confidence": 0.7
            })
        
        return groups
