"""
Asifah Analytics -- Japan Rhetoric & Coercion Tracker
v1.0.0 -- May 2026

ANALYTICAL FRAME:
This tracker answers two paired questions:

  OUTBOUND -- "Is Japan moving toward active military commitment in
              East Asia (Taiwan defense, Article 9 reinterpretation,
              long-range strike posture)?"

  INBOUND  -- "Are China, North Korea, or Russia escalating military or
              rhetorical pressure against Japan?"

Japan is structurally distinct from China/Taiwan trackers because Japan
is BOTH an active strike-capable actor under Takaichi-era posture AND a
target of multi-vector pressure (PLA Eastern Theater, DPRK missiles,
Russia Far East, China Coast Guard at Senkaku). This requires a dual-
dashboard architecture mirroring the Israel tracker.

DUAL DASHBOARD:

  OUTBOUND -- "Is Japan committing to active military posture?"
    Tracks: Takaichi cabinet statements, Article 9 reinterpretation
            language, Taiwan defense commitments, MOFA bluebook,
            JSDF deployment milestones, long-range strike capability
            deployment, alliance posture (Quad/AUKUS/Philippines)

  INBOUND -- "Is Japan being threatened or pressured?"
    Tracks: PLA Eastern Theater patrols, China MFA/MoD condemnations,
            Senkaku/Diaoyu CCG incursions, Okinawa airspace pressure,
            DPRK missile launches over/toward Japan, Russia Far East
            bomber/naval exercises

FIVE OUTBOUND POSTURE ACTORS:
  1. PM_CABINET           -- Takaichi statements, Article 9, Taiwan commitments
  2. MOFA                 -- bluebook, Taiwan statements, formal protests
  3. MOD_JSDF             -- deployments, scrambles, exercise rhetoric, strike capability
  4. LDP_DIET             -- defense budget, Article 9 votes, Diet positioning
  5. US_ALLIANCE          -- INDOPACOM signaling, treaty language, joint exercises (reporting actor)

SIX INBOUND THREAT ACTORS:
  1. CHINA_THREAT         -- PLA Eastern Theater, MFA/MoD, Hu Xijin/Jun Zhengping
  2. DPRK_THREAT          -- Kim Jong Un / KCNA threats, missile flies over Japan, J-Alert
  3. RUSSIA_THREAT        -- Northern Territories, Hokkaido bomber incursions, Tsushima naval
  4. SENKAKU_INTRUSION    -- China Coast Guard incursions in Senkaku/Diaoyu (operational)
  5. OKINAWA_PRESSURE     -- PLA aircraft/naval activity near Okinawa, Ryukyu, southwest islands
  6. TAIWAN_STRAIT_PROXIMITY -- PLA Taiwan exercises spilling into Japan-relevant ADIZ

ESCALATION SCALE (canonical across all rhetoric trackers):
  L0 -- Baseline      (no rhetoric activity)
  L1 -- Rhetoric      (statements without substance)
  L2 -- Warning       (formal protests, summons, harsh language)
  L3 -- Directive     (named decisions, capability commitments)
  L4 -- Operational   (deployment orders, exercise execution)
  L5 -- Active Conflict / Kinetic Activity

ARTICLE 9 ESCALATION (Japan-unique vector):
  L2 -- "potentially critical situation" / "collective self-defense" generic language
  L3 -- Cabinet decision named (e.g. "Cabinet approves new interpretation")
  L4 -- Diet vote scheduled or passed on Article 9 reinterpretation
  L5 -- Article 9 amendment ratified OR JSDF in active combat under reinterpretation

KEY TRIPWIRES (auto-escalate to L4+):
  - "Potentially critical situation" formally invoked by PM
  - JSDF in active combat operations
  - PLA fires across median line into JADIZ
  - DPRK missile lands in Japan EEZ or territorial waters
  - China Coast Guard fires at JCG vessels at Senkaku
  - Diet votes on Article 9 reinterpretation

CACHE STRATEGY (matching China/Taiwan/Israel pattern):
  Primary cache:    rhetoric:japan:latest (TTL 12h)
  Articles cache:   rhetoric:japan:articles (TTL 12h)
  Cross-theater:    rhetoric:crosstheater:fingerprints (WRITES)

SOURCE STRATEGY:
  Primary RSS:      Japan Times, Mainichi English, Kyodo, NHK World, Nikkei Asia
  GDELT:            English + Japanese (jpn) language queries
  NewsAPI:          Japan-related queries
  BlueSky:          Asia-scoped accounts via bluesky_signals_asia
  Brave fallback:   When GDELT/NewsAPI underperform
  Telegram:         Asia channels (limited Japan-specific coverage)

CROSS-THEATER FINGERPRINTS WRITTEN:
  japan: {
    overall_level, inbound_max_level, outbound_max_level,
    taiwan_defense_active, article9_active, senkaku_active,
    okinawa_pla_active, strike_capability_milestone,
    china_japan_friction, dprk_japan_threat,
  }

CROSS-THEATER FINGERPRINTS READ:
  china.outbound_max_level    -> amplifies china_threat inbound (+1 if L3+)
  taiwan.china_pressure       -> amplifies taiwan_strait_proximity
  (dprk fingerprint when DPRK tracker exists)
"""

import os
import json
import time
import hashlib
import requests
import feedparser
import re
import threading
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from flask import jsonify
import unicodedata
import math

# ============================================
# OPTIONAL DEPENDENCIES (BlueSky for OSINT)
# ============================================
try:
    from bluesky_signals_asia import fetch_bluesky_for_target
    BLUESKY_AVAILABLE = True
except ImportError:
    BLUESKY_AVAILABLE = False
    print("[Japan Rhetoric] ⚠️ BlueSky Asia signals not available (non-fatal)")


# ============================================
# CACHE / CONFIG
# ============================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL', '')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN', '')

CACHE_KEY                 = 'rhetoric:japan:latest'
ARTICLES_KEY              = 'rhetoric:japan:articles'
CROSSTHEATER_KEY          = 'rhetoric:crosstheater:fingerprints'
CACHE_TTL_HOURS           = 12
BACKGROUND_REFRESH_HOURS  = 12

NEWSAPI_KEY = os.environ.get('NEWSAPI_KEY', '')
BRAVE_API_KEY = os.environ.get('BRAVE_API_KEY', '')

# Defensive timeouts (Asia backend convention)
RSS_TIMEOUT     = 12
GDELT_TIMEOUT   = (5, 15)
NEWSAPI_TIMEOUT = 10
BRAVE_TIMEOUT   = 10

# ============================================
# ESCALATION SCALE (canonical)
# ============================================
LEVEL_LABELS = {
    0: 'Baseline',
    1: 'Rhetoric',
    2: 'Warning',
    3: 'Directive',
    4: 'Operational',
    5: 'Kinetic Activity',
}

