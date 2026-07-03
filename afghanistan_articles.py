"""
afghanistan_articles.py -- Asifah Analytics Asia Backend -- v1.0.0 Jul 2026

AFGHANISTAN ARTICLE FEED (pre-tracker). Serves the stability page's articles
section at /api/asia/threat/afghanistan with the platform article contract:
  { success, top_signals: [{title, url, source, feed_type, lang, published}],
    last_updated }

SOURCES (EN + Dari + Pashto + social):
  - Google News RSS search (EN, Dari hl=fa, Pashto hl=ps)
  - Direct RSS: TOLOnews, Pajhwok, Hasht-e Subh (8am.media),
    BBC Pashto, BBC Persian/Afghanistan
  - Reddit r/afghanistan (.rss) for the Social tab
Feeds unreachable from the build sandbox -- verify counts on first deploy
via /api/asia/threat/afghanistan/health (the USGS drill).

When the rhetoric tracker ships, its richer scan can supersede this module;
until then this is the honest article layer. Redis: articles:afghanistan:latest
(TTL 8h > 6h refresh; cold-gap rule). Cross-worker SET NX EX lock.
"""

import os
import re
import json
import time
import threading
from datetime import datetime, timezone

import requests

UPSTASH_URL   = os.environ.get('UPSTASH_REDIS_REST_URL') or os.environ.get('UPSTASH_REDIS_URL', '')
UPSTASH_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN') or os.environ.get('UPSTASH_REDIS_TOKEN', '')

CACHE_KEY          = 'articles:afghanistan:latest'
LOCK_KEY           = 'lock:afghanistan_articles'
REFRESH_HOURS      = 6
CACHE_TTL          = 8 * 3600
LOCK_TTL           = 15 * 60
BOOT_DELAY_SECONDS = 90
MAX_ARTICLES       = 80
UA                 = {'User-Agent': 'Mozilla/5.0 (compatible; AsifahAnalytics/1.0)'}

FEEDS = [
    # (name, url, feed_type, lang)
    ('GoogleNews-EN', 'https://news.google.com/rss/search?q=Afghanistan%20(Taliban%20OR%20ISKP%20OR%20TTP%20OR%20Kabul)&hl=en-US&gl=US&ceid=US:en', 'rss', 'en'),
    ('GoogleNews-Dari', 'https://news.google.com/rss/search?q=%D8%A7%D9%81%D8%BA%D8%A7%D9%86%D8%B3%D8%AA%D8%A7%D9%86&hl=fa&gl=AF&ceid=AF:fa', 'rss', 'fa'),
    ('GoogleNews-Pashto', 'https://news.google.com/rss/search?q=%D8%A7%D9%81%D8%BA%D8%A7%D9%86%D8%B3%D8%AA%D8%A7%D9%86&hl=ps&gl=AF&ceid=AF:ps', 'rss', 'ps'),
    ('TOLOnews', 'https://tolonews.com/rss', 'rss', 'en'),
    ('Pajhwok', 'https://pajhwok.com/feed/', 'rss', 'en'),
    ('Hasht-e Subh', 'https://8am.media/feed/', 'rss', 'fa'),
    ('BBC Pashto', 'https://feeds.bbci.co.uk/pashto/rss.xml', 'rss', 'ps'),
    ('BBC Persian Afghanistan', 'https://feeds.bbci.co.uk/persian/afghanistan/rss.xml', 'rss', 'fa'),
    ('Reddit r/afghanistan', 'https://www.reddit.com/r/afghanistan/.rss', 'reddit', 'en'),
]

_refresh_thread = None


def _redis_get(key):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    try:
        r = requests.get(f'{UPSTASH_URL}/get/{key}',
                         headers={'Authorization': f'Bearer {UPSTASH_TOKEN}'}, timeout=5)
        if r.status_code != 200:
            return None
        result = r.json().get('result')
        return json.loads(result) if result else None
    except Exception as e:
        print(f'[AFG Articles] Redis GET error: {str(e)[:100]}')
        return None


def _redis_set(key, value, ttl=CACHE_TTL):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return False
    try:
        r = requests.post(f'{UPSTASH_URL}/set/{key}',
                          headers={'Authorization': f'Bearer {UPSTASH_TOKEN}',
                                   'Content-Type': 'application/json'},
                          data=json.dumps(value, default=str),
                          params={'EX': ttl}, timeout=5)
        return r.json().get('result') == 'OK'
    except Exception as e:
        print(f'[AFG Articles] Redis SET error: {str(e)[:100]}')
        return False


def _acquire_lock():
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return True
    try:
        r = requests.get(f'{UPSTASH_URL}/set/{LOCK_KEY}/1',
                         headers={'Authorization': f'Bearer {UPSTASH_TOKEN}'},
                         params={'NX': 'true', 'EX': LOCK_TTL}, timeout=5)
        return r.json().get('result') == 'OK'
    except Exception:
        return True


