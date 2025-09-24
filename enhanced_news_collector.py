"""
Enhanced News Collection System
Combines WebCrawlerAI with local LLM for intelligent news sourcing
"""

import asyncio
import httpx
import feedparser
import re
from bs4 import BeautifulSoup
import trafilatura
from readability import Document
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
import os

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

class EnhancedNewsCollector:
    """Enhanced news collector using WebCrawlerAI principles with local LLM"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        self.visited_urls = set()
        
        # Enhanced news sources with intelligent crawling
        self.news_sources = [
            {
                "name": "CNN",
                "base_url": "https://www.cnn.com",
                "article_selectors": {
                    "title": ["h1[data-module='ArticleHeadline']", "h1.headline", "h1"],
                    "content": [".article__content p", ".zn-body__paragraph", "p"],
                    "links": "a[href*='/2025/']"
                }
            },
            {
                "name": "BBC News",
                "base_url": "https://www.bbc.com/news",
                "article_selectors": {
                    "title": ["h1", ".story-headline"],
                    "content": [".story-body p", ".article-body p"],
                    "links": "a[href*='/news/']"
                }
            },
            {
                "name": "Reuters",
                "base_url": "https://www.reuters.com",
                "article_selectors": {
                    "title": ["h1", ".article-headline"],
                    "content": [".article-body p", ".StandardArticleBody_body p"],
                    "links": "a[href*='/article/']"
                }
            },
            {
                "name": "Associated Press",
                "base_url": "https://apnews.com",
                "article_selectors": {
                    "title": ["h1", ".Page-headline"],
                    "content": [".Article p", ".RichTextStoryBody p"],
                    "links": "a[href*='/article/']"
                }
            },
            {
                "name": "The Guardian",
                "base_url": "https://www.theguardian.com",
                "article_selectors": {
                    "title": ["h1", ".content__headline"],
                    "content": [".content__article-body p", ".article-body p"],
                    "links": "a[href*='/']"
                }
            },
            {
                "name": "NPR",
                "base_url": "https://www.npr.org",
                "article_selectors": {
                    "title": ["h1", ".storytitle"],
                    "content": [".transcript p", ".storytext p"],
                    "links": "a[href*='/']"
                }
            },
            {
                "name": "ESPN",
                "base_url": "https://www.espn.com",
                "article_selectors": {
                    "title": ["h1", ".headline"],
                    "content": [".article-body p", ".story p"],
                    "links": "a[href*='/']"
                }
            }
        ]
        
        # RSS feeds for additional coverage
        self.rss_feeds = [
            "http://feeds.bbci.co.uk/news/rss.xml",
            "https://feeds.reuters.com/reuters/topNews",
            "https://feeds.apnews.com/rss/apf-topnews",
            "https://www.npr.org/rss/rss.php?id=1001",
            "https://feeds.cnn.com/rss/edition.rss"
        ]
        
        # API keys for additional sources
        self.api_keys = {
            'newsapi': os.getenv('NEWSAPI_KEY', 'd69a3b23cad345b898a6ee4d6303c69b'),
            'newsdata': os.getenv('NEWSDATA_KEY', 'pub_83ffea09fe7d4707aa82f3b6c5a0da7c')
        }
    
    async def collect_articles(self) -> List[NewsArticle]:
        """Main method to collect articles from all sources"""
        print("🔍 Starting enhanced news collection...")
        
        all_articles = []
        
        # Collect from APIs
        api_articles = await self._collect_from_apis()
        all_articles.extend(api_articles)
        print(f"📡 Collected {len(api_articles)} articles from APIs")
        
        # Collect from intelligent web crawling
        web_articles = await self._collect_from_websites()
        all_articles.extend(web_articles)
        print(f"🌐 Collected {len(web_articles)} articles from web crawling")
        
        # Collect from RSS feeds
        rss_articles = await self._collect_from_rss()
        all_articles.extend(rss_articles)
        print(f"📡 Collected {len(rss_articles)} articles from RSS feeds")
        
        # Remove duplicates
        unique_articles = self._remove_duplicates(all_articles)
        print(f"✅ Total unique articles collected: {len(unique_articles)}")
        
        return unique_articles
    
    async def _collect_from_apis(self) -> List[NewsArticle]:
        """Collect articles from news APIs"""
        articles = []
        
        # NewsAPI
        try:
            response = await self.client.get(
                "https://newsapi.org/v2/top-headlines",
                params={
                    'apiKey': self.api_keys['newsapi'],
                    'language': 'en',
                    'pageSize': 50,
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
        except Exception as e:
            print(f"❌ NewsAPI error: {e}")
        
        # NewsData
        try:
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
        except Exception as e:
            print(f"❌ NewsData error: {e}")
        
        return articles
    
    async def _collect_from_websites(self) -> List[NewsArticle]:
        """Intelligent web crawling using enhanced selectors"""
        articles = []
        
        for source in self.news_sources:
            try:
                print(f"🌐 Crawling {source['name']}...")
                source_articles = await self._crawl_source(source)
                articles.extend(source_articles)
                print(f"✅ Found {len(source_articles)} articles from {source['name']}")
            except Exception as e:
                print(f"❌ Error crawling {source['name']}: {e}")
        
        return articles
    
    async def _crawl_source(self, source: Dict) -> List[NewsArticle]:
        """Crawl a specific news source"""
        articles = []
        
        try:
            response = await self.client.get(source['base_url'])
            if response.status_code != 200:
                return articles
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find article links
            links = soup.select(source['article_selectors']['links'])
            article_urls = [urljoin(source['base_url'], link.get('href', '')) for link in links[:10]]  # Limit to 10 articles
            
            for url in article_urls:
                if url in self.visited_urls:
                    continue
                
                try:
                    article = await self._extract_article(url, source)
                    if article:
                        articles.append(article)
                        self.visited_urls.add(url)
                except Exception as e:
                    print(f"❌ Error extracting article from {url}: {e}")
                    continue
                    
        except Exception as e:
            print(f"❌ Error crawling {source['name']}: {e}")
        
        return articles
    
    async def _extract_article(self, url: str, source: Dict) -> Optional[NewsArticle]:
        """Extract article content from a URL"""
        try:
            response = await self.client.get(url)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract title
            title = None
            for selector in source['article_selectors']['title']:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text().strip()
                    break
            
            if not title:
                return None
            
            # Extract content
            content = ""
            for selector in source['article_selectors']['content']:
                content_elems = soup.select(selector)
                if content_elems:
                    content = " ".join([elem.get_text().strip() for elem in content_elems])
                    break
            
            # Use trafilatura as fallback for content extraction
            if not content:
                content = trafilatura.extract(response.text)
            
            return NewsArticle(
                title=title,
                url=url,
                source=source['name'],
                content=content[:1000] if content else "",  # Limit content length
                published_at=datetime.now(),
                category="general"
            )
            
        except Exception as e:
            print(f"❌ Error extracting article from {url}: {e}")
            return None
    
    async def _collect_from_rss(self) -> List[NewsArticle]:
        """Collect articles from RSS feeds"""
        articles = []
        
        for feed_url in self.rss_feeds:
            try:
                print(f"📡 Parsing RSS feed: {feed_url}")
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:10]:  # Limit to 10 entries per feed
                    if hasattr(entry, 'title') and hasattr(entry, 'link'):
                        articles.append(NewsArticle(
                            title=entry.title,
                            url=entry.link,
                            source=feed.feed.get('title', 'RSS Feed'),
                            content=getattr(entry, 'summary', ''),
                            published_at=datetime.now(),
                            category="general"
                        ))
                        
            except Exception as e:
                print(f"❌ Error parsing RSS feed {feed_url}: {e}")
        
        return articles
    
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
