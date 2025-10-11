#!/usr/bin/env python3
"""
Beacon 3 Web Interface - Flask API for article submission and monitoring
"""

import asyncio
import logging
from flask import Flask, request, jsonify, render_template_string
import re
import subprocess
from .article_processor import ArticleProcessor
import os
import requests

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global processor instance
processor = ArticleProcessor()
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "d69a3b23cad345b898a6ee4d6303c69b")

# --- Simple Auto-Fetch Scheduler (NewsAPI: 1 article every 2 minutes) ---
import threading
from datetime import datetime, timezone

auto_fetch_thread = None
auto_fetch_stop_event = None
auto_fetch_running = False
auto_fetch_interval_sec = 120  # default 2 minutes
auto_fetch_query = ''
auto_fetch_last_url = ''
auto_fetch_last_time = None
auto_fetch_last_error = ''

def _newsapi_fetch_one(query: str = '') -> str:
    """Return newest article URL from NewsAPI (or empty string)."""
    if not NEWSAPI_KEY:
        raise RuntimeError("NEWSAPI_KEY not configured")
    headers = {'X-Api-Key': NEWSAPI_KEY}
    params = { 'language': 'en', 'pageSize': 1 }
    if query:
        url = 'https://newsapi.org/v2/everything'
        params['q'] = query
        params['sortBy'] = 'publishedAt'
    else:
        url = 'https://newsapi.org/v2/top-headlines'
    r = requests.get(url, headers=headers, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    articles = data.get('articles') or []
    # Fallback when empty: try top-headlines with country hints
    if not articles and not query:
        for country in ('us', 'gb'):
            try:
                p2 = { 'language': 'en', 'pageSize': 1, 'country': country }
                r2 = requests.get('https://newsapi.org/v2/top-headlines', headers=headers, params=p2, timeout=20)
                r2.raise_for_status()
                d2 = r2.json()
                arts2 = d2.get('articles') or []
                if arts2:
                    return arts2[0].get('url') or ''
            except Exception:
                continue
        return ''
    if not articles:
        return ''
    return articles[0].get('url') or ''

def _auto_fetch_loop():
    global auto_fetch_running, auto_fetch_last_url, auto_fetch_last_time, auto_fetch_last_error
    logger.info(f"🛰️ AutoFetch loop started (interval={auto_fetch_interval_sec}s, query='{auto_fetch_query}')")
    while auto_fetch_running and auto_fetch_stop_event and not auto_fetch_stop_event.is_set():
        try:
            url = _newsapi_fetch_one(auto_fetch_query)
            if url and url != auto_fetch_last_url:
                try:
                    asyncio.run(processor.submit_article(url))
                    logger.info(f"✅ AutoFetch queued article: {url}")
                    auto_fetch_last_url = url
                    auto_fetch_last_error = ''
                except Exception as e:
                    auto_fetch_last_error = str(e)
                    logger.warning(f"⚠️ AutoFetch submit failed: {e}")
            else:
                logger.info("ℹ️ AutoFetch: no new URL or duplicate; skipping")
            auto_fetch_last_time = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            auto_fetch_last_error = str(e)
            logger.warning(f"⚠️ AutoFetch fetch failed: {e}")
        # Sleep with stop support
        if auto_fetch_stop_event.wait(auto_fetch_interval_sec):
            break
    logger.info("🛑 AutoFetch loop stopped")

# HTML Template (same as Beacon 2)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Beacon 3 - AI News Desk</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
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
            color: #2d3748;
            margin-bottom: 40px;
        }
        .card {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        .btn {
            background: linear-gradient(135deg, #4a5568 0%, #2d3748 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            font-size: 1rem;
            margin: 5px;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
        }
        .btn-success { background: linear-gradient(135deg, #48bb78 0%, #38a169 100%); }
        .btn-danger { background: linear-gradient(135deg, #f56565 0%, #e53e3e 100%); }
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        .status-running { background-color: #48bb78; }
        .status-stopped { background-color: #f56565; }

        .article-card {
            background: white;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
            border-left: 5px solid #4a5568;
            transition: all 0.3s ease;
            position: relative;
        }
        .article-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.15);
        }

        .cluster-card {
            background: linear-gradient(135deg, #e2e8f0 0%, #cbd5e0 100%);
            color: #2d3748;
            border-radius: 16px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
            position: relative;
        }
        .cluster-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 35px rgba(0, 0, 0, 0.15);
        }

        .cluster-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
            cursor: pointer;
        }
        .cluster-header h3 {
            margin: 0;
            font-size: 1.3rem;
        }
        .cluster-toggle {
            background: rgba(74, 85, 104, 0.1);
            border: none;
            color: #2d3748;
            width: 32px;
            height: 32px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: background 0.3s ease;
        }
        .cluster-toggle:hover {
            background: rgba(74, 85, 104, 0.2);
        }

        .cluster-sources {
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid rgba(226, 232, 240, 0.8);
        }
        .cluster-source {
            background: rgba(255, 255, 255, 0.7);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 12px;
            transition: background 0.3s ease;
            border: 1px solid rgba(226, 232, 240, 0.8);
        }
        .cluster-source:hover {
            background: rgba(255, 255, 255, 0.9);
            border-color: #e2e8f0;
        }
        .cluster-source:last-child {
            margin-bottom: 0;
        }

        .cluster-excerpt {
            color: #4a5568;
            line-height: 1.6;
            margin: 12px 0;
            font-size: 0.95rem;
            text-align: left;
        }

        .cluster-sources-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 16px 0 8px 0;
            padding: 8px 0;
            border-top: 1px solid rgba(226, 232, 240, 0.5);
        }

        .cluster-sources-content {
            margin-top: 8px;
        }

        .cluster-source-item {
            background: rgba(255, 255, 255, 0.5);
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 8px;
            border: 1px solid rgba(226, 232, 240, 0.3);
            transition: background 0.2s ease;
        }

        .cluster-source-item:hover {
            background: rgba(255, 255, 255, 0.7);
        }

        .cluster-toggle-btn {
            background: #4a5568;
            color: white;
            border: none;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 0.8rem;
            cursor: pointer;
            transition: background 0.2s ease;
        }

        .cluster-toggle-btn:hover {
            background: #2d3748;
        }

        .article-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            margin-top: 16px;
            padding-top: 16px;
            border-top: 1px solid #e2e8f0;
            font-size: 0.9rem;
            color: #718096;
        }
        .article-meta span {
            display: flex;
            align-items: center;
        }

        .excerpt {
            color: #4a5568;
            line-height: 1.6;
            margin: 12px 0;
        }

        .card-badge {
            display: inline-block;
            background: rgba(74, 85, 104, 0.1);
            color: #2d3748;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.8rem;
            margin-left: 12px;
        }

        a {
            color: #3182ce;
            text-decoration: none;
            font-weight: 500;
            transition: color 0.2s ease;
        }
        a:hover {
            color: #2c5aa0;
            text-decoration: underline;
        }

        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
        }
        .form-group input, .form-group textarea {
            width: 100%;
            padding: 12px;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            font-size: 1rem;
        }
        .loading { text-align: center; color: #718096; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #f7fafc;
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }
        .stat-number {
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }
        .stat-label {
            color: #718096;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Beacon 3 - AI News Desk</h1>
            <p>Autonomous News Processing & Clustering</p>
        </div>

        <div class="card">
            <h2>📊 System Status</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="total-articles">0</div>
                    <div class="stat-label">Total Articles</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="completed-articles">0</div>
                    <div class="stat-label">Completed</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="total-clusters">0</div>
                    <div class="stat-label">Clusters</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="queue-size">0</div>
                    <div class="stat-label">In Queue</div>
                </div>
            </div>

            <div id="processor-status">
                <span class="status-indicator status-stopped"></span>
                <span id="status-text">Processor is STOPPED</span>
            </div>

            <div style="margin-top: 20px;">
                <button class="btn btn-success" id="start-btn" onclick="startProcessor()">▶️ Start Processor</button>
                <button class="btn btn-danger" id="stop-btn" onclick="stopProcessor()" style="display: none;">⏹️ Stop Processor</button>
                <button class="btn" onclick="refreshStats()">🔄 Refresh Stats</button>
            </div>
        </div>

        <div class="card">
            <h2>📰 Submit Article</h2>
            <form id="article-form">
                <div class="form-group">
                    <label for="url">Article URL:</label>
                    <input type="url" id="url" name="url" required placeholder="https://example.com/article">
                </div>
                <button type="submit" class="btn">🚀 Submit Article</button>
            </form>
        </div>

        <div class="card">
            <h2>⚙️ Automation</h2>
            <div class="form-group">
                <label for="newsapi-query">Query (optional):</label>
                <input type="text" id="newsapi-query" placeholder="e.g., digital id OR uk">
            </div>
            <div style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
                <button class="btn" onclick="fetchNewsApi()">📥 Fetch 10 Articles (manual)</button>
                <button class="btn" id="auto-on" onclick="startAutoFetch()">▶️ Start auto (1 / 2 min)</button>
                <button class="btn btn-danger" id="auto-off" onclick="stopAutoFetch()">⏹️ Stop auto</button>
            </div>
            <div id="newsapi-status" class="loading" style="margin-top:10px;"></div>
        </div>

        <div class="card">
            <h2>📚 Recent Articles & Clusters</h2>
            <button class="btn" onclick="loadFeed()">🔄 Refresh Feed</button>
            <div id="feed-container" class="loading">Loading feed...</div>
        </div>
    </div>

    <script>
        // Auto-refresh stats every 5 seconds
        setInterval(refreshStats, 5000);

        async function refreshStats() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();

                document.getElementById('total-articles').textContent = data.stats.total_articles;
                document.getElementById('completed-articles').textContent = data.stats.completed_articles;
                document.getElementById('total-clusters').textContent = data.stats.total_clusters;
                document.getElementById('queue-size').textContent = data.stats.queued_items;

                const indicator = document.querySelector('.status-indicator');
                const statusText = document.getElementById('status-text');
                const startBtn = document.getElementById('start-btn');
                const stopBtn = document.getElementById('stop-btn');

                if (data.is_running) {
                    indicator.className = 'status-indicator status-running';
                    statusText.textContent = 'Processor is RUNNING';
                    startBtn.style.display = 'none';
                    stopBtn.style.display = 'inline-block';
                } else {
                    indicator.className = 'status-indicator status-stopped';
                    statusText.textContent = 'Processor is STOPPED';
                    startBtn.style.display = 'inline-block';
                    stopBtn.style.display = 'none';
                }
            } catch (error) {
                console.error('Error refreshing stats:', error);
            }
        }

        async function startProcessor() {
            const btn = document.getElementById('start-btn');
            btn.disabled = true;
            btn.textContent = 'Starting...';

            try {
                const response = await fetch('/api/start-processor', { method: 'POST' });
                const data = await response.json();

                if (data.success) {
                    alert('Processor started!');
                    refreshStats();
                } else {
                    alert('Failed to start: ' + data.error);
                }
            } catch (error) {
                alert('Error starting processor: ' + error);
            } finally {
                btn.disabled = false;
                btn.textContent = '▶️ Start Processor';
            }
        }

        async function stopProcessor() {
            const btn = document.getElementById('stop-btn');
            btn.disabled = true;
            btn.textContent = 'Stopping...';

            try {
                const response = await fetch('/api/stop-processor', { method: 'POST' });
                const data = await response.json();

                if (data.success) {
                    alert('Processor stopped!');
                    refreshStats();
                } else {
                    alert('Failed to stop: ' + data.error);
                }
            } catch (error) {
                alert('Error stopping processor: ' + error);
            } finally {
                btn.disabled = false;
                btn.textContent = '⏹️ Stop Processor';
            }
        }

        async function loadFeed() {
            try {
                const response = await fetch('/api/feed');
                const data = await response.json();
                const container = document.getElementById('feed-container');

                let html = '';

                // Render clusters first
                if (data.clusters && data.clusters.length > 0) {
                    html += data.clusters.map(cluster => createClusterCard(cluster)).join('');
                }

                // Then render standalone articles
                if (data.articles && data.articles.length > 0) {
                    html += data.articles.map(article => createArticleCard(article)).join('');
                }

                if (html === '') {
                    html = '<div class="loading">No content found.</div>';
                }

                container.innerHTML = html;
            } catch (error) {
                console.error('Error loading feed:', error);
                document.getElementById('feed-container').innerHTML = '<div class="loading">Error loading feed.</div>';
            }
        }

        async function fetchNewsApi() {
            const statusEl = document.getElementById('newsapi-status');
            statusEl.textContent = 'Fetching 10 articles from NewsAPI.org...';
            try {
                const q = document.getElementById('newsapi-query').value || '';
                const resp = await fetch('/api/fetch-newsapi', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ limit: 10, q })
                });
                const data = await resp.json();
                if (data.success) {
                    statusEl.textContent = `Queued ${data.queued} articles (skipped ${data.skipped}).`;
                    loadFeed();
                } else {
                    statusEl.textContent = 'Error: ' + (data.error || 'Unknown error');
                }
            } catch (e) {
                statusEl.textContent = 'Fetch failed: ' + e;
            }
        }

        async function startAutoFetch() {
            const q = document.getElementById('newsapi-query').value || '';
            const resp = await fetch('/api/auto-fetch/start', {
                method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: q, interval_sec: 120 })
            });
            const data = await resp.json();
            document.getElementById('newsapi-status').textContent = data.success ? 'Auto-fetch started.' : ('Error: ' + (data.error || 'unknown'));
        }

        async function stopAutoFetch() {
            const resp = await fetch('/api/auto-fetch/stop', { method: 'POST' });
            const data = await resp.json();
            document.getElementById('newsapi-status').textContent = data.success ? 'Auto-fetch stopped.' : ('Error: ' + (data.error || 'unknown'));
        }

        function createClusterCard(cluster) {
            const articles = cluster.articles || [];
            const sourcesHtml = articles.map((article, index) => `
                <div class="cluster-source-item">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="flex: 1;">
                            <a href="${article.url}" target="_blank" style="color: #3182ce; text-decoration: none; font-weight: 500;">
                                ${article.source_domain || 'Unknown Source'}
                            </a>
                        </div>
                        <div style="font-size: 0.8rem; opacity: 0.8;">
                            📅 ${new Date(article.created_at).toLocaleDateString()}
                        </div>
                    </div>
                </div>
            `).join("");

            return `
                <div class="cluster-card">
                    <div class="cluster-header">
                        <h3>🔗 ${cluster.title}</h3>
                    </div>
                    <div class="cluster-excerpt">
                        ${cluster.summary}
                    </div>
                    <div class="cluster-sources-header">
                        <span>📚 ${articles.length} ${articles.length === 1 ? 'source' : 'sources'}</span>
                        <button class="cluster-toggle-btn" onclick="toggleClusterSources(this)" data-cluster-id="${cluster.cluster_id}">
                            ▶️ Expand
                        </button>
                    </div>
                    <div class="cluster-sources-content" id="sources-content-${cluster.cluster_id}" style="display: none;">
                        ${sourcesHtml}
                    </div>
                    <div style="margin-top: 16px; font-size: 0.8rem; opacity: 0.6; text-align: right;">
                        Created: ${new Date(cluster.created_at).toLocaleDateString()}
                    </div>
                </div>
            `;
        }

        function createArticleCard(article) {
            return `
                <div class="article-card">
                    <h3 style="margin-bottom: 12px; color: #2d3748;">${article.generated_title}</h3>
                    <div class="excerpt">${article.excerpt || 'No excerpt available'}</div>
                    <div class="article-meta">
                        <span>🌐 ${article.source_domain || 'Unknown'}</span>
                        <span>📅 ${new Date(article.created_at).toLocaleDateString()}</span>
                        <span>🔗 <a href="${article.url}" target="_blank" style="color: #3182ce; text-decoration: none; font-weight: 500;">View Original</a></span>
                        ${article.cluster_title ? `<span>📁 ${article.cluster_title}</span>` : ''}
                    </div>
                </div>
            `;
        }

        function toggleClusterSources(buttonElement) {
            const clusterId = buttonElement.getAttribute('data-cluster-id');
            const sourcesContent = document.getElementById(`sources-content-${clusterId}`);

            if (sourcesContent.style.display === 'none') {
                sourcesContent.style.display = 'block';
                buttonElement.textContent = '▼';
            } else {
                sourcesContent.style.display = 'none';
                buttonElement.textContent = '▶';
            }
        }

        // Handle form submission
        document.getElementById('article-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            const url = document.getElementById('url').value;

            try {
                const response = await fetch('/api/submit', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({url: url})
                });

                const data = await response.json();

                if (data.success) {
                    alert('Article submitted successfully!');
                    document.getElementById('url').value = '';
                    loadFeed(); // Refresh the feed
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                alert('Error submitting article: ' + error);
            }
        });

        // Initial load
        refreshStats();
        loadFeed();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Main web interface"""
    logger.info(f"🌐 Serving main web interface")
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/submit', methods=['POST'])
def submit_article():
    """Submit article for processing"""
    logger.info(f"📝 API: Article submission requested")
    
    try:
        data = request.get_json()
        url = data.get('url')

        if not url:
            logger.warning(f"⚠️ API: No URL provided")
            return jsonify({'success': False, 'error': 'URL is required'})

        # Submit article asynchronously
        article_id = asyncio.run(processor.submit_article(url))
        logger.info(f"✅ API: Article {article_id} submitted successfully")

        return jsonify({'success': True, 'article_id': article_id})
    except Exception as e:
        logger.error(f"❌ API: Error submitting article: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/status')
def get_status():
    """Get system status"""
    logger.debug(f"📊 API: Status requested")
    
    try:
        status = asyncio.run(processor.get_status())
        logger.debug(f"📊 API: Status retrieved successfully")
        return jsonify(status)
    except Exception as e:
        logger.error(f"❌ API: Error getting status: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/feed')
def get_feed():
    """Get clustered feed"""
    logger.debug(f"📚 API: Feed requested")
    
    try:
        import sqlite3

        # Get all clusters with their articles
        conn = sqlite3.connect(processor.db.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get all clusters
            cursor.execute('''
                SELECT c.*, COUNT(ac.article_id) as actual_count
                FROM clusters c
                LEFT JOIN article_clusters ac ON c.cluster_id = ac.cluster_id
                GROUP BY c.cluster_id
                ORDER BY c.created_at DESC
            ''')
            cluster_rows = cursor.fetchall()

            clusters = []
            for cluster_row in cluster_rows:
                cluster = dict(cluster_row)

                # Get articles in this cluster
                cursor.execute('''
                    SELECT a.*, ac.similarity_score
                    FROM articles a
                    JOIN article_clusters ac ON a.article_id = ac.article_id
                    WHERE ac.cluster_id = ? AND a.status = 'completed'
                    ORDER BY ac.similarity_score DESC
                ''', (cluster['cluster_id'],))

                articles_in_cluster = [dict(row) for row in cursor.fetchall()]
                cluster['articles'] = articles_in_cluster
                clusters.append(cluster)

            # Get standalone articles (not in any cluster)
            cursor.execute('''
                SELECT a.* FROM articles a
                WHERE a.status = 'completed' AND a.article_id NOT IN (
                    SELECT DISTINCT ac.article_id FROM article_clusters ac
                )
                ORDER BY a.created_at DESC
                LIMIT 20
            ''')
            standalone_articles = [dict(row) for row in cursor.fetchall()]

            logger.debug(f"📚 API: Feed retrieved - {len(clusters)} clusters, {len(standalone_articles)} standalone articles")
            return jsonify({
                'clusters': clusters,
                'articles': standalone_articles
            })
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"❌ API: Error getting feed: {e}")
        return jsonify({'clusters': [], 'articles': [], 'error': str(e)})

@app.route('/list')
def list_page():
    """Render the Articles List page with filter UI"""
    logger.info("🌐 Serving Articles List page")
    LIST_HTML = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Beacon 3 - Articles List</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f7fafc; margin:0; padding:20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; border-radius: 16px; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); margin-bottom: 24px; }
        .toolbar { display:flex; gap:8px; align-items:center; margin-bottom: 12px; }
        .btn { background: #2d3748; color:white; border:0; padding:8px 12px; border-radius:8px; cursor:pointer; font-size: 0.9rem; }
        select { padding:6px 10px; border:1px solid #cbd5e0; border-radius:8px; background:white; }
        table { width:100%; border-collapse: separate; border-spacing: 0; table-layout: fixed; }
        thead th { position: sticky; top: 0; background: #f0f4f8; border-bottom: 2px solid #cbd5e0; z-index: 1; text-transform: uppercase; font-size: 12px; letter-spacing: .02em; color:#2d3748; }
        th, td { text-align:left; padding: 10px 12px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
        tbody tr:nth-child(even) { background: #fbfdff; }
        tbody tr.failed { background: #fff5f5; }
        .badge { display:inline-block; padding:2px 8px; border-radius: 10px; font-weight:600; font-size:12px; }
        .badge-success { background:#c6f6d5; color:#22543d; }
        .badge-failed { background:#fed7d7; color:#742a2a; }
        .muted { color:#718096; font-size: 12px; }
        .nowrap { white-space: nowrap; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
        .truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .col-url { width: 360px; }
        .col-title { width: 340px; }
        .col-excerpt { width: 420px; }
        .table-wrap { max-height: 70vh; overflow: auto; border: 1px solid #e2e8f0; border-radius: 12px; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="card">
          <h2>📋 Articles List</h2>
          <div class="toolbar">
            <label for="status">Filter:</label>
            <select id="status" onchange="loadArticles()">
              <option value="all">All</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
            </select>
            <button class="btn" onclick="loadArticles()">Refresh</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style="width:70px">ID</th>
                  <th style="width:110px">Status</th>
                  <th class="col-url">URL</th>
                  <th class="col-title">Title</th>
                  <th class="col-excerpt">Excerpt</th>
                  <th style="width:160px">Created</th>
                  <th style="width:160px">Processed</th>
                  <th>Last Error</th>
                </tr>
              </thead>
              <tbody id="rows"><tr><td colspan="8" class="muted" style="padding:16px;">Loading...</td></tr></tbody>
            </table>
          </div>
        </div>
      </div>
      <script>
      async function loadArticles() {
        const status = document.getElementById('status').value;
        const res = await fetch(`/api/articles?status=${status}`);
        const data = await res.json();
        const rowsHtml = (data.articles || []).map(a => {
          const isSuccess = a.status === 'completed';
          const rowClass = isSuccess ? '' : 'failed';
          const title = (a.generated_title || a.original_title || '').trim();
          const excerpt = (a.excerpt || '').trim();
          const domain = a.source_domain || '';
          const lastErr = a.last_error || '';
          return `
            <tr class="${rowClass}">
              <td class="nowrap">${a.article_id}</td>
              <td>${isSuccess ? '<span class="badge badge-success">success</span>' : '<span class="badge badge-failed">failed</span>'}</td>
              <td>
                <div class="truncate"><a href="${a.url}" target="_blank">${a.url}</a></div>
                <div class="muted truncate">${domain}</div>
              </td>
              <td class="truncate" title="${title}">${title}</td>
              <td class="truncate" title="${excerpt}">${excerpt}</td>
              <td class="nowrap">${a.created_at || ''}</td>
              <td class="nowrap">${a.processed_at || ''}</td>
              <td class="truncate" title="${lastErr}">${lastErr}</td>
            </tr>`;
        }).join('');
        document.getElementById('rows').innerHTML = rowsHtml || `<tr><td colspan="8" class="muted" style="padding:16px;">No articles found.</td></tr>`;
      }
      loadArticles();
      </script>
    </body>
    </html>
    """
    return render_template_string(LIST_HTML)

