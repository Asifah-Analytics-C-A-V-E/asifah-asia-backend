"""
Asifah Analytics — Asia Backend v1.0.0
March 2026

Asia-Pacific Conflict Probability Dashboard Backend
Targets: Afghanistan, China, India, Japan, North Korea, Pakistan, South Korea, Taiwan

Architecture modeled on Europe backend (app.py v1.1.0)
Adapted for Asia-Pacific geopolitical monitoring with:
  - Asia-Pacific source weights (SCMP, Nikkei, The Hindu, Yonhap, etc.)
  - GDELT languages: English, Mandarin (zho), Korean (kor), Urdu (urd), Dari (prs)
  - Asia-Pacific Reddit subreddits
  - NOTAM monitoring (FAA NOTAM API — ICAO regions)
  - Flight disruption tracking
  - Military posture integration hooks

v1.0.0 — Initial build
  - All threat/NOTAM/flight data cached in memory with 4-hour TTL
  - Background thread refreshes all caches every 4 hours automatically
  - Normal page loads return cached data in <100ms
  - Force fresh scan with ?force=true query parameter
  - /api/asia/dashboard endpoint returns all country scores in one call

© 2026 Asifah Analytics. All rights reserved.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS, cross_origin
import requests
from datetime import datetime, timezone, timedelta
import os
import time
import re
import math
import xml.etree.ElementTree as ET
import threading
import json

try:
    from telegram_signals_asia import fetch_asia_telegram_signals
    TELEGRAM_AVAILABLE = True
    print("[Asia Backend] ✅ Telegram signals available")
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[Asia Backend] ⚠️ Telegram signals not available")

# v1.1.0 (April 2026) — Bluesky as alternate source to Telegram.
# When 13/18 Telegram channels are flood-waited, Bluesky fills the gap.
# Graceful fallback: if module missing, just skip.
try:
    from bluesky_signals_asia import fetch_bluesky_for_target
    BLUESKY_AVAILABLE = True
    print("[Asia Backend] ✅ Bluesky signals available")
except ImportError:
    BLUESKY_AVAILABLE = False
    print("[Asia Backend] ⚠️ Bluesky signals not available")

try:
    from rhetoric_tracker_china import register_china_rhetoric_endpoints
    CHINA_RHETORIC_AVAILABLE = True
    print("[Asia Backend] ✅ China rhetoric tracker loaded")
except ImportError:
    CHINA_RHETORIC_AVAILABLE = False
    print("[Asia Backend] ⚠️ China rhetoric tracker not available")

try:
    from rhetoric_tracker_taiwan import register_taiwan_rhetoric_endpoints
    TAIWAN_RHETORIC_AVAILABLE = True
    print("[Asia Backend] ✅ Taiwan rhetoric tracker loaded")
except ImportError:
    TAIWAN_RHETORIC_AVAILABLE = False
    print("[Asia Backend] ⚠️ Taiwan rhetoric tracker not available")
    print("[Asia Backend] ✅ China rhetoric tracker loaded")
except ImportError:
    CHINA_RHETORIC_AVAILABLE = False
    print("[Asia Backend] ⚠️ China rhetoric tracker not available")

try:
    from china_stability import register_china_stability_endpoints
    CHINA_STABILITY_AVAILABLE = True
    print("[Asia Backend] ✅ China stability module loaded")
except ImportError:
    CHINA_STABILITY_AVAILABLE = False
    print("[Asia Backend] ⚠️ China stability module not available")

try:
    from china_stability import register_china_stability_endpoints
    CHINA_STABILITY_AVAILABLE = True
    print("[Asia Backend] ✅ China stability module loaded")
except ImportError:
    CHINA_STABILITY_AVAILABLE = False
    print("[Asia Backend] ⚠️ China stability module not available")

try:
    from china_humanitarian import register_china_humanitarian_endpoints
    CHINA_HUMANITARIAN_AVAILABLE = True
    print("[Asia Backend] ✅ China humanitarian module loaded")
except ImportError:
    CHINA_HUMANITARIAN_AVAILABLE = False
    print("[Asia Backend] ⚠️ China humanitarian module not available")

# In-memory Telegram cache — fetched ONCE per refresh cycle, shared across all country scans
_telegram_cache = {'messages': [], 'fetched_at': None, 'ttl_seconds': 4 * 3600}  # v1.1.0 — 4h TTL (was 1h)

app = Flask(__name__)
# Belt-and-suspenders CORS: both flask_cors AND after_request handler
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=False)

# ========================================
# CONFIGURATION
# ========================================
NEWSAPI_KEY = os.environ.get('NEWSAPI_KEY')
GDELT_BASE_URL = "http://api.gdeltproject.org/api/v2/doc/doc"

# Cache TTL in seconds
# v1.1.0 (April 2026) — 12h → 6h. With self-caching working and GDELT
# cooldowns preventing wasted cycles, 4 refreshes/day gives better
# recovery from transient failures and fresher data for users.
CACHE_TTL = 6 * 60 * 60

# NOTAM cache TTL (2 hours)
NOTAM_CACHE_TTL = 2 * 60 * 60

# Upstash Redis (persistent cache across Render cold starts)
UPSTASH_REDIS_URL = os.environ.get('UPSTASH_REDIS_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN')
NOTAM_REDIS_KEY = 'asia_notam_cache'
FLIGHT_REDIS_KEY = 'asia_flight_cache'
FLIGHT_CACHE_TTL = 12 * 60 * 60  # 12 hours
THREAT_REDIS_PREFIX = 'asia_threat_'  # e.g. asia_threat_taiwan_7d
THREAT_CACHE_TTL = 12 * 60 * 60  # 12 hours

# Rate limiting
RATE_LIMIT = 100
RATE_LIMIT_WINDOW = 86400
rate_limit_data = {
    'requests': 0,
    'reset_time': time.time() + RATE_LIMIT_WINDOW
}

# ========================================
# IN-MEMORY RESPONSE CACHE
# ========================================
_cache = {}
_cache_lock = threading.Lock()


def cache_get(key):
    """Get a cached response if it exists and is fresh."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        if time.time() - entry['timestamp'] > CACHE_TTL:
            del _cache[key]
            return None
        return entry['data']


def cache_set(key, data):
    """Store a response in the in-memory cache."""
    with _cache_lock:
        _cache[key] = {
            'data': data,
            'timestamp': time.time()
        }


def cache_age(key):
    """Return age of cache entry in seconds, or None if not cached."""
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        return time.time() - entry['timestamp']


# ========================================
# REDIS HELPERS
# ========================================

def _redis_request(method, path, **kwargs):
    """Make a request to Upstash Redis REST API."""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        url = f"{UPSTASH_REDIS_URL}{path}"
        caller_headers = kwargs.pop('headers', {})
        headers = {"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"}
        headers.update(caller_headers)
        resp = requests.request(method, url, headers=headers, timeout=5, **kwargs)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"[Redis] Error: {str(e)[:100]}")
    return None

def _get_rhetoric_level(target):
    """Read rhetoric tracker level from Redis crosstheater fingerprint."""
    try:
        key = 'rhetoric:crosstheater:fingerprints'
        result = _redis_request('GET', f'/get/{key}')
        if result and result.get('result'):
            fingerprints = json.loads(result['result'])
            if target == 'china':
                return fingerprints.get('china', {}).get('level', 0)
            elif target == 'taiwan':
                return fingerprints.get('taiwan', {}).get('level', 0)
            # Stubs for when trackers go live
            elif target == 'north_korea':
                return fingerprints.get('north_korea', {}).get('level', 0)
            elif target in ('india', 'pakistan'):
                return fingerprints.get(target, {}).get('level', 0)
    except Exception as e:
        print(f"[Rhetoric Boost] Redis read error: {str(e)[:80]}")
    return 0


# Rhetoric level → probability boost (matches Europe pattern)
RHETORIC_BOOST_TABLE = {
    0: 0,
    1: 2,
    2: 5,
    3: 10,
    4: 18,
    5: 25,
}

# Military posture alert_level → probability boost
MILITARY_POSTURE_BOOST_TABLE = {
    'normal':   0,
    'elevated': 4,
    'high':     9,
    'surge':    15,
}


def _get_military_level(target):
    """
    Read military posture alert_level string for a target FROM REDIS.
    military_tracker.py lives only on ME backend and writes to Redis.
    Asia reads from that shared Redis cache — no duplicate scans.
    Returns (alert_level_str, boost_int) tuple.
    """
    try:
        if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
            return 'normal', 0
        resp = requests.get(
            f'{UPSTASH_REDIS_URL}/get/military_cache',
            headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'},
            timeout=4
        )
        result = resp.json().get('result')
        if not result:
            return 'normal', 0
        data = json.loads(result)
        actors = data.get('actors', {})
        # Try exact match first, then partial (e.g. "china" → "china_pla")
        actor_data = actors.get(target, {})
        if not actor_data:
            for k, v in actors.items():
                if target in k or k in target:
                    actor_data = v
                    break
        alert_level = actor_data.get('alert_level', 'normal')
        boost = MILITARY_POSTURE_BOOST_TABLE.get(alert_level, 0)
        print(f'[Asia v1.1] Military posture {target}: {alert_level} (+{boost})')
        return alert_level, boost
    except Exception as e:
        print(f"[Military Boost] {target} read error: {str(e)[:80]}")
        return 'normal', 0
  
def load_threat_cache_redis(target, days=7):
    """Load threat cache from Redis."""
    key = f"{THREAT_REDIS_PREFIX}{target}_{days}d"
    result = _redis_request('GET', f"/get/{key}")
    if result and result.get('result'):
        try:
            return json.loads(result['result'])
        except Exception:
            pass
    return None


def save_threat_cache_redis(target, data, days=7):
    """Save threat cache to Redis with TTL."""
    key = f"{THREAT_REDIS_PREFIX}{target}_{days}d"
    try:
        payload = json.dumps(data, default=str)
        # Upstash REST: SET key value EX seconds
        _redis_request('POST', f"/set/{key}",
                       data=payload,
                       params={'EX': THREAT_CACHE_TTL},
                       headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                                "Content-Type": "application/json"})
    except Exception as e:
        print(f"[Redis] Save error: {str(e)[:100]}")

def is_threat_cache_fresh_redis(target, days=7):
    """Check if Redis threat cache is fresh. Returns (is_fresh, data)."""
    cached = load_threat_cache_redis(target, days)
    if not cached:
        return False, None
    cached_at = cached.get('cached_at', '')
    if cached_at:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(
                cached_at.replace('Z', '+00:00'))).total_seconds()
            if age < THREAT_CACHE_TTL:
                return True, cached
        except Exception:
            pass
    return False, None


def is_notam_cache_fresh():
    """Check if Redis NOTAM cache is fresh."""
    result = _redis_request('GET', f"/get/{NOTAM_REDIS_KEY}")
    if result and result.get('result'):
        try:
            data = json.loads(result['result'])
            cached_at = data.get('timestamp', '')
            if cached_at:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(
                    cached_at.replace('Z', '+00:00'))).total_seconds()
                if age < NOTAM_CACHE_TTL:
                    return True, data
        except Exception:
            pass
    return False, None


def save_notam_cache_redis(data):
    """Save NOTAM cache to Redis."""
    try:
        payload = json.dumps(data)
        _redis_request('POST', f"/set/{NOTAM_REDIS_KEY}",
                       data=payload,
                       params={'EX': NOTAM_CACHE_TTL},
                       headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                                "Content-Type": "application/json"})
    except Exception as e:
        print(f"[Redis] NOTAM save error: {str(e)[:100]}")


def is_flight_cache_fresh():
    """Check if Redis flight cache is fresh."""
    result = _redis_request('GET', f"/get/{FLIGHT_REDIS_KEY}")
    if result and result.get('result'):
        try:
            data = json.loads(result['result'])
            cached_at = data.get('timestamp', '')
            if cached_at:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(
                    cached_at.replace('Z', '+00:00'))).total_seconds()
                if age < FLIGHT_CACHE_TTL:
                    return True, data
        except Exception:
            pass
    return False, None


def save_flight_cache_redis(data):
    """Save flight disruption cache to Redis."""
    try:
        payload = json.dumps(data)
        _redis_request('POST', f"/set/{FLIGHT_REDIS_KEY}",
                       data=payload,
                       params={'EX': FLIGHT_CACHE_TTL},
                       headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                                "Content-Type": "application/json"})
    except Exception as e:
        print(f"[Redis] Flight save error: {str(e)[:100]}")


# ========================================
# RATE LIMITING
# ========================================

def check_rate_limit():
    """Simple daily rate limiter."""
    now = time.time()
    if now > rate_limit_data['reset_time']:
        rate_limit_data['requests'] = 0
        rate_limit_data['reset_time'] = now + RATE_LIMIT_WINDOW
    rate_limit_data['requests'] += 1
    return rate_limit_data['requests'] <= RATE_LIMIT


