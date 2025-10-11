#!/usr/bin/env python3
"""
Beacon 3 LLM Service - Gemma primary, Llama secondary
"""

import asyncio
import aiohttp
import logging
import json
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class LLMService:
    """LLM service with Gemma primary, Llama secondary"""

    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url.rstrip('/')
        self.primary_model = "gemma:2b"
        self.secondary_model = "llama3.1:8b"
        self.timeout = aiohttp.ClientTimeout(total=90)  # Increased timeout for Llama
        self.max_retries = 3  # Increased retries

    async def generate_title(self, content: str, original_title: str = "") -> str:
        """Generate neutral title using LLM"""
        logger.info(f"🎯 Generating title for content length: {len(content)}")
        
        # Try primary model (Gemma)
        logger.debug(f"🤖 Trying primary model: {self.primary_model}")
        title = await self._call_llm_title(content, original_title, self.primary_model)
        
        if title and self._is_valid_title(title):
            title_score = self._score_title_quality(title, content)
            logger.info(f"✅ Primary model generated valid title (score: {title_score:.2f}): {title[:50]}...")
            if title_score >= 0.2:  # More inclusive threshold
                logger.info(f"🎯 Primary model title accepted (score: {title_score:.2f} >= 0.2)")
                return title
            else:
                logger.warning(f"⚠️ Primary model title score too low ({title_score:.2f} < 0.2), trying secondary model")
        
        # Try secondary model (Llama)
        logger.debug(f"🤖 Trying secondary model: {self.secondary_model}")
        title = await self._call_llm_title(content, original_title, self.secondary_model)
        
        if title and self._is_valid_title(title):
            title_score = self._score_title_quality(title, content)
            logger.info(f"✅ Secondary model generated valid title (score: {title_score:.2f}): {title[:50]}...")
            if title_score >= 0.15:  # Even more inclusive threshold
                logger.info(f"🎯 Secondary model title accepted (score: {title_score:.2f} >= 0.15)")
                return title
            else:
                logger.warning(f"⚠️ Secondary model title score too low ({title_score:.2f} < 0.15)")
        
        # Fallback logic: If both models generated titles but scored low, accept the better one
        logger.warning(f"🔄 FALLBACK: Both models failed thresholds, checking for borderline acceptance...")
        
        # Try to get the best title from both attempts
        primary_title = await self._call_llm_title(content, original_title, self.primary_model)
        secondary_title = await self._call_llm_title(content, original_title, self.secondary_model)
        
        best_title = None
        best_score = 0.0
        
        if primary_title and self._is_valid_title(primary_title):
            primary_score = self._score_title_quality(primary_title, content)
            logger.debug(f"🔄 FALLBACK: Primary title score: {primary_score:.2f}")
            if primary_score > best_score:
                best_title = primary_title
                best_score = primary_score
        
        if secondary_title and self._is_valid_title(secondary_title):
            secondary_score = self._score_title_quality(secondary_title, content)
            logger.debug(f"🔄 FALLBACK: Secondary title score: {secondary_score:.2f}")
            if secondary_score > best_score:
                best_title = secondary_title
                best_score = secondary_score
        
        if best_title and best_score >= 0.1:  # Very low threshold for fallback
            logger.warning(f"🔄 FALLBACK: Accepting borderline title (score: {best_score:.2f}): {best_title[:50]}...")
            return best_title
        
        # Final fallback: Use original title or generate a simple fallback
        logger.warning(f"🔄 Using fallback title generation")
        fallback_title = self._generate_fallback_title(original_title, content)
        if fallback_title:
            logger.info(f"✅ Fallback title generated: {fallback_title}")
            return fallback_title

        # If all else fails, raise exception
        logger.error(f"❌ All title generation attempts failed - no acceptable titles found")
        raise Exception("LLM title generation failed")

    async def generate_excerpt(self, content: str, original_title: str = "") -> str:
        """Generate neutral excerpt using LLM"""
        logger.info(f"🎯 Generating excerpt for content length: {len(content)}")
        
        # Try primary model (Gemma)
        logger.debug(f"🤖 Trying primary model: {self.primary_model}")
        excerpt = await self._call_llm_excerpt(content, original_title, self.primary_model)
        
        if excerpt and self._is_valid_excerpt(excerpt):
            logger.info(f"✅ Primary model generated valid excerpt: {excerpt[:50]}...")
            return excerpt
        
        # Try secondary model (Llama)
        logger.debug(f"🤖 Trying secondary model: {self.secondary_model}")
        excerpt = await self._call_llm_excerpt(content, original_title, self.secondary_model)
        
        if excerpt and self._is_valid_excerpt(excerpt):
            logger.info(f"✅ Secondary model generated valid excerpt: {excerpt[:50]}...")
            return excerpt
        
        # Final fallback: Generate excerpt from content
        logger.warning(f"🔄 Using fallback excerpt generation")
        fallback_excerpt = self._generate_fallback_excerpt(content)
        if fallback_excerpt:
            logger.info(f"✅ Fallback excerpt generated: {fallback_excerpt[:50]}...")
            return fallback_excerpt

        # If all else fails, raise exception
        logger.error(f"❌ Both LLM models failed to generate valid excerpt")
        raise Exception("LLM excerpt generation failed")

    def _generate_fallback_title(self, original_title: str, content: str) -> str:
        """Generate a fallback title when LLM fails"""
        if original_title and len(original_title.strip()) > 10:
            # Use original title if it's reasonable length
            return original_title.strip()

        # Extract first meaningful sentence from content as fallback
        sentences = content.split('.')
        for sentence in sentences[:5]:  # Check first 5 sentences
            sentence = sentence.strip()
            if len(sentence) > 20 and len(sentence) < 100:
                return sentence + '.'

        # Ultimate fallback
        return "News Article"

    def _generate_fallback_excerpt(self, content: str) -> str:
        """Generate a fallback excerpt when LLM fails"""
        if not content:
            return "Content not available."

        # Extract first paragraph or meaningful sentences
        paragraphs = content.split('\n\n')
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if len(paragraph) > 100 and len(paragraph) < 300:
                return paragraph[:250] + '...' if len(paragraph) > 250 else paragraph

        # Fallback to first few sentences
        sentences = content.split('.')
        meaningful_sentences = [s.strip() for s in sentences[:3] if len(s.strip()) > 20]
        if meaningful_sentences:
            return '. '.join(meaningful_sentences) + '.'

        return "Article summary not available."

    async def _call_llm_title(self, content: str, original_title: str, model: str) -> Optional[str]:
        """Call LLM for title generation with enhanced prompt for key events"""
        # Extract key topics and events from content
        key_topics = self._extract_key_topics(content)
        location = self._extract_location(content)
        event_type = self._extract_event_type(content)
        
        prompt = f"""You are a professional news editor. Create a neutral, factual headline that captures the key event without sensationalism or bias.

Original Title: {original_title}
Content: {content[:2000]}

Key Topics Identified: {', '.join(key_topics)}
Location: {location}
Event Type: {event_type}

Requirements:
- Write a specific, descriptive headline (35-80 characters)
- PRIORITIZE key events, locations, and specific terms
- Use strong, specific nouns (shooting, attack, explosion, etc.)
- Include location when relevant (Michigan, New York, etc.)
- Use action verbs (killed, injured, arrested, etc.)
- Avoid generic words like "Update", "News", "Breaking"
- Be completely neutral and factual - no sensationalism
- Avoid politically charged language
- Focus on the most important event details
- Do not use dramatic words like "Dark Turn", "Attack", "Crisis" unless they are direct quotes

Examples of good headlines:
- "Michigan Church Shooting Leaves 4 Dead"
- "Explosion at New York Building Kills 3"
- "Police Arrest Suspect in Bank Robbery"

Return only the headline:"""

        logger.debug(f"📝 Calling {model} for title generation")
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"🔄 {model} title attempt {attempt + 1}/{self.max_retries}")
                start_time = asyncio.get_event_loop().time()
                
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(
                        f"{self.ollama_url}/api/chat",
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "stream": False,
                            "options": {"temperature": 0.0, "max_tokens": 100}
                        }
                    ) as response:
                        duration = asyncio.get_event_loop().time() - start_time
                        logger.debug(f"⏱️ {model} response time: {duration:.2f}s")
                        
                        if response.status == 200:
                            result = await response.json()
                            title = result.get('message', {}).get('content', '').strip()
                            cleaned_title = self._clean_llm_output(title)
                            logger.debug(f"📊 {model} title response: {cleaned_title[:50]}...")
                            return cleaned_title
                        else:
                            logger.warning(f"⚠️ {model} title attempt {attempt + 1} failed: HTTP {response.status}")
            except asyncio.TimeoutError:
                duration = asyncio.get_event_loop().time() - start_time
                logger.error(f"⏰ {model} title attempt {attempt + 1} TIMEOUT after {duration:.2f}s")
            except Exception as e:
                logger.error(f"❌ OLLAMA CRASH: {model} title attempt {attempt + 1} failed: {e}")
                logger.error(f"❌ OLLAMA CONNECTION ERROR: {e}")
                if attempt < self.max_retries - 1:
                    backoff_time = 2 ** attempt
                    logger.debug(f"⏳ Retrying in {backoff_time}s...")
                    await asyncio.sleep(backoff_time)  # Exponential backoff
        
        logger.error(f"❌ {model} title generation failed after {self.max_retries} attempts")
        return None

    async def _call_llm_excerpt(self, content: str, original_title: str, model: str) -> Optional[str]:
        """Call LLM for excerpt generation"""
        prompt = f"""Analyze this news article and create a completely neutral, factual summary without any political bias or sensationalism.

Article Title: {original_title}
Article Content: {content[:3000]}

Requirements:
- Write a neutral, factual summary (100-150 words)
- Focus ONLY on key facts and events
- Avoid ALL opinion, bias, or sensationalism
- Use completely objective, neutral language
- Include who, what, when, where, why in a factual manner
- Be comprehensive but concise
- Do not use politically charged words or dramatic language
- Present information factually without judgment

Return only the summary:"""

        logger.debug(f"📝 Calling {model} for excerpt generation")
        
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.post(
                        f"{self.ollama_url}/api/chat",
                        json={
                            "model": model,
                            "messages": [{"role": "user", "content": prompt}],
                            "stream": False,
                            "options": {"temperature": 0.05, "max_tokens": 300}
                        }
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            excerpt = result.get('message', {}).get('content', '').strip()
                            cleaned_excerpt = self._clean_llm_output(excerpt)
                            logger.debug(f"📊 {model} excerpt response: {cleaned_excerpt[:50]}...")
                            return cleaned_excerpt
                        else:
                            logger.warning(f"⚠️ {model} excerpt attempt {attempt + 1} failed: HTTP {response.status}")
            except Exception as e:
                logger.error(f"❌ OLLAMA CRASH: {model} excerpt attempt {attempt + 1} failed: {e}")
                logger.error(f"❌ OLLAMA CONNECTION ERROR: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
        
        logger.error(f"❌ {model} excerpt generation failed after {self.max_retries} attempts")
        return None

    def _clean_llm_output(self, text: str) -> str:
        """Clean LLM output"""
        if not text:
            return ""
        
        # Remove fenced code blocks and inline code markers
        text = re.sub(r"```[\s\S]*?```", " ", text)
        text = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", text)

        # Remove common prefixes (more comprehensive)
        prefixes = [
            r'^Sure, here is the headline you requested:\s*',
            r'^Sure, here\'s the headline you requested:\s*',
            r'^Sure, here is the summary you requested:\s*',
            r'^Sure, here\'s the summary you requested:\s*',
            r'^Sure, here is the headline:\s*',
            r'^Sure, here\'s the headline:\s*',
            r'^Sure, here is the summary:\s*',
            r'^Sure, here\'s the summary:\s*',
            r'^Here is the headline:\s*',
            r'^Here\'s the headline:\s*',
            r'^Here is the summary:\s*',
            r'^Here\'s the summary:\s*',
            r'^The headline is:\s*',
            r'^The summary is:\s*',
            r'^Headline:\s*',
            r'^Title:\s*',
            r'^Summary:\s*',
            r'^Excerpt:\s*',
            r'^\*\*',
            r'^\*',
        ]
        
        for prefix in prefixes:
            text = re.sub(prefix, '', text, flags=re.IGNORECASE)
        
        # Remove common suffixes
        suffixes = [
            r'\*\*$',
            r'\*$',
        ]
        
        for suffix in suffixes:
            text = re.sub(suffix, '', text)
        
        # Remove quotes if they wrap the entire text
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]

        # Strip leading markdown header markers like '#', '##', '###'
        text = re.sub(r'^\s*#{1,6}\s*', '', text)

        # Remove simple HTML tags that sometimes leak (e.g., </em>)
        text = re.sub(r'<[^>]+>', '', text)
        
        # Strip common CSS/JS artifacts
        css_js_tokens = [
            r"\{[^}]*\}",
            r";\s*\n?",
            r"\b(font\-|color:|background:|display:|position:|margin:|padding:|border:)\b",
        ]
        for pat in css_js_tokens:
            text = re.sub(pat, ' ', text, flags=re.IGNORECASE)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def _is_valid_title(self, title: str) -> bool:
        """Check if LLM-generated title is valid"""
        if not title or len(title) < 10 or len(title) > 100:
            logger.debug(f"⚠️ Title length invalid: {len(title)}")
            return False
        
        # Check for refusal patterns
        refusal_words = ['cannot', 'unable', 'inappropriate', 'sorry']
        if any(word in title.lower() for word in refusal_words):
            logger.debug(f"⚠️ Title contains refusal words")
            return False
        
        logger.debug(f"✅ Title validation passed")
        return True

    def _is_valid_excerpt(self, excerpt: str) -> bool:
        """Check if LLM-generated excerpt is valid"""
        if not excerpt or len(excerpt) < 50 or len(excerpt) > 1000:  # Increased limit from 500 to 1000
            logger.debug(f"⚠️ Excerpt length invalid: {len(excerpt)}")
            return False
        
        # Check for refusal patterns
        refusal_words = ['cannot', 'unable', 'inappropriate', 'sorry']
        if any(word in excerpt.lower() for word in refusal_words):
            logger.debug(f"⚠️ Excerpt contains refusal words")
            return False
        
        # Reject code/CSS indicators or meta explanations
        banned_patterns = [
            r"```",
            r"\bstylesheet\b",
            r"\bcss\b",
            r"\bcode block\b",
            r"^\s*var\s+\w+\s*=",
            r"\bfunction\s+\w+\s*\(",
            r"\{\s*\w+\s*:\s*\w+\s*;",
            r"font\-family\s*:|color\s*:|background\s*:|display\s*:|position\s*:|margin\s*:|padding\s*:|border\s*:",
            r"^\s*@media\s",
        ]
        for pat in banned_patterns:
            if re.search(pat, excerpt, flags=re.IGNORECASE|re.MULTILINE):
                logger.debug(f"⚠️ Excerpt rejected due to banned pattern: {pat}")
                return False
        
        logger.debug(f"✅ Excerpt validation passed")
        return True

    def _extract_key_topics(self, content: str) -> list:
        """Extract key topics and events from content"""
        import re
        
        # Key event patterns
        event_patterns = [
            r'(shooting|attack|explosion|fire|crash|accident|murder|killing)',
            r'(arrest|charged|convicted|sentenced)',
            r'(election|vote|campaign|debate)',
            r'(storm|flood|earthquake|disaster)',
            r'(protest|demonstration|riot)',
            r'(strike|lockout|layoff)',
            r'(merger|acquisition|bankruptcy)'
        ]
        
        topics = []
        for pattern in event_patterns:
            matches = re.findall(pattern, content.lower())
            topics.extend(matches)
        
        return list(set(topics))[:5]  # Top 5 unique topics

    def _extract_location(self, content: str) -> str:
        """Extract location from content"""
        import re
        
        # Common location patterns
        location_patterns = [
            r'([A-Z][a-z]+ (?:City|County|State))',
            r'([A-Z][a-z]+(?:, [A-Z]{2})?)',
            r'(New York|Los Angeles|Chicago|Houston|Phoenix|Philadelphia|San Antonio|San Diego|Dallas|San Jose)',
            r'(Michigan|California|Texas|Florida|New York|Pennsylvania|Illinois|Ohio|Georgia|North Carolina)'
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
        
        return "Unknown"

    def _extract_event_type(self, content: str) -> str:
        """Extract event type from content"""
        import re
        
        event_types = {
            'crime': r'(shooting|murder|robbery|theft|assault|kidnapping)',
            'disaster': r'(fire|explosion|crash|accident|storm|flood)',
            'politics': r'(election|vote|campaign|debate|protest)',
            'business': r'(merger|acquisition|bankruptcy|strike)',
            'sports': r'(game|match|championship|tournament)',
            'health': r'(pandemic|outbreak|disease|medical)'
        }
        
        for event_type, pattern in event_types.items():
            if re.search(pattern, content.lower()):
                return event_type
        
        return "general"

    def _score_title_quality(self, title: str, content: str) -> float:
        """Score title quality based on specificity and relevance - category-aware with debug logging"""
        logger.debug(f"🔍 SCORING DEBUG: Starting title scoring")
        logger.debug(f"🔍 SCORING DEBUG: Title: '{title}' (length: {len(title)})")
        logger.debug(f"🔍 SCORING DEBUG: Content preview: '{content[:100]}...'")
        
        score = 0.0
        
        # Length score (more inclusive range)
        length = len(title)
        logger.debug(f"🔍 SCORING DEBUG: Length analysis - {length} chars")
        if 25 <= length <= 80:  # More inclusive range
            score += 0.3
            logger.debug(f"🔍 SCORING DEBUG: Length bonus +0.3 (total: {score})")
        elif 15 <= length <= 100:  # Even more inclusive
            score += 0.2
            logger.debug(f"🔍 SCORING DEBUG: Length bonus +0.2 (total: {score})")
        else:
            logger.debug(f"🔍 SCORING DEBUG: No length bonus (total: {score})")
        
        # Category-specific terms (EXPANDED for all news types)
        category_terms = {
            'crime': ['shooting', 'attack', 'killed', 'injured', 'arrested', 'explosion', 'fire', 'crash', 'murder', 'robbery'],
            'politics': ['election', 'vote', 'campaign', 'debate', 'protest', 'government', 'parliament', 'minister', 'policy', 'legislation'],
            'technology': ['digital', 'app', 'system', 'platform', 'software', 'innovation', 'cyber', 'data', 'id', 'authentication'],
            'business': ['merger', 'acquisition', 'bankruptcy', 'strike', 'market', 'company', 'revenue', 'profit', 'economy', 'trade'],
            'health': ['pandemic', 'outbreak', 'disease', 'medical', 'health', 'treatment', 'vaccine', 'hospital', 'covid', 'virus'],
            'sports': ['game', 'match', 'championship', 'tournament', 'team', 'player', 'season', 'league', 'win', 'score'],
            'environment': ['climate', 'environment', 'pollution', 'carbon', 'green', 'sustainable', 'energy', 'renewable', 'emissions']
        }
        
        # Score based on content category with detailed logging
        logger.debug(f"🔍 SCORING DEBUG: Analyzing content categories...")
        category_found = None
        for category, terms in category_terms.items():
            content_matches = [term for term in terms if term in content.lower()]
            if content_matches:
                logger.debug(f"🔍 SCORING DEBUG: Content matches {category}: {content_matches}")
                category_found = category
                title_matches = [term for term in terms if term in title.lower()]
                logger.debug(f"🔍 SCORING DEBUG: Title matches {category}: {title_matches}")
                for term in title_matches:
                    score += 0.1
                    logger.debug(f"🔍 SCORING DEBUG: +0.1 for term '{term}' (total: {score})")
                break  # Only score the first matching category
        
        if not category_found:
            logger.debug(f"🔍 SCORING DEBUG: No content category matches found")
        
        # Location score (prefer location inclusion)
        location = self._extract_location(content)
        logger.debug(f"🔍 SCORING DEBUG: Location extracted: '{location}'")
        if location != "Unknown" and location.lower() in title.lower():
            score += 0.2
            logger.debug(f"🔍 SCORING DEBUG: Location bonus +0.2 (total: {score})")
        else:
            logger.debug(f"🔍 SCORING DEBUG: No location bonus (total: {score})")
        
        # Avoid generic terms
        generic_terms = ['update', 'news', 'breaking', 'latest', 'report']
        generic_found = [term for term in generic_terms if term in title.lower()]
        if generic_found:
            score -= 0.1 * len(generic_found)
            logger.debug(f"🔍 SCORING DEBUG: Generic penalty -{0.1 * len(generic_found)} for terms: {generic_found} (total: {score})")
        
        # Action verb score (EXPANDED)
        action_verbs = ['announces', 'launches', 'introduces', 'implements', 'develops', 'creates', 'builds', 'establishes', 'killed', 'injured', 'arrested']
        action_found = [verb for verb in action_verbs if verb in title.lower()]
        if action_found:
            score += 0.1 * len(action_found)
            logger.debug(f"🔍 SCORING DEBUG: Action verb bonus +{0.1 * len(action_found)} for verbs: {action_found} (total: {score})")
        
        final_score = min(score, 1.0)  # Cap at 1.0
        logger.debug(f"🔍 SCORING DEBUG: Final score: {final_score}")
        return final_score
