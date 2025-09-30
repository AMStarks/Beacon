#!/usr/bin/env python3
"""
Debug content extraction
"""

import asyncio
import httpx
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse

async def debug_content():
    """Debug what content is being extracted"""
    url = "https://www.bbc.com/news/articles/cj4y159190go"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.text

        soup = BeautifulSoup(content, 'html.parser')

        # Extract title
        title = soup.title.string if soup.title else ""
        if not title:
            og_title = soup.find("meta", property="og:title")
            title = og_title["content"] if og_title else ""

        # Extract main content (improved)
        content_clean = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
        content_clean = re.sub(r'<style[^>]*>.*?</style>', '', content_clean, flags=re.IGNORECASE | re.DOTALL)
        content_clean = re.sub(r'<nav[^>]*>.*?</nav>', '', content_clean, flags=re.IGNORECASE | re.DOTALL)
        content_clean = re.sub(r'<header[^>]*>.*?</header>', '', content_clean, flags=re.IGNORECASE | re.DOTALL)
        content_clean = re.sub(r'<footer[^>]*>.*?</footer>', '', content_clean, flags=re.IGNORECASE | re.DOTALL)
        content_clean = re.sub(r'<aside[^>]*>.*?</aside>', '', content_clean, flags=re.IGNORECASE | re.DOTALL)
        
        # Try to find main article content
        article_match = re.search(r'<article[^>]*>(.*?)</article>', content_clean, re.IGNORECASE | re.DOTALL)
        if article_match:
            content_clean = article_match.group(1)
        else:
            # Look for main content div
            main_match = re.search(r'<main[^>]*>(.*?)</main>', content_clean, re.IGNORECASE | re.DOTALL)
            if main_match:
                content_clean = main_match.group(1)
        
        content_clean = re.sub(r'<[^>]+>', ' ', content_clean)  # Remove HTML tags
        content_clean = re.sub(r'\s+', ' ', content_clean).strip()  # Clean whitespace
        
        print(f"Title: {title}")
        print(f"Content length: {len(content_clean)}")
        print(f"Content preview: {content_clean[:500]}...")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_content())
