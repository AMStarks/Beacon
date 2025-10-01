#!/usr/bin/env python3
"""
Incremental clustering processor for only processing new articles against recent ones.
Avoids reprocessing all articles for each new addition.
"""

import sqlite3
import json
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import time

class IncrementalClustering:
    def __init__(self, db_path="beacon_articles.db"):
        self.db_path = db_path
        self.recent_days = 30  # Only compare against articles from last 30 days
        self.max_comparisons = 100  # Limit comparisons per new article
    
    def process_incremental_clustering(self, new_article_id: int) -> Dict:
        """Process clustering for a single new article against recent articles only"""
        start_time = time.time()
        
        # Get new article data
        new_article = self._get_article_by_id(new_article_id)
        if not new_article:
            return {"error": "Article not found", "processing_time": 0}
        
        # Get identifiers
        identifiers = self._parse_identifiers(new_article)
        if not identifiers or not any(identifiers.values()):
            return {"error": "No identifiers found", "processing_time": 0}
        
        # Get recent articles for comparison
        recent_articles = self._get_recent_articles_for_comparison(new_article_id)
        
        if not recent_articles:
            return {
                "status": "no_recent_articles",
                "comparisons": 0,
                "processing_time": time.time() - start_time
            }
        
        # Find potential matches
        potential_matches = self._find_potential_matches_incremental(
            new_article_id, identifiers, recent_articles
        )
        
        # Process clustering
        clustering_result = self._process_clustering_incremental(
            new_article_id, identifiers, potential_matches
        )
        
        processing_time = time.time() - start_time
        
        return {
            "status": "completed",
            "new_article_id": new_article_id,
            "recent_articles_checked": len(recent_articles),
            "potential_matches": len(potential_matches),
            "clustering_result": clustering_result,
            "processing_time": processing_time
        }
    
    def _get_article_by_id(self, article_id: int) -> Dict:
        """Get article by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT article_id, url, title, content, identifier_1, identifier_2, 
                   identifier_3, identifier_4, identifier_5, identifier_6
            FROM articles 
            WHERE article_id = ?
        """, (article_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'article_id': row[0],
                'url': row[1],
                'title': row[2],
                'content': row[3],
                'identifier_1': row[4],
                'identifier_2': row[5],
                'identifier_3': row[6],
                'identifier_4': row[7],
                'identifier_5': row[8],
                'identifier_6': row[9]
            }
        return None
    
    def _get_recent_articles_for_comparison(self, exclude_article_id: int) -> List[Dict]:
        """Get recent articles for comparison, excluding the new article"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=self.recent_days)
        cursor.execute("""
            SELECT article_id, url, title, content, identifier_1, identifier_2, 
                   identifier_3, identifier_4, identifier_5, identifier_6
            FROM articles 
            WHERE created_at >= ? AND article_id != ? AND identifier_1 != ''
            ORDER BY created_at DESC
            LIMIT ?
        """, (cutoff_date, exclude_article_id, self.max_comparisons))
        
        articles = []
        for row in cursor.fetchall():
            articles.append({
                'article_id': row[0],
                'url': row[1],
                'title': row[2],
                'content': row[3],
                'identifier_1': row[4],
                'identifier_2': row[5],
                'identifier_3': row[6],
                'identifier_4': row[7],
                'identifier_5': row[8],
                'identifier_6': row[9]
            })
        
        conn.close()
        return articles
    
    def _parse_identifiers(self, article: Dict) -> Dict:
        """Parse identifiers from article"""
        return {
            'topic_primary': article.get('identifier_1', ''),
            'topic_secondary': article.get('identifier_2', ''),
            'entity_primary': article.get('identifier_3', ''),
            'entity_secondary': article.get('identifier_4', ''),
            'location_primary': article.get('identifier_5', ''),
            'event_or_policy': article.get('identifier_6', '')
        }
    
    def _find_potential_matches_incremental(self, article_id: int, identifiers: Dict, 
                                          recent_articles: List[Dict]) -> List[Dict]:
        """Find potential matches using incremental approach"""
        potential_matches = []
        
        for candidate in recent_articles:
            candidate_identifiers = self._parse_identifiers(candidate)
            score, has_high_weight = self._calculate_weighted_score(identifiers, candidate_identifiers)
            
            if score >= 2 and has_high_weight:
                potential_matches.append({
                    'article_id': candidate['article_id'],
                    'identifiers': candidate_identifiers,
                    'score': score,
                    'has_high_weight': has_high_weight,
                    'title': candidate.get('title', ''),
                    'url': candidate.get('url', '')
                })
        
        # Sort by score (highest first)
        return sorted(potential_matches, key=lambda x: x['score'], reverse=True)
    
    def _calculate_weighted_score(self, identifiers1: Dict, identifiers2: Dict) -> Tuple[float, bool]:
        """Calculate weighted similarity score"""
        score = 0.0
        has_high_weight = False
        
        # Weight mapping
        weights = {
            'event_or_policy': 3,
            'entity_primary': 2,
            'entity_secondary': 2,
            'location_primary': 2,
            'topic_primary': 1,
            'topic_secondary': 1
        }
        
        for field, weight in weights.items():
            val1 = identifiers1.get(field, '').lower().strip()
            val2 = identifiers2.get(field, '').lower().strip()
            
            if val1 and val2:
                if val1 == val2:
                    score += weight
                    if weight >= 2:
                        has_high_weight = True
                elif self._calculate_similarity(val1, val2) > 0.8:
                    score += weight * 0.5
                    if weight >= 2:
                        has_high_weight = True
        
        return score, has_high_weight
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using Jaccard similarity"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _process_clustering_incremental(self, article_id: int, identifiers: Dict, 
                                       potential_matches: List[Dict]) -> Dict:
        """Process clustering using incremental approach"""
        if not potential_matches:
            return {
                'clustered': False,
                'cluster_id': None,
                'matches_found': 0
            }
        
        # For testing, simulate clustering logic
        # In production, this would call the LLM clustering service
        
        best_match = potential_matches[0]  # Highest scoring match
        
        return {
            'clustered': True,
            'cluster_id': f"cluster_{article_id}_{best_match['article_id']}",
            'matches_found': len(potential_matches),
            'best_match': {
                'article_id': best_match['article_id'],
                'score': best_match['score'],
                'title': best_match['title']
            }
        }
    
    def get_incremental_stats(self) -> Dict:
        """Get incremental clustering statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get total articles
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_articles = cursor.fetchone()[0]
        
        # Get recent articles (last 30 days)
        cutoff_date = datetime.now() - timedelta(days=self.recent_days)
        cursor.execute("SELECT COUNT(*) FROM articles WHERE created_at >= ?", (cutoff_date,))
        recent_articles = cursor.fetchone()[0]
        
        # Get articles with identifiers
        cursor.execute("SELECT COUNT(*) FROM articles WHERE identifier_1 != ''")
        articles_with_identifiers = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_articles": total_articles,
            "recent_articles": recent_articles,
            "articles_with_identifiers": articles_with_identifiers,
            "recent_days": self.recent_days,
            "max_comparisons": self.max_comparisons
        }

def main():
    """Test the incremental clustering processor"""
    processor = IncrementalClustering()
    
    # Test with church shooting article
    test_article_id = 36
    
    print("Testing incremental clustering...")
    
    # Process incremental clustering
    result = processor.process_incremental_clustering(test_article_id)
    print(f"Incremental clustering result: {result}")
    
    # Get stats
    stats = processor.get_incremental_stats()
    print(f"Incremental stats: {stats}")

if __name__ == "__main__":
    main()