LEVEL_COLORS = {
    0: '#6b7280',
    1: '#3b82f6',
    2: '#f59e0b',
    3: '#f97316',
    4: '#ef4444',
    5: '#dc2626',
}

# ============================================
# ACTORS (dual-dashboard, 11 total)
# ============================================
ACTORS = {
    # ════════════════════════════════════════════════════════════
    # INBOUND — threats TO Japan
    # ════════════════════════════════════════════════════════════
    'china_threat': {
        'name': 'China (PRC) — Inbound Threat',
        'flag': '🇨🇳', 'icon': '🚀',
        'color': '#dc2626',
        'role': 'Strategic / Diplomatic / Military Pressure',
        'description': 'PLA Eastern Theater Command, China MFA/MoD condemnations, PLA-linked social media (Hu Xijin, Jun Zhengping)',
        'keywords': [
            # Direct condemnation language
            'china condemns japan', 'china warns japan',
            'china mfa japan', 'china foreign ministry japan',
            'china mod japan', 'china ministry of defense japan',
            'beijing warns tokyo', 'beijing condemns tokyo',
            'china summons japan ambassador', 'china summons japanese envoy',
            # Eastern Theater Command activity (China-side)
            'eastern theater command japan', 'pla eastern theater japan',
            'pla aircraft japan', 'pla navy japan', 'pla bombers japan',
            'chinese fighter near japan', 'pla jet near japan',
            # Specific PLA-linked accounts / commentators
            'hu xijin japan', 'global times japan',
            'jun zhengping japan', 'china military mouthpiece japan',
            'people\'s liberation army japan',
            # Symbolic/historical pressure
            'shimonoseki anniversary japan', 'national humiliation japan',
            'japanese militarism warning', 'remilitarization japan warning',
            # Embassy / diplomatic friction
            'jgsdf officer chinese embassy', 'japan officer chinese embassy',
            'chinese embassy tokyo incident',
            # Combat readiness / patrols
            'combat readiness patrol japan', 'pla combat patrol east china sea',
            # Chinese language signals
            '中国 警告 日本', '中国 谴责 日本', '解放军 日本',
            '东部战区 日本', '中国外交部 日本',
        ],
        'baseline_statements_per_week': 8,
    },
    'dprk_threat': {
        'name': 'DPRK (North Korea) — Missile Threat',
        'flag': '🇰🇵', 'icon': '☢️',
        'color': '#a855f7',
        'role': 'Missile / Nuclear Threat',
        'description': 'Kim Jong Un / KCNA threats targeting Japan, missile launches over/toward Japan, J-Alert events',
        'keywords': [
            # Direct missile threats targeting Japan
            'north korea missile japan', 'dprk missile japan',
            'north korea missile flies over japan',
            'missile flies over japan', 'kim missile japan',
            'north korea threatens japan', 'dprk threatens japan',
            'pyongyang threatens tokyo', 'pyongyang warns japan',
            # J-Alert system triggers
            'j-alert', 'j alert japan',
            'japan missile alert', 'japan nationwide alert',
            # Nuclear posturing toward Japan
            'north korea nuclear japan', 'dprk nuclear japan',
            'kim nuclear strike japan', 'pyongyang nuclear threat japan',
            # KCNA / state media targeting Japan
            'kcna japan', 'rodong sinmun japan',
            'north korea state media japan',
            # Specific weapon systems
            'hwasong japan', 'north korea slbm japan',
            'dprk icbm japan',
            # Korean language signals
            '북한 미사일 일본', '김정은 일본', '조선 일본 위협',
        ],
        'baseline_statements_per_week': 4,
    },
    'russia_threat': {
        'name': 'Russia — Far East Threat',
        'flag': '🇷🇺', 'icon': '🛩️',
        'color': '#7c3aed',
        'role': 'Northern Territories / Far East Pressure',
        'description': 'Russia Far East bomber incursions, Hokkaido approaches, Northern Territories rhetoric, Tsushima/Soya naval activity',
        'keywords': [
            # Bomber / aircraft incursions
            'russian bombers hokkaido', 'russian bombers near japan',
            'russian fighter near japan', 'russian aircraft japan',
            'tu-95 hokkaido', 'tu-160 japan',
            'russian planes japan adiz',
            # Naval activity
            'russian navy soya strait', 'russian navy tsushima',
            'russian destroyer near japan', 'russian submarine japan',
            'russian fleet la perouse', 'russian fleet pacific',
            # Northern Territories / Kuril
            'northern territories russia', 'kuril islands japan',
            'russia kuril deployment', 'russia southern kurils',
            'russia japan territorial dispute',
            # Russia-Japan tensions
            'russia warns japan', 'russia condemns japan',
            'russia japan sanctions',
            # Russian language signals
            'россия япония', 'курилы япония',
        ],
        'baseline_statements_per_week': 3,
    },
    'senkaku_intrusion': {
        'name': 'Senkaku / Diaoyu Intrusions',
        'flag': '🇨🇳', 'icon': '🚢',
        'color': '#f97316',
        'role': 'Maritime Sovereignty Pressure',
        'description': 'China Coast Guard incursions in Senkaku/Diaoyu territorial waters, JCG patrol responses',
        'keywords': [
            # Direct incursion language
            'senkaku islands incursion', 'senkaku intrusion',
            'diaoyu islands incursion', 'china coast guard senkaku',
            'ccg senkaku', 'chinese vessels senkaku',
            'chinese ships senkaku', 'china intrudes senkaku',
            # Japanese coast guard responses
            'japan coast guard senkaku', 'jcg senkaku',
            'jcg patrol senkaku', 'japan coast guard china',
            'jcg drives off chinese',
            # East China Sea standoffs
            'east china sea japan', 'east china sea standoff',
            'east china sea confrontation',
            # Specific named incidents
            'senkaku incident', 'diaoyu incident',
            'senkaku territorial waters', 'senkaku contiguous zone',
            # Chinese language signals
            '钓鱼岛 日本', '尖閣 中国', '钓鱼岛 海警',
            # Japanese language signals
            '尖閣諸島', '尖閣 領海', '海上保安庁 中国',
        ],
        'baseline_statements_per_week': 5,
    },
    'okinawa_pressure': {
        'name': 'Okinawa / Southwest Islands Pressure',
        'flag': '🇨🇳', 'icon': '🛩️',
        'color': '#f59e0b',
        'role': 'Ryukyu / Southwest Air-Sea Pressure',
        'description': 'PLA aircraft/naval activity near Okinawa, Miyako Strait passage, Ryukyu chain pressure',
        'keywords': [
            # PLA activity near Okinawa
            'pla aircraft okinawa', 'pla navy okinawa',
            'chinese warship okinawa', 'pla bomber okinawa',
            'chinese drone okinawa', 'chinese fighter near okinawa',
            # Miyako Strait passage
            'miyako strait passage', 'pla miyako strait',
            'chinese fleet miyako', 'pla navy miyako',
            # Southwest islands / Ryukyu chain
            'ryukyu chain pressure', 'southwest islands incursion',
            'pla ryukyu', 'china ryukyu',
            # JSDF response
            'asdf scramble china', 'jsdf scramble okinawa',
            'japan air defense scramble china',
            # Japanese language signals
            '南西諸島', '宮古海峡', '沖縄 中国軍',
        ],
        'baseline_statements_per_week': 4,
    },
    'taiwan_strait_proximity': {
        'name': 'Taiwan Strait Spillover',
        'flag': '🇹🇼', 'icon': '⚠️',
        'color': '#fbbf24',
        'role': 'Regional Spillover Risk',
        'description': 'PLA Taiwan exercises spilling into Japan-relevant ADIZ space; Yonaguni proximity events',
        'keywords': [
            # PLA Taiwan exercises near Japan
            'pla taiwan exercise yonaguni', 'pla joint sword japan',
            'taiwan strait crisis japan', 'taiwan exercise japan adiz',
            'joint sword exercise japan',
            # Yonaguni / Ishigaki proximity
            'yonaguni pla', 'yonaguni chinese activity',
            'ishigaki pla', 'sakishima islands pla',
            # Spillover events
            'taiwan exercise spillover', 'pla missile near yonaguni',
            'pla blockade japan adiz',
        ],
        'baseline_statements_per_week': 2,
    },

    # ════════════════════════════════════════════════════════════
    # OUTBOUND — Japan's posture
    # ════════════════════════════════════════════════════════════
    'pm_cabinet': {
        'name': 'PM Cabinet (Takaichi)',
        'flag': '🇯🇵', 'icon': '🏛️',
        'color': '#0891b2',
        'role': 'Executive / Constitutional Posture',
        'description': 'Prime Minister statements, Cabinet decisions, Article 9 reinterpretation language, Taiwan defense commitments',
        'keywords': [
            # PM identity / statements
            'takaichi defense', 'takaichi taiwan', 'takaichi china',
            'sanae takaichi', 'pm takaichi', 'prime minister takaichi',
            'takaichi cabinet', 'kantei statement', 'cabinet secretary japan',
            # Article 9 / collective self-defense language
            'article 9 reinterpretation', 'article 9 japan',
            'collective self-defense', 'collective self defense',
            'japan collective self-defense taiwan',
            'reinterpretation constitution japan',
            # "Potentially critical situation" — specific legal trigger
            'potentially critical situation',
            'japan situation gravely affecting',
            'existential threat japan',
            # Taiwan defense commitment language
            'japan taiwan defense', 'japan taiwan contingency',
            'japan would defend taiwan',
            'japan come to taiwan defense',
            'japan taiwan emergency',
            # Counter-strike / strike capability rhetoric
            'japan counter-strike', 'japan counterstrike capability',
            'japan strike capability', 'japan stand-off missile',
            # Japanese language signals
            '高市 防衛', '高市 台湾', '集団的自衛権',
            '反撃能力', '存立危機事態',
        ],
        'baseline_statements_per_week': 6,
    },
    'mofa': {
        'name': 'MOFA (Ministry of Foreign Affairs)',
        'flag': '🇯🇵', 'icon': '📜',
        'color': '#0e7490',
        'role': 'Diplomatic Posture',
        'description': 'Diplomatic Bluebook, Taiwan statements, formal protests, ambassador summons, China condemnations',
        'keywords': [
            # MOFA identity
            'japan mofa', 'japan foreign ministry',
            'japan ministry of foreign affairs',
            'japanese foreign minister',
            'japan summons chinese ambassador',
            'japan summons russian ambassador',
            # Diplomatic Bluebook
            'japan diplomatic bluebook', 'japan bluebook china',
            'japan annual bluebook',
            # Formal protests
            'japan formal protest china', 'japan strong protest',
            'tokyo protests beijing', 'tokyo lodges protest',
            # Taiwan-related diplomatic statements
            'japan supports taiwan', 'japan international community taiwan',
            'japan-taiwan relations',
            # Japanese language signals
            '外務省', '日本 抗議',
        ],
        'baseline_statements_per_week': 5,
    },
    'mod_jsdf': {
        'name': 'MoD / JSDF (Defense Ministry)',
        'flag': '🇯🇵', 'icon': '⚔️',
        'color': '#155e75',
        'role': 'Military Posture / Deployment',
        'description': 'Defense Ministry statements, JSDF deployments, scrambles, exercise rhetoric, strike capability deployment milestones',
        'keywords': [
            # MoD identity
            'japan defense ministry', 'japan ministry of defense',
            'japanese defense minister', 'japan mod statement',
            # JSDF activity
            'jsdf deployment', 'jsdf scramble',
            'japan self-defense force deployment',
            'jasdf scramble', 'asdf scramble',
            'jmsdf deployment', 'jmsdf taiwan strait',
            'jgsdf deployment', 'japan ground self-defense',
            # Specific platforms / events
            'js ikazuchi', 'js ise', 'js izumo',
            'japan helicopter destroyer', 'japan aegis destroyer',
            # Strike capability deployment milestones
            'tomahawk japan deployment', 'tomahawk delivery japan',
            'japan stand-off missile deployment',
            'type 12 missile deployment', 'type-12 japan',
            'japan hypersonic deployment',
            # Exercise rhetoric
            'us-japan joint exercise', 'japan-us joint exercise',
            'keen sword exercise', 'orient shield exercise',
            'yama sakura exercise', 'japan-philippines exercise',
            # Southwest islands deployment
            'yonaguni garrison', 'ishigaki garrison', 'miyako garrison',
            'japan amphibious rapid deployment brigade',
            # Defense budget signals
            'japan 2 percent gdp defense', 'japan defense buildup',
            'japan defense budget record',
            # Japanese language signals
            '防衛省', '自衛隊 配備', '反撃能力 配備',
        ],
        'baseline_statements_per_week': 8,
    },
    'ldp_diet': {
        'name': 'LDP / Diet (Political Posture)',
        'flag': '🇯🇵', 'icon': '🗳️',
        'color': '#0369a1',
        'role': 'Legislative / Political Posture',
        'description': 'LDP positioning, Diet Article 9 debates, defense budget votes, security legislation',
        'keywords': [
            # LDP identity
            'liberal democratic party japan', 'ldp japan',
            'ldp defense', 'ldp security policy',
            'ldp china policy', 'ldp taiwan policy',
            # Diet activity
            'japan diet vote defense', 'diet article 9',
            'japan diet security', 'japan diet china',
            'national diet japan defense',
            # Article 9 reinterpretation legislative
            'diet article 9 vote', 'diet constitution amendment',
            'lower house defense vote', 'upper house defense vote',
            'japan security legislation',
            # Defense budget legislative
            'japan defense budget vote', 'diet defense spending',
            'japan supplementary budget defense',
            # Komeito (LDP coalition partner — restraining vector)
            'komeito defense', 'komeito coalition',
            'komeito article 9', 'komeito security',
            # Japanese language signals
            '自民党 防衛', '国会 安全保障', '公明党 防衛',
        ],
        'baseline_statements_per_week': 4,
    },
    'us_alliance': {
        'name': 'US-Japan Alliance (Reporting Actor)',
        'flag': '🇺🇸', 'icon': '🤝',
        'color': '#1d4ed8',
        'role': 'Treaty / Coordination Posture',
        'description': 'INDOPACOM signaling on Japan, US-Japan treaty language, joint exercise coordination, Article V invocations',
        'keywords': [
            # INDOPACOM signaling on Japan
            'indopacom japan', 'us indopacom japan',
            'us forces japan', 'usfj statement',
            'us military japan deployment',
            # Treaty language
            'us-japan treaty', 'article v japan',
            'mutual defense treaty japan', 'us defends japan',
            'us-japan alliance', 'us commitment japan',
            # Coordination / joint exercises
            'us-japan summit', 'biden-takaichi', 'trump-takaichi',
            'us-japan joint statement',
            'us-japan-korea trilateral', 'us-japan-philippines',
            # Specific coordination events
            'us aircraft carrier japan', 'us navy japan port call',
            'reciprocal access agreement japan',
            # 7th Fleet / Yokosuka activity
            'seventh fleet japan', '7th fleet yokosuka',
            'us navy yokosuka', 'us forces okinawa',
        ],
        'baseline_statements_per_week': 5,
    },
}

