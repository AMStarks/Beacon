#!/usr/bin/env python3
"""
Check current excerpts in database
"""

from beacon_database import BeaconDatabase

def check_excerpts():
    db = BeaconDatabase()
    articles = db.get_all_articles()
    print(f"Found {len(articles)} articles")
    
    for article in articles[:3]:
        print(f"ID {article['article_id']}: {article['excerpt'][:150]}...")

if __name__ == "__main__":
    check_excerpts()


