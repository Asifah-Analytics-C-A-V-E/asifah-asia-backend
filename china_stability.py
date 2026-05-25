"""
Asifah Analytics — China Stability Index
v1.0.0 — March 2026

ANALYTICAL FRAME:
China's stability is analytically distinct from other countries tracked
by Asifah Analytics. Unlike Lebanon or Iraq where instability = collapse
risk, China's risk has TWO dimensions:

  INTERNAL: Economic stress + social unrest + leadership fractures
  EXTERNAL: Stability enabling external aggression (Taiwan, SCS)

This tracker scores BOTH dimensions separately and feeds a composite
stability index into the frontend.

SCORING VECTORS:

  1. ECONOMIC HEALTH         25%  — yuan, PMI, property sector, trade
  2. RHETORIC/MILITARY       20%  — from rhetoric tracker Redis fingerprint
  3. DOMESTIC UNREST         20%  — protests, labor, social signals
  4. LEADERSHIP STABILITY    15%  — Xi consolidation, Politburo, purges
  5. MINORITY SUPPRESSION    10%  — Xinjiang, Tibet, HK signals
  6. US-CHINA RELATIONS      10%  — tariffs, tech decoupling, sanctions

STABILITY LABELS:
  80-100: Controlled       — tight grip, no significant signals
  60-79:  Managed Tension  — economic pressure or social signals emerging
  40-59:  Elevated Stress  — multiple vectors elevated simultaneously
  20-39:  Systemic Pressure — leadership + economic + unrest converging
  0-19:   Crisis Risk      — major simultaneous shocks (rare)

NOTE: Higher score = MORE stable (inverse of conflict probability)

REDIS KEYS:
  Cache:         china:stability:latest
  History:       china:stability:history
  Cross-theater: rhetoric:crosstheater:fingerprints (READS china key)

ENDPOINTS:
  GET /api/china/stability
  GET /api/china/stability/summary

COPYRIGHT 2025-2026 Asifah Analytics. All rights reserved.
"""

import os
import json
import time
import threading
import requests
import xml.etree.ElementTree as ET
import urllib.parse
from datetime import datetime, timezone, timedelta
from flask import jsonify, request

# ============================================
# CONFIG
# ============================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN') or os.environ.get('UPSTASH_REDIS_REST_TOKEN')
NEWSAPI_KEY         = os.environ.get('NEWSAPI_KEY')

CACHE_KEY           = 'china:stability:latest'
HISTORY_KEY         = 'china:stability:history'
CROSSTHEATER_KEY    = 'rhetoric:crosstheater:fingerprints'
CACHE_TTL           = 6 * 3600   # 6 hours
SCAN_INTERVAL_HOURS = 12

_stability_lock    = threading.Lock()
_stability_running = False

# ============================================
# LEADERSHIP — static reference data
# ============================================
CHINA_LEADERSHIP = [
    {
        'role':      'General Secretary / President / CMC Chairman',
        'name':      'Xi Jinping',
        'since':     '2012',
        'note':      'Consolidated power; removed term limits 2018; third term secured 2022',
        'status':    'active',
        'flag':      '🇨🇳',
        'risk_note': 'No clear succession mechanism; health rumors = destabilizing signal',
    },
    {
        'role':      'Premier (Head of Government)',
        'name':      'Li Qiang',
        'since':     '2023',
        'note':      'Xi loyalist; replaced Li Keqiang; handles economic policy day-to-day',
        'status':    'active',
        'flag':      '🇨🇳',
        'risk_note': 'Oversees property crisis response and trade war management',
    },
    {
        'role':      'Director, Central Foreign Affairs Commission',
        'name':      'Wang Yi',
        'since':     '2023',
        'note':      'Foreign policy chief; also State Councilor; key interlocutor with US',
        'status':    'active',
        'flag':      '🇨🇳',
        'risk_note': 'Manages Taiwan Strait and South China Sea diplomatic escalation',
    },
    {
        'role':      'Minister of National Defense',
        'name':      'Dong Jun',
        'since':     '2024',
        'note':      'PLAN admiral; replaced Dong Jun after predecessor removed for corruption',
        'status':    'active',
        'flag':      '🇨🇳',
        'risk_note': 'PLA purges of Rocket Force (2023) and defense ministry signal Xi control concerns',
    },
    {
        'role':      'Governor, People\'s Bank of China',
        'name':      'Pan Gongsheng',
        'since':     '2023',
        'note':      'Manages monetary policy; faces property sector crisis and yuan pressure',
        'status':    'active',
        'flag':      '🇨🇳',
        'risk_note': 'Yuan depreciation pressure and capital flight are key stability signals',
    },
]