def get_rate_limit_info():
    return {
        'requests_today': rate_limit_data['requests'],
        'limit': RATE_LIMIT,
        'reset_time': rate_limit_data['reset_time']
    }


# ========================================
# BACKGROUND REFRESH THREAD
# ========================================

def _refresh_all_caches():
    """
    Refresh all cached data in the background.
    Runs every CACHE_TTL seconds so no user request ever triggers a cold scan.
    """
    print("[Background Refresh] Waiting 30s for app to stabilize before first refresh...")
    time.sleep(30)

    targets = list(TARGET_KEYWORDS.keys())

    while True:
        print(f"\n[Background Refresh] Starting full cache refresh at {datetime.now(timezone.utc).isoformat()}")
        start = time.time()

        for target in targets:
            try:
                print(f"[Background Refresh] Refreshing {target}...")
                from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_run_threat_scan, target, 7)
                    try:
                        data = future.result(timeout=120)
                    except FuturesTimeout:
                        print(f"[Background Refresh] ✗ {target} timed out after 120s — skipping")
                        continue
                cache_set(f'threat_{target}_7d', data)
                save_threat_cache_redis(target, data, days=7)
                print(f"[Background Refresh] ✓ {target} cached (probability: {data.get('probability', '?')}%)")
            except Exception as e:
                print(f"[Background Refresh] ✗ {target} failed: {e}")
            time.sleep(2)

        try:
            print("[Background Refresh] Refreshing NOTAMs via FAA...")
            notam_data = _run_notam_scan()
            cache_set('notams', notam_data)
            print(f"[Background Refresh] ✓ NOTAMs cached ({notam_data.get('total_notams', 0)} alerts)")
        except Exception as e:
            print(f"[Background Refresh] ✗ NOTAMs failed: {e}")

        time.sleep(5)

        try:
            print("[Background Refresh] Refreshing flights...")
            flight_data = _run_flight_scan()
            cache_set('flights', flight_data)
            print(f"[Background Refresh] ✓ Flights cached ({flight_data.get('total_disruptions', 0)} disruptions)")
        except Exception as e:
            print(f"[Background Refresh] ✗ Flights failed: {e}")

        time.sleep(5)

        try:
            print("[Background Refresh] Refreshing travel advisories...")
            ta_data = _run_travel_advisory_scan()
            cache_set('travel_advisories', ta_data)
            print(f"[Background Refresh] ✓ Travel advisories cached")
        except Exception as e:
            print(f"[Background Refresh] ✗ Travel advisories failed: {e}")

        elapsed = time.time() - start
        print(f"[Background Refresh] Complete in {elapsed:.1f}s. Sleeping {CACHE_TTL}s until next refresh.\n")
        time.sleep(CACHE_TTL)


def start_background_refresh():
    """Start the background refresh thread (daemon so it dies with the app)."""
    thread = threading.Thread(target=_refresh_all_caches, daemon=True)
    thread.start()
    print("[Background Refresh] Thread started — will refresh all caches every 4 hours")


# ========================================
# U.S. STATE DEPT TRAVEL ADVISORIES
# ========================================
TRAVEL_ADVISORY_API = "https://cadataapi.state.gov/api/TravelAdvisories"

TRAVEL_ADVISORY_CODES = {
    'afghanistan': ['AF'],
    'china':       ['CH'],
    'india':       ['IN'],
    'japan':       ['JA'],
    'north_korea': ['KN'],
    'pakistan':    ['PK'],
    'south_korea': ['KS'],
    'taiwan':      ['TW'],
}

# State Dept country name slug for direct advisory links
TRAVEL_ADVISORY_SLUGS = {
    'afghanistan': 'afghanistan',
    'china':       'china',
    'india':       'india',
    'japan':       'japan',
    'north_korea': 'north-korea-democratic-peoples-republic-of-korea',
    'pakistan':    'pakistan',
    'south_korea': 'south-korea-republic-of-korea',
    'taiwan':      'taiwan',
}

TRAVEL_ADVISORY_LEVELS = {
    1: {'label': 'Exercise Normal Precautions',    'short': 'Normal Precautions',  'color': '#10b981'},
    2: {'label': 'Exercise Increased Caution',     'short': 'Increased Caution',   'color': '#f59e0b'},
    3: {'label': 'Reconsider Travel',              'short': 'Reconsider Travel',   'color': '#f97316'},
    4: {'label': 'Do Not Travel',                  'short': 'Do Not Travel',       'color': '#ef4444'},
}


# ========================================
# SOURCE WEIGHTS — ASIA-PACIFIC EDITION
# ========================================
SOURCE_WEIGHTS = {
    'premium': {
        'sources': [
            'The New York Times', 'The Washington Post', 'Reuters',
            'Associated Press', 'AP News', 'BBC News', 'The Guardian',
            'Financial Times', 'Wall Street Journal', 'The Economist',
            'Nikkei Asia', 'South China Morning Post', 'The Hindu',
            'Yonhap News', 'Kyodo News',
        ],
        'weight': 1.0
    },
    'regional_asia': {
        # v1.1.0 (April 2026) — Source names must match EXACTLY what's passed
        # into fetch_direct_rss() calls below. Previously had "Dawn (Pakistan)"
        # here while RSS call passed "Dawn" — every Pakistan article fell
        # through to standard 0.5 weight. Fixed by aligning strings.
        'sources': [
            'NHK World', 'Japan Times', 'Mainichi', 'Asahi Shimbun',
            'Korea Herald', 'Korea Times', 'Chosun Ilbo',
            'KBS World',  # v1.1.0 — DPRK coverage
            # Pakistan regional — all aligned to RSS-call strings
            'Dawn', 'The News International', 'Geo News',
            'Express Tribune',  # v1.1.0
            'RFE/RL Gandhara (PK)', 'RFE/RL Gandhara', 'SATP Pakistan',
            'Al Jazeera PK',  # v1.1.0
            # India
            'Times of India', 'Hindustan Times', 'NDTV',
            # Taiwan
            'Taipei Times', 'Focus Taiwan', 'Liberty Times',
            # China state
            'Global Times', 'Xinhua', 'CGTN',
            # Broadcast + DPRK specialists
            'Radio Free Asia', 'NK News', 'Daily NK', '38 North',
            # Afghan outlets — aligned to RSS-call strings
            'Tolo News', 'TOLOnews', 'Ariana News',
            'Pajhwok Afghan News', 'Khaama Press',
            # International broadcasters
            'Voice of America', 'Radio Free Europe',
        ],
        'weight': 0.8
    },
    'standard': {
        'sources': ['*'],
        'weight': 0.5
    }
}

# ========================================
# TARGET BASELINES — ASIA-PACIFIC
# ========================================
TARGET_BASELINES = {
    # v1.1.0 (April 2026) — Baselines adjusted for nuclear-armed states
    # with active border conflicts. Previously DPRK at +20 and Pakistan
    # at +12 were too low; actual chronic elevated state warrants higher
    # floor given missile tests (DPRK) and Iran/Afghan border wars (Pak).
    'afghanistan': {'base_adjustment': +18, 'description': 'Active Taliban governance; ISIS-K; Level 4 advisory; no US embassy'},
    'north_korea': {'base_adjustment': +25, 'description': 'Nuclear state; active provocations; Level 4 advisory; no US embassy; chronic missile tests'},
    'pakistan':    {'base_adjustment': +18, 'description': 'Nuclear state; TTP insurgency; Iran border strikes; Afghan "open war"; Level 3 advisory'},
    'taiwan':      {'base_adjustment': +10, 'description': 'Active PLA exercises; strait tensions; Level 2 advisory'},
    'south_korea': {'base_adjustment': +8,  'description': 'DPRK artillery/nuclear range; DMZ; Level 1 but active threat'},
    'china':       {'base_adjustment': +8,  'description': 'Regional power competition; SCS disputes; Level 2 advisory'},
    'india':       {'base_adjustment': +6,  'description': 'Kashmir LoC; China LAC tensions; Level 2 advisory'},
    'japan':       {'base_adjustment': +4,  'description': 'NK missile overflights; China ADIZ pressure; Level 1'},
}

