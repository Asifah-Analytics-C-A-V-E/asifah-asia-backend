"""
asia_regional_bluf.py
Asifah Analytics -- Asia Backend Module
v2.1.0 -- April 2026

Asia-Pacific Regional BLUF (Bottom Line Up Front) Engine.

Reads from China + Taiwan rhetoric tracker Redis caches and synthesizes
a single analyst-prose BLUF paragraph + structured top-line signals.

Architecture mirrors me_regional_bluf.py v2.0 (proven-working pattern).

v2.1.0 changes vs v2.0.0:
- Added compatibility shim _normalize_tracker_data() — handles both
  legacy trackers (free-form so_what) AND v2.0+ trackers self-emitting top_signals[]
- Added _synthesize_top_signals_legacy() — builds canonical signals from
  raw fields when a tracker hasn't been upgraded yet
- Output emits top_signals[] (canonical), max_level, theatre_summary,
  region: 'asia' for GPI consumption
- Top 5 signals (was 6) — matches ME pattern
- Canonical signal categories: red_line_breached, theatre_high,
  deterrence_gap, kinetic_pressure, economic_pressure, mutual_escalation,
  coalition_strong, silence_anomaly
- Forward-compatible with future stability anchors (Singapore-pattern
  influence vector) via INFLUENCE_LABELS/COLORS constants

v2.0.0 changes vs v1.x (already shipped):
- Flask import inside register function (matches ME pattern)
- Removed background refresh thread
- Cache check inside build_regional_bluf()
- Redis SET uses /set/{key} convention

Author: RCGG / Asifah Analytics
"""

import os
import json
import traceback
from datetime import datetime, timezone
import requests


# ============================================================
# CONFIG
# ============================================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL', '')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN', '')

# Source caches (written by respective trackers)
TRACKER_KEYS = {
    'china':    'rhetoric:china:latest',
    'taiwan':   'rhetoric:taiwan:latest',
    'pakistan': 'rhetoric:pakistan:latest',
    'japan':    'rhetoric:japan:latest',
    'india':    'rhetoric:india:latest',   # Patch 12 (May 2026) — absorber-class tracker
    'vietnam':  'rhetoric:vietnam:latest', # Jun 2026 -- SCS coercion-response tracker
    'afghanistan': 'rhetoric:afghanistan:latest',  # Jul 2026 -- four-wheel contested node
    'dprk':     'rhetoric:dprk:latest',   # Jul 2026 -- leverage-integrity tracker (INVERTED read)
    # Future Asia trackers slot in here:
    # 'philippines': 'rhetoric:philippines:latest',
}

THEATRE_FLAGS = {
    'china':    '\U0001f1e8\U0001f1f3',  # 🇨🇳
    'taiwan':   '\U0001f1f9\U0001f1fc',  # 🇹🇼
    'pakistan': '\U0001f1f5\U0001f1f0',  # 🇵🇰
    'japan':    '\U0001f1ef\U0001f1f5',  # 🇯🇵
    'india':    '\U0001f1ee\U0001f1f3',  # 🇮🇳
    'vietnam':  '\U0001f1fb\U0001f1f3',  # VN
    'afghanistan': '\U0001f1e6\U0001f1eb',  # AF
    'dprk':     '\U0001f1f0\U0001f1f5',  # 🇰🇵
}
    'china':    'CHINA',
    'taiwan':   'TAIWAN',
    'pakistan': 'PAKISTAN',
    'japan':    'JAPAN',
    'india':    'INDIA',
    'vietnam':  'VIETNAM',
    'afghanistan': 'AFGHANISTAN',
    'dprk':     'NORTH KOREA',
}

# v2.5 (Jun 2026): one-clause "why this theatre matters regionally" -- used as the
# plain-language So-What tail when a tracker is quiet, so every live theatre
# (China, Taiwan, Pakistan, Japan, India, Vietnam) still carries context at baseline.
THEATRE_ROLE = {
    'china':    'the primary driver of regional military and economic pressure',
    'taiwan':   'the central cross-strait flashpoint and the bellwether for US credibility in Asia',
    'pakistan': 'a western-front pressure valve that pulls Indian attention away from the China frontier',
    'japan':    'the alliance anchor whose posture signals how far US-led deterrence extends',
    'india':    'an absorber-class swing state whose alignment tilts the wider regional balance',
    'vietnam':  'a South China Sea claimant tied to the Hormuz energy-import chain, where shocks land as input-cost and sovereignty pressure',
    'afghanistan': 'a four-wheel contested node (Iran friction, Pakistan kinetic, Russia normalization, China extraction) whose instability exports terror risk, refugees, and narcotics pressure across the region',
    'dprk':     'a combatant-tier client of Russia whose leverage decays as the Ukraine war winds down -- and which escalates when sidelined, not when courted, making a quiet Pyongyang a signal rather than a reassurance',
}

# Top-N signals emitted to GPI (matches ME pattern)
TOP_SIGNALS_COUNT = 12      # v2.4.0 May 21 2026 — bumped from 5; supports per-theatre quota
MAX_PER_THEATRE   = 3       # v2.4.0 May 21 2026 — per-tracker quota during selection

# Our synthesis cache
BLUF_CACHE_KEY    = 'rhetoric:asia:regional_bluf'
BLUF_CACHE_TTL    = 14 * 3600    # 14h -- outlasts any individual tracker TTL


# ============================================================
# ESCALATION + INFLUENCE LABELS (canonical across all regional BLUFs)
# ============================================================
ESCALATION_LABELS = {
    0: 'Monitoring',
    1: 'Rhetoric',
    2: 'Warning',
    3: 'Direct Threat',
    4: 'Incident',
    5: 'Active Conflict',
}

ESCALATION_COLORS = {
    0: '#6b7280',
    1: '#3b82f6',
    2: '#f59e0b',
    3: '#f97316',
    4: '#ef4444',
    5: '#dc2626',
}

# v2.1: forward-compat for future Asia stability anchors (e.g. Singapore as
# diplomatic mediator pattern). Currently no Asia trackers use influence axis.
INFLUENCE_LABELS = {
    0: 'Standby',
    1: 'Engaged',
    2: 'Active',
    3: 'Mediation Engaged',
    4: 'High-Stakes Mediation',
    5: 'Crisis Mediation',
}

INFLUENCE_COLORS = {
    0: '#6b7280',
    1: '#a78bfa',
    2: '#8b5cf6',
    3: '#7c3aed',
    4: '#6d28d9',
    5: '#5b21b6',
}


