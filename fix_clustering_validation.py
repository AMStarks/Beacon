#!/usr/bin/env python3
"""
Script to validate and fix existing clusters using the improved clustering logic.
This will identify and split incoherent clusters.
"""

import sqlite3
import json
from datetime import datetime
from clustering_service import ClusteringService

def validate_all_clusters():
    """Validate all existing clusters and fix incoherent ones"""
    service = ClusteringService()
    
    # Get all clusters
    conn = sqlite3.connect("beacon_articles.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT cluster_id, cluster_title, cluster_summary, article_ids, created_at
        FROM clusters 
        ORDER BY created_at DESC
    """)
    
    clusters = cursor.fetchall()
    conn.close()
    
    print(f"Found {len(clusters)} clusters to validate")
    
    incoherent_clusters = []
    
    for cluster in clusters:
        cluster_id = cluster[0]
        cluster_title = cluster[1]
        article_ids = json.loads(cluster[3])
        
        print(f"\nValidating cluster {cluster_id}: '{cluster_title}' ({len(article_ids)} articles)")
        
        # Validate cluster coherence
        is_coherent = service.validate_cluster_coherence(cluster_id)
        
        if not is_coherent:
            print(f"❌ Cluster {cluster_id} is INCOHERENT")
            incoherent_clusters.append(cluster_id)
        else:
            print(f"✅ Cluster {cluster_id} is coherent")
    
    # Fix incoherent clusters
    if incoherent_clusters:
        print(f"\nFixing {len(incoherent_clusters)} incoherent clusters...")
        
        for cluster_id in incoherent_clusters:
            print(f"Splitting cluster {cluster_id}...")
            split_articles = service.split_incoherent_cluster(cluster_id)
            print(f"Split cluster {cluster_id} into {len(split_articles)} standalone articles")
    else:
        print("\n✅ All clusters are coherent!")

def analyze_problematic_cluster():
    """Analyze the specific problematic cluster with Digital ID and Politics articles"""
    conn = sqlite3.connect("beacon_articles.db")
    cursor = conn.cursor()
    
    # Get the Digital ID cluster
    cursor.execute("""
        SELECT cluster_id, cluster_title, cluster_summary, article_ids
        FROM clusters 
        WHERE cluster_title LIKE '%Digital ID%'
        ORDER BY created_at DESC
        LIMIT 1
    """)
    
    cluster = cursor.fetchone()
    if not cluster:
        print("No Digital ID cluster found")
        return
    
    cluster_id, title, summary, article_ids_json = cluster
    article_ids = json.loads(article_ids_json)
    
    print(f"Analyzing cluster {cluster_id}: '{title}'")
    print(f"Articles: {article_ids}")
    
    # Get article details
    cursor.execute("""
        SELECT article_id, title, source, identifier_1, identifier_2, identifier_3, 
               identifier_4, identifier_5, identifier_6
        FROM articles 
        WHERE article_id IN ({})
        ORDER BY article_id
    """.format(','.join('?' * len(article_ids))), article_ids)
    
    articles = cursor.fetchall()
    
    print("\nArticle details:")
    for article in articles:
        print(f"  ID {article[0]}: {article[1]}")
        print(f"    Source: {article[2]}")
        print(f"    Topic Primary: {article[3]}")
        print(f"    Topic Secondary: {article[4]}")
        print(f"    Entity Primary: {article[5]}")
        print(f"    Entity Secondary: {article[6]}")
        print(f"    Location: {article[7]}")
        print(f"    Event/Policy: {article[8]}")
        print()
    
    conn.close()
    
    # Test with improved clustering service
    service = ClusteringService()
    is_coherent = service.validate_cluster_coherence(cluster_id)
    
    print(f"Cluster coherence validation: {'✅ COHERENT' if is_coherent else '❌ INCOHERENT'}")
    
    if not is_coherent:
        print("This cluster should be split due to incoherence")

if __name__ == "__main__":
    print("=== Clustering Validation and Fix Script ===")
    
    print("\n1. Analyzing problematic cluster...")
    analyze_problematic_cluster()
    
    print("\n2. Validating all clusters...")
    validate_all_clusters()
    
    print("\n=== Validation Complete ===")
