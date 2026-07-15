"""
Asifah Analytics -- China Rhetoric & Coercion Tracker
v1.0.0 -- March 2026

ANALYTICAL FRAME:
This tracker answers one question:

  "Will China attempt to annex / take back Taiwan by force?"
  (plus: is friction with Japan and/or the United States escalating?)

The CCP does not telegraph operations the way Iran does. Signals are
institutional and formulaic -- meaning SPIKES above baseline are the
signal, not the raw volume. A PLA MND spokesperson saying "shoot fish
in a barrel" is orders of magnitude more significant than ten routine
"safeguard sovereignty" statements.

DUAL DASHBOARD:

  OUTBOUND -- "Is China moving toward coercive action?"
    Tracks: Xi/CMC authorization language, PLA exercise escalation,
            MFA/Global Times rhetoric spikes, TAO coercion signals,
            PLAN/PLAAF deployment language, economic coercion signals

  INBOUND -- "What is the status quo coalition signaling back?"
    Tracks: Taiwan MND ADIZ violation counts, ROC defense posture,
            US 7th Fleet / arms sales / official visits,
            Japan JSDF posture / Senkaku signals,
            AUKUS/Australia deployment language

FIVE OUTBOUND THREAT VECTORS:
  1. XI / CMC AUTHORIZATION  -- top-level political signaling, timeline language
  2. PLA OPERATIONAL POSTURE -- exercise escalation, live fire, blockade drills
  3. MFA / GLOBAL TIMES      -- rhetoric spikes above formulaic baseline
  4. TAO COERCION            -- Taiwan Affairs Office pressure/incentive swings
  5. ECONOMIC COERCION       -- trade restrictions, semiconductor, rare earth signals

THREE INBOUND VECTORS:
  1. TAIWAN DEFENSE          -- ADIZ violations, scrambles, MND posture signals
  2. US COMMITMENT           -- 7th Fleet ops, arms sales, senior visits, FONOPS
  3. JAPAN / REGIONAL        -- JSDF posture, Senkaku, AUKUS, basing signals

SCORING WEIGHTS:
  Xi/CMC Authorization    weight 3.5
  PLA Operational         weight 3.0
  MFA/Global Times        weight 1.5
  TAO Coercion            weight 1.5
  Economic Coercion       weight 1.0
  Convergence bonus:      +10 if 3+ outbound vectors simultaneously at L3+
  Japan friction bonus:   +5 if Japan vector at L3+

KEY TRIPWIRES (auto-escalate to L4+):
  - Named exercise announced (Joint Sword, Justice Mission, Strait Thunder)
  - "Reunification by force" language from Xi or CMC directly
  - PLAN carrier enters Taiwan Strait east side
  - PLA median line crossings exceed 20 aircraft in 24h
  - US senior official visits Taipei (triggers PLA response cycle)
  - Japan explicitly names Taiwan as security concern at minister level

SOURCE STRATEGY:
  Primary RSS:  PRC MND (EN), Global Times, Xinhua, China Military,
                Taiwan MND ADIZ, Focus Taiwan (CNA), Taipei Times,
                USNI News, SCMP, Nikkei Asia, CSIS AMTI
  Secondary:    GDELT (eng, zho, jpn), Google News RSS (EN + ZH)
  Reddit:       r/CredibleDefense, r/Sino, r/taiwan, r/geopolitics,
                r/LessCredibleDefence, r/GlobalPowers, r/OSINT,
                r/anime_titties, r/Philippines, r/Japan, r/australia
  Telegram:     Routed through telegram_signals_asia shared cache

REDIS KEYS:
  Cache:         rhetoric:china:latest
  Legacy:        china_rhetoric_cache
  History:       rhetoric:china:history
  Cross-theater: rhetoric:crosstheater:fingerprints (WRITES)

ENDPOINTS:
  GET /api/rhetoric/china
  GET /api/rhetoric/china/summary
  GET /api/rhetoric/china/history

CHANGELOG:
  v1.0.0 (2026-03-24): Initial build -- dual dashboard, Taiwan Strait focus

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
    from china_signal_interpreter import (
        check_red_lines,
        build_so_what,
        build_historical_matches,
        build_top_signals,
    )
    _INTERPRETER_AVAILABLE = True
    print("[China Rhetoric] Signal interpreter loaded")
except ImportError as e:
    print(f"[China Rhetoric] WARNING: china_signal_interpreter not available ({e})")
    _INTERPRETER_AVAILABLE = False

# ────────────────────────────────────────────────────────────
# JAWBONING PRIMITIVE — Phase 5b wire-in for Xi (May 16, 2026)
# Mirrors Trump-on-US wire-in pattern from rhetoric_tracker_us.py.
# Detects Xi rare-earth / critical-minerals rhetoric and writes
# jawboning:command:china:* fingerprints with 24h TTL via ME backend.
# Cross-theater consumers (US, India, Cuba trackers + butterfly reader)
# read these fingerprints to amplify their own actor scoring.
# ────────────────────────────────────────────────────────────
try:
    from jawboning_proxy_asia import detect_jawboning_via_proxy
    JAWBONING_PRIMITIVE_AVAILABLE = True
    print("[China Rhetoric] ✅ Jawboning primitive available (Phase 5b mode)")
except ImportError as e:
    JAWBONING_PRIMITIVE_AVAILABLE = False
    detect_jawboning_via_proxy = None
    print(f"[China Rhetoric] WARNING: jawboning_proxy_asia not available ({e})")

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
    print("[China Rhetoric] Telegram signals available")
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[China Rhetoric] Telegram signals not available -- RSS/GDELT only")

RHETORIC_CACHE_KEY        = 'rhetoric:china:latest'
RHETORIC_CACHE_KEY_LEGACY = 'china_rhetoric_cache'
HISTORY_KEY               = 'rhetoric:china:history'
BASELINE_KEY              = 'rhetoric_baseline:china'
CROSSTHEATER_KEY          = 'rhetoric:crosstheater:fingerprints'

RHETORIC_CACHE_TTL  = 6 * 3600
SCAN_INTERVAL_HOURS = 6

_rhetoric_running = False
_rhetoric_lock    = threading.Lock()


# ============================================
# ESCALATION LEVELS
# ============================================
ESCALATION_LEVELS = {
    0: {'label': 'Baseline',        'color': '#6b7280', 'description': 'Routine statements, no significant signals'},
    1: {'label': 'Rhetoric',        'color': '#3b82f6', 'description': 'Standard sovereignty language, formulaic warnings'},
    2: {'label': 'Warning',         'color': '#f59e0b', 'description': 'Elevated exercise tempo, escalatory MFA language'},
    3: {'label': 'Confrontation',   'color': '#f97316', 'description': 'Named exercises, live-fire drills, explicit threat signals'},
    4: {'label': 'Coercion',        'color': '#ef4444', 'description': 'Blockade posture, direct authorization language from Xi/CMC'},
    5: {'label': 'Active Conflict', 'color': '#dc2626', 'description': 'Confirmed military action, blockade in effect, invasion underway'},
}


# ============================================
# ACTORS
# ============================================
ACTORS = {

    # ── OUTBOUND ACTORS ──────────────────────────────────────────

    'xi_cmc': {
        'name': 'Xi Jinping / CMC',
        'flag': '🇨🇳',
        'icon': '👁️',
        'color': '#dc2626',
        'dashboard': 'outbound',
        'role': 'Supreme Authorization Authority',
        'description': 'Xi as CMC chairman -- final authority on PLA operations. Direct Xi statements on Taiwan are the highest-value signal in this tracker.',
        'keywords': [
            'xi jinping taiwan', 'xi jinping reunification',
            'xi jinping military', 'xi orders pla',
            'xi inspects troops', 'xi addresses military',
            'xi jinping pla', 'xi warns taiwan',
            'xi jinping warns', 'xi jinping threatens',
            'xi says taiwan', 'xi on taiwan',
            'reunification is inevitable', 'reunification by force',
            'china will be reunified', 'taiwan must be reunified',
            'historical inevitability taiwan',
            'xi jinping speech taiwan', 'xi jinping address',
            'xi jinping military commission',
            'central military commission taiwan',
            'cmc taiwan', 'cmc orders', 'cmc directive',
            'central military commission orders',
            'military commission approves',
            'reunification timeline', 'by 2027', 'by 2035', 'by 2049',
            'historical mission taiwan', 'sacred mission taiwan',
            'complete reunification', 'resolve taiwan question',
            'taiwan question must be resolved',
            '习近平 台湾', '习近平 军队', '习近平 解放军',
            '习近平 统一', '统一台湾', '武力统一',
            '中央军委', '两岸统一', '完成统一',
            '台湾问题', '神圣使命', '历史使命',
        ],
        'baseline_statements_per_week': 3,
        'tripwires': [
            'rare earth export ban',
            'china blockades taiwan ports',
            'tsmc targeted',
        ],
    },

    'pla_operational': {
        'name': 'PLA / Eastern Theater Command',
        'flag': '🇨🇳',
        'icon': '⚔️',
        'color': '#b91c1c',
        'dashboard': 'outbound',
        'role': 'Military Operations / Exercise Escalation',
        'description': 'PLA operational signals -- exercise announcements, live-fire drills, carrier deployments, median line crossings. Eastern Theater Command is the primary actor for Taiwan operations.',
        'keywords': [
            'joint sword', 'strait thunder', 'justice mission',
            'pla exercise taiwan', 'pla drills taiwan',
            'pla live fire', 'eastern theater command',
            'eastern theater exercise', 'eastern theater drill',
            'pla encirclement', 'pla blockade drill',
            'pla taiwan drill', 'pla taiwan exercise',
            'chinese carrier taiwan', 'plan carrier strait',
            'liaoning taiwan', 'shandong taiwan', 'fujian taiwan',
            'plan warship taiwan', 'chinese warship strait',
            'plan enters strait', 'plan east of taiwan',
            'chinese navy taiwan', 'plan deployment taiwan',
            'pla aircraft taiwan', 'plaaf taiwan',
            'median line violation', 'median line crossing',
            'adiz violation taiwan', 'taiwan adiz intrusion',
            'pla crosses median line', 'j-20 taiwan',
            'h-6 taiwan', 'pla bomber taiwan',
            'pla amphibious', 'pla landing exercise',
            'amphibious assault china', 'type 075 taiwan',
            'civilian ferry military', 'roll-on roll-off military',
            'pla invasion drill', 'pla blockade taiwan',
            'pla rocket force taiwan', 'df-26 taiwan',
            'df-21d taiwan', 'df-17 taiwan',
            'pla missile taiwan', 'rocket force exercise',
            'pla combat readiness', 'pla readiness patrol',
            'pla joint patrol taiwan', 'pla encircles taiwan',
            '东部战区', '解放军演习', '解放军台湾',
            '联合利剑', '海峡雷霆', '正义使命',
            '解放军实弹', '航母台湾', '中线越线',
            '火箭军', '东风导弹', '两栖登陆',
        ],
        'baseline_statements_per_week': 15,
        'tripwires': [
            'joint sword',
            'strait thunder',
            'justice mission',
            'pla encircles taiwan',
            'pla blockade',
            'median line crossing',
            'eastern theater live fire',
            'pla missile launch taiwan',
        ],
    },

    'mfa_globaltimes': {
        'name': 'MFA / Global Times',
        'flag': '🇨🇳',
        'icon': '📢',
        'color': '#7c3aed',
        'dashboard': 'outbound',
        'role': 'Rhetoric Escalation / Policy Signaling',
        'description': 'MFA spokesperson statements and Global Times editorials -- formulaic 95% of the time. Score spikes above baseline only. Global Times is a deliberate CCP signaling instrument.',
        'keywords': [
            'mfa spokesperson taiwan', 'foreign ministry taiwan',
            'china foreign ministry warns', 'beijing warns taiwan',
            'china warns taiwan', 'china warns us taiwan',
            'zhao lijian taiwan', 'wang wenbin taiwan',
            'lin jian taiwan', 'mao ning taiwan',
            'china urges us', 'china urges taiwan',
            'china opposes taiwan', 'china firmly opposes',
            'stop interfering taiwan', 'do not play with fire',
            'those who play with fire', 'fire will burn themselves',
            'cannon fodder taiwan', 'protection fees taiwan',
            'shoot fish in a barrel', 'fish in a barrel',
            'firepower package will be delivered',
            'nowhere to hide', 'military force is on the table',
            'use of force is not ruled out', 'peace or war',
            'drastic measures', 'countermeasures taiwan',
            'stern warning taiwan',
            'global times editorial taiwan',
            'global times warns taiwan', 'global times us taiwan',
            'global times pla taiwan', 'hu xijin taiwan',
            '外交部 台湾', '发言人 台湾', '中国警告',
            '玩火者必自焚', '不排除使用武力', '环球时报 台湾',
            '采取一切必要措施', '严正警告',
        ],
        'baseline_statements_per_week': 20,
        'tripwires': [
            'shoot fish in a barrel',
            'firepower package will be delivered',
            'use of force is not ruled out',
            'military force is on the table',
            'drastic measures',
        ],
    },

    'tao': {
        'name': 'Taiwan Affairs Office (TAO)',
        'flag': '🇨🇳',
        'icon': '🏛️',
        'color': '#0891b2',
        'dashboard': 'outbound',
        'role': 'Cross-Strait Policy / Coercion Signals',
        'description': 'TAO is the PRC body directly responsible for Taiwan policy. Shifts from incentive to coercion language are leading indicators of political decision to escalate.',
        'keywords': [
            'taiwan affairs office', 'tao statement', 'tao taiwan',
            'chen binhua', 'zhu fenglian', 'tao spokesperson',
            'taiwan affairs office warns', 'taiwan affairs office says',
            'cross-strait relations', 'cross strait tensions',
            'reunification incentives', 'taiwan economic benefits',
            'taiwan travel ban', 'taiwan trade restriction',
            'tao punishes taiwan', 'tao sanctions taiwan',
            'tao warns separatists', 'dpp separatist',
            'lai ching-te separatist', 'independence means war',
            'taiwan independence means',
            '国台办', '两岸关系', '台湾当局',
            '分裂分子', '台独', '台湾独立',
            '两岸统一大业', '反分裂',
        ],
        'baseline_statements_per_week': 8,
        'tripwires': [
            'independence means war',
            'taiwan independence means war',
            'tao punishes',
        ],
    },

    'economic_coercion': {
        'name': 'Economic Coercion Signals',
        'flag': '🇨🇳',
        'icon': '📊',
        'color': '#d97706',
        'dashboard': 'outbound',
        'role': 'Economic Pressure / TSMC / Rare Earth Signals',
        'description': 'China economic coercion against Taiwan, US, and Japan. Semiconductor, rare earth, and trade restriction signals are gray-zone tools that can precede or accompany military escalation.',
        'keywords': [
            'tsmc china threat', 'china tsmc', 'semiconductor china taiwan',
            'chip war china taiwan', 'china export controls chips',
            'china bans semiconductor', 'chip blockade',
            'china rare earth ban', 'rare earth export controls',
            'china restricts rare earth', 'china magnet ban',
            'gallium germanium ban', 'china critical minerals',
            'china bans taiwan', 'china trade ban taiwan',
            'china sanctions taiwan', 'china restricts taiwan imports',
            'china trade restriction taiwan',
            'china economic coercion', 'gray zone taiwan',
            'china blockade taiwan economy', 'china financial pressure',
            '稀土出口管制', '半导体封锁', '对台经济制裁',
            '台湾贸易限制', '芯片战争',
        ],
        'baseline_statements_per_week': 4,
        'tripwires': [
            'rare earth export ban',
            'china blockades taiwan ports',
            'tsmc targeted',
        ],
    },

    # ── CROSS-THEATER OUTBOUND ACTOR ─────────────────────────────
    # v1.2.0 (April 2026) — China-Iran Axis as dedicated actor.
    # China's role in enabling Iran is architecturally different
    # from its economic coercion of Taiwan. ISR/logistics support
    # to Iran during US-Iran conflict is an aggressive cross-theater
    # projection that belongs in OUTBOUND. Sub-scored across four
    # categories (weapons, ISR, dual-use, diplomatic) — see
    # CHINA_IRAN_AXIS_TRIGGERS below for the ladder.
    'china_iran_axis': {
        'name': 'China → Iran (Axis Support)',
        'flag': '🇮🇷',
        'icon': '🛰️',
        'color': '#dc2626',
        'dashboard': 'outbound',
        'role': 'Cross-Theater — Chinese Support Enabling Iran',
        'description': (
            'China as active supporter of Iran. Sub-categorized across: '
            'weapons/hardware transfer (MANPADS, missiles, components), '
            'ISR/satellite cooperation (TEE-01B, Emposat, Earth Eye Co — '
            'FT Apr 2026), dual-use logistics (chemicals, fuel, electronics), '
            'and diplomatic cover (UN shields, sanctions blocking). '
            'The ISR dimension is particularly consequential as it enables '
            'kinetic targeting of US installations.'
        ),
        'keywords': [
            # Direct mentions (both word orders)
            'china iran', 'iran china', 'chinese iran', 'iran chinese',
            'beijing tehran', 'tehran beijing', 'china tehran', 'beijing iran',
            # Material / capability transfers
            'china arms iran', 'china backs iran', 'china supplies iran',
            'china military aid iran', 'china iran axis',
            'china sends missiles iran', 'china manpads iran',
            # ISR / satellite / space (multiple orders for FT-style headlines)
            'chinese satellite', 'chinese spy satellite', 'china satellite iran',
            'iran chinese satellite', 'irgc chinese satellite',
            'chinese isr iran', 'china ground station iran',
            'iran used chinese satellite',
            # Named entities — TEE-01B story
            'tee-01b', 'tee01b', 'emposat', 'earth eye co', 'earth eye',
            'chang guang satellite',  # Houthi ISR support precedent
            # Dual-use
            'china dual use iran', 'china components iran',
            'china chemicals iran military', 'china fuel iran military',
            # Diplomatic cover
            'china shields iran un', 'china blocks iran sanctions',
            'china iran oil sanctions', 'china buys iranian oil war',
            # Cross-language
            '中国伊朗', '中伊', '中国武器伊朗', '中国支持伊朗',
            'الصين تسلح إيران', 'الصين إيران',
            'چین ایران', 'ایران چین',
        ],
        'baseline_statements_per_week': 3,
        'tripwires': [
            'china directly arms iran',
            'china sends missiles iran confirmed',
            'chinese spy satellite iran targeting',
            'pla weapons iran conflict',
        ],
    },

    # ── INBOUND ACTORS ───────────────────────────────────────────

    'taiwan_defense': {
        'name': 'Taiwan MND / ROC Defense',
        'flag': '🇹🇼',
        'icon': '🛡️',
        'color': '#16a34a',
        'dashboard': 'inbound',
        'role': 'Taiwan Defense Posture / ADIZ Ground Truth',
        'description': 'ROC Ministry of National Defense -- ADIZ violation counts, scramble reports, defense budget signals. The ADIZ daily report is ground truth for PLA pressure tempo.',
        'keywords': [
            'taiwan adiz', 'taiwan adiz violation', 'taiwan adiz report',
            'pla aircraft taiwan adiz', 'taiwan scrambles jets',
            'taiwan air force scrambles', 'taiwan detects pla',
            'taiwan tracks pla', 'taiwan monitors pla',
            'median line violation', 'pla crosses median line',
            'taiwan mnd report', 'taiwan defense ministry',
            'taiwan raises alert', 'taiwan defense alert',
            'taiwan military readiness', 'taiwan combat readiness',
            'taiwan mobilizes', 'taiwan reserve',
            'lai ching-te defense', 'taiwan defense budget',
            'taiwan patriot', 'taiwan missile defense',
            'taiwan f-16', 'taiwan submarine',
            'taiwan drone', 'taiwan asymmetric',
            'hai kun submarine', 'taiwan himars',
            'taiwan us arms', 'us arms taiwan',
            'lai ching-te warns', 'lai ching-te military',
            '台灣國防部', '共機擾台', '防空識別區',
            '中線越線', '台灣戰備', '台灣空軍',
        ],
        'baseline_statements_per_week': 7,
        'tripwires': [
            'taiwan raises alert level',
            'taiwan mobilizes reserves',
            'adiz violations exceed 50',
        ],
    },

    'us_commitment': {
        'name': 'US Commitment Signals',
        'flag': '🇺🇸',
        'icon': '🔷',
        'color': '#2563eb',
        'dashboard': 'inbound',
        'role': 'US Deterrence Posture / 7th Fleet / Arms Sales',
        'description': 'US signaling on Taiwan -- 7th Fleet FONOPS, arms sales, senior official visits to Taipei, strategic ambiguity language. US signals trigger PLA response cycles.',
        'keywords': [
            'seventh fleet taiwan', '7th fleet taiwan',
            'us carrier taiwan', 'uss taiwan strait',
            'us warship taiwan strait', 'us fonops taiwan',
            'freedom of navigation taiwan', 'us transit taiwan strait',
            'us navy taiwan', 'us arms taiwan', 'us weapons taiwan',
            'us taiwan arms sale', 'f-16 taiwan',
            'us taiwan military sale', 'pentagon taiwan',
            'taiwan relations act', 'tra taiwan',
            'us taiwan defense', 'taipei act',
            'us official taiwan', 'us senator taiwan',
            'us congressman taiwan', 'pelosi taiwan',
            'us visit taipei', 'taipei visit us',
            'us secretary taiwan', 'us diplomat taiwan',
            'us defend taiwan', 'us military intervention taiwan',
            'us strategic ambiguity taiwan', 'us would defend taiwan',
            'biden defend taiwan', 'trump taiwan',
            'us taiwan commitment', 'us taiwan security',
            'quad taiwan', 'aukus taiwan', 'us japan taiwan',
            'first island chain', 'indo-pacific taiwan',
            '美国 台湾', '第七舰队', '台湾军售',
            '美台军事', '美国干涉台湾',
        ],
        'baseline_statements_per_week': 8,
        'tripwires': [
            'us official visits taipei',
            'us arms sale taiwan approved',
            'seventh fleet enters strait',
            'us would defend taiwan',
            'us deploys carrier taiwan',
        ],
    },

    'japan_regional': {
        'name': 'Japan / Regional Coalition',
        'flag': '🇯🇵',
        'icon': '🗾',
        'color': '#db2777',
        'dashboard': 'inbound',
        'role': 'Japan / JSDF / AUKUS Posture',
        'description': 'Japan is the most under-rated actor in this space. A Japanese minister explicitly naming Taiwan as a security concern is a bigger signal than most PLA press releases. Also tracks AUKUS, Philippines, and Australia as coalition members.',
        'keywords': [
            'japan taiwan security', 'japan defend taiwan',
            'japan taiwan contingency', 'japan taiwan conflict',
            'japan would defend taiwan', 'takaichi taiwan',
            'japan prime minister taiwan', 'japan foreign minister taiwan',
            'japan names taiwan security', 'japan defense white paper taiwan',
            'jsdf taiwan', 'japan self defense taiwan',
            'japan scrambles jets china', 'japan adiz china',
            'japan senkaku', 'senkaku islands',
            'china japan senkaku', 'japan china east china sea',
            'japan rearmament', 'japan defense budget',
            'japan long range missile', 'japan tomahawk',
            'japan strike capability', 'japan preemptive',
            'japan kyushu missile', 'japan military buildup',
            'aukus taiwan', 'australia taiwan', 'australia china taiwan',
            'australia deploy', 'australia military taiwan',
            'philippines taiwan', 'philippines china scs',
            'us philippines basing', 'edca philippines',
            'south korea taiwan', 'korea taiwan',
            '台湾有事', '日本 台湾', '自衛隊 台湾',
            '尖閣諸島', '日中関係', '中国軍',
        ],
        'baseline_statements_per_week': 5,
        'tripwires': [
            'japan would defend taiwan',
            'japan names taiwan security',
            'japan deploys forces',
            'senkaku incident',
            'aukus taiwan contingency',
        ],
    },
}


# ============================================
# REPORTING ACTORS (language discounted)
# ============================================
REPORTING_ACTORS = {'taiwan_defense', 'us_commitment', 'japan_regional'}

REPORTING_LANGUAGE = [
    'condemns', 'condemned', 'protests', 'denounces',
    'calls on', 'urges', 'expresses concern', 'deeply concerned',
    'in response to', 'following the drills', 'following the exercise',
    'according to', 'reports that', 'monitors', 'tracks',
    'detected', 'observed', 'confirmed',
    '谴责', '抗议', '关切', '回应',
]


# ============================================
# THREAT VECTORS -- OUTBOUND
# ============================================

XI_CMC_TRIGGERS = {
    5: [
        'reunification by force', 'military action taiwan authorized',
        'xi orders eastern theater', 'xi orders pla attack',
        'pla ordered to act', 'military operation taiwan begins',
        '武力统一台湾', '习近平下令', '军事行动台湾',
    ],
    4: [
        'reunification timeline accelerated', 'by 2027 taiwan',
        'xi jinping warns taiwan directly', 'xi threatens taiwan',
        'xi on full military readiness', 'cmc authorizes exercise',
        'resolve taiwan question this generation',
        '武统', '2027统一', '习近平警告台湾',
    ],
    3: [
        'complete reunification', 'sacred mission taiwan',
        'resolve taiwan question', 'reunification inevitable',
        'xi jinping taiwan speech', 'xi addresses pla taiwan',
        'historical mission taiwan', 'xi warns separatists',
        '完成统一', '统一大业', '两岸统一',
    ],
    2: [
        'xi jinping taiwan', 'xi jinping military',
        'central military commission', 'xi inspects troops',
        'cmc directive', 'xi rearmament',
        '习近平 军队', '中央军委',
    ],
    1: [
        'xi jinping', 'cmc', 'beijing taiwan',
        '习近平', '台湾问题',
    ],
}

PLA_OPERATIONAL_TRIGGERS = {
    5: [
        'pla launches attack taiwan', 'pla invades taiwan',
        'pla blockade in effect', 'pla fires missiles taiwan',
        'eastern theater combat operations',
        '解放军进攻台湾', '解放军封锁', '导弹袭击台湾',
    ],
    4: [
        'joint sword', 'strait thunder', 'justice mission',
        'pla encircles taiwan', 'pla blockade drill',
        'pla live fire taiwan', 'pla combat exercise taiwan',
        'carrier east of taiwan', 'plan blockade simulation',
        'pla amphibious assault drill', 'eastern theater live fire',
        '联合利剑', '海峡雷霆', '正义使命',
        '封锁演习', '实弹演习台湾',
    ],
    3: [
        'pla exercise taiwan', 'pla drills taiwan',
        'median line violation', 'pla crosses median line',
        'multiple pla aircraft adiz', 'pla bomber taiwan',
        'pla carrier strait', 'plan warship taiwan',
        'pla readiness patrol taiwan', 'eastern theater exercise',
        '东部战区演习', '解放军越中线', '共机扰台',
    ],
    2: [
        'pla aircraft taiwan', 'pla taiwan',
        'plaaf taiwan', 'plan taiwan',
        'pla patrol taiwan', 'chinese military taiwan',
        '解放军台湾', '共机', '解放军巡逻',
    ],
    1: [
        'pla', 'eastern theater', 'chinese military',
        '解放军', '东部战区',
    ],
}

MFA_TRIGGERS = {
    5: [
        'shoot fish in a barrel', 'firepower package delivered',
        'use of force is not ruled out', 'military force is on the table',
        'nowhere to escape', 'nowhere to hide',
        '武力选项', '不排除武力', '瓮中捉鳖',
    ],
    4: [
        'drastic measures', 'stern warning', 'countermeasures taiwan',
        'china will not hesitate', 'grave consequences taiwan',
        'do not play with fire', 'those who play with fire',
        '严正警告', '采取强有力措施', '玩火者必自焚',
    ],
    3: [
        'china firmly opposes', 'china resolutely opposes',
        'cross red line', 'exceed china patience',
        'china warns us taiwan', 'escalate taiwan tensions',
        '坚决反对', '触碰红线', '中国警告',
    ],
    2: [
        'china opposes', 'sovereignty and territorial integrity',
        'internal affair china', 'non-interference taiwan',
        'one china principle', 'one china policy',
        '主权和领土完整', '内政', '一个中国',
    ],
    1: [
        'foreign ministry', 'spokesperson', 'global times',
        '外交部', '发言人', '环球时报',
    ],
}

TAO_TRIGGERS = {
    5: [
        'independence means war', 'taiwan independence war',
        'tao declares emergency', 'cross-strait war',
        '台独就是战争', '两岸战争',
    ],
    4: [
        'tao punishes taiwan', 'tao sanctions dpp',
        'cross-strait red line', 'tao travel ban',
        'china blocks taiwan strait', 'tao economic retaliation',
        '国台办制裁', '惩戒台独',
    ],
    3: [
        'tao warns separatists', 'tao warns lai',
        'dpp separatist tao', 'tao strong measures',
        'tao condemns taiwan', 'tao taiwan warning',
        '国台办警告', '分裂分子', '台独势力',
    ],
    2: [
        'tao statement', 'taiwan affairs office says',
        'cross-strait relations tao', 'tao spokesperson',
        '国台办表示', '两岸关系',
    ],
    1: [
        'taiwan affairs office', 'tao', '国台办',
    ],
}

# ============================================
# v1.2.0 (April 2026) — China-Iran Axis: SUB-SCORED trigger ladders
# Replaces the previous unused IRAN_AXIS_TRIGGERS with four
# separate trigger dicts, one per dimension. The china_iran_axis
# actor's score is the MAX of all four sub-scores. Writing them
# separately lets the cross-theater fingerprint surface which
# dimension is elevated (e.g. "ISR L4" is worse than "diplomatic L4"
# because ISR enables kinetic targeting).
# Russia-specific satellite triggers moved to russia_iran_axis
# on the Russia tracker — not China's responsibility to track.
# ============================================

# WEAPONS: Direct material support — missiles, MANPADS, components
CHINA_IRAN_WEAPONS_TRIGGERS = {
    5: [
        'china sends missiles iran', 'china ships missiles iran',
        'china manpads iran', 'chinese missiles used iran',
        'china directly arms iran', 'pla weapons iran conflict',
        'beijing arms tehran war', 'china military equipment iran war',
        '中国向伊朗提供导弹', '中国武器伊朗',
    ],
    4: [
        'china ships weapons iran', 'china sends weapons iran',
        'china arms iran conflict', 'chinese weapons iran us',
        'beijing supplies iran war', 'china military aid iran',
        'china iran missile shipment', 'manpads iran china',
        'chinese shoulder fired missiles iran',
        '中国向伊朗运送武器', '中伊军事合作',
    ],
    3: [
        'china iran military', 'china supports iran war',
        'china helps iran', 'china backing iran',
        'chinese components iran missiles',
        '中国支持伊朗',
    ],
    2: [
        'china iran military cooperation', 'china arms iran',
        'china iran hardware',
    ],
    1: [
        'china iran weapons', 'chinese arms iran',
    ],
}

# ISR / SATELLITE: Intelligence, surveillance, reconnaissance enablement
# The highest-consequence dimension — enables kinetic targeting.
CHINA_IRAN_ISR_TRIGGERS = {
    5: [
        'chinese spy satellite iran targeting', 'tee-01b irgc targeting',
        'china satellite strike iran', 'chinese imagery iran strike',
        'china satellite us base target iran',
    ],
    4: [
        'iran used chinese satellite', 'chinese satellite iran bases',
        'chinese spy satellite iran', 'irgc chinese satellite',
        'emposat iran irgc', 'earth eye co iran',
        'tee-01b', 'tee01b',
        'chang guang satellite iran',
        '中国卫星伊朗',
    ],
    3: [
        'chinese satellite iran', 'china satellite iran',
        'china ground station iran', 'chinese isr iran',
        'china targeting data iran', 'in-orbit transfer iran',
        'china space cooperation iran',
    ],
    2: [
        'china iran space', 'chinese imagery iran',
        'belt and road iran space',
    ],
    1: [
        'china iran satellite', 'chinese iran imagery',
    ],
}

# DUAL-USE: Chemicals, fuel, electronics, semiconductors — fungible goods
CHINA_IRAN_DUALUSE_TRIGGERS = {
    5: [
        'china dual use iran confirmed', 'pla dual use iran',
        'china ballistic materials iran',
    ],
    4: [
        'china chemicals iran military', 'china fuel iran military',
        'china components iran missiles', 'china missile fuel iran',
        'china electronics iran military',
    ],
    3: [
        'china dual use iran', 'china components iran',
        'china semiconductor iran military', 'china precursor chemicals iran',
    ],
    2: [
        'china iran trade precursor', 'chinese parts iran',
    ],
    1: [
        'china iran trade', 'chinese goods iran',
    ],
}

# DIPLOMATIC: UN shields, sanctions blocking, framing cover
CHINA_IRAN_DIPLOMATIC_TRIGGERS = {
    5: [
        'china vetoes iran sanctions', 'china blocks iran un resolution',
        'beijing shields iran un security council',
    ],
    4: [
        'china shields iran un', 'china blocks iran sanctions',
        'china opposes iran sanctions', 'beijing defends iran un',
    ],
    3: [
        'china iran oil sanctions', 'china buys iranian oil war',
        'china neutral iran conflict', 'beijing iran war stance',
    ],
    2: [
        'china iran trade war', 'china iran us conflict',
        'china calls restraint iran',
    ],
    1: [
        'china iran diplomatic', 'beijing tehran', 'china iran axis',
        '中伊关系', '中国伊朗石油',
    ],
}

ECONOMIC_TRIGGERS = {
    5: [
        'china blockades taiwan ports', 'taiwan ports closed china',
        'tsmc seized', 'rare earth total ban',
        '台湾港口封锁', '全面禁运台湾',
    ],
    4: [
        'rare earth export ban', 'rare earth ban taiwan',
        'china semiconductor ban taiwan', 'china chip blockade',
        'china cuts taiwan trade', 'china economic blockade',
        '稀土出口禁令', '芯片封锁台湾',
    ],
    3: [
        'china rare earth restriction', 'gallium ban',
        'germanium ban', 'china critical mineral',
        'china bans taiwan products', 'china trade war taiwan',
        '稀土管制', '镓锗禁令', '对台贸易限制',
    ],
    2: [
        'china export controls', 'china trade restriction',
        'china economic pressure taiwan', 'china tsmc',
        '出口管制', '经济压力台湾',
    ],
    1: [
        'economic coercion', 'china trade taiwan',
        'tsmc', 'rare earth', '稀土',
    ],
}


# ============================================
# REGIME SIGNALS (May 7 2026)
# Five sub-detection ladders for China's contribution to structural shifts
# in the international system. China's role is distinct from Iran/Russia:
#   - Iran   = densest sanctions evasion behavior (gold-for-oil)
#   - Russia = densest arms supplier + dedollarization rhetoric + shadow fleet
#   - China  = ARCHITECT of the alternative system: yuan internationalization,
#              BRICS Pay backbone, mBridge CBDC, MFA dedollarization voice,
#              SOE bank facilitation of sanctioned-state trade
# Each fires from China-origin content and writes to the cross-theater
# fingerprint for the convergence registry to consume.
# Note: China is NOT a sanctioned state — these signals measure China as
# the architect/anchor, not as an evader.
# ============================================

# Sub-signal 1: Yuan Internationalization (CIPS, mBridge, petroyuan)
# Feeds: financial_system_fragmentation, dedollarization_drumbeat
# THE primary China signal — yuan as alternative reserve/settlement currency
CHINA_YUAN_INTERNATIONALIZATION_TRIGGERS = {
    5: [
        'yuan replaces dollar reserves', 'cips overtakes swift',
        'petroyuan dominates oil pricing', 'yuan world reserve currency',
        '人民币取代美元', '人民币世界储备货币',
    ],
    4: [
        'yuan internationalization', 'cips expansion',
        'cross-border interbank payment system', 'mbridge cbdc',
        'yuan settlement oil', 'petroyuan oil contracts',
        'yuan denominated trade', 'yuan reserve currency',
        'china yuan global', 'rmb internationalization',
        'digital yuan cbdc', 'e-cny cross border',
        'yuan oil pricing', 'china yuan saudi oil',
        '人民币国际化', '跨境支付系统',
        'CIPS', '数字人民币', '石油人民币',
    ],
    3: [
        'cips transactions', 'yuan cross-border trade',
        'yuan settlement growth', 'china yuan trade share',
        'rmb global payment', 'yuan offshore market',
        'china currency swap', 'yuan bilateral trade',
        'yuan trade settlement', 'cnh offshore yuan',
        '人民币跨境', '人民币结算',
        '货币互换', '离岸人民币',
    ],
    2: [
        'yuan global trade', 'yuan trade growth',
        'china yuan policy', 'yuan exchange rate',
        'rmb yuan', 'china currency',
        '人民币', '中国货币',
    ],
    1: [
        'yuan', 'rmb', 'chinese currency',
        '人民币', '元',
    ],
}

# Sub-signal 2: MFA Dedollarization Rhetoric (Wang Yi / Lin Jian / Mao Ning)
# Feeds: dedollarization_drumbeat
# China MFA explicit public-stage rhetoric on dollar/SWIFT alternatives
CHINA_MFA_DEDOLLARIZATION_TRIGGERS = {
    5: [
        'wang yi announces dollar replacement', 'china foreign minister exits dollar',
        'mfa announces swift alternative complete', 'china declares dollar end',
        '王毅宣布替代美元', '中国外交部宣布脱钩美元',
    ],
    4: [
        'wang yi dedollarization', 'wang yi dollar weaponization',
        'wang yi multipolar economy', 'lin jian dedollarization',
        'mao ning dedollarization', 'china mfa dollar',
        'china foreign ministry dollar', 'wang yi financial sovereignty',
        'china criticizes dollar dominance', 'china dollar weaponization',
        'mfa briefing dedollarization', 'china mfa swift',
        'china foreign minister yuan', 'beijing dedollarization',
        '王毅 美元', '王毅 多极化',
        '林剑 美元', '毛宁 美元',
        '外交部 去美元化',
    ],
    3: [
        'china criticizes us dollar', 'china dollar hegemony',
        'china financial sovereignty', 'china multipolar finance',
        'china non-western financial', 'china global south finance',
        'china criticizes swift', 'china unilateral sanctions',
        'china us financial decoupling', 'china dollar trap',
        '中国批评美元霸权', '美元霸权',
        '金融多极化', '金融主权',
    ],
    2: [
        'china dollar criticism', 'china us trade',
        'china financial system', 'china dollar policy',
        '美元政策', '中美金融',
    ],
    1: [
        'china us dollar', 'china financial', 'china currency policy',
        '中国美元', '中国金融',
    ],
}

# Sub-signal 3: BRICS Architect Role (China as backbone of BRICS financial system)
# Feeds: financial_system_fragmentation, dedollarization_drumbeat
# China's leadership role in BRICS Pay, NDB, BRICS+ expansion
CHINA_BRICS_ARCHITECT_TRIGGERS = {
    5: [
        'brics pay launches china backbone', 'china brics common currency',
        'ndb sanctions tool china', 'brics replaces imf china',
        '中国主导金砖支付', '金砖货币',
    ],
    4: [
        'china brics summit', 'china brics expansion',
        'china brics pay', 'xi brics summit',
        'china hosts brics', 'china brics+ expansion',
        'china new development bank', 'china ndb expansion',
        'china brics technology', 'china brics financial architecture',
        'beijing brics summit', 'china leads brics',
        'brics chairmanship china', 'china brics common currency',
        '金砖国家峰会', '金砖+扩容',
        '金砖支付', '新开发银行',
    ],
    3: [
        'china brics partnership', 'china brics cooperation',
        'china multipolar order', 'china shanghai cooperation',
        'china sco brics', 'china global south',
        'china emerging economies leadership', 'china brics infrastructure',
        'china asian infrastructure', 'china aiib expansion',
        '金砖合作', '上海合作组织',
        '亚投行', '一带一路',
    ],
    2: [
        'china brics', 'china sco',
        'china emerging markets', 'china global south',
        '金砖', '上合',
    ],
    1: [
        'brics china', 'shanghai cooperation', 'sco china',
        '金砖国家', '上合组织',
    ],
}

# Sub-signal 4: Sanctions Facilitator (Chinese SOE banks facilitating sanctioned trade)
# Feeds: sanctions_evasion_cluster, financial_system_fragmentation
# China as the financial intermediary enabling Iran/Russia/DPRK trade
CHINA_SANCTIONS_FACILITATOR_TRIGGERS = {
    5: [
        'china soe bank sanctioned russia', 'us sanctions chinese major bank',
        'china bank cuts off swift sanctions', 'treasury 311 china bank',
        '中国银行被制裁',
    ],
    4: [
        'chinese bank iran trade', 'chinese bank russia trade',
        'china soe bank sanctions', 'china bank dprk facilitation',
        'china bank ofac sanction', 'us sanctions chinese bank',
        'china bank correspondent banking', 'china bank sdn list',
        'china dprk sanctions evasion', 'china iran oil financing',
        'china russia oil financing', 'chinese bank facilitates iran',
        'hong kong gold transit iran', 'macau financial intermediary',
        'icbc iran sanctions', 'bank of china russia',
        '中国银行 伊朗', '中国银行 制裁',
    ],
    3: [
        'china intermediary trade russia', 'china intermediary trade iran',
        'china third country trade evasion', 'china reflagged ships',
        'china bank correspondent', 'china financial intermediary',
        'china us treasury warning', 'china secondary sanctions',
        'china dprk financial', 'china iran financial',
        '中国金融中介', '中国转运伊朗',
    ],
    2: [
        'china secondary sanctions', 'china us treasury',
        'china financial cooperation iran', 'china bank scrutiny',
        '中国制裁', '美国财政部 中国',
    ],
    1: [
        'china sanctions', 'china financial',
        '中国制裁', '中国金融',
    ],
}

# Sub-signal 5: Oil-Yuan Settlement (China-Saudi/Russia/Iran oil yuan deals)
# Feeds: financial_system_fragmentation, energy_bloc_consolidation
# China is the COUNTERPARTY to all major oil-yuan settlement
CHINA_OIL_YUAN_SETTLEMENT_TRIGGERS = {
    5: [
        'china saudi oil yuan settled', 'china russia oil 100 percent yuan',
        'china iran oil yuan exclusively', 'opec oil yuan pricing major',
        '中沙石油人民币', '中俄石油人民币',
    ],
    4: [
        'china saudi yuan oil', 'china russia yuan oil',
        'china iran yuan oil', 'shanghai oil futures yuan',
        'china yuan oil pricing', 'china yuan crude settlement',
        'china oil yuan benchmark', 'sse yuan crude',
        'china uae yuan trade', 'china saudi currency swap',
        'china oil import yuan', 'petroyuan oil china',
        '上海原油期货', '人民币原油',
        '中沙货币互换', '中俄能源人民币',
    ],
    3: [
        'china oil non-dollar', 'china crude yuan trade',
        'china saudi yuan deal', 'china qatar yuan',
        'china oil settlement local currency', 'china lng yuan',
        'china natural gas yuan', 'china energy yuan',
        'china brazil yuan trade', 'china oil currency diversification',
        '人民币能源贸易', '能源人民币结算',
    ],
    2: [
        'china oil deal', 'china oil pricing',
        'china oil import', 'china saudi trade',
        '中国石油贸易', '中沙贸易',
    ],
    1: [
        'china oil', 'china saudi', 'china crude',
        '中国石油', '中沙',
    ],
}


# ============================================
# THREAT VECTORS -- INBOUND
# ============================================

TAIWAN_DEFENSE_TRIGGERS = {
    5: [
        'taiwan raises combat alert', 'taiwan mobilizes reserves',
        'taiwan detects imminent attack', 'taiwan activates wartime',
        '台灣進入戰備', '台灣動員',
    ],
    4: [
        'taiwan full alert', 'taiwan highest alert',
        'taiwan emergency defense', 'taiwan deploys patriots',
        'taiwan mobilizes', 'taiwan war footing',
        '台灣進入高度戒備', '台灣緊急部署',
    ],
    3: [
        'taiwan adiz mass violation', 'taiwan scrambles multiple jets',
        'taiwan raises alert', 'taiwan tracks pla fleet',
        'taiwan monitors carrier', 'taiwan defense heightened',
        '共機大規模擾台', '台灣緊急升空',
    ],
    2: [
        'taiwan adiz violation', 'taiwan scrambles',
        'taiwan detects pla', 'taiwan monitors',
        'taiwan defense', 'taiwan military',
        '共機擾台', '台灣國防',
    ],
    1: [
        'taiwan air force', 'taiwan military', 'taiwan mnd',
        '台灣空軍', '國防部',
    ],
}

US_COMMITMENT_TRIGGERS = {
    5: [
        'us deploys carrier taiwan conflict',
        'us military intervention taiwan',
        'us would go to war taiwan',
        'us activates taiwan relations act',
    ],
    4: [
        'us official visits taipei',
        'us senior official taiwan',
        'us arms sale taiwan approved',
        'seventh fleet enters strait',
        'us carrier taiwan contingency',
        '美国官员访台', '美台军售',
    ],
    3: [
        'us transit taiwan strait', 'us fonops taiwan',
        'us warship taiwan strait', 'us navy taiwan',
        'us reaffirms taiwan commitment', 'us taiwan relations act',
        '美舰穿越台湾海峡', '美国重申台湾',
    ],
    2: [
        'us taiwan', 'seventh fleet', 'us navy pacific',
        'us arms taiwan', 'us taiwan security',
        '美国 台湾', '第七舰队',
    ],
    1: [
        'us pacific', 'us military asia', 'indo-pacific',
        '美国太平洋', '印太',
    ],
}

JAPAN_REGIONAL_TRIGGERS = {
    5: [
        'japan deploys forces taiwan', 'japan military action taiwan',
        'japan defends taiwan', 'jsdf taiwan contingency activated',
    ],
    4: [
        'japan names taiwan security concern',
        'japan would defend taiwan',
        'japan taiwan explicit commitment',
        'senkaku incident armed',
        'aukus taiwan deployment',
        '日本明言防衛台灣', '台湾有事 日本',
    ],
    3: [
        'japan taiwan contingency', 'japan taiwan conflict',
        'jsdf taiwan', 'japan defense white paper taiwan',
        'senkaku confrontation', 'japan scrambles china',
        'aukus taiwan', 'australia china taiwan',
        '台湾有事', '日本自衛隊',
    ],
    2: [
        'japan taiwan', 'japan china tension',
        'jsdf china', 'japan senkaku',
        'australia taiwan', 'aukus',
        '日台', '日中', '自衛隊',
    ],
    1: [
        'japan', 'jsdf', 'australia', 'aukus',
        '日本', '自衛隊',
    ],
}


# ============================================
# RSS SOURCES
# ============================================
RSS_SOURCES = {
    'prc_mnd': {
        'url': 'https://www.globaltimes.cn/rss/opinion.xml',
        'name': 'PRC MND (Official)',
        'weight': 1.0,
        'note': 'PRC MND RSS dead -- using Global Times as primary CCP signal',
    },
    'global_times': {
        'url': 'https://www.globaltimes.cn/rss/opinion.xml',
        'name': 'Global Times',
        'weight': 0.85,
        'note': 'CCP signaling instrument',
    },
    'xinhua_en': {
        'url': 'https://english.news.cn/rss/world.xml',
        'name': 'Xinhua English',
        'weight': 0.75,
    },
    'china_military': {
        'url': 'https://www.scmp.com/rss/4/feed',
        'name': 'China Military (via SCMP)',
        'weight': 0.9,
        'note': 'PLA official RSS dead -- SCMP China military coverage as replacement',
    },
    'taiwan_mnd': {
        'url': 'https://focustaiwan.tw/rss/politics.xml',
        'name': 'Taiwan MND (via Focus Taiwan Politics)',
        'weight': 0.95,
        'note': 'Taiwan MND RSS inaccessible -- Focus Taiwan politics covers MND releases',
    },
    'focus_taiwan': {
        'url': 'https://focustaiwan.tw/rss/cross-strait.xml',
        'name': 'Focus Taiwan Cross-Strait',
        'weight': 0.95,
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
    },
    'usni_news': {
        'url': 'https://news.usni.org/feed',
        'name': 'USNI News',
        'weight': 1.0,
        'note': '7th Fleet movements -- critical for US commitment signals',
    },
    'war_on_rocks': {
        'url': 'https://warontherocks.com/feed/',
        'name': 'War on the Rocks',
        'weight': 0.95,
    },
    'the_diplomat': {
        'url': 'https://thediplomat.com/feed/',
        'name': 'The Diplomat',
        'weight': 0.9,
    },
    'scmp': {
        'url': 'https://www.scmp.com/rss/91/feed',
        'name': 'South China Morning Post',
        'weight': 0.9,
    },
    'nikkei_asia': {
        'url': 'https://asia.nikkei.com/rss/feed/nar',
        'name': 'Nikkei Asia',
        'weight': 0.9,
    },
    'japan_times': {
        'url': 'https://japantimes.co.jp/feed/',
        'name': 'Japan Times',
        'weight': 0.85,
    },
    'rfa': {
        'url': 'https://www.rfa.org/english/rss2.xml',
        'name': 'Radio Free Asia',
        'weight': 0.85,
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
    'CredibleDefense', 'geopolitics', 'worldnews', 'Sino',
    'taiwan', 'Taiwanese', 'LessCredibleDefence', 'GlobalPowers',
    'OSINT', 'WarCollege', 'NCD', 'anime_titties',
    'Philippines', 'Japan', 'australia', 'vietnam',
    'CombatFootage', 'EastAsia', 'AsiaPacific',
]
REDDIT_USER_AGENT = 'AsifahAnalytics-China/1.0.0 (OSINT tracker)'

GDELT_QUERIES = {
    'eng_outbound': 'China PLA Taiwan military exercise threat OR blockade OR invasion',
    'eng_inbound':  'Taiwan ADIZ US Navy strait Japan defense OR JSDF OR AUKUS',
    'zho_outbound': '解放军 台湾 演习 OR 统一 OR 武力',
    'zho_inbound':  '台湾 国防 OR 美军 OR 日本防衛',
    'jpn_japan':    '台湾有事 OR 自衛隊 台湾 OR 中国軍',
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
        print(f"[China Rhetoric] Redis GET error: {str(e)[:80]}")
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
        print(f"[China Rhetoric] Redis SET error: {str(e)[:80]}")
    return False


def _redis_lpush_trim(key, value, max_len=336):
    """Push to list and trim -- 336 entries = 6h intervals x 8 weeks."""
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
        print(f"[China Rhetoric] Redis LPUSH error: {str(e)[:80]}")


# ============================================
# ARTICLE FETCHING
# ============================================

def _parse_pub_date(pub_str):
    """Robustly parse publication date to UTC-aware datetime."""
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
            print(f"[China RSS] {source_name}: HTTP {resp.status_code}")
            return []
        # Strip BOM and leading whitespace before parsing -- some feeds have encoding preambles
        content = resp.content.lstrip(b'\xef\xbb\xbf').strip()
        root = ET.fromstring(content)
        items = root.findall('.//item')
        for item in items[:max_items]:
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
        print(f"[China RSS] {source_name}: {len(articles)} articles")
    except ET.ParseError as e:
        print(f"[China RSS] {source_name}: XML parse error: {str(e)[:80]}")
    except Exception as e:
        print(f"[China RSS] {source_name}: {str(e)[:80]}")
    return articles


def _fetch_gdelt(query, language='eng', days=3, max_records=25):
    """Fetch from GDELT."""
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
        resp = requests.get(GDELT_BASE_URL, params=params, timeout=15)
        if resp.status_code == 200:
            lang_map = {'eng': 'en', 'zho': 'zh', 'jpn': 'ja', 'kor': 'ko'}
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
            print(f"[China GDELT] {language}: {len(articles)} articles")
        else:
            print(f"[China GDELT] {language}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"[China GDELT] {language}: {str(e)[:80]}")
    return articles


def _fetch_newsapi(query, days=3, max_results=30):
    """NewsAPI fallback when GDELT is rate-limited or timing out."""
    articles = []
    if not NEWSAPI_KEY:
        print("[China NewsAPI] No API key configured — skipping")
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
            print(f"[China NewsAPI] '{query[:40]}': {len(articles)} articles")
        else:
            print(f"[China NewsAPI] HTTP {resp.status_code}")
    except Exception as e:
        print(f"[China NewsAPI] Error: {str(e)[:80]}")
    return articles
  
def _fetch_google_news_rss(query, label, lang='en', gl='US', max_items=15):
    """Fetch Google News RSS."""
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
        print(f"[China GNews] {label}: {len(articles)} articles")
    except Exception as e:
        print(f"[China GNews] {label}: {str(e)[:80]}")
    return articles


def _fetch_reddit(subreddits, keywords, days=3, max_per_sub=8):
    """Fetch Reddit posts."""
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
                print(f"[China Reddit] r/{sub}: {str(e)[:60]}")
    print(f"[China Reddit] {len(articles)} posts across {len(subreddits)} subs")
    return articles


# ============================================
# SOURCE WEIGHT HELPER
# ============================================

def _get_source_weight(source_name):
    """Return credibility weight for a source."""
    premium = [
        'Reuters', 'AP News', 'Associated Press', 'BBC',
        'Financial Times', 'Wall Street Journal', 'The Economist',
        'USNI News', 'CSIS', 'War on the Rocks',
        'PRC MND', 'China Military', 'Taiwan MND',
        'Focus Taiwan', 'South China Morning Post', 'Nikkei Asia',
    ]
    high = [
        'Global Times', 'Xinhua', 'CGTN',
        'Taipei Times', 'Taiwan News', 'Japan Times',
        'The Diplomat', 'Radio Free Asia', 'NK News',
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
    """
    Score a single actor against their trigger keywords.
    Returns level (0-5), matched triggers, article count, top articles.
    """
    actor = ACTORS[actor_key]
    now   = datetime.now(timezone.utc)

    # Standard single-ladder actors
    # Standard single-ladder actors
    trigger_map = {
        'xi_cmc':            XI_CMC_TRIGGERS,
        'pla_operational':   PLA_OPERATIONAL_TRIGGERS,
        'mfa_globaltimes':   MFA_TRIGGERS,
        'tao':               TAO_TRIGGERS,
        'economic_coercion': ECONOMIC_TRIGGERS,
        'taiwan_defense':    TAIWAN_DEFENSE_TRIGGERS,
        'us_commitment':     US_COMMITMENT_TRIGGERS,
        'japan_regional':    JAPAN_REGIONAL_TRIGGERS,
    }.get(actor_key, {})

    # v1.2.0 — china_iran_axis merges four sub-scored ladders
    # into one combined trigger_map for scoring purposes. The MAX level
    # across all four sub-categories becomes the actor's level.
    # Sub-levels are computed separately below for fingerprint writing.
    if actor_key == 'china_iran_axis':
        trigger_map = {}
        for lvl in range(1, 6):
            trigger_map[lvl] = (
                CHINA_IRAN_WEAPONS_TRIGGERS.get(lvl, [])
                + CHINA_IRAN_ISR_TRIGGERS.get(lvl, [])
                + CHINA_IRAN_DUALUSE_TRIGGERS.get(lvl, [])
                + CHINA_IRAN_DIPLOMATIC_TRIGGERS.get(lvl, [])
            )
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

        # Source weight
        src_weight = article.get('source_weight_override',
                                 _get_source_weight(article.get('source', {}).get('name', '')))

        # Reporting language discount for inbound actors
        is_reporting = False
        if actor_key in REPORTING_ACTORS:
            if any(rl in text for rl in REPORTING_LANGUAGE):
                is_reporting = True
                src_weight *= 0.4

        # Find highest trigger level
        article_level   = 0
        matched_trigger = None
        for level in [5, 4, 3, 2, 1]:
            triggers = trigger_map.get(level, [])
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

    # Normalize weighted score to 0-5
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

    # Tripwire override -- any match auto-escalates to minimum L4
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
                print(f"[China Rhetoric] TRIPWIRE: {actor_key} -> {tripwire}")
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
# v1.2.0 — CHINA-IRAN AXIS SUB-SCORING (April 2026)
# Computes individual sub-scores per dimension for the cross-theater
# fingerprint, so downstream consumers know WHICH dimension is elevated
# (ISR L4 is more consequential than diplomatic L4 — ISR enables kinetic).
# ============================================

def _score_china_iran_axis_subscores(articles):
    """
    Score each dimension of China-Iran axis separately.
    Returns a dict with per-dimension max levels and the overall max.
    Run in addition to standard _score_actor for china_iran_axis,
    solely to surface granular sub-levels for the fingerprint.
    """
    dimensions = {
        'weapons':    CHINA_IRAN_WEAPONS_TRIGGERS,
        'isr':        CHINA_IRAN_ISR_TRIGGERS,
        'dualuse':    CHINA_IRAN_DUALUSE_TRIGGERS,
        'diplomatic': CHINA_IRAN_DIPLOMATIC_TRIGGERS,
    }
    scores = {dim: 0 for dim in dimensions}

    for article in articles:
        title = (article.get('title', '') or '').lower()
        desc  = (article.get('description', '') or '').lower()
        text  = f"{title} {desc}"

        for dim, ladder in dimensions.items():
            for level in range(5, 0, -1):
                for phrase in ladder.get(level, []):
                    if phrase.lower() in text:
                        if level > scores[dim]:
                            scores[dim] = level
                        break
                if scores[dim] >= level:
                    break

    scores['max'] = max(scores.values()) if scores else 0
    return scores


# ============================================
# REGIME SIGNAL SUB-SCORER (May 7 2026)
# Mirrors iran/russia tracker's regime signal scoring pattern.
# Runs all five regime-signal ladders against the article corpus and
# returns per-dimension max levels. Output flows to (a) the
# cross-theater fingerprint write, and (b) the outbound score modifier.
# Note: only affects outbound_score, not inbound_score — regime
# fragmentation is something China is DOING, not RECEIVING.
# ============================================
def _score_china_regime_signals(articles):
    """
    Score each China regime-signal dimension separately.
    Returns dict: {
        'yuan_internationalization': 0-5,
        'mfa_dedollarization':       0-5,
        'brics_architect':           0-5,
        'sanctions_facilitator':     0-5,
        'oil_yuan_settlement':       0-5,
        'max':                       0-5,  # highest across all dimensions
        'active_count':              int,  # count of dimensions at L3+
    }
    Active count is what feeds the score modifier (capped at +5 in
    _compute_outbound_score). Per-dimension levels are written to the
    cross-theater fingerprint so the convergence registry can read them.
    """
    dimensions = {
        'yuan_internationalization': CHINA_YUAN_INTERNATIONALIZATION_TRIGGERS,
        'mfa_dedollarization':       CHINA_MFA_DEDOLLARIZATION_TRIGGERS,
        'brics_architect':           CHINA_BRICS_ARCHITECT_TRIGGERS,
        'sanctions_facilitator':     CHINA_SANCTIONS_FACILITATOR_TRIGGERS,
        'oil_yuan_settlement':       CHINA_OIL_YUAN_SETTLEMENT_TRIGGERS,
    }
    scores = {dim: 0 for dim in dimensions}

    for article in articles:
        title = (article.get('title', '') or '').lower()
        desc  = (article.get('description', '') or '').lower()
        text  = f"{title} {desc}"

        for dim, ladder in dimensions.items():
            # Find highest level matched in this article for this dimension
            for level in range(5, 0, -1):
                phrases = ladder.get(level, [])
                if any(phrase.lower() in text for phrase in phrases):
                    if level > scores[dim]:
                        scores[dim] = level
                    break

    scores['max'] = max(scores.values()) if scores else 0
    scores['active_count'] = sum(1 for dim in dimensions if scores[dim] >= 3)
    return scores


# ============================================
# COMPOSITE SCORING
# ============================================

def _compute_outbound_score(actor_results, regime_signals=None):
    """
    Compute composite outbound score (0-100).

    v1.2.0 (April 2026) — added china_iran_axis actor weight (2.5).
    v1.4 (May 7 2026) — added optional regime_signals parameter. When 3+ regime
    signals fire at L3+, applies a capped +5 modifier reflecting that China is
    contributing to structural-system fragmentation (yuan internationalization,
    BRICS Pay backbone, MFA dedollarization rhetoric, sanctions facilitator,
    oil-yuan settlement). The cap prevents rhetoric noise from dominating;
    only L3+ (Confrontation level) signals count toward the modifier.
    Note: only affects OUTBOUND score, not inbound — regime fragmentation
    is something China is DOING, not RECEIVING.
    """
    weights = {
        'xi_cmc':            3.5,
        'pla_operational':   3.0,
        'mfa_globaltimes':   1.5,
        'tao':               1.5,
        'economic_coercion': 1.0,
        # v1.2.0 — China-Iran axis weighted at 2.5 because it's a
        # high-consequence cross-theater signal (ISR support enables
        # kinetic strikes). Weighted below xi_cmc/pla but above mfa/tao
        # since material support is more significant than rhetoric.
        'china_iran_axis':   2.5,
    }
    total_weight = sum(weights.values())
    weighted_sum = 0.0
    max_level    = 0

    for actor_key, weight in weights.items():
        level         = actor_results.get(actor_key, {}).get('level', 0)
        weighted_sum += level * weight
        max_level     = max(max_level, level)

    score = int((weighted_sum / (total_weight * 5)) * 100)

    # Convergence bonus: +10 if 3+ outbound actors at L3+
    elevated = sum(
        1 for k in weights
        if actor_results.get(k, {}).get('level', 0) >= 3
    )
    if elevated >= 3:
        score = min(100, score + 10)
        print(f"[China Rhetoric] Convergence bonus: {elevated} outbound actors at L3+")

    # ── v1.4 (May 7 2026): Regime Signal Modifier (capped +5, outbound only) ──
    # When China is contributing to structural-system fragmentation
    # (yuan internationalization, MFA dedollarization, BRICS architect,
    # sanctions facilitator, oil-yuan settlement), bump the OUTBOUND score
    # modestly. Capped so rhetoric noise can't dominate. Inbound unaffected.
    if regime_signals:
        active_count = regime_signals.get('active_count', 0)
        # +1 per active dimension (L3+), capped at +5
        regime_modifier = min(active_count, 5)
        if regime_modifier > 0:
            score = min(100, score + regime_modifier)
            print(f"[China Rhetoric] 🌐 Regime signal modifier: +{regime_modifier} "
                  f"({active_count} dimensions at L3+) → outbound only")

    return score, max_level


def _compute_inbound_score(actor_results):
    """Compute composite inbound score (0-100)."""
    weights = {
        'taiwan_defense': 2.0,
        'us_commitment':  3.0,
        'japan_regional': 2.0,
    }
    total_weight = sum(weights.values())
    weighted_sum = 0.0
    max_level    = 0

    for actor_key, weight in weights.items():
        level         = actor_results.get(actor_key, {}).get('level', 0)
        weighted_sum += level * weight
        max_level     = max(max_level, level)

    score = int((weighted_sum / (total_weight * 5)) * 100)

    # Japan friction bonus: +5 if Japan at L3+
    japan_level = actor_results.get('japan_regional', {}).get('level', 0)
    if japan_level >= 3:
        score = min(100, score + 5)
        print(f"[China Rhetoric] Japan friction bonus applied (Japan L{japan_level})")

    return score, max_level


# ============================================
# CROSS-THEATER FINGERPRINT
# ============================================

def _read_crosstheater_amplifiers():
    """
    Read fingerprints from Iran (oil/Hormuz pressure), Japan (alliance hardening),
    and Taiwan (defense rhetoric) to amplify China's outbound and contextualize
    its strategic environment.

    Returns dict of:
      {
        'iran_hormuz_pressure': bool,   # Iran threatening or active in Hormuz
        'iran_theatre_score':   int,    # 0-100, Iran's overall pressure level
        'iran_irgc_level':      int,    # 0-5, IRGC operational posture
        'iran_proxy_active':    bool,   # Iran proxy network elevated
        'japan_article9_active': bool,  # Constitutional reinterpretation in motion
        'japan_taiwan_defense':  bool,  # Japan committing to Taiwan defense
        'japan_outbound_max':    int,   # 0-5, Japan posture max
        'taiwan_outbound_max':   int,   # 0-5, Taiwan defense rhetoric max
        'taiwan_us_alliance':    int,   # 0-5, Taiwan-US alliance signaling
        'amplifier_actor_deltas': {},   # actor_key -> level delta to apply
        'context_notes':         [],    # human-readable notes for fingerprint
      }
    """
    amplifiers = {
        'iran_hormuz_pressure':  False,
        'iran_theatre_score':    0,
        'iran_irgc_level':       0,
        'iran_proxy_active':     False,
        'japan_article9_active': False,
        'japan_taiwan_defense':  False,
        'japan_outbound_max':    0,
        'taiwan_outbound_max':   0,
        'taiwan_us_alliance':    0,
        'amplifier_actor_deltas': {},
        'context_notes':         [],
    }

    fingerprints = _redis_get(CROSSTHEATER_KEY) or {}

    # ── IRAN READ — China's oil/Hormuz dependency vector ──
    iran_fp = fingerprints.get('iran', {}) or {}
    iran_score = int(iran_fp.get('theatre_score', 0) or 0)
    iran_irgc = int(iran_fp.get('irgc_level', 0) or 0)
    iran_proxy = int(iran_fp.get('proxy_activation_level', 0) or 0)
    iran_targets = iran_fp.get('named_targets', []) or []

    amplifiers['iran_theatre_score'] = iran_score
    amplifiers['iran_irgc_level'] = iran_irgc
    amplifiers['iran_proxy_active'] = iran_proxy >= 3

    # Hormuz check — China imports ~50% of oil through Hormuz
    hormuz_signaled = any(t in iran_targets for t in ['hormuz', 'strait of hormuz', 'persian gulf'])
    if hormuz_signaled or (iran_score >= 60 and iran_irgc >= 3):
        amplifiers['iran_hormuz_pressure'] = True
        amplifiers['context_notes'].append(
            f"Iran posture L-equiv (score {iran_score}, IRGC L{iran_irgc}) — "
            f"China oil supply chain pressure "
            f"({'Hormuz signals active' if hormuz_signaled else 'IRGC operational'})"
        )
        # Amplify China's economic_coercion actor — China likely to push
        # de-escalation rhetoric to protect oil supply
        if 'economic_coercion' in ACTORS:
            amplifiers['amplifier_actor_deltas']['economic_coercion'] = +1
        # Amplify mfa_globaltimes — China typically pushes "stability" framing
        if 'mfa_globaltimes' in ACTORS:
            amplifiers['amplifier_actor_deltas']['mfa_globaltimes'] = +1
        print(f"[China Rhetoric] Iran-Hormuz amplifier active: score={iran_score}, irgc=L{iran_irgc}, hormuz={hormuz_signaled}")

    if amplifiers['iran_proxy_active']:
        amplifiers['context_notes'].append(
            f"Iran proxy network at L{iran_proxy} — regional instability "
            f"affects China BRI and energy routes"
        )

    # ── JAPAN READ — Alliance hardening pressure on China ──
    japan_fp = fingerprints.get('japan', {}) or {}
    japan_outbound = int(japan_fp.get('outbound_max_level', 0) or 0)
    japan_article9 = bool(japan_fp.get('article9_active', False))
    japan_taiwan_def = bool(japan_fp.get('taiwan_defense_active', False))

    amplifiers['japan_outbound_max'] = japan_outbound
    amplifiers['japan_article9_active'] = japan_article9
    amplifiers['japan_taiwan_defense'] = japan_taiwan_def

    if japan_article9:
        amplifiers['context_notes'].append(
            "Japan Article 9 reinterpretation active — "
            "China likely to amplify militarism warnings"
        )
        # Amplify China outbound on Japan-relevant actors
        for ak in ('mfa_globaltimes', 'pla_operational'):
            if ak in ACTORS:
                amplifiers['amplifier_actor_deltas'][ak] = (
                    amplifiers['amplifier_actor_deltas'].get(ak, 0) + 1
                )

    if japan_taiwan_def and japan_outbound >= 3:
        amplifiers['context_notes'].append(
            "Japan committing to Taiwan defense — "
            "trilateral pressure on China's Taiwan calculus"
        )
        # Amplify TAO (Taiwan Affairs Office) and PLA operational
        for ak in ('tao', 'pla_operational'):
            if ak in ACTORS:
                amplifiers['amplifier_actor_deltas'][ak] = (
                    amplifiers['amplifier_actor_deltas'].get(ak, 0) + 1
                )

    # ── TAIWAN READ — Strong ROC defense rhetoric amplifies China posture ──
    taiwan_fp = fingerprints.get('taiwan', {}) or {}
    taiwan_outbound = int(taiwan_fp.get('outbound_max_level', 0) or
                          taiwan_fp.get('inbound_max_level', 0) or 0)
    taiwan_us = int(taiwan_fp.get('us_alliance_level', 0) or 0)

    amplifiers['taiwan_outbound_max'] = taiwan_outbound
    amplifiers['taiwan_us_alliance'] = taiwan_us

    if taiwan_outbound >= 3 or taiwan_us >= 3:
        amplifiers['context_notes'].append(
            f"Taiwan defense signaling (L{taiwan_outbound}) + "
            f"US alliance (L{taiwan_us}) — China outbound likely to escalate"
        )

    return amplifiers


def _write_crosstheater_fingerprint(outbound_score, outbound_max, inbound_max,
                                    overall_level, actor_results,
                                    axis_subscores=None,
                                    crosstheater_amplifiers=None,
                                    regime_signals=None):
    """
    Write China fingerprint to shared Redis cross-theater key.
    v1.2.0: includes china_iran_axis sub-scores so downstream consumers
    (Iran tracker, Global Pressure Index) can see WHICH dimension of
    China support is elevated — ISR is more consequential than diplomatic.
    v1.3.0: includes cross-theater READ context (Iran/Japan/Taiwan amplifiers
    that influenced this scan) so downstream consumers see what China is
    REACTING to, not just what China is doing.
    v1.4 (May 7 2026): adds optional regime_signals parameter. When passed,
    writes 5 per-dimension levels + 5 active flags + 2 aggregates to the
    fingerprint so the convergence registry can detect dedollarization_drumbeat,
    financial_system_fragmentation, and sanctions_evasion_cluster convergences.
    """
    fingerprints = _redis_get(CROSSTHEATER_KEY) or {}

    # v1.2.0 — Safe defaults if caller didn't pass axis_subscores
    axis_subscores = axis_subscores or {}
    crosstheater_amplifiers = crosstheater_amplifiers or {}
    # v1.4 — Safe default for regime_signals
    regime_signals = regime_signals or {}
    axis_level     = actor_results.get('china_iran_axis', {}).get('level', 0)

    fingerprints['china'] = {
        'level':          overall_level,
        'outbound_score': outbound_score,
        'outbound_max':   outbound_max,
        'inbound_max':    inbound_max,
        'pla_level':      actor_results.get('pla_operational', {}).get('level', 0),
        'xi_level':       actor_results.get('xi_cmc', {}).get('level', 0),
        'mfa_level':      actor_results.get('mfa_globaltimes', {}).get('level', 0),
        'tao_level':      actor_results.get('tao', {}).get('level', 0),
        'econ_level':     actor_results.get('economic_coercion', {}).get('level', 0),
        'japan_friction': actor_results.get('japan_regional', {}).get('level', 0),
        'us_commitment':  actor_results.get('us_commitment', {}).get('level', 0),
        # ── v1.2.0 China-Iran Axis (April 2026) ──
        # Written from China's perspective: what China is DOING toward Iran.
        # Overall level + per-dimension sub-levels for granular downstream use.
        'china_iran_axis_level':        axis_level,
        'china_iran_weapons_level':     axis_subscores.get('weapons', 0),
        'china_iran_isr_level':         axis_subscores.get('isr', 0),
        'china_iran_dualuse_level':     axis_subscores.get('dualuse', 0),
        'china_iran_diplomatic_level':  axis_subscores.get('diplomatic', 0),
        # Binary flag for map-overlay / frontend consumers:
        'china_iran_active':            axis_level >= 2,
        # ── v1.3.0 Cross-theater READ context (May 2026) ──
        # What China is REACTING to from Iran/Japan/Taiwan fingerprints.
        'iran_hormuz_pressure':   crosstheater_amplifiers.get('iran_hormuz_pressure', False),
        'iran_theatre_score':     crosstheater_amplifiers.get('iran_theatre_score', 0),
        'iran_irgc_level':        crosstheater_amplifiers.get('iran_irgc_level', 0),
        'iran_proxy_active':      crosstheater_amplifiers.get('iran_proxy_active', False),
        'japan_article9_active':  crosstheater_amplifiers.get('japan_article9_active', False),
        'japan_taiwan_defense':   crosstheater_amplifiers.get('japan_taiwan_defense', False),
        'japan_outbound_max':     crosstheater_amplifiers.get('japan_outbound_max', 0),
        'taiwan_outbound_max':    crosstheater_amplifiers.get('taiwan_outbound_max', 0),
        'crosstheater_context':   crosstheater_amplifiers.get('context_notes', []),

        # ── Regime Signals (May 7 2026) — Convergence Registry Consumer Surface ──
        # Per-dimension max levels for the 5 regime-signal sub-detection ladders.
        # China is the ARCHITECT of the alternative system — yuan internationalization,
        # BRICS Pay backbone, MFA dedollarization rhetoric, sanctions facilitator.
        # Read by convergence_registry entries: dedollarization_drumbeat (China is
        # PRIMARY trigger), financial_system_fragmentation, sanctions_evasion_cluster
        # (via sanctions facilitator), energy_bloc_consolidation (via oil-yuan).
        # Active flag = level >= 3 (Confrontation or above on China scale).
        'china_yuan_internationalization_level':  regime_signals.get('yuan_internationalization', 0),
        'china_yuan_internationalization_active': regime_signals.get('yuan_internationalization', 0) >= 3,
        'china_mfa_dedollarization_level':        regime_signals.get('mfa_dedollarization', 0),
        'china_mfa_dedollarization_active':       regime_signals.get('mfa_dedollarization', 0) >= 3,
        'china_brics_architect_level':            regime_signals.get('brics_architect', 0),
        'china_brics_architect_active':           regime_signals.get('brics_architect', 0) >= 3,
        'china_sanctions_facilitator_level':      regime_signals.get('sanctions_facilitator', 0),
        'china_sanctions_facilitator_active':     regime_signals.get('sanctions_facilitator', 0) >= 3,
        'china_oil_yuan_settlement_level':        regime_signals.get('oil_yuan_settlement', 0),
        'china_oil_yuan_settlement_active':       regime_signals.get('oil_yuan_settlement', 0) >= 3,
        # Aggregate flags for convergence registry simple-AND logic
        'china_regime_signals_max':               regime_signals.get('max', 0),
        'china_regime_signals_active':            regime_signals.get('active_count', 0),

        'label':          ESCALATION_LEVELS[overall_level]['label'],
        'updated_at':     datetime.now(timezone.utc).isoformat(),
    }

    _redis_set(CROSSTHEATER_KEY, fingerprints)
    n_amps = len(crosstheater_amplifiers.get('amplifier_actor_deltas', {}) or {})
    n_regime = regime_signals.get('active_count', 0)
    print(f"[China Rhetoric] Cross-theater fingerprint written "
          f"(L{overall_level}, axis L{axis_level}, {n_amps} amplifiers, {n_regime} regime signals)")


# ============================================
# CHINA WHEEL — RIM READER (v1.0, Jul 2026)
# ============================================
# The China wheel reads its rim. Two spokes now write to it:
#   spoke:china:kazakhstan  (Kazakhstan tracker -- Turkey-wheel schema:
#                            level / relationship / top_signal + dual-track extras)
#   spoke:china:dprk        (DPRK tracker -- native schema:
#                            node_class / leverage_integrity / dependency_note)
# The two schemas DIFFER by design (Kazakhstan mirrored the Turkey wheel; DPRK
# wrote its own), so the reader NORMALIZES both into one shape rather than
# forcing either writer to change. Surface-only: rim reads are attached to the
# scan payload for the interpreter, the Asia BLUF, and future China-wheel
# narratives to consume. No score modification yet -- polarity per spoke
# (client / friction / alignment) is a China-wheel scoping decision, not a
# default. Freshness-gated at 24h, absence-honest: missing or stale spokes are
# reported as such, never invented.

SPOKE_READ_KEYS_CHINA = {
    'kazakhstan': 'spoke:china:kazakhstan',   # first China-wheel spoke (hedge integrity, dual-track)
    'dprk':       'spoke:china:dprk',          # second spoke (leverage integrity, client dependency)
    # Future China-rim spokes slot in here (Pakistan/CPEC, Myanmar, Laos, ...):
}


def _normalize_china_spoke(fp, now):
    """Fold either spoke schema into one common shape.

    Both writers carry `ts` and `level`; everything else differs. Kazakhstan
    uses `relationship`/`top_signal`, DPRK uses `node_class`/`dependency_note`.
    We key off the common fields and preserve spoke-specific extras
    (leverage_integrity for DPRK, dual-track counts for Kazakhstan) without
    forcing them into the shared triple.
    """
    fresh = False
    ts_raw = fp.get('ts') or fp.get('updated_at')
    if ts_raw:
        try:
            ts = datetime.fromisoformat(str(ts_raw).replace('Z', '+00:00'))
            fresh = (now - ts).total_seconds() <= 86400
        except Exception:
            fresh = False
    out = {
        'present':      True,
        'fresh':        fresh,
        'level':        fp.get('level', 0),
        'relationship': fp.get('relationship') or fp.get('node_class') or 'unknown',
        'note':         fp.get('top_signal') or fp.get('dependency_note') or '',
        'ts':           ts_raw,
    }
    if 'leverage_integrity' in fp:
        out['leverage_integrity'] = fp.get('leverage_integrity')
    if 'track' in fp:
        out['track']          = fp.get('track')
        out['elite_signals']  = fp.get('elite_signals', 0)
        out['street_signals'] = fp.get('street_signals', 0)
    return out


def _read_china_spokes():
    """Read the China rim. Returns {spoke_name: normalized_read}."""
    spokes = {}
    now = datetime.now(timezone.utc)
    for name, key in SPOKE_READ_KEYS_CHINA.items():
        try:
            fp = _redis_get(key)
            if not fp or not isinstance(fp, dict):
                spokes[name] = {'present': False}
                continue
            spokes[name] = _normalize_china_spoke(fp, now)
        except Exception as e:
            spokes[name] = {'present': False, 'error': str(e)[:60]}
    live = [n for n, s in spokes.items() if s.get('present') and s.get('fresh')]
    print(f"[China Rhetoric] China rim reads: {len(live)}/{len(SPOKE_READ_KEYS_CHINA)} "
          f"fresh ({', '.join(live) if live else 'none'})")
    return spokes


# ============================================
# MAIN SCAN
# ============================================

def run_china_rhetoric_scan():
    """
    Full China rhetoric scan. Fetches all sources, scores all actors,
    computes dual dashboard, writes to Redis.
    """
    scan_start = time.time()
    print(f"\n[China Rhetoric] Starting scan at {datetime.now(timezone.utc).isoformat()}")

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
            print(f"[China RSS] {feed_key}: {str(e)[:80]}")

    # Google News RSS -- English
    gn_queries = [
        ('China PLA Taiwan military exercise blockade invasion', 'GNews:China Military EN'),
        ('Taiwan ADIZ violation defense strait', 'GNews:Taiwan Defense EN'),
        ('US seventh fleet Taiwan Japan JSDF strait', 'GNews:US Japan Taiwan EN'),
        ('China Taiwan reunification Xi Jinping force', 'GNews:Xi Taiwan EN'),
        ('Joint Sword Strait Thunder PLA exercise Taiwan', 'GNews:PLA Exercise EN'),
    ]
    for query, label in gn_queries:
        try:
            all_articles.extend(_fetch_google_news_rss(query, label))
            time.sleep(0.3)
        except Exception as e:
            print(f"[China GNews] {label}: {str(e)[:60]}")

    # Google News RSS -- Chinese
    zh_queries = [
        ('解放军台湾演习 OR 武统 OR 联合利剑', 'GNews:PLA ZH', 'zh', 'TW'),
        ('台湾国防 OR 共机扰台 OR 中线', 'GNews:Taiwan Defense ZH', 'zh', 'TW'),
    ]
    for query, label, lang, gl in zh_queries:
        try:
            all_articles.extend(_fetch_google_news_rss(query, label, lang=lang, gl=gl))
            time.sleep(0.3)
        except Exception as e:
            print(f"[China GNews ZH] {label}: {str(e)[:60]}")

    # GDELT
    for query_key, query in GDELT_QUERIES.items():
        lang = 'eng'
        if 'zho' in query_key:
            lang = 'zho'
        elif 'jpn' in query_key:
            lang = 'jpn'
        try:
            all_articles.extend(_fetch_gdelt(query, language=lang, days=3))
            time.sleep(0.5)
        except Exception as e:
            print(f"[China GDELT] {query_key}: {str(e)[:60]}")

    # Reddit
    reddit_keywords = [
        'Taiwan strait', 'PLA exercise', 'China Taiwan',
        'median line', 'Taiwan ADIZ',
    ]
    try:
        all_articles.extend(_fetch_reddit(REDDIT_SUBREDDITS, reddit_keywords, days=3))
    except Exception as e:
        print(f"[China Reddit]: {str(e)[:80]}")

    # Telegram -- shared Asia cache
    if TELEGRAM_AVAILABLE:
        try:
            telegram_msgs = fetch_asia_telegram_signals(hours_back=72, include_extended=True)
            china_kws = ['taiwan', 'pla', 'china military', 'strait', '解放军', '台湾']
            tg_count  = 0
            for msg in (telegram_msgs or []):
                txt = (msg.get('title', '') or '').lower()
                if any(kw in txt for kw in china_kws):
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
            print(f"[China Rhetoric] Telegram: {tg_count} relevant messages")
        except Exception as e:
            print(f"[China Rhetoric] Telegram error: {str(e)[:80]}")

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

    print(f"[China Rhetoric] Total articles after dedup: {len(all_articles)}")

    # Score all actors
    actor_results = {}
    for actor_key in ACTORS:
        try:
            actor_results[actor_key] = _score_actor(actor_key, all_articles)
            lvl = actor_results[actor_key]['level']
            print(f"[China Rhetoric] {actor_key}: L{lvl} ({ESCALATION_LEVELS[lvl]['label']})")
        except Exception as e:
            print(f"[China Rhetoric] Score error {actor_key}: {str(e)[:80]}")
            actor_results[actor_key] = {
                'actor': actor_key, 'level': 0,
                'level_label': 'Baseline', 'level_color': '#6b7280',
                'weighted_score': 0, 'article_count': 0,
                'matched_triggers': [], 'top_articles': [],
                **{k: ACTORS[actor_key][k] for k in
                   ['name', 'flag', 'icon', 'color', 'dashboard', 'role', 'description']},
            }

    # ── Regime Signals (May 7 2026) ──
    # Five sub-detection ladders for China's contribution to structural shifts
    # in the international system (yuan internationalization, MFA dedollarization,
    # BRICS architect role, sanctions facilitator, oil-yuan settlement).
    # Output feeds (a) cross-theater fingerprint, (b) outbound score modifier.
    regime_signals = _score_china_regime_signals(all_articles)
    if regime_signals.get('active_count', 0) > 0:
        active_dims = [d for d in
                       ['yuan_internationalization', 'mfa_dedollarization',
                        'brics_architect', 'sanctions_facilitator',
                        'oil_yuan_settlement']
                       if regime_signals.get(d, 0) >= 3]
        print(f"[China Rhetoric] 🌐 Regime signals: {regime_signals['active_count']} active "
              f"({', '.join(active_dims)}) — max L{regime_signals['max']}")

    # Compute dashboard scores
    outbound_score, outbound_max = _compute_outbound_score(actor_results,
                                                            regime_signals=regime_signals)
    inbound_score,  inbound_max  = _compute_inbound_score(actor_results)

    # Overall level = outbound max (this tracker answers the outbound question)
    overall_level = outbound_max
    overall_label = ESCALATION_LEVELS[overall_level]['label']

    # v1.2.0 — compute China-Iran axis sub-scores for fingerprint granularity
    axis_subscores = _score_china_iran_axis_subscores(all_articles)
    if axis_subscores.get('max', 0) > 0:
        print(f"[China Rhetoric] Axis sub-scores — "
              f"weapons:{axis_subscores['weapons']}, isr:{axis_subscores['isr']}, "
              f"dualuse:{axis_subscores['dualuse']}, diplomatic:{axis_subscores['diplomatic']}")

    # ── v1.3.0 — READ cross-theater fingerprints (Iran/Japan/Taiwan) ──
    crosstheater_amplifiers = _read_crosstheater_amplifiers()

    # Apply actor level deltas from cross-theater amplifiers
    for actor_key, delta in crosstheater_amplifiers.get('amplifier_actor_deltas', {}).items():
        if actor_key in actor_results:
            current_level = actor_results[actor_key].get('level', 0) or 0
            new_level = min(5, current_level + delta)
            if new_level > current_level:
                print(f"[China Rhetoric] Cross-theater amplifier: "
                      f"{actor_key} L{current_level} → L{new_level}")
                actor_results[actor_key]['level'] = new_level
                # Recalculate label/color if those fields exist
                if 'label' in actor_results[actor_key]:
                    actor_results[actor_key]['label'] = ESCALATION_LEVELS[new_level]['label']
                if 'color' in actor_results[actor_key]:
                    actor_results[actor_key]['color'] = ESCALATION_LEVELS[new_level]['color']

    # Recompute outbound_max after amplification
    outbound_max = max(
        (actor_results[a].get('level', 0) for a in actor_results if a in OUTBOUND_ACTORS),
        default=outbound_max
    ) if 'OUTBOUND_ACTORS' in dir() else max(
        (a.get('level', 0) for a in actor_results.values()),
        default=outbound_max
    )
    overall_level = outbound_max
    overall_label = ESCALATION_LEVELS[overall_level]['label']

    # Write cross-theater fingerprint (now with amplifier context + regime signals)
    _write_crosstheater_fingerprint(
        outbound_score, outbound_max, inbound_max,
        overall_level, actor_results,
        axis_subscores=axis_subscores,
        crosstheater_amplifiers=crosstheater_amplifiers,
        regime_signals=regime_signals
    )

    # ──────────────────────────────────────────────────────────────────────
    # PHASE 5b — JAWBONING DETECTION (Xi → ME detector → Redis fingerprints)
    # Mirrors rhetoric_tracker_us.py Phase 5b pattern. Hard-bounded threaded
    # call so scan completes even if ME backend is slow/unreachable.
    # Writes fingerprints directly (no dual-track compare — Xi has no
    # inline computation to compare against, this IS the source of truth).
    # ──────────────────────────────────────────────────────────────────────
    if JAWBONING_PRIMITIVE_AVAILABLE:
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as _JBTimeout
        _jb_executor = ThreadPoolExecutor(max_workers=1)
        try:
            _jb_future = _jb_executor.submit(
                detect_jawboning_via_proxy,
                leader_id='xi',
                country_id='china',
                actor_results=actor_results,
                write_fingerprints=True,            # write to Redis (production mode)
                scan_id=datetime.now(timezone.utc).isoformat(),
            )
            try:
                jb_results = _jb_future.result(timeout=25)
            except _JBTimeout:
                print("[China Rhetoric] ⏱️ Jawboning detector exceeded 25s — "
                      "abandoning (scan continues, fingerprints will be stale)")
                jb_results = None
            except Exception as e:
                print(f"[China Rhetoric] ⚠️ Jawboning detector error: "
                      f"{type(e).__name__}: {str(e)[:160]}")
                jb_results = None

            if isinstance(jb_results, dict):
                fired = [sig for sig, v in jb_results.items() if v]
                if fired:
                    print(f"[China Rhetoric] 🦋 Xi jawboning fired: {', '.join(fired)}")
                else:
                    print(f"[China Rhetoric] Xi jawboning evaluated, "
                          f"0/{len(jb_results)} signatures fired this scan")
        finally:
            _jb_executor.shutdown(wait=False)
    # ──────────────────────────────────────────────────────────────────────
    # End Phase 5b block.
    # ──────────────────────────────────────────────────────────────────────

    scan_time = round(time.time() - scan_start, 1)

    # ── Signal interpreter (Red Lines + Historical + So What) ──
    red_lines_triggered = []
    historical_matches  = []
    so_what             = {}
    top_signals         = []
    if _INTERPRETER_AVAILABLE:
        try:
            # Build scan_data shape that interpreter expects
            interp_scan_data = {
                'actors':            actor_results,
                'articles':          all_articles,
                'domestic_fracture': 0,  # placeholder; future: wire from dedicated scanner
            }
            red_lines_triggered = check_red_lines(all_articles, actor_results)
            def _lvl(key):
                return actor_results.get(key, {}).get('level', 0)
            interp_vectors = {
                'kinetic_pressure':  max(_lvl('pla_operational'), _lvl('xi_cmc') if _lvl('xi_cmc') >= 3 else 0),
                'economic_pressure': _lvl('economic_coercion'),
                'domestic_fracture': 0,
                'us_commitment':     _lvl('us_commitment'),
            }
            historical_matches = build_historical_matches(actor_results, interp_vectors)
            so_what = build_so_what(interp_scan_data, red_lines_triggered, historical_matches)
            print(f"[China Rhetoric] Interpreter: "
                  f"{len(red_lines_triggered)} red lines, "
                  f"scenario: {so_what.get('scenario_icon','')} {so_what.get('scenario','')[:40]}")
        except Exception as e:
            print(f"[China Rhetoric] Interpreter error: {e}")

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

        # Overall
        'overall_level': overall_level,
        'overall_label': overall_label,
        'overall_color': ESCALATION_LEVELS[overall_level]['color'],

        # Actor breakdown
        'actors': actor_results,

        # Component levels (for cross-theater + frontend dashboard cards)
        'xi_level':              actor_results.get('xi_cmc', {}).get('level', 0),
        'pla_level':             actor_results.get('pla_operational', {}).get('level', 0),
        'mfa_level':             actor_results.get('mfa_globaltimes', {}).get('level', 0),
        'tao_level':             actor_results.get('tao', {}).get('level', 0),
        'econ_level':            actor_results.get('economic_coercion', {}).get('level', 0),
        'taiwan_defense_level':  actor_results.get('taiwan_defense', {}).get('level', 0),
        'us_commitment_level':   actor_results.get('us_commitment', {}).get('level', 0),
        'japan_level':           actor_results.get('japan_regional', {}).get('level', 0),

        # Interpreter output
        'red_lines':          red_lines_triggered,
        'historical_matches': historical_matches,
        'so_what':            so_what,

        'escalation_levels': ESCALATION_LEVELS,

        # ── Regime Signals (May 7 2026) ──
        # Per-dimension max levels for cross-theater fingerprint + GPI consumption.
        'regime_signals':              regime_signals,
        'regime_signals_active_count': regime_signals.get('active_count', 0),
        'regime_signals_max_level':    regime_signals.get('max', 0),

        # ── Cross-theater amplifiers (v2.2 — May 7 2026) ──
        # Exposed in result so build_top_signals can read for commodity convergence
        # injection (e.g. hormuz_china_oil_dependency when Iran pressure on Hormuz
        # intersects China's ~50% oil import dependency).
        'crosstheater_amplifiers': crosstheater_amplifiers,

        'version':           '2.2.0-china',  # v2.2: commodity convergence injection
    }

    # v2.0: Build top_signals AFTER result dict is constructed (needs overall_level + so_what)
    if _INTERPRETER_AVAILABLE:
        try:
            top_signals = build_top_signals(result)
            print(f"[China Rhetoric] top_signals: {len(top_signals)} emitted")
        except Exception as e:
            print(f"[China Rhetoric] build_top_signals error: {e}")
            top_signals = []
    result['top_signals'] = top_signals

    # v1.0 (Jul 2026): the China wheel reads its rim. Two spokes now live
    # (Kazakhstan + DPRK). Surface-only; attached for the interpreter, the Asia
    # BLUF, and future China-wheel narratives. No score modification yet.
    result['spoke_reads'] = _read_china_spokes()

    # Cache to Redis
    _redis_set(RHETORIC_CACHE_KEY, result)
    _redis_set(RHETORIC_CACHE_KEY_LEGACY, result)

    # History snapshot for chart rendering
    _redis_lpush_trim(HISTORY_KEY, {
        'ts':             datetime.now(timezone.utc).isoformat(),
        'outbound_score': outbound_score,
        'inbound_score':  inbound_score,
        'level':          overall_level,
        'label':          overall_label,
        'xi_level':       actor_results.get('xi_cmc', {}).get('level', 0),
        'pla_level':      actor_results.get('pla_operational', {}).get('level', 0),
        'japan_level':    actor_results.get('japan_regional', {}).get('level', 0),
        'us_level':       actor_results.get('us_commitment', {}).get('level', 0),
    })

    regime_active = regime_signals.get('active_count', 0)
    regime_str = f" | Regime: {regime_active} active" if regime_active > 0 else ""
    print(f"[China Rhetoric] Scan complete in {scan_time}s | "
          f"Outbound L{outbound_max} ({outbound_score}/100) | "
          f"Inbound L{inbound_max} ({inbound_score}/100){regime_str}")

    return result


# ============================================
# BACKGROUND REFRESH
# ============================================

def _background_scan_loop():
    """Background thread: refresh China rhetoric every 6 hours."""
    print("[China Rhetoric] Background thread started (6h cycle)")
    time.sleep(120)  # Boot delay -- let app stabilize first
    while True:
        try:
            run_china_rhetoric_scan()
        except Exception as e:
            print(f"[China Rhetoric] Background scan error: {str(e)[:200]}")
        time.sleep(SCAN_INTERVAL_HOURS * 3600)


# ============================================
# FLASK ENDPOINT REGISTRATION
# ============================================

def register_china_rhetoric_endpoints(app):
    """Register China rhetoric endpoints on the Flask app."""

    @app.route('/api/rhetoric/china', methods=['GET'])
    def api_china_rhetoric():
        """
        China rhetoric tracker -- dual dashboard.
        Outbound: Is China moving toward coercive action against Taiwan?
        Inbound:  What is the US/Japan/Taiwan coalition signaling back?
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
            result = run_china_rhetoric_scan()
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200]}), 500
        finally:
            with _rhetoric_lock:
                _rhetoric_running = False

    @app.route('/api/rhetoric/china/summary', methods=['GET'])
    def api_china_rhetoric_summary():
        """Lightweight summary -- scores and levels only, no full actor detail."""
        cached = _redis_get(RHETORIC_CACHE_KEY)
        if not cached:
            return jsonify({
                'success': False,
                'error': 'No data yet -- run /api/rhetoric/china?force=true'
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
            'xi_level':           cached.get('xi_level', 0),
            'pla_level':          cached.get('pla_level', 0),
            'mfa_level':          cached.get('mfa_level', 0),
            'tao_level':          cached.get('tao_level', 0),
            'econ_level':         cached.get('econ_level', 0),
            'taiwan_defense_level': cached.get('taiwan_defense_level', 0),
            'us_commitment_level':  cached.get('us_commitment_level', 0),
            'japan_level':        cached.get('japan_level', 0),
            'total_articles':     cached.get('total_articles', 0),
            # Interpreter summary (for cross-page BLUF use)
            'red_lines_count':    len(cached.get('red_lines', [])),
            'scenario':           (cached.get('so_what') or {}).get('scenario', ''),
            'scenario_icon':      (cached.get('so_what') or {}).get('scenario_icon', ''),
            'scenario_color':     (cached.get('so_what') or {}).get('scenario_color', '#6b7280'),
            'kinetic_pressure':   (cached.get('so_what') or {}).get('kinetic_pressure', 0),
            'economic_pressure':  (cached.get('so_what') or {}).get('economic_pressure', 0),
            'coalition_pushback': (cached.get('so_what') or {}).get('coalition_pushback', 0),
            'version':            '1.1.0-china',
        })

    @app.route('/api/rhetoric/china/history', methods=['GET'])
    def api_china_rhetoric_history():
        """Return rhetoric history for chart rendering (last 8 weeks)."""
        history = _redis_get(HISTORY_KEY)
        if not isinstance(history, list):
            history = []
        return jsonify({
            'success': True,
            'count':   len(history),
            'history': history[:120],  # 30 days at 6h intervals
        })

    # Start background refresh thread
    bg = threading.Thread(target=_background_scan_loop, daemon=True)
    bg.start()

    print("[China Rhetoric] Endpoints registered: "
          "/api/rhetoric/china, /api/rhetoric/china/summary, /api/rhetoric/china/history")