# ============================================================
# REDIS HELPERS (matching ME BLUF pattern exactly)
# ============================================================
def _redis_get(key):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        resp = requests.get(
            f'{UPSTASH_REDIS_URL}/get/{key}',
            headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'},
            timeout=5
        )
        result = resp.json().get('result')
        return json.loads(result) if result else None
    except Exception as e:
        print(f'[Asia BLUF] Redis GET error ({key}): {e}')
        return None


def _redis_set(key, value, ttl=BLUF_CACHE_TTL):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return False
    try:
        payload = json.dumps(value, default=str)
        params = {'EX': ttl} if ttl else {}
        resp = requests.post(
            f'{UPSTASH_REDIS_URL}/set/{key}',
            headers={
                'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}',
                'Content-Type': 'application/json'
            },
            data=payload,
            params=params,
            timeout=5
        )
        return resp.json().get('result') == 'OK'
    except Exception as e:
        print(f'[Asia BLUF] Redis SET error ({key}): {e}')
        return False


# ============================================================
# SAFE-ACCESS HELPERS (defensive, kept from v1.1.0)
# ============================================================
def _safe_dict(val):
    """Always return a dict -- even if val is None, non-dict, or missing."""
    return val if isinstance(val, dict) else {}

def _safe_list(val):
    """Always return a list -- even if val is None, non-list, or missing."""
    return val if isinstance(val, list) else []

def _safe_int(val, default=0):
    """Always return an int -- even if val is None, str, float, or missing."""
    try:
        return int(val) if val is not None else default
    except (TypeError, ValueError):
        return default

def _safe_str(val, default=''):
    """Always return a string -- even if val is None, int, or missing."""
    return str(val) if val is not None else default


# ============================================================
# COMPATIBILITY SHIM -- v2.1
# ============================================================
# Trackers will gradually be upgraded to emit a canonical shape.
# Until then, this shim normalizes both legacy trackers (China/Taiwan emit
# so_what + red_lines at top-level) AND v2.0+ self-emitting trackers into
# the same internal representation that the BLUF engine consumes.
#
# Canonical internal shape (matches ME BLUF v2.0):
# {
#     'theatre':      str,
#     'flag':         str,
#     'levels': {
#         'threat':         0-5,
#         'influence':      0-5 or None,
#         'green':          0-5 or None,
#         'dominant_axis':  'threat'|'influence'|'green',
#         'dominant_level': 0-5,
#     },
#     'score':        0-100,
#     'so_what':      {...},
#     'red_lines':    {...},
#     'top_signals':  [...],   # NEW v2.0+ -- pre-prioritized
#     'scanned_at':   str,
#     'raw':          <untouched original>,  # for legacy access
# }
# ============================================================

def _normalize_tracker_data(theatre, raw_data):
    """
    Convert raw tracker cache into canonical shape regardless of version.
    """
    if not raw_data:
        return None

    flag = THEATRE_FLAGS.get(theatre, '')
    so_what    = _safe_dict(raw_data.get('so_what'))
    red_lines  = _safe_list(raw_data.get('red_lines'))

    # ---- THREAT LEVEL extraction (China + Taiwan use 'overall_level') ----
    threat = _safe_int(raw_data.get('overall_level'))
    if not threat:
        # Fallbacks for any other Asia tracker (Pakistan + future use 'theatre_level' — ME canonical)
        threat = _safe_int(raw_data.get('theatre_level',
                          raw_data.get('theatre_escalation_level',
                          raw_data.get('threat_level', 0))))

    # ---- SCORE extraction ----
    score = _safe_int(raw_data.get('theatre_score',
                     raw_data.get('rhetoric_score',
                     raw_data.get('overall_score', 0))))

    # ---- INFLUENCE LEVEL (Asia trackers don't currently use this; future-ready) ----
    influence = raw_data.get('influence_level')

    # ---- DOMINANT AXIS ----
    threat_int    = int(threat or 0)
    influence_int = int(influence or 0)
    dominant_level = max(threat_int, influence_int)
    dominant_axis  = 'influence' if influence_int > threat_int else 'threat'

    # ---- TOP SIGNALS (v2.0+ if self-emitted; else synthesize from raw) ----
    if 'top_signals' in raw_data and isinstance(raw_data['top_signals'], list):
        top_signals = list(raw_data['top_signals'])
    else:
        top_signals = _synthesize_top_signals_legacy(
            theatre, raw_data, threat_int, score, so_what, red_lines
        )

    # ALWAYS augment with BLUF-level diplomatic signals (v3.2.0 — mirrors ME pattern).
    # Forward-compatible: today's Asia trackers (China/Taiwan) don't emit diplomatic_track
    # data, so this is a no-op now. When future trackers (Korea peace talks, ASEAN
    # mediation, etc.) emit diplomatic_track in their interpretation block, signals
    # automatically surface to GPI's diplomatic axis with zero additional code.
    diplomatic_sigs = _extract_diplomatic_signals(theatre, raw_data, threat_int)
    existing_categories = {s.get('category') for s in top_signals}
    for ds in diplomatic_sigs:
        if ds.get('category') not in existing_categories:
            top_signals.append(ds)

    return {
        'theatre':      theatre,
        'flag':         flag,
        'levels': {
            'threat':         threat_int,
            'influence':      influence_int if influence is not None else None,
            'green':          None,
            'dominant_axis':  dominant_axis,
            'dominant_level': dominant_level,
        },
        'score':        score,
        'so_what':      so_what,
        'red_lines':    red_lines,
        'top_signals':  top_signals,
        'scanned_at':   _safe_str(raw_data.get('scanned_at') or raw_data.get('timestamp') or raw_data.get('updated_at', '')),
        'raw':          raw_data,
    }


