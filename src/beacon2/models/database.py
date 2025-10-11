#!/usr/bin/env python3
"""
Beacon 2 Database Schema - Clean, normalized design
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

class Beacon2Database:
    """Clean database schema for Beacon 2"""

    def __init__(self, db_path: str = "beacon2_articles.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Create tables with proper relationships"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Articles table - core content
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS articles (
                    article_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL UNIQUE,
                    original_title TEXT,
                    generated_title TEXT,
                    excerpt TEXT,
                    content TEXT,
                    source_domain TEXT,
                    status TEXT DEFAULT 'pending', -- pending, processing, completed, failed
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP
                )
            ''')

            # Clusters table - article groupings
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clusters (
                    cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    summary TEXT,
                    article_count INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Article-cluster relationships
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS article_clusters (
                    article_id INTEGER NOT NULL,
                    cluster_id INTEGER NOT NULL,
                    similarity_score REAL,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (article_id, cluster_id),
                    FOREIGN KEY (article_id) REFERENCES articles(article_id),
                    FOREIGN KEY (cluster_id) REFERENCES clusters(cluster_id)
                )
            ''')

            # Processing queue for autonomous operation
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS processing_queue (
                    queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    article_id INTEGER NOT NULL,
                    priority INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'queued', -- queued, processing, completed, failed
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    FOREIGN KEY (article_id) REFERENCES articles(article_id)
                )
            ''')

            # System status for monitoring
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_status (
                    status_id INTEGER PRIMARY KEY DEFAULT 1,
                    last_processed_article INTEGER DEFAULT 0,
                    total_articles INTEGER DEFAULT 0,
                    total_clusters INTEGER DEFAULT 0,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_running BOOLEAN DEFAULT 0,
                    CONSTRAINT single_row CHECK (status_id = 1)
                )
            ''')

            # Initialize system status if not exists
            cursor.execute('''
                INSERT OR IGNORE INTO system_status (status_id) VALUES (1)
            ''')

            # Indexes for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_status ON articles(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_articles_created ON articles(created_at)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_queue_status ON processing_queue(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_article_clusters ON article_clusters(cluster_id)')

            conn.commit()
            logger.info("✅ Beacon 2 database initialized")

    def add_article(self, url: str, original_title: str = None) -> int:
        """Add article to database"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO articles (url, original_title, status)
                VALUES (?, ?, 'pending')
            ''', (url, original_title))
            article_id = cursor.lastrowid
            conn.commit()
            logger.info(f"✅ Added article {article_id}: {url}")
            return article_id

    def get_pending_articles(self, limit: int = 10) -> List[Dict]:
        """Get articles ready for processing"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM articles
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def update_article_status(self, article_id: int, status: str, **kwargs):
        """Update article status and optional fields"""
        fields = ['status']
        values = [status]

        if 'generated_title' in kwargs:
            fields.append('generated_title')
            values.append(kwargs['generated_title'])

        if 'excerpt' in kwargs:
            fields.append('excerpt')
            values.append(kwargs['excerpt'])

        if 'content' in kwargs:
            fields.append('content')
            values.append(kwargs['content'])

        if 'source_domain' in kwargs:
            fields.append('source_domain')
            values.append(kwargs['source_domain'])

        if 'processed_at' in kwargs:
            fields.append('processed_at')
            values.append(kwargs['processed_at'])

        fields.append('updated_at')
        values.append(datetime.now(timezone.utc).isoformat())
        values.append(article_id)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = f'''
                UPDATE articles
                SET {', '.join(f'{field} = ?' for field in fields)}
                WHERE article_id = ?
            '''
            cursor.execute(query, values)
            conn.commit()

    def get_system_status(self) -> Dict:
        """Get current system status"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM system_status WHERE status_id = 1')
            row = cursor.fetchone()
            return dict(row) if row else {}

    def update_system_status(self, **kwargs):
        """Update system status"""
        fields = []
        values = []

        for key, value in kwargs.items():
            fields.append(f'{key} = ?')
            values.append(value)

        if not fields:
            return

        values.append(datetime.now(timezone.utc).isoformat())
        values.append(1)  # status_id

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = f'''
                UPDATE system_status
                SET {', '.join(fields)}, last_activity = ?
                WHERE status_id = ?
            '''
            cursor.execute(query, values)
            conn.commit()

    def add_to_queue(self, article_id: int, priority: int = 1):
        """Add article to processing queue"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO processing_queue (article_id, priority, status)
                VALUES (?, ?, 'queued')
            ''', (article_id, priority))
            conn.commit()

    def get_queue_item(self) -> Optional[Dict]:
        """Get next item from processing queue"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pq.*, a.url, a.original_title
                FROM processing_queue pq
                JOIN articles a ON pq.article_id = a.article_id
                WHERE pq.status = 'queued'
                ORDER BY pq.priority DESC, pq.created_at ASC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                # Mark as processing
                cursor.execute('UPDATE processing_queue SET status = ?, started_at = ? WHERE queue_id = ?',
                             ('processing', datetime.now(timezone.utc).isoformat(), row['queue_id']))
                conn.commit()
                return dict(row)
            return None

    def complete_queue_item(self, queue_id: int, success: bool = True, error: str = None):
        """Mark queue item as completed or failed"""
        status = 'completed' if success else 'failed'
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE processing_queue
                SET status = ?, completed_at = ?, error_message = ?
                WHERE queue_id = ?
            ''', (status, datetime.now(timezone.utc).isoformat(), error, queue_id))
            conn.commit()

    def create_cluster(self, title: str, summary: str) -> int:
        """Create a new cluster"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO clusters (title, summary)
                    VALUES (?, ?)
                ''', (title, summary))
                cluster_id = cursor.lastrowid
                conn.commit()
                logger.info(f"✅ Created cluster {cluster_id}: {title}")
                return cluster_id
        except Exception as e:
            logger.error(f"❌ Failed to create cluster '{title}': {e}")
            return 0

    def add_to_cluster(self, article_id: int, cluster_id: int, similarity_score: float = 1.0):
        """Add article to cluster"""
        logger.info(f"💾 add_to_cluster called: article {article_id} -> cluster {cluster_id} (sim: {similarity_score:.3f})")

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                logger.debug(f"🔍 Checking if article {article_id} already in cluster {cluster_id}")
                # Check if this exact relationship already exists
                cursor.execute('''
                    SELECT similarity_score FROM article_clusters
                    WHERE article_id = ? AND cluster_id = ?
                ''', (article_id, cluster_id))

                existing = cursor.fetchone()
                logger.debug(f"🔍 Existing relationship check result: {existing}")

                if existing:
                    logger.warning(f"⚠️ Article {article_id} already in cluster {cluster_id}, updating similarity")
                    logger.info(f"📈 Updating similarity from {existing[0]:.3f} to {similarity_score:.3f}")

                    # Update existing similarity score
                    cursor.execute('''
                        UPDATE article_clusters
                        SET similarity_score = ?, added_at = ?
                        WHERE article_id = ? AND cluster_id = ?
                    ''', (similarity_score, datetime.now(timezone.utc).isoformat(), article_id, cluster_id))

                    logger.debug(f"✅ Updated existing relationship for article {article_id} in cluster {cluster_id}")
                else:
                    logger.info(f"➕ Inserting new relationship: article {article_id} -> cluster {cluster_id}")

                    # Insert new relationship
                    cursor.execute('''
                        INSERT INTO article_clusters (article_id, cluster_id, similarity_score)
                        VALUES (?, ?, ?)
                    ''', (article_id, cluster_id, similarity_score))

                    logger.debug(f"✅ Inserted new relationship for article {article_id} in cluster {cluster_id}")

                logger.debug(f"📊 Updating cluster {cluster_id} article count")
                # Update cluster article count and timestamp
                cursor.execute('''
                    UPDATE clusters
                    SET article_count = (SELECT COUNT(*) FROM article_clusters WHERE cluster_id = ?),
                        updated_at = ?
                    WHERE cluster_id = ?
                ''', (cluster_id, datetime.now(timezone.utc).isoformat(), cluster_id))

                logger.debug(f"💾 Committing transaction for article {article_id} -> cluster {cluster_id}")
                conn.commit()
                logger.info(f"✅ Successfully added article {article_id} to cluster {cluster_id} (similarity: {similarity_score:.3f})")

        except Exception as e:
            logger.error(f"❌ Failed to add article {article_id} to cluster {cluster_id}: {e}")
            logger.error(f"🔍 Error type: {type(e).__name__}")
            import traceback
            logger.error(f"🔍 Traceback: {traceback.format_exc()}")
            raise

    def get_article_clusters(self, article_id: int) -> List[Dict]:
        """Get clusters for an article"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.*, ac.similarity_score
                FROM clusters c
                JOIN article_clusters ac ON c.cluster_id = ac.cluster_id
                WHERE ac.article_id = ?
                ORDER BY ac.similarity_score DESC
            ''', (article_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_recent_articles(self, limit: int = 50, include_processing: bool = False) -> List[Dict]:
        """Get recent articles for display or clustering"""
        logger.debug(f"📋 get_recent_articles called with limit={limit}, include_processing={include_processing}")

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Build the WHERE clause based on whether to include processing articles
            if include_processing:
                where_clause = "WHERE a.status IN ('completed', 'processing')"
                logger.debug(f"🔍 Including processing articles in query")
            else:
                where_clause = "WHERE a.status = 'completed'"
                logger.debug(f"🔍 Only including completed articles in query")

            logger.debug(f"🔍 Executing query to get recent articles")
            cursor.execute(f'''
                SELECT a.*, c.title as cluster_title
                FROM articles a
                LEFT JOIN article_clusters ac ON a.article_id = ac.article_id
                LEFT JOIN clusters c ON ac.cluster_id = c.cluster_id
                {where_clause}
                ORDER BY a.created_at DESC
                LIMIT ?
            ''', (limit,))

            results = cursor.fetchall()

            # Log details of returned articles for debugging
            processing_count = sum(1 for row in results if row['status'] == 'processing')
            completed_count = len(results) - processing_count

            logger.debug(f"📊 Query returned {len(results)} articles ({completed_count} completed, {processing_count} processing)")

            for i, row in enumerate(results[:5]):  # Log first 5 for brevity
                logger.debug(f"   Article {row['article_id']}: {row['created_at']} - {(row['generated_title'] or '')[:40]}... (status: {row['status']})")

            return [dict(row) for row in results]

    def get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Get a single article by ID"""
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

    def cleanup_empty_clusters(self) -> int:
        """Remove clusters with no articles"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Find empty clusters
                cursor.execute('''
                    SELECT c.cluster_id, c.title
                    FROM clusters c
                    LEFT JOIN article_clusters ac ON c.cluster_id = ac.cluster_id
                    WHERE ac.article_id IS NULL
                ''')

                empty_clusters = cursor.fetchall()
                if not empty_clusters:
                    return 0

                # Delete empty clusters
                cluster_ids = [cluster[0] for cluster in empty_clusters]  # cluster_id is first column
                cursor.execute(f'''
                    DELETE FROM clusters WHERE cluster_id IN ({','.join(['?'] * len(cluster_ids))})
                ''', cluster_ids)

                conn.commit()

                logger.info(f"🗑️ Cleaned up {len(empty_clusters)} empty clusters")
                for cluster in empty_clusters:
                    logger.info(f"  Removed cluster {cluster[0]}: {cluster[1]}")  # cluster_id and title

                return len(empty_clusters)

        except Exception as e:
            logger.error(f"❌ Failed to cleanup empty clusters: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Article stats
            cursor.execute('SELECT COUNT(*) FROM articles WHERE status = "completed"')
            completed_articles = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM articles WHERE status = "failed"')
            failed_articles = cursor.fetchone()[0]

            # Cluster stats
            cursor.execute('SELECT COUNT(*) FROM clusters')
            total_clusters = cursor.fetchone()[0]

            # Queue stats
            cursor.execute('SELECT COUNT(*) FROM processing_queue WHERE status = "queued"')
            queued_items = cursor.fetchone()[0]

            return {
                'completed_articles': completed_articles,
                'failed_articles': failed_articles,
                'total_clusters': total_clusters,
                'queued_items': queued_items,
                'total_articles': completed_articles + failed_articles
            }
