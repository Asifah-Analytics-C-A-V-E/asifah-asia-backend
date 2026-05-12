"""
Asifah Analytics — India Rhetoric & Coercion Tracker
v1.0.0 — May 2026

ANALYTICAL FRAME (this is the question this tracker answers):
==============================================================

  "Is India absorbing external pressure (economic, kinetic, diplomatic)
   without losing internal cohesion — and how is that absorption shaping
   its external posture?"

India is the platform's FIRST absorber-class tracker. This is a structural
departure from China (command-node, asks "will China take Taiwan?") and Iran
(command-node, asks "is Iran moving kinetic?"). India is downstream of the
command nodes — it ABSORBS pressure rather than originating it. The tracker
is built around this asymmetry.

THE THREE-DASHBOARD MODEL:
==========================

  OUTBOUND — "India's external posture signaling"
    Tracks: PMO/Modi rhetoric, MEA/Jaishankar foreign policy positioning,
            Armed Forces LAC/LoC/naval signaling, Economic Statecraft
            (RBI, MoF) outbound monetary diplomacy, Hindutva non-state
            ideological projection.

  INBOUND — "Pressure absorption signals from upstream theaters"
    Tracks: Pakistan LoC/Kashmir escalations, China LAC pressure, China
            tech/economic coercion, Iran/Hormuz oil pricing reverberations,
            US tariff/H-1B/Khalistan friction. Read from cross-theater
            fingerprints written by Iran, China, Pakistan, US trackers.

  INTERNAL — "Cohesion under absorption"
    Tracks: Opposition (INDIA bloc — Rahul Gandhi, Kharge, Mamata, Stalin)
            rhetorical posture (attacking vs aligned with government),
            communal/minority-stress signals, Hindutva ideological actor
            volatility (RSS, VHP, Bajrang Dal), regional federal friction.
            This is India's UNIQUE structural addition — China's CCP is
            rhetorically monolithic; India's chaotic democracy is its
            absorption-resilience analytical strength.

CHANGELOG:
==========
  v1.0.0 (2026-05-12): Initial build — three-dashboard absorber-node tracker.
                       Patches 1-3 (scaffold + actors + sources)
                       Patch 4    (trigger ladders + detection + scoring +
                                  own_signals builder for absorption proxy)

COPYRIGHT 2025-2026 Asifah Analytics. All rights reserved.
"""

import os
import json
import threading
import time
import requests
import xml.etree.ElementTree as ET
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from flask import jsonify, request


# ============================================================================
# CONFIG
# ============================================================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN') or os.environ.get('UPSTASH_REDIS_REST_TOKEN')
NEWSAPI_KEY         = os.environ.get('NEWSAPI_KEY')
BRAVE_API_KEY       = os.environ.get('BRAVE_API_KEY')
GDELT_BASE_URL      = 'https://api.gdeltproject.org/api/v2/doc/doc'

try:
    from telegram_signals_asia import fetch_asia_telegram_signals
    TELEGRAM_AVAILABLE = True
    print("[India Rhetoric] Telegram signals available")
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[India Rhetoric] Telegram signals not available — RSS/GDELT only")

try:
    from absorption_proxy_asia import detect_and_persist_via_proxy as detect_absorption_and_persist
    ABSORPTION_DETECTOR_AVAILABLE = True
    print("[India Rhetoric] ✅ Absorption proxy available (routes through ME backend)")
except ImportError:
    ABSORPTION_DETECTOR_AVAILABLE = False
    print("[India Rhetoric] ⚠️ Absorption proxy not importable — skipping Butterfly write")

RHETORIC_CACHE_KEY        = 'rhetoric:india:latest'
RHETORIC_CACHE_KEY_LEGACY = 'india_rhetoric_cache'
HISTORY_KEY               = 'rhetoric:india:history'
BASELINE_KEY              = 'rhetoric_baseline:india'

# Cross-theater key conventions — India writes to BOTH for max compatibility
CROSSTHEATER_SHARED_KEY   = 'rhetoric:crosstheater:fingerprints'
CROSSTHEATER_INDIA_KEY    = 'fingerprint:india:current'

# Cross-theater key conventions — India READS from each upstream's home key
UPSTREAM_KEYS = {
    'iran':     ('shared',   'iran'),
    'china':    ('shared',   'china'),
    'pakistan': ('direct',   'crosstheater:pakistan:fingerprint'),
    'us':       ('direct',   'fingerprint:us:current'),
}

RHETORIC_CACHE_TTL  = 6 * 3600
SCAN_INTERVAL_HOURS = 6
HISTORY_MAX_ENTRIES = 336

_rhetoric_running = False
_rhetoric_lock    = threading.Lock()


# ============================================================================
# ESCALATION LEVELS  (canonical 0–5 scale)
# ============================================================================
ESCALATION_LEVELS = {
    0: {'label': 'Baseline',         'color': '#6b7280',
        'description': 'Routine statements, no significant absorption signals'},
    1: {'label': 'Rhetoric',         'color': '#3b82f6',
        'description': 'Standard policy positioning, baseline cohesion'},
    2: {'label': 'Warning',          'color': '#f59e0b',
        'description': 'Elevated rhetoric on Pakistan/China/Khalistan; minor absorption flagged'},
    3: {'label': 'Confrontation',    'color': '#f97316',
        'description': 'Named adversary signaling, active absorption, opposition attacks rising'},
    4: {'label': 'Coercion',         'color': '#ef4444',
        'description': 'Multi-axis absorption converging, communal/cohesion stress'},
    5: {'label': 'Active Crisis',    'color': '#dc2626',
        'description': 'Kinetic/BoP-class: LoC/LAC clash, formal duty measures, communal violence at scale'},
}


DASHBOARDS = ('outbound', 'inbound', 'internal')


