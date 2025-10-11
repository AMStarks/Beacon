#!/usr/bin/env python3
"""
Synchronous neutral excerpt generator for Flask compatibility
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

class SyncNeutralExcerptGenerator:
    """Generate neutral, factual excerpts from article URLs using synchronous requests"""
    
    def __init__(self, ollama_url: str = "http://127.0.0.1:11434", model: str = "gemma:2b"):
        self.ollama_url = ollama_url
        self.model = model
        self.target_words = 100
        self.tolerance = 0.15  # 15% tolerance
    
    def generate_neutral_excerpt(self, url: str) -> Dict[str, Any]:
        """Generate a neutral excerpt from article URL"""
        try:
            # Step 1: Fetch article content from URL
            article_content = self._fetch_article_content(url)
            if not article_content:
                return {"success": False, "error": "Failed to fetch article content"}
            
            # Step 2: Extract key information
            extracted_info = self._extract_article_info(article_content)
            
            # Step 3: Generate excerpt using LLM
            neutral_excerpt = self._generate_excerpt_with_llm(
                extracted_info.get("content", ""), 
                extracted_info.get("original_title", "")
            )
            
            if not neutral_excerpt:
                return {"success": False, "error": "LLM failed to generate excerpt"}
            
            # Step 4: Clean and validate excerpt
            clean_excerpt = neutral_excerpt.strip()
            word_count = len(clean_excerpt.split())
            
            result = {
                "success": True,
                "neutral_excerpt": clean_excerpt,
                "word_count": word_count,
                "original_url": url,
                "extracted_info": extracted_info,
                "generated_at": datetime.now().isoformat()
            }
            import json as _json
            print(_json.dumps(result, ensure_ascii=False))
            return result
            
        except Exception as e:
            logger.error(f"❌ Error generating neutral excerpt: {e}")
            return {"success": False, "error": str(e)}
    
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
        
        # Extract main content (improved)
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
            "content": content_clean[:500],  # Limit for excerpt generation
            "source_domain": ""
        }
    
    def _generate_excerpt_with_llm(self, content: str, original_title: str) -> str:
        """Generate neutral excerpt using Grok-style two-stage approach"""
        try:
            # Try Grok-style LLM approach first
            logger.info("🤖 Attempting Grok-style LLM pipeline...")
            excerpts = self._extract_unique_excerpts_grok(content)
            if excerpts:
                summary = self._synthesize_neutral_summary_grok(excerpts)
                if summary:
                    return self._post_process_summary_grok(summary)
            
            # Fallback to intelligent extraction
            logger.info("🔄 Falling back to intelligent Grok-style extraction...")
            return self._intelligent_extraction_grok(content, original_title)
            
        except Exception as e:
            logger.error(f"❌ Error in Grok-style generation: {e}")
            return self._intelligent_extraction_grok(content, original_title)
    
    def _extract_unique_excerpts_grok(self, content: str) -> list:
        """Stage 1: Extract unique excerpts using Grok approach"""
        try:
            # Truncate if too long
            if len(content) > 2000:
                content = content[:2000] + "..."
            
            prompt = f"Extract 4-6 unique key excerpts from this article. Each should be a concise sentence. Output as numbered list:\n\n{content}"
            
            messages = [
                {"role": "system", "content": "Extract unique, factual excerpts. Return only numbered list."},
                {"role": "user", "content": prompt}
            ]
            
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.1, "max_tokens": 300}
                },
                timeout=20  # Shorter timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                content_text = result.get('message', {}).get('content', '').strip()
                
                # Parse numbered list
                excerpts = []
                for line in content_text.split('\n'):
                    line = line.strip()
                    if re.match(r'^\d+\.', line):
                        excerpt = re.sub(r'^\d+\.\s*', '', line).strip()
                        if excerpt and len(excerpt) > 15:
                            excerpts.append(excerpt)
                
                return excerpts[:6]
            return []
                
        except Exception as e:
            logger.error(f"❌ Grok extraction failed: {e}")
            return []
    
    def _synthesize_neutral_summary_grok(self, excerpts: list) -> str:
        """Stage 2: Synthesize using Grok approach"""
        try:
            excerpts_text = '\n'.join([f"{i+1}. {excerpt}" for i, excerpt in enumerate(excerpts)])
            
            prompt = f"Create a neutral 100-word summary using these excerpts. Be factual and objective:\n\n{excerpts_text}"
            
            messages = [
                {"role": "system", "content": "Create neutral, factual summaries. Return only the summary."},
                {"role": "user", "content": prompt}
            ]
            
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.1, "max_tokens": 150}
                },
                timeout=20
            )
            
            if response.status_code == 200:
                result = response.json()
                summary = result.get('message', {}).get('content', '').strip()
                return re.sub(r'^(Summary:|Key points:)', '', summary, flags=re.IGNORECASE).strip()
            return ""
                
        except Exception as e:
            logger.error(f"❌ Grok synthesis failed: {e}")
            return ""
    
    def _intelligent_extraction_grok(self, content: str, title: str) -> str:
        """Intelligent extraction using Grok-style scoring"""
        try:
            # Split into sentences
            sentences = re.split(r'[.!?]+', content)
            sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 20]
            
            # Score sentences based on Grok's criteria
            scored_sentences = []
            for sentence in sentences:
                score = self._score_sentence_grok_style(sentence, title)
                if score > 0.3:  # Only keep high-scoring sentences
                    scored_sentences.append((sentence, score))
            
            # Sort by score and take top sentences
            scored_sentences.sort(key=lambda x: x[1], reverse=True)
            top_sentences = [sent[0] for sent in scored_sentences[:6]]
            
            # Create structured summary
            if top_sentences:
                summary = '. '.join(top_sentences) + '.'
                return self._post_process_summary_grok(summary)
            else:
                return self._create_simple_summary_grok(content, title)
                
        except Exception as e:
            logger.error(f"❌ Intelligent extraction failed: {e}")
            return self._create_simple_summary_grok(content, title)
    
    def _score_sentence_grok_style(self, sentence: str, title: str) -> float:
        """Score sentences using Grok's approach - focus on warnings, divisions, quotes, polling, reviews"""
        score = 0.0
        
        # Key Grok criteria
        grok_indicators = [
            'warn', 'warned', 'warning', 'alienate', 'abandon', 'fracture', 'division',
            'polling', 'survey', 'review', 'policy', 'climate', 'net zero', 'emissions',
            'said', 'stated', 'noted', 'emphasized', 'highlighted', 'urged', 'called',
            'percentage', '%', 'voters', 'election', 'party', 'liberal', 'conservative'
        ]
        
        sentence_lower = sentence.lower()
        for indicator in grok_indicators:
            if indicator in sentence_lower:
                score += 0.1
        
        # Title relevance
        title_words = set(title.lower().split())
        sentence_words = set(sentence_lower.split())
        common_words = title_words.intersection(sentence_words)
        if common_words:
            score += 0.2 * (len(common_words) / len(title_words))
        
        # Length preference (medium-length sentences)
        word_count = len(sentence.split())
        if 10 <= word_count <= 40:
            score += 0.2
        elif 5 <= word_count <= 60:
            score += 0.1
        
        # Avoid boilerplate
        boilerplate = ['share', 'save', 'follow', 'subscribe', 'newsletter', 'photograph', 'view image']
        if not any(bp in sentence_lower for bp in boilerplate):
            score += 0.1
        
        return score
    
    def _create_simple_summary_grok(self, content: str, title: str) -> str:
        """Simple fallback summary"""
        sentences = content.split('.')[:5]
        meaningful = [s.strip() for s in sentences if len(s.strip()) > 30 and not any(word in s.lower() for word in ['share', 'save', 'follow'])]
        
        if meaningful:
            summary = '. '.join(meaningful[:3]) + '.'
            return self._post_process_summary_grok(summary)
        else:
            return f"{title}. Latest news update."
    
    def _post_process_summary_grok(self, summary: str) -> str:
        """Post-process to enforce word count"""
        try:
            words = summary.split()
            word_count = len(words)
            
            min_words = int(self.target_words * (1 - self.tolerance))
            max_words = int(self.target_words * (1 + self.tolerance))
            
            if word_count > max_words:
                # Truncate by sentences
                sentences = re.split(r'[.!?]+', summary)
                sentences = [s.strip() for s in sentences if s.strip()]
                current_words = []
                for sent in sentences:
                    sent_words = sent.split()
                    if len(current_words) + len(sent_words) <= max_words:
                        current_words.extend(sent_words)
                    else:
                        break
                summary = ' '.join(current_words)
                if summary and not summary.endswith('.'):
                    summary += '.'
            
            elif word_count < min_words:
                summary += " Additional details available in the full article."
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Post-processing failed: {e}")
            return summary
    
    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API synchronously"""
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
            
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "max_tokens": 150
                    }
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('message', {}).get('content', '').strip()
            else:
                raise Exception(f"Ollama API error: {response.status_code}")
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ Ollama API call timed out after 30 seconds.")
            return ""
        except Exception as e:
            logger.error(f"❌ Error calling Ollama: {e}")
            return ""

if __name__ == "__main__":
    import sys
    # Intentionally do not print anything else here; generate_neutral_excerpt already prints JSON
    generator = SyncNeutralExcerptGenerator()
    _ = generator.generate_neutral_excerpt(sys.argv[1] if len(sys.argv) > 1 else "https://example.com")
