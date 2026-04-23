"""
asia_regional_bluf.py
Asifah Analytics -- Asia Backend Module
v1.1.0 -- April 2026 (hardened)

Asia-Pacific Regional BLUF synthesizer.

Reads from China + Taiwan Redis caches (populated by their respective
rhetoric trackers) and produces a regional synthesis: posture, prose
BLUF, signals array, vector readouts.

Matches the ME /api/rhetoric/me/bluf response contract so that
rhetoric-asia.html can use the same fetch pattern as rhetoric-index.html.

v1.1.0 changes (hardened vs v1.0.0):
- Full traceback logging to Render logs for any crash
- NEW /api/rhetoric/asia/bluf/debug endpoint -- reveals cache contents
- Bullet-proof type handling (None/int/str/dict/list all safe)
- Redis SET pattern matches trackers (command-array format)
- Graceful single-tracker mode
- Safe-access helpers throughout

Author: RCGG / Asifah Analytics
"""

import os
import json
import time
import threading
import traceback
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
BLUF_CACHE_TTL    = 15 * 60     # 15 minutes

# Background refresh
REFRESH_INTERVAL  = 15 * 60     # 15 minutes
BOOT_DELAY        = 90          # seconds to wait for trackers on cold boot


# ============================================================
# SAFE-ACCESS HELPERS (bullet-proof type handling)
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
# REDIS HELPERS (REST) — matching trackers' patterns
# ============================================================
def _redis_get(key):
    """GET key from Upstash Redis REST. Returns parsed JSON dict or None."""
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        print("[Asia BLUF] WARNING: Redis creds missing from env")
        return None
    try:
        r = requests.get(
            f'{UPSTASH_REDIS_URL}/get/{key}',
            headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'},
            timeout=6,
        )
        if r.status_code != 200:
            print(f"[Asia BLUF] Redis GET {key} -> HTTP {r.status_code}")
            return None
        data = r.json().get('result')
        if not data:
            return None
        return json.loads(data)
    except Exception as e:
        print(f"[Asia BLUF] redis_get error for {key}: {e}")
        return None


def _redis_set(key, value, ttl=BLUF_CACHE_TTL):
    """
    SET key using tracker-compatible command-array pattern.
    This mirrors how rhetoric_tracker_china writes to Redis.
    """
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return False
    try:
        payload = json.dumps(value, default=str)
        requests.post(
            UPSTASH_REDIS_URL,
            headers={
                'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}',
                'Content-Type': 'application/json'
            },
            json=["SET", key, payload, "EX", str(ttl)],
            timeout=5,
        )
        return True
    except Exception as e:
        print(f"[Asia BLUF] redis_set error for {key}: {e}")
        return False


