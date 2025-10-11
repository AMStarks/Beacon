#!/usr/bin/env python3
"""
Synchronous neutral title generator for Flask compatibility
"""

import requests
import re
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime
from typing import Dict, Any, Optional
import logging
import os

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Initialize logging configuration defensively
try:
    if not logging.getLogger().handlers:
        from logging_config import setup_logging
        setup_logging()
except Exception:
    # Proceed without fallback to avoid mixed formatting
    pass

logger = logging.getLogger(__name__)

class SyncNeutralTitleGenerator:
    """Generate neutral, factual titles from article URLs using synchronous requests"""
    
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434", model: str = "gemma:2b"):
        self.ollama_url = ollama_url
        self.model = model
        logger.debug(f"Initialized SyncNeutralTitleGenerator with ollama_url: {ollama_url}, model: {model}")
    
    def generate_neutral_title(self, url: str) -> Dict[str, Any]:
        """Generate a neutral title from article URL"""
        logger.info(f"🚀 Starting title generation for URL: {url}")
        try:
            # Step 1: Fetch article content from URL
            logger.debug(f"📰 Step 1: Fetching article content from {url}")
            article_content = self._fetch_article_content(url)
            if not article_content:
                logger.error(f"❌ Failed to fetch article content from {url}")
                return {"error": "Failed to fetch article content"}
            logger.debug(f"✅ Fetched {len(article_content)} characters of content")
            
            # Step 2: Extract key information
            logger.debug(f"🔍 Step 2: Extracting article information")
            extracted_info = self._extract_article_info(article_content)
            logger.debug(f"✅ Extracted info: title='{extracted_info.get('original_title', '')[:50]}...', description='{extracted_info.get('description', '')[:50]}...'")
            
            # Step 3: Generate neutral title using LLM
            logger.debug(f"🤖 Step 3: Generating title with LLM")
            neutral_title = self._generate_title_with_llm(extracted_info)
            logger.debug(f"✅ Generated title: '{neutral_title}'")
            
            # Step 4: Validate and clean title
            logger.debug(f"🧹 Step 4: Validating and cleaning title")
            clean_title = self._validate_and_clean_title(neutral_title, extracted_info.get("original_title", ""))
            logger.info(f"✅ Final clean title: '{clean_title}'")
            
            # Emit compact JSON for subprocess consumption
            result = {
                "success": True,
                "neutral_title": clean_title,
                "original_url": url,
                "extracted_info": extracted_info,
                "generated_at": datetime.now().isoformat()
            }
            import json as _json
            print(_json.dumps(result, ensure_ascii=False))
            return result
            
        except Exception as e:
            logger.error(f"❌ Error generating neutral title: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return {"error": str(e)}
    
    def _fetch_article_content(self, url: str) -> Optional[str]:
        """Fetch article content from URL using synchronous requests"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"❌ Error fetching article content: {e}")
            return None
    
    def _extract_article_info(self, content: str) -> Dict[str, Any]:
        """Extract key information from article content"""
        soup = BeautifulSoup(content, 'html.parser')
        
        # Extract title
        title = soup.title.string if soup.title else ""
        if not title:
            og_title = soup.find("meta", property="og:title")
            title = og_title["content"] if og_title else ""
        
        # Extract meta description
        desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', content, re.IGNORECASE)
        description = desc_match.group(1).strip() if desc_match else ""
        
        # Extract main content
        content_clean = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
        content_clean = re.sub(r'<style[^>]*>.*?</style>', '', content_clean, flags=re.IGNORECASE | re.DOTALL)
        content_clean = re.sub(r'<nav[^>]*>.*?</nav>', '', content_clean, flags=re.IGNORECASE | re.DOTALL)
        content_clean = re.sub(r'<header[^>]*>.*?</header>', '', content_clean, flags=re.IGNORECASE | re.DOTALL)
        content_clean = re.sub(r'<footer[^>]*>.*?</footer>', '', content_clean, flags=re.IGNORECASE | re.DOTALL)
        content_clean = re.sub(r'<aside[^>]*>.*?</aside>', '', content_clean, flags=re.IGNORECASE | re.DOTALL)
        
        # Try to find main article content
        article_match = re.search(r'<article[^>]*>(.*?)</article>', content_clean, re.IGNORECASE | re.DOTALL)
        if article_match:
            content_clean = article_match.group(1)
        else:
            main_match = re.search(r'<main[^>]*>(.*?)</main>', content_clean, re.IGNORECASE | re.DOTALL)
            if main_match:
                content_clean = main_match.group(1)
        
        content_clean = re.sub(r'<[^>]+>', ' ', content_clean)
        content_clean = re.sub(r'\s+', ' ', content_clean).strip()
        
        return {
            "original_title": title,
            "description": description,
            "content": content_clean[:2000],  # Limit for title generation
            "source_domain": ""
        }
    
    def _generate_title_with_llm(self, article_info: Dict[str, Any]) -> str:
        """Generate neutral title using LLM"""
        try:
            prompt = self._create_title_prompt(article_info)
            response = self._call_ollama(prompt)
            return response
        except Exception as e:
            logger.error(f"❌ Error generating title with LLM: {e}")
            return article_info.get("original_title", "")
    
    def _create_title_prompt(self, article_info: Dict[str, Any]) -> str:
        """Create prompt for neutral title generation"""
        original_title = article_info.get("original_title", "")
        content_preview = article_info.get("content", "")[:1000]
        
        prompt = f"""You are a neutral news editor. Create a factual, unbiased headline for this article.

Original Title: {original_title}
Content Preview: {content_preview}

Requirements:
- Write a neutral, factual headline (35-80 characters)
- Avoid opinion words, bias, or sensationalism
- Use title case
- No generic words like "News" or "Breaking"
- Focus on facts, not emotions
- Be specific and descriptive
- If the content is inappropriate or you cannot create a neutral headline, return "News Update"

Return only the headline:"""
        
        return prompt
    
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API synchronously"""
        logger.debug(f"🤖 Calling Ollama API with model: {self.model}")
        logger.debug(f"🤖 Prompt length: {len(prompt)} characters")
        logger.debug(f"🤖 Prompt preview: {prompt[:200]}...")
        
        try:
            url = f"{self.ollama_url}/api/chat"
            logger.debug(f"🤖 API URL: {url}")
            
            payload = {
                "model": self.model,
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
            }
            logger.debug(f"🤖 Payload: {payload}")
            
            response = requests.post(url, json=payload, timeout=60)
            logger.debug(f"🤖 Response status: {response.status_code}")
            logger.debug(f"🤖 Response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"🤖 Response JSON: {result}")
                content = result.get('message', {}).get('content', '').strip()
                logger.debug(f"🤖 Generated content: '{content}'")
                return content
            else:
                logger.error(f"❌ Ollama API error: {response.status_code}")
                logger.error(f"❌ Response text: {response.text}")
                raise Exception(f"Ollama API error: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Request error calling Ollama: {e}")
            logger.error(f"❌ Response status: {getattr(e.response, 'status_code', 'N/A')}")
            logger.error(f"❌ Response text: {getattr(e.response, 'text', 'N/A')}")
            return ""
        except KeyError as e:
            logger.error(f"❌ Key error in Ollama response: {e}")
            logger.error(f"❌ Response was: {response.json() if 'response' in locals() else 'No response'}")
            return ""
        except Exception as e:
            logger.error(f"❌ Unexpected error calling Ollama: {e}")
            import traceback
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return ""
    
    def _validate_and_clean_title(self, title: str, original_title: str) -> str:
        """Validate and clean the generated title"""
        if not title or len(title.strip()) < 10:
            logger.warning(f"Title too short or empty: '{title}'. Using original.")
            return original_title
        
        # Check for LLM refusal messages
        refusal_patterns = [
            r"i cannot generate",
            r"cannot create",
            r"unable to",
            r"inappropriate",
            r"strong opinion",
            r"specific reference"
        ]
        
        title_lower = title.lower()
        for pattern in refusal_patterns:
            if re.search(pattern, title_lower):
                logger.warning(f"LLM refused to generate title: '{title}'. Using fallback.")
                return "News Update"
        
        # Clean the title
        title = title.strip()
        title = re.sub(r'^(Headline:|Title:|News:|Sure, here is the headline:)\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\*\*(.*?)\*\*', r'\1', title)  # Remove markdown bold formatting
        title = re.sub(r'\s*[.!?]+$', '', title)
        
        # Remove quotes if they wrap the entire title
        if title.startswith('"') and title.endswith('"'):
            title = title[1:-1]
        
        # Ensure it starts with a capital letter
        if title and title[0].islower():
            title = title[0].upper() + title[1:]
        
        # Final validation - if still problematic, use fallback
        if len(title) < 10 or title.lower() in ["news update", "processing", "failed"]:
            return "News Update"
        
        return title

if __name__ == "__main__":
    import sys
    generator = SyncNeutralTitleGenerator()
    result = generator.generate_neutral_title(sys.argv[1] if len(sys.argv) > 1 else "https://example.com")
    if isinstance(result, dict) and "error" in result:
        print(f"Result: {result}")
    else:
        print(f"Result: {result}")
