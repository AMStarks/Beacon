#!/usr/bin/env python3
import sys
sys.path.insert(0, "/root/beacon3/src")
import os

print(f"Current working directory: {os.getcwd()}")

from database import Beacon3Database

db = Beacon3Database('/root/beacon3/beacon3_articles.db')
articles = db.get_recent_articles(5, include_processing=True)
print(f"Found {len(articles)} articles")
for article in articles[:3]:
    print(f"Article {article['article_id']}: {article['status']} - {article.get('generated_title', '')[:50]}...")
