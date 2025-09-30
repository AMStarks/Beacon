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

logger = logging.getLogger(__name__)

class SyncNeutralTitleGenerator:
    """Generate neutral, factual titles from article URLs using synchronous requests"""
    
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434", model: str = "gemma:2b"):
        self.ollama_url = ollama_url
        self.model = model
    
    def generate_neutral_title(self, url: str) -> Dict[str, Any]:
        """Generate a neutral title from article URL"""
        try:
            # Step 1: Fetch article content from URL
            article_content = self._fetch_article_content(url)
            if not article_content:
                return {"error": "Failed to fetch article content"}
            
            # Step 2: Extract key information
            extracted_info = self._extract_article_info(article_content)
            
            # Step 3: Generate neutral title using LLM
            neutral_title = self._generate_title_with_llm(extracted_info)
            
            # Step 4: Validate and clean title
            clean_title = self._validate_and_clean_title(neutral_title, extracted_info.get("original_title", ""))
            
            return {
                "success": True,
                "neutral_title": clean_title,
                "original_url": url,
                "extracted_info": extracted_info,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating neutral title: {e}")
            return {"error": str(e)}
    
    def _fetch_article_content(self, url: str) -> Optional[str]:
        """Fetch article content from URL using synchronous requests"""
        try:
            response = requests.get(url, timeout=30)
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
        
        prompt = f"""Create a neutral headline for: {original_title}. Return only the headline:"""
        
        return prompt
    
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API synchronously"""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
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
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('message', {}).get('content', '').strip()
            else:
                raise Exception(f"Ollama API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Error calling Ollama: {e}")
            return ""
    
    def _validate_and_clean_title(self, title: str, original_title: str) -> str:
        """Validate and clean the generated title"""
        if not title or len(title.strip()) < 10:
            logger.warning(f"Title too short or empty: '{title}'. Using original.")
            return original_title
        
        # Clean the title
        title = title.strip()
        title = re.sub(r'^(Headline:|Title:|News:)\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*[.!?]+$', '', title)
        
        # Ensure it starts with a capital letter
        if title and title[0].islower():
            title = title[0].upper() + title[1:]
        
        return title
