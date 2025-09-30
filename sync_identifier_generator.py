#!/usr/bin/env python3
"""
Updated identifier generator for 6 typed JSON fields.
Generates: topic_primary, topic_secondary, entity_primary, entity_secondary, location_primary, event_or_policy
"""

import requests
import json
import re
import sys
import os

class SyncIdentifierGenerator:
    def __init__(self):
        self.ollama_url = "http://localhost:11434/api/generate"
        self.model = "gemma:2b"
        
    def _fetch_article_content(self, url):
        """Fetch article content from URL"""
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"Error fetching article content: {e}")
            return None
    
    def _clean_identifier(self, identifier):
        """Clean and normalize identifier text"""
        if not identifier:
            return ""
        
        # Remove common prefixes
        prefixes_to_remove = [
            "Sure, here are the key identifiers:",
            "Here are the key identifiers:",
            "Key identifiers:",
            "Identifiers:",
            "The key identifiers are:",
            "Based on the article, the key identifiers are:"
        ]
        
        cleaned = identifier.strip()
        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
        
        return cleaned
    
    def _parse_json_response(self, response_text):
        """Parse response and extract 6 typed identifiers"""
        try:
            # Clean the response
            cleaned = self._clean_identifier(response_text)
            
            # Parse the format: **1. Main topic:** Church service, etc.
            result = {}
            
            # Map the label format to our fields
            field_mapping = {
                'Main topic': 'topic_primary',
                'Secondary topic': 'topic_secondary', 
                'Main person/organization': 'entity_primary',
                'Secondary entity': 'entity_secondary',
                'Location_primary': 'location_primary',
                'Specific event': 'event_or_policy'
            }
            
            for label, field in field_mapping.items():
                # Pattern to match "**Label:** answer"
                pattern = rf'\*\*{re.escape(label)}:\*\*\s*([^\n]+)'
                match = re.search(pattern, cleaned, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    # Remove any remaining markdown
                    value = re.sub(r'\*\*', '', value)
                    result[field] = value
                    print(f"Found {field}: {value}")
                else:
                    result[field] = ''
                    print(f"Not found {field}")
            
            # Validate that we have meaningful content
            if any(result.values()):
                return result
                    
        except Exception as e:
            print(f"Parsing error: {e}")
            print(f"Raw response: {response_text}")
        
        # Fallback: return empty structure
        return {
            'topic_primary': '',
            'topic_secondary': '',
            'entity_primary': '',
            'entity_secondary': '',
            'location_primary': '',
            'event_or_policy': ''
        }
    
    def generate_identifiers(self, url):
        """Generate 6 typed identifiers for an article"""
        print(f"Generating identifiers for: {url}")
        
        # Fetch article content
        content = self._fetch_article_content(url)
        if not content:
            print("Failed to fetch article content")
            return None
        
        # Truncate content if too long
        if len(content) > 2000:
            content = content[:2000] + "..."
        
        # Optimized prompt - shorter and more direct
        prompt = f"""Extract from: {content}

**Main topic:** [2-4 words]
**Secondary topic:** [2-4 words]  
**Main person/org:** [2-4 words]
**Secondary entity:** [2-4 words]
**Main location:** [2-4 words]
**Specific event:** [2-4 words]"""

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
                timeout=120  # Increased timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                response_text = result.get('response', '')
                
                # Parse the JSON response
                identifiers = self._parse_json_response(response_text)
                
                print(f"Generated identifiers: {identifiers}")
                return identifiers
            else:
                print(f"Ollama API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"Error generating identifiers: {e}")
            return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 sync_identifier_generator.py <url>")
        sys.exit(1)
    
    url = sys.argv[1]
    generator = SyncIdentifierGenerator()
    identifiers = generator.generate_identifiers(url)
    
    if identifiers:
        print("\n=== GENERATED IDENTIFIERS ===")
        for key, value in identifiers.items():
            print(f"{key}: {value}")
    else:
        print("Failed to generate identifiers")

if __name__ == "__main__":
    main()
