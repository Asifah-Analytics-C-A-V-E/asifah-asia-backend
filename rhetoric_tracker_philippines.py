# -*- coding: utf-8 -*-
"""
Asifah Analytics -- Philippines West Philippine Sea & Alliance Tracker
v1.0.0 -- November 2, 2026

ANALYTICAL FRAME
  The Philippines is the South China Sea claimant with a US treaty ally's
  trip-wire built in. Vietnam's question is "is Hanoi keeping pace?"; Manila's
  is sharper:

    "What is China doing to the Philippines at sea right now -- is Manila
     (and its partners) answering -- and is anything approaching the line
     where the 1951 Mutual Defense Treaty stops being a talking point?"

  Second Thomas (Ayungin) Shoal and the grounded BRP Sierra Madre, Scarborough
  (Bajo de Masinloc), Sabina (Escoda) and Thitu (Pag-asa) are where a gray-zone
  incident can become an alliance event. That is what makes this theatre
  different from Vietnam: a Filipino death caused by Chinese action is a
  question for Washington, not just for Manila.

DASHBOARDS
  OUTBOUND -- "Is Manila asserting and defending?"
    marcos_state       Palace / DFA / NSC / National Maritime Council: protests, lawfare
    afp_pcg            AFP + Philippine Coast Guard: resupply runs, patrols, posture
    us_alliance        MDT / EDCA / Balikatan / Typhon-NMESIS deployments
    regional_partners  Japan RAA, Australia SOVFA, Vietnam, India (BrahMos), others
  INBOUND -- "What is China doing to the Philippines?"
    china_scs_pressure CCG + maritime militia: water cannon, ramming, blocking, lasers
    beijing_coercion   MFA, "nature reserve" / baseline claims, sovereignty lawfare
    economic_pressure  trade, tourism, banana-style coercion
  INTERNAL -- "Is the home front holding?"
    duterte_faction    Marcos-Duterte rupture: impeachment, ICC, the pro-Beijing pull

KEY METRIC
  COERCION-RESPONSE GAP = inbound China pressure - max(Manila response,
  partner response). Same idea as Vietnam's gap; the difference is that for
  Manila the partner side has a treaty in it.

SENSOR DESIGN (lessons from the Nov 2 2026 Africa + Asia debug)
  * Literal trigger ladders are kept as one input, but the CO-OCCURRENCE
    matcher (asia_signal_matcher.py, profile 'philippines') is the main
    engine: "China water-cannons Philippine boat near Second Thomas Shoal"
    fires without anyone having written that exact sentence into a list.
  * L3+ needs two outlets. One outlet tops out at L2.
  * GDELT goes through gdelt_gateway (shared budget). No direct NewsAPI
    (the per-tracker key was deleted Oct 18; the gateway serves app.py).
  * CORPUS HEALTH: a thin corpus is reported as thin, never as quiet.
    Unread is not quiet.
  * Background scan is leader-gated across gunicorn workers (Redis NX lock),
    so two workers do not both spend the GDELT budget.

DISCIPLINE: convergence framing, not prediction. The tracker reports which
signals are present and what they would mean together; it never says whether
kinetic action is coming.

REDIS KEYS
  rhetoric:philippines:latest     (cache, read by the Asia BLUF + Actor Matrix)
  rhetoric:philippines:history    (history list)
  rhetoric:crosstheater:fingerprints   (READS china / taiwan / vietnam, WRITES philippines)

ENDPOINTS
  GET /api/rhetoric/philippines            (?force=true runs a scan -- no paid API, no LLM)
  GET /api/rhetoric/philippines/summary
  GET /api/rhetoric/philippines/history

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

try:
    from asia_signal_matcher import apply_actor_cooccurrence as _asia_cooc
except Exception as _e:
    print(f"[Philippines Rhetoric] asia_signal_matcher unavailable: {_e}")
    _asia_cooc = None

try:
    from gdelt_gateway import gdelt_fetch_probed as _gw_gdelt
    _GDELT_GATEWAY = True
except Exception:
    _GDELT_GATEWAY = False
    print("[Philippines Rhetoric] gdelt_gateway not available -- GDELT skipped (no direct calls)")

try:
    from butterfly_proxy_asia import read_butterfly_signals_via_proxy
    _BUTTERFLY_AVAILABLE = True
except ImportError:
    _BUTTERFLY_AVAILABLE = False

try:
    from convergence_proxy_asia import find_convergences_for_country_proxy
    _CONVERGENCE_PROXY_AVAILABLE = True
except ImportError:
    _CONVERGENCE_PROXY_AVAILABLE = False

try:
    from telegram_signals_asia import fetch_asia_telegram_signals
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False

TRACKER_VERSION = '1.1.0-philippines'

# ============================================
# CONFIG
# ============================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN') or os.environ.get('UPSTASH_REDIS_REST_TOKEN')

RHETORIC_CACHE_KEY = 'rhetoric:philippines:latest'
HISTORY_KEY        = 'rhetoric:philippines:history'
CROSSTHEATER_KEY   = 'rhetoric:crosstheater:fingerprints'
SCAN_LOCK_KEY      = 'rhetoric:philippines:scan_lock'

SCAN_INTERVAL_HOURS = 6
MIN_HEALTHY_CORPUS  = 40     # below this, 'quiet' is not a finding

_rhetoric_running = False
_rhetoric_lock    = threading.Lock()


# ============================================
# ESCALATION LEVELS (same rungs as the Vietnam SCS tracker)
# ============================================
ESCALATION_LEVELS = {
    0: {'label': 'Baseline',        'color': '#6b7280', 'description': 'Routine WPS activity, no significant signals'},
    1: {'label': 'Rhetoric',        'color': '#3b82f6', 'description': 'Standard sovereignty statements, routine patrols'},
    2: {'label': 'Warning',         'color': '#f59e0b', 'description': 'Elevated CCG/militia presence, protests, mild coercion'},
    3: {'label': 'Confrontation',   'color': '#f97316', 'description': 'Blocking, shadowing, swarming, sustained gray-zone pressure'},
    4: {'label': 'High Alert',      'color': '#ef4444', 'description': 'Water cannon, ramming, boarding, injuries, resupply interdicted'},
    5: {'label': 'Active Conflict', 'color': '#dc2626', 'description': 'Deaths, vessel sunk, kinetic exchange, MDT invoked'},
}


# ============================================
# ACTORS
# ============================================
def _actor(name, flag, icon, color, dashboard, role, description, keywords, tripwires):
    return {'name': name, 'flag': flag, 'icon': icon, 'color': color, 'dashboard': dashboard,
            'role': role, 'description': description, 'keywords': keywords, 'tripwires': tripwires}

ACTORS = {
    # -- OUTBOUND --------------------------------------------------
    'marcos_state': _actor(
        'Palace / DFA / NSC', '🇵🇭', '🏛️', '#1d4ed8', 'outbound',
        'Diplomatic Protest / Lawfare / Policy Signals',
        'Malacanang, the Department of Foreign Affairs, the National Security Council and the '
        'National Maritime Council: diplomatic protests, summonses, the 2016 arbitral award, '
        'and how hard Manila is prepared to name and shame Beijing.',
        ['marcos', 'malacanang', 'malacañang', 'philippine foreign affairs', 'dfa philippines',
         'philippine foreign secretary', 'national maritime council', 'philippine national security council',
         'diplomatic protest', 'arbitral award', 'arbitral ruling', 'west philippine sea',
         'philippines protests', 'manila protests', 'philippine government', 'philippines summons',
         'tarriela', 'note verbale', 'lazaro', 'manalo'],
        ['philippines recalls ambassador', 'philippines expels chinese', 'philippines severs'],
    ),
    'afp_pcg': _actor(
        'AFP / Philippine Coast Guard', '🇵🇭', '⚓', '#b91c1c', 'outbound',
        'Resupply / Patrols / Posture',
        'Armed Forces of the Philippines and the Philippine Coast Guard (plus BFAR): rotation-and-resupply '
        'runs to the BRP Sierra Madre, patrols at Scarborough and Sabina, missile and shore-defence posture.',
        ['philippine coast guard', 'pcg', 'armed forces of the philippines', 'philippine navy',
         'philippine military', 'afp chief', 'brawner', 'teodoro', 'bfar', 'sierra madre',
         'rotation and resupply', 'resupply mission', 'philippine troops', 'philippine air force',
         'philippine marines', 'brp ', 'ayungin', 'second thomas', 'scarborough', 'escoda'],
        ['philippine navy fires', 'philippines deploys warships to scarborough'],
    ),
    'us_alliance': _actor(
        'US-Philippines Alliance', '🇺🇸', '🤝', '#2563eb', 'outbound',
        'MDT / EDCA / Balikatan / Deployments',
        'The 1951 Mutual Defense Treaty and its working parts: EDCA sites, Balikatan and KAMANDAG, the '
        'Typhon and NMESIS deployments, Task Force Philippines, and every statement that Article IV covers '
        'Philippine coast guard vessels anywhere in the South China Sea.',
        ['mutual defense treaty', 'mutual defence treaty', 'edca', 'balikatan', 'kamandag', 'typhon',
         'nmesis', 'us philippines', 'u.s.-philippines', 'us-philippine', 'united states philippines',
         'task force philippines', 'indopacom philippines', 'hegseth manila', 'rubio manila',
         'us troops philippines', 'us marines philippines', 'article iv', 'ironclad', 'us ally philippines'],
        ['mutual defense treaty invoked', 'invokes mutual defense treaty', 'us invokes article iv'],
    ),
    'regional_partners': _actor(
        'Regional Partners', '🌏', '🧭', '#7c3aed', 'outbound',
        'Japan / Australia / Vietnam / India / Others',
        'The partnership web that turns a bilateral dispute into a coalition question: the Japan '
        'Reciprocal Access Agreement, Australian and Canadian visiting-forces deals, joint sails '
        '(maritime cooperative activities), BrahMos from India, and Philippines-Vietnam coast guard ties.',
        ['reciprocal access agreement', 'japan philippines', 'philippines japan', 'australia philippines',
         'philippines australia', 'vietnam philippines', 'philippines vietnam', 'india philippines',
         'brahmos', 'maritime cooperative activity', 'joint sail', 'visiting forces agreement',
         'sofva', 'canada philippines', 'france philippines', 'new zealand philippines',
         'south korea philippines', 'asean code of conduct', 'philippines asean chair'],
        ['japan troops philippines', 'japan philippines defense pact'],
    ),
    # -- INBOUND ---------------------------------------------------
    'china_scs_pressure': _actor(
        'China at Sea (CCG / Militia / PLAN)', '🇨🇳', '⚔️', '#dc2626', 'inbound',
        'Coast Guard / Maritime Militia / Navy',
        'China Coast Guard, maritime militia and PLA Navy action against Philippine vessels and features: '
        'water cannon, ramming, blocking, lasers, flares at aircraft, boarding and seizure, swarming of '
        'Philippine-held features, and any change to who physically holds what.',
        ['china coast guard', 'chinese coast guard', 'ccg', 'maritime militia', 'chinese vessels',
         'chinese ships', 'water cannon', 'rammed', 'chinese navy', 'pla navy', 'west philippine sea',
         'scarborough', 'second thomas', 'ayungin', 'sabina', 'pag-asa', 'thitu', 'sandy cay',
         'huangyan', '中国海警'],
        ['filipino killed china', 'sierra madre seized', 'china seizes sierra madre',
         'china sinks philippine', 'philippine sailor killed'],
    ),
    'beijing_coercion': _actor(
        'Beijing Political Coercion', '🇨🇳', '📢', '#7c3aed', 'inbound',
        'MFA / Claims / Lawfare at Manila',
        'Beijing\'s political track against Manila: MFA and CCG statements, the Scarborough "nature reserve" '
        'and baselines, rejection of the 2016 award, warnings over US missiles, and sanctions on Filipino '
        'officials.',
        ['chinese foreign ministry', 'china foreign ministry', 'beijing warns', 'china warns philippines',
         'china accuses philippines', 'nature reserve', 'huangyan dao', 'china sanctions philippine',
         'chinese embassy manila', 'china rejects arbitral', 'lin jian', 'mao ning', 'guo jiakun',
         'china coast guard spokesperson', 'liu dejun', 'gan yu', '黄岩岛', '仁爱礁'],
        ['china declares scarborough', 'china annexes scarborough', 'china adiz south china sea'],
    ),
    'economic_pressure': _actor(
        'China Economic Pressure', '🇨🇳', '💹', '#d97706', 'inbound',
        'Trade / Tourism / Investment Leverage',
        'China\'s economic leverage on Manila: agricultural import bans (the 2012 banana precedent), tourism '
        'advisories, investment freezes and customs friction.',
        ['china bans philippine', 'philippine bananas', 'china tourism philippines', 'chinese tourists philippines',
         'china trade philippines', 'philippines china trade', 'china investment philippines',
         'china import ban philippines', 'china travel advisory philippines', 'pogo', 'chinese investment'],
        ['china trade embargo philippines', 'china bans all philippine imports'],
    ),
    # -- INTERNAL --------------------------------------------------
    'duterte_faction': _actor(
        'Marcos-Duterte Rupture', '🇵🇭', '⚖️', '#a16207', 'internal',
        'Domestic Cohesion / The Pro-Beijing Pull',
        'The home front: Vice President Sara Duterte\'s impeachment fight, Rodrigo Duterte\'s ICC case, '
        'and the faction that has historically argued for accommodation with Beijing. A divided Manila '
        'answers the sea more slowly.',
        ['duterte', 'sara duterte', 'rodrigo duterte', 'impeachment', 'icc duterte', 'vice president duterte',
         'duterte supporters', 'duterte rally', 'davao'],
        ['duterte destabilization plot', 'coup philippines'],
    ),
}

# L5 ASSERTION RULE (Rachel, Oct 6 2026): only a ladder that measures hostilities
# may assert L5 Active Conflict. China at sea (deaths / sinking) and the AFP/PCG
# (Philippine forces firing) can; diplomatic, economic, alliance and domestic
# political ladders top out at L4 however loud they get.
ACTOR_LEVEL_CAP = {
    'china_scs_pressure': 5, 'afp_pcg': 5,
    'beijing_coercion': 4, 'economic_pressure': 4, 'marcos_state': 4,
    'us_alliance': 4, 'regional_partners': 4, 'duterte_faction': 4,
}

# Plain-language names for the one-line top indicator on cards and the BLUF.
PLAIN_ACTOR = {
    'china_scs_pressure': "Chinese coast guard and militia pressure on Philippine vessels and features",
    'beijing_coercion':   "Beijing's political and legal pressure on Manila",
    'economic_pressure':  "Chinese economic pressure on the Philippines",
    'marcos_state':       "Manila's diplomatic response (Palace / DFA)",
    'afp_pcg':            "Philippine military and coast guard activity",
    'us_alliance':        "US-Philippine alliance activity",
    'regional_partners':  "Japan, Australia and other partners' activity with the Philippines",
    'duterte_faction':    "The Marcos-Duterte political split",
}

OUTBOUND_ACTOR_KEYS = ['marcos_state', 'afp_pcg', 'us_alliance', 'regional_partners']
INBOUND_ACTOR_KEYS  = ['china_scs_pressure', 'beijing_coercion', 'economic_pressure']
INTERNAL_ACTOR_KEYS = ['duterte_faction']
REPORTING_ACTORS    = set(INBOUND_ACTOR_KEYS)

# Every actor needs the article to be ABOUT the Philippines first -- otherwise
# 'beijing warns' on a Taiwan story or 'impeachment' on a US story would count.
PH_GATE = ['philippine', 'philippines', 'filipino', 'manila', 'marcos', 'duterte', 'pilipinas',
           'west philippine sea', 'scarborough', 'bajo de masinloc', 'second thomas', 'ayungin',
           'sierra madre', 'sabina', 'escoda', 'pag-asa', 'thitu', 'reed bank', 'recto bank',
           'malacanang', 'malacañang', '菲律宾', '菲律賓', 'tsina']
WEATHER_TERMS = ['typhoon', 'storm', 'flood', 'landslide', 'earthquake', 'bagyo', 'capsiz', 'tsunami']
REPORTING_LANGUAGE  = ['according to', 'reports that', 'said in a statement', 'monitors', 'tracks',
                       'detected', 'observed', 'expresses concern', 'deeply concerned', '谴责', '关切']


# ============================================
# LITERAL TRIGGER LADDERS (kept short -- the co-occurrence matcher is the main engine)
# ============================================
TRIGGERS = {
    'marcos_state': {
        5: ['philippines recalls ambassador', 'philippines severs ties'],
        4: ['philippines summons chinese ambassador', 'files new arbitration', 'second arbitration case'],
        3: ['diplomatic protest', 'note verbale', 'arbitral award', 'arbitral ruling', 'philippines protests'],
        2: ['west philippine sea', 'national maritime council', 'marcos china', 'dfa china'],
        1: ['philippine foreign affairs', 'malacanang', 'malacañang'],
    },
    'afp_pcg': {
        5: ['philippine navy fires', 'philippines returns fire'],
        4: ['resupply blocked', 'resupply mission blocked', 'sierra madre resupply', 'deploys warships'],
        3: ['rotation and resupply', 'resupply mission', 'coast guard patrol', 'brahmos', 'typhon'],
        2: ['philippine coast guard', 'armed forces of the philippines', 'philippine navy'],
        1: ['philippine military', 'afp chief'],
    },
    'us_alliance': {
        5: ['invokes mutual defense treaty', 'mutual defense treaty invoked'],
        4: ['article iv', 'typhon', 'nmesis', 'task force philippines'],
        3: ['mutual defense treaty', 'edca', 'balikatan', 'kamandag', 'us troops philippines'],
        2: ['us philippines', 'u.s.-philippines', 'us-philippine', 'ironclad'],
        1: ['united states philippines'],
    },
    'regional_partners': {
        5: ['japan philippines defense pact'],
        4: ['reciprocal access agreement', 'brahmos', 'visiting forces agreement'],
        3: ['maritime cooperative activity', 'joint sail', 'sofva'],
        2: ['japan philippines', 'australia philippines', 'vietnam philippines', 'india philippines'],
        1: ['asean code of conduct'],
    },
    'china_scs_pressure': {
        5: ['philippine sailor killed', 'china sinks philippine'],
        4: ['water cannon', 'water-cannon', 'rammed', 'rams philippine', 'laser', 'boarded', 'seized'],
        3: ['blocked', 'dangerous maneuver', 'swarm', 'maritime militia', 'shadowed'],
        2: ['china coast guard', 'chinese coast guard', 'ccg', 'chinese vessels'],
        1: ['west philippine sea'],
    },
    'beijing_coercion': {
        5: ['china annexes scarborough', 'china adiz south china sea'],
        4: ['nature reserve', 'baselines', 'china sanctions philippine'],
        3: ['china warns philippines', 'beijing warns', 'china accuses philippines'],
        2: ['chinese foreign ministry', 'china foreign ministry', 'chinese embassy manila'],
        1: ['china philippines'],
    },
    'economic_pressure': {
        5: ['china trade embargo philippines'],
        4: ['china bans philippine', 'china import ban philippines'],
        3: ['china travel advisory philippines', 'philippine bananas'],
        2: ['china trade philippines', 'china investment philippines'],
        1: ['chinese tourists philippines'],
    },
    'duterte_faction': {
        5: ['coup philippines'],
        4: ['duterte arrested', 'sara duterte impeached', 'impeachment trial'],
        3: ['impeachment', 'icc duterte', 'duterte rally'],
        2: ['sara duterte', 'rodrigo duterte'],
        1: ['duterte'],
    },
}


# ============================================
# SOURCES
# ============================================
# Outlet feeds are best-effort: each feed's article count is reported in
# source_health so a dead feed shows up in /debug instead of vanishing.
RSS_SOURCES = {
    'inquirer_globalnation': {'url': 'https://globalnation.inquirer.net/feed', 'name': 'Inquirer Global Nation', 'weight': 0.9},
    'inquirer_news':         {'url': 'https://newsinfo.inquirer.net/feed',     'name': 'Inquirer',               'weight': 0.85},
    'philstar':              {'url': 'https://www.philstar.com/rss/headlines', 'name': 'Philstar',               'weight': 0.85},
    'rappler':               {'url': 'https://www.rappler.com/feed/',          'name': 'Rappler',                'weight': 0.85},
    'gma':                   {'url': 'https://data.gmanetwork.com/gno/rss/news/feed.xml', 'name': 'GMA News',   'weight': 0.85},
    'pna':                   {'url': 'https://www.pna.gov.ph/latest.rss',      'name': 'Philippine News Agency', 'weight': 0.8},
    'benar_news':            {'url': 'https://www.benarnews.org/english/rss2.xml', 'name': 'BenarNews',          'weight': 0.85},
    'csis_amti':             {'url': 'https://amti.csis.org/feed/',            'name': 'CSIS AMTI',              'weight': 0.95},
    'usni_news':             {'url': 'https://news.usni.org/feed',             'name': 'USNI News',              'weight': 1.0},
    'the_diplomat':          {'url': 'https://thediplomat.com/feed/',          'name': 'The Diplomat',           'weight': 0.9},
    'scmp':                  {'url': 'https://www.scmp.com/rss/91/feed',       'name': 'South China Morning Post', 'weight': 0.9},
}

# Google News search -- the reliable backbone. Philippine edition first.
GN_QUERIES = [
    ('China coast guard Philippines West Philippine Sea', 'GNews:PH Inbound', 'en', 'PH'),
    ('Ayungin OR "Second Thomas" OR "Sierra Madre" resupply', 'GNews:PH Ayungin', 'en', 'PH'),
    ('Scarborough OR "Bajo de Masinloc" OR Sabina OR Escoda China', 'GNews:PH Shoals', 'en', 'PH'),
    ('Philippines diplomatic protest China DFA', 'GNews:PH Protest', 'en', 'PH'),
    ('"Mutual Defense Treaty" OR EDCA OR Typhon OR NMESIS Philippines', 'GNews:PH Alliance', 'en', 'PH'),
    ('Philippines Japan OR Australia OR Vietnam OR India defense maritime', 'GNews:PH Partners', 'en', 'PH'),
    ('China Philippines water cannon OR rammed OR laser', 'GNews:PH Kinetic (intl)', 'en', 'US'),
    ('Sara Duterte OR "Rodrigo Duterte" impeachment OR ICC', 'GNews:PH Domestic', 'en', 'PH'),
    ('Tsina barko West Philippine Sea', 'GNews:PH Filipino', 'fil', 'PH'),
    ('菲律宾 海警 仁爱礁 OR 黄岩岛', 'GNews:PH Chinese-language', 'zh-CN', 'CN'),
]

GDELT_QUERIES = {
    'eng_inbound':  '"West Philippine Sea" OR ("China coast guard" Philippines)',
    'eng_outbound': 'Philippines (Scarborough OR "Second Thomas" OR Ayungin OR Sabina)',
}

TELEGRAM_KWS = ['philippine', 'philippines', 'manila', 'west philippine sea', 'scarborough',
                'second thomas', 'ayungin', 'sierra madre', 'sabina', 'spratly']


# ============================================
# REDIS
# ============================================
def _redis_get(key):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        resp = requests.get(f"{UPSTASH_REDIS_URL}/get/{key}",
                            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"}, timeout=5)
        data = resp.json()
        if data.get('result'):
            return json.loads(data['result'])
    except Exception as e:
        print(f"[Philippines Rhetoric] Redis GET error: {str(e)[:80]}")
    return None


def _redis_cmd(cmd, timeout=5):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        r = requests.post(UPSTASH_REDIS_URL,
                          headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                                   "Content-Type": "application/json"},
                          json=cmd, timeout=timeout)
        return r.json()
    except Exception as e:
        print(f"[Philippines Rhetoric] Redis {cmd[0]} error: {str(e)[:80]}")
    return None


def _redis_set(key, value):
    return _redis_cmd(["SET", key, json.dumps(value, default=str)]) is not None


def _redis_lpush_trim(key, value, max_len=336):
    _redis_cmd(["LPUSH", key, json.dumps(value, default=str)])
    _redis_cmd(["LTRIM", key, 0, max_len - 1])


def _redis_lrange(key, n=120):
    res = _redis_cmd(["LRANGE", key, 0, n - 1]) or {}
    out = []
    for item in res.get('result') or []:
        try:
            out.append(json.loads(item))
        except Exception:
            pass
    return out


def _acquire_scan_lock(ttl=int(SCAN_INTERVAL_HOURS * 3600 * 0.9)):
    """One gunicorn worker per scan window. No Redis -> allow (local dev)."""
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return True
    res = _redis_cmd(['SET', SCAN_LOCK_KEY, datetime.now(timezone.utc).isoformat(), 'NX', 'EX', ttl], timeout=8)
    if res is None:
        return True
    return res.get('result') == 'OK'


# ============================================
# CROSS-THEATER
# ============================================
def _read_fingerprints():
    fp = _redis_get(CROSSTHEATER_KEY) or {}
    return fp if isinstance(fp, dict) else {}


def _write_philippines_fingerprint(result):
    fps = _read_fingerprints()
    a = result['actors']
    fps['philippines'] = {
        'level':                  result['overall_level'],
        'outbound_score':         result['outbound_score'],
        'outbound_max_level':     result['outbound_max_level'],
        'inbound_score':          result['inbound_score'],
        'inbound_max_level':      result['inbound_max_level'],
        'internal_max_level':     result['internal_max_level'],
        'china_scs_level':        a['china_scs_pressure']['level'],
        'beijing_coercion_level': a['beijing_coercion']['level'],
        'economic_level':         a['economic_pressure']['level'],
        'state_level':            a['marcos_state']['level'],
        'afp_pcg_level':          a['afp_pcg']['level'],
        'us_alliance_level':      a['us_alliance']['level'],
        'regional_level':         a['regional_partners']['level'],
        'duterte_level':          a['duterte_faction']['level'],
        'coercion_gap':           result['coercion_gap'],
        'mdt_watch':              result['so_what'].get('mdt_watch', False),
        'corpus_health':          result['corpus_health']['status'],
        'is_absorber_node':       True,
        'is_command_node':        False,
        'label':                  ESCALATION_LEVELS[result['overall_level']]['label'],
        'updated_at':             datetime.now(timezone.utc).isoformat(),
    }
    _redis_set(CROSSTHEATER_KEY, fps)


# ============================================
# FETCHING
# ============================================
_UA = {'User-Agent': 'Mozilla/5.0 (compatible; AsifahAnalytics/1.0; +https://asifahanalytics.com)'}


def _parse_pub_date(pub_str):
    if not pub_str:
        return None
    try:
        return datetime.fromisoformat(str(pub_str).replace('Z', '+00:00'))
    except Exception:
        pass
    try:
        return parsedate_to_datetime(pub_str).astimezone(timezone.utc)
    except Exception:
        pass
    try:
        clean = ''.join(ch for ch in str(pub_str) if ch.isdigit())
        if len(clean) >= 14:
            return datetime.strptime(clean[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
        if len(clean) == 8:
            return datetime.strptime(clean, '%Y%m%d').replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None


def _fetch_rss(url, source_name, weight=0.85, max_items=25):
    articles = []
    try:
        resp = requests.get(url, timeout=12, headers=_UA)
        if resp.status_code != 200:
            print(f"[Philippines RSS] {source_name}: HTTP {resp.status_code}")
            return [], f'http_{resp.status_code}'
        root = ET.fromstring(resp.content.lstrip(b'\xef\xbb\xbf').strip())
        for item in root.findall('.//item')[:max_items]:
            t = item.find('title')
            if t is None or not t.text:
                continue
            link = item.find('link')
            pub = item.find('pubDate')
            desc = item.find('description')
            articles.append({
                'title':       t.text.strip(),
                'description': ((desc.text or '') if desc is not None else '')[:500],
                'url':         link.text.strip() if link is not None and link.text else '',
                'publishedAt': pub.text if pub is not None else '',
                'source':      {'name': source_name},
                'content':     t.text.strip(),
                'source_weight_override': weight,
                'language':    'en',
            })
        return articles, 'ok'
    except ET.ParseError:
        return [], 'xml_error'
    except Exception as e:
        return [], f'error:{type(e).__name__}'


def _fetch_google_news_rss(query, label, lang='en', gl='PH', max_items=20):
    articles = []
    try:
        url = (f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}"
               f"&hl={lang}&gl={gl}&ceid={gl}:{lang.split('-')[0] if lang != 'zh-CN' else 'zh-Hans'}")
        resp = requests.get(url, timeout=12, headers=_UA)
        if resp.status_code != 200:
            return [], f'http_{resp.status_code}'
        root = ET.fromstring(resp.content)
        for item in root.findall('.//item')[:max_items]:
            t = item.find('title')
            if t is None or not t.text:
                continue
            link = item.find('link')
            pub = item.find('pubDate')
            src = item.find('source')
            articles.append({
                'title':       t.text.strip(),
                'description': t.text.strip(),
                'url':         link.text if link is not None else '',
                'publishedAt': pub.text if pub is not None else '',
                'source':      {'name': (src.text.strip() if src is not None and src.text else label)},
                'content':     t.text.strip(),
                'language':    lang,
            })
        return articles, 'ok'
    except Exception as e:
        return [], f'error:{type(e).__name__}'


def _fetch_gdelt(query, label):
    if not _GDELT_GATEWAY:
        return [], 'gateway_unavailable'
    try:
        raw, probe = _gw_gdelt(query, language='eng', timespan='3d', maxrecords=50, label=label)
        out = [{
            'title':       a.get('title', ''),
            'description': '',
            'url':         a.get('url', ''),
            'publishedAt': a.get('published', ''),
            'source':      {'name': a.get('source') or 'GDELT'},
            'content':     a.get('title', ''),
            'language':    'en',
        } for a in (raw or [])]
        return out, ('ok' if (probe or {}).get('sensed') else f"not_sensed:{(probe or {}).get('reason')}")
    except Exception as e:
        return [], f'error:{type(e).__name__}'


def _gather_articles():
    all_articles, health = [], {}
    for key, cfg in RSS_SOURCES.items():
        arts, status = _fetch_rss(cfg['url'], cfg['name'], weight=cfg.get('weight', 0.85))
        health[cfg['name']] = {'count': len(arts), 'status': status}
        all_articles.extend(arts)
        time.sleep(0.2)
    for query, label, lang, gl in GN_QUERIES:
        arts, status = _fetch_google_news_rss(query, label, lang=lang, gl=gl)
        health[label] = {'count': len(arts), 'status': status}
        all_articles.extend(arts)
        time.sleep(0.3)
    for key, query in GDELT_QUERIES.items():
        arts, status = _fetch_gdelt(query, f'philippines_{key}')
        health[f'GDELT:{key}'] = {'count': len(arts), 'status': status}
        all_articles.extend(arts)
    if TELEGRAM_AVAILABLE:
        try:
            n = 0
            for msg in (fetch_asia_telegram_signals(hours_back=72, include_extended=True) or []):
                txt = (msg.get('title', '') or '').lower()
                if any(k in txt for k in TELEGRAM_KWS):
                    all_articles.append({
                        'title': msg.get('title', '')[:200], 'description': msg.get('title', '')[:500],
                        'url': msg.get('url', ''), 'publishedAt': msg.get('published', ''),
                        'source': {'name': msg.get('source', 'Telegram')},
                        'content': msg.get('title', '')[:500], 'language': 'multi'})
                    n += 1
            health['Telegram'] = {'count': n, 'status': 'ok'}
        except Exception as e:
            health['Telegram'] = {'count': 0, 'status': f'error:{type(e).__name__}'}

    # Dedup by URL, then by normalised title (Google News repeats wire copy)
    seen_u, seen_t, out = set(), set(), []
    for a in all_articles:
        u = (a.get('url', '') or '').split('?')[0].rstrip('/')
        t = ''.join(ch for ch in (a.get('title', '') or '').lower() if ch.isalnum())[:90]
        if (u and u in seen_u) or (t and t in seen_t):
            continue
        if u:
            seen_u.add(u)
        if t:
            seen_t.add(t)
        out.append(a)
    # Drop anything older than 7 days (undated items kept -- RSS often omits dates)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    fresh = []
    for a in out:
        d = _parse_pub_date(a.get('publishedAt'))
        if d is not None and d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        if d is None or d >= cutoff:
            fresh.append(a)
    return fresh, health


# ============================================
# SCORING
# ============================================
def _source_weight(name):
    s = (name or '').lower()
    if any(p in s for p in ['reuters', 'associated press', 'ap news', 'bbc', 'usni', 'csis', 'nikkei',
                            'south china morning post', 'financial times', 'bloomberg', 'kyodo']):
        return 1.0
    if any(h in s for h in ['inquirer', 'philstar', 'rappler', 'gma', 'abs-cbn', 'manila bulletin',
                            'philippine news agency', 'benarnews', 'the diplomat', 'manila times', 'one news']):
        return 0.85
    if 'gdelt' in s:
        return 0.4
    return 0.55


def _score_actor(actor_key, articles):
    actor = ACTORS[actor_key]
    ladder = TRIGGERS.get(actor_key, {})
    now = datetime.now(timezone.utc)
    gate = [k.lower() for k in actor['keywords']]
    matched, top, score, count = [], [], 0.0, 0
    for a in articles:
        text = f"{a.get('title', '')} {a.get('description', '')} {a.get('content', '')}".lower()
        if not any(k in text for k in PH_GATE) or not any(k in text for k in gate):
            continue
        d = _parse_pub_date(a.get('publishedAt'))
        age = 48.0
        if d:
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            age = max(0.1, (now - d).total_seconds() / 3600)
        decay = 1.0 if age <= 24 else 0.8 if age <= 48 else 0.6 if age <= 72 else max(0.2, 1.0 - (age / 168) * 0.8)
        w = a.get('source_weight_override', _source_weight((a.get('source') or {}).get('name', '')))
        is_rep = actor_key in REPORTING_ACTORS and any(r in text for r in REPORTING_LANGUAGE)
        if is_rep:
            w *= 0.6
        lvl, trig = 0, None
        for L in (5, 4, 3, 2, 1):
            for t in ladder.get(L, []):
                if t in text:
                    lvl, trig = L, t
                    break
            if lvl:
                break
        if not lvl:
            continue
        if trig not in matched:
            matched.append(trig)
        c = lvl * decay * w
        score += c
        count += 1
        top.append({'title': a.get('title', '')[:150], 'url': a.get('url', ''),
                    'source': (a.get('source') or {}).get('name', ''), 'publishedAt': a.get('publishedAt', ''),
                    'level': lvl, 'trigger': trig, 'contribution': round(c, 2), 'is_reporting': is_rep})
    level = 0 if score == 0 else 1 if score < 3 else 2 if score < 8 else 3 if score < 16 else 4 if score < 28 else 5
    # v1.1 (Nov 2 2026): VOLUME CANNOT CLIMB ABOVE EVIDENCE. 205 articles about
    # the Duterte impeachment trial summed past 28 and printed the domestic
    # split at L5 Active Conflict. The score now sets the level only up to the
    # highest trigger an article actually carried ...
    if top:
        level = min(level, max(t['level'] for t in top))
    # Tripwires force L4 -- but only when 2+ outlets carry them (one blog is not a tripwire)
    for tw in actor.get('tripwires', []):
        outlets = {(a.get('source') or {}).get('name', '') for a in articles
                   if tw in f"{a.get('title', '')} {a.get('description', '')}".lower()}
        if len(outlets) >= 2:
            level = max(level, 4)
            matched.append(f"TRIPWIRE: {tw}")
    # Literal ladders obey the platform corroboration rule too: L3+ needs 2 outlets.
    if level >= 3:
        hi = {t['source'] for t in top if t['level'] >= 3}
        if len(hi) < 2 and not any(str(m).startswith('TRIPWIRE') for m in matched):
            level = 2
    # ... and each actor's own ceiling applies (L5 assertion rule, Oct 6 2026:
    # Active Conflict only where the ladder measures hostilities).
    level = min(level, ACTOR_LEVEL_CAP.get(actor_key, 5))
    top.sort(key=lambda x: x['contribution'], reverse=True)
    return {
        'actor': actor_key, 'name': actor['name'], 'flag': actor['flag'], 'icon': actor['icon'],
        'color': actor['color'], 'dashboard': actor['dashboard'], 'role': actor['role'],
        'description': actor['description'], 'level': level,
        'level_label': ESCALATION_LEVELS[level]['label'], 'level_color': ESCALATION_LEVELS[level]['color'],
        'weighted_score': round(score, 2), 'article_count': count,
        'matched_triggers': matched[:10], 'top_articles': top[:5],
    }


def _composite(actor_results, keys_weights):
    total = sum(keys_weights.values())
    s = sum(actor_results[k]['level'] * w for k, w in keys_weights.items())
    mx = max(actor_results[k]['level'] for k in keys_weights)
    score = int((s / (total * 5)) * 100)
    elevated = sum(1 for k in keys_weights if actor_results[k]['level'] >= 3)
    if elevated >= 3:
        score = min(100, score + 8)
    return score, mx


# ============================================
# INTERPRETER (built in -- small on purpose)
# ============================================
def _has(articles, *groups):
    """Articles whose text has a term from EVERY group (plain lowercase substring)."""
    hits = []
    for a in articles:
        t = f"{a.get('title', '')} {a.get('description', '')}".lower()
        if all(any(g in t for g in grp) for grp in groups):
            hits.append(a)
    return hits


def _outlets(hits):
    return {(a.get('source') or {}).get('name', '') for a in hits}


RED_LINES = [
    # (id, label, icon, color, groups, positive)
    ('filipino_death', 'A Filipino killed in a China-linked incident at sea', '🚨', '#dc2626',
     (['killed', 'dead', 'died', 'death'], ['filipino', 'philippine'],
      ['chinese', 'china coast guard', 'ccg', 'maritime militia', 'china rams', 'china water'],
      ['shoal', 'vessel', 'boat', 'coast guard', 'west philippine sea']), False),
    ('sierra_madre', 'The BRP Sierra Madre outpost threatened (tow, seizure, blockade)', '⚓', '#ef4444',
     (['sierra madre', 'ayungin', 'second thomas'], ['tow', 'seize', 'seizure', 'blockade', 'remove', 'board']), False),
    ('scarborough_build', 'Construction or a permanent barrier at Scarborough', '🏗️', '#ef4444',
     (['scarborough', 'bajo de masinloc', 'huangyan'], ['reclamation', 'island-building', 'structure',
                                                        'construction', 'barrier', 'buoy', 'dredg']), False),
    ('mdt_invoked', 'Mutual Defense Treaty consultations or invocation', '🛡️', '#dc2626',
     (['mutual defense treaty', 'mutual defence treaty', 'article iv', 'mdt'],
      ['invoke', 'invoked', 'invoking', 'consultations', 'triggered']), False),
    ('coalition_sail', 'Multinational joint sail / partner forces in the WPS', '🟢', '#22c55e',
     (['joint sail', 'maritime cooperative activit', 'multilateral maritime'], ['philippine', 'philippines']), True),
]


def _check_red_lines(articles):
    out = []
    for rid, label, icon, color, groups, positive in RED_LINES:
        hits = _has(articles, *groups)
        if rid == 'filipino_death':   # typhoon season is not a red line
            hits = [a for a in hits if not any(w in f"{a.get('title', '')} {a.get('description', '')}".lower()
                                                for w in WEATHER_TERMS)]
        outlets = _outlets(hits)
        if not hits:
            continue
        status = 'BREACHED' if len(outlets) >= 2 else 'APPROACHING'
        out.append({'id': rid, 'label': label, 'icon': icon, 'color': color, 'status': status,
                    'positive': positive, 'outlets': len(outlets),
                    'evidence': [{'title': a.get('title', '')[:150], 'url': a.get('url', ''),
                                  'source': (a.get('source') or {}).get('name', '')} for a in hits[:3]]})
    return out


SCENARIOS = {
    0: ('Quiet water', '🌊', '#6b7280'),
    1: ('Routine friction', '🔵', '#3b82f6'),
    2: ('Gray-zone pressure', '🟡', '#f59e0b'),
    3: ('Sustained confrontation', '🟠', '#f97316'),
    4: ('Contact at sea', '🔴', '#ef4444'),
    5: ('Lethal incident / alliance test', '⛔', '#dc2626'),
}


def _build_so_what(actor_results, red_lines, corpus_ok):
    L = lambda k: actor_results[k]['level']
    inbound = max(L(k) for k in INBOUND_ACTOR_KEYS)
    response = max(L('marcos_state'), L('afp_pcg'))
    partner = max(L('us_alliance'), L('regional_partners'))
    gap = max(0, inbound - max(response, partner))
    breached = {r['id'] for r in red_lines if r['status'] == 'BREACHED' and not r['positive']}
    mdt_watch = bool({'filipino_death', 'mdt_invoked', 'sierra_madre'} & breached) or \
        (L('china_scs_pressure') >= 4 and L('us_alliance') >= 3)
    name, icon, color = SCENARIOS[min(5, inbound)]
    parts = []
    if not corpus_ok:
        parts.append('The read is thin this cycle -- low levels below reflect fewer articles, not a calm sea.')
    if inbound >= 4:
        parts.append('China is in physical contact with Philippine vessels, not just shadowing them.')
    elif inbound == 3:
        parts.append('Chinese pressure is sustained and corroborated across outlets.')
    elif inbound == 2:
        parts.append('Chinese presence is reported but not yet at the level of contact.')
    if gap >= 2:
        parts.append(f'A coercion-response gap of {gap} levels is open: pressure is outrunning both Manila\'s answer and its partners\'.')
    elif inbound >= 3 and partner >= 3:
        parts.append('Partners are visibly present, which is what keeps a shoal incident from becoming a fait accompli.')
    if mdt_watch:
        parts.append('This is the band where the Mutual Defense Treaty stops being background: watch Washington\'s wording, '
                     'not just Manila\'s.')
    if L('duterte_faction') >= 3:
        parts.append('The Marcos-Duterte rupture is loud enough to slow Manila\'s answer at sea.')
    if not parts:
        parts.append('No corroborated escalation in the West Philippine Sea this cycle.')
    return {'scenario': name, 'scenario_icon': icon, 'scenario_color': color,
            'inbound_pressure': inbound, 'response_strength': response, 'partner_strength': partner,
            'coercion_gap': gap, 'mdt_watch': mdt_watch, 'text': ' '.join(parts)}


FLAG = '🇵🇭'


def _clean_headline(title):
    t = str(title or '').strip()
    if ' - ' in t:
        head, tail = t.rsplit(' - ', 1)
        if 0 < len(tail) <= 60:
            t = head
    return t[:140]


def _actor_sentence(k, rec):
    """One plain-language sentence about an actor, with its best evidence."""
    lv = rec.get('level', 0)
    outlets = {x.get('source') for x in rec.get('top_articles') or [] if x.get('source')}
    s = f"{PLAIN_ACTOR.get(k, rec.get('name', k))} is at L{lv} ({ESCALATION_LEVELS[lv]['label']})"
    if outlets:
        s += f", reported by {len(outlets)} outlet{'s' if len(outlets) != 1 else ''}"
    tops = rec.get('top_articles') or []
    if tops and tops[0].get('title'):
        s += f". Latest: \u201c{_clean_headline(tops[0]['title'])}\u201d"
    return s + '.'


def _build_top_indicator(result):
    """v1.1 -- THE one plain-language line the stability card and the Asia BLUF lead with.
    Order: a corroborated red line, else the highest actor (China at sea wins ties),
    else an honest 'nothing corroborated' / 'thin read' line."""
    for rl in result.get('red_lines') or []:
        if rl.get('status') == 'BREACHED' and not rl.get('positive'):
            return f"{rl['label']} -- reported by {rl['outlets']} outlets."
    a = result['actors']
    order = INBOUND_ACTOR_KEYS + ['afp_pcg', 'us_alliance', 'marcos_state', 'regional_partners'] + INTERNAL_ACTOR_KEYS
    best = max(order, key=lambda k: (a[k]['level'], -order.index(k)))
    if a[best]['level'] >= 2:
        return _actor_sentence(best, a[best])
    if not result['corpus_health']['ok']:
        return ("Too few articles were collected this cycle to judge the West Philippine Sea; "
                "low levels mean less evidence, not a calm sea.")
    return "No corroborated escalation was reported in the West Philippine Sea this cycle."


def _build_top_signals(result):
    sigs = []
    lvl = result['overall_level']
    for rl in result['red_lines']:
        if rl['positive']:
            if rl['status'] == 'BREACHED':
                sigs.append({'priority': 9, 'category': 'green_line_active', 'theatre': 'philippines', 'level': lvl,
                             'icon': '🟢', 'color': '#22c55e',
                             'short_text': f"{FLAG} PHILIPPINES: Coalition-positive -- {rl['label'][:48]}",
                             'long_text': f"PHILIPPINES deterrence-positive signal: {rl['label']}."})
            continue
        pri = 12 if rl['status'] == 'BREACHED' else 8
        sigs.append({'priority': pri,
                     'category': 'red_line_breached' if rl['status'] == 'BREACHED' else 'red_line_approaching',
                     'theatre': 'philippines', 'level': lvl, 'icon': rl['icon'], 'color': rl['color'],
                     'short_text': f"{FLAG} PHILIPPINES: {'BREACH' if rl['status'] == 'BREACHED' else 'Watch'} -- {rl['label'][:54]}",
                     'long_text': f"PHILIPPINES red line {rl['status'].lower()} ({rl['outlets']} outlet(s)): {rl['label']}."})
    sw = result['so_what']
    if sw['coercion_gap'] >= 2:
        sigs.append({'priority': 10, 'category': 'coercion_gap', 'theatre': 'philippines', 'level': lvl,
                     'icon': '📉', 'color': '#f97316',
                     'short_text': f"{FLAG} PHILIPPINES: Coercion-response gap L{sw['coercion_gap']}",
                     'long_text': f"PHILIPPINES: Chinese pressure at L{sw['inbound_pressure']} vs Manila L{sw['response_strength']} "
                                  f"/ partners L{sw['partner_strength']}."})
    a = result['actors']
    for k in INBOUND_ACTOR_KEYS + OUTBOUND_ACTOR_KEYS + INTERNAL_ACTOR_KEYS:
        if a[k]['level'] >= 3:
            sigs.append({'priority': 4 + a[k]['level'], 'category': 'actor_elevated', 'theatre': 'philippines',
                         'level': a[k]['level'], 'icon': a[k]['icon'], 'color': a[k]['level_color'],
                         'short_text': f"{FLAG} PHILIPPINES: {a[k]['name']} at L{a[k]['level']} ({a[k]['level_label']})",
                         'long_text': _actor_sentence(k, a[k])})
    if not result['corpus_health']['ok']:
        sigs.append({'priority': 3, 'category': 'sensor_degraded', 'theatre': 'philippines', 'level': 0,
                     'icon': '📡', 'color': '#6b7280',
                     'short_text': f"{FLAG} PHILIPPINES: thin read ({result['total_articles']} articles) -- not a quiet sea",
                     'long_text': 'PHILIPPINES: source corpus below health threshold; absence of signal is not a finding.'})
    sigs.sort(key=lambda s: -s['priority'])
    return sigs[:8]


def _build_bluf(result):
    sw = result['so_what']
    # No level prefix: the regional BLUF already leads with the level label.
    return (f"{sw['text']} (Chinese pressure L{sw['inbound_pressure']}, Manila's answer "
            f"L{sw['response_strength']}, partners L{sw['partner_strength']}.)")


def _build_watch(result):
    a = result['actors']
    items = []
    if a['china_scs_pressure']['level'] >= 3:
        items.append('the next Ayungin resupply run and whether it gets through')
    if a['us_alliance']['level'] >= 3:
        items.append('US wording on Article IV ("public vessels... anywhere in the South China Sea")')
    if a['beijing_coercion']['level'] >= 3:
        items.append('any new Chinese administrative claim at Scarborough')
    if a['duterte_faction']['level'] >= 3:
        items.append('whether the domestic fight spills into foreign policy votes')
    if not items:
        items = ['water cannon or ramming at Second Thomas, Scarborough or Sabina',
                 'Typhon/NMESIS moves and Beijing\'s answer']
    return 'Watch: ' + '; '.join(items) + '.'


# ============================================
# MAIN SCAN
# ============================================
def run_philippines_rhetoric_scan():
    t0 = time.time()
    print(f"\n[Philippines Rhetoric] Scan start {datetime.now(timezone.utc).isoformat()}")
    fps = _read_fingerprints()
    articles, source_health = _gather_articles()
    n = len(articles)
    live_sources = sum(1 for v in source_health.values() if v['count'] > 0)
    corpus_ok = n >= MIN_HEALTHY_CORPUS and live_sources >= 4
    corpus_health = {'ok': corpus_ok, 'status': 'healthy' if corpus_ok else 'degraded',
                     'articles': n, 'live_sources': live_sources, 'threshold': MIN_HEALTHY_CORPUS}
    print(f"[Philippines Rhetoric] {n} articles from {live_sources} live sources ({corpus_health['status']})")

    actor_results = {}
    for k in ACTORS:
        try:
            actor_results[k] = _score_actor(k, articles)
        except Exception as e:
            print(f"[Philippines Rhetoric] score error {k}: {str(e)[:80]}")
            actor_results[k] = _score_actor(k, [])

    cooccurrence_report = None
    if _asia_cooc:
        try:
            cooccurrence_report = _asia_cooc('philippines', articles, actor_results, ESCALATION_LEVELS)
        except Exception as e:
            print(f"[Philippines Rhetoric] cooc error: {str(e)[:80]}")
    for k, r in actor_results.items():
        cap = ACTOR_LEVEL_CAP.get(k, 5)
        if r['level'] > cap:
            r['level'] = cap
            r['level_label'] = ESCALATION_LEVELS[cap]['label']
            r['level_color'] = ESCALATION_LEVELS[cap]['color']
        print(f"[Philippines Rhetoric] {k}: L{r['level']}")

    outbound_score, outbound_max = _composite(actor_results, {
        'marcos_state': 2.0, 'afp_pcg': 2.5, 'us_alliance': 2.5, 'regional_partners': 1.5})
    inbound_score, inbound_max = _composite(actor_results, {
        'china_scs_pressure': 3.0, 'beijing_coercion': 2.0, 'economic_pressure': 1.0})
    internal_max = actor_results['duterte_faction']['level']
    # Domestic politics colours the theatre but cannot by itself make it a sea crisis.
    overall_level = max(outbound_max, inbound_max, min(3, internal_max))

    red_lines = _check_red_lines(articles)
    so_what = _build_so_what(actor_results, red_lines, corpus_ok)

    # Two-front / three-front context from the neighbours
    china_fp, taiwan_fp, vn_fp = fps.get('china') or {}, fps.get('taiwan') or {}, fps.get('vietnam') or {}
    crosstheater = {
        'china_pla_level':      int(china_fp.get('pla_level', 0) or 0),
        'taiwan_inbound_max':   int(taiwan_fp.get('inbound_max_level', taiwan_fp.get('inbound_max', 0)) or 0),
        'vietnam_china_scs':    int(vn_fp.get('china_scs_level', 0) or 0),
    }
    crosstheater['scs_two_claimants_pressed'] = (inbound_max >= 3 and crosstheater['vietnam_china_scs'] >= 3)
    crosstheater['taiwan_and_wps_pressed'] = (inbound_max >= 3 and crosstheater['taiwan_inbound_max'] >= 3)

    result = {
        'success':            True,
        'theatre':            'philippines',
        'scanned_at':         datetime.now(timezone.utc).isoformat(),
        'scan_time_seconds':  round(time.time() - t0, 1),
        'total_articles':     n,
        'corpus_health':      corpus_health,
        'source_health':      source_health,
        'outbound_score':     outbound_score,
        'outbound_max_level': outbound_max,
        'inbound_score':      inbound_score,
        'inbound_max_level':  inbound_max,
        'internal_max_level': internal_max,
        'overall_level':      overall_level,
        'overall_label':      ESCALATION_LEVELS[overall_level]['label'],
        'overall_color':      ESCALATION_LEVELS[overall_level]['color'],
        'theatre_level':      overall_level,
        'theatre_score':      max(outbound_score, inbound_score),
        'actors':             actor_results,
        'china_scs_level':    actor_results['china_scs_pressure']['level'],
        'us_alliance_level':  actor_results['us_alliance']['level'],
        'afp_pcg_level':      actor_results['afp_pcg']['level'],
        'red_lines':          red_lines,
        'so_what':            so_what,
        'coercion_gap':       so_what['coercion_gap'],
        'crosstheater':       crosstheater,
        'cooccurrence':       cooccurrence_report,
        'escalation_levels':  ESCALATION_LEVELS,
        'version':            TRACKER_VERSION,
    }
    result['top_indicator'] = _build_top_indicator(result)
    result['top_signals'] = _build_top_signals(result)
    result['bluf'] = _build_bluf(result)
    result['watch_indicators'] = _build_watch(result)

    if _BUTTERFLY_AVAILABLE:
        try:
            b = read_butterfly_signals_via_proxy('philippines') or {}
            result['butterfly'] = {k: b.get(k) for k in ('upstream_stressors', 'context_notes', 'success')}
        except Exception as e:
            result['butterfly'] = {'error': str(e)[:80]}
    if _CONVERGENCE_PROXY_AVAILABLE:
        try:
            result['external_convergences'] = find_convergences_for_country_proxy('philippines') or []
        except Exception:
            result['external_convergences'] = []

    _write_philippines_fingerprint(result)
    _redis_set(RHETORIC_CACHE_KEY, result)
    _redis_lpush_trim(HISTORY_KEY, {
        'ts': result['scanned_at'], 'level': overall_level, 'label': result['overall_label'],
        'outbound_score': outbound_score, 'inbound_score': inbound_score,
        'coercion_gap': so_what['coercion_gap'], 'china_scs_level': result['china_scs_level'],
        'us_alliance_level': result['us_alliance_level'], 'corpus': corpus_health['status']})
    print(f"[Philippines Rhetoric] done in {result['scan_time_seconds']}s | L{overall_level} | "
          f"in L{inbound_max} out L{outbound_max} gap L{so_what['coercion_gap']}")
    return result


# ============================================
# BACKGROUND + ENDPOINTS
# ============================================
def _background_scan_loop():
    time.sleep(260)   # after China / Taiwan / Vietnam have written fingerprints
    while True:
        try:
            if _acquire_scan_lock():
                run_philippines_rhetoric_scan()
            else:
                print('[Philippines Rhetoric] another worker owns this scan window -- skipping')
        except Exception as e:
            print(f"[Philippines Rhetoric] background error: {str(e)[:200]}")
        time.sleep(SCAN_INTERVAL_HOURS * 3600)


def register_philippines_rhetoric_endpoints(app):

    @app.route('/api/rhetoric/philippines', methods=['GET'])
    def api_philippines_rhetoric():
        global _rhetoric_running
        force = request.args.get('force', 'false').lower() == 'true'
        if not force:
            cached = _redis_get(RHETORIC_CACHE_KEY)
            if cached:
                cached['from_cache'] = True
                return jsonify(cached)
        with _rhetoric_lock:
            if _rhetoric_running:
                cached = _redis_get(RHETORIC_CACHE_KEY)
                if cached:
                    cached['from_cache'] = True
                    cached['scan_in_progress'] = True
                    return jsonify(cached)
                return jsonify({'success': False, 'error': 'Scan in progress'}), 202
            _rhetoric_running = True
        try:
            return jsonify(run_philippines_rhetoric_scan())
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200]}), 500
        finally:
            with _rhetoric_lock:
                _rhetoric_running = False

    @app.route('/api/rhetoric/philippines/summary', methods=['GET'])
    def api_philippines_rhetoric_summary():
        c = _redis_get(RHETORIC_CACHE_KEY)
        if not c:
            return jsonify({'success': False,
                            'error': 'No data yet -- first scan runs ~4 minutes after boot'}), 404
        sw = c.get('so_what') or {}
        return jsonify({
            'success': True, 'theatre': 'philippines', 'flag': FLAG,
            'scanned_at': c.get('scanned_at'),
            'overall_level': c.get('overall_level', 0), 'overall_label': c.get('overall_label', 'Baseline'),
            'overall_color': c.get('overall_color', '#6b7280'),
            'outbound_score': c.get('outbound_score', 0), 'outbound_max_level': c.get('outbound_max_level', 0),
            'inbound_score': c.get('inbound_score', 0), 'inbound_max_level': c.get('inbound_max_level', 0),
            'internal_max_level': c.get('internal_max_level', 0),
            'china_scs_level': c.get('china_scs_level', 0), 'us_alliance_level': c.get('us_alliance_level', 0),
            'afp_pcg_level': c.get('afp_pcg_level', 0),
            'coercion_gap': c.get('coercion_gap', 0), 'mdt_watch': sw.get('mdt_watch', False),
            'scenario': sw.get('scenario', ''), 'scenario_icon': sw.get('scenario_icon', ''),
            'scenario_color': sw.get('scenario_color', '#6b7280'), 'so_what': sw.get('text', ''),
            'bluf': c.get('bluf', ''), 'watch_indicators': c.get('watch_indicators', ''),
            'top_indicator': c.get('top_indicator', ''),
            'top_signals': (c.get('top_signals') or [])[:3],
            'red_lines_count': len(c.get('red_lines') or []),
            'total_articles': c.get('total_articles', 0),
            'corpus_health': (c.get('corpus_health') or {}).get('status', 'unknown'),
            'version': c.get('version', TRACKER_VERSION),
        })

    @app.route('/api/rhetoric/philippines/history', methods=['GET'])
    def api_philippines_rhetoric_history():
        h = _redis_lrange(HISTORY_KEY, 120)
        return jsonify({'success': True, 'count': len(h), 'history': h})

    threading.Thread(target=_background_scan_loop, daemon=True).start()
    print("[Philippines Rhetoric] Endpoints registered: /api/rhetoric/philippines (+ /summary, /history)")
