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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CrawledArticle:
    id: str
    title: str
    content: str
    url: str
    source: str
    published_at: datetime
    category: str = "general"
    country: str = "us"
    language: str = "en"

class EnhancedCrawlerService:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        self.visited_urls = set()
        self.allowlist_playwright = {"www.theguardian.com", "www.politico.com", "www.axios.com"}
        
        # Enhanced news sources with better selectors
        self.news_sources = [
            {
                "name": "CNN",
                "base_url": "https://www.cnn.com",
                "article_selectors": {
                    "title": ["h1[data-module='ArticleHeadline']", "h1.headline", "h1"],
                    "content": [".article__content p", ".zn-body__paragraph", "p"],
                    "links": "a[href*='/2025/']"
                },
                "exclude_selectors": [".ad", ".advertisement", ".social", ".share", ".comment"]
            },
            {
                "name": "BBC News",
                "base_url": "https://www.bbc.com/news",
                "article_selectors": {
                    "title": ["h1[data-testid='headline']", "h1", ".story-headline"],
                    "content": ["[data-testid='text-block']", ".story-body p", "p"],
                    "links": "a[href*='/news/']"
                },
                "exclude_selectors": [".ad", ".advertisement", ".social", ".share"]
            },
            {
                "name": "Reuters",
                "base_url": "https://www.reuters.com",
                "article_selectors": {
                    "title": ["h1[data-testid='Headline']", "h1", ".article-headline"],
                    "content": ["[data-testid='paragraph']", ".article-body p", "p"],
                    "links": "a[href*='/article/']"
                },
                "exclude_selectors": [".ad", ".advertisement", ".social"]
            },
            {
                "name": "Associated Press",
                "base_url": "https://apnews.com",
                "article_selectors": {
                    "title": ["h1[data-key='headline']", "h1", ".headline"],
                    "content": [".Article p", ".article-content p", "p"],
                    "links": "a[href*='/article/']"
                },
                "exclude_selectors": [".ad", ".advertisement", ".social"]
            },
            {
                "name": "The Guardian",
                "base_url": "https://www.theguardian.com",
                "article_selectors": {
                    "title": ["h1[data-testid='headline']", "h1", ".content__headline"],
                    "content": ["[data-testid='paragraph']", ".content__article-body p", "p"],
                    "links": "a[href*='/2025/']"
                },
                "exclude_selectors": [".ad", ".advertisement", ".social", ".share"]
            },
            {
                "name": "NPR",
                "base_url": "https://www.npr.org",
                "article_selectors": {
                    "title": ["h1", ".storytitle"],
                    "content": [".storytext p", ".transcript p", "p"],
                    "links": "a[href*='/2025/']"
                },
                "exclude_selectors": [".ad", ".advertisement", ".social", ".share"]
            },
            {
                "name": "ESPN",
                "base_url": "https://www.espn.com",
                "article_selectors": {
                    "title": ["h1", ".headline"],
                    "content": [".article-body p", ".story-body p", "p"],
                    "links": "a[href*='/story/']"
                },
                "exclude_selectors": [".ad", ".advertisement", ".social", ".share"]
            }
        ]
        
        # Enhanced RSS feeds
        self.rss_feeds = [
            "https://feeds.bbci.co.uk/news/rss.xml",
            "https://rss.cnn.com/rss/edition.rss",
            "https://feeds.reuters.com/reuters/topNews",
            "https://feeds.apnews.com/ap/topnews",
            "https://www.theguardian.com/world/rss",
            "https://feeds.npr.org/1001/rss.xml",
            "https://www.espn.com/espn/rss/news"
        ]

    async def crawl_news_sources(self) -> List[CrawledArticle]:
        """Enhanced news crawling with better content extraction"""
        all_articles = []
        
        # Crawl web sources
        for source in self.news_sources:
            try:
                articles = await self.crawl_source(source)
                all_articles.extend(articles)
                logger.info(f"Found {len(articles)} articles from {source['name']}")
            except Exception as e:
                logger.error(f"Error crawling {source['name']}: {e}")
        
        # Crawl RSS feeds
        rss_articles = await self.crawl_rss_feeds()
        all_articles.extend(rss_articles)
        logger.info(f"Found {len(rss_articles)} articles from RSS feeds")
        
        return all_articles

    async def crawl_source(self, source: Dict[str, Any]) -> List[CrawledArticle]:
        """Crawl a specific news source"""
        articles = []
        
        try:
            # Strategy 1: RSS first if available
            rss_links = await self.try_rss(source)
            links = rss_links
            
            # Strategy 2: if RSS sparse, fetch homepage and parse
            if len(links) < 5:
                response = await self.client.get(source["base_url"])
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                links = list(set(links + self.extract_article_links(soup, source)))
            
            # Strategy 3: sitemap URLs (best-effort)
            if len(links) < 5:
                links = list(set(links + await self.try_sitemap(source)))
            
            # Crawl each article
            for link in links[:10]:  # Limit to 10 articles per source
                if link not in self.visited_urls:
                    self.visited_urls.add(link)
                    article = await self.crawl_article(link, source)
                    if article:
                        articles.append(article)
            
        except Exception as e:
            logger.error(f"Error crawling {source['name']}: {e}")
        
        return articles

    async def try_rss(self, source: Dict[str, Any]) -> List[str]:
        """Try common RSS endpoints for a site (best-effort)"""
        candidates = [
            urljoin(source["base_url"], "/rss"),
            urljoin(source["base_url"], "/feed"),
            urljoin(source["base_url"], "/feeds"),
        ]
        links: List[str] = []
        for url in candidates:
            try:
                feed = feedparser.parse(url)
                for e in feed.entries[:10]:
                    if getattr(e, "link", None):
                        links.append(e.link)
                if links:
                    break
            except Exception:
                continue
        return links

    async def try_sitemap(self, source: Dict[str, Any]) -> List[str]:
        """Fetch sitemap.xml and collect a few article links"""
        links: List[str] = []
        for path in ["/sitemap.xml", "/sitemap_index.xml"]:
            url = urljoin(source["base_url"], path)
            try:
                r = await self.client.get(url)
                if r.status_code != 200:
                    continue
                try:
                    root = ET.fromstring(r.text)
                except Exception:
                    continue
                for loc in root.iter():
                    if loc.tag.endswith('loc') and loc.text:
                        u = loc.text.strip()
                        if self.is_article_url(u, source):
                            links.append(u)
                if links:
                    break
            except Exception:
                continue
        return links[:10]

    def extract_article_links(self, soup: BeautifulSoup, source: Dict[str, Any]) -> List[str]:
        """Extract article links from parsed HTML"""
        links = []
        
        # Find all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Convert relative URLs to absolute
            full_url = urljoin(source["base_url"], href)
            
            # Filter for article URLs
            if self.is_article_url(full_url, source):
                links.append(full_url)
        
        return list(set(links))  # Remove duplicates

    def is_article_url(self, url: str, source: Dict[str, Any]) -> bool:
        """Check if URL is likely an article"""
        # Skip if already visited
        if url in self.visited_urls:
            return False
        
        # Skip non-article URLs
        skip_patterns = [
            '/video/', '/gallery/', '/slideshow/', '/interactive/',
            '/live/', '/breaking/', '/opinion/', '/editorial/',
            '/advertisement/', '/ad/', '/sponsor/'
        ]
        
        if any(pattern in url.lower() for pattern in skip_patterns):
            return False
        
        # Check for article indicators
        article_indicators = [
            '/2025/', '/2024/', '/article/', '/news/', '/story/', '/post/'
        ]
        
        return any(indicator in url for indicator in article_indicators)

    async def crawl_article(self, url: str, source: Dict[str, Any]) -> Optional[CrawledArticle]:
        """Crawl a single article with enhanced content extraction"""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            html = response.text
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            title = self.extract_title(soup, source)
            if not title or len(title) < 10:
                # Optional Playwright fallback for JS-only pages
                rendered = await self.render_page(url)
                if rendered:
                    soup = BeautifulSoup(rendered, 'html.parser')
                    title = self.extract_title(soup, source)
                if not title or len(title) < 10:
                    return None
            
            # Extract content
            content = self.extract_content(soup, source)
            if not content or len(content) < 50:
                rendered = await self.render_page(url)
                if rendered:
                    soup = BeautifulSoup(rendered, 'html.parser')
                    content = self.extract_content(soup, source)
                if not content or len(content) < 50:
                    return None
            
            # Create article object
            article = CrawledArticle(
                id=f"crawled_{hash(url) % 1000000}",
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
            logger.error(f"Error crawling article {url}: {e}")
            return None

    async def render_page(self, url: str) -> Optional[str]:
        """Optional Playwright rendering; returns HTML or None."""
        try:
            from urllib.parse import urlparse
            host = urlparse(url).netloc
            if host not in self.allowlist_playwright:
                return None
            try:
                from playwright.async_api import async_playwright
            except Exception:
                return None
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent=self.client.headers.get('User-Agent', ''), java_script_enabled=True)
                page = await context.new_page()
                # Block heavy resources
                await page.route("**/*", lambda route: route.abort() if route.request.resource_type in {"image", "font", "media"} else route.continue_())
                try:
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                    html = await page.content()
                finally:
                    await context.close()
                    await browser.close()
                return html
        except Exception:
            return None

    def extract_title(self, soup: BeautifulSoup, source: Dict[str, Any]) -> Optional[str]:
        """Extract article title with multiple fallback strategies"""
        title_selectors = source["article_selectors"]["title"]
        
        for selector in title_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    title = element.get_text().strip()
                    if self.is_valid_title(title):
                        return self.clean_text(title)
            except Exception:
                continue
        
        # Fallback to meta title
        meta_title = soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content'):
            title = meta_title['content'].strip()
            if self.is_valid_title(title):
                return self.clean_text(title)
        
        # Fallback to page title
        page_title = soup.find('title')
        if page_title:
            title = page_title.get_text().strip()
            if self.is_valid_title(title):
                return self.clean_text(title)
        
        return None

    def extract_content(self, soup: BeautifulSoup, source: Dict[str, Any]) -> Optional[str]:
        """Extract article content with robust boilerplate removal and fallbacks"""
        html_str = str(soup)

        # 1) Try trafilatura
        try:
            text = trafilatura.extract(html_str, include_comments=False, include_tables=False) or ""
            text = (text or '').strip()
            if self.is_valid_content(text):
                return self.clean_text(text)
        except Exception:
            pass

        # 2) Try readability-lxml
        try:
            doc = Document(html_str)
            readable_html = doc.summary(html_partial=True)
            readable_soup = BeautifulSoup(readable_html, 'html.parser')
            paras = [p.get_text(strip=True) for p in readable_soup.find_all('p')]
            text = ' '.join(paras)
            if self.is_valid_content(text):
                return self.clean_text(text)
        except Exception:
            pass

        # 3) Fallback to original CSS selectors
        content_selectors = source["article_selectors"]["content"]
        exclude_selectors = source.get("exclude_selectors", [])
        for selector in exclude_selectors:
            for element in soup.select(selector):
                element.decompose()
        content_paragraphs = []
        for selector in content_selectors:
            try:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text().strip()
                    if self.is_valid_content(text):
                        content_paragraphs.append(text)
                if content_paragraphs:
                    break
            except Exception:
                continue
        if not content_paragraphs:
            return None
        return self.clean_text(' '.join(content_paragraphs))

    def is_valid_title(self, title: str) -> bool:
        """Check if title is valid"""
        if not title or len(title) < 10:
            return False
        
        # Skip navigation and UI elements
        skip_words = [
            'menu', 'navigation', 'search', 'login', 'sign up', 'subscribe',
            'advertisement', 'ad', 'sponsor', 'cookie', 'privacy', 'terms',
            'home', 'about', 'contact', 'help', 'support', 'feedback'
        ]
        
        title_lower = title.lower()
        if any(word in title_lower for word in skip_words):
            return False
        
        # Skip titles that are mostly single letters or numbers
        words = title.split()
        meaningful_words = [w for w in words if len(w) > 2]
        if len(meaningful_words) < 2:
            return False
        
        # Skip titles that are mostly punctuation or numbers
        if len(re.sub(r'[^\w\s]', '', title)) < len(title) * 0.5:
            return False
        
        return True

    def is_valid_content(self, text: str) -> bool:
        """Check if content is valid"""
        if not text or len(text) < 20:
            return False
        
        # Skip navigation and UI elements
        skip_words = [
            'cookie', 'privacy', 'terms', 'subscribe', 'newsletter',
            'advertisement', 'ad', 'sponsor', 'share', 'comment'
        ]
        
        text_lower = text.lower()
        if any(word in text_lower for word in skip_words):
            return False
        
        return True

    def clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove HTML entities
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        
        # Remove common HTML artifacts
        text = re.sub(r'<[^>]+>', '', text)
        
        return text.strip()

    async def crawl_rss_feeds(self) -> List[CrawledArticle]:
        """Crawl RSS feeds for additional articles"""
        articles = []
        
        for feed_url in self.rss_feeds:
            try:
                feed = feedparser.parse(feed_url)
                
                for entry in feed.entries[:5]:  # Limit to 5 per feed
                    if hasattr(entry, 'link') and hasattr(entry, 'title'):
                        # Create article from RSS entry
                        article = CrawledArticle(
                            id=f"rss_{hash(entry.link) % 1000000}",
                            title=self.clean_text(entry.title),
                            content=self.clean_text(getattr(entry, 'summary', '')),
                            url=entry.link,
                            source="RSS Feed",
                            published_at=datetime.now(),
                            category="general",
                            country="us",
                            language="en"
                        )
                        articles.append(article)
                        
            except Exception as e:
                logger.error(f"Error crawling RSS feed {feed_url}: {e}")
        
        return articles

    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
