"""
Rate-Limited News Collection System
Respects API rate limits with 1 API call per minute
"""

import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
import os
import time
import xml.etree.ElementTree as ET
from readability import Document
import trafilatura

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
            'web_scraping': 0,
            'rss': 0
        }
        
        # API keys for news sources
        self.api_keys = {
            'newsapi': os.getenv('NEWSAPI_KEY', 'd69a3b23cad345b898a6ee4d6303c69b'),
            'newsdata': os.getenv('NEWSDATA_KEY', 'pub_83ffea09fe7d4707aa82f3b6c5a0da7c')
        }

        # Website configurations for lightweight scraping
        self.web_sources = [
            {
                "name": "BBC News",
                "base_url": "https://www.bbc.com/news",
                "title_selector": "h1, .story-headline, .gs-c-promo-heading__title",
                "content_selector": "article p, .ssrcss-uf6wea-RichTextComponentWrapper p"
            },
            {
                "name": "Reuters",
                "base_url": "https://www.reuters.com",
                "title_selector": "h1, .article-header__heading__title",
                "content_selector": "article p, .article-body__content p"
            },
            {
                "name": "Associated Press",
                "base_url": "https://apnews.com",
                "title_selector": "h1, .Page-headline",
                "content_selector": ".RichTextStoryBody p, article p"
            },
            {
                "name": "NPR",
                "base_url": "https://www.npr.org",
                "title_selector": "h1, .storytitle",
                "content_selector": ".storytext p, article p"
            }
        ]

        # RSS feeds for additional breadth (parsed without feedparser dependency)
        self.rss_feeds = [
            {"name": "Reuters World", "url": "https://www.reuters.com/world/rss"},
            {"name": "AP Top News", "url": "https://feeds.apnews.com/apf-topnews"},
            {"name": "NPR Top Stories", "url": "https://feeds.npr.org/1001/rss.xml"},
            {"name": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"}
        ]
    
    async def collect_articles(self) -> List[NewsArticle]:
        """Main method to collect articles with rate limiting"""
        print("🔍 Starting rate-limited news collection...")
        
        # Prevent visited URL cache from growing unbounded and missing refreshes
        if len(self.visited_urls) > 2000:
            self.visited_urls = set(list(self.visited_urls)[-1000:])

        all_articles = []
        
        # Collect from APIs with rate limiting
        api_articles = await self._collect_from_apis_with_rate_limit()
        all_articles.extend(api_articles)
        print(f"📡 Collected {len(api_articles)} articles from APIs")
        
        # Collect from simple web scraping (no rate limits)
        web_articles = await self._collect_from_websites()
        all_articles.extend(web_articles)
        print(f"🌐 Collected {len(web_articles)} articles from web scraping")

        # Collect from RSS feeds with gentle rate limiting
        rss_articles = await self._collect_from_rss()
        all_articles.extend(rss_articles)
        print(f"🛰️ Collected {len(rss_articles)} articles from RSS feeds")
        
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
                            content = await self._fetch_article_content_generic(article['url'])
                            articles.append(NewsArticle(
                                title=article['title'],
                                url=article['url'],
                                source=article.get('source', {}).get('name', 'Unknown'),
                                content=content,
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
                            content = await self._fetch_article_content_generic(article['link'])
                            articles.append(NewsArticle(
                                title=article['title'],
                                url=article['link'],
                                source=article.get('source_id', 'Unknown'),
                                content=content,
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
        
        for source in self.web_sources:
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
            
            for link in links[:20]:  # modest limit per source
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
            response = await self.client.get(url, timeout=20.0)
            if response.status_code != 200:
                return None

            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            # Extract title
            title_elem = soup.select_one(source['title_selector'])
            if title_elem:
                title = title_elem.get_text().strip()
            else:
                doc = Document(html)
                title = doc.short_title().strip()
            if not title:
                return None

            # Extract content: prefer structured paragraphs
            paragraphs = [elem.get_text().strip() for elem in soup.select(source['content_selector'])]
            paragraphs = [p for p in paragraphs if len(p.split()) > 5]

            content = "\n".join(paragraphs[:6])

            if len(content) < 400:
                # Fallback to readability
                doc = Document(html)
                summary_html = doc.summary(html_partial=True)
                readability_text = BeautifulSoup(summary_html, 'html.parser').get_text(separator=' ').strip()
                if len(readability_text) < 400:
                    # Final fallback: trafilatura
                    extracted = trafilatura.extract(html)
                    if extracted:
                        readability_text = extracted.strip()
                content = (content + '\n' + readability_text).strip()

            content = re.sub(r'\s+', ' ', content)

            return NewsArticle(
                title=title,
                url=url,
                source=source['name'],
                content=content[:2000] if content else "",
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

    async def _collect_from_rss(self) -> List[NewsArticle]:
        """Collect articles from RSS feeds with lightweight XML parsing"""
        articles = []

        # Respect rate limiting on RSS calls as well
        if not self._can_make_api_call('rss'):
            print("⏰ RSS feeds recently fetched, skipping")
            return articles

        for feed in self.rss_feeds:
            try:
                response = await self.client.get(feed['url'])
                if response.status_code != 200:
                    continue

                root = None
                try:
                    root = ET.fromstring(response.text)
                except ET.ParseError:
                    continue

                items = root.findall('.//item')[:10]
                for item in items:
                    title_elem = item.find('title')
                    link_elem = item.find('link')
                    description_elem = item.find('description')

                    if title_elem is None or link_elem is None:
                        continue

                    title = (title_elem.text or '').strip()
                    link = (link_elem.text or '').strip()
                    if not title or not link:
                        continue

                    description = ''
                    if description_elem is not None and description_elem.text:
                        description = re.sub('<[^<]+?>', '', description_elem.text).strip()

                    full_content = await self._fetch_article_content_generic(link)
                    content = full_content or description

                    articles.append(NewsArticle(
                        title=title,
                        url=link,
                        source=feed['name'],
                        content=content[:2000],
                        published_at=datetime.now(),
                        category="general"
                    ))
            except Exception as rss_error:
                print(f"❌ Error parsing RSS feed {feed['name']}: {rss_error}")

        self.api_call_times['rss'] = time.time()
        return articles

    async def _fetch_article_content_generic(self, url: str) -> str:
        """Fetch article body text using readability/trafilatura."""
        try:
            response = await self.client.get(url, timeout=20.0, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            if response.status_code != 200:
                return ""

            html = response.text
            text = trafilatura.extract(html)
            if not text:
                doc = Document(html)
                summary_html = doc.summary(html_partial=True)
                text = BeautifulSoup(summary_html, 'html.parser').get_text(separator=' ')

            if not text:
                return ""

            return re.sub(r'\s+', ' ', text).strip()
        except Exception as e:
            print(f"❌ Error fetching article body from {url}: {e}")
            return ""