# ============================================
# SCORING KEYWORDS
# ============================================

ECONOMIC_STRESS_KEYWORDS = {
    5: [
        'china economic collapse', 'china financial crisis',
        'yuan freefall', 'china bank run', 'china default',
        'china recession severe', 'evergrande collapse',
        '中国经济崩溃', '人民币暴跌',
    ],
    4: [
        'china property crisis', 'evergrande bankruptcy',
        'country garden default', 'china youth unemployment',
        'china gdp misses', 'china deflation',
        'china capital flight', 'yuan depreciation',
        'china exports fall', 'china trade war escalates',
        '房地产危机', '青年失业',
    ],
    3: [
        'china economy slows', 'china pmi contracts',
        'china growth warning', 'china stimulus fails',
        'china property downturn', 'china consumer confidence',
        'china debt crisis', 'local government debt china',
        '中国经济放缓', '刺激措施',
    ],
    2: [
        'china economy', 'china gdp', 'china trade',
        'yuan exchange rate', 'china imports exports',
        'china manufacturing', 'china consumption',
        '中国经济', '人民币',
    ],
    1: [
        'china economic', 'china financial',
        '中国金融', '经济',
    ],
}

DOMESTIC_UNREST_KEYWORDS = {
    5: [
        'china uprising', 'china revolution',
        'china mass protests', 'china nationwide protests',
        'tiananmen 2', 'china civil unrest widespread',
        '中国大规模抗议', '全国性示威',
    ],
    4: [
        'china protests', 'china demonstrations',
        'white paper protests', 'china workers strike',
        'china labor dispute', 'china riot',
        'china crackdown protesters', 'china dissidents arrested',
        '中国抗议', '工人罢工',
    ],
    3: [
        'china social unrest', 'china discontent',
        'china censorship circumvented', 'china vpn surge',
        'china social media censored', 'china anger',
        'china online protest', 'china weibo deleted',
        '社会不稳定', '翻墙',
    ],
    2: [
        'china dissent', 'china petition',
        'china human rights', 'china activists',
        '维权', '异见',
    ],
    1: [
        'china protest', 'china unrest',
        '抗议', '示威',
    ],
}

LEADERSHIP_STRESS_KEYWORDS = {
    5: [
        'xi jinping removed', 'xi jinping health critical',
        'china coup', 'politburo standing committee purge',
        'china leadership crisis', 'xi jinping successor',
        '习近平健康', '政变',
    ],
    4: [
        'china purge', 'anti-corruption campaign china',
        'pla generals arrested', 'rocket force purge',
        'china minister removed', 'china official corruption',
        'xi jinping health', 'china succession',
        '肃清', '反腐',
    ],
    3: [
        'china politburo', 'china leadership',
        'xi jinping power', 'china party congress',
        'china cadre removed', 'china official detained',
        '政治局', '习近平权力',
    ],
    2: [
        'xi jinping', 'china communist party',
        'china party leadership', 'china government',
        '习近平', '中共',
    ],
    1: [
        'xi', 'ccp', 'china leadership',
        '中国领导', '党',
    ],
}

MINORITY_SUPPRESSION_KEYWORDS = {
    5: [
        'xinjiang genocide confirmed', 'tibet mass uprising',
        'hong kong independence declared', 'uyghur massacre',
        '新疆种族灭绝', '西藏起义',
    ],
    4: [
        'xinjiang crackdown', 'uyghur detention',
        'tibet protests', 'hong kong crackdown',
        'xinjiang surveillance', 'uyghur forced labor',
        'tibet self-immolation', 'hong kong arrests',
        '新疆镇压', '西藏抗议',
    ],
    3: [
        'xinjiang', 'uyghur', 'tibet',
        'hong kong protest', 'hong kong national security',
        'xinjiang cotton', 'forced labor china',
        '维吾尔', '新疆',
    ],
    2: [
        'minority rights china', 'ethnic tension china',
        'hong kong', 'xinjiang policy',
        '少数民族', '香港',
    ],
    1: [
        'xinjiang', 'tibet', 'hong kong',
        '新疆', '西藏', '香港',
    ],
}

