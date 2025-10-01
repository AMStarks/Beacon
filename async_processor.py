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
import requests

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
            ], capture_output=True, text=True, timeout=180)
            
            if identifier_result.returncode != 0:
                print(f"Identifier generation failed: {identifier_result.stderr}")
                return False
            
            # Step 4: Fetch article content
            print("Fetching article content...")
            import json
            import re
            from bs4 import BeautifulSoup
            
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
                    element.decompose()
                
                selectors = ['article', '[role="main"]', '.article-content', '.post-content', '.entry-content', 'main']
                article_content = ""
                for selector in selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        article_content = elem.get_text().strip()
                        break
                
                if not article_content:
                    body = soup.find('body')
                    if body:
                        article_content = body.get_text().strip()
                
                article_content = re.sub(r'\s+', ' ', article_content)
                article_content = article_content[:5000]
            else:
                article_content = ""
            
            # Step 5: Parse results
            print("Parsing results...")
            
            # Parse title
            title_match = re.search(r"'neutral_title':\s*'([^']+)'", title_result.stdout)
            title = title_match.group(1) if title_match else "Processing..."
            
            # Parse excerpt (handle escaped quotes)
            excerpt_match = re.search(r"'neutral_excerpt':\s*'(.+?)',\s*'word_count'", excerpt_result.stdout, re.DOTALL)
            if not excerpt_match:
                excerpt_match = re.search(r"'neutral_excerpt':\s*\"(.+?)\",\s*'word_count'", excerpt_result.stdout, re.DOTALL)
            excerpt = excerpt_match.group(1) if excerpt_match else ""
            
            # Parse identifiers (already handled by parse_identifier_output)
            identifiers = self.parse_identifier_output(identifier_result.stdout)
            
            # Step 6: Update database with results
            print("Updating database...")
            self.update_database(article_id, title, excerpt, identifiers, article_content)
            
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
    
    def update_database(self, article_id: int, title: str, excerpt: str, identifiers: dict, content: str):
        """Update database with generated content"""
        try:
            import json
            # Escape all values for safe embedding
            title_safe = title.replace("'", "''")
            excerpt_safe = excerpt.replace("'", "''")
            content_safe = content.replace("'", "''")
            identifiers_json = json.dumps(identifiers).replace("'", "''")
            
            # Update database
            update_script = f"""
import sqlite3
import json

# Recreate identifiers from parent
identifiers = json.loads('{identifiers_json}')

conn = sqlite3.connect('beacon_articles.db')
cursor = conn.cursor()

# Values already escaped
title = '''{title_safe}'''
excerpt = '''{excerpt_safe}'''
content = '''{content_safe}'''

# Update article
cursor.execute('''
    UPDATE articles 
    SET title = ?, excerpt = ?, content = ?,
        identifier_1 = ?, identifier_2 = ?, identifier_3 = ?,
        identifier_4 = ?, identifier_5 = ?, identifier_6 = ?
    WHERE article_id = ?
''', (
    title, excerpt, content,
    identifiers.get('topic_primary', ''),
    identifiers.get('topic_secondary', ''),
    identifiers.get('entity_primary', ''),
    identifiers.get('entity_secondary', ''),
    identifiers.get('location_primary', ''),
    identifiers.get('event_or_policy', ''),
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
            import ast
            
            # Try to find the dict after "Generated identifiers:"
            json_match = re.search(r"Generated identifiers:\s*(\{.+?\})\s*\n", output, re.DOTALL)
            if json_match:
                dict_str = json_match.group(1)
                # Use ast.literal_eval to safely parse Python dict with apostrophes
                return ast.literal_eval(dict_str)
        except Exception as e:
            print(f"Error parsing identifiers: {e}")
            print(f"Output was: {output[:500]}")
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
            # Get short content for clustering from DB (use excerpt)
            import sqlite3
            conn_local = sqlite3.connect('beacon_articles.db')
            cur = conn_local.cursor()
            cur.execute('SELECT excerpt FROM articles WHERE article_id = ?', (article_id,))
            row = cur.fetchone()
            conn_local.close()
            content = (row[0] or '') if row else ''
            content = content[:1500]

            # Run clustering - call directly instead of via subprocess to avoid f-string issues
            import sqlite3
            conn_cluster = sqlite3.connect('beacon_articles.db')
            cursor_cluster = conn_cluster.cursor()
            cursor_cluster.execute('''
                SELECT identifier_1, identifier_2, identifier_3, 
                       identifier_4, identifier_5, identifier_6
                FROM articles WHERE article_id = ?
            ''', (article_id,))
            result = cursor_cluster.fetchone()
            conn_cluster.close()
            
            if result:
                identifiers_dict = {
                    'topic_primary': result[0] or '',
                    'topic_secondary': result[1] or '',
                    'entity_primary': result[2] or '',
                    'entity_secondary': result[3] or '',
                    'location_primary': result[4] or '',
                    'event_or_policy': result[5] or ''
                }
                
                # Import and call clustering service directly
                sys.path.append(self.base_path)
                from clustering_service import ClusteringService
                service = ClusteringService()
                cluster_id = service.process_clustering(article_id, identifiers_dict, content)
                
                if cluster_id:
                    print(f'Article clustered with ID: {cluster_id}')
                else:
                    print('No clustering performed')
            else:
                print('No identifiers found for clustering')
                
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
