#!/usr/bin/env python3
"""
Test the improved excerpt generator
"""

from improved_excerpt_generator import ImprovedExcerptGenerator

def test_improved_excerpt():
    print("🧪 Testing improved excerpt generator...")
    
    gen = ImprovedExcerptGenerator()
    result = gen.generate_neutral_excerpt("https://www.theguardian.com/australia-news/2025/sep/30/senior-liberal-party-women-maria-kovacic-warn-will-alienate-more-voters-abandons-net-zero")
    
    print(f"Success: {result.get('success', False)}")
    print(f"Word Count: {result.get('word_count', 0)}")
    print(f"Quality Score: {result.get('quality_score', 0)}")
    print(f"Excerpt: {result.get('neutral_excerpt', 'No excerpt')}")
    
    if result.get('success'):
        print("✅ Improved excerpt generation working!")
    else:
        print(f"❌ Error: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    test_improved_excerpt()