def _extract_diplomatic_signals(theatre, raw_data, threat_int):
    """
    BLUF-level diplomatic signal extractor (v3.2.0 — mirrors ME pattern).

    Reads diplomatic_track + green_lines from a tracker's interpretation block.
    Forward-compatible no-op when trackers don't emit diplomatic data.

    Returns list of signal dicts (possibly empty).
    """
    flag    = THEATRE_FLAGS.get(theatre, '')
    display = THEATRE_DISPLAY.get(theatre, theatre.upper())
    interp  = (raw_data.get('interpretation') or {}) if isinstance(raw_data.get('interpretation'), dict) else {}
    signals = []

    # Green lines / diplomatic de-escalation (UNGATED + dual-schema).
    green_lines = interp.get('green_lines') if interp else None
    if green_lines and isinstance(green_lines, dict):
        if 'count' in green_lines:
            gl_count = green_lines.get('count', 0)
        else:
            gl_count = green_lines.get('active_count', 0) + green_lines.get('signaled_count', 0)
        if gl_count >= 1:
            gl_priority = 6 + min(threat_int, 4)
            signals.append({
                'priority':       gl_priority,
                'category':       'green_line_active',
                'theatre':        theatre,
                'level':          min(threat_int, 4),
                'icon':           '✅',
                'color':          '#10b981',
                'pressure_type':  'diplomatic',
                'short_text':     f'{flag} {display}: De-escalation signals ({gl_count})',
                'long_text':      f'{flag} {display}: {gl_count} green-line de-escalation '
                                  f'trigger{"s" if gl_count != 1 else ""} active.',
            })

    # Diplomatic track — mediation, talks, peace overtures.
    diplomatic_track = interp.get('diplomatic_track') if interp else None
    if diplomatic_track and isinstance(diplomatic_track, dict):
        active_count   = diplomatic_track.get('active_count', 0)
        signaled_count = diplomatic_track.get('signaled_count', 0)
        scenario       = diplomatic_track.get('scenario', '')
        score          = diplomatic_track.get('score', 0)
        if active_count + signaled_count > 0:
            dt_priority = 7 + min(threat_int, 4)
            short_status = 'ACTIVE' if active_count > 0 else 'SIGNALED'
            signals.append({
                'priority':       dt_priority,
                'category':       'diplomatic_track_active',
                'theatre':        theatre,
                'level':          min(threat_int, 4),
                'icon':           '🕊️',
                'color':          '#0ea5e9',
                'pressure_type':  'diplomatic',
                'short_text':     f'{flag} {display}: Diplomatic track {short_status} ({scenario[:40]})',
                'long_text':      f'{flag} {display} diplomatic track: {active_count} active + '
                                  f'{signaled_count} signaled off-ramp triggers (score {score}/100). '
                                  f'Scenario: {scenario}.',
                'diplomatic_active_count':   active_count,
                'diplomatic_signaled_count': signaled_count,
                'diplomatic_score':          score,
                'diplomatic_scenario':       scenario,
            })

    return signals


