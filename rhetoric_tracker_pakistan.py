"""
========================================
PAKISTAN RHETORIC TRACKER (v1.0.0 — April 2026)
========================================

Multi-actor architecture for Pakistan, the only nuclear-armed Muslim state
and a structural cross-roads actor: South Asia geographically, ME-aligned
on diplomatic-mediation rhetoric, China-aligned strategically (CPEC), and
GCC-aligned financially.

Pakistan is filed under the ASIA backend but writes cross-theater
fingerprints into the ME, China, and (future) India-axis fingerprint
buses so the GPI's narrative detection layer can use Pakistan as a
hinge actor.

ACTORS (9):
    1. pakistan_army           — COAS / ISPR — the actual power broker
    2. pakistan_civilian_gov   — PM / FO / civilian leadership
    3. pakistan_isi            — Inter-Services Intelligence (shadow actor)
    4. india_pakistan          — Inbound: Modi / MEA / Indian Army on Kashmir/LoC
    5. afghanistan_pakistan    — Inbound: Taliban / TTP / Durand Line
    6. iran_pakistan           — Iran-Pakistan border, Jaish al-Adl, mediation
    7. china_pakistan_axis     — Beijing — CPEC / Gwadar / military sales
    8. gcc_pakistan            — Saudi/UAE/Qatar — financial lifeline + mediation
    9. us_pakistan             — Washington — F-16s, sanctions, counterterror

VECTORS (7 escalation ladders):
    - kashmir_loc_level         — LoC / infiltration / Kashmir status
    - afghan_border_level       — TTP attacks / cross-border strikes / Durand
    - nuclear_doctrine_level    — Missile tests / NCA / Nasr / no-first-use
    - proxy_mediation_level     — Pakistan AS mediator (Iran-US, KSA-Iran)
    - balochistan_insurgency_level — BLA / CPEC site targeting / Gwadar
    - civil_military_friction_level — Imran / PTI / judicial-military
    - economic_stress_level     — IMF / reserves / rupee — bridges to stability

CROSS-THEATER FINGERPRINTS WRITTEN:
    pakistan_iran_active        (read by Iran tracker)
    pakistan_china_active       (read by China tracker)
    pakistan_india_active       (read by future India tracker)
    pakistan_mediating_iran_us  (read by ME BLUF for mediation_substitution)
    pakistan_nuclear_signaling  (read by GPI for nuclear_signaling_global)

CANONICAL SIGNAL EMISSIONS (via build_top_signals in interpreter):
    red_line_breached, kinetic_pressure, theatre_high,
    crosstheater_pakistan_iran, crosstheater_pakistan_china,
    crosstheater_pakistan_india, regime_fracture,
    nuclear_signaling, mediation_active, silence_anomaly
"""

import os
import json
import time
import threading
import requests
import re
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote_plus
from flask import jsonify, request

# Signal interpreter -- So What, Red Lines, Historical Patterns + canonical top_signals
try:
    from pakistan_signal_interpreter import (
        interpret_signals as pakistan_interpret_signals,
        build_top_signals as pakistan_build_top_signals,
    )
    INTERPRETER_AVAILABLE = True
    print("[Pakistan Rhetoric] ✅ Signal interpreter loaded (incl. build_top_signals v1.0)")
except Exception as e:
    import traceback as _tb
    INTERPRETER_AVAILABLE = False
    pakistan_interpret_signals = None
    pakistan_build_top_signals = None
    print(f"[Pakistan Rhetoric] ⚠️ Signal interpreter not available: {e}")
    _tb.print_exc()

# Optional Telegram + Bluesky signal sources
try:
    from telegram_signals_asia import fetch_asia_telegram_signals
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    fetch_asia_telegram_signals = None

try:
    from bluesky_signals_asia import fetch_bluesky_for_target
    BLUESKY_AVAILABLE = True
except ImportError:
    BLUESKY_AVAILABLE = False
    fetch_bluesky_for_target = None


# ============================================
# CONFIG
# ============================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN') or os.environ.get('UPSTASH_REDIS_REST_TOKEN')
NEWSAPI_KEY         = os.environ.get('NEWSAPI_KEY')
BRAVE_API_KEY       = os.environ.get('BRAVE_API_KEY')

RHETORIC_CACHE_KEY    = 'rhetoric:pakistan:latest'
RHETORIC_CACHE_TTL    = 12 * 60 * 60  # 12 hours
CROSSTHEATER_KEY      = 'crosstheater:pakistan:fingerprint'
CROSSTHEATER_TTL      = 14 * 60 * 60  # 14 hours -- read by other trackers

# v2.0 production config
GDELT_BASE_URL        = 'https://api.gdeltproject.org/api/v2/doc/doc'
NEWSAPI_BASE          = 'https://newsapi.org/v2/everything'
BRAVE_API_BASE        = 'https://api.search.brave.com/res/v1/news/search'
REDDIT_USER_AGENT     = 'AsifahAnalytics-Pakistan/1.0 (+https://asifahanalytics.com)'
HISTORY_KEY           = 'rhetoric:pakistan:history'

# Subreddits relevant to Pakistan analysis
PAKISTAN_SUBREDDITS = [
    'pakistan', 'IndiaSpeaks', 'CredibleDefense',
    'geopolitics', 'kashmir', 'afghanistan',
]

# Reporting language discount for inbound actors
REPORTING_LANGUAGE = [
    'reported', 'according to', 'said in a statement',
    'analyst said', 'analysts say', 'experts say',
    'sources said', 'reportedly',
]
REPORTING_ACTORS = {
    'india_pakistan', 'afghanistan_pakistan',
    'iran_pakistan', 'gcc_pakistan',
}

# Premium / high-signal source weights
PREMIUM_SOURCES = [
    'Reuters', 'AP News', 'Associated Press', 'BBC', 'Bloomberg',
    'Financial Times', 'Wall Street Journal', 'The Economist',
    'Dawn', 'The News International', 'Express Tribune', 'Geo News',
    'The Hindu', 'Hindustan Times', 'Indian Express',
    'Al-Monitor', 'Foreign Policy', 'War on the Rocks', 'ISPR',
]
HIGH_SIGNAL_SOURCES = [
    'ARY News', 'Samaa', 'NDTV', 'India Today',
    'Times of India', 'Tribune India',
    'The Diplomat', 'Stimson', 'Brookings', 'Wilson Center',
    'CSIS', 'IISS', 'Carnegie Endowment',
    'Al Jazeera', 'Middle East Eye',
]

# Tripwire phrases — auto-escalate to L4+ on any match
PAKISTAN_TRIPWIRES = [
    'pakistan invades afghanistan',
    'martial law pakistan', 'pakistan coup',
    'pakistan default declared',
    'nasr deployed', 'pakistan nuclear use',
    'india pakistan war',
    'gwadar overrun', 'cpec massacre',
]

# Concurrency / scan locking
_rhetoric_lock    = threading.Lock()
_rhetoric_running = False


