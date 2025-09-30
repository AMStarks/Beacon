#!/usr/bin/env python3
"""
Date Extraction Utility for Beacon
Extracts written dates from article content and manages sourced dates
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

class DateExtractor:
    """Extract and manage dates for articles"""
    
    def __init__(self):
        # Common date patterns in news articles
        self.date_patterns = [
            # ISO format: 2024-09-29, 2024-09-29T10:00:00Z
            r'\b(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?)?)\b',
            # US format: September 29, 2024, Sep 29, 2024
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b',
            # UK format: 29 September 2024, 29 Sep 2024
            r'\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}\b',
            # Short format: 29/09/2024, 09/29/2024
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b',
            # Relative dates: "5 days ago", "yesterday", "today"
            r'\b(\d+)\s+days?\s+ago\b',
            r'\b(yesterday|today|tomorrow)\b',
            # Time-based: "2 hours ago", "3 minutes ago"
            r'\b(\d+)\s+(?:hours?|minutes?|hrs?|mins?)\s+ago\b'
        ]
        
        # Month name mappings
        self.month_names = {
            'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
            'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
            'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'october': 10, 'oct': 10,
            'november': 11, 'nov': 11, 'december': 12, 'dec': 12
        }
    
    def get_sourced_date(self) -> str:
        """Get current timestamp as sourced date"""
        return datetime.now(timezone.utc).isoformat()
    
    def extract_written_date(self, article_content: str, article_url: str = "") -> Optional[str]:
        """
        Extract written date from article content
        Returns ISO format date string or None if not found
        """
        try:
            # Look for dates in the first 2000 characters (usually in header/intro)
            content_sample = article_content[:2000]
            
            # Try each pattern
            for pattern in self.date_patterns:
                matches = re.findall(pattern, content_sample, re.IGNORECASE)
                if matches:
                    for match in matches:
                        parsed_date = self._parse_date_match(match)
                        if parsed_date:
                            logger.info(f"📅 Extracted written date: {parsed_date}")
                            return parsed_date
            
            # If no date found in content, try to extract from URL patterns
            if article_url:
                url_date = self._extract_date_from_url(article_url)
                if url_date:
                    logger.info(f"📅 Extracted date from URL: {url_date}")
                    return url_date
            
            logger.warning("⚠️ No written date found in article")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extracting written date: {e}")
            return None
    
    def _parse_date_match(self, date_str: str) -> Optional[str]:
        """Parse a matched date string into ISO format"""
        try:
            # Handle relative dates
            if date_str.lower() in ['yesterday', 'today', 'tomorrow']:
                now = datetime.now(timezone.utc)
                if date_str.lower() == 'yesterday':
                    return (now.replace(hour=0, minute=0, second=0, microsecond=0) - 
                           timedelta(days=1)).isoformat()
                elif date_str.lower() == 'today':
                    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                elif date_str.lower() == 'tomorrow':
                    return (now.replace(hour=0, minute=0, second=0, microsecond=0) + 
                           timedelta(days=1)).isoformat()
            
            # Handle "X days ago" format
            if 'days ago' in date_str.lower():
                days = int(re.search(r'\d+', date_str).group())
                ago_date = datetime.now(timezone.utc) - timedelta(days=days)
                return ago_date.isoformat()
            
            # Handle "X hours ago" format
            if 'hours ago' in date_str.lower() or 'hrs ago' in date_str.lower():
                hours = int(re.search(r'\d+', date_str).group())
                ago_date = datetime.now(timezone.utc) - timedelta(hours=hours)
                return ago_date.isoformat()
            
            # Handle ISO format
            if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
                if 'T' in date_str:
                    return datetime.fromisoformat(date_str.replace('Z', '+00:00')).isoformat()
                else:
                    return datetime.fromisoformat(date_str).isoformat()
            
            # Handle month name formats
            for month_name, month_num in self.month_names.items():
                if month_name in date_str.lower():
                    # Extract year and day
                    year_match = re.search(r'\b(20\d{2})\b', date_str)
                    day_match = re.search(r'\b(\d{1,2})\b', date_str)
                    
                    if year_match and day_match:
                        year = int(year_match.group(1))
                        day = int(day_match.group(1))
                        return datetime(year, month_num, day, tzinfo=timezone.utc).isoformat()
            
            # Handle MM/DD/YYYY or DD/MM/YYYY format
            if '/' in date_str:
                parts = date_str.split('/')
                if len(parts) == 3:
                    try:
                        # Try MM/DD/YYYY first (US format)
                        month, day, year = map(int, parts)
                        if 1 <= month <= 12 and 1 <= day <= 31:
                            return datetime(year, month, day, tzinfo=timezone.utc).isoformat()
                    except ValueError:
                        # Try DD/MM/YYYY (UK format)
                        try:
                            day, month, year = map(int, parts)
                            if 1 <= month <= 12 and 1 <= day <= 31:
                                return datetime(year, month, day, tzinfo=timezone.utc).isoformat()
                        except ValueError:
                            pass
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error parsing date '{date_str}': {e}")
            return None
    
    def _extract_date_from_url(self, url: str) -> Optional[str]:
        """Extract date from URL patterns like /2024/09/29/ or /2024-09-29/"""
        try:
            # Look for YYYY/MM/DD or YYYY-MM-DD patterns in URL
            date_patterns = [
                r'/(\d{4})/(\d{2})/(\d{2})/',
                r'/(\d{4})-(\d{2})-(\d{2})/',
                r'/(\d{4})(\d{2})(\d{2})/'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, url)
                if match:
                    year, month, day = map(int, match.groups())
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        return datetime(year, month, day, tzinfo=timezone.utc).isoformat()
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error extracting date from URL: {e}")
            return None
    
    def add_dates_to_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add sourced and written dates to an article
        Returns article with added date fields
        """
        # Add sourced date (when article enters Beacon)
        article['sourced_date'] = self.get_sourced_date()
        
        # Extract written date from content
        written_date = self.extract_written_date(
            article.get('content', ''),
            article.get('url', '')
        )
        
        if written_date:
            article['written_date'] = written_date
        else:
            # If no written date found, use sourced date as fallback
            article['written_date'] = article['sourced_date']
            logger.warning(f"⚠️ No written date found for article, using sourced date: {article['title']}")
        
        return article

# Global instance
date_extractor = DateExtractor()
