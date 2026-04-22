"""
asia_regional_bluf.py
Asifah Analytics -- Asia Backend Module
v1.0.0 -- April 2026

Asia-Pacific Regional BLUF synthesizer.

Reads from China + Taiwan Redis summary caches (populated by their
respective rhetoric trackers) and produces a regional synthesis:
posture, prose BLUF, signals array, vector readouts.

Matches the ME /api/rhetoric/me/bluf response contract so that
rhetoric-asia.html can use the same fetch pattern as rhetoric-index.html.

Expected response shape:
{
    'success':        True,
    'posture_label':  'ELEVATED',
    'posture_color':  '#ef4444',
    'bluf':           '<prose synthesis>',
    'signals':        [{'icon': '⚔️', 'color': '#ef4444', 'text': '...'}, ...],
    'generated_at':   ISO timestamp,
    'from_cache':     bool,
    # additional analytical data:
    'peak_level':         int,
    'deterrence_gap':     int (Taiwan-specific),
    'red_lines_breached': int,
    'trackers_live':      int,
    'trackers_total':     int,
}

Author: RCGG / Asifah Analytics
"""

import os
import json
import time
import threading
from datetime import datetime, timezone
import requests
from flask import jsonify


# ============================================================
# CONFIG
# ============================================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN') or os.environ.get('UPSTASH_REDIS_REST_TOKEN')

# Source caches — written by respective trackers
CHINA_CACHE_KEY   = 'rhetoric:china:latest'
TAIWAN_CACHE_KEY  = 'rhetoric:taiwan:latest'

# Our synthesis cache
BLUF_CACHE_KEY    = 'rhetoric:asia:bluf'
BLUF_CACHE_TTL    = 15 * 60   # 15 minutes

# Background refresh
REFRESH_INTERVAL  = 15 * 60   # 15 minutes
BOOT_DELAY        = 90        # wait for trackers on cold start


# ============================================================
# REDIS HELPERS (REST)
# ============================================================
def _redis_get(key):
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return None
    try:
        r = requests.get(
            f'{UPSTASH_REDIS_URL}/get/{key}',
            headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'},
            timeout=6,
        )
        if r.status_code != 200:
            return None
        data = r.json().get('result')
        if not data:
            return None
        return json.loads(data)
    except Exception as e:
        print(f"[Asia BLUF] redis_get error for {key}: {e}")
        return None


def _redis_set(key, value, ttl=BLUF_CACHE_TTL):
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return False
    try:
        payload = json.dumps(value)
        r = requests.post(
            f'{UPSTASH_REDIS_URL}/set/{key}',
            headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'},
            json={'value': payload, 'EX': ttl},
            timeout=6,
        )
        return r.status_code == 200
    except Exception as e:
        print(f"[Asia BLUF] redis_set error for {key}: {e}")
        return False


