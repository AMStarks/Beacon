"""
Topic Processing Layer - Local LLM Version
Implements the second layer of the Beacon architecture using local GPT-2 for topic detection and grouping
"""

import asyncio
import json
import hashlib
from typing import List, Dict, Any
from datetime import datetime
from local_llm_service import local_llm
from enhanced_title_generator import enhanced_title_generator

class TopicProcessor:
    """Processes articles into topics using local LLM intelligence"""
    
    def __init__(self):
        self.llm_enabled = True  # Always use local LLM now
        
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
        
        print(f"🧠 Processing {len(articles)} articles into topics using local LLM...")
        
        try:
            # Group articles by similarity first
            grouped_articles = self._group_articles_by_similarity(articles)
            
            topics = []
            for group in grouped_articles:
                if not group:
                    continue
                    
                # Create topic from article group
                topic = await self._create_topic_from_group(group)
                if topic:
                    topics.append(topic)
            
            print(f"✅ Created {len(topics)} topics from {len(articles)} articles")
            return topics
            
        except Exception as e:
            print(f"❌ Error processing articles: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _group_articles_by_similarity(self, articles: List) -> List[List]:
        """Simple grouping by title similarity"""
        groups = []
        used_articles = set()
        
        for i, article in enumerate(articles):
            if i in used_articles:
                continue
                
            group = [article]
            used_articles.add(i)
            
            # Find similar articles
            for j, other_article in enumerate(articles[i+1:], i+1):
                if j in used_articles:
                    continue
                    
                if self._are_similar(article, other_article):
                    group.append(other_article)
                    used_articles.add(j)
            
            groups.append(group)
        
        return groups
    
    def _are_similar(self, article1, article2) -> bool:
        """Check if two articles are similar"""
        # Handle NewsArticle objects - they have .title attribute
        title1 = getattr(article1, 'title', '').lower()
        title2 = getattr(article2, 'title', '').lower()
        
        # Simple keyword matching
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        # If they share significant words, consider them similar
        common_words = words1.intersection(words2)
        return len(common_words) >= 2
    
    async def _create_topic_from_group(self, articles: List) -> Dict[str, Any]:
        """Create a topic from a group of articles using local LLM"""
        if not articles:
            return None
            
        try:
            # Prepare text for LLM - handle NewsArticle objects
            articles_text = '\n\n'.join([
                f"Headline: {getattr(article, 'title', 'No title')}\n"
                f"Source: {getattr(article, 'source', 'Unknown source')}\n"
                f"Body: {getattr(article, 'content', '')[:1500]}"
                for article in articles
            ])
            has_multiple_articles = len(articles) > 1
            
            # Generate title and summary using enhanced title generator
            if has_multiple_articles:
                title = await enhanced_title_generator.generate_title(articles_text)
            else:
                title = enhanced_title_generator.clean_headline(getattr(articles[0], 'title', 'News Update'))
            summary = await enhanced_title_generator.generate_summary(articles_text)
            
            # Calculate source weights and names
            source_names = list({getattr(article, 'source', 'Unknown') for article in articles})
            source_weights = [self._get_source_weight(source) for source in source_names]
            avg_confidence = sum(source_weights) / len(source_weights) if source_weights else 0.5
            
            # Create topic
            topic = {
                'id': hashlib.sha256(title.encode()).hexdigest()[:12],
                'title': title,
                'canonical_title': title,
                'summary': summary,
                'sources': articles,
                'source_names': source_names,
                'status': 'active',
                'created_at': getattr(articles[0], 'published_at', datetime.now().isoformat()),
                'article_count': len(articles),
                'confidence_score': avg_confidence,
                'last_updated': datetime.now().isoformat()
            }
            
            return topic
            
        except Exception as e:
            print(f"❌ Error creating topic: {e}")
            import traceback
            traceback.print_exc()
            return None
    
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
        try:
            sources = topic.get('sources', [])
            articles_text = '\n'.join([
                f"{getattr(article, 'title', 'No title')} - {getattr(article, 'source', 'Unknown source')}"
                for article in sources
            ])
            
            return await local_llm.generate_summary(articles_text)
            
        except Exception as e:
            print(f"❌ Error generating LLM summary: {e}")
            return f"Summary generation failed: {e}"