ACTOR_KEYWORDS = {k: v['keywords'] for k, v in ACTORS.items()}

# Actor classification (mirrors Israel pattern)
INBOUND_ACTORS  = ['china_threat', 'dprk_threat', 'russia_threat',
                   'senkaku_intrusion', 'okinawa_pressure', 'taiwan_strait_proximity']
OUTBOUND_ACTORS = ['pm_cabinet', 'mofa', 'mod_jsdf', 'ldp_diet', 'us_alliance']

# US alliance is a reporting actor (reports on coordination, doesn't independently posture)
REPORTING_ACTORS = {'us_alliance'}

REPORTING_LANGUAGE = [
    'condemns', 'condemned', 'denounces', 'calls for',
    'urges restraint', 'expressed concern', 'deeply concerned',
    'in response to', 'following the', 'reaffirms commitment',
]

# Brake/coordination language (for US-Japan, indicates restraint)
BRAKE_LANGUAGE = [
    'us urges japan caution', 'washington warns japan restraint',
    'us-japan careful coordination', 'avoid escalation',
]

# Greenlight language (US backing Japan posture)
GREENLIGHT_LANGUAGE = [
    'us backs japan', 'us authorizes japan', 'us supports japan',
    'us greenlight japan', 'us tomahawk delivery japan',
    'us approves japan', 'us reaffirms japan defense',
    'article v invoked', 'us military backing japan',
]


