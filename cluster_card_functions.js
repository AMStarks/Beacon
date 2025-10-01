
        // Option 1: Single Cluster Card (Collapsed View)
        function createClusterCardOption1(cluster, articles) {
            const card = document.createElement('div');
            card.className = 'card cluster-card option-1';
            card.style.borderLeft = '5px solid #4CAF50';
            card.style.backgroundColor = '#f0f8f0';
            
            const mostRecent = articles[0];
            const identifierSets = articles.map(a => [a.identifier_1, a.identifier_2, a.identifier_3, a.identifier_4, a.identifier_5, a.identifier_6].filter(id => id));
            const commonIdentifiers = identifierSets[0].filter(id => identifierSets.every(set => set.includes(id)));
            
            card.innerHTML = `
                <div style="background: #4CAF50; color: white; padding: 10px; margin: -20px -20px 15px -20px; border-radius: 5px 5px 0 0;">
                    <h3 style="margin: 0;">🔗 CLUSTER OPTION 1: ${cluster.cluster_title || 'Related Articles'}</h3>
                    <small>${articles.length} Articles • Updated ${formatDate(new Date(cluster.updated_at))}</small>
                </div>
                <div class="article-excerpt">
                    <p>${cluster.cluster_summary || mostRecent.excerpt}</p>
                </div>
                <div style="margin: 15px 0; padding: 10px; background: white; border-radius: 5px;">
                    <h4 style="margin: 0 0 10px 0;">📰 Sources:</h4>
                    ${articles.map(a => `<div style="margin: 5px 0;">• ${a.source || 'Unknown'} (Article #${a.article_id}) - <a href="${a.url}" target="_blank">View</a></div>`).join('')}
                </div>
                <div class="identifiers">
                    <h4>🏷️ Common Identifiers:</h4>
                    <div class="identifier-tags">
                        ${commonIdentifiers.map(id => '<span class="tag">' + id + '</span>').join('')}
                    </div>
                </div>
                <button onclick="toggleCluster${cluster.cluster_id}()" style="width: 100%; padding: 10px; margin-top: 10px; background: #4CAF50; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    Expand Cluster ▼
                </button>
                <div id="cluster-details-${cluster.cluster_id}" style="display: none; margin-top: 15px; padding-top: 15px; border-top: 2px solid #4CAF50;">
                    ${articles.map(a => `
                        <div style="margin: 15px 0; padding: 15px; background: white; border: 1px solid #ddd; border-radius: 5px;">
                            <h3 style="margin: 0 0 10px 0;">${a.title}</h3>
                            <p style="margin: 5px 0;"><strong>Source:</strong> ${a.source || 'Unknown'} (Article #${a.article_id})</p>
                            <p>${a.excerpt}</p>
                            <a href="${a.url}" target="_blank" style="color: #4CAF50;">🔗 View Original</a>
                        </div>
                    `).join('')}
                </div>
            `;
            
            // Add toggle function
            window['toggleCluster' + cluster.cluster_id] = function() {
                const details = document.getElementById('cluster-details-' + cluster.cluster_id);
                const button = card.querySelector('button');
                if (details.style.display === 'none') {
                    details.style.display = 'block';
                    button.textContent = 'Collapse Cluster ▲';
                } else {
                    details.style.display = 'none';
                    button.textContent = 'Expand Cluster ▼';
                }
            };
            
            return card;
        }
        
        // Option 3: Hybrid Approach (Collapsed with Preview)
        function createClusterCardOption3(cluster, articles) {
            const card = document.createElement('div');
            card.className = 'card cluster-card option-3';
            card.style.borderLeft = '5px solid #2196F3';
            card.style.backgroundColor = '#f0f7ff';
            
            const primary = articles[0];
            const others = articles.slice(1);
            
            card.innerHTML = `
                <div style="background: #2196F3; color: white; padding: 10px; margin: -20px -20px 15px -20px; border-radius: 5px 5px 0 0;">
                    <h3 style="margin: 0;">🔗 CLUSTER OPTION 3: ${cluster.cluster_title || 'Related Articles'}</h3>
                </div>
                <h2>${primary.title}</h2>
                <div class="article-meta">
                    <span>🌐 ${primary.source || 'Unknown'}</span>
                    <span>🔗 <a href="${primary.url}" target="_blank">View Original</a></span>
                </div>
                <div class="article-excerpt">
                    <p>${primary.excerpt || 'No excerpt available'}</p>
                </div>
                <div class="article-info">
                    <p><strong>Article ID:</strong> ${primary.article_id}</p>
                </div>
                ${others.length > 0 ? `
                <div style="margin: 15px 0; padding: 15px; background: white; border-radius: 5px; border: 1px solid #2196F3;">
                    <h4 style="margin: 0 0 10px 0;">+${others.length} more source${others.length > 1 ? 's' : ''} covering this story:</h4>
                    ${others.map(a => `<div style="margin: 5px 0;">• ${a.source || 'Unknown'} (Article #${a.article_id})</div>`).join('')}
                    <button onclick="toggleSources${cluster.cluster_id}()" style="width: 100%; padding: 8px; margin-top: 10px; background: #2196F3; color: white; border: none; border-radius: 5px; cursor: pointer;">
                        View All Sources ▼
                    </button>
                    <div id="sources-details-${cluster.cluster_id}" style="display: none; margin-top: 10px;">
                        ${others.map(a => `
                            <div style="margin: 10px 0; padding: 10px; background: #f0f7ff; border-left: 3px solid #2196F3;">
                                <h4 style="margin: 0 0 5px 0;">${a.title}</h4>
                                <p style="margin: 5px 0; font-size: 0.9em;">${a.excerpt}</p>
                                <a href="${a.url}" target="_blank" style="color: #2196F3;">🔗 View Original</a>
                            </div>
                        `).join('')}
                    </div>
                </div>
                ` : ''}
                <div class="identifiers">
                    <h4>🏷️ Identifiers:</h4>
                    <div class="identifier-tags">
                        ${[primary.identifier_1, primary.identifier_2, primary.identifier_3, primary.identifier_4, primary.identifier_5, primary.identifier_6].filter(id => id).map(id => '<span class="tag">' + id + '</span>').join('')}
                    </div>
                </div>
            `;
            
            // Add toggle function for sources
            window['toggleSources' + cluster.cluster_id] = function() {
                const details = document.getElementById('sources-details-' + cluster.cluster_id);
                const button = card.querySelector('button');
                if (details && button) {
                    if (details.style.display === 'none') {
                        details.style.display = 'block';
                        button.textContent = 'Hide Sources ▲';
                    } else {
                        details.style.display = 'none';
                        button.textContent = 'View All Sources ▼';
                    }
                }
            };
            
            return card;
        }

