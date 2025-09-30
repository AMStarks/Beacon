#!/usr/bin/env python3
"""
Beacon Database - SQLite database for storing articles with sourced and written dates
"""

import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BeaconDatabase:
    """Database class for storing Beacon articles with sourced and written dates"""
    
    def __init__(self, db_path: str = "beacon_articles.db"):
        """Initialize the database connection"""
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Create the articles table if it doesn't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create articles table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS articles (
                        article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        url TEXT NOT NULL,
                        date_sourced TEXT NOT NULL,
                        date_written TEXT,
                        title TEXT NOT NULL,
                        content TEXT,
                        excerpt TEXT,
                        source TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                
                # Create index on URL for faster lookups
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_url ON articles(url)
                ''')
                
                conn.commit()
                logger.info("✅ Database initialized successfully")
                
        except Exception as e:
            logger.error(f"❌ Failed to initialize database: {e}")
            raise
    
    def add_article(self, url: str, title: str, content: str = None, 
                   excerpt: str = None, source: str = None, date_written: str = None) -> int:
        """Add a new article to the database
        
        Args:
            url: Article URL
            title: Article title
            content: Article content (optional)
            excerpt: Article excerpt (optional)
            source: Article source (optional)
            date_written: When article was written (optional)
            
        Returns:
            int: The assigned article ID
        """
        try:
            # Get current UTC timestamp for date_sourced
            date_sourced = datetime.now(timezone.utc).isoformat()
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO articles (url, date_sourced, date_written, title, content, excerpt, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (url, date_sourced, date_written, title, content, excerpt, source))
                
                article_id = cursor.lastrowid
                conn.commit()
                
                logger.info(f"✅ Article added with ID {article_id}: {title[:50]}...")
                return article_id
                
        except Exception as e:
            logger.error(f"❌ Failed to add article: {e}")
            raise
    
    def get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Get an article by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM articles WHERE article_id = ?
                ''', (article_id,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get article {article_id}: {e}")
            return None
    
    def get_all_articles(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all articles, ordered by newest first"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM articles 
                    ORDER BY created_at DESC 
                    LIMIT ?
                ''', (limit,))
                
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"❌ Failed to get articles: {e}")
            return []
    
    def get_article_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """Get an article by URL"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT * FROM articles WHERE url = ?
                ''', (url,))
                
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get article by URL: {e}")
            return None
    
    def update_article(self, article_id: int, **kwargs) -> bool:
        """Update an article with new data"""
        try:
            # Build dynamic update query
            fields = []
            values = []
            
            for key, value in kwargs.items():
                if key in ['url', 'date_sourced', 'date_written', 'title', 'content', 'excerpt', 'source']:
                    fields.append(f"{key} = ?")
                    values.append(value)
            
            if not fields:
                return False
            
            values.append(article_id)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute(f'''
                    UPDATE articles 
                    SET {', '.join(fields)}
                    WHERE article_id = ?
                ''', values)
                
                conn.commit()
                logger.info(f"✅ Article {article_id} updated")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to update article {article_id}: {e}")
            return False
    
    def delete_article(self, article_id: int) -> bool:
        """Delete an article by ID"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    DELETE FROM articles WHERE article_id = ?
                ''', (article_id,))
                
                conn.commit()
                logger.info(f"✅ Article {article_id} deleted")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to delete article {article_id}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total articles
                cursor.execute('SELECT COUNT(*) FROM articles')
                total_articles = cursor.fetchone()[0]
                
                # Articles with written dates
                cursor.execute('SELECT COUNT(*) FROM articles WHERE date_written IS NOT NULL')
                articles_with_written_date = cursor.fetchone()[0]
                
                # Latest article
                cursor.execute('''
                    SELECT title, date_sourced FROM articles 
                    ORDER BY created_at DESC LIMIT 1
                ''')
                latest = cursor.fetchone()
                
                return {
                    'total_articles': total_articles,
                    'articles_with_written_date': articles_with_written_date,
                    'latest_article': {
                        'title': latest[0] if latest else None,
                        'date_sourced': latest[1] if latest else None
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {}

# Test the database
if __name__ == "__main__":
    print("🧪 Testing Beacon Database...")
    
    # Initialize database
    db = BeaconDatabase("test_beacon.db")
    
    # Add a test article
    article_id = db.add_article(
        url="https://www.bbc.com/news/articles/cj4y159190go",
        title="China makes landmark pledge to cut its climate emissions",
        content="China, the world's biggest source of planet-warming gases...",
        source="BBC News",
        date_written="2024-09-29T00:00:00+00:00"
    )
    
    print(f"✅ Added article with ID: {article_id}")
    
    # Get the article
    article = db.get_article(article_id)
    print(f"✅ Retrieved article: {article['title']}")
    print(f"   Article ID: {article['article_id']}")
    print(f"   Date Sourced: {article['date_sourced']}")
    print(f"   Date Written: {article['date_written']}")
    
    # Get stats
    stats = db.get_stats()
    print(f"✅ Database stats: {stats}")
    
    print("🎉 Database test completed successfully!")
