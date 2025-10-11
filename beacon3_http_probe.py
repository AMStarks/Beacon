#!/usr/bin/env python3
"""
Beacon 3 - HTTP-only RSS Probe

Classifies domains by basic accessibility (HTTP status + content hints)
without using the full extractor. Outputs two CSVs in the reports folder
and prints a JSON summary with their paths.
"""

import csv
import json
import os
import sys
import time
from typing import Dict, Any, List
from urllib.parse import urlparse

import feedparser
import requests


DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
}

PAYWALL_HINTS = ['subscribe', 'paywall', 'subscriber-only', 'log in to continue', 'please subscribe']
ANTI_BOT_HINTS = ['cloudflare', 'checking your browser', 'verify you are a human']
JS_REQUIRED_HINTS = ['enable javascript', 'requires javascript']


def sniff_hint(text: str) -> str:
    t = (text or '').lower()
    if any(x in t for x in PAYWALL_HINTS):
        return 'paywall'
    if any(x in t for x in ANTI_BOT_HINTS):
        return 'anti_bot'
    if any(x in t for x in JS_REQUIRED_HINTS):
        return 'js_required'
    return ''


def load_feeds(path: str) -> List[Dict[str, Any]]:
    with open(path, 'r') as f:
        return json.load(f).get('feeds', [])


def http_probe_url(url: str, timeout: int = 15) -> Dict[str, Any]:
    try:
        r = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
        h = sniff_hint(r.text[:4000]) if r.status_code == 200 else ''
        return {
            'status': r.status_code,
            'final_url': r.url,
            'hint': h,
            'ok': r.status_code == 200 and h == '',
        }
    except requests.exceptions.RequestException as e:
        return {'status': 0, 'final_url': url, 'hint': 'network', 'ok': False, 'error': str(e)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--feeds', default='/root/beacon3/beacon3_rss_feeds.json')
    ap.add_argument('--out', default='/root/beacon3/_reports')
    ap.add_argument('--sample', type=int, default=2)
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)

    feeds = load_feeds(args.feeds)
    domain_stats: Dict[str, Dict[str, Any]] = {}
    url_rows: List[List[Any]] = []

    for fc in feeds:
        feed_url = fc['url']
        feed_name = fc.get('name', feed_url)
        parsed = feedparser.parse(feed_url)
        entries = getattr(parsed, 'entries', [])[: args.sample]
        for e in entries:
            link = e.get('link')
            if not link:
                continue
            dom = urlparse(link).netloc.lower()
            res = http_probe_url(link)
            if dom not in domain_stats:
                domain_stats[dom] = {'domain': dom, 'tested': 0, 'ok': 0, 's401': 0, 's403': 0, 's5xx': 0, 'hint_paywall': 0, 'hint_anti_bot': 0, 'hint_js': 0, 'fail': 0}
            ds = domain_stats[dom]
            ds['tested'] += 1
            st = res.get('status', 0)
            if res.get('ok'):
                ds['ok'] += 1
            else:
                if st == 401:
                    ds['s401'] += 1
                elif st == 403:
                    ds['s403'] += 1
                elif st >= 500:
                    ds['s5xx'] += 1
                hint = res.get('hint', '')
                if hint == 'paywall':
                    ds['hint_paywall'] += 1
                elif hint == 'anti_bot':
                    ds['hint_anti_bot'] += 1
                elif hint == 'js_required':
                    ds['hint_js'] += 1
                ds['fail'] += 1
            url_rows.append([feed_name, dom, link, st, res.get('hint', '')])

    ts = time.strftime('%Y%m%d-%H%M%S')
    urls_csv = os.path.join(args.out, f'http_probe_urls_{ts}.csv')
    dom_csv = os.path.join(args.out, f'http_probe_domains_{ts}.csv')

    with open(urls_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['feed', 'domain', 'url', 'status', 'hint'])
        w.writerows(url_rows)

    with open(dom_csv, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['domain', 'tested', 'ok', 's401', 's403', 's5xx', 'hint_paywall', 'hint_anti_bot', 'hint_js', 'fail'])
        # Sort by ok ratio desc
        for dom, ds in sorted(domain_stats.items(), key=lambda kv: (-(kv[1]['ok'] / max(1, kv[1]['tested'])), kv[0])):
            w.writerow([ds['domain'], ds['tested'], ds['ok'], ds['s401'], ds['s403'], ds['s5xx'], ds['hint_paywall'], ds['hint_anti_bot'], ds['hint_js'], ds['fail']])

    print(json.dumps({'success': True, 'urls_report': urls_csv, 'domains_report': dom_csv, 'domains': len(domain_stats)}, indent=2))


if __name__ == '__main__':
    main()