# ========================================
# TARGET KEYWORDS — ASIA-PACIFIC
# ========================================
TARGET_KEYWORDS = {

    'afghanistan': {
        'keywords': [
            # Core country/actors
            'afghanistan', 'afghan', 'kabul', 'taliban', 'kandahar',
            'helmand', 'nangarhar', 'kunduz', 'herat', 'jalalabad',
            # Militant groups
            'isis-k', 'iskp', 'islamic state khorasan', 'is-khorasan',
            'al-qaeda afghanistan', 'haqqani network', 'sirajuddin haqqani',
            'tehrik-i-taliban', 'ttp', 'pakistani taliban',
            'national resistance front', 'nrf afghanistan', 'panjshir resistance',
            # Pakistan cross-border strikes
            'pakistan strikes afghanistan', 'pakistan bombs afghanistan',
            'pakistan airstrike afghanistan', 'pakistan shelling afghanistan',
            'pakistan afghanistan border attack', 'pakistan afghan border clash',
            'pakistan military operation afghanistan', 'durand line',
            'pakistan afghanistan tension', 'pak-afghan border',
            'torkham border', 'torkham crossing', 'torkham checkpoint',
            'khyber pass attack', 'khyber pass closure',
            # Taliban ops / instability
            'taliban crackdown', 'taliban execution', 'taliban attack',
            'taliban bomb', 'kabul blast', 'kabul explosion', 'kabul attack',
            'suicide bomb afghanistan', 'IED afghanistan',
            'afghanistan airstrike', 'afghanistan bomb blast',
            'afghanistan humanitarian crisis', 'afghanistan famine',
            # Iran border
            'afghanistan iran border', 'iran afghanistan clash',
        ],
        'reddit_keywords': [
            'afghanistan', 'taliban', 'isis-k', 'kabul',
            'pakistan afghanistan', 'afghan conflict',
            'resistance front', 'haqqani', 'iskp',
        ],
    },

    'china': {
        'keywords': [
            'china military', 'pla', 'chinese military', 'peoples liberation army',
            'south china sea', 'taiwan strait', 'china taiwan',
            'china navy', 'plan warship', 'chinese carrier', 'plan carrier',
            'plan exercises', 'pla navy', 'pla air force',
            'china nuclear', 'china missile', 'df-41', 'df-21', 'df-17',
            'china us military', 'china india border',
            'china air force', 'j-20', 'h-6 bomber',
            'xi jinping military', 'china war',
            'china adiz', 'china airspace violation',
            'pla exercise', 'pla drills', 'pla live fire',
            'china blockade taiwan', 'china taiwan contingency',
            'chinese warships', 'chinese destroyer', 'chinese frigate',
            # Iran oil angle — China keeps PLAN assets near Gulf for oil supply protection
            'china iran oil', 'china iran military', 'china iran naval',
            'china warships iran', 'china deploys warships', 'chinese warships iran',
            'warships near iran china', 'plan gulf', 'chinese warship gulf', 'china warship middle east',
            'china iran energy', 'china oil iran sanctions',
            'plan indian ocean', 'china djibouti base',
            'china pakistan gwadar', 'cpec military',
            # SCS / island disputes
            'spratly islands', 'paracel islands', 'scarborough shoal',
            'china philippines', 'china vietnam south sea',
            'china coast guard', 'china water cannon',
            # Japan / Senkaku angle
            'china japan senkaku', 'diaoyu islands',
            'china japan adiz', 'chinese warship japan',
            # Korean peninsula — China as NK backer
            'china north korea', 'china dprk support',
        ],
        'reddit_keywords': [
            'china military', 'pla', 'south china sea', 'taiwan strait',
            'sino', 'china taiwan', 'pla exercise', 'scs',
            'china iran', 'plan carrier', 'chinese warship',
        ],
    },

    'india': {
        'keywords': [
            'india military', 'indian army', 'indian air force', 'indian navy',
            'india pakistan', 'india china border', 'lac', 'line of actual control',
            'kashmir', 'line of control', 'india nuclear',
            'india missile', 'agni missile', 'brahmos',
            'india military exercise', 'quad india',
            'india china standoff', 'galwan valley',
            'india pakistan tension', 'india border skirmish',
            'loc incident', 'loc ceasefire violation', 'kashmir shelling',
            'kashmir gunfight', 'kashmir encounter', 'bsf pakistan',
        ],
        'reddit_keywords': [
            'india military', 'india pakistan', 'india china',
            'kashmir', 'indiandefense',
        ],
    },

    'japan': {
        'keywords': [
            'japan military', 'jsdf', 'japan self defense force',
            'japan taiwan', 'japan china', 'senkaku',
            'japan north korea missile', 'dprk missile japan',
            'japan rearmament', 'japan defense budget',
            'japan us military', 'us bases japan', 'okinawa base',
            'japan scramble jets', 'japan airspace violation',
            'japan coast guard', 'japan naval exercise',
            'japan missile defense', 'pac-3 japan',
        ],
        'reddit_keywords': [
            'japan military', 'jsdf', 'senkaku', 'japan defense',
            'japan', 'japannews',
        ],
    },

    'north_korea': {
        'keywords': [
            # Bare country terms — catch anything
            'north korea', 'dprk', 'pyongyang',
            # Kim Jong Un — every statement is a signal
            'kim jong un', 'kim jong-un', 'kim orders', 'kim inspects',
            'kim threatens', 'kim warns', 'kim vows', 'kim declares',
            'north korean leader',
            # Missile / launch events
            'north korea missile', 'dprk missile', 'north korea launches',
            'dprk launches', 'north korea fires', 'dprk fires',
            'north korea ballistic', 'dprk ballistic',
            'north korea icbm', 'dprk icbm', 'hwasong',
            'pyongyang fires', 'pyongyang launches',
            'north korea test', 'dprk test',
            # Nuclear
            'north korea nuclear', 'dprk nuclear',
            'north korea nuclear weapon', 'dprk nuclear warhead',
            'north korea nuclear test', 'punggye-ri', 'yongbyon',
            'north korea enrichment', 'north korea tactical nuclear',
            # State media / official pronouncements
            'kcna', 'dprk state media', 'korean central news agency',
            'pyongyang warns', 'pyongyang threatens',
            'north korea warns', 'north korea threatens', 'north korea vows',
            # Military activity
            'north korea artillery', 'north korea drone',
            'north korea submarine', 'dprk hypersonic',
            'north korea military exercise', 'north korea provocation',
            'dprk provocation', 'north korea balloon',
            'north korea trash balloon',
            # Troops in Russia — big 2025/2026 story
            'north korea troops russia', 'dprk soldiers ukraine',
            'north korea soldiers deployed', 'korean soldiers russia',
            'north korean troops ukraine',
            # Inter-Korean / DMZ
            'inter-korean', 'dmz', 'north korea south korea',
            'nll violation', 'korean demilitarized zone',
            'dmz incident',
            # Korean language signals
            '북한 미사일', '북한 핵', '김정은', '조선인민군',
            '북한 도발', '북한 발사', '탄도미사일',
        ],
        'reddit_keywords': [
            'north korea', 'dprk', 'kim jong un', 'pyongyang',
            'north korea missile', 'dprk launch', 'icbm launch',
            'north korea nuclear', 'north korea troops russia',
            'northkorea', 'korean peninsula',
        ],
    },

    'pakistan': {
        'keywords': [
            # Bare country terms
            'pakistan military', 'pakistan army', 'ispr',
            # Nuclear / missiles
            'pakistan nuclear', 'shaheen missile', 'nasr missile',
            'pakistan missile test', 'pakistan ballistic missile',
            # India-Pakistan / LoC
            'india pakistan', 'line of control', 'kashmir military',
            'kashmir insurgency', 'loc ceasefire', 'loc incident',
            'india pakistan skirmish', 'india pakistan standoff',
            'pulwama', 'balakot',
            # TTP — daily signal source
            'pakistan taliban', 'ttp attack', 'ttp militants',
            'ttp pakistan', 'tehrik-i-taliban', 'tehrik-e-taliban',
            'ttp kills', 'ttp ambush', 'ttp soldiers',
            # Balochistan insurgency
            'balochistan attack', 'baloch militant',
            'balochistan liberation army', 'bla attack',
            'blf attack', 'baloch insurgent',
            'quetta attack', 'gwadar attack', 'turbat attack',
            # Iran cross-border — major 2026 story
            'iran pakistan border', 'iran strikes pakistan',
            'iran bombs pakistan', 'iran attack pakistan',
            'iran balochistan', 'iran jaish al-adl',
            'jaish al-adl', 'jaish al adl',
            'irgc pakistan', 'iran retaliates pakistan',
            'pakistan retaliates iran', 'pakistan iran border',
            'pakistan iran tension', 'pakistan iran standoff',
            'pakistan closes iran border', 'pakistan iran escalation',
            'pakistan iran incident', 'pakistan iran drone',
            'iran fires missiles pakistan', 'iran fires pakistan',
            'iran fires missiles into', 'iran fires missiles into pakistan',
            'pakistan-iran border', 'pakistan retaliation iran',
            'pakistan retaliates', 'pakistan closes iran',
            'iranian missiles pakistan', 'iranian balochistan',
            # Pakistan military operations
            'pakistan army operation', 'pakistan airspace',
            'pakistan us military', 'pakistan china military',
            'cpec security', 'gwadar security',
            'pakistan coup', 'pakistan bomb blast',
            'pakistan suicide bomb',
            # Cross-border Afghanistan operations — key operational signal
            'pakistan strikes afghanistan', 'pakistan bombs afghanistan',
            'pakistan airstrike afghanistan', 'pakistan shelling afghanistan',
            'pakistan military operation afghanistan', 'pak-afghan border',
            'pakistan afghanistan border attack', 'durand line',
            'afghanistan retaliates pakistan', 'pak-afghan war',
            'pakistan jet afghanistan', 'pakistan bombs khost',
            'pakistan bombs paktika', 'pakistan bombs kunar',
            'pakistan bombs nangarhar', 'pakistan bombs bajaur',
        ],
        'reddit_keywords': [
            'pakistan military', 'pakistan army', 'india pakistan',
            'kashmir', 'pakistan afghanistan', 'ttp attack',
            'balochistan attack', 'iran pakistan border',
            'pakistan iran', 'jaish al-adl', 'pakistan news',
        ],
    },

    'south_korea': {
        'keywords': [
            'south korea military', 'rok military', 'roka',
            'south korea north korea', 'inter-korean',
            'korea us military', 'us forces korea', 'usfk',
            'south korea missile', 'south korea nuclear',
            'dmz incident', 'korean demilitarized zone',
            'south korea japan defense', 'quad south korea',
            'south korea ukraine', 'rok arms export',
            'korea defense budget', 'korea rearmament',
        ],
        'reddit_keywords': [
            'south korea military', 'korea', 'korean peninsula',
            'north korea', 'CredibleDefense',
        ],
    },

    'taiwan': {
        'keywords': [
            'taiwan strait', 'taiwan military', 'roc military',
            'pla taiwan', 'taiwan adiz', 'china taiwan',
            'taiwan invasion', 'taiwan blockade',
            'taiwan us arms', 'us taiwan defense',
            'taiwan strait incursion', 'median line violation',
            'joint sword', 'pla exercise taiwan',
            'taiwan independence', 'taiwan contingency',
            'seventh fleet taiwan', 'taiwan japan defense',
        ],
        'reddit_keywords': [
            'taiwan', 'taiwan strait', 'pla taiwan', 'china taiwan',
            'taiwan defense', 'CredibleDefense',
        ],
    },
}


# ========================================
# NOTAM REGIONS — ASIA-PACIFIC ICAO CODES
# ========================================
NOTAM_REGIONS = {
    'taiwan_strait': {
        'name': 'Taiwan Strait / East China Sea',
        'icao_codes': ['RCTP', 'RCSS', 'ZGGG'],  # Taipei, Songshan, Guangzhou
        'fir': ['RJJJ', 'RCFIR'],
    },
    'korean_peninsula': {
        'name': 'Korean Peninsula',
        'icao_codes': ['RKSI', 'RKSS', 'ZKPY'],  # Incheon, Gimpo, Pyongyang
        'fir': ['RKRR', 'ZKKP'],
    },
    'south_china_sea': {
        'name': 'South China Sea',
        'icao_codes': ['WMKK', 'RPLL', 'VVTS'],  # Kuala Lumpur, Manila, Ho Chi Minh
        'fir': ['WSJC', 'RPHI'],
    },
    'japan': {
        'name': 'Japan / Okinawa',
        'icao_codes': ['RJTT', 'RJBB', 'ROAH'],  # Tokyo, Osaka, Naha (Okinawa)
        'fir': ['RJJJ', 'RJTT'],
    },
    'south_asia': {
        'name': 'South Asia (India/Pakistan/Afghanistan)',
        'icao_codes': ['VIDP', 'OPKC', 'OAKB'],  # Delhi, Karachi, Kabul
        'fir': ['VIDF', 'OPLR', 'OAKX'],
    },
}


# ========================================
# REDDIT CONFIGURATION — ASIA-PACIFIC
# ========================================
REDDIT_USER_AGENT = "AsifahAnalytics-Asia/1.0.0 (OSINT monitoring tool)"
REDDIT_SUBREDDITS = {
    # -------------------------------------------------------
    # AFGHANISTAN — Taliban ops, TTP, ISIS-K, Pak cross-border
    # -------------------------------------------------------
    'afghanistan': [
        # Core geopolitics / defense — always high signal
        'geopolitics', 'CredibleDefense', 'worldnews', 'LessCredibleDefence',
        'WarCollege', 'NCD', 'GlobalPowers', 'OSINT',
        # The one you thought I'd laugh at — active Asia geopolitics community
        'anime_titties',
        # Country-specific
        'afghanistan', 'Pashtun', 'pakistan',
        # Regional
        'SouthAsia', 'CentralAsia',
        # Conflict tracking
        'CombatFootage', 'UkraineRussiaReport',
        # Iran angle (Iran-Pak border, IRGC Jaish al-Adl ops)
        'iran',
    ],

    # -------------------------------------------------------
    # CHINA — PLA, SCS, Taiwan Strait, Iran oil, PLAN deployments
    # -------------------------------------------------------
    'china': [
        # Core
        'geopolitics', 'CredibleDefense', 'worldnews', 'LessCredibleDefence',
        'WarCollege', 'NCD', 'GlobalPowers', 'OSINT',
        'anime_titties',
        # China-specific
        'Sino', 'china',
        # Taiwan / SCS adversaries
        'taiwan', 'Taiwanese', 'Philippines', 'Vietnam',
        # Regional
        'EastAsia', 'AsiaPacific', 'southeast_asia',
        # Alliance watchers
        'Australia',
        # Naval / air
        'navy', 'AirForce',
        # Iran oil angle (China-Iran energy)
        'iran',
        # Conflict footage for SCS incidents
        'CombatFootage',
    ],

    # -------------------------------------------------------
    # INDIA — LAC, LoC, Pakistan, Quad, Indian Ocean
    # -------------------------------------------------------
    'india': [
        # Core
        'geopolitics', 'CredibleDefense', 'worldnews', 'LessCredibleDefence',
        'WarCollege', 'NCD', 'GlobalPowers', 'OSINT',
        'anime_titties',
        # India-specific
        'india', 'IndiaSpeaks', 'IndiaDefence',
        # Adversary angle
        'pakistan', 'Sino',
        # Regional
        'SouthAsia',
        # Conflict footage
        'CombatFootage',
        # Alliance angle
        'Australia',
    ],

    # -------------------------------------------------------
    # JAPAN — JSDF, Senkaku, NK missile alerts, AUKUS
    # -------------------------------------------------------
    'japan': [
        # Core
        'geopolitics', 'CredibleDefense', 'worldnews', 'LessCredibleDefence',
        'WarCollege', 'NCD', 'GlobalPowers', 'OSINT',
        'anime_titties',
        # Japan-specific
        'japan', 'japannews',
        # Regional / adversary angle
        'EastAsia', 'AsiaPacific', 'Sino',
        # North Korea missile alerts
        'northkorea', 'korea',
        # Naval / air (7th Fleet, JSDF)
        'navy', 'AirForce',
        # Alliance
        'Australia',
    ],

    # -------------------------------------------------------
    # NORTH KOREA — missile launches, nuclear, troops in Russia
    # -------------------------------------------------------
    'north_korea': [
        # Core
        'geopolitics', 'CredibleDefense', 'worldnews', 'LessCredibleDefence',
        'WarCollege', 'NCD', 'GlobalPowers', 'OSINT',
        'anime_titties',
        # NK-specific
        'northkorea', 'korea',
        # Regional
        'EastAsia', 'AsiaPacific',
        # NK troops in Ukraine — cross-post source
        'ukraine', 'UkraineRussiaReport',
        # Conflict footage (missile launches, border incidents)
        'CombatFootage',
        # South Korea existential angle
        'southkorea',
    ],

    # -------------------------------------------------------
    # PAKISTAN — TTP, Balochistan, Iran border, India LoC, nuclear
    # -------------------------------------------------------
    'pakistan': [
        # Core
        'geopolitics', 'CredibleDefense', 'worldnews', 'LessCredibleDefence',
        'WarCollege', 'NCD', 'GlobalPowers', 'OSINT',
        'anime_titties',
        # Pakistan-specific
        'pakistan', 'Pashtun',
        # India angle (LoC, Kashmir)
        'india', 'IndiaSpeaks',
        # Afghanistan angle (TTP, cross-border)
        'afghanistan',
        # Iran angle (Iran-Pak border strikes, Jaish al-Adl)
        'iran',
        # Regional
        'SouthAsia',
        # Conflict footage
        'CombatFootage',
    ],

    # -------------------------------------------------------
    # SOUTH KOREA — NK threat, USFK, inter-Korean, NK troops in Russia
    # -------------------------------------------------------
    'south_korea': [
        # Core
        'geopolitics', 'CredibleDefense', 'worldnews', 'LessCredibleDefence',
        'WarCollege', 'NCD', 'GlobalPowers', 'OSINT',
        'anime_titties',
        # Korea-specific
        'korea', 'southkorea', 'northkorea',
        # Regional
        'EastAsia', 'AsiaPacific',
        # NK troops in Russia context
        'ukraine', 'UkraineRussiaReport',
        # Conflict footage (NK provocations, artillery)
        'CombatFootage',
    ],

    # -------------------------------------------------------
    # TAIWAN — PLA exercises, strait crossings, blockade scenarios
    # -------------------------------------------------------
    'taiwan': [
        # Core
        'geopolitics', 'CredibleDefense', 'worldnews', 'LessCredibleDefence',
        'WarCollege', 'NCD', 'GlobalPowers', 'OSINT',
        'anime_titties',
        # Taiwan-specific
        'taiwan', 'Taiwanese',
        # China angle
        'Sino', 'china',
        # Regional — SCS neighbors watch Taiwan closely
        'EastAsia', 'AsiaPacific', 'Philippines', 'Vietnam',
        # Alliance watchers
        'Australia',
        # Naval (7th Fleet, PLAN)
        'navy', 'AirForce',
        # Conflict footage
        'CombatFootage',
    ],
}