# ============================================================================
# ACTORS  (7 clusters)
# ============================================================================
ACTORS = {

    'pmo': {
        'name': 'PMO / Modi / BJP Leadership',
        'flag': '🇮🇳',
        'icon': '🏛️',
        'color': '#f97316',
        'dashboards': ['outbound', 'internal'],
        'weight': 3.5,
        'role': 'Apex Political Signaling',
        'description': (
            'Modi himself + BJP party machinery + PMO India official voice. '
            'Highest-value rhetoric in the tracker. Modi-class jawboning '
            '(e.g., May 2026 gold call) writes directly into absorption layer.'
        ),
        'keywords': [
            'narendra modi', 'pm modi', 'prime minister modi', 'modi ji',
            'modi says', 'modi warns', 'modi addresses', 'modi tells',
            'modi calls on', 'modi urges', 'modi appeals',
            'mann ki baat', 'modi mann ki baat', 'pmo india',
            'modi rally', 'modi speech', 'modi independence day',
            'modi red fort', 'modi parliament',
            'avoid buying gold', 'suspend gold purchases', 'cut gold imports',
            'foreign travel', 'discretionary imports', 'aatmanirbhar',
            'self-reliance', 'self reliance', 'vocal for local', 'make in india',
            'bjp president', 'bjp leader', 'bharatiya janata party',
            'amit shah', 'jp nadda', 'home minister shah',
            'bjp rally', 'bjp manifesto',
            'मोदी', 'प्रधानमंत्री', 'भाजपा', 'मन की बात',
            'مودی', 'وزیر اعظم', 'بھارتیہ جنتا پارٹی',
        ],
        'baseline_statements_per_week': 12,
        'tripwires': [
            'modi addresses nation emergency',
            'modi announces gold import duty',
            'modi suspends foreign visits',
            'modi declares national security threat',
        ],
    },

    'mea': {
        'name': 'MEA / Jaishankar / Ambassadors',
        'flag': '🇮🇳',
        'icon': '🌐',
        'color': '#0ea5e9',
        'dashboards': ['outbound'],
        'weight': 3.0,
        'role': 'Foreign Policy Doctrine Voice',
        'description': (
            'External Affairs Ministry rhetoric architect. Jaishankar is the '
            'public voice of "strategic autonomy" doctrine. MEA spokesperson '
            'briefings and senior ambassador statements round out the cluster.'
        ),
        'keywords': [
            's jaishankar', 'jaishankar', 'eam jaishankar',
            'external affairs minister', 'minister of external affairs',
            'mea spokesperson', 'arindam bagchi', 'randhir jaiswal',
            'ministry of external affairs', 'south block',
            'strategic autonomy', 'multipolar', 'multi-alignment',
            'civilisational state', 'civilizational state',
            'global south', 'voice of global south',
            'india first', 'national interest', 'realpolitik',
            'india china talks', 'india pakistan talks', 'india us talks',
            'india russia', 'india iran', 'india israel',
            'sushma swaraj bhavan', 'raisina dialogue',
            'विदेश मंत्री', 'जयशंकर', 'विदेश मंत्रालय',
            'وزیر خارجہ', 'جے شنکر', 'وزارت خارجہ',
        ],
        'baseline_statements_per_week': 8,
        'tripwires': [
            'india recalls ambassador',
            'mea summons envoy',
            'india suspends bilateral mechanism',
            'india expels diplomats',
        ],
    },

    'armed_forces': {
        'name': 'Armed Forces / CDS / Service Chiefs',
        'flag': '🇮🇳',
        'icon': '🎖️',
        'color': '#a855f7',
        'dashboards': ['outbound', 'inbound'],
        'weight': 2.5,
        'role': 'Military Posture & Operational Signaling',
        'description': (
            'CDS Anil Chauhan, three service chiefs, Northern/Eastern Commands '
            '(LAC + LoC), Naval Fleets, Andaman & Nicobar Command. '
            'LAC and LoC tactical statements are the primary signal class.'
        ),
        'keywords': [
            'chief of defence staff', 'cds anil chauhan', 'cds chauhan',
            'army chief', 'navy chief', 'air chief marshal',
            'general manoj pande', 'admiral hari kumar', 'chief of naval staff',
            'iaf chief',
            'northern command', 'eastern command', 'western command',
            'southern command', 'training command',
            'andaman nicobar command', 'tri-services command',
            'eastern naval command', 'western naval command',
            'ins vikrant', 'ins vikramaditya',
            'lac', 'line of actual control', 'galwan', 'depsang', 'demchok',
            'tawang', 'arunachal', 'ladakh', 'siachen',
            'loc', 'line of control', 'uri', 'pathankot', 'pulwama',
            'cross-border', 'surgical strike', 'pre-emptive',
            'forward posture', 'mobilization', 'mobilisation',
            'integrated theatre command', 'jointness',
            'rafale', 's-400', 'tejas', 'brahmos',
            'सेनाध्यक्ष', 'थलसेना', 'वायुसेना', 'नौसेना', 'नियंत्रण रेखा',
            'فوج کے سربراہ', 'لائن آف کنٹرول', 'فوجی',
        ],
        'baseline_statements_per_week': 6,
        'tripwires': [
            'lac forward troop movement',
            'loc ceasefire violation cluster',
            'army moves troops to forward positions',
            'naval task force deployed',
            'india strikes across loc',
        ],
    },

    'economic_statecraft': {
        'name': 'MoF / RBI / Commerce / Petroleum',
        'flag': '🇮🇳',
        'icon': '🪙',
        'color': '#eab308',
        'dashboards': ['outbound', 'inbound'],
        'weight': 2.0,
        'role': 'Monetary & Trade Statecraft',
        'description': (
            'Finance Minister Sitharaman, RBI Governor, Commerce Minister '
            'Goyal, Petroleum Minister Puri. Bridges to the commodity tracker — '
            'every signal here is a candidate input to absorption_detector.'
        ),
        'keywords': [
            'nirmala sitharaman', 'finance minister sitharaman',
            'sitharaman budget', 'sitharaman parliament', 'finance ministry',
            'shaktikanta das', 'rbi governor', 'reserve bank of india',
            'rbi monetary policy', 'mpc', 'monetary policy committee',
            'rbi intervention', 'rbi gold reserves',
            'piyush goyal', 'commerce minister goyal',
            'hardeep puri', 'petroleum minister puri', 'oil minister puri',
            'forex reserves', 'foreign exchange reserves', 'fx reserves',
            'rupee internationalization', 'rupee trade', 'rupee invoicing',
            'oil import diversification', 'energy security',
            'brics payments', 'brics pay', 'mbridge',
            'import duty', 'tariff', 'export duty', 'safeguard duty',
            'aatmanirbhar bharat', 'production linked incentive',
            'pli scheme',
            'सीतारमण', 'वित्त मंत्री', 'भारतीय रिजर्व बैंक', 'विदेशी मुद्रा भंडार',
            'سیتارمن', 'وزیر خزانہ', 'ریزرو بینک', 'زر مبادلہ',
        ],
        'baseline_statements_per_week': 7,
        'tripwires': [
            'rbi raises rates emergency',
            'gold import duty hike announced',
            'forex reserves drop below 580 billion',
            'capital controls signaled',
            'rupee record low',
        ],
    },

    'opposition': {
        'name': 'Congress / INDIA Bloc Opposition',
        'flag': '🇮🇳',
        'icon': '⚖️',
        'color': '#3b82f6',
        'dashboards': ['internal'],
        'weight': 1.5,
        'role': 'Internal Cohesion Proxy (inverse-scored)',
        'description': (
            'Rahul Gandhi, Mallikarjun Kharge, Mamata Banerjee, MK Stalin, '
            'Akhilesh Yadav, Tejashwi Yadav. When this cluster goes loud on '
            'FX/unemployment/communal/Manipur → cohesion stress. When quiet '
            'or aligned post-attack → cohesion strong. INVERSE SCORED.'
        ),
        'keywords': [
            'rahul gandhi', 'mallikarjun kharge', 'congress president kharge',
            'sonia gandhi', 'priyanka gandhi', 'inc president',
            'indian national congress', 'congress party',
            'india bloc', 'i.n.d.i.a alliance', 'opposition alliance',
            'mamata banerjee', 'trinamool congress', 'tmc bengal',
            'mk stalin', 'dmk tamil nadu', 'dmk chief',
            'akhilesh yadav', 'samajwadi party', 'sp uttar pradesh',
            'tejashwi yadav', 'rjd bihar',
            'revanth reddy', 'congress telangana',
            'aap kejriwal', 'arvind kejriwal',
            'modi government failure', 'bjp failure',
            'unemployment crisis', 'economic mismanagement',
            'attack on democracy', 'institutional capture',
            'manipur', 'manipur violence', 'gyanvapi', 'love jihad',
            'inflation modi', 'rupee fall',
            'electoral bonds', 'pegasus',
            'राहुल गांधी', 'कांग्रेस', 'विपक्ष', 'ममता बनर्जी',
            'راہول گاندھی', 'کانگریس', 'حزب اختلاف',
        ],
        'baseline_statements_per_week': 10,
        'tripwires': [
            'no-confidence motion filed',
            'opposition walkout sustained',
            'opposition unified statement on emergency',
            'opposition demands prime minister resignation',
        ],
    },

    'hindutva_ideological': {
        'name': 'RSS / VHP / Saffron Voices',
        'flag': '🇮🇳',
        'icon': '🕉️',
        'color': '#dc2626',
        'dashboards': ['internal'],
        'weight': 1.5,
        'role': 'Non-state Ideological Vector',
        'description': (
            'RSS (Mohan Bhagwat), VHP, Bajrang Dal, prominent saffron voices, '
            'Yogi Adityanath when speaking ideologically. Tracks Hindutva '
            'projection, minority-stress rhetoric, communal flashpoints.'
        ),
        'keywords': [
            'mohan bhagwat', 'rss chief', 'rashtriya swayamsevak sangh',
            'sarsanghchalak', 'rss vijayadashami',
            'sangh parivar', 'pracharak',
            'vishwa hindu parishad', 'vhp', 'bajrang dal',
            'hindu jagran manch',
            'yogi adityanath', 'cm yogi', 'up chief minister',
            'ajay singh bisht',
            'hindutva', 'hindu rashtra', 'sanatan dharma',
            'love jihad', 'land jihad', 'urban naxal',
            'gyanvapi', 'kashi vishwanath', 'mathura',
            'ayodhya', 'ram mandir', 'pran pratishtha',
            'cow vigilante', 'gau rakshak',
            'ghar wapsi', 'religious conversion',
            'uniform civil code', 'ucc',
            'मोहन भागवत', 'राष्ट्रीय स्वयंसेवक संघ', 'हिंदुत्व',
            'विश्व हिंदू परिषद', 'बजरंग दल',
            'موہن بھاگوت', 'آر ایس ایس', 'ہندوتوا',
        ],
        'baseline_statements_per_week': 8,
        'tripwires': [
            'rss chief major doctrinal speech',
            'temple mosque flashpoint violence',
            'mass communal incident',
            'bhagwat names specific country',
        ],
    },

    'adversary_crossreads': {
        'name': 'Adversary Voices on India',
        'flag': '🌐',
        'icon': '📡',
        'color': '#7c3aed',
        'dashboards': ['inbound'],
        'weight': 2.0,
        'role': 'Bidirectional Inbound Pressure',
        'description': (
            'Pakistan PM/army/MOFA, China MFA/PLA/Global Times, '
            'Khalistan actors abroad (SFJ Pannun), US officials making '
            'India-targeted statements (tariffs, H-1B, Khalistan indictments).'
        ),
        'keywords': [
            'pakistan army', 'asim munir', 'general munir',
            'shehbaz sharif on india', 'bilawal bhutto on india',
            'isi', 'ispr', 'gen syed asim munir',
            'pakistan mofa india', 'islamabad warns india',
            'china mfa india', 'mao ning india', 'lin jian india',
            'global times india', 'china daily india',
            'wang yi india', 'pla western theater',
            'zangnan', 'south tibet',
            'khalistan', 'sikhs for justice', 'sfj', 'gurpatwant singh pannun',
            'nijjar', 'hardeep singh nijjar', 'amritpal singh',
            'referendum 2020',
            'trump tariff india', 'trump h-1b', 'trump h1b',
            'tariff india', 'us sanctions india', 'state department india',
            'us trade representative india',
            'पाकिस्तान फौज', 'चीन ने कहा', 'खालिस्तान',
            'پاکستانی فوج', 'عاصم منیر', 'بلاول بھٹو',
        ],
        'baseline_statements_per_week': 9,
        'tripwires': [
            'pakistan nuclear signaling toward india',
            'china names indian territorial claim',
            'khalistan actor assassination',
            'us imposes tariff on indian sector',
            'china pla mobilizes lac',
        ],
    },
}


# ============================================================================
# SOURCES — RSS feeds, Reddit subs, GDELT queries, Brave queries
# ============================================================================

RSS_FEEDS = [
    {'url': 'https://www.thehindu.com/news/feeder/default.rss',
     'source': 'The Hindu', 'weight': 0.95, 'language': 'en'},
    {'url': 'https://www.thehindu.com/news/national/feeder/default.rss',
     'source': 'The Hindu — National', 'weight': 0.95, 'language': 'en'},
    {'url': 'https://www.thehindu.com/business/feeder/default.rss',
     'source': 'The Hindu — Business', 'weight': 0.95, 'language': 'en'},
    {'url': 'https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml',
     'source': 'Hindustan Times', 'weight': 0.90, 'language': 'en'},
    {'url': 'https://indianexpress.com/section/india/feed/',
     'source': 'Indian Express', 'weight': 0.92, 'language': 'en'},
    {'url': 'https://www.livemint.com/rss/news',
     'source': 'Mint', 'weight': 0.92, 'language': 'en'},
    {'url': 'https://www.business-standard.com/rss/home_page_top_stories.rss',
     'source': 'Business Standard', 'weight': 0.90, 'language': 'en'},
    {'url': 'https://feeds.feedburner.com/ndtvnews-india-news',
     'source': 'NDTV', 'weight': 0.85, 'language': 'en'},
    {'url': 'https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms',
     'source': 'Times of India', 'weight': 0.75, 'language': 'en'},
    {'url': 'https://thewire.in/rss',
     'source': 'The Wire', 'weight': 0.85, 'language': 'en'},
    {'url': 'https://theprint.in/feed/',
     'source': 'The Print', 'weight': 0.85, 'language': 'en'},
    {'url': 'https://scroll.in/feed.xml',
     'source': 'Scroll', 'weight': 0.80, 'language': 'en'},
    {'url': 'https://www.reuters.com/world/india/rss',
     'source': 'Reuters India', 'weight': 0.98, 'language': 'en'},
    {'url': 'https://www.indiatoday.in/rss/home',
     'source': 'India Today', 'weight': 0.80, 'language': 'en'},
    {'url': 'https://idsa.in/rss/idsa-comments',
     'source': 'IDSA', 'weight': 0.90, 'language': 'en'},
    {'url': 'https://www.orfonline.org/feed/',
     'source': 'ORF', 'weight': 0.92, 'language': 'en'},
    {'url': 'https://carnegieindia.org/rss/all',
     'source': 'Carnegie India', 'weight': 0.92, 'language': 'en'},
]


REDDIT_SUBREDDITS = [
    'india', 'IndiaSpeaks', 'IndianModerate', 'librandu',
    'IndianEconomy', 'IndianDefense', 'IndianDefence',
    'IndianHistory', 'unitedstatesofindia',
    'Kashmir', 'pakistan', 'china',
    'geopolitics', 'CredibleDefense', 'LessCredibleDefence',
    'IndiaInvestments',
]


