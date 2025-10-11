#!/usr/bin/env python3
"""
Beacon 2 Web Interface - Simple Flask API for article submission and monitoring
"""

import asyncio
import logging
from flask import Flask, request, jsonify, render_template_string
from ..core.article_processor import ArticleProcessor

# Initialize logging configuration
try:
    from ..logging_config import setup_logging
    setup_logging(level=logging.DEBUG)  # Enable debug logging for troubleshooting
    print("✅ Logging initialized in Beacon 2 API (DEBUG level)")
except Exception as e:
    print(f"⚠️ Logging initialization failed: {e}")
    # Proceed without fallback to avoid mixed formatting

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Global processor instance
processor = ArticleProcessor()

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Beacon 2 - AI News Desk</title>
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

        /* Enhanced Card System */
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

        /* New cluster card structure styles */
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

        /* Link styling */
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

        /* Responsive Design */
        @media (max-width: 768px) {
            .container {
                padding: 10px;
            }
            .header h1 {
                font-size: 2rem;
            }
            .stats-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 12px;
            }
            .article-card, .cluster-card {
                padding: 16px;
            }
            .cluster-header {
                flex-direction: column;
                align-items: flex-start;
                gap: 8px;
            }
            .article-meta {
                flex-direction: column;
                gap: 8px;
            }
        }

        @media (max-width: 480px) {
            .stats-grid {
                grid-template-columns: 1fr;
            }
            .header h1 {
                font-size: 1.8rem;
            }
            .btn {
                padding: 10px 16px;
                font-size: 0.9rem;
            }
        }

        /* Enhanced Visual Elements */
        .cluster-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #4a5568 0%, #2d3748 100%);
            border-radius: 16px 16px 0 0;
        }

        .article-card::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            width: 5px;
            background: linear-gradient(180deg, #4a5568 0%, #2d3748 100%);
            border-radius: 16px 0 0 16px;
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
            <h1>🔍 Beacon 2 - AI News Desk</h1>
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

        function toggleCluster(headerElement) {
            const clusterCard = headerElement.closest('.cluster-card');
            const sourcesDiv = clusterCard.querySelector('.cluster-sources');
            const toggleButton = headerElement.querySelector('.cluster-toggle');

            if (sourcesDiv.style.display === 'none') {
                sourcesDiv.style.display = 'block';
                toggleButton.textContent = '−';
            } else {
                sourcesDiv.style.display = 'none';
                toggleButton.textContent = '+';
            }
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
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/submit', methods=['POST'])
def submit_article():
    """Submit article for processing"""
    try:
        data = request.get_json()
        url = data.get('url')

        if not url:
            return jsonify({'success': False, 'error': 'URL is required'})

        # Submit article asynchronously
        article_id = asyncio.run(processor.submit_article(url))

        return jsonify({'success': True, 'article_id': article_id})
    except Exception as e:
        logger.error(f"Error submitting article: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/status')
def get_status():
    """Get system status"""
    try:
        status = asyncio.run(processor.get_status())
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/feed')
def get_feed():
    """Get clustered feed"""
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
                    WHERE ac.cluster_id = ?
                    ORDER BY ac.similarity_score DESC
                ''', (cluster['cluster_id'],))

                articles_in_cluster = [dict(row) for row in cursor.fetchall()]
                cluster['articles'] = articles_in_cluster
                clusters.append(cluster)

            # Get standalone articles (not in any cluster)
            cursor.execute('''
                SELECT a.* FROM articles a
                WHERE a.article_id NOT IN (
                    SELECT DISTINCT ac.article_id FROM article_clusters ac
                )
                ORDER BY a.created_at DESC
                LIMIT 20
            ''')
            standalone_articles = [dict(row) for row in cursor.fetchall()]

            return jsonify({
                'clusters': clusters,
                'articles': standalone_articles
            })
        finally:
            conn.close()

    except Exception as e:
        logger.error(f"Error getting feed: {e}")
        return jsonify({'clusters': [], 'articles': [], 'error': str(e)})

@app.route('/api/start-processor', methods=['POST'])
def start_processor():
    """Start the continuous processor"""
    try:
        # Ensure logging is initialized at click time
        try:
            from ..logging_config import setup_logging
            setup_logging()
        except Exception:
            pass

        logger.info("🟢 API: start-processor requested")

        # Start processor in background (non-blocking)
        import threading

        def run_processor():
            # Ensure logging also initialized in thread context
            try:
                from ..logging_config import setup_logging
                setup_logging()
            except Exception:
                pass
            logger.info("🚀 PROCESSOR-START: Background processor thread initializing")
            asyncio.run(processor.run_continuous_processor(max_articles=50))

        thread = threading.Thread(target=run_processor, daemon=True)
        thread.start()

        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error starting processor: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/stop-processor', methods=['POST'])
def stop_processor():
    """Stop the continuous processor"""
    try:
        processor.stop_processor()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error stopping processor: {e}")
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
