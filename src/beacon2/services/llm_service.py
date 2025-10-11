#!/usr/bin/env python3
"""
LLM Service - Robust integration with Ollama and rule-based fallbacks
"""

import asyncio
import aiohttp
import json
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class LLMService:
    """Robust LLM service with multiple fallback strategies"""

    def __init__(self, ollama_url: str = "http://localhost:11434", model: str = "gemma:2b"):
        self.ollama_url = ollama_url.rstrip('/')
        self.model = model
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.max_retries = 2
        self.target_excerpt_words = 150  # Target word count for excerpts
        self.excerpt_tolerance = 0.3  # 30% tolerance

    async def generate_title(self, content: str, original_title: str = "") -> str:
        """Generate neutral title with LLM + fallback"""
        # Try LLM first
        llm_title = await self._call_llm_title(content, original_title)
        if llm_title and self._is_valid_title(llm_title):
            return llm_title

        # Fallback to rule-based
        return self._generate_title_fallback(content, original_title)

    async def generate_excerpt(self, content: str, original_title: str = "") -> str:
        """Generate neutral excerpt with LLM + fallback"""
        # Try LLM first
        llm_excerpt = await self._call_llm_excerpt(content, original_title)
        if llm_excerpt and self._is_valid_excerpt(llm_excerpt):
            return llm_excerpt

        # Fallback to rule-based
        return self._generate_excerpt_fallback(content, original_title)

    async def _call_llm_title(self, content: str, original_title: str) -> Optional[str]:
        """Call Ollama for title generation"""
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

    async def _call_llm_excerpt(self, content: str, original_title: str) -> Optional[str]:
        """Call Ollama for excerpt generation"""
        # Pre-clean content to remove obvious webpage artifacts
        cleaned_content = self._pre_clean_content(content)

        prompt = f"""Analyze this news article and extract the core topic and key facts for similarity comparison.

Article Title: {original_title}
Article Content: {cleaned_content[:4000]}

ANALYSIS INSTRUCTIONS:
- Identify the MAIN TOPIC/EVENT (what happened, where, when)
- Extract KEY ENTITIES (people, places, organizations involved)
- Find SIGNIFICANT DETAILS (numbers, outcomes, context)
- Focus on FACTUAL CONTENT only (ignore metadata, timestamps, credits)

POLITICAL NEUTRALITY REQUIREMENTS:
- Remain completely neutral and factual
- Avoid any political bias, opinion, or judgment
- Present information objectively without favoring any viewpoint
- Use neutral language that reports facts without interpretation

TOPIC IDENTIFICATION:
- What is the primary news event or story?
- Who are the main people/organizations involved?
- What are the key facts and outcomes?

IMPORTANT: Generate a DETAILED summary that is 250-350 words long. Provide comprehensive factual information about the event, including:
- Full context and background
- All key details and timeline
- Involved parties and their roles
- Outcomes and consequences
- Any official statements or investigations

Return a structured analysis in this format:
TOPIC: [main topic/event in 3-5 words]
ENTITIES: [key people/places/orgs involved]
FACTS: [3-5 key factual details]
SUMMARY: [Detailed neutral summary in 100-150 words providing comprehensive factual information about the event, including key details, context, and outcomes while maintaining complete objectivity]"""

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(
                        f"{self.ollama_url}/api/chat",
                        json={
                            "model": self.model,
                            "messages": [{"role": "user", "content": prompt}],
                            "stream": False,
                            "options": {"temperature": 0.05, "max_tokens": 400}
                        }
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            raw_response = result.get('message', {}).get('content', '').strip()

                            # Parse structured response
                            analysis = self._parse_llm_analysis(raw_response)
                            if analysis and analysis.get('summary'):
                                # Use the summary as the excerpt
                                excerpt = analysis['summary']
                                cleaned_excerpt = self._clean_llm_output(excerpt)

                                # Validate: should not contain obvious webpage artifacts
                                artifacts = [
                                    'illustration', 'getty', 'shutterstock', 'video', '0:',
                                    'explainer', 'news|', 'civil rights', 'opinion',
                                    'matt kenyon', 'the guardian', 'shutterstock', 'izzuanroslan',
                                    'by ', 'share', 'follow', 'subscribe'
                                ]
                                has_artifacts = any(artifact in cleaned_excerpt.lower() for artifact in artifacts)

                                if not has_artifacts:
                                    word_count = len(cleaned_excerpt.split())
                                    if 80 <= word_count <= 200:  # Range for 100-150 word LLM-generated excerpts
                                        return cleaned_excerpt
            except Exception as e:
                logger.warning(f"LLM excerpt attempt {attempt + 1} failed: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)

        return None

    def _clean_llm_output(self, text: str) -> str:
        """Clean LLM output"""
        if not text:
            return ""

        # Remove common prefixes (more comprehensive)
        prefixes = [
            r'^Sure, here is the headline:\s*',
            r'^Here is the headline:\s*',
            r'^The headline is:\s*',
            r'^Headline:\s*',
            r'^Title:\s*',
            r'^Summary:\s*',
            r'^Excerpt:\s*',
            r'^\*\*Sure, here is the headline:\s*\*\*',
            r'^\*\*',
            r'^\*',
        ]

        for prefix in prefixes:
            text = re.sub(prefix, '', text, flags=re.IGNORECASE)

        # Remove common suffixes (like trailing **)
        suffixes = [
            r'\*\*$',  # Remove trailing **
            r'\*$',    # Remove trailing *
        ]

        for suffix in suffixes:
            text = re.sub(suffix, '', text)

        # Remove quotes if they wrap the entire text
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]

        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _parse_llm_analysis(self, response: str) -> Optional[Dict[str, str]]:
        """Parse structured LLM analysis response"""
        try:
            lines = response.strip().split('\n')
            analysis = {}

            for line in lines:
                line = line.strip()
                if ': ' in line:
                    key, value = line.split(': ', 1)
                    key = key.strip().upper()
                    value = value.strip()
                    analysis[key] = value

            return analysis if analysis else None

        except Exception as e:
            logger.warning(f"Failed to parse LLM analysis: {e}")
            return None

    def _pre_clean_content(self, content: str) -> str:
        """Pre-clean content before sending to LLM to remove obvious webpage artifacts"""
        if not content:
            return ""

        # Remove video timestamps and player elements
        content = re.sub(r'\d{1,2}:\d{2}', '', content)  # Remove timestamps like "0:24"

        # Remove author bylines and metadata patterns
        content = re.sub(r'By [A-Za-z\s]+|Share|Follow us|Subscribe', '', content, flags=re.IGNORECASE)

        # Remove image/video references
        content = re.sub(r'Illustration:|Getty Images|Shutterstock|View image|video|Video', '', content, flags=re.IGNORECASE)

        # Remove common metadata patterns
        content = re.sub(r'EXPLAINER|News\|Civil Rights|Opinion', '', content, flags=re.IGNORECASE)

        # Clean up excessive whitespace
        content = re.sub(r'\s+', ' ', content).strip()

        return content

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
        # Pre-clean content to remove obvious artifacts
        cleaned_content = self._pre_clean_content(content)

        # Extract key sentences
        sentences = re.split(r'[.!?]+', cleaned_content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        if not sentences:
            return f"{original_title}. News update."

        # Take sentences to reach target word count
        excerpt_sentences = []
        current_words = 0
        target_words = int(self.target_excerpt_words * (1 - self.excerpt_tolerance))

        for sentence in sentences:
            # Skip sentences that look like metadata
            if any(meta in sentence.lower() for meta in ['illustration', 'getty', 'shutterstock', 'explainer', 'news|']):
                continue

            sentence_words = len(sentence.split())
            if current_words + sentence_words <= target_words * 1.5:  # Allow some flexibility
                excerpt_sentences.append(sentence)
                current_words += sentence_words
            else:
                break

        excerpt = '. '.join(excerpt_sentences)

        # Ensure minimum length
        if current_words < 50 and len(sentences) > len(excerpt_sentences):
            # Add more sentences if we don't have enough content
            remaining_sentences = sentences[len(excerpt_sentences):len(excerpt_sentences) + 3]
            additional_sentences = [s for s in remaining_sentences if len(s.strip()) > 15]
            excerpt += '. ' + '. '.join(additional_sentences)
            excerpt = excerpt.strip()

        # Clean up and ensure it ends properly
        excerpt = re.sub(r'\s+', ' ', excerpt).strip()
        if not excerpt.endswith('.'):
            excerpt += '.'

        return excerpt if excerpt else f"{original_title}. Latest news update."
