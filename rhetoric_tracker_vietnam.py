# -*- coding: utf-8 -*-
"""
Asifah Analytics -- Vietnam South China Sea & Sovereignty Tracker
v1.0.0 -- June 2026

ANALYTICAL FRAME:
This tracker is the South China Sea mirror of rhetoric_tracker_taiwan.py. The
central question is maritime-sovereignty coercion, not cross-strait invasion:

  "What is China doing in the South China Sea against Vietnam right now --
   is Vietnam's response + coalition posture keeping pace -- and is a
   coercion-response gap opening that lets Beijing normalize gray-zone
   control of contested features?"

DUAL DASHBOARD:

  OUTBOUND -- "Is Vietnam asserting/defending its SCS sovereignty?"
    CPV / State leadership sovereignty signals (To Lam dual role),
    MOFA diplomacy + lawfare (UNCLOS, PCA, note verbale, ASEAN),
    Coast Guard / Navy maritime posture (Vanguard Bank, Spratly features,
    oil/gas survey defense, fisheries protection, maritime militia),
    US partnership (CSP, cutters, port calls, MDA),
    Indo-Pacific hedging (Philippines, Japan, India + bamboo diplomacy)

  INBOUND -- "What is China doing against Vietnam in the SCS?"
    China Coast Guard + maritime militia + survey-vessel incursions,
    Beijing political coercion (MFA, "indisputable sovereignty"),
    economic coercion (trade, rare earth, tourism, border).
    Scanned directly (Vietnam-specific SCS keywords) and contextualized by
    the China rhetoric fingerprint when available.

CROSS-COUNTRY / BUTTERFLY (answers "is there convergence?"):
  - Reads the IRAN fingerprint  -> hormuz_vietnam_energy_dependency
  - Reads the TAIWAN fingerprint -> china_two_front_convergence
    (Beijing pressuring Taiwan AND Vietnam at once)
  - US + regional partners       -> vietnam_indo_pacific_convergence
  - Reads the BUTTERFLY proxy (ME upstream stressors via Asia proxy)
  - Reads the CONVERGENCE proxy (ME-registered convergences for Vietnam)

KEY METRIC:
  COERCION-RESPONSE GAP = inbound China SCS pressure - (Vietnam + coalition
  response). The Vietnam analog of Taiwan's deterrence gap. A widening gap is
  the single most important signal this tracker produces.

DISCIPLINE: convergence framing, NOT prediction. The tracker reports which
signals are present, never whether kinetic action is imminent.

REDIS KEYS:
  Cache:         rhetoric:vietnam:latest
  Legacy:        vietnam_rhetoric_cache
  History:       rhetoric:vietnam:history
  Cross-theater: rhetoric:crosstheater:fingerprints
                 (READS china/taiwan/iran, WRITES vietnam)

ENDPOINTS:
  GET /api/rhetoric/vietnam
  GET /api/rhetoric/vietnam/summary
  GET /api/rhetoric/vietnam/history

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

# Signal interpreter (Red Lines + Historical + So What + Top Signals + BLUF)
try:
    from vietnam_signal_interpreter import (
        check_red_lines,
        build_so_what,
        build_historical_matches,
        build_top_signals,
        build_bluf,
        build_watch_indicators,
    )
    _INTERPRETER_AVAILABLE = True
    print("[Vietnam Rhetoric] Signal interpreter loaded")
except ImportError as e:
    print(f"[Vietnam Rhetoric] WARNING: vietnam_signal_interpreter not available ({e})")
    _INTERPRETER_AVAILABLE = False

# Butterfly proxy (ME upstream stressors via Asia proxy)
try:
    from butterfly_proxy_asia import read_butterfly_signals_via_proxy
    _BUTTERFLY_AVAILABLE = True
    print("[Vietnam Rhetoric] Butterfly proxy available")
except ImportError:
    _BUTTERFLY_AVAILABLE = False
    print("[Vietnam Rhetoric] Butterfly proxy not available -- skipping upstream stressors")

# Convergence proxy (ME-registered convergences via Asia proxy)
try:
    from convergence_proxy_asia import find_convergences_for_country_proxy
    _CONVERGENCE_PROXY_AVAILABLE = True
    print("[Vietnam Rhetoric] Convergence proxy available")
except ImportError:
    _CONVERGENCE_PROXY_AVAILABLE = False
    print("[Vietnam Rhetoric] Convergence proxy not available -- skipping external convergences")

# ============================================
# CONFIG
# ============================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN') or os.environ.get('UPSTASH_REDIS_REST_TOKEN')
NEWSAPI_KEY         = os.environ.get('NEWSAPI_KEY')
GDELT_BASE_URL      = 'https://api.gdeltproject.org/api/v2/doc/doc'

try:
    from telegram_signals_asia import fetch_asia_telegram_signals
    TELEGRAM_AVAILABLE = True
    print("[Vietnam Rhetoric] Telegram signals available")
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[Vietnam Rhetoric] Telegram signals not available -- RSS/GDELT only")

RHETORIC_CACHE_KEY        = 'rhetoric:vietnam:latest'
RHETORIC_CACHE_KEY_LEGACY = 'vietnam_rhetoric_cache'
HISTORY_KEY               = 'rhetoric:vietnam:history'
CROSSTHEATER_KEY          = 'rhetoric:crosstheater:fingerprints'

RHETORIC_CACHE_TTL  = 6 * 3600
SCAN_INTERVAL_HOURS = 6

_rhetoric_running = False
_rhetoric_lock    = threading.Lock()


# ============================================
# ESCALATION LEVELS
# ============================================
ESCALATION_LEVELS = {
    0: {'label': 'Baseline',        'color': '#6b7280', 'description': 'Routine SCS activity, no significant signals'},
    1: {'label': 'Rhetoric',        'color': '#3b82f6', 'description': 'Standard sovereignty statements, routine patrols'},
    2: {'label': 'Warning',         'color': '#f59e0b', 'description': 'Elevated CCG presence, survey activity, mild coercion'},
    3: {'label': 'Confrontation',   'color': '#f97316', 'description': 'Survey/rig incursion, oil-gas standoff, sovereignty escalation'},
    4: {'label': 'High Alert',      'color': '#ef4444', 'description': 'Ramming incident, feature presence change, sustained standoff'},
    5: {'label': 'Active Conflict', 'color': '#dc2626', 'description': 'Casualties, vessel sinking, kinetic exchange at sea'},
}


# ============================================
# ACTORS
# ============================================
ACTORS = {

    # -- OUTBOUND ACTORS (Vietnam-side signals) --------------------

    'cpv_state': {
        'name': 'CPV / State Leadership',
        'flag': '🇻🇳',
        'icon': '🏛️',
        'color': '#dc2626',
        'dashboard': 'outbound',
        'role': 'Party / State Sovereignty Signals',
        'description': 'CPV Politburo and State leadership (To Lam holds both General Secretary and '
                       'State President) sovereignty signaling on the South China Sea. Hanoi balances '
                       'sovereignty assertion against its "bamboo diplomacy" hedge with Beijing.',
        'keywords': [
            'to lam', 'vietnam general secretary', 'vietnam president',
            'vietnam politburo', 'vietnam communist party', 'cpv',
            'pham minh chinh', 'vietnam prime minister',
            'vietnam sovereignty', 'vietnam territorial', 'vietnam south china sea',
            'vietnam east sea', 'vietnam defends sovereignty',
            'vietnam rejects china claim', 'vietnam protests china',
            'hanoi sovereignty', 'vietnam indisputable sovereignty',
            'vietnam will defend', 'vietnam national interest sea',
            # Vietnamese
            'tô lâm', 'chủ quyền', 'biển đông', 'việt nam phản đối',
            'bộ chính trị', 'tổng bí thư',
        ],
        'baseline_statements_per_week': 5,
        'tripwires': [
            'vietnam mobilizes navy',
            'vietnam declares emergency south china sea',
            'vietnam recalls ambassador china',
        ],
    },

    'mofa_diplomacy': {
        'name': 'MOFA Diplomacy / Lawfare',
        'flag': '🇻🇳',
        'icon': '🌐',
        'color': '#0891b2',
        'dashboard': 'outbound',
        'role': 'Diplomatic Protest / UNCLOS / ASEAN',
        'description': 'Vietnam Ministry of Foreign Affairs diplomatic track: protests, note verbale '
                       'to the UN, UNCLOS / 2016 PCA invocation, ASEAN coordination, and Code of '
                       'Conduct negotiation. The lawfare and coalition-building vector.',
        'keywords': [
            'vietnam foreign ministry', 'vietnam mofa', 'vietnam spokesperson',
            'vietnam diplomatic protest', 'vietnam note verbale', 'vietnam un submission',
            'vietnam unclos', 'vietnam pca', 'vietnam tribunal',
            'vietnam asean', 'code of conduct south china sea', 'coc south china sea',
            'vietnam demarche', 'vietnam summons china', 'vietnam condemns china',
            'vietnam law of the sea', 'vietnam continental shelf',
            'vietnam diplomatic note', 'vietnam rejects nine-dash',
            # Vietnamese
            'bộ ngoại giao', 'người phát ngôn', 'công hàm', 'phản đối ngoại giao',
        ],
        'baseline_statements_per_week': 6,
        'tripwires': [
            'vietnam files un case china',
            'vietnam initiates arbitration china',
            'vietnam summons chinese ambassador',
        ],
    },

    'maritime_posture': {
        'name': 'Maritime Posture (Coast Guard / Navy)',
        'flag': '🇻🇳',
        'icon': '⚓',
        'color': '#b91c1c',
        'dashboard': 'outbound',
        'role': 'Coast Guard / Navy / Survey-Defense / Fisheries',
        'description': 'Vietnam Coast Guard, People\'s Navy, fisheries-surveillance and maritime-'
                       'militia posture in the SCS: Vanguard Bank survey defense, Spratly (Truong Sa) '
                       'feature activity and island-building, oil/gas escort, and fisher protection.',
        'keywords': [
            'vietnam coast guard', 'vietnam navy', 'vietnam fisheries surveillance',
            'vietnam maritime militia', 'vietnam vessel', 'vietnam patrol',
            'vanguard bank', 'bai tu chinh', 'block 06-01', 'nam con son',
            'vietnam spratly', 'truong sa', 'vietnam island building',
            'vietnam dredging', 'vietnam reclamation spratly', 'vietnam outpost',
            'vietnam paracel', 'hoang sa', 'vietnam oil rig escort',
            'petrovietnam', 'vietnam survey vessel', 'vietnam fishing boat',
            'vietnam standoff china', 'vietnam shadows china',
            # Vietnamese
            'cảnh sát biển', 'hải quân việt nam', 'kiểm ngư',
            'trường sa', 'hoàng sa', 'tàu cá', 'bãi tư chính',
        ],
        'baseline_statements_per_week': 10,
        'tripwires': [
            'vietnam navy deploys spratly',
            'vietnam coast guard standoff',
            'vietnam expels chinese vessel',
        ],
    },

    'us_partnership': {
        'name': 'US-Vietnam Partnership',
        'flag': '🇺🇸',
        'icon': '🤝',
        'color': '#1d4ed8',
        'dashboard': 'outbound',
        'role': 'US Security Cooperation / CSP / Maritime Capacity',
        'description': 'US-Vietnam relationship signals: the 2023 Comprehensive Strategic Partnership, '
                       'coast-guard cutter transfers, carrier port calls, maritime-domain-awareness '
                       'support, and defense cooperation. Beijing watches every US-Vietnam security step.',
        'keywords': [
            'us vietnam', 'united states vietnam', 'us vietnam defense',
            'comprehensive strategic partnership', 'us vietnam security',
            'us carrier vietnam', 'carrier visits da nang', 'uss vietnam port call',
            'coast guard cutter vietnam', 'us cutter hanoi', 'maritime domain awareness vietnam',
            'us vietnam maritime', 'us arms vietnam', 'us vietnam cooperation',
            'blinken vietnam', 'austin vietnam', 'us official hanoi', 'biden vietnam',
            'us vietnam trade defense', 'us indo-pacific vietnam',
            # Vietnamese
            'hoa kỳ việt nam', 'đối tác chiến lược toàn diện',
        ],
        'baseline_statements_per_week': 5,
        'tripwires': [
            'us vietnam defense agreement',
            'us base access vietnam',
            'us vietnam mutual security',
        ],
    },

    'regional_partners': {
        'name': 'Indo-Pacific Partners / Hedge',
        'flag': '🌏',
        'icon': '🧭',
        'color': '#7c3aed',
        'dashboard': 'outbound',
        'role': 'Philippines / Japan / India / ASEAN Diversification',
        'description': 'Vietnam\'s partnership diversification and "bamboo diplomacy" hedge: maritime '
                       'cooperation with the Philippines, Japan, India, and Australia, plus ASEAN '
                       'coordination. Also captures the Russia/China side of the hedge for balance.',
        'keywords': [
            'vietnam philippines', 'vietnam japan', 'vietnam india', 'vietnam australia',
            'vietnam coast guard agreement', 'vietnam philippines coast guard',
            'vietnam japan defense', 'vietnam india maritime', 'vietnam quad',
            'vietnam asean maritime', 'vietnam regional security',
            'vietnam russia', 'vietnam china party', 'vietnam balancing',
            'bamboo diplomacy', 'vietnam hedging', 'vietnam comprehensive partner',
            'vietnam south korea defense', 'vietnam eu maritime',
            # Vietnamese
            'việt nam philippines', 'việt nam nhật bản', 'việt nam ấn độ',
        ],
        'baseline_statements_per_week': 4,
        'tripwires': [
            'vietnam philippines defense pact',
            'vietnam japan security treaty',
            'vietnam joins quad',
        ],
    },

    # -- INBOUND ACTORS (China SCS pressure on Vietnam) --

    'china_scs_pressure': {
        'name': 'China SCS Pressure (CCG / Militia)',
        'flag': '🇨🇳',
        'icon': '⚔️',
        'color': '#dc2626',
        'dashboard': 'inbound',
        'role': 'Coast Guard / Maritime Militia / Survey Incursion',
        'description': 'China Coast Guard, maritime militia, and survey-vessel pressure on Vietnam: '
                       'Vanguard Bank incursions, Haiyang Dizhi survey deployments, ramming and '
                       'water-cannon incidents, and gray-zone presence around Vietnamese features.',
        'keywords': [
            'china coast guard vietnam', 'ccg vietnam', 'chinese maritime militia',
            'china survey vessel', 'haiyang dizhi', 'hysy-981', 'hd-981',
            'china rig vietnam', 'china incursion vanguard', 'china vanguard bank',
            'china rams vietnam', 'china water cannon vietnam', 'china blocks vietnam',
            'china spratly vietnam', 'china paracel', 'china militia swarm',
            'china survey vietnam eez', 'china pressure vietnam oil',
            'china intrudes vietnam waters', 'china harasses vietnam',
            # Chinese
            '中国海警', '海上民兵', '海洋地质', '南海越南',
        ],
        'baseline_statements_per_week': 12,
        'tripwires': [
            'china rams vietnamese vessel',
            'vietnamese fishermen killed',
            'china seizes vietnam feature',
            'china rig vietnam eez',
        ],
    },

    'beijing_coercion': {
        'name': 'Beijing Political Coercion',
        'flag': '🇨🇳',
        'icon': '📢',
        'color': '#7c3aed',
        'dashboard': 'inbound',
        'role': 'MFA / Nine-Dash / Sovereignty Claims at Hanoi',
        'description': 'Beijing political coercion directed at Hanoi: MFA warnings, "indisputable '
                       'sovereignty" assertions over the nine/ten-dash line, CCG Law enforcement '
                       'claims, and demands that Vietnam halt cooperation with external partners.',
        'keywords': [
            'china warns vietnam', 'beijing warns vietnam', 'china mfa vietnam',
            'china indisputable sovereignty', 'nine-dash line', 'ten-dash line',
            'china south china sea adiz', 'scs adiz', 'china coast guard law',
            'china opposes vietnam', 'china external interference south china sea',
            'china sovereignty south china sea', 'china historic rights',
            'china demands vietnam', 'china rejects vietnam claim',
            # Chinese
            '中国警告越南', '无可争辩主权', '九段线', '南海行为',
        ],
        'baseline_statements_per_week': 8,
        'tripwires': [
            'china declares south china sea adiz',
            'china enacts nine-dash law',
            'china detains vietnamese under ccg law',
        ],
    },

    'economic_pressure': {
        'name': 'China Economic Pressure',
        'flag': '🇨🇳',
        'icon': '💹',
        'color': '#d97706',
        'dashboard': 'inbound',
        'role': 'Trade / Rare Earth / Tourism / Border Leverage',
        'description': 'China economic coercion leverage over Vietnam: trade dependency, rare-earth '
                       'and input supply, tourism flows, and land-border friction. Vietnam\'s deep '
                       'trade reliance on China is the principal economic vulnerability.',
        'keywords': [
            'china trade vietnam', 'china tariff vietnam', 'china rare earth vietnam',
            'china tourism vietnam', 'china border vietnam', 'china economic pressure vietnam',
            'china supply chain vietnam', 'china input vietnam', 'china customs vietnam',
            'china bans vietnam', 'china restricts vietnam', 'china fishing ban',
            'china seizes fishing boat vietnam', 'china fishing moratorium',
            # Chinese
            '对越南贸易', '稀土越南', '禁渔',
        ],
        'baseline_statements_per_week': 4,
        'tripwires': [
            'china trade embargo vietnam',
            'china closes border vietnam',
            'china rare earth ban vietnam',
        ],
    },
}

OUTBOUND_ACTOR_KEYS = ['cpv_state', 'mofa_diplomacy', 'maritime_posture', 'us_partnership', 'regional_partners']
INBOUND_ACTOR_KEYS  = ['china_scs_pressure', 'beijing_coercion', 'economic_pressure']

# Inbound actors report ON Chinese actions; discount reporting language to
# avoid inflating the inbound dashboard from neutral coverage.
REPORTING_ACTORS = {'china_scs_pressure', 'beijing_coercion', 'economic_pressure'}

REPORTING_LANGUAGE = [
    'condemns', 'condemned', 'protests', 'denounces',
    'calls on', 'urges', 'expresses concern', 'deeply concerned',
    'in response to', 'following the standoff', 'following the incursion',
    'according to', 'reports that', 'monitors', 'tracks',
    'detected', 'observed', 'confirmed', 'vietnam coast guard says',
    '谴责', '抗议', '关切',
]


# ============================================
# THREAT VECTORS -- trigger ladders (L5 -> L1)
# ============================================

CPV_STATE_TRIGGERS = {
    5: [
        'vietnam mobilizes navy', 'vietnam declares emergency south china sea',
        'vietnam recalls ambassador china', 'vietnam war footing',
    ],
    4: [
        'vietnam will defend sovereignty', 'vietnam rejects china claim',
        'to lam south china sea', 'vietnam national interest sea',
        'vietnam firm sovereignty', 'chủ quyền',
    ],
    3: [
        'vietnam protests china', 'vietnam sovereignty', 'hanoi sovereignty',
        'vietnam east sea', 'vietnam defends', 'việt nam phản đối',
    ],
    2: [
        'vietnam south china sea', 'vietnam politburo', 'to lam', 'tô lâm',
        'vietnam communist party', 'biển đông',
    ],
    1: [
        'vietnam government', 'cpv', 'vietnam president', 'vietnam',
    ],
}

MOFA_TRIGGERS = {
    5: [
        'vietnam files un case china', 'vietnam initiates arbitration china',
        'vietnam summons chinese ambassador',
    ],
    4: [
        'vietnam note verbale', 'vietnam un submission', 'vietnam rejects nine-dash',
        'vietnam demarche', 'vietnam summons china', 'công hàm',
    ],
    3: [
        'vietnam diplomatic protest', 'vietnam unclos', 'vietnam pca',
        'vietnam condemns china', 'code of conduct south china sea',
        'phản đối ngoại giao',
    ],
    2: [
        'vietnam foreign ministry', 'vietnam mofa', 'vietnam asean',
        'vietnam spokesperson', 'bộ ngoại giao',
    ],
    1: [
        'vietnam diplomatic', 'vietnam foreign', 'vietnam law of the sea',
    ],
}

MARITIME_TRIGGERS = {
    5: [
        'vietnam expels chinese vessel', 'vietnam navy deploys spratly',
        'vietnam fires warning', 'vietnam vessel sunk',
    ],
    4: [
        'vietnam coast guard standoff', 'vanguard bank standoff',
        'vietnam shadows china', 'vietnam survey defense',
        'vietnam island building', 'bãi tư chính',
    ],
    3: [
        'vietnam coast guard', 'vietnam navy', 'vietnam fisheries surveillance',
        'vietnam patrol', 'vietnam spratly', 'truong sa', 'petrovietnam',
        'cảnh sát biển', 'trường sa',
    ],
    2: [
        'vietnam maritime', 'vietnam vessel', 'vietnam fishing boat',
        'vietnam paracel', 'hoang sa', 'hải quân việt nam',
    ],
    1: [
        'vietnam sea', 'vietnam maritime militia', 'vietnam waters',
    ],
}

US_PARTNERSHIP_TRIGGERS = {
    5: [
        'us vietnam defense agreement', 'us base access vietnam',
        'us vietnam mutual security',
    ],
    4: [
        'us carrier vietnam', 'carrier visits da nang', 'coast guard cutter vietnam',
        'us vietnam defense', 'us cutter hanoi', 'comprehensive strategic partnership',
    ],
    3: [
        'us vietnam security', 'us vietnam maritime', 'maritime domain awareness vietnam',
        'us official hanoi', 'us arms vietnam', 'blinken vietnam', 'austin vietnam',
    ],
    2: [
        'us vietnam', 'united states vietnam', 'us vietnam cooperation',
        'us indo-pacific vietnam', 'hoa kỳ việt nam',
    ],
    1: [
        'us vietnam trade', 'washington hanoi', 'us vietnam relations',
    ],
}

REGIONAL_TRIGGERS = {
    5: [
        'vietnam philippines defense pact', 'vietnam japan security treaty',
        'vietnam joins quad',
    ],
    4: [
        'vietnam philippines coast guard', 'vietnam japan defense',
        'vietnam india maritime', 'vietnam coast guard agreement',
    ],
    3: [
        'vietnam philippines', 'vietnam japan', 'vietnam india',
        'vietnam australia', 'vietnam regional security', 'vietnam asean maritime',
    ],
    2: [
        'vietnam comprehensive partner', 'bamboo diplomacy', 'vietnam balancing',
        'vietnam hedging', 'vietnam south korea defense',
    ],
    1: [
        'vietnam asean', 'vietnam russia', 'vietnam partner',
    ],
}

# Inbound triggers
CHINA_SCS_TRIGGERS = {
    5: [
        'china rams vietnamese vessel', 'vietnamese fishermen killed',
        'china seizes vietnam feature', 'china sinks vietnam',
    ],
    4: [
        'china rig vietnam eez', 'haiyang dizhi vietnam', 'hd-981',
        'china water cannon vietnam', 'china survey vietnam eez',
        'china incursion vanguard', 'china vanguard bank',
    ],
    3: [
        'china coast guard vietnam', 'ccg vietnam', 'chinese maritime militia',
        'china survey vessel', 'china blocks vietnam', 'china harasses vietnam',
        '中国海警',
    ],
    2: [
        'china spratly vietnam', 'china paracel', 'china militia swarm',
        'china intrudes vietnam waters', '海上民兵',
    ],
    1: [
        'china south china sea', 'china pressure vietnam', 'china vietnam waters',
    ],
}

BEIJING_COERCION_TRIGGERS = {
    5: [
        'china declares south china sea adiz', 'china enacts nine-dash law',
        'china detains vietnamese under ccg law',
    ],
    4: [
        'china indisputable sovereignty', 'china historic rights south china sea',
        'china demands vietnam', 'china coast guard law', '无可争辩主权',
    ],
    3: [
        'china warns vietnam', 'beijing warns vietnam', 'china opposes vietnam',
        'nine-dash line', 'china external interference south china sea',
        '中国警告越南',
    ],
    2: [
        'china mfa vietnam', 'china sovereignty south china sea', 'china rejects vietnam claim',
        '九段线',
    ],
    1: [
        'china south china sea claim', 'beijing south china sea', 'china vietnam',
    ],
}

ECONOMIC_PRESSURE_TRIGGERS = {
    5: [
        'china trade embargo vietnam', 'china closes border vietnam',
        'china rare earth ban vietnam',
    ],
    4: [
        'china bans vietnam', 'china restricts vietnam', 'china fishing ban',
        'china seizes fishing boat vietnam', '禁渔',
    ],
    3: [
        'china tariff vietnam', 'china customs vietnam', 'china economic pressure vietnam',
        'china fishing moratorium', '对越南贸易',
    ],
    2: [
        'china trade vietnam', 'china supply chain vietnam', 'china rare earth vietnam',
        'china tourism vietnam',
    ],
    1: [
        'china border vietnam', 'china input vietnam', 'china economy vietnam',
    ],
}


# ============================================
# RSS SOURCES
# ============================================
RSS_SOURCES = {
    # Vietnam primary -- outbound + domestic SCS coverage
    'vnexpress': {
        'url': 'https://e.vnexpress.net/rss/news.rss',
        'name': 'VnExpress International',
        'weight': 0.9,
        'note': 'Largest Vietnamese outlet, English edition',
    },
    'tuoi_tre': {
        'url': 'https://tuoitrenews.vn/rss/politics.rss',
        'name': 'Tuoi Tre News',
        'weight': 0.85,
        'note': 'Fast on SCS incidents',
    },
    'vietnamnet': {
        'url': 'https://vietnamnet.vn/en/rss/politics.rss',
        'name': 'VietnamNet',
        'weight': 0.8,
    },
    'vietnam_news': {
        'url': 'https://vietnamnews.vn/rss/politics-laws.rss',
        'name': 'Vietnam News (VNA)',
        'weight': 0.85,
        'note': 'State news agency -- official Hanoi line',
    },
    # SCS satellite / analytical -- the core inbound source
    'csis_amti': {
        'url': 'https://amti.csis.org/feed/',
        'name': 'CSIS AMTI',
        'weight': 0.95,
        'note': 'South China Sea satellite imagery analysis -- primary SCS source',
    },
    # US commitment signals
    'usni_news': {
        'url': 'https://news.usni.org/feed',
        'name': 'USNI News',
        'weight': 1.0,
        'note': '7th Fleet movements, US-Vietnam maritime cooperation',
    },
    # Regional analytical
    'scmp': {
        'url': 'https://www.scmp.com/rss/91/feed',
        'name': 'South China Morning Post',
        'weight': 0.9,
        'note': 'China reaction + SCS coverage',
    },
    'nikkei_asia': {
        'url': 'https://asia.nikkei.com/rss/feed/nar',
        'name': 'Nikkei Asia',
        'weight': 0.9,
        'note': 'Vietnam economy + maritime security',
    },
    'the_diplomat': {
        'url': 'https://thediplomat.com/feed/',
        'name': 'The Diplomat',
        'weight': 0.9,
        'note': 'Strong SCS + Vietnam ASEAN analysis',
    },
    'rfa': {
        'url': 'https://www.rfa.org/english/rss2.xml',
        'name': 'Radio Free Asia',
        'weight': 0.85,
        'note': 'RFA Vietnamese service breaks SCS incidents',
    },
    'reuters_world': {
        'url': 'https://feeds.reuters.com/Reuters/worldNews',
        'name': 'Reuters World',
        'weight': 1.0,
        'note': 'Newswire baseline for major breaking stories',
    },
    'benar_news': {
        'url': 'https://www.benarnews.org/english/rss2.xml',
        'name': 'BenarNews',
        'weight': 0.85,
        'note': 'Southeast Asia maritime / SCS dedicated coverage',
    },
}

REDDIT_SUBREDDITS = [
    'vietnam', 'geopolitics', 'CredibleDefense', 'worldnews',
    'southeastasia', 'LessCredibleDefence', 'GlobalPowers',
    'Sino', 'OSINT', 'WarCollege', 'Philippines', 'AsiaPacific',
    'CombatFootage', 'NCD',
]
REDDIT_USER_AGENT = 'AsifahAnalytics-Vietnam/1.0.0 (OSINT tracker)'

GDELT_QUERIES = {
    'eng_inbound':  'China coast guard Vietnam South China Sea survey Vanguard Bank',
    'eng_outbound': 'Vietnam sovereignty navy coast guard Spratly US partnership',
    'vie_inbound':  'Trung Quốc hải cảnh Việt Nam biển Đông bãi Tư Chính',
    'vie_outbound': 'Việt Nam chủ quyền cảnh sát biển Trường Sa',
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
        print(f"[Vietnam Rhetoric] Redis GET error: {str(e)[:80]}")
    return None


def _redis_set(key, value):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return False
    try:
        requests.post(
            UPSTASH_REDIS_URL,
            headers={
                "Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                "Content-Type": "application/json"
            },
            json=["SET", key, json.dumps(value, default=str)],
            timeout=5
        )
        return True
    except Exception as e:
        print(f"[Vietnam Rhetoric] Redis SET error: {str(e)[:80]}")
    return False


def _redis_lpush_trim(key, value, max_len=336):
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
        print(f"[Vietnam Rhetoric] Redis LPUSH error: {str(e)[:80]}")


# ============================================
# CROSS-THEATER FINGERPRINT READS
# ============================================

def _read_china_fingerprint():
    """Read China rhetoric fingerprint -- general Beijing posture context.
    Vietnam's inbound is scanned directly (SCS keywords); the China fingerprint
    adds context (is Beijing broadly assertive right now?)."""
    try:
        fingerprints = _redis_get(CROSSTHEATER_KEY)
        if fingerprints and 'china' in fingerprints:
            china = fingerprints['china']
            print(f"[Vietnam Rhetoric] China fingerprint: L{china.get('level', 0)} "
                  f"(PLA L{china.get('pla_level', 0)}, MFA L{china.get('mfa_level', 0)})")
            return china
    except Exception as e:
        print(f"[Vietnam Rhetoric] China fingerprint read error: {str(e)[:80]}")
    print("[Vietnam Rhetoric] China fingerprint not available -- inbound from SCS scan only")
    return None


def _read_taiwan_fingerprint():
    """Read Taiwan fingerprint -- for china_two_front_convergence.
    If Beijing is pressuring Taiwan AND the SCS against Vietnam simultaneously,
    that is a regional multi-front coercion pattern."""
    try:
        fingerprints = _redis_get(CROSSTHEATER_KEY)
        if fingerprints and 'taiwan' in fingerprints:
            taiwan = fingerprints['taiwan']
            inbound = int(taiwan.get('inbound_max_level', taiwan.get('inbound_max', 0)) or 0)
            print(f"[Vietnam Rhetoric] Taiwan fingerprint: inbound L{inbound} "
                  f"(PLA pressure proxy for two-front read)")
            return taiwan
    except Exception as e:
        print(f"[Vietnam Rhetoric] Taiwan fingerprint read error: {str(e)[:80]}")
    return None


def _read_iran_fingerprint():
    """Read Iran fingerprint -- for hormuz_vietnam_energy_dependency.
    Vietnam is a net energy importer with refining reliance; Hormuz pressure
    raises input costs and adds friction to SCS oil/gas operations."""
    iran_data = {
        'hormuz_pressure_active': False,
        'theatre_score':          0,
        'irgc_level':             0,
        'proxy_active':           False,
    }
    try:
        fingerprints = _redis_get(CROSSTHEATER_KEY)
        if fingerprints and 'iran' in fingerprints:
            iran_fp = fingerprints['iran']
            iran_score = int(iran_fp.get('theatre_score', 0) or 0)
            iran_irgc = int(iran_fp.get('irgc_level', 0) or 0)
            iran_proxy = int(iran_fp.get('proxy_activation_level', 0) or 0)
            iran_targets = iran_fp.get('named_targets', []) or []

            iran_data['theatre_score'] = iran_score
            iran_data['irgc_level'] = iran_irgc
            iran_data['proxy_active'] = iran_proxy >= 3

            hormuz_signaled = any(t in iran_targets for t in ['hormuz', 'strait of hormuz', 'persian gulf'])
            if hormuz_signaled or (iran_score >= 60 and iran_irgc >= 3):
                iran_data['hormuz_pressure_active'] = True
                print(f"[Vietnam Rhetoric] Iran-Hormuz read: score={iran_score}, irgc=L{iran_irgc}")
            else:
                print(f"[Vietnam Rhetoric] Iran fingerprint quiet (score={iran_score}, irgc=L{iran_irgc})")
    except Exception as e:
        print(f"[Vietnam Rhetoric] Iran fingerprint read error: {str(e)[:80]}")
    return iran_data


def _write_vietnam_fingerprint(outbound_score, outbound_max, inbound_score,
                                inbound_max, overall_level, actor_results,
                                coercion_gap=0):
    """Write Vietnam fingerprint back to the shared cross-theater key so other
    trackers / the Asia BLUF / GPI / convergence registry can read Vietnam."""
    fingerprints = _redis_get(CROSSTHEATER_KEY) or {}

    fingerprints['vietnam'] = {
        'level':                overall_level,
        'outbound_score':       outbound_score,
        'outbound_max':         outbound_max,
        'outbound_max_level':   outbound_max,
        'inbound_score':        inbound_score,
        'inbound_max':          inbound_max,
        'inbound_max_level':    inbound_max,
        # SCS-specific actor levels
        'cpv_level':            actor_results.get('cpv_state', {}).get('level', 0),
        'mofa_level':           actor_results.get('mofa_diplomacy', {}).get('level', 0),
        'maritime_level':       actor_results.get('maritime_posture', {}).get('level', 0),
        'us_level':             actor_results.get('us_partnership', {}).get('level', 0),
        'us_alliance_level':    actor_results.get('us_partnership', {}).get('level', 0),
        'regional_level':       actor_results.get('regional_partners', {}).get('level', 0),
        'china_scs_level':      actor_results.get('china_scs_pressure', {}).get('level', 0),
        'beijing_coercion_level': actor_results.get('beijing_coercion', {}).get('level', 0),
        'economic_level':       actor_results.get('economic_pressure', {}).get('level', 0),
        'coercion_gap':         coercion_gap,
        # convergence flags for other consumers
        'is_absorber_node':     True,
        'is_command_node':      False,
        'label':                ESCALATION_LEVELS[overall_level]['label'],
        'updated_at':           datetime.now(timezone.utc).isoformat(),
    }

    _redis_set(CROSSTHEATER_KEY, fingerprints)
    print(f"[Vietnam Rhetoric] Vietnam fingerprint written (L{overall_level}, gap L{coercion_gap})")


# ============================================
# ARTICLE FETCHING
# ============================================

def _parse_pub_date(pub_str):
    if not pub_str:
        return None
    try:
        return datetime.fromisoformat(pub_str.replace('Z', '+00:00'))
    except Exception:
        pass
    try:
        return parsedate_to_datetime(pub_str).astimezone(timezone.utc)
    except Exception:
        pass
    try:
        clean = pub_str.replace('T', '').replace('Z', '').replace('-', '').replace(':', '').replace(' ', '')
        if len(clean) >= 14:
            return datetime.strptime(clean[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
        elif len(clean) == 8:
            return datetime.strptime(clean[:8], '%Y%m%d').replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def _fetch_rss(url, source_name, weight=0.85, max_items=20):
    articles = []
    try:
        resp = requests.get(url, timeout=12, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code != 200:
            print(f"[Vietnam RSS] {source_name}: HTTP {resp.status_code}")
            return []
        content = resp.content.lstrip(b'\xef\xbb\xbf').strip()
        root = ET.fromstring(content)
        for item in root.findall('.//item')[:max_items]:
            title_el = item.find('title')
            link_el  = item.find('link')
            pub_el   = item.find('pubDate')
            desc_el  = item.find('description')
            if title_el is None or not title_el.text:
                continue
            articles.append({
                'title':       title_el.text.strip(),
                'description': (desc_el.text or title_el.text or '')[:500] if desc_el is not None else '',
                'url':         link_el.text.strip() if link_el is not None and link_el.text else '',
                'publishedAt': pub_el.text if pub_el is not None else '',
                'source':      {'name': source_name},
                'content':     title_el.text.strip(),
                'source_weight_override': weight,
                'language':    'en',
            })
        print(f"[Vietnam RSS] {source_name}: {len(articles)} articles")
    except ET.ParseError as e:
        print(f"[Vietnam RSS] {source_name}: XML error: {str(e)[:80]}")
    except Exception as e:
        print(f"[Vietnam RSS] {source_name}: {str(e)[:80]}")
    return articles


def _fetch_gdelt(query, language='eng', days=3, max_records=25):
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
        if resp.status_code == 200:
            # 'vie' -> 'vi' added for Vietnamese-language GDELT articles
            lang_map = {'eng': 'en', 'zho': 'zh', 'jpn': 'ja', 'vie': 'vi'}
            for art in resp.json().get('articles', []):
                articles.append({
                    'title':       art.get('title', ''),
                    'description': art.get('title', ''),
                    'url':         art.get('url', ''),
                    'publishedAt': art.get('seendate', ''),
                    'source':      {'name': art.get('domain', f'GDELT ({language})')},
                    'content':     art.get('title', ''),
                    'language':    lang_map.get(language, language),
                })
            print(f"[Vietnam GDELT] {language}: {len(articles)} articles")
        else:
            print(f"[Vietnam GDELT] {language}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[Vietnam GDELT] {language}: {str(e)[:80]}")
    return articles


def _fetch_newsapi(query, days=3, max_results=30):
    """NewsAPI fallback when GDELT is rate-limited or timing out."""
    articles = []
    if not NEWSAPI_KEY:
        print("[Vietnam NewsAPI] No API key configured -- skipping")
        return []
    try:
        from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%Y-%m-%d')
        resp = requests.get(
            'https://newsapi.org/v2/everything',
            params={
                'q':        query,
                'from':     from_date,
                'sortBy':   'publishedAt',
                'language': 'en',
                'pageSize': max_results,
                'apiKey':   NEWSAPI_KEY,
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
                    'content':     a.get('content', '') or a.get('description', '') or '',
                    'language':    'en',
                })
            print(f"[Vietnam NewsAPI] '{query[:40]}': {len(articles)} articles")
        else:
            print(f"[Vietnam NewsAPI] HTTP {resp.status_code}")
    except Exception as e:
        print(f"[Vietnam NewsAPI] Error: {str(e)[:80]}")
    return articles


def _fetch_google_news_rss(query, label, lang='en', gl='US', max_items=15):
    articles = []
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl={lang}&gl={gl}&ceid={gl}:{lang}"
        resp = requests.get(url, timeout=12, headers={'User-Agent': 'Mozilla/5.0'})
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
                        'language':    lang,
                    })
        print(f"[Vietnam GNews] {label}: {len(articles)} articles")
    except Exception as e:
        print(f"[Vietnam GNews] {label}: {str(e)[:80]}")
    return articles


def _fetch_reddit(subreddits, keywords, days=3, max_per_sub=8):
    articles = []
    since = datetime.now(timezone.utc) - timedelta(days=days)
    for sub in subreddits:
        for kw in keywords[:2]:
            try:
                resp = requests.get(
                    f"https://www.reddit.com/r/{sub}/search.json",
                    params={'q': kw, 'sort': 'new', 't': 'week',
                            'limit': max_per_sub, 'restrict_sr': 'true'},
                    headers={'User-Agent': REDDIT_USER_AGENT},
                    timeout=10
                )
                if resp.status_code == 200:
                    for post in resp.json().get('data', {}).get('children', []):
                        p = post.get('data', {})
                        created  = p.get('created_utc', 0)
                        pub_time = datetime.fromtimestamp(created, tz=timezone.utc)
                        if pub_time >= since:
                            articles.append({
                                'title':       p.get('title', '')[:200],
                                'description': (p.get('selftext', '') or '')[:400],
                                'url':         f"https://www.reddit.com{p.get('permalink', '')}",
                                'publishedAt': pub_time.isoformat(),
                                'source':      {'name': f"r/{sub}"},
                                'content':     (p.get('selftext', '') or '')[:400],
                                'language':    'en',
                            })
                time.sleep(0.5)
            except Exception as e:
                print(f"[Vietnam Reddit] r/{sub}: {str(e)[:60]}")
    print(f"[Vietnam Reddit] {len(articles)} posts")
    return articles


# ============================================
# SOURCE WEIGHT HELPER
# ============================================

def _get_source_weight(source_name):
    premium = [
        'Reuters', 'AP News', 'Associated Press', 'BBC',
        'Financial Times', 'Wall Street Journal', 'The Economist',
        'USNI News', 'CSIS', 'CSIS AMTI',
        'South China Morning Post', 'Nikkei Asia', 'Vietnam News',
    ]
    high = [
        'VnExpress', 'Tuoi Tre', 'VietnamNet', 'The Diplomat',
        'Radio Free Asia', 'BenarNews', 'AEI', 'Brookings', 'RAND', 'IISS',
    ]
    src = source_name.lower()
    if any(p.lower() in src for p in premium):
        return 1.0
    if any(h.lower() in src for h in high):
        return 0.85
    if src.startswith('r/'):
        return 0.35
    if 'gdelt' in src:
        return 0.4
    return 0.55


# ============================================
# SCORING ENGINE
# ============================================

def _score_actor(actor_key, articles):
    """Score a single actor against trigger keywords (time-decay + source-weight)."""
    actor = ACTORS[actor_key]
    now   = datetime.now(timezone.utc)

    trigger_map = {
        'cpv_state':          CPV_STATE_TRIGGERS,
        'mofa_diplomacy':     MOFA_TRIGGERS,
        'maritime_posture':   MARITIME_TRIGGERS,
        'us_partnership':     US_PARTNERSHIP_TRIGGERS,
        'regional_partners':  REGIONAL_TRIGGERS,
        'china_scs_pressure': CHINA_SCS_TRIGGERS,
        'beijing_coercion':   BEIJING_COERCION_TRIGGERS,
        'economic_pressure':  ECONOMIC_PRESSURE_TRIGGERS,
    }.get(actor_key, {})

    matched_triggers = []
    top_articles     = []
    weighted_score   = 0.0
    article_count    = 0

    for article in articles:
        title   = (article.get('title', '') or '').lower()
        desc    = (article.get('description', '') or '').lower()
        content = (article.get('content', '') or '').lower()
        text    = f"{title} {desc} {content}"

        actor_kws = [kw.lower() for kw in actor['keywords']]
        if not any(kw in text for kw in actor_kws[:20]):
            continue

        # Time decay
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

        src_weight = article.get('source_weight_override',
                                 _get_source_weight(article.get('source', {}).get('name', '')))

        is_reporting = False
        if actor_key in REPORTING_ACTORS:
            if any(rl in text for rl in REPORTING_LANGUAGE):
                is_reporting = True
                src_weight *= 0.4

        article_level   = 0
        matched_trigger = None
        for level in [5, 4, 3, 2, 1]:
            for trigger in trigger_map.get(level, []):
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

        contribution    = article_level * decay * src_weight
        weighted_score += contribution
        article_count  += 1

        top_articles.append({
            'title':        article.get('title', '')[:150],
            'url':          article.get('url', ''),
            'source':       article.get('source', {}).get('name', ''),
            'publishedAt':  article.get('publishedAt', ''),
            'level':        article_level,
            'trigger':      matched_trigger,
            'contribution': round(contribution, 2),
            'is_reporting': is_reporting,
        })

    # Normalize to 0-5
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

    # Tripwire override
    for tripwire in actor.get('tripwires', []):
        for article in articles:
            text = (
                (article.get('title', '') or '') + ' ' +
                (article.get('description', '') or '')
            ).lower()
            if tripwire in text:
                level = max(level, 4)
                if tripwire not in matched_triggers:
                    matched_triggers.append(f"TRIPWIRE: {tripwire}")
                print(f"[Vietnam Rhetoric] TRIPWIRE: {actor_key} -> {tripwire}")
                break

    top_articles.sort(key=lambda x: x['contribution'], reverse=True)

    return {
        'actor':            actor_key,
        'name':             actor['name'],
        'flag':             actor['flag'],
        'icon':             actor['icon'],
        'color':            actor['color'],
        'dashboard':        actor['dashboard'],
        'role':             actor['role'],
        'description':      actor['description'],
        'level':            level,
        'level_label':      ESCALATION_LEVELS[level]['label'],
        'level_color':      ESCALATION_LEVELS[level]['color'],
        'weighted_score':   round(weighted_score, 2),
        'article_count':    article_count,
        'matched_triggers': matched_triggers[:10],
        'top_articles':     top_articles[:5],
    }


# ============================================
# COMPOSITE SCORING
# ============================================

def _compute_outbound_score(actor_results):
    """Compute Vietnam outbound score (0-100) -- sovereignty + response posture."""
    weights = {
        'cpv_state':          2.0,
        'mofa_diplomacy':     1.5,
        'maritime_posture':   2.5,   # the core SCS response vector
        'us_partnership':     2.5,
        'regional_partners':  1.0,
    }
    total_weight = sum(weights.values())
    weighted_sum = 0.0
    max_level    = 0

    for actor_key, weight in weights.items():
        level         = actor_results.get(actor_key, {}).get('level', 0)
        weighted_sum += level * weight
        max_level     = max(max_level, level)

    score = int((weighted_sum / (total_weight * 5)) * 100)

    # Convergence bonus: +8 if 3+ outbound actors at L3+
    elevated = sum(
        1 for k in weights
        if actor_results.get(k, {}).get('level', 0) >= 3
    )
    if elevated >= 3:
        score = min(100, score + 8)
        print(f"[Vietnam Rhetoric] Convergence bonus: {elevated} outbound actors at L3+")

    return score, max_level


def _compute_inbound_score(actor_results, china_fp=None):
    """Compute Vietnam inbound score (0-100) from the SCS article scan.
    Unlike Taiwan (which reads inbound primarily from the China fingerprint,
    where pla_level == pressure on Taiwan), Vietnam scans its own SCS-specific
    inbound actors directly. The China fingerprint adds optional context only.
    Returns (score, max_level, source_note)."""
    weights = {
        'china_scs_pressure': 3.0,
        'beijing_coercion':   2.0,
        'economic_pressure':  1.0,
    }
    total_weight = sum(weights.values())
    weighted_sum = 0.0
    max_level    = 0

    for actor_key, weight in weights.items():
        level         = actor_results.get(actor_key, {}).get('level', 0)
        weighted_sum += level * weight
        max_level     = max(max_level, level)

    score       = int((weighted_sum / (total_weight * 5)) * 100)
    source_note = 'scs_article_scan'

    # Optional context: if the China fingerprint shows broad assertiveness
    # (high MFA / PLA posture) while Vietnam's own SCS scan is quiet, nudge the
    # inbound score up modestly -- Beijing-wide posture is a leading indicator.
    if china_fp:
        china_mfa = int(china_fp.get('mfa_level', 0) or 0)
        china_pla = int(china_fp.get('pla_level', 0) or 0)
        china_ctx = max(china_mfa, china_pla)
        if china_ctx >= 4 and max_level < china_ctx:
            bumped = min(100, score + 6)
            print(f"[Vietnam Rhetoric] Inbound context bump from China fingerprint "
                  f"(MFA L{china_mfa}, PLA L{china_pla}): {score} -> {bumped}")
            score = bumped
            source_note = 'scs_article_scan+china_context'

    print(f"[Vietnam Rhetoric] Inbound from SCS scan: {score}/100 (max L{max_level})")
    return score, max_level, source_note


# ============================================
# MAIN SCAN
# ============================================

def run_vietnam_rhetoric_scan():
    """
    Full Vietnam SCS rhetoric scan. Reads cross-theater fingerprints, fetches
    all sources, scores all actors, computes the coercion-response gap, runs the
    interpreter, wires the butterfly + convergence proxies, and writes Redis.
    """
    scan_start = time.time()
    print(f"\n[Vietnam Rhetoric] Starting scan at {datetime.now(timezone.utc).isoformat()}")

    # Read cross-theater fingerprints FIRST
    china_fp  = _read_china_fingerprint()    # general Beijing posture context
    taiwan_fp = _read_taiwan_fingerprint()   # two-front convergence input
    iran_data = _read_iran_fingerprint()     # hormuz energy convergence input

    all_articles = []

    # RSS feeds
    for feed_key, feed_config in RSS_SOURCES.items():
        try:
            articles = _fetch_rss(
                feed_config['url'],
                feed_config['name'],
                weight=feed_config.get('weight', 0.85),
                max_items=20
            )
            all_articles.extend(articles)
            time.sleep(0.3)
        except Exception as e:
            print(f"[Vietnam RSS] {feed_key}: {str(e)[:80]}")

    # Google News RSS -- English
    gn_queries = [
        ('China coast guard Vietnam South China Sea Vanguard Bank', 'GNews:Vietnam Inbound EN'),
        ('Vietnam sovereignty Spratly navy coast guard', 'GNews:Vietnam Outbound EN'),
        ('US Vietnam defense partnership carrier Da Nang', 'GNews:US Vietnam EN'),
        ('Vietnam Philippines Japan India maritime cooperation', 'GNews:Vietnam Regional EN'),
    ]
    for query, label in gn_queries:
        try:
            all_articles.extend(_fetch_google_news_rss(query, label))
            time.sleep(0.3)
        except Exception as e:
            print(f"[Vietnam GNews] {label}: {str(e)[:60]}")

    # Google News RSS -- Vietnamese
    vi_queries = [
        ('Trung Quốc hải cảnh biển Đông bãi Tư Chính', 'GNews:Vietnam Inbound VI', 'vi', 'VN'),
        ('Việt Nam chủ quyền Trường Sa cảnh sát biển', 'GNews:Vietnam Outbound VI', 'vi', 'VN'),
    ]
    for query, label, lang, gl in vi_queries:
        try:
            all_articles.extend(_fetch_google_news_rss(query, label, lang=lang, gl=gl))
            time.sleep(0.3)
        except Exception as e:
            print(f"[Vietnam GNews VI] {label}: {str(e)[:60]}")

    # GDELT + NewsAPI fallback
    for query_key, query in GDELT_QUERIES.items():
        lang = 'vie' if query_key.startswith('vie') else 'eng'
        try:
            gdelt_results = _fetch_gdelt(query, language=lang, days=3)
            if gdelt_results:
                all_articles.extend(gdelt_results)
            elif lang == 'eng':
                print(f"[Vietnam GDELT] {query_key}: empty -- trying NewsAPI fallback")
                all_articles.extend(_fetch_newsapi(query, days=3))
            time.sleep(0.5)
        except Exception as e:
            print(f"[Vietnam GDELT] {query_key}: {str(e)[:60]}")
            if lang == 'eng':
                all_articles.extend(_fetch_newsapi(query, days=3))

    # Reddit
    reddit_keywords = ['Vietnam South China Sea', 'Vietnam coast guard', 'Vanguard Bank', 'Vietnam China']
    try:
        all_articles.extend(_fetch_reddit(REDDIT_SUBREDDITS, reddit_keywords, days=3))
    except Exception as e:
        print(f"[Vietnam Reddit]: {str(e)[:80]}")

    # Telegram
    if TELEGRAM_AVAILABLE:
        try:
            telegram_msgs = fetch_asia_telegram_signals(hours_back=72, include_extended=True)
            vietnam_kws = ['vietnam', 'việt nam', 'south china sea', 'biển đông',
                           'vanguard bank', 'spratly', 'paracel', 'hanoi', 'scs']
            tg_count = 0
            for msg in (telegram_msgs or []):
                txt = (msg.get('title', '') or '').lower()
                if any(kw in txt for kw in vietnam_kws):
                    all_articles.append({
                        'title':       msg.get('title', '')[:200],
                        'description': msg.get('title', '')[:500],
                        'url':         msg.get('url', ''),
                        'publishedAt': msg.get('published', ''),
                        'source':      {'name': msg.get('source', 'Telegram')},
                        'content':     msg.get('title', '')[:500],
                        'language':    'multi',
                    })
                    tg_count += 1
            print(f"[Vietnam Rhetoric] Telegram: {tg_count} relevant messages")
        except Exception as e:
            print(f"[Vietnam Rhetoric] Telegram error: {str(e)[:80]}")

    # Deduplicate by URL
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
    print(f"[Vietnam Rhetoric] Total articles after dedup: {len(all_articles)}")

    # Score all actors
    actor_results = {}
    for actor_key in ACTORS:
        try:
            actor_results[actor_key] = _score_actor(actor_key, all_articles)
            lvl = actor_results[actor_key]['level']
            print(f"[Vietnam Rhetoric] {actor_key}: L{lvl} ({ESCALATION_LEVELS[lvl]['label']})")
        except Exception as e:
            print(f"[Vietnam Rhetoric] Score error {actor_key}: {str(e)[:80]}")
            actor_results[actor_key] = {
                'actor': actor_key, 'level': 0,
                'level_label': 'Baseline', 'level_color': '#6b7280',
                'weighted_score': 0, 'article_count': 0,
                'matched_triggers': [], 'top_articles': [],
                **{k: ACTORS[actor_key][k] for k in
                   ['name', 'flag', 'icon', 'color', 'dashboard', 'role', 'description']},
            }

    # Composite scores
    outbound_score, outbound_max = _compute_outbound_score(actor_results)
    inbound_score, inbound_max, inbound_source = _compute_inbound_score(actor_results, china_fp)

    overall_level = max(outbound_max, inbound_max)
    overall_label = ESCALATION_LEVELS[overall_level]['label']
    scan_time     = round(time.time() - scan_start, 1)

    # ── Signal interpreter (Red Lines + Historical + So What) ──
    red_lines_triggered = []
    historical_matches  = []
    so_what             = {}
    coercion_gap        = 0
    if _INTERPRETER_AVAILABLE:
        try:
            def _lvl(key):
                return actor_results.get(key, {}).get('level', 0)
            _inbound  = max(_lvl('china_scs_pressure'), _lvl('beijing_coercion'), _lvl('economic_pressure'))
            _response = max(_lvl('maritime_posture'), _lvl('mofa_diplomacy'), _lvl('cpv_state'),
                            _lvl('us_partnership'), _lvl('regional_partners'))
            interp_vectors = {
                'inbound_pressure':  _inbound,
                'response_strength': _response,
                'partner_strength':  max(_lvl('us_partnership'), _lvl('regional_partners')),
                'coercion_gap':      max(0, _inbound - _response),
            }
            red_lines_triggered = check_red_lines(all_articles, actor_results)
            historical_matches  = build_historical_matches(actor_results, interp_vectors)
            so_what = build_so_what(
                {'actors': actor_results, 'articles': all_articles},
                red_lines_triggered, historical_matches
            )
            coercion_gap = so_what.get('coercion_gap', interp_vectors['coercion_gap'])
            print(f"[Vietnam Rhetoric] Interpreter: {len(red_lines_triggered)} red lines, "
                  f"coercion_gap L{coercion_gap}, "
                  f"scenario: {so_what.get('scenario_icon','')} {so_what.get('scenario','')[:40]}")
        except Exception as e:
            print(f"[Vietnam Rhetoric] Interpreter error: {e}")

    # Write Vietnam fingerprint (after we have coercion_gap)
    _write_vietnam_fingerprint(
        outbound_score, outbound_max, inbound_score,
        inbound_max, overall_level, actor_results, coercion_gap=coercion_gap
    )

    # ── Cross-theater amplifiers (read by interpreter convergence injection) ──
    us_lvl       = actor_results.get('us_partnership', {}).get('level', 0)
    regional_lvl = actor_results.get('regional_partners', {}).get('level', 0)
    china_scs_lvl = actor_results.get('china_scs_pressure', {}).get('level', 0)
    taiwan_inbound = int(taiwan_fp.get('inbound_max_level', taiwan_fp.get('inbound_max', 0)) or 0) if taiwan_fp else 0

    crosstheater_amplifiers = {
        # Iran / Hormuz energy convergence
        'iran_hormuz_pressure': iran_data.get('hormuz_pressure_active', False),
        'iran_theatre_score':   iran_data.get('theatre_score', 0),
        'iran_irgc_level':      iran_data.get('irgc_level', 0),
        # Indo-Pacific partnership convergence
        'partner_outbound_max': max(us_lvl, regional_lvl),
        'indo_pacific_active':  (us_lvl >= 2 and regional_lvl >= 2),
        # China two-front convergence (Taiwan + SCS)
        'taiwan_inbound_max':   taiwan_inbound,
        'china_scs_level':      china_scs_lvl,
    }

    result = {
        'success':           True,
        'scanned_at':        datetime.now(timezone.utc).isoformat(),
        'scan_time_seconds': scan_time,
        'total_articles':    len(all_articles),

        # Dual dashboard
        'outbound_score':     outbound_score,
        'outbound_max_level': outbound_max,
        'inbound_score':      inbound_score,
        'inbound_max_level':  inbound_max,
        'inbound_source':     inbound_source,

        # Overall
        'overall_level': overall_level,
        'overall_label': overall_label,
        'overall_color': ESCALATION_LEVELS[overall_level]['color'],
        'theatre_score': outbound_score,

        # Actor breakdown
        'actors': actor_results,

        # Component levels for the stability-page card (Vietnam-native naming)
        'cpv_level':       actor_results.get('cpv_state', {}).get('level', 0),
        'mofa_level':      actor_results.get('mofa_diplomacy', {}).get('level', 0),
        'maritime_level':  actor_results.get('maritime_posture', {}).get('level', 0),
        'us_level':        actor_results.get('us_partnership', {}).get('level', 0),
        'regional_level':  actor_results.get('regional_partners', {}).get('level', 0),
        'china_scs_level': actor_results.get('china_scs_pressure', {}).get('level', 0),
        'beijing_coercion_level': actor_results.get('beijing_coercion', {}).get('level', 0),
        'economic_level':  actor_results.get('economic_pressure', {}).get('level', 0),

        # China fingerprint context (pass-through)
        'china_overall_level':   china_fp.get('level', 0) if china_fp else 0,
        'china_mfa_level':       china_fp.get('mfa_level', 0) if china_fp else 0,
        'china_pla_level':       china_fp.get('pla_level', 0) if china_fp else 0,
        'china_fingerprint_age': china_fp.get('updated_at', '') if china_fp else '',

        # Interpreter output
        'red_lines':          red_lines_triggered,
        'historical_matches': historical_matches,
        'so_what':            so_what,
        'coercion_gap':       coercion_gap,

        'escalation_levels': ESCALATION_LEVELS,
        'crosstheater_amplifiers': crosstheater_amplifiers,
        'version':           '1.0.0-vietnam',
    }

    # Build top_signals (needs the assembled result), then BLUF + Watch from it
    top_signals = []
    if _INTERPRETER_AVAILABLE:
        try:
            top_signals = build_top_signals(result)
            print(f"[Vietnam Rhetoric] top_signals: {len(top_signals)} emitted")
        except Exception as e:
            print(f"[Vietnam Rhetoric] build_top_signals error: {e}")
            top_signals = []
    result['top_signals'] = top_signals

    if _INTERPRETER_AVAILABLE:
        try:
            result['bluf'] = build_bluf(result)
            result['watch_indicators'] = build_watch_indicators(result)
        except Exception as e:
            print(f"[Vietnam Rhetoric] build_bluf/watch error: {e}")
            result['bluf'] = ''
            result['watch_indicators'] = ''

    # ── Butterfly proxy: upstream stressors from ME via Asia proxy ──
    if _BUTTERFLY_AVAILABLE:
        try:
            bundle = read_butterfly_signals_via_proxy('vietnam')
            result['butterfly'] = {
                'upstream_stressors':     bundle.get('upstream_stressors', []),
                'context_notes':          bundle.get('context_notes', []),
                'amplifier_actor_deltas': bundle.get('amplifier_actor_deltas', {}),
                'success':                bundle.get('success', False),
            }
            print(f"[Vietnam Rhetoric] Butterfly: "
                  f"{len(result['butterfly']['upstream_stressors'])} upstream stressors, "
                  f"{len(result['butterfly']['context_notes'])} notes")
        except Exception as e:
            print(f"[Vietnam Rhetoric] Butterfly proxy error: {str(e)[:80]}")
            result['butterfly'] = {}
    else:
        result['butterfly'] = {}

    # ── Convergence proxy: ME-registered convergences relevant to Vietnam ──
    if _CONVERGENCE_PROXY_AVAILABLE:
        try:
            ext = find_convergences_for_country_proxy('vietnam') or []
            result['external_convergences'] = ext
            print(f"[Vietnam Rhetoric] External convergences: {len(ext)}")
        except Exception as e:
            print(f"[Vietnam Rhetoric] Convergence proxy error: {str(e)[:80]}")
            result['external_convergences'] = []
    else:
        result['external_convergences'] = []

    # Cache to Redis
    _redis_set(RHETORIC_CACHE_KEY, result)
    _redis_set(RHETORIC_CACHE_KEY_LEGACY, result)

    # History snapshot
    _redis_lpush_trim(HISTORY_KEY, {
        'ts':             datetime.now(timezone.utc).isoformat(),
        'outbound_score': outbound_score,
        'inbound_score':  inbound_score,
        'level':          overall_level,
        'label':          overall_label,
        'coercion_gap':   coercion_gap,
        'china_scs_level': china_scs_lvl,
        'maritime_level': actor_results.get('maritime_posture', {}).get('level', 0),
        'us_level':       us_lvl,
    })

    print(f"[Vietnam Rhetoric] Scan complete in {scan_time}s | "
          f"Outbound L{outbound_max} ({outbound_score}/100) | "
          f"Inbound L{inbound_max} ({inbound_score}/100) [{inbound_source}] | "
          f"Coercion gap L{coercion_gap}")

    return result


# ============================================
# BACKGROUND REFRESH
# ============================================

def _background_scan_loop():
    """Background thread: refresh Vietnam SCS rhetoric every 6 hours."""
    print("[Vietnam Rhetoric] Background thread started (6h cycle)")
    # Stagger boot so Vietnam starts AFTER China + Taiwan write their fingerprints
    # (china_two_front_convergence reads the Taiwan fingerprint).
    time.sleep(200)
    while True:
        try:
            run_vietnam_rhetoric_scan()
        except Exception as e:
            print(f"[Vietnam Rhetoric] Background scan error: {str(e)[:200]}")
        time.sleep(SCAN_INTERVAL_HOURS * 3600)


# ============================================
# FLASK ENDPOINT REGISTRATION
# ============================================

def register_vietnam_rhetoric_endpoints(app):
    """Register Vietnam SCS rhetoric endpoints on the Flask app."""

    @app.route('/api/rhetoric/vietnam', methods=['GET'])
    def api_vietnam_rhetoric():
        """
        Vietnam South China Sea tracker -- dual dashboard.
        Outbound: Is Vietnam asserting/defending SCS sovereignty?
        Inbound:  What is China doing in the SCS against Vietnam?
        ?force=true to bypass cache and run a fresh scan.
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
                    cached['from_cache'] = True
                    cached['scan_in_progress'] = True
                    return jsonify(cached)
                return jsonify({'success': False, 'error': 'Scan in progress'}), 202
            _rhetoric_running = True

        try:
            result = run_vietnam_rhetoric_scan()
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200]}), 500
        finally:
            with _rhetoric_lock:
                _rhetoric_running = False

    @app.route('/api/rhetoric/vietnam/summary', methods=['GET'])
    def api_vietnam_rhetoric_summary():
        """Lightweight summary -- scores, levels, BLUF + watch for the card."""
        cached = _redis_get(RHETORIC_CACHE_KEY)
        if not cached:
            return jsonify({
                'success': False,
                'error': 'No data yet -- run /api/rhetoric/vietnam?force=true'
            }), 404
        return jsonify({
            'success':            True,
            'scanned_at':         cached.get('scanned_at'),
            'overall_level':      cached.get('overall_level', 0),
            'overall_label':      cached.get('overall_label', 'Baseline'),
            'overall_color':      cached.get('overall_color', '#6b7280'),
            'outbound_score':     cached.get('outbound_score', 0),
            'outbound_max_level': cached.get('outbound_max_level', 0),
            'inbound_score':      cached.get('inbound_score', 0),
            'inbound_max_level':  cached.get('inbound_max_level', 0),
            'inbound_source':     cached.get('inbound_source', 'unknown'),
            # Vietnam-native actor levels
            'cpv_level':          cached.get('cpv_level', 0),
            'mofa_level':         cached.get('mofa_level', 0),
            'maritime_level':     cached.get('maritime_level', 0),
            'us_level':           cached.get('us_level', 0),
            'regional_level':     cached.get('regional_level', 0),
            'china_scs_level':    cached.get('china_scs_level', 0),
            'china_overall_level': cached.get('china_overall_level', 0),
            'total_articles':     cached.get('total_articles', 0),
            # Gold Standard card native fields
            'bluf':               cached.get('bluf', ''),
            'watch_indicators':   cached.get('watch_indicators', ''),
            # Interpreter summary
            'red_lines_count':    len(cached.get('red_lines', [])),
            'scenario':           (cached.get('so_what') or {}).get('scenario', ''),
            'scenario_icon':      (cached.get('so_what') or {}).get('scenario_icon', ''),
            'scenario_color':     (cached.get('so_what') or {}).get('scenario_color', '#6b7280'),
            'response_strength':  (cached.get('so_what') or {}).get('response_strength', 0),
            'inbound_pressure':   (cached.get('so_what') or {}).get('inbound_pressure', 0),
            'partner_strength':   (cached.get('so_what') or {}).get('partner_strength', 0),
            'coercion_gap':       cached.get('coercion_gap', 0),
            'version':            '1.0.0-vietnam',
        })

    @app.route('/api/rhetoric/vietnam/history', methods=['GET'])
    def api_vietnam_rhetoric_history():
        """Return rhetoric history for chart rendering."""
        history = _redis_get(HISTORY_KEY)
        if not isinstance(history, list):
            history = []
        return jsonify({
            'success': True,
            'count':   len(history),
            'history': history[:120],
        })

    # Start background refresh thread -- staggered after China + Taiwan (200s)
    bg = threading.Thread(target=_background_scan_loop, daemon=True)
    bg.start()

    print("[Vietnam Rhetoric] Endpoints registered: "
          "/api/rhetoric/vietnam, /api/rhetoric/vietnam/summary, /api/rhetoric/vietnam/history")