# ============================================================
# POSTURE DETERMINATION
# ============================================================
def _determine_regional_posture(china, taiwan):
    """Roll up posture across China + Taiwan."""
    china  = _safe_dict(china)
    taiwan = _safe_dict(taiwan)

    cn_level  = _safe_int(china.get('overall_level'))
    tw_level  = _safe_int(taiwan.get('overall_level'))
    max_level = max(cn_level, tw_level)

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
    """Generate regional prose paragraph. 2-4 sentences."""
    cn = _safe_dict(china)
    tw = _safe_dict(taiwan)
    cn_so_what = _safe_dict(cn.get('so_what'))
    tw_so_what = _safe_dict(tw.get('so_what'))

    date_str = datetime.now(timezone.utc).strftime('%b %d, %Y')
    parts = [f"Asia-Pacific Rhetoric Monitor ({date_str}):"]

    parts.append(
        f"Regional posture at {posture['label']} -- peak escalation L{posture['peak_level']} "
        f"across China + Taiwan trackers."
    )

    # China vector
    cn_level   = _safe_int(cn.get('overall_level'))
    cn_kinetic = _safe_int(cn_so_what.get('kinetic_pressure'))
    cn_econ    = _safe_int(cn_so_what.get('economic_pressure'))
    cn_pla     = _safe_int(cn.get('pla_level'))
    cn_xi      = _safe_int(cn.get('xi_level'))

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
    tw_level   = _safe_int(tw.get('overall_level'))
    tw_def     = _safe_int(tw.get('defense_level'))
    tw_us      = _safe_int(tw.get('us_level'))
    tw_gap     = _safe_int(tw_so_what.get('deterrence_gap'))
    tw_det     = _safe_int(tw_so_what.get('deterrence_strength'))

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
    """Build the bluf signals array -- short analytical blurbs with icon+color."""
    cn = _safe_dict(china)
    tw = _safe_dict(taiwan)
    cn_so_what = _safe_dict(cn.get('so_what'))
    tw_so_what = _safe_dict(tw.get('so_what'))
    cn_red_lines = _safe_list(cn.get('red_lines'))
    tw_red_lines = _safe_list(tw.get('red_lines'))

    signals = []

    # Red-line signals first
    for rl in cn_red_lines[:2]:
        rl = _safe_dict(rl)
        status = _safe_str(rl.get('status'))
        label  = _safe_str(rl.get('label'))
        if status == 'BREACHED':
            signals.append({
                'icon': '🔴', 'color': '#dc2626',
                'text': f"CHINA BREACH: {label}",
            })
        elif status == 'APPROACHING':
            signals.append({
                'icon': '🟠', 'color': '#f97316',
                'text': f"China approaching: {label}",
            })

    for rl in tw_red_lines[:2]:
        rl = _safe_dict(rl)
        status = _safe_str(rl.get('status'))
        label  = _safe_str(rl.get('label'))
        is_positive = _safe_str(rl.get('color')) == '#22c55e'
        if status == 'BREACHED':
            signals.append({
                'icon':  '🟢' if is_positive else '🔴',
                'color': '#22c55e' if is_positive else '#dc2626',
                'text':  f"TAIWAN {'DETERRENCE-POSITIVE' if is_positive else 'BREACH'}: {label}",
            })
        elif status == 'APPROACHING':
            signals.append({
                'icon': '🟠', 'color': '#f97316',
                'text': f"Taiwan approaching: {label}",
            })

    # Vector-based fallback signals
    if not signals:
        cn_kinetic = _safe_int(cn_so_what.get('kinetic_pressure'))
        cn_econ    = _safe_int(cn_so_what.get('economic_pressure'))
        cn_level   = _safe_int(cn.get('overall_level'))
        cn_pla     = _safe_int(cn.get('pla_level'))
        if cn_kinetic >= 3:
            signals.append({
                'icon': '⚔️', 'color': '#ef4444',
                'text': f"CHINA L{cn_level}: PLA operational L{cn_pla} -- cross-strait coercion active"
            })
        if cn_econ >= 3:
            signals.append({
                'icon': '💰', 'color': '#f97316',
                'text': f"CHINA: Economic coercion L{cn_econ} -- trade/investment pressure active"
            })

    # Deterrence gap signal
    tw_gap = _safe_int(tw_so_what.get('deterrence_gap'))
    if tw_gap >= 3:
        signals.append({
            'icon': '⚠️', 'color': '#dc2626',
            'text': f"DETERRENCE GAP L{tw_gap}: inbound pressure exceeding coalition response"
        })
    elif tw_gap >= 2:
        signals.append({
            'icon': '📉', 'color': '#f59e0b',
            'text': f"Deterrence gap L{tw_gap}: coalition signaling lagging inbound pressure"
        })

    # Coalition strength signal
    tw_us  = _safe_int(tw.get('us_level'))
    tw_def = _safe_int(tw.get('defense_level'))
    if tw_us >= 3 and tw_def >= 3 and not any('DETERRENCE' in _safe_str(s.get('text')) for s in signals):
        signals.append({
            'icon': '🤝', 'color': '#10b981',
            'text': f"COALITION STRONG: US L{tw_us}, Taiwan defense L{tw_def} -- deterrence coordinated"
        })

    # Mutual escalation
    cn_level = _safe_int(cn.get('overall_level'))
    tw_level = _safe_int(tw.get('overall_level'))
    if cn_level >= 3 and tw_level >= 3:
        signals.append({
            'icon': '🌀', 'color': '#dc2626',
            'text': f"MUTUAL ESCALATION: both sides L3+ simultaneously -- coordination window compressed"
        })

    # Baseline fallback
    if not signals:
        signals.append({
            'icon': '🌏', 'color': '#6b7280',
            'text': 'All Asia-Pacific theaters at baseline -- monitoring for coercion escalation'
        })

    return signals[:6]