GDELT_QUERIES = {
    'en': [
        '(india OR modi OR jaishankar) AND (china OR pakistan OR taiwan OR kashmir)',
        '(india OR rbi) AND (rupee OR gold OR oil OR import OR forex)',
        '(india OR khalistan) AND (canada OR pannun OR diaspora)',
        '(modi OR bjp) AND (rss OR hindutva OR manipur OR ayodhya)',
        '(india OR jaishankar) AND (russia OR putin OR brics OR opec)',
    ],
    'hi': [
        'मोदी',
        'भारत चीन',
        'भारत पाकिस्तान',
        'विदेशी मुद्रा',
    ],
    'ur': [
        'مودی بھارت',
        'بھارت پاکستان',
        'بھارت چین',
    ],
}


BRAVE_QUERIES = [
    'modi statement india foreign policy site:thehindu.com OR site:livemint.com',
    'jaishankar india china relations',
    'rbi rupee defense forex reserves india',
    'india khalistan canada news',
    'india pakistan loc ceasefire violation',
]


# ============================================================================
# TRIGGER LADDERS — Per-actor 5-level escalation ladders (PATCH 4)
# ============================================================================
# Each actor has its own ladder. Level 5 is most severe, Level 1 is baseline.
# Triggers are case-insensitive phrase matches. Multilingual coverage matters
# for India: en/hi/ur trigger phrases all live in the same dict.
# Pattern mirrors China/Iran trackers — proven scoring path.

# ── PMO TRIGGERS ────────────────────────────────────────────────────────────
PMO_TRIGGERS = {
    5: [
        'modi declares emergency', 'modi war footing', 'modi national security threat',
        'modi orders armed forces', 'modi orders strike',
        'modi addresses nation crisis', 'modi assumes special powers',
        'मोदी आपातकाल', 'مودی ایمرجنسی',
    ],
    4: [
        'modi suspends foreign visits', 'modi cancels foreign tour',
        'modi gold duty hike', 'modi announces import controls',
        'modi warns pakistan', 'modi warns china',
        'modi calls emergency cabinet', 'modi statement on terror attack',
        'modi all-party meeting',
        'मोदी ने चेतावनी', 'مودی نے خبردار',
    ],
    3: [
        'modi avoid buying gold', 'modi suspend gold purchases',
        'modi cut consumption', 'modi appeal to citizens',
        'modi defence preparedness', 'modi border review',
        'modi urges restraint', 'pm modi calls on',
        'मोदी ने अपील', 'مودی نے اپیل',
    ],
    2: [
        'modi mann ki baat', 'modi rally', 'modi speech',
        'modi aatmanirbhar', 'modi vocal for local', 'modi make in india',
        'amit shah statement', 'home minister shah',
        'मोदी ने कहा', 'مودی نے کہا',
    ],
    1: [
        'narendra modi', 'pm modi', 'prime minister modi',
        'pmo india', 'bjp leader',
        'मोदी', 'مودی',
    ],
}

# ── MEA TRIGGERS ────────────────────────────────────────────────────────────
MEA_TRIGGERS = {
    5: [
        'india recalls ambassador', 'india expels diplomats',
        'india suspends diplomatic ties', 'mea downgrades relations',
        'india breaks bilateral mechanism',
        'भारत ने राजदूत वापस',
    ],
    4: [
        'mea summons envoy', 'mea protest note',
        'jaishankar warns', 'india suspends bilateral',
        'jaishankar rejects', 'india demands explanation',
        'india expresses serious concern',
        'जयशंकर ने चेतावनी', 'جے شنکر نے خبردار',
    ],
    3: [
        'jaishankar strategic autonomy', 'jaishankar multipolar',
        'jaishankar global south', 'india position firm',
        'mea spokesperson briefing', 'india rejects interference',
        'jaishankar civilisational state',
        'जयशंकर ने कहा', 'جے شنکر نے کہا',
    ],
    2: [
        'jaishankar meeting', 'jaishankar talks',
        'india delegation', 'mea statement',
        'south block briefing', 'raisina dialogue',
    ],
    1: [
        'jaishankar', 'external affairs minister', 'mea',
        'विदेश मंत्री',
    ],
}

# ── ARMED FORCES TRIGGERS ───────────────────────────────────────────────────
ARMED_FORCES_TRIGGERS = {
    5: [
        'india strikes across loc', 'india strikes pakistan',
        'india crosses lac', 'india fires across loc',
        'army combat operations', 'naval task force engaged',
        'indian air force strikes', 'army returns fire',
        'भारतीय सेना हमला',
    ],
    4: [
        'army moves troops forward', 'forward troop movement',
        'army mobilization', 'army mobilisation',
        'lac forward posture', 'loc heavy firing',
        'integrated theatre command activated', 'naval task force deployed',
        'army on full alert', 'air defence activated',
        'सेना तैनाती', 'فوج تعینات',
    ],
    3: [
        'cds chauhan warns', 'army chief warns',
        'navy chief warns', 'iaf chief warns',
        'army deployment lac', 'army patrol depsang',
        'army patrol galwan', 'army tawang',
        'navy carrier deployed', 'ins vikrant exercise',
        'सेना अध्यक्ष चेतावनी',
    ],
    2: [
        'lac patrolling', 'loc ceasefire violation',
        'army exercise', 'army drill',
        'forward base infrastructure', 'army logistics',
        'eastern command statement', 'northern command statement',
        'सीमा पर तैनाती',
    ],
    1: [
        'chief of defence staff', 'army chief', 'navy chief',
        'air chief marshal', 'lac', 'loc',
        'line of actual control', 'line of control',
        'थलसेना',
    ],
}

# ── ECONOMIC STATECRAFT TRIGGERS ────────────────────────────────────────────
ECONOMIC_STATECRAFT_TRIGGERS = {
    5: [
        'rbi emergency rate hike', 'capital controls imposed',
        'india approaches imf', 'rupee record low crisis',
        'forex reserves crisis', 'india suspends gold imports',
        'budget emergency measures',
        'आरबीआई आपातकालीन', 'سرمائے کنٹرول',
    ],
    4: [
        'gold import duty hike', 'rbi raises rates',
        'sitharaman emergency budget', 'capital controls signaled',
        'forex below 580 billion', 'oil import freeze',
        'goyal export ban', 'puri oil emergency',
        'rupee 88', 'rupee 90',
        'सोना आयात शुल्क', 'سونے کی درآمدی ڈیوٹی',
    ],
    3: [
        'rbi intervention rupee', 'rbi defends rupee',
        'rbi sells dollars', 'rbi gold accumulation',
        'sitharaman fiscal warning', 'sitharaman import bill',
        'goyal tariff response', 'rupee internationalization',
        'brics payments active', 'mbridge india',
        'pli scheme expansion',
        'रुपये की रक्षा', 'روپیہ کا دفاع',
    ],
    2: [
        'rbi monetary policy', 'mpc meeting',
        'sitharaman budget', 'finance minister statement',
        'goyal commerce', 'commerce ministry',
        'forex reserves report', 'rbi quarterly',
        'अर्थव्यवस्था', 'معیشت',
    ],
    1: [
        'rbi', 'reserve bank', 'sitharaman',
        'shaktikanta das', 'goyal', 'puri',
        'विदेशी मुद्रा',
    ],
}

# ── OPPOSITION TRIGGERS (INVERSE-SCORED) ────────────────────────────────────
# NOTE: Higher level = MORE opposition attacks = LOWER cohesion.
# Read by the internal dashboard as cohesion stress.
OPPOSITION_TRIGGERS = {
    5: [
        'no-confidence motion filed', 'no confidence motion filed',
        'opposition demands prime minister resignation',
        'opposition demands modi resignation',
        'opposition impeachment', 'opposition unified emergency',
        'india bloc national protest',
        'विपक्ष इस्तीफा', 'حزب اختلاف استعفیٰ',
    ],
    4: [
        'opposition walkout sustained', 'opposition boycott parliament',
        'rahul gandhi declares', 'kharge declares',
        'mamata banerjee walkout', 'stalin walkout',
        'opposition censure motion', 'india bloc rally',
        'rahul gandhi modi government failure',
        'राहुल गांधी हमला',
    ],
    3: [
        'rahul gandhi attacks modi', 'kharge attacks bjp',
        'opposition demands jpc', 'opposition slams government',
        'opposition manipur crisis', 'opposition unemployment',
        'opposition economic mismanagement',
        'india bloc statement', 'mamata banerjee criticizes',
        'electoral bonds opposition', 'pegasus opposition',
        'विपक्ष ने आरोप',
    ],
    2: [
        'rahul gandhi statement', 'kharge statement',
        'congress press conference', 'opposition meeting',
        'india bloc meeting', 'mamata banerjee meeting',
        'tmc statement', 'dmk statement',
        'विपक्ष बैठक',
    ],
    1: [
        'rahul gandhi', 'kharge', 'congress party',
        'india bloc', 'opposition alliance',
        'mamata banerjee', 'stalin',
        'राहुल गांधी', 'کانگریس',
    ],
}

# ── HINDUTVA IDEOLOGICAL TRIGGERS ───────────────────────────────────────────
HINDUTVA_TRIGGERS = {
    5: [
        'mass communal violence', 'temple mosque attack deaths',
        'bhagwat names enemy nation', 'rss authorizes mobilization',
        'hindutva mass mobilization',
        'सांप्रदायिक हिंसा',
    ],
    4: [
        'rss chief major speech', 'bhagwat vijayadashami doctrine',
        'temple mosque flashpoint violence', 'gyanvapi escalation',
        'mathura tensions', 'vhp aggressive statement',
        'bajrang dal mobilization', 'cow vigilante killings',
        'love jihad arrests', 'mass conversion arrests',
        'हिंदुत्व रैली',
    ],
    3: [
        'mohan bhagwat speech', 'rss chief statement',
        'sarsanghchalak address', 'vhp statement',
        'bajrang dal protest', 'hindu rashtra demand',
        'yogi adityanath warning', 'ghar wapsi campaign',
        'uniform civil code push', 'ucc bill',
        'राष्ट्रीय स्वयंसेवक संघ',
    ],
    2: [
        'rss meeting', 'rss vijayadashami',
        'vhp meeting', 'sangh parivar',
        'pracharak training', 'ram mandir event',
        'pran pratishtha anniversary',
        'मोहन भागवत',
    ],
    1: [
        'rss', 'vhp', 'bajrang dal',
        'mohan bhagwat', 'hindutva',
        'हिंदुत्व',
    ],
}

