"""
rhetoric_tracker_afghanistan.py -- Asifah Analytics Asia Backend -- v1.0.0 Jul 2026
Cloned from rhetoric_tracker_afghanistan.py (contract donor -- the afghanistan-stability
page consumes this exact payload shape) with Asia-backend conventions.

CONTESTED-NODE TRACKER (Azerbaijan schema): Afghanistan sits on four wheels of
MIXED polarity -- Iran (friction), Pakistan (kinetic), Russia (normalization),
China (extraction). No coalition; four separate wheels, each managing Kabul
for its own reasons. Multi-wheel convergence is the GPI-relevant signal.

ACTORS (11): taliban_kabul, taliban_kandahar, haqqani_interior, drug_economy,
  iskp, ttp, pakistan_state, iran_afghanistan, russia_engagement,
  china_engagement, un_rights
VECTORS (4 -- these keys ARE the page gauge contract):
  kinetic_afpak, repression_rights, external_friction, illicit_economy
CROSS-READS: humanitarian:afghanistan:latest (disaster strain, VZ pattern,
  +1.2/+0.6 recency-decayed on the 0-10 composite) + Asia commodity proxy.
EMITS: rhetoric:afghanistan:latest + crosstheater:afghanistan:fingerprint
  (hub_presence 4 wheels + node_class 'contested' + contested_signal >=3).
ENDPOINTS: /api/rhetoric/afghanistan (+ /summary /history, ?force=true)
Convergence, not prediction. The reader completes the inference.
"""

import os
import re
import json
import time
import threading
import traceback
from datetime import datetime, timezone, timedelta

import requests

# Optional dependencies — degrade gracefully if missing
try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    print("[AFG Rhetoric] ⚠️  feedparser unavailable — RSS disabled")

# Cross-tracker commodity fingerprints — read via local WHA proxy.
# Architecture note: rhetoric_tracker_afghanistan lives on the WHA backend, but
# commodity_tracker.py lives on the ME backend. We don't import across
# backends — instead, the WHA backend has commodity_proxy_wha.py which
# caches commodity fingerprints in WHA-local Redis with a 1-hour TTL.
# This tracker calls the WHA-local proxy endpoint (same Flask app —
# resolves over localhost or the public URL with negligible overhead).
ASIA_BACKEND_SELF_URL = os.environ.get(
    'ASIA_BACKEND_SELF_URL',
    'http://localhost:10000'  # default Render port for in-process calls
)
COMMODITY_FINGERPRINT_AVAILABLE = True  # always — we use HTTP proxy, not import

print("[AFG Rhetoric] Module loading...")

# Try to import signal interpreter for prose generation
try:
    from afghanistan_signal_interpreter import (
        build_top_signals,
        build_executive_summary,
        build_so_what_factor,
        score_alignment_drift,
        build_alignment_drift_top_signal,
    )
    AFG_INTERPRETER_AVAILABLE = True
    print("[AFG Rhetoric] ✅ Signal interpreter loaded")
except ImportError:
    AFG_INTERPRETER_AVAILABLE = False
    print("[AFG Rhetoric] ⚠️  afghanistan_signal_interpreter unavailable (will ship in shipment 2)")

# ============================================
# CONFIGURATION
# ============================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN')
NEWSAPI_KEY         = os.environ.get('NEWSAPI_KEY')
BRAVE_API_KEY       = os.environ.get('BRAVE_API_KEY')

CACHE_TTL_HOURS                = 12
BACKGROUND_REFRESH_HOURS       = 12
INITIAL_SCAN_DELAY_SECONDS     = 90
CROSSTHEATER_FINGERPRINT_TTL_HOURS = 13   # 12h refresh + 1h buffer

REDIS_KEY_LATEST       = 'rhetoric:afghanistan:latest'
HISTORY_KEY            = 'rhetoric:afghanistan:history'   # canonical snapshot index (May 22 2026 — read by wha_regional_bluf.prose_v2)
REDIS_KEY_FINGERPRINT_AXIS         = 'rhetoric:afghanistan:china_axis_active'
REDIS_KEY_FINGERPRINT_CHANCAY      = 'rhetoric:afghanistan:chancay_pressure'
REDIS_KEY_FINGERPRINT_MINING       = 'rhetoric:afghanistan:mining_disruption'

GDELT_BASE_URL   = 'https://api.gdeltproject.org/api/v2/doc/doc'
NEWSAPI_BASE_URL = 'https://newsapi.org/v2/everything'
BRAVE_BASE_URL   = 'https://api.search.brave.com/res/v1/news/search'


# ============================================
# ALERT-LEVEL THRESHOLDS (per actor)
# ============================================
# Score → alert level mapping. These are tuned for an 8-actor 4-vector model
# at typical Afghanistan news volume (~50-150 articles/scan). Compare to baseline
# statements_per_week in each actor definition to detect surge conditions.
def actor_alert_level(score, baseline):
    """Map a numeric actor-score to a discrete alert level using the actor's baseline."""
    if score < baseline * 0.5:
        return 'low'
    if score < baseline * 1.0:
        return 'normal'
    if score < baseline * 1.8:
        return 'elevated'
    if score < baseline * 2.8:
        return 'high'
    return 'surge'