# ============================================
# REDIS HELPERS (Upstash REST API)
# ============================================
def _redis_get(key):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        r = requests.get(
            f'{UPSTASH_REDIS_URL}/get/{key}',
            headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'},
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json().get('result')
            if data:
                return json.loads(data)
    except Exception as e:
        print(f'[Pakistan Rhetoric] Redis GET {key} error: {e}')
    return None


def _redis_set(key, value, ttl=RHETORIC_CACHE_TTL):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return False
    try:
        r = requests.post(
            f'{UPSTASH_REDIS_URL}/set/{key}?EX={ttl}',
            headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'},
            data=json.dumps(value),
            timeout=5,
        )
        return r.status_code == 200
    except Exception as e:
        print(f'[Pakistan Rhetoric] Redis SET {key} error: {e}')
        return False


# ============================================
# ACTORS — 9 total
# ============================================
ACTORS = {
    # ── 1. PAKISTAN ARMY (the actual power broker) ──
    'pakistan_army': {
        'name': 'Pakistan Army / COAS',
        'flag': '🇵🇰',
        'icon': '🪖',
        'color': '#16a34a',   # Pakistan green
        'role': 'Strategic Power Broker — COAS / ISPR',
        'description': (
            'The Pakistan Army (Chief of Army Staff and ISPR — Inter-Services '
            'Public Relations) is the actual strategic decision-maker on '
            'national security. Civilian governments come and go; the COAS '
            'sets the doctrine. Watch for ISPR press conferences, COAS '
            'speeches at GHQ Rawalpindi, and corps commander conference '
            'readouts.'
        ),
        'keywords': [
            # COAS / institutional
            'coas', 'chief of army staff', 'ispr',
            'inter-services public relations', 'gen asim munir',
            'general asim munir', 'army chief',
            'ghq rawalpindi', 'corps commander conference',
            'pakistan army statement', 'pakistan military statement',
            # Doctrine signaling
            'full spectrum deterrence', 'pakistan military doctrine',
            'pakistan strategic forces', 'national command authority',
            # Urdu
            'پاک فوج', 'آرمی چیف', 'آئی ایس پی آر',
        ],
        'baseline_statements_per_week': 8,
    },

    # ── 2. PAKISTAN CIVILIAN GOVERNMENT ──
    'pakistan_civilian_gov': {
        'name': 'Pakistan Civilian Government',
        'flag': '🇵🇰',
        'icon': '🏛️',
        'color': '#0ea5e9',
        'role': 'Civilian Leadership — PM / Foreign Office',
        'description': (
            'Prime Minister, Foreign Office (MOFA), Foreign Minister, and '
            'civilian cabinet. Often the public-facing voice but not the '
            'decision-maker on strategic / military matters. Watch for '
            'divergence between civilian rhetoric and Army messaging — '
            'civil-military friction signal.'
        ),
        'keywords': [
            'shehbaz sharif', 'pakistan prime minister',
            'pakistan foreign minister', 'pakistan foreign office',
            'mofa pakistan', 'islamabad statement',
            'pakistan cabinet', 'pakistan pm',
            # Urdu
            'وزیر اعظم پاکستان', 'وزارت خارجہ',
        ],
        'baseline_statements_per_week': 12,
    },

    # ── 3. ISI (shadow actor) ──
    'pakistan_isi': {
        'name': 'Inter-Services Intelligence (ISI)',
        'flag': '🇵🇰',
        'icon': '🕶️',
        'color': '#7c3aed',
        'role': 'Strategic Intelligence — Shadow Actor',
        'description': (
            'Inter-Services Intelligence (ISI) — the dominant intelligence '
            'service. Generally invisible publicly; mentions in OSINT '
            'usually indicate either a major operation, a leak, or '
            'attribution by adversary services (CIA, RAW, NDS). Silence '
            'is normal; presence is significant.'
        ),
        'keywords': [
            'isi', 'inter-services intelligence', 'pakistan intelligence',
            'isi chief', 'dg isi', 'director general isi',
            'isi operation', 'pakistan spy agency',
            # Urdu
            'آئی ایس آئی',
        ],
        'baseline_statements_per_week': 1,  # silence-significance actor
    },

    # ── 4. INDIA → PAKISTAN (inbound) ──
    'india_pakistan': {
        'name': 'India (re: Pakistan)',
        'flag': '🇮🇳',
        'icon': '⚔️',
        'color': '#dc2626',
        'role': 'Adversary — Kashmir / LoC / Indus / Cross-border',
        'description': (
            'Inbound rhetoric from India: Modi government, Ministry of '
            'External Affairs (MEA), Indian Army on Line of Control (LoC) '
            'incidents, Kashmir status, Indus Waters Treaty disputes, and '
            'cross-border counter-terror strikes. Mirror actor for the '
            'future India tracker.'
        ),
        'keywords': [
            # Indian leadership
            'modi pakistan', 'jaishankar pakistan', 'mea india',
            'india pakistan', 'indian army pakistan', 'rajnath singh pakistan',
            # Kashmir / LoC
            'line of control', 'loc kashmir', 'kashmir infiltration',
            'kashmir militants', 'jammu kashmir', 'article 370',
            'kashmir ceasefire', 'kashmir shelling',
            # Indus Waters
            'indus waters treaty', 'indus river dispute',
            # Cross-border
            'india surgical strike', 'balakot', 'pulwama',
            # Hindi / Urdu
            'भारत पाकिस्तान', 'بھارت پاکستان', 'مقبوضہ کشمیر',
        ],
        'baseline_statements_per_week': 6,
    },

    # ── 5. AFGHANISTAN → PAKISTAN (inbound, including TTP) ──
    'afghanistan_pakistan': {
        'name': 'Afghanistan / TTP (re: Pakistan)',
        'flag': '🇦🇫',
        'icon': '🏔️',
        'color': '#f97316',
        'role': 'Inbound Threat — Taliban / TTP / Durand Line',
        'description': (
            'Afghan Taliban government statements on Pakistan, plus the '
            'Tehrik-i-Taliban Pakistan (TTP, the Pakistani Taliban) which '
            'shelters in Afghanistan and conducts cross-border attacks '
            'into KP (Khyber Pakhtunkhwa) and Balochistan. Durand Line '
            'incidents, Afghan refugee tensions, Pakistani airstrikes '
            'inside Afghanistan all flow here.'
        ),
        'keywords': [
            # TTP
            'ttp', 'tehrik-i-taliban pakistan', 'pakistani taliban',
            'ttp attack', 'ttp pakistan', 'noor wali mehsud',
            # Afghan side
            'taliban pakistan', 'kabul pakistan', 'afghanistan pakistan border',
            'durand line', 'afghan refugees pakistan',
            # Pakistani strikes in Afghanistan
            'pakistan strikes afghanistan', 'pakistan airstrike afghan',
            'kp province attack', 'khyber pakhtunkhwa attack',
            # Pashto / Urdu
            'تحریک طالبان پاکستان', 'دیورنډ کرښه',
        ],
        'baseline_statements_per_week': 5,
    },

    # ── 6. IRAN ↔ PAKISTAN (border + mediation) ──
    'iran_pakistan': {
        'name': 'Iran ↔ Pakistan',
        'flag': '🇮🇷',
        'icon': '🤝',
        'color': '#f59e0b',
        'role': 'Border Activity + Mediation Channel',
        'description': (
            'Bidirectional Iran-Pakistan relationship: shared Baloch '
            'insurgent problem (Jaish al-Adl operates in Sistan-Baluchistan, '
            'Iran), 2024 mutual airstrikes precedent, AND Pakistan as '
            'mediator in Iran-US negotiations (the cancelled Witkoff-Kushner '
            'trip in April 2026 was Pakistan-hosted). Dual-axis: threat '
            'AND diplomatic.'
        ),
        'keywords': [
            # Border / insurgent
            'iran pakistan border', 'jaish al-adl', 'jaish ul-adl',
            'sistan-baluchistan', 'iran strikes pakistan',
            'pakistan strikes iran', 'iran-pakistan border incident',
            # Mediation
            'pakistan mediate iran', 'pakistan iran us mediation',
            'witkoff pakistan', 'kushner pakistan',
            'pakistan hosts iran talks', 'islamabad iran us',
            # Farsi / Urdu
            'ایران پاکستان', 'پاکستان میانجی',
        ],
        'baseline_statements_per_week': 3,
    },

    # ── 7. CHINA → PAKISTAN AXIS (CPEC / strategic) ──
    'china_pakistan_axis': {
        'name': 'China → Pakistan (Strategic Partner)',
        'flag': '🇨🇳',
        'icon': '🚇',
        'color': '#dc2626',
        'role': 'External Strategic Partner — CPEC / Gwadar / Military',
        'description': (
            'China-Pakistan Economic Corridor (CPEC), Gwadar deep-sea port, '
            'JF-17 / J-10C fighter sales, satellite launches, and the '
            'broader "all-weather friendship". Watch for CPEC site attacks '
            '(BLA targets Chinese workers), Gwadar militarization signals, '
            'and any China-Pakistan nuclear-cooperation rhetoric.'
        ),
        'keywords': [
            'cpec', 'china pakistan economic corridor',
            'gwadar port', 'gwadar', 'jf-17', 'j-10c',
            'china pakistan', 'beijing islamabad',
            'chinese workers pakistan', 'cpec security',
            'china pakistan all-weather', 'belt road pakistan',
            'pakistan china military', 'pakistan satellite china',
            # Mandarin / Urdu
            '中国巴基斯坦', 'چین پاکستان', 'سی پیک',
        ],
        'baseline_statements_per_week': 4,
    },

    # ── 8. GCC → PAKISTAN (financial lifeline) ──
    'gcc_pakistan': {
        'name': 'GCC → Pakistan (Saudi/UAE/Qatar)',
        'flag': '🇸🇦',
        'icon': '🛢️',
        'color': '#0284c7',
        'role': 'External Patron — Financial Lifeline / Mediation',
        'description': (
            'Gulf Cooperation Council financial support: Saudi loans / '
            'deposits, UAE investments, Qatari LNG. Persistent (unconfirmed) '
            'rumors of Saudi nuclear umbrella arrangement with Pakistan. '
            'GCC-Iran mediation rhetoric also routes here when Pakistan is '
            'involved as an interlocutor.'
        ),
        'keywords': [
            'saudi pakistan', 'saudi arabia pakistan', 'saudi loan pakistan',
            'uae pakistan', 'qatar pakistan',
            'pakistan gcc', 'mbs pakistan',
            'saudi nuclear pakistan', 'saudi pakistan deposit',
            # Arabic / Urdu
            'السعودية باكستان', 'سعودی عرب پاکستان',
        ],
        'baseline_statements_per_week': 3,
    },

    # ── 9. US → PAKISTAN (counterterror / sanctions) ──
    'us_pakistan': {
        'name': 'US → Pakistan',
        'flag': '🇺🇸',
        'icon': '🦅',
        'color': '#3b82f6',
        'role': 'Adversary-Partner — Counterterror / F-16 / Sanctions',
        'description': (
            'United States rhetoric on Pakistan: counterterrorism pressure, '
            'F-16 maintenance program disputes, sanctions tied to nuclear '
            'proliferation history, IMF leverage, and the perpetual '
            '"trust deficit." Trump-era specific: pressure on Pakistan to '
            'host or NOT host Iran-US talks (the cancelled Witkoff trip).'
        ),
        'keywords': [
            'us pakistan', 'state department pakistan', 'pentagon pakistan',
            'centcom pakistan', 'trump pakistan',
            'us sanctions pakistan', 'f-16 pakistan',
            'us imf pakistan', 'state department islamabad',
            'us counterterror pakistan',
            # Trump cancellation specific
            'trump cancels pakistan', 'witkoff pakistan cancelled',
        ],
        'baseline_statements_per_week': 4,
    },
}


# ============================================
# VECTOR ESCALATION LADDERS — 7 total
# ============================================
# Each ladder maps L0 (baseline) → L5 (active conflict / crisis)
# Triggers are matched as substrings (lowercased)

KASHMIR_LOC_TRIGGERS = {
    5: [  # Active war or major incident
        'kashmir war', 'india pakistan war',
        'mass casualty kashmir', 'kashmir strike',
    ],
    4: [  # Heavy exchange of fire / mobilization
        'loc heavy shelling', 'loc casualties', 'loc artillery exchange',
        'kashmir mobilization', 'india pakistan mobilization',
        'troops kashmir border',
    ],
    3: [  # Cross-LoC firing / specific incident
        'loc firing', 'loc ceasefire violation', 'loc shelling',
        'kashmir infiltration claim', 'pakistan crosses loc',
        'india crosses loc',
    ],
    2: [  # Rhetorical escalation
        'kashmir threats', 'kashmir warning', 'india warns pakistan kashmir',
        'pakistan warns india kashmir', 'kashmir martyrs',
    ],
    1: [  # Routine reference
        'kashmir', 'line of control', 'jammu kashmir',
        'azad kashmir', 'kashmir issue',
    ],
}

AFGHAN_BORDER_TRIGGERS = {
    5: [
        'mass casualty ttp attack', 'pakistan invades afghanistan',
        'afghan war pakistan',
    ],
    4: [
        'pakistan airstrike afghanistan', 'pakistan strikes inside afghanistan',
        'major ttp attack', 'kp province massacre',
        'durand line clash', 'afghan taliban pakistan war',
    ],
    3: [
        'ttp attack pakistan', 'tehrik-i-taliban attack',
        'cross-border attack pakistan', 'pakistan border clash',
        'pakistan afghanistan tension',
    ],
    2: [
        'ttp threat', 'ttp warning', 'pakistan warns taliban',
        'durand line tension',
    ],
    1: [
        'ttp', 'durand line', 'afghan refugees pakistan',
        'pakistan afghanistan border',
    ],
}

NUCLEAR_DOCTRINE_TRIGGERS = {
    5: [
        'pakistan nuclear test', 'pakistan nuclear use',
        'nasr deployed', 'tactical nuclear pakistan use',
    ],
    4: [
        'nasr missile test', 'shaheen test',
        'pakistan first use', 'pakistan nuclear threshold',
        'pakistan nuclear doctrine change',
    ],
    3: [
        'pakistan missile test', 'pakistan ballistic test',
        'national command authority meeting',
        'shaheen missile', 'babur missile test',
    ],
    2: [
        'pakistan deterrence', 'full spectrum deterrence',
        'pakistan strategic forces',
    ],
    1: [
        'pakistan nuclear', 'pakistan missile',
        'national command authority', 'nca pakistan',
    ],
}

PROXY_MEDIATION_TRIGGERS = {
    # Pakistan AS mediator — this is a POSITIVE signal but "elevated" tempo
    # (high mediation activity) is itself analytically important
    5: [  # Mediation breakthrough
        'pakistan brokers iran us deal', 'pakistan mediation success',
    ],
    4: [  # Active high-level mediation
        'witkoff islamabad', 'pakistan hosts iran us',
        'kushner islamabad', 'pakistan iran us breakthrough',
    ],
    3: [  # Mediation underway
        'pakistan mediates iran', 'pakistan iran us mediation',
        'islamabad iran talks', 'pakistan envoy iran',
    ],
    2: [
        'pakistan iran channel', 'pakistan diplomatic channel iran',
    ],
    1: [
        'pakistan diplomacy iran', 'pakistan mediator',
    ],
}

BALOCHISTAN_INSURGENCY_TRIGGERS = {
    5: [
        'gwadar overrun', 'cpec major attack',
        'balochistan declares', 'mass casualty balochistan',
    ],
    4: [
        'bla major attack', 'gwadar attack', 'cpec workers killed',
        'chinese workers killed pakistan', 'balochistan offensive',
    ],
    3: [
        'bla attack', 'baloch liberation army attack',
        'cpec security incident', 'balochistan attack',
        'baloch militant attack',
    ],
    2: [
        'bla threat', 'baloch insurgent threat',
        'balochistan unrest',
    ],
    1: [
        'bla', 'baloch liberation army',
        'balochistan insurgency', 'baloch militants',
    ],
}

CIVIL_MILITARY_FRICTION_TRIGGERS = {
    5: [
        'pakistan coup', 'martial law pakistan',
        'army takes over pakistan',
    ],
    4: [
        'pakistan supreme court army', 'judicial military clash',
        'pakistan election crisis', 'pti banned',
    ],
    3: [
        'imran khan jail', 'pti suppression',
        'pakistan election rigging', 'army interferes politics',
    ],
    2: [
        'imran khan trial', 'pti protest',
        'pakistan civil military tension',
    ],
    1: [
        'imran khan', 'pti', 'pakistan tehreek-e-insaf',
    ],
}

ECONOMIC_STRESS_TRIGGERS = {
    5: [
        'pakistan default', 'pakistan sovereign default',
        'pakistan imf collapse', 'rupee collapse',
    ],
    4: [
        'pakistan reserves critical', 'pakistan imf bailout urgent',
        'pakistan default risk', 'rupee crash',
    ],
    3: [
        'pakistan imf talks', 'pakistan reserves low',
        'pakistan economic crisis', 'rupee falls',
        'pakistan inflation crisis',
    ],
    2: [
        'pakistan economy struggling', 'pakistan imf review',
    ],
    1: [
        'pakistan imf', 'pakistan economy',
        'pakistan reserves',
    ],
}


# ============================================
# RED LINES (severity 3 = breach = escalatory)
# ============================================
RED_LINES = [
    {
        'id':    'kashmir_loc_war',
        'label': 'Kashmir LoC Major Exchange',
        'severity': 3,
        'icon':  '🚨',
        'description': (
            'India-Pakistan exchange of fire at LoC reaching mobilization '
            'or casualty thresholds historically associated with the '
            '2019 Balakot crisis or beyond.'
        ),
        'trigger_vectors': ['kashmir_loc_level'],
        'trigger_threshold': 4,
    },
    {
        'id':    'nuclear_doctrine_shift',
        'label': 'Pakistan Nuclear Doctrine Signal',
        'severity': 3,
        'icon':  '☢️',
        'description': (
            'Pakistan signals doctrine change (e.g., abandoning ambiguity, '
            'first-use threshold lowered, NCA emergency convened). '
            'Reads to GPI as nuclear_signaling_global.'
        ),
        'trigger_vectors': ['nuclear_doctrine_level'],
        'trigger_threshold': 4,
    },
    {
        'id':    'cross_border_war',
        'label': 'Pakistan-Afghanistan Cross-Border War',
        'severity': 3,
        'icon':  '⚔️',
        'description': (
            'Pakistan conducts strikes inside Afghanistan beyond '
            'tit-for-tat threshold, OR TTP conducts mass-casualty '
            'attack inside Pakistan triggering full mobilization.'
        ),
        'trigger_vectors': ['afghan_border_level'],
        'trigger_threshold': 4,
    },
    {
        'id':    'cpec_strategic_attack',
        'label': 'CPEC / Gwadar Strategic Attack',
        'severity': 3,
        'icon':  '🚇',
        'description': (
            'BLA conducts major attack on CPEC site, Gwadar port, or '
            'kills significant number of Chinese workers — triggers '
            'Pakistan-China crisis response.'
        ),
        'trigger_vectors': ['balochistan_insurgency_level'],
        'trigger_threshold': 4,
    },
    {
        'id':    'civilian_collapse',
        'label': 'Civilian Government Collapse',
        'severity': 3,
        'icon':  '🏛️',
        'description': (
            'Coup, martial law, or unprecedented judicial-military clash '
            'destabilizing civilian government legitimacy.'
        ),
        'trigger_vectors': ['civil_military_friction_level'],
        'trigger_threshold': 5,
    },
    {
        'id':    'sovereign_default',
        'label': 'Sovereign Default / Reserves Crisis',
        'severity': 3,
        'icon':  '💸',
        'description': (
            'Pakistan defaults on sovereign debt or reserves cross '
            'critical IMF threshold — bridges to stability page.'
        ),
        'trigger_vectors': ['economic_stress_level'],
        'trigger_threshold': 5,
    },
]


# ============================================
# RSS FEEDS (Asia-tier sources, Pakistan-focused)
# ============================================
RHETORIC_RSS_FEEDS = [
    # Pakistani press (English)
    ("https://www.dawn.com/feeds/home", 1.0),
    ("https://www.thenews.com.pk/rss/1/1", 0.95),
    ("https://tribune.com.pk/feed/home", 0.9),
    ("https://www.geo.tv/rss/1/53", 0.9),
    # Indian press (for India-Pakistan view)
    ("https://www.thehindu.com/news/national/feeder/default.rss", 0.85),
    ("https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml", 0.8),
    # ME / Gulf coverage of Pakistan-Iran
    ("https://www.al-monitor.com/rss", 0.85),
    # Western analytical
    ("https://www.ft.com/world?format=rss", 1.0),
    ("https://feeds.reuters.com/Reuters/worldNews", 1.0),
    # Targeted Google News queries
    ("https://news.google.com/rss/search?q=Pakistan+Army+ISPR+COAS+2026&hl=en&gl=US&ceid=US:en", 1.0),
    ("https://news.google.com/rss/search?q=Kashmir+LoC+India+Pakistan+2026&hl=en&gl=US&ceid=US:en", 1.0),
    ("https://news.google.com/rss/search?q=TTP+Pakistan+Afghanistan+border+2026&hl=en&gl=US&ceid=US:en", 1.0),
    ("https://news.google.com/rss/search?q=Pakistan+nuclear+missile+test+2026&hl=en&gl=US&ceid=US:en", 1.0),
    ("https://news.google.com/rss/search?q=Balochistan+BLA+Gwadar+CPEC+2026&hl=en&gl=US&ceid=US:en", 1.0),
    ("https://news.google.com/rss/search?q=Pakistan+IMF+rupee+default+2026&hl=en&gl=US&ceid=US:en", 0.9),
    ("https://news.google.com/rss/search?q=Imran+Khan+PTI+Pakistan+2026&hl=en&gl=US&ceid=US:en", 0.85),
    # Pakistan as mediator (key for mediation_substitution narrative)
    ("https://news.google.com/rss/search?q=Pakistan+mediates+Iran+US+OR+Witkoff+Pakistan+2026&hl=en&gl=US&ceid=US:en", 1.05),
    # CPEC + China-Pakistan
    ("https://news.google.com/rss/search?q=CPEC+China+Pakistan+OR+Gwadar+attack+2026&hl=en&gl=US&ceid=US:en", 1.0),

    # ── Native Urdu RSS feeds (v2.1.0 — Apr 28 2026) ──
    # Direct RSS from Pakistani Urdu publications. URLs taken from Feedspot's
    # Urdu News RSS list. Source-name mapping below classifies these as 'Urdu'
    # so the frontend Urdu tab will populate.
    ("https://www.express.pk/feed/", 0.9),                  # Express News Urdu (largest by reach)
    ("https://urdu.arynews.tv/feed/", 0.9),                 # ARY News Urdu
    ("https://www.bolnews.com/urdu/feed/", 0.85),           # Bol News Urdu
    ("https://www.independenturdu.com/rss.xml", 0.85),      # Independent Urdu (BBC-style analytical)

    # Expanded Google News Urdu queries (was: only پاکستان+فوج)
    ("https://news.google.com/rss/search?q=پاکستان+فوج+2026&hl=ur&gl=PK&ceid=PK:ur", 0.9),
    ("https://news.google.com/rss/search?q=کشمیر+پاکستان+بھارت&hl=ur&gl=PK&ceid=PK:ur", 0.85),
    ("https://news.google.com/rss/search?q=آئی+ایس+پی+آر+بیان&hl=ur&gl=PK&ceid=PK:ur", 0.85),    # ISPR statement
    ("https://news.google.com/rss/search?q=بلوچستان+حملہ&hl=ur&gl=PK&ceid=PK:ur", 0.85),         # Balochistan attack

    # Hindi (for Indian-side perspective, bucketed as 'Regional')
    ("https://news.google.com/rss/search?q=कश्मीर+पाकिस्तान+2026&hl=hi&gl=IN&ceid=IN:hi", 0.85),
]


# ============================================
# RSS / FETCH HELPERS
# ============================================
# (these are new functions to be added before run_pakistan_rhetoric_scan)


def _redis_lpush_trim(key, value, max_len=336):
    """
    Push a snapshot to a Redis list and trim to max_len.
    336 entries = 12h intervals × 24 weeks of history.
    Used for trend tracking / future newsletter feature.
    """
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return
    try:
        payload = json.dumps(value, default=str)
        # Upstash REST: pipeline-style command via JSON body
        requests.post(
            UPSTASH_REDIS_URL,
            headers={
                'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}',
                'Content-Type':  'application/json',
            },
            json=['LPUSH', key, payload],
            timeout=5,
        )
        requests.post(
            UPSTASH_REDIS_URL,
            headers={
                'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}',
                'Content-Type':  'application/json',
            },
            json=['LTRIM', key, 0, max_len - 1],
            timeout=5,
        )
    except Exception as e:
        print(f'[Pakistan Rhetoric] Redis LPUSH error: {str(e)[:80]}')


def _parse_pub_date(pub_str):
    """Robustly parse publication date strings to UTC-aware datetime."""
    if not pub_str:
        return None
    # ISO-8601
    try:
        return datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
    except Exception:
        pass
    # RFC-822 (RSS standard)
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(pub_str).astimezone(timezone.utc)
    except Exception:
        pass
    # Compact GDELT format (YYYYMMDDHHMMSS)
    try:
        clean = pub_str.replace('T', '').replace('Z', '').replace('-', '').replace(':', '').replace(' ', '')
        if len(clean) >= 14:
            return datetime.strptime(clean[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
        if len(clean) == 8:
            return datetime.strptime(clean[:8], '%Y%m%d').replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def _fetch_rss(url, source_name, weight=0.85, max_items=20, language='en'):
    """Fetch and parse an RSS feed using xml.etree.
    Robust to malformed feeds (logs & returns []). Includes 8/15s split timeout
    pattern lesson from project memory.

    v2.1.0: Added `language` parameter (default 'en' preserves existing behavior)
    so native-Urdu feeds tag articles with lang='ur' for the frontend Urdu tab.
    """
    import xml.etree.ElementTree as ET
    articles = []
    try:
        resp = requests.get(
            url, timeout=(8, 15),
            headers={'User-Agent': 'Mozilla/5.0 (compatible; AsifahAnalytics/1.0)'},
        )
        if resp.status_code != 200:
            print(f'[Pakistan RSS] {source_name}: HTTP {resp.status_code}')
            return []
        root = ET.fromstring(resp.content)
        items = root.findall('.//item')
        for item in items[:max_items]:
            title_el = item.find('title')
            link_el  = item.find('link')
            pub_el   = item.find('pubDate')
            desc_el  = item.find('description')
            if title_el is None or not title_el.text:
                continue
            articles.append({
                'title':       (title_el.text or '').strip()[:300],
                'description': ((desc_el.text or title_el.text) or '')[:600] if desc_el is not None else (title_el.text or '')[:600],
                'url':         (link_el.text or '').strip() if link_el is not None and link_el.text else '',
                'publishedAt': pub_el.text if (pub_el is not None and pub_el.text) else '',
                'source':      {'name': source_name},
                'content':     (title_el.text or '').strip()[:600],
                'source_weight_override': weight,
                'language':    language,
            })
        print(f'[Pakistan RSS] {source_name}: {len(articles)} articles')
    except ET.ParseError as e:
        print(f'[Pakistan RSS] {source_name}: XML parse error: {str(e)[:80]}')
    except requests.exceptions.Timeout:
        print(f'[Pakistan RSS] {source_name}: timeout')
    except Exception as e:
        print(f'[Pakistan RSS] {source_name}: {str(e)[:80]}')
    return articles


def _fetch_gdelt(query, language='eng', days=3, max_records=25):
    """
    Fetch from GDELT 2.0 doc API.
    Per project memory: timeout=(5,15), 429 short-circuit, 0.5s polite delay handled by caller.
    """
    articles = []
    try:
        params = {
            'query':      query,
            'mode':       'artlist',
            'maxrecords': max_records,
            'timespan':   f'{days}d',
            'format':     'json',
            'sourcelang': language,
        }
        resp = requests.get(GDELT_BASE_URL, params=params, timeout=(5, 15))
        if resp.status_code == 429:
            print(f'[Pakistan GDELT] {language}: rate-limited (429), short-circuit')
            return []
        if resp.status_code != 200:
            print(f'[Pakistan GDELT] {language}: HTTP {resp.status_code}')
            return []
        lang_map = {'eng': 'en', 'urd': 'ur', 'hin': 'hi', 'ara': 'ar', 'fas': 'fa'}
        for art in resp.json().get('articles', []):
            articles.append({
                'title':       art.get('title', '')[:300],
                'description': art.get('title', '')[:300],
                'url':         art.get('url', ''),
                'publishedAt': art.get('seendate', ''),
                'source':      {'name': art.get('domain', f'GDELT ({language})')},
                'content':     art.get('title', '')[:300],
                'language':    lang_map.get(language, language),
            })
        print(f'[Pakistan GDELT] {language}: {len(articles)} articles')
    except requests.exceptions.Timeout:
        print(f'[Pakistan GDELT] {language}: timeout')
    except Exception as e:
        print(f'[Pakistan GDELT] {language}: {str(e)[:80]}')
    return articles


def _fetch_newsapi(query, language='en', days=3, max_records=20):
    """
    Fetch from NewsAPI.org as fallback when GDELT 429s or returns thin results.
    Free tier limited to 100 req/day — caller should gate this.
    """
    if not NEWSAPI_KEY:
        return []
    articles = []
    try:
        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
        params = {
            'q':         query,
            'from':      from_date,
            'sortBy':    'publishedAt',
            'language':  language,
            'pageSize':  max_records,
            'apiKey':    NEWSAPI_KEY,
        }
        resp = requests.get(NEWSAPI_BASE, params=params, timeout=(5, 15))
        if resp.status_code == 429:
            print(f'[Pakistan NewsAPI] {query[:40]}: rate-limited (429)')
            return []
        if resp.status_code != 200:
            print(f'[Pakistan NewsAPI] {query[:40]}: HTTP {resp.status_code}')
            return []
        for art in resp.json().get('articles', []):
            articles.append({
                'title':       (art.get('title') or '')[:300],
                'description': (art.get('description') or '')[:600],
                'url':         art.get('url', ''),
                'publishedAt': art.get('publishedAt', ''),
                'source':      {'name': (art.get('source') or {}).get('name', 'NewsAPI')},
                'content':     (art.get('content') or art.get('description') or '')[:600],
                'language':    language,
            })
        print(f'[Pakistan NewsAPI] {query[:40]}: {len(articles)} articles')
    except Exception as e:
        print(f'[Pakistan NewsAPI] {query[:40]}: {str(e)[:80]}')
    return articles


def _fetch_brave(query, max_records=15):
    """
    Brave Search News API — tertiary fallback (free tier: 2000 q/mo, 1 q/sec).
    Caller should sleep(1.0) between calls.
    """
    if not BRAVE_API_KEY:
        return []
    articles = []
    try:
        resp = requests.get(
            BRAVE_API_BASE,
            headers={
                'Accept':                       'application/json',
                'Accept-Encoding':              'gzip',
                'X-Subscription-Token':         BRAVE_API_KEY,
            },
            params={'q': query, 'count': max_records, 'freshness': 'pw'},  # past week
            timeout=(5, 15),
        )
        if resp.status_code != 200:
            print(f'[Pakistan Brave] {query[:40]}: HTTP {resp.status_code}')
            return []
        for art in (resp.json().get('results') or []):
            articles.append({
                'title':       (art.get('title') or '')[:300],
                'description': (art.get('description') or '')[:600],
                'url':         art.get('url', ''),
                'publishedAt': art.get('age', '') or art.get('page_age', ''),
                'source':      {'name': (art.get('meta_url') or {}).get('hostname', 'Brave')},
                'content':     (art.get('description') or '')[:600],
                'language':    'en',
            })
        print(f'[Pakistan Brave] {query[:40]}: {len(articles)} articles')
    except Exception as e:
        print(f'[Pakistan Brave] {query[:40]}: {str(e)[:80]}')
    return articles


def _fetch_reddit(subreddits, keywords, days=3, max_per_sub=8):
    """Fetch Pakistan-relevant Reddit posts."""
    articles = []
    since = datetime.now(timezone.utc) - timedelta(days=days)
    for sub in subreddits:
        for kw in keywords[:2]:    # cap to 2 keywords per sub to limit API hits
            try:
                resp = requests.get(
                    f'https://www.reddit.com/r/{sub}/search.json',
                    params={
                        'q':            kw,
                        'sort':         'new',
                        't':            'week',
                        'limit':        max_per_sub,
                        'restrict_sr':  'true',
                    },
                    headers={'User-Agent': REDDIT_USER_AGENT},
                    timeout=(5, 10),
                )
                if resp.status_code == 200:
                    for post in resp.json().get('data', {}).get('children', []):
                        p = post.get('data', {})
                        created  = p.get('created_utc', 0)
                        pub_time = datetime.fromtimestamp(created, tz=timezone.utc)
                        if pub_time >= since:
                            articles.append({
                                'title':       (p.get('title', '') or '')[:200],
                                'description': (p.get('selftext', '') or '')[:400],
                                'url':         f"https://www.reddit.com{p.get('permalink', '')}",
                                'publishedAt': pub_time.isoformat(),
                                'source':      {'name': f'r/{sub}'},
                                'content':     (p.get('selftext', '') or '')[:400],
                                'language':    'en',
                            })
                time.sleep(0.5)
            except Exception as e:
                print(f'[Pakistan Reddit] r/{sub} ({kw}): {str(e)[:60]}')
    print(f'[Pakistan Reddit] {len(articles)} posts across {len(subreddits)} subs')
    return articles


def _get_source_weight(source_name):
    """Return credibility weight for a source. Higher = more trusted."""
    if not source_name:
        return 0.55
    src = source_name.lower()
    if any(p.lower() in src for p in PREMIUM_SOURCES):
        return 1.0
    if any(h.lower() in src for h in HIGH_SIGNAL_SOURCES):
        return 0.85
    if src.startswith('r/'):
        return 0.35
    if 'gdelt' in src:
        return 0.4
    if 'telegram' in src:
        return 0.6
    if 'bluesky' in src:
        return 0.65
    if 'brave' in src:
        return 0.55
    if 'newsapi' in src:
        return 0.6
    return 0.55


# ============================================
# CLASSIFICATION ENGINE
# ============================================

def _score_actor(actor_key, articles):
    """
    Score a single actor against their keyword set.
    Returns dict with level (0-5), statement_count, top_articles, max_level.

    Strategy mirrors China tracker's _score_actor:
      1. Filter articles that mention any actor keyword
      2. Apply time decay (24h: 1.0 / 48h: 0.8 / 72h: 0.6 / >72h: linear decay)
      3. Apply source weight + reporting-language discount (0.4x for inbound actors)
      4. Walk the cross-vector trigger ladders to find article level
      5. Aggregate weighted contributions → normalize to 0-5 level
      6. Tripwire override: any tripwire match auto-escalates to L4+
    """
    actor = ACTORS[actor_key]
    now   = datetime.now(timezone.utc)

    # All vector trigger ladders are relevant — the actor scoring picks up
    # the highest level mentioned in articles ABOUT this actor regardless
    # of which vector the trigger belongs to.
    all_triggers = [
        KASHMIR_LOC_TRIGGERS,
        AFGHAN_BORDER_TRIGGERS,
        NUCLEAR_DOCTRINE_TRIGGERS,
        PROXY_MEDIATION_TRIGGERS,
        BALOCHISTAN_INSURGENCY_TRIGGERS,
        CIVIL_MILITARY_FRICTION_TRIGGERS,
        ECONOMIC_STRESS_TRIGGERS,
    ]

    matched_triggers = []
    top_articles     = []
    weighted_score   = 0.0
    statement_count  = 0
    max_level        = 0

    actor_kws = [kw.lower() for kw in actor.get('keywords', [])]
    if not actor_kws:
        return _empty_actor_result(actor_key, actor)

    for article in articles:
        title   = (article.get('title', '') or '').lower()
        desc    = (article.get('description', '') or '').lower()
        content = (article.get('content', '') or '').lower()
        text    = f'{title} {desc} {content}'

        # Filter: must mention at least one of this actor's keywords
        if not any(kw in text for kw in actor_kws[:25]):
            continue

        # ── Time decay ──
        pub_dt    = _parse_pub_date(article.get('publishedAt', ''))
        age_hours = 48.0
        if pub_dt:
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            age_hours = max(0.1, (now - pub_dt).total_seconds() / 3600)
        if age_hours <= 24:
            decay = 1.0
        elif age_hours <= 48:
            decay = 0.8
        elif age_hours <= 72:
            decay = 0.6
        else:
            decay = max(0.2, 1.0 - (age_hours / 168) * 0.8)

        # ── Source weight ──
        src_weight = article.get(
            'source_weight_override',
            _get_source_weight((article.get('source') or {}).get('name', '')),
        )

        # ── Reporting-language discount for inbound actors ──
        is_reporting = False
        if actor_key in REPORTING_ACTORS:
            if any(rl in text for rl in REPORTING_LANGUAGE):
                is_reporting = True
                src_weight *= 0.4

        # ── Walk vector trigger ladders to find max article level ──
        article_level   = 0
        matched_trigger = None
        # Search L5 → L1 (highest-priority match wins)
        for level in [5, 4, 3, 2, 1]:
            for trigger_dict in all_triggers:
                triggers = trigger_dict.get(level, [])
                for trigger in triggers:
                    if trigger in text:
                        article_level   = level
                        matched_trigger = trigger
                        if trigger not in matched_triggers:
                            matched_triggers.append(trigger)
                        break
                if article_level > 0:
                    break
            if article_level > 0:
                break

        if article_level == 0:
            # Article mentions actor but no escalation trigger — count as L1 baseline statement
            article_level   = 1
            matched_trigger = '(baseline mention)'

        contribution    = article_level * decay * src_weight
        weighted_score += contribution
        statement_count += 1
        max_level       = max(max_level, article_level)

        top_articles.append({
            'title':        (article.get('title', '') or '')[:180],
            'url':          article.get('url', ''),
            'source':       (article.get('source') or {}).get('name', ''),
            'published':    article.get('publishedAt', ''),
            'level':        article_level,
            'language':     article.get('language', 'en'),
            'trigger':      matched_trigger,
            'contribution': round(contribution, 2),
            'is_reporting': is_reporting,
        })

    # ── Normalize weighted score → 0-5 level ──
    if weighted_score == 0:
        level = 0
    elif weighted_score < 3:
        level = 1
    elif weighted_score < 8:
        level = 2
    elif weighted_score < 16:
        level = 3
    elif weighted_score < 28:
        level = 4
    else:
        level = 5

    # ── Tripwire override: any tripwire phrase auto-escalates to L4+ ──
    for tripwire in PAKISTAN_TRIPWIRES:
        for article in articles:
            text = (
                (article.get('title', '') or '') + ' ' +
                (article.get('description', '') or '')
            ).lower()
            if tripwire in text:
                level = max(level, 4)
                if f'TRIPWIRE: {tripwire}' not in matched_triggers:
                    matched_triggers.append(f'TRIPWIRE: {tripwire}')
                print(f'[Pakistan Rhetoric] TRIPWIRE: {actor_key} → {tripwire}')
                break

    top_articles.sort(key=lambda x: x['contribution'], reverse=True)

    return {
        'name':              actor['name'],
        'flag':              actor['flag'],
        'icon':              actor['icon'],
        'color':             actor['color'],
        'role':              actor['role'],
        'escalation_level':  level,
        'max_level':         max_level,
        'statement_count':   statement_count,
        'weighted_score':    round(weighted_score, 2),
        'matched_triggers':  matched_triggers[:10],
        'top_articles':      top_articles[:5],
        'silence_alert':     False,   # set by silence-detection pass
    }


def _empty_actor_result(actor_key, actor):
    """Empty result for actors with no keywords or scoring errors."""
    return {
        'name':              actor['name'],
        'flag':              actor['flag'],
        'icon':              actor['icon'],
        'color':             actor['color'],
        'role':              actor['role'],
        'escalation_level':  0,
        'max_level':         0,
        'statement_count':   0,
        'weighted_score':    0.0,
        'matched_triggers':  [],
        'top_articles':      [],
        'silence_alert':     False,
    }


# ============================================
# VECTOR LADDERING (independent of actor scoring)
# ============================================

def _score_vector_level(articles, trigger_ladder):
    """
    Walk all articles against a single vector's trigger ladder.
    Returns max level matched (0-5) across all articles in the scan window.
    Independent of which actor the article was attributed to.
    """
    max_level = 0
    matched   = []
    for article in articles:
        text = (
            (article.get('title', '') or '') + ' ' +
            (article.get('description', '') or '') + ' ' +
            (article.get('content', '') or '')
        ).lower()
        for level in [5, 4, 3, 2, 1]:
            for trigger in trigger_ladder.get(level, []):
                if trigger in text:
                    if level > max_level:
                        max_level = level
                    matched.append({'level': level, 'trigger': trigger,
                                    'title': (article.get('title', '') or '')[:120]})
                    break
            else:
                continue
            break
        if max_level >= 5:
            break    # can't go higher
    return max_level, matched[:5]


# ============================================
# SILENCE ANOMALY DETECTION
# ============================================

def _detect_silence_anomalies(actor_results, theatre_level, scan_window_days=7):
    """
    Compare each actor's statement_count vs. their baseline_statements_per_week.
    Flag silence when count < 30% of baseline AND theatre level >= 3.

    Special handling:
      - ISI: baseline is 1/week. Silence is the NORMAL state. Only flag
        if rest of theatre is firing (theatre_level >= 4) AND ISI count = 0.
      - Pakistan Army: baseline 8/week. Silence during high tempo is the
        most analytically critical signal — pre-action indicator.
    """
    anomalies = []
    for actor_key, result in actor_results.items():
        actor   = ACTORS.get(actor_key, {})
        baseline = actor.get('baseline_statements_per_week', 5)
        count    = result.get('statement_count', 0)

        # ISI special case
        if actor_key == 'pakistan_isi':
            if theatre_level >= 4 and count == 0:
                result['silence_alert'] = True
                anomalies.append({
                    'actor_id':       actor_key,
                    'actor_name':     actor['name'],
                    'baseline':       baseline,
                    'observed':       count,
                    'theatre_level':  theatre_level,
                    'severity':       'HIGH',
                    'note':           'ISI silence during high theatre tempo — possible operational windup',
                })
            continue

        # Standard silence detection: < 30% of baseline + theatre >= 3
        threshold = max(1, int(baseline * (scan_window_days / 7) * 0.3))
        if theatre_level >= 3 and count < threshold:
            result['silence_alert'] = True
            severity = 'HIGH' if actor_key == 'pakistan_army' else 'MEDIUM'
            anomalies.append({
                'actor_id':       actor_key,
                'actor_name':     actor['name'],
                'baseline':       baseline,
                'observed':       count,
                'theatre_level':  theatre_level,
                'severity':       severity,
                'note':           f'{actor["name"]} below 30% of baseline during theatre L{theatre_level}',
            })

    return anomalies


# ============================================
# THE PRODUCTION SCAN ORCHESTRATOR
# ============================================

def run_pakistan_rhetoric_scan():
    """
    Production-depth Pakistan rhetoric scan.

    Phases:
      1. Multi-source article fetch (RSS + GDELT 4-lang + NewsAPI + Brave + Telegram + Bluesky + Reddit)
      2. Deduplicate by URL
      3. Per-actor classification (9 actors)
      4. Per-vector laddering (7 vectors)
      5. Silence anomaly detection
      6. Composite theatre level + score
      7. Cross-theater fingerprint flags + Redis writes
      8. Interpreter (red lines + so-what + historical patterns)
      9. build_top_signals canonical emission
     10. History snapshot for trend tracking
     11. Cache + return
    """
    print(f"\n[Pakistan Rhetoric] === Starting scan at {datetime.now(timezone.utc).isoformat()} ===")
    scan_start = time.time()

    all_articles = []

    # ================================================================
    # PHASE 1A — RSS FEEDS
    # ================================================================
    for feed_url, weight in RHETORIC_RSS_FEEDS:
        try:
            # v2.1.0 — detect feed language from URL so frontend tabs bucket correctly
            feed_lang = 'en'  # default
            if 'hl=ur' in feed_url or 'urdu' in feed_url.lower() or \
               'express.pk' in feed_url or 'arynews.tv' in feed_url or \
               'bolnews.com/urdu' in feed_url or 'independenturdu' in feed_url:
                feed_lang = 'ur'
            elif 'hl=hi' in feed_url:
                feed_lang = 'hi'
            elif 'thehindu.com' in feed_url or 'hindustantimes' in feed_url:
                feed_lang = 'en'  # English-language Indian press → still 'en' but source name buckets to Regional

            # Derive a friendly source name from URL
            if 'dawn.com' in feed_url:                  sn = 'Dawn'
            elif 'thenews.com.pk' in feed_url:          sn = 'The News International'
            elif 'tribune.com.pk' in feed_url:          sn = 'Express Tribune'
            elif 'geo.tv' in feed_url:                  sn = 'Geo News'
            elif 'thehindu.com' in feed_url:            sn = 'The Hindu'
            elif 'hindustantimes' in feed_url:          sn = 'Hindustan Times'
            elif 'al-monitor' in feed_url:              sn = 'Al-Monitor'
            elif 'ft.com' in feed_url:                  sn = 'Financial Times'
            elif 'reuters.com' in feed_url:             sn = 'Reuters'
            # ── New Urdu feed source-names (v2.1.0) ──
            elif 'express.pk' in feed_url:              sn = 'Express News Urdu'
            elif 'urdu.arynews.tv' in feed_url:         sn = 'ARY News Urdu'
            elif 'bolnews.com/urdu' in feed_url:        sn = 'Bol News Urdu'
            elif 'independenturdu' in feed_url:         sn = 'Independent Urdu'
            elif 'news.google.com' in feed_url and 'hl=ur' in feed_url:
                                                         sn = 'Google News Urdu (PK)'
            elif 'news.google.com' in feed_url and 'hl=hi' in feed_url:
                                                         sn = 'Google News Hindi (IN)'
            elif 'news.google.com' in feed_url:         sn = 'Google News (PK query)'
            else:                                       sn = 'RSS'
            articles = _fetch_rss(feed_url, sn, weight=weight, max_items=20, language=feed_lang)
            all_articles.extend(articles)
            time.sleep(0.3)
        except Exception as e:
            print(f'[Pakistan RSS] feed error: {str(e)[:80]}')

    # ================================================================
    # PHASE 1B — GDELT (English + Urdu + Hindi + Arabic + Farsi)
    # ================================================================
    gdelt_queries = [
        ('Pakistan army OR ISPR OR COAS', 'eng'),
        ('Pakistan Kashmir OR LoC OR India border', 'eng'),
        ('Pakistan TTP OR Afghan border OR Durand', 'eng'),
        ('Pakistan Balochistan OR BLA OR Gwadar OR CPEC', 'eng'),
        ('Pakistan IMF OR rupee OR reserves OR default', 'eng'),
        ('Pakistan Imran Khan OR PTI OR judicial', 'eng'),
        ('Pakistan nuclear OR Nasr OR missile test', 'eng'),
        ('Pakistan mediates Iran OR Witkoff Pakistan', 'eng'),
        # Urdu (v2.1.0 — expanded from 1 → 4 queries to match English depth)
        ('پاکستان فوج', 'urd'),                    # Pakistan army
        ('کشمیر بھارت پاکستان', 'urd'),            # Kashmir India Pakistan
        ('آئی ایس پی آر بیان', 'urd'),             # ISPR statement
        ('بلوچستان حملہ یا دہشت گردی', 'urd'),     # Balochistan attack OR terrorism
        # Hindi
        ('कश्मीर पाकिस्तान', 'hin'),
        # Arabic (GCC coverage)
        ('باكستان', 'ara'),
        # Farsi (Iran-Pakistan border)
        ('پاکستان ایران', 'fas'),
    ]
    gdelt_total = 0
    for query, lang in gdelt_queries:
        try:
            results = _fetch_gdelt(query, language=lang, days=3, max_records=20)
            all_articles.extend(results)
            gdelt_total += len(results)
            time.sleep(0.5)    # politeness delay between GDELT calls
        except Exception as e:
            print(f'[Pakistan GDELT] {lang} error: {str(e)[:60]}')

    # ================================================================
    # PHASE 1C — NewsAPI fallback (gated on GDELT thinness)
    # ================================================================
    if gdelt_total < 20:
        print(f'[Pakistan Rhetoric] GDELT thin ({gdelt_total} articles) — engaging NewsAPI fallback')
        for query, lang in [
            ('Pakistan military OR Imran Khan OR Kashmir', 'en'),
            ('Pakistan Balochistan OR TTP OR Afghan border', 'en'),
            ('Pakistan nuclear OR mediation Iran', 'en'),
        ]:
            try:
                all_articles.extend(_fetch_newsapi(query, language=lang, days=3, max_records=15))
                time.sleep(0.3)
            except Exception as e:
                print(f'[Pakistan NewsAPI] error: {str(e)[:60]}')

    # ================================================================
    # PHASE 1D — Brave Search tertiary fallback
    # ================================================================
    if BRAVE_API_KEY and (gdelt_total + len(all_articles)) < 40:
        print(f'[Pakistan Rhetoric] Engaging Brave fallback')
        for q in [
            'Pakistan ISPR statement',
            'Pakistan Kashmir LoC',
            'Pakistan TTP attack',
            'Pakistan Balochistan BLA',
        ]:
            try:
                all_articles.extend(_fetch_brave(q, max_records=10))
                time.sleep(1.1)    # Brave rate limit: 1/sec
            except Exception as e:
                print(f'[Pakistan Brave] error: {str(e)[:60]}')

    # ================================================================
    # PHASE 1E — Telegram
    # ================================================================
    if TELEGRAM_AVAILABLE and fetch_asia_telegram_signals:
        try:
            tg_msgs = fetch_asia_telegram_signals(hours_back=72, include_extended=True)
            pakistan_kws = [
                'pakistan', 'ispr', 'islamabad', 'kashmir', 'loc',
                'imran khan', 'pti', 'ttp', 'balochistan', 'bla',
                'gwadar', 'cpec', 'rawalpindi', 'durand',
                'پاکستان', 'भारत पाकिस्तान',
            ]
            tg_count = 0
            for msg in (tg_msgs or []):
                text = (msg.get('title', '') or '').lower()
                if any(kw in text for kw in pakistan_kws):
                    all_articles.append({
                        'title':       (msg.get('title', '') or '')[:200],
                        'description': (msg.get('title', '') or '')[:500],
                        'url':         msg.get('url', ''),
                        'publishedAt': msg.get('published', ''),
                        'source':      {'name': msg.get('source', 'Telegram')},
                        'content':     (msg.get('title', '') or '')[:500],
                        'language':    'multi',
                    })
                    tg_count += 1
            print(f'[Pakistan Rhetoric] Telegram: {tg_count} relevant messages')
        except Exception as e:
            print(f'[Pakistan Rhetoric] Telegram error: {str(e)[:80]}')

    # ================================================================
    # PHASE 1F — Bluesky (target='pakistan')
    # ================================================================
    if BLUESKY_AVAILABLE and fetch_bluesky_for_target:
        try:
            bsky = fetch_bluesky_for_target('pakistan', days=7) or []
            for p in bsky:
                all_articles.append({
                    'title':       (p.get('title', '') or '')[:200],
                    'description': (p.get('description', '') or '')[:500],
                    'url':         p.get('url', ''),
                    'publishedAt': p.get('publishedAt', ''),
                    'source':      p.get('source', {'name': 'Bluesky'}),
                    'content':     (p.get('content', '') or '')[:500],
                    'language':    p.get('language', 'en'),
                    'source_weight_override': p.get('source_weight_override', 0.65),
                })
            print(f'[Pakistan Rhetoric] Bluesky: {len(bsky)} posts')
        except Exception as e:
            print(f'[Pakistan Rhetoric] Bluesky error: {str(e)[:80]}')

    # ================================================================
    # PHASE 1G — Reddit
    # ================================================================
    try:
        reddit_kws = [
            'Pakistan army', 'Kashmir LoC',
            'TTP Pakistan', 'Imran Khan', 'CPEC',
        ]
        all_articles.extend(_fetch_reddit(PAKISTAN_SUBREDDITS, reddit_kws, days=3, max_per_sub=6))
    except Exception as e:
        print(f'[Pakistan Reddit] error: {str(e)[:80]}')

    # ================================================================
    # PHASE 2 — Deduplicate by URL
    # ================================================================
    seen_urls = set()
    deduped   = []
    for a in all_articles:
        url = (a.get('url', '') or '').split('?')[0].rstrip('/')
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        deduped.append(a)
    all_articles = deduped
    print(f'[Pakistan Rhetoric] Total articles after dedup: {len(all_articles)}')

    # ================================================================
    # PHASE 3 — Per-actor classification
    # ================================================================
    actor_results = {}
    for actor_key in ACTORS:
        try:
            actor_results[actor_key] = _score_actor(actor_key, all_articles)
            r = actor_results[actor_key]
            print(f'[Pakistan Rhetoric] {actor_key:25} L{r["escalation_level"]} '
                  f'({r["statement_count"]} statements, score {r["weighted_score"]})')
        except Exception as e:
            print(f'[Pakistan Rhetoric] Score error {actor_key}: {str(e)[:80]}')
            actor_results[actor_key] = _empty_actor_result(actor_key, ACTORS[actor_key])

    # ================================================================
    # PHASE 4 — Per-vector laddering
    # ================================================================
    kashmir_lvl,  kashmir_matches  = _score_vector_level(all_articles, KASHMIR_LOC_TRIGGERS)
    afghan_lvl,   afghan_matches   = _score_vector_level(all_articles, AFGHAN_BORDER_TRIGGERS)
    nuclear_lvl,  nuclear_matches  = _score_vector_level(all_articles, NUCLEAR_DOCTRINE_TRIGGERS)
    proxy_lvl,    proxy_matches    = _score_vector_level(all_articles, PROXY_MEDIATION_TRIGGERS)
    baloch_lvl,   baloch_matches   = _score_vector_level(all_articles, BALOCHISTAN_INSURGENCY_TRIGGERS)
    civmil_lvl,   civmil_matches   = _score_vector_level(all_articles, CIVIL_MILITARY_FRICTION_TRIGGERS)
    economic_lvl, economic_matches = _score_vector_level(all_articles, ECONOMIC_STRESS_TRIGGERS)

    print(f'[Pakistan Rhetoric] Vector levels: kashmir L{kashmir_lvl}, '
          f'afghan L{afghan_lvl}, nuclear L{nuclear_lvl}, proxy L{proxy_lvl}, '
          f'baloch L{baloch_lvl}, civmil L{civmil_lvl}, econ L{economic_lvl}')

    # ================================================================
    # PHASE 5 — Composite theatre level + score
    # ================================================================
    vector_levels = [kashmir_lvl, afghan_lvl, nuclear_lvl, proxy_lvl,
                     baloch_lvl, civmil_lvl, economic_lvl]
    theatre_level = max(vector_levels) if vector_levels else 0

    # Score formula: weighted vector sum scaled to 0-100
    # max possible = 7 vectors × 5 = 35; scale to 100
    raw = sum(vector_levels)
    theatre_score = min(100, round(raw * (100 / 35)))

    # ================================================================
    # PHASE 6 — Silence anomaly detection
    # ================================================================
    silence_anomalies = _detect_silence_anomalies(actor_results, theatre_level)
    if silence_anomalies:
        print(f'[Pakistan Rhetoric] Silence anomalies detected: '
              f'{[s["actor_id"] for s in silence_anomalies]}')

    # ================================================================
    # PHASE 7 — Cross-theater fingerprint flags
    # ================================================================
    india_actor = actor_results.get('india_pakistan', {})
    iran_actor  = actor_results.get('iran_pakistan', {})
    china_actor = actor_results.get('china_pakistan_axis', {})

    pakistan_india_active = (
        kashmir_lvl >= 3 or
        india_actor.get('escalation_level', 0) >= 3
    )
    pakistan_iran_active = (
        iran_actor.get('escalation_level', 0) >= 3 or
        proxy_lvl >= 3
    )
    pakistan_china_active = (
        china_actor.get('escalation_level', 0) >= 3 or
        baloch_lvl >= 4    # BLA hits CPEC = China-axis stress
    )
    pakistan_mediating_iran_us = proxy_lvl >= 3
    pakistan_nuclear_signaling = nuclear_lvl >= 3

    # Build top articles list for the page (top 15 across all actors)
    all_top = []
    for r in actor_results.values():
        all_top.extend(r.get('top_articles', []))
    all_top.sort(key=lambda a: a.get('contribution', 0), reverse=True)

    # ================================================================
    # PHASE 8 — Assemble result dict
    # ================================================================
    scan_time = round(time.time() - scan_start, 1)
    result = {
        'success':                          True,
        'generated_at':                     datetime.now(timezone.utc).isoformat(),
        'scanned_at':                       datetime.now(timezone.utc).isoformat(),
        'scan_time_seconds':                scan_time,
        'theatre':                          'pakistan',
        'theatre_score':                    theatre_score,
        'theatre_level':                    theatre_level,
        'rhetoric_score':                   theatre_score,
        # Vector levels (canonical names matching skeleton + frontend expectations)
        'kashmir_loc_level':                kashmir_lvl,
        'afghan_border_level':              afghan_lvl,
        'nuclear_doctrine_level':           nuclear_lvl,
        'proxy_mediation_level':            proxy_lvl,
        'balochistan_insurgency_level':     baloch_lvl,
        'civil_military_friction_level':    civmil_lvl,
        'economic_stress_level':            economic_lvl,
        # Actor block
        'actors':                           actor_results,
        # Article counts + top
        'total_articles':                   len(all_articles),
        'top_articles':                     all_top[:15],
        # Silence
        'silence_anomalies':                silence_anomalies,
        # Cross-theater fingerprints
        'pakistan_iran_active':             pakistan_iran_active,
        'pakistan_china_active':            pakistan_china_active,
        'pakistan_india_active':            pakistan_india_active,
        'pakistan_mediating_iran_us':       pakistan_mediating_iran_us,
        'pakistan_nuclear_signaling':       pakistan_nuclear_signaling,
        # Vector match samples (for analyst debugging)
        'vector_matches': {
            'kashmir_loc':            kashmir_matches,
            'afghan_border':          afghan_matches,
            'nuclear_doctrine':       nuclear_matches,
            'proxy_mediation':        proxy_matches,
            'balochistan_insurgency': baloch_matches,
            'civil_military':         civmil_matches,
            'economic_stress':        economic_matches,
        },
        'version':                          '2.0.0-production',
    }

    # ================================================================
    # PHASE 9 — Run interpreter (red lines + so-what + historical)
    # ================================================================
    if INTERPRETER_AVAILABLE and pakistan_interpret_signals:
        try:
            result['interpretation'] = pakistan_interpret_signals(result)
            print(f'[Pakistan Rhetoric] ✅ Interpreter: '
                  f'{result["interpretation"]["red_lines"]["breached_count"]} red lines breached')
        except Exception as e:
            print(f'[Pakistan Rhetoric] ⚠️ Interpreter error: {str(e)[:120]}')

    # ================================================================
    # PHASE 10 — build_top_signals canonical emission
    # ================================================================
    if pakistan_build_top_signals:
        try:
            result['top_signals'] = pakistan_build_top_signals(result)
            print(f'[Pakistan Rhetoric] ✅ Built {len(result["top_signals"])} top_signals')
        except Exception as e:
            print(f'[Pakistan Rhetoric] ⚠️ build_top_signals error: {str(e)[:120]}')
            result['top_signals'] = []
    else:
        result['top_signals'] = []

    # ================================================================
    # PHASE 11 — Cross-theater fingerprint Redis write
    # ================================================================
    fingerprint = {
        'theatre':                       'pakistan',
        'theatre_level':                 theatre_level,
        'theatre_score':                 theatre_score,
        'kashmir_loc_level':             kashmir_lvl,
        'afghan_border_level':           afghan_lvl,
        'nuclear_doctrine_level':        nuclear_lvl,
        'proxy_mediation_level':         proxy_lvl,
        'balochistan_insurgency_level':  baloch_lvl,
        'civil_military_friction_level': civmil_lvl,
        'economic_stress_level':         economic_lvl,
        'pakistan_iran_active':          pakistan_iran_active,
        'pakistan_china_active':         pakistan_china_active,
        'pakistan_india_active':         pakistan_india_active,
        'pakistan_mediating_iran_us':    pakistan_mediating_iran_us,
        'pakistan_nuclear_signaling':    pakistan_nuclear_signaling,
        'updated_at':                    datetime.now(timezone.utc).isoformat(),
    }
    _redis_set(CROSSTHEATER_KEY, fingerprint, ttl=CROSSTHEATER_TTL)

    # ================================================================
    # PHASE 12 — History snapshot (for newsletter / trend tracking)
    # ================================================================
    try:
        _redis_lpush_trim(HISTORY_KEY, {
            'ts':                         datetime.now(timezone.utc).isoformat(),
            'theatre_level':              theatre_level,
            'theatre_score':              theatre_score,
            'kashmir_loc_level':          kashmir_lvl,
            'afghan_border_level':        afghan_lvl,
            'nuclear_doctrine_level':     nuclear_lvl,
            'proxy_mediation_level':      proxy_lvl,
            'balochistan_insurgency_level': baloch_lvl,
            'civil_military_friction_level': civmil_lvl,
            'economic_stress_level':      economic_lvl,
            'pakistan_iran_active':       pakistan_iran_active,
            'pakistan_china_active':      pakistan_china_active,
            'pakistan_india_active':      pakistan_india_active,
            'pakistan_mediating_iran_us': pakistan_mediating_iran_us,
            'pakistan_nuclear_signaling': pakistan_nuclear_signaling,
            'red_lines_breached':         (result.get('interpretation') or {})
                                              .get('red_lines', {}).get('breached_count', 0),
        })
    except Exception as e:
        print(f'[Pakistan Rhetoric] History snapshot error: {str(e)[:80]}')

    # ================================================================
    # PHASE 13 — Cache + return
    # ================================================================
    _redis_set(RHETORIC_CACHE_KEY, result, ttl=RHETORIC_CACHE_TTL)

    print(f'[Pakistan Rhetoric] ✅ Scan complete in {scan_time}s '
          f'(L{theatre_level}, score {theatre_score}/100, '
          f'{len(all_articles)} articles)')

    return result


# ============================================
# BACKGROUND REFRESH LOOP
# ============================================

def _background_pakistan_scan_loop():
    """
    12h background refresh loop. 90s boot delay to let Render stabilize first.
    Mirrors China tracker's pattern.
    """
    print('[Pakistan Rhetoric] Background thread started (12h cycle)')
    time.sleep(90)    # boot stabilization
    while True:
        try:
            with _rhetoric_lock:
                global _rhetoric_running
                if not _rhetoric_running:
                    _rhetoric_running = True
                    try:
                        run_pakistan_rhetoric_scan()
                    finally:
                        _rhetoric_running = False
        except Exception as e:
            print(f'[Pakistan Rhetoric] Background scan error: {str(e)[:120]}')
        # Sleep 12 hours
        time.sleep(12 * 60 * 60)


def _start_pakistan_background_refresh():
    """Start the background refresh thread. Idempotent."""
    t = threading.Thread(target=_background_pakistan_scan_loop, daemon=True, name='PakistanRhetoricRefresh')
    t.start()
    return t


# ============================================
# FLASK ENDPOINT REGISTRATION
# ============================================
def register_pakistan_rhetoric_endpoints(app):
    """Register Pakistan rhetoric endpoints on the Flask app."""

    @app.route('/api/rhetoric/pakistan', methods=['GET'])
    def api_pakistan_rhetoric():
        """
        Pakistan rhetoric tracker — 9-actor / 7-vector matrix.
        ?force=true to bypass cache and run fresh scan.
        """
        force = request.args.get('force', 'false').lower() == 'true'

        if not force:
            cached = _redis_get(RHETORIC_CACHE_KEY)
            if cached:
                cached['from_cache'] = True
                return jsonify(cached)

        with _rhetoric_lock:
            global _rhetoric_running
            if _rhetoric_running:
                cached = _redis_get(RHETORIC_CACHE_KEY)
                if cached:
                    cached['from_cache']        = True
                    cached['scan_in_progress']  = True
                    return jsonify(cached)
                return jsonify({'success': False, 'error': 'Scan in progress'}), 202
            _rhetoric_running = True

        try:
            result = run_pakistan_rhetoric_scan()
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200]}), 500
        finally:
            with _rhetoric_lock:
                _rhetoric_running = False

    @app.route('/api/rhetoric/pakistan/summary', methods=['GET'])
    def api_pakistan_rhetoric_summary():
        """Lightweight summary — scores and levels only."""
        cached = _redis_get(RHETORIC_CACHE_KEY)
        if not cached:
            return jsonify({'success': False, 'error': 'No cached data'}), 404
        return jsonify({
            'success':                       True,
            'theatre':                       'pakistan',
            'theatre_level':                 cached.get('theatre_level', 0),
            'theatre_score':                 cached.get('theatre_score', 0),
            'kashmir_loc_level':             cached.get('kashmir_loc_level', 0),
            'afghan_border_level':           cached.get('afghan_border_level', 0),
            'nuclear_doctrine_level':        cached.get('nuclear_doctrine_level', 0),
            'proxy_mediation_level':         cached.get('proxy_mediation_level', 0),
            'balochistan_insurgency_level':  cached.get('balochistan_insurgency_level', 0),
            'civil_military_friction_level': cached.get('civil_military_friction_level', 0),
            'economic_stress_level':         cached.get('economic_stress_level', 0),
            'pakistan_iran_active':          cached.get('pakistan_iran_active', False),
            'pakistan_china_active':         cached.get('pakistan_china_active', False),
            'pakistan_india_active':         cached.get('pakistan_india_active', False),
            'pakistan_mediating_iran_us':    cached.get('pakistan_mediating_iran_us', False),
            'pakistan_nuclear_signaling':    cached.get('pakistan_nuclear_signaling', False),
            'generated_at':                  cached.get('generated_at'),
        })

    @app.route('/api/rhetoric/pakistan/history', methods=['GET'])
    def api_pakistan_rhetoric_history():
        """
        Trend history — last N snapshots. Powers future newsletter trends.
        Default returns last 56 snapshots (~28 days at 12h cycle).
        """
        n = min(int(request.args.get('n', 56)), 336)
        if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
            return jsonify({'success': False, 'error': 'Redis not configured'}), 500
        try:
            r = requests.post(
                UPSTASH_REDIS_URL,
                headers={
                    'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}',
                    'Content-Type':  'application/json',
                },
                json=['LRANGE', HISTORY_KEY, 0, n - 1],
                timeout=5,
            )
            raw = r.json().get('result') or []
            snapshots = []
            for entry in raw:
                try:
                    snapshots.append(json.loads(entry))
                except Exception:
                    continue
            return jsonify({
                'success':   True,
                'count':     len(snapshots),
                'snapshots': snapshots,
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200]}), 500

    # ── Start background refresh thread (12h cycle) ──
    _start_pakistan_background_refresh()
    print('[Pakistan Rhetoric] Endpoints registered: '
          '/api/rhetoric/pakistan, /summary, /history')


# ============================================
# STANDALONE ENTRY (for testing)
# ============================================
if __name__ == '__main__':
    print("=" * 60)
    print("PAKISTAN RHETORIC TRACKER — STANDALONE TEST")
    print("=" * 60)
    result = run_pakistan_rhetoric_scan()
    print(f"\n  Theatre level:    L{result['theatre_level']}")
    print(f"  Theatre score:    {result['theatre_score']}/100")
    print(f"  Cross-theater fingerprints:")
    print(f"    pakistan_iran_active:          {result['pakistan_iran_active']}")
    print(f"    pakistan_china_active:         {result['pakistan_china_active']}")
    print(f"    pakistan_india_active:         {result['pakistan_india_active']}")
    print(f"    pakistan_mediating_iran_us:    {result['pakistan_mediating_iran_us']}")
    print(f"    pakistan_nuclear_signaling:    {result['pakistan_nuclear_signaling']}")
