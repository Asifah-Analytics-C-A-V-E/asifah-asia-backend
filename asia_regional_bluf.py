"""
asia_regional_bluf.py
Asifah Analytics -- Asia Backend Module
v2.0.0 -- April 2026

Asia-Pacific Regional BLUF (Bottom Line Up Front) Engine.

Reads from China + Taiwan rhetoric tracker Redis caches and synthesizes
a single analyst-prose BLUF paragraph + structured top-line signals.

Architecture mirrors me_regional_bluf.py (which is proven-working).

v2.0.0 changes vs v1.x:
- Flask import moved INSIDE register function (matches ME pattern)
- Removed background refresh thread (ME pattern -- cache-first, on-demand)
- Cache check lives inside build_regional_bluf() (ME pattern)
- Redis SET uses /set/{key} path convention (matches ME)
- Renamed registration function to register_asia_bluf_routes(app)
- Kept defensive _safe_* helpers from v1.1.0 (harmless, good defense)
- Kept /bluf/debug endpoint for Redis cache inspection
- Kept full-traceback logging on synthesis failure

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
CHINA_CACHE_KEY   = 'rhetoric:china:latest'
TAIWAN_CACHE_KEY  = 'rhetoric:taiwan:latest'

# Our synthesis cache
BLUF_CACHE_KEY    = 'rhetoric:asia:regional_bluf'
BLUF_CACHE_TTL    = 14 * 3600    # 14h -- outlasts any individual tracker TTL


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
# TRACKER READERS
# ============================================================
def _read_all_trackers():
    """
    Read China + Taiwan caches. Returns dict of tracker_name -> data.
    Missing caches are simply omitted (graceful degradation).
    """
    trackers = {}
    china = _redis_get(CHINA_CACHE_KEY)
    if china:
        trackers['china'] = china
    taiwan = _redis_get(TAIWAN_CACHE_KEY)
    if taiwan:
        trackers['taiwan'] = taiwan
    return trackers


# ============================================================
# POSTURE DETERMINATION
# ============================================================
def _determine_regional_posture(china, taiwan):
    """
    Roll up posture across China + Taiwan.
    Taiwan's deterrence_gap is the critical extra signal unique to this region.
    """
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
    tw_level = _safe_int(tw.get('overall_level'))
    tw_def   = _safe_int(tw.get('defense_level'))
    tw_us    = _safe_int(tw.get('us_level'))
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
# SIGNALS ARRAY
# ============================================================
def _build_signals(posture, china, taiwan):
    """Build top signals array -- colored pills rendered on the hub page."""
    cn = _safe_dict(china)
    tw = _safe_dict(taiwan)
    cn_so_what = _safe_dict(cn.get('so_what'))
    tw_so_what = _safe_dict(tw.get('so_what'))
    cn_red_lines = _safe_list(cn.get('red_lines'))
    tw_red_lines = _safe_list(tw.get('red_lines'))

    signals = []

    # Red-line signals first (priority)
    for rl in cn_red_lines[:2]:
        rl = _safe_dict(rl)
        status = _safe_str(rl.get('status'))
        label  = _safe_str(rl.get('label'))
        if status == 'BREACHED':
            signals.append({'icon': '🔴', 'color': '#dc2626', 'text': f"CHINA BREACH: {label}"})
        elif status == 'APPROACHING':
            signals.append({'icon': '🟠', 'color': '#f97316', 'text': f"China approaching: {label}"})

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
            signals.append({'icon': '🟠', 'color': '#f97316', 'text': f"Taiwan approaching: {label}"})

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

    # Deterrence-gap signal (Taiwan-specific)
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

    # Mutual cross-strait escalation
    cn_level = _safe_int(cn.get('overall_level'))
    tw_level = _safe_int(tw.get('overall_level'))
    if cn_level >= 3 and tw_level >= 3:
        signals.append({
            'icon': '🌀', 'color': '#dc2626',
            'text': 'MUTUAL ESCALATION: both sides L3+ simultaneously -- coordination window compressed'
        })

    # Baseline fallback
    if not signals:
        signals.append({
            'icon': '🌏', 'color': '#6b7280',
            'text': 'All Asia-Pacific theaters at baseline -- monitoring for coercion escalation'
        })

    return signals[:6]


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

    print('[Asia BLUF] Building regional BLUF from China + Taiwan caches...')

    try:
        trackers = _read_all_trackers()

        if not trackers:
            return {
                'success': False,
                'error':   'No tracker data available',
                'bluf':    'BLUF unavailable -- no tracker caches loaded.',
                'signals': [],
                'posture_label': 'UNAVAILABLE',
                'posture_color': '#6b7280',
            }

        china  = trackers.get('china')
        taiwan = trackers.get('taiwan')

        posture = _determine_regional_posture(china, taiwan)
        bluf    = _build_bluf_prose(posture, china, taiwan)
        signals = _build_signals(posture, china, taiwan)

        trackers_live = len(trackers)

        result = {
            'success':            True,
            'from_cache':         False,
            'bluf':               bluf,
            'signals':            signals,
            'posture_label':      posture['label'],
            'posture_color':      posture['color'],
            'peak_level':         posture['peak_level'],
            'cn_level':           posture['cn_level'],
            'tw_level':           posture['tw_level'],
            'deterrence_gap':     posture['deterrence_gap'],
            'kinetic_pressure':   posture['kinetic_pressure'],
            'red_lines_breached': posture['breached_count'],
            'trackers_live':      trackers_live,
            'trackers_total':     2,
            'generated_at':       datetime.now(timezone.utc).isoformat(),
            'version':            '2.0.0-asia-bluf',
        }

        _redis_set(BLUF_CACHE_KEY, result)
        print(f"[Asia BLUF] Built: posture={posture['label']}, "
              f"peak_level=L{posture['peak_level']}, "
              f"breached={posture['breached_count']}, "
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
