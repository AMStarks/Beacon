#!/usr/bin/env python3
"""
Batch LLM processor for processing multiple articles in single LLM calls.
More efficient than individual calls.
"""

import requests
import json
import re
from typing import List, Dict, Any
import time

class BatchLLMProcessor:
    def __init__(self, ollama_url="http://localhost:11434/api/generate", model="gemma:2b"):
        self.ollama_url = ollama_url
        self.model = model
    
    def process_batch_identifiers(self, articles: List[Dict]) -> List[Dict]:
        """Process multiple articles for identifiers in a single LLM call"""
        if not articles:
            return []
        
        # Prepare batch content
        batch_content = ""
        for i, article in enumerate(articles, 1):
            content = article.get('content', '')[:1000]  # Limit content length
            batch_content += f"Article {i}:\n{content}\n\n"
        
        # Create batch prompt
        prompt = f"""Extract identifiers from these {len(articles)} articles:

{batch_content}

For each article, provide:
**Main topic:** [2-4 words]
**Secondary topic:** [2-4 words]  
**Main person/org:** [2-4 words]
**Secondary entity:** [2-4 words]
**Main location:** [2-4 words]
**Specific event:** [2-4 words]

Format as: Article 1: [identifiers], Article 2: [identifiers], etc."""
        
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9
                    }
                },
                timeout=180  # Longer timeout for batch processing
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                return self._parse_batch_response(response_text, len(articles))
            else:
                print(f"Batch LLM error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"Batch processing error: {e}")
            return []
    
    def _parse_batch_response(self, response_text: str, num_articles: int) -> List[Dict]:
        """Parse batch LLM response"""
        results = []
        
        # Look for each article's identifiers
        for i in range(1, num_articles + 1):
            article_identifiers = {}
            
            # Try to find identifiers for this article
            article_pattern = rf'Article {i}.*?(?=Article {i+1}|$)'
            match = re.search(article_pattern, response_text, re.DOTALL | re.IGNORECASE)
            
            if match:
                article_text = match.group(0)
                
                # Extract each field
                fields = ['Main topic', 'Secondary topic', 'Main person/org', 'Secondary entity', 'Main location', 'Specific event']
                field_keys = ['topic_primary', 'topic_secondary', 'entity_primary', 'entity_secondary', 'location_primary', 'event_or_policy']
                
                for field, key in zip(fields, field_keys):
                    pattern = rf'\*\*{re.escape(field)}:\*\*\s*([^\n]+)'
                    field_match = re.search(pattern, article_text, re.IGNORECASE)
                    if field_match:
                        article_identifiers[key] = field_match.group(1).strip()
                    else:
                        article_identifiers[key] = ''
            else:
                # Fallback: create empty identifiers
                article_identifiers = {
                    'topic_primary': '',
                    'topic_secondary': '',
                    'entity_primary': '',
                    'entity_secondary': '',
                    'location_primary': '',
                    'event_or_policy': ''
                }
            
            results.append(article_identifiers)
        
        return results
    
    def process_batch_titles(self, articles: List[Dict]) -> List[str]:
        """Process multiple articles for titles in a single LLM call"""
        if not articles:
            return []
        
        # Prepare batch content
        batch_content = ""
        for i, article in enumerate(articles, 1):
            content = article.get('content', '')[:1000]
            batch_content += f"Article {i}:\n{content}\n\n"
        
        prompt = f"""Generate neutral titles for these {len(articles)} articles:

{batch_content}

Format as: Article 1: [title], Article 2: [title], etc."""
        
        try:
            response = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": 0.9
                    }
                },
                timeout=180
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                return self._parse_batch_titles(response_text, len(articles))
            else:
                print(f"Batch title error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"Batch title processing error: {e}")
            return []
    
    def _parse_batch_titles(self, response_text: str, num_articles: int) -> List[str]:
        """Parse batch title response"""
        titles = []
        
        for i in range(1, num_articles + 1):
            pattern = rf'Article {i}:\s*([^\n]+)'
            match = re.search(pattern, response_text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                # Clean title
                title = re.sub(r'\*\*', '', title)  # Remove markdown
                title = re.sub(r'^[^:]*:', '', title)  # Remove prefixes
                titles.append(title)
            else:
                titles.append(f"Article {i} Title")
        
        return titles

def main():
    """Test batch processing"""
    processor = BatchLLMProcessor()
    
    # Test with sample articles
    test_articles = [
        {
            'content': 'Four dead after gunman opens fire in a Michigan Mormon church service before setting it on fire. The suspect has been identified as Thomas Jacob Sanford, from neighbouring Burton.'
        },
        {
            'content': 'A gunman opened fire inside a Michigan church and set the building ablaze during a crowded Sunday service, killing four people and injuring eight, before he was fatally shot by police.'
        }
    ]
    
    print("Testing batch identifier processing...")
    start_time = time.time()
    identifiers = processor.process_batch_identifiers(test_articles)
    end_time = time.time()
    
    print(f"Batch processing completed in {end_time - start_time:.2f} seconds")
    print(f"Processed {len(identifiers)} articles")
    
    for i, ident in enumerate(identifiers):
        print(f"Article {i+1} identifiers: {ident}")

if __name__ == "__main__":
    main()
