#!/usr/bin/env python3
"""
Beacon 3 - RSS Source Probe

Purpose:
- Iterate configured RSS feeds
- Fetch a small sample of links per feed
- Probe extraction using the app's ContentExtractor
- Classify per-domain reliability and recommend: keep | tune | block

Outputs:
- JSON report with per-URL and per-domain details
- CSV summary per-domain
"""

import asyncio
import csv
import json
import os
import re
import sys
from collections import defaultdict, Counter
from datetime import datetime
from typing import Dict, Any, List

import feedparser
import requests

# Use the app's extractor for fidelity
APP_SRC_DIR = '/root/beacon3/src'
if os.path.isdir(APP_SRC_DIR):
    sys.path.insert(0, APP_SRC_DIR)

try:
    from content_extractor import ContentExtractor  # type: ignore
except Exception:
    ContentExtractor = None  # Fallback handled below

DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

PAYWALL_HINTS = [
    'subscribe', 'subscriber-only', 'paywall', 'metered',
    'log in to continue', 'please subscribe', 'create an account',
]

CF_BOT_HINTS = [
    'cloudflare', 'verify you are a human', 'checking your browser before accessing',
]

JS_REQUIRED_HINTS = [
    'enable javascript', 'please enable javascript', 'requires javascript',
]

def sniff_page_hints(text: str) -> str:
    t = text.lower()
    if any(k in t for k in PAYWALL_HINTS):
        return 'paywall'
    if any(k in t for k in CF_BOT_HINTS):
        return 'anti_bot'
    if any(k in t for k in JS_REQUIRED_HINTS):
        return 'js_required'
    return ''

def load_feeds(path: str) -> List[Dict[str, Any]]:
    with open(path, 'r') as f:
        data = json.load(f)
    return data.get('feeds', [])

async def extract_with_app(url: str) -> Dict[str, Any]:
    if ContentExtractor is None:
        return {'success': False, 'error': 'extractor_unavailable'}
    extractor = ContentExtractor()
    try:
        return await extractor.extract_content(url)
    except Exception as e:
        return {'success': False, 'error': str(e)}

def preflight(url: str) -> Dict[str, Any]:
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=20, allow_redirects=True)
        text_preview = r.text[:4000] if isinstance(r.text, str) else ''
        hint = sniff_page_hints(text_preview)
        return {
            'ok': r.status_code == 200,
            'status': r.status_code,
            'final_url': r.url,
            'hint': hint,
        }
    except requests.exceptions.RequestException as e:
        return {'ok': False, 'status': 0, 'final_url': url, 'error': str(e), 'hint': 'network_error'}

async def probe_url(url: str) -> Dict[str, Any]:
    pf = preflight(url)
    result: Dict[str, Any] = {'url': url, 'preflight': pf}
    # If not 200, classify quickly
    if not pf.get('ok'):
        status = pf.get('status', 0)
        if status in (401, 403):
            result['classification'] = 'anti_bot'
        elif status in (404,):
            result['classification'] = 'not_found'
        elif status >= 500:
            result['classification'] = 'server_error'
        else:
            result['classification'] = pf.get('hint') or 'network_error'
        return result

    # Try real extraction
    ext = await extract_with_app(pf['final_url'])
    result['extract'] = {k: ext.get(k) for k in ('success', 'error')}

    if not ext.get('success'):
        # Use hint if present
        result['classification'] = pf.get('hint') or 'extract_failed'
        return result

    content = ext.get('content') or ''
    title = (ext.get('title') or '').strip()
    if len(content) >= 800 and len(title) >= 10:
        result['classification'] = 'success'
    else:
        result['classification'] = 'too_short'
    result['metrics'] = {'content_len': len(content), 'title_len': len(title)}
    return result

async def probe_feed(feed_cfg: Dict[str, Any], sample: int = 5) -> Dict[str, Any]:
    feed_url = feed_cfg['url']
    feed_name = feed_cfg.get('name', feed_url)
    parsed = feedparser.parse(feed_url)
    entries = parsed.entries[:sample] if getattr(parsed, 'entries', None) else []
    results: List[Dict[str, Any]] = []
    for e in entries:
        link = e.get('link')
        if not link:
            continue
        res = await probe_url(link)
        results.append(res)
    return {
        'feed': feed_name,
        'url': feed_url,
        'results': results,
    }

def summarize_by_domain(feed_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from urllib.parse import urlparse
    domain_to_stats: Dict[str, Dict[str, Any]] = {}
    for fr in feed_results:
        for r in fr['results']:
            url = r['url']
            dom = urlparse(url).netloc.lower()
            if dom not in domain_to_stats:
                domain_to_stats[dom] = {'domain': dom, 'total': 0, 'success': 0, 'reasons': Counter(), 'feeds': set()}
            ds = domain_to_stats[dom]
            ds['total'] += 1
            if r.get('classification') == 'success':
                ds['success'] += 1
            else:
                ds['reasons'][r.get('classification', 'unknown')] += 1
            ds['feeds'].add(fr['feed'])

    summary: List[Dict[str, Any]] = []
    for dom, ds in domain_to_stats.items():
        rate = (ds['success'] / max(1, ds['total'])) * 100.0
        top_reasons = ','.join([f"{k}:{v}" for k, v in ds['reasons'].most_common(3)])
        if rate >= 70.0:
            rec = 'keep'
        elif rate < 30.0 or ds['reasons'].get('anti_bot') or ds['reasons'].get('paywall'):
            rec = 'block'
        else:
            rec = 'tune'
        summary.append({
            'domain': dom,
            'tested': ds['total'],
            'success_rate': round(rate, 1),
            'top_reasons': top_reasons,
            'feeds': sorted(ds['feeds']),
            'recommendation': rec,
        })
    summary.sort(key=lambda x: (-x['success_rate'], x['domain']))
    return summary

async def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--feeds', default='/root/beacon3/beacon3_rss_feeds.json')
    ap.add_argument('--out', default='/root/beacon3/_reports')
    ap.add_argument('--sample', type=int, default=5)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    feeds = load_feeds(args.feeds)

    feed_results: List[Dict[str, Any]] = []
    for f in feeds:
        fr = await probe_feed(f, sample=args.sample)
        feed_results.append(fr)

    summary = summarize_by_domain(feed_results)

    ts = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
    json_path = os.path.join(args.out, f'rss_probe_{ts}.json')
    csv_path = os.path.join(args.out, f'rss_probe_summary_{ts}.csv')

    with open(json_path, 'w') as jf:
        json.dump({'generated_at': ts, 'feeds': feed_results, 'summary': summary}, jf, indent=2)

    with open(csv_path, 'w', newline='') as cf:
        writer = csv.DictWriter(cf, fieldnames=['domain', 'tested', 'success_rate', 'top_reasons', 'recommendation'])
        writer.writeheader()
        for row in summary:
            writer.writerow({k: row[k] for k in writer.fieldnames})

    # Print a brief console summary
    print(json.dumps({'success': True, 'report_json': json_path, 'report_csv': csv_path, 'domains': len(summary)}, indent=2))

if __name__ == '__main__':
    asyncio.run(main())


