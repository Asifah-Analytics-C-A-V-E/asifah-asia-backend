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
import feedparser
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
    # Pakistani press
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
    # Urdu / Hindi / Pashto
    ("https://news.google.com/rss/search?q=پاکستان+فوج+2026&hl=ur&gl=PK&ceid=PK:ur", 0.9),
    ("https://news.google.com/rss/search?q=कश्मीर+पाकिस्तान+2026&hl=hi&gl=IN&ceid=IN:hi", 0.85),
]


# ============================================
# MAIN SCAN FUNCTION (skeleton — extend with full classifier)
# ============================================
def run_pakistan_rhetoric_scan():
    """
    Run the Pakistan rhetoric scan: fetch articles, classify by actor,
    score vectors, run interpreter, write cross-theater fingerprints,
    cache and return.

    NOTE (v1.0): This is the architectural skeleton. The article-fetch
    and classification logic mirrors the China/Iran/Israel patterns but
    is left as a TODO to keep this file readable. Production version
    should match those trackers' classify_articles() depth.
    """
    print("[Pakistan Rhetoric] Starting scan...")
    scan_start = time.time()

    # ── 1. Initialize result skeleton ──
    result = {
        'success':                          True,
        'generated_at':                     datetime.now(timezone.utc).isoformat(),
        'theatre':                          'pakistan',
        'theatre_score':                    0,
        'theatre_level':                    0,
        # Vector levels
        'kashmir_loc_level':                0,
        'afghan_border_level':              0,
        'nuclear_doctrine_level':           0,
        'proxy_mediation_level':            0,
        'balochistan_insurgency_level':     0,
        'civil_military_friction_level':    0,
        'economic_stress_level':            0,
        # Actor block (skeleton)
        'actors':                           {a: _empty_actor(info)
                                             for a, info in ACTORS.items()},
        # Top articles
        'top_articles':                     [],
        'silence_anomalies':                [],
        'total_articles':                   0,
        'rhetoric_score':                   0,
        # Cross-theater fingerprint flags (filled below)
        'pakistan_iran_active':             False,
        'pakistan_china_active':            False,
        'pakistan_india_active':            False,
        'pakistan_mediating_iran_us':       False,
        'pakistan_nuclear_signaling':       False,
    }

    # ── 2. Fetch + classify (TODO — implement using China tracker pattern) ──
    # See rhetoric_tracker_china.py:classify_articles() for the canonical
    # multi-source aggregation pattern. Will need:
    #   - RSS fetch (RHETORIC_RSS_FEEDS)
    #   - GDELT queries (multi-language: en, ur, hi, ar, fa)
    #   - NewsAPI fallback
    #   - Brave Search fallback
    #   - Telegram (Asia channels — see telegram_signals_asia.py)
    #   - Bluesky (see bluesky_signals_asia.py with target='pakistan')
    #   - Per-actor scoring against ACTORS keyword sets
    #   - Per-vector scoring against trigger ladders
    #   - Silence anomaly detection (compare actor statement_count vs
    #     baseline_statements_per_week)

    # ── 3. Compute composite theatre level (max across all vectors) ──
    vector_levels = [
        result['kashmir_loc_level'],
        result['afghan_border_level'],
        result['nuclear_doctrine_level'],
        result['proxy_mediation_level'],
        result['balochistan_insurgency_level'],
        result['civil_military_friction_level'],
        result['economic_stress_level'],
    ]
    result['theatre_level'] = max(vector_levels) if vector_levels else 0
    # Score: weighted sum (placeholder formula)
    result['theatre_score']   = min(100, sum(vector_levels) * 4)
    result['rhetoric_score']  = result['theatre_score']

    # ── 4. Cross-theater fingerprint flags ──
    # India-axis activity
    india_actor = result['actors'].get('india_pakistan', {})
    result['pakistan_india_active'] = (
        result['kashmir_loc_level'] >= 3 or
        india_actor.get('escalation_level', 0) >= 3
    )
    # Iran-axis (border OR mediation)
    iran_actor = result['actors'].get('iran_pakistan', {})
    result['pakistan_iran_active'] = (
        iran_actor.get('escalation_level', 0) >= 3 or
        result['proxy_mediation_level'] >= 3
    )
    # China-axis (CPEC / strategic)
    china_actor = result['actors'].get('china_pakistan_axis', {})
    result['pakistan_china_active'] = (
        china_actor.get('escalation_level', 0) >= 3 or
        result['balochistan_insurgency_level'] >= 4   # BLA hits CPEC = China-axis stress
    )
    # Mediating Iran-US (specific to mediation_substitution narrative)
    result['pakistan_mediating_iran_us'] = result['proxy_mediation_level'] >= 3
    # Nuclear signaling (read by GPI)
    result['pakistan_nuclear_signaling'] = result['nuclear_doctrine_level'] >= 3

    # ── 5. Run interpreter (red lines, so what, historical) ──
    if INTERPRETER_AVAILABLE and pakistan_interpret_signals:
        try:
            result['interpretation'] = pakistan_interpret_signals(result)
            print(f"[Pakistan Rhetoric] ✅ Interpreter: "
                  f"{result['interpretation']['red_lines']['breached_count']} red lines breached")
        except Exception as e:
            print(f"[Pakistan Rhetoric] ⚠️ Interpreter error (non-fatal): {e}")

    # ── 6. Build canonical top_signals[] for Asia BLUF + GPI ──
    if pakistan_build_top_signals:
        try:
            result['top_signals'] = pakistan_build_top_signals(result)
            print(f"[Pakistan Rhetoric] ✅ Built {len(result['top_signals'])} "
                  f"top_signals for BLUF/GPI")
        except Exception as e:
            print(f"[Pakistan Rhetoric] ⚠️ build_top_signals error: {str(e)[:120]}")
            result['top_signals'] = []
    else:
        result['top_signals'] = []

    # ── 7. Write cross-theater fingerprint to Redis ──
    fingerprint = {
        'theatre':                       'pakistan',
        'theatre_level':                 result['theatre_level'],
        'theatre_score':                 result['theatre_score'],
        'kashmir_loc_level':             result['kashmir_loc_level'],
        'afghan_border_level':           result['afghan_border_level'],
        'nuclear_doctrine_level':        result['nuclear_doctrine_level'],
        'proxy_mediation_level':         result['proxy_mediation_level'],
        'balochistan_insurgency_level':  result['balochistan_insurgency_level'],
        'pakistan_iran_active':          result['pakistan_iran_active'],
        'pakistan_china_active':         result['pakistan_china_active'],
        'pakistan_india_active':         result['pakistan_india_active'],
        'pakistan_mediating_iran_us':    result['pakistan_mediating_iran_us'],
        'pakistan_nuclear_signaling':    result['pakistan_nuclear_signaling'],
        'updated_at':                    datetime.now(timezone.utc).isoformat(),
    }
    _redis_set(CROSSTHEATER_KEY, fingerprint, ttl=CROSSTHEATER_TTL)

    # ── 8. Cache + return ──
    _redis_set(RHETORIC_CACHE_KEY, result, ttl=RHETORIC_CACHE_TTL)

    elapsed = time.time() - scan_start
    print(f"[Pakistan Rhetoric] ✅ Scan complete in {elapsed:.1f}s "
          f"(L{result['theatre_level']}, score {result['theatre_score']}/100)")

    return result


def _empty_actor(info):
    """Empty actor dict for skeleton scan results."""
    return {
        'name':              info['name'],
        'flag':              info['flag'],
        'icon':              info['icon'],
        'color':             info['color'],
        'role':              info['role'],
        'statement_count':   0,
        'escalation_level':  0,
        'max_level':         0,
        'top_articles':      [],
        'silence_alert':     False,
    }


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
