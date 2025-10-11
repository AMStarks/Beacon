#!/usr/bin/env python3
"""
Cluster Audit Bolt-on: compute cohesion/separation metrics, evaluate clusters and singletons,
and provide suggestions to split/merge/keep. Designed to be non-invasive and callable via API.
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .database import Beacon3Database
from .clustering_service import ClusteringService

logger = logging.getLogger(__name__)


@dataclass
class ClusterMetrics:
    cluster_id: int
    size: int
    cohesion_mean: float
    cohesion_median: float
    separation_min: float
    title_overlap_rate: float
    entity_overlap_rate: float


class ClusterAuditService:
    def __init__(self, db: Optional[Beacon3Database] = None):
        self.db = db or Beacon3Database()
        self.cluster = ClusteringService(self.db)

    def _pairwise_similarities(self, texts: List[str]) -> List[float]:
        sims: List[float] = []
        n = len(texts)
        for i in range(n):
            for j in range(i + 1, n):
                sims.append(self.cluster.calculate_similarity(texts[i], texts[j]))
        return sims

    def _title_and_entity_overlap(self, titles: List[str]) -> Tuple[float, float]:
        import re
        def ents(s: str) -> set:
            # Simple proxy: capitalized 1-3 word sequences
            pat = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")
            return set(pat.findall(s or ''))

        def toks(s: str) -> set:
            t = re.sub(r'[^A-Za-z0-9\s]', ' ', (s or '').lower()).split()
            return set(w for w in t if len(w) >= 3)

        n = len(titles)
        if n < 2:
            return 0.0, 0.0

        ent_hits = 0
        tok_hits = 0
        pairs = 0
        for i in range(n):
            for j in range(i + 1, n):
                pairs += 1
                if ents(titles[i]) & ents(titles[j]):
                    ent_hits += 1
                if toks(titles[i]) & toks(titles[j]):
                    tok_hits += 1
        return (ent_hits / pairs if pairs else 0.0, tok_hits / pairs if pairs else 0.0)

    def compute_cluster_metrics(self, cluster_id: int) -> Optional[ClusterMetrics]:
        arts = self.db.get_cluster_articles(cluster_id)
        if not arts:
            return None

        # Build short texts (title + excerpt + content preview)
        texts: List[str] = []
        titles: List[str] = []
        for a in arts:
            titles.append((a.get('generated_title') or a.get('original_title') or '')[:200])
            preview = (a.get('content') or '')[:1200]
            texts.append(f"{titles[-1]} {a.get('excerpt') or ''} {preview}")

        pairwise = self._pairwise_similarities(texts)
        if not pairwise:
            cohesion_mean = 0.0
            cohesion_median = 0.0
        else:
            import numpy as np
            cohesion_mean = float(np.mean(pairwise))
            cohesion_median = float(np.median(pairwise))

        # Separation: min distance to any other cluster's centroid proxy (use highest cross-sim as inverse distance)
        # Simplify: compare this cluster's concatenated text vs a sample of other clusters' concatenations
        others = self.db.get_clusters(limit=50)
        concat = ' '.join(texts)
        best_cross = 0.0
        for other in others:
            if other['cluster_id'] == cluster_id:
                continue
            other_arts = self.db.get_cluster_articles(other['cluster_id'])
            if not other_arts:
                continue
            other_concat = ' '.join(((oa.get('generated_title') or oa.get('original_title') or '') + ' ' + (oa.get('excerpt') or '') + ' ' + (oa.get('content') or '')[:1200]) for oa in other_arts)
            sim = self.cluster.calculate_similarity(concat, other_concat)
            if sim > best_cross:
                best_cross = sim
        separation_min = 1.0 - best_cross  # larger is better separation

        ent_rate, title_rate = self._title_and_entity_overlap(titles)

        return ClusterMetrics(
            cluster_id=cluster_id,
            size=len(arts),
            cohesion_mean=cohesion_mean,
            cohesion_median=cohesion_median,
            separation_min=separation_min,
            title_overlap_rate=title_rate,
            entity_overlap_rate=ent_rate,
        )

    def evaluate_clusters_batch(self, limit: int = 50) -> List[Dict]:
        results: List[Dict] = []
        clusters = self.db.get_clusters(limit=limit)
        for c in clusters:
            metrics = self.compute_cluster_metrics(c['cluster_id'])
            if not metrics:
                continue
            label = self._label_from_metrics(metrics)
            payload = {
                'cluster_id': metrics.cluster_id,
                'metrics': metrics.__dict__,
                'label': label,
            }
            self.db.upsert_cluster_evaluation(metrics.cluster_id, json.dumps(metrics.__dict__), label=label)
            results.append(payload)
        return results

    def _label_from_metrics(self, m: ClusterMetrics) -> str:
        # Simple heuristic labeling
        if m.size >= 3 and m.cohesion_mean >= 0.22 and m.separation_min >= 0.65:
            return 'correct'
        if m.size >= 2 and m.cohesion_mean < 0.12:
            return 'split_needed'
        if m.size >= 2 and m.separation_min < 0.40:
            return 'should_merge'
        return 'mixed'

    def singleton_merge_candidates(self, limit: int = 50) -> List[Dict]:
        singles = self.db.get_singleton_articles(limit=limit)
        suggestions: List[Dict] = []
        recent = self.db.get_recent_articles(100, include_processing=True)
        for a in singles:
            base_text = f"{(a.get('generated_title') or a.get('original_title') or '')} {a.get('excerpt') or ''} {(a.get('content') or '')[:1200]}"
            best = (None, 0.0)
            for r in recent:
                if r['article_id'] == a['article_id']:
                    continue
                cand_text = f"{(r.get('generated_title') or r.get('original_title') or '')} {r.get('excerpt') or ''} {(r.get('content') or '')[:1200]}"
                sim = self.cluster.calculate_similarity(base_text, cand_text)
                if sim > best[1]:
                    best = (r, sim)
            if best[0] and best[1] >= 0.22:
                suggestions.append({'article_id': a['article_id'], 'candidate_article_id': best[0]['article_id'], 'similarity': best[1]})
        return suggestions

    def propose_param_adjustments(self) -> Dict:
        # Placeholder: suggest slight adjustments based on recent evals aggregate
        evals = self.db.get_recent_cluster_evaluations(200)
        n_split = sum(1 for e in evals if (e.get('label') == 'split_needed'))
        n_merge = sum(1 for e in evals if (e.get('label') == 'should_merge'))
        params = {
            'similarity_threshold': self.cluster.similarity_threshold,
            'weights_default': {'tfidf': 0.6, 'semantic': 0.0, 'location': 0.3, 'event': 0.1}
        }
        # Simple rule: if many splits, raise threshold slightly; if many merges, lower slightly
        if n_split > n_merge + 5:
            params['similarity_threshold'] = min(0.28, params['similarity_threshold'] + 0.02)
        elif n_merge > n_split + 5:
            params['similarity_threshold'] = max(0.16, params['similarity_threshold'] - 0.02)
        self.db.save_cluster_params(json.dumps(params))
        return params