# ── ADVERSARY CROSS-READS TRIGGERS ──────────────────────────────────────────
ADVERSARY_TRIGGERS = {
    5: [
        'pakistan nuclear strike threat india',
        'pakistan first use india', 'pakistan tactical nukes india',
        'china pla mobilizes lac', 'china mobilizes western theater',
        'us imposes major sanctions india',
        'khalistan assassination claim',
        'पाकिस्तान परमाणु',
    ],
    4: [
        'pakistan nuclear signaling india', 'asim munir warns india',
        'china names indian territorial claim',
        'china claims zangnan', 'pla activity lac escalation',
        'global times threatens india',
        'us tariffs indian sector', 'h-1b visa india restriction',
        'pannun threat india', 'sfj banned activity',
        'nijjar evidence release',
        'عاصم منیر بھارت',
    ],
    3: [
        'asim munir statement india', 'shehbaz sharif on india',
        'bilawal bhutto on india', 'pakistan mofa india',
        'mao ning india', 'lin jian india',
        'wang yi india statement', 'global times india editorial',
        'trump tariff india', 'state department india',
        'pannun statement', 'sfj statement',
        'amritpal singh statement',
        'चीन ने कहा',
    ],
    2: [
        'pakistan army statement', 'islamabad mea india',
        'china mfa briefing india', 'china daily india',
        'us trade representative india', 'ustr india',
        'khalistan referendum announcement',
        'پاکستانی فوج',
    ],
    1: [
        'pakistan army', 'asim munir', 'china mfa',
        'pla western theater', 'khalistan', 'pannun',
        'us state department india',
    ],
}


# Master trigger map — used by _score_actor() to look up the right ladder
TRIGGER_MAP = {
    'pmo':                  PMO_TRIGGERS,
    'mea':                  MEA_TRIGGERS,
    'armed_forces':         ARMED_FORCES_TRIGGERS,
    'economic_statecraft':  ECONOMIC_STATECRAFT_TRIGGERS,
    'opposition':           OPPOSITION_TRIGGERS,
    'hindutva_ideological': HINDUTVA_TRIGGERS,
    'adversary_crossreads': ADVERSARY_TRIGGERS,
}


# ============================================================================
# SPECIFICITY EXTRACTION — named geographies, named assets (mirrors Iran)
# ============================================================================
# When India rhetoric mentions specific places/assets, that elevates
# specificity_score and surfaces as named_targets in the cross-theater
# fingerprint. Downstream consumers (Iran, China trackers) read these
# named_targets to know what India is signaling about.

SPECIFIC_GEOGRAPHIES_INDIA = [
    # LAC frontier
    'galwan', 'depsang', 'demchok', 'pangong', 'tawang', 'arunachal',
    'ladakh', 'siachen', 'sikkim', 'nathula', 'dokalam', 'doklam',
    # LoC / Kashmir
    'loc', 'line of control', 'uri', 'pulwama', 'pathankot',
    'kashmir', 'jammu', 'srinagar', 'baramulla', 'kupwara', 'shopian',
    # Internal flashpoints
    'manipur', 'imphal', 'churachandpur', 'gyanvapi', 'ayodhya', 'mathura',
    # Naval / Indo-Pacific
    'andaman', 'nicobar', 'malacca', 'bay of bengal', 'arabian sea',
    'duqm', 'agalega', 'sittwe',
    # Economic chokepoints
    'mumbai port', 'chennai port', 'vizag', 'jnpt',
    # International (diaspora / friction)
    'canada', 'ottawa', 'brampton', 'surrey',  # khalistan-adjacent
    'london', 'birmingham',                     # uk diaspora
    'new jersey', 'queens', 'california',       # us diaspora
]

SPECIFIC_ASSETS_INDIA = [
    'ins vikrant', 'ins vikramaditya', 'ins arihant', 'ins arighat',
    'rafale', 's-400', 'tejas', 'brahmos', 'agni', 'prithvi',
    'gold reserves', 'forex reserves', 'sovereign gold bonds',
    'rbi gold', 'imd missile',
    'nyom airfield', 'leh airfield', 'thoise',
]


def _score_specificity(text):
    """
    Iran-style specificity scoring. Used to extract named_targets for the
    cross-theater fingerprint write. Higher score = more concrete signal.
    Returns (score 0-10, breakdown dict).
    """
    score = 0
    breakdown = {'named_geographies': [], 'named_assets': []}
    text_lower = (text or '').lower()
    for geo in SPECIFIC_GEOGRAPHIES_INDIA:
        if geo in text_lower:
            breakdown['named_geographies'].append(geo)
            score += 1
    for asset in SPECIFIC_ASSETS_INDIA:
        if asset in text_lower:
            breakdown['named_assets'].append(asset)
            score += 1
    return min(score, 10), breakdown


# ============================================================================
# SOURCE WEIGHTS
# ============================================================================

def _get_source_weight(source_name):
    """Return a weight 0.5-1.0 based on source reputation."""
    name = (source_name or '').lower()
    tier_a = ['reuters', 'the hindu', 'idsa', 'orf', 'carnegie',
              'bbc', 'financial times', 'wall street journal']
    tier_b = ['hindustan times', 'indian express', 'mint',
              'business standard', 'the print']
    tier_c = ['ndtv', 'india today', 'the wire', 'scroll',
              'times of india']
    if any(s in name for s in tier_a): return 1.0
    if any(s in name for s in tier_b): return 0.85
    if any(s in name for s in tier_c): return 0.70
    return 0.60


def _parse_pub_date(pub_str):
    """Parse common RSS/JSON date formats. Returns datetime or None."""
    if not pub_str:
        return None
    for fmt_fn in (
        lambda s: parsedate_to_datetime(s),
        lambda s: datetime.fromisoformat(s.replace('Z', '+00:00')),
    ):
        try:
            dt = fmt_fn(pub_str)
            if dt and dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            continue
    return None


# ============================================================================
# CORE ACTOR SCORER (PATCH 4 — heart of the tracker)
# ============================================================================

def _score_actor(actor_key, articles):
    """
    Score a single actor against their keyword filter + trigger ladder.

    Returns:
        {
            'actor':            actor_key,
            'name':             actor's display name,
            ...metadata fields from ACTORS[actor_key]...,
            'level':            0-5 escalation level,
            'level_label':      ESCALATION_LEVELS[level]['label'],
            'level_color':      ESCALATION_LEVELS[level]['color'],
            'weighted_score':   float,
            'article_count':    int,
            'matched_triggers': list[str] (deduped),
            'top_articles':     list[dict] (top 5 by contribution),
            'specificity':      {'score': 0-10, 'named_geographies': [...], 'named_assets': [...]},
            'top_phrases':      list[str] (most-distinct phrases for fingerprint),
        }

    Pattern mirrors China's _score_actor (proven), adds Iran's specificity
    extraction (named_geographies / named_assets / top_phrases).
    """
    actor = ACTORS[actor_key]
    now   = datetime.now(timezone.utc)
    trigger_ladder = TRIGGER_MAP.get(actor_key, {})

    matched_triggers = []
    top_articles     = []
    weighted_score   = 0.0
    article_count    = 0
    specificity_total = 0
    geo_set    = set()
    asset_set  = set()
    phrase_pool = []

    actor_keywords_lower = [kw.lower() for kw in actor['keywords']]

    for article in articles:
        title   = (article.get('title') or '').lower()
        desc    = (article.get('description') or '').lower()
        content = (article.get('content') or '').lower()
        text    = f"{title} {desc} {content}"

        # Stage 1: actor keyword filter (only consider articles that mention
        # this actor at all)
        if not any(kw in text for kw in actor_keywords_lower[:25]):
            continue

        # Stage 2: time decay (more recent = more weight)
        pub_dt    = _parse_pub_date(article.get('publishedAt') or article.get('published'))
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

        # Stage 3: source weight
        source_field = article.get('source')
        if isinstance(source_field, dict):
            source_name = source_field.get('name', '')
        else:
            source_name = source_field or ''
        src_weight = article.get('source_weight_override',
                                 _get_source_weight(source_name))

        # Stage 4: find highest trigger level present in this article
        article_level   = 0
        matched_trigger = None
        for level in [5, 4, 3, 2, 1]:
            triggers = trigger_ladder.get(level, [])
            for trigger in triggers:
                if trigger in text:
                    article_level   = level
                    matched_trigger = trigger
                    if trigger not in matched_triggers:
                        matched_triggers.append(trigger)
                    break
            if article_level > 0:
                break

        if article_level == 0:
            continue

        # Stage 5: specificity extraction (Iran pattern)
        spec_score, spec_breakdown = _score_specificity(text)
        specificity_total += spec_score
        for geo in spec_breakdown['named_geographies']:
            geo_set.add(geo)
        for asset in spec_breakdown['named_assets']:
            asset_set.add(asset)

        contribution = article_level * decay * src_weight
        weighted_score += contribution
        article_count  += 1

        # Collect phrase candidates from the title (cleaner than mixed text)
        if article.get('title'):
            phrase_pool.append(article.get('title')[:140])

        top_articles.append({
            'title':        (article.get('title') or '')[:160],
            'url':          article.get('url') or '',
            'source':       source_name,
            'publishedAt':  article.get('publishedAt') or article.get('published') or '',
            'level':        article_level,
            'trigger':      matched_trigger,
            'contribution': round(contribution, 2),
            'specificity':  spec_score,
        })

    # Map weighted_score to 0-5 level (same thresholds as China — proven calibration)
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

    # Stage 6: tripwire override — any tripwire match auto-escalates to L4 minimum
    for tripwire in actor.get('tripwires', []):
        tw_lower = tripwire.lower()
        for article in articles:
            text = (
                (article.get('title') or '') + ' ' +
                (article.get('description') or '')
            ).lower()
            if tw_lower in text:
                level = max(level, 4)
                if f"TRIPWIRE: {tripwire}" not in matched_triggers:
                    matched_triggers.append(f"TRIPWIRE: {tripwire}")
                print(f"[India Rhetoric] TRIPWIRE: {actor_key} -> {tripwire}")
                break

    top_articles.sort(key=lambda x: x['contribution'], reverse=True)

    return {
        'actor':            actor_key,
        'name':             actor['name'],
        'flag':             actor['flag'],
        'icon':             actor['icon'],
        'color':            actor['color'],
        'dashboards':       actor['dashboards'],
        'weight':           actor['weight'],
        'role':             actor['role'],
        'description':      actor['description'],
        'level':            level,
        'level_label':      ESCALATION_LEVELS[level]['label'],
        'level_color':      ESCALATION_LEVELS[level]['color'],
        'weighted_score':   round(weighted_score, 2),
        'article_count':    article_count,
        'matched_triggers': matched_triggers[:12],
        'top_articles':     top_articles[:5],
        'specificity': {
            'score':              min(specificity_total, 100),
            'named_geographies':  sorted(list(geo_set))[:10],
            'named_assets':       sorted(list(asset_set))[:10],
        },
        'top_phrases': phrase_pool[:5],
    }