# ========================================
# ASIA-PACIFIC ESCALATION KEYWORDS
# ========================================
ESCALATION_KEYWORDS = [
    'strike', 'attack', 'bombing', 'airstrike', 'missile', 'rocket',
    'military operation', 'offensive', 'retaliate', 'retaliation',
    'response', 'counterattack', 'invasion', 'incursion',
    'shelling', 'artillery', 'drone strike', 'drone attack',
    'threatens', 'warned', 'vowed', 'promised to strike',
    'will respond', 'severe response', 'consequences',
    'mobilization', 'troops deployed', 'forces gathering',
    'military buildup', 'reserves called up',
    'killed', 'dead', 'casualties', 'wounded', 'injured',
    'death toll', 'fatalities',
    'nuclear threat', 'nuclear posture', 'tactical nuclear',
    'airspace violation', 'airspace closed', 'no-fly zone',
    'sovereignty violation', 'territorial integrity',
    'flight cancellations', 'cancelled flights', 'suspend flights',
    'suspended flights', 'airline suspends', 'halted flights',
    'grounded flights', 'travel advisory',
    'do not travel', 'avoid all travel', 'reconsider travel',
    # Asia-specific escalation
    'median line violation', 'adiz violation',
    'taiwan strait closure', 'blockade taiwan',
    'icbm launch', 'missile test north korea',
    'nuclear test dprk', 'kim jong un orders',
    'line of actual control', 'galwan', 'doklam',
    'pakistan india skirmish', 'kashmir shelling',
    'pla exercise live fire', 'joint sword',
    'carrier group deployment', 'seventh fleet',
    'scrambles jets', 'jets scrambled',
    'base attacked', 'base hit', 'base struck',
    'intercepts missile', 'shoots down missile',
    'air defense activated', 'pac-3 activated',
    'regime change', 'coup attempt',
    # Airlines
    'cathay pacific cancel', 'japan airlines cancel',
    'ana cancel flights', 'korean air cancel',
    'air india cancel', 'pia cancel flights',
    'china airlines cancel', 'eva air cancel',
]


# ========================================
# DATE PARSING HELPER
# ========================================