# ============================================
# ACTOR DEFINITIONS — 8 actors total
# ============================================
ACTORS = {
    # ════════════ TALIBAN / DOMESTIC (4) ════════════
    'taliban_kabul': {
        'name': 'Taliban — Kabul Cabinet', 'flag': '🇦🇫', 'icon': '🏛️', 'color': '#e2e8f0',
        'role': 'Governing voice — spokesmen, ministries, diplomacy',
        'description': 'Zabihullah Mujahid + ministry spokesmen + FM Muttaqi: the Emirate\'s public-facing governance and engagement track.',
        'vector': 'external_friction',
        'keywords': ['zabihullah mujahid','taliban spokesman','islamic emirate','amir khan muttaqi',
                     'taliban foreign ministry','taliban government','kabul government','taliban cabinet',
                     'mohammad hasan akhund','taliban statement','emirate statement',
                     'طالبان','امارت اسلامی','ذبیح الله مجاهد','متقی'],
        'baseline_statements_per_week': 10,
    },
    'taliban_kandahar': {
        'name': 'Kandahar — Emir & Clerical Circle', 'flag': '🇦🇫', 'icon': '📜', 'color': '#a855f7',
        'role': 'Supreme authority — decrees, morality enforcement, repression driver',
        'description': 'Haibatullah Akhundzada decrees + PVPV (vice-and-virtue) enforcement + edicts on women, education, media. The repression signal source.',
        'vector': 'repression_rights',
        'keywords': ['haibatullah akhundzada','akhundzada decree','taliban decree','supreme leader taliban',
                     'vice and virtue','pvpv','morality law taliban','taliban edict','kandahar shura',
                     'women ban afghanistan','girls education ban','flogging afghanistan','public execution afghanistan',
                     'هبت الله آخوندزاده','فرمان طالبان','امر بالمعروف'],
        'baseline_statements_per_week': 4,
    },
    'haqqani_interior': {
        'name': 'Haqqani / Interior', 'flag': '🇦🇫', 'icon': '🛡️', 'color': '#f97316',
        'role': 'Interior ministry + internal fault line vs Kandahar',
        'description': 'Sirajuddin Haqqani and Interior: security operations, ISKP counterops, and the pragmatist-vs-cleric friction that is the regime\'s principal internal fault line.',
        'vector': 'kinetic_afpak',
        'keywords': ['sirajuddin haqqani','haqqani network','taliban interior ministry','haqqani speech',
                     'taliban internal rift','taliban divisions','kandahar kabul rift',
                     'سراج الدین حقانی','وزارت داخله'],
        'baseline_statements_per_week': 3,
    },
    'drug_economy': {
        'name': 'Illicit Economy Watch', 'flag': '💊', 'icon': '📦', 'color': '#84cc16',
        'role': 'Meth surge, opium stockpiles, trafficking corridors (post-ban)',
        'description': 'UNODC reporting + seizure news: post-2022-ban economy is meth (ephedra), stockpile drawdown, and trafficking-corridor friction with Iran/Pakistan/Central Asia.',
        'vector': 'illicit_economy',
        'keywords': ['afghanistan methamphetamine','afghan meth','ephedra afghanistan','unodc afghanistan',
                     'opium stockpile','afghan opium','poppy ban','drug seizure afghanistan','afghan heroin',
                     'drug trafficking afghanistan','narcotics afghanistan'],
        'baseline_statements_per_week': 3,
    },
    # ════════════ KINETIC ADVERSARIES (2) ════════════
    'iskp': {
        'name': 'ISIS-Khorasan (ISKP)', 'flag': '☠️', 'icon': '💣', 'color': '#dc2626',
        'role': 'Terror-export vector — attacks + claims + external plots',
        'description': 'ISKP activity reporting: attacks in Afghanistan AND external operations (Moscow, Kerman, Europe plots). External attribution = two-theater signal by construction.',
        'vector': 'kinetic_afpak',
        'keywords': ['iskp','isis-k','isis khorasan','islamic state khorasan','isis-kp',
                     'iskp attack','iskp claim','isis afghanistan','kabul bombing','kabul attack',
                     'iskp plot','isis-k plot','داعش خراسان','داعش'],
        'baseline_statements_per_week': 5,
    },
    'ttp': {
        'name': 'TTP (Pakistani Taliban)', 'flag': '🇵🇰', 'icon': '⚔️', 'color': '#b91c1c',
        'role': 'Cross-border kinetic driver — the sanctuary dispute',
        'description': 'Tehrik-e-Taliban Pakistan attacks and claims: the core of Islamabad\'s case against Kabul and the primary Af-Pak kinetic driver.',
        'vector': 'kinetic_afpak',
        'keywords': ['ttp','tehrik-e-taliban','tehreek-e-taliban','pakistani taliban','ttp attack','ttp claim',
                     'ttp sanctuary','ttp afghanistan','تحریک طالبان پاکستان'],
        'baseline_statements_per_week': 6,
    },
    # ════════════ THE FOUR WHEELS (4) ════════════
    'pakistan_state': {
        'name': 'Pakistan (State)', 'flag': '🇵🇰', 'icon': '🪖', 'color': '#16a34a',
        'role': 'Kinetic wheel — strikes, closures, deportations, Durand Line',
        'description': 'ISPR + MOFA + military statements on Afghanistan: cross-border strikes, Torkham/Chaman closures, deportation waves as pressure levers.',
        'vector': 'kinetic_afpak',
        'keywords': ['pakistan strike afghanistan','pakistan airstrike afghan','ispr afghanistan','pakistan afghanistan border',
                     'torkham','chaman border','durand line','pakistan deport afghan','afghan refugees pakistan deport',
                     'pakistan foreign office afghanistan','pakistan taliban talks'],
        'baseline_statements_per_week': 8,
    },
    'iran_afghanistan': {
        'name': 'Iran (re: Afghanistan)', 'flag': '🇮🇷', 'icon': '💧', 'color': '#0ea5e9',
        'role': 'Friction wheel — water, deportations, border incidents, pragmatic trade',
        'description': 'Iranian MFA/officials on Afghanistan: Helmand River treaty enforcement, mass deportations of Afghans, Herat border incidents, fuel trade. Mixed polarity by design.',
        'vector': 'external_friction',
        'keywords': ['iran afghanistan','helmand river','helmand water','hirmand','iran deport afghan',
                     'afghan migrants iran','iran taliban','iran afghan border','herat border iran',
                     'هیرمند','اخراج مهاجران افغان'],
        'baseline_statements_per_week': 5,
    },
    'russia_engagement': {
        'name': 'Russia (Engagement)', 'flag': '🇷🇺', 'icon': '🤝', 'color': '#64748b',
        'role': 'Normalization wheel — recognition, ISKP counterterror, Central Asia buffer',
        'description': 'Moscow\'s formal recognition (2025) and engagement track: Kabulov/Lavrov statements, security cooperation vs ISKP, trade corridors.',
        'vector': 'external_friction',
        'keywords': ['russia taliban','russia recognize taliban','russia afghanistan','kabulov','lavrov afghanistan',
                     'moscow taliban','russia recognition emirate','russia iskp'],
        'baseline_statements_per_week': 3,
    },
    'china_engagement': {
        'name': 'China (Extraction)', 'flag': '🇨🇳', 'icon': '⛏️', 'color': '#eab308',
        'role': 'Extraction wheel — Mes Aynak, Amu Darya oil, Wakhan security',
        'description': 'Beijing\'s economic-foothold track: Mes Aynak copper (MCC), Amu Darya oil, ambassador-level engagement, Wakhan/ETIM security anxieties.',
        'vector': 'external_friction',
        'keywords': ['china taliban','china afghanistan','mes aynak','amu darya oil','mcc afghanistan',
                     'china ambassador kabul','wakhan corridor','china mining afghanistan','belt and road afghanistan'],
        'baseline_statements_per_week': 3,
    },
    # ════════════ RIGHTS EVIDENCE STREAM (1) ════════════
    'un_rights': {
        'name': 'UN / UNAMA Rights Reporting', 'flag': '🇺🇳', 'icon': '⚖️', 'color': '#38bdf8',
        'role': 'Repression evidence stream — UNAMA, OHCHR, special rapporteur',
        'description': 'UN human-rights reporting on Afghanistan: the documented evidence layer for the repression/rights vector (women\'s rights, corporal punishment, media).',
        'vector': 'repression_rights',
        'keywords': ['unama','un afghanistan human rights','richard bennett afghanistan','ohchr afghanistan',
                     'un women afghanistan','gender apartheid','un report taliban','human rights watch afghanistan',
                     'amnesty afghanistan'],
        'baseline_statements_per_week': 4,
    },
}

# Helper sets for downstream classification logic
DOMESTIC_ACTORS = ['taliban_kabul', 'taliban_kandahar', 'haqqani_interior', 'drug_economy']
EXTERNAL_ACTORS = ['pakistan_state', 'iran_afghanistan', 'russia_engagement', 'china_engagement']
RESOURCE_ACTORS = ['drug_economy']
ALIGNMENT_ACTORS = {'russia_engagement': 'external_friction', 'china_engagement': 'external_friction'}

# Vector groupings for the 4-vector composite score
VECTOR_GROUPS = {
    'kinetic_afpak':      ['ttp', 'pakistan_state', 'iskp', 'haqqani_interior'],
    'repression_rights':  ['taliban_kandahar', 'un_rights'],
    'external_friction':  ['iran_afghanistan', 'russia_engagement', 'china_engagement', 'taliban_kabul'],
    'illicit_economy':    ['drug_economy'],
}


# ============================================
# TRIPWIRES — high-severity events that escalate alert level regardless of volume
# ============================================
TRIPWIRES = {
    'iskp_external_attack': {
        'patterns': ['iskp attack moscow','isis-k attack iran','iskp attack europe','isis-k plot',
                     'iskp external attack','isis khorasan attack','crocus','kerman bombing'],
        'severity': 'surge',
        'note': 'ISKP external operation attributed to Afghan-based planning -- two-theater signal.',
    },
    'pakistan_strikes_afghanistan': {
        'patterns': ['pakistan airstrike afghanistan','pakistan strikes afghanistan','pakistani jets afghanistan',
                     'pakistan bombs afghan','cross-border strike afghanistan'],
        'severity': 'surge',
        'note': 'Kinetic escalation across the Durand Line.',
    },
    'border_closure': {
        'patterns': ['torkham closed','chaman closed','torkham closure','border crossing closed afghanistan',
                     'pakistan closes border afghanistan'],
        'severity': 'high',
        'note': 'Trade/humanitarian chokepoint -- doubles as a pressure lever.',
    },
    'mass_repression_event': {
        'patterns': ['public execution afghanistan','mass flogging','taliban execute','stadium execution',
                     'new decree women afghanistan','women banned afghanistan'],
        'severity': 'high',
        'note': 'Repression escalation event -- rights vector spike.',
    },
    'helmand_water_clash': {
        'patterns': ['iran afghanistan border clash','helmand clash','iran taliban clash','hirmand clash',
                     'iran afghan border fire'],
        'severity': 'high',
        'note': 'Water-friction kinetic event on the Iran wheel.',
    },
    'recognition_event': {
        'patterns': ['recognizes taliban','recognises taliban','recognize islamic emirate','formal recognition taliban',
                     'establishes ties taliban'],
        'severity': 'elevated',
        'note': 'Normalization milestone -- reshapes the wheel map.',
    },
    'mass_deportation_wave': {
        'patterns': ['mass deportation afghans','deport afghan refugees','expel afghan migrants',
                     'deportation wave afghanistan'],
        'severity': 'elevated',
        'note': 'Forced-return reabsorption pressure (Iran/Pakistan lever).',
    },
}

