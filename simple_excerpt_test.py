#!/usr/bin/env python3
"""
Simple synchronous excerpt test
"""

import requests
import json

def test_simple_excerpt():
    """Test excerpt generation with synchronous requests"""
    print("🧪 Testing simple excerpt generation...")
    
    prompt = "Write a brief summary: China makes landmark pledge to cut its climate emissions"
    
    try:
        response = requests.post(
            "http://127.0.0.1:11434/api/chat",
            json={
                "model": "llama3.1:8b",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "max_tokens": 100
                }
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result.get('message', {}).get('content', '').strip()
            print(f"✅ LLM Response: {content}")
            print(f"Word count: {len(content.split())}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_simple_excerpt()