def _synthesize_top_signals_legacy(theatre, raw_data, threat_int, score, so_what, red_lines):
    """
    For Asia trackers (China, Taiwan) that haven't been upgraded to v2.0+
    self-emit pattern. Synthesize top_signals[] from raw fields.
    Returns list of canonical signal dicts.
    """
    flag    = THEATRE_FLAGS.get(theatre, '')
    display = THEATRE_DISPLAY.get(theatre, theatre.upper())
    signals = []

    # ---- 1. RED LINES BREACHED ----
    for rl in red_lines:
        rl = _safe_dict(rl)
        status = _safe_str(rl.get('status'))
        label  = _safe_str(rl.get('label'))
        is_positive = _safe_str(rl.get('color')) == '#22c55e'
        if status == 'BREACHED':
            if is_positive:
                # Taiwan deterrence-positive red line
                signals.append({
                    'priority':   9,
                    'category':   'green_line_active',
                    'theatre':    theatre,
                    'level':      threat_int,
                    'icon':       '🟢',
                    'color':      '#22c55e',
                    'short_text': f'{flag} {display}: DETERRENCE-POSITIVE — {label[:50]}',
                    'long_text':  f'{flag} {display}: Positive red line breached — {label}.',
                })
            else:
                signals.append({
                    'priority':   12,
                    'category':   'red_line_breached',
                    'theatre':    theatre,
                    'level':      threat_int,
                    'icon':       rl.get('icon', '🔴'),
                    'color':      '#dc2626',
                    'short_text': f'{flag} {display}: BREACH — {label[:55]}',
                    'long_text':  f'{flag} {display} red line breached at L{threat_int}: {label}.',
                })
        elif status == 'APPROACHING':
            signals.append({
                'priority':   8,
                'category':   'red_line_approaching',
                'theatre':    theatre,
                'level':      threat_int,
                'icon':       '🟠',
                'color':      '#f97316',
                'short_text': f'{flag} {display}: Approaching — {label[:50]}',
                'long_text':  f'{flag} {display} approaching red line: {label}.',
            })

    # ---- 2. THEATRE HIGH (overall L4+) ----
    # L5 GATE (v3.3.0 — May 21 2026): Per platform L5 Reservation Contract,
    # L5 "Active Conflict" requires an explicit kinetic/humanitarian/economic/
    # diplomatic trigger. If tracker emits l5_gate dict, we honor its decision.
    # If tracker doesn't emit l5_gate (legacy trackers), we trust their level
    # as-is until they're upgraded per the weekend audit.
    # LABEL PRESERVATION: prefer tracker's own theatre_label + signal_text_short
    # if emitted. Falls back to ESCALATION_LABELS dict for legacy trackers.
    effective_level = threat_int
    l5_gate = raw_data.get('l5_gate')
    if threat_int >= 5 and isinstance(l5_gate, dict):
        # If tracker emits l5_gate, cap at L4 unless at least one axis gate is True
        if not any(l5_gate.get(axis) for axis in ('kinetic', 'humanitarian', 'economic', 'diplomatic')):
            effective_level = 4
            print(f"[Asia BLUF] L5 gate enforced: {theatre} capped at L4 "
                  f"(no l5_gate axes fired; tracker score {score})")

    if effective_level >= 4:
        # Prefer tracker's own label; fall back to canonical dict
        tracker_label = raw_data.get('theatre_label') or ESCALATION_LABELS.get(effective_level, '')
        signals.append({
            'priority':   9 + effective_level,
            'category':   'theatre_high',
            'theatre':    theatre,
            'level':      effective_level,
            'icon':       '🔴',
            'color':      ESCALATION_COLORS.get(effective_level, '#6b7280'),
            'short_text': raw_data.get('signal_text_short') or
                          f'{flag} {display} L{effective_level} — {tracker_label}',
            'long_text':  raw_data.get('signal_text_long') or
                          f'{flag} {display} at L{effective_level} {tracker_label} (score {score}/100)',
        })

    # ---- 3. CHINA-SPECIFIC: kinetic + economic vectors ----
    if theatre == 'china':
        kinetic = _safe_int(so_what.get('kinetic_pressure'))
        econ    = _safe_int(so_what.get('economic_pressure'))
        domestic_fracture = _safe_int(so_what.get('domestic_fracture'))
        coalition_pushback = _safe_int(so_what.get('coalition_pushback'))

        if kinetic >= 3:
            pla_lvl = _safe_int(raw_data.get('pla_level'))
            signals.append({
                'priority':   8 + kinetic,
                'category':   'kinetic_pressure',
                'theatre':    'china',
                'level':      kinetic,
                'icon':       '⚔️',
                'color':      '#ef4444',
                'short_text': f'{flag} CHINA: Kinetic vector L{kinetic} (PLA L{pla_lvl})',
                'long_text':  f'CHINA kinetic pressure L{kinetic} — PLA operational level L{pla_lvl}; cross-strait coercion active.',
            })
        if econ >= 3:
            signals.append({
                'priority':   7 + econ,
                'category':   'economic_pressure',
                'theatre':    'china',
                'level':      econ,
                'icon':       '💰',
                'color':      '#f97316',
                'short_text': f'{flag} CHINA: Economic coercion L{econ}',
                'long_text':  f'CHINA economic coercion L{econ} — trade/investment pressure tools active.',
            })
        if domestic_fracture >= 3:
            signals.append({
                'priority':   6 + domestic_fracture,
                'category':   'domestic_fracture',
                'theatre':    'china',
                'level':      domestic_fracture,
                'icon':       '🏚️',
                'color':      '#a855f7',
                'short_text': f'{flag} CHINA: Domestic fracture L{domestic_fracture}',
                'long_text':  f'CHINA domestic fracture indicators L{domestic_fracture} — internal stress accelerates external posturing risk.',
            })
        if coalition_pushback >= 3:
            signals.append({
                'priority':   5 + coalition_pushback,
                'category':   'coalition_pushback',
                'theatre':    'china',
                'level':      coalition_pushback,
                'icon':       '🛡️',
                'color':      '#10b981',
                'short_text': f'{flag} CHINA: Coalition pushback L{coalition_pushback}',
                'long_text':  f'CHINA-facing coalition activity L{coalition_pushback} — US/Japan/Australia coordinated signaling detected.',
            })

    # ---- 4. TAIWAN-SPECIFIC: deterrence gap + coalition strength ----
    if theatre == 'taiwan':
        gap            = _safe_int(so_what.get('deterrence_gap'))
        deterrence_str = _safe_int(so_what.get('deterrence_strength'))
        inbound        = _safe_int(so_what.get('inbound_pressure'))
        domestic_resv  = _safe_int(so_what.get('domestic_resolve'))
        us_lvl         = _safe_int(raw_data.get('us_level'))
        def_lvl        = _safe_int(raw_data.get('defense_level'))

        if gap >= 3:
            signals.append({
                'priority':   11,
                'category':   'deterrence_gap',
                'theatre':    'taiwan',
                'level':      gap,
                'icon':       '⚠️',
                'color':      '#dc2626',
                'short_text': f'{flag} TAIWAN: Deterrence gap L{gap}',
                'long_text':  f'TAIWAN deterrence gap L{gap} — inbound pressure L{inbound} exceeds coalition response L{deterrence_str}. Coercion-into-weakness pattern.',
            })
        elif gap >= 2:
            signals.append({
                'priority':   7,
                'category':   'deterrence_gap',
                'theatre':    'taiwan',
                'level':      gap,
                'icon':       '📉',
                'color':      '#f59e0b',
                'short_text': f'{flag} TAIWAN: Deterrence gap L{gap}',
                'long_text':  f'TAIWAN deterrence gap L{gap} — coalition signaling lagging inbound pressure; reinforcement window open.',
            })

        if us_lvl >= 3 and def_lvl >= 3 and gap < 2:
            signals.append({
                'priority':   6,
                'category':   'coalition_strong',
                'theatre':    'taiwan',
                'level':      max(us_lvl, def_lvl),
                'icon':       '🤝',
                'color':      '#10b981',
                'short_text': f'{flag} TAIWAN: Coalition strong (US L{us_lvl}, ROC L{def_lvl})',
                'long_text':  f'TAIWAN coalition posture strong — US partnership L{us_lvl}, ROC defense L{def_lvl}; deterrence coordinated.',
            })

        if domestic_resv >= 4:
            signals.append({
                'priority':   6,
                'category':   'domestic_resolve',
                'theatre':    'taiwan',
                'level':      domestic_resv,
                'icon':       '🏛️',
                'color':      '#0ea5e9',
                'short_text': f'{flag} TAIWAN: Domestic resolve L{domestic_resv}',
                'long_text':  f'TAIWAN domestic resolve L{domestic_resv} — Lai presidential signaling and asymmetric resilience aligned.',
            })

    # ---- 5. DPRK-SPECIFIC: leverage (inverted) + nuclear tripwire + expeditionary ----
    # The DPRK instrument is INVERTED: a low leverage_integrity is the DANGEROUS
    # reading, because Pyongyang escalates when it is negotiated around, not when
    # it is courted. A generic score read would call this "high pressure" and stop;
    # these vectors surface WHY -- the leverage-decay logic, the discrete Black
    # Swan (a seventh test), and the expeditionary transfer convergence.
    if theatre == 'dprk':
        lev = _safe_dict(raw_data.get('leverage_integrity'))
        lev_state = _safe_str(lev.get('state'))
        lev_score = _safe_int(lev.get('integrity'))

        if lev_state in ('decaying', 'collapsed'):
            signals.append({
                'priority':   11,
                'category':   'leverage_decay',
                'theatre':    'dprk',
                'level':      4 if lev_state == 'decaying' else 5,
                'icon':       '🎰',
                'color':      '#ef4444' if lev_state == 'decaying' else '#dc2626',
                'short_text': f'{flag} DPRK: Leverage {lev_state.upper()} ({lev_score}/100)',
                'long_text':  (f'DPRK leverage {lev_state} at {lev_score}/100 — the relevance-'
                               f'signal band. Pyongyang historically escalates FOR ATTENTION '
                               f'when its war-rent is switched off, not when it is courted. '
                               f'Read a provocation here as a bid for relevance, not advantage.'),
            })

        trip = _safe_str(_safe_dict(raw_data.get('nuclear_tripwire')).get('state'))
        if trip in ('APPROACHING', 'BREACHED'):
            signals.append({
                'priority':   13 if trip == 'BREACHED' else 10,
                'category':   'nuclear_tripwire',
                'theatre':    'dprk',
                'level':      5 if trip == 'BREACHED' else 4,
                'icon':       '☢️',
                'color':      '#dc2626' if trip == 'BREACHED' else '#ef4444',
                'short_text': f'{flag} DPRK: Nuclear test tripwire {trip}',
                'long_text':  (f'DPRK nuclear-test tripwire {trip} — the discrete Black Swan. '
                               f'A seventh test resets the baseline for every downstream read.'),
            })

        prov_class = _safe_str(raw_data.get('provocation_class'))
        if raw_data.get('provocation_active') and prov_class:
            signals.append({
                'priority':   9,
                'category':   'nuclear_signaling',
                'theatre':    'dprk',
                'level':      3,
                'icon':       '🚀',
                'color':      '#f59e0b',
                'short_text': f'{flag} DPRK: {prov_class.replace("_", " ").title()} signaling',
                'long_text':  (f'DPRK provocation active — class {prov_class.replace("_", " ")}. '
                               f'Location is the audience: type and site carry the message.'),
            })

        exped = _safe_dict(raw_data.get('expeditionary_footprint'))
        if exped.get('tunnel_convergence'):
            hosts = ', '.join(_safe_list(exped.get('hosts'))[:3])
            signals.append({
                'priority':   10,
                'category':   'expeditionary_footprint',
                'theatre':    'dprk',
                'level':      4,
                'icon':       '🔨',
                'color':      '#a855f7',
                'short_text': f'{flag} DPRK: Expeditionary convergence ({hosts})',
                'long_text':  (f'DPRK labor + tunnel-construction + malign-actor co-location '
                               f'({hosts}) converging — the compound pattern that has preceded '
                               f'documented transfers of DPRK tunnelling expertise.'),
            })

    # Sort descending; BLUF will dedupe + globally rank with other regions
    signals.sort(key=lambda s: s['priority'], reverse=True)
    return signals


