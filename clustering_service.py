#!/usr/bin/env python3
"""
Clustering service with normalization and weighted matching.
Implements the 6-typed identifier clustering logic.
"""

import requests
import json
import re
from typing import Dict, List, Tuple, Optional
import sqlite3
from datetime import datetime, timedelta

class ClusteringService:
    def __init__(self, db_path="beacon_articles.db"):
        self.db_path = db_path
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "gemma:2b"
        
        # Weighted scoring system
        self.weights = {
            'event_or_policy': 3,  # Highest weight
            'entity_primary': 2,
            'entity_secondary': 2,
            'location_primary': 2,
            'topic_primary': 1,
            'topic_secondary': 1
        }
        
        # Minimum score to trigger LLM clustering
        self.min_score_threshold = 2
        
        # Minimum LLM clustering score to merge
        self.min_llm_score = 80
    
    def normalize_identifier(self, identifier: str) -> str:
        """Normalize identifier text for comparison"""
        if not identifier:
            return ""
        
        # Convert to lowercase
        normalized = identifier.lower().strip()
        
        # Remove punctuation except hyphens and spaces
        normalized = re.sub(r'[^\w\s-]', '', normalized)
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return normalized
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts using improved matching"""
        if not text1 or not text2:
            return 0.0
        
        # Normalize texts
        text1 = text1.lower().strip()
        text2 = text2.lower().strip()
        
        # Exact match
        if text1 == text2:
            return 1.0
        
        # Check for key word overlaps (more flexible)
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        # Calculate overlap
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        if union == 0:
            return 0.0
        
        # Jaccard similarity
        jaccard = intersection / union
        
        # Boost for key words that indicate same topic
        key_words = ['church', 'shooting', 'michigan', 'gunman', 'attack', 'fire', 'mormon']
        key_overlap = sum(1 for word in key_words if word in words1 and word in words2)
        
        # If we have key word overlap, boost the score
        if key_overlap > 0:
            jaccard = max(jaccard, 0.3 + (key_overlap * 0.2))
        
        # Boost for high overlap
        if jaccard >= 0.9:
            return 1.0
        elif jaccard >= 0.7:
            return 0.9
        elif jaccard >= 0.3:
            return 0.8
        else:
            return jaccard
    
    def calculate_weighted_score(self, identifiers1: Dict, identifiers2: Dict) -> Tuple[float, bool]:
        """Calculate weighted similarity score between two identifier sets"""
        total_score = 0.0
        has_high_weight = False
        
        for field, weight in self.weights.items():
            val1 = self.normalize_identifier(identifiers1.get(field, ''))
            val2 = self.normalize_identifier(identifiers2.get(field, ''))
            
            if val1 and val2:
                similarity = self.calculate_similarity(val1, val2)
                field_score = similarity * weight
                total_score += field_score
                
                # Check if this is a high-weight field
                if weight >= 2 and similarity > 0.5:
                    has_high_weight = True
        
        return total_score, has_high_weight
    
    def get_llm_clustering_score(self, article1_content: str, article2_content: str) -> float:
        """Get LLM-based clustering score for two articles using direct Gemma"""
        prompt = f"""Compare these two news articles and determine if they cover the same story/event:

ARTICLE 1:
{article1_content[:2000]}

ARTICLE 2:
{article2_content[:2000]}

Rate their similarity on a scale of 0-100% where:
- 100% = Same exact story/event
- 80-99% = Very similar, likely same story
- 60-79% = Related but different aspects
- 40-59% = Somewhat related topics
- 20-39% = Different but related subjects
- 0-19% = Completely different