# ============================================================================
# DASHBOARD AGGREGATORS — outbound / inbound / internal maxes
# ============================================================================

def _compute_dashboard_levels(actor_results):
    """
    Compute per-dashboard max levels by walking each actor's `dashboards`
    membership list. An actor contributes to every dashboard it's a member of.

    For the OPPOSITION cluster, level is INVERSE — a high opposition level
    means a LOW cohesion. The internal dashboard reads this as cohesion stress
    directly; no inversion needed at aggregation time (we WANT the high signal
    to surface as internal stress).

    Returns:
        {
          'outbound_level': 0-5,
          'inbound_level':  0-5,
          'internal_level': 0-5,
          'outbound_contributors': [actor_key, ...],
          ...etc...
        }
    """
    dash_max = {'outbound': 0, 'inbound': 0, 'internal': 0}
    dash_contributors = {'outbound': [], 'inbound': [], 'internal': []}

    for actor_key, result in actor_results.items():
        lvl = result.get('level', 0)
        for d in result.get('dashboards', []):
            if lvl > dash_max[d]:
                dash_max[d] = lvl
            if lvl >= 2:   # only list actors that actually fired
                dash_contributors[d].append(actor_key)

    return {
        'outbound_level':        dash_max['outbound'],
        'inbound_level':         dash_max['inbound'],
        'internal_level':        dash_max['internal'],
        'outbound_contributors': dash_contributors['outbound'],
        'inbound_contributors':  dash_contributors['inbound'],
        'internal_contributors': dash_contributors['internal'],
    }


# ============================================================================
# THEATRE SCORE / LEVEL — overall India composite
# ============================================================================

def _compute_theatre_score(actor_results, dashboard_levels):
    """
    Composite score that rolls 7 actors + 3 dashboards into a single India
    posture metric. Used for the cross-theater fingerprint write and for the
    stability page banner.

    Pattern: Each actor contributes weight × level. Convergence bonus when
    multiple dashboards are simultaneously elevated. Theatre level is the
    canonical 0-5 max across dashboards.
    """
    weighted_sum = 0.0
    for actor_key, result in actor_results.items():
        weight = result.get('weight') or ACTORS[actor_key].get('weight', 1.0)
        level  = result.get('level', 0)
        weighted_sum += weight * level

    # Convergence bonus — penalize having multiple dashboards lit simultaneously
    lit_dashboards = sum(
        1 for d in ('outbound_level', 'inbound_level', 'internal_level')
        if dashboard_levels.get(d, 0) >= 3
    )
    convergence_bonus = 0
    if lit_dashboards >= 2: convergence_bonus = 5
    if lit_dashboards == 3: convergence_bonus = 10

    theatre_score = round(weighted_sum + convergence_bonus, 1)
    theatre_level = max(
        dashboard_levels.get('outbound_level', 0),
        dashboard_levels.get('inbound_level', 0),
        dashboard_levels.get('internal_level', 0),
    )

    return {
        'theatre_score':     theatre_score,
        'theatre_level':     theatre_level,
        'convergence_bonus': convergence_bonus,
        'lit_dashboards':    lit_dashboards,
    }


# ============================================================================
# OWN SIGNALS BUILDER (PATCH 4 — feeds absorption_proxy)
# ============================================================================
# This is the bridge between detection and the Butterfly Build. It converts
# the 7-actor result set into the boolean signal dict that absorption_detector
# rules check via when_own(). Naming matches the keys the detector expects
# (modi_gold_jawboning, rbi_fx_defense, armed_forces_lac_active, etc.).

def _build_own_signals(actor_results):
    """
    Map per-actor detection results to the flat signal dict that
    absorption_detector consumes via when_own() predicates.

    See absorption_detector.ABSORPTION_RULES for the contract — each rule
    declares which keys it expects. This function emits all of them.
    """
    pmo                  = actor_results.get('pmo', {}) or {}
    mea                  = actor_results.get('mea', {}) or {}
    armed                = actor_results.get('armed_forces', {}) or {}
    econ                 = actor_results.get('economic_statecraft', {}) or {}
    opposition           = actor_results.get('opposition', {}) or {}
    hindutva             = actor_results.get('hindutva_ideological', {}) or {}
    adversary            = actor_results.get('adversary_crossreads', {}) or {}

    # Helper: did this actor mention any of these keywords?
    def _has_phrase(actor_result, phrases):
        triggers = actor_result.get('matched_triggers', []) or []
        joined   = ' '.join(triggers).lower()
        return any(p.lower() in joined for p in phrases)

    # Helper: did this actor's top articles mention any of these phrases?
    def _articles_mention(actor_result, phrases):
        for art in actor_result.get('top_articles', []) or []:
            t = (art.get('title') or '').lower() + ' ' + (art.get('trigger') or '').lower()
            for p in phrases:
                if p.lower() in t:
                    return True
        return False

    # Modi gold jawboning — PMO must be active AND mention gold/discretionary
    modi_gold_jawboning = (
        pmo.get('level', 0) >= 2 and (
            _has_phrase(pmo, ['gold', 'discretionary imports', 'aatmanirbhar',
                              'vocal for local', 'cut consumption'])
            or _articles_mention(pmo, ['gold', 'सोना', 'سونا'])
        )
    )

    # RBI FX defense — economic_statecraft active AND mentions FX/rupee/forex
    rbi_fx_defense = (
        econ.get('level', 0) >= 2 and (
            _has_phrase(econ, ['rbi', 'rupee', 'forex', 'fx reserves',
                               'defends rupee', 'intervention'])
            or _articles_mention(econ, ['rbi', 'rupee', 'forex', 'विदेशी मुद्रा'])
        )
    )

    # MEA US friction — MEA active AND mentions US/tariff/visa
    mea_us_friction_active = (
        mea.get('level', 0) >= 2 and (
            _has_phrase(mea, ['us', 'tariff', 'visa', 'h-1b', 'h1b',
                              'state department'])
            or _articles_mention(mea, ['us', 'tariff', 'visa', 'trump'])
        )
    )

    # Commerce ministry tariff response — economic_statecraft active AND mentions tariff/duty
    commerce_tariff_response = (
        econ.get('level', 0) >= 2 and (
            _has_phrase(econ, ['tariff', 'duty', 'export ban', 'import duty',
                               'goyal'])
            or _articles_mention(econ, ['tariff', 'duty'])
        )
    )

    # Armed Forces LAC activity — armed_forces active AND mentions LAC/China-border
    armed_forces_lac_active = (
        armed.get('level', 0) >= 2 and (
            _has_phrase(armed, ['lac', 'line of actual control',
                                'ladakh', 'galwan', 'tawang', 'arunachal'])
            or _articles_mention(armed, ['lac', 'ladakh'])
        )
    )

    # Kashmir LoC activity — armed_forces active AND mentions LoC/Kashmir
    kashmir_loc_active = (
        armed.get('level', 0) >= 2 and (
            _has_phrase(armed, ['loc', 'line of control', 'kashmir',
                                'jammu', 'srinagar', 'pulwama', 'uri'])
            or _articles_mention(armed, ['loc', 'kashmir', 'कश्मीर'])
        )
    )

    # Communal stress — hindutva active OR opposition specifically attacking on communal
    communal_stress_active = (
        hindutva.get('level', 0) >= 3
        or (
            opposition.get('level', 0) >= 3 and
            _has_phrase(opposition, ['manipur', 'communal', 'gyanvapi',
                                     'love jihad', 'mathura'])
        )
    )

    # Opposition alignment — derived classification (normal / attacking / aligned)
    if opposition.get('level', 0) >= 4:
        opposition_alignment = 'attacking'
    elif opposition.get('level', 0) <= 1 and (
        armed.get('level', 0) >= 3 or adversary.get('level', 0) >= 3
    ):
        # Opposition is quiet WHILE armed forces or adversary signals are loud
        # — classic post-attack rally-round-the-flag alignment
        opposition_alignment = 'aligned'
    else:
        opposition_alignment = 'normal'

    return {
        'modi_gold_jawboning':       modi_gold_jawboning,
        'rbi_fx_defense':            rbi_fx_defense,
        'mea_us_friction_active':    mea_us_friction_active,
        'commerce_tariff_response':  commerce_tariff_response,
        'armed_forces_lac_active':   armed_forces_lac_active,
        'kashmir_loc_active':        kashmir_loc_active,
        'communal_stress_active':    communal_stress_active,
        'opposition_alignment':      opposition_alignment,
        # Raw actor levels — useful for callers that want finer-grained reads
        'pmo_level':                 pmo.get('level', 0),
        'mea_level':                 mea.get('level', 0),
        'armed_forces_level':        armed.get('level', 0),
        'economic_statecraft_level': econ.get('level', 0),
        'opposition_level':          opposition.get('level', 0),
        'hindutva_level':            hindutva.get('level', 0),
        'adversary_level':           adversary.get('level', 0),
    }


# ============================================================================
# BIDIRECTIONAL FLAGS — what relationships are India "active" with right now
# ============================================================================
# Mirrors Pakistan's pakistan_india_active / pakistan_china_active pattern.
# These get embedded in India's cross-theater fingerprint write so downstream
# trackers can quick-check the relationship state.

def _build_bidirectional_flags(actor_results):
    """
    Compute india_X_active flags from the adversary cross-reads cluster
    + supporting context from armed forces / MEA / economic statecraft.
    """
    adversary = actor_results.get('adversary_crossreads', {}) or {}
    armed     = actor_results.get('armed_forces', {}) or {}
    mea       = actor_results.get('mea', {}) or {}
    econ      = actor_results.get('economic_statecraft', {}) or {}

    triggers_all = (
        ' '.join(adversary.get('matched_triggers', []) or []) + ' ' +
        ' '.join(armed.get('matched_triggers', []) or []) + ' ' +
        ' '.join(mea.get('matched_triggers', []) or [])
    ).lower()

    pakistan_active = (
        adversary.get('level', 0) >= 2 and (
            'pakistan' in triggers_all or 'munir' in triggers_all
            or 'loc' in triggers_all or 'kashmir' in triggers_all
        )
    )

    china_lac_active = (
        (armed.get('level', 0) >= 2 or adversary.get('level', 0) >= 2)
        and (
            'lac' in triggers_all or 'galwan' in triggers_all
            or 'arunachal' in triggers_all or 'tawang' in triggers_all
            or 'ladakh' in triggers_all or 'zangnan' in triggers_all
        )
    )

    china_tech_friction_active = (
        econ.get('level', 0) >= 2 and (
            'china' in triggers_all and (
                'tariff' in triggers_all or 'tech' in triggers_all
                or 'app' in triggers_all or 'semiconductor' in triggers_all
            )
        )
    )

    us_friction_active = (
        (mea.get('level', 0) >= 2 or adversary.get('level', 0) >= 2) and (
            'us' in triggers_all or 'trump' in triggers_all
            or 'h-1b' in triggers_all or 'tariff india' in triggers_all
            or 'khalistan' in triggers_all
        )
    )

    russia_active = (
        mea.get('level', 0) >= 2 and (
            'russia' in triggers_all or 'putin' in triggers_all
            or 'brics' in triggers_all or 'opec' in triggers_all
        )
    )

    return {
        'india_pakistan_active':           pakistan_active,
        'india_china_lac_active':          china_lac_active,
        'india_china_tech_friction_active': china_tech_friction_active,
        'india_us_friction_active':        us_friction_active,
        'india_russia_active':             russia_active,
    }