def parse_pub_date(pub_str):
    """
    Robustly parse a publication date string into a UTC-aware datetime.
    Handles ISO 8601, RFC 2822, and GDELT seendate formats.
    Always returns a timezone-aware datetime or None.
    """
    if not pub_str:
        return None

    def _make_aware(dt):
        """Ensure datetime is timezone-aware (UTC)."""
        if dt is not None and dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    try:
        # ISO 8601 / RFC 3339 (most common: NewsAPI, Reddit)
        dt = datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
        return _make_aware(dt)
    except (ValueError, AttributeError):
        pass
    try:
        # RFC 2822 (RSS feeds): "Thu, 12 Mar 2026 12:28:03 GMT"
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(pub_str).astimezone(timezone.utc)
    except Exception:
        pass
    try:
        # GDELT seendate format: "20260312T122803Z" or "20260312122803"
        clean = pub_str.replace('T', '').replace('Z', '').replace('-', '').replace(':', '').replace(' ', '')
        if len(clean) >= 14:
            return datetime.strptime(clean[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
        elif len(clean) == 8:
            return datetime.strptime(clean[:8], '%Y%m%d').replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None


# ========================================
# ARTICLE FETCHING — NEWS API
# ========================================

def fetch_newsapi_articles(query, days=7):
    """Fetch articles from NewsAPI."""
    if not NEWSAPI_KEY:
        return []
    try:
        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
        response = requests.get(
            'https://newsapi.org/v2/everything',
            params={
                'q': query,
                'from': from_date,
                'sortBy': 'publishedAt',
                'language': 'en',
                'pageSize': 30,
                'apiKey': NEWSAPI_KEY,
            },
            timeout=(5, 15)
        )
        if response.status_code == 200:
            articles = response.json().get('articles', [])
            for a in articles:
                a['language'] = 'en'
            return articles
    except Exception as e:
        print(f"[Asia v1.0] NewsAPI error: {str(e)[:100]}")
    return []


# ========================================
# ARTICLE FETCHING — GDELT
# ========================================

# v1.1.0 — GDELT rate-limit cooldown cache
# When GDELT soft-blocks a language (429 or non-JSON HTML), we remember
# the timestamp and skip that language for 15 minutes to avoid making
# the whole Asia scan exceed the 25s endpoint timeout.
_GDELT_COOLDOWN = {}  # language -> unix_timestamp_when_ok_to_retry
_GDELT_COOLDOWN_SECONDS = 15 * 60  # 15 minutes


def fetch_gdelt_articles(query, days=7, language='eng'):
    """Fetch articles from GDELT API. Hardened against soft-blocks and non-JSON."""
    # ── v1.1.0 — Respect per-language cooldown ──
    now = time.time()
    cooldown_until = _GDELT_COOLDOWN.get(language, 0)
    if cooldown_until > now:
        remaining = int(cooldown_until - now)
        print(f"[Asia GDELT] {language}: In cooldown ({remaining}s remaining) — skipping")
        return []

    try:
        params = {
            'query': query,
            'mode': 'artlist',
            'maxrecords': 30,
            'timespan': f'{days}d',
            'format': 'json',
            'sourcelang': language,
        }
        resp = None
        for attempt in range(2):
            try:
                resp = requests.get(GDELT_BASE_URL, params=params, timeout=(5, 15))
                if resp.status_code == 429:
                    print(f"[Asia GDELT] {language}: Rate limited (429) — cooling down {_GDELT_COOLDOWN_SECONDS // 60}min")
                    _GDELT_COOLDOWN[language] = now + _GDELT_COOLDOWN_SECONDS
                    return []
                if resp.status_code == 200:
                    break
            except requests.Timeout:
                if attempt == 0:
                    print(f"[Asia GDELT] {language}: Retry after timeout...")
                    time.sleep(2)
                    continue
                raise

        if resp and resp.status_code == 200:
            # ── v1.1.0 — Detect HTML error pages (GDELT soft-block signature) ──
            body = resp.text.lstrip()
            if body.startswith('<') or 'html' in resp.headers.get('content-type', '').lower():
                print(f"[Asia GDELT] {language}: HTML response (likely soft-block) — cooling down {_GDELT_COOLDOWN_SECONDS // 60}min")
                _GDELT_COOLDOWN[language] = now + _GDELT_COOLDOWN_SECONDS
                return []

            try:
                data = resp.json()
            except (json.JSONDecodeError, ValueError):
                print(f"[Asia GDELT] {language}: Non-JSON response — cooling down {_GDELT_COOLDOWN_SECONDS // 60}min")
                _GDELT_COOLDOWN[language] = now + _GDELT_COOLDOWN_SECONDS
                return []

            lang_map = {
                'eng': 'en', 'zho': 'zh', 'kor': 'ko',
                'urd': 'ur', 'prs': 'fa', 'jpn': 'ja',
            }
            articles = []
            for art in data.get('articles', []):
                articles.append({
                    'title': art.get('title', ''),
                    'description': art.get('title', ''),
                    'url': art.get('url', ''),
                    'publishedAt': art.get('seendate', ''),
                    'source': {'name': f"GDELT ({language})"},
                    'content': art.get('title', ''),
                    'language': lang_map.get(language, language),
                })
            if articles:
                print(f"[Asia GDELT] {language}: ✓ {len(articles)} articles")
            return articles
    except Exception as e:
        print(f"[Asia GDELT] {language} error: {str(e)[:80]}")
    return []


# ========================================
# ARTICLE FETCHING — GOOGLE NEWS RSS
# ========================================

def fetch_google_news_rss(query, source_name, lang='en', gl='US'):
    """Fetch articles from Google News RSS."""
    articles = []
    try:
        encoded_query = requests.utils.quote(query)
        ceid = f"{lang.upper()}-{gl}"
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl={lang}&gl={gl}&ceid={ceid}"
        response = requests.get(url, timeout=(5, 15), headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            for item in items[:15]:
                title_elem = item.find('title')
                link_elem = item.find('link')
                pub_elem = item.find('pubDate')
                if title_elem is not None:
                    articles.append({
                        'title': title_elem.text or '',
                        'description': title_elem.text or '',
                        'url': link_elem.text if link_elem is not None else '',
                        'publishedAt': pub_elem.text if pub_elem is not None else '',
                        'source': {'name': source_name},
                        'content': title_elem.text or '',
                        'language': lang,
                    })
    except Exception as e:
        print(f"[Asia RSS] {source_name} error: {str(e)[:100]}")
    return articles


def fetch_direct_rss(url, source_name, weight=0.85, max_items=15):
    """Fetch articles directly from an RSS feed URL (not Google News)."""
    articles = []
    try:
        response = requests.get(url, timeout=(5, 15), headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            items = root.findall('.//item')
            for item in items[:max_items]:
                title_elem = item.find('title')
                link_elem = item.find('link')
                pub_elem = item.find('pubDate')
                desc_elem = item.find('description')
                if title_elem is not None and title_elem.text:
                    articles.append({
                        'title': title_elem.text.strip(),
                        'description': (desc_elem.text or title_elem.text or '').strip(),
                        'url': link_elem.text.strip() if link_elem is not None and link_elem.text else '',
                        'publishedAt': pub_elem.text if pub_elem is not None else '',
                        'source': {'name': source_name},
                        'content': title_elem.text.strip(),
                        'source_weight_override': weight,
                    })
    except Exception as e:
        print(f"[Direct RSS] {source_name} error: {str(e)[:100]}")
    return articles


# ========================================
# ARTICLE FETCHING — REDDIT
# ========================================

# v1.1.0 — Reddit cooldown (platform-wide, not per-subreddit)
# Reddit aggressively rate-limits unauthenticated requests, often returning
# 429 (Too Many Requests) or 403 (Forbidden) without explicit retry-after.
# When we hit one, cool down ALL Reddit calls for 30 minutes to avoid
# burning through our request budget on a single scan.
_REDDIT_COOLDOWN_UNTIL = 0  # unix timestamp
_REDDIT_COOLDOWN_SECONDS = 30 * 60


def fetch_reddit_posts(target, keywords, days=7):
    """Fetch Reddit posts from relevant subreddits."""
    global _REDDIT_COOLDOWN_UNTIL

    articles = []
    subreddits = REDDIT_SUBREDDITS.get(target, [])
    if not subreddits:
        return []

    # ── v1.1.0 — Respect cooldown ──
    now_ts = time.time()
    if _REDDIT_COOLDOWN_UNTIL > now_ts:
        remaining = int(_REDDIT_COOLDOWN_UNTIL - now_ts)
        print(f"[Asia Reddit] In cooldown ({remaining}s remaining) — skipping all subs")
        return []

    since = datetime.now(timezone.utc) - timedelta(days=days)
    total_fetched = 0
    sub_successes = 0
    sub_failures = 0

    for subreddit in subreddits:
        sub_article_count = 0
        for keyword in keywords[:3]:
            try:
                url = f"https://www.reddit.com/r/{subreddit}/search.json"
                params = {
                    'q': keyword,
                    'sort': 'new',
                    'limit': 10,
                    't': 'week',
                    'restrict_sr': 'true'
                }
                response = requests.get(
                    url, params=params, timeout=10,
                    headers={"User-Agent": REDDIT_USER_AGENT}
                )

                # ── v1.1.0 — Observable failure handling ──
                if response.status_code == 429:
                    print(f"[Asia Reddit] 429 rate-limited — cooling down {_REDDIT_COOLDOWN_SECONDS // 60}min")
                    _REDDIT_COOLDOWN_UNTIL = time.time() + _REDDIT_COOLDOWN_SECONDS
                    # Bail entirely — don't hammer other subs during cooldown
                    print(f"[Asia Reddit] Summary: {total_fetched} posts fetched before cooldown ({sub_successes}/{len(subreddits)} subs)")
                    return articles
                if response.status_code == 403:
                    print(f"[Asia Reddit] 403 forbidden (r/{subreddit}) — skipping")
                    break
                if response.status_code != 200:
                    print(f"[Asia Reddit] r/{subreddit} HTTP {response.status_code} — skipping")
                    break

                posts = response.json().get('data', {}).get('children', [])
                for post in posts:
                    post_data = post.get('data', {})
                    created = post_data.get('created_utc', 0)
                    post_time = datetime.fromtimestamp(created, tz=timezone.utc)
                    if post_time >= since:
                        articles.append({
                            'title': post_data.get('title', ''),
                            'description': post_data.get('selftext', '')[:500],
                            'url': f"https://www.reddit.com{post_data.get('permalink', '')}",
                            'publishedAt': post_time.isoformat(),
                            'source': {'name': f"r/{subreddit}"},
                            'content': post_data.get('selftext', '')[:500],
                            'language': 'en',
                        })
                        sub_article_count += 1
                time.sleep(0.5)
            except requests.Timeout:
                print(f"[Asia Reddit] r/{subreddit} timeout on '{keyword}' — skipping keyword")
                continue
            except Exception as e:
                print(f"[Asia Reddit] r/{subreddit} error: {str(e)[:80]}")
                continue

        total_fetched += sub_article_count
        if sub_article_count > 0:
            sub_successes += 1
        else:
            sub_failures += 1

    print(f"[Asia Reddit] {target}: {total_fetched} posts from {sub_successes}/{len(subreddits)} subs")
    return articles


# ========================================
# THREAT SCORING
# ========================================

def get_source_weight(source_name):
    """Return source credibility weight."""
    for tier, tier_data in SOURCE_WEIGHTS.items():
        if tier == 'standard':
            continue
        if source_name in tier_data.get('sources', []):
            return tier_data['weight']
    return SOURCE_WEIGHTS['standard']['weight']


def calculate_threat_probability(articles, days=7, target=None):
    """
    Score articles against escalation keywords with time decay and source weighting.
    Returns probability (0-100), momentum, and breakdown.
    """
    if not articles:
        return {'probability': 0, 'momentum': 'stable', 'breakdown': {}, 'top_contributors': []}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    # Deduplicate articles by URL before scoring to prevent same article
    # matching multiple keywords and inflating weighted_score
    seen_urls_score = set()
    deduped_articles = []
    for a in articles:
        url = (a.get('url', '') or a.get('link', '') or '').split('?')[0].rstrip('/')
        if url and url in seen_urls_score:
            continue
        if url:
            seen_urls_score.add(url)
        deduped_articles.append(a)
    articles = deduped_articles

    scored_articles = []
    deescalation_keywords = [
        'ceasefire', 'peace talks', 'negotiations', 'diplomacy', 'de-escalation',
        'withdraw', 'pullback', 'summit', 'agreement', 'deal', 'truce',
        'diplomatic solution', 'talks resume', 'dialogue',
    ]

    for article in articles:
        title = (article.get('title', '') or '').lower()
        description = (article.get('description', '') or '').lower()
        content = (article.get('content', '') or '').lower()
        text = f"{title} {description} {content}"

        # Time decay
        pub_str = article.get('publishedAt', '')
        try:
            if pub_str:
                pub_date = parse_pub_date(pub_str)
                if pub_date is None:
                    raise ValueError("unparseable date")
                if pub_date.tzinfo is None:
                    pub_date = pub_date.replace(tzinfo=timezone.utc)
                age_hours = (now - pub_date).total_seconds() / 3600
                if age_hours <= 24:
                    time_decay = 1.0
                elif age_hours <= 48:
                    time_decay = 0.8
                elif age_hours <= 72:
                    time_decay = 0.6
                else:
                    time_decay = max(0.2, 1.0 - (age_hours / (days * 24)) * 0.8)
            else:
                time_decay = 0.5
        except Exception:
            time_decay = 0.5

        # Escalation scoring
        matched_keywords = [kw for kw in ESCALATION_KEYWORDS if kw in text]
        severity = len(matched_keywords)

        # De-escalation penalty
        deesc_matches = [kw for kw in deescalation_keywords if kw in text]
        if deesc_matches:
            severity = max(0, severity - len(deesc_matches) * 2)

        if severity == 0:
            continue

        source_name = article.get('source', {}).get('name', 'Unknown') if isinstance(
            article.get('source'), dict) else str(article.get('source', 'Unknown'))
        # v1.1.0 — Honor per-article weight override from fetch_direct_rss.
        # Previously ignored, meaning Dawn (weight=0.95) was scored at 0.5 anyway.
        override = article.get('source_weight_override')
        if isinstance(override, (int, float)) and 0 < override <= 1.0:
            source_weight = float(override)
        else:
            source_weight = get_source_weight(source_name)

        contribution = severity * source_weight * time_decay
        scored_articles.append({
            'article': article,
            'severity': severity,
            'source_weight': source_weight,
            'time_decay': time_decay,
            'contribution': contribution,
            'source': source_name,
            'deescalation': len(deesc_matches) > 0,
        })

    if not scored_articles:
        return {'probability': 0, 'momentum': 'stable', 'breakdown': {
            'weighted_score': 0, 'recent_articles_48h': 0, 'older_articles': 0,
            'deescalation_count': 0,
        }, 'top_contributors': []}

    weighted_score = sum(s['contribution'] for s in scored_articles)
    def _article_age_hours(s):
        pd = parse_pub_date(s['article'].get('publishedAt', '') or '')
        if pd is None:
            return 999
        if pd.tzinfo is None:
            pd = pd.replace(tzinfo=timezone.utc)
        return (now - pd).total_seconds() / 3600

    recent_count = sum(1 for s in scored_articles if _article_age_hours(s) <= 48)

    deesc_count = sum(1 for s in scored_articles if s['deescalation'])
    older_count = len(scored_articles) - recent_count

    # Normalize to 0-100
    probability = min(100, int(weighted_score * 1.5))

    # Momentum
    if recent_count > older_count * 1.5:
        momentum = 'increasing'
    elif older_count > recent_count * 1.5:
        momentum = 'decreasing'
    else:
        momentum = 'stable'

    top_contributors = sorted(scored_articles, key=lambda x: x['contribution'], reverse=True)[:10]

    return {
        'probability': probability,
        'momentum': momentum,
        'breakdown': {
            'weighted_score': round(weighted_score, 2),
            'recent_articles_48h': recent_count,
            'older_articles': older_count,
            'deescalation_count': deesc_count,
        },
        'top_contributors': [
            {
                'source': c['source'],
                'contribution': round(c['contribution'], 2),
                'severity': c['severity'],
                'source_weight': c['source_weight'],
                'time_decay': round(c['time_decay'], 2),
                'deescalation': c['deescalation'],
            } for c in top_contributors
        ]
    }


# ========================================
# FLIGHT DISRUPTION SCANNER
# ========================================

def scan_asian_flight_disruptions(articles):
    """Scan articles for Asia-Pacific flight disruption signals."""
    disruptions = []
    flight_keywords = [
        'flight cancelled', 'flights cancelled', 'flights suspended',
        'airspace closed', 'airport closed', 'no fly zone',
        'airline suspend', 'flights grounded', 'aviation warning',
        'taiwan strait closed', 'korean airspace', 'japan airspace',
    ]
    seen = set()
    for article in articles:
        title = (article.get('title', '') or '').lower()
        desc = (article.get('description', '') or '').lower()
        text = f"{title} {desc}"
        if any(kw in text for kw in flight_keywords):
            url = article.get('url', '')
            if url not in seen:
                seen.add(url)
                disruptions.append({
                    'title': article.get('title', ''),
                    'source': article.get('source', {}).get('name', 'Unknown') if isinstance(
                        article.get('source'), dict) else str(article.get('source', '')),
                    'url': url,
                    'publishedAt': article.get('publishedAt', ''),
                })
    return disruptions[:20]


# ========================================
# NOTAM SCANNING — FAA API
# ========================================

def scan_asia_notams():
    """Scan FAA NOTAM API for Asia-Pacific regions."""
    notams = []
    FAA_NOTAM_URL = "https://notams.aim.faa.gov/notamSearch/search"

    for region_key, region in NOTAM_REGIONS.items():
        icao_codes = region.get('icao_codes', [])[:3]
        for icao in icao_codes:
            try:
                params = {
                    'searchType': 0,
                    'designatorsForLocation': icao,
                    'radiusWithDesignator': 100,
                    'pageSize': 10,
                    'pageOffset': 0,
                }
                response = requests.get(
                    FAA_NOTAM_URL, params=params,
                    headers={'Accept': 'application/json'},
                    timeout=15
                )
                if response.status_code == 200:
                    data = response.json()
                    items = data.get('notamList', [])
                    for item in items:
                        text = (item.get('traditionalMessage', '')
                                or item.get('icaoMessage', '')
                                or item.get('plainLanguage', ''))
                        notams.append({
                            'icao': icao,
                            'region': region['name'],
                            'id': item.get('notamNumber', ''),
                            'text': text[:500],
                            'effectiveStart': item.get('startDate', ''),
                            'effectiveEnd': item.get('endDate', ''),
                        })
            except Exception as e:
                print(f"[Asia NOTAM] {icao} error: {str(e)[:80]}")
            time.sleep(0.3)

    return notams


# ========================================
# TRAVEL ADVISORY SCANNER
# ========================================

def _run_travel_advisory_scan():
    """Fetch all travel advisories from State Dept and extract Asia-Pacific targets."""
    print("[Asia] Travel Advisories: Fetching from State Dept API...")
    results = {}

    try:
        response = requests.get(TRAVEL_ADVISORY_API, timeout=20)
        if response.status_code != 200:
            print(f"[Asia] Travel Advisories: HTTP {response.status_code}")
            return {'success': False, 'error': f'HTTP {response.status_code}', 'advisories': {}}

        all_advisories = response.json()
        print(f"[Asia] Travel Advisories: Got {len(all_advisories)} total advisories")

        for target, codes in TRAVEL_ADVISORY_CODES.items():
            for advisory in all_advisories:
                cats = advisory.get('Category', [])
                if any(code in cats for code in codes):
                    title = advisory.get('Title', '')
                    level_match = re.search(r'Level\s+(\d)', title)
                    level = int(level_match.group(1)) if level_match else None
                    published = advisory.get('Published', '')
                    updated = advisory.get('Updated', '')
                    link = advisory.get('Link', '')
                    summary_html = advisory.get('Summary', '')

                    # Extract first paragraph as short summary
                    short_summary = ''
                    summary_match = re.search(r'<p[^>]*>(.*?)</p>', summary_html, re.DOTALL)
                    if summary_match:
                        short_summary = re.sub(r'<[^>]+>', '', summary_match.group(1)).strip()

                    # Detect if recently changed (within last 30 days)
                    recently_changed = False
                    change_description = ''
                    try:
                        updated_dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                        age_days = (datetime.now(timezone.utc) - updated_dt).days
                        recently_changed = age_days <= 30

                        change_match = re.search(
                            r'(advisory level was (?:increased|decreased|raised|lowered|changed).*?\.)',
                            summary_html, re.IGNORECASE
                        )
                        if change_match:
                            change_description = re.sub(r'<[^>]+>', '', change_match.group(1)).strip()
                        elif recently_changed:
                            if 'no change' in summary_html.lower() or 'no changes to the advisory level' in summary_html.lower():
                                change_description = 'Updated (level unchanged)'
                            else:
                                change_description = f'Updated {age_days} day{"s" if age_days != 1 else ""} ago'
                    except Exception:
                        pass

                    level_info = TRAVEL_ADVISORY_LEVELS.get(level, {})

                    results[target] = {
                        'country_code': cats[0] if cats else '',
                        'title': title,
                        'level': level,
                        'level_label': level_info.get('label', 'Unknown'),
                        'level_short': level_info.get('short', 'Unknown'),
                        'level_color': level_info.get('color', '#6b7280'),
                        'published': published,
                        'updated': updated,
                        'recently_changed': recently_changed,
                        'change_description': change_description,
                        'short_summary': short_summary,
                        'link': link
                    }
                    print(f"[Asia] Travel Advisory: {target} -> Level {level} ({level_info.get('short', '?')})")
                    break

    except Exception as e:
        print(f"[Asia] Travel Advisories error: {e}")
        return {'success': False, 'error': str(e), 'advisories': {}}

    return {
        'success': True,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'advisories': results,
        'version': '1.0.0-asia'
    }


# ========================================
# MAIN THREAT SCAN
# ========================================

def _run_threat_scan(target, days=7):
    """
    Run a full threat scan for a target. Returns the complete response dict.
    Used by both the API endpoint and the background refresh thread.
    """
    query = ' OR '.join(TARGET_KEYWORDS[target]['keywords'][:8])

    # English
    articles_en = fetch_newsapi_articles(query, days)
    articles_gdelt_en = fetch_gdelt_articles(query, days, 'eng')

    # Language-specific GDELT
    articles_gdelt_zh = []
    articles_gdelt_ko = []
    articles_gdelt_ur = []
    articles_gdelt_fa = []
    articles_gdelt_ja = []

    if target in ('china', 'taiwan'):
        time.sleep(0.5)
        articles_gdelt_zh = fetch_gdelt_articles(query, days, 'zho')
    if target in ('south_korea', 'north_korea'):
        time.sleep(0.5)
        articles_gdelt_ko = fetch_gdelt_articles(query, days, 'kor')
    if target in ('pakistan', 'afghanistan'):
        time.sleep(0.5)
        articles_gdelt_ur = fetch_gdelt_articles(query, days, 'urd')
        time.sleep(0.5)
        articles_gdelt_fa = fetch_gdelt_articles(query, days, 'prs')
    if target == 'japan':
        time.sleep(0.5)
        articles_gdelt_ja = fetch_gdelt_articles(query, days, 'jpn')

    # Reddit
    articles_reddit = fetch_reddit_posts(
        target,
        TARGET_KEYWORDS[target]['reddit_keywords'],
        days
    )

    # Target-specific RSS
    rss_articles = []

    if target == 'taiwan':
        try:
            rss_articles.extend(fetch_google_news_rss(
                'Taiwan strait OR PLA OR China military taiwan OR blockade',
                'Taiwan News'))
        except Exception as e:
            print(f"Taiwan RSS error: {e}")
        try:
            rss_articles.extend(fetch_google_news_rss(
                '台灣海峽 OR 解放軍 OR 台海', 'Taiwan News (ZH)', lang='zh', gl='TW'))
        except Exception as e:
            print(f"Taiwan ZH RSS error: {e}")

    if target == 'north_korea':
        try:
            rss_articles.extend(fetch_google_news_rss(
                'North Korea missile OR DPRK launch OR Kim Jong Un military',
                'North Korea News'))
        except Exception as e:
            print(f"North Korea RSS error: {e}")
        try:
            rss_articles.extend(fetch_google_news_rss(
                '북한 미사일 OR 김정은', 'North Korea News (KO)', lang='ko', gl='KR'))
        except Exception as e:
            print(f"North Korea KO RSS error: {e}")
        # v1.1.0 — DPRK premium sources
        # NK News — DPRK specialist (semi-paywalled but RSS headlines free)
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://www.nknews.org/feed/',
                'NK News', weight=0.95))
        except Exception as e:
            print(f"NK News RSS error: {e}")
        # Daily NK — ground-level DPRK reporting from defector networks
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://www.dailynk.com/english/feed/',
                'Daily NK', weight=0.9))
        except Exception as e:
            print(f"Daily NK RSS error: {e}")
        # 38 North — Stimson Center DPRK analysis
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://www.38north.org/feed/',
                '38 North', weight=0.95))
        except Exception as e:
            print(f"38 North RSS error: {e}")
        # Yonhap News (English) — South Korea wire service with DPRK desk
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://en.yna.co.kr/RSS/northkorea.xml',
                'Yonhap News', weight=1.0))
        except Exception as e:
            print(f"Yonhap RSS error: {e}")
        # KBS World English — South Korean public broadcaster NK desk
        try:
            rss_articles.extend(fetch_direct_rss(
                'http://world.kbs.co.kr/rss/rss_news.htm?lang=e&id=Po',
                'KBS World', weight=0.85))
        except Exception as e:
            print(f"KBS World RSS error: {e}")

    if target == 'china':
        try:
            rss_articles.extend(fetch_google_news_rss(
                'China military OR PLA OR south china sea OR taiwan strait',
                'China News'))
        except Exception as e:
            print(f"China RSS error: {e}")

    if target == 'pakistan':
        try:
            rss_articles.extend(fetch_google_news_rss(
                'Pakistan military OR Pakistan strikes Afghanistan OR Pakistan army operation OR TTP attack',
                'Pakistan News'))
        except Exception as e:
            print(f"Pakistan RSS error: {e}")
        # Dawn — Pakistan's leading English newspaper
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://www.dawn.com/feeds/home',
                'Dawn', weight=0.95))
        except Exception as e:
            print(f"Dawn RSS error: {e}")
        # Geo News — major Pakistani broadcaster
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://www.geo.tv/rss/10',
                'Geo News', weight=0.85))
        except Exception as e:
            print(f"Geo News RSS error: {e}")
        # The News International — solid on military/security
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://www.thenews.com.pk/rss/1/8',
                'The News International', weight=0.85))
        except Exception as e:
            print(f"The News RSS error: {e}")
        # RFE/RL Gandhara — Pakistan/Afghan borderlands specialist
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://gandhara.rferl.org/api/zrqmilty',
                'RFE/RL Gandhara (PK)', weight=0.95))
        except Exception as e:
            print(f"Gandhara PK RSS error: {e}")
        # SATP — South Asia Terrorism Portal incident reports
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://www.satp.org/rss/conflict-updates.xml',
                'SATP Pakistan', weight=0.9))
        except Exception as e:
            print(f"SATP RSS error: {e}")
        # v1.1.0 — Additional Pakistan premium sources
        # Express Tribune — English daily, strong on Afghan/TTP desk
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://tribune.com.pk/feed/home',
                'Express Tribune', weight=0.85))
        except Exception as e:
            print(f"Express Tribune RSS error: {e}")
        # Al Jazeera Pakistan/Afghanistan coverage
        try:
            rss_articles.extend(fetch_google_news_rss(
                'Pakistan Afghanistan TTP site:aljazeera.com',
                'Al Jazeera PK'))
        except Exception as e:
            print(f"Al Jazeera PK RSS error: {e}")

    if target == 'afghanistan':
        # Google News — English operational reporting
        try:
            rss_articles.extend(fetch_google_news_rss(
                'Afghanistan Taliban attack OR Pakistan strikes Afghanistan OR ISIS-K Kabul OR Afghan border',
                'Afghanistan News'))
        except Exception as e:
            print(f"Afghanistan RSS error: {e}")
        # Tolo News — Afghan broadcaster
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://tolonews.com/rss.xml',
                'Tolo News', weight=0.9))
        except Exception as e:
            print(f"Tolo News RSS error: {e}")
        # Khaama Press — Afghan news agency
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://www.khaama.com/feed/',
                'Khaama Press', weight=0.9))
        except Exception as e:
            print(f"Khaama Press RSS error: {e}")
        # Pajhwok Afghan News — gold standard ground-level Afghan reporting
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://pajhwok.com/feed/',
                'Pajhwok Afghan News', weight=0.9))
        except Exception as e:
            print(f"Pajhwok RSS error: {e}")
        # Ariana News — Afghan broadcaster
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://ariananews.af/feed/',
                'Ariana News', weight=0.85))
        except Exception as e:
            print(f"Ariana News RSS error: {e}")
        # RFE/RL Gandhara — Afghan/Pak borderlands specialist
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://gandhara.rferl.org/api/zrqmilty',
                'RFE/RL Gandhara', weight=0.95))
        except Exception as e:
            print(f"Gandhara RSS error: {e}")
        # ReliefWeb — UN/NGO humanitarian + security incidents
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://reliefweb.int/country/afg/rss.xml',
                'ReliefWeb Afghanistan', weight=0.85))
        except Exception as e:
            print(f"ReliefWeb RSS error: {e}")
        # Afghanistan Analysts Network — deep analytical reporting
        try:
            rss_articles.extend(fetch_direct_rss(
                'https://www.afghanistan-analysts.org/feed/',
                'Afghanistan Analysts Network', weight=0.95))
        except Exception as e:
            print(f"AAN RSS error: {e}")
        # Dawn — targeted Google News query for Pak-Afghan border stories only
        try:
            rss_articles.extend(fetch_google_news_rss(
                'Pakistan Afghanistan border OR Durand line OR Pakistan airstrike Afghanistan OR TTP Afghanistan',
                'Dawn (AF)'))
        except Exception as e:
            print(f"Dawn AF RSS error: {e}")

    if target == 'india':
        try:
            rss_articles.extend(fetch_google_news_rss(
                'India military OR India China border OR India Pakistan OR Kashmir',
                'India News'))
        except Exception as e:
            print(f"India RSS error: {e}")

    if target == 'japan':
        try:
            rss_articles.extend(fetch_google_news_rss(
                'Japan JSDF OR Japan military OR Japan North Korea OR Senkaku',
                'Japan News'))
        except Exception as e:
            print(f"Japan RSS error: {e}")
        try:
            rss_articles.extend(fetch_google_news_rss(
                '自衛隊 OR 北朝鮮 ミサイル OR 尖閣', 'Japan News (JA)', lang='ja', gl='JP'))
        except Exception as e:
            print(f"Japan JA RSS error: {e}")

    if target == 'south_korea':
        try:
            rss_articles.extend(fetch_google_news_rss(
                'South Korea military OR Korea DPRK OR inter-Korean',
                'South Korea News'))
        except Exception as e:
            print(f"South Korea RSS error: {e}")

    # Telegram — uses shared in-memory cache to avoid fetching 8x per refresh cycle
    telegram_articles = []
    if TELEGRAM_AVAILABLE:
        try:
            now = datetime.now(timezone.utc)
            cache_age_secs = (
                (now - _telegram_cache['fetched_at']).total_seconds()
                if _telegram_cache['fetched_at'] else 9999
            )
            # v1.1.0 — CRITICAL FIX: Do NOT force re-fetch when messages list is empty.
            # Previously `if ... or not _telegram_cache['messages']` meant every scan
            # after a flood-waited fetch would hammer Telegram again, creating a
            # doom loop of 13/18 channels getting rate-limited on every request.
            # Now we respect the TTL regardless of result size — empty is a valid
            # cache state that means "we tried recently and got nothing useful."
            if cache_age_secs > _telegram_cache['ttl_seconds']:
                print(f"[Telegram Cache] Fetching fresh (last fetch: {int(cache_age_secs)}s ago)")
                try:
                    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(fetch_asia_telegram_signals,
                            max(days * 24, 168), True)
                        _telegram_cache['messages'] = future.result(timeout=60)
                except Exception:
                    print("[Telegram Cache] Fetch timed out or failed — using empty cache")
                    _telegram_cache['messages'] = []
                _telegram_cache['fetched_at'] = now
            else:
                print(f"[Telegram Cache] Using cached messages ({int(cache_age_secs)}s old, {len(_telegram_cache['messages'])} msgs)")

            telegram_msgs = _telegram_cache['messages']
            if telegram_msgs:
                target_kws = [kw.lower() for kw in TARGET_KEYWORDS.get(target, {}).get('keywords', [])]
                target_name = target.replace('_', ' ').lower()
                for msg in telegram_msgs:
                    msg_text = (msg.get('title', '') or '').lower()
                    if target_name in msg_text or any(kw in msg_text for kw in target_kws[:15]):
                        telegram_articles.append({
                            'title': msg.get('title', '')[:200],
                            'description': msg.get('title', '')[:500],
                            'url': msg.get('url', ''),
                            'publishedAt': msg.get('published', ''),
                            'source': {'name': msg.get('source', 'Telegram')},
                            'content': msg.get('title', '')[:500],
                            'language': 'multi',
                        })
        except Exception as e:
            print(f"[Asia Scan] Telegram error: {str(e)[:100]}")

    # v1.1.0 (April 2026) — Bluesky signals (replaces gap from flood-waited Telegram)
    bluesky_articles = []
    if BLUESKY_AVAILABLE:
        try:
            from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(fetch_bluesky_for_target, target, days, 20)
                try:
                    bluesky_articles = future.result(timeout=45)
                except FuturesTimeout:
                    print(f"[{target}] Bluesky fetch >45s — skipping this scan")
                    bluesky_articles = []
        except Exception as e:
            print(f"[{target}] Bluesky error: {str(e)[:100]}")
            bluesky_articles = []

    all_articles = (
        articles_en + articles_gdelt_en +
        articles_gdelt_zh + articles_gdelt_ko +
        articles_gdelt_ur + articles_gdelt_fa + articles_gdelt_ja +
        articles_reddit + rss_articles + telegram_articles +
        bluesky_articles
    )

    # Deduplicate by URL — prevents same article scoring multiple times
    seen_urls = set()
    deduped = []
    for a in all_articles:
        url = a.get('url', '') or a.get('link', '')
        # Normalize Google News redirect URLs by their core content
        if 'news.google.com/rss/articles/' in url:
            url = url.split('?')[0]  # strip query params
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(a)
        elif not url:
            deduped.append(a)  # keep articles with no URL rather than drop
    all_articles = deduped

    # Filter soft/cultural noise from community subreddits
    # These subreddits carry country-name articles with zero security signal
    NOISE_SUBREDDITS = {
        'r/afghanistan', 'r/india', 'r/pakistan', 'r/china',
        'r/japan', 'r/korea', 'r/taiwan',
    }
    SECURITY_KEYWORDS_QUICK = {
        'attack', 'strike', 'bomb', 'blast', 'kill', 'dead', 'casualt',
        'military', 'troops', 'missile', 'drone', 'armed', 'conflict',
        'terror', 'militant', 'insurgent', 'war', 'clash', 'skirmish',
        'border', 'arrest', 'detain', 'sanction', 'nuclear', 'weapon',
        'explosion', 'shoot', 'fire', 'troops', 'soldier', 'forces',
    }
    filtered = []
    noise_count = 0
    for a in all_articles:
        src = a.get('source', {})
        src_name = (src.get('name', '') if isinstance(src, dict) else str(src)).lower()
        if src_name in NOISE_SUBREDDITS:
            # Only keep if title/description contains a security keyword
            text = (
                (a.get('title', '') or '') + ' ' +
                (a.get('description', '') or '')
            ).lower()
            if any(kw in text for kw in SECURITY_KEYWORDS_QUICK):
                filtered.append(a)
            else:
                noise_count += 1
        else:
            filtered.append(a)
    if noise_count > 0:
        print(f"[Asia Scan] Filtered {noise_count} soft/cultural noise articles for {target}")
    all_articles = filtered

    # Score
    scoring_result = calculate_threat_probability(all_articles, days, target)
    baseline_adjustment = TARGET_BASELINES.get(target, {}).get('base_adjustment', 0)
    probability = min(99, scoring_result['probability'] + baseline_adjustment)
    momentum = scoring_result['momentum']
    breakdown = scoring_result['breakdown']

    # ── Rhetoric boost ──
    rhetoric_level = _get_rhetoric_level(target)
    rhetoric_boost = RHETORIC_BOOST_TABLE.get(rhetoric_level, 0)
    if rhetoric_boost > 0:
        print(f"[{target}] Rhetoric boost: +{rhetoric_boost} (L{rhetoric_level})")
        probability = min(99, probability + rhetoric_boost)

    # ── Military posture boost ──
    mil_posture, military_boost = _get_military_level(target)
    if military_boost > 0:
        print(f"[{target}] Military boost: +{military_boost} ({mil_posture})")
        probability = min(99, probability + military_boost)

    # Timeline
    if probability < 30:
        timeline = "180+ Days (Low priority)"
    elif probability < 50:
        timeline = "91-180 Days"
    elif probability < 70:
        timeline = "31-90 Days"
    else:
        timeline = "0-30 Days (Elevated threat)"

    if momentum == 'increasing' and probability > 50:
        timeline = "0-30 Days (Elevated threat)"

    # Confidence
    unique_sources = len(set(
        a.get('source', {}).get('name', 'Unknown') if isinstance(a.get('source'), dict)
        else str(a.get('source', 'Unknown'))
        for a in all_articles
    ))
    if len(all_articles) >= 20 and unique_sources >= 8:
        confidence = "High"
    elif len(all_articles) >= 10 and unique_sources >= 5:
        confidence = "Medium"
    else:
        confidence = "Low"

    # Top articles
    top_articles = []
    for contributor in scoring_result.get('top_contributors', []):
        for article in all_articles:
            src = article.get('source', {}).get('name', '') if isinstance(
                article.get('source'), dict) else str(article.get('source', ''))
            if src == contributor['source']:
                top_articles.append({
                    'title': article.get('title', 'No title'),
                    'source': contributor['source'],
                    'url': article.get('url', ''),
                    'publishedAt': article.get('publishedAt', ''),
                    'contribution': contributor['contribution'],
                    'severity': contributor['severity'],
                    'source_weight': contributor['source_weight'],
                    'time_decay': contributor['time_decay'],
                    'deescalation': contributor['deescalation'],
                })
                break

    # Flight disruptions
    flight_disruptions = []
    try:
        flight_disruptions = scan_asian_flight_disruptions(all_articles)
    except Exception as e:
        print(f"Flight disruption scan error: {e}")

    result = {
        'success': True,
        'target': target,
        'region': 'asia',
        'probability': probability,
        'timeline': timeline,
        'confidence': confidence,
        'momentum': momentum,
        'total_articles': len(all_articles),
        'recent_articles_48h': breakdown.get('recent_articles_48h', 0),
        'older_articles': breakdown.get('older_articles', 0),
        'deescalation_count': breakdown.get('deescalation_count', 0),
        'scoring_breakdown': breakdown,
        'top_scoring_articles': top_articles,
        'escalation_keywords': ESCALATION_KEYWORDS,
        'target_keywords': TARGET_KEYWORDS[target]['keywords'],
        'flight_disruptions': flight_disruptions,
        'articles_en': [a for a in all_articles if a.get('language') == 'en'][:20],
        'articles_zh': [a for a in all_articles if a.get('language') == 'zh'][:20],
        'articles_ko': [a for a in all_articles if a.get('language') == 'ko'][:20],
        'articles_ur': [a for a in all_articles if a.get('language') == 'ur'][:20],
        'articles_fa': [a for a in all_articles if a.get('language') == 'fa'][:20],
        'articles_ja': [a for a in all_articles if a.get('language') == 'ja'][:20],
        'articles_reddit': [a for a in all_articles
                            if isinstance(a.get('source'), dict) and
                            a.get('source', {}).get('name', '').startswith('r/')][:20],
        'articles_bluesky': [a for a in all_articles
                             if isinstance(a.get('source'), dict) and
                             a.get('source', {}).get('name', '').startswith('Bluesky @')][:20],
        'articles_telegram': [a for a in all_articles
                              if isinstance(a.get('source'), dict) and
                              a.get('source', {}).get('name', '').startswith('Telegram @')][:20],
        'days_analyzed': days,
        'cached_at': datetime.now(timezone.utc).isoformat(),
        'version': '1.1.0-asia',  # v1.1.0 — Phase A + Phase B fixes applied
    }

    # ============================================
    # v1.1.0 (April 2026) — CRITICAL: Self-caching inside the scan function.
    # Previously, the endpoint's 25s timeout would detach the scan via
    # executor.shutdown(wait=False) — which meant background scans NEVER wrote
    # their results to Redis. Countries like DPRK and Pakistan (multi-language
    # GDELT makes them slow) got stuck in "warming" forever because every scan
    # exceeded 25s and its result was thrown away. Now the scan writes to cache
    # as its FINAL step, regardless of whether the endpoint is still waiting.
    # Endpoint cache-write becomes defensive/idempotent — double-write is safe.
    # ============================================
    try:
        cache_set(f'threat_{target}_{days}d', result)
        save_threat_cache_redis(target, result, days)
        print(f"[{target}] ✓ Scan result self-cached (probability: {probability}%, {len(all_articles)} articles)")
    except Exception as cache_err:
        print(f"[{target}] ⚠️  Self-cache failed: {str(cache_err)[:100]}")

    return result