RSS_FEEDS = {
    'gn_en':   {'url': 'https://news.google.com/rss/search?q=Afghanistan%20(Taliban%20OR%20ISKP%20OR%20TTP%20OR%20Kabul)&hl=en-US&gl=US&ceid=US:en', 'name': 'GoogleNews-EN', 'weight': 0.85, 'language': 'en'},
    'gn_dari': {'url': 'https://news.google.com/rss/search?q=%D8%A7%D9%81%D8%BA%D8%A7%D9%86%D8%B3%D8%AA%D8%A7%D9%86&hl=fa&gl=AF&ceid=AF:fa', 'name': 'GoogleNews-Dari', 'weight': 0.8, 'language': 'fa'},
    'gn_ps':   {'url': 'https://news.google.com/rss/search?q=%D8%A7%D9%81%D8%BA%D8%A7%D9%86%D8%B3%D8%AA%D8%A7%D9%86&hl=ps&gl=AF&ceid=AF:ps', 'name': 'GoogleNews-Pashto', 'weight': 0.8, 'language': 'ps'},
    'tolo':    {'url': 'https://tolonews.com/rss', 'name': 'TOLOnews', 'weight': 1.0, 'language': 'en'},
    'pajhwok': {'url': 'https://pajhwok.com/feed/', 'name': 'Pajhwok', 'weight': 1.0, 'language': 'en'},
    'hasht':   {'url': 'https://8am.media/feed/', 'name': 'Hasht-e Subh', 'weight': 0.95, 'language': 'fa'},
    'bbc_ps':  {'url': 'https://feeds.bbci.co.uk/pashto/rss.xml', 'name': 'BBC Pashto', 'weight': 1.0, 'language': 'ps'},
    'bbc_fa':  {'url': 'https://feeds.bbci.co.uk/persian/afghanistan/rss.xml', 'name': 'BBC Persian AFG', 'weight': 1.0, 'language': 'fa'},
}

GDELT_QUERIES_EN = [
    '"Taliban" AND ("decree" OR "statement" OR "spokesman")',
    '"Afghanistan" AND ("ISKP" OR "ISIS-K" OR "TTP")',
    '"Afghanistan" AND ("Pakistan" OR "border" OR "Durand")',
    '"Afghanistan" AND ("Iran" OR "Helmand" OR "deportation")',
]
GDELT_QUERIES_ES = [
    'طالبان',            # Taliban (fas)
    'افغانستان پاکستان',  # Afghanistan Pakistan (fas)
]


# ============================================
# CACHE / REDIS HELPERS
# ============================================
CACHE_FILE = '/tmp/afghanistan_rhetoric_cache.json'
_background_scan_running = False
_background_scan_lock = threading.Lock()
_last_scan_started_at = None


def _redis_get(key):
    """Read a JSON value from Upstash Redis. Returns None if unavailable / missing."""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        resp = requests.get(
            f"{UPSTASH_REDIS_URL}/get/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            timeout=8
        )
        if resp.status_code != 200:
            return None
        body = resp.json()
        raw = body.get('result')
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        print(f"[AFG Rhetoric] Redis GET error ({key}): {str(e)[:120]}")
        return None


def _redis_set(key, value, ttl_hours=CACHE_TTL_HOURS):
    """Write a JSON value to Upstash Redis with TTL. Returns True on success."""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return False
    try:
        ttl_seconds = int(ttl_hours * 3600)
        url = f"{UPSTASH_REDIS_URL}/setex/{key}/{ttl_seconds}"
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            data=json.dumps(value, default=str),
            timeout=8
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[AFG Rhetoric] Redis SET error ({key}): {str(e)[:120]}")
        return False


def load_cache():
    """Try Redis first, fallback to /tmp file."""
    cached = _redis_get(REDIS_KEY_LATEST)
    if cached:
        return cached
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _redis_lpush_trim(key, value, max_len=336):
    """LPUSH + LTRIM to keep rolling history (336 = 14 days × 24 hourly entries).
    Canonical helper added May 22 2026 — mirrors Cuba pattern, read by wha_regional_bluf.prose_v2.
    Uses same direct-key style as _redis_set (Upstash accepts colons in keys without encoding)."""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return False
    try:
        # LPUSH the new entry
        resp = requests.post(
            f"{UPSTASH_REDIS_URL}/lpush/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            data=json.dumps(value, default=str),
            timeout=8,
        )
        if resp.status_code != 200:
            return False
        # LTRIM to bound buffer length
        requests.post(
            f"{UPSTASH_REDIS_URL}/ltrim/{key}/0/{max_len - 1}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            timeout=8,
        )
        return True
    except Exception as e:
        print(f"[AFG Rhetoric] Redis LPUSH error ({key}): {str(e)[:120]}")
        return False


def save_cache(data):
    """Save to Redis + /tmp fallback."""
    data['cached_at'] = datetime.now(timezone.utc).isoformat()
    if _redis_set(REDIS_KEY_LATEST, data, ttl_hours=CACHE_TTL_HOURS):
        print("[AFG Rhetoric] ✅ Saved to Redis")
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    except Exception as e:
        print(f"[AFG Rhetoric] /tmp save error: {e}")


def is_cache_fresh(data):
    """Check if cache is younger than CACHE_TTL_HOURS."""
    if not data or 'cached_at' not in data:
        return False
    try:
        cached_at = datetime.fromisoformat(data['cached_at'])
        age = datetime.now(timezone.utc) - cached_at
        return age.total_seconds() < (CACHE_TTL_HOURS * 3600)
    except Exception:
        return False


# ============================================
# DATA FETCHERS — RSS / GDELT / NewsAPI / Brave
# ============================================
def fetch_rss_articles(feed_id, feed_config, max_articles=30):
    """Fetch + parse a single RSS feed."""
    if not FEEDPARSER_AVAILABLE:
        return []
    articles = []
    try:
        feed = feedparser.parse(feed_config['url'])
        for entry in feed.entries[:max_articles]:
            articles.append({
                'title':       entry.get('title', ''),
                'description': entry.get('summary', '') or entry.get('description', ''),
                'url':         entry.get('link', ''),
                'published':   entry.get('published', ''),
                'source':      feed_config['name'],
                'feed_id':     feed_id,
                'feed_type':   'rss',
                'language':    feed_config.get('language', 'en'),
                'feed_weight': feed_config.get('weight', 1.0),
            })
    except Exception as e:
        print(f"[AFG Rhetoric] RSS fetch error ({feed_id}): {str(e)[:120]}")
    return articles


def fetch_all_rss():
    all_articles = []
    for feed_id, feed_config in RSS_FEEDS.items():
        articles = fetch_rss_articles(feed_id, feed_config)
        if articles:
            print(f"[AFG Rhetoric] RSS {feed_id}: {len(articles)} articles")
        all_articles.extend(articles)
    return all_articles


