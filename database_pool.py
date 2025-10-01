#!/usr/bin/env python3
"""
Database connection pool for efficient database operations.
Reuses database connections to avoid overhead.
"""

import sqlite3
import threading
from typing import Optional
from contextlib import contextmanager

class DatabasePool:
    def __init__(self, db_path: str, max_connections: int = 5):
        self.db_path = db_path
        self.max_connections = max_connections
        self.connections = []
        self.lock = threading.Lock()
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize the connection pool"""
        for _ in range(self.max_connections):
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            self.connections.append(conn)
    
    @contextmanager
    def get_connection(self):
        """Get a database connection from the pool"""
        conn = None
        try:
            with self.lock:
                if self.connections:
                    conn = self.connections.pop()
                else:
                    # Create new connection if pool is empty
                    conn = sqlite3.connect(self.db_path, check_same_thread=False)
                    conn.row_factory = sqlite3.Row
            
            yield conn
        finally:
            if conn:
                with self.lock:
                    if len(self.connections) < self.max_connections:
                        self.connections.append(conn)
                    else:
                        conn.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> list:
        """Execute a query and return results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an update query and return affected rows"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount
    
    def close_all(self):
        """Close all connections in the pool"""
        with self.lock:
            for conn in self.connections:
                conn.close()
            self.connections.clear()

# Global database pool instance
_db_pool = None

def get_db_pool(db_path: str = "beacon_articles.db") -> DatabasePool:
    """Get the global database pool instance"""
    global _db_pool
    if _db_pool is None:
        _db_pool = DatabasePool(db_path)
    return _db_pool

def close_db_pool():
    """Close the global database pool"""
    global _db_pool
    if _db_pool:
        _db_pool.close_all()
        _db_pool = None