# ============================================================================
# AGGREGATED PHRASES + NAMED TARGETS — for cross-theater fingerprint write
# ============================================================================

def _aggregate_top_phrases(actor_results, limit=8):
    """Collect top phrases across all actors (weighted by actor weight)."""
    weighted_phrases = []
    for actor_key, result in actor_results.items():
        weight = result.get('weight', 1.0)
        for phrase in result.get('top_phrases', []) or []:
            weighted_phrases.append((weight, phrase))
    weighted_phrases.sort(key=lambda t: t[0], reverse=True)
    seen, out = set(), []
    for _, phrase in weighted_phrases:
        if phrase and phrase not in seen:
            seen.add(phrase)
            out.append(phrase)
        if len(out) >= limit:
            break
    return out


def _aggregate_named_targets(actor_results, limit=12):
    """Union of named_geographies + named_assets across all actors."""
    seen = set()
    for result in actor_results.values():
        spec = result.get('specificity', {}) or {}
        for geo in spec.get('named_geographies', []) or []:
            seen.add(geo)
        for asset in spec.get('named_assets', []) or []:
            seen.add(asset)
    return sorted(list(seen))[:limit]


# ============================================================================
# REDIS HELPERS — minimal Upstash REST shim used by the read function
# ============================================================================
# Mirrors the helpers in China/Iran/Pakistan trackers. Lazy-defined here so
# Patch 5 stands alone; Patch 8 (main scan) will use these same helpers.

def _redis_get(key):
    """GET a JSON value from Upstash. Returns parsed object or None."""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        url = f"{UPSTASH_REDIS_URL}/get/{urllib.parse.quote(key, safe='')}"
        r = requests.get(
            url,
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            timeout=5,
        )
        if r.status_code != 200:
            return None
        payload = r.json()
        raw = payload.get('result')
        if raw in (None, '', 'null'):
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
    except Exception as e:
        print(f"[India Rhetoric] Redis GET error ({key}): {str(e)[:160]}")
        return None


def _redis_set(key, value, ttl=RHETORIC_CACHE_TTL):
    """SET a JSON value to Upstash with optional TTL. Returns True/False."""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return False
    try:
        if isinstance(value, (dict, list)):
            payload = json.dumps(value, default=str)
        else:
            payload = str(value)
        if ttl and ttl > 0:
            url = f"{UPSTASH_REDIS_URL}/setex/{urllib.parse.quote(key, safe='')}/{int(ttl)}"
        else:
            url = f"{UPSTASH_REDIS_URL}/set/{urllib.parse.quote(key, safe='')}"
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            data=payload,
            timeout=5,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[India Rhetoric] Redis SET error ({key}): {str(e)[:160]}")
        return False


def _redis_lpush_trim(key, value, max_len=HISTORY_MAX_ENTRIES):
    """LPUSH + LTRIM combo for bounded history lists."""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return False
    try:
        payload = json.dumps(value, default=str) if isinstance(value, (dict, list)) else str(value)
        # LPUSH (Upstash REST POST body = element)
        push_url = f"{UPSTASH_REDIS_URL}/lpush/{urllib.parse.quote(key, safe='')}"
        r = requests.post(
            push_url,
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            data=payload,
            timeout=5,
        )
        if r.status_code != 200:
            return False
        # LTRIM 0 max_len-1
        trim_url = f"{UPSTASH_REDIS_URL}/ltrim/{urllib.parse.quote(key, safe='')}/0/{max_len-1}"
        requests.post(
            trim_url,
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            timeout=5,
        )
        return True
    except Exception as e:
        print(f"[India Rhetoric] Redis LPUSH/LTRIM error ({key}): {str(e)[:160]}")
        return False


# ============================================================================
# CROSS-THEATER READ (PATCH 5) — Iran / China / Pakistan / US subscribers
# ============================================================================
# India is downstream of multiple command-node trackers. This function reads
# their fingerprints from Redis, normalizes the different key conventions in
# use across the platform, and returns:
#
#   1. A flat `upstream_fingerprints` dict suitable for handing directly to
#      absorption_proxy_asia.detect_and_persist_via_proxy()
#   2. An `amplifier_actor_deltas` dict telling _score_actor() which actors
#      should get a +1 level boost because upstream pressure is on
#   3. A list of human-readable context_notes that surface in the BLUF text
#      ("China LAC pressure detected — armed_forces amplified")
#   4. An `india_upstream_stressors[]` list of stressor labels for downstream
#      display (the absorption card's "upstream stressors" pills)
#
# The function NEVER fails the whole scan. If Redis is unreachable or any
# single upstream fingerprint is missing, it returns sensible defaults so
# the rest of the India scan can complete. Pattern mirrors China's
# _read_crosstheater_amplifiers() (which is the most battle-tested reader
# in the codebase).
#
# DUAL KEY CONVENTION REALITY (per architecture memo May 12):
#   iran     — shared dict at CROSSTHEATER_SHARED_KEY, sub-key 'iran'
#   china    — shared dict at CROSSTHEATER_SHARED_KEY, sub-key 'china'
#   pakistan — direct key 'crosstheater:pakistan:fingerprint'
#   us       — direct key 'fingerprint:us:current'
# This reader handles all four cleanly via the UPSTREAM_KEYS map at top.


