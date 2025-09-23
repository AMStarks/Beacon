#!/usr/bin/env python3
import asyncio
from crawler_service import CrawlerService

async def test_crawler():
    """Test the crawler service"""
    print("Testing Beacon Crawler Service...")
    
    crawler = CrawlerService()
    
    try:
        # Test RSS feed crawling (safer than web scraping)
        print("Testing RSS feed crawling...")
        rss_articles = await crawler.crawl_rss_feeds()
        print(f"Found {len(rss_articles)} articles from RSS feeds")
        
        for i, article in enumerate(rss_articles[:3]):  # Show first 3
            print(f"\nArticle {i+1}:")
            print(f"Title: {article.title}")
            print(f"Source: {article.source}")
            print(f"URL: {article.url}")
            print(f"Content preview: {article.content[:100]}...")
        
        # Test web crawling (limited)
        print("\nTesting web crawling...")
        web_articles = await crawler.crawl_news_sources()
        print(f"Found {len(web_articles)} articles from web sources")
        
        for i, article in enumerate(web_articles[:3]):  # Show first 3
            print(f"\nWeb Article {i+1}:")
            print(f"Title: {article.title}")
            print(f"Source: {article.source}")
            print(f"URL: {article.url}")
            print(f"Content preview: {article.content[:100]}...")
        
    except Exception as e:
        print(f"Error during testing: {e}")
    finally:
        await crawler.close()

if __name__ == "__main__":
    asyncio.run(test_crawler())
