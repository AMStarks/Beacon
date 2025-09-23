#!/usr/bin/env python3
"""
Simple text summarizer without requiring large model downloads
"""

import re
from typing import List, Dict, Any

class SimpleSummarizer:
    """Simple rule-based summarizer for news articles"""
    
    def __init__(self):
        self.stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that', 'these', 'those'
        }
    
    def summarize_topic(self, topic: Dict[str, Any]) -> str:
        """Generate a simple summary for a topic"""
        try:
            # Get all article titles and content
            articles = topic.get('articles', [])
            if not articles:
                return "No articles available for summary."
            
            # Extract key information
            titles = [getattr(article, 'title', '') for article in articles]
            sources = [getattr(article, 'source', '') for article in articles]
            
            # Create summary based on titles and sources
            source_count = len(set(sources))
            main_sources = list(set(sources))[:3]  # Top 3 sources
            
            # Extract key topics from titles
            key_topics = self._extract_key_topics(titles)
            
            # Generate summary
            summary_parts = []
            
            if key_topics:
                summary_parts.append(f"This topic covers {', '.join(key_topics[:3])}.")
            
            if source_count > 1:
                summary_parts.append(f"Coverage from {source_count} sources including {', '.join(main_sources)}.")
            else:
                summary_parts.append(f"Reported by {sources[0]}.")
            
            # Add context based on topic type
            topic_title = topic.get('title', '').lower()
            if any(word in topic_title for word in ['breaking', 'urgent', 'emergency']):
                summary_parts.append("This appears to be breaking news requiring immediate attention.")
            elif any(word in topic_title for word in ['update', 'latest', 'new']):
                summary_parts.append("This represents the latest developments in an ongoing story.")
            
            return " ".join(summary_parts)
            
        except Exception as e:
            return f"Error generating summary: {str(e)}"
    
    def _extract_key_topics(self, titles: List[str]) -> List[str]:
        """Extract key topics from article titles"""
        all_words = []
        for title in titles:
            words = re.findall(r'\b[a-zA-Z]{4,}\b', title.lower())
            all_words.extend(words)
        
        # Count word frequency
        word_count = {}
        for word in all_words:
            if word not in self.stop_words and len(word) > 3:
                word_count[word] = word_count.get(word, 0) + 1
        
        # Return most frequent words
        sorted_words = sorted(word_count.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_words[:5] if count > 1]

def test_simple_summarizer():
    """Test the simple summarizer"""
    print("🧪 Testing Simple Summarizer")
    print("=" * 40)
    
    # Mock topic data
    class MockArticle:
        def __init__(self, title, source):
            self.title = title
            self.source = source
    
    mock_topic = {
        'title': 'Breaking: Major Tech Company Announces AI Breakthrough',
        'articles': [
            MockArticle('Tech Giant Unveils Revolutionary AI System', 'TechCrunch'),
            MockArticle('AI Breakthrough Could Transform Healthcare', 'Wired'),
            MockArticle('New AI Technology Promises Medical Advances', 'MIT News')
        ]
    }
    
    summarizer = SimpleSummarizer()
    summary = summarizer.summarize_topic(mock_topic)
    
    print(f"📝 Topic: {mock_topic['title']}")
    print(f"📊 Articles: {len(mock_topic['articles'])}")
    print(f"🤖 Summary: {summary}")
    
    return True

if __name__ == "__main__":
    test_simple_summarizer()