# ============================================================
# TRACKER READERS
# ============================================================
def _read_all_trackers():
    """
    Read all Asia tracker caches and normalize via shim.
    Returns dict of tracker_name -> NORMALIZED data.
    Missing caches are simply omitted (graceful degradation).
    """
    trackers = {}
    for theatre, redis_key in TRACKER_KEYS.items():
        raw = _redis_get(redis_key)
        if raw:
            normalized = _normalize_tracker_data(theatre, raw)
            if normalized:
                trackers[theatre] = normalized
                lvls = normalized['levels']
                axis_str = (f"T{lvls['threat']}" +
                            (f"/I{lvls['influence']}" if lvls['influence'] is not None else ''))
                print(f'[Asia BLUF] {theatre}: loaded ({axis_str}, score={normalized["score"]})')
        else:
            print(f'[Asia BLUF] {theatre}: no cache available')
    return trackers


# ============================================================
# POSTURE DETERMINATION
# ============================================================
def _determine_regional_posture(trackers):
    """
    Roll up posture across ALL live Asia trackers (v2.5, Jun 2026).
    Previously China + Taiwan only -- which meant a Pakistan/Japan/India spike
    could never lift max_level (the value GPI reads at altitude 3). Now max_level
    and breached_count span every live tracker, and the peak theatre is named.
    China/Taiwan extras (deterrence_gap, kinetic_pressure) are preserved as
    additional ladder triggers and for the cross-strait synthesis.
    """
    trackers = _safe_dict(trackers)

    levels      = {}
    breached_by = {}
    for theatre, data in trackers.items():
        data = _safe_dict(data)
        levels[theatre]      = _safe_int(_safe_dict(data.get('levels')).get('threat'))
        breached_by[theatre] = sum(
            1 for r in _safe_list(data.get('red_lines'))
            if _safe_dict(r).get('status') == 'BREACHED'
        )

    max_level      = max(levels.values()) if levels else 0
    total_breached = sum(breached_by.values())
    # Peak theatre = highest level (canonical-order tie-break via dict order)
    peak_theatre   = max(levels, key=lambda t: levels[t]) if levels else None

    # China/Taiwan extras (preserved for backward compat + cross-strait synthesis)
    cn_so_what       = _safe_dict(_safe_dict(trackers.get('china')).get('so_what'))
    tw_so_what       = _safe_dict(_safe_dict(trackers.get('taiwan')).get('so_what'))
    deterrence_gap   = _safe_int(tw_so_what.get('deterrence_gap'))
    kinetic_pressure = _safe_int(cn_so_what.get('kinetic_pressure'))
    inbound_pressure = _safe_int(tw_so_what.get('inbound_pressure'))
    cn_level         = _safe_int(levels.get('china'))
    tw_level         = _safe_int(levels.get('taiwan'))

    # ── Scenario ladder (max_level now spans ALL trackers) ──
    if total_breached >= 2 or max_level >= 5:
        label, color = 'CRITICAL -- MULTI-BREACH OR ACTIVE CONFLICT', '#dc2626'
    elif total_breached >= 1 or max_level >= 4 or deterrence_gap >= 3:
        label, color = 'ELEVATED -- RED LINE OR DETERRENCE GAP', '#ef4444'
    elif max_level >= 3 or kinetic_pressure >= 3:
        label, color = 'ELEVATED -- CONFRONTATION', '#f97316'
    elif max_level >= 2 or deterrence_gap >= 2:
        label, color = 'WARNING', '#f59e0b'
    elif max_level >= 1:
        label, color = 'MONITORING -- RHETORIC', '#3b82f6'
    else:
        label, color = 'BASELINE', '#6b7280'

    return {
        'label':             label,
        'color':             color,
        'peak_level':        max_level,
        'peak_theatre':      peak_theatre,
        'levels_by_theatre': levels,
        'cn_level':          cn_level,
        'tw_level':          tw_level,
        'breached_count':    total_breached,
        'deterrence_gap':    deterrence_gap,
        'kinetic_pressure':  kinetic_pressure,
        'inbound_pressure':  inbound_pressure,
    }


# ============================================================
# BLUF PROSE SYNTHESIS
# ============================================================
def _country_line(theatre, data):
    """One plain-language sentence for a single tracker (v2.5, Jun 2026).
    Active theatres (level >= 2 or a breached red line) speak in their own voice
    -- the tracker's own bluf or top-signal long_text. Quiet theatres fall back to
    a static regional-role clause, so every live theatre still carries a 'why it
    matters' tail (this is what guarantees India / Japan are never silent)."""
    data = _safe_dict(data)
    name = THEATRE_DISPLAY.get(theatre, theatre.upper())
    flag = THEATRE_FLAGS.get(theatre, '')
    lvl  = _safe_int(_safe_dict(data.get('levels')).get('threat'))
    lvl_label = ESCALATION_LABELS.get(lvl, 'Monitoring').lower()
    raw  = _safe_dict(data.get('raw'))
    sigs = _safe_list(data.get('top_signals'))
    breached = sum(
        1 for r in _safe_list(data.get('red_lines'))
        if _safe_dict(r).get('status') == 'BREACHED'
    )
    # The theatre's own plain-language line, if it publishes one
    own = _safe_str(raw.get('bluf')).strip()
    if not own and sigs:
        own = _safe_str(_safe_dict(sigs[0]).get('long_text')).strip()
    role = THEATRE_ROLE.get(theatre, '')
    top_sig_lvl = _safe_int(_safe_dict(sigs[0]).get('level')) if sigs else 0
    # Active (own voice) if escalated, breached, OR carrying a high-level signal
    # (e.g. a cross-theater convergence) even while the headline level is low.
    active = (lvl >= 2 or breached or top_sig_lvl >= 3)
    tail = own if (active and own) else (role or own)
    lead = f"{flag} {name}: {lvl_label}"
    line = f"{lead} -- {tail}" if tail else f"{lead}."
    if line[-1] not in '.!?':
        line += '.'
    return line