def _parse_rss(text, name, feed_type, lang, limit=20):
    """Regex RSS/Atom item parser -- no external deps, defensive by design."""
    items = []
    chunks = re.findall(r'<item>(.*?)</item>', text, re.DOTALL)
    if not chunks:
        chunks = re.findall(r'<entry>(.*?)</entry>', text, re.DOTALL)   # Atom (Reddit)
    for c in chunks[:limit]:
        def _tag(t):
            m = re.search(rf'<{t}[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{t}>', c, re.DOTALL)
            return (m.group(1).strip() if m else '')
        title = re.sub(r'<[^>]+>', '', _tag('title'))[:220]
        link = _tag('link')
        if not link:
            m = re.search(r'<link[^>]*href="([^"]+)"', c)
            link = m.group(1) if m else ''
        pub = _tag('pubDate') or _tag('published') or _tag('updated')
        if title and link:
            items.append({'title': title, 'url': link.strip(), 'source': name,
                          'feed_type': feed_type, 'lang': lang, 'published': pub})
    return items


def _fetch_feed(name, url, feed_type, lang):
    try:
        r = requests.get(url, headers=UA, timeout=12)
        if r.status_code != 200:
            print(f'[AFG Articles] {name} HTTP {r.status_code}')
            return []
        items = _parse_rss(r.text, name, feed_type, lang)
        print(f'[AFG Articles] {name}: {len(items)} items')
        return items
    except Exception as e:
        print(f'[AFG Articles] {name} failed: {type(e).__name__}: {str(e)[:110]}')
        return []


def run_afghanistan_articles(force=False):
    if not force:
        cached = _redis_get(CACHE_KEY)
        if cached and cached.get('last_updated'):
            try:
                age = (datetime.now(timezone.utc) -
                       datetime.fromisoformat(cached['last_updated'])).total_seconds()
                if age < REFRESH_HOURS * 3600:
                    cached['from_cache'] = True
                    return cached
            except Exception:
                pass

    print('[AFG Articles] === Sweep starting ===')
    t0 = time.time()
    all_items, seen, per_feed = [], set(), {}
    for name, url, ftype, lang in FEEDS:
        items = _fetch_feed(name, url, ftype, lang)
        per_feed[name] = len(items)
        for it in items:
            key = it['url'].split('?')[0].rstrip('/')
            if key and key not in seen:
                seen.add(key)
                all_items.append(it)

    payload = {
        'success':      True,
        'theatre':      'afghanistan',
        'module':       'afghanistan_articles',
        'version':      '1.0.0',
        'top_signals':  all_items[:MAX_ARTICLES],
        'article_count': len(all_items[:MAX_ARTICLES]),
        'feeds_health': per_feed,
        'elapsed_sec':  round(time.time() - t0, 2),
        'last_updated': datetime.now(timezone.utc).isoformat(),
        'from_cache':   False,
    }
    _redis_set(CACHE_KEY, payload)
    print(f"[AFG Articles] === {payload['article_count']} articles in {payload['elapsed_sec']}s ===")
    return payload


def _background_refresh_loop():
    print('[AFG Articles] Background refresh thread started')
    time.sleep(BOOT_DELAY_SECONDS)
    while True:
        try:
            if _acquire_lock():
                run_afghanistan_articles(force=True)
            else:
                print('[AFG Articles] Another worker owns this cycle -- skipping')
        except Exception as e:
            print(f'[AFG Articles] Background error: {str(e)[:150]}')
        time.sleep(REFRESH_HOURS * 3600)


def _start_background_refresh():
    global _refresh_thread
    if _refresh_thread is None or not _refresh_thread.is_alive():
        _refresh_thread = threading.Thread(target=_background_refresh_loop, daemon=True)
        _refresh_thread.start()


def register_afghanistan_articles_endpoints(app):
    from flask import jsonify, request as flask_request

    @app.route('/api/asia/threat/afghanistan', methods=['GET'])
    def api_afghanistan_articles():
        force = flask_request.args.get('force', '').lower() in ('true', '1', 'yes')
        try:
            return jsonify(run_afghanistan_articles(force=force))
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200], 'top_signals': []}), 500

    @app.route('/api/asia/threat/afghanistan/health', methods=['GET'])
    def api_afghanistan_articles_health():
        cached = _redis_get(CACHE_KEY) or {}
        return jsonify({
            'module':        'afghanistan_articles',
            'version':       '1.0.0',
            'redis_configured': bool(UPSTASH_URL and UPSTASH_TOKEN),
            'cached_at':     cached.get('last_updated', ''),
            'article_count': cached.get('article_count', 0),
            'feeds_health':  cached.get('feeds_health', {}),
            'refresh_hours': REFRESH_HOURS,
        })

    _start_background_refresh()
    print('[AFG Articles] Endpoints registered: /api/asia/threat/afghanistan (+/health)')
