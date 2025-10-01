#!/usr/bin/env python3
"""
Async queue processor using Redis for background article processing.
Allows multiple articles to be processed simultaneously without blocking.
"""

import redis
import json
import time
import threading
from typing import Dict, List, Any
import requests
import subprocess
import os

class AsyncQueueProcessor:
    def __init__(self, redis_host="localhost", redis_port=6379, redis_db=0):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=redis_db, decode_responses=True)
        self.queue_name = "article_processing_queue"
        self.result_queue = "article_results_queue"
        self.worker_count = 3  # Number of worker threads
        self.workers = []
        self.running = False
    
    def enqueue_article(self, article_data: Dict) -> str:
        """Add article to processing queue"""
        job_id = f"job_{int(time.time() * 1000)}"
        job_data = {
            "job_id": job_id,
            "article_data": article_data,
            "created_at": time.time(),
            "status": "queued"
        }
        
        self.redis_client.lpush(self.queue_name, json.dumps(job_data))
        return job_id
    
    def get_job_result(self, job_id: str) -> Dict:
        """Get result for a specific job"""
        result_key = f"result_{job_id}"
        result = self.redis_client.get(result_key)
        
        if result:
            return json.loads(result)
        else:
            return {"status": "not_found"}
    
    def start_workers(self):
        """Start worker threads for processing articles"""
        self.running = True
        
        for i in range(self.worker_count):
            worker = threading.Thread(target=self._worker_loop, args=(i,))
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
        
        print(f"Started {self.worker_count} worker threads")
    
    def stop_workers(self):
        """Stop all worker threads"""
        self.running = False
        for worker in self.workers:
            worker.join()
        print("All workers stopped")
    
    def _worker_loop(self, worker_id: int):
        """Main worker loop for processing articles"""
        print(f"Worker {worker_id} started")
        
        while self.running:
            try:
                # Get job from queue (blocking with timeout)
                job_data = self.redis_client.brpop(self.queue_name, timeout=5)
                
                if job_data:
                    job_json = job_data[1]
                    job = json.loads(job_json)
                    
                    print(f"Worker {worker_id} processing job {job['job_id']}")
                    
                    # Process the article
                    result = self._process_article(job)
                    
                    # Store result
                    result_key = f"result_{job['job_id']}"
                    self.redis_client.set(result_key, json.dumps(result), ex=3600)  # Expire in 1 hour
                    
                    print(f"Worker {worker_id} completed job {job['job_id']}")
                
            except Exception as e:
                print(f"Worker {worker_id} error: {e}")
                time.sleep(1)
    
    def _process_article(self, job: Dict) -> Dict:
        """Process a single article"""
        article_data = job["article_data"]
        job_id = job["job_id"]
        
        try:
            # Update status to processing
            result = {
                "job_id": job_id,
                "status": "processing",
                "started_at": time.time()
            }
            
            # Generate title
            title_result = self._generate_title(article_data)
            result["title"] = title_result.get("title", "")
            
            # Generate excerpt
            excerpt_result = self._generate_excerpt(article_data)
            result["excerpt"] = excerpt_result.get("excerpt", "")
            
            # Generate identifiers
            identifiers_result = self._generate_identifiers(article_data)
            result["identifiers"] = identifiers_result
            
            # Update status to completed
            result["status"] = "completed"
            result["completed_at"] = time.time()
            result["processing_time"] = result["completed_at"] - result["started_at"]
            
            return result
            
        except Exception as e:
            return {
                "job_id": job_id,
                "status": "error",
                "error": str(e),
                "completed_at": time.time()
            }
    
    def _generate_title(self, article_data: Dict) -> Dict:
        """Generate title for article"""
        try:
            # Call title generator
            result = subprocess.run([
                "python3", "sync_title_generator.py", 
                article_data.get("url", "")
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Parse result
                import re
                title_match = re.search(r"'title': '([^']+)'", result.stdout)
                if title_match:
                    return {"title": title_match.group(1)}
            
            return {"title": ""}
            
        except Exception as e:
            print(f"Title generation error: {e}")
            return {"title": ""}
    
    def _generate_excerpt(self, article_data: Dict) -> Dict:
        """Generate excerpt for article"""
        try:
            # Call excerpt generator
            result = subprocess.run([
                "python3", "sync_excerpt_generator.py", 
                article_data.get("url", "")
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Parse result
                import re
                excerpt_match = re.search(r"'neutral_excerpt': '([^']+)'", result.stdout)
                if excerpt_match:
                    return {"excerpt": excerpt_match.group(1)}
            
            return {"excerpt": ""}
            
        except Exception as e:
            print(f"Excerpt generation error: {e}")
            return {"excerpt": ""}
    
    def _generate_identifiers(self, article_data: Dict) -> Dict:
        """Generate identifiers for article"""
        try:
            # Call identifier generator
            result = subprocess.run([
                "python3", "sync_identifier_generator.py", 
                article_data.get("url", "")
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # Parse result
                import re
                identifiers = {}
                field_mapping = {
                    'topic_primary': 'topic_primary',
                    'topic_secondary': 'topic_secondary',
                    'entity_primary': 'entity_primary',
                    'entity_secondary': 'entity_secondary',
                    'location_primary': 'location_primary',
                    'event_or_policy': 'event_or_policy'
                }
                
                for field, key in field_mapping.items():
                    pattern = rf"'{field}': '([^']*)'"
                    match = re.search(pattern, result.stdout)
                    if match:
                        identifiers[key] = match.group(1)
                    else:
                        identifiers[key] = ""
                
                return identifiers
            
            return {}
            
        except Exception as e:
            print(f"Identifier generation error: {e}")
            return {}
    
    def get_queue_stats(self) -> Dict:
        """Get queue statistics"""
        queue_length = self.redis_client.llen(self.queue_name)
        result_count = len(self.redis_client.keys("result_*"))
        
        return {
            "queue_length": queue_length,
            "result_count": result_count,
            "worker_count": len(self.workers)
        }

def main():
    """Test the async queue processor"""
    processor = AsyncQueueProcessor()
    
    # Test with sample articles
    test_articles = [
        {
            "url": "https://www.abc.net.au/news/2025-09-29/michigan-mormon-church-fatal-shooting/105828872",
            "content": "Four dead after gunman opens fire in a Michigan Mormon church service"
        },
        {
            "url": "https://www.bbc.com/news/articles/ceq2vd15glwo",
            "content": "A gunman opened fire inside a Michigan church and set the building ablaze"
        }
    ]
    
    print("Testing async queue processor...")
    
    # Start workers
    processor.start_workers()
    
    # Enqueue articles
    job_ids = []
    for article in test_articles:
        job_id = processor.enqueue_article(article)
        job_ids.append(job_id)
        print(f"Enqueued article: {job_id}")
    
    # Wait for processing
    print("Waiting for processing...")
    time.sleep(30)  # Wait 30 seconds
    
    # Check results
    for job_id in job_ids:
        result = processor.get_job_result(job_id)
        print(f"Job {job_id}: {result.get('status', 'unknown')}")
        if result.get('status') == 'completed':
            print(f"  Title: {result.get('title', 'N/A')}")
            print(f"  Identifiers: {result.get('identifiers', {})}")
    
    # Get stats
    stats = processor.get_queue_stats()
    print(f"Queue stats: {stats}")
    
    # Stop workers
    processor.stop_workers()

if __name__ == "__main__":
    main()