def _build_bluf_prose(posture, trackers):
    """Generate the regional prose paragraph in plain language (v2.5, Jun 2026).
    Multi-country: every live tracker contributes a sentence (was China + Taiwan
    only). The So-What pops because each theatre speaks in its own voice when
    active and carries a regional-role clause when quiet. Ordered most-active first.
    """
    trackers = _safe_dict(trackers)
    date_str = datetime.now(timezone.utc).strftime('%b %d, %Y')
    parts = [f"Asia-Pacific Rhetoric Monitor ({date_str}):"]

    # Plain posture line, naming the peak theatre
    plain_posture = posture['label'].split('--')[0].strip().title() or 'Baseline'
    peak      = posture.get('peak_theatre')
    peak_name = THEATRE_DISPLAY.get(peak, '')
    peak_flag = THEATRE_FLAGS.get(peak, '')
    peak_lvl  = _safe_int(posture.get('peak_level'))
    if peak_lvl >= 1 and peak_name:
        parts.append(
            f"Regional posture {plain_posture} -- the sharpest signal is "
            f"{peak_flag} {peak_name} at {ESCALATION_LABELS.get(peak_lvl, '').lower()} (L{peak_lvl})."
        )
    else:
        parts.append(f"Regional posture {plain_posture} -- all Asia-Pacific trackers at or near baseline.")

    # One sentence per live tracker, most active first
    levels = _safe_dict(posture.get('levels_by_theatre'))
    order  = sorted(trackers.keys(), key=lambda t: -_safe_int(levels.get(t)))
    for theatre in order:
        parts.append(_country_line(theatre, trackers[theatre]))

    # Cross-country convergence -- most specific first
    cn_l   = _safe_int(levels.get('china'))
    tw_l   = _safe_int(levels.get('taiwan'))
    l3plus = [THEATRE_DISPLAY.get(t, t.upper()) for t in trackers
              if _safe_int(levels.get(t)) >= 3]
    if cn_l >= 3 and tw_l >= 3:
        parts.append(
            "Mutual cross-strait escalation -- China and Taiwan are both at Direct-Threat level "
            "or higher at the same time; the US / Taiwan / Japan coordination tempo becomes the "
            "decisive variable."
        )
    elif len(l3plus) >= 2:
        parts.append(
            f"Multiple theaters elevated at once ({', '.join(l3plus)}) -- the combination compounds "
            f"risk beyond any single front; watch for cross-theater coordination."
        )
    elif _safe_int(posture.get('breached_count')) >= 1:
        parts.append(
            f"{posture['breached_count']} red line(s) breached across Asia-Pacific -- "
            f"adjacent categories warrant elevated monitoring for cascade."
        )

    return ' '.join(parts)


# ============================================================
# TOP SIGNALS COLLECTOR (v2.1)
# ============================================================
def _build_signals(posture, trackers):
    """
    v2.1 NEW PIPELINE.
    Each tracker — whether v2.0+ self-emitting or legacy shimmed —
    arrives normalized with a 'top_signals' array attached. This function:
      1. Collects all top_signals[] from all trackers
      2. Adds an Asia-specific cross-tracker MUTUAL ESCALATION signal if applicable
      3. Globally sorts by priority (descending)
      4. Dedupes by (theatre, category) key
      5. Returns top TOP_SIGNALS_COUNT (5)
    """
    all_signals = []
    for theatre, data in trackers.items():
        for sig in data.get('top_signals', []):
            sig.setdefault('priority', 5)
            sig.setdefault('category', 'unknown')
            sig.setdefault('theatre', theatre)
            sig.setdefault('icon', '•')
            sig.setdefault('color', '#6b7280')
            sig.setdefault('short_text', '')
            sig.setdefault('long_text', sig.get('short_text', ''))
            all_signals.append(sig)

    # Cross-tracker: Mutual cross-strait escalation
    cn_level = posture.get('cn_level', 0)
    tw_level = posture.get('tw_level', 0)
    if cn_level >= 3 and tw_level >= 3:
        all_signals.append({
            'priority':   13,
            'category':   'mutual_escalation',
            'theatre':    'regional',
            'level':      max(cn_level, tw_level),
            'icon':       '🌀',
            'color':      '#dc2626',
            'short_text': 'CROSS-STRAIT: Mutual escalation L3+',
            'long_text':  'CROSS-STRAIT MUTUAL ESCALATION: Both sides simultaneously at L3+ — coordination window compressed; US/Taiwan/Japan tempo decisive.',
        })

    # Global sort
    all_signals.sort(key=lambda x: x.get('priority', 0), reverse=True)
    # Dedupe by (theatre, category) AND enforce per-theatre quota (v2.4.0 May 21 2026)
    # Per-tracker quota: max MAX_PER_THEATRE signals per country tracker.
    # Cross-tracker signals (theatre='regional') bypass the quota — they're
    # platform-level convergence signals, not per-country emissions.
    seen           = set()
    theatre_counts = {}
    deduped        = []
    for s in all_signals:
        theatre = s.get('theatre', '')
        key     = f'{theatre}:{s.get("category", "")}'
        if key in seen:
            continue
        if theatre != 'regional' and theatre_counts.get(theatre, 0) >= MAX_PER_THEATRE:
            continue
        seen.add(key)
        theatre_counts[theatre] = theatre_counts.get(theatre, 0) + 1
        deduped.append(s)
    # Baseline fallback if absolutely nothing
    if not deduped:
        deduped.append({
            'priority':   1,
            'category':   'baseline',
            'theatre':    'regional',
            'level':      0,
            'icon':       '🌏',
            'color':      '#6b7280',
            'short_text': 'Asia-Pacific at baseline',
            'long_text':  'All Asia-Pacific theaters at baseline — monitoring for coercion escalation.',
        })

    return deduped     # v2.3.0: full deduped pool (caller caps for display)