US_CHINA_TENSION_KEYWORDS = {
    5: [
        'us china war declared', 'us china military conflict',
        'china sanctions maximum', 'us decouples china completely',
        '中美战争', '全面制裁',
    ],
    4: [
        'us china tariffs escalate', 'chip ban china expanded',
        'us sanctions china officials', 'china retaliates us',
        'technology war china', 'us china trade war intensifies',
        '芯片禁令', '贸易战升级',
    ],
    3: [
        'us china tariffs', 'chip export controls china',
        'us china sanctions', 'decoupling china',
        'us china technology war', 'china rare earth ban',
        '出口管制', '脱钩',
    ],
    2: [
        'us china relations', 'us china trade',
        'us china technology', 'china sanctions',
        '中美关系', '贸易',
    ],
    1: [
        'us china', 'china america',
        '中美', '中国美国',
    ],
}


# ============================================
# REDIS HELPERS
# ============================================

def _redis_get(key):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        resp = requests.get(
            f"{UPSTASH_REDIS_URL}/get/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            timeout=5
        )
        data = resp.json()
        if data.get('result'):
            return json.loads(data['result'])
    except Exception as e:
        print(f"[China Stability] Redis GET error: {str(e)[:80]}")
    return None


def _redis_set(key, value, ttl=None):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return False
    try:
        payload = json.dumps(value, default=str)
        cmd = ["SET", key, payload]
        if ttl:
            cmd += ["EX", ttl]
        requests.post(
            UPSTASH_REDIS_URL,
            headers={
                "Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                "Content-Type": "application/json"
            },
            json=cmd,
            timeout=5
        )
        return True
    except Exception as e:
        print(f"[China Stability] Redis SET error: {str(e)[:80]}")
    return False


def _redis_lpush_trim(key, value, max_len=168):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return
    try:
        payload = json.dumps(value, default=str)
        requests.post(
            UPSTASH_REDIS_URL,
            headers={
                "Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                "Content-Type": "application/json"
            },
            json=["LPUSH", key, payload],
            timeout=5
        )
        requests.post(
            UPSTASH_REDIS_URL,
            headers={
                "Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                "Content-Type": "application/json"
            },
            json=["LTRIM", key, 0, max_len - 1],
            timeout=5
        )
    except Exception as e:
        print(f"[China Stability] Redis LPUSH error: {str(e)[:80]}")


# ============================================
# LIVE ECONOMIC INDICATORS
# ============================================

def _fetch_yuan_usd():
    """
    Fetch live Yuan/USD exchange rate from exchangerate-api.com (free, no key needed).
    Returns (rate, change_pct, status) where status is 'stable'|'warning'|'stress'.
    """
    try:
        resp = requests.get(
            'https://open.er-api.com/v6/latest/USD',
            timeout=(5, 10)
        )
        if resp.status_code == 200:
            data = resp.json()
            rate = data.get('rates', {}).get('CNY', None)
            if rate:
                # Yuan weakening (higher CNY per USD) = stress signal
                # Historical range: ~6.3 (strong) to ~7.3+ (weak/stress)
                if rate >= 7.3:
                    status = 'stress'
                elif rate >= 7.1:
                    status = 'warning'
                else:
                    status = 'stable'
                print(f"[China Stability] Yuan/USD: {rate:.4f} ({status})")
                return rate, status
    except Exception as e:
        print(f"[China Stability] Yuan/USD fetch error: {str(e)[:80]}")
    return None, 'unknown'


def _fetch_brent_price():
    """
    Fetch live Brent crude oil price.
    Uses Yahoo Finance RSS as a free source — same pattern as ME backend.
    Returns (price, change_pct, status).
    """
    try:
        # Try Yahoo Finance quote for Brent (BZ=F)
        resp = requests.get(
            'https://query1.finance.yahoo.com/v8/finance/chart/BZ=F',
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=(5, 10)
        )
        if resp.status_code == 200:
            data = resp.json()
            meta = data.get('chart', {}).get('result', [{}])[0].get('meta', {})
            price = meta.get('regularMarketPrice') or meta.get('previousClose')
            prev  = meta.get('chartPreviousClose') or meta.get('previousClose')
            if price:
                change_pct = round(((price - prev) / prev) * 100, 2) if prev and prev != 0 else 0.0
                # Brent context for China:
                # High oil = cost pressure on import-dependent China
                # Very high (>100) = significant economic stress
                if price >= 100:
                    status = 'stress'
                elif price >= 85:
                    status = 'elevated'
                else:
                    status = 'normal'
                print(f"[China Stability] Brent: ${price:.2f} ({change_pct:+.2f}%, {status})")
                return round(price, 2), change_pct, status
    except Exception as e:
        print(f"[China Stability] Brent fetch error: {str(e)[:80]}")
    return None, 0.0, 'unknown'


