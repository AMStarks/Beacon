#!/usr/bin/env python3
"""
Similarity pre-filtering for quick keyword matching before full comparison.
Reduces computational overhead by filtering out obviously different articles.
"""

import re
from typing import Dict, List, Tuple
from collections import Counter

class SimilarityPreFilter:
    def __init__(self):
        # Key word categories for quick matching
        self.keyword_categories = {
            'violence': ['shooting', 'attack', 'violence', 'murder', 'killing', 'death', 'fatal', 'injured', 'wounded'],
            'location': ['michigan', 'california', 'texas', 'florida', 'new york', 'chicago', 'los angeles', 'detroit'],
            'entities': ['church', 'school', 'hospital', 'government', 'police', 'fbi', 'federal'],
            'events': ['fire', 'explosion', 'crash', 'accident', 'disaster', 'emergency', 'crisis'],
            'politics': ['trump', 'biden', 'election', 'campaign', 'policy', 'government', 'congress'],
            'international': ['gaza', 'israel', 'palestine', 'ukraine', 'russia', 'china', 'iran']
        }
        
        # Weight for each category
        self.category_weights = {
            'violence': 3,
            'location': 2,
            'entities': 2,
            'events': 2,
            'politics': 1,
            'international': 3
        }
    
    def extract_keywords(self, text: str) -> Dict[str, List[str]]:
        """Extract keywords from text for each category"""
        text_lower = text.lower()
        keywords = {}
        
        for category, words in self.keyword_categories.items():
            found_words = [word for word in words if word in text_lower]
            keywords[category] = found_words
        
        return keywords
    
    def calculate_quick_similarity(self, text1: str, text2: str) -> float:
        """Calculate quick similarity score based on keyword overlap"""
        keywords1 = self.extract_keywords(text1)
        keywords2 = self.extract_keywords(text2)
        
        total_score = 0.0
        total_weight = 0.0
        
        for category in self.keyword_categories.keys():
            words1 = set(keywords1.get(category, []))
            words2 = set(keywords2.get(category, []))
            
            if words1 or words2:
                # Calculate overlap
                intersection = len(words1.intersection(words2))
                union = len(words1.union(words2))
                
                if union > 0:
                    category_score = intersection / union
                    weight = self.category_weights[category]
                    
                    total_score += category_score * weight
                    total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def should_proceed_with_full_comparison(self, text1: str, text2: str, threshold: float = 0.3) -> bool:
        """Determine if articles should proceed to full similarity comparison"""
        quick_score = self.calculate_quick_similarity(text1, text2)
        return quick_score >= threshold
    
    def filter_articles(self, target_text: str, candidate_texts: List[str], threshold: float = 0.3) -> List[Tuple[int, float]]:
        """Filter candidate articles based on quick similarity"""
        filtered_candidates = []
        
        for i, candidate_text in enumerate(candidate_texts):
            quick_score = self.calculate_quick_similarity(target_text, candidate_text)
            
            if quick_score >= threshold:
                filtered_candidates.append((i, quick_score))
        
        # Sort by score (highest first)
        return sorted(filtered_candidates, key=lambda x: x[1], reverse=True)
    
    def get_keyword_summary(self, text: str) -> Dict[str, int]:
        """Get summary of keywords found in text"""
        keywords = self.extract_keywords(text)
        summary = {}
        
        for category, words in keywords.items():
            summary[category] = len(words)
        
        return summary

def main():
    """Test the pre-filtering system"""
    prefilter = SimilarityPreFilter()
    
    # Test with church shooting articles
    text1 = "Four dead after gunman opens fire in a Michigan Mormon church service before setting it on fire"
    text2 = "A gunman opened fire inside a Michigan church and set the building ablaze during a crowded Sunday service"
    text3 = "Donald Trump announces new peace plan for Middle East conflict resolution"
    
    print("Testing similarity pre-filtering...")
    
    # Test quick similarity
    score12 = prefilter.calculate_quick_similarity(text1, text2)
    score13 = prefilter.calculate_quick_similarity(text1, text3)
    
    print(f"Church shooting vs Church shooting: {score12:.3f}")
    print(f"Church shooting vs Trump peace plan: {score13:.3f}")
    
    # Test filtering
    candidates = [text2, text3]
    filtered = prefilter.filter_articles(text1, candidates, threshold=0.3)
    
    print(f"Filtered candidates: {len(filtered)} out of {len(candidates)}")
    for i, score in filtered:
        print(f"  Candidate {i}: {score:.3f}")
    
    # Test keyword extraction
    keywords = prefilter.extract_keywords(text1)
    print(f"Keywords in text1: {keywords}")

if __name__ == "__main__":
    main()