def _run_notam_scan():
    """Run a full NOTAM scan. Returns the complete response dict."""
    is_fresh, cached = is_notam_cache_fresh()
    if is_fresh and cached:
        cached['cached'] = True
        cached['cache_source'] = 'redis'
        return cached

    print("[NOTAM Scan] Running fresh Asia NOTAM scan from FAA...")
    notams = scan_asia_notams()

    result = {
        'success': True,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'total_notams': len(notams),
        'notams': notams,
        'regions_scanned': list(NOTAM_REGIONS.keys()),
        'data_source': 'FAA NOTAM API',
        'version': '1.0.0-asia',
        'cached': False,
    }

    save_notam_cache_redis(result)
    cache_set('notams', result)
    return result


def _run_flight_scan():
    """Run a full flight disruption scan."""
    is_fresh, cached = is_flight_cache_fresh()
    if is_fresh and cached:
        cached['cached'] = True
        cached['cache_source'] = 'redis'
        return cached

    print("[Flight Scan] Running fresh Asia flight disruption scan...")

    flight_queries = [
        'Asia flight cancelled OR suspended OR grounded Taiwan Strait',
        'airline cancel flights Korea OR Japan OR Taiwan OR China',
        'airspace closed Asia OR Taiwan OR Korea OR Japan',
        'Cathay Pacific OR Japan Airlines OR Korean Air cancel suspend flights',
        'NOTAM airspace restriction Asia Pacific',
        'flight disruption war zone Asia',
        'Taiwan Strait aviation warning OR closed',
        'North Korea missile flight warning Japan Korea',
    ]

    all_articles = []
    for fq in flight_queries:
        try:
            all_articles.extend(fetch_newsapi_articles(fq, days=3))
        except Exception as e:
            print(f"[Asia] Flight query error: {e}")
        try:
            all_articles.extend(fetch_gdelt_articles(fq, days=3, language='eng'))
        except Exception as e:
            print(f"[Asia] Flight GDELT query error: {e}")

    seen_urls = set()
    unique_articles = []
    for a in all_articles:
        url = a.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            unique_articles.append(a)

    disruptions = scan_asian_flight_disruptions(unique_articles)

    result = {
        'success': True,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'total_disruptions': len(disruptions),
        'disruptions': disruptions,
        'cancellations': disruptions,
        'version': '1.0.0-asia',
        'cached': False,
    }

    save_flight_cache_redis(result)
    cache_set('flights', result)
    return result


