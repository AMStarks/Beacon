#!/usr/bin/env python3
"""
Article caching system for similar patterns and identifiers.
Reduces redundant LLM calls for similar content.
"""

import json
import hashlib
import sqlite3
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import re

class ArticleCache:
    def __init__(self, db_path="beacon_articles.db"):
        self.db_path = db_path
        self.cache_table = "article_cache"
        self._create_cache_table()
    
    def _create_cache_table(self):
        """Create cache table for storing patterns and results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.cache_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE NOT NULL,
                content_pattern TEXT NOT NULL,
                identifiers TEXT NOT NULL,
                title TEXT,
                excerpt TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                use_count INTEGER DEFAULT 1
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate hash for content similarity"""
        # Normalize content for consistent hashing
        normalized = re.sub(r'\s+', ' ', content.lower().strip())
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def _extract_content_pattern(self, content: str) -> str:
        """Extract key pattern from content for similarity matching"""
        # Extract key phrases and entities
        content_lower = content.lower()
        
        # Key patterns to look for
        patterns = []
        
        # Location patterns
        location_patterns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', content)
        patterns.extend([loc for loc in location_patterns if len(loc) > 3])
        
        # Event patterns
        event_keywords = ['shooting', 'attack', 'crash', 'fire', 'explosion', 'bombing', 'stabbing']
        for keyword in event_keywords:
            if keyword in content_lower:
                patterns.append(keyword)
        
        # Entity patterns
        entity_patterns = re.findall(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', content)
        patterns.extend([ent for ent in entity_patterns if len(ent.split()) == 2])
        
        return ' '.join(patterns[:10])  # Limit to 10 patterns
    
    def get_cached_identifiers(self, content: str) -> Optional[Dict]:
        """Get cached identifiers for similar content"""
        content_hash = self._generate_content_hash(content)
        content_pattern = self._extract_content_pattern(content)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # First try exact hash match
        cursor.execute(f"""
            SELECT identifiers FROM {self.cache_table} 
            WHERE content_hash = ?
        """, (content_hash,))
        
        result = cursor.fetchone()
        if result:
            cursor.execute(f"""
                UPDATE {self.cache_table} 
                SET last_used = ?, use_count = use_count + 1
                WHERE content_hash = ?
            """, (datetime.now(), content_hash))
            conn.commit()
            conn.close()
            return json.loads(result[0])
        
        # Try pattern similarity match
        cursor.execute(f"""
            SELECT identifiers, content_pattern FROM {self.cache_table}
            WHERE last_used >= ?
        """, (datetime.now() - timedelta(days=7),))  # Only recent cache
        
        best_match = None
        best_similarity = 0
        
        for row in cursor.fetchall():
            cached_identifiers = json.loads(row[0])
            cached_pattern = row[1]
            
            # Calculate pattern similarity
            similarity = self._calculate_pattern_similarity(content_pattern, cached_pattern)
            
            if similarity > 0.7 and similarity > best_similarity:  # High similarity threshold
                best_similarity = similarity
                best_match = cached_identifiers
        
        conn.close()
        
        if best_match:
            # Update cache usage
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(f"""
                UPDATE {self.cache_table} 
                SET last_used = ?, use_count = use_count + 1
                WHERE identifiers = ?
            """, (datetime.now(), json.dumps(best_match)))
            conn.commit()
            conn.close()
        
        return best_match
    
    def _calculate_pattern_similarity(self, pattern1: str, pattern2: str) -> float:
        """Calculate similarity between content patterns"""
        if not pattern1 or not pattern2:
            return 0.0
        
        words1 = set(pattern1.lower().split())
        words2 = set(pattern2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def cache_identifiers(self, content: str, identifiers: Dict, title: str = "", excerpt: str = ""):
        """Cache identifiers for future use"""
        content_hash = self._generate_content_hash(content)
        content_pattern = self._extract_content_pattern(content)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(f"""
                INSERT OR REPLACE INTO {self.cache_table} 
                (content_hash, content_pattern, identifiers, title, excerpt, created_at, last_used, use_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                content_hash,
                content_pattern,
                json.dumps(identifiers),
                title,
                excerpt,
                datetime.now(),
                datetime.now(),
                1
            ))
            
            conn.commit()
            
        except Exception as e:
            print(f"Cache error: {e}")
        finally:
            conn.close()
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT COUNT(*) FROM {self.cache_table}")
        total_entries = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT AVG(use_count) FROM {self.cache_table}")
        avg_usage = cursor.fetchone()[0] or 0
        
        cursor.execute(f"""
            SELECT COUNT(*) FROM {self.cache_table} 
            WHERE last_used >= ?
        """, (datetime.now() - timedelta(days=1),))
        recent_usage = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_entries": total_entries,
            "average_usage": avg_usage,
            "recent_usage": recent_usage
        }
    
    def cleanup_old_cache(self, days: int = 30):
        """Clean up old cache entries"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days)
        cursor.execute(f"""
            DELETE FROM {self.cache_table} 
            WHERE last_used < ?
        """, (cutoff_date,))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return deleted_count

def main():
    """Test the caching system"""
    cache = ArticleCache()
    
    # Test content
    test_content = "Four dead after gunman opens fire in a Michigan Mormon church service before setting it on fire."
    
    # Test caching
    test_identifiers = {
        'topic_primary': 'Church Shooting',
        'topic_secondary': 'Mass Violence',
        'entity_primary': 'Thomas Sanford',
        'entity_secondary': 'FBI',
        'location_primary': 'Michigan',
        'event_or_policy': 'Church Attack'
    }
    
    cache.cache_identifiers(test_content, test_identifiers, "Test Title", "Test Excerpt")
    
    # Test retrieval
    cached = cache.get_cached_identifiers(test_content)
    print(f"Cached identifiers: {cached}")
    
    # Test stats
    stats = cache.get_cache_stats()
    print(f"Cache stats: {stats}")

if __name__ == "__main__":
    main()
