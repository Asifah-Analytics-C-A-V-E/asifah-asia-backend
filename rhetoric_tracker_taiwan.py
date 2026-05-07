"""
Asifah Analytics -- Taiwan Rhetoric & Deterrence Tracker
v1.0.0 -- March 2026

ANALYTICAL FRAME:
This tracker answers the mirror question to rhetoric_tracker_china.py:

  "How is Taiwan and its coalition responding to Chinese coercion --
   and is Taiwan's own posture hardening in ways that could trigger
   a PLA response cycle?"

Taiwan is not a passive actor. Lai Ching-te independence language,
US arms deals, senior US official visits to Taipei, and Japan naming
Taiwan as a security concern all TRIGGER PLA exercise response cycles.
This tracker catches both the defensive deterrence posture AND the
inadvertent escalation signals from the Taiwan side.

DUAL DASHBOARD:

  OUTBOUND -- "Is Taiwan hardening its posture / triggering PLA response?"
    Tracks: Presidential independence signals (Lai Ching-te),
            ROC defense budget / capability announcements,
            US arms acquisition signals,
            Diplomatic recognition pushes / foreign visits,
            Taiwan asymmetric warfare posture

  INBOUND -- "What is the PLA / Beijing signaling at Taiwan right now?"
    READS China rhetoric fingerprint from Redis (written by rhetoric_tracker_china.py)
    Also tracks: PLA ADIZ violations (raw count from Taiwan MND),
                 PLA exercise announcements targeting Taiwan,
                 Beijing coercion signals (TAO, MFA) directed at Taiwan,
                 Economic coercion signals

  The INBOUND dashboard is the cross-theater integration layer --
  Taiwan's inbound IS China's outbound. We don't re-scan for it;
  we read the fingerprint China already wrote.

FIVE OUTBOUND VECTORS (Taiwan side):
  1. LAI / PRESIDENTIAL     -- independence language, status quo signals,
                               provocation language that triggers PLA
  2. ROC DEFENSE POSTURE    -- defense budget, capability, readiness signals
  3. US PARTNERSHIP         -- arms acquisition, joint exercises, US visits
  4. DIPLOMATIC POSTURE     -- recognition pushes, international space signals,
                               UN bids, foreign minister visits
  5. ASYMMETRIC / RESILIENCE -- civilian defense, drone program, reserve reform,
                               civil defense buildup signals

FOUR INBOUND VECTORS (China pressure on Taiwan):
  1. PLA DIRECT PRESSURE    -- read from China fingerprint (pla_level)
  2. XI / CMC SIGNALS       -- read from China fingerprint (xi_level)
  3. ECONOMIC COERCION      -- read from China fingerprint (econ_level)
  4. TAO / MFA PRESSURE     -- read from China fingerprint (mfa_level + tao_level)

SCORING:
  Outbound weights:
    Lai/Presidential    3.0 (independence language = primary PLA trigger)
    ROC Defense         2.0
    US Partnership      2.5 (US visits/arms = guaranteed PLA response cycle)
    Diplomatic Posture  1.5
    Asymmetric          1.0
  Inbound:
    Computed from China fingerprint Redis read -- no independent scan needed

TRIPWIRES -- Taiwan side (auto-escalate to L4):
  - Lai Ching-te uses "Taiwan is a country" / "two states" language
  - Senior US Cabinet official visits Taipei
  - Taiwan declares independence formally
  - Taiwan US defense treaty announced
  - Taiwan requests UN General Assembly seat
  - Taiwan-Japan mutual defense commitment announced

SOURCE STRATEGY:
  Primary RSS:  Focus Taiwan (CNA), Taipei Times, Taiwan News,
                Taiwan MND ADIZ reports, USNI News (US commitment),
                Nikkei Asia (Japan-Taiwan), SCMP (China reaction)
  Secondary:    GDELT (eng, zho traditional), Google News RSS (EN + ZH-TW)
  Reddit:       r/taiwan, r/Taiwanese, r/CredibleDefense, r/geopolitics,
                r/LessCredibleDefence, r/GlobalPowers, r/Sino,
                r/anime_titties, r/Japan, r/Philippines
  Telegram:     Routed through telegram_signals_asia shared cache
  Cross-theater: READS rhetoric:crosstheater:fingerprints (China key)

REDIS KEYS:
  Cache:         rhetoric:taiwan:latest
  Legacy:        taiwan_rhetoric_cache
  History:       rhetoric:taiwan:history
  Cross-theater: rhetoric:crosstheater:fingerprints (READS china key,
                 WRITES taiwan key)

ENDPOINTS:
  GET /api/rhetoric/taiwan
  GET /api/rhetoric/taiwan/summary
  GET /api/rhetoric/taiwan/history

CHANGELOG:
  v1.0.0 (2026-03-24): Initial build -- mirror dual dashboard,
                        cross-theater Redis integration with China tracker

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

# Signal interpreter (Red Lines + Historical + So What)
try:
    from taiwan_signal_interpreter import (
        check_red_lines,
        build_so_what,
        build_historical_matches,
        build_top_signals,
    )
    _INTERPRETER_AVAILABLE = True
    print("[Taiwan Rhetoric] Signal interpreter loaded")
except ImportError as e:
    print(f"[Taiwan Rhetoric] WARNING: taiwan_signal_interpreter not available ({e})")
    _INTERPRETER_AVAILABLE = False

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
    print("[Taiwan Rhetoric] Telegram signals available")
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[Taiwan Rhetoric] Telegram signals not available -- RSS/GDELT only")

RHETORIC_CACHE_KEY        = 'rhetoric:taiwan:latest'
RHETORIC_CACHE_KEY_LEGACY = 'taiwan_rhetoric_cache'
HISTORY_KEY               = 'rhetoric:taiwan:history'
CROSSTHEATER_KEY          = 'rhetoric:crosstheater:fingerprints'

RHETORIC_CACHE_TTL  = 6 * 3600
SCAN_INTERVAL_HOURS = 6

_rhetoric_running = False
_rhetoric_lock    = threading.Lock()


# ============================================
# ESCALATION LEVELS
# ============================================
ESCALATION_LEVELS = {
    0: {'label': 'Baseline',        'color': '#6b7280', 'description': 'Normal defense posture, no significant signals'},
    1: {'label': 'Rhetoric',        'color': '#3b82f6', 'description': 'Standard defense statements, routine US engagement'},
    2: {'label': 'Warning',         'color': '#f59e0b', 'description': 'Elevated defense signals, arms acquisition, mild provocation'},
    3: {'label': 'Confrontation',   'color': '#f97316', 'description': 'Defense budget surge, senior US visit, Lai independence signals'},
    4: {'label': 'High Alert',      'color': '#ef4444', 'description': 'Major US arms deal, Taiwan-US defense commitment, formal independence push'},
    5: {'label': 'Active Conflict', 'color': '#dc2626', 'description': 'Independence declaration, full mobilization, active hostilities'},
}


# ============================================
# ACTORS
# ============================================
ACTORS = {

    # ── OUTBOUND ACTORS (Taiwan-side signals) ────────────────────

    'lai_presidential': {
        'name': 'Lai Ching-te / Presidential Office',
        'flag': '🇹🇼',
        'icon': '👁️',
        'color': '#dc2626',
        'dashboard': 'outbound',
        'role': 'Presidential Authorization / Independence Signals',
        'description': 'Lai Ching-te is the primary PLA trigger on the Taiwan side. Independence-adjacent language from the Presidential Office almost always generates a PLA exercise response cycle within days.',
        'keywords': [
            # Lai direct
            'lai ching-te', 'lai chingte', 'lai president taiwan',
            'taiwan president warns', 'taiwan president says',
            'taiwan president military', 'roc president',
            # Independence signals -- the primary PLA trigger
            'taiwan is a country', 'taiwan sovereign state',
            'two states', 'two countries', 'taiwan independence',
            'declare independence', 'independence referendum',
            'taiwan not part of china', 'taiwan separate nation',
            'taiwan self-determination', 'taiwan status quo',
            'taiwan sovereignty', 'maintain taiwan sovereignty',
            # Lai specific provocation language
            'lai separatist', 'lai independence speech',
            'lai warns china', 'lai on reunification',
            'lai rejects reunification', 'lai rejects one china',
            'lai one china', 'taiwan two states theory',
            # Presidential office general
            'presidential office taiwan', 'taipei presidential',
            'taiwan government warns', 'taiwan government says',
            # Traditional Chinese
            '賴清德', '台灣總統', '台獨',
            '兩國論', '台灣主權', '台灣獨立',
            '總統府', '台灣是主權國家',
        ],
        'baseline_statements_per_week': 5,
        'tripwires': [
            'taiwan is a country',
            'two states',
            'declare independence',
            'taiwan not part of china',
            'lai two states',
            'independence referendum',
        ],
    },

    'roc_defense': {
        'name': 'ROC Defense Posture',
        'flag': '🇹🇼',
        'icon': '⚔️',
        'color': '#b91c1c',
        'dashboard': 'outbound',
        'role': 'Military Readiness / Capability Signals',
        'description': 'ROC MND defense posture signals -- budget announcements, capability acquisitions, readiness changes, conscription reform. Rising defense investment signals Taiwan hardening for a long conflict.',
        'keywords': [
            # Defense budget
            'taiwan defense budget', 'taiwan military spending',
            'taiwan gdp defense', 'taiwan 3 percent defense',
            'taiwan defense increase', 'taiwan special defense budget',
            'taiwan arms procurement', 'taiwan weapons budget',
            # Capability signals
            'taiwan patriot', 'taiwan himars', 'taiwan f-16',
            'taiwan submarine', 'taiwan hai kun',
            'taiwan drone program', 'taiwan drone',
            'taiwan missile', 'taiwan harpoon',
            'taiwan stinger', 'taiwan javelin',
            'taiwan asymmetric warfare', 'taiwan porcupine',
            'taiwan overall defense concept', 'odc taiwan',
            # Readiness / mobilization
            'taiwan military exercise', 'han kuang',
            'taiwan combat readiness', 'taiwan reserve reform',
            'taiwan conscription', 'taiwan extended conscription',
            'taiwan mobilization', 'taiwan civil defense',
            'taiwan wartime', 'taiwan full-scale exercise',
            # JSDF / US joint exercises
            'taiwan us joint exercise', 'taiwan japan exercise',
            'taiwan us training', 'taiwan military cooperation',
            # MND official statements
            'taiwan mnd', 'taiwan defense ministry',
            'taiwan ministry defense', 'taiwan armed forces',
            'taiwan military', 'republic of china military',
            'roc military', 'roc armed forces',
            # Traditional Chinese
            '台灣國防部', '國防預算', '漢光演習',
            '台灣軍事', '兵役', '國軍', '海鯤',
        ],
        'baseline_statements_per_week': 10,
        'tripwires': [
            'han kuang exercise',
            'taiwan extends conscription',
            'taiwan emergency mobilization',
            'taiwan declares emergency',
        ],
    },

    'us_partnership': {
        'name': 'US-Taiwan Partnership',
        'flag': '🇺🇸',
        'icon': '🤝',
        'color': '#1d4ed8',
        'dashboard': 'outbound',
        'role': 'US Arms / Visits / Commitments -- Primary PLA Trigger',
        'description': 'US-Taiwan relationship signals. Every senior US official visit to Taipei and every major arms sale approval triggers a PLA exercise response cycle. This actor captures the signals that Beijing is watching most closely.',
        'keywords': [
            # US official visits -- each one triggers a PLA response
            'us official visits taipei', 'us senator taiwan',
            'us congressman taiwan', 'us secretary taiwan',
            'us cabinet taiwan', 'us official taipei',
            'pelosi taiwan', 'us delegation taiwan',
            'us lawmaker taiwan', 'us military delegation taiwan',
            # Arms sales -- specific systems that change calculus
            'us arms sale taiwan', 'us weapons taiwan',
            'taiwan arms sale approved', 'f-16 taiwan sale',
            'taiwan m1 abrams', 'taiwan stinger sale',
            'taiwan harpoon sale', 'taiwan himars sale',
            'taiwan patriot sale', 'taiwan javelin sale',
            'taiwan submarine sale', 'us taiwan arms',
            # Joint defense / treaty language
            'us taiwan defense treaty', 'us taiwan mutual defense',
            'us taiwan alliance', 'us committed taiwan',
            'us defend taiwan', 'us would defend taiwan',
            'biden defend taiwan', 'trump taiwan defense',
            'us taiwan relations act', 'tra invoked',
            # Taiwan Relations Act / TAIPEI Act
            'taiwan relations act', 'taipei act',
            'us taiwan security commitment',
            # Military cooperation
            'us taiwan joint exercise', 'us taiwan military cooperation',
            'us military advisor taiwan', 'us troops taiwan',
            'us taiwan military training',
            # Intelligence / tech sharing
            'us taiwan intelligence', 'us taiwan technology',
            'us taiwan chip cooperation', 'tsmc us',
            # Traditional Chinese
            '美台軍售', '美台關係', '台灣關係法',
            '美國訪台', '美台防衛', '聯合演習',
        ],
        'baseline_statements_per_week': 6,
        'tripwires': [
            'us official visits taipei',
            'us cabinet official taipei',
            'us taiwan defense treaty',
            'us troops taiwan deployed',
            'us taiwan mutual defense announced',
        ],
    },

    'diplomatic_posture': {
        'name': 'Taiwan Diplomatic Posture',
        'flag': '🇹🇼',
        'icon': '🌐',
        'color': '#0891b2',
        'dashboard': 'outbound',
        'role': 'International Space / Recognition Pushes',
        'description': 'Taiwan international space signals -- formal diplomatic recognition gains, UN participation pushes, foreign minister visits. Beijing responds aggressively to any expansion of Taiwan\'s international space.',
        'keywords': [
            # Diplomatic recognition
            'taiwan diplomatic recognition', 'recognizes taiwan',
            'country recognizes taiwan', 'establishes relations taiwan',
            'taiwan formal relations', 'taiwan ally',
            'taiwan loses ally', 'switches recognition taiwan',
            'taiwan only has', 'taiwan allies',
            # UN / multilateral
            'taiwan un bid', 'taiwan united nations',
            'taiwan who participation', 'taiwan icao',
            'taiwan international organizations',
            'meaningful participation taiwan',
            # Foreign minister / visits
            'taiwan foreign minister', 'joseph wu',
            'taiwan mofa', 'taiwan diplomat',
            'foreign official visits taiwan',
            'eu taiwan', 'europe taiwan relations',
            'g7 taiwan', 'nato taiwan',
            'india taiwan', 'czech taiwan',
            'lithuania taiwan',
            # Pacific allies
            'taiwan pacific ally', 'palau taiwan',
            'marshall islands taiwan', 'tuvalu taiwan',
            # Trade agreements
            'taiwan trade agreement', 'taiwan fta',
            'taiwan us trade', 'taiwan eu trade',
            # Traditional Chinese
            '台灣外交', '台灣邦交', '外交部',
            '台灣國際空間', '邦交國',
        ],
        'baseline_statements_per_week': 4,
        'tripwires': [
            'taiwan requests un membership',
            'major country recognizes taiwan',
            'taiwan eu formal relations',
            'g7 taiwan security commitment',
        ],
    },

    'asymmetric_resilience': {
        'name': 'Asymmetric / Civil Defense',
        'flag': '🇹🇼',
        'icon': '🛡️',
        'color': '#7c3aed',
        'dashboard': 'outbound',
        'role': 'Porcupine Strategy / Civil Defense / Resilience Signals',
        'description': 'Taiwan asymmetric warfare and civil defense buildup. The "porcupine strategy" -- making Taiwan too costly to invade -- is a deterrence signal that also raises Beijing\'s perception of the cost of action.',
        'keywords': [
            # Asymmetric / porcupine
            'taiwan porcupine strategy', 'overall defense concept',
            'taiwan asymmetric', 'taiwan guerrilla',
            'taiwan drone swarm', 'taiwan unmanned',
            'taiwan sea mines', 'taiwan anti-ship',
            'taiwan mobile missile', 'taiwan dispersal',
            # Civil defense
            'taiwan civil defense', 'taiwan air raid drill',
            'taiwan bomb shelter', 'taiwan emergency drill',
            'taiwan evacuation drill', 'taiwan blackout drill',
            'taiwan wartime drill', 'taiwan resilience',
            # Reserve / manpower reform
            'taiwan reserve reform', 'taiwan reserve training',
            'taiwan conscription extension', 'taiwan one year service',
            'taiwan military training extended',
            # Infrastructure resilience
            'taiwan underground base', 'taiwan hardened',
            'taiwan dispersed basing', 'taiwan survivability',
            'taiwan critical infrastructure',
            # Domestic production
            'taiwan indigenous defense', 'taiwan domestic weapons',
            'taiwan domestic submarine', 'taiwan indigenous fighter',
            'taiwan ching-kuo', 'taiwan jet production',
            # Traditional Chinese
            '台灣不對稱', '全民防衛', '民防',
            '防空演習', '避難演習', '後備軍',
        ],
        'baseline_statements_per_week': 3,
        'tripwires': [
            'taiwan nationwide civil defense drill',
            'taiwan activates reserve forces',
            'taiwan emergency shelter order',
        ],
    },

    # ── INBOUND ACTORS (China pressure -- read from Redis fingerprint) ──

    'pla_pressure': {
        'name': 'PLA Direct Pressure',
        'flag': '🇨🇳',
        'icon': '⚔️',
        'color': '#dc2626',
        'dashboard': 'inbound',
        'role': 'PLA Exercise / ADIZ / Operational Pressure on Taiwan',
        'description': 'PLA operational pressure on Taiwan -- read primarily from China rhetoric tracker fingerprint (pla_level). Also supplemented by Taiwan MND ADIZ reports.',
        'keywords': [
            # These are for the supplemental article scan only --
            # primary data comes from China fingerprint
            'pla exercise taiwan', 'pla drills taiwan',
            'pla aircraft taiwan', 'median line crossing',
            'adiz violation taiwan', 'pla bomber taiwan',
            'pla carrier taiwan', 'eastern theater taiwan',
            'pla encircles taiwan', 'pla blockade',
            'joint sword', 'strait thunder', 'justice mission',
            '解放军台湾', '东部战区', '共机扰台', '联合利剑',
        ],
        'baseline_statements_per_week': 15,
        'tripwires': [
            'joint sword',
            'strait thunder',
            'pla live fire taiwan',
            'pla encircles taiwan',
        ],
    },

    'beijing_coercion': {
        'name': 'Beijing Political Coercion',
        'flag': '🇨🇳',
        'icon': '📢',
        'color': '#7c3aed',
        'dashboard': 'inbound',
        'role': 'Xi / MFA / TAO Coercion Directed at Taiwan',
        'description': 'Beijing political coercion signals directed at Taiwan -- Xi authorization language, MFA threats, TAO pressure. Read primarily from China fingerprint (xi_level, mfa_level, tao_level).',
        'keywords': [
            'xi jinping warns taiwan', 'beijing warns taiwan',
            'china threatens taiwan', 'mfa warns taiwan',
            'tao warns taiwan', 'tao warns separatists',
            'independence means war', 'china will reunify',
            'china warns us taiwan', 'reunification by force',
            'shoot fish in a barrel', 'firepower package',
            '习近平警告台湾', '北京警告台湾', '独立即战争',
        ],
        'baseline_statements_per_week': 12,
        'tripwires': [
            'independence means war',
            'reunification by force',
            'shoot fish in a barrel',
        ],
    },

    'economic_pressure': {
        'name': 'China Economic Pressure',
        'flag': '🇨🇳',
        'icon': '💹',
        'color': '#d97706',
        'dashboard': 'inbound',
        'role': 'Trade Bans / Rare Earth / Financial Pressure on Taiwan',
        'description': 'China economic coercion directed at Taiwan and its coalition partners. Read primarily from China fingerprint (econ_level). Semiconductor and rare earth signals are particularly significant.',
        'keywords': [
            'china bans taiwan', 'china trade ban taiwan',
            'china sanctions taiwan', 'china rare earth taiwan',
            'china chip ban taiwan', 'china economic pressure taiwan',
            'tsmc china threat', 'china blockade taiwan economy',
            'china financial pressure taiwan',
            '对台贸易限制', '经济制裁台湾', '稀土台湾',
        ],
        'baseline_statements_per_week': 4,
        'tripwires': [
            'china blockades taiwan ports',
            'rare earth total ban taiwan',
            'china seizes tsmc',
        ],
    },
}


# ============================================
# REPORTING ACTORS (language discounted)
# ============================================
# Inbound actors report ON Chinese actions rather than initiating threats.
# Discount their rhetoric scores to avoid inflating the inbound dashboard.
REPORTING_ACTORS = {'pla_pressure', 'beijing_coercion', 'economic_pressure'}

REPORTING_LANGUAGE = [
    'condemns', 'condemned', 'protests', 'denounces',
    'calls on', 'urges', 'expresses concern', 'deeply concerned',
    'in response to', 'following the drills', 'following the exercise',
    'according to', 'reports that', 'monitors', 'tracks',
    'detected', 'observed', 'confirmed', 'taiwan mnd says',
    '谴责', '抗议', '关切', '台灣國防部表示',
]


# ============================================
# THREAT VECTORS -- OUTBOUND (Taiwan)
# ============================================

LAI_TRIGGERS = {
    5: [
        'taiwan declares independence', 'formal independence declaration',
        'taiwan is a sovereign nation', 'two states officially',
        'end one china policy', 'taiwan nation state',
        '台灣宣布獨立', '正式宣布台獨',
    ],
    4: [
        'taiwan is a country', 'two states theory',
        'two countries theory', 'lai two states',
        'independence referendum', 'taiwan not part of china',
        'taiwan separate nation', 'taiwan self-determination',
        'lai rejects one china', 'lai rejects reunification',
        '兩國論', '台灣是國家', '公投獨立',
    ],
    3: [
        'lai independence speech', 'lai warns china',
        'taiwan sovereignty', 'maintain taiwan sovereignty',
        'taiwan status quo', 'taiwan democratic',
        'lai ching-te warns', 'taiwan resilience',
        'taiwan determination', 'taiwan will defend',
        '台灣主權', '賴清德警告', '台灣堅定',
    ],
    2: [
        'lai ching-te says', 'taiwan president',
        'presidential office taiwan', 'taipei says',
        'taiwan government', 'roc president',
        '賴清德', '台灣總統府',
    ],
    1: [
        'lai ching-te', 'taiwan president', 'taipei',
        '賴清德', '台北',
    ],
}

ROC_DEFENSE_TRIGGERS = {
    5: [
        'taiwan emergency mobilization', 'taiwan declares emergency',
        'taiwan activates wartime powers', 'taiwan full mobilization',
        '台灣緊急動員', '戒嚴',
    ],
    4: [
        'taiwan defense budget surge', 'taiwan special defense budget',
        'taiwan extends conscription', 'taiwan one year service confirmed',
        'han kuang largest exercise', 'taiwan maximum readiness',
        '漢光演習', '延長兵役', '特別國防預算',
    ],
    3: [
        'taiwan defense budget increase', 'taiwan arms procurement',
        'taiwan military exercise', 'taiwan combat readiness',
        'taiwan reserve reform', 'taiwan asymmetric',
        'taiwan submarine', 'taiwan drone program',
        '國防預算增加', '台灣軍演', '後備改革',
    ],
    2: [
        'taiwan defense', 'taiwan military', 'taiwan mnd',
        'taiwan armed forces', 'taiwan patriot',
        'taiwan f-16', 'taiwan himars',
        '台灣國防', '國軍',
    ],
    1: [
        'taiwan military', 'roc military', 'taiwan defense',
        '台灣軍事', '台灣國防部',
    ],
}

US_PARTNERSHIP_TRIGGERS = {
    5: [
        'us taiwan defense treaty signed', 'us taiwan mutual defense',
        'us troops deployed taiwan', 'us taiwan alliance formal',
        'us taiwan military alliance',
    ],
    4: [
        'us official visits taipei', 'us cabinet taipei',
        'us secretary state taiwan', 'us arms sale approved taiwan',
        'us taiwan defense commitment', 'us would defend taiwan',
        'us major arms deal taiwan', 'large us arms package taiwan',
        '美國高官訪台', '美台防禦承諾',
    ],
    3: [
        'us senator taiwan', 'us congressman taiwan',
        'us delegation taipei', 'us arms sale taiwan',
        'us taiwan relations act', 'us reaffirms taiwan',
        'us navy transit strait', 'us fonops taiwan',
        '美國訪台', '美台軍售',
    ],
    2: [
        'us taiwan', 'us taipei', 'us arms taiwan',
        'us taiwan security', 'us taiwan relations',
        '美台', '美國台灣',
    ],
    1: [
        'taiwan relations act', 'us taiwan', 'seventh fleet',
        '台灣關係法', '第七艦隊',
    ],
}

DIPLOMATIC_TRIGGERS = {
    5: [
        'taiwan requests un seat', 'taiwan un general assembly',
        'major power recognizes taiwan', 'eu recognizes taiwan',
        'g7 taiwan security guarantee',
    ],
    4: [
        'country recognizes taiwan', 'establishes relations taiwan',
        'taiwan diplomatic recognition', 'taiwan nato link',
        'eu taiwan formal relations', 'taiwan g7',
        '建交台灣', '台灣邦交',
    ],
    3: [
        'taiwan who participation', 'taiwan icao bid',
        'taiwan international organization',
        'taiwan loses ally', 'taiwan gains ally',
        'foreign minister visits taiwan',
        '台灣國際空間', '外交部長訪台',
    ],
    2: [
        'taiwan diplomacy', 'taiwan foreign relations',
        'taiwan mofa', 'taiwan allies',
        '台灣外交', '外交部',
    ],
    1: [
        'taiwan foreign', 'taiwan diplomatic', 'taiwan international',
        '台灣外交',
    ],
}

ASYMMETRIC_TRIGGERS = {
    5: [
        'taiwan nationwide civil defense', 'taiwan activates reserve',
        'taiwan full civil defense activation',
        '全民防衛動員', '後備動員',
    ],
    4: [
        'taiwan civil defense drill nationwide', 'taiwan wartime drill',
        'taiwan air raid drill major', 'taiwan bomb shelter order',
        'taiwan extends military service confirmed',
        '防空演習全國', '戰時演練',
    ],
    3: [
        'taiwan civil defense', 'taiwan air raid drill',
        'taiwan emergency drill', 'taiwan resilience drill',
        'taiwan reserve training', 'taiwan porcupine',
        'taiwan asymmetric warfare', 'taiwan drone swarm',
        '民防演習', '台灣不對稱作戰',
    ],
    2: [
        'taiwan reserve', 'taiwan conscription',
        'taiwan civil defense plan', 'taiwan defense resilience',
        '後備軍', '台灣民防',
    ],
    1: [
        'taiwan reserve', 'taiwan civil', 'taiwan drill',
        '台灣演習', '民防',
    ],
}

# Inbound triggers -- supplemental scan only (primary data from China fingerprint)
PLA_PRESSURE_TRIGGERS = {
    5: ['pla launches attack', 'pla invades', 'pla blockade in effect', '解放军进攻'],
    4: ['joint sword', 'strait thunder', 'justice mission', 'pla encircles', '联合利剑'],
    3: ['pla exercise taiwan', 'median line violation', 'pla live fire', '解放军演习'],
    2: ['pla aircraft taiwan', 'pla taiwan', 'adiz violation', '共机扰台'],
    1: ['pla', 'eastern theater', 'chinese military', '解放军'],
}

BEIJING_COERCION_TRIGGERS = {
    5: ['reunification by force', 'shoot fish in a barrel', 'military action authorized', '武力统一'],
    4: ['drastic measures', 'independence means war', 'stern warning taiwan', '独立即战争'],
    3: ['china firmly opposes', 'china warns taiwan', 'tao warns', 'beijing warns', '中国警告台湾'],
    2: ['china opposes taiwan', 'one china principle', 'tao statement', '国台办'],
    1: ['beijing', 'china taiwan', 'mfa taiwan', '北京', '外交部台湾'],
}

ECONOMIC_PRESSURE_TRIGGERS = {
    5: ['china blockades taiwan', 'rare earth total ban', 'tsmc seized', '台湾港口封锁'],
    4: ['rare earth export ban', 'china chip blockade', 'china economic blockade', '稀土禁令'],
    3: ['china bans taiwan products', 'china trade war taiwan', 'china rare earth', '对台贸易限制'],
    2: ['china export controls taiwan', 'china economic pressure', '出口管制台湾'],
    1: ['china trade taiwan', 'economic coercion', 'tsmc', '台湾经济'],
}


# ============================================
# RSS SOURCES
# ============================================
RSS_SOURCES = {
    # Taiwan primary -- outbound signals
    'focus_taiwan': {
        'url': 'https://focustaiwan.tw/rss/cross-strait.xml',
        'name': 'Focus Taiwan Cross-Strait',
        'weight': 0.95,
        'note': 'Best English Taiwan cross-strait coverage',
    },
    'focus_taiwan_politics': {
        'url': 'https://focustaiwan.tw/rss/politics.xml',
        'name': 'Focus Taiwan Politics',
        'weight': 0.95,
        'note': 'ROC government and defense announcements',
    },
    'taipei_times': {
        'url': 'https://www.taipeitimes.com/xml/index.rss',
        'name': 'Taipei Times',
        'weight': 0.85,
    },
    'taiwan_news': {
        'url': 'https://www.taiwannews.com.tw/rss/news.rss',
        'name': 'Taiwan News',
        'weight': 0.75,
        'note': 'Fast on breaking cross-strait incidents',
    },
    'taiwan_mnd': {
        'url': 'https://focustaiwan.tw/rss/politics.xml',
        'name': 'Taiwan MND (via Focus Taiwan)',
        'weight': 0.95,
        'note': 'Taiwan MND RSS inaccessible -- Focus Taiwan politics covers MND releases',
    },
    'prc_mnd': {
        'url': 'https://www.globaltimes.cn/rss/opinion.xml',
        'name': 'PRC MND (via Global Times)',
        'weight': 0.9,
        'note': 'PRC MND RSS dead -- Global Times as primary CCP signal',
    },
    'global_times_opinion': {
        'url': 'https://www.globaltimes.cn/rss/opinion.xml',
        'name': 'Global Times Opinion',
        'weight': 0.85,
    },
    'china_military': {
        'url': 'https://www.scmp.com/rss/4/feed',
        'name': 'China Military (via SCMP)',
        'weight': 0.9,
        'note': 'PLA official RSS dead -- SCMP China section as replacement',
    },
    # US commitment signals
    'usni_news': {
        'url': 'https://news.usni.org/feed',
        'name': 'USNI News',
        'weight': 1.0,
        'note': '7th Fleet movements, US arms sales',
    },
    # Regional analytical
    'scmp': {
        'url': 'https://www.scmp.com/rss/91/feed',
        'name': 'South China Morning Post',
        'weight': 0.9,
    },
    'nikkei_asia': {
        'url': 'https://asia.nikkei.com/rss/feed/nar',
        'name': 'Nikkei Asia',
        'weight': 0.9,
        'note': 'Japan-Taiwan security relationship',
    },
    'the_diplomat': {
        'url': 'https://thediplomat.com/feed/',
        'name': 'The Diplomat',
        'weight': 0.9,
    },
    'war_on_rocks': {
        'url': 'https://warontherocks.com/feed/',
        'name': 'War on the Rocks',
        'weight': 0.95,
    },
    'rfa': {
        'url': 'https://www.rfa.org/english/rss2.xml',
        'name': 'Radio Free Asia',
        'weight': 0.85,
        'note': 'Taiwan, Tibet, Xinjiang, Hong Kong',
    },
    'csis_amti': {
        'url': 'https://amti.csis.org/feed/',
        'name': 'CSIS AMTI',
        'weight': 0.95,
        'note': 'South China Sea satellite imagery analysis',
    },
    # ============================================
    # v1.4.0 (April 2026) — Cross-theater source expansion
    # Added to catch stories like China-Iran military fusion
    # (e.g. FT April 18 2026: TEE-01B satellite story).
    # Israeli press often breaks China-Iran cooperation first.
    # Premier investigative outlets catch intelligence scoops
    # that Asia-regional feeds don't prioritize.
    # ============================================
    'jpost': {
        'url': 'https://rss.jpost.com/rss/rssfeedsheadlines.aspx',
        'name': 'Jerusalem Post',
        'weight': 0.90,
        'note': 'Breaks China-Iran cooperation stories; Mossad-adjacent sourcing',
    },
    'times_of_israel': {
        'url': 'https://www.timesofisrael.com/feed/',
        'name': 'Times of Israel',
        'weight': 0.90,
        'note': 'Iranian/proxy operations coverage with ME-regional angle',
    },
    'al_monitor': {
        'url': 'https://www.al-monitor.com/rss',
        'name': 'Al-Monitor',
        'weight': 0.90,
        'note': 'ME analysis incl. China/Russia engagement in region',
    },
    'ft_world': {
        'url': 'https://www.ft.com/world?format=rss',
        'name': 'Financial Times (World)',
        'weight': 1.0,
        'note': 'Premier investigative — breaks intelligence/finance stories like TEE-01B satellite',
    },
    'reuters_world': {
        'url': 'https://feeds.reuters.com/Reuters/worldNews',
        'name': 'Reuters World',
        'weight': 1.0,
        'note': 'Newswire baseline — picks up most major breaking stories',
    },
    'middle_east_eye': {
        'url': 'https://www.middleeasteye.net/rss.xml',
        'name': 'Middle East Eye',
        'weight': 0.85,
        'note': 'ME regional — China/Russia activity in Gulf & Levant',
    },
}

REDDIT_SUBREDDITS = [
    'taiwan', 'Taiwanese', 'CredibleDefense', 'geopolitics',
    'worldnews', 'LessCredibleDefence', 'GlobalPowers',
    'Sino', 'OSINT', 'WarCollege', 'NCD', 'anime_titties',
    'Japan', 'Philippines', 'australia', 'EastAsia', 'AsiaPacific',
    'CombatFootage',
]
REDDIT_USER_AGENT = 'AsifahAnalytics-Taiwan/1.0.0 (OSINT tracker)'

GDELT_QUERIES = {
    'eng_outbound': 'Taiwan independence Lai Ching-te defense military US arms',
    'eng_inbound':  'PLA Taiwan exercise China military threat blockade',
    'zho_outbound': '台灣 獨立 賴清德 國防 軍事',
    'zho_inbound':  '解放軍 台灣 演習 武力 封鎖',
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
        print(f"[Taiwan Rhetoric] Redis GET error: {str(e)[:80]}")
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
        print(f"[Taiwan Rhetoric] Redis SET error: {str(e)[:80]}")
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
        print(f"[Taiwan Rhetoric] Redis LPUSH error: {str(e)[:80]}")


# ============================================
# CROSS-THEATER: READ CHINA FINGERPRINT
# ============================================

def _read_china_fingerprint():
    """
    Read China rhetoric tracker fingerprint from shared Redis key.
    Returns china_data dict or None if not available.
    This is the primary input for Taiwan's inbound dashboard.
    """
    try:
        fingerprints = _redis_get(CROSSTHEATER_KEY)
        if fingerprints and 'china' in fingerprints:
            china = fingerprints['china']
            age_str = china.get('updated_at', '')
            age_hours = 99.0
            if age_str:
                try:
                    updated = datetime.fromisoformat(age_str.replace('Z', '+00:00'))
                    age_hours = (datetime.now(timezone.utc) - updated).total_seconds() / 3600
                except Exception:
                    pass
            print(f"[Taiwan Rhetoric] China fingerprint: L{china.get('level', 0)} "
                  f"(PLA L{china.get('pla_level', 0)}, Xi L{china.get('xi_level', 0)}, "
                  f"{age_hours:.1f}h old)")
            return china
    except Exception as e:
        print(f"[Taiwan Rhetoric] China fingerprint read error: {str(e)[:80]}")
    print("[Taiwan Rhetoric] China fingerprint not available -- inbound from article scan only")
    return None


def _read_japan_fingerprint():
    """
    Read Japan rhetoric tracker fingerprint from shared Redis key.
    v1.3.0 — Japan committing to Taiwan defense is a major Taiwan strategic input.

    Returns japan_data dict or None.
    """
    try:
        fingerprints = _redis_get(CROSSTHEATER_KEY)
        if fingerprints and 'japan' in fingerprints:
            japan = fingerprints['japan']
            taiwan_def = japan.get('taiwan_defense_active', False)
            article9 = japan.get('article9_active', False)
            outbound = japan.get('outbound_max_level', 0)
            print(f"[Taiwan Rhetoric] Japan fingerprint: outbound L{outbound}, "
                  f"taiwan_defense={taiwan_def}, article9={article9}")
            return japan
    except Exception as e:
        print(f"[Taiwan Rhetoric] Japan fingerprint read error: {str(e)[:80]}")
    return None


def _read_iran_fingerprint():
    """
    Read Iran rhetoric tracker fingerprint from shared Redis key.
    v2.1 (May 7 2026) — Taiwan reads Iran/Hormuz pressure because Taiwan's
    ~99% oil import dependency creates compound blockade vulnerability.

    Returns dict with hormuz_pressure_active, theatre_score, irgc_level, named_targets.
    """
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

            # Hormuz check — Taiwan imports ~99% of oil, mostly from Middle East
            hormuz_signaled = any(t in iran_targets for t in ['hormuz', 'strait of hormuz', 'persian gulf'])
            if hormuz_signaled or (iran_score >= 60 and iran_irgc >= 3):
                iran_data['hormuz_pressure_active'] = True
                print(f"[Taiwan Rhetoric] Iran-Hormuz read: score={iran_score}, irgc=L{iran_irgc}, hormuz={hormuz_signaled}")
            else:
                print(f"[Taiwan Rhetoric] Iran fingerprint quiet (score={iran_score}, irgc=L{iran_irgc})")
    except Exception as e:
        print(f"[Taiwan Rhetoric] Iran fingerprint read error: {str(e)[:80]}")
    return iran_data


def _apply_japan_amplifier(actor_results, japan_fp):
    """
    v1.3.0 — Apply Japan-alliance amplifier to Taiwan's actor scores.

    When Japan signals Taiwan defense commitments, Taiwan's us_partnership
    and roc_defense actors gain confidence/level.

    Returns dict of {actor_key: amplifier_delta} applied for downstream
    fingerprint context.
    """
    deltas = {}
    if not japan_fp:
        return deltas

    taiwan_def = bool(japan_fp.get('taiwan_defense_active', False))
    article9 = bool(japan_fp.get('article9_active', False))
    outbound = int(japan_fp.get('outbound_max_level', 0) or 0)

    # When Japan publicly commits to Taiwan defense, Taiwan's US-alliance vector
    # gets +1 (because the alliance is now visibly trilateral, not just bilateral)
    if taiwan_def and 'us_partnership' in actor_results:
        current = actor_results['us_partnership'].get('level', 0) or 0
        new_level = min(5, current + 1)
        if new_level > current:
            actor_results['us_partnership']['level'] = new_level
            deltas['us_partnership'] = +1
            print(f"[Taiwan Rhetoric] Japan amplifier: us_partnership L{current} → L{new_level} "
                  f"(Japan Taiwan defense active)")

    # When Japan Article 9 is in active legislative motion at L3+ outbound,
    # Taiwan's defense rhetoric gets +1 (regional pivot, Taiwan reads it as supportive context)
    if article9 and outbound >= 3 and 'roc_defense' in actor_results:
        current = actor_results['roc_defense'].get('level', 0) or 0
        new_level = min(5, current + 1)
        if new_level > current:
            actor_results['roc_defense']['level'] = new_level
            deltas['roc_defense'] = +1
            print(f"[Taiwan Rhetoric] Japan amplifier: roc_defense L{current} → L{new_level} "
                  f"(Japan Article 9 active + outbound L{outbound})")

    return deltas


def _write_taiwan_fingerprint(outbound_score, outbound_max, inbound_score,
                               inbound_max, overall_level, actor_results,
                               japan_amplifiers=None):
    """Write Taiwan fingerprint back to shared cross-theater key.
    v1.3.0: also emits outbound_max_level, inbound_max_level, us_alliance_level
    aliases for consistency with other Asia trackers, plus Japan amplifier flags.
    """
    fingerprints = _redis_get(CROSSTHEATER_KEY) or {}
    japan_amplifiers = japan_amplifiers or {}

    fingerprints['taiwan'] = {
        'level':                overall_level,
        'outbound_score':       outbound_score,
        'outbound_max':         outbound_max,
        # v1.3.0 — canonical naming aliases used by other trackers/proxies
        'outbound_max_level':   outbound_max,
        'inbound_max_level':    inbound_max,
        'inbound_score':        inbound_score,
        'inbound_max':          inbound_max,
        'lai_level':            actor_results.get('lai_presidential', {}).get('level', 0),
        'defense_level':        actor_results.get('roc_defense', {}).get('level', 0),
        'us_level':             actor_results.get('us_partnership', {}).get('level', 0),
        # Alias consistent with Japan tracker's us_alliance_level naming
        'us_alliance_level':    actor_results.get('us_partnership', {}).get('level', 0),
        'diplomatic_level':     actor_results.get('diplomatic_posture', {}).get('level', 0),
        'asymmetric_level':     actor_results.get('asymmetric_resilience', {}).get('level', 0),
        # v1.3.0 — Japan amplifier transparency
        'japan_amplifier_active': bool(japan_amplifiers),
        'japan_amplifier_deltas': japan_amplifiers,
        'label':                ESCALATION_LEVELS[overall_level]['label'],
        'updated_at':           datetime.now(timezone.utc).isoformat(),
    }

    _redis_set(CROSSTHEATER_KEY, fingerprints)
    print(f"[Taiwan Rhetoric] Taiwan fingerprint written (L{overall_level})")


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
            print(f"[Taiwan RSS] {source_name}: HTTP {resp.status_code}")
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
        print(f"[Taiwan RSS] {source_name}: {len(articles)} articles")
    except ET.ParseError as e:
        print(f"[Taiwan RSS] {source_name}: XML error: {str(e)[:80]}")
    except Exception as e:
        print(f"[Taiwan RSS] {source_name}: {str(e)[:80]}")
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
            lang_map = {'eng': 'en', 'zho': 'zh', 'jpn': 'ja'}
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
            print(f"[Taiwan GDELT] {language}: {len(articles)} articles")
        else:
            print(f"[Taiwan GDELT] {language}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[Taiwan GDELT] {language}: {str(e)[:80]}")
    return articles


def _fetch_newsapi(query, days=3, max_results=30):
    """NewsAPI fallback when GDELT is rate-limited or timing out."""
    articles = []
    if not NEWSAPI_KEY:
        print("[Taiwan NewsAPI] No API key configured — skipping")
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
            print(f"[Taiwan NewsAPI] '{query[:40]}': {len(articles)} articles")
        else:
            print(f"[Taiwan NewsAPI] HTTP {resp.status_code}")
    except Exception as e:
        print(f"[Taiwan NewsAPI] Error: {str(e)[:80]}")
    return articles


def _fetch_google_news_rss(query, label, lang='en', gl='US', max_items=15):
    articles = []
    try:
        encoded = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded}&hl={lang}&gl={gl}&ceid={lang.upper()}-{gl}"
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
        print(f"[Taiwan GNews] {label}: {len(articles)} articles")
    except Exception as e:
        print(f"[Taiwan GNews] {label}: {str(e)[:80]}")
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
                print(f"[Taiwan Reddit] r/{sub}: {str(e)[:60]}")
    print(f"[Taiwan Reddit] {len(articles)} posts")
    return articles


# ============================================
# SOURCE WEIGHT HELPER
# ============================================

def _get_source_weight(source_name):
    premium = [
        'Reuters', 'AP News', 'Associated Press', 'BBC',
        'Financial Times', 'Wall Street Journal', 'The Economist',
        'USNI News', 'CSIS', 'War on the Rocks',
        'PRC MND', 'China Military', 'Taiwan MND',
        'Focus Taiwan', 'South China Morning Post', 'Nikkei Asia',
    ]
    high = [
        'Global Times', 'Xinhua', 'Taipei Times', 'Taiwan News',
        'Japan Times', 'The Diplomat', 'Radio Free Asia',
        'AEI', 'Brookings', 'RAND', 'IISS', 'CSIS AMTI',
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
    """Score a single actor against trigger keywords."""
    actor = ACTORS[actor_key]
    now   = datetime.now(timezone.utc)

    trigger_map = {
        'lai_presidential':      LAI_TRIGGERS,
        'roc_defense':           ROC_DEFENSE_TRIGGERS,
        'us_partnership':        US_PARTNERSHIP_TRIGGERS,
        'diplomatic_posture':    DIPLOMATIC_TRIGGERS,
        'asymmetric_resilience': ASYMMETRIC_TRIGGERS,
        'pla_pressure':          PLA_PRESSURE_TRIGGERS,
        'beijing_coercion':      BEIJING_COERCION_TRIGGERS,
        'economic_pressure':     ECONOMIC_PRESSURE_TRIGGERS,
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
                print(f"[Taiwan Rhetoric] TRIPWIRE: {actor_key} -> {tripwire}")
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
    """Compute Taiwan outbound score (0-100)."""
    weights = {
        'lai_presidential':      3.0,
        'roc_defense':           2.0,
        'us_partnership':        2.5,
        'diplomatic_posture':    1.5,
        'asymmetric_resilience': 1.0,
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
        print(f"[Taiwan Rhetoric] Convergence bonus: {elevated} outbound actors at L3+")

    return score, max_level


def _compute_inbound_score_from_fingerprint(china_fp, actor_results):
    """
    Compute Taiwan inbound score using China fingerprint as primary source.
    Falls back to article scan if fingerprint unavailable.
    Returns (score 0-100, max_level 0-5, source_note).
    """
    if china_fp:
        # Primary: use China fingerprint directly
        pla_level  = china_fp.get('pla_level', 0)
        xi_level   = china_fp.get('xi_level', 0)
        mfa_level  = china_fp.get('mfa_level', 0)
        tao_level  = china_fp.get('tao_level', 0)
        econ_level = china_fp.get('econ_level', 0)

        # Weighted composite of China pressure vectors
        # PLA and Xi get highest weight -- most dangerous signals
        weighted = (
            pla_level  * 3.0 +
            xi_level   * 2.5 +
            mfa_level  * 1.5 +
            tao_level  * 1.5 +
            econ_level * 1.0
        )
        total_weight = 3.0 + 2.5 + 1.5 + 1.5 + 1.0   # 10.0
        score        = int((weighted / (total_weight * 5)) * 100)
        max_level    = max(pla_level, xi_level, mfa_level, tao_level, econ_level)
        source_note  = 'china_fingerprint'

        print(f"[Taiwan Rhetoric] Inbound from China fingerprint: "
              f"PLA L{pla_level} Xi L{xi_level} MFA L{mfa_level} -> {score}/100")
        return score, max_level, source_note

    else:
        # Fallback: use article scan inbound actors
        weights = {
            'pla_pressure':    3.0,
            'beijing_coercion': 2.0,
            'economic_pressure': 1.0,
        }
        total_weight = sum(weights.values())
        weighted_sum = 0.0
        max_level    = 0

        for actor_key, weight in weights.items():
            level         = actor_results.get(actor_key, {}).get('level', 0)
            weighted_sum += level * weight
            max_level     = max(max_level, level)

        score       = int((weighted_sum / (total_weight * 5)) * 100)
        source_note = 'article_scan_fallback'
        print(f"[Taiwan Rhetoric] Inbound from article scan (China fingerprint unavailable): {score}/100")
        return score, max_level, source_note


# ============================================
# MAIN SCAN
# ============================================

def run_taiwan_rhetoric_scan():
    """
    Full Taiwan rhetoric scan. Fetches all sources, scores all actors,
    reads China fingerprint for inbound dashboard, writes to Redis.
    """
    scan_start = time.time()
    print(f"\n[Taiwan Rhetoric] Starting scan at {datetime.now(timezone.utc).isoformat()}")

    # Read China fingerprint FIRST -- before any article fetching
    china_fp = _read_china_fingerprint()
    # v1.3.0 — Read Japan fingerprint for trilateral Taiwan-defense amplifier
    japan_fp = _read_japan_fingerprint()
    # v2.1 (May 7 2026) — Read Iran fingerprint for Hormuz-oil convergence
    # (Taiwan's ~99% oil import dependency creates compound blockade vulnerability)
    iran_data = _read_iran_fingerprint()

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
            print(f"[Taiwan RSS] {feed_key}: {str(e)[:80]}")

    # Google News RSS
    gn_queries = [
        ('Taiwan Lai Ching-te independence defense military', 'GNews:Taiwan Outbound EN'),
        ('Taiwan ADIZ PLA China exercise strait threat', 'GNews:Taiwan Inbound EN'),
        ('US Taiwan arms sale senator visit Taipei', 'GNews:US Taiwan EN'),
        ('Taiwan Japan defense JSDF contingency', 'GNews:Japan Taiwan EN'),
        ('Taiwan civil defense reserve conscription drill', 'GNews:Taiwan Civil EN'),
    ]
    for query, label in gn_queries:
        try:
            all_articles.extend(_fetch_google_news_rss(query, label))
            time.sleep(0.3)
        except Exception as e:
            print(f"[Taiwan GNews] {label}: {str(e)[:60]}")

    # Google News RSS -- Traditional Chinese
    zh_queries = [
        ('台灣 賴清德 獨立 國防 軍事', 'GNews:Taiwan Outbound ZH', 'zh', 'TW'),
        ('共機擾台 解放軍 台灣海峽 演習', 'GNews:Taiwan Inbound ZH', 'zh', 'TW'),
    ]
    for query, label, lang, gl in zh_queries:
        try:
            all_articles.extend(_fetch_google_news_rss(query, label, lang=lang, gl=gl))
            time.sleep(0.3)
        except Exception as e:
            print(f"[Taiwan GNews ZH] {label}: {str(e)[:60]}")

    # GDELT + NewsAPI fallback
    for query_key, query in GDELT_QUERIES.items():
        lang = 'eng'
        if 'zho' in query_key:
            lang = 'zho'
        try:
            gdelt_results = _fetch_gdelt(query, language=lang, days=3)
            if gdelt_results:
                all_articles.extend(gdelt_results)
            elif lang == 'eng':
                print(f"[Taiwan GDELT] {query_key}: empty — trying NewsAPI fallback")
                all_articles.extend(_fetch_newsapi(query, days=3))
            time.sleep(0.5)
        except Exception as e:
            print(f"[Taiwan GDELT] {query_key}: {str(e)[:60]}")
            if lang == 'eng':
                all_articles.extend(_fetch_newsapi(query, days=3))

    # Reddit
    reddit_keywords = ['Taiwan defense', 'Lai Ching-te', 'Taiwan ADIZ', 'Taiwan independence']
    try:
        all_articles.extend(_fetch_reddit(REDDIT_SUBREDDITS, reddit_keywords, days=3))
    except Exception as e:
        print(f"[Taiwan Reddit]: {str(e)[:80]}")

    # Telegram
    if TELEGRAM_AVAILABLE:
        try:
            telegram_msgs = fetch_asia_telegram_signals(hours_back=72, include_extended=True)
            taiwan_kws = ['taiwan', '台灣', 'lai ching', 'adiz', 'pla taiwan', 'taipei']
            tg_count   = 0
            for msg in (telegram_msgs or []):
                txt = (msg.get('title', '') or '').lower()
                if any(kw in txt for kw in taiwan_kws):
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
            print(f"[Taiwan Rhetoric] Telegram: {tg_count} relevant messages")
        except Exception as e:
            print(f"[Taiwan Rhetoric] Telegram error: {str(e)[:80]}")

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

    print(f"[Taiwan Rhetoric] Total articles after dedup: {len(all_articles)}")

    # Score all actors
    actor_results = {}
    for actor_key in ACTORS:
        try:
            actor_results[actor_key] = _score_actor(actor_key, all_articles)
            lvl = actor_results[actor_key]['level']
            print(f"[Taiwan Rhetoric] {actor_key}: L{lvl} ({ESCALATION_LEVELS[lvl]['label']})")
        except Exception as e:
            print(f"[Taiwan Rhetoric] Score error {actor_key}: {str(e)[:80]}")
            actor_results[actor_key] = {
                'actor': actor_key, 'level': 0,
                'level_label': 'Baseline', 'level_color': '#6b7280',
                'weighted_score': 0, 'article_count': 0,
                'matched_triggers': [], 'top_articles': [],
                **{k: ACTORS[actor_key][k] for k in
                   ['name', 'flag', 'icon', 'color', 'dashboard', 'role', 'description']},
            }

    # Compute outbound score
    outbound_score, outbound_max = _compute_outbound_score(actor_results)

    # Compute inbound score (from China fingerprint or fallback)
    inbound_score, inbound_max, inbound_source = _compute_inbound_score_from_fingerprint(
        china_fp, actor_results
    )

    # ── v1.3.0 — Apply Japan-alliance amplifier ──
    # Japan committing to Taiwan defense or Article 9 reinterpretation amplifies
    # Taiwan's us_partnership and roc_defense actors. This makes Taiwan tracker
    # reflect trilateral alliance reality, not just bilateral US-Taiwan.
    japan_amplifiers = _apply_japan_amplifier(actor_results, japan_fp)

    # Recompute outbound_max if Japan amplifier changed any outbound actor levels
    if japan_amplifiers:
        outbound_max = max(
            (actor_results[a].get('level', 0) for a in actor_results
             if a in OUTBOUND_ACTOR_KEYS),
            default=outbound_max
        ) if 'OUTBOUND_ACTOR_KEYS' in dir() else outbound_max

    # Overall level = max of outbound and inbound max
    # (Taiwan's analytical question covers both its own posture AND what China is doing)
    overall_level = max(outbound_max, inbound_max)
    overall_label = ESCALATION_LEVELS[overall_level]['label']

    # Write Taiwan fingerprint (v1.3.0 — includes Japan amplifier context)
    _write_taiwan_fingerprint(
        outbound_score, outbound_max, inbound_score,
        inbound_max, overall_level, actor_results,
        japan_amplifiers=japan_amplifiers
    )

    scan_time = round(time.time() - scan_start, 1)

    # ── Signal interpreter (Red Lines + Historical + So What) ──
    red_lines_triggered = []
    historical_matches  = []
    so_what             = {}
    if _INTERPRETER_AVAILABLE:
        try:
            interp_scan_data = {
                'actors':          actor_results,
                'articles':        all_articles,
                'mass_emigration': 0,  # placeholder; future: wire from dedicated scanner
            }
            red_lines_triggered = check_red_lines(all_articles, actor_results)
            def _lvl(key):
                return actor_results.get(key, {}).get('level', 0)
            _det_strength = max(_lvl('us_partnership'), _lvl('roc_defense'), _lvl('diplomatic_posture'))
            _inbound      = max(_lvl('pla_pressure'), _lvl('beijing_coercion'), _lvl('economic_pressure'))
            _resolve      = max(_lvl('lai_presidential'), _lvl('asymmetric_resilience'))
            interp_vectors = {
                'deterrence_strength': _det_strength,
                'inbound_pressure':    _inbound,
                'domestic_resolve':    _resolve,
                'deterrence_gap':      max(0, _inbound - _det_strength),
                'mass_emigration':     0,
            }
            historical_matches = build_historical_matches(actor_results, interp_vectors)
            so_what = build_so_what(interp_scan_data, red_lines_triggered, historical_matches)
            print(f"[Taiwan Rhetoric] Interpreter: "
                  f"{len(red_lines_triggered)} red lines, "
                  f"deterrence_gap: L{so_what.get('deterrence_gap', 0)}, "
                  f"scenario: {so_what.get('scenario_icon','')} {so_what.get('scenario','')[:40]}")
        except Exception as e:
            print(f"[Taiwan Rhetoric] Interpreter error: {e}")

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

        # Actor breakdown
        'actors': actor_results,

        # Component levels for frontend dashboard card
        'lai_level':          actor_results.get('lai_presidential', {}).get('level', 0),
        'defense_level':      actor_results.get('roc_defense', {}).get('level', 0),
        'us_level':           actor_results.get('us_partnership', {}).get('level', 0),
        'diplomatic_level':   actor_results.get('diplomatic_posture', {}).get('level', 0),
        'asymmetric_level':   actor_results.get('asymmetric_resilience', {}).get('level', 0),

        # Inbound from China fingerprint (pass through for frontend)
        'china_pla_level':    china_fp.get('pla_level', 0) if china_fp else 0,
        'china_xi_level':     china_fp.get('xi_level', 0) if china_fp else 0,
        'china_mfa_level':    china_fp.get('mfa_level', 0) if china_fp else 0,
        'china_econ_level':   china_fp.get('econ_level', 0) if china_fp else 0,
        'china_overall_level': china_fp.get('level', 0) if china_fp else 0,
        'china_fingerprint_age': china_fp.get('updated_at', '') if china_fp else '',

        # Interpreter output

    # v2.0: Build top_signals AFTER result dict (needs overall_level + so_what)
    top_signals = []
    if _INTERPRETER_AVAILABLE:
        try:
            top_signals = build_top_signals(result)
            print(f"[Taiwan Rhetoric] top_signals: {len(top_signals)} emitted")
        except Exception as e:
            print(f"[Taiwan Rhetoric] build_top_signals error: {e}")
            top_signals = []
    result['top_signals'] = top_signals

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
        'lai_level':      actor_results.get('lai_presidential', {}).get('level', 0),
        'defense_level':  actor_results.get('roc_defense', {}).get('level', 0),
        'us_level':       actor_results.get('us_partnership', {}).get('level', 0),
        'china_pla_level': china_fp.get('pla_level', 0) if china_fp else 0,
        'china_xi_level':  china_fp.get('xi_level', 0) if china_fp else 0,
    })

    print(f"[Taiwan Rhetoric] Scan complete in {scan_time}s | "
          f"Outbound L{outbound_max} ({outbound_score}/100) | "
          f"Inbound L{inbound_max} ({inbound_score}/100) [{inbound_source}]")

    return result


# ============================================
# BACKGROUND REFRESH
# ============================================

def _background_scan_loop():
    """Background thread: refresh Taiwan rhetoric every 6 hours."""
    print("[Taiwan Rhetoric] Background thread started (6h cycle)")
    # Stagger boot delay so Taiwan starts AFTER China (China writes fingerprint first)
    time.sleep(180)
    while True:
        try:
            run_taiwan_rhetoric_scan()
        except Exception as e:
            print(f"[Taiwan Rhetoric] Background scan error: {str(e)[:200]}")
        time.sleep(SCAN_INTERVAL_HOURS * 3600)


# ============================================
# FLASK ENDPOINT REGISTRATION
# ============================================

def register_taiwan_rhetoric_endpoints(app):
    """Register Taiwan rhetoric endpoints on the Flask app."""

    @app.route('/api/rhetoric/taiwan', methods=['GET'])
    def api_taiwan_rhetoric():
        """
        Taiwan rhetoric tracker -- dual dashboard.
        Outbound: Is Taiwan hardening its posture / triggering PLA response?
        Inbound:  What is China (PLA/Xi/MFA) signaling at Taiwan?
                  (Read from China fingerprint -- runs without re-scanning)
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
                    cached['from_cache'] = True
                    cached['scan_in_progress'] = True
                    return jsonify(cached)
                return jsonify({'success': False, 'error': 'Scan in progress'}), 202
            _rhetoric_running = True

        try:
            result = run_taiwan_rhetoric_scan()
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200]}), 500
        finally:
            with _rhetoric_lock:
                _rhetoric_running = False

    @app.route('/api/rhetoric/taiwan/summary', methods=['GET'])
    def api_taiwan_rhetoric_summary():
        """Lightweight summary -- scores and levels only."""
        cached = _redis_get(RHETORIC_CACHE_KEY)
        if not cached:
            return jsonify({
                'success': False,
                'error': 'No data yet -- run /api/rhetoric/taiwan?force=true'
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
            'lai_level':          cached.get('lai_level', 0),
            'defense_level':      cached.get('defense_level', 0),
            'us_level':           cached.get('us_level', 0),
            'diplomatic_level':   cached.get('diplomatic_level', 0),
            'asymmetric_level':   cached.get('asymmetric_level', 0),
            'china_pla_level':    cached.get('china_pla_level', 0),
            'china_xi_level':     cached.get('china_xi_level', 0),
            'china_overall_level': cached.get('china_overall_level', 0),
            'total_articles':     cached.get('total_articles', 0),
            # Interpreter summary (for cross-page BLUF use)
            'red_lines_count':     len(cached.get('red_lines', [])),
            'scenario':            (cached.get('so_what') or {}).get('scenario', ''),
            'scenario_icon':       (cached.get('so_what') or {}).get('scenario_icon', ''),
            'scenario_color':      (cached.get('so_what') or {}).get('scenario_color', '#6b7280'),
            'deterrence_strength': (cached.get('so_what') or {}).get('deterrence_strength', 0),
            'inbound_pressure':    (cached.get('so_what') or {}).get('inbound_pressure', 0),
            'domestic_resolve':    (cached.get('so_what') or {}).get('domestic_resolve', 0),
            'deterrence_gap':      (cached.get('so_what') or {}).get('deterrence_gap', 0),
            'version':             '1.1.0-taiwan',
        })

    @app.route('/api/rhetoric/taiwan/history', methods=['GET'])
    def api_taiwan_rhetoric_history():
        """Return rhetoric history for chart rendering."""
        history = _redis_get(HISTORY_KEY)
        if not isinstance(history, list):
            history = []
        return jsonify({
            'success': True,
            'count':   len(history),
            'history': history[:120],
        })

    # Start background refresh thread -- staggered after China (180s delay)
    bg = threading.Thread(target=_background_scan_loop, daemon=True)
    bg.start()

    print("[Taiwan Rhetoric] Endpoints registered: "
          "/api/rhetoric/taiwan, /api/rhetoric/taiwan/summary, /api/rhetoric/taiwan/history")
