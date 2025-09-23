"""
News Collection Layer
Implements the first layer of the Beacon architecture - gathering news articles from multiple sources
"""

import asyncio
import httpx
import os
from typing import List, Dict, Any
from datetime import datetime
import feedparser
from bs4 import BeautifulSoup

class NewsArticle:
    """Represents a single news article"""
    def __init__(self, title: str, url: str, source: str, content: str = "", 
                 published_at: datetime = None, category: str = "", 
                 country: str = "US", language: str = "en"):
        self.title = title
        self.url = url
        self.source = source
        self.content = content
        self.published_at = published_at or datetime.now()
        self.category = category
        self.country = country
        self.language = language

class NewsCollector:
    """Collects news articles from multiple sources"""
    
    def __init__(self):
        self.api_keys = {
            'newsapi': os.getenv('NEWSAPI_KEY', 'd69a3b23cad345b898a6ee4d6303c69b'),
            'newsdata': os.getenv('NEWSDATA_KEY', 'pub_83ffea09fe7d4707aa82f3b6c5a0da7c')
        }
        
        # News sources configuration
        self.news_sources = {
            'apis': [
                {'name': 'NewsAPI', 'url': 'https://newsapi.org/v2/top-headlines', 'key': 'newsapi'},
                {'name': 'NewsData', 'url': 'https://newsdata.io/api/1/news', 'key': 'newsdata'}
            ],
            'websites': [
                {'name': 'BBC News', 'url': 'https://www.bbc.com/news'},
                {'name': 'Associated Press', 'url': 'https://apnews.com'},
                {'name': 'NPR', 'url': 'https://www.npr.org'},
                {'name': 'ESPN', 'url': 'https://www.espn.com'}
            ],
            'rss_feeds': [
                {'name': 'BBC RSS', 'url': 'http://feeds.bbci.co.uk/news/rss.xml'},
                {'name': 'AP RSS', 'url': 'https://feeds.apnews.com/rss/apf-topnews'},
                {'name': 'NPR RSS', 'url': 'https://feeds.npr.org/1001/rss.xml'}
            ]
        }
    
    async def collect_articles(self) -> List[NewsArticle]:
        """Main method to collect articles from all sources"""
        print("🔍 Starting news collection from all sources...")
        
        all_articles = []
        
        # Collect from APIs
        api_articles = await self._collect_from_apis()
        all_articles.extend(api_articles)
        print(f"📡 Collected {len(api_articles)} articles from APIs")
        
        # Collect from websites
        website_articles = await self._collect_from_websites()
        all_articles.extend(website_articles)
        print(f"🌐 Collected {len(website_articles)} articles from websites")
        
        # Collect from RSS feeds
        rss_articles = await self._collect_from_rss()
        all_articles.extend(rss_articles)
        print(f"📡 Collected {len(rss_articles)} articles from RSS feeds")
        
        print(f"✅ Total articles collected: {len(all_articles)}")
        return all_articles
    
    async def _collect_from_apis(self) -> List[NewsArticle]:
        """Collect articles from news APIs"""
        articles = []
        
        async with httpx.AsyncClient() as client:
            # NewsAPI
            try:
                response = await client.get(
                    self.news_sources['apis'][0]['url'],
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
                                published_at=datetime.fromisoformat(article['publishedAt'].replace('Z', '+00:00')) if article.get('publishedAt') else datetime.now(),
                                category=article.get('category', 'general')
                            ))
            except Exception as e:
                print(f"❌ Error collecting from NewsAPI: {e}")
        
        return articles
    
    async def _collect_from_websites(self) -> List[NewsArticle]:
        """Collect articles by crawling news websites"""
        articles = []
        
        async with httpx.AsyncClient() as client:
            for source in self.news_sources['websites']:
                try:
                    print(f"🌐 Crawling {source['name']}...")
                    response = await client.get(source['url'])
                    
                    if response.status_code == 200:
                        # Parse HTML content
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Extract article links and titles
                        links = soup.find_all('a', href=True)
                        for link in links[:10]:  # Limit to 10 articles per source
                            href = link.get('href')
                            title = link.get_text(strip=True)
                            
                            if href and title and len(title) > 10:
                                # Make absolute URL
                                if href.startswith('/'):
                                    href = source['url'] + href
                                elif not href.startswith('http'):
                                    continue
                                
                                articles.append(NewsArticle(
                                    title=title,
                                    url=href,
                                    source=source['name'],
                                    content="",
                                    published_at=datetime.now()
                                ))
                    
                except Exception as e:
                    print(f"❌ Error crawling {source['name']}: {e}")
        
        return articles
    
    async def _collect_from_rss(self) -> List[NewsArticle]:
        """Collect articles from RSS feeds"""
        articles = []
        
        for feed in self.news_sources['rss_feeds']:
            try:
                print(f"📡 Parsing RSS feed: {feed['name']}")
                feed_data = feedparser.parse(feed['url'])
                
                for entry in feed_data.entries[:10]:  # Limit to 10 articles per feed
                    if entry.get('title') and entry.get('link'):
                        articles.append(NewsArticle(
                            title=entry['title'],
                            url=entry['link'],
                            source=feed['name'],
                            content=entry.get('summary', ''),
                            published_at=datetime(*entry.published_parsed[:6]) if entry.get('published_parsed') else datetime.now()
                        ))
                        
            except Exception as e:
                print(f"❌ Error parsing RSS feed {feed['name']}: {e}")
        
        return articles