@app.route('/api/articles')
def api_articles():
    """Return list of articles with optional status filter"""
    try:
        status = (request.args.get('status') or 'all').lower()
        status_map = {
            'success': 'completed',
            'failed': 'failed'
        }
        sql = "SELECT a.*,(SELECT error_message FROM processing_queue pq WHERE pq.article_id=a.article_id ORDER BY pq.created_at DESC LIMIT 1) as last_error FROM articles a"
        params = []
        if status in status_map:
            sql += " WHERE a.status = ?"
            params.append(status_map[status])
        sql += " ORDER BY a.created_at DESC LIMIT 200"  # simple cap

        import sqlite3
        conn = sqlite3.connect(processor.db.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        # Sanitize titles defensively for API output
        def sanitize_title(raw: str) -> str:
            if not raw:
                return ""
            text = str(raw).strip()
            text = re.sub(r'^\s*#{1,6}\s*', '', text)
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'^(title|headline)\s*[:\-]\s*', '', text, flags=re.IGNORECASE)
            text = text.strip().strip('"\'\u201c\u201d\u2018\u2019').strip('*').strip()
            return text
        articles = []
        for a in rows:
            a['generated_title'] = sanitize_title(a.get('generated_title') or a.get('original_title') or '')
            articles.append(a)
        conn.close()
        return jsonify({'articles': articles})
    except Exception as e:
        logger.error(f"❌ API: Error listing articles: {e}")
        return jsonify({'articles': [], 'error': str(e)}), 500

