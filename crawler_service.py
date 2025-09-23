import asyncio
import httpx
from datetime import datetime
from typing import List, Dict, Any, Optional
import re
import hashlib
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass
import json

@dataclass
class CrawledArticle:
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

class CrawlerService:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.visited_urls = set()
        
        # Enhanced news sources to crawl
        self.news_sources = [
            # Major International
            {
                "name": "CNN",
                "base_url": "https://www.cnn.com",
                "article_selectors": {
                    "title": "h1[data-module='ArticleHeadline']",
                    "content": ".article__content p",
                    "links": "a[href*='/2025/']"
                }
            },
            {
                "name": "BBC News",
                "base_url": "https://www.bbc.com/news",
                "article_selectors": {
                    "title": "h1[data-testid='headline']",
                    "content": "[data-testid='text-block']",
                    "links": "a[href*='/news/']"
                }
            },
            {
                "name": "Reuters",
                "base_url": "https://www.reuters.com",
                "article_selectors": {
                    "title": "h1[data-testid='Headline']",
                    "content": "[data-testid='paragraph']",
                    "links": "a[href*='/article/']"
                }
            },
            {
                "name": "Associated Press",
                "base_url": "https://apnews.com",
                "article_selectors": {
                    "title": "h1[data-key='headline']",
                    "content": ".Article p",
                    "links": "a[href*='/article/']"
                }
            },
            {
                "name": "The Guardian",
                "base_url": "https://www.theguardian.com",
                "article_selectors": {
                    "title": "h1[data-testid='headline']",
                    "content": "[data-testid='paragraph']",
                    "links": "a[href*='/2025/']"
                }
            },
            # US News
            {
                "name": "NPR",
                "base_url": "https://www.npr.org",
                "article_selectors": {
                    "title": "h1",
                    "content": ".storytext p",
                    "links": "a[href*='/2025/']"
                }
            },
            {
                "name": "Politico",
                "base_url": "https://www.politico.com",
                "article_selectors": {
                    "title": "h1",
                    "content": ".story-text p",
                    "links": "a[href*='/news/']"
                }
            },
            {
                "name": "Axios",
                "base_url": "https://www.axios.com",
                "article_selectors": {
                    "title": "h1",
                    "content": ".story-text p",
                    "links": "a[href*='/2025/']"
                }
            },
            # Tech News
            {
                "name": "TechCrunch",
                "base_url": "https://techcrunch.com",
                "article_selectors": {
                    "title": "h1",
                    "content": ".article-content p",
                    "links": "a[href*='/2025/']"
                }
            },
            {
                "name": "The Verge",
                "base_url": "https://www.theverge.com",
                "article_selectors": {
                    "title": "h1",
                    "content": ".c-entry-content p",
                    "links": "a[href*='/2025/']"
                }
            },
            # Sports
            {
                "name": "ESPN",
                "base_url": "https://www.espn.com",
                "article_selectors": {
                    "title": "h1",
                    "content": ".article-body p",
                    "links": "a[href*='/story/']"
                }
            },
            {
                "name": "Sports Illustrated",
                "base_url": "https://www.si.com",
                "article_selectors": {
                    "title": "h1",
                    "content": ".article-content p",
                    "links": "a[href*='/2025/']"
                }
            }
        ]
        
        # RSS feeds for additional sources
        self.rss_feeds = [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://rss.cnn.com/rss/edition.rss",
            "https://feeds.reuters.com/reuters/topNews",
            "https://feeds.apnews.com/ap/topnews",
            "https://www.theguardian.com/world/rss"
        ]
    
    async def crawl_news_sources(self) -> List[CrawledArticle]:
        """Crawl news sources for articles"""
        articles = []
        
        # Crawl each news source
        for source in self.news_sources:
            try:
                print(f"Crawling {source['name']}...")
                source_articles = await self.crawl_source(source)
                articles.extend(source_articles)
                print(f"Found {len(source_articles)} articles from {source['name']}")
            except Exception as e:
                print(f"Error crawling {source['name']}: {e}")
        
        # Also crawl RSS feeds
        try:
            rss_articles = await self.crawl_rss_feeds()
            articles.extend(rss_articles)
            print(f"Found {len(rss_articles)} articles from RSS feeds")
        except Exception as e:
            print(f"Error crawling RSS feeds: {e}")
        
        return articles
    
    async def crawl_source(self, source: Dict[str, Any]) -> List[CrawledArticle]:
        """Crawl a specific news source"""
        articles = []
        
        try:
            # Get the main page
            response = await self.client.get(source["base_url"])
            response.raise_for_status()
            html = response.text
            
            # Extract article links
            article_links = self.extract_article_links(html, source)
            
            # Crawl each article
            for link in article_links[:10]:  # Limit to 10 articles per source
                if link not in self.visited_urls:
                    self.visited_urls.add(link)
                    article = await self.crawl_article(link, source)
                    if article:
                        articles.append(article)
                        await asyncio.sleep(1)  # Be respectful
            
        except Exception as e:
            print(f"Error crawling {source['name']}: {e}")
        
        return articles
    
    def extract_article_links(self, html: str, source: Dict[str, Any]) -> List[str]:
        """Extract article links from HTML"""
        links = []
        
        # Simple regex to find article links
        link_pattern = r'href="([^"]*)"'
        matches = re.findall(link_pattern, html)
        
        for match in matches:
            # Convert relative URLs to absolute
            full_url = urljoin(source["base_url"], match)
            
            # Filter for article URLs
            if self.is_article_url(full_url, source):
                links.append(full_url)
        
        return list(set(links))  # Remove duplicates
    
    def is_article_url(self, url: str, source: Dict[str, Any]) -> bool:
        """Check if URL is likely an article"""
        # Simple heuristics
        article_indicators = [
            '/2025/',
            '/article/',
            '/news/',
            '/story/',
            '/post/'
        ]
        
        return any(indicator in url for indicator in article_indicators)
    
    async def crawl_article(self, url: str, source: Dict[str, Any]) -> Optional[CrawledArticle]:
        """Crawl a single article"""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            html = response.text
            
            # Extract title
            title = self.extract_title(html, source)
            if not title:
                return None
            
            # Extract content
            content = self.extract_content(html, source)
            if not content:
                return None
            
            # Create article object
            article = CrawledArticle(
                title=title,
                content=content,
                url=url,
                source=source["name"],
                published_at=datetime.now(),
                category="general",
                country="us",
                language="en"
            )
            
            return article
            
        except Exception as e:
            print(f"Error crawling article {url}: {e}")
            return None
    
    def extract_title(self, html: str, source: Dict[str, Any]) -> Optional[str]:
        """Extract article title from HTML"""
        # Simple regex-based extraction
        title_patterns = [
            r'<h1[^>]*>([^<]+)</h1>',
            r'<title>([^<]+)</title>',
            r'"headline":"([^"]+)"',
            r'"title":"([^"]+)"'
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                if len(title) > 10:  # Reasonable title length
                    return title
        
        return None
    
    def extract_content(self, html: str, source: Dict[str, Any]) -> Optional[str]:
        """Extract article content from HTML"""
        # Remove script and style tags
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        
        # Extract text from paragraphs
        paragraph_pattern = r'<p[^>]*>([^<]+)</p>'
        paragraphs = re.findall(paragraph_pattern, html, re.IGNORECASE)
        
        if paragraphs:
            content = ' '.join(paragraphs)
            # Clean up the content
            content = re.sub(r'\s+', ' ', content)
            content = content.strip()
            
            if len(content) > 100:  # Reasonable content length
                return content
        
        return None
    
    async def crawl_rss_feeds(self) -> List[CrawledArticle]:
        """Crawl RSS feeds for articles"""
        articles = []
        
        for feed_url in self.rss_feeds:
            try:
                response = await self.client.get(feed_url)
                response.raise_for_status()
                xml_content = response.text
                
                # Parse RSS feed (simple approach)
                rss_articles = self.parse_rss_feed(xml_content, feed_url)
                articles.extend(rss_articles)
                
            except Exception as e:
                print(f"Error crawling RSS feed {feed_url}: {e}")
        
        return articles
    
    def parse_rss_feed(self, xml_content: str, feed_url: str) -> List[CrawledArticle]:
        """Parse RSS feed XML"""
        articles = []
        
        # Simple RSS parsing
        item_pattern = r'<item>(.*?)</item>'
        items = re.findall(item_pattern, xml_content, re.DOTALL)
        
        for item in items[:5]:  # Limit to 5 items per feed
            try:
                # Extract title
                title_match = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item)
                if not title_match:
                    title_match = re.search(r'<title>(.*?)</title>', item)
                
                if not title_match:
                    continue
                
                title = title_match.group(1).strip()
                
                # Extract link
                link_match = re.search(r'<link>(.*?)</link>', item)
                if not link_match:
                    continue
                
                url = link_match.group(1).strip()
                
                # Extract description
                desc_match = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>', item)
                if not desc_match:
                    desc_match = re.search(r'<description>(.*?)</description>', item)
                
                content = desc_match.group(1).strip() if desc_match else ""
                
                # Clean up content
                content = re.sub(r'<[^>]+>', '', content)
                content = re.sub(r'\s+', ' ', content).strip()
                
                if len(content) > 50:  # Reasonable content length
                    article = CrawledArticle(
                        title=title,
                        content=content,
                        url=url,
                        source=self.get_source_from_feed(feed_url),
                        published_at=datetime.now(),
                        category="general",
                        country="us",
                        language="en"
                    )
                    articles.append(article)
                    
            except Exception as e:
                print(f"Error parsing RSS item: {e}")
                continue
        
        return articles
    
    def get_source_from_feed(self, feed_url: str) -> str:
        """Get source name from feed URL"""
        if "bbci.co.uk" in feed_url:
            return "BBC News"
        elif "cnn.com" in feed_url:
            return "CNN"
        elif "reuters.com" in feed_url:
            return "Reuters"
        elif "apnews.com" in feed_url:
            return "Associated Press"
        elif "theguardian.com" in feed_url:
            return "The Guardian"
        else:
            return "RSS Feed"
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
