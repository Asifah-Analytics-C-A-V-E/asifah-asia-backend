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
    'china':  'rhetoric:china:latest',
    'taiwan': 'rhetoric:taiwan:latest',
    # Future Asia trackers slot in here:
    # 'japan':       'rhetoric:japan:latest',
    # 'korea_north': 'rhetoric:dprk:latest',
    # 'india':       'rhetoric:india:latest',
    # 'philippines': 'rhetoric:philippines:latest',
}

THEATRE_FLAGS = {
    'china':  '\U0001f1e8\U0001f1f3',  # 🇨🇳
    'taiwan': '\U0001f1f9\U0001f1fc',  # 🇹🇼
}

THEATRE_DISPLAY = {
    'china':  'CHINA',
    'taiwan': 'TAIWAN',
}

# Top-N signals emitted to GPI (matches ME pattern)
TOP_SIGNALS_COUNT = 5

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
        # Fallbacks for any other Asia tracker
        threat = _safe_int(raw_data.get('theatre_escalation_level',
                          raw_data.get('threat_level', 0)))

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
        top_signals = raw_data['top_signals']
    else:
        top_signals = _synthesize_top_signals_legacy(
            theatre, raw_data, threat_int, score, so_what, red_lines
        )

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
        'scanned_at':   _safe_str(raw_data.get('scanned_at') or raw_data.get('timestamp', '')),
        'raw':          raw_data,
    }


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
    if threat_int >= 4:
        signals.append({
            'priority':   9 + threat_int,
            'category':   'theatre_high',
            'theatre':    theatre,
            'level':      threat_int,
            'icon':       '🔴',
            'color':      ESCALATION_COLORS.get(threat_int, '#6b7280'),
            'short_text': f'{flag} {display} L{threat_int} — {ESCALATION_LABELS.get(threat_int, "")}',
            'long_text':  f'{flag} {display} at L{threat_int} {ESCALATION_LABELS.get(threat_int, "")} (score {score}/100)',
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
def _determine_regional_posture(china, taiwan):
    """
    Roll up posture across China + Taiwan.
    v2.1: Consumes NORMALIZED tracker dicts (post-shim).
    Taiwan's deterrence_gap is the critical extra signal unique to this region.
    """
    china  = _safe_dict(china)
    taiwan = _safe_dict(taiwan)

    # v2.1: read threat level from normalized 'levels' dict
    cn_levels = _safe_dict(china.get('levels'))
    tw_levels = _safe_dict(taiwan.get('levels'))
    cn_level  = _safe_int(cn_levels.get('threat'))
    tw_level  = _safe_int(tw_levels.get('threat'))
    max_level = max(cn_level, tw_level)

    # red_lines + so_what live at top level of normalized shape
    cn_red_lines = _safe_list(china.get('red_lines'))
    tw_red_lines = _safe_list(taiwan.get('red_lines'))
    cn_breached  = sum(1 for r in cn_red_lines if _safe_dict(r).get('status') == 'BREACHED')
    tw_breached  = sum(1 for r in tw_red_lines if _safe_dict(r).get('status') == 'BREACHED')
    total_breached = cn_breached + tw_breached

    cn_so_what = _safe_dict(china.get('so_what'))
    tw_so_what = _safe_dict(taiwan.get('so_what'))

    deterrence_gap   = _safe_int(tw_so_what.get('deterrence_gap'))
    kinetic_pressure = _safe_int(cn_so_what.get('kinetic_pressure'))
    inbound_pressure = _safe_int(tw_so_what.get('inbound_pressure'))

    # ── Scenario ladder ──
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
        'label':            label,
        'color':            color,
        'peak_level':       max_level,
        'cn_level':         cn_level,
        'tw_level':         tw_level,
        'breached_count':   total_breached,
        'deterrence_gap':   deterrence_gap,
        'kinetic_pressure': kinetic_pressure,
        'inbound_pressure': inbound_pressure,
    }


# ============================================================
# BLUF PROSE SYNTHESIS
# ============================================================
def _build_bluf_prose(posture, china, taiwan):
    """
    Generate regional prose paragraph. 2-4 sentences.
    v2.1: Consumes NORMALIZED tracker dicts. Reads underlying tracker fields via .raw,
    threat level via .levels.threat, so_what + red_lines at top level.
    """
    cn = _safe_dict(china)
    tw = _safe_dict(taiwan)
    cn_raw = _safe_dict(cn.get('raw'))   # original tracker fields
    tw_raw = _safe_dict(tw.get('raw'))
    cn_so_what = _safe_dict(cn.get('so_what'))
    tw_so_what = _safe_dict(tw.get('so_what'))

    date_str = datetime.now(timezone.utc).strftime('%b %d, %Y')
    parts = [f"Asia-Pacific Rhetoric Monitor ({date_str}):"]

    parts.append(
        f"Regional posture at {posture['label']} -- peak escalation L{posture['peak_level']} "
        f"across China + Taiwan trackers."
    )

    # China vector — read level from normalized, sub-vectors from raw
    cn_level   = _safe_int(_safe_dict(cn.get('levels')).get('threat'))
    cn_kinetic = _safe_int(cn_so_what.get('kinetic_pressure'))
    cn_econ    = _safe_int(cn_so_what.get('economic_pressure'))
    cn_pla     = _safe_int(cn_raw.get('pla_level'))
    cn_xi      = _safe_int(cn_raw.get('xi_level'))

    if cn_level or cn_kinetic or cn_econ:
        china_desc = f"China coercion at L{cn_level}"
        if cn_kinetic >= 3:
            china_desc += f" -- kinetic vector L{cn_kinetic} (PLA operational L{cn_pla})"
            if cn_econ >= 3:
                china_desc += f" converging with economic coercion L{cn_econ}"
            china_desc += "."
        elif cn_kinetic >= 2:
            china_desc += f" -- kinetic signaling L{cn_kinetic}, below operational threshold."
        elif cn_econ >= 3:
            china_desc += f" -- economic coercion L{cn_econ} leading, kinetic restrained."
        elif cn_xi >= 2:
            china_desc += f" -- Xi/CMC L{cn_xi} political signaling, below operational tempo."
        else:
            china_desc += " -- baseline rhetoric, no operational signals."
        parts.append(china_desc)

    # Taiwan vector
    tw_level = _safe_int(_safe_dict(tw.get('levels')).get('threat'))
    tw_def   = _safe_int(tw_raw.get('defense_level'))
    tw_us    = _safe_int(tw_raw.get('us_level'))
    tw_gap   = _safe_int(tw_so_what.get('deterrence_gap'))
    tw_det   = _safe_int(tw_so_what.get('deterrence_strength'))

    if tw_level or tw_gap or tw_det:
        tw_desc = f"Taiwan deterrence at L{tw_level}"
        if tw_gap >= 3:
            tw_desc += f" -- ⚠️ deterrence gap L{tw_gap} (inbound pressure exceeds coalition response)."
        elif tw_gap >= 2:
            tw_desc += f" -- deterrence gap L{tw_gap} warrants coalition reinforcement."
        elif tw_us >= 3 and tw_def >= 3:
            tw_desc += f" -- strong coalition posture (US L{tw_us}, ROC defense L{tw_def})."
        elif tw_us >= 2:
            tw_desc += f" -- US partnership L{tw_us}, defense L{tw_def}, baseline deterrence."
        else:
            tw_desc += " -- routine posture, coalition and defense signals at baseline."
        parts.append(tw_desc)

    # Convergence / cross-strait synthesis
    if cn_level >= 3 and tw_level >= 3:
        parts.append(
            f"⚠️ Mutual cross-strait escalation -- both sides at L3+ simultaneously. "
            f"Coordination tempo between US/Taiwan/Japan becomes decisive variable."
        )
    elif cn_level >= 3 and tw_gap >= 2:
        parts.append(
            f"China escalating into a deterrence gap -- classic coercion-into-weakness pattern. "
            f"Watch coalition response tempo in next 48-72 hours."
        )
    elif posture['breached_count'] >= 1:
        parts.append(
            f"{posture['breached_count']} red line(s) breached across Asia-Pacific trackers -- "
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

    # Dedupe by (theatre, category)
    seen = set()
    deduped = []
    for s in all_signals:
        key = f'{s.get("theatre", "")}:{s.get("category", "")}'
        if key not in seen:
            seen.add(key)
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

    return deduped[:TOP_SIGNALS_COUNT]


# ============================================================
# MAIN BUILD FUNCTION (matches ME pattern -- cache check inside)
# ============================================================
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

        china  = trackers.get('china')
        taiwan = trackers.get('taiwan')

        posture = _determine_regional_posture(china, taiwan)
        bluf    = _build_bluf_prose(posture, china, taiwan)
        # v2.1: signals collector now reads from ALL trackers' top_signals[]
        top_signals = _build_signals(posture, trackers)

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
            'signals':            top_signals,           # legacy alias
            'top_signals':        top_signals,           # canonical (GPI reads this)
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
