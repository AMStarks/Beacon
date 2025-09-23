"""
Topic Processing Layer
Implements the second layer of the Beacon architecture - LLM-powered topic detection and grouping
"""

import os
import json
import hashlib
import asyncio
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
        
        if not self.llm_enabled:
            raise Exception("❌ LLM is not enabled. GROK_API_KEY and LLM_TITLES=1 must be set.")
        
        # Use LLM for intelligent topic grouping - NO FALLBACKS
        topics = await self._llm_topic_grouping(articles)
        
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
3. Create a clear, concise title for each group (under 50 characters, be very brief)
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
            # Add longer delay to avoid rate limiting
            await asyncio.sleep(5)  # 5 second delay between LLM calls
            
            # Call Grok API with timeout
            async with httpx.AsyncClient(timeout=30.0) as client:
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
                    except json.JSONDecodeError as e:
                        raise Exception(f"❌ Failed to parse LLM response as JSON: {e}")
                elif response.status_code == 429:
                    raise Exception("⚠️ Rate limited by Grok API - no fallback available")
                else:
                    raise Exception(f"❌ LLM API error: {response.status_code} - {response.text}")
                    
        except Exception as e:
            raise Exception(f"❌ LLM processing failed: {e}")
    
    
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
    
    
    def _get_source_weight(self, source: str) -> float:
        """Get weight for a source based on hierarchy"""
        source_lower = source.lower()
        
        if source_lower in self.source_tiers:
            return self.source_tiers[source_lower]
        
        for known_source, weight in self.source_tiers.items():
            if known_source in source_lower or source_lower in known_source:
                return weight
        
        return self.source_tiers['default']
    
    async def generate_llm_summary(self, topic: Dict[str, Any]) -> str:
        """Generate LLM summary for a topic"""
        if not self.llm_enabled:
            return "LLM summarization is not enabled."
        
        # Prepare article data for LLM
        article_contents = []
        for article in topic.get('articles', []):
            article_contents.append(f"Source: {article.source}\nTitle: {article.title}\nContent: {getattr(article, 'content', '')[:500]}")
        
        combined_content = "\n\n---\n\n".join(article_contents)
        
        system_prompt = """You are an expert news summarizer. Create a concise, politically neutral summary of a news topic based on multiple articles.
        
        Rules:
        1. The summary should be 3-5 sentences long
        2. It must be strictly politically neutral and objective
        3. Synthesize information from all provided articles
        4. Focus on key facts and developments
        5. Do not include introductory or concluding remarks"""
        
        user_prompt = f"""Please provide a politically neutral summary for this news topic:
        
        Topic: {topic.get('title', 'Unknown Topic')}
        
        Articles:
        {combined_content}
        
        Provide only the summary text."""
        
        try:
            # Add longer delay to avoid rate limiting
            await asyncio.sleep(3)  # 3 second delay for summary calls
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.x.ai/v1/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.llm_api_key}"
                    },
                    json={
                        "model": "grok-4-latest",
                        "stream": False,
                        "temperature": 0.2,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ]
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result['choices'][0]['message']['content'].strip()
                else:
                    return f"Error generating summary: HTTP {response.status_code}"
                    
        except Exception as e:
            return f"Error generating summary: {e}"