# ============================================================
# MAIN BUILD FUNCTION (matches ME pattern -- cache check inside)
# ============================================================
# ── Multi-axis tagging + structured BLUF blocks (Jun 13 2026, approach B) ──
# Mirrors the GPI's NARRATIVE_AXIS_SETS so regional signals declare their axis
# set; the front-end renders one pill per axis. Primary axis first.
_REGIONAL_AXIS_SETS = {
    'kinetic_pressure': ['kinetic'], 'red_line_breached': ['kinetic'],
    'theatre_high': ['kinetic'], 'theatre_active': ['kinetic'],
    'mutual_escalation': ['kinetic'], 'deterrence_gap': ['kinetic'],
    'china_two_front_convergence': ['kinetic', 'diplomatic'],
    'scs_red_line': ['kinetic'], 'kinetic_threshold': ['kinetic'],
    'sovereignty_erosion': ['kinetic', 'diplomatic'],
    'economic_stress': ['economic'], 'sovereign_default': ['economic'],
    'commodity': ['economic'], 'commodity_coupling': ['economic'],
    'hormuz_japan_oil_dependency': ['economic'],
    'green_line_active': ['diplomatic'], 'diplomatic_track_active': ['diplomatic'],
    'diplomatic_active': ['diplomatic'], 'coalition_positive': ['diplomatic'],
    'humanitarian': ['humanitarian'], 'displacement': ['humanitarian'],
    'health_emergency': ['humanitarian'], 'food_price_crisis': ['humanitarian'],
}
_AXIS_KEYWORD_HINTS = [
    ('economic', ['economic', 'default', 'reserves', 'oil', 'commodity', 'trade', 'currency', 'sanction']),
    ('humanitarian', ['humanitarian', 'displace', 'refugee', 'famine', 'health', 'outbreak']),
    ('diplomatic', ['diplomatic', 'coalition', 'partnership', 'deterrence-positive', 'mediation', 'negotiat']),
]

def _axes_for_signal(sig):
    """Ordered axis list for a regional signal. category map > keyword hint >
    kinetic default."""
    cat = _safe_str(_safe_dict(sig).get('category')).lower()
    if cat in _REGIONAL_AXIS_SETS:
        return list(_REGIONAL_AXIS_SETS[cat])
    blob = (cat + ' ' + _safe_str(sig.get('short_text')) + ' ' +
            _safe_str(sig.get('long_text'))).lower()
    for axis, kws in _AXIS_KEYWORD_HINTS:
        if any(k in blob for k in kws):
            return [axis]
    return ['kinetic']

def _tag_signal_axes(signals):
    """Attach 'axes' (and align primary 'pressure_type') to each signal."""
    out = []
    for s in _safe_list(signals):
        s2 = dict(s)
        axes = _axes_for_signal(s2)
        s2['axes'] = axes
        s2.setdefault('pressure_type', axes[0])
        out.append(s2)
    return out

def _build_bluf_blocks(posture, trackers):
    """Structured paragraph blocks for the front-end (approach B).
    Returns a list of {label, text} dicts. label='' renders as a plain
    paragraph; a non-empty label renders bold/highlighted (e.g. the header).
    Built from the same parts as _build_bluf_prose so the two stay in sync."""
    trackers = _safe_dict(trackers)
    date_str = datetime.now(timezone.utc).strftime('%b %d, %Y')
    plain_posture = posture['label'].split('--')[0].strip().title() or 'Baseline'
    peak      = posture.get('peak_theatre')
    peak_name = THEATRE_DISPLAY.get(peak, '')
    peak_flag = THEATRE_FLAGS.get(peak, '')
    peak_lvl  = _safe_int(posture.get('peak_level'))

    blocks = []
    # Block 1: header (highlighted label, no body)
    blocks.append({'label': f'Asia-Pacific Rhetoric Monitor ({date_str})', 'text': ''})

    # Block 2: Regional posture (highlighted)
    if peak_lvl >= 1 and peak_name:
        posture_txt = (f"{plain_posture} -- the sharpest signal is {peak_flag} "
                       f"{peak_name} at {ESCALATION_LABELS.get(peak_lvl, '').lower()} (L{peak_lvl}).")
    else:
        posture_txt = f"{plain_posture} -- all Asia-Pacific trackers at or near baseline."
    blocks.append({'label': 'Regional Posture', 'text': posture_txt})

    # Block 3: Theatre Reads -- one sentence per live tracker, most active first
    levels = _safe_dict(posture.get('levels_by_theatre'))
    order  = sorted(trackers.keys(), key=lambda t: -_safe_int(levels.get(t)))
    country_lines = [_country_line(theatre, trackers[theatre]) for theatre in order]
    if country_lines:
        blocks.append({'label': 'Theatre Reads', 'text': ' '.join(country_lines)})

    # Block 4: Convergence closer (highlighted) -- same logic as prose builder
    cn_l   = _safe_int(levels.get('china'))
    tw_l   = _safe_int(levels.get('taiwan'))
    l3plus = [THEATRE_DISPLAY.get(t, t.upper()) for t in trackers
              if _safe_int(levels.get(t)) >= 3]
    closer = None
    if cn_l >= 3 and tw_l >= 3:
        closer = ("Mutual cross-strait escalation -- China and Taiwan are both at Direct-Threat "
                  "level or higher at the same time; the US / Taiwan / Japan coordination tempo "
                  "becomes the decisive variable.")
    elif len(l3plus) >= 2:
        closer = (f"Multiple theaters elevated at once ({', '.join(l3plus)}) -- the combination "
                  f"compounds risk beyond any single front; watch for cross-theater coordination.")
    elif _safe_int(posture.get('breached_count')) >= 1:
        closer = (f"{posture['breached_count']} red line(s) breached across Asia-Pacific -- "
                  f"adjacent categories warrant elevated monitoring for cascade.")
    if closer:
        blocks.append({'label': 'Convergence Watch', 'text': closer})

    return blocks


