#!/usr/bin/env python3
"""
Async processor for background LLM processing.
Handles title, excerpt, and identifier generation, plus clustering.
"""

import subprocess
import sys
import os
import time
from datetime import datetime

class AsyncProcessor:
    def __init__(self):
        self.base_path = "/root/Beacon"
        
    def process_article(self, article_id: int, url: str):
        """Process article in background: title, excerpt, identifiers, clustering"""
        print(f"Starting async processing for article {article_id}")
        
        try:
            # Step 1: Generate title
            print("Generating title...")
            title_result = subprocess.run([
                "python3", f"{self.base_path}/sync_title_generator.py", url
            ], capture_output=True, text=True, timeout=120)
            
            if title_result.returncode != 0:
                print(f"Title generation failed: {title_result.stderr}")
                return False
            
            # Step 2: Generate excerpt
            print("Generating excerpt...")
            excerpt_result = subprocess.run([
                "python3", f"{self.base_path}/sync_excerpt_generator.py", url
            ], capture_output=True, text=True, timeout=120)
            
            if excerpt_result.returncode != 0:
                print(f"Excerpt generation failed: {excerpt_result.stderr}")
                return False
            
            # Step 3: Generate identifiers
            print("Generating identifiers...")
            identifier_result = subprocess.run([
                "python3", f"{self.base_path}/sync_identifier_generator.py", url
            ], capture_output=True, text=True, timeout=120)
            
            if identifier_result.returncode != 0:
                print(f"Identifier generation failed: {identifier_result.stderr}")
                return False
            
            # Step 4: Update database with results
            print("Updating database...")
            self.update_database(article_id, title_result.stdout, excerpt_result.stdout, identifier_result.stdout)
            
            # Step 5: Process clustering
            print("Processing clustering...")
            self.process_clustering(article_id, url)
            
            print(f"Async processing completed for article {article_id}")
            return True
            
        except subprocess.TimeoutExpired:
            print(f"Processing timed out for article {article_id}")
            return False
        except Exception as e:
            print(f"Error processing article {article_id}: {e}")
            return False
    
    def update_database(self, article_id: int, title: str, excerpt: str, identifier_output: str):
        """Update database with generated content"""
        try:
            # Parse identifier output
            identifiers = self.parse_identifier_output(identifier_output)
            
            # Update database
            update_script = f"""
import sqlite3
import json

conn = sqlite3.connect('beacon.db')
cursor = conn.cursor()

# Clean title and excerpt
title = '''{title}'''.strip()
excerpt = '''{excerpt}'''.strip()

# Update article
cursor.execute('''
    UPDATE articles 
    SET title = ?, excerpt = ?, 
        identifier_1 = ?, identifier_2 = ?, identifier_3 = ?,
        identifier_4 = ?, identifier_5 = ?, identifier_6 = ?,
        updated_at = ?
    WHERE article_id = ?
''', (
    title, excerpt,
    identifiers.get('topic_primary', ''),
    identifiers.get('topic_secondary', ''),
    identifiers.get('entity_primary', ''),
    identifiers.get('entity_secondary', ''),
    identifiers.get('location_primary', ''),
    identifiers.get('event_or_policy', ''),
    '{datetime.now()}',
    {article_id}
))

conn.commit()
conn.close()
print("Database updated successfully")
"""
            
            result = subprocess.run([
                "python3", "-c", update_script
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                print("Database updated successfully")
            else:
                print(f"Database update failed: {result.stderr}")
                
        except Exception as e:
            print(f"Error updating database: {e}")
    
    def parse_identifier_output(self, output: str):
        """Parse identifier generator output"""
        try:
            # Look for JSON in the output
            import json
            import re
            
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
        except:
            pass
        
        # Fallback: return empty structure
        return {
            'topic_primary': '',
            'topic_secondary': '',
            'entity_primary': '',
            'entity_secondary': '',
            'location_primary': '',
            'event_or_policy': ''
        }
    
    def process_clustering(self, article_id: int, url: str):
        """Process clustering for the article"""
        try:
            # Get article content for clustering
            import requests
            response = requests.get(url, timeout=30)
            content = response.text if response.status_code == 200 else ""
            
            # Run clustering
            clustering_script = f"""
import sys
sys.path.append('{self.base_path}')
from clustering_service import ClusteringService

# Get identifiers from database
import sqlite3
conn = sqlite3.connect('beacon.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT identifier_1, identifier_2, identifier_3, 
           identifier_4, identifier_5, identifier_6
    FROM articles WHERE article_id = ?
''', ({article_id},))
result = cursor.fetchone()
conn.close()

if result:
    identifiers = {{
        'topic_primary': result[0] or '',
        'topic_secondary': result[1] or '',
        'entity_primary': result[2] or '',
        'entity_secondary': result[3] or '',
        'location_primary': result[4] or '',
        'event_or_policy': result[5] or ''
    }}
    
    # Process clustering
    service = ClusteringService()
    cluster_id = service.process_clustering({article_id}, identifiers, '''{content}''')
    
    if cluster_id:
        print(f"Article clustered with ID: {{cluster_id}}")
    else:
        print("No clustering performed")
else:
    print("No identifiers found for clustering")
"""
            
            result = subprocess.run([
                "python3", "-c", clustering_script
            ], capture_output=True, text=True, timeout=180)
            
            if result.returncode == 0:
                print("Clustering processed successfully")
            else:
                print(f"Clustering failed: {result.stderr}")
                
        except Exception as e:
            print(f"Error processing clustering: {e}")

def main():
    """Test the async processor"""
    if len(sys.argv) != 3:
        print("Usage: python3 async_processor.py <article_id> <url>")
        sys.exit(1)
    
    article_id = int(sys.argv[1])
    url = sys.argv[2]
    
    processor = AsyncProcessor()
    success = processor.process_article(article_id, url)
    
    if success:
        print("Processing completed successfully")
    else:
        print("Processing failed")

if __name__ == "__main__":
    main()
