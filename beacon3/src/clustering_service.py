#!/usr/bin/env python3
"""
Beacon 3 Clustering Service - TF-IDF similarity without LLM
"""

import logging
import re
import difflib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.decomposition import LatentDirichletAllocation
import numpy as np
import spacy

logger = logging.getLogger(__name__)

class ClusteringService:
    """TF-IDF based clustering without LLM dependency"""

    def __init__(self, db):
        self.db = db
        self.vectorizer = TfidfVectorizer(
            max_features=2000,  # Increased for better feature capture
            stop_words='english',
            ngram_range=(1, 3),  # Extended to 3-grams for better context
            min_df=1,
            max_df=0.95
        )
        self.similarity_threshold = 0.08  # Much more permissive baseline for news articles
        self.lda_model = None
        self.nlp = None
        self._load_nlp_model()

    def calculate_similarity(self, text1: str, text2: str, weights: Optional[Dict[str, float]] = None) -> float:
        """Calculate enhanced similarity using multiple methods with optional dynamic weights"""
        logger.debug(f"🔍 Calculating enhanced similarity between texts")
        
        if not text1 or not text2:
            return 0.0
        
        try:
            # Normalize texts
            text1 = self._normalize_text(text1)
            text2 = self._normalize_text(text2)
            
            # 1. TF-IDF cosine similarity (base method)
            tfidf_matrix = self.vectorizer.fit_transform([text1, text2])
            tfidf_similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            # 2. Semantic similarity (if spaCy available)
            semantic_similarity = self._calculate_semantic_similarity(text1, text2)
            
            # 3. Location similarity
            location_similarity = self._calculate_location_similarity(text1, text2)
            
            # 4. Event similarity
            event_similarity = self._calculate_event_similarity(text1, text2)
            
            # Weighted combination (semantic removed - no word vectors in small model)
            default_weights = {
                'tfidf': 0.6,
                'semantic': 0.0,  # Keep disabled for sm model
                'location': 0.25,
                'event': 0.15
            }
            w = weights or default_weights
            
            final_similarity = (
                w['tfidf'] * tfidf_similarity +
                w['semantic'] * semantic_similarity +
                w['location'] * location_similarity +
                w['event'] * event_similarity
            )
            
            logger.debug(f"📊 Similarity scores - TF-IDF: {tfidf_similarity:.4f}, Semantic: {semantic_similarity:.4f}, Location: {location_similarity:.4f}, Event: {event_similarity:.4f}")
            logger.debug(f"📊 Final weighted similarity: {final_similarity:.4f}")
            
            return final_similarity
            
        except Exception as e:
            logger.error(f"❌ Enhanced similarity calculation failed: {e}")
            return 0.0

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text

    def _story_signature(self, title: str, excerpt: str) -> set:
        """Generate a deterministic story signature: title 3-grams + key entities + salient tokens.

        This is used for corroboration gating prior to clustering.
        """
        import re
        normalized_title = self._normalize_text(title or "")
        normalized_excerpt = self._normalize_text(excerpt or "")
        text = f"{normalized_title} {normalized_excerpt}".strip()

        # 3-grams from title dominate; fallback to bigrams if short
        words = [w for w in text.split() if len(w) >= 3]
        n = 3 if len(words) >= 3 else 2
        grams = set()
        for i in range(len(words) - n + 1):
            grams.add(' '.join(words[i:i+n]))

        ents = set()
        if self.nlp and (title or excerpt):
            try:
                doc = self.nlp((title or "") + " " + (excerpt or ""))
                for ent in doc.ents:
                    if ent.label_ in ('GPE','ORG','EVENT'):
                        ents.add(self._normalize_geo_name(ent.text))
            except Exception:
                pass
        else:
            # fallback: simple capitalized sequences (2-3 tokens)
            cap = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", (title or "") + " " + (excerpt or ""))
            ents.update(self._normalize_geo_name(c) for c in cap)

        # Salient single tokens from title
        salient = set(words[:6])
        signature = grams | ents | salient
        return set(s for s in signature if s)

    async def find_similar_articles(self, article_id: int, content: str) -> List[Tuple[int, float]]:
        """Find similar articles using similarity with dynamic weights per inferred article type"""
        logger.info(f"🔍 Finding similar articles for article {article_id}")
        
        try:
            # Get recent articles
            logger.debug(f"📋 Getting recent articles for comparison")
            recent_articles = self.db.get_recent_articles(150, include_processing=True)
            logger.info(f"📋 Found {len(recent_articles)} recent articles")
            
            # Infer article type for the current article to pick weights/threshold
            inferred_type = self._infer_article_type(content)
            weights, threshold = self._get_weights_and_threshold(inferred_type)
            logger.info(f"🧭 Inferred article type for {article_id}: {inferred_type} | weights={weights} | threshold={threshold}")

            # Base article context for conservative gating
            base_article = self.db.get_article(article_id) or {}
            base_title = (base_article.get('generated_title') or base_article.get('original_title') or '')
            base_excerpt = base_article.get('excerpt', '')
            base_created = base_article.get('created_at')
            base_domain = (base_article.get('source_domain') or '').lower()
            base_sig = self._story_signature(base_title, base_excerpt)

            def _norm_tokens(s_: str) -> set:
                t = re.sub(r'[^A-Za-z0-9\s]', ' ', (s_ or '').lower())
                stop = {
                    'the','and','for','with','that','this','from','have','has','are','was','were','will','into','over','under','after','before','about',
                    'your','their','them','they','you','our','but','not','out','his','her','its','had','who','what','when','where','why','how'
                }
                return set(w for w in t.split() if len(w) >= 3 and w not in stop)

            similar = []
            
            for article in recent_articles:
                if article['article_id'] == article_id:
                    logger.debug(f"⏭️ Skipping self (article {article_id})")
                    continue
                
                # Prepare content for comparison
                existing_content = self._prepare_content_for_comparison(article)
                
                if not existing_content.strip():
                    logger.debug(f"⚠️ Article {article['article_id']} has no processable content")
                    continue
                
                # Calculate similarity
                logger.debug(f"⚖️ Calculating similarity with article {article['article_id']} | type={inferred_type} | weights={weights} | threshold={threshold}")
                similarity = self.calculate_similarity(content, existing_content, weights=weights)
                # Policy topic boost (non-semantic, lexical)
                if inferred_type == 'policy':
                    boost = self._topic_boost_policy(content, existing_content)
                    if boost:
                        logger.debug(f"➕ Applying policy topic boost: +{boost:.3f}")
                        similarity += boost
                
                # Conservative gates before accepting similarity: title, tokens, time, simple-entity proxy
                cand_title = (article.get('generated_title') or article.get('original_title') or '')
                cand_excerpt = article.get('excerpt', '')
                cand_created = article.get('created_at')
                cand_domain = (article.get('source_domain') or '').lower()
                cand_sig = self._story_signature(cand_title, cand_excerpt)

                title_sim = difflib.SequenceMatcher(None, (base_title or '').lower(), (cand_title or '').lower()).ratio() if base_title and cand_title else 0.0
                base_tok = _norm_tokens(base_title + ' ' + base_excerpt)
                cand_tok = _norm_tokens(cand_title + ' ' + cand_excerpt)
                inter = base_tok & cand_tok
                union = base_tok | cand_tok
                jaccard = (len(inter) / len(union)) if union else 0.0

                # Story signature overlap (use smaller set as denominator)
                sig_inter = len(base_sig & cand_sig)
                sig_min = max(1, min(len(base_sig), len(cand_sig)))
                sig_overlap = sig_inter / sig_min

                # Simple capitalized multi-word (2-3 tokens) overlap as entity proxy
                ent_pat = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b")
                entity_overlap = bool(set(ent_pat.findall(base_title)) & set(ent_pat.findall(cand_title)))
                # Allow single-word GPE overlap (e.g., Gaza, Israel) if spaCy is available
                if not entity_overlap and self.nlp:
                    try:
                        base_gpe = set(self._extract_location_entities(base_title + ' ' + base_excerpt))
                        cand_gpe = set(self._extract_location_entities(cand_title + ' ' + cand_excerpt))
                        entity_overlap = len(base_gpe & cand_gpe) > 0
                    except Exception:
                        pass

                def _parse_dt(x: Optional[str]):
                    try:
                        return datetime.fromisoformat((x or '').replace('Z', '+00:00'))
                    except Exception:
                        return None
                bdt = _parse_dt(base_created)
                cdt = _parse_dt(cand_created)
                time_ok = (bdt is not None and cdt is not None and abs((bdt - cdt).total_seconds()) / 3600.0 <= 72)

                # Very permissive gates: allow clustering with minimal similarity
                token_thresh = 0.15 if entity_overlap else 0.10  # Very low token threshold
                signals_passed = (
                    (1 if title_sim >= 0.40 else 0)  # Much lower title threshold
                    + (1 if jaccard >= token_thresh else 0)
                    + (1 if time_ok else 0)
                    + (1 if entity_overlap else 0)
                ) >= 1  # Only need one signal instead of two

                geo = {'germany','german','munich','uk','united','kingdom','britain','france','french','iran','iranian','israel','gaza','palestine','chicago','illinois','europe','european','union','usa','america','us'}
                geography_only = bool(inter) and inter.issubset(geo)

                # Very relaxed same-domain requirement: allow same-domain clustering more easily
                same_domain = (base_domain and cand_domain and base_domain == cand_domain)
                if same_domain:
                    # Same domain articles need only minimal similarity
                    if not (title_sim >= 0.30 and jaccard >= 0.08 and time_ok):
                        logger.debug("🧪 Same-domain gate FAIL base=%s cand=%s title=%.3f jacc=%.3f time=%s", article_id, article['article_id'], title_sim, jaccard, time_ok)
                        continue

                # Very permissive gates - minimal requirements
                if not (signals_passed and sig_overlap >= 0.08 and not (geography_only and title_sim < 0.30)):
                    logger.debug(
                        "🧪 Gate FAIL base=%s cand=%s sim=%.3f title=%.3f jacc=%.3f sig=%.3f ent=%s time=%s geo_only=%s same_domain=%s",
                        article_id, article['article_id'], similarity, title_sim, jaccard, sig_overlap, entity_overlap, time_ok, geography_only, ((article.get('source_domain') or '').lower() == (base_article.get('source_domain') or '').lower())
                    )
                    continue

                if similarity >= threshold:
                    similar.append((article['article_id'], similarity))
                    logger.info(f"✅ Similarity PASS: base={article_id} vs cand={article['article_id']} sim={similarity:.4f} >= {threshold} type={inferred_type}")
                else:
                    logger.info(f"❌ Similarity FAIL: base={article_id} vs cand={article['article_id']} sim={similarity:.4f} < {threshold} type={inferred_type}")
            
            # Sort by similarity (highest first)
            similar.sort(key=lambda x: x[1], reverse=True)
            
            logger.info(f"🏁 Found {len(similar)} similar articles")
            return similar[:10]  # Limit to top 10
            
        except Exception as e:
            logger.error(f"❌ Similarity search failed: {e}")
            return []

    def _prepare_content_for_comparison(self, article: Dict) -> str:
        """Prepare article content for similarity comparison"""
        # Combine title, excerpt, and content (sanitized)
        title = article.get('generated_title', '') or article.get('original_title', '')
        excerpt = article.get('excerpt', '')
        content = article.get('content', '')

        content_preview = content[:1200] if content else ''

        raw = f"{title} {excerpt} {content_preview}"
        # Strip code blocks, inline code, html, and CSS-like braces
        raw = re.sub(r"```[\s\S]*?```", " ", raw)
        raw = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", raw)
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = re.sub(r"\{[^}]*\}", " ", raw)

        combined = self._normalize_text(raw)
        return combined

    def _infer_article_type(self, text: str, title: Optional[str] = None) -> str:
        """Heuristically infer article type: 'breaking' or 'policy' (default to 'breaking' if unsure)"""
        sample = (title or '') + ' ' + (text or '')
        sample_lower = sample.lower()

        breaking_terms = [
            'killed', 'injured', 'arrested', 'shooting', 'attack', 'explosion', 'fire', 'crash',
            'dead', 'deaths', 'evacuated', 'police said', 'authorities', 'suspect'
        ]

        policy_terms = [
            'policy', 'proposal', 'proposes', 'plan', 'plans', 'rollout', 'regulation', 'eidas', 'estonia',
            'analysis', 'opinion', 'what can it learn', 'lessons', 'debate', 'parliament', 'minister', 'white paper'
        ]

        if any(term in sample_lower for term in breaking_terms):
            return 'breaking'
        if any(term in sample_lower for term in policy_terms):
            return 'policy'
        # Fallback: treat as breaking for stricter clustering by default
        return 'breaking'

    def _get_weights_and_threshold(self, article_type: str) -> Tuple[Dict[str, float], float]:
        """Return similarity weights and threshold based on inferred article type"""
        if article_type == 'policy':
            # Policy/analysis: emphasize location and event context; keep minimum gate strength
            return ({'tfidf': 0.45, 'semantic': 0.0, 'location': 0.35, 'event': 0.20}, 0.16)
        # Default/breaking: TF-IDF dominant, current global behavior
        return ({'tfidf': 0.6, 'semantic': 0.0, 'location': 0.3, 'event': 0.1}, self.similarity_threshold)

    def _topic_boost_policy(self, base_text: str, candidate_text: str) -> float:
        """Small additive boost for policy articles sharing key topic+geo terms"""
        base = base_text.lower()
        cand = candidate_text.lower()
        def has(term: str, s: str) -> bool:
            return term in s
        uk_terms = ['united kingdom', 'uk', 'britain', 'great britain']
        topic_terms = ['digital id', 'digital identity', 'eidas']
        uk_match = any(has(t, base) for t in uk_terms) and any(has(t, cand) for t in uk_terms)
        topic_match = any(has(t, base) for t in topic_terms) and any(has(t, cand) for t in topic_terms)
        return 0.03 if (uk_match and topic_match) else 0.0

    async def cluster_article(self, article_id: int, content: str) -> Optional[int]:
        """Add article to appropriate cluster or create new one"""
        logger.info(f"🎯 Starting clustering process for article {article_id}")
        
        try:
            # Find similar articles
            logger.debug(f"🔎 Finding similar articles for article {article_id}")
            similar = await self.find_similar_articles(article_id, content)
            
            if not similar:
                logger.info(f"🚫 No similar articles found for article {article_id}, keeping as standalone article")
                # Don't create cluster for standalone articles
                return None
            
            logger.info(f"✅ Found {len(similar)} similar articles for article {article_id}")
            
            # Check if any similar articles are already in clusters
            for similar_id, similarity in similar:
                logger.debug(f"🔍 Checking similar article {similar_id} (similarity: {similarity:.3f})")
                
                clusters = self.db.get_article_clusters(similar_id)
                
                if clusters:
                    # Add to existing cluster
                    cluster_id = clusters[0]['cluster_id']
                    cluster_title = clusters[0]['title']
                    logger.info(f"🎉 Found existing cluster {cluster_id}: '{cluster_title}' for similar article {similar_id}")
                    
                    try:
                        logger.debug(f"💾 Adding article {article_id} to cluster {cluster_id}")
                        self.db.add_to_cluster(article_id, cluster_id, similarity)
                        logger.info(f"✅ Successfully added article {article_id} to cluster {cluster_id}")
                        return cluster_id
                    except Exception as e:
                        logger.error(f"❌ Failed to add article {article_id} to cluster {cluster_id}: {e}")
                        continue
            
            # No existing clusters found, evaluate whether we have enough corroboration to form a cluster
            # Require at least one corroborating article from a distinct source domain
            base = self.db.get_article(article_id) or {}
            base_domain = (base.get('source_domain') or '').lower()
            distinct_candidates: List[Tuple[int, float]] = []
            for sid, s in similar:
                try:
                    art = self.db.get_article(sid) or {}
                    dom = (art.get('source_domain') or '').lower()
                    if dom and dom != base_domain:
                        distinct_candidates.append((sid, s))
                except Exception:
                    continue

            if not distinct_candidates:
                logger.info("🚫 Insufficient cross-domain corroboration for article %s; leaving as singleton for now", article_id)
                return None

            logger.info(f"🏗️ Creating new cluster with {len(distinct_candidates)} cross-domain similar articles")
            cluster_id = await self._create_new_cluster(article_id, content, distinct_candidates[:3])
            
            # Add similar articles to the new cluster
            if cluster_id:
                for similar_id, similarity in similar[:3]:
                    try:
                        logger.debug(f"💾 Adding similar article {similar_id} to new cluster {cluster_id}")
                        self.db.add_to_cluster(similar_id, cluster_id, similarity)
                    except Exception as e:
                        logger.error(f"❌ Failed to add similar article {similar_id} to cluster: {e}")
            
            return cluster_id
            
        except Exception as e:
            logger.error(f"❌ Clustering failed for article {article_id}: {e}")
            import traceback
            logger.error(f"🔍 Traceback: {traceback.format_exc()}")
            return None

    async def _create_new_cluster(self, article_id: int, content: str, similar_articles: List[Tuple[int, float]] = None) -> Optional[int]:
        """Create a new cluster"""
        logger.info(f"🏗️ Creating new cluster for article {article_id}")
        
        try:
            # Get article title to exclude from summary
            article = self.db.get_article(article_id)
            article_title = article.get('generated_title', '') if article else None
            
            # Build combined context from base + top similar articles (titles + excerpts + previews)
            combined_texts: List[str] = []
            try:
                base_row = self.db.get_article(article_id) or {}
                base_title = (base_row.get('generated_title') or base_row.get('original_title') or '')
                base_excerpt = base_row.get('excerpt') or ''
                base_preview = (base_row.get('content') or '')[:1200]
                combined_texts.append(f"{base_title} {base_excerpt} {base_preview}")
            except Exception:
                pass

            if similar_articles:
                for similar_id, _sim in similar_articles[:3]:
                    try:
                        r = self.db.get_article(similar_id) or {}
                        t = (r.get('generated_title') or r.get('original_title') or '')
                        e = r.get('excerpt') or ''
                        p = (r.get('content') or '')[:1000]
                        combined_texts.append(f"{t} {e} {p}")
                    except Exception:
                        continue

            # Generate cluster title from aggregated context (deterministic)
            cluster_title = self._generate_cluster_title(combined_texts or [content])
            logger.debug(f"📝 Generated cluster title: {cluster_title}")
            
            # Generate summary from aggregated context (deterministic)
            cluster_summary = self._generate_cluster_summary(combined_texts or [content], article_title)
            logger.debug(f"📝 Generated cluster summary: {cluster_summary[:100]}...")
            
            # Create cluster
            cluster_id = self.db.create_cluster(cluster_title, cluster_summary)
            
            if not cluster_id:
                logger.error(f"❌ Failed to create cluster")
                return None
            
            # Add main article to cluster
            self.db.add_to_cluster(article_id, cluster_id, 1.0)
            logger.debug(f"✅ Added main article {article_id} to cluster {cluster_id}")
            
            # Add similar articles if provided
            if similar_articles:
                for similar_id, similarity in similar_articles:
                    self.db.add_to_cluster(similar_id, cluster_id, similarity)
                    logger.debug(f"✅ Added similar article {similar_id} to cluster {cluster_id} (similarity: {similarity:.3f})")
            
            logger.info(f"✅ Created new cluster {cluster_id} for article {article_id}")
            return cluster_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create new cluster: {e}")
            return None

    def _generate_cluster_title(self, texts: List[str]) -> str:
        """Generate deterministic, informative cluster title from multiple texts.

        Heuristics: choose a prominent location or organization and a concise topic/action phrase.
        No LLM dependency.
        """
        logger.debug(f"📝 Generating deterministic cluster title from {len(texts)} texts")

        all_text = ' '.join(texts or [])

        # 1) Try central headline selection from member texts
        def headline_candidate(t: str) -> str:
            t = (t or '').strip()
            # take first sentence or first ~12 words as the headline proxy
            import re
            first_sent = re.split(r"(?<=[\.!?])\s+", t)[0]
            words = first_sent.split()
            if len(words) > 12:
                return ' '.join(words[:12])
            return first_sent if len(first_sent) >= 8 else ' '.join((t.split()[:12]))

        def tokens(s: str) -> set:
            import re
            return set(re.findall(r"[a-z0-9]+", s.lower()))

        heads = [headline_candidate(t) for t in texts[:5]]
        if heads:
            head_tokens = [tokens(h) for h in heads]
            best_idx = 0
            best_score = -1.0
            for i in range(len(heads)):
                score = 0.0
                for j in range(len(heads)):
                    if i == j:
                        continue
                    a, b = head_tokens[i], head_tokens[j]
                    if not a or not b:
                        continue
                    inter = len(a & b)
                    uni = len(a | b)
                    score += (inter / uni) if uni else 0.0
                if score > best_score and len(heads[i].split()) >= 5:
                    best_score = score
                    best_idx = i
            central = heads[best_idx].strip(' .')
            # normalize capitalization; titlecase but keep ALL CAPS acronyms
            if central:
                try:
                    normalized = ' '.join(w if w.isupper() else (w.capitalize() if len(w) > 3 else w.lower()) for w in central.split())
                    if 10 <= len(normalized) <= 90:
                        return normalized
                except Exception:
                    if 10 <= len(central) <= 90:
                        return central

        # Extract locations and orgs via spaCy if available; fallback to regex
        locations: List[str] = []
        orgs: List[str] = []
        if self.nlp:
            try:
                doc = self.nlp(all_text)
                for ent in doc.ents:
                    if ent.label_ == 'GPE':
                        locations.append(self._normalize_geo_name(ent.text))
                    elif ent.label_ == 'ORG':
                        orgs.append(ent.text.strip())
            except Exception:
                pass
        if not locations:
            m = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", all_text)
            locations = [self._normalize_geo_name(s) for s in m]

        # Topic keywords
        topic_map = {
            'ceasefire': ['ceasefire','truce','hostage','deal','agreement'],
            'air base': ['air base','airforce','air force','facility','fighter','jets','training'],
            'attack': ['attack','assault','strike','bombing'],
            'election': ['election','vote','campaign','polls'],
            'protest': ['protest','demonstration','rally'],
            'economy': ['market','inflation','stocks','economy'],
        }
        lc_text = all_text.lower()
        topic_scores: Dict[str, int] = {}
        for topic, kws in topic_map.items():
            topic_scores[topic] = sum(lc_text.count(k) for k in kws)
        topic = max(topic_scores, key=topic_scores.get) if topic_scores else 'update'

        def top_item(items: List[str]) -> Optional[str]:
            if not items:
                return None
            counts = Counter([i.strip() for i in items if i.strip()])
            return (counts.most_common(1)[0][0] if counts else None)

        loc = top_item([l for l in locations if l and l not in {'unknown','european union'}])
        org = top_item(orgs)

        # Compose
        if loc and topic:
            title = f"{loc.title()} - {topic.title()}"
        elif org and topic:
            title = f"{org} - {topic.title()}"
        else:
            # fallback: top two non-stopword tokens
            toks = re.findall(r"[A-Za-z]{3,}", all_text)
            common = [w for w,_ in Counter([w.lower() for w in toks]).most_common(5)]
            if len(common) >= 2:
                title = f"{common[0].title()} {common[1].title()}"
            else:
                title = "News Update"

        logger.debug(f"📝 Generated cluster title: {title}")
        return title

    def _extract_key_topics_for_cluster(self, content: str) -> list:
        """Extract key topics for cluster title"""
        event_patterns = [
            r'(shooting|attack|explosion|fire|crash|accident|murder|killing)',
            r'(arrest|charged|convicted|sentenced)',
            r'(election|vote|campaign|debate)',
            r'(storm|flood|earthquake|disaster)',
            r'(protest|demonstration|riot)',
        ]
        
        topics = []
        for pattern in event_patterns:
            matches = re.findall(pattern, content.lower())
            topics.extend(matches)
        
        return list(set(topics))[:3]

    def _extract_location_for_cluster(self, content: str) -> str:
        """Extract location for cluster title"""
        location_patterns = [
            r'(Michigan|California|Texas|Florida|New York|Pennsylvania|Illinois|Ohio|Georgia)',
            r'([A-Z][a-z]+ City)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)
        
        return "Unknown"

    def _extract_event_type_for_cluster(self, content: str) -> str:
        """Extract event type for cluster title"""
        event_types = {
            'crime': r'(shooting|murder|robbery|theft|assault|kidnapping)',
            'disaster': r'(fire|explosion|crash|accident|storm|flood)',
            'politics': r'(election|vote|campaign|debate|protest)',
        }
        
        for event_type, pattern in event_types.items():
            if re.search(pattern, content.lower()):
                return event_type
        
        return "general"

    def _generate_cluster_summary(self, texts: List[str], article_title: str = None) -> str:
        """Generate concise, deterministic cluster summary from multiple sources.

        Strategy: collect first 1–2 meaningful sentences from up to 3 texts, deduplicate,
        cap at ~120–140 words. No LLM.
        """
        logger.debug(f"📝 Generating deterministic cluster summary from {len(texts)} texts")

        def clean(t: str) -> str:
            t = t or ''
            if article_title:
                t = t.replace(article_title, '', 1)
            t = re.sub(r"```[\s\S]*?```", " ", t)
            t = re.sub(r"`{1,3}([^`]+)`{1,3}", r"\1", t)
            t = re.sub(r"<[^>]+>", " ", t)
            t = re.sub(r"\{[^}]*\}", " ", t)
            t = re.sub(r"\s+", " ", t).strip()
            return t

        sentences: List[str] = []
        for raw in texts[:3]:
            safe = clean(raw)
            parts = re.split(r"(?<=[\.!?])\s+", safe)
            for p in parts:
                s = p.strip()
                if 30 <= len(s) <= 240:
                    sentences.append(s)
                    break  # take first good sentence from this text

        # Deduplicate sentences by lowercase
        seen = set()
        deduped: List[str] = []
        for s in sentences:
            k = s.lower()
            if k not in seen:
                seen.add(k)
                deduped.append(s)

        # Truncate to ~140 words total
        out: List[str] = []
        count = 0
        for s in deduped:
            n = len(s.split())
            if count + n > 140:
                break
            out.append(s)
            count += n

        summary = ' '.join(out)[:800].strip()
        if summary and not summary.endswith(('.', '!', '?')):
            summary += '.'
        if not summary:
            # fallback to condensed cleaned text
            fallback = clean(' '.join(texts))
            summary = (fallback[:300] + '...') if len(fallback) > 300 else fallback

        logger.debug(f"📝 Generated cluster summary: {summary[:120]}...")
        return summary

    def _load_nlp_model(self):
        """Load spaCy model for semantic analysis"""
        try:
            self.nlp = spacy.load("en_core_web_sm")
            logger.info("✅ spaCy model loaded successfully")
        except OSError:
            logger.warning("⚠️ spaCy model not found, using basic text processing")
            self.nlp = None

    def _extract_semantic_features(self, text: str) -> Dict[str, float]:
        """Extract semantic features using spaCy"""
        if not self.nlp:
            return {}
        
        doc = self.nlp(text)
        features = {}
        
        # Named entities
        entities = [ent.text for ent in doc.ents if ent.label_ in ['PERSON', 'ORG', 'GPE', 'EVENT']]
        features['entities'] = len(entities)
        
        # Key phrases (noun phrases)
        noun_phrases = [chunk.text for chunk in doc.noun_chunks]
        features['noun_phrases'] = len(noun_phrases)
        
        # Sentiment indicators
        sentiment_words = ['killed', 'injured', 'arrested', 'destroyed', 'damaged', 'closed', 'dead', 'wounded']
        sentiment_count = sum(1 for word in sentiment_words if word in text.lower())
        features['sentiment_indicators'] = sentiment_count
        
        return features

    def _normalize_geo_name(self, name: str) -> str:
        """Normalize geopolitical synonyms to canonical forms for matching"""
        if not name:
            return ""
        n = name.strip().lower()
        synonyms = {
            # United Kingdom
            'uk': 'united kingdom', 'u.k.': 'united kingdom', 'u.k': 'united kingdom',
            'united kingdom': 'united kingdom', 'britain': 'united kingdom', 'great britain': 'united kingdom',
            'gb': 'united kingdom', 'england': 'united kingdom',
            # United States
            'us': 'united states', 'u.s.': 'united states', 'u.s': 'united states',
            'usa': 'united states', 'u.s.a.': 'united states', 'united states': 'united states',
            'america': 'united states',
            # European Union
            'eu': 'european union', 'e.u.': 'european union', 'e.u': 'european union',
            'european union': 'european union',
        }
        return synonyms.get(n, n)

    def _extract_location_entities(self, text: str) -> List[str]:
        """Extract location entities from text and normalize synonyms"""
        if not self.nlp:
            return []
        
        doc = self.nlp(text)
        locations = []
        
        for ent in doc.ents:
            if ent.label_ == 'GPE':  # Geopolitical entities
                locations.append(self._normalize_geo_name(ent.text))
        
        return locations

    def _extract_event_entities(self, text: str) -> List[str]:
        """Extract event entities from text"""
        if not self.nlp:
            return []
        
        doc = self.nlp(text)
        events = []
        
        for ent in doc.ents:
            if ent.label_ == 'EVENT':
                events.append(ent.text)
        
        return events

    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate semantic similarity using word embeddings"""
        if not self.nlp:
            return 0.0
        
        try:
            doc1 = self.nlp(text1)
            doc2 = self.nlp(text2)
            
            # Calculate similarity using spaCy's built-in similarity
            similarity = doc1.similarity(doc2)
            return similarity
        except Exception as e:
            logger.error(f"❌ Semantic similarity calculation failed: {e}")
            return 0.0

    def _calculate_location_similarity(self, text1: str, text2: str) -> float:
        """Calculate location-based similarity"""
        locations1 = set(self._extract_location_entities(text1))
        locations2 = set(self._extract_location_entities(text2))
        
        if not locations1 or not locations2:
            return 0.0
        
        # Jaccard similarity for locations
        intersection = len(locations1.intersection(locations2))
        union = len(locations1.union(locations2))
        
        return intersection / union if union > 0 else 0.0

    def _calculate_event_similarity(self, text1: str, text2: str) -> float:
        """Calculate event-based similarity"""
        events1 = set(self._extract_event_entities(text1))
        events2 = set(self._extract_event_entities(text2))
        
        if not events1 or not events2:
            return 0.0
        
        # Jaccard similarity for events
        intersection = len(events1.intersection(events2))
        union = len(events1.union(events2))
        
        return intersection / union if union > 0 else 0.0