# ============================================================
# POSTURE DETERMINATION
# ============================================================
def _determine_regional_posture(china, taiwan):
    """
    Roll up posture across China + Taiwan to a single Asia-Pacific regional label.
    Taiwan's deterrence_gap is a critical extra signal unique to this region.
    """
    cn_level = (china or {}).get('overall_level', 0)
    tw_level = (taiwan or {}).get('overall_level', 0)
    max_level = max(cn_level, tw_level)

    # Extract interpreter fields (if trackers are v1.1.0+, these will exist)
    cn_red_lines = (china or {}).get('red_lines', [])
    tw_red_lines = (taiwan or {}).get('red_lines', [])
    cn_breached = sum(1 for r in cn_red_lines if r.get('status') == 'BREACHED')
    tw_breached = sum(1 for r in tw_red_lines if r.get('status') == 'BREACHED')
    total_breached = cn_breached + tw_breached

    cn_so_what = (china or {}).get('so_what', {}) or {}
    tw_so_what = (taiwan or {}).get('so_what', {}) or {}

    deterrence_gap    = tw_so_what.get('deterrence_gap', 0)
    kinetic_pressure  = cn_so_what.get('kinetic_pressure', 0)
    inbound_pressure  = tw_so_what.get('inbound_pressure', 0)

    # ── Scenario ladder ──
    if total_breached >= 2 or max_level >= 5:
        label = 'CRITICAL -- MULTI-BREACH OR ACTIVE CONFLICT'
        color = '#dc2626'
    elif total_breached >= 1 or max_level >= 4 or deterrence_gap >= 3:
        label = 'ELEVATED -- RED LINE OR DETERRENCE GAP'
        color = '#ef4444'
    elif max_level >= 3 or kinetic_pressure >= 3:
        label = 'ELEVATED -- CONFRONTATION'
        color = '#f97316'
    elif max_level >= 2 or deterrence_gap >= 2:
        label = 'WARNING'
        color = '#f59e0b'
    elif max_level >= 1:
        label = 'MONITORING -- RHETORIC'
        color = '#3b82f6'
    else:
        label = 'BASELINE'
        color = '#6b7280'

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
    Generate regional prose paragraph. 2-4 sentences synthesizing the state.
    """
    cn = china or {}
    tw = taiwan or {}
    cn_so_what = cn.get('so_what', {}) or {}
    tw_so_what = tw.get('so_what', {}) or {}

    date_str = datetime.now(timezone.utc).strftime('%b %d, %Y')

    parts = [f"Asia-Pacific Rhetoric Monitor ({date_str}):"]

    # Regional posture lead
    parts.append(
        f"Regional posture at {posture['label']} -- peak escalation L{posture['peak_level']} "
        f"across China + Taiwan trackers."
    )

    # China vector
    cn_level    = cn.get('overall_level', 0)
    cn_kinetic  = cn_so_what.get('kinetic_pressure', 0)
    cn_econ     = cn_so_what.get('economic_pressure', 0)
    cn_coalition = cn_so_what.get('coalition_pushback', 0)
    cn_pla      = cn.get('pla_level', 0)
    cn_xi       = cn.get('xi_level', 0)

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
    tw_level    = tw.get('overall_level', 0)
    tw_def      = tw.get('defense_level', 0)
    tw_us       = tw.get('us_level', 0)
    tw_diplo    = tw.get('diplomatic_level', 0)
    tw_gap      = tw_so_what.get('deterrence_gap', 0)
    tw_det      = tw_so_what.get('deterrence_strength', 0)
    tw_resolve  = tw_so_what.get('domestic_resolve', 0)

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

    # Convergence flag
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
# SIGNALS ARRAY
# ============================================================
def _build_signals(posture, china, taiwan):
    """
    Build the bluf signals array -- short analytical blurbs with icon+color.
    Frontend renders each as a colored pill.
    """
    cn = china or {}
    tw = taiwan or {}
    cn_so_what = cn.get('so_what', {}) or {}
    tw_so_what = tw.get('so_what', {}) or {}
    cn_red_lines = cn.get('red_lines', [])
    tw_red_lines = tw.get('red_lines', [])

    signals = []

    # Red-line signals first (most important)
    for rl in cn_red_lines[:2]:
        if rl.get('status') == 'BREACHED':
            signals.append({
                'icon':  '🔴',
                'color': '#dc2626',
                'text':  f"CHINA BREACH: {rl.get('label', '')}",
            })
        elif rl.get('status') == 'APPROACHING':
            signals.append({
                'icon':  '🟠',
                'color': '#f97316',
                'text':  f"China approaching: {rl.get('label', '')}",
            })

    for rl in tw_red_lines[:2]:
        if rl.get('status') == 'BREACHED':
            is_positive = rl.get('color') == '#22c55e'
            signals.append({
                'icon':  '🟢' if is_positive else '🔴',
                'color': '#22c55e' if is_positive else '#dc2626',
                'text':  f"TAIWAN {'DETERRENCE-POSITIVE' if is_positive else 'BREACH'}: {rl.get('label', '')}",
            })
        elif rl.get('status') == 'APPROACHING':
            signals.append({
                'icon':  '🟠',
                'color': '#f97316',
                'text':  f"Taiwan approaching: {rl.get('label', '')}",
            })

    # Vector-based signals (if no red-line signals were added, add context)
    if not signals:
        cn_kinetic = cn_so_what.get('kinetic_pressure', 0)
        cn_econ    = cn_so_what.get('economic_pressure', 0)
        if cn_kinetic >= 3:
            signals.append({
                'icon':  '⚔️', 'color': '#ef4444',
                'text':  f"CHINA L{cn.get('overall_level', 0)}: PLA operational "
                         f"L{cn.get('pla_level', 0)} -- cross-strait coercion active"
            })
        if cn_econ >= 3:
            signals.append({
                'icon':  '💰', 'color': '#f97316',
                'text':  f"CHINA: Economic coercion L{cn_econ} -- trade/investment pressure active"
            })

    # Deterrence-gap signal (Taiwan-specific critical reading)
    tw_gap = tw_so_what.get('deterrence_gap', 0)
    if tw_gap >= 3:
        signals.append({
            'icon':  '⚠️', 'color': '#dc2626',
            'text':  f"DETERRENCE GAP L{tw_gap}: inbound pressure exceeding coalition response"
        })
    elif tw_gap >= 2:
        signals.append({
            'icon':  '📉', 'color': '#f59e0b',
            'text':  f"Deterrence gap L{tw_gap}: coalition signaling lagging inbound pressure"
        })

    # Coalition strength signal
    tw_us  = tw.get('us_level', 0)
    tw_def = tw.get('defense_level', 0)
    if tw_us >= 3 and tw_def >= 3 and not any('DETERRENCE' in s.get('text','') for s in signals):
        signals.append({
            'icon':  '🤝', 'color': '#10b981',
            'text':  f"COALITION STRONG: US L{tw_us}, Taiwan defense L{tw_def} -- deterrence coordinated"
        })

    # Mutual escalation warning
    cn_level = cn.get('overall_level', 0)
    tw_level = tw.get('overall_level', 0)
    if cn_level >= 3 and tw_level >= 3:
        signals.append({
            'icon':  '🌀', 'color': '#dc2626',
            'text':  f"MUTUAL ESCALATION: both sides L3+ simultaneously -- coordination window compressed"
        })

    # Baseline fallback
    if not signals:
        signals.append({
            'icon':  '🌏', 'color': '#6b7280',
            'text':  'All Asia-Pacific theaters at baseline -- monitoring for coercion escalation'
        })

    return signals[:6]  # Cap at 6 signals


# ============================================================
# BLUF SYNTHESIS
# ============================================================
def synthesize_asia_bluf():
    """
    Main synthesis function. Reads China + Taiwan caches, produces BLUF dict.
    Returns None if both source caches are empty.
    """
    china  = _redis_get(CHINA_CACHE_KEY)
    taiwan = _redis_get(TAIWAN_CACHE_KEY)

    if not china and not taiwan:
        print("[Asia BLUF] Both source caches empty -- skipping synthesis")
        return None

    trackers_live  = sum(1 for t in [china, taiwan] if t is not None)
    trackers_total = 2

    posture = _determine_regional_posture(china, taiwan)
    bluf    = _build_bluf_prose(posture, china, taiwan)
    signals = _build_signals(posture, china, taiwan)

    # Count breached red lines
    red_lines_breached = posture['breached_count']

    result = {
        'success':            True,
        'posture_label':      posture['label'],
        'posture_color':      posture['color'],
        'bluf':               bluf,
        'signals':            signals,
        'generated_at':       datetime.now(timezone.utc).isoformat(),
        'from_cache':         False,
        # Analytical detail
        'peak_level':         posture['peak_level'],
        'cn_level':           posture['cn_level'],
        'tw_level':           posture['tw_level'],
        'deterrence_gap':     posture['deterrence_gap'],
        'kinetic_pressure':   posture['kinetic_pressure'],
        'red_lines_breached': red_lines_breached,
        'trackers_live':      trackers_live,
        'trackers_total':     trackers_total,
        'version':            '1.0.0-asia-bluf',
    }

    # Cache it
    _redis_set(BLUF_CACHE_KEY, result, ttl=BLUF_CACHE_TTL)
    print(f"[Asia BLUF] Synthesized: {posture['label']} "
          f"(peak L{posture['peak_level']}, {red_lines_breached} breached, "
          f"deterrence gap L{posture['deterrence_gap']})")

    return result


# ============================================================
# BACKGROUND REFRESH
# ============================================================
_refresh_running = False
_refresh_lock    = threading.Lock()


def _background_refresh_loop():
    """Sleep BOOT_DELAY, then synthesize every REFRESH_INTERVAL."""
    time.sleep(BOOT_DELAY)
    print(f"[Asia BLUF] Background refresh started (every {REFRESH_INTERVAL}s)")
    while True:
        try:
            synthesize_asia_bluf()
        except Exception as e:
            print(f"[Asia BLUF] Background refresh error: {e}")
        time.sleep(REFRESH_INTERVAL)


# ============================================================
# FLASK ENDPOINT REGISTRATION
# ============================================================
def register_asia_bluf_endpoint(app):
    """Register /api/rhetoric/asia/bluf on the given Flask app."""

    @app.route('/api/rhetoric/asia/bluf', methods=['GET'])
    def api_asia_rhetoric_bluf():
        """
        Asia-Pacific regional BLUF. Returns cached synthesis; regenerates
        if cache missing. Matches ME /api/rhetoric/me/bluf contract.
        """
        # Try cache first
        cached = _redis_get(BLUF_CACHE_KEY)
        if cached:
            cached['from_cache'] = True
            return jsonify(cached)

        # Cache miss -- synthesize on the fly
        try:
            result = synthesize_asia_bluf()
            if result is None:
                return jsonify({
                    'success': False,
                    'error':   'No tracker data available yet -- China and Taiwan caches empty',
                }), 404
            return jsonify(result)
        except Exception as e:
            print(f"[Asia BLUF] Synthesis error: {e}")
            return jsonify({'success': False, 'error': str(e)[:200]}), 500

    # Start background refresh thread
    bg = threading.Thread(target=_background_refresh_loop, daemon=True)
    bg.start()

    print("[Asia BLUF] Endpoint registered: /api/rhetoric/asia/bluf")
