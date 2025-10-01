#!/usr/bin/env python3
"""
Worker pool processor for parallel article processing.
Processes multiple articles simultaneously using multiprocessing.
"""

import multiprocessing
import subprocess
import time
import sys
import os
from typing import List, Dict, Any
import sqlite3
from datetime import datetime

class WorkerPoolProcessor:
    def __init__(self, num_workers=3, base_path="/root/Beacon"):
        self.num_workers = num_workers
        self.base_path = base_path
        
    def process_single_article(self, article_data):
        """Process a single article - designed for multiprocessing"""
        article_id, url = article_data
        
        try:
            print(f"Worker processing article {article_id}: {url}")
            
            # Step 1: Generate title
            title_result = subprocess.run([
                "python3", f"{self.base_path}/sync_title_generator.py", url
            ], capture_output=True, text=True, timeout=120)
            
            if title_result.returncode != 0:
                return {"article_id": article_id, "success": False, "error": f"Title generation failed: {title_result.stderr}"}
            
            # Step 2: Generate excerpt
            excerpt_result = subprocess.run([
                "python3", f"{self.base_path}/sync_excerpt_generator.py", url
            ], capture_output=True, text=True, timeout=120)
            
            if excerpt_result.returncode != 0:
                return {"article_id": article_id, "success": False, "error": f"Excerpt generation failed: {excerpt_result.stderr}"}
            
            # Step 3: Generate identifiers
            identifier_result = subprocess.run([
                "python3", f"{self.base_path}/sync_identifier_generator.py", url
            ], capture_output=True, text=True, timeout=120)
            
            if identifier_result.returncode != 0:
                return {"article_id": article_id, "success": False, "error": f"Identifier generation failed: {identifier_result.stderr}"}
            
            # Parse identifier output
            identifiers = self.parse_identifier_output(identifier_result.stdout)
            
            # Update database
            self.update_database(article_id, title_result.stdout, excerpt_result.stdout, identifiers)
            
            return {
                "article_id": article_id,
                "success": True,
                "title": title_result.stdout.strip(),
                "excerpt": excerpt_result.stdout.strip(),
                "identifiers": identifiers
            }
            
        except Exception as e:
            return {"article_id": article_id, "success": False, "error": str(e)}
    
    def parse_identifier_output(self, output: str):
        """Parse identifier generator output"""
        try:
            import json
            import re
            
            # Look for the generated identifiers in the output
            lines = output.split('\n')
            identifiers = {}
            
            for line in lines:
                if 'topic_primary:' in line:
                    identifiers['topic_primary'] = line.split('topic_primary:')[1].strip()
                elif 'topic_secondary:' in line:
                    identifiers['topic_secondary'] = line.split('topic_secondary:')[1].strip()
                elif 'entity_primary:' in line:
                    identifiers['entity_primary'] = line.split('entity_primary:')[1].strip()
                elif 'entity_secondary:' in line:
                    identifiers['entity_secondary'] = line.split('entity_secondary:')[1].strip()
                elif 'location_primary:' in line:
                    identifiers['location_primary'] = line.split('location_primary:')[1].strip()
                elif 'event_or_policy:' in line:
                    identifiers['event_or_policy'] = line.split('event_or_policy:')[1].strip()
            
            return identifiers
            
        except Exception as e:
            print(f"Error parsing identifiers: {e}")
            return {}
    
    def update_database(self, article_id: int, title: str, excerpt: str, identifiers: Dict):
        """Update database with results"""
        try:
            conn = sqlite3.connect(f"{self.base_path}/beacon_articles.db")
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE articles 
                SET title = ?, excerpt = ?, 
                    identifier_1 = ?, identifier_2 = ?, identifier_3 = ?,
                    identifier_4 = ?, identifier_5 = ?, identifier_6 = ?,
                    updated_at = ?
                WHERE article_id = ?
            ''', (
                title.strip(),
                excerpt.strip(),
                identifiers.get('topic_primary', ''),
                identifiers.get('topic_secondary', ''),
                identifiers.get('entity_primary', ''),
                identifiers.get('entity_secondary', ''),
                identifiers.get('location_primary', ''),
                identifiers.get('event_or_policy', ''),
                datetime.now(),
                article_id
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Database update error: {e}")
    
    def process_articles_parallel(self, articles: List[tuple]) -> List[Dict]:
        """Process multiple articles in parallel using worker pool"""
        print(f"Processing {len(articles)} articles with {self.num_workers} workers...")
        
        start_time = time.time()
        
        # Use multiprocessing Pool
        with multiprocessing.Pool(processes=self.num_workers) as pool:
            results = pool.map(self.process_single_article, articles)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print(f"Completed processing in {processing_time:.2f} seconds")
        print(f"Average time per article: {processing_time/len(articles):.2f} seconds")
        
        # Print results summary
        successful = sum(1 for r in results if r.get('success', False))
        failed = len(results) - successful
        
        print(f"Results: {successful} successful, {failed} failed")
        
        return results

def main():
    """Test worker pool with sample articles"""
    if len(sys.argv) < 2:
        print("Usage: python3 worker_pool_processor.py <article_id1,url1> [article_id2,url2] ...")
        sys.exit(1)
    
    # Parse command line arguments
    articles = []
    for arg in sys.argv[1:]:
        if ',' in arg:
            article_id, url = arg.split(',', 1)
            articles.append((int(article_id), url))
        else:
            print(f"Invalid format: {arg}. Use: article_id,url")
            sys.exit(1)
    
    if not articles:
        print("No articles to process")
        sys.exit(1)
    
    # Create processor and run
    processor = WorkerPoolProcessor(num_workers=3)
    results = processor.process_articles_parallel(articles)
    
    # Print detailed results
    for result in results:
        if result.get('success'):
            print(f"✅ Article {result['article_id']}: {result.get('title', 'No title')[:50]}...")
        else:
            print(f"❌ Article {result['article_id']}: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()
