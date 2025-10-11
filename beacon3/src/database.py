#!/usr/bin/env python3
"""
Beacon 3 Database - Clean SQLite schema
"""

import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

class Beacon3Database:
    """Clean database schema for Beacon 3"""

    def __init__(self, db_path: str = "beacon3_articles.db"):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Create tables with proper relationships"""
        logger.info(f"🗄️ Initializing Beacon 3 database: {self.db_path}")
        
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
                    status TEXT DEFAULT 'pending',
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
                    status TEXT DEFAULT 'queued',
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

            # Cluster quality evaluations (audit snapshots)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cluster_evaluations (
                    eval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cluster_id INTEGER NOT NULL,
                    label TEXT, -- correct | mixed | duplicate | split_needed | should_merge
                    metrics_json TEXT NOT NULL,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (cluster_id) REFERENCES clusters(cluster_id)
                )
            ''')

            # Operator or automated feedback for clusters (merge/split/keep)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cluster_feedback (
                    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL, -- merge | split | keep
                    from_cluster_id INTEGER NOT NULL,
                    to_cluster_id INTEGER, -- when merging or referencing another cluster
                    reason TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (from_cluster_id) REFERENCES clusters(cluster_id),
                    FOREIGN KEY (to_cluster_id) REFERENCES clusters(cluster_id)
                )
            ''')

            # Parameters history for clustering (for tuning/canary)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS cluster_params_history (
                    params_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    params_json TEXT NOT NULL,
                    window_start TIMESTAMP,
                    window_end TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cluster_evals_cluster ON cluster_evaluations(cluster_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_cluster_feedback_from ON cluster_feedback(from_cluster_id)')

            conn.commit()
            logger.info("✅ Beacon 3 database initialized")

    def add_article(self, url: str, original_title: str = None) -> int:
        """Add article to database"""
        logger.info(f"📝 Adding article: {url}")
        
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

    def update_article_status(self, article_id: int, status: str, **kwargs):
        """Update article status and optional fields"""
        logger.debug(f"📝 Updating article {article_id} status to {status}")
        
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
            logger.debug(f"✅ Updated article {article_id}")

    def add_to_queue(self, article_id: int, priority: int = 1):
        """Add article to processing queue"""
        logger.debug(f"📝 Adding article {article_id} to queue with priority {priority}")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO processing_queue (article_id, priority, status)
                VALUES (?, ?, 'queued')
            ''', (article_id, priority))
            conn.commit()
            logger.debug(f"✅ Added article {article_id} to queue")

    def get_queue_item(self) -> Optional[Dict]:
        """Get next item from processing queue"""
        logger.debug(f"📋 Getting next queue item")
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pq.*, a.url, a.original_title
                FROM processing_queue pq
                JOIN articles a ON pq.article_id = a.article_id
                WHERE pq.status IN ('queued','pending')
                ORDER BY pq.priority DESC, pq.created_at ASC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            if row:
                # Mark as processing
                cursor.execute('UPDATE processing_queue SET status = ?, started_at = ? WHERE queue_id = ?',
                             ('processing', datetime.now(timezone.utc).isoformat(), row['queue_id']))
                conn.commit()
                logger.debug(f"✅ Retrieved queue item: article {row['article_id']}")
                return dict(row)
            logger.debug(f"📭 No items in queue")
            return None

    def complete_queue_item(self, queue_id: int, success: bool = True, error: str = None):
        """Mark queue item as completed or failed"""
        status = 'completed' if success else 'failed'
        logger.debug(f"📝 Completing queue item {queue_id} with status {status}")
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE processing_queue
                SET status = ?, completed_at = ?, error_message = ?
                WHERE queue_id = ?
            ''', (status, datetime.now(timezone.utc).isoformat(), error, queue_id))
            conn.commit()
            logger.debug(f"✅ Completed queue item {queue_id}")

    def create_cluster(self, title: str, summary: str) -> int:
        """Create a new cluster"""
        logger.info(f"🏗️ Creating cluster: {title}")
        
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
        logger.info(f"📝 Adding article {article_id} to cluster {cluster_id} (similarity: {similarity_score:.3f})")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Check if relationship already exists
                cursor.execute('''
                    SELECT similarity_score FROM article_clusters
                    WHERE article_id = ? AND cluster_id = ?
                ''', (article_id, cluster_id))

                existing = cursor.fetchone()

                if existing:
                    logger.debug(f"📝 Updating existing relationship for article {article_id} in cluster {cluster_id}")
                    cursor.execute('''
                        UPDATE article_clusters
                        SET similarity_score = ?, added_at = ?
                        WHERE article_id = ? AND cluster_id = ?
                    ''', (similarity_score, datetime.now(timezone.utc).isoformat(), article_id, cluster_id))
                else:
                    logger.debug(f"📝 Creating new relationship for article {article_id} in cluster {cluster_id}")
                    cursor.execute('''
                        INSERT INTO article_clusters (article_id, cluster_id, similarity_score)
                        VALUES (?, ?, ?)
                    ''', (article_id, cluster_id, similarity_score))

                # Update cluster article count
                cursor.execute('''
                    UPDATE clusters
                    SET article_count = (SELECT COUNT(*) FROM article_clusters WHERE cluster_id = ?),
                        updated_at = ?
                    WHERE cluster_id = ?
                ''', (cluster_id, datetime.now(timezone.utc).isoformat(), cluster_id))

                conn.commit()
                logger.info(f"✅ Successfully added article {article_id} to cluster {cluster_id}")

        except Exception as e:
            logger.error(f"❌ Failed to add article {article_id} to cluster {cluster_id}: {e}")
            raise

    def get_article_clusters(self, article_id: int) -> List[Dict]:
        """Get clusters for an article"""
        logger.debug(f"📋 Getting clusters for article {article_id}")
        
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
        logger.debug(f"📋 Getting recent articles (limit: {limit}, include_processing: {include_processing})")
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if include_processing:
                where_clause = "WHERE a.status IN ('completed', 'processing')"
            else:
                where_clause = "WHERE a.status = 'completed'"

            cursor.execute(f'''
                SELECT a.*, c.title as cluster_title
                FROM articles a
                LEFT JOIN article_clusters ac ON a.article_id = ac.article_id
                LEFT JOIN clusters c ON ac.cluster_id = c.cluster_id
                {where_clause}
                ORDER BY a.created_at DESC
                LIMIT ?
            ''', (limit,))

            results = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"📊 Retrieved {len(results)} recent articles")
            return results

    def get_article(self, article_id: int) -> Optional[Dict[str, Any]]:
        """Get a single article by ID"""
        logger.debug(f"📋 Getting article {article_id}")
        
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

    def update_system_status(self, **kwargs):
        """Update system status"""
        logger.debug(f"📝 Updating system status: {kwargs}")
        
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
            logger.debug(f"✅ Updated system status")

    def get_system_status(self) -> Dict:
        """Get current system status"""
        logger.debug(f"📋 Getting system status")
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM system_status WHERE status_id = 1')
            row = cursor.fetchone()
            return dict(row) if row else {}

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        logger.debug(f"📊 Getting database statistics")
        
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

            # Queue stats: count any items not yet finished (support 'queued', 'pending', 'processing')
            cursor.execute('SELECT COUNT(*) FROM processing_queue WHERE status IN ("queued","pending","processing")')
            queued_items = cursor.fetchone()[0]

            stats = {
                'completed_articles': completed_articles,
                'failed_articles': failed_articles,
                'total_clusters': total_clusters,
                'queued_items': queued_items,
                'total_articles': completed_articles + failed_articles
            }
            
            logger.debug(f"📊 Database stats: {stats}")
            return stats

    # ---------- Bolt-on: Cluster audit helpers ----------

    def get_clusters(self, limit: int = 200) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute('''
                SELECT * FROM clusters ORDER BY datetime(created_at) DESC LIMIT ?
            ''', (limit,))
            return [dict(r) for r in cur.fetchall()]

    def get_cluster_articles(self, cluster_id: int) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute('''
                SELECT a.*
                FROM articles a
                JOIN article_clusters ac ON a.article_id = ac.article_id
                WHERE ac.cluster_id = ? AND a.status = 'completed'
                ORDER BY datetime(a.created_at) DESC
            ''', (cluster_id,))
            return [dict(r) for r in cur.fetchall()]

    def get_singleton_articles(self, limit: int = 200) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute('''
                SELECT a.*
                FROM articles a
                LEFT JOIN article_clusters ac ON a.article_id = ac.article_id
                WHERE ac.cluster_id IS NULL AND a.status = 'completed'
                ORDER BY datetime(a.created_at) DESC
                LIMIT ?
            ''', (limit,))
            return [dict(r) for r in cur.fetchall()]

    def upsert_cluster_evaluation(self, cluster_id: int, metrics_json: str, label: Optional[str] = None, notes: Optional[str] = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO cluster_evaluations (cluster_id, label, metrics_json, notes)
                VALUES (?, ?, ?, ?)
            ''', (cluster_id, label, metrics_json, notes))
            conn.commit()
            return cur.lastrowid

    def get_recent_cluster_evaluations(self, limit: int = 100) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute('''
                SELECT * FROM cluster_evaluations ORDER BY datetime(created_at) DESC LIMIT ?
            ''', (limit,))
            return [dict(r) for r in cur.fetchall()]

    def insert_cluster_feedback(self, action: str, from_cluster_id: int, to_cluster_id: Optional[int] = None, reason: Optional[str] = None) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO cluster_feedback (action, from_cluster_id, to_cluster_id, reason)
                VALUES (?, ?, ?, ?)
            ''', (action, from_cluster_id, to_cluster_id, reason))
            conn.commit()
            return cur.lastrowid

    def save_cluster_params(self, params_json: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO cluster_params_history (params_json)
                VALUES (?)
            ''', (params_json,))
            conn.commit()
            return cur.lastrowid

    def get_current_cluster_params(self) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute('''
                SELECT params_json FROM cluster_params_history ORDER BY params_id DESC LIMIT 1
            ''')
            row = cur.fetchone()
            if not row:
                return None
            try:
                import json
                return json.loads(row['params_json'])
            except Exception:
                return None
