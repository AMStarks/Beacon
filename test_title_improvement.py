#!/usr/bin/env python3
"""
Test script to verify title improvement with Grok LLM integration.
This script tests the title refinement process without running the full application.
"""

import asyncio
import os
from datetime import datetime
from news_service import NewsArticle, TopicCluster
from llm_service import LLMService

async def test_title_improvement():
    """Test the title improvement process"""
    
    # Check if Grok API key is available
    if not os.getenv('GROK_API_KEY'):
        print("❌ GROK_API_KEY not found. Set it to test LLM improvements.")
        print("   Example: export GROK_API_KEY='your-api-key'")
        return
    
    # Create sample articles with problematic titles
    sample_articles = [
        NewsArticle(
            title="Outdoor Brand Arc'teryx Apologises For 'dragon' Fireworks IN Himalayas",
            content="Arc'teryx apologized for fireworks display that resembled a dragon in the Himalayas...",
            url="https://example.com/1",
            source="Test Source",
            published_at=datetime.now(),
            category="general",
            country="us",
            language="en"
        ),
        NewsArticle(
            title="Earlybirds Club IS A Dance Party From 6 P.m. TO 10 p.m., Started BY Two...",
            content="The Earlybirds Club hosts dance parties from 6 PM to 10 PM, started by two founders...",
            url="https://example.com/2",
            source="Test Source",
            published_at=datetime.now(),
            category="general",
            country="us",
            language="en"
        ),
        NewsArticle(
            title="Tiktok's Algorithm TO BE Licensed TO US Joint Venture Led BY Oracle And...",
            content="TikTok's algorithm will be licensed to a US joint venture led by Oracle and other partners...",
            url="https://example.com/3",
            source="Test Source",
            published_at=datetime.now(),
            category="general",
            country="us",
            language="en"
        )
    ]
    
    # Create a topic cluster
    topic = TopicCluster(
        id="test_topic",
        title="Outdoor Brand Arc'teryx Apologises For 'dragon' Fireworks IN Himalayas",
        summary="Topic with 2 sources covering outdoor brand apology for fireworks display",
        articles=sample_articles,
        confidence_score=0.8,
        last_updated=datetime.now(),
        status="active"
    )
    
    print("🧪 Testing Title Improvement with Grok LLM")
    print("=" * 50)
    print(f"Original title: {topic.title}")
    print(f"Original summary: {topic.summary}")
    print()
    
    # Initialize LLM service
    llm_service = LLMService()
    
    if not llm_service.enabled:
        print("❌ LLM service not enabled. Check GROK_API_KEY.")
        return
    
    try:
        # Test the refinement
        headlines = [article.title for article in sample_articles]
        sources = [article.source for article in sample_articles]
        
        print("🔄 Calling Grok LLM for title refinement...")
        improved = await llm_service.refine(
            headlines=headlines,
            sources=sources,
            current_title=topic.title,
            current_summary=topic.summary
        )
        
        print("✅ LLM Refinement Results:")
        print(f"Improved title: {improved['title']}")
        print(f"Improved summary: {improved['summary']}")
        print()
        
        # Check improvements
        original_len = len(topic.title)
        improved_len = len(improved['title'])
        
        print("📊 Analysis:")
        print(f"Original length: {original_len} characters")
        print(f"Improved length: {improved_len} characters")
        print(f"Length change: {improved_len - original_len:+d} characters")
        
        if improved_len < original_len:
            print("✅ Title is now shorter and more concise")
        else:
            print("⚠️  Title is longer than original")
        
        if "..." not in improved['title']:
            print("✅ No truncation ellipses in improved title")
        else:
            print("⚠️  Still contains truncation ellipses")
            
        if len(improved['title']) <= 60:
            print("✅ Title is under 60 characters (good for display)")
        else:
            print("⚠️  Title is over 60 characters")
            
    except Exception as e:
        print(f"❌ Error during LLM refinement: {e}")
    finally:
        await llm_service.close()

if __name__ == "__main__":
    asyncio.run(test_title_improvement())