# ========================================
# API ENDPOINTS
# ========================================

@app.route('/', defaults={'path': ''}, methods=['OPTIONS'])
@app.route('/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Respond to CORS preflight requests."""
    from flask import make_response
    r = make_response('', 204)
    r.headers['Access-Control-Allow-Origin'] = '*'
    r.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    r.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
    r.headers['Access-Control-Max-Age'] = '86400'
    return r

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
    return response

@app.errorhandler(500)
def internal_error(e):
    import traceback
    tb = traceback.format_exc()
    print(f"[500 ERROR] {tb}")
    response = jsonify({'error': 'Internal server error', 'detail': str(e)})
    response.status_code = 500
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
    return response

@app.errorhandler(Exception)
def unhandled_exception(e):
    import traceback
    tb = traceback.format_exc()
    print(f"[UNHANDLED EXCEPTION] {tb}")
    response = jsonify({'error': 'Unhandled exception', 'detail': str(e)})
    response.status_code = 500
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,OPTIONS'
    return response


@app.route('/api/asia/threat/<target>', methods=['GET'])
def api_asia_threat(target):
    """
    Main threat assessment endpoint for Asia-Pacific targets.
    Returns cached data by default. Pass ?force=true to trigger a fresh OSINT scan.
    """
    try:
        force = request.args.get('force', 'false').lower() == 'true'
        days = int(request.args.get('days', 7))

        if target not in TARGET_KEYWORDS:
            return jsonify({
                'success': False,
                'error': f"Invalid target. Must be one of: {', '.join(TARGET_KEYWORDS.keys())}"
            }), 400

        cache_key = f'threat_{target}_{days}d'

        if not force:
            cached = cache_get(cache_key)
            if cached:
                cached['cached'] = True
                cached['cache_source'] = 'memory'
                age = cache_age(cache_key)
                cached['cache_age_seconds'] = int(age) if age else 0
                cached['cache_age_human'] = f"{int(age / 60)}m ago" if age else 'unknown'
                return jsonify(cached)

            is_fresh, redis_cached = is_threat_cache_fresh_redis(target, days)
            if is_fresh and redis_cached:
                redis_cached['cached'] = True
                redis_cached['cache_source'] = 'redis'
                redis_cached['cache_age_human'] = 'from redis'
                cache_set(cache_key, redis_cached)
                return jsonify(redis_cached)

        if not check_rate_limit():
            return jsonify({
                'success': False,
                'error': 'Hourly limit reached. Try again later.',
                'probability': 0,
                'timeline': 'Rate limited',
                'confidence': 'Low',
                'rate_limited': True
            }), 200

        # Run scan with hard 25s timeout — safely under Render's 30s request limit.
        # If scan takes longer, kick it off in background and return cached/placeholder.
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(_run_threat_scan, target, days)
        try:
            response_data = future.result(timeout=25)
            response_data['cached'] = False
            response_data['cache_age_seconds'] = 0
            response_data['cache_age_human'] = 'fresh scan'
            cache_set(cache_key, response_data)
            save_threat_cache_redis(target, response_data, days)
            executor.shutdown(wait=False)
            return jsonify(response_data)
        except FuturesTimeout:
            print(f"[{target}] Scan >25s — returning cached, scan continues in background")
            executor.shutdown(wait=False)
            cached = cache_get(cache_key)
            if cached:
                cached['from_cache'] = True
                cached['scan_in_progress'] = True
                cached['message'] = 'Fresh scan in progress — refresh in 60s for updated data'
                return jsonify(cached)
            _, redis_cached = is_threat_cache_fresh_redis(target, days)
            if redis_cached:
                redis_cached['from_cache'] = True
                redis_cached['scan_in_progress'] = True
                redis_cached['message'] = 'Fresh scan in progress — refresh in 60s for updated data'
                return jsonify(redis_cached)
            return jsonify({
                'success': True,
                'target': target,
                'probability': None,
                'timeline': 'Scan in progress',
                'confidence': 'Low',
                'scan_in_progress': True,
                'warming': True,
                'message': 'Scan in progress — refresh in 60 seconds',
            }), 202

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'probability': 0,
            'timeline': 'Unknown',
            'confidence': 'Low'
        }), 500


