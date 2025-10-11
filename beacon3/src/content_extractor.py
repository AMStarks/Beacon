#!/usr/bin/env python3
"""
Beacon 3 Content Extractor - Robust extraction with multiple fallback methods
"""

import asyncio
import aiohttp
import logging
import trafilatura
import requests
from urllib.parse import urlparse
from typing import Dict, Any, Optional
import brotli

logger = logging.getLogger(__name__)

class ContentExtractor:
    """Robust content extraction with multiple fallback methods"""

    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',  # Support Brotli compression
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        self.timeout = aiohttp.ClientTimeout(total=30)

    async def extract_content(self, url: str) -> Dict[str, Any]:
        """Extract content with multiple fallback methods"""
        logger.info(f"🚀 Starting robust content extraction for {url}")
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        # Try multiple extraction methods in order of preference
        extraction_methods = [
            ('aiohttp_trafilatura', self._extract_with_aiohttp_trafilatura),
            ('requests_trafilatura', self._extract_with_requests_trafilatura),
            ('aiohttp_direct', self._extract_with_aiohttp_direct),
            ('requests_direct', self._extract_with_requests_direct)
        ]
        
        for method_name, method_func in extraction_methods:
            try:
                logger.debug(f"🔄 Trying extraction method: {method_name}")
                result = await method_func(url)
                
                if result and result.get('success') and self._validate_content(result.get('content', '')):
                    logger.info(f"✅ Content extraction successful using {method_name}")
                    result['extraction_method'] = method_name
                    return result
                else:
                    logger.warning(f"⚠️ {method_name} failed or returned invalid content")
                    
            except Exception as e:
                logger.warning(f"⚠️ {method_name} failed with exception: {e}")
                continue
        
        # Domain-specific fallbacks for problematic sites

        # Washington Post fallback (try mobile/paywall bypass)
        if 'washingtonpost.com' in domain:
            try:
                logger.info("🧭 Domain rule: washingtonpost.com → try mobile/paywall bypass")
                mobile_url = url.replace('www.washingtonpost.com', 'www.washingtonpost.com/amphtml')
                strong_headers = dict(self.headers)
                strong_headers.update({
                    'Referer': 'https://www.google.com/',
                    'Cache-Control': 'no-cache'
                })
                r = requests.get(mobile_url, headers=strong_headers, timeout=15, allow_redirects=True)
                if r.status_code == 200:
                    html = r.text
                    # Try trafilatura on mobile version
                    extracted = trafilatura.extract(html, include_comments=False, include_tables=False, include_images=False, include_links=False)
                    if extracted and len(extracted) > 500:
                        return {
                            'success': True,
                            'title': '',
                            'content': extracted,
                            'author': '',
                            'publish_date': '',
                            'source_domain': domain,
                            'extraction_method': 'washingtonpost_mobile'
                        }
            except Exception as e:
                logger.warning(f"⚠️ Washington Post fallback failed: {e}")

        # NPR fallback (try different URL patterns)
        elif 'npr.org' in domain:
            try:
                logger.info("🧭 Domain rule: npr.org → try text version")
                text_url = url.replace('/sections/', '/text/')
                if text_url == url:
                    text_url = url + '?format=text'
                r = requests.get(text_url, headers=self.headers, timeout=15)
                if r.status_code == 200:
                    html = r.text
                    extracted = trafilatura.extract(html, include_comments=False, include_tables=False, include_images=False, include_links=False)
                    if extracted and len(extracted) > 300:
                        return {
                            'success': True,
                            'title': '',
                            'content': extracted,
                            'author': '',
                            'publish_date': '',
                            'source_domain': domain,
                            'extraction_method': 'npr_text'
                        }
            except Exception as e:
                logger.warning(f"⚠️ NPR fallback failed: {e}")

        # Guardian fallback (try different sections)
        elif 'theguardian.com' in domain:
            try:
                logger.info("🧭 Domain rule: theguardian.com → try article extraction")
                # Try to extract using newspaper3k as additional fallback
                try:
                    from newspaper import Article
                    article = Article(url)
                    article.download()
                    article.parse()
                    if article.text and len(article.text) > 300:
                        return {
                            'success': True,
                            'title': article.title,
                            'content': article.text,
                            'author': ', '.join(article.authors) if article.authors else '',
                            'publish_date': article.publish_date.isoformat() if article.publish_date else '',
                            'source_domain': domain,
                            'extraction_method': 'guardian_newspaper'
                        }
                except ImportError:
                    pass  # newspaper3k not available, continue with other methods
                except Exception as e:
                    logger.warning(f"⚠️ Guardian newspaper fallback failed: {e}")
            except Exception as e:
                logger.warning(f"⚠️ Guardian fallback failed: {e}")

        # Al Jazeera fallback
        elif 'aljazeera.com' in domain:
            try:
                logger.info("🧭 Domain rule: aljazeera.com → try English version")
                english_url = url.replace('/ar/', '/en/').replace('/es/', '/en/')
                if english_url != url:
                    r = requests.get(english_url, headers=self.headers, timeout=15)
                    if r.status_code == 200:
                        html = r.text
                        extracted = trafilatura.extract(html, include_comments=False, include_tables=False, include_images=False, include_links=False)
                        if extracted and len(extracted) > 300:
                            return {
                                'success': True,
                                'title': '',
                                'content': extracted,
                                'author': '',
                                'publish_date': '',
                                'source_domain': domain,
                                'extraction_method': 'aljazeera_english'
                            }
            except Exception as e:
                logger.warning(f"⚠️ Al Jazeera fallback failed: {e}")

        # Legacy ABC News fallback
        if 'abcnews.go.com' in domain:
            try:
                logger.info("🧭 Domain rule: abcnews.go.com → try AMP + CSS fallback")
                amp_url = url
                if '/amp' not in amp_url:
                    amp_url = url.rstrip('/') + '/amp'
                strong_headers = dict(self.headers)
                strong_headers.update({
                    'Referer': 'https://www.google.com/',
                    'Cache-Control': 'no-cache'
                })
                r = requests.get(amp_url, headers=strong_headers, timeout=15, allow_redirects=True)
                if r.status_code == 200:
                    html = r.text
                    # Try trafilatura first on AMP
                    extracted = trafilatura.extract(html, include_comments=False, include_tables=False, include_images=False, include_links=False)
                    if not extracted:
                        # CSS fallback for AMP body
                        try:
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(html, 'html.parser')
                            # Common AMP containers
                            candidates = [
                                'article',
                                'main',
                                'div[itemprop="articleBody"]',
                                'div[data-component="Article"]'
                            ]
                            text = ''
                            for sel in candidates:
                                node = soup.select_one(sel)
                                if node:
                                    text = node.get_text(' ', strip=True)
                                    if len(text) > 200:
                                        break
                            if text and len(text) > 200:
                                return {
                                    'success': True,
                                    'title': '',
                                    'content': text,
                                    'author': '',
                                    'publish_date': '',
                                    'source_domain': domain,
                                    'extraction_method': 'abcnews_amp_css'
                                }
                        except Exception as e:
                            logger.warning(f"⚠️ ABC AMP CSS fallback failed: {e}")
                    else:
                        return {
                            'success': True,
                            'title': '',
                            'content': extracted,
                            'author': '',
                            'publish_date': '',
                            'source_domain': domain,
                            'extraction_method': 'abcnews_amp_trafilatura'
                        }
                else:
                    logger.warning(f"⚠️ ABC AMP HTTP {r.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ ABC domain-specific fallback failed: {e}")
        
        logger.error(f"❌ All extraction methods failed for {url}")
        return {'success': False, 'error': 'All extraction methods failed'}

    async def _extract_with_aiohttp_trafilatura(self, url: str) -> Dict[str, Any]:
        """Extract content using aiohttp + trafilatura (primary method)"""
        logger.debug(f"🔄 Method 1: aiohttp + trafilatura for {url}")
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        logger.debug(f"📊 HTML content length: {len(html_content)} characters")
                        
                        # Extract with trafilatura
                        extracted = trafilatura.extract(html_content, include_comments=False, include_tables=False, include_images=False, include_links=False)
                        metadata = trafilatura.extract_metadata(html_content)
                        
                        if extracted:
                            return {
                                'success': True,
                                'title': metadata.title if metadata and metadata.title else '',
                                'content': extracted,
                                'author': metadata.author if metadata and metadata.author else '',
                                'publish_date': metadata.date if metadata and metadata.date else '',
                                'source_domain': urlparse(url).netloc
                            }
                    else:
                        logger.warning(f"⚠️ HTTP {response.status} for {url}")
        except Exception as e:
            logger.warning(f"⚠️ aiohttp_trafilatura failed: {e}")
        
        return {'success': False}
    
    async def _extract_with_requests_trafilatura(self, url: str) -> Dict[str, Any]:
        """Extract content using requests + trafilatura (fallback method)"""
        logger.debug(f"🔄 Method 2: requests + trafilatura for {url}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                html_content = response.text
                logger.debug(f"📊 HTML content length: {len(html_content)} characters")
                
                # Extract with trafilatura
                extracted = trafilatura.extract(html_content, include_comments=False, include_tables=False, include_images=False, include_links=False)
                metadata = trafilatura.extract_metadata(html_content)
                
                if extracted:
                    return {
                        'success': True,
                        'title': metadata.title if metadata and metadata.title else '',
                        'content': extracted,
                        'author': metadata.author if metadata and metadata.author else '',
                        'publish_date': metadata.date if metadata and metadata.date else '',
                        'source_domain': urlparse(url).netloc
                    }
            else:
                logger.warning(f"⚠️ HTTP {response.status_code} for {url}")
        except Exception as e:
            logger.warning(f"⚠️ requests_trafilatura failed: {e}")
        
        return {'success': False}
    
    async def _extract_with_aiohttp_direct(self, url: str) -> Dict[str, Any]:
        """Extract content using aiohttp direct (fallback method)"""
        logger.debug(f"🔄 Method 3: aiohttp direct for {url}")
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url, headers=self.headers) as response:
                    if response.status == 200:
                        html_content = await response.text()
                        logger.debug(f"📊 HTML content length: {len(html_content)} characters")
                        
                        # Simple text extraction (fallback)
                        import re
                        # Remove HTML tags and extract text
                        text = re.sub(r'<[^>]+>', ' ', html_content)
                        text = re.sub(r'\s+', ' ', text).strip()
                        
                        if len(text) > 200:
                            return {
                                'success': True,
                                'title': '',
                                'content': text,
                                'author': '',
                                'publish_date': '',
                                'source_domain': urlparse(url).netloc
                            }
                    else:
                        logger.warning(f"⚠️ HTTP {response.status} for {url}")
        except Exception as e:
            logger.warning(f"⚠️ aiohttp_direct failed: {e}")
        
        return {'success': False}
    
    async def _extract_with_requests_direct(self, url: str) -> Dict[str, Any]:
        """Extract content using requests direct (last resort)"""
        logger.debug(f"🔄 Method 4: requests direct for {url}")
        
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                html_content = response.text
                logger.debug(f"📊 HTML content length: {len(html_content)} characters")
                
                # Simple text extraction (last resort)
                import re
                # Remove HTML tags and extract text
                text = re.sub(r'<[^>]+>', ' ', html_content)
                text = re.sub(r'\s+', ' ', text).strip()
                
                if len(text) > 200:
                    return {
                        'success': True,
                        'title': '',
                        'content': text,
                        'author': '',
                        'publish_date': '',
                        'source_domain': urlparse(url).netloc
                    }
            else:
                logger.warning(f"⚠️ HTTP {response.status_code} for {url}")
        except Exception as e:
            logger.warning(f"⚠️ requests_direct failed: {e}")
        
        return {'success': False}

    def _validate_content(self, content: str) -> bool:
        """Validate content quality"""
        logger.debug(f"🔍 Validating content quality")
        
        # Check minimum length
        if len(content) < 200:
            logger.debug(f"⚠️ Content too short: {len(content)} characters")
            return False
        
        # Check for meaningful content patterns
        content_lower = content.lower()
        
        # Look for article indicators
        article_indicators = [
            'said', 'told', 'according to', 'reported', 'announced',
            'police', 'officials', 'authorities', 'government'
        ]
        
        indicator_count = sum(1 for indicator in article_indicators if indicator in content_lower)
        
        if indicator_count < 2:
            logger.debug(f"⚠️ Insufficient article indicators: {indicator_count}")
            return False
        
        # Check for proper names (capitalized words)
        words = content.split()
        proper_names = [word for word in words if word.istitle() and len(word) > 2]
        
        if len(proper_names) < 3:
            logger.debug(f"⚠️ Insufficient proper names: {len(proper_names)}")
            return False
        
        logger.debug(f"✅ Content validation passed")
        return True
