#!/usr/bin/env python3
"""
Test synchronous generators
"""

from sync_title_generator import SyncNeutralTitleGenerator
from sync_excerpt_generator import SyncNeutralExcerptGenerator

def test_generators():
    """Test the synchronous generators"""
    print("🧪 Testing synchronous generators...")
    
    # Test title generator
    title_gen = SyncNeutralTitleGenerator()
    title_result = title_gen.generate_neutral_title("https://www.bbc.com/news/articles/cj4y159190go")
    
    print(f"Title Generator Success: {title_result.get('success')}")
    print(f"Title: {title_result.get('neutral_title', 'FAILED')}")
    
    # Test excerpt generator
    excerpt_gen = SyncNeutralExcerptGenerator()
    excerpt_result = excerpt_gen.generate_neutral_excerpt("https://www.bbc.com/news/articles/cj4y159190go")
    
    print(f"Excerpt Generator Success: {excerpt_result.get('success')}")
    print(f"Excerpt: {excerpt_result.get('neutral_excerpt', 'FAILED')[:100]}...")

if __name__ == "__main__":
    test_generators()
