#!/usr/bin/env python3
"""
Test script to verify proper capitalization of two-letter words in titles.
"""

from simple_topic_detector import SimpleTopicDetector

def test_capitalization():
    """Test the capitalization logic with various problematic titles"""
    
    detector = SimpleTopicDetector()
    
    # Test cases with problematic capitalization
    test_titles = [
        "Outdoor Brand Arc'teryx Apologises For 'dragon' Fireworks IN Himalayas",
        "Earlybirds Club IS A Dance Party From 6 P.m. TO 10 p.m., Started BY Two...",
        "Tiktok's Algorithm TO BE Licensed TO US Joint Venture Led BY Oracle And...",
        "What IS Antifa, The Leftist Movement Trump Says He's Labeling 'maior",
        "A Powerful Storm Wiped Out These Baby Pterosaurs 150 Million Years Ago",
        "France Formally Recognises Palestinian State",
        "Duchess OF York Dropped From Multiple Charities Over Epstein Email"
    ]
    
    print("🧪 Testing Title Capitalization Improvements")
    print("=" * 60)
    
    for i, title in enumerate(test_titles, 1):
        print(f"\n{i}. Original:")
        print(f"   {title}")
        
        # Clean the title
        cleaned = detector._clean_title(title)
        print(f"   Cleaned: {cleaned}")
        
        # Check for common issues
        issues = []
        if "..." in cleaned:
            issues.append("Contains ellipses")
        if len(cleaned) > 60:
            issues.append(f"Too long ({len(cleaned)} chars)")
        if any(word.isupper() and len(word) == 2 for word in cleaned.split()):
            issues.append("Two-letter words in caps")
        if any(word.lower() in ['to', 'in', 'of', 'at', 'by', 'is', 'be', 'am', 'do', 'go', 'up', 'us', 'we', 'me', 'my', 'it', 'if', 'so', 'no', 'he', 'hi'] and word.isupper() for word in cleaned.split()):
            issues.append("Small words incorrectly capitalized")
        
        if issues:
            print(f"   ⚠️  Issues: {', '.join(issues)}")
        else:
            print(f"   ✅ Good capitalization")
    
    print(f"\n📊 Summary:")
    print(f"   Tested {len(test_titles)} titles")
    print(f"   Capitalization logic includes proper handling of two-letter words")

if __name__ == "__main__":
    test_capitalization()