@app.route('/api/asia/dashboard', methods=['GET'])
def api_asia_dashboard():
    """
    Single batch endpoint — returns all country scores in one response.
    ALWAYS returns immediately from cache. Never runs live scans on this endpoint.
    Cache is populated by the background refresh thread every 4 hours.
    Pass ?force=true ONLY via the individual /api/asia/threat/<target> endpoints.
    """
    try:
        days = int(request.args.get('days', 7))
        targets = list(TARGET_KEYWORDS.keys())

        dashboard = {
            'success': True,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'version': '1.0.0-asia',
            'countries': {},
            'cache_cold': False
        }

        cold_count = 0

        for target in targets:
            cache_key = f'threat_{target}_{days}d'
            cached = cache_get(cache_key)

            if cached:
                dashboard['countries'][target] = {
                    'probability': cached.get('probability', 0),
                    'momentum': cached.get('momentum', 'stable'),
                    'timeline': cached.get('timeline', 'Unknown'),
                    'confidence': cached.get('confidence', 'Low'),
                    'total_articles': cached.get('total_articles', 0),
                    'flight_disruptions': len(cached.get('flight_disruptions', [])),
                    'cached': True,
                    'cached_at': cached.get('cached_at', None),
                    'cache_age_seconds': int(cache_age(cache_key) or 0)
                }
            else:
                # Try Redis fallback before giving up
                is_fresh, redis_cached = is_threat_cache_fresh_redis(target, days)
                if is_fresh and redis_cached:
                    cache_set(cache_key, redis_cached)  # Warm in-memory from Redis
                    dashboard['countries'][target] = {
                        'probability': redis_cached.get('probability', 0),
                        'momentum': redis_cached.get('momentum', 'stable'),
                        'timeline': redis_cached.get('timeline', 'Unknown'),
                        'confidence': redis_cached.get('confidence', 'Low'),
                        'total_articles': redis_cached.get('total_articles', 0),
                        'flight_disruptions': len(redis_cached.get('flight_disruptions', [])),
                        'cached': True,
                        'cache_source': 'redis',
                        'cached_at': redis_cached.get('cached_at', None),
                        'cache_age_seconds': 0
                    }
                else:
                    # Truly cold — return skeleton, background thread will populate
                    cold_count += 1
                    dashboard['countries'][target] = {
                        'probability': None,
                        'momentum': 'unknown',
                        'timeline': 'Awaiting first scan',
                        'confidence': 'None',
                        'total_articles': 0,
                        'flight_disruptions': 0,
                        'cached': False,
                        'warming': True
                    }

        dashboard['all_cached'] = cold_count == 0
        dashboard['cache_cold'] = cold_count > 0
        dashboard['cold_count'] = cold_count
        return jsonify(dashboard)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/asia/notams', methods=['GET'])
def api_asia_notams():
    """Asia-Pacific NOTAMs endpoint. Redis-cached with ?force=true override."""
    try:
        force = request.args.get('force', 'false').lower() == 'true'

        if not force:
            cached = cache_get('notams')
            if cached:
                cached['cached'] = True
                cached['cache_source'] = 'memory'
                cached['cache_age_seconds'] = int(cache_age('notams') or 0)
                return jsonify(cached)

            is_fresh, redis_cached = is_notam_cache_fresh()
            if is_fresh and redis_cached:
                redis_cached['cached'] = True
                redis_cached['cache_source'] = 'redis'
                cache_set('notams', redis_cached)
                return jsonify(redis_cached)

        if not check_rate_limit():
            return jsonify({'error': 'Rate limit exceeded'}), 429

        data = _run_notam_scan()
        return jsonify(data)

    except Exception as e:
        return jsonify({
            'success': False, 'error': str(e),
            'notams': [], 'total_notams': 0
        }), 500


@app.route('/api/asia/flights', methods=['GET'])
def api_asia_flights():
    """Asia-Pacific flight disruptions endpoint. Redis-cached with ?force=true override."""
    try:
        force = request.args.get('force', 'false').lower() == 'true'

        if not force:
            cached = cache_get('flights')
            if cached:
                cached['cached'] = True
                cached['cache_source'] = 'memory'
                return jsonify(cached)

            is_fresh, redis_cached = is_flight_cache_fresh()
            if is_fresh and redis_cached:
                redis_cached['cached'] = True
                redis_cached['cache_source'] = 'redis'
                cache_set('flights', redis_cached)
                return jsonify(redis_cached)

        if not check_rate_limit():
            return jsonify({'error': 'Rate limit exceeded'}), 429

        data = _run_flight_scan()
        return jsonify(data)

    except Exception as e:
        return jsonify({
            'success': False, 'error': str(e),
            'disruptions': [], 'total_disruptions': 0
        }), 500


@app.route('/api/asia/travel-advisories', methods=['GET'])
def api_asia_travel_advisories():
    """State Dept travel advisories for Asia-Pacific targets."""
    try:
        force = request.args.get('force', 'false').lower() == 'true'

        if not force:
            cached = cache_get('travel_advisories')
            if cached:
                cached['cached'] = True
                return jsonify(cached)

        data = _run_travel_advisory_scan()
        cache_set('travel_advisories', data)
        return jsonify(data)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/asia/cache-status', methods=['GET'])
def api_asia_cache_status():
    """See cache freshness for all endpoints."""
    status = {}
    targets = list(TARGET_KEYWORDS.keys())
    for target in targets:
        key = f'threat_{target}_7d'
        age = cache_age(key)
        status[target] = {
            'cached': age is not None,
            'age_minutes': int(age / 60) if age else None,
            'fresh': age is not None and age < CACHE_TTL,
        }
    return jsonify({
        'success': True,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'cache_ttl_hours': CACHE_TTL / 3600,
        'targets': status,
        'notams': {'cached': cache_get('notams') is not None},
        'flights': {'cached': cache_get('flights') is not None},
    })


@app.route('/rate-limit', methods=['GET'])
def rate_limit_status():
    return jsonify(get_rate_limit_info())


@app.route('/robots.txt')
def robots():
    return "User-agent: *\nDisallow: /api/\n", 200, {'Content-Type': 'text/plain'}


@app.route('/favicon.ico', methods=['GET', 'HEAD'])
def favicon():
    """v1.1.0 — Prevent 500 error spam from browser favicon requests."""
    return '', 204


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'Backend is running',
        'message': 'Asifah Analytics — Asia API v1.0.0',
        'version': '1.0.0',
        'region': 'asia',
        'features': [
            'In-memory response caching (4-hour TTL)',
            'Background refresh thread (auto-refreshes all caches)',
            'Single dashboard endpoint (/api/asia/dashboard)',
            'Force fresh scan with ?force=true',
            'GDELT multilingual: English, Mandarin, Korean, Urdu, Dari, Japanese',
        ],
        'targets': list(TARGET_KEYWORDS.keys()),
        'endpoints': {
            '/api/asia/threat/<target>': 'Get threat assessment (cached, ?force=true for fresh)',
            '/api/asia/dashboard': 'Get all country scores in one call (cached)',
            '/api/asia/notams': 'Get Asia-Pacific NOTAMs (cached, ?force=true for fresh)',
            '/api/asia/flights': 'Get Asia-Pacific flight disruptions (cached)',
            '/api/asia/travel-advisories': 'Get State Dept travel advisories',
            '/api/asia/cache-status': 'See cache freshness for all endpoints',
            '/api/military/posture': 'Full military posture scan (all actors, ?force=true)',
            '/api/military/posture/<target>': 'Military posture for specific target',
            '/rate-limit': 'Get rate limit status',
            '/health': 'Health check',
        }
    })


# ========================================
# MILITARY POSTURE PROXY (v1.0.0 — April 2026)
# ========================================
# Asia backend doesn't scan military posture itself — that's ME's job.
# These endpoints proxy requests to ME backend, which has military_tracker.py
# installed and runs the periodic scans. Benefits:
#   - Single source of truth for military_tracker.py (lives on ME only)
#   - No duplicate scans across backends
#   - No memory pressure on Asia from military scanning
#   - Frontend code is identical regardless of region
# URL path preserved as /api/military/posture/<target> for Asia frontend compat
ME_BACKEND_URL = 'https://asifah-backend.onrender.com'
MILITARY_PROXY_TIMEOUT = 10  # seconds
MILITARY_PROXY_CACHE_TTL = 600  # cache ME responses locally for 10 min
_military_proxy_cache = {}  # {target: (timestamp, data)}


def _military_proxy_safe_default(error_msg=None):
    """Safe-default response when ME is unreachable — keeps frontend from breaking."""
    resp = {
        'alert_level': 'normal',
        'alert_label': 'Normal',
        'alert_color': 'green',
        'military_bonus': 0,
        'show_banner': False,
        'banner_text': '',
        'top_signals': [],
    }
    if error_msg:
        resp['_proxy_error'] = error_msg
    return resp


@app.route('/api/military/posture', methods=['GET', 'OPTIONS'])
def military_posture():
    """Proxy: forward full posture scan request to ME backend."""
    if request.method == 'OPTIONS':
        return '', 200
    try:
        days = int(request.args.get('days', 7))
        force = request.args.get('force', 'false').lower() == 'true'
        me_url = f'{ME_BACKEND_URL}/api/military-posture?days={days}&refresh={force}'
        r = requests.get(me_url, timeout=30)  # longer timeout — full scan
        if r.status_code != 200:
            return jsonify({'error': f'ME backend returned {r.status_code}'}), r.status_code
        return jsonify(r.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/military/posture/<target>', methods=['GET', 'OPTIONS'])
def military_posture_target(target):
    """
    Proxy: forward per-target military posture requests to ME backend.
    Asia caches ME's response briefly to reduce cross-backend traffic.
    """
    if request.method == 'OPTIONS':
        return '', 200

    # Check local proxy cache
    now = time.time()
    cached = _military_proxy_cache.get(target)
    if cached and (now - cached[0] < MILITARY_PROXY_CACHE_TTL):
        resp = dict(cached[1])
        resp['_proxy_cache'] = True
        resp['_proxy_cache_age_s'] = int(now - cached[0])
        return jsonify(resp)

    # Fetch from ME backend
    try:
        me_url = f'{ME_BACKEND_URL}/api/military-posture/{target}'
        r = requests.get(me_url, timeout=MILITARY_PROXY_TIMEOUT)
        if r.status_code != 200:
            print(f"[Military Proxy] {target}: ME returned HTTP {r.status_code}")
            return jsonify(_military_proxy_safe_default(f'ME backend returned {r.status_code}')), 200
        data = r.json()
        _military_proxy_cache[target] = (now, data)
        data['_proxy_cache'] = False
        return jsonify(data)
    except requests.exceptions.Timeout:
        print(f"[Military Proxy] {target}: ME backend timeout")
        return jsonify(_military_proxy_safe_default('ME backend timeout')), 200
    except Exception as e:
        print(f"[Military Proxy] {target}: {str(e)[:100]}")
        return jsonify(_military_proxy_safe_default(str(e)[:100])), 200


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'version': '1.0.0-asia',
        'region': 'asia',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'cache_entries': len(_cache),
        'targets': list(TARGET_KEYWORDS.keys()),
    })


# ========================================
# START BACKGROUND REFRESH ON BOOT
# ========================================
if CHINA_RHETORIC_AVAILABLE:
    register_china_rhetoric_endpoints(app)

if TAIWAN_RHETORIC_AVAILABLE:
    register_taiwan_rhetoric_endpoints(app)

if CHINA_STABILITY_AVAILABLE:
    register_china_stability_endpoints(app)

if CHINA_HUMANITARIAN_AVAILABLE:
    register_china_humanitarian_endpoints(app)

# On Render with gunicorn, this runs once per worker.
start_background_refresh()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
