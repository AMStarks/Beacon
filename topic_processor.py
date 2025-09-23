"""
Topic Processing Layer
Implements the second layer of the Beacon architecture - LLM-powered topic detection and grouping
"""

import os
import json
import hashlib
from typing import List, Dict, Any
from datetime import datetime
import httpx

class TopicProcessor:
    """Processes articles into topics using LLM intelligence"""
    
    def __init__(self):
        self.llm_api_key = os.getenv('GROK_API_KEY')
        self.llm_enabled = bool(self.llm_api_key and os.getenv('LLM_TITLES', '0') == '1')
        
        # Source hierarchy for weighting
        self.source_tiers = {
            'bbc': 1.0, 'ap': 1.0, 'reuters': 1.0, 'guardian': 1.0, 'npr': 1.0,
            'associated press': 1.0, 'the guardian': 1.0,
            'cnn': 0.8, 'fox': 0.8, 'abc': 0.8, 'cbs': 0.8, 'nbc': 0.8,
            'espn': 0.8, 'bloomberg': 0.8, 'wall street journal': 0.8,
            'techcrunch': 0.6, 'wired': 0.6, 'politico': 0.6,
            'default': 0.5
        }
    
    async def process_articles(self, articles: List) -> List[Dict[str, Any]]:
        """Main method to process articles into topics"""
        if not articles:
            return []
        
        print(f"🧠 Processing {len(articles)} articles into topics...")
        
        if self.llm_enabled:
            # Use LLM for intelligent topic grouping
            topics = await self._llm_topic_grouping(articles)
        else:
            # Fallback to simple keyword-based grouping
            topics = self._simple_topic_grouping(articles)
        
        print(f"✅ Created {len(topics)} topics from {len(articles)} articles")
        return topics
    
    async def _llm_topic_grouping(self, articles: List) -> List[Dict[str, Any]]:
        """Use LLM to intelligently group articles by story"""
        print("🤖 Using LLM for intelligent topic grouping...")
        
        # Prepare article data for LLM
        article_data = []
        for i, article in enumerate(articles):
            article_data.append({
                "index": i,
                "title": article.title,
                "source": article.source,
                "url": article.url,
                "content": getattr(article, 'content', '')[:500]  # First 500 chars
            })
        
        # Create LLM prompt
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
            # Call Grok API
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.llm_api_key}"
                    },
                    json={
                        "model": "grok-4-latest",
                        "stream": False,
                        "temperature": 0,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    llm_response = result['choices'][0]['message']['content']
                    
                    # Parse LLM response
                    try:
                        groups = json.loads(llm_response)
                        return self._convert_groups_to_topics(groups, articles)
                    except json.JSONDecodeError:
                        print("❌ Failed to parse LLM response as JSON")
                        return self._simple_topic_grouping(articles)
                else:
                    print(f"❌ LLM API error: {response.status_code}")
                    return self._simple_topic_grouping(articles)
                    
        except Exception as e:
            print(f"❌ LLM processing failed: {e}")
            return self._simple_topic_grouping(articles)
    
    def _simple_topic_grouping(self, articles: List) -> List[Dict[str, Any]]:
        """Fallback: Simple keyword-based topic grouping"""
        print("📝 Using simple keyword-based grouping...")
        
        groups = []
        used_articles = set()
        
        for i, article in enumerate(articles):
            if i in used_articles:
                continue
                
            # Find similar articles based on keywords
            similar_indices = [i]
            article_keywords = self._extract_keywords(article.title)
            
            for j, other_article in enumerate(articles[i+1:], i+1):
                if j in used_articles:
                    continue
                    
                other_keywords = self._extract_keywords(other_article.title)
                similarity = self._calculate_similarity(article_keywords, other_keywords)
                
                if similarity > 0.3:  # 30% similarity threshold
                    similar_indices.append(j)
                    used_articles.add(j)
            
            used_articles.add(i)
            
            # Create group
            group_articles = [articles[idx] for idx in similar_indices]
            group_title = self._create_topic_title(group_articles)
            group_summary = self._create_topic_summary(group_articles)
            
            groups.append({
                "title": group_title,
                "summary": group_summary,
                "article_indices": similar_indices,
                "is_hot_update": False,
                "confidence": 0.7
            })
        
        return self._convert_groups_to_topics(groups, articles)
    
    def _convert_groups_to_topics(self, groups: List[Dict], articles: List) -> List[Dict[str, Any]]:
        """Convert LLM groups into topic objects"""
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
            topic = {
                "id": hashlib.sha256(group["title"].encode()).hexdigest()[:12],
                "title": group["title"],
                "summary": group["summary"],
                "articles": group_articles,
                "source_count": len(group_articles),
                "source_names": source_names,
                "is_hot_update": group.get("is_hot_update", False),
                "confidence_score": avg_confidence * group.get("confidence", 0.8),
                "last_updated": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "status": "active"
            }
            
            topics.append(topic)
        
        return topics
    
    def _extract_keywords(self, title: str) -> set:
        """Extract meaningful keywords from a title"""
        if not title:
            return set()
        
        words = title.lower().split()
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'
        }
        
        meaningful_words = {word for word in words if len(word) > 2 and word not in stop_words}
        return meaningful_words
    
    def _calculate_similarity(self, keywords1: set, keywords2: set) -> float:
        """Calculate similarity between two sets of keywords"""
        if not keywords1 or not keywords2:
            return 0.0
        
        intersection = len(keywords1.intersection(keywords2))
        union = len(keywords1.union(keywords2))
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _create_topic_title(self, articles: List) -> str:
        """Create a topic title from articles"""
        if not articles:
            return "Unknown Topic"
        
        # Use the first article's title as base
        base_title = articles[0].title
        
        # Clean up the title
        title = base_title.strip()
        
        # Remove common suffixes
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
    
    def _create_topic_summary(self, articles: List) -> str:
        """Create a topic summary from articles"""
        if not articles:
            return "No summary available"
        
        source_count = len(set(article.source for article in articles))
        return f"Coverage from {source_count} sources on this developing story."
    
    def _get_source_weight(self, source: str) -> float:
        """Get weight for a source based on hierarchy"""
        source_lower = source.lower()
        
        if source_lower in self.source_tiers:
            return self.source_tiers[source_lower]
        
        for known_source, weight in self.source_tiers.items():
            if known_source in source_lower or source_lower in known_source:
                return weight
        
        return self.source_tiers['default']
