"""
Debug Enhanced Title Generator
Fixes title generation to avoid defaulting to "Breaking News"
"""

import re
import asyncio
from typing import List, Dict, Any
from local_llm_service import local_llm

class EnhancedTitleGenerator:
    """Generates concise, clean titles with better fallback logic"""
    
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
        prompt = f"""Create a concise news headline (3-6 words max) for these key topics: {key_context}

Rules:
1. Use only 3-6 words
2. Focus on the main subject and action
3. Use proper title case
4. Be specific and clear
5. No dates, times, or source names
6. No "Keywords:" or other artifacts

Examples of good headlines:
- "Trump Wins Election"
- "Hurricane Hits Florida" 
- "Supreme Court Rules"
- "Market Crashes"

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
        if len(title) > 50:
            title = title[:47] + '...'
        
        # Ensure minimum meaningful length
        if len(title) < 10:
            title = "News Update"
        
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
    
    def _extract_fallback_title(self, articles_text: str) -> str:
        """Extract a fallback title from article text when LLM fails"""
        keywords = self._extract_keywords(articles_text)
        
        if not keywords:
            return "News Update"
        
        # Try to create a meaningful title from keywords
        if len(keywords) >= 2:
            # Use first two keywords
            title = f"{keywords[0].capitalize()} {keywords[1].capitalize()}"
        else:
            # Use first keyword with generic action
            title = f"{keywords[0].capitalize()} Update"
        
        return self._post_process_title(title)
    
    async def generate_title(self, articles_text: str) -> str:
        """Generate a concise, clean title using enhanced methods"""
        try:
            # Create optimized prompt with limited context
            prompt = self._create_optimized_prompt(articles_text)
            
            # Get LLM response
            if not local_llm.is_loaded:
                await local_llm.load_model()
            
            inputs = local_llm.tokenizer.encode(prompt, return_tensors='pt')
            
            with local_llm.model.no_grad():
                outputs = local_llm.model.generate(
                    inputs,
                    max_length=inputs.shape[1] + 10,  # Very short generation
                    num_return_sequences=1,
                    temperature=0.3,  # Lower temperature for more focused output
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
            
            # If title is too generic, try fallback
            if clean_title in ["Breaking News", "News Update", "News"]:
                fallback_title = self._extract_fallback_title(articles_text)
                if fallback_title not in ["Breaking News", "News Update", "News"]:
                    clean_title = fallback_title
            
            return clean_title
            
        except Exception as e:
            print(f"❌ Error generating title: {e}")
            # Use fallback extraction
            return self._extract_fallback_title(articles_text)
    
    async def generate_summary(self, articles_text: str) -> str:
        """Generate a clean summary using enhanced methods"""
        try:
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
                await local_llm.load_model()
            
            inputs = local_llm.tokenizer.encode(prompt, return_tensors='pt')
            
            with local_llm.model.no_grad():
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
            
        except Exception as e:
            print(f"❌ Error generating summary: {e}")
            return "News coverage of current events."

# Global instance
enhanced_title_generator = EnhancedTitleGenerator()
