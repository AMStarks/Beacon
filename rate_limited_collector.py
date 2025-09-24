"""
Rate-Limited News Collection System
Respects API rate limits with 1 API call per minute
"""

import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
import os
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class NewsArticle:
    """Represents a single news article"""
    title: str
    url: str
    source: str
    content: str = ""
    published_at: datetime = None
    category: str = ""
    country: str = "US"
    language: str = "en"

class RateLimitedNewsCollector:
    """Rate-limited news collector that respects API limits"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        self.visited_urls = set()
        
        # Rate limiting tracking
        self.api_call_times = {
            'newsapi': 0,
            'newsdata': 0,
            'web_scraping': 0
        }
        
        # API keys for news sources
        self.api_keys = {
            'newsapi': os.getenv('NEWSAPI_KEY', 'd69a3b23cad345b898a6ee4d6303c69b'),
            'newsdata': os.getenv('NEWSDATA_KEY', 'pub_83ffea09fe7d4707aa82f3b6c5a0da7c')
        }
    
    async def collect_articles(self) -> List[NewsArticle]:
        """Main method to collect articles with rate limiting"""
        print("🔍 Starting rate-limited news collection...")
        
        all_articles = []
        
        # Collect from APIs with rate limiting
        api_articles = await self._collect_from_apis_with_rate_limit()
        all_articles.extend(api_articles)
        print(f"📡 Collected {len(api_articles)} articles from APIs")
        
        # Collect from simple web scraping (no rate limits)
        web_articles = await self._collect_from_websites()
        all_articles.extend(web_articles)
        print(f"🌐 Collected {len(web_articles)} articles from web scraping")
        
        # Remove duplicates
        unique_articles = self._remove_duplicates(all_articles)
        print(f"✅ Total unique articles collected: {len(unique_articles)}")
        
        return unique_articles
    
    async def _collect_from_apis_with_rate_limit(self) -> List[NewsArticle]:
        """Collect articles from APIs with strict rate limiting"""
        articles = []
        
        # NewsAPI - only call if 60+ seconds since last call
        if self._can_make_api_call('newsapi'):
            try:
                print("📡 Calling NewsAPI...")
                response = await self.client.get(
                    "https://newsapi.org/v2/top-headlines",
                    params={
                        'apiKey': self.api_keys['newsapi'],
                        'language': 'en',
                        'pageSize': 10,  # Reduced from 20
                        'country': 'us'
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    for article in data.get('articles', []):
                        if article.get('title') and article.get('url'):
                            articles.append(NewsArticle(
                                title=article['title'],
                                url=article['url'],
                                source=article.get('source', {}).get('name', 'Unknown'),
                                content=article.get('description', ''),
                                published_at=datetime.now(),
                                category=article.get('category', 'general')
                            ))
                    print(f"✅ NewsAPI: {len(articles)} articles")
                elif response.status_code == 429:
                    print("⚠️ NewsAPI rate limited, skipping")
                else:
                    print(f"❌ NewsAPI error: {response.status_code}")
            except Exception as e:
                print(f"❌ NewsAPI error: {e}")
            
            self.api_call_times['newsapi'] = time.time()
        else:
            print("⏰ NewsAPI rate limited, skipping")
        
        # NewsData - only call if 60+ seconds since last call
        if self._can_make_api_call('newsdata'):
            try:
                print("📡 Calling NewsData...")
                response = await self.client.get(
                    "https://newsdata.io/api/1/news",
                    params={
                        'apikey': self.api_keys['newsdata'],
                        'language': 'en',
                        'category': 'top'
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    for article in data.get('results', []):
                        if article.get('title') and article.get('link'):
                            articles.append(NewsArticle(
                                title=article['title'],
                                url=article['link'],
                                source=article.get('source_id', 'Unknown'),
                                content=article.get('description', ''),
                                published_at=datetime.now(),
                                category=article.get('category', ['general'])[0] if article.get('category') else 'general'
                            ))
                    print(f"✅ NewsData: {len(articles)} articles")
                elif response.status_code == 429:
                    print("⚠️ NewsData rate limited, skipping")
                else:
                    print(f"❌ NewsData error: {response.status_code}")
            except Exception as e:
                print(f"❌ NewsData error: {e}")
            
            self.api_call_times['newsdata'] = time.time()
        else:
            print("⏰ NewsData rate limited, skipping")
        
        return articles
    
    def _can_make_api_call(self, api_name: str) -> bool:
        """Check if we can make an API call based on rate limiting"""
        current_time = time.time()
        last_call_time = self.api_call_times.get(api_name, 0)
        
        # Only allow 1 call per minute (60 seconds)
        return (current_time - last_call_time) >= 60
    
    async def _collect_from_websites(self) -> List[NewsArticle]:
        """Simple web scraping for news articles (no rate limits)"""
        articles = []
        
        # Simple news sources
        news_sources = [
            {
                "name": "BBC News",
                "base_url": "https://www.bbc.com/news",
                "title_selector": "h1, .story-headline",
                "content_selector": "p"
            }
        ]
        
        for source in news_sources:
            try:
                print(f"🌐 Scraping {source['name']}...")
                source_articles = await self._scrape_source(source)
                articles.extend(source_articles)
                print(f"✅ Found {len(source_articles)} articles from {source['name']}")
            except Exception as e:
                print(f"❌ Error scraping {source['name']}: {e}")
        
        return articles
    
    async def _scrape_source(self, source: Dict) -> List[NewsArticle]:
        """Scrape a specific news source"""
        articles = []
        
        try:
            response = await self.client.get(source['base_url'])
            if response.status_code != 200:
                return articles
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find article links
            links = soup.find_all('a', href=True)
            article_urls = []
            
            for link in links[:5]:  # Limit to 5 articles
                href = link.get('href')
                if href and ('/news/' in href or '/article/' in href or '/story/' in href):
                    full_url = urljoin(source['base_url'], href)
                    if full_url not in self.visited_urls:
                        article_urls.append(full_url)
                        self.visited_urls.add(full_url)
            
            for url in article_urls:
                try:
                    article = await self._extract_article(url, source)
                    if article:
                        articles.append(article)
                except Exception as e:
                    print(f"❌ Error extracting article from {url}: {e}")
                    continue
                    
        except Exception as e:
            print(f"❌ Error scraping {source['name']}: {e}")
        
        return articles
    
    async def _extract_article(self, url: str, source: Dict) -> Optional[NewsArticle]:
        """Extract article content from a URL"""
        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title_elem = soup.select_one(source['title_selector'])
            if not title_elem:
                return None
            
            title = title_elem.get_text().strip()
            
            # Extract content
            content_elems = soup.select(source['content_selector'])
            content = " ".join([elem.get_text().strip() for elem in content_elems[:3]])  # First 3 paragraphs
            
            return NewsArticle(
                title=title,
                url=url,
                source=source['name'],
                content=content[:500] if content else "",  # Limit content length
                published_at=datetime.now(),
                category="general"
            )
            
        except Exception as e:
            print(f"❌ Error extracting article from {url}: {e}")
            return None
    
    def _remove_duplicates(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Remove duplicate articles based on title similarity"""
        unique_articles = []
        seen_titles = set()
        
        for article in articles:
            # Simple deduplication based on title similarity
            title_words = set(article.title.lower().split())
            is_duplicate = False
            
            for seen_title in seen_titles:
                seen_words = set(seen_title.lower().split())
                if len(title_words.intersection(seen_words)) >= 3:  # 3+ common words = likely duplicate
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_articles.append(article)
                seen_titles.add(article.title)
        
        return unique_articles
