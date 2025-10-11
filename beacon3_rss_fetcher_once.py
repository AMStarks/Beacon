#!/usr/bin/env python3
"""
Beacon 3 RSS Feed Fetcher - High-volume, reliable news collection
Fetches articles from curated RSS feeds and enqueues for processing
"""

import feedparser
import json
import sys
import hashlib
import sqlite3
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse
import logging
import re

# Setup paths
sys.path.insert(0, '/root/beacon3/src')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class RSSFetcher:
    """Fetch and enqueue articles from RSS feeds"""
    
    def __init__(self, config_path='/root/beacon3/beacon3_rss_feeds.json', db_path='/root/beacon3/beacon3_articles.db'):
        self.config_path = config_path
        self.db_path = db_path
        self.stats = {
            'feeds_processed': 0,
            'feeds_failed': 0,
            'items_checked': 0,
            'items_enqueued': 0,
            'items_duplicate': 0,
            'items_invalid': 0
        }
        # Age filter (days)
        self.max_age_days = 7
        # Hard blocklist for paywalled/problematic sources
        self.blocked_domains = set([
            'wsj.com', 'www.wsj.com',
            'bloomberg.com', 'www.bloomberg.com',
            'latimes.com', 'www.latimes.com',
            'nytimes.com', 'www.nytimes.com',
            'abcnews.go.com'
        ])
        # Heuristics to filter low-quality commerce/deals content
        self.commerce_path_keywords = set([
            'deal', 'deals', 'coupon', 'promo', 'promotion',
            'black-friday', 'prime-day', 'cyber-monday', 'sale', 'bargains', 'discount'
        ])
        self.commerce_title_patterns = [
            r"\bprime\s*day\b",
            r"\bblack\s*friday\b",
            r"\bcyber\s*monday\b",
            r"\bdeals?\b",
            r"\bsale\b",
            r"\bdiscount\b",
            r"\bsave\s*\$?\d+%?\b",
            r"\$\s?\d+\s?(off|deal|sale)?",
            r"\bunder\s*\$\s?\d+\b",
            r"\bbest\s+[^\s]+\s+deals\b"
        ]
        # Domain-specific deal sections (path contains these tokens)
        self.commerce_domain_path_tokens = {
            'zdnet.com': ['deals', 'amazon-prime-day', 'black-friday'],
            'cnet.com': ['deals', 'black-friday', 'prime-day'],
            'theverge.com': ['deals'],
            'techradar.com': ['deals'],
        }

        # Domain/path block rules for anti-bot, paywall, or non-article sections
        self.domain_path_block_rules = {
            'theguardian.com': ['/video/'],
            'npr.org': ['/picture-show/'],
            'espn.com': ['/game/', 'gameId=', '/games', '/live/'],
        }
        # Generic path blocks (applied to any domain)
        self.generic_path_blocks = ['/video/', '/live/', '/gallery/', '/galleries/']
        
    def normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication"""
        try:
            # Parse URL
            parsed = urlparse(url)
            
            # Remove common tracking parameters
            tracking_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 
                              'fbclid', 'gclid', 'ref', 'source', 'campaign']
            
            # Normalize scheme to https
            scheme = 'https' if parsed.scheme == 'http' else parsed.scheme
            
            # Remove www prefix
            netloc = parsed.netloc.lower()
            if netloc.startswith('www.'):
                netloc = netloc[4:]
            
            # Remove trailing slash from path
            path = parsed.path.rstrip('/')
            
            # Reconstruct clean URL (without query params for now - simplifies deduplication)
            normalized = urlunparse((scheme, netloc, path, '', '', ''))
            return normalized
            
        except Exception as e:
            logger.warning(f"Failed to normalize URL {url}: {e}")
            return url.lower().strip()
    
    def url_hash(self, url: str) -> str:
        """Generate hash for URL deduplication"""
        normalized = self.normalize_url(url)
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def url_exists(self, url: str) -> bool:
        """Check if URL already exists in database"""
        try:
            normalized_url = self.normalize_url(url)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Check both articles table (by URL hash) and processing_queue (by original URL)
            cursor.execute('''
                SELECT 1 FROM articles 
                WHERE url = ? OR url = ?
                LIMIT 1
            ''', (url, normalized_url))
            
            exists = cursor.fetchone() is not None
            conn.close()
            
            return exists
            
        except Exception as e:
            logger.warning(f"Error checking URL existence: {e}")
            return False  # Assume doesn't exist if check fails
    
    def enqueue_article(self, url: str, original_title: str = None, source_domain: str = None) -> bool:
        """Add article URL to processing queue (with basic metadata)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert into articles table first
            cursor.execute('''
                INSERT INTO articles (url, original_title, source_domain, status, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', datetime('now'), datetime('now'))
            ''', (url, (original_title or '').strip(), (source_domain or '').strip()))
            
            article_id = cursor.lastrowid
            
            # Add to processing queue
            cursor.execute('''
                INSERT INTO processing_queue (article_id, status, created_at)
                VALUES (?, 'pending', datetime('now'))
            ''', (article_id,))
            
            conn.commit()
            conn.close()
            
            logger.debug(f"✅ Enqueued article {article_id}: {url[:80]}")
            return True
            
        except sqlite3.IntegrityError as e:
            # URL already exists (UNIQUE constraint)
            logger.debug(f"⏭️  Duplicate URL (integrity): {url[:60]}")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to enqueue {url}: {e}")
            return False
    
    def is_valid_article_url(self, url: str, title: str) -> bool:
        """Validate if URL and title look like a real article"""
        if not url or not title:
            return False
        
        # Must be http/https
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Title must be meaningful length
        if len(title.strip()) < 10:
            return False
        
        # Skip common non-article patterns
        skip_patterns = [
            '/tag/', '/category/', '/author/', '/page/',
            '/feed/', '/rss/', '/archive/', '/search/',
            'javascript:', 'mailto:', '#'
        ]
        
        url_lower = url.lower()
        if any(pattern in url_lower for pattern in skip_patterns):
            return False
        
        # Skip if title looks like metadata
        title_lower = title.lower().strip()
        skip_title_patterns = [
            'rss feed', 'subscribe', 'newsletter', 'follow us',
            'advertisement', 'sponsored'
        ]
        
        if any(pattern in title_lower for pattern in skip_title_patterns):
            return False
        
        return True

    def is_commerce_post(self, url: str, title: str, summary: str, tags) -> bool:
        """Detect low-quality commerce/deals content to skip ingestion"""
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower().lstrip('www.')
            path = parsed.path.lower()

            # Domain + path token rules
            for domain, tokens in self.commerce_domain_path_tokens.items():
                if domain in host and any(tok in path for tok in tokens):
                    logging.debug(f"🧹 Skipping commerce by domain/path: {host}{path}")
                    return True

            # Generic path keyword rules
            if any(tok in path for tok in self.commerce_path_keywords):
                logging.debug(f"🧹 Skipping commerce by path keywords: {path}")
                return True

            # Title/summary regex rules
            hay = f"{title}\n{summary}".lower()
            for pat in self.commerce_title_patterns:
                if re.search(pat, hay, re.IGNORECASE):
                    logging.debug(f"🧹 Skipping commerce by title/summary pattern: '{title[:80]}'")
                    return True

            # Tag/category rules (RSS tags)
            if tags:
                tag_terms = []
                for t in tags:
                    term = None
                    if isinstance(t, dict):
                        term = t.get('term') or t.get('label')
                    else:
                        term = str(t)
                    if term:
                        tag_terms.append(term.lower())
                if any(x in tag_terms for x in ['deals', 'deal', 'commerce', 'shopping']):
                    logging.debug(f"🧹 Skipping commerce by tags: {tag_terms[:5]}")
                    return True

        except Exception:
            # On any detection error, do not block the article
            return False

        return False

    def is_blocked_by_path(self, url: str) -> bool:
        """Block domain/path combos that are known to fail (paywalls, non-articles)."""
        try:
            parsed = urlparse(url)
            host = parsed.netloc.lower().lstrip('www.')
            path_q = (parsed.path + '?' + (parsed.query or '')).lower()

            # Domain-specific rules
            for domain, tokens in self.domain_path_block_rules.items():
                if domain in host and any(tok in path_q for tok in tokens):
                    return True

            # Generic rules
            if any(tok in path_q for tok in self.generic_path_blocks):
                return True

        except Exception:
            return False
        return False
    
    def fetch_feed(self, feed_config: dict) -> dict:
        """Fetch and process a single RSS feed"""
        feed_url = feed_config['url']
        feed_name = feed_config['name']
        max_items = feed_config.get('max_items', 10)
        
        logger.info(f"📡 Fetching {feed_name} ({feed_url})")
        
        result = {
            'feed_name': feed_name,
            'success': False,
            'items_checked': 0,
            'items_enqueued': 0,
            'error': None
        }
        
        try:
            # Parse RSS feed
            feed = feedparser.parse(feed_url)
            
            # Check for parsing errors
            if hasattr(feed, 'bozo') and feed.bozo:
                logger.warning(f"⚠️  Feed parsing issue for {feed_name}: {feed.bozo_exception}")
            
            # Check if feed has entries
            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                logger.warning(f"⚠️  No entries found in {feed_name}")
                result['error'] = 'No entries'
                return result
            
            logger.debug(f"📊 Found {len(feed.entries)} entries in {feed_name}")
            
            # Process entries (limit to max_items)
            from datetime import datetime, timezone, timedelta
            cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)

            for entry in feed.entries[:max_items]:
                result['items_checked'] += 1
                self.stats['items_checked'] += 1
                
                # Extract URL and title
                url = entry.get('link', '')
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                tags = entry.get('tags', [])
                source_domain = urlparse(url).netloc.lower()

                # Age gate: skip items older than max_age_days (use published/updated if available)
                try:
                    dt_struct = entry.get('published_parsed') or entry.get('updated_parsed')
                    if dt_struct:
                        dt = datetime(*dt_struct[:6], tzinfo=timezone.utc)
                        if dt < cutoff:
                            logger.info(f"🕒 Skipped old article (> {self.max_age_days}d): {title[:80]}")
                            self.stats['items_invalid'] += 1
                            continue
                    else:
                        # No date provided: conservatively skip
                        logger.info(f"🕒 Skipped undated article (no published/updated): {title[:80]}")
                        self.stats['items_invalid'] += 1
                        continue
                except Exception:
                    logger.info(f"🕒 Skipped article due to date parse error: {title[:80]}")
                    self.stats['items_invalid'] += 1
                    continue
                
                # Skip hard-blocked domains
                if source_domain in self.blocked_domains:
                    logger.info(f"🛑 Skipped blocked domain: {source_domain} :: {title[:80]}")
                    self.stats['items_invalid'] += 1
                    continue
                
                # Validate
                if not self.is_valid_article_url(url, title):
                    logger.debug(f"⚠️  Invalid article: {title[:60]}")
                    self.stats['items_invalid'] += 1
                    continue

                # Skip low-quality commerce/deals content
                if self.is_commerce_post(url, title, summary, tags):
                    logger.info(f"🧹 Skipped commerce/deal post: {title[:80]}")
                    self.stats['items_invalid'] += 1
                    continue

                # Skip known-bad domain/path combinations
                if self.is_blocked_by_path(url):
                    logger.info(f"🛑 Skipped by path rules: {url[:120]}")
                    self.stats['items_invalid'] += 1
                    continue
                
                # Check if already exists
                if self.url_exists(url):
                    logger.debug(f"⏭️  Duplicate: {title[:60]}")
                    self.stats['items_duplicate'] += 1
                    continue
                
                # Enqueue new article
                if self.enqueue_article(url, original_title=title, source_domain=source_domain):
                    result['items_enqueued'] += 1
                    self.stats['items_enqueued'] += 1
                    logger.info(f"✅ Enqueued from {feed_name}: {title[:60]}")
            
            result['success'] = True
            self.stats['feeds_processed'] += 1
            
            logger.info(f"✅ {feed_name}: {result['items_enqueued']}/{result['items_checked']} new articles")
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch {feed_name}: {e}")
            result['error'] = str(e)
            self.stats['feeds_failed'] += 1
        
        return result
    
    def fetch_all_feeds(self, priority_filter=None):
        """Fetch articles from all configured feeds"""
        logger.info("🚀 Starting RSS feed collection")
        
        try:
            # Load configuration
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            feeds = config.get('feeds', [])
            settings = config.get('settings', {})
            max_items = settings.get('max_items_per_feed', 10)
            max_total = settings.get('max_total_enqueues_per_run', 50)
            
            logger.info(f"📋 Loaded {len(feeds)} feeds from config")
            
            # Filter by priority if specified
            if priority_filter:
                feeds = [f for f in feeds if f.get('priority') == priority_filter]
                logger.info(f"🎯 Filtered to {len(feeds)} {priority_filter} priority feeds")
            
            # Process each feed
            for feed_config in feeds:
                # Respect global cap across all feeds
                if self.stats['items_enqueued'] >= max_total:
                    logger.info(f"⏹️  Reached max_total_enqueues_per_run={max_total}, stopping early")
                    break
                feed_config['max_items'] = max_items
                self.fetch_feed(feed_config)
            
            # Print summary
            logger.info("=" * 60)
            logger.info("📊 RSS COLLECTION SUMMARY")
            logger.info(f"   Feeds processed: {self.stats['feeds_processed']}")
            logger.info(f"   Feeds failed: {self.stats['feeds_failed']}")
            logger.info(f"   Items checked: {self.stats['items_checked']}")
            logger.info(f"   Items enqueued: {self.stats['items_enqueued']}")
            logger.info(f"   Items duplicate: {self.stats['items_duplicate']}")
            logger.info(f"   Items invalid: {self.stats['items_invalid']}")
            logger.info("=" * 60)
            
            # Output JSON for monitoring
            print(json.dumps({
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'stats': self.stats
            }))
            
        except Exception as e:
            logger.error(f"❌ Fatal error in fetch_all_feeds: {e}")
            import traceback
            logger.error(traceback.format_exc())
            print(json.dumps({
                'success': False,
                'error': str(e),
                'stats': self.stats
            }))

def main():
    """Main entry point"""
    fetcher = RSSFetcher()
    fetcher.fetch_all_feeds()

if __name__ == '__main__':
    main()

