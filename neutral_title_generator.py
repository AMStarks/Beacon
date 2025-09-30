#!/usr/bin/env python3
"""
Neutral Title Generator - Creates unbiased titles from article URLs
"""

import asyncio
import httpx
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class NeutralTitleGenerator:
    """Generate neutral, factual titles from article URLs using LLM"""
    
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434", model: str = "llama3.1:8b"):
        self.ollama_url = ollama_url
        self.model = model
        self.client = httpx.AsyncClient(timeout=60.0)
    
    def generate_neutral_title(self, url: str) -> Dict[str, Any]:
        """
        Generate a neutral title from article URL
        
        Args:
            url: Article URL to process
            
        Returns:
            Dict with generated title and metadata
        """
        try:
            # Step 1: Fetch article content from URL
            article_content = await self._fetch_article_content(url)
            if not article_content:
                return {"error": "Failed to fetch article content"}
            
            # Step 2: Extract key information
            extracted_info = self._extract_article_info(article_content)
            
            # Step 3: Generate neutral title using LLM
            neutral_title = await self._generate_title_with_llm(extracted_info)
            
            # Step 4: Validate and clean title
            clean_title = self._validate_and_clean_title(neutral_title)
            
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
            
            # Extract main content (simplified)
            # Remove scripts, styles, and other non-content elements
            content_clean = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
            content_clean = re.sub(r'<style[^>]*>.*?</style>', '', content_clean, flags=re.IGNORECASE | re.DOTALL)
            content_clean = re.sub(r'<[^>]+>', ' ', content_clean)  # Remove HTML tags
            content_clean = re.sub(r'\s+', ' ', content_clean).strip()  # Clean whitespace
            
            return {
                "title": title,
                "description": description,
                "content": content_clean[:2000],  # Limit content length
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
            "content_preview": article_content.get("content", "")[:500],  # First 500 chars
            "source_domain": urlparse(article_content.get("url", "")).netloc
        }
    
    async def _generate_title_with_llm(self, article_info: Dict[str, Any]) -> str:
        """Generate neutral title using LLM"""
        try:
            # Create prompt for neutral title generation
            prompt = self._create_neutral_title_prompt(article_info)
            
            # Call Ollama API
            response = await self._call_ollama(prompt)
            
            return response.strip()
            
        except Exception as e:
            logger.error(f"❌ Error generating title with LLM: {e}")
            return "News Update"
    
    def _create_neutral_title_prompt(self, article_info: Dict[str, Any]) -> str:
        """Create prompt for neutral title generation"""
        original_title = article_info.get("original_title", "")
        content_preview = article_info.get("content_preview", "")
        source_domain = article_info.get("source_domain", "")
        
        prompt = f"""You are a neutral news editor. Create a factual, unbiased headline for this article.

Original Title: {original_title}
Source: {source_domain}
Content Preview: {content_preview}

Requirements:
- Write a neutral, factual headline (35-80 characters)
- Avoid opinion words, bias, or sensationalism
- Use title case
- No generic words like "News" or "Breaking"
- Focus on facts, not emotions
- Be specific and descriptive

Return only the headline:"""

        return prompt
    
    async def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API to get LLM response"""
        try:
            messages = [
                {
                    "role": "system",
                    "content": "You are a neutral news editor. Write factual, unbiased headlines. Return only the headline."
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
                        "max_tokens": 100,   # Short response
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
            return "News Update"
    
    def _validate_and_clean_title(self, title: str) -> str:
        """Validate and clean the generated title"""
        if not title or len(title.strip()) < 10:
            return "News Update"
        
        # Remove common prefixes/suffixes
        title = title.strip()
        title = re.sub(r'^(Headline:|Title:|News:)\s*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'\s*[.!?]+$', '', title)  # Remove trailing punctuation
        
        # Ensure proper length
        if len(title) > 100:
            title = title[:97] + "..."
        
        # Capitalize properly
        title = title.title()
        
        return title

# Test the generator
async def test_neutral_title_generator():
    """Test the neutral title generator"""
    generator = NeutralTitleGenerator()
    
    # Test with BBC article
    test_url = "https://www.bbc.com/news/articles/cj4y159190go"
    
    print("🧪 Testing Neutral Title Generator...")
    result = await generator.generate_neutral_title(test_url)
    
    if result.get("success"):
        print(f"✅ Generated Title: {result['neutral_title']}")
        print(f"📊 Original URL: {result['original_url']}")
        print(f"⏰ Generated at: {result['generated_at']}")
    else:
        print(f"❌ Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_neutral_title_generator())