# ============================================
# ARTICLE 9 ESCALATION TRIPWIRES
# Japan-unique vector — constitutional reinterpretation language
# ============================================
ARTICLE9_L2_TRIGGERS = [
    'collective self-defense taiwan', 'japan collective self-defense',
    'potentially critical situation', 'japan situation gravely',
    'existential threat japan', 'reinterpretation discussion',
]

ARTICLE9_L3_TRIGGERS = [
    'cabinet approves new interpretation', 'cabinet decision article 9',
    'cabinet okays reinterpretation', 'kantei article 9 decision',
    'pm approves article 9 change',
]

ARTICLE9_L4_TRIGGERS = [
    'diet vote article 9', 'diet votes article 9',
    'lower house article 9', 'upper house article 9',
    'diet passes article 9', 'national diet article 9 reinterpretation',
    'security legislation passes', 'security legislation enacted',
]

ARTICLE9_L5_TRIGGERS = [
    'jsdf combat operations', 'jsdf in combat',
    'article 9 amendment ratified', 'constitution amended japan defense',
    'jsdf engages enemy', 'japan enters combat',
]


# ============================================
# TAIWAN DEFENSE COMMITMENT TRIPWIRES
# Specific to PM/Cabinet escalation on Taiwan
# ============================================
TAIWAN_DEFENSE_L3_TRIGGERS = [
    'japan would defend taiwan',
    'japan come to taiwan defense',
    'japan taiwan contingency',
    'japan taiwan emergency declared',
    'pm declares taiwan defense',
]

TAIWAN_DEFENSE_L4_TRIGGERS = [
    'japan invokes collective self-defense taiwan',
    'taiwan emergency situation declared',
    'taiwan contingency invoked',
    'jsdf mobilizes taiwan',
]


# ============================================
# STRIKE CAPABILITY MILESTONES
# Long-range / counter-strike deployment events
# ============================================
STRIKE_CAPABILITY_TRIGGERS = [
    'tomahawk delivery japan', 'tomahawk deployed japan',
    'tomahawk arrives japan', 'first tomahawk japan',
    'japan stand-off missile deployed', 'type-12 deployed',
    'japan strike capability operational',
    'japan counter-strike operational',
    'japan hypersonic deployed',
]


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
            timeout=8
        )
        data = resp.json()
        if not data.get('result'):
            return None
        return json.loads(data['result'])
    except Exception as e:
        print(f"[Japan Rhetoric] Redis GET error ({key}): {str(e)[:120]}")
        return None


