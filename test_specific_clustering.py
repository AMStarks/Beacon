#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, "/root/beacon3/src")

from article_processor import ArticleProcessor

async def test_specific_clustering():
    processor = ArticleProcessor()

    # Test clustering for specific articles that should be related
    test_articles = [
        ("Macron Names New Prime Minister to End Political Crisis", 3),
        ("Censure Motion Fails, But French Plot to Kill Bart De Wever Continues", None)  # Find this article ID
    ]

    # First find the article ID for the second article
    import sqlite3
    conn = sqlite3.connect('/root/beacon3/beacon3_articles.db')
    cursor = conn.cursor()
    cursor.execute("SELECT article_id FROM articles WHERE generated_title LIKE '%Censure Motion%'")
    row = cursor.fetchone()
    if row:
        test_articles[1] = (test_articles[1][0], row[0])
    conn.close()

    print(f"Testing clustering for: {test_articles}")

    for title, aid in test_articles:
        if aid:
            print(f"\n--- Testing Article {aid}: {title[:50]}... ---")

            # Get article content
            article = processor.db.get_article(aid)
            if article:
                content = f"{article.get('generated_title', '')} {article.get('excerpt', '')}"
                cluster_id = await processor.clustering_service.cluster_article(aid, content)
                print(f"  -> Cluster ID: {cluster_id}")

if __name__ == "__main__":
    asyncio.run(test_specific_clustering())
