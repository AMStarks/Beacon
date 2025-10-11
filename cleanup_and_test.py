#!/usr/bin/env python3
"""
Script to clean up problematic articles and test the improved processing.
"""

import sqlite3
import subprocess
import sys
from datetime import datetime

def cleanup_problematic_articles():
    """Remove articles with processing errors"""
    conn = sqlite3.connect('beacon_articles.db')
    cursor = conn.cursor()
    
    print("Cleaning up problematic articles...")
    
    # Find articles with processing errors
    problematic_patterns = [
        "Processing...",
        "FAILED:",
        "I cannot generate",
        "cannot create",
        "unable to",
        "inappropriate",
        "strong opinion",
        "specific reference"
    ]
    
    # Get problematic articles
    cursor.execute("""
        SELECT article_id, title, excerpt 
        FROM articles 
        WHERE title LIKE '%Processing%' 
           OR title LIKE '%FAILED%'
           OR title LIKE '%cannot%'
           OR title LIKE '%unable%'
           OR title LIKE '%inappropriate%'
           OR excerpt LIKE '%Processing%'
           OR excerpt LIKE '%FAILED%'
    """)
    
    problematic_articles = cursor.fetchall()
    print(f"Found {len(problematic_articles)} problematic articles:")
    
    for article in problematic_articles:
        print(f"  ID {article[0]}: {article[1][:50]}...")
    
    if problematic_articles:
        # Delete problematic articles
        article_ids = [str(article[0]) for article in problematic_articles]
        placeholders = ','.join('?' * len(article_ids))
        
        cursor.execute(f"DELETE FROM articles WHERE article_id IN ({placeholders})", article_ids)
        conn.commit()
        print(f"Deleted {len(problematic_articles)} problematic articles")
    else:
        print("No problematic articles found")
    
    conn.close()

def test_improved_processing():
    """Test the improved processing with a sample URL"""
    print("\nTesting improved processing...")
    
    # Test URL (use a reliable news source)
    test_url = "https://www.bbc.com/news/technology"
    
    try:
        # Test title generation
        print("Testing title generation...")
        result = subprocess.run([
            "python3", "sync_title_generator.py", test_url
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Title generation test passed")
            # Extract title from output
            import re
            title_match = re.search(r"'neutral_title':\s*'([^']+)'", result.stdout)
            if title_match:
                print(f"Generated title: {title_match.group(1)}")
        else:
            print(f"❌ Title generation test failed: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        print("❌ Title generation test timed out")
    except Exception as e:
        print(f"❌ Title generation test error: {e}")

def get_database_stats():
    """Get current database statistics"""
    conn = sqlite3.connect('beacon_articles.db')
    cursor = conn.cursor()
    
    # Total articles
    cursor.execute("SELECT COUNT(*) FROM articles")
    total_articles = cursor.fetchone()[0]
    
    # Articles with processing errors
    cursor.execute("""
        SELECT COUNT(*) FROM articles 
        WHERE title LIKE '%Processing%' 
           OR title LIKE '%FAILED%'
           OR title LIKE '%cannot%'
    """)
    error_articles = cursor.fetchone()[0]
    
    # Articles with good titles
    cursor.execute("""
        SELECT COUNT(*) FROM articles 
        WHERE title NOT LIKE '%Processing%' 
           AND title NOT LIKE '%FAILED%'
           AND title NOT LIKE '%cannot%'
           AND LENGTH(title) > 10
    """)
    good_articles = cursor.fetchone()[0]
    
    # Clusters
    cursor.execute("SELECT COUNT(*) FROM clusters")
    total_clusters = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"\nDatabase Statistics:")
    print(f"  Total articles: {total_articles}")
    print(f"  Articles with errors: {error_articles}")
    print(f"  Good articles: {good_articles}")
    print(f"  Total clusters: {total_clusters}")

def main():
    """Main cleanup and test function"""
    print("=== Article Cleanup and Testing ===")
    
    # Get initial stats
    print("\n1. Initial database statistics:")
    get_database_stats()
    
    # Clean up problematic articles
    print("\n2. Cleaning up problematic articles...")
    cleanup_problematic_articles()
    
    # Get stats after cleanup
    print("\n3. Database statistics after cleanup:")
    get_database_stats()
    
    # Test improved processing
    print("\n4. Testing improved processing...")
    test_improved_processing()
    
    print("\n=== Cleanup and Testing Complete ===")
    print("\nReady to restart collector with improved processing!")

if __name__ == "__main__":
    main()
