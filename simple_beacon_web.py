#!/usr/bin/env python3
"""
Simple Beacon Web Interface - Working version with database backend
"""

from flask import Flask, render_template_string, request, jsonify
import json
from datetime import datetime, timezone
from beacon_database import BeaconDatabase
from sync_title_generator import SyncNeutralTitleGenerator
from sync_excerpt_generator import SyncNeutralExcerptGenerator
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize database and generators
db = BeaconDatabase("beacon_articles.db")
title_generator = SyncNeutralTitleGenerator()
excerpt_generator = SyncNeutralExcerptGenerator()

# Simple HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Beacon AI News Desk</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 0;
            padding: 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }
        .header h1 {
            font-size: 3rem;
            margin-bottom: 10px;
        }
        .card {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        .article-meta {
            display: flex;
            gap: 20px;
            margin-bottom: 15px;
            font-size: 0.9rem;
            color: #718096;
            flex-wrap: wrap;
        }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            font-size: 1rem;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
        }
        .results {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
            display: none;
        }
        .date-display {
            background: #e6fffa;
            border: 1px solid #81e6d9;
            border-radius: 8px;
            padding: 15px;
            margin: 15px 0;
        }
        .date-item {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }
        .date-label {
            font-weight: 600;
            color: #2d3748;
        }
        .date-value {
            color: #4a5568;
            font-family: monospace;
        }
        .error {
            background: #fed7d7;
            border: 1px solid #feb2b2;
            color: #c53030;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .success {
            background: #c6f6d5;
            border: 1px solid #9ae6b4;
            color: #22543d;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }
        
        .url-input-section {
            margin: 20px 0;
            padding: 20px;
            background: #f8f9fa;
            border-radius: 10px;
            border: 2px solid #e9ecef;
        }
        
        .url-form {
            max-width: 600px;
            margin: 0 auto;
        }
        
        .input-group {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        
        #url-input {
            flex: 1;
            padding: 12px 15px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        #url-input:focus {
            outline: none;
            border-color: #007bff;
            box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
        }
        
        #submit-btn {
            padding: 12px 25px;
            background: #007bff;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        
        #submit-btn:hover {
            background: #0056b3;
        }
        
        #submit-btn:disabled {
            background: #6c757d;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Beacon AI News Desk</h1>
            <p>Intelligent news processing with database backend</p>
        </div>

        <div class="url-input-section">
            <form id="url-form" class="url-form">
                <div class="input-group">
                    <input type="url" id="url-input" placeholder="Enter article URL here..." required>
                    <button type="submit" id="submit-btn">Submit</button>
                </div>
            </form>
        </div>

        <div id="articles-container">
            <!-- Dynamic articles will be loaded here -->
        </div>
            
            <div class="results" id="results">
                <div class="date-display" id="date-display" style="display: none;">
                    <div class="date-item">
                        <span class="date-label">📥 Sourced Date:</span>
                        <span class="date-value" id="sourced-date">Loading...</span>
                    </div>
                    <div class="date-item">
                        <span class="date-label">📝 Written Date:</span>
                        <span class="date-value" id="written-date">Loading...</span>
                    </div>
                </div>
                
                <div id="article-info" style="display: none;">
                    <h4>📊 Article Information</h4>
                    <p><strong>Article ID:</strong> <span id="article-id"></span></p>
                    <p><strong>URL:</strong> <span id="article-url"></span></p>
                    <p><strong>Title:</strong> <span id="article-title"></span></p>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Simple function to load dates from database
        async function loadAllArticles() {
            try {
                console.log('Loading all articles...');
                const response = await fetch('/api/articles');
                const data = await response.json();
                
                if (data.success) {
                    console.log('Articles loaded:', data.articles);
                    displayArticles(data.articles);
                } else {
                    console.error('Failed to load articles:', data.error);
                }
            } catch (error) {
                console.error('Error loading articles:', error);
            }
        }
        
        function displayArticles(articles) {
            const container = document.getElementById('articles-container');
            container.innerHTML = '';
            
            articles.forEach(item => {
                const card = item.is_cluster ? createClusterCard(item) : createArticleCard(item);
                container.appendChild(card);
            });
        }
        
        function createClusterCard(cluster) {
            const card = document.createElement('div');
            card.className = 'card';
            card.style.background = 'linear-gradient(135deg, #e0f2fe 0%, #dbeafe 100%)';
            card.style.border = '2px solid #3b82f6';
            
            // Create sources list HTML
            const sourcesHTML = cluster.sources.map(s => `
                <div style="margin: 5px 0; padding: 8px; background: white; border-radius: 6px;">
                    <span style="color: #3b82f6; font-weight: 600;">Article ${s.article_id}</span> - 
                    <span style="color: #64748b;">${s.source || 'Unknown'}</span> - 
                    <a href="${s.url}" target="_blank" style="color: #3b82f6;">View</a>
                </div>
            `).join('');
            
            card.innerHTML = `
                <div style="background: #3b82f6; color: white; padding: 8px 16px; border-radius: 8px; display: inline-block; margin-bottom: 15px; font-weight: 600;">
                    📊 CLUSTER #${cluster.cluster_id}
                </div>
                <h2>${cluster.cluster_title || 'Cluster'}</h2>
                <div class="article-meta">
                    <span>📰 <strong>${cluster.sources.length} Related Articles</strong></span>
                    <span>🔄 <strong>Updated:</strong> ${formatDate(new Date(cluster.updated_at))}</span>
                </div>
                <div class="article-excerpt">
                    <p>${cluster.cluster_summary || 'No summary available'}</p>
                </div>
                <div class="article-info">
                    <p><strong>Cluster ID:</strong> ${cluster.cluster_id}</p>
                    <p><strong>Sources:</strong></p>
                    ${sourcesHTML}
                </div>
            `;
            return card;
        }
        
        function createArticleCard(article) {
            const card = document.createElement('div');
            card.className = 'card';
            card.innerHTML = `
                <h2>${article.title}</h2>
                <div class="article-meta">
                    <span>🌐 ${article.source || 'Unknown'}</span>
                    <span>🔗 <a href="${article.url}" target="_blank">View Original</a></span>
                </div>
                <div class="article-meta">
                    <span>📥 <strong>Sourced Date:</strong> ${formatDate(new Date(article.date_sourced))}</span>
                    <span>📝 <strong>Written Date:</strong> ${formatDate(new Date(article.date_written))}</span>
                </div>
                <div class="article-excerpt">
                    <p>${article.excerpt || 'No excerpt available'}</p>
                </div>
                <div class="article-info">
                    <p><strong>Article ID:</strong> ${article.article_id}</p>
                    <p><strong>URL:</strong> ${article.url}</p>
                </div>
            `;
            return card;
        }
        
        function formatDate(date) {
            const day = date.getDate().toString().padStart(2, '0');
            const month = date.toLocaleDateString('en', { month: 'short' });
            const year = date.getFullYear().toString().slice(-2);
            return `${day}, ${month}, ${year}`;
        }
        
        async function loadDates() {
            console.log('Loading dates...');
            try {
                const response = await fetch('/api/process-article', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: 'https://www.bbc.com/news/articles/cj4y159190go',
                        title: 'China makes landmark pledge to cut its climate emissions',
                        content: 'China, the world\\'s biggest source of planet-warming gases, has for the first time committed to an absolute target to cut its emissions...',
                        source: 'BBC News',
                        date_written: '2024-09-29T00:00:00+00:00'
                    })
                });
                
                console.log('Response received:', response.status);
                const data = await response.json();
                console.log('Data:', data);
                
                if (data.success) {
                    console.log('Success! Updating dates...');
                    console.log('Article data:', data.article);
                    
                    // Format dates to (DD, Mon, YY) format
                    const sourcedDate = new Date(data.article.date_sourced);
                    const writtenDate = new Date(data.article.date_written);
                    
                    const formatDate = (date) => {
                        const day = date.getDate().toString().padStart(2, '0');
                        const month = date.toLocaleDateString('en', { month: 'short' });
                        const year = date.getFullYear().toString().slice(-2);
                        return `${day}, ${month}, ${year}`;
                    };
                    
                    // Update the date displays
                    document.getElementById('sourced-date-display').textContent = formatDate(sourcedDate);
                    document.getElementById('written-date-display').textContent = formatDate(writtenDate);
                    
                    // Update title and excerpt from database
                    console.log('Updating title to:', data.article.title);
                    console.log('Updating excerpt to:', data.article.excerpt);
                    
                    // Check if elements exist
                    const articleTitleEl = document.getElementById('article-title');
                    const displayTitleEl = document.getElementById('display-title');
                    const excerptContentEl = document.getElementById('excerpt-content');
                    
                    console.log('Elements found:', {
                        articleTitle: !!articleTitleEl,
                        displayTitle: !!displayTitleEl,
                        excerptContent: !!excerptContentEl
                    });
                    
                    if (articleTitleEl) articleTitleEl.textContent = data.article.title;
                    if (displayTitleEl) displayTitleEl.textContent = data.article.title;
                    if (excerptContentEl) excerptContentEl.textContent = data.article.excerpt || 'No excerpt available';
                    
                    // Show article info
                    document.getElementById('article-id').textContent = data.article.article_id;
                    document.getElementById('article-url').textContent = data.article.url;
                    document.getElementById('article-info').style.display = 'block';
                    
                    console.log('Dates, title, and excerpt updated successfully');
                } else {
                    console.error('API returned success: false');
                }
            } catch (error) {
                console.error('Error loading dates:', error);
                document.getElementById('sourced-date-display').textContent = 'Error: ' + error.message;
                document.getElementById('written-date-display').textContent = 'Error: ' + error.message;
            }
        }
        
        // Load articles when page loads
        window.addEventListener('load', function() {
            console.log('Page loaded, calling loadAllArticles...');
            loadAllArticles();
        });
        
        // Also try to load articles immediately
        document.addEventListener('DOMContentLoaded', function() {
            console.log('DOM loaded, calling loadAllArticles...');
            loadAllArticles();
        });
        
        // Handle URL form submission
        document.getElementById('url-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const urlInput = document.getElementById('url-input');
            const submitBtn = document.getElementById('submit-btn');
            const url = urlInput.value.trim();
            
            if (!url) return;
            
            // Disable button and show loading
            submitBtn.disabled = true;
            submitBtn.textContent = 'Processing...';
            
            try {
                console.log('Submitting URL:', url);
                
                const response = await fetch('/api/process-article', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        url: url,
                        title: 'Processing...',
                        content: 'Processing...',
                        source: 'User Input',
                        date_written: new Date().toISOString()
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    console.log('Article processed successfully:', data.article);
                    
                    // Clear input field
                    urlInput.value = '';
                    
                    // Reload articles to show new one
                    await loadAllArticles();
                    
                    // Show success message
                    showMessage('Article processed successfully!', 'success');
                } else {
                    console.error('Failed to process article:', data.error);
                    showMessage('Failed to process article: ' + data.error, 'error');
                }
            } catch (error) {
                console.error('Error processing article:', error);
                showMessage('Error processing article: ' + error.message, 'error');
            } finally {
                // Re-enable button
                submitBtn.disabled = false;
                submitBtn.textContent = 'Submit';
            }
        });
        
        function showMessage(message, type) {
            // Create temporary message element
            const messageEl = document.createElement('div');
            messageEl.className = `message ${type}`;
            messageEl.textContent = message;
            messageEl.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                border-radius: 8px;
                color: white;
                font-weight: 600;
                z-index: 1000;
                background: ${type === 'success' ? '#28a745' : '#dc3545'};
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            `;
            
            document.body.appendChild(messageEl);
            
            // Remove after 3 seconds
            setTimeout(() => {
                if (messageEl.parentNode) {
                    messageEl.parentNode.removeChild(messageEl);
                }
            }, 3000);
        }
        
        // Process article function
        async function processArticle() {
            await loadDates();
            document.getElementById('results').style.display = 'block';
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main page"""
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/articles')
def get_articles():
    """Get all articles and clusters from database"""
    try:
        import sqlite3
        
        # Get all clusters with their data
        conn = sqlite3.connect('beacon_articles.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT cluster_id, cluster_title, cluster_summary, article_ids, 
                   created_at, updated_at
            FROM clusters 
            ORDER BY updated_at DESC
        ''')
        clusters_rows = cursor.fetchall()
        
        clusters = []
        clustered_article_ids = set()
        
        for row in clusters_rows:
            cluster_data = dict(row)
            article_ids = json.loads(cluster_data['article_ids'])
            clustered_article_ids.update(article_ids)
            
            # Get article URLs/sources for this cluster
            cursor.execute(f'''
                SELECT article_id, url, source 
                FROM articles 
                WHERE article_id IN ({','.join('?' * len(article_ids))})
            ''', article_ids)
            
            sources = [{'article_id': r[0], 'url': r[1], 'source': r[2]} 
                      for r in cursor.fetchall()]
            
            cluster_data['sources'] = sources
            cluster_data['article_ids'] = article_ids
            cluster_data['is_cluster'] = True
            clusters.append(cluster_data)
        
        # Get standalone articles (not in any cluster)
        cursor.execute('''
            SELECT * FROM articles 
            WHERE cluster_id IS NULL 
            ORDER BY created_at DESC
        ''')
        standalone_rows = cursor.fetchall()
        standalone_articles = [dict(row) for row in standalone_rows]
        
        conn.close()
        
        # Combine clusters and standalone articles
        all_items = clusters + standalone_articles
        
        return jsonify({"success": True, "articles": all_items})
    except Exception as e:
        logger.error(f"Error in get_articles: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/process-article', methods=['POST'])
def process_article():
    """Process article and add to database"""
    try:
        data = request.get_json()
        
        # Extract article data
        url = data.get('url', '')
        title = data.get('title', '')
        content = data.get('content', '')
        excerpt = data.get('excerpt', '')
        source = data.get('source', '')
        date_written = data.get('date_written', None)
        
        # Check if article already exists by URL
        existing_article = db.get_article_by_url(url)
        
        if existing_article:
            # Article already exists - return existing data
            logger.info(f"✅ Article already exists with ID: {existing_article['article_id']}")
            return jsonify({
                'success': True,
                'article': existing_article
            })
        else:
            # Generate neutral title and excerpt from URL
            logger.info(f"🤖 Generating neutral title and excerpt for URL: {url}")
            import asyncio
            
            # Generate neutral title
            title_result = title_generator.generate_neutral_title(url)
            if title_result.get('success'):
                neutral_title = title_result['neutral_title']
                logger.info(f"✅ Generated neutral title: {neutral_title}")
            else:
                neutral_title = title  # Fallback to original title
                logger.warning(f"⚠️ Failed to generate neutral title, using original: {title}")
            
            # Generate neutral excerpt
            excerpt_result = excerpt_generator.generate_neutral_excerpt(url)
            if excerpt_result.get('success'):
                neutral_excerpt = excerpt_result['neutral_excerpt']
                logger.info(f"✅ Generated neutral excerpt ({excerpt_result['word_count']} words): {neutral_excerpt[:100]}...")
            else:
                neutral_excerpt = excerpt  # Fallback to original excerpt
                logger.warning(f"⚠️ Failed to generate neutral excerpt, using original: {excerpt}")
            
            # Add new article to database with neutral title and excerpt
            article_id = db.add_article(
                url=url,
                title=neutral_title,  # Use generated neutral title
                content=content,
                excerpt=neutral_excerpt,  # Use generated neutral excerpt
                source=source,
                date_written=date_written
            )
            
            # Get the article back from database
            article = db.get_article(article_id)
            
            logger.info(f"✅ New article processed and stored with ID: {article_id}")
            
            return jsonify({
                'success': True,
                'article': article,
                'neutral_title_generated': title_result.get('success', False),
                'neutral_excerpt_generated': excerpt_result.get('success', False),
                'excerpt_word_count': excerpt_result.get('word_count', 0)
            })
        
    except Exception as e:
        logger.error(f"❌ Failed to process article: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/stats')
def get_stats():
    """Get database statistics"""
    try:
        stats = db.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        logger.error(f"❌ Failed to get stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("🚀 Starting Beacon Web Interface...")
    print("📊 Database initialized")
    print("🌐 Web interface available at http://0.0.0.0:80")
    app.run(host='0.0.0.0', port=80, debug=False)