def fetch_gdelt_query(query, language='eng', days=7, max_articles=50):
    """Fetch a single GDELT query with circuit-breaker timeout."""
    params = {
        'query':       f'{query} sourcelang:{language}',
        'mode':        'artlist',
        'maxrecords':  max_articles,
        'format':      'json',
        'timespan':    f'{days}d',
    }
    try:
        resp = requests.get(GDELT_BASE_URL, params=params, timeout=(5, 12))
        if resp.status_code == 429:
            return []  # rate limited — bail silently
        if resp.status_code != 200:
            return []
        data = resp.json()
        articles = []
        for item in data.get('articles', []):
            articles.append({
                'title':       item.get('title', ''),
                'description': '',
                'url':         item.get('url', ''),
                'published':   item.get('seendate', ''),
                'source':      item.get('domain', 'GDELT'),
                'feed_id':     'gdelt',
                'feed_type':   'gdelt',
                'language':    'fa' if language == 'fas' else 'en',
                'feed_weight': 0.85,
            })
        return articles
    except Exception:
        return []


def fetch_all_gdelt(days=7):
    all_articles = []
    for q in GDELT_QUERIES_EN:
        all_articles.extend(fetch_gdelt_query(q, language='eng', days=days))
        time.sleep(0.5)
    for q in GDELT_QUERIES_ES:
        all_articles.extend(fetch_gdelt_query(q, language='fas', days=days))
        time.sleep(0.5)
    print(f"[AFG Rhetoric] GDELT: {len(all_articles)} articles")
    return all_articles


