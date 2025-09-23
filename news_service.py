import asyncio
import httpx
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import os
from dataclasses import dataclass
import hashlib
from enhanced_topic_detector import EnhancedTopicDetector
from entity_resolver import EntityResolver
from cache_store import CacheStore
from providers import NewsAPIProvider, NewsDataProvider, GuardianProvider, GNewsProvider
from llm_service import LLMService

@dataclass
class NewsArticle:
    title: str
    content: str
    url: str
    source: str
    published_at: datetime
    category: str
    country: str
    language: str
    sentiment: Optional[str] = None
    topics: List[str] = None

@dataclass
class TopicCluster:
    id: str
    title: str
    summary: str
    articles: List[NewsArticle]
    confidence_score: float
    last_updated: datetime
    status: str = "active"

class NewsService:
    def __init__(self):
        self.newsapi_key = os.getenv('NEWSAPI_KEY', 'd69a3b23cad345b898a6ee4d6303c69b')
        self.newsdata_key = os.getenv('NEWSDATA_KEY', 'pub_83ffea09fe7d4707aa82f3b6c5a0da7c')
        self.client = httpx.AsyncClient(timeout=30.0)
        self.cache = CacheStore()
        self.demo_mode = False
        
        # Rate limiting: 80% of daily limits (20% buffer)
        self.newsapi_daily_limit = 800  # 80% of 1000
        self.newsdata_daily_limit = 160  # 80% of 200
        self.newsapi_used = 0
        self.newsdata_used = 0
        self.last_reset = datetime.now().date()
        
        # Enhanced topic detector
        self.topic_detector = EnhancedTopicDetector()
        self.entity_resolver = EntityResolver()
        self.llm = LLMService()
        self.providers = [
            NewsAPIProvider(self.client, self.cache, self.newsapi_key),
            NewsDataProvider(self.client, self.cache, self.newsdata_key)
        ]
        guardian_key = os.getenv('GUARDIAN_API_KEY')
        if guardian_key:
            self.providers.append(GuardianProvider(self.client, self.cache, guardian_key))
        gnews_key = os.getenv('GNEWS_API_KEY')
        if gnews_key:
            self.providers.append(GNewsProvider(self.client, self.cache, gnews_key))
        
    def _check_rate_limit(self, api_type: str) -> bool:
        """Check if we're within rate limits"""
        today = datetime.now().date()
        if today != self.last_reset:
            # Reset counters for new day
            self.newsapi_used = 0
            self.newsdata_used = 0
            self.last_reset = today
        
        if api_type == 'newsapi':
            return self.newsapi_used < self.newsapi_daily_limit
        elif api_type == 'newsdata':
            return self.newsdata_used < self.newsdata_daily_limit
        return False
    
    def _increment_usage(self, api_type: str):
        """Increment API usage counter"""
        if api_type == 'newsapi':
            self.newsapi_used += 1
        elif api_type == 'newsdata':
            self.newsdata_used += 1
    
    async def fetch_newsapi_articles(self, query: str = None, category: str = None, country: str = 'us') -> List[NewsArticle]:
        """Fetch articles from The News API"""
        if not self._check_rate_limit('newsapi'):
            print(f"NewsAPI rate limit reached ({self.newsapi_used}/{self.newsapi_daily_limit})")
            return []
            
        try:
            url = "https://newsapi.org/v2/top-headlines"
            params = {
                'apiKey': self.newsapi_key,
                'country': country,
                'pageSize': 50
            }
            
            if query:
                params['q'] = query
            if category:
                params['category'] = category
                
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            self._increment_usage('newsapi')
            
            articles = []
            for item in data.get('articles', []):
                if item.get('title') and item.get('url'):
                    article = NewsArticle(
                        title=item['title'],
                        content=item.get('description', '') or item.get('content', ''),
                        url=item['url'],
                        source=item['source']['name'],
                        published_at=datetime.fromisoformat(item['publishedAt'].replace('Z', '+00:00')),
                        category=item.get('category', 'general'),
                        country=country,
                        language='en'
                    )
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            print(f"Error fetching from News API: {e}")
            return []
    
    async def fetch_newsdata_articles(self, query: str = None, category: str = None, country: str = 'us') -> List[NewsArticle]:
        """Fetch articles from NewsData.io"""
        if not self._check_rate_limit('newsdata'):
            print(f"NewsData.io rate limit reached ({self.newsdata_used}/{self.newsdata_daily_limit})")
            return []
            
        try:
            url = "https://newsdata.io/api/1/news"
            params = {
                'apikey': self.newsdata_key,
                'country': country,
                'language': 'en',
                'size': 50
            }
            
            if query:
                params['q'] = query
            if category:
                params['category'] = category
                
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            self._increment_usage('newsdata')
            
            articles = []
            for item in data.get('results', []):
                if item.get('title') and item.get('link'):
                    article = NewsArticle(
                        title=item['title'],
                        content=item.get('description', '') or item.get('content', ''),
                        url=item['link'],
                        source=item.get('source_id', 'Unknown'),
                        published_at=datetime.fromisoformat(item['pubDate'].replace('Z', '+00:00')),
                        category=item.get('category', ['general'])[0] if item.get('category') else 'general',
                        country=country,
                        language='en'
                    )
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            print(f"Error fetching from NewsData.io: {e}")
            return []
    
    async def fetch_all_news(self) -> List[NewsArticle]:
        """Fetch using provider layer with dedupe and minimal calls"""
        raw: List[Dict[str, Any]] = []
        for p in self.providers:
            try:
                raw += await p.fetch({"country": "us"})
                raw += await p.fetch({"country": "us", "category": "sports"})
            except Exception as e:
                print(f"Provider error: {e}")
                continue
        by_url: Dict[str, Dict[str, Any]] = {}
        for r in raw:
            by_url.setdefault(r["url"], r)
        out: List[NewsArticle] = []
        for r in by_url.values():
            try:
                dt = datetime.fromisoformat((r.get("published_at") or "").replace('Z', '+00:00')) if r.get("published_at") else datetime.now()
            except Exception:
                dt = datetime.now()
            out.append(NewsArticle(
                title=r["title"], content=r.get("content", ""), url=r["url"],
                source=r.get("source", "API"), published_at=dt,
                category='general', country='us', language='en'
            ))
        return out
    
    def detect_topics(self, articles: List[NewsArticle]) -> List[TopicCluster]:
        """Detect topics from articles using enhanced topic detection"""
        return self.topic_detector.detect_topics(articles)
    
    def create_summary(self, articles: List[NewsArticle]) -> str:
        """Create a neutral summary from multiple articles"""
        if not articles:
            return "No information available."
        
        # Simple approach: take the most recent article's content
        most_recent = max(articles, key=lambda x: x.published_at)
        
        # Extract first few sentences
        content = most_recent.content or most_recent.title
        sentences = content.split('.')[:2]
        summary = '. '.join(sentences).strip()
        
        if not summary.endswith('.'):
            summary += '.'
        
        return summary

    async def refine_with_llm(self, topic: TopicCluster) -> TopicCluster:
        """Optionally refine title/summary with Grok LLM."""
        headlines = [a.title for a in topic.articles]
        sources = [a.source for a in topic.articles]
        improved = await self.llm.refine(headlines, sources, topic.title, topic.summary)
        topic.title = improved.get("title", topic.title)
        topic.summary = improved.get("summary", topic.summary)
        return topic
    
    def extract_facts(self, topic: TopicCluster) -> List[Dict[str, Any]]:
        """Extract facts from topic articles"""
        facts = []
        
        for article in topic.articles:
            # Simple fact extraction based on common patterns
            content = article.content or article.title
            
            # Look for numbers, dates, locations
            import re
            
            # Extract scores/scores
            scores = re.findall(r'(\d+)-(\d+)', content)
            for score in scores:
                facts.append({
                    "fact": f"Score: {score[0]}-{score[1]}",
                    "confidence": 0.9,
                    "source": article.source
                })
            
            # Extract locations
            locations = re.findall(r'in ([A-Z][a-z]+ [A-Z][a-z]+)', content)
            for location in locations:
                facts.append({
                    "fact": f"Location: {location}",
                    "confidence": 0.8,
                    "source": article.source
                })
        
        # If no specific facts found, create general ones
        if not facts:
            facts.append({
                "fact": f"Reported by {len(topic.articles)} sources",
                "confidence": 0.9,
                "source": "Multiple sources"
            })
            
            facts.append({
                "fact": f"Latest update: {max(topic.articles, key=lambda x: x.published_at).published_at.strftime('%Y-%m-%d %H:%M')}",
                "confidence": 0.95,
                "source": "Timestamp"
            })
        
        return facts
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
