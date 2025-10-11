#!/usr/bin/env python3
"""
Beacon 3 Web Interface - Flask API for article submission and monitoring
"""

import asyncio
import logging
from flask import Flask, request, jsonify, render_template_string
from .article_processor import ArticleProcessor
from .cluster_audit import ClusterAuditService
import os
import requests
import json
import subprocess

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global processor instance
processor = ArticleProcessor()
auditor = ClusterAuditService(processor.db)
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "d69a3b23cad345b898a6ee4d6303c69b")

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
        .feed-grid { display:grid; grid-template-columns: 1fr; gap: 20px; }
        @media (min-width: 900px) { .feed-grid { grid-template-columns: 1fr 1fr; } }
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
            <h2>⚙️ Trial Automation: Fetch 10 from NewsAPI.org</h2>
            <div class="form-group">
                <label for="newsapi-query">Query (optional):</label>
                <input type="text" id="newsapi-query" placeholder="e.g., digital id OR uk">
            </div>
            <button class="btn" onclick="fetchNewsApi()">📥 Fetch 10 Articles</button>
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

                container.innerHTML = `<div class="feed-grid">${html}</div>`;
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

        function leanBadge(lean, confidence){
            // Accepts lean as -1, 0, 1 or a float in [-1,1]. Confidence in [0,1].
            const colors = { '-1':'#93c5fd', '0':'#fde68a', '1':'#fecaca', 'null':'#e5e7eb' };
            let discrete = null;
            if (lean === -1 || lean === 0 || lean === 1) {
                discrete = lean;
            } else if (typeof lean === 'number') {
                if (lean <= -0.33) discrete = -1; else if (lean >= 0.33) discrete = 1; else discrete = 0;
            }
            const key = (discrete===-1||discrete===0||discrete===1)? String(discrete): 'null';
            const color = colors[key];
            const label = key==='-1'?'Left': key==='0'?'Center': key==='1'?'Right':'Unknown';
            let opacity = 1.0;
            let dashed = '';
            if (typeof confidence === 'number') {
                const c = Math.max(0, Math.min(1, confidence));
                opacity = 0.4 + 0.6 * c; // 0.4..1.0
                if (c < 0.5) dashed = 'border:1px dashed rgba(0,0,0,0.25);';
            }
            const title = (typeof confidence === 'number') ? `${label} (${confidence.toFixed(2)})` : label;
            return `<span title="${title}" style="display:inline-flex;align-items:center;gap:6px;font-size:.85rem;">
                <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${color};opacity:${opacity};border:1px solid rgba(0,0,0,.04);${dashed}"></span>${label}
            </span>`;
        }

        function mixBar(left, center, right){
            const l = left||0, c = center||0, r = right||0;
            const total = l + c + r;
            if (!total || total <= 1) return '';
            const p = (x) => `${(100 * x / total).toFixed(1)}%`;
            const title = `Left ${l} • Center ${c} • Right ${r}`;
            return `<span title="${title}" style="display:inline-flex;align-items:center;gap:8px;">
                <span style="display:inline-flex;width:80px;height:6px;border-radius:4px;overflow:hidden;border:1px solid rgba(0,0,0,0.06);background:#f1f5f9;">
                    <span style="display:inline-block;background:#93c5fd;width:${p(l)};"></span>
                    <span style="display:inline-block;background:#fde68a;width:${p(c)};"></span>
                    <span style="display:inline-block;background:#fecaca;width:${p(r)};"></span>
                </span>
            </span>`;
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
                        <span style="display:flex;align-items:center;gap:12px;">${leanBadge(cluster.cluster_lean, null)} ${mixBar(cluster.lean_left, cluster.lean_center, cluster.lean_right)}</span>
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
            const bias = leanBadge(article.source_lean, article.source_confidence);
            return `
                <div class="article-card">
                    <h3 style="margin-bottom: 12px; color: #2d3748;">${article.generated_title}</h3>
                    <div class="excerpt">${article.excerpt || 'No excerpt available'}</div>
                    <div class="article-meta">
                        <span>🌐 ${article.source_domain || 'Unknown'} ${bias}</span>
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
                ORDER BY datetime(c.created_at) DESC
            ''')
            cluster_rows = cursor.fetchall()

            # Load source bias map
            import json, os
            bias_path = '/root/beacon3/source_bias.json'
            bias_map = {}
            try:
                if os.path.exists(bias_path):
                    with open(bias_path, 'r') as bf:
                        bias_map = json.load(bf)
            except Exception:
                bias_map = {}

            def bias_for(domain: str):
                d = (domain or '').lower()
                if not d:
                    return None, None
                info = bias_map.get(d) or bias_map.get(d.lstrip('www.')) or bias_map.get('www.' + d) or {}
                return info.get('lean'), info.get('confidence')

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
                # Attach bias to each article and compute cluster lean mix
                left = center = right = 0
                leans = []
                for art in articles_in_cluster:
                    lean, conf = bias_for(art.get('source_domain'))
                    art['source_lean'] = lean
                    art['source_confidence'] = conf
                    if lean == -1:
                        left += 1
                    elif lean == 0:
                        center += 1
                    elif lean == 1:
                        right += 1
                    if lean is not None and conf:
                        leans.append((lean, float(conf)))
                if leans:
                    num = sum(l * c for l, c in leans)
                    den = sum(c for _, c in leans) or 1.0
                    cluster_lean = num / den
                else:
                    cluster_lean = None
                cluster['lean_left'] = left
                cluster['lean_center'] = center
                cluster['lean_right'] = right
                cluster['cluster_lean'] = cluster_lean
                cluster['articles'] = articles_in_cluster
                clusters.append(cluster)

            # Get standalone articles (not in any cluster)
            cursor.execute('''
                SELECT a.* FROM articles a
                WHERE a.status = 'completed' AND a.article_id NOT IN (
                    SELECT DISTINCT ac.article_id FROM article_clusters ac
                )
                ORDER BY datetime(a.created_at) DESC
                LIMIT 20
            ''')
            standalone_articles = [dict(row) for row in cursor.fetchall()]
            for art in standalone_articles:
                lean, conf = bias_for(art.get('source_domain'))
                art['source_lean'] = lean
                art['source_confidence'] = conf

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
        .btn { background: #2d3748; color:white; border:0; padding:8px 14px; border-radius:8px; cursor:pointer; }
        .filter { margin-bottom: 16px; }
        table { width:100%; border-collapse: collapse; }
        th, td { text-align:left; padding: 10px 8px; border-bottom: 1px solid #e2e8f0; vertical-align: top; }
        .status-success { color: #2f855a; font-weight: 600; }
        .status-failed { color: #c53030; font-weight: 600; }
        .muted { color:#718096; font-size: 0.9rem; }
        .nowrap { white-space: nowrap; }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="card">
          <h2>📋 Articles List</h2>
          <div class="filter">
            <label for="status">Filter:</label>
            <select id="status" onchange="loadArticles()">
              <option value="all">All</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
            </select>
            <button class="btn" onclick="loadArticles()">Refresh</button>
          </div>
          <div id="table-container">Loading...</div>
        </div>
      </div>
      <script>
      async function loadArticles() {
        const status = document.getElementById('status').value;
        const res = await fetch(`/api/articles?status=${status}`);
        const data = await res.json();
        const rows = (data.articles || []).map(a => `
          <tr>
            <td class="nowrap">${a.article_id}</td>
            <td>${a.status === 'completed' ? '<span class=\"status-success\">success</span>' : '<span class=\"status-failed\">failed</span>'}</td>
            <td><a href="${a.url}" target="_blank">${a.url}</a><div class="muted">${a.source_domain || ''}</div></td>
            <td>${(a.generated_title || '').slice(0,120)}</td>
            <td>${(a.excerpt || '').slice(0,160)}</td>
            <td class="nowrap">${a.created_at || ''}</td>
            <td class="nowrap">${a.processed_at || ''}</td>
            <td>${a.last_error || ''}</td>
          </tr>
        `).join('');
        const html = `
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Status</th><th>URL</th><th>Title</th><th>Excerpt</th><th>Created</th><th>Processed</th><th>Last Error</th>
              </tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>`;
        document.getElementById('table-container').innerHTML = html;
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
        articles = [dict(r) for r in cur.fetchall()]
        conn.close()
        return jsonify({'articles': articles})
    except Exception as e:
        logger.error(f"❌ API: Error listing articles: {e}")
        return jsonify({'articles': [], 'error': str(e)}), 500

@app.route('/admin')
def admin_page():
    """Render Admin Panel"""
    logger.info("🌐 Serving Admin Panel")
    ADMIN_HTML = """
    <!DOCTYPE html>
    <html lang=\"en\">
    <head>
      <meta charset=\"UTF-8\">
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
      <title>Beacon 3 - Admin</title>
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f7fafc; margin:0; padding:20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .grid { display: grid; grid-template-columns: 1fr; gap: 24px; }
        @media (min-width: 900px) { .grid { grid-template-columns: 1fr 1fr; } }
        .card { background: white; border-radius: 16px; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.08); }
        .btn { background: #2d3748; color:white; border:0; padding:10px 14px; border-radius:8px; cursor:pointer; margin-right:8px; }
        .btn.secondary { background:#4a5568; }
        .muted { color:#718096; }
        textarea { width:100%; min-height: 360px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.95rem; padding:12px; border:1px solid #e2e8f0; border-radius: 8px; }
        pre { background:#f7fafc; border-radius:8px; padding:12px; }
        .row { display:flex; gap:10px; align-items:center; flex-wrap: wrap; }
      </style>
    </head>
    <body>
      <div class=\"container\">
        <h1>🛠️ Admin Panel</h1>
        <div class=\"grid\">
          <div class=\"card\">
            <h2>System Controls</h2>
            <div id=\"stats\" class=\"muted\">Loading status...</div>
            <div class=\"row\" style=\"margin-top:12px;\">
              <button class=\"btn\" onclick=\"startProc()\">Start Processor</button>
              <button class=\"btn secondary\" onclick=\"stopProc()\">Stop Processor</button>
              <button class=\"btn\" onclick=\"triggerRss()\">Trigger RSS Now</button>
              <button class=\"btn secondary\" onclick=\"refreshStatus()\">Refresh Status</button>
            </div>
            <div style=\"margin-top:12px;\" class=\"muted\">Tip: RSS also runs every 15 minutes via systemd timer.</div>
          </div>
          <div class=\"card\">
            <h2>Source Bias Map</h2>
            <div class=\"muted\">Edit JSON mapping of domains → { lean: -1|0|1, confidence: 0..1 }.</div>
            <textarea id=\"biasText\" placeholder=\"{\n  \"example.com\": { \"lean\": 0, \"confidence\": 0.6 }\n}\"></textarea>
            <div class=\"row\" style=\"margin-top:10px;\">
              <button class=\"btn\" onclick=\"saveBias()\">Save</button>
              <span id=\"biasStatus\" class=\"muted\"></span>
            </div>
          </div>
        </div>
        <div class=\"card\" style=\"margin-top:24px;\">
          <h2>Quick Links</h2>
          <div class=\"row\">
            <a class=\"btn secondary\" href=\"/\">Main UI</a>
            <a class=\"btn secondary\" href=\"/list\">Articles List</a>
          </div>
        </div>
      </div>
      <script>
      async function refreshStatus(){
        const r = await fetch('/api/status');
        const d = await r.json();
        const isRun = d.is_running ? 'RUNNING' : 'STOPPED';
        document.getElementById('stats').innerHTML = `
          <div><b>Processor:</b> ${isRun}</div>
          <div><b>Total Articles:</b> ${d.stats.total_articles} &nbsp; <b>Completed:</b> ${d.stats.completed_articles} &nbsp; <b>Failed:</b> ${d.stats.failed_articles}</div>
          <div><b>Clusters:</b> ${d.stats.total_clusters} &nbsp; <b>In Queue:</b> ${d.stats.queued_items}</div>
        `;
      }
      async function startProc(){ await fetch('/api/start-processor', {method:'POST'}); refreshStatus(); }
      async function stopProc(){ await fetch('/api/stop-processor', {method:'POST'}); refreshStatus(); }
      async function triggerRss(){
        const r = await fetch('/api/trigger-rss', {method:'POST'});
        const d = await r.json();
        alert(d.success ? 'RSS fetch triggered.' : ('Failed: ' + (d.error||'unknown')));
      }
      async function loadBias(){
        const r = await fetch('/api/bias-map');
        const d = await r.json();
        const text = JSON.stringify(d.bias_map || {}, null, 2);
        document.getElementById('biasText').value = text;
      }
      async function saveBias(){
        const el = document.getElementById('biasText');
        try {
          const obj = JSON.parse(el.value);
          const r = await fetch('/api/bias-map', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ bias_map: obj }) });
          const d = await r.json();
          document.getElementById('biasStatus').textContent = d.success ? 'Saved.' : ('Error: ' + (d.error||'unknown'));
        } catch(e){
          document.getElementById('biasStatus').textContent = 'Invalid JSON: ' + e;
        }
      }
      refreshStatus();
      loadBias();
      </script>
    </body>
    </html>
    """
    return render_template_string(ADMIN_HTML)

@app.route('/api/bias-map', methods=['GET', 'POST'])
def api_bias_map():
    """Get or update the source bias map JSON"""
    bias_path = '/root/beacon3/source_bias.json'
    try:
        if request.method == 'GET':
            data = {}
            try:
                if os.path.exists(bias_path):
                    with open(bias_path, 'r') as f:
                        data = json.load(f)
            except Exception as e:
                logger.warning(f"⚠️ Failed reading bias map: {e}")
                data = {}
            return jsonify({'success': True, 'bias_map': data, 'path': bias_path})

        payload = request.get_json(silent=True) or {}
        bias_map = payload.get('bias_map')
        if not isinstance(bias_map, dict):
            return jsonify({'success': False, 'error': 'bias_map must be an object'}), 400
        tmp_path = bias_path + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump(bias_map, f, indent=2, sort_keys=True)
        os.replace(tmp_path, bias_path)
        logger.info("✅ Bias map updated")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"❌ API: Error handling bias map: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/trigger-rss', methods=['POST'])
def api_trigger_rss():
    """Trigger a one-shot RSS fetch in the background"""
    try:
        script = '/root/beacon3/beacon3_rss_fetcher_once.py'
        if not os.path.exists(script):
            return jsonify({'success': False, 'error': 'RSS script not found'}), 404
        subprocess.Popen(['/usr/bin/python3', script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        logger.info("🚀 Triggered RSS fetcher once")
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"❌ API: trigger RSS failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

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

@app.route('/api/start-processor', methods=['POST'])
def start_processor():
    """Start the continuous processor"""
    logger.info(f"🚀 API: Start processor requested")

    try:
        # Parse optional parameters
        payload = request.get_json(silent=True) or {}
        max_articles = int(payload.get('max_articles', 500))
        try:
            per_article_delay_seconds = float(payload.get('per_article_delay_seconds', 1.0))
        except Exception:
            per_article_delay_seconds = 1.0

        # Start processor in background (non-blocking)
        import threading

        def run_processor():
            logger.info(f"🚀 PROCESSOR-START: Background processor thread initializing (max_articles={max_articles}, delay={per_article_delay_seconds}s)")
            try:
                # Create new event loop for the processor
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    processor.run_continuous_processor(
                        max_articles=max_articles,
                        per_article_delay_seconds=per_article_delay_seconds,
                    )
                )
            except Exception as e:
                logger.error(f"❌ PROCESSOR-THREAD: Error in processor loop: {e}")
            finally:
                loop.close()

        thread = threading.Thread(target=run_processor, daemon=True)
        thread.start()

        logger.info(f"✅ API: Processor started successfully")
        return jsonify({'success': True, 'max_articles': max_articles, 'per_article_delay_seconds': per_article_delay_seconds})
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

@app.route('/api/cluster-audit/run', methods=['POST'])
def api_cluster_audit_run():
    """Run a batch cluster audit and return results"""
    try:
        payload = request.get_json(silent=True) or {}
        limit = int(payload.get('limit', 50))
        results = auditor.evaluate_clusters_batch(limit=limit)
        return jsonify({'success': True, 'results': results})
    except Exception as e:
        logger.error(f"❌ API: cluster audit failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cluster-audit/singletons', methods=['GET'])
def api_cluster_audit_singletons():
    """Suggest merges for singleton articles"""
    try:
        limit = int(request.args.get('limit', 50))
        suggestions = auditor.singleton_merge_candidates(limit=limit)
        return jsonify({'success': True, 'suggestions': suggestions})
    except Exception as e:
        logger.error(f"❌ API: singleton suggestions failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cluster-audit/params/propose', methods=['POST'])
def api_cluster_audit_params_propose():
    """Propose clustering parameter adjustments based on recent evaluations"""
    try:
        params = auditor.propose_param_adjustments()
        return jsonify({'success': True, 'params': params})
    except Exception as e:
        logger.error(f"❌ API: propose params failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/routes', methods=['GET'])
def api_routes():
    """List registered routes for debugging"""
    try:
        routes = [str(r) for r in app.url_map.iter_rules()]
        return jsonify({'success': True, 'routes': routes})
    except Exception as e:
        logger.error(f"❌ API: routes listing failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rebuild-cluster-summaries', methods=['POST'])
def rebuild_cluster_summaries():
    """Rebuild summaries for recent clusters using sanitized text from top members"""
    try:
        import sqlite3, re
        conn = sqlite3.connect(processor.db.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # Get recent clusters
        cur.execute('SELECT cluster_id FROM clusters ORDER BY datetime(created_at) DESC LIMIT 20')
        cluster_ids = [r['cluster_id'] for r in cur.fetchall()]

        def sanitize(text: str) -> str:
            if not text:
                return ''
            text = re.sub(r"```[\s\S]*?```", " ", text)
            text = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", text)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\{[^}]*\}", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text

        rebuilt = 0
        for cid in cluster_ids:
            cur.execute('''
                SELECT a.generated_title, a.excerpt, a.content
                FROM articles a
                JOIN article_clusters ac ON a.article_id = ac.article_id
                WHERE ac.cluster_id = ? AND a.status = 'completed'
                ORDER BY ac.similarity_score DESC
                LIMIT 3
            ''', (cid,))
            arts = cur.fetchall()
            if not arts:
                continue
            parts = []
            for a in arts:
                parts.append(sanitize((a['generated_title'] or '') + ' ' + (a['excerpt'] or '') + ' ' + ((a['content'] or '')[:800])))
            combined = ' '.join(p for p in parts if p)
            if not combined:
                continue
            # Create a simple summary: first ~100 words
            words = combined.split()
            summary = ' '.join(words[:100])
            if not summary.endswith('.'):
                summary += '.'
            cur.execute('UPDATE clusters SET summary = ?, updated_at = CURRENT_TIMESTAMP WHERE cluster_id = ?', (summary, cid))
            rebuilt += 1
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'rebuilt': rebuilt})
    except Exception as e:
        logger.error(f"❌ API: rebuild cluster summaries failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/revalidate-clusters', methods=['POST'])
def revalidate_clusters():
    """Prune mismatched cluster members using stricter gates (title/jaccard/time)."""
    try:
        import sqlite3, re, difflib
        from datetime import datetime

        def norm_tokens(s_: str) -> set:
            t = re.sub(r'[^A-Za-z0-9\s]', ' ', (s_ or '').lower())
            stop = {
                'the','and','for','with','that','this','from','have','has','are','was','were','will','into','over','under','after','before','about',
                'your','their','them','they','you','our','but','not','out','his','her','its','had','who','what','when','where','why','how'
            }
            return set(w for w in t.split() if len(w) >= 3 and w not in stop)

        def parse_dt(x: str):
            try:
                return datetime.fromisoformat((x or '').replace('Z', '+00:00'))
            except Exception:
                return None

        conn = sqlite3.connect(processor.db.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute('SELECT cluster_id FROM clusters ORDER BY datetime(updated_at) DESC, datetime(created_at) DESC LIMIT 20')
        clusters = [r['cluster_id'] for r in cur.fetchall()]

        removed = 0
        checked = 0
        for cid in clusters:
            cur.execute('''
                SELECT a.* , ac.similarity_score
                FROM articles a
                JOIN article_clusters ac ON a.article_id = ac.article_id
                WHERE ac.cluster_id = ? AND a.status IN ('completed','processing')
                ORDER BY ac.similarity_score DESC
            ''', (cid,))
            rows = [dict(r) for r in cur.fetchall()]
            if not rows:
                continue
            base = rows[0]
            base_title = (base.get('generated_title') or base.get('original_title') or '')
            base_excerpt = base.get('excerpt') or ''
            bdt = parse_dt(base.get('created_at'))
            base_tok = norm_tokens(base_title + ' ' + base_excerpt)

            for cand in rows[1:]:
                checked += 1
                cand_title = (cand.get('generated_title') or cand.get('original_title') or '')
                cand_excerpt = cand.get('excerpt') or ''
                cdt = parse_dt(cand.get('created_at'))
                title_sim = difflib.SequenceMatcher(None, base_title.lower(), cand_title.lower()).ratio() if base_title and cand_title else 0.0
                cand_tok = norm_tokens(cand_title + ' ' + cand_excerpt)
                inter = base_tok & cand_tok
                union = base_tok | cand_tok
                jacc = (len(inter) / len(union)) if union else 0.0
                time_ok = (bdt is not None and cdt is not None and abs((bdt - cdt).total_seconds())/3600.0 <= 72)
                strong = (1 if title_sim >= 0.70 else 0) + (1 if jacc >= 0.33 else 0) + (1 if time_ok else 0)
                if strong < 2:
                    cur.execute('DELETE FROM article_clusters WHERE cluster_id = ? AND article_id = ?', (cid, cand['article_id']))
                    removed += 1
            # refresh article_count
            cur.execute('''
                UPDATE clusters SET article_count = (SELECT COUNT(*) FROM article_clusters WHERE cluster_id = ?), updated_at = CURRENT_TIMESTAMP WHERE cluster_id = ?
            ''', (cid, cid))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'checked': checked, 'removed': removed})
    except Exception as e:
        logger.error(f"❌ API: revalidate clusters failed: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5005, debug=True)