def fetch_newsapi(query, days=7):
    """Fetch from NewsAPI."""
    if not NEWSAPI_KEY:
        return []
    from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
    params = {
        'q':        query,
        'from':     from_date,
        'language': 'en',
        'sortBy':   'publishedAt',
        'pageSize': 30,
        'apiKey':   NEWSAPI_KEY,
    }
    try:
        resp = requests.get(NEWSAPI_BASE_URL, params=params, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        articles = []
        for item in data.get('articles', []):
            articles.append({
                'title':       item.get('title', ''),
                'description': item.get('description', ''),
                'url':         item.get('url', ''),
                'published':   item.get('publishedAt', ''),
                'source':      (item.get('source') or {}).get('name', 'NewsAPI'),
                'feed_id':     'newsapi',
                'feed_type':   'newsapi',
                'language':    'en',
                'feed_weight': 0.9,
            })
        return articles
    except Exception:
        return []


def fetch_all_newsapi(days=7):
    queries = [
        'Taliban decree OR statement',
        'Afghanistan Pakistan border OR strike',
        'ISKP OR "ISIS-K" attack',
        'TTP attack OR claim',
        'Afghanistan Iran Helmand OR deportation',
        'Russia OR China Taliban engagement',
        'Afghanistan UNAMA OR "human rights"',
    ]
    all_articles = []
    for q in queries:
        all_articles.extend(fetch_newsapi(q, days=days))
        time.sleep(0.5)
    if all_articles:
        print(f"[AFG Rhetoric] NewsAPI: {len(all_articles)} articles")
    return all_articles


def fetch_brave(query, days=7):
    """Brave Search News API — tertiary fallback."""
    if not BRAVE_API_KEY:
        return []
    params = {'q': query, 'count': 20, 'spellcheck': '0'}
    try:
        resp = requests.get(
            BRAVE_BASE_URL,
            params=params,
            headers={
                'Accept':                'application/json',
                'Accept-Encoding':       'gzip',
                'X-Subscription-Token':  BRAVE_API_KEY,
            },
            timeout=10
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        articles = []
        for item in data.get('results', []):
            articles.append({
                'title':       item.get('title', ''),
                'description': item.get('description', ''),
                'url':         item.get('url', ''),
                'published':   item.get('age', ''),
                'source':      (item.get('source') or '') or 'Brave',
                'feed_id':     'brave',
                'feed_type':   'brave',
                'language':    'en',
                'feed_weight': 0.75,
            })
        return articles
    except Exception:
        return []


def fetch_all_brave(days=7, gdelt_count=0, newsapi_count=0):
    """Brave fallback — only fires when GDELT + NewsAPI returned <10 articles total."""
    if gdelt_count + newsapi_count >= 10:
        return []
    queries = [
        'Taliban Afghanistan 2026',
        'Pakistan Afghanistan border strike',
        'ISKP attack',
        'Afghanistan earthquake OR deportation',
    ]
    all_articles = []
    for q in queries:
        all_articles.extend(fetch_brave(q, days=days))
        time.sleep(0.5)
    if all_articles:
        print(f"[AFG Rhetoric] Brave fallback: {len(all_articles)} articles")
    return all_articles


# ============================================
# CLASSIFICATION + SCORING
# ============================================
def _normalize_text(text):
    """Lowercase + strip diacritics-light for keyword matching."""
    return (text or '').lower()


def _classify_article_actor(article):
    """
    Match an article against actor keyword lists. Returns (actor_id, hit_count) tuples
    for all matching actors. Multi-actor matching is allowed (e.g., a "Boluarte visits
    Las Bambas" headline can hit both presidency AND las_bambas).
    """
    title = _normalize_text(article.get('title', ''))
    desc  = _normalize_text(article.get('description', ''))
    text  = title + ' ' + desc

    matches = []
    for actor_id, actor_data in ACTORS.items():
        hit_count = 0
        for kw in actor_data['keywords']:
            if kw.lower() in text:
                hit_count += 1
        if hit_count > 0:
            matches.append((actor_id, hit_count))
    return matches


def _check_tripwires(text):
    """Check article text against TRIPWIRES patterns. Returns list of (tripwire_id, severity)."""
    text_lower = _normalize_text(text)
    triggered = []
    for tw_id, tw_data in TRIPWIRES.items():
        for pattern in tw_data['patterns']:
            if pattern.lower() in text_lower:
                triggered.append((tw_id, tw_data['severity']))
                break  # only count each tripwire once per article
    return triggered


def _score_actor_articles(articles_for_actor, actor_id):
    """
    Compute weighted score for an actor: sum of (feed_weight × keyword-density × recency).
    Returns dict with score, article_count, language_breakdown, sources, top_articles, tripwires.
    """
    if not articles_for_actor:
        return {
            'score': 0,
            'article_count': 0,
            'language_breakdown': {},
            'sources': [],
            'top_articles': [],
            'tripwires': [],
        }

    score = 0
    lang_count = {}
    src_count = {}
    tripwires_seen = set()

    for art in articles_for_actor:
        feed_w = art.get('feed_weight', 1.0)
        kw_hits = art.get('_actor_hits', 1)  # set by classifier
        kw_factor = min(1.0 + (kw_hits - 1) * 0.15, 2.0)  # diminishing returns
        article_score = feed_w * kw_factor
        score += article_score

        lang = art.get('language', 'en')
        lang_count[lang] = lang_count.get(lang, 0) + 1
        src = art.get('source', 'Unknown')
        src_count[src] = src_count.get(src, 0) + 1

        # Tripwire check
        full_text = f"{art.get('title', '')} {art.get('description', '')}"
        for tw_id, severity in _check_tripwires(full_text):
            tripwires_seen.add((tw_id, severity))

    # Sort articles by article_score descending
    sorted_articles = sorted(
        articles_for_actor,
        key=lambda a: a.get('feed_weight', 1.0) * min(1.0 + (a.get('_actor_hits', 1) - 1) * 0.15, 2.0),
        reverse=True,
    )
    top_articles = []
    for a in sorted_articles[:8]:
        top_articles.append({
            'title':       a.get('title', ''),
            'url':         a.get('url', ''),
            'source':      a.get('source', ''),
            'language':    a.get('language', 'en'),
            'published':   a.get('published', ''),
            'feed_type':   a.get('feed_type', ''),
        })

    sources = sorted(src_count.items(), key=lambda x: -x[1])[:6]

    return {
        'score':              round(score, 2),
        'article_count':      len(articles_for_actor),
        'language_breakdown': lang_count,
        'sources':            [{'source': s, 'count': c} for s, c in sources],
        'top_articles':       top_articles,
        'tripwires':          [{'id': tw_id, 'severity': sev} for tw_id, sev in tripwires_seen],
    }


# ============================================
# CROSS-TRACKER FINGERPRINT INTEGRATION
# ============================================
def _read_commodity_pressure_for_afghanistan():
    """
    Read commodity supply-risk fingerprints for Afghanistan's exposed commodities
    via the WHA-local commodity proxy (commodity_proxy_wha.py).

    The proxy caches ME-backend fingerprints in WHA Redis with 1-hour TTL,
    so this call is a cheap localhost hit on the proxy — no cross-backend
    HTTP latency unless the WHA-local cache misses.

    Returns dict {commodity_id: risk_dict} for any active pressure.
    Returns {} on error / empty / proxy unavailable — graceful degradation.
    """
    try:
        url = f"{ASIA_BACKEND_SELF_URL}/api/asia/commodity/afghanistan"
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        # Proxy returns {fingerprints: {commodity_id: risk_dict}, ...}
        return data.get('fingerprints', {}) or {}
    except Exception as e:
        print(f"[AFG Rhetoric] commodity proxy read error: {str(e)[:120]}")
        return {}


def _read_commodity_pressure_story_for_afghanistan():
    """
    Read the composite pressure STORY from the WHA-local commodity proxy
    (/api/wha/commodity/afghanistan -- 12hr-cached pass-through of the ME backend's
    /api/commodity-pressure/afghanistan). This is the SAME payload the Afghanistan stability
    page renders (composite points, alert band, per-commodity global alerts),
    so the rhetoric tracker and stability page tell ONE story.

    Returns compact dict or {} on any failure (graceful degradation):
      {alert, points, profile_count, commodities: {commodity_id: global_alert_level}}
    """
    try:
        url = f"{ASIA_BACKEND_SELF_URL}/api/asia/commodity/afghanistan"
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        commodities = {}
        for tile in (data.get('commodity_summaries') or []):
            cid = tile.get('commodity')
            if cid:
                commodities[cid] = tile.get('global_alert_level') or 'normal'
        return {
            'alert':         (data.get('alert_level') or 'normal').lower(),
            'points':        round(float(data.get('commodity_pressure') or 0), 1),
            'profile_count': data.get('profile_count') or len(commodities),
            'commodities':   commodities,
        }
    except Exception as e:
        print(f"[AFG Rhetoric] commodity story read error: {str(e)[:120]}")
        return {}


def _read_crosstheater_amplifiers():
    """
    Sibling-tracker fingerprints that shape Afghanistan's analytical context
    (the wheels, read from the shared Redis -- absence-honest when missing):
      pakistan_fingerprint -- crosstheater:pakistan:fingerprint (confirmed sibling)
      iran_fingerprint     -- crosstheater:iran:fingerprint     (ME backend, attempted)
      china_fingerprint    -- crosstheater:china:fingerprint    (attempted)
    """
    amplifiers = {}
    candidate_keys = {
        'pakistan_fingerprint': 'crosstheater:pakistan:fingerprint',
        'iran_fingerprint':     'crosstheater:iran:fingerprint',
        'china_fingerprint':    'crosstheater:china:fingerprint',
    }
    for label, redis_key in candidate_keys.items():
        val = _redis_get(redis_key)
        if val:
            amplifiers[label] = val
    return amplifiers

def _builtin_fallback_signals(composite_score, composite_level, vector_scores,
                              vector_levels, actor_summaries, tripwires_global,
                              disaster_state):
    """Interpreter-absent fallback (v1 ships without a dedicated interpreter):
    compact executive summary + canonical-ish top_signals so the page and the
    Asia BLUF always have something honest to render. Estimative voice only."""
    sigs = []
    # tripwire hits first
    for tw in (tripwires_global or [])[:3]:
        name = tw.get('tripwire', tw.get('id', 'tripwire')) if isinstance(tw, dict) else str(tw)
        sev  = tw.get('severity', 'high') if isinstance(tw, dict) else 'high'
        sigs.append({'level': sev, 'type': 'tripwire', 'priority': 10,
                     'category': 'tripwire', 'theatre': 'afghanistan',
                     'pressure_type': 'kinetic',
                     'short_text': f"\U0001f1e6\U0001f1eb AFGHANISTAN tripwire: {str(name).replace('_',' ')}",
                     'long_text':  f"AFGHANISTAN tripwire fired: {str(name).replace('_',' ')} -- "
                                   f"pattern-level escalation event this scan window."})
    # disaster strain
    if disaster_state and (disaster_state.get('severity_band') in ('catastrophic','major')) \
            and float(disaster_state.get('recency_weight',0) or 0) > 0:
        _b=disaster_state.get('severity_band'); _m=disaster_state.get('peak_magnitude_30d')
        sigs.append({'level': 'high' if _b=='catastrophic' else 'elevated', 'type': 'natural_disaster_strain',
                     'priority': 9, 'category': 'natural_disaster_strain', 'theatre': 'afghanistan',
                     'pressure_type': 'humanitarian',
                     'short_text': f"\U0001f30b AFGHANISTAN: Hindu Kush seismic strain -- M{_m} ({_b})",
                     'long_text':  f"AFGHANISTAN natural-disaster strain: peak M{_m} ({_b} band; sensor: "
                                   f"afghanistan_humanitarian, USGS bounding-box). A disaster of this scale is "
                                   f"consistent with degraded state capacity in an aid-constrained system. "
                                   f"Convergence read, not a prediction of outcome."})
    # contested-node read: >=3 wheels elevated+ (AZ schema -- the headline signal)
    _wheels = {'iran_afghanistan':'friction','pakistan_state':'kinetic',
               'russia_engagement':'normalization','china_engagement':'extraction'}
    _active = [(k,r) for k,r in _wheels.items()
               if (actor_summaries or {}).get(k,{}).get('level','low') in ('elevated','high','surge')]
    if len(_active) >= 3:
        _roles = ', '.join(k.split('_')[0].title() + ' (' + r + ')' for k,r in _active)
        sigs.append({'level':'high','type':'contested_node','priority':9,
                     'category':'contested_node','theatre':'afghanistan',
                     'pressure_type':'diplomatic',
                     'short_text': '\U0001f6de AFGHANISTAN contested node: ' + str(len(_active)) + '/4 wheels active',
                     'long_text':  'AFGHANISTAN multi-wheel convergence: ' + _roles + ' simultaneously '
                                   'elevated on one contested node. Mixed-polarity engagement of this '
                                   'breadth is the pattern that has historically preceded competitive '
                                   'positioning cascades. Convergence read, not a prediction of alignment.'})

    # surge/high actors
    for akey, summ in (actor_summaries or {}).items():
        lvl = summ.get('level','low') if isinstance(summ,dict) else 'low'
        if lvl in ('high','surge'):
            sigs.append({'level': lvl, 'type': 'actor_signal', 'priority': 7,
                         'category': 'actor_signal', 'theatre': 'afghanistan',
                         'pressure_type': 'kinetic',
                         'short_text': f"\U0001f1e6\U0001f1eb {akey.replace('_',' ').title()} at {lvl.upper()}",
                         'long_text':  f"AFGHANISTAN actor {akey.replace('_',' ')} scanning at {lvl} -- "
                                       f"elevated statement tempo/severity versus baseline."})
    sigs.sort(key=lambda x: -x.get('priority',0))

    vecs_hot = [k.replace('_',' ') for k,v in (vector_levels or {}).items()
                if v in ('elevated','high','surge')]
    parts = [f"Afghanistan composite {composite_score:.1f} ({composite_level.upper()})."]
    parts.append(f"Active vectors: {', '.join(vecs_hot[:3])}." if vecs_hot
                 else "All four vectors at baseline this scan.")
    if disaster_state.get('active_disaster'):
        parts.append(f"Hindu Kush seismic strain active (M{disaster_state.get('peak_magnitude_30d')}, "
                     f"{disaster_state.get('severity_band')}).")
    parts.append("Four-wheel contested node: Iran friction, Pakistan kinetic, "
                 "Russia normalization, China extraction -- convergence read, not prediction.")
    return sigs[:8], ' '.join(parts), []


def _write_afghanistan_fingerprints(actor_levels, vector_scores, tripwires_global):
    """
    Afghanistan crosstheater slice -- AZERBAIJAN-schema contested node.
    hub_presence: four wheels of MIXED polarity, each with level/role/top read.
      iran     = friction      (water, deportations, border incidents)
      pakistan = kinetic       (TTP sanctuary, strikes, Durand Line)
      russia   = normalization (formal recognition 2025, ISKP counterterror)
      china    = extraction    (Mes Aynak, Amu Darya oil, Wakhan)
    node_class: 'contested'. Contested-node signal fires at >=3 wheels
    elevated+ (mixed polarity means 2 active is a Tuesday -- AZ lesson).
    Consumers: Asia BLUF, GPI Iran-wheel narrative, future wheel recomputes.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    def _wheel(actor_key, role):
        lvl = actor_levels.get(actor_key, 'low')
        return {'level': lvl, 'role': role,
                'active': lvl in ('elevated', 'high', 'surge')}

    hub_presence = {
        'iran':     _wheel('iran_afghanistan', 'friction'),
        'pakistan': _wheel('pakistan_state',   'kinetic'),
        'russia':   _wheel('russia_engagement','normalization'),
        'china':    _wheel('china_engagement', 'extraction'),
    }
    wheels_active = sum(1 for w in hub_presence.values() if w['active'])

    slice_payload = {
        'ts':               now_iso,
        'theatre':          'afghanistan',
        'node_class':       'contested',
        'hub_presence':     hub_presence,
        'wheels_active':    wheels_active,
        'contested_signal': wheels_active >= 3,
        'kinetic_afpak':    vector_scores.get('kinetic_afpak', 0),
        'repression_rights': vector_scores.get('repression_rights', 0),
        'iskp_level':       actor_levels.get('iskp', 'low'),
        'ttp_level':        actor_levels.get('ttp', 'low'),
        'tripwires':        tripwires_global[:5] if isinstance(tripwires_global, list) else [],
    }
    _redis_set('crosstheater:afghanistan:fingerprint', slice_payload, ttl_hours=14)
    print(f"[AFG Rhetoric] Crosstheater slice written -- wheels_active={wheels_active}, "
          f"contested_signal={wheels_active >= 3}")

def _compute_afghanistan_l5_gate(tripwires_global, actor_summaries, vector_scores):
    """
    Per platform L5 Reservation Contract: Afghanistan L5 "Active Crisis" requires
    an explicit kinetic / humanitarian / economic / diplomatic L5 trigger.

    Afghanistan is a contested-node tracker. L5 'Active Crisis' is reserved for
    crisis-class events: ISKP mass-casualty external operation, open cross-border
    war (Pakistan or Iran), catastrophic Hindu Kush quake with state-capacity
    collapse, or famine-scale humanitarian rupture. Scaffold today -- the
    weekend audit adds severity-5 tripwires per axis; until then the gate
    correctly returns any=False.

    Returns dict with axis flags + reason string.
    """
    gate = {
        'kinetic':      False,
        'humanitarian': False,
        'economic':     False,
        'diplomatic':   False,
        'reason':       '',
        'any':          False,
    }

    # Convert tripwires_global to a flat set for lookup by (actor_id, tw_id)
    fired_tws = set()
    for entry in tripwires_global or []:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            fired_tws.add(f"{entry[0]}:{entry[1]}")
        elif isinstance(entry, dict):
            actor = entry.get('actor_id', '')
            twid  = entry.get('tw_id', '')
            if actor and twid:
                fired_tws.add(f"{actor}:{twid}")

    reasons = []

    # ── KINETIC L5 (scaffold — refine in weekend audit) ──
    # Would fire on: ISKP mass-casualty external op, Pakistan/Iran cross-border war,
    # Kabul-regime collapse with kinetic contest. No severity-5 tripwires
    # currently defined in Afghanistan's ACTORS dict. Awaits weekend audit.
    # Today: never fires.

    # ── HUMANITARIAN L5 (scaffold — refine in weekend audit) ──
    # Would fire on: famine-scale rupture, catastrophic quake displacement,
    # deportation-wave humanitarian collapse. No severity-5 tripwires currently defined.
    # Today: never fires.

    # ── ECONOMIC L5 (scaffold — refine in weekend audit) ──
    # Would fire on: afghani collapse, banking-system failure,
    # total aid-pipeline shutdown. No severity-5 tripwires currently defined.
    # Today: never fires.

    # ── DIPLOMATIC L5 (scaffold — refine in weekend audit) ──
    # Would fire on: recognition-cascade rupture, wheel-power embassy
    # closures, UN-mandate collapse. No severity-5 tripwires currently defined.
    # Today: never fires.

    gate['any']    = any(gate[k] for k in ('kinetic', 'humanitarian', 'economic', 'diplomatic'))
    gate['reason'] = '; '.join(reasons) if reasons else 'No L5 axis trigger fired (L5 reserved for crisis-class events: ISKP mass-casualty external op, cross-border war, catastrophic quake)'

    return gate


def _build_afghanistan_signal_text(theatre_level, theatre_score, vector_levels, actor_summaries, l5_capped=False):
    """
    Build short_text + long_text for Afghanistan's theatre_high signal.
    Returns dict {'short': str, 'long': str}.
    """
    # Identify top vectors at elevated+
    vectors_active = []
    if isinstance(vector_levels, dict):
        for vec, lvl in vector_levels.items():
            if lvl in ('elevated', 'high', 'surge'):
                vectors_active.append(vec.replace('_', ' '))

    vectors_brief = ', '.join(vectors_active[:3]) if vectors_active else 'baseline'

    # Identify top actors at elevated+
    actors_active = []
    if isinstance(actor_summaries, dict):
        for actor, summary in actor_summaries.items():
            lvl = summary.get('level', 'low') if isinstance(summary, dict) else 'low'
            if lvl in ('elevated', 'high', 'surge'):
                actors_active.append(actor.replace('_', ' '))

    actors_brief = ', '.join(actors_active[:3]) if actors_active else ''

    label_map = {0: 'Monitoring', 1: 'Rhetoric', 2: 'Warning',
                 3: 'Direct Threat', 4: 'Coercion', 5: 'Active Crisis'}
    label = label_map.get(theatre_level, 'Monitoring')

    short = f"🇦🇫 AFGHANISTAN L{theatre_level} {label} — {vectors_brief}"
    if len(short) > 120:
        short = short[:117] + '...'

    long_parts = [f"🇦🇫 AFGHANISTAN at L{theatre_level} {label} (theatre score {theatre_score}/100)."]
    if vectors_active:
        long_parts.append(f"Active vectors: {vectors_brief}.")
    if actors_active:
        long_parts.append(f"Top actors: {actors_brief}.")
    if l5_capped:
        long_parts.append("L5 axis gate did not fire — capped at L4 ceiling per platform L5 Reservation Contract.")
    else:
        long_parts.append("Afghanistan is a contested-node tracker: four mixed-polarity wheels (Iran friction, Pakistan kinetic, Russia normalization, China extraction).")

    return {'short': short, 'long': ' '.join(long_parts)}


# ============================================
# MAIN SCAN ORCHESTRATOR
# ============================================
def scan_afghanistan_rhetoric(force=False, days=7):
    """
    Full scan: fetch from all sources, classify per actor, score, build summaries,
    write fingerprints, return result.
    """
    global _last_scan_started_at
    _last_scan_started_at = datetime.now(timezone.utc)
    scan_start = time.time()

    print(f"[AFG Rhetoric] === Scan start (force={force}, days={days}) ===")

    # ── Fetch all sources ──
    rss_articles = fetch_all_rss()
    print(f"[AFG Rhetoric] RSS total: {len(rss_articles)}")
    gdelt_articles = fetch_all_gdelt(days=days)
    newsapi_articles = fetch_all_newsapi(days=days)
    brave_articles = fetch_all_brave(
        days=days,
        gdelt_count=len(gdelt_articles),
        newsapi_count=len(newsapi_articles),
    )

    all_articles = rss_articles + gdelt_articles + newsapi_articles + brave_articles
    # Dedupe by URL
    seen_urls = set()
    deduped = []
    for a in all_articles:
        u = a.get('url', '')
        if u and u not in seen_urls:
            seen_urls.add(u)
            deduped.append(a)
    all_articles = deduped
    print(f"[AFG Rhetoric] Articles after dedup: {len(all_articles)}")

    # ── Classify articles by actor ──
    articles_by_actor = {actor_id: [] for actor_id in ACTORS.keys()}
    for art in all_articles:
        matches = _classify_article_actor(art)
        for actor_id, hit_count in matches:
            art_copy = dict(art)
            art_copy['_actor_hits'] = hit_count
            articles_by_actor[actor_id].append(art_copy)

    # ── Score each actor ──
    actor_summaries = {}
    actor_levels = {}
    tripwires_global = []
    for actor_id, actor_data in ACTORS.items():
        scored = _score_actor_articles(articles_by_actor[actor_id], actor_id)
        baseline = actor_data['baseline_statements_per_week']
        level = actor_alert_level(scored['score'], baseline)
        actor_levels[actor_id] = level

        actor_summaries[actor_id] = {
            'name':         actor_data['name'],
            'flag':         actor_data['flag'],
            'icon':         actor_data['icon'],
            'color':        actor_data['color'],
            'role':         actor_data['role'],
            'description':  actor_data['description'],
            'vector':       actor_data['vector'],
            'score':        scored['score'],
            'level':        level,
            'baseline':     baseline,
            'article_count':       scored['article_count'],
            'language_breakdown':  scored['language_breakdown'],
            'sources':             scored['sources'],
            'top_articles':        scored['top_articles'],
            'tripwires':           scored['tripwires'],
        }
        for tw in scored['tripwires']:
            tripwires_global.append({'actor': actor_id, **tw})

    # ── Compute 4-vector composite scores ──
    vector_scores = {}
    vector_levels = {}
    for vector_id, member_actors in VECTOR_GROUPS.items():
        total = sum(actor_summaries[a]['score'] for a in member_actors if a in actor_summaries)
        vector_scores[vector_id] = round(total, 2)
        # Level for vector = max actor level in vector
        levels_seen = [actor_summaries[a]['level'] for a in member_actors if a in actor_summaries]
        order = ['low', 'normal', 'elevated', 'high', 'surge']
        if levels_seen:
            vector_levels[vector_id] = max(levels_seen, key=lambda lv: order.index(lv))
        else:
            vector_levels[vector_id] = 'low'

    # ── Read cross-tracker context ──
    commodity_pressure = _read_commodity_pressure_for_afghanistan()
    # Attach the composite pressure story under a reserved key -- consumers
    # iterating per-commodity fingerprints skip underscore-prefixed keys.
    _story = _read_commodity_pressure_story_for_afghanistan()
    if _story:
        commodity_pressure['_pressure_story'] = _story
    crosstheater_amplifiers = _read_crosstheater_amplifiers()

    # ── Write Afghanistan fingerprints for downstream consumers ──
    _write_afghanistan_fingerprints(actor_levels, vector_scores, tripwires_global)

    # ── Compute composite Afghanistan pressure score ──
    composite_score = round(sum(vector_scores.values()), 2)

    # ── Disaster sensor cross-read (afghanistan_humanitarian.py -- Jul 2026) ──
    # Sensor below, analyst above: capped recency-decayed strain on the 0-10
    # composite (VZ pattern, rescaled): catastrophic +1.2 x recency, major +0.6.
    disaster_state = {}
    try:
        _sensor = _redis_get('humanitarian:afghanistan:latest') or {}
        disaster_state = _sensor.get('disaster_state', {}) if isinstance(_sensor, dict) else {}
    except Exception as _e:
        print(f'[AFG Rhetoric] Disaster sensor read error: {str(_e)[:100]}')
    _band = (disaster_state.get('severity_band') or 'none').lower()
    _rw   = float(disaster_state.get('recency_weight', 0) or 0)
    _dmod = round((1.2 if _band == 'catastrophic' else (0.6 if _band == 'major' else 0)) * _rw, 2)
    if _dmod:
        composite_score = round(composite_score + _dmod, 2)
        print(f'[AFG Rhetoric] Disaster strain: +{_dmod} (band={_band}, recency={_rw})')
    composite_level = max(
        (actor_summaries[a]['level'] for a in actor_summaries),
        key=lambda lv: ['low', 'normal', 'elevated', 'high', 'surge'].index(lv),
        default='low',
    )

    # ── Build executive summary + so-what + top signals via interpreter ──
    if AFG_INTERPRETER_AVAILABLE:
        try:
            top_signals = build_top_signals(actor_summaries, tripwires_global,
                                             commodity_pressure, crosstheater_amplifiers)
            executive_summary = build_executive_summary(actor_summaries, vector_scores,
                                                       vector_levels, tripwires_global)
            alignment_drift = score_alignment_drift(actor_summaries, tripwires_global,
                                                    commodity_pressure, crosstheater_amplifiers,
                                                    country='afghanistan')
            so_what = build_so_what_factor(actor_summaries, vector_scores, vector_levels,
                                           tripwires_global, commodity_pressure,
                                           alignment_drift=alignment_drift)
            # Sensor + contested-node signals fire on BOTH paths (Jul 2026):
            # the interpreter owns prose; the tracker owns its cross-reads.
            try:
                _extra, _, _ = _builtin_fallback_signals(
                    composite_score, composite_level, vector_scores, vector_levels,
                    actor_summaries, [], disaster_state)
                _have = {s.get('type') for s in top_signals if isinstance(s, dict)}
                for _sig in _extra:
                    if _sig.get('type') in ('natural_disaster_strain', 'contested_node') \
                            and _sig.get('type') not in _have:
                        top_signals.append(_sig)
            except Exception as _e:
                print(f'[AFG Rhetoric] cross-read append error: {str(_e)[:100]}')
            election_watch = None   # N/A -- the Emirate rules by decree; no electoral cycle to watch
        except Exception as e:
            print(f"[AFG Rhetoric] Interpreter error: {str(e)[:200]}")
            traceback.print_exc()
            top_signals, executive_summary, so_what = _builtin_fallback_signals(
            composite_score, composite_level, vector_scores, vector_levels,
            actor_summaries, tripwires_global, disaster_state)
            election_watch = None
            alignment_drift = None
    else:
        top_signals, executive_summary, so_what = _builtin_fallback_signals(
            composite_score, composite_level, vector_scores, vector_levels,
            actor_summaries, tripwires_global, disaster_state)
        election_watch = None
        alignment_drift = None

    # ── Alignment-drift convergence signal (BRI inroad read) -> WHA BLUF / GPI ──
    if AFG_INTERPRETER_AVAILABLE and alignment_drift:
        _drift_sig = build_alignment_drift_top_signal(alignment_drift)
        if _drift_sig and not any(s.get('category') == 'alignment_drift' for s in top_signals):
            top_signals = [_drift_sig] + list(top_signals)


    # ── BLUF compatibility shim ──
    # wha_regional_bluf.py's _normalize_tracker_data() expects an integer
    # theatre_level (0-5) and a 0-100 theatre_score. Afghanistan emits a
    # categorical composite_level + a free-running composite_score; map
    # them so the regional BLUF can ingest Afghanistan cleanly alongside Cuba.
    LEVEL_TO_THEATRE_INT = {'low': 0, 'normal': 1, 'elevated': 2, 'high': 3, 'surge': 4}
    raw_theatre_level = LEVEL_TO_THEATRE_INT.get(composite_level, 0)
    # Cap theatre_score at 100 — composite_score is unbounded by design
    theatre_score = min(100, int(composite_score))

    # ── L5 RESERVATION CONTRACT (v1.0.0 May 21 2026) ──
    # Compute L5 gate; cap theatre_level at L4 if raw is L5 but gate didn't fire.
    # Afghanistan scaffolds today — no severity-5 tripwires yet. Gate is silent until
    # weekend audit adds real L5-class triggers per axis.
    l5_gate = _compute_afghanistan_l5_gate(tripwires_global, actor_summaries, vector_scores)
    if raw_theatre_level >= 5 and not l5_gate['any']:
        theatre_level = 4
        l5_capped = True
        print(f"[AFG Rhetoric] L5 gate enforced: raw={raw_theatre_level} capped at L4 "
              f"(reason: {l5_gate['reason']})")
    else:
        theatre_level = raw_theatre_level
        l5_capped = False

    # ── Build label + signal text for BLUF consumption ──
    label_map_afghanistan = {0: 'Monitoring', 1: 'Rhetoric', 2: 'Warning',
                      3: 'Direct Threat', 4: 'Coercion', 5: 'Active Crisis'}
    theatre_label = label_map_afghanistan.get(theatre_level, 'Monitoring')

    signal_text = _build_afghanistan_signal_text(
        theatre_level, theatre_score, vector_levels, actor_summaries, l5_capped,
    )

    scan_time = round(time.time() - scan_start, 1)

    result = {
        'success':               True,
        'country':               'afghanistan',
        'composite_score':       composite_score,
        'composite_level':       composite_level,
        # BLUF compatibility shim — see definitions above
        'theatre_level':         theatre_level,
        'theatre_score':         theatre_score,

        # ── L5 Reservation Contract fields (v1.0.0 May 21 2026) ──
        'theatre_label':         theatre_label,
        'signal_text_short':     signal_text['short'],
        'signal_text_long':      signal_text['long'],
        'l5_gate':               l5_gate,
        'raw_theatre_level':     raw_theatre_level,
        'l5_capped':             l5_capped,
        'source_class':          'contested_node',  # four-wheel contested node (AZ schema)
        'vector_scores':         vector_scores,
        'vector_levels':         vector_levels,
        'actor_summaries':       actor_summaries,
        'tripwires_global':      tripwires_global,
        'commodity_pressure':    commodity_pressure,
        'crosstheater_amplifiers': crosstheater_amplifiers,
        'top_signals':           top_signals,
        'executive_summary':     executive_summary,
        'so_what':               so_what,
        'alignment_drift':       alignment_drift,
        'source_breakdown': {
            'rss':     len(rss_articles),
            'gdelt':   len(gdelt_articles),
            'newsapi': len(newsapi_articles),
            'brave':   len(brave_articles),
        },
        'total_articles_scanned': len(all_articles),
        'scan_time_seconds':      scan_time,
        'days_analyzed':          days,
        'last_updated':           datetime.now(timezone.utc).isoformat(),
        'cached':                 False,
        'version':                '1.0.0',
    }

    save_cache(result)

    # ── Canonical history snapshot (May 22 2026 reconciled schema) ──
    # Universal fields read by wha_regional_bluf.prose_v2:
    #   theatre_level, theatre_score, scanned_at, red_lines_count
    # Plus Afghanistan-specific vector levels.
    try:
        _redis_lpush_trim(HISTORY_KEY, {
            'theatre_level':       theatre_level,
            'theatre_score':       theatre_score,
            'scanned_at':          result.get('last_updated') or datetime.now(timezone.utc).isoformat(),
            'red_lines_count':     len(tripwires_global),
            'kinetic_afpak':       vector_levels.get('kinetic_afpak'),
            'repression_rights':   vector_levels.get('repression_rights'),
            'external_friction':   vector_levels.get('external_friction'),
            'illicit_economy':     vector_levels.get('illicit_economy'),
        }, max_len=336)
    except Exception as e:
        print(f"[AFG Rhetoric] History snapshot write failed: {e}")

    print(f"[AFG Rhetoric] ✅ Scan complete in {scan_time}s — composite {composite_level} ({composite_score})")
    return result


# ============================================
# BACKGROUND REFRESH LOOP
# ============================================
def _background_refresh_loop():
    """Periodic refresh — initial 90s delay, then every BACKGROUND_REFRESH_HOURS."""
    global _background_scan_running
    time.sleep(INITIAL_SCAN_DELAY_SECONDS)
    while True:
        try:
            with _background_scan_lock:
                if _background_scan_running:
                    time.sleep(60)
                    continue
                _background_scan_running = True
            try:
                print("[AFG Rhetoric] Background refresh starting...")
                scan_afghanistan_rhetoric(force=True, days=7)
                print("[AFG Rhetoric] Background refresh complete.")
            finally:
                with _background_scan_lock:
                    _background_scan_running = False
            time.sleep(BACKGROUND_REFRESH_HOURS * 3600)
        except Exception as e:
            print(f"[AFG Rhetoric] Background loop error: {e}")
            time.sleep(600)


def _start_background_refresh():
    t = threading.Thread(target=_background_refresh_loop, daemon=True, name='AfghanistanRhetoricBG')
    t.start()
    print(f"[AFG Rhetoric] Background refresh thread started (initial delay {INITIAL_SCAN_DELAY_SECONDS}s)")


# ============================================
# FLASK ENDPOINTS
# ============================================
def register_afghanistan_rhetoric_endpoints(app, start_background=True):
    """Register Afghanistan rhetoric endpoints on a Flask app + start background refresh."""
    from flask import jsonify, request

    @app.route('/api/rhetoric/afghanistan', methods=['GET', 'OPTIONS'])
    def api_afghanistan_rhetoric():
        if request.method == 'OPTIONS':
            return ('', 204)
        force = request.args.get('refresh', '').lower() in ('true', '1', 'yes')

        cached = load_cache()
        if cached and is_cache_fresh(cached) and not force:
            cached['cached'] = True
            return jsonify(cached)

        # Cache miss or force refresh — return cached (if any) and trigger background scan
        if cached and not force:
            cached['cached'] = True
            cached['stale'] = True
            # Trigger background scan if not already running
            with _background_scan_lock:
                if not _background_scan_running:
                    threading.Thread(
                        target=lambda: scan_afghanistan_rhetoric(force=True, days=7),
                        daemon=True,
                    ).start()
            return jsonify(cached)

        # No cache at all — do synchronous scan (slow!)
        result = scan_afghanistan_rhetoric(force=force, days=7)
        return jsonify(result)

    @app.route('/api/rhetoric/afghanistan/debug', methods=['GET'])
    def api_afghanistan_rhetoric_debug():
        """Diagnostic — config snapshot + cache freshness."""
        cached = load_cache()
        return jsonify({
            'version':                  '1.0.0',
            'actor_count':              len(ACTORS),
            'actors':                   list(ACTORS.keys()),
            'vector_count':             len(VECTOR_GROUPS),
            'vectors':                  list(VECTOR_GROUPS.keys()),
            'rss_feeds':                len(RSS_FEEDS),
            'gdelt_queries_en':         len(GDELT_QUERIES_EN),
            'gdelt_queries_es':         len(GDELT_QUERIES_ES),
            'tripwires':                len(TRIPWIRES),
            'redis_configured':         bool(UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN),
            'newsapi_configured':       bool(NEWSAPI_KEY),
            'brave_configured':         bool(BRAVE_API_KEY),
            'commodity_fingerprint':    COMMODITY_FINGERPRINT_AVAILABLE,
            'interpreter_available':    AFG_INTERPRETER_AVAILABLE,
            'cache_present':            cached is not None,
            'cache_fresh':              is_cache_fresh(cached) if cached else False,
            'cache_age_hours':          None if not cached else round(
                (datetime.now(timezone.utc) - datetime.fromisoformat(cached.get('cached_at', '2020-01-01T00:00:00+00:00'))).total_seconds() / 3600, 2
            ) if cached.get('cached_at') else None,
            'last_scan_started_at':     _last_scan_started_at.isoformat() if _last_scan_started_at else None,
            'background_running':       _background_scan_running,
        })

    print("[AFG Rhetoric] ✅ Endpoints registered:")
    print("  GET  /api/rhetoric/afghanistan")
    print("  GET  /api/rhetoric/afghanistan/debug")

    if start_background:
        _start_background_refresh()
    else:
        print("[AFG Rhetoric] ℹ️ Background refresh disabled on this instance")


print("[AFG Rhetoric] Module loaded.")
