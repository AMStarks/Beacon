#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, "/root/beacon3/src")

from article_processor import ArticleProcessor

async def test_manual_cluster():
    processor = ArticleProcessor()

    # Get two articles that should be clustered
    article1 = processor.db.get_article(3)  # Macron article
    article2 = processor.db.get_article(58)  # Censure motion article

    print(f"Article 3: {article1.get('generated_title', '')[:60]}...")
    print(f"Article 58: {article2.get('generated_title', '')[:60]}...")

    if article1 and article2:
        # Test similarity calculation directly
        content1 = f"{article1.get('generated_title', '')} {article1.get('excerpt', '')}"
        content2 = f"{article2.get('generated_title', '')} {article2.get('excerpt', '')}"

        similarity = processor.clustering_service.calculate_similarity(content1, content2)
        print(f"Similarity score: {similarity}")

        # Check if they pass the basic threshold
        threshold = 0.08
        print(f"Passes threshold ({similarity} >= {threshold}): {similarity >= threshold}")

        # Try to force cluster them
        print("Attempting to create cluster manually...")
        cluster_id = await processor.clustering_service._create_new_cluster(3, content1, [(58, similarity)])
        print(f"Created cluster ID: {cluster_id}")

if __name__ == "__main__":
    asyncio.run(test_manual_cluster())
