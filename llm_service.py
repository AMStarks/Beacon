#!/usr/bin/env python3
"""
Robust LLM Service with proper async integration and fallbacks.
Replaces fragile subprocess calls with proper async HTTP requests.
"""

import asyncio
import aiohttp
import json
import logging
from typing import Optional, Dict, Any
import re

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "gemma:2b"):
        self.ollama_url = ollama_url.rstrip('/')
        self.model = model
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.max_retries = 2

    async def generate_title(self, content: str, original_title: str = "") -> str:
        """Generate neutral title with fallback to rule-based generation"""
        try:
            # Try LLM first
            llm_title = await self._call_ollama_title(content, original_title)
            if llm_title and self._is_valid_title(llm_title):
                logger.info(f"✅ LLM generated title: '{llm_title}'")
                return llm_title

        except Exception as e:
            logger.warning(f"⚠️ LLM title generation failed: {e}")

        # Fallback to rule-based generation
        logger.info("🔄 Using rule-based title generation")
        return self._generate_title_fallback(content, original_title)

    async def generate_excerpt(self, content: str, original_title: str = "") -> str:
        """Generate neutral excerpt with fallback to rule-based generation"""
        try:
            # Try LLM first
            llm_excerpt = await self._call_ollama_excerpt(content, original_title)
            if llm_excerpt and self._is_valid_excerpt(llm_excerpt):
                logger.info(f"✅ LLM generated excerpt: '{llm_excerpt[:50]}...'")
                return llm_excerpt

        except Exception as e:
            logger.warning(f"⚠️ LLM excerpt generation failed: {e}")

        # Fallback to rule-based generation
        logger.info("🔄 Using rule-based excerpt generation")
        return self._generate_excerpt_fallback(content, original_title)

    async def _call_ollama_title(self, content: str, original_title: str) -> Optional[str]:
        """Call Ollama API for title generation"""
        prompt = f"""You are a neutral news editor. Create a factual, unbiased headline for this article.

Original Title: {original_title}
Content Preview: {content[:1000]}

Requirements:
- Write a neutral, factual headline (35-80 characters)
- Avoid opinion words, bias, or sensationalism
- Use title case
- No generic words like "News" or "Breaking"
- Focus on facts, not emotions
- Be specific and descriptive

Return only the headline:"""

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(
                        f"{self.ollama_url}/api/chat",
                        json={
                            "model": self.model,
                            "messages": [{"role": "user", "content": prompt}],
                            "stream": False,
                            "options": {"temperature": 0.0, "max_tokens": 100}
                        }
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            title = result.get('message', {}).get('content', '').strip()
                            return self._clean_llm_output(title)
            except Exception as e:
                logger.warning(f"LLM title attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)

        return None

    async def _call_ollama_excerpt(self, content: str, original_title: str) -> Optional[str]:
        """Call Ollama API for excerpt generation"""
        prompt = f"""Create a neutral, factual summary (80-120 words) of this news article.

Title: {original_title}
Content: {content[:1500]}

Requirements:
- Be completely neutral and factual
- Include key facts and context
- Avoid opinions or bias
- Write in proper journalistic style
- Focus on who, what, when, where, why
- No sensationalism or emotional language

Return only the summary:"""

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(
                        f"{self.ollama_url}/api/chat",
                        json={
                            "model": self.model,
                            "messages": [{"role": "user", "content": prompt}],
                            "stream": False,
                            "options": {"temperature": 0.1, "max_tokens": 200}
                        }
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            excerpt = result.get('message', {}).get('content', '').strip()
                            return self._clean_llm_output(excerpt)
            except Exception as e:
                logger.warning(f"LLM excerpt attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)

        return None

    def _clean_llm_output(self, text: str) -> str:
        """Clean LLM output"""
        if not text:
            return ""

        # Remove common prefixes
        text = re.sub(r'^(Headline:|Title:|Summary:|Excerpt:)\s*', '', text, flags=re.IGNORECASE)

        # Remove quotes if they wrap the entire text
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _is_valid_title(self, title: str) -> bool:
        """Check if LLM-generated title is valid"""
        if not title or len(title) < 10 or len(title) > 100:
            return False

        # Check for refusal patterns
        refusal_words = ['cannot', 'unable', 'inappropriate', 'sorry']
        return not any(word in title.lower() for word in refusal_words)

    def _is_valid_excerpt(self, excerpt: str) -> bool:
        """Check if LLM-generated excerpt is valid"""
        if not excerpt or len(excerpt) < 50 or len(excerpt) > 300:
            return False

        # Check for refusal patterns
        refusal_words = ['cannot', 'unable', 'inappropriate', 'sorry']
        return not any(word in excerpt.lower() for word in refusal_words)

    def _generate_title_fallback(self, content: str, original_title: str) -> str:
        """Rule-based title generation fallback"""
        # Extract first meaningful sentence
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if sentences:
            # Use first sentence as title, limit length
            title = sentences[0][:80]
            if not title.endswith('.'):
                title += '.'
            return title

        # Ultimate fallback
        return original_title or "News Update"

    def _generate_excerpt_fallback(self, content: str, original_title: str) -> str:
        """Rule-based excerpt generation fallback"""
        # Extract key sentences
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]

        # Take first 2-3 sentences, ensure total length is reasonable
        excerpt_sentences = sentences[:3]
        excerpt = '. '.join(excerpt_sentences)

        if len(excerpt) > 200:
            excerpt = excerpt[:197] + '...'

        return excerpt if excerpt else f"{original_title}. Latest news update."

# Global LLM service instance
_llm_service = None

def get_llm_service() -> LLMService:
    """Get global LLM service instance"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

# Test function
async def test_llm_service():
    """Test LLM service functionality"""
    service = get_llm_service()

    # Test content
    test_content = """
    Scientists at a major university have discovered a new method for recycling plastic waste.
    The breakthrough could help reduce pollution in oceans and landfills. Researchers say the
    process is cost-effective and environmentally friendly. The team published their findings
    in a leading scientific journal yesterday.
    """

    print("Testing LLM service...")

    # Test title generation
    title = await service.generate_title(test_content, "Plastic Recycling Breakthrough")
    print(f"Generated title: {title}")

    # Test excerpt generation
    excerpt = await service.generate_excerpt(test_content, "Plastic Recycling Breakthrough")
    print(f"Generated excerpt: {excerpt}")

if __name__ == "__main__":
    asyncio.run(test_llm_service())
