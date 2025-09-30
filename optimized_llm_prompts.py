#!/usr/bin/env python3
"""
Optimized LLM Prompts for News Article Processing
Based on 2024 research on prompt engineering for content extraction
"""

from typing import Dict, Any

class OptimizedLLMPrompts:
    """Optimized prompts for different types of content extraction"""
    
    @staticmethod
    def get_identifier_extraction_prompt(content: str) -> str:
        """Optimized prompt for extracting 12 key identifiers"""
        return f"""You are a news analysis expert. Extract exactly 12 key identifiers from this article.

Instructions:
- Focus on: people, organizations, locations, events, topics, concepts
- Use specific names and terms, not generic words
- Prioritize: proper nouns, key topics, important entities
- Format: Return ONLY a JSON array of 12 strings

Article Content:
{content}

JSON Array:"""

    @staticmethod
    def get_fallback_prompt(content: str) -> str:
        """Simpler prompt for difficult content"""
        return f"""Extract 12 key terms from this news article. Return as JSON array.

Focus on: names, places, topics, events.

Content:
{content}

JSON:"""

    @staticmethod
    def get_structured_prompt(content: str) -> str:
        """Highly structured prompt for better compliance"""
        return f"""Task: Extract 12 key identifiers from news article.

Rules:
1. Return ONLY JSON array format
2. Use specific terms, not generic words
3. Include: people, places, organizations, topics
4. Each identifier should be 1-3 words

Article:
{content}

Required format: ["identifier1", "identifier2", "identifier3", "identifier4", "identifier5", "identifier6", "identifier7", "identifier8", "identifier9", "identifier10", "identifier11", "identifier12"]

Output:"""

    @staticmethod
    def get_news_specific_prompt(content: str) -> str:
        """News-specific prompt focusing on journalism elements"""
        return f"""As a news editor, identify the 12 most important elements of this story.

Extract:
- Key people mentioned
- Important locations
- Organizations involved
- Main topics/themes
- Significant events

Article:
{content}

Return as JSON array of 12 strings:"""

    @staticmethod
    def get_emergency_prompt(content: str) -> str:
        """Ultra-simple prompt for problematic content"""
        return f"""List 12 important words from this text:

{content}

Format: ["word1", "word2", "word3", "word4", "word5", "word6", "word7", "word8", "word9", "word10", "word11", "word12"]"""

# Prompt selection strategy
def select_optimal_prompt(content: str, attempt: int = 1) -> str:
    """Select the best prompt based on content and attempt number"""
    
    if attempt == 1:
        return OptimizedLLMPrompts.get_identifier_extraction_prompt(content)
    elif attempt == 2:
        return OptimizedLLMPrompts.get_structured_prompt(content)
    elif attempt == 3:
        return OptimizedLLMPrompts.get_news_specific_prompt(content)
    else:
        return OptimizedLLMPrompts.get_emergency_prompt(content)

# Content quality assessment
def assess_content_quality(content: str) -> Dict[str, Any]:
    """Assess content quality for optimal prompt selection"""
    
    quality_score = 0
    issues = []
    
    # Length check
    if len(content) < 100:
        issues.append("Content too short")
        quality_score -= 2
    elif len(content) > 3000:
        issues.append("Content too long")
        quality_score -= 1
    
    # Content structure check
    if not any(word in content.lower() for word in ['news', 'article', 'story', 'report']):
        issues.append("No news indicators")
        quality_score -= 1
    
    # Proper noun check
    proper_nouns = len([word for word in content.split() if word[0].isupper()])
    if proper_nouns < 5:
        issues.append("Few proper nouns")
        quality_score -= 1
    
    # HTML remnants check
    if '<' in content and '>' in content:
        issues.append("HTML remnants")
        quality_score -= 2
    
    return {
        'score': quality_score,
        'issues': issues,
        'recommended_prompt': 'structured' if quality_score < 0 else 'standard'
    }
