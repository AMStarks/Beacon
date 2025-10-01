#!/usr/bin/env python3
"""
Clustering batch processor for comparing new articles in batches.
More efficient than individual comparisons.
"""

import sqlite3
import json
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta
import time

class ClusteringBatchProcessor:
    def __init__(self, db_path="beacon_articles.db"):
        self.db_path = db_path
        self.batch_size = 5  # Process articles in batches of 5
    
    def process_batch_clustering(self, new_article_ids: List[int]) -> Dict:
        """Process clustering for a batch of new articles"""
        if not new_article_ids:
            return {"processed": 0, "clusters_created": 0, "articles_clustered": 0}
        
        results = {
            "processed": 0,
            "clusters_created": 0,
            "articles_clustered": 0,
            "processing_time": 0
        }
        
        start_time = time.time()
        
        # Get new articles data
        new_articles = self._get_articles_by_ids(new_article_ids)
        if not new_articles:
            return results
        
        # Get recent articles for comparison (last 30 days)
        recent_articles = self._get_recent_articles(days=30)
        
        # Process each new article
        for article in new_articles:
            article_id = article['article_id']
            identifiers = self._parse_identifiers(article)
            
            if not identifiers:
                continue
            
            # Find potential matches in batch
            potential_matches = self._find_potential_matches_batch(
                article_id, identifiers, recent_articles
            )
            
            if potential_matches:
                # Process clustering for this article
                cluster_result = self._process_article_clustering(
                    article_id, identifiers, potential_matches
                )
                
                if cluster_result['clustered']:
                    results["articles_clustered"] += 1
                    if cluster_result['new_cluster']:
                        results["clusters_created"] += 1
            
            results["processed"] += 1
        
        results["processing_time"] = time.time() - start_time
        return results
    
    def _get_articles_by_ids(self, article_ids: List[int]) -> List[Dict]:
        """Get articles by IDs"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        placeholders = ','.join(['?' for _ in article_ids])
        cursor.execute(f"""
            SELECT article_id, url, title, content, identifier_1, identifier_2, 
                   identifier_3, identifier_4, identifier_5, identifier_6
            FROM articles 
            WHERE article_id IN ({placeholders})
        """, article_ids)
        
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
    
    def _get_recent_articles(self, days: int = 30) -> List[Dict]:
        """Get recent articles for comparison"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days)
        cursor.execute("""
            SELECT article_id, url, title, content, identifier_1, identifier_2, 
                   identifier_3, identifier_4, identifier_5, identifier_6
            FROM articles 
            WHERE created_at >= ? AND identifier_1 != ''
            ORDER BY created_at DESC
        """, (cutoff_date,))
        
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
    
    def _find_potential_matches_batch(self, article_id: int, identifiers: Dict, 
                                    recent_articles: List[Dict]) -> List[Dict]:
        """Find potential matches in batch"""
        potential_matches = []
        
        for candidate in recent_articles:
            if candidate['article_id'] == article_id:
                continue
            
            candidate_identifiers = self._parse_identifiers(candidate)
            score, has_high_weight = self._calculate_weighted_score(identifiers, candidate_identifiers)
            
            if score >= 2 and has_high_weight:
                potential_matches.append({
                    'article_id': candidate['article_id'],
                    'identifiers': candidate_identifiers,
                    'score': score,
                    'has_high_weight': has_high_weight
                })
        
        return potential_matches
    
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
        """Calculate text similarity"""
        if not text1 or not text2:
            return 0.0
        
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _process_article_clustering(self, article_id: int, identifiers: Dict, 
                                  potential_matches: List[Dict]) -> Dict:
        """Process clustering for a single article"""
        # For now, just return basic clustering logic
        # In a full implementation, this would call the LLM clustering service
        
        if len(potential_matches) > 0:
            return {
                'clustered': True,
                'new_cluster': True,  # Simplified for testing
                'cluster_id': f"cluster_{article_id}_{int(time.time())}"
            }
        
        return {
            'clustered': False,
            'new_cluster': False,
            'cluster_id': None
        }
    
    def get_batch_stats(self) -> Dict:
        """Get batch processing statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get total articles
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_articles = cursor.fetchone()[0]
        
        # Get recent articles
        cutoff_date = datetime.now() - timedelta(days=30)
        cursor.execute("SELECT COUNT(*) FROM articles WHERE created_at >= ?", (cutoff_date,))
        recent_articles = cursor.fetchone()[0]
        
        # Get clusters
        cursor.execute("SELECT COUNT(*) FROM clusters")
        total_clusters = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_articles": total_articles,
            "recent_articles": recent_articles,
            "total_clusters": total_clusters,
            "batch_size": self.batch_size
        }

def main():
    """Test the clustering batch processor"""
    processor = ClusteringBatchProcessor()
    
    # Test with sample article IDs
    test_article_ids = [36, 37]  # Church shooting articles
    
    print("Testing clustering batch processor...")
    
    # Process batch clustering
    result = processor.process_batch_clustering(test_article_ids)
    print(f"Batch processing result: {result}")
    
    # Get stats
    stats = processor.get_batch_stats()
    print(f"Batch stats: {stats}")

if __name__ == "__main__":
    main()
