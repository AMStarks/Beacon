#!/usr/bin/env python3
"""
Similarity index for faster clustering comparisons.
Pre-computes and stores similarity scores between common identifier patterns.
"""

import sqlite3
import json
from typing import Dict, List, Tuple
import re

class SimilarityIndex:
    def __init__(self, db_path="beacon_articles.db"):
        self.db_path = db_path
        self.index_table = "similarity_index"
        self._create_index_table()
    
    def _create_index_table(self):
        """Create similarity index table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.index_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier1 TEXT NOT NULL,
                identifier2 TEXT NOT NULL,
                similarity_score REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(identifier1, identifier2)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _normalize_identifier(self, identifier: str) -> str:
        """Normalize identifier for consistent comparison"""
        if not identifier:
            return ""
        return identifier.lower().strip()
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two identifiers"""
        if not text1 or not text2:
            return 0.0
        
        text1 = self._normalize_identifier(text1)
        text2 = self._normalize_identifier(text2)
        
        if text1 == text2:
            return 1.0
        
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return 0.0
        
        jaccard = intersection / union
        
        # Boost for key words
        key_words = ['church', 'shooting', 'michigan', 'gunman', 'attack', 'fire', 'mormon', 'trump', 'peace', 'gaza']
        key_overlap = sum(1 for word in key_words if word in words1 and word in words2)
        
        if key_overlap > 0:
            jaccard = max(jaccard, 0.3 + (key_overlap * 0.2))
        
        return min(jaccard, 1.0)
    
    def get_similarity(self, identifier1: str, identifier2: str) -> float:
        """Get similarity score from index or calculate and store"""
        if not identifier1 or not identifier2:
            return 0.0
        
        # Normalize for lookup
        norm1 = self._normalize_identifier(identifier1)
        norm2 = self._normalize_identifier(identifier2)
        
        # Check if we have this pair in index
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT similarity_score FROM {self.index_table} 
            WHERE (identifier1 = ? AND identifier2 = ?) 
            OR (identifier1 = ? AND identifier2 = ?)
        """, (norm1, norm2, norm2, norm1))
        
        result = cursor.fetchone()
        
        if result:
            conn.close()
            return result[0]
        
        # Calculate and store similarity
        similarity = self._calculate_similarity(identifier1, identifier2)
        
        cursor.execute(f"""
            INSERT OR REPLACE INTO {self.index_table} 
            (identifier1, identifier2, similarity_score) 
            VALUES (?, ?, ?)
        """, (norm1, norm2, similarity))
        
        conn.commit()
        conn.close()
        
        return similarity
    
    def batch_calculate_similarities(self, identifiers: List[str]) -> Dict[Tuple[str, str], float]:
        """Calculate similarities for a batch of identifiers"""
        similarities = {}
        
        for i, id1 in enumerate(identifiers):
            for j, id2 in enumerate(identifiers[i+1:], i+1):
                similarity = self.get_similarity(id1, id2)
                similarities[(id1, id2)] = similarity
                similarities[(id2, id1)] = similarity  # Symmetric
        
        return similarities
    
    def get_stats(self) -> Dict:
        """Get index statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"SELECT COUNT(*) FROM {self.index_table}")
        total_pairs = cursor.fetchone()[0]
        
        cursor.execute(f"SELECT AVG(similarity_score) FROM {self.index_table}")
        avg_similarity = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "total_pairs": total_pairs,
            "average_similarity": avg_similarity
        }

def main():
    """Test the similarity index"""
    index = SimilarityIndex()
    
    # Test with some sample identifiers
    test_identifiers = [
        "Church shooting",
        "Michigan attack", 
        "Gunman opens fire",
        "Mormon church",
        "Mass violence"
    ]
    
    print("Testing similarity index...")
    
    for i, id1 in enumerate(test_identifiers):
        for j, id2 in enumerate(test_identifiers[i+1:], i+1):
            similarity = index.get_similarity(id1, id2)
            print(f"{id1} vs {id2}: {similarity:.3f}")
    
    stats = index.get_stats()
    print(f"\nIndex stats: {stats}")

if __name__ == "__main__":
    main()