def _redis_set(key, value, ttl_hours=CACHE_TTL_HOURS):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return False
    try:
        ttl_seconds = ttl_hours * 3600
        payload = json.dumps(value)
        url = f"{UPSTASH_REDIS_URL}/setex/{key}/{ttl_seconds}"
        resp = requests.post(
            url,
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            data=payload,
            timeout=8
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[Japan Rhetoric] Redis SET error ({key}): {str(e)[:120]}")
        return False


# ============================================
# RSS / DATA FETCHING
# ============================================
RSS_FEEDS = {
    'japan_times': {
        'name': 'Japan Times',
        'url': 'https://www.japantimes.co.jp/feed/',
        'weight': 1.0,
    },
    'mainichi_en': {
        'name': 'Mainichi English',
        'url': 'https://mainichi.jp/english/rss/etc/mainichi-english.rss',
        'weight': 0.95,
    },
    'kyodo_news': {
        'name': 'Kyodo News',
        'url': 'https://english.kyodonews.net/rss/news.xml',
        'weight': 0.95,
    },
    'nhk_world': {
        'name': 'NHK World',
        'url': 'https://www3.nhk.or.jp/nhkworld/en/news/all_news.xml',
        'weight': 0.9,
    },
    'nikkei_asia': {
        'name': 'Nikkei Asia',
        'url': 'https://asia.nikkei.com/rss/feed/nar',
        'weight': 0.95,
    },
    'reuters_japan': {
        'name': 'Reuters Japan',
        'url': 'https://news.google.com/rss/search?q=japan+china+taiwan+OR+japan+defense+OR+takaichi&hl=en&gl=US&ceid=US:en',
        'weight': 0.85,
    },
}


def fetch_rss_articles(feed_id, feed_config, max_articles=30):
    """Fetch articles from a single RSS feed."""
    try:
        resp = requests.get(feed_config['url'], timeout=RSS_TIMEOUT,
                           headers={'User-Agent': 'AsifahAnalytics-Japan/1.0'})
        if resp.status_code != 200:
            print(f"[Japan Rhetoric RSS] {feed_id}: HTTP {resp.status_code}")
            return []
        feed = feedparser.parse(resp.content)
        articles = []
        for entry in feed.entries[:max_articles]:
            articles.append({
                'title':       (entry.get('title') or '')[:300],
                'description': (entry.get('summary') or entry.get('description') or '')[:600],
                'url':         entry.get('link') or '',
                'publishedAt': entry.get('published') or entry.get('updated') or '',
                'source':      {'name': feed_config['name']},
                'content':     (entry.get('summary') or '')[:600],
                'language':    'en',
                'feed_type':   'rss',
                'source_weight_override': feed_config.get('weight', 1.0),
            })
        if articles:
            print(f"[Japan Rhetoric RSS] {feed_id}: {len(articles)} articles")
        return articles
    except Exception as e:
        print(f"[Japan Rhetoric RSS] {feed_id} error: {str(e)[:120]}")
        return []


def fetch_all_rss():
    """Fetch from all configured RSS feeds."""
    all_articles = []
    for feed_id, feed_config in RSS_FEEDS.items():
        articles = fetch_rss_articles(feed_id, feed_config)
        all_articles.extend(articles)
        time.sleep(0.4)
    return all_articles


# ============================================
# GDELT (English + Japanese)
# ============================================
GDELT_QUERIES_EN = [
    'Japan China military',
    'Senkaku Diaoyu islands',
    'Takaichi Taiwan defense',
    'JSDF deployment',
    'Article 9 Japan reinterpretation',
    'Japan counter-strike capability Tomahawk',
    'PLA Eastern Theater Japan',
    'Okinawa PLA pressure',
    'Japan North Korea missile',
    'Japan Russia Far East bombers',
    'Japan-Philippines defense agreement',
    'JMSDF Taiwan Strait transit',
    'Eastern China Sea Japan',
    'Japan Quad military',
]

GDELT_QUERIES_JA = [
    '自衛隊 中国',
    '尖閣諸島 中国',
    '高市 台湾',
    '反撃能力 配備',
    '北朝鮮 ミサイル 日本',
    '南西諸島 防衛',
    '日米共同訓練',
    '集団的自衛権',
]


def fetch_gdelt_query(query, language='eng', days=7, max_articles=50):
    """Fetch GDELT articles for a single query."""
    base_url = 'https://api.gdeltproject.org/api/v2/doc/doc'
    timespan = f'{days*24}h'
    params = {
        'query':         f'{query} sourcelang:{language}',
        'mode':          'ArtList',
        'maxrecords':    max_articles,
        'format':        'json',
        'timespan':      timespan,
        'sort':          'DateDesc',
    }
    try:
        resp = requests.get(base_url, params=params, timeout=GDELT_TIMEOUT)
        if resp.status_code == 429:
            print(f"[Japan GDELT] 429 rate limit on '{query[:40]}' — backing off")
            return []
        if resp.status_code != 200:
            return []
        data = resp.json()
        articles = []
        for art in data.get('articles', []):
            articles.append({
                'title':       (art.get('title') or '')[:300],
                'description': (art.get('title') or '')[:300],
                'url':         art.get('url') or '',
                'publishedAt': art.get('seendate') or '',
                'source':      {'name': art.get('domain') or 'GDELT'},
                'content':     (art.get('title') or '')[:300],
                'language':    language[:2],
                'feed_type':   'gdelt',
            })
        return articles
    except Exception as e:
        print(f"[Japan GDELT] '{query[:40]}' error: {str(e)[:100]}")
        return []


def fetch_all_gdelt(days=7):
    """Fetch GDELT for all configured queries (English + Japanese)."""
    all_articles = []
    for q in GDELT_QUERIES_EN:
        articles = fetch_gdelt_query(q, language='eng', days=days)
        all_articles.extend(articles)
        time.sleep(0.5)
    for q in GDELT_QUERIES_JA:
        articles = fetch_gdelt_query(q, language='jpn', days=days)
        all_articles.extend(articles)
        time.sleep(0.5)
    print(f"[Japan GDELT] Total: {len(all_articles)} articles")
    return all_articles


# ============================================
# NewsAPI
# ============================================
def fetch_newsapi(query, days=7):
    if not NEWSAPI_KEY:
        return []
    from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    try:
        resp = requests.get(
            'https://newsapi.org/v2/everything',
            params={
                'q':           query,
                'from':        from_date,
                'sortBy':      'publishedAt',
                'language':    'en',
                'apiKey':      NEWSAPI_KEY,
                'pageSize':    50,
            },
            timeout=NEWSAPI_TIMEOUT
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        articles = []
        for a in data.get('articles', []) or []:
            a['feed_type'] = 'newsapi'
            articles.append(a)
        return articles
    except Exception:
        return []


def fetch_all_newsapi(days=7):
    if not NEWSAPI_KEY:
        return []
    queries = [
        'Japan China Senkaku',
        'Takaichi Taiwan defense',
        'JSDF deployment Tomahawk',
        'Japan North Korea missile',
        'Article 9 Japan reinterpretation',
        'Okinawa PLA pressure',
    ]
    all_articles = []
    for q in queries:
        all_articles.extend(fetch_newsapi(q, days))
        time.sleep(0.4)
    print(f"[Japan NewsAPI] Total: {len(all_articles)} articles")
    return all_articles


# ============================================
# Brave (tertiary fallback)
# ============================================
def fetch_brave(query, days=7):
    if not BRAVE_API_KEY:
        return []
    try:
        resp = requests.get(
            'https://api.search.brave.com/res/v1/news/search',
            headers={
                'Accept':              'application/json',
                'Accept-Encoding':     'gzip',
                'X-Subscription-Token': BRAVE_API_KEY,
            },
            params={
                'q':           query,
                'count':       20,
                'freshness':   'pw' if days <= 7 else 'pm',
                'spellcheck':  'false',
            },
            timeout=BRAVE_TIMEOUT
        )
        if resp.status_code != 200:
            return []
        data = resp.json()
        articles = []
        for r in data.get('results', []) or []:
            articles.append({
                'title':       (r.get('title') or '')[:300],
                'description': (r.get('description') or '')[:500],
                'url':         r.get('url') or '',
                'publishedAt': r.get('age', '') or r.get('page_age', ''),
                'source':      {'name': (r.get('meta_url', {}) or {}).get('hostname', 'Brave')},
                'content':     (r.get('description') or '')[:500],
                'language':    'en',
                'feed_type':   'brave',
            })
        return articles
    except Exception:
        return []


def fetch_all_brave(days=7):
    if not BRAVE_API_KEY:
        return []
    queries = [
        'Takaichi Taiwan',
        'Senkaku islands incursion',
        'JSDF Tomahawk deployment',
        'Article 9 reinterpretation',
    ]
    all_articles = []
    for q in queries:
        all_articles.extend(fetch_brave(q, days))
        time.sleep(1.0)
    print(f"[Japan Brave] Total: {len(all_articles)} articles")
    return all_articles


# ============================================
# BlueSky (Asia accounts)
# ============================================
def fetch_bluesky_japan(days=7):
    """Fetch BlueSky posts targeted at Japan via Asia module."""
    if not BLUESKY_AVAILABLE:
        return []
    try:
        posts = fetch_bluesky_for_target('japan', days=days)
        for p in posts:
            p['feed_type'] = 'bluesky'
        return posts
    except Exception as e:
        print(f"[Japan BlueSky] Error: {str(e)[:120]}")
        return []


# ============================================
# ARTICLE SCORING / CLASSIFICATION
# ============================================
def _normalize_text(text):
    """Lowercase + Unicode-normalize for matching."""
    if not text:
        return ''
    return unicodedata.normalize('NFKC', text).lower()


def _classify_article_actor(article):
    """Match an article against actor keywords. Returns the best-matching
    actor key, or None if no match. Searches title + description + content."""
    text = ' '.join([
        article.get('title', '') or '',
        article.get('description', '') or '',
        article.get('content', '') or '',
    ])
    text_norm = _normalize_text(text)
    if not text_norm:
        return None

    best_actor = None
    best_match_count = 0
    for actor_key, keywords in ACTOR_KEYWORDS.items():
        match_count = 0
        for kw in keywords:
            if kw.lower() in text_norm:
                match_count += 1
        if match_count > best_match_count:
            best_match_count = match_count
            best_actor = actor_key
    return best_actor if best_match_count >= 1 else None


def _check_tripwires(text):
    """Check for tripwire phrases (Article 9, Taiwan defense, strike capability).
    Returns dict of which tripwires fired."""
    text_norm = _normalize_text(text)
    return {
        'article9_l2': any(t in text_norm for t in ARTICLE9_L2_TRIGGERS),
        'article9_l3': any(t in text_norm for t in ARTICLE9_L3_TRIGGERS),
        'article9_l4': any(t in text_norm for t in ARTICLE9_L4_TRIGGERS),
        'article9_l5': any(t in text_norm for t in ARTICLE9_L5_TRIGGERS),
        'taiwan_defense_l3': any(t in text_norm for t in TAIWAN_DEFENSE_L3_TRIGGERS),
        'taiwan_defense_l4': any(t in text_norm for t in TAIWAN_DEFENSE_L4_TRIGGERS),
        'strike_capability': any(t in text_norm for t in STRIKE_CAPABILITY_TRIGGERS),
        'reporting_language': any(t in text_norm for t in REPORTING_LANGUAGE),
        'brake_language':     any(t in text_norm for t in BRAKE_LANGUAGE),
        'greenlight_language': any(t in text_norm for t in GREENLIGHT_LANGUAGE),
    }


def _score_actor_articles(articles_for_actor, is_reporting=False):
    """Compute a level (0-5) for an actor based on article count + tripwires.
    Reporting actors (us_alliance) get a downgrade unless coordination/greenlight present."""
    if not articles_for_actor:
        return 0, {}

    # Aggregate tripwires across all articles for this actor
    aggregate_tripwires = {
        'article9_l2': False, 'article9_l3': False, 'article9_l4': False, 'article9_l5': False,
        'taiwan_defense_l3': False, 'taiwan_defense_l4': False,
        'strike_capability': False,
        'reporting_language': False, 'brake_language': False, 'greenlight_language': False,
    }
    for art in articles_for_actor:
        text = ' '.join([art.get('title', ''), art.get('description', ''), art.get('content', '')])
        tw = _check_tripwires(text)
        for k, v in tw.items():
            if v:
                aggregate_tripwires[k] = True

    article_count = len(articles_for_actor)

    # Tripwire-driven escalation (highest tripwire wins)
    if aggregate_tripwires['article9_l5']:
        level = 5
    elif aggregate_tripwires['article9_l4'] or aggregate_tripwires['taiwan_defense_l4']:
        level = 4
    elif aggregate_tripwires['article9_l3'] or aggregate_tripwires['taiwan_defense_l3'] or aggregate_tripwires['strike_capability']:
        level = 3
    elif aggregate_tripwires['article9_l2']:
        level = 2
    else:
        # Volume-driven escalation
        if article_count >= 25:
            level = 4
        elif article_count >= 15:
            level = 3
        elif article_count >= 8:
            level = 2
        elif article_count >= 3:
            level = 1
        else:
            level = 0

    # Reporting actor downgrade (unless greenlight)
    if is_reporting:
        if aggregate_tripwires['greenlight_language']:
            pass  # no downgrade
        elif aggregate_tripwires['reporting_language']:
            level = max(0, level - 1)

    return level, aggregate_tripwires


# ============================================
# CROSS-THEATER FINGERPRINT READS
# ============================================
def _read_crosstheater_amplifiers():
    """Read fingerprints from China + Taiwan trackers to amplify Japan inbound.
    Returns dict of amplifier modifiers (additive to actor levels)."""
    amplifiers = {}
    fingerprints = _redis_get(CROSSTHEATER_KEY) or {}

    # China outbound L3+ amplifies china_threat by +1
    china_fp = fingerprints.get('china', {}) or {}
    china_outbound = int(china_fp.get('outbound_max_level', 0) or 0)
    if china_outbound >= 3:
        amplifiers['china_threat'] = +1
        print(f"[Japan Rhetoric] China outbound at L{china_outbound} — amplifying china_threat +1")

    # Taiwan tracker reading PLA pressure on Taiwan amplifies taiwan_strait_proximity
    taiwan_fp = fingerprints.get('taiwan', {}) or {}
    taiwan_china_pressure = int(taiwan_fp.get('china_pressure_level', 0) or
                                 taiwan_fp.get('outbound_max_level', 0) or 0)
    if taiwan_china_pressure >= 3:
        amplifiers['taiwan_strait_proximity'] = +1
        print(f"[Japan Rhetoric] Taiwan pressure at L{taiwan_china_pressure} — amplifying taiwan_strait_proximity +1")

    return amplifiers


# ============================================
# CROSS-THEATER FINGERPRINT WRITES
# ============================================
def _write_crosstheater_fingerprint(actor_levels, actor_tripwires,
                                    inbound_max, outbound_max, overall_level):
    """Write Japan fingerprint to shared Redis cross-theater key."""
    fingerprints = _redis_get(CROSSTHEATER_KEY) or {}

    # Aggregate tripwire flags across all relevant actors
    pm_tw = actor_tripwires.get('pm_cabinet', {}) or {}
    mod_tw = actor_tripwires.get('mod_jsdf', {}) or {}
    diet_tw = actor_tripwires.get('ldp_diet', {}) or {}

    article9_active = (pm_tw.get('article9_l2') or pm_tw.get('article9_l3') or
                       pm_tw.get('article9_l4') or pm_tw.get('article9_l5') or
                       diet_tw.get('article9_l3') or diet_tw.get('article9_l4'))
    taiwan_defense_active = (pm_tw.get('taiwan_defense_l3') or pm_tw.get('taiwan_defense_l4'))
    strike_capability_milestone = (mod_tw.get('strike_capability') or
                                   pm_tw.get('strike_capability'))

    fingerprints['japan'] = {
        'overall_level':              int(overall_level),
        'inbound_max_level':          int(inbound_max),
        'outbound_max_level':         int(outbound_max),
        'taiwan_defense_active':      bool(taiwan_defense_active),
        'article9_active':            bool(article9_active),
        'senkaku_active':             int(actor_levels.get('senkaku_intrusion', 0)) >= 3,
        'okinawa_pla_active':         int(actor_levels.get('okinawa_pressure', 0)) >= 3,
        'strike_capability_milestone': bool(strike_capability_milestone),
        'china_japan_friction':       int(actor_levels.get('china_threat', 0)),
        'dprk_japan_threat':          int(actor_levels.get('dprk_threat', 0)),
        'updated_at':                 datetime.now(timezone.utc).isoformat(),
    }
    _redis_set(CROSSTHEATER_KEY, fingerprints, ttl_hours=24)
    print(f"[Japan Rhetoric] Cross-theater fingerprint written (overall L{overall_level}, inbound L{inbound_max}, outbound L{outbound_max})")


# ============================================
# MAIN SCAN
# ============================================
def scan_japan_rhetoric(force=False, days=7):
    """Full scan: fetch articles, classify by actor, score levels, write cache."""
    if not force:
        cached = _redis_get(CACHE_KEY)
        if cached and cached.get('updated_at'):
            try:
                ts = datetime.fromisoformat(cached['updated_at'].replace('Z', '+00:00'))
                if datetime.now(timezone.utc) - ts < timedelta(hours=CACHE_TTL_HOURS):
                    print("[Japan Rhetoric] Cache hit — returning cached scan")
                    return cached
            except Exception:
                pass

    print("[Japan Rhetoric] Starting fresh scan...")

    # ── Fetch from all sources ──
    rss_articles    = fetch_all_rss()
    gdelt_articles  = fetch_all_gdelt(days=days)
    newsapi_articles = fetch_all_newsapi(days=days)

    # Brave fallback if upstream sparse
    brave_articles = []
    if (len(gdelt_articles) + len(newsapi_articles)) < 10:
        print("[Japan Rhetoric] Upstream sparse — firing Brave fallback")
        brave_articles = fetch_all_brave(days=days)

    bluesky_articles = fetch_bluesky_japan(days=days)

    all_articles = rss_articles + gdelt_articles + newsapi_articles + brave_articles + bluesky_articles
    print(f"[Japan Rhetoric] Total articles fetched: {len(all_articles)}")

    # ── Deduplicate by URL ──
    seen_urls = set()
    deduped = []
    for art in all_articles:
        url = art.get('url', '')
        if url and url not in seen_urls:
            seen_urls.add(url)
            deduped.append(art)
    print(f"[Japan Rhetoric] After dedup: {len(deduped)} articles")

    # ── Classify each article by actor ──
    by_actor = {k: [] for k in ACTORS.keys()}
    unclassified = []
    for art in deduped:
        actor = _classify_article_actor(art)
        if actor:
            by_actor[actor].append(art)
        else:
            unclassified.append(art)

    # ── Score each actor ──
    actor_levels = {}
    actor_tripwires = {}
    actor_article_counts = {}
    for actor_key in ACTORS.keys():
        is_reporting = actor_key in REPORTING_ACTORS
        articles_for_this_actor = by_actor.get(actor_key, [])
        level, tripwires = _score_actor_articles(articles_for_this_actor, is_reporting=is_reporting)
        actor_levels[actor_key] = level
        actor_tripwires[actor_key] = tripwires
        actor_article_counts[actor_key] = len(articles_for_this_actor)

    # ── Apply cross-theater amplifiers ──
    amplifiers = _read_crosstheater_amplifiers()
    for actor_key, delta in amplifiers.items():
        if actor_key in actor_levels:
            new_level = min(5, actor_levels[actor_key] + delta)
            print(f"[Japan Rhetoric] Cross-theater amplifier: {actor_key} L{actor_levels[actor_key]} → L{new_level}")
            actor_levels[actor_key] = new_level

    # ── Compute inbound + outbound max levels ──
    inbound_max = max((actor_levels[a] for a in INBOUND_ACTORS if a in actor_levels), default=0)
    outbound_max = max((actor_levels[a] for a in OUTBOUND_ACTORS if a in actor_levels), default=0)
    overall_level = max(inbound_max, outbound_max)

    # ── Compute theatre score (0-100) ──
    # Weighted: inbound contributes ~50%, outbound ~50%
    inbound_score = inbound_max * 10  # 0-50
    outbound_score = outbound_max * 10  # 0-50
    # Convergence bonus: +5 if both inbound AND outbound at L3+
    convergence_bonus = 5 if (inbound_max >= 3 and outbound_max >= 3) else 0
    theatre_score = min(100, inbound_score + outbound_score + convergence_bonus)

    # ── Determine alert level ──
    if overall_level >= 5:
        alert_level = 'kinetic'
    elif overall_level >= 4:
        alert_level = 'critical'
    elif overall_level >= 3:
        alert_level = 'high'
    elif overall_level >= 2:
        alert_level = 'elevated'
    elif overall_level >= 1:
        alert_level = 'rhetoric'
    else:
        alert_level = 'normal'

    # ── Write cross-theater fingerprint ──
    _write_crosstheater_fingerprint(actor_levels, actor_tripwires,
                                    inbound_max, outbound_max, overall_level)

    # ── Build top articles list for frontend ──
    top_articles = []
    for actor_key, articles in by_actor.items():
        if not articles:
            continue
        # Take top 5 articles per actor (most recent first)
        sorted_articles = sorted(articles,
                                key=lambda a: a.get('publishedAt', ''),
                                reverse=True)[:5]
        for art in sorted_articles:
            top_articles.append({
                'title':       art.get('title', '')[:300],
                'url':         art.get('url', ''),
                'source':      art.get('source', {}).get('name', 'Unknown'),
                'published':   art.get('publishedAt', ''),
                'actor':       actor_key,
                'feed_type':   art.get('feed_type', 'unknown'),
                'language':    art.get('language', 'en'),
            })

    # ── Build payload ──
    payload = {
        'theatre':              'japan',
        'theatre_score':        theatre_score,
        'overall_level':        overall_level,
        'inbound_max_level':    inbound_max,
        'outbound_max_level':   outbound_max,
        'alert_level':          alert_level,
        'level_label':          LEVEL_LABELS.get(overall_level, 'Baseline'),
        'level_color':          LEVEL_COLORS.get(overall_level, '#6b7280'),
        'actors':               {k: {
            'name':         ACTORS[k]['name'],
            'flag':         ACTORS[k]['flag'],
            'icon':         ACTORS[k]['icon'],
            'color':        ACTORS[k]['color'],
            'role':         ACTORS[k]['role'],
            'description':  ACTORS[k]['description'],
            'level':        actor_levels.get(k, 0),
            'level_label':  LEVEL_LABELS.get(actor_levels.get(k, 0), 'Baseline'),
            'level_color':  LEVEL_COLORS.get(actor_levels.get(k, 0), '#6b7280'),
            'article_count': actor_article_counts.get(k, 0),
            'is_inbound':   k in INBOUND_ACTORS,
            'is_outbound':  k in OUTBOUND_ACTORS,
            'is_reporting': k in REPORTING_ACTORS,
            'tripwires':    actor_tripwires.get(k, {}),
        } for k in ACTORS.keys()},
        'inbound_actors':       INBOUND_ACTORS,
        'outbound_actors':      OUTBOUND_ACTORS,
        'total_articles':       len(deduped),
        'classified_articles':  sum(actor_article_counts.values()),
        'top_articles':         top_articles[:50],  # Top 50 across all actors
        'sources_breakdown':    {
            'rss':       len(rss_articles),
            'gdelt':     len(gdelt_articles),
            'newsapi':   len(newsapi_articles),
            'brave':     len(brave_articles),
            'bluesky':   len(bluesky_articles),
        },
        'cross_theater_amplifiers': amplifiers,
        'updated_at':           datetime.now(timezone.utc).isoformat(),
        'version':              '1.0.0',
    }

    # ── Cache result ──
    _redis_set(CACHE_KEY, payload, ttl_hours=CACHE_TTL_HOURS)
    _redis_set(ARTICLES_KEY, top_articles, ttl_hours=CACHE_TTL_HOURS)

    print(f"[Japan Rhetoric] Scan complete — score={theatre_score}, overall={overall_level}, inbound={inbound_max}, outbound={outbound_max}")
    return payload


# ============================================
# BACKGROUND REFRESH
# ============================================
_japan_refresh_thread = None
_japan_refresh_stop = threading.Event()


def _background_refresh_loop():
    """Loop that periodically refreshes the cache."""
    print("[Japan Rhetoric] Background refresh thread started")
    # Initial boot delay
    time.sleep(90)
    while not _japan_refresh_stop.is_set():
        try:
            scan_japan_rhetoric(force=True)
        except Exception as e:
            print(f"[Japan Rhetoric] Background refresh error: {str(e)[:200]}")
        # Sleep until next refresh
        for _ in range(BACKGROUND_REFRESH_HOURS * 3600):
            if _japan_refresh_stop.is_set():
                return
            time.sleep(1)


def _start_background_refresh():
    global _japan_refresh_thread
    if _japan_refresh_thread is None or not _japan_refresh_thread.is_alive():
        _japan_refresh_thread = threading.Thread(target=_background_refresh_loop, daemon=True)
        _japan_refresh_thread.start()


# ============================================
# FLASK ENDPOINT REGISTRATION
# ============================================
def register_japan_rhetoric_endpoints(app):
    """Register Japan rhetoric tracker endpoints with the Flask app."""

    # Optional interpreter — non-fatal if missing
    try:
        from japan_signal_interpreter import interpret_japan_signals
        _INTERPRETER_AVAILABLE = True
    except ImportError:
        _INTERPRETER_AVAILABLE = False
        print("[Japan Rhetoric] ⚠️ japan_signal_interpreter not available (frontend will synthesize)")

    @app.route('/api/rhetoric/japan', methods=['GET'])
    def api_rhetoric_japan():
        from flask import request
        force = request.args.get('force', '').lower() in ('true', '1', 'yes')
        try:
            data = scan_japan_rhetoric(force=force)
            # Inject So What card if interpreter is available
            if _INTERPRETER_AVAILABLE and data and not data.get('so_what'):
                try:
                    so_what = interpret_japan_signals(data)
                    if so_what:
                        data['so_what'] = so_what
                except Exception as ie:
                    print(f"[Japan Rhetoric] Interpreter error (non-fatal): {str(ie)[:150]}")
            return jsonify(data)
        except Exception as e:
            print(f"[Japan Rhetoric] /api/rhetoric/japan error: {str(e)[:200]}")
            return jsonify({
                'error':   str(e)[:200],
                'theatre': 'japan',
                'success': False,
            }), 500

    @app.route('/api/rhetoric/japan/summary', methods=['GET'])
    def api_rhetoric_japan_summary():
        try:
            data = scan_japan_rhetoric(force=False)
            return jsonify({
                'theatre':            'japan',
                'theatre_score':      data.get('theatre_score', 0),
                'overall_level':      data.get('overall_level', 0),
                'inbound_max_level':  data.get('inbound_max_level', 0),
                'outbound_max_level': data.get('outbound_max_level', 0),
                'alert_level':        data.get('alert_level', 'normal'),
                'level_label':        data.get('level_label', 'Baseline'),
                'updated_at':         data.get('updated_at', ''),
            })
        except Exception as e:
            return jsonify({'error': str(e)[:200]}), 500

    @app.route('/api/rhetoric/japan/articles', methods=['GET'])
    def api_rhetoric_japan_articles():
        try:
            articles = _redis_get(ARTICLES_KEY) or []
            return jsonify({
                'theatre':  'japan',
                'count':    len(articles),
                'articles': articles,
            })
        except Exception as e:
            return jsonify({'error': str(e)[:200]}), 500

    # Start background refresh on registration
    _start_background_refresh()
    print("[Japan Rhetoric] Endpoints registered: /api/rhetoric/japan, /summary, /articles")
