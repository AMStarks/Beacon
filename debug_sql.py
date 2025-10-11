#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('/root/beacon3/beacon3_articles.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute('''
    SELECT a.*, c.title as cluster_title
    FROM articles a
    LEFT JOIN article_clusters ac ON a.article_id = ac.article_id
    LEFT JOIN clusters c ON ac.cluster_id = c.cluster_id
    WHERE a.status = "completed"
    ORDER BY a.created_at DESC
    LIMIT ?
''', (5,))

results = [dict(row) for row in cursor.fetchall()]
print(f"Found {len(results)} articles")
for row in results[:3]:
    print(f"Article {row['article_id']}: {row['status']} - {row.get('generated_title', '')[:50]}...")

conn.close()
