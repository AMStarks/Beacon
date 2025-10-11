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
from similarity_index import SimilarityIndex
from database_pool import get_db_pool

class ClusteringService:
    def __init__(self, db_path="beacon_articles.db"):
        self.db_path = db_path
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "gemma:2b"
        self.similarity_index = SimilarityIndex(db_path)
        self.db_pool = get_db_pool(db_path)
        
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
        
        # Minimum LLM clustering score to merge (increased for stricter clustering)
        self.min_llm_score = 87
    
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
        # Check topic coherence first - articles must be about the same topic
        if not self._check_topic_coherence(identifiers1, identifiers2):
            return 0.0, False
        
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
    
    def _check_topic_coherence(self, identifiers1: Dict, identifiers2: Dict) -> bool:
        """Check if articles are about the same topic, not just sharing entities"""
        # If both have event_or_policy, they should be similar
        if identifiers1.get('event_or_policy') and identifiers2.get('event_or_policy'):
            event_similarity = self.calculate_similarity(
                identifiers1['event_or_policy'], 
                identifiers2['event_or_policy']
            )
            if event_similarity > 0.7:
                return True
        
        # If both have topic_primary, they should be similar  
        if identifiers1.get('topic_primary') and identifiers2.get('topic_primary'):
            topic_similarity = self.calculate_similarity(
                identifiers1['topic_primary'], 
                identifiers2['topic_primary']
            )
            if topic_similarity > 0.7:
                return True
        
        # If both have topic_secondary, they should be similar
        if identifiers1.get('topic_secondary') and identifiers2.get('topic_secondary'):
            topic_similarity = self.calculate_similarity(
                identifiers1['topic_secondary'], 
                identifiers2['topic_secondary']
            )
            if topic_similarity > 0.7:
                return True
        
        # If no topic coherence found, reject clustering
        return False
    
    def get_llm_clustering_score(self, article1_content: str, article2_content: str) -> float:
        """Get LLM-based clustering score for two articles using direct Gemma"""
        prompt = f"""Analyze these two news articles and determine if they cover the SAME SPECIFIC STORY or EVENT:

ARTICLE 1:
{article1_content[:2000]}

ARTICLE 2:
{article2_content[:2000]}

Rate their similarity on a scale of 0-100% where:
- 100% = Same exact story/event (e.g., same incident, same policy announcement, same breaking news)
- 80-99% = Very similar, likely same story but different angles
- 60-79% = Related but different aspects of same topic
- 40-59% = Somewhat related topics but different stories
- 20-39% = Different stories but related subjects
- 0-19% = Completely different stories

IMPORTANT: A TV discussion about politics is NOT the same as a policy announcement, even if they mention the same political party.

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
        """Find existing articles that might cluster with the new article (smart clustering - recent articles only)"""
        # Get only recent articles (last 7 days) with identifiers for temporal clustering
        seven_days_ago = datetime.now() - timedelta(days=7)
        rows = self.db_pool.execute_query("""
            SELECT article_id, identifier_1, identifier_2, identifier_3, 
                   identifier_4, identifier_5, identifier_6, created_at
            FROM articles 
            WHERE article_id != ? AND cluster_id IS NULL 
            AND created_at >= ?
            ORDER BY created_at DESC
        """, (new_article_id, seven_days_ago))
        
        potential_matches = []
        
        for row in rows:
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
                        
                        # Validate the updated cluster
                        if not self.validate_cluster_coherence(cluster_result[0]):
                            print(f"Cluster {cluster_result[0]} is incoherent, splitting...")
                            self.split_incoherent_cluster(cluster_result[0])
                            conn.close()
                            return None
                        
                        conn.close()
                        return cluster_result[0]
                    else:
                        # Create new cluster
                        print("Creating new cluster")
                        cluster_title = f"Cluster {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        cluster_summary = f"Articles covering related topics (LLM score: {llm_score}%)"
                        
                        cluster_id = self.create_cluster([article_id, match_article_id], 
                                                        cluster_title, cluster_summary)
                        
                        # Validate the new cluster
                        if not self.validate_cluster_coherence(cluster_id):
                            print(f"New cluster {cluster_id} is incoherent, removing...")
                            self.split_incoherent_cluster(cluster_id)
                            conn.close()
                            return None
                        
                        conn.close()
                        return cluster_id
        
        conn.close()
        print("No clusters created")
        return None
    
    def validate_cluster_coherence(self, cluster_id: int) -> bool:
        """Validate that all articles in a cluster are semantically coherent"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get cluster info
            cursor.execute("""
                SELECT cluster_title, cluster_summary, article_ids 
                FROM clusters WHERE cluster_id = ?
            """, (cluster_id,))
            cluster_result = cursor.fetchone()
            
            if not cluster_result:
                return False
            
            article_ids = json.loads(cluster_result[2])
            if len(article_ids) < 2:
                return True  # Single article clusters are always valid
            
            # Get all articles in cluster
            cursor.execute("""
                SELECT article_id, title, content, identifier_1, identifier_2, 
                       identifier_3, identifier_4, identifier_5, identifier_6
                FROM articles WHERE article_id IN ({})
            """.format(','.join('?' * len(article_ids))), article_ids)
            
            articles = cursor.fetchall()
            
            # Check if all articles share coherent topics
            topics = set()
            events = set()
            
            for article in articles:
                if article[3]:  # identifier_1 (topic_primary)
                    topics.add(article[3].lower())
                if article[6]:  # identifier_6 (event_or_policy)
                    events.add(article[6].lower())
            
            # If we have multiple distinct topics or events, cluster may be incoherent
            if len(topics) > 2 or len(events) > 2:
                print(f"Cluster {cluster_id} may be incoherent: {len(topics)} topics, {len(events)} events")
                return False
            
            # Additional LLM validation for cluster coherence
            if len(articles) >= 2:
                # Compare first two articles for semantic coherence
                article1_content = articles[0][2]  # content
                article2_content = articles[1][2]  # content
                
                llm_score = self.get_llm_clustering_score(article1_content, article2_content)
                if llm_score < 75:  # Lower threshold for validation
                    print(f"Cluster {cluster_id} failed LLM coherence check: {llm_score}%")
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error validating cluster {cluster_id}: {e}")
            return False
        finally:
            conn.close()
    
    def split_incoherent_cluster(self, cluster_id: int) -> List[int]:
        """Split an incoherent cluster into smaller, coherent clusters"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get cluster articles
            cursor.execute("SELECT article_ids FROM clusters WHERE cluster_id = ?", (cluster_id,))
            result = cursor.fetchone()
            if not result:
                return []
            
            article_ids = json.loads(result[0])
            
            # For now, just remove the cluster and let articles be re-clustered
            # In a more sophisticated implementation, we'd group articles by similarity
            
            # Remove cluster
            cursor.execute("DELETE FROM clusters WHERE cluster_id = ?", (cluster_id,))
            
            # Remove cluster_id from articles
            for article_id in article_ids:
                cursor.execute("UPDATE articles SET cluster_id = NULL WHERE article_id = ?", (article_id,))
            
            conn.commit()
            return article_ids
            
        except Exception as e:
            print(f"Error splitting cluster {cluster_id}: {e}")
            conn.rollback()
            return []
        finally:
            conn.close()

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