Respond with ONLY a number (0-100), no explanation."""

        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '').strip()
            
            if response_text:
                # Extract number from response
                score_match = re.search(r'(\d+)', response_text)
                if score_match:
                    return float(score_match.group(1))
                    
        except Exception as e:
            print(f"Error getting LLM clustering score: {e}")
        
        return 0.0
    
    def find_potential_clusters(self, new_article_id: int, new_identifiers: Dict) -> List[Tuple[int, float]]:
        """Find existing articles that might cluster with the new article"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all existing articles with identifiers
        cursor.execute("""
            SELECT article_id, identifier_1, identifier_2, identifier_3, 
                   identifier_4, identifier_5, identifier_6
            FROM articles 
            WHERE article_id != ? AND cluster_id IS NULL
        """, (new_article_id,))
        
        potential_matches = []
        
        for row in cursor.fetchall():
            article_id = row[0]
            existing_identifiers = {
                'topic_primary': row[1] or '',
                'topic_secondary': row[2] or '',
                'entity_primary': row[3] or '',
                'entity_secondary': row[4] or '',
                'location_primary': row[5] or '',
                'event_or_policy': row[6] or ''
            }
            
            # Calculate weighted score
            score, has_high_weight = self.calculate_weighted_score(
                new_identifiers, existing_identifiers
            )
            
            # Check if meets threshold
            if score >= self.min_score_threshold and has_high_weight:
                potential_matches.append((article_id, score))
        
        conn.close()
        return sorted(potential_matches, key=lambda x: x[1], reverse=True)
    
    def create_cluster(self, article_ids: List[int], cluster_title: str, cluster_summary: str) -> int:
        """Create a new cluster and assign articles to it"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Create cluster
            cursor.execute("""
                INSERT INTO clusters (cluster_title, cluster_summary, article_ids, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (cluster_title, cluster_summary, json.dumps(article_ids), 
                  datetime.now(), datetime.now()))
            
            cluster_id = cursor.lastrowid
            
            # Update articles with cluster_id
            for article_id in article_ids:
                cursor.execute("""
                    UPDATE articles SET cluster_id = ? WHERE article_id = ?
                """, (cluster_id, article_id))
            
            conn.commit()
            return cluster_id
            
        except Exception as e:
            conn.rollback()
            print(f"Error creating cluster: {e}")
            return None
        finally:
            conn.close()
    
    def add_to_existing_cluster(self, article_id: int, cluster_id: int):
        """Add an article to an existing cluster"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get existing cluster
            cursor.execute("SELECT article_ids FROM clusters WHERE cluster_id = ?", (cluster_id,))
            result = cursor.fetchone()
            
            if result:
                existing_ids = json.loads(result[0])
                existing_ids.append(article_id)
                
                # Update cluster
                cursor.execute("""
                    UPDATE clusters 
                    SET article_ids = ?, updated_at = ?
                    WHERE cluster_id = ?
                """, (json.dumps(existing_ids), datetime.now(), cluster_id))
                
                # Update article
                cursor.execute("""
                    UPDATE articles SET cluster_id = ? WHERE article_id = ?
                """, (cluster_id, article_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            conn.rollback()
            print(f"Error adding to cluster: {e}")
            return False
        finally:
            conn.close()
    
    def process_clustering(self, article_id: int, identifiers: Dict, article_content: str) -> Optional[int]:
        """Process clustering for a new article"""
        print(f"Processing clustering for article {article_id}")
        
        # Find potential matches
        potential_matches = self.find_potential_clusters(article_id, identifiers)
        
        if not potential_matches:
            print("No potential clusters found")
            return None
        
        print(f"Found {len(potential_matches)} potential matches")
        
        # Get article content for LLM comparison
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for match_article_id, score in potential_matches:
            print(f"Checking article {match_article_id} (score: {score})")
            
            # Get existing article content
            cursor.execute("SELECT content FROM articles WHERE article_id = ?", (match_article_id,))
            result = cursor.fetchone()
            
            if result:
                existing_content = result[0]
                
                # Get LLM clustering score
                llm_score = self.get_llm_clustering_score(article_content, existing_content)
                print(f"LLM clustering score: {llm_score}%")
                
                if llm_score >= self.min_llm_score:
                    # Check if existing article is already in a cluster
                    cursor.execute("SELECT cluster_id FROM articles WHERE article_id = ?", (match_article_id,))
                    cluster_result = cursor.fetchone()
                    
                    if cluster_result and cluster_result[0]:
                        # Add to existing cluster
                        print(f"Adding to existing cluster {cluster_result[0]}")
                        self.add_to_existing_cluster(article_id, cluster_result[0])
                        conn.close()
                        return cluster_result[0]
                    else:
                        # Create new cluster
                        print("Creating new cluster")
                        cluster_title = f"Cluster {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        cluster_summary = f"Articles covering related topics (LLM score: {llm_score}%)"
                        
                        cluster_id = self.create_cluster([article_id, match_article_id], 
                                                        cluster_title, cluster_summary)
                        conn.close()
                        return cluster_id
        
        conn.close()
        print("No clusters created")
        return None

def main():
    """Test the clustering service"""
    service = ClusteringService()
    
    # Test identifiers
    test_identifiers = {
        'topic_primary': 'Middle East Peace',
        'topic_secondary': 'Gaza Conflict',
        'entity_primary': 'Donald Trump',
        'entity_secondary': 'Israel',
        'location_primary': 'Gaza Strip',
        'event_or_policy': '20-Point Peace Plan'
    }
    
    # Test normalization
    for key, value in test_identifiers.items():
        normalized = service.normalize_identifier(value)
        print(f"{key}: '{value}' -> '{normalized}'")
    
    # Test similarity
    similarity = service.calculate_similarity("Middle East Peace", "middle east peace")
    print(f"Similarity: {similarity}")

if __name__ == "__main__":
    main()