def _read_upstream_fingerprints():
    """
    Read all relevant upstream theater fingerprints. Returns a dict shape
    that is COMPATIBLE WITH absorption_detector.ABSORPTION_RULES — meaning
    the field names match what the detector's `when_upstream()` predicates
    expect.

    Returns:
        {
            'upstream_fingerprints': {
                'iran':     {... raw fingerprint from shared dict ...},
                'china':    {... raw fingerprint from shared dict ...},
                'pakistan': {... raw fingerprint from direct key ...},
                'us':       {... raw fingerprint from direct key ...},
            },
            'amplifier_actor_deltas': {
                'pmo':          +1,    # if upstream stress is significant
                'armed_forces': +1,    # if china LAC or pakistan LoC fired
                ...
            },
            'india_upstream_stressors': [
                'iran_hormuz_oil', 'us_tariff_pressure', ...
            ],
            'context_notes': [
                'Iran-Hormuz pressure active (theatre_score=65) — Modi gold ...',
                'China LAC posture elevated (PLA L3) — armed_forces amplified',
                ...
            ],
            'read_at': '2026-05-12T...Z',
        }

    If an upstream fingerprint isn't available, its slot will be {} (empty
    dict). Callers should never assume any particular field is present;
    always use .get() with defaults.
    """
    upstream_fps = {'iran': {}, 'china': {}, 'pakistan': {}, 'us': {}}
    amplifier_actor_deltas = {}
    upstream_stressors = []
    context_notes = []

    # ── Step 1: pull the shared cross-theater dict (Iran + China live here)
    shared_dict = _redis_get(CROSSTHEATER_SHARED_KEY) or {}
    if isinstance(shared_dict, dict):
        if isinstance(shared_dict.get('iran'), dict):
            upstream_fps['iran'] = shared_dict['iran']
        if isinstance(shared_dict.get('china'), dict):
            upstream_fps['china'] = shared_dict['china']

    # ── Step 2: pull per-country direct keys (Pakistan + US)
    pak_fp = _redis_get('crosstheater:pakistan:fingerprint')
    if isinstance(pak_fp, dict):
        upstream_fps['pakistan'] = pak_fp

    us_fp = _redis_get('fingerprint:us:current')
    if isinstance(us_fp, dict):
        upstream_fps['us'] = us_fp

    # ── Step 3: IRAN amplifier logic
    # Iran is India's primary commodity-pressure upstream. Hormuz pressure
    # directly elevates Modi/economic-statecraft jawboning likelihood.
    iran = upstream_fps['iran']
    if iran:
        iran_score = int(iran.get('theatre_score', 0) or 0)
        iran_irgc  = int(iran.get('irgc_level', 0) or 0)
        iran_proxy = int(iran.get('proxy_activation_level', 0) or 0)
        iran_targets = iran.get('named_targets', []) or []

        # Hormuz signal: either explicit flag, or named-target match, or
        # high theatre_score + IRGC elevation combo
        hormuz_named = any(t in iran_targets for t in
                          ['hormuz', 'strait of hormuz', 'persian gulf'])
        hormuz_pressure = (
            bool(iran.get('iran_hormuz_pressure'))
            or hormuz_named
            or (iran_score >= 60 and iran_irgc >= 3)
        )

        if hormuz_pressure:
            upstream_stressors.append('iran_hormuz_oil')
            context_notes.append(
                f"Iran-Hormuz pressure active (theatre_score={iran_score}, "
                f"IRGC L{iran_irgc}) — Modi-class jawboning + RBI FX defense "
                f"more likely; PMO + economic_statecraft amplified."
            )
            # Amplify the actors most likely to absorb this pressure
            amplifier_actor_deltas['pmo'] = amplifier_actor_deltas.get('pmo', 0) + 1
            amplifier_actor_deltas['economic_statecraft'] = (
                amplifier_actor_deltas.get('economic_statecraft', 0) + 1
            )

        # BRICS / dedollarization regime signals — relevant for India's
        # rupee-internationalization rhetoric (Jaishankar / RBI)
        if iran.get('iran_brics_alignment_active') or iran.get('iran_dedollarization_active'):
            upstream_stressors.append('iran_brics_dedollarization')
            context_notes.append(
                "Iran BRICS/dedollarization rhetoric active — India MEA + "
                "economic_statecraft positioning amplified (strategic autonomy frame)."
            )
            amplifier_actor_deltas['mea'] = amplifier_actor_deltas.get('mea', 0) + 1

        # Proxy activation = regional volatility multiplier
        if iran_proxy >= 3:
            context_notes.append(
                f"Iran proxy network at L{iran_proxy} — regional volatility "
                f"affects India's Indian Ocean / Gulf corridor positioning."
            )

    # ── Step 4: CHINA amplifier logic
    # China is India's primary kinetic-pressure upstream (LAC) AND
    # economic-pressure upstream (tech, BRICS architect).
    china = upstream_fps['china']
    if china:
        china_level = int(china.get('level', 0) or 0)
        china_pla   = int(china.get('pla_level', 0) or 0)
        china_econ  = int(china.get('econ_level', 0) or 0)

        # LAC pressure: high PLA level or high overall level fires LAC stressor
        if china_pla >= 3 or china_level >= 3:
            upstream_stressors.append('china_pla_lac_posture')
            context_notes.append(
                f"China PLA posture elevated (PLA L{china_pla}, overall "
                f"L{china_level}) — India armed_forces amplified; LAC "
                f"absorption signature candidate."
            )
            amplifier_actor_deltas['armed_forces'] = (
                amplifier_actor_deltas.get('armed_forces', 0) + 1
            )
            amplifier_actor_deltas['adversary_crossreads'] = (
                amplifier_actor_deltas.get('adversary_crossreads', 0) + 1
            )

        # Tech/economic coercion vector
        if china_econ >= 3:
            upstream_stressors.append('china_tech_economic_coercion')
            context_notes.append(
                f"China economic coercion vector L{china_econ} — India "
                f"economic_statecraft amplified (tech sovereignty + app bans)."
            )
            amplifier_actor_deltas['economic_statecraft'] = (
                amplifier_actor_deltas.get('economic_statecraft', 0) + 1
            )

        # BRICS architect — competes with rupee internationalization
        if china.get('china_brics_architect_active'):
            if 'china_brics_architecture' not in upstream_stressors:
                upstream_stressors.append('china_brics_architecture')
            context_notes.append(
                "China BRICS architect role active — India MEA "
                "multipolar / rupee-internationalization stance amplified."
            )

        # Yuan internationalization — competes directly with rupee push
        if china.get('china_yuan_internationalization_active'):
            context_notes.append(
                "China yuan-internationalization push active — India "
                "economic_statecraft rupee-trade rhetoric amplified."
            )

    # ── Step 5: PAKISTAN amplifier logic
    # Pakistan is India's primary kinetic-pressure upstream on LoC + Kashmir.
    pak = upstream_fps['pakistan']
    if pak:
        pak_level    = int(pak.get('theatre_level', 0) or 0)
        pak_kashmir  = int(pak.get('kashmir_loc_level', 0) or 0)
        pak_nuclear  = int(pak.get('nuclear_doctrine_level', 0) or 0)

        if pak_kashmir >= 3 or pak.get('pakistan_india_active'):
            upstream_stressors.append('pakistan_loc_escalation')
            context_notes.append(
                f"Pakistan LoC/Kashmir level L{pak_kashmir} "
                f"(india_active={bool(pak.get('pakistan_india_active'))}) — "
                f"India armed_forces + adversary_crossreads amplified."
            )
            amplifier_actor_deltas['armed_forces'] = (
                amplifier_actor_deltas.get('armed_forces', 0) + 1
            )
            amplifier_actor_deltas['adversary_crossreads'] = (
                amplifier_actor_deltas.get('adversary_crossreads', 0) + 1
            )

        if pak_nuclear >= 3 or pak.get('pakistan_nuclear_signaling'):
            upstream_stressors.append('pakistan_nuclear_signaling')
            context_notes.append(
                f"Pakistan nuclear doctrine signaling L{pak_nuclear} — "
                f"India top-level political (PMO) + adversary_crossreads "
                f"amplified; tripwire territory."
            )
            amplifier_actor_deltas['pmo'] = amplifier_actor_deltas.get('pmo', 0) + 1
            amplifier_actor_deltas['adversary_crossreads'] = (
                amplifier_actor_deltas.get('adversary_crossreads', 0) + 1
            )

    # ── Step 6: US amplifier logic
    # US can fire on India in several ways: tariffs, H-1B, Khalistan
    # indictments. The us_outbound_targets list is the canonical signal.
    us = upstream_fps['us']
    if us:
        us_active   = bool(us.get('us_active'))
        us_exec_vol = float(us.get('us_executive_volatility', 0) or 0)
        us_dhs      = bool(us.get('us_dhs_enforcement_active'))
        us_outbound = us.get('us_outbound_targets', []) or []

        # India in outbound targets = direct US-on-India rhetoric
        india_targeted = any(
            (isinstance(t, dict) and t.get('country') == 'india')
            or (isinstance(t, str) and t.lower() == 'india')
            for t in us_outbound
        )

        if india_targeted:
            upstream_stressors.append('us_tariff_pressure')
            context_notes.append(
                "US tracker shows India in outbound_targets — likely tariff "
                "/ H-1B / Khalistan rhetoric. India MEA + economic_statecraft "
                "+ adversary_crossreads amplified."
            )
            amplifier_actor_deltas['mea'] = amplifier_actor_deltas.get('mea', 0) + 1
            amplifier_actor_deltas['economic_statecraft'] = (
                amplifier_actor_deltas.get('economic_statecraft', 0) + 1
            )
            amplifier_actor_deltas['adversary_crossreads'] = (
                amplifier_actor_deltas.get('adversary_crossreads', 0) + 1
            )

        # General Trump-class executive volatility — indirect pressure
        if us_active and us_exec_vol >= 1.5:
            if 'us_executive_volatility' not in upstream_stressors:
                upstream_stressors.append('us_executive_volatility')
            context_notes.append(
                f"US executive volatility ratio {us_exec_vol:.2f} — broad "
                f"unpredictability; India MEA amplified for hedging language."
            )

        # DHS enforcement (H-1B / Khalistan deportations)
        if us_dhs:
            if 'us_h1b_pressure' not in upstream_stressors:
                upstream_stressors.append('us_h1b_pressure')
            context_notes.append(
                "US DHS enforcement active — H-1B + Khalistan diaspora "
                "pressure on India."
            )

    # ── Step 7: Deduplicate + cap context notes
    # Keep at most 6 context notes to avoid downstream display bloat
    context_notes = context_notes[:6]

    return {
        'upstream_fingerprints':    upstream_fps,
        'amplifier_actor_deltas':   amplifier_actor_deltas,
        'india_upstream_stressors': upstream_stressors,
        'context_notes':            context_notes,
        'read_at':                  datetime.now(timezone.utc).isoformat(),
    }


def _apply_amplifier_deltas(actor_results, deltas):
    """
    Apply per-actor level boosts from the cross-theater read step.
    Caps the boosted level at 5 (the platform max). Mutates the input dict.

    This is called AFTER _score_actor() has run for every actor, so the
    amplifier boost reflects "upstream context elevates what we're already
    seeing" rather than amplifying noise.
    """
    if not deltas:
        return actor_results
    for actor_key, delta in deltas.items():
        if actor_key not in actor_results:
            continue
        cur = actor_results[actor_key].get('level', 0)
        # Only boost if actor is already firing at L1+ (no boosting silence)
        if cur >= 1:
            new_level = min(5, cur + int(delta))
            if new_level != cur:
                actor_results[actor_key]['level']         = new_level
                actor_results[actor_key]['level_label']   = ESCALATION_LEVELS[new_level]['label']
                actor_results[actor_key]['level_color']   = ESCALATION_LEVELS[new_level]['color']
                actor_results[actor_key]['amplified_by']  = delta
                actor_results[actor_key]['original_level'] = cur
    return actor_results


# ============================================================================
# CROSS-THEATER WRITE (PATCH 6) — India fingerprint, dual-key persistence
# ============================================================================
# India is the platform's FIRST absorber-class tracker. Its fingerprint is
# read by:
#   • Iran tracker      (looks in shared dict under 'india' key)
#   • China tracker     (same shared dict)
#   • Pakistan tracker  (looks at 'fingerprint:india:current' direct key)
#   • US tracker        (same direct key)
#   • Future GPI Absorption Dimension (filters for is_absorber_node: True)
#
# Two write conventions in production on the platform — we write to BOTH:
#
#   Convention A — shared dict at CROSSTHEATER_SHARED_KEY
#                  We update existing['india'] = {...} preserving other keys
#                  Used by: Iran, China readers
#
#   Convention B — per-country direct key at CROSSTHEATER_INDIA_KEY
#                  We write the full fingerprint under one key
#                  Used by: Pakistan, US readers
#
# PAYLOAD CONTRACT (consumed by 4 downstream trackers + GPI):
# ──────────────────────────────────────────────────────────
# Standard fields (every fingerprint has these):
#   ts, theatre, theatre_score, theatre_level, level, score
#
# India-specific posture levels:
#   outbound_level, inbound_level, internal_level
#
# Per-actor levels (7 clusters):
#   pmo_level, mea_level, armed_forces_level, economic_statecraft_level,
#   opposition_level, hindutva_level, adversary_level
#
# Bidirectional flags (mirrors Pakistan's pattern):
#   india_pakistan_active, india_china_lac_active,
#   india_china_tech_friction_active, india_us_friction_active,
#   india_russia_active
#
# Node-class flags:
#   is_command_node: False    # India is absorber, NOT commander
#   is_absorber_node: True    # NEW — India is platform's FIRST
#
# Butterfly Build (Phase 2) fields:
#   absorption_active, absorption_count, upstream_stressors[],
#   cohesion_stress_level
#
# Named cohesion/absorption signals (consumed for display + by downstream):
#   modi_jawboning_active, rbi_fx_defense_active,
#   communal_stress_active, opposition_alignment
#
# Specificity fields (Iran-pattern):
#   top_phrases, named_targets, specificity_score


