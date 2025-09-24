"""
Enhanced Title Generator
Uses improved prompts, post-processing, and context optimization for concise titles
"""

import re
import asyncio
import torch
from typing import List, Dict, Any
from local_llm_service import local_llm

class EnhancedTitleGenerator:
    """Generates concise, clean titles using improved LLM prompts and post-processing"""
    
    def __init__(self):
        self.title_templates = [
            "{subject} {action} {object}",
            "{subject} vs {object}",
            "{subject} breaks {object}",
            "{subject} {action}",
            "{action} {object}"
        ]
    
    def _extract_keywords(self, articles_text: str) -> List[str]:
        """Extract key words from articles for better context"""
        # Remove common stop words and extract meaningful terms
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
            'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 
            'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 
            'may', 'might', 'can', 'must', 'shall', 'this', 'that', 'these', 'those'
        }
        
        # Extract words longer than 3 characters, not stop words
        words = re.findall(r'\b[a-zA-Z]{4,}\b', articles_text.lower())
        keywords = [word for word in words if word not in stop_words]
        
        # Count frequency and return top keywords
        word_freq = {}
        for word in keywords:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Return top 10 most frequent keywords
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, freq in sorted_words[:10]]
    
    def _create_optimized_prompt(self, articles_text: str) -> str:
        """Create an optimized prompt with key context only"""
        # Extract key information
        keywords = self._extract_keywords(articles_text)
        key_context = " ".join(keywords[:5])  # Use top 5 keywords only
        
        # Create focused prompt
        prompt = f"""Create a descriptive news headline (6-12 words) for these key topics: {key_context}

Rules:
1. Use 6-12 words for clarity
2. Focus on the main subject and action
3. Use proper title case
4. Be specific and descriptive
5. No dates, times, or source names
6. No "Keywords:" or other artifacts

Examples of good headlines:
- "Trump Wins Presidential Election"
- "Hurricane Devastates Florida Coast" 
- "Supreme Court Rules on Abortion"
- "Stock Market Crashes Amid Recession"

Headline:"""
        
        return prompt
    
    def _post_process_title(self, title: str) -> str:
        """Clean and format the title using post-processing rules"""
        if not title:
            return "News Update"
        
        # Remove common artifacts
        title = re.sub(r'Keywords?:.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'Date:.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'Time:.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'Published:.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'Source:.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'active\s+', '', title, flags=re.IGNORECASE)
        title = re.sub(r'BBC News.*', '', title, flags=re.IGNORECASE)
        title = re.sub(r'Associated Press.*', '', title, flags=re.IGNORECASE)
        
        # Remove extra whitespace and newlines
        title = re.sub(r'\s+', ' ', title)
        title = title.strip()
        
        # Apply proper title case rules
        title = self._apply_title_case(title)
        
        # Enforce length limit
        if len(title) > 80:
            title = title[:77] + '...'
        
        # Ensure minimum meaningful length
        if len(title) < 15:
            title = "Breaking News Update"
        
        return title
    
    def _apply_title_case(self, title: str) -> str:
        """Apply proper title case rules"""
        # Words to keep lowercase
        lowercase_words = {
            'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'if', 'in', 'nor', 
            'of', 'on', 'or', 'per', 'so', 'the', 'to', 'up', 'via', 'vs', 'with'
        }
        
        # Words to always capitalize
        uppercase_words = {
            'us', 'uk', 'eu', 'nato', 'fbi', 'cia', 'nsa', 'ai', 'tv', 'ceo', 
            'covid', 'trump', 'biden', 'putin', 'zelensky'
        }
        
        words = title.split()
        result = []
        
        for i, word in enumerate(words):
            # Clean the word
            clean_word = re.sub(r'[^\w]', '', word.lower())
            
            # First word is always capitalized
            if i == 0:
                result.append(word.capitalize())
            # Always uppercase words
            elif clean_word in uppercase_words:
                result.append(word.upper())
            # Lowercase words
            elif clean_word in lowercase_words:
                result.append(word.lower())
            # Everything else gets capitalized
            else:
                result.append(word.capitalize())
        
        return ' '.join(result)
    
    async def generate_title(self, articles_text: str) -> str:
        """Generate a concise, clean title using enhanced methods with timeout protection"""
        try:
            # Add timeout protection to prevent freezing
            title = await asyncio.wait_for(
                self._generate_title_with_timeout(articles_text),
                timeout=30.0  # 30 second timeout
            )
            return title
            
        except asyncio.TimeoutError:
            print("⏰ Title generation timed out, using fallback")
            return self._generate_fallback_title(articles_text)
        except Exception as e:
            print(f"❌ Error generating title: {e}")
            return self._generate_fallback_title(articles_text)
    
    async def _generate_title_with_timeout(self, articles_text: str) -> str:
        """Generate title with internal timeout protection"""
        # Create optimized prompt with limited context
        prompt = self._create_optimized_prompt(articles_text)
        
        # Get LLM response with timeout
        if not local_llm.is_loaded:
            await asyncio.wait_for(local_llm.load_model(), timeout=10.0)
        
        inputs = local_llm.tokenizer.encode(prompt, return_tensors='pt')
        
        with torch.no_grad():
            outputs = local_llm.model.generate(
                inputs,
                max_length=inputs.shape[1] + 25,  # Allow for longer titles
                num_return_sequences=1,
                temperature=0.7,  # Higher temperature for more creative output
                do_sample=True,
                pad_token_id=local_llm.tokenizer.eos_token_id
            )
        
        response = local_llm.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract title from response
        if 'Headline:' in response:
            title = response.split('Headline:')[-1].strip()
        else:
            title = response[len(prompt):].strip()
        
        # Post-process the title
        clean_title = self._post_process_title(title)
        
        return clean_title
    
    def _generate_fallback_title(self, articles_text: str) -> str:
        """Generate a fallback title when LLM fails"""
        # Extract key words for a better fallback
        keywords = self._extract_keywords(articles_text)
        
        if keywords:
            # Create a descriptive fallback using keywords
            key_words = keywords[:3]  # Use top 3 keywords
            fallback = " ".join(key_words).title()
            
            # Ensure it's not too long
            if len(fallback) > 50:
                fallback = fallback[:47] + "..."
            
            # Ensure it's not too short
            if len(fallback) < 10:
                fallback = f"{fallback} News Update"
            
            return fallback
        
        return "Breaking News Update"
    
    async def generate_summary(self, articles_text: str) -> str:
        """Generate a clean summary using enhanced methods with timeout protection"""
        try:
            # Add timeout protection to prevent freezing
            summary = await asyncio.wait_for(
                self._generate_summary_with_timeout(articles_text),
                timeout=30.0  # 30 second timeout
            )
            return summary
            
        except asyncio.TimeoutError:
            print("⏰ Summary generation timed out, using fallback")
            return self._generate_fallback_summary(articles_text)
        except Exception as e:
            print(f"❌ Error generating summary: {e}")
            return self._generate_fallback_summary(articles_text)
    
    async def _generate_summary_with_timeout(self, articles_text: str) -> str:
        """Generate summary with internal timeout protection"""
        # Create focused summary prompt
        keywords = self._extract_keywords(articles_text)
        key_context = " ".join(keywords[:8])  # Use top 8 keywords
        
        prompt = f"""Write a brief, neutral summary (1-2 sentences) of these news topics: {key_context}

Rules:
1. Be factual and neutral
2. Focus on key developments
3. No opinion or speculation
4. 1-2 sentences only

Summary:"""
        
        if not local_llm.is_loaded:
            await asyncio.wait_for(local_llm.load_model(), timeout=10.0)
        
        inputs = local_llm.tokenizer.encode(prompt, return_tensors='pt')
        
        with torch.no_grad():
            outputs = local_llm.model.generate(
                inputs,
                max_length=inputs.shape[1] + 50,
                num_return_sequences=1,
                temperature=0.5,
                do_sample=True,
                pad_token_id=local_llm.tokenizer.eos_token_id
            )
        
        response = local_llm.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract summary
        if 'Summary:' in response:
            summary = response.split('Summary:')[-1].strip()
        else:
            summary = response[len(prompt):].strip()
        
        # Clean up summary
        summary = re.sub(r'\s+', ' ', summary)
        summary = summary.strip()
        
        if len(summary) < 20:
            summary = "News coverage of current events."
        
        return summary[:200]  # Limit to 200 characters
    
    def _generate_fallback_summary(self, articles_text: str) -> str:
        """Generate a fallback summary when LLM fails"""
        # Extract key words for a better fallback
        keywords = self._extract_keywords(articles_text)
        
        if keywords and len(keywords) >= 2:
            # Create a simple summary using keywords
            key_words = keywords[:4]  # Use top 4 keywords
            fallback = f"Coverage of {', '.join(key_words[:2])} and related developments."
            return fallback[:200]
        
        return "News coverage of current events."

# Global instance
enhanced_title_generator = EnhancedTitleGenerator()