# ============================================================
# BLUF SYNTHESIS
# ============================================================
def synthesize_asia_bluf():
    """
    Main synthesis. Reads China + Taiwan caches, produces BLUF dict.
    Returns None if both source caches are empty.
    Full traceback logged on any exception.
    """
    try:
        china  = _redis_get(CHINA_CACHE_KEY)
        taiwan = _redis_get(TAIWAN_CACHE_KEY)

        if not china and not taiwan:
            print("[Asia BLUF] Both source caches empty -- skipping synthesis")
            return None

        trackers_live = sum(1 for t in [china, taiwan] if t is not None)

        posture = _determine_regional_posture(china, taiwan)
        bluf    = _build_bluf_prose(posture, china, taiwan)
        signals = _build_signals(posture, china, taiwan)

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
            'red_lines_breached': posture['breached_count'],
            'trackers_live':      trackers_live,
            'trackers_total':     2,
            'version':            '1.1.0-asia-bluf',
        }

        _redis_set(BLUF_CACHE_KEY, result, ttl=BLUF_CACHE_TTL)
        print(f"[Asia BLUF] Synthesized: {posture['label']} "
              f"(peak L{posture['peak_level']}, {posture['breached_count']} breached, "
              f"deterrence gap L{posture['deterrence_gap']})")
        return result

    except Exception as e:
        # FULL TRACEBACK to Render logs -- the whole point of v1.1.0
        print(f"[Asia BLUF] SYNTHESIS EXCEPTION: {e}")
        print(f"[Asia BLUF] Traceback follows:")
        print(traceback.format_exc())
        raise  # Re-raise so endpoint handler returns 500 with the message


# ============================================================
# BACKGROUND REFRESH
# ============================================================
def _background_refresh_loop():
    """Sleep BOOT_DELAY, then synthesize every REFRESH_INTERVAL."""
    time.sleep(BOOT_DELAY)
    print(f"[Asia BLUF] Background refresh started (every {REFRESH_INTERVAL}s)")
    while True:
        try:
            synthesize_asia_bluf()
        except Exception as e:
            print(f"[Asia BLUF] Background refresh caught: {e}")
        time.sleep(REFRESH_INTERVAL)


# ============================================================
# FLASK ENDPOINT REGISTRATION
# ============================================================
def register_asia_bluf_endpoint(app):
    """Register /api/rhetoric/asia/bluf + debug endpoint on the given Flask app."""

    @app.route('/api/rhetoric/asia/bluf', methods=['GET'])
    def api_asia_rhetoric_bluf():
        """Asia-Pacific regional BLUF."""
        try:
            # Try cache first
            cached = _redis_get(BLUF_CACHE_KEY)
            if cached and isinstance(cached, dict):
                cached['from_cache'] = True
                return jsonify(cached)

            # Cache miss -- synthesize on the fly
            result = synthesize_asia_bluf()
            if result is None:
                return jsonify({
                    'success': False,
                    'error':   'No tracker data available yet -- China and Taiwan caches empty',
                }), 404
            return jsonify(result)
        except Exception as e:
            # Full traceback logged inside synthesize_asia_bluf already
            return jsonify({
                'success': False,
                'error':   f'{type(e).__name__}: {str(e)[:300]}',
            }), 500

    @app.route('/api/rhetoric/asia/bluf/debug', methods=['GET'])
    def api_asia_rhetoric_bluf_debug():
        """
        v1.1.0 debug endpoint -- reveals what's actually in Redis for each cache.
        Does NOT attempt synthesis. Safe to hit even when synthesis is crashing.
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
                'module_version':   '1.1.0-asia-bluf',
            })
        except Exception as e:
            return jsonify({
                'success':   False,
                'error':     f'{type(e).__name__}: {str(e)[:300]}',
                'traceback': traceback.format_exc()[:1500],
            }), 500

    # Start background refresh thread
    bg = threading.Thread(target=_background_refresh_loop, daemon=True)
    bg.start()

    print("[Asia BLUF] Endpoints registered: /api/rhetoric/asia/bluf + /bluf/debug")
