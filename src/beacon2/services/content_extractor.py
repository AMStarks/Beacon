#!/usr/bin/env python3
"""
Content Extractor - Hybrid extraction engine with JavaScript support
"""

import asyncio
import aiohttp
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class ContentExtractor:
    """Hybrid content extraction with BeautifulSoup + Playwright fallback"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.playwright_available = False

        # Try to import Playwright for JavaScript rendering
        try:
            from playwright.async_api import async_playwright
            self.playwright_available = True
            logger.info("✅ Playwright available for JavaScript rendering")
        except ImportError:
            logger.warning("⚠️ Playwright not available - JavaScript sites may fail")
            self.playwright_available = False

    async def extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content using hybrid approach: BeautifulSoup -> Playwright fallback"""
        logger.info(f"🚀 Starting content extraction for {url}")

        try:
            # First attempt: Fast BeautifulSoup extraction
            logger.debug(f"📄 Attempting BeautifulSoup extraction for {url}")
            result = await self._extract_with_beautifulsoup(url)

            if result['success']:
                logger.debug(f"🔍 BeautifulSoup result: title='{result.get('title', 'None')[:50]}...', content_length={len(result.get('content', ''))}")

                # Check if we got meaningful content (stricter validation)
                logger.debug(f"🔍 Validating content quality for {url}")
                is_meaningful = self._is_meaningful_content(result)

                if is_meaningful:
                    logger.info(f"✅ Fast extraction successful for {url} (method: {result.get('extraction_method', 'beautifulsoup')})")
                    return result
                else:
                    logger.warning(f"⚠️ BeautifulSoup produced poor quality content for {url}")
            else:
                logger.warning(f"⚠️ BeautifulSoup extraction failed for {url}: {result.get('error', 'unknown error')}")

            # If BeautifulSoup failed or got poor content, check if site is JavaScript-heavy
            logger.debug(f"🔍 Checking if {url} is JavaScript-heavy")
            is_js_heavy = await self._is_javascript_heavy(url)

            if is_js_heavy:
                logger.info(f"🔄 JavaScript site detected for {url}, trying Playwright...")

                # Second attempt: JavaScript rendering with Playwright
                playwright_result = await self._extract_with_playwright(url)
                if playwright_result['success']:
                    logger.info(f"✅ Playwright extraction successful for {url}")

                    # Validate Playwright results too
                    if self._is_meaningful_content(playwright_result):
                        logger.info(f"✅ Playwright content quality validated for {url}")
                        return playwright_result
                    else:
                        logger.warning(f"⚠️ Playwright produced poor quality content for {url}")

            # If both methods failed, return the best result we got
            logger.warning(f"⚠️ Limited extraction success for {url} - using best available result")
            return result

        except Exception as e:
            logger.error(f"❌ Content extraction failed for {url}: {e}")
            import traceback
            logger.error(f"🔍 Full traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}

    async def _extract_with_beautifulsoup(self, url: str) -> Dict[str, Any]:
        """Fast extraction using BeautifulSoup (original method)"""
        try:
            # Fetch HTML content
            html_content = await self._fetch_html(url)
            if not html_content:
                return {'success': False, 'error': 'Failed to fetch content'}

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')

            # Extract structured data
            result = {
                'url': url,
                'success': True,
                'title': self._extract_title(soup),
                'description': self._extract_description(soup),
                'content': self._extract_main_content(soup),
                'author': self._extract_author(soup),
                'publish_date': self._extract_publish_date(soup),
                'source_domain': urlparse(url).netloc,
                'extracted_at': asyncio.get_event_loop().time(),
                'extraction_method': 'beautifulsoup'
            }

            # If content is weak, but description is decent, provide summary-only fallback
            content_text = result.get('content') or ''
            desc = (result.get('description') or '').strip()
            if len(content_text) < 200 and len(desc) >= 140:
                result['content'] = desc
                result['extraction_method'] = 'rss_summary_fallback'
                result['success'] = True
            return result

        except Exception as e:
            logger.error(f"❌ BeautifulSoup extraction failed for {url}: {e}")
            return {'success': False, 'error': str(e)}

    async def _is_javascript_heavy(self, url: str) -> bool:
        """Simple, reliable site-specific JavaScript detection"""
        # Known JavaScript-heavy news sites that need Playwright
        javascript_sites = {
            'cnn.com',
            'edition.cnn.com',
            'bbc.com',
            'bbc.co.uk',
            'nytimes.com',
            'washingtonpost.com',
            'theguardian.com',
            'reuters.com',
            'apnews.com',
            'bloomberg.com',
            'ft.com',
            'wsj.com'
        }

        # Check if URL matches any known JavaScript site
        for site in javascript_sites:
            if site in url.lower():
                logger.info(f"🎯 Known JavaScript site detected: {url}")
                return True

        # Fallback: check for obvious indicators
        try:
            html_content = await self._fetch_html(url)
            if not html_content:
                return False

            html_text = html_content.lower()

            # Quick indicators of modern JavaScript sites
            js_indicators = ['react', 'vue', 'angular', 'webpack', 'next.js']
            indicator_count = sum(1 for indicator in js_indicators if indicator in html_text)

            # If multiple modern framework indicators, likely JavaScript-heavy
            if indicator_count >= 2:
                logger.info(f"🔍 Modern framework detected in {url} ({indicator_count} indicators)")
                return True

        except Exception as e:
            logger.warning(f"Error checking JavaScript indicators for {url}: {e}")

        return False

    def _is_meaningful_content(self, result: Dict[str, Any]) -> bool:
        """Stricter validation for meaningful article content vs HTML fragments"""
        title = result.get('title', '').strip()
        content = result.get('content', '').strip()

        # Must have substantial content ( stricter requirement)
        if len(content) < 200:
            logger.debug(f"⚠️ Content too short: {len(content)} chars")
            return False

        # Must have a meaningful title (not just metadata)
        if not title or len(title) < 10:
            logger.debug(f"⚠️ Title too short or missing: '{title}'")
            return False

        # Check for obvious HTML fragments and metadata
        html_indicators = [
            'See all topics', 'Facebook Tweet Email Link', 'Link Copied',
            'Crime Gun violence Federal agencies', 'Ryan Sun/AP',
            'Follow', 'Share', 'Subscribe', 'Advertisement',
            '<script', '<style', '<meta', '<link',
            'function(', 'var ', 'const ', 'let ',
            'document.', 'window.', 'console.',
            'loading', 'spinner', 'placeholder',
            'Advertisement', 'Sponsored', 'Promoted'
        ]

        combined_text = (title + ' ' + content).lower()

        # Count HTML indicators
        indicator_count = sum(1 for indicator in html_indicators if indicator.lower() in combined_text)

        # Reject if any HTML indicators found (very strict)
        if indicator_count > 0:
            logger.debug(f"⚠️ HTML fragments detected: {indicator_count} indicators")
            return False

        # Check for actual article content patterns
        article_patterns = [
            r'\b(said|told|according to|reported|announced|stated)\b',
            r'\b(police|officials|authorities|government)\b.*\b(said|stated|announced)\b',
            r'\b\d{4}\b',  # Years (common in articles)
            r'\b[A-Z][a-z]+ [A-Z][a-z]+\b'  # Proper names
        ]

        # Must have at least 2 article patterns
        pattern_count = sum(1 for pattern in article_patterns if re.search(pattern, combined_text, re.IGNORECASE))

        if pattern_count < 2:
            logger.debug(f"⚠️ Insufficient article patterns: {pattern_count}/4")
            return False

        # Content should be mostly readable text (not code/metadata)
        words = content.split()
        if len(words) < 20:  # Too few words
            logger.debug(f"⚠️ Too few words: {len(words)}")
            return False

        # Check for reasonable word length distribution
        avg_word_length = sum(len(word) for word in words) / len(words)
        if avg_word_length < 3 or avg_word_length > 12:  # Suspicious word lengths
            logger.debug(f"⚠️ Suspicious word length: {avg_word_length:.1f}")
            return False

        logger.debug(f"✅ Content quality validated for {result.get('url', 'unknown')}")
        return True

    async def _extract_with_playwright(self, url: str) -> Dict[str, Any]:
        """Extract content using Playwright for JavaScript rendering"""
        logger.info(f"🎭 Starting Playwright extraction for {url}")

        if not self.playwright_available:
            logger.error(f"❌ Playwright not available for {url}")
            return {'success': False, 'error': 'Playwright not available'}

        try:
            from playwright.async_api import async_playwright
            logger.debug(f"🔧 Importing Playwright for {url}")

            async with async_playwright() as p:
                logger.debug(f"🌐 Launching Chromium browser for {url}")
                # Launch browser
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # Set user agent and load page
                await page.set_user_agent(self.headers['User-Agent'])
                logger.debug(f"📄 Navigating to {url}")
                await page.goto(url, wait_until='networkidle', timeout=30000)

                # Wait for content to load
                logger.debug(f"⏳ Waiting for content to load on {url}")
                await page.wait_for_timeout(3000)

                # Get rendered HTML
                logger.debug(f"📋 Getting rendered HTML for {url}")
                html_content = await page.content()
                html_length = len(html_content)
                logger.debug(f"📊 Rendered HTML length: {html_length} characters")

                # Close browser
                await browser.close()
                logger.debug(f"🔒 Browser closed for {url}")

                # Parse with BeautifulSoup
                logger.debug(f"🔍 Parsing HTML with BeautifulSoup for {url}")
                soup = BeautifulSoup(html_content, 'html.parser')

                # Extract structured data
                logger.debug(f"📝 Extracting content elements for {url}")
                result = {
                    'url': url,
                    'success': True,
                    'title': self._extract_title(soup),
                    'description': self._extract_description(soup),
                    'content': self._extract_main_content(soup),
                    'author': self._extract_author(soup),
                    'publish_date': self._extract_publish_date(soup),
                    'source_domain': urlparse(url).netloc,
                    'extracted_at': asyncio.get_event_loop().time(),
                    'extraction_method': 'playwright'
                }

                logger.info(f"✅ Playwright extraction completed for {url}")
                return result

        except Exception as e:
            logger.error(f"❌ Playwright extraction failed for {url}: {e}")
            import traceback
            logger.error(f"🔍 Playwright error traceback: {traceback.format_exc()}")
            return {'success': False, 'error': str(e)}

    async def _fetch_html(self, url: str) -> Optional[str]:
        """Fetch HTML content with retries"""
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.get(url, headers=self.headers) as response:
                        if response.status == 200:
                            return await response.text()
                        else:
                            logger.warning(f"HTTP {response.status} for {url}")
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                if attempt < 2:
                    await asyncio.sleep(1)

        return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Extract article title with multiple fallback methods"""
        # Method 1: OpenGraph title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()

        # Method 2: Twitter card title
        twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
        if twitter_title and twitter_title.get('content'):
            return twitter_title['content'].strip()

        # Method 3: HTML title tag
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()

        # Method 4: h1 headline
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()

        return ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract article description"""
        # Method 1: OpenGraph description
        og_desc = soup.find('meta', property='og:description')
        if og_desc and og_desc.get('content'):
            return og_desc['content'].strip()

        # Method 2: Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc['content'].strip()

        # Method 3: Twitter description
        twitter_desc = soup.find('meta', attrs={'name': 'twitter:description'})
        if twitter_desc and twitter_desc.get('content'):
            return twitter_desc['content'].strip()

        return ""

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """Extract main article content with multiple strategies"""
        # Strategy 1: Look for article tags
        article = soup.find('article')
        if article:
            content = self._clean_content(article.get_text())
            if len(content) > 200:
                return content

        # Strategy 2: Look for main content areas
        for selector in ['main', '[role="main"]', '.content', '.article-content', '.post-content']:
            element = soup.select_one(selector)
            if element:
                content = self._clean_content(element.get_text())
                if len(content) > 200:
                    return content

        # Strategy 3: Look for common article containers
        for selector in ['.article', '.story', '.entry', '.post']:
            element = soup.select_one(selector)
            if element:
                content = self._clean_content(element.get_text())
                if len(content) > 200:
                    return content

        # Strategy 4: Fallback to body content (cleaned)
        body = soup.find('body')
        if body:
            content = self._clean_content(body.get_text())
            if len(content) > 200:
                return content[:2000]  # Limit length

        return ""

    def _extract_author(self, soup: BeautifulSoup) -> str:
        """Extract author information"""
        # Method 1: OpenGraph author
        og_author = soup.find('meta', property='article:author')
        if og_author and og_author.get('content'):
            return og_author['content'].strip()

        # Method 2: JSON-LD author
        json_ld = soup.find('script', type='application/ld+json')
        if json_ld:
            try:
                data = json.loads(json_ld.string)
                if isinstance(data, list):
                    data = data[0]
                author = data.get('author', {})
                if isinstance(author, dict):
                    return author.get('name', '')
                elif isinstance(author, str):
                    return author
            except:
                pass

        # Method 3: Common author selectors
        for selector in ['.author', '.byline', '[rel="author"]', '.post-author']:
            element = soup.select_one(selector)
            if element:
                return element.get_text().strip()

        return ""

    def _extract_publish_date(self, soup: BeautifulSoup) -> str:
        """Extract publication date"""
        # Method 1: OpenGraph publish date
        og_date = soup.find('meta', property='article:published_time')
        if og_date and og_date.get('content'):
            return og_date['content'].strip()

        # Method 2: JSON-LD date
        json_ld = soup.find('script', type='application/ld+json')
        if json_ld:
            try:
                data = json.loads(json_ld.string)
                if isinstance(data, list):
                    data = data[0]
                date_published = data.get('datePublished', '')
                if date_published:
                    return date_published
            except:
                pass

        # Method 3: Common date selectors
        for selector in ['.date', '.published', '.post-date', 'time[datetime]']:
            element = soup.select_one(selector)
            if element:
                datetime_attr = element.get('datetime')
                if datetime_attr:
                    return datetime_attr
                return element.get_text().strip()

        return ""

    def _clean_content(self, text: str) -> str:
        """Clean and normalize extracted content"""
        if not text:
            return ""

        # Remove video timestamps and player elements
        text = re.sub(r'\d{1,2}:\d{2}', '', text)  # Remove timestamps like "0:24"
        text = re.sub(r'video|Video|VIDEO', '', text, flags=re.IGNORECASE)

        # Remove author bylines and metadata
        text = re.sub(r'By [A-Za-z\s]+|Share|Follow us|Subscribe', '', text, flags=re.IGNORECASE)

        # Remove excessive whitespace and line breaks
        text = re.sub(r'\s+', ' ', text)

        # Remove common unwanted elements
        unwanted_patterns = [
            r'Advertisement',
            r'Share this',
            r'Follow us',
            r'Subscribe to',
            r'Related Articles',
            r'More from',
            r'© \d{4}',
            r'View image in fullscreen',
            r'Illustration:',
            r'Getty Images',
            r'Shutterstock',
        ]

        for pattern in unwanted_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)

        # Remove multiple spaces and clean up
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove leading/trailing punctuation
        text = text.strip('.,;:!?')

        return text

# Test function
async def test_content_extractor():
    """Test content extraction"""
    extractor = ContentExtractor()

    test_urls = [
        "https://www.bbc.com/news/articles/cj4y159190go",
        "https://www.cnn.com/2024/09/29/climate/china-climate-emissions/index.html"
    ]

    for url in test_urls:
        print(f"\n🔍 Testing: {url}")
        result = await extractor.extract_content(url)

        if result['success']:
            print(f"✅ Title: {result['title']}")
            print(f"✅ Content length: {len(result['content'])} chars")
            print(f"✅ Domain: {result['source_domain']}")
        else:
            print(f"❌ Failed: {result['error']}")

if __name__ == "__main__":
    asyncio.run(test_content_extractor())