def build_regional_bluf(force=False):
    """
    Build the Asia regional BLUF. Reads China + Taiwan caches, synthesizes,
    caches result in Redis. Returns dict.

    Cache check is inside this function (matches ME pattern). The endpoint
    handler simply calls this and returns the result.
    """
    # Cache-first unless forced
    if not force:
        cached = _redis_get(BLUF_CACHE_KEY)
        if cached and cached.get('generated_at'):
            try:
                age = (datetime.now(timezone.utc) -
                       datetime.fromisoformat(cached['generated_at'])).total_seconds()
                if age < BLUF_CACHE_TTL:
                    cached['from_cache'] = True
                    return cached
            except Exception:
                pass

    print('[Asia BLUF v2.1] Building regional BLUF from all Asia tracker caches...')

    try:
        trackers = _read_all_trackers()

        if not trackers:
            return {
                'success': False,
                'error':   'No tracker data available',
                'bluf':    'BLUF unavailable -- no tracker caches loaded.',
                'signals': [],
                'top_signals': [],
                'posture_label': 'UNAVAILABLE',
                'posture_color': '#6b7280',
            }

        posture = _determine_regional_posture(trackers)
        bluf    = _build_bluf_prose(posture, trackers)
        # v2.3.0: signals collector returns full pool; cap separately for display
        all_signals = _build_signals(posture, trackers)            # full pool — for GPI axis aggregation
        all_signals = _tag_signal_axes(all_signals)                # Jun 13 2026: multi-axis pills
        top_signals = all_signals[:TOP_SIGNALS_COUNT]                # capped for display
        bluf_blocks = _build_bluf_blocks(posture, trackers)         # approach B structured blocks

        trackers_live = len(trackers)

        # v2.1: Per-theatre summary (canonical — matches ME BLUF output shape)
        theatre_summary = {}
        for t, data in trackers.items():
            lvls       = _safe_dict(data.get('levels'))
            threat_lvl = _safe_int(lvls.get('threat'))
            infl_lvl   = lvls.get('influence')
            theatre_summary[t] = {
                'level':            threat_lvl,
                'label':            ESCALATION_LABELS.get(threat_lvl, 'Unknown'),
                'color':            ESCALATION_COLORS.get(threat_lvl, '#6b7280'),
                'score':            data.get('score', 0),
                'flag':             data.get('flag', THEATRE_FLAGS.get(t, '')),
                'timestamp':        data.get('scanned_at', ''),
                # Dual-axis fields:
                'threat_level':     threat_lvl,
                'influence_level':  infl_lvl,
                'green_level':      lvls.get('green'),
                'dominant_axis':    lvls.get('dominant_axis', 'threat'),
                'dominant_level':   lvls.get('dominant_level', threat_lvl),
                'is_dual_axis':     infl_lvl is not None,
                'influence_label':  INFLUENCE_LABELS.get(infl_lvl, '') if infl_lvl is not None else None,
                'influence_color':  INFLUENCE_COLORS.get(infl_lvl, '#6b7280') if infl_lvl is not None else None,
            }

        # Theatres at L3+ (matches ME pattern for GPI consumption)
        theatres_at_l3plus = sum(
            1 for t in theatre_summary.values() if t.get('threat_level', 0) >= 3
        )

        # Average score across live trackers
        scores = [t.get('score', 0) for t in theatre_summary.values()]
        avg_score = round(sum(scores) / len(scores), 1) if scores else 0

        result = {
            'success':            True,
            'from_cache':         False,
            'bluf':               bluf,
            'bluf_v2':            bluf_blocks,           # Jun 13 2026: structured paragraph blocks (approach B)
            'signals':            all_signals,           # v2.3.0: FULL signal pool — for GPI axis aggregation
            'top_signals':        top_signals,           # v2.3.0: capped — for display + prose synthesis
            'posture_label':      posture['label'],
            'posture_color':      posture['color'],
            'peak_level':         posture['peak_level'], # legacy alias
            'max_level':          posture['peak_level'], # canonical (GPI reads this)
            'avg_score':          avg_score,
            'cn_level':           posture['cn_level'],
            'tw_level':           posture['tw_level'],
            'deterrence_gap':     posture['deterrence_gap'],
            'kinetic_pressure':   posture['kinetic_pressure'],
            'red_lines_breached': posture['breached_count'],
            'trackers_live':      trackers_live,
            'theatres_live':      trackers_live,         # canonical alias
            'theatres_at_l3plus': theatres_at_l3plus,    # canonical
            'trackers_total':     len(TRACKER_KEYS),
            'theatre_summary':    theatre_summary,       # canonical
            'generated_at':       datetime.now(timezone.utc).isoformat(),
            'version':            '2.1.0',
            'region':             'asia',                # canonical (GPI reads this)
            'top_signals_count':  len(top_signals),
        }

        _redis_set(BLUF_CACHE_KEY, result)
        print(f"[Asia BLUF v2.1] Built: posture={posture['label']}, "
              f"max_level=L{posture['peak_level']}, "
              f"breached={posture['breached_count']}, "
              f"signals={len(top_signals)}, "
              f"deterrence_gap=L{posture['deterrence_gap']}")
        return result

    except Exception as e:
        # Full traceback to Render logs
        print(f"[Asia BLUF] SYNTHESIS EXCEPTION: {e}")
        print(f"[Asia BLUF] Traceback follows:")
        print(traceback.format_exc())
        return {
            'success': False,
            'error':   f'{type(e).__name__}: {str(e)[:300]}',
            'bluf':    'BLUF synthesis failed -- check backend logs for traceback.',
            'signals': [],
            'posture_label': 'ERROR',
            'posture_color': '#6b7280',
        }


# ============================================================
# ROUTE REGISTRATION (matches ME pattern -- imports inside)
# ============================================================
def register_asia_bluf_routes(app):
    """Register Asia BLUF endpoints on the given Flask app."""
    from flask import jsonify, request as flask_request

    @app.route('/api/rhetoric/asia/bluf', methods=['GET'])
    def asia_regional_bluf():
        force = flask_request.args.get('force', 'false').lower() == 'true'
        result = build_regional_bluf(force=force)
        return jsonify(result)

    @app.route('/api/rhetoric/asia/bluf/debug', methods=['GET'])
    def asia_regional_bluf_debug():
        """
        Diagnostic endpoint -- reveals what's actually in Redis.
        Does NOT attempt synthesis. Safe to hit even when synthesis is broken.
        """
        try:
            china  = _redis_get(CHINA_CACHE_KEY)
            taiwan = _redis_get(TAIWAN_CACHE_KEY)
            bluf   = _redis_get(BLUF_CACHE_KEY)

            def _describe(obj, name):
                if obj is None:
                    return {'status': 'MISSING', 'name': name}
                if not isinstance(obj, dict):
                    return {'status': 'BAD_TYPE', 'name': name, 'type': type(obj).__name__}
                return {
                    'status':          'OK',
                    'name':            name,
                    'top_level_keys':  sorted(obj.keys()),
                    'has_so_what':     isinstance(obj.get('so_what'), dict),
                    'so_what_keys':    sorted(_safe_dict(obj.get('so_what')).keys()),
                    'has_red_lines':   isinstance(obj.get('red_lines'), list),
                    'red_lines_count': len(_safe_list(obj.get('red_lines'))),
                    'overall_level':   obj.get('overall_level'),
                    'scanned_at':      obj.get('scanned_at'),
                    'version':         obj.get('version'),
                }

            return jsonify({
                'success':          True,
                'redis_configured': bool(UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN),
                'china_cache':      _describe(china,  CHINA_CACHE_KEY),
                'taiwan_cache':     _describe(taiwan, TAIWAN_CACHE_KEY),
                'bluf_cache':       _describe(bluf,   BLUF_CACHE_KEY),
                'module_version':   '2.0.0-asia-bluf',
            })
        except Exception as e:
            return jsonify({
                'success':   False,
                'error':     f'{type(e).__name__}: {str(e)[:300]}',
                'traceback': traceback.format_exc()[:1500],
            }), 500

    print('[Asia BLUF] Routes registered: /api/rhetoric/asia/bluf + /bluf/debug')