@app.route('/api/fetch-newsapi', methods=['POST'])
def fetch_newsapi():
    """Fetch up to 10 articles from NewsAPI.org and enqueue them"""
    logger.info("🛰️ API: Fetch NewsAPI requested")
    try:
        payload = request.get_json(silent=True) or {}
        limit = int(payload.get('limit', 10))
        limit = max(1, min(limit, 10))  # hard cap at 10 as requested
        query = (payload.get('q') or '').strip()

        if not NEWSAPI_KEY:
            return jsonify({'success': False, 'error': 'NEWSAPI_KEY not configured'}), 400

        # Build request: prefer everything endpoint with language=en; fallback to top-headlines
        params = {
            'language': 'en',
            'pageSize': limit,
        }
        url = 'https://newsapi.org/v2/top-headlines'
        if query:
            url = 'https://newsapi.org/v2/everything'
            params['q'] = query
            params['sortBy'] = 'publishedAt'
        headers = {'X-Api-Key': NEWSAPI_KEY}

        logger.info(f"🌐 NewsAPI request url={url} params={params}")
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if r.status_code != 200:
            logger.error(f"❌ NewsAPI error: HTTP {r.status_code} - {r.text[:200]}")
            return jsonify({'success': False, 'error': f'NewsAPI HTTP {r.status_code}'}), 502

        data = r.json()
        articles = data.get('articles') or []
        logger.info(f"📦 NewsAPI returned {len(articles)} articles")

        queued = 0
        skipped = 0
        import asyncio as _asyncio
        for a in articles:
            url = a.get('url')
            if not url:
                skipped += 1
                continue
            try:
                _asyncio.run(processor.submit_article(url))
                queued += 1
            except Exception as e:
                logger.warning(f"⚠️ Failed to enqueue {url}: {e}")
                skipped += 1

        logger.info(f"✅ NewsAPI fetch complete: queued={queued}, skipped={skipped}")
        return jsonify({'success': True, 'queued': queued, 'skipped': skipped})

    except Exception as e:
        logger.error(f"❌ API: Error fetching NewsAPI: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auto-fetch/start', methods=['POST'])
def api_auto_fetch_start():
    """Enable and start the systemd timer for auto-fetch (every 2 minutes)."""
    try:
        payload = request.get_json(silent=True) or {}
        query = (payload.get('query') or '').strip()
        # Write query to EnvironmentFile used by service
        try:
            with open('/etc/default/beacon3-autofetch', 'w') as f:
                f.write(f"NEWS_QUERY={query}\n")
        except Exception as e:
            logger.warning(f"⚠️ Could not write autofetch env: {e}")

        # Enable and start the timer (2-minute cadence defined in unit)
        subprocess.run(['systemctl', 'enable', '--now', 'beacon3-autofetch.timer'], check=False)
        # Kick a first run to avoid waiting the first interval
        subprocess.run(['systemctl', 'start', 'beacon3-autofetch.service'], check=False)

        # Report timer status
        status = subprocess.run(['systemctl', 'is-active', 'beacon3-autofetch.timer'], capture_output=True, text=True)
        return jsonify({'success': True, 'timer_active': status.stdout.strip()})
    except Exception as e:
        logger.error(f"❌ API: Auto-fetch start failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auto-fetch/stop', methods=['POST'])
def api_auto_fetch_stop():
    """Disable and stop the systemd timer for auto-fetch."""
    try:
        subprocess.run(['systemctl', 'disable', '--now', 'beacon3-autofetch.timer'], check=False)
        status = subprocess.run(['systemctl', 'is-active', 'beacon3-autofetch.timer'], capture_output=True, text=True)
        return jsonify({'success': True, 'timer_active': status.stdout.strip()})
    except Exception as e:
        logger.error(f"❌ API: Auto-fetch stop failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/start-processor', methods=['POST'])
def start_processor():
    """Start the continuous processor"""
    logger.info(f"🚀 API: Start processor requested")
    
    try:
        # Start processor in background (non-blocking)
        import threading

        def run_processor():
            logger.info(f"🚀 PROCESSOR-START: Background processor thread initializing")
            asyncio.run(processor.run_continuous_processor(max_articles=50))

        thread = threading.Thread(target=run_processor, daemon=True)
        thread.start()

        logger.info(f"✅ API: Processor started successfully")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"❌ API: Error starting processor: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stop-processor', methods=['POST'])
def stop_processor():
    """Stop the continuous processor"""
    logger.info(f"⏹️ API: Stop processor requested")
    
    try:
        processor.stop_processor()
        logger.info(f"✅ API: Processor stopped successfully")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"❌ API: Error stopping processor: {e}")
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)
