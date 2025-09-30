#!/usr/bin/env python3
"""
Debug the advanced excerpt generator
"""

from advanced_excerpt_generator import AdvancedExcerptGenerator
import logging

logging.basicConfig(level=logging.INFO)

def debug_advanced_excerpt():
    print("🔍 Debugging advanced excerpt generator...")
    
    gen = AdvancedExcerptGenerator()
    
    # Test content extraction
    print("Step 1: Fetching content...")
    content = gen._fetch_article_content("https://www.theguardian.com/australia-news/2025/sep/30/senior-liberal-party-women-maria-kovacic-warn-will-alienate-more-voters-abandons-net-zero")
    print(f"Content length: {len(content) if content else 0}")
    
    if content:
        print("Step 2: Cleaning content...")
        cleaned = gen._clean_web_content(content)
        print(f"Cleaned content length: {len(cleaned)}")
        print(f"Cleaned content preview: {cleaned[:200]}...")
        
        print("Step 3: Extracting info...")
        info = gen._extract_article_info_advanced(cleaned)
        print(f"Extracted info: {info}")
        
        print("Step 4: Generating excerpt...")
        excerpt = gen._generate_excerpt_with_advanced_processing(cleaned, info.get('original_title', 'Test'))
        print(f"Generated excerpt: {excerpt}")
        
        print("Step 5: Post-processing...")
        final = gen._post_process_summary(excerpt)
        print(f"Final excerpt: {final}")

if __name__ == "__main__":
    debug_advanced_excerpt()
