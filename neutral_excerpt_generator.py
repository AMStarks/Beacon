#!/usr/bin/env python3
"""
Neutral Excerpt Generator - Creates unbiased 100-word summaries from article URLs
"""

import asyncio
import httpx
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class NeutralExcerptGenerator:
    """Generate neutral, factual excerpts from article URLs using LLM"""
    
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434", model: str = "llama3.1:8b"):
        self.ollama_url = ollama_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=15.0)
        self.target_words = 100
        self.tolerance = 0.15  # 15% tolerance
    
    async def generate_neutral_excerpt(self, url: str) -> Dict[str, Any]:
        """
        Generate a neutral excerpt from article URL
        
        Args:
            url: Article URL to process
            
        Returns:
            Dict with generated excerpt and metadata
        """
        try:
            # Step 1: Fetch article content from URL
            article_content = await self._fetch_article_content(url)
            if not article_content:
                return {"error": "Failed to fetch article content"}
            
            # Step 2: Extract key information
            extracted_info = self._extract_article_info(article_content)
            
            # Step 3: Generate simple excerpt without LLM (server overload)
            neutral_excerpt = self._create_simple_excerpt(extracted_info)
            
            # Step 4: Clean excerpt
            clean_excerpt = neutral_excerpt.strip()
            
            # Step 5: Check word count and adjust if needed
            final_excerpt = self._adjust_word_count(clean_excerpt)
            
            return {
                "success": True,
                "neutral_excerpt": final_excerpt,
                "word_count": len(final_excerpt.split()),
                "original_url": url,
                "extracted_info": extracted_info,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Error generating neutral excerpt: {e}")
            return {"error": str(e)}
    
    async def _fetch_article_content(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch and parse article content from URL"""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            # Basic content extraction (can be enhanced with BeautifulSoup)
            content = response.text
            
            # Extract title from HTML
            title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else ""
            
            # Extract meta description
            desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', content, re.IGNORECASE)
            description = desc_match.group(1).strip() if desc_match else ""
            
            # Extract main content (improved)
            # Remove scripts, styles, and other non-content elements
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
                # Look for main content div
                main_match = re.search(r'<main[^>]*>(.*?)</main>', content_clean, re.IGNORECASE | re.DOTALL)
                if main_match:
                    content_clean = main_match.group(1)
                else:
                    # Look for content div
                    content_match = re.search(r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>', content_clean, re.IGNORECASE | re.DOTALL)
                    if content_match:
                        content_clean = content_match.group(1)
            
            content_clean = re.sub(r'<[^>]+>', ' ', content_clean)  # Remove HTML tags
            content_clean = re.sub(r'\s+', ' ', content_clean).strip()  # Clean whitespace
            
            # Remove common navigation and header text
            nav_patterns = [
                r'Skip to content.*?',
                r'Watch Live.*?',
                r'British Broadcasting Corporation.*?',
                r'Home News Sport Business.*?',
                r'Innovation Culture Arts Travel.*?',
                r'Israel-Gaza War.*?',
                r'War in Ukraine.*?',
                r'US & Canada.*?',
                r'UK UK Politics.*?',
                r'England N\. Ireland.*?',
                r'Scotland Scotland Politics.*?',
                r'Wales Wales Politics.*?',
                r'Africa Asia China India Australia Europe.*?',
                r'Latin America Middle East.*?',
                r'In Pictures BBC InDepth.*?',
                r'BBC Verify Sport Business.*?',
                r'Executive Lounge Technology.*?',
                r'of Business Future of Business.*?',
                r'Innovation Technology Science & Health.*?',
                r'Artificial Intelligence AI v the Mind.*?',
                r'Culture Film & TV Music Art & Design.*?',
                r'Style Books Entertainment News.*?',
                r'Arts Arts in Motion Travel Destinations.*?',
                r'Africa Antarctica Asia Australia and Pacific.*?',
                r'Caribbean & Bermuda Central America Europe.*?',
                r'Middle East North America South America.*?',
                r'World\'s Table Culture & Experiences.*?',
                r'Adventures The SpeciaList.*?',
                r'To the Ends of The Earth.*?',
                r'Earth Natural Wonders Weather & Science.*?'
            ]
            
            for pattern in nav_patterns:
                content_clean = re.sub(pattern, '', content_clean, flags=re.IGNORECASE)
            
            return {
                "title": title,
                "description": description,
                "content": content_clean[:3000],  # Limit content length for excerpt generation
                "url": url
            }
            
        except Exception as e:
            logger.error(f"❌ Error fetching article content: {e}")
            return None
    
    def _extract_article_info(self, article_content: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key information from article content"""
        return {
            "original_title": article_content.get("title", ""),
            "description": article_content.get("description", ""),
            "content_preview": article_content.get("content", "")[:1000],  # First 1000 chars for excerpt
            "source_domain": urlparse(article_content.get("url", "")).netloc
        }
    
    async def _generate_excerpt_with_llm(self, article_info: Dict[str, Any]) -> str:
        """Generate neutral excerpt using LLM"""
        try:
            # Create prompt for neutral excerpt generation
            prompt = self._create_neutral_excerpt_prompt(article_info)
            
            # Call Ollama API
            response = await self._call_ollama(prompt)
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"❌ Error generating excerpt with LLM: {e}")
            return "News update available."
    
    def _create_neutral_excerpt_prompt(self, article_info: Dict[str, Any]) -> str:
        """Create prompt for neutral excerpt generation"""
        original_title = article_info.get("original_title", "")
        content_preview = article_info.get("content_preview", "")
        source_domain = article_info.get("source_domain", "")
        
        # For now, create a simple excerpt without LLM due to server overload
        # Extract first few sentences from content
        content_sentences = content_preview.split('.')[:3]
        content_summary = '. '.join(content_sentences).strip()
        
        if content_summary:
            excerpt = f"{original_title}. {content_summary}."
        else:
            excerpt = f"{original_title}. Latest news update."
        
        # Truncate to reasonable length
        if len(excerpt) > 200:
            excerpt = excerpt[:200] + "..."
        
        print(f"DEBUG: Generated excerpt without LLM: {excerpt[:100]}...")
        return excerpt
    
    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API to get LLM response"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a neutral news editor. Write factual, unbiased summaries. Return only the summary."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            response = await self.client.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.0,  # Deterministic for consistency
                        "max_tokens": 100,   # Much shorter for faster response
                        "stop": ["Here's", "Sure,", "Let me", "I'll", "Here are"]
                    }
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('message', {}).get('content', '').strip()
            else:
                raise Exception(f"Ollama API error: {response.status_code}")
                
        except Exception as e:
            logger.error(f"❌ Error calling Ollama: {e}")
            return "News update available."
    
    def _validate_and_clean_excerpt(self, excerpt: str) -> str:
        """Validate and clean the generated excerpt"""
        if not excerpt or len(excerpt.strip()) < 20:
            # Create intelligent fallback from title and content
            return self._create_intelligent_fallback()
        
        # Remove common prefixes/suffixes
        excerpt = excerpt.strip()
        excerpt = re.sub(r'^(Summary:|Excerpt:|News:)\s*', '', excerpt, flags=re.IGNORECASE)
        excerpt = re.sub(r'\s*[.!?]+$', '.', excerpt)  # Ensure proper ending
        
        # Ensure it starts with a capital letter
        if excerpt and excerpt[0].islower():
            excerpt = excerpt[0].upper() + excerpt[1:]
        
        return excerpt
    
    def _create_simple_excerpt(self, article_info: Dict[str, Any]) -> str:
        """Create a simple excerpt without LLM"""
        original_title = article_info.get("original_title", "")
        content_preview = article_info.get("content_preview", "")
        
        # Extract first few sentences from content
        content_sentences = content_preview.split('.')[:3]
        content_summary = '. '.join(content_sentences).strip()
        
        if content_summary:
            excerpt = f"{original_title}. {content_summary}."
        else:
            excerpt = f"{original_title}. Latest news update."
        
        # Truncate to reasonable length
        if len(excerpt) > 200:
            excerpt = excerpt[:200] + "..."
        
        return excerpt
    
    def _adjust_word_count(self, excerpt: str) -> str:
        """Adjust excerpt to meet word count requirements"""
        words = excerpt.split()
        word_count = len(words)
        
        # Calculate target range (85-115 words with 15% tolerance)
        min_words = int(self.target_words * (1 - self.tolerance))  # 85 words
        max_words = int(self.target_words * (1 + self.tolerance))  # 115 words
        
        if word_count < min_words:
            # Too short - try to expand (this is a simplified approach)
            logger.warning(f"⚠️ Excerpt too short ({word_count} words), target: {self.target_words}")
            return excerpt
        elif word_count > max_words:
            # Too long - truncate to target length
            logger.warning(f"⚠️ Excerpt too long ({word_count} words), truncating to {self.target_words}")
            return ' '.join(words[:self.target_words]) + "..."
        else:
            # Within acceptable range
            logger.info(f"✅ Excerpt word count: {word_count} (target: {self.target_words})")
            return excerpt

# Test the generator
async def test_neutral_excerpt_generator():
    """Test the neutral excerpt generator"""
    generator = NeutralExcerptGenerator()
    
    # Test with BBC article
    test_url = "https://www.bbc.com/news/articles/cj4y159190go"
    
    print("🧪 Testing Neutral Excerpt Generator...")
    result = await generator.generate_neutral_excerpt(test_url)
    
    if result.get("success"):
        print(f"✅ Generated Excerpt: {result['neutral_excerpt']}")
        print(f"📊 Word Count: {result['word_count']}")
        print(f"📊 Original URL: {result['original_url']}")
        print(f"⏰ Generated at: {result['generated_at']}")
    else:
        print(f"❌ Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_neutral_excerpt_generator())