def _build_india_fingerprint(
    actor_results,
    dashboard_levels,
    theatre,
    own_signals,
    bidirectional_flags,
    upstream_stressors=None,
    absorption_results=None,
):
    """
    Assemble India's cross-theater fingerprint payload. Pure function — no
    Redis IO. Returns the dict that gets persisted by _write_india_fingerprint.

    Patch 7 will pass live absorption_results here; Patch 6 alone leaves
    those fields at safe defaults.
    """
    upstream_stressors = list(upstream_stressors or [])
    absorption_results = list(absorption_results or [])

    # Cohesion stress: composite of opposition + hindutva activity
    # (internal dashboard) capped at L5
    opposition_lvl = (actor_results.get('opposition', {}) or {}).get('level', 0)
    hindutva_lvl   = (actor_results.get('hindutva_ideological', {}) or {}).get('level', 0)
    cohesion_stress_level = min(5, max(opposition_lvl, hindutva_lvl))

    # Aggregate top phrases + named targets across all actors
    top_phrases   = _aggregate_top_phrases(actor_results, limit=8)
    named_targets = _aggregate_named_targets(actor_results, limit=12)

    # Specificity score: sum of all actors' specificity (capped at 100)
    spec_total = sum(
        (r.get('specificity', {}) or {}).get('score', 0)
        for r in actor_results.values()
    )
    spec_total = min(spec_total, 100)

    fingerprint = {
        # ── Identity ─────────────────────────────────────────────────────
        'ts':                datetime.now(timezone.utc).isoformat(),
        'updated_at':        datetime.now(timezone.utc).isoformat(),
        'theatre':           'India',
        'tracker_version':   '1.0.0',

        # ── Node-class flags (the architecturally important ones) ────────
        'is_command_node':   False,
        'is_absorber_node':  True,

        # ── Standard composite scores ────────────────────────────────────
        'theatre_score':     theatre.get('theatre_score', 0),
        'theatre_level':     theatre.get('theatre_level', 0),
        'level':             theatre.get('theatre_level', 0),       # alias
        'score':             theatre.get('theatre_score', 0),       # alias
        'convergence_bonus': theatre.get('convergence_bonus', 0),
        'lit_dashboards':    theatre.get('lit_dashboards', 0),

        # ── Per-dashboard maxes ──────────────────────────────────────────
        'outbound_level':    dashboard_levels.get('outbound_level', 0),
        'inbound_level':     dashboard_levels.get('inbound_level', 0),
        'internal_level':    dashboard_levels.get('internal_level', 0),
        'outbound_contributors': dashboard_levels.get('outbound_contributors', []),
        'inbound_contributors':  dashboard_levels.get('inbound_contributors', []),
        'internal_contributors': dashboard_levels.get('internal_contributors', []),

        # ── Per-actor levels (7 clusters) ────────────────────────────────
        'pmo_level':                 (actor_results.get('pmo', {}) or {}).get('level', 0),
        'mea_level':                 (actor_results.get('mea', {}) or {}).get('level', 0),
        'armed_forces_level':        (actor_results.get('armed_forces', {}) or {}).get('level', 0),
        'economic_statecraft_level': (actor_results.get('economic_statecraft', {}) or {}).get('level', 0),
        'opposition_level':          opposition_lvl,
        'hindutva_level':            hindutva_lvl,
        'adversary_level':           (actor_results.get('adversary_crossreads', {}) or {}).get('level', 0),

        # ── Bidirectional flags (relationship state) ─────────────────────
        'india_pakistan_active':            bidirectional_flags.get('india_pakistan_active', False),
        'india_china_lac_active':           bidirectional_flags.get('india_china_lac_active', False),
        'india_china_tech_friction_active': bidirectional_flags.get('india_china_tech_friction_active', False),
        'india_us_friction_active':         bidirectional_flags.get('india_us_friction_active', False),
        'india_russia_active':              bidirectional_flags.get('india_russia_active', False),

        # ── Named cohesion / absorption signals ──────────────────────────
        # These are the high-signal flags downstream consumers + the
        # rhetoric-india frontend will most often display directly.
        'modi_jawboning_active':    bool(own_signals.get('modi_gold_jawboning')),
        'rbi_fx_defense_active':    bool(own_signals.get('rbi_fx_defense')),
        'mea_us_friction_active':   bool(own_signals.get('mea_us_friction_active')),
        'kashmir_loc_active':       bool(own_signals.get('kashmir_loc_active')),
        'armed_forces_lac_active':  bool(own_signals.get('armed_forces_lac_active')),
        'communal_stress_active':   bool(own_signals.get('communal_stress_active')),
        'opposition_alignment':     own_signals.get('opposition_alignment', 'normal'),

        # ── Butterfly Build (Phase 2) — populated fully by Patch 7 ───────
        # Patch 6 alone leaves these at safe defaults. When Patch 7 calls
        # the absorption proxy, it will overwrite these with live values
        # by passing absorption_results to this builder.
        'absorption_active':       len(absorption_results) > 0,
        'absorption_count':        len(absorption_results),
        'absorption_signature_ids': [r.get('signature_id') for r in absorption_results if r.get('signature_id')],
        'upstream_stressors':       upstream_stressors,
        'cohesion_stress_level':    cohesion_stress_level,

        # ── Specificity (Iran-pattern) ───────────────────────────────────
        'top_phrases':       top_phrases,
        'named_targets':     named_targets,
        'specificity_score': spec_total,
    }

    return fingerprint


def _write_india_fingerprint(fingerprint):
    """
    Write India's fingerprint to BOTH cross-theater key conventions.

    Convention A (shared dict): read by Iran + China trackers.
        We MERGE into the existing dict so we don't clobber Iran's or
        China's entries.

    Convention B (direct key): read by Pakistan + US trackers.
        We write the full fingerprint under one key.

    Returns:
        dict with two booleans showing which writes succeeded:
            {'shared_dict_write': True/False, 'direct_key_write': True/False}
    """
    results = {'shared_dict_write': False, 'direct_key_write': False}

    # ── Write A: merge into shared dict
    try:
        shared = _redis_get(CROSSTHEATER_SHARED_KEY) or {}
        if not isinstance(shared, dict):
            shared = {}
        shared['india'] = fingerprint
        # 8-hour TTL matches Iran's convention for the shared dict
        ok_a = _redis_set(CROSSTHEATER_SHARED_KEY, shared, ttl=8 * 3600)
        results['shared_dict_write'] = bool(ok_a)
        if ok_a:
            print(f"[India Rhetoric] ✅ Cross-theater fingerprint written to shared dict "
                  f"(L{fingerprint.get('theatre_level', 0)}, "
                  f"score={fingerprint.get('theatre_score', 0)}, "
                  f"is_absorber_node=True)")
        else:
            print("[India Rhetoric] ⚠️ Shared-dict write returned False")
    except Exception as e:
        print(f"[India Rhetoric] ❌ Shared-dict write error: {str(e)[:160]}")

    # ── Write B: per-country direct key
    try:
        # 14-hour TTL matches Pakistan's convention for direct-key fingerprints
        ok_b = _redis_set(CROSSTHEATER_INDIA_KEY, fingerprint, ttl=14 * 3600)
        results['direct_key_write'] = bool(ok_b)
        if ok_b:
            print(f"[India Rhetoric] ✅ Cross-theater fingerprint written to "
                  f"{CROSSTHEATER_INDIA_KEY}")
        else:
            print(f"[India Rhetoric] ⚠️ Direct-key write to {CROSSTHEATER_INDIA_KEY} returned False")
    except Exception as e:
        print(f"[India Rhetoric] ❌ Direct-key write error: {str(e)[:160]}")

    return results

# ============================================================================
# ABSORPTION INTEGRATION (PATCH 7) — call the Butterfly Build
# ============================================================================
# This is the patch that makes the Butterfly Build's wings actually flap
# every scan. After Patch 4 has scored actors, Patch 5 has applied upstream
# amplifiers, and we know which upstream fingerprints + own_signals to send,
# this function calls the Asia proxy → ME backend → absorption_detector and
# returns the structured results.
#
# CRITICAL DESIGN POINT — what the absorption proxy expects:
#
#     detect_and_persist_via_proxy(
#         country='india',
#         upstream_fingerprints={'iran': {...}, 'china': {...},
#                                'pakistan': {...}, 'us': {...}},
#         own_signals={'modi_gold_jawboning': True, 'rbi_fx_defense': False, ...},
#     ) → list[dict]
#
# Each returned dict has shape:
#     {
#         'signature_id':        'india_gold_suppress_demand',
#         'rule_id':             'india_gold_modi_2026_05',
#         'confidence':          0.85,
#         'upstream_stressors':  ['iran_hormuz_oil', ...],
#         'cohesion_stress_level': 1,
#         'upstream_evidence':   [...],
#         'persisted':           True/False,
#     }
#
# The 'persisted' flag tells us whether the ME backend successfully wrote
# the dynamic signature to Redis (which absorption_signatures.py's
# read_absorption_signature endpoint can then serve back).
#
# WHAT WE DO WITH THE RESULTS:
#   1. Pass them to _build_india_fingerprint() so the next fingerprint write
#      includes absorption_active: True + absorption_count + signature_ids
#   2. Log a clear "🦋 N absorption signature(s) fired" line so deploy logs
#      surface the moment
#   3. Return them so the caller can include them in the scan result
#      payload (Patch 8 will surface them on /api/rhetoric/india)
#
# FAILURE HANDLING:
#   The proxy already has graceful failure built in — if ME backend is
#   unreachable, it returns [] and logs a warning. We propagate that:
#   absorption_active becomes False, scan continues, fingerprint still
#   writes (just without absorption fields populated).


def _run_absorption_detection(upstream_fingerprints, own_signals):
    """
    Call the Asia absorption proxy to detect + persist absorption signatures.

    Returns:
        list[dict] — one entry per fired rule, possibly empty.
        Empty list does NOT signal failure; it signals "no absorption rules
        fire under current conditions" which is the normal case most of
        the time.

    The proxy itself routes the call to ME backend's /api/absorption/detect.
    All detection rules + the static catalog + Redis persistence live on
    ME. This function is the Asia-side bridge.
    """
    if not ABSORPTION_DETECTOR_AVAILABLE:
        print("[India Rhetoric] ⚠️ Absorption proxy unavailable — "
              "skipping Butterfly write this scan")
        return []

    if not own_signals:
        # Defensive — if Patch 4's own_signals builder somehow returned empty
        return []

    try:
        results = detect_absorption_and_persist(
            country='india',
            upstream_fingerprints=upstream_fingerprints or {},
            own_signals=own_signals or {},
        )
    except Exception as e:
        print(f"[India Rhetoric] ❌ Absorption proxy call failed: {str(e)[:200]}")
        return []

    results = results or []

    # Log the moment — this is the line that appears in Render deploy logs
    # when the Butterfly fires
    if results:
        signature_summary = ', '.join(
            f"{r.get('signature_id', '?')}@{r.get('confidence', 0):.2f}"
            for r in results
        )
        persisted_count = sum(1 for r in results if r.get('persisted'))
        print(f"[India Rhetoric] 🦋 {len(results)} absorption signature(s) fired: "
              f"{signature_summary}  "
              f"({persisted_count}/{len(results)} persisted to ME Redis)")
    else:
        print("[India Rhetoric] 🦋 No absorption signatures fired this scan "
              "(no rule had both upstream + own conditions satisfied)")

    return results


# ============================================================================
# END OF PATCH 7
# ============================================================================
# The function above completes the Butterfly Build's automatic firing path:
#
#   Patch 4 scoring → Patch 5 read → Patch 6 fingerprint shape →
#   Patch 7 absorption call → Patch 6 fingerprint write (now with absorption)
#
# Patches that follow will add:
#   Patch 8 — Main scan orchestration + endpoints + registration
#               (this is where _run_absorption_detection actually gets called)
#   Patch 9 — US tracker patch (add 'india' to outbound keyword dict)
#   Patch 10 — Asia app.py registration of the india tracker
#   Patch 11 — rhetoric-india.html (full dedicated frontend page)
#   Patch 12 — rhetoric-asia.html update (add India link to hub)
#   Patch 13 — india-stability.html update (live rhetoric panel)
