#!/usr/bin/env python3
import asyncio
import sys
import os
sys.path.insert(0, "/root/beacon3/src")
sys.path.insert(0, "/root/beacon3")

# Set up basic logging to avoid import issues
import logging
logging.basicConfig(level=logging.INFO)

from article_processor import ArticleProcessor

async def test_clustering():
    processor = ArticleProcessor()

    # Get articles directly from database since get_recent_articles might have issues
    import sqlite3
    conn = sqlite3.connect('/root/beacon3/beacon3_articles.db')
    cursor = conn.cursor()
    cursor.execute("SELECT article_id, original_title, generated_title, excerpt, status FROM articles WHERE status = 'completed' LIMIT 5")
    articles = []
    for row in cursor.fetchall():
        article = {
            'article_id': row[0],
            'original_title': row[1],
            'generated_title': row[2],
            'excerpt': row[3],
            'status': row[4]
        }
        articles.append(article)
    conn.close()

    print(f"Found {len(articles)} completed articles")

    for article in articles:
        if article.get("generated_title"):
            title = article["generated_title"][:60] if article.get("generated_title") else ""
            aid = article["article_id"]
            print(f"Article {aid}: {title}...")

            # Test clustering for this article
            content = f"{article.get('generated_title', '')} {article.get('excerpt', '')}"
            cluster_id = await processor.clustering_service.cluster_article(aid, content)
            print(f"  -> Cluster ID: {cluster_id}")

if __name__ == "__main__":
    asyncio.run(test_clustering())