# ============================================================
# HKEX HANG SENG INDEX FETCHER (v1.0 — May 25 2026)
# ============================================================
# Canonical TASE pattern mirror for Hong Kong Stock Exchange.
# Black Swan POC: tracks Chinese economic confidence via HK-listed equity
# performance — same architectural family as TASE-for-Israel, allows
# comparative analysis of how regional conflict signals correlate with
# financial-confidence stress in two adversary-proximate equity markets.
#
# Sourcing strategy (3-tier fallback):
#   Primary:  Yahoo Finance (^HSI)              — free, no key
#   Fallback: Yahoo Finance (^HSCE / 0001.HK)   — alternate Hong Kong tickers
#   Last resort: Cached last-known value        — 7-day Redis TTL
#
# Market-hours awareness: HKEX trades Mon–Fri (Hong Kong Time, UTC+8).
# We don't skip on weekends — Yahoo serves the last close fine — but we
# DO mark the trend label appropriately when market is closed.
# ============================================================
def _fetch_hkex_index():
    """
    Fetch Hong Kong Hang Seng Index (HSI).
    Primary:  Yahoo Finance ^HSI (free, no key)
    Fallback: Yahoo Finance ^HSCE (Hang Seng China Enterprises) / 0001.HK
    Last resort: Cached last-known value (7-day Redis TTL)

    Returns dict matching TASE-pattern schema:
        {index, value, change_pct_24h, trend, source, sparkline, timestamp}
    """
    print("[China Stability] Fetching HKEX Hang Seng...")

    # ── Check HKEX market hours (Mon–Fri, Hong Kong time UTC+8) ──
    hk_tz = timezone(timedelta(hours=8))
    now_hk = datetime.now(hk_tz)
    hkex_closed = now_hk.weekday() in (5, 6)  # 5=Saturday, 6=Sunday
    if hkex_closed:
        print(f"[China Stability] HKEX closed (weekday={now_hk.weekday()}) — Yahoo will serve last close")

    HKEX_LAST_KNOWN_KEY = 'hkex_last_known'

    # ── Primary + Fallback: Yahoo Finance tickers in priority order ──
    # ^HSI = Hang Seng Index (main benchmark, 50 blue-chips)
    # ^HSCE = Hang Seng China Enterprises Index (H-shares, mainland Chinese cos listed in HK)
    # 0001.HK = CK Hutchison (last-ditch sanity check that Yahoo HK feed is alive)
    for ticker in ['^HSI', '^HSCE', '0001.HK']:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval=1d&range=5d"
            r = requests.get(url, timeout=(5, 10), headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            if r.status_code == 200:
                data = r.json()
                result = data.get('chart', {}).get('result', [{}])[0]
                meta = result.get('meta', {})
                price = meta.get('regularMarketPrice')
                prev = meta.get('previousClose') or meta.get('chartPreviousClose')

                # Build sparkline from 5-day daily closes
                sparkline = []
                indicators = result.get('indicators', {}).get('quote', [{}])[0]
                closes = indicators.get('close', []) or []
                timestamps = result.get('timestamp', []) or []
                for ts, c in zip(timestamps, closes):
                    if c is not None:
                        try:
                            sparkline.append({
                                'time': datetime.fromtimestamp(ts, tz=timezone.utc).strftime('%m-%d'),
                                'value': round(float(c), 2)
                            })
                        except Exception:
                            continue

                if price and price > 0:
                    change_pct = ((price - prev) / prev * 100) if prev else 0
                    print(f"[China Stability] ✅ Yahoo {ticker}: {price:,.2f} ({change_pct:+.2f}%) · {len(sparkline)} sparkline pts")

                    # Cache this good value for last-resort use (7-day TTL)
                    try:
                        _redis_set(
                            HKEX_LAST_KNOWN_KEY,
                            {'value': round(price, 2), 'change_pct_24h': round(change_pct, 3), 'index': ticker.replace('^', '')},
                            ttl=7 * 24 * 3600
                        )
                    except Exception:
                        pass

                    return {
                        'index': ticker.replace('^', ''),
                        'value': round(price, 2),
                        'change_pct_24h': round(change_pct, 3),
                        'trend': 'rising' if change_pct > 0.3 else ('falling' if change_pct < -0.3 else 'flat'),
                        'source': 'Yahoo Finance',
                        'sparkline': sparkline,
                        'market_status': 'closed' if hkex_closed else 'open',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
        except Exception as e:
            print(f"[China Stability] Yahoo {ticker} error: {str(e)[:80]}")
            continue

    # ── Last resort: serve cached last-known value ──
    try:
        cached = _redis_get(HKEX_LAST_KNOWN_KEY)
        if cached and isinstance(cached, dict):
            print(f"[China Stability] Using last-known HKEX value: {cached.get('value')}")
            return {
                'index': cached.get('index', 'HSI'),
                'value': cached.get('value'),
                'change_pct_24h': cached.get('change_pct_24h', 0),
                'trend': 'unknown',
                'source': 'Yahoo Finance (last known)',
                'sparkline': [],
                'estimated': True,
                'market_status': 'closed' if hkex_closed else 'unknown',
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        print(f"[China Stability] Last-known HKEX cache read failed: {e}")

    # Nothing worked — return unavailable shape so frontend renders gracefully
    return {
        'index': 'HSI',
        'value': None,
        'change_pct_24h': 0,
        'trend': 'unknown',
        'source': 'Unavailable',
        'sparkline': [],
        'estimated': True,
        'market_status': 'unknown',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }


def _get_economic_indicator_boost(yuan_rate, yuan_status, brent_price, brent_status):
    """
    Convert live economic indicators into an instability level boost (0-2).
    Used to augment the keyword-based economic vector score.
    """
    boost = 0

    if yuan_status == 'stress':
        boost += 2
        print(f"[China Stability] Yuan stress boost: +2 (rate {yuan_rate:.4f})")
    elif yuan_status == 'warning':
        boost += 1
        print(f"[China Stability] Yuan warning boost: +1 (rate {yuan_rate:.4f})")

    if brent_status == 'stress':
        boost += 1
        print(f"[China Stability] Brent stress boost: +1 (${brent_price:.2f})")

    return boost


# ============================================
# ARTICLE FETCHING
# ============================================

def _fetch_newsapi(query, days=3, max_results=30):
    articles = []
    if not NEWSAPI_KEY:
        return []
    try:
        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
        resp = requests.get(
            'https://newsapi.org/v2/everything',
            params={
                'q': query, 'from': from_date,
                'sortBy': 'publishedAt', 'language': 'en',
                'pageSize': max_results, 'apiKey': NEWSAPI_KEY,
            },
            timeout=(5, 15)
        )
        if resp.status_code == 200:
            for a in resp.json().get('articles', []):
                articles.append({
                    'title':       a.get('title', ''),
                    'description': a.get('description', '') or '',
                    'url':         a.get('url', ''),
                    'publishedAt': a.get('publishedAt', ''),
                    'source':      {'name': a.get('source', {}).get('name', 'NewsAPI')},
                    'content':     a.get('content', '') or '',
                    'language':    'en',
                })
            print(f"[China Stability] NewsAPI '{query[:40]}': {len(articles)} articles")
    except Exception as e:
        print(f"[China Stability] NewsAPI error: {str(e)[:80]}")
    return articles


def _fetch_google_news_rss(query, label, max_items=15):
    articles = []
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en"
        resp = requests.get(url, timeout=(5, 15), headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall('.//item')[:max_items]:
                title_el = item.find('title')
                link_el  = item.find('link')
                pub_el   = item.find('pubDate')
                if title_el is not None and title_el.text:
                    articles.append({
                        'title':       title_el.text.strip(),
                        'description': title_el.text.strip(),
                        'url':         link_el.text if link_el is not None else '',
                        'publishedAt': pub_el.text if pub_el is not None else '',
                        'source':      {'name': label},
                        'content':     title_el.text.strip(),
                        'language':    'en',
                    })
        print(f"[China Stability] GNews '{label}': {len(articles)} articles")
    except Exception as e:
        print(f"[China Stability] GNews error: {str(e)[:80]}")
    return articles


# ============================================
# VECTOR SCORING ENGINE
# ============================================

def _score_vector(articles, keyword_map, vector_name):
    """Score a single stability vector against articles. Returns 0-5 level."""
    weighted_score = 0.0
    matched = []
    now = datetime.now(timezone.utc)

    for article in articles:
        title   = (article.get('title', '') or '').lower()
        desc    = (article.get('description', '') or '').lower()
        content = (article.get('content', '') or '').lower()
        text    = f"{title} {desc} {content}"

        article_level   = 0
        matched_trigger = None

        for level in [5, 4, 3, 2, 1]:
            for kw in keyword_map.get(level, []):
                if kw in text:
                    article_level   = level
                    matched_trigger = kw
                    break
            if article_level > 0:
                break

        if article_level == 0:
            continue

        # Time decay
        pub_str   = article.get('publishedAt', '')
        age_hours = 48.0
        if pub_str:
            try:
                pub_dt    = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
                age_hours = max(0.1, (now - pub_dt).total_seconds() / 3600)
            except Exception:
                pass

        decay = 1.0 if age_hours <= 24 else 0.8 if age_hours <= 48 else 0.6 if age_hours <= 72 else 0.4

        # Source weight
        src = (article.get('source', {}).get('name', '') or '').lower()
        src_weight = 1.0 if any(p in src for p in ['reuters', 'ap news', 'bbc', 'ft', 'wsj', 'scmp', 'nikkei']) else \
                     0.85 if any(p in src for p in ['bloomberg', 'economist', 'diplomat', 'cnn', 'guardian']) else \
                     0.4 if 'r/' in src else 0.6

        contribution = article_level * decay * src_weight
        weighted_score += contribution

        if matched_trigger and matched_trigger not in matched:
            matched.append(matched_trigger)

    # Normalize to 0-5
    if weighted_score == 0:   level = 0
    elif weighted_score < 3:  level = 1
    elif weighted_score < 8:  level = 2
    elif weighted_score < 16: level = 3
    elif weighted_score < 28: level = 4
    else:                     level = 5

    print(f"[China Stability] {vector_name}: L{level} (raw score {weighted_score:.1f}, {len(matched)} triggers)")
    return level, matched[:8]


# ============================================
# CROSS-THEATER: READ RHETORIC FINGERPRINT
# ============================================

def _read_rhetoric_level():
    """Read China rhetoric tracker level from cross-theater Redis fingerprint."""
    try:
        fingerprints = _redis_get(CROSSTHEATER_KEY)
        if fingerprints and 'china' in fingerprints:
            china = fingerprints['china']
            level     = china.get('level', 0)
            pla_level = china.get('pla_level', 0)
            xi_level  = china.get('xi_level', 0)
            print(f"[China Stability] Rhetoric fingerprint: L{level} (PLA L{pla_level}, Xi L{xi_level})")
            return level, pla_level, xi_level
    except Exception as e:
        print(f"[China Stability] Rhetoric fingerprint error: {str(e)[:80]}")
    return 0, 0, 0


# ============================================
# COMPOSITE STABILITY SCORE
# ============================================

def _compute_stability_score(vector_levels):
    """
    Compute composite stability score (0-100).
    Higher = MORE stable. Inverted from conflict probability.

    Weights:
      economic     25%
      rhetoric     20%  (from fingerprint)
      unrest       20%
      leadership   15%
      minority     10%
      us_china     10%
    """
    weights = {
        'economic':   0.25,
        'rhetoric':   0.20,
        'unrest':     0.20,
        'leadership': 0.15,
        'minority':   0.10,
        'us_china':   0.10,
    }

    # Each vector level 0-5 contributes to instability
    # Level 0 = no instability signal, Level 5 = maximum instability
    instability_score = sum(
        vector_levels.get(k, 0) * w * 20   # 20 = (100 / 5 levels)
        for k, w in weights.items()
    )

    # Stability = inverse of instability
    stability = max(0, min(100, round(100 - instability_score)))

    # Convergence penalty: if 3+ vectors at L3+, extra -10
    elevated = sum(1 for v in vector_levels.values() if v >= 3)
    if elevated >= 3:
        stability = max(0, stability - 10)
        print(f"[China Stability] Convergence penalty: {elevated} vectors at L3+")

    return stability


def _stability_label(score):
    if score >= 80: return ('Controlled',        '#22c55e')
    if score >= 60: return ('Managed Tension',   '#f59e0b')
    if score >= 40: return ('Elevated Stress',   '#f97316')
    if score >= 20: return ('Systemic Pressure', '#ef4444')
    return              ('Crisis Risk',          '#dc2626')


# ============================================
# MAIN SCAN
# ============================================

def run_china_stability_scan():
    """Full China stability scan. Fetches articles, scores vectors, computes composite score."""
    scan_start = time.time()
    print(f"\n[China Stability] Starting scan at {datetime.now(timezone.utc).isoformat()}")

    # Read rhetoric fingerprint first
    rhetoric_level, pla_level, xi_level = _read_rhetoric_level()

    # Fetch live economic indicators
    yuan_rate, yuan_status                  = _fetch_yuan_usd()
    brent_price, brent_change, brent_status = _fetch_brent_price()
    hkex                                    = _fetch_hkex_index()  # v1.0 May 25 2026 — HKEX HSI fetcher
    econ_indicator_boost = _get_economic_indicator_boost(
        yuan_rate, yuan_status, brent_price, brent_status
    )

    # Fetch articles
    all_articles = []

    queries = [
        ('China economy GDP property crisis yuan', 'GNews:China Economy'),
        ('China protests unrest labor strike social', 'GNews:China Unrest'),
        ('Xi Jinping leadership Politburo purge', 'GNews:China Leadership'),
        ('Xinjiang Uyghur Tibet Hong Kong crackdown', 'GNews:China Minorities'),
        ('US China tariffs sanctions technology decoupling', 'GNews:US-China'),
        ('China PLA military Taiwan South China Sea', 'GNews:China Military'),
    ]

    for query, label in queries:
        try:
            all_articles.extend(_fetch_google_news_rss(query, label))
            time.sleep(0.3)
        except Exception as e:
            print(f"[China Stability] GNews error {label}: {str(e)[:60]}")

    # NewsAPI fallback for economic and unrest
    if NEWSAPI_KEY:
        for query in ['China economy property crisis 2026', 'China protests unrest 2026']:
            try:
                all_articles.extend(_fetch_newsapi(query, days=3))
                time.sleep(0.3)
            except Exception as e:
                print(f"[China Stability] NewsAPI error: {str(e)[:60]}")

    # Deduplicate
    seen = set()
    deduped = []
    for a in all_articles:
        url = (a.get('url', '') or '').split('?')[0].rstrip('/')
        if url and url in seen:
            continue
        if url:
            seen.add(url)
        deduped.append(a)
    all_articles = deduped
    print(f"[China Stability] Total articles after dedup: {len(all_articles)}")

    # Score vectors
    econ_level_raw, econ_triggers = _score_vector(all_articles, ECONOMIC_STRESS_KEYWORDS, 'economic')
    econ_level = min(5, econ_level_raw + econ_indicator_boost)
    if econ_indicator_boost > 0:
        print(f"[China Stability] Economic level boosted: L{econ_level_raw} -> L{econ_level} (live indicators)")
    unrest_level,     unrest_triggers    = _score_vector(all_articles, DOMESTIC_UNREST_KEYWORDS,     'unrest')
    leadership_level, leadership_triggers = _score_vector(all_articles, LEADERSHIP_STRESS_KEYWORDS, 'leadership')
    minority_level,   minority_triggers  = _score_vector(all_articles, MINORITY_SUPPRESSION_KEYWORDS,'minority')
    us_china_level,   us_china_triggers  = _score_vector(all_articles, US_CHINA_TENSION_KEYWORDS,   'us_china')

    vector_levels = {
        'economic':   econ_level,
        'rhetoric':   rhetoric_level,
        'unrest':     unrest_level,
        'leadership': leadership_level,
        'minority':   minority_level,
        'us_china':   us_china_level,
    }

    stability_score = _compute_stability_score(vector_levels)
    label, color    = _stability_label(stability_score)

    scan_time = round(time.time() - scan_start, 1)

    result = {
        'success':         True,
        'scanned_at':      datetime.now(timezone.utc).isoformat(),
        'scan_time_seconds': scan_time,
        'total_articles':  len(all_articles),

        # Composite score
        'stability_score': stability_score,
        'stability_label': label,
        'stability_color': color,

        # Vector breakdown
        'vectors': {
            'economic':   {'level': econ_level,       'triggers': econ_triggers,       'weight': '25%'},
            'rhetoric':   {'level': rhetoric_level,   'triggers': ['from_fingerprint'], 'weight': '20%'},
            'unrest':     {'level': unrest_level,     'triggers': unrest_triggers,     'weight': '20%'},
            'leadership': {'level': leadership_level, 'triggers': leadership_triggers, 'weight': '15%'},
            'minority':   {'level': minority_level,   'triggers': minority_triggers,   'weight': '10%'},
            'us_china':   {'level': us_china_level,   'triggers': us_china_triggers,   'weight': '10%'},
        },

        # Rhetoric sub-levels
        'rhetoric_level':  rhetoric_level,
        'pla_level':       pla_level,
        'xi_level':        xi_level,

        # Leadership reference data
        'leadership':      CHINA_LEADERSHIP,

        # Shorthand for frontend card
        'econ_level':      econ_level,
        'unrest_level':    unrest_level,
        'leadership_level': leadership_level,
        'minority_level':  minority_level,
        'us_china_level':  us_china_level,

        # Live economic indicators
        'yuan_usd':          yuan_rate,
        'yuan_status':       yuan_status,
        'brent_price':       brent_price,
        'brent_change_pct':  brent_change,
        'brent_status':      brent_status,
        'hkex':              hkex,                  # v1.0 May 25 2026 — HKEX Hang Seng (canonical TASE-pattern)
        'econ_indicator_boost': econ_indicator_boost,

        'version': '1.0.0-china-stability',
    }

    # Cache to Redis
    _redis_set(CACHE_KEY, result, ttl=CACHE_TTL)

    # History snapshot
    _redis_lpush_trim(HISTORY_KEY, {
        'ts':              datetime.now(timezone.utc).isoformat(),
        'stability_score': stability_score,
        'label':           label,
        'econ_level':      econ_level,
        'unrest_level':    unrest_level,
        'rhetoric_level':  rhetoric_level,
        'leadership_level': leadership_level,
    })

    print(f"[China Stability] Scan complete in {scan_time}s | "
          f"Score: {stability_score}/100 ({label})")
    return result


# ============================================
# BACKGROUND REFRESH
# ============================================

def _background_loop():
    print("[China Stability] Background thread started (12h cycle)")
    time.sleep(240)   # 4 min stagger after boot
    while True:
        try:
            run_china_stability_scan()
        except Exception as e:
            print(f"[China Stability] Background scan error: {str(e)[:200]}")
        time.sleep(SCAN_INTERVAL_HOURS * 3600)


# ============================================
# FLASK ENDPOINT REGISTRATION
# ============================================

def register_china_stability_endpoints(app):
    """Register China stability endpoints on the Flask app."""

    @app.route('/api/china/stability', methods=['GET'])
    def api_china_stability():
        """
        China Stability Index — composite score across 6 vectors.
        ?force=true to bypass cache and run fresh scan.
        """
        force = request.args.get('force', 'false').lower() == 'true'

        if not force:
            cached = _redis_get(CACHE_KEY)
            if cached:
                cached['from_cache'] = True
                return jsonify(cached)

        global _stability_running
        with _stability_lock:
            if _stability_running:
                cached = _redis_get(CACHE_KEY)
                if cached:
                    cached['from_cache'] = True
                    cached['scan_in_progress'] = True
                    return jsonify(cached)
                return jsonify({'success': False, 'error': 'Scan in progress'}), 202
            _stability_running = True

        try:
            result = run_china_stability_scan()
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200]}), 500
        finally:
            with _stability_lock:
                _stability_running = False

    @app.route('/api/china/stability/summary', methods=['GET'])
    def api_china_stability_summary():
        """Lightweight summary for frontend card rendering."""
        cached = _redis_get(CACHE_KEY)
        if not cached:
            return jsonify({
                'success': False,
                'error': 'No data yet — run /api/china/stability?force=true'
            }), 404
        return jsonify({
            'success':          True,
            'scanned_at':       cached.get('scanned_at'),
            'stability_score':  cached.get('stability_score', 0),
            'stability_label':  cached.get('stability_label', 'Unknown'),
            'stability_color':  cached.get('stability_color', '#6b7280'),
            'econ_level':       cached.get('econ_level', 0),
            'unrest_level':     cached.get('unrest_level', 0),
            'rhetoric_level':   cached.get('rhetoric_level', 0),
            'leadership_level': cached.get('leadership_level', 0),
            'minority_level':   cached.get('minority_level', 0),
            'us_china_level':   cached.get('us_china_level', 0),
            'pla_level':        cached.get('pla_level', 0),
            'xi_level':         cached.get('xi_level', 0),
            'leadership':       cached.get('leadership', CHINA_LEADERSHIP),
            'total_articles':   cached.get('total_articles', 0),
            'yuan_usd':         cached.get('yuan_usd'),
            'yuan_status':      cached.get('yuan_status', 'unknown'),
            'brent_price':      cached.get('brent_price'),
            'brent_change_pct': cached.get('brent_change_pct', 0),
            'brent_status':     cached.get('brent_status', 'unknown'),
            'hkex':             cached.get('hkex', {}),     # v1.0 May 25 2026
            'version':          '1.0.0-china-stability',
        })

    @app.route('/api/china/stability/history', methods=['GET'])
    def api_china_stability_history():
        """Return stability history for trend chart."""
        history = _redis_get(HISTORY_KEY)
        if not isinstance(history, list):
            history = []
        return jsonify({
            'success': True,
            'count':   len(history),
            'history': history[:120],
        })

    # Start background thread
    bg = threading.Thread(target=_background_loop, daemon=True)
    bg.start()

    print("[China Stability] Endpoints registered: "
          "/api/china/stability, /api/china/stability/summary, /api/china/stability/history")
