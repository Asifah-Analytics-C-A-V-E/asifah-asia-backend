"""
═══════════════════════════════════════════════════════════════════════
  ASIFAH ANALYTICS — ASIA BACKEND CONVERGENCE PROXY
  v1.0.0 (May 7 2026)
═══════════════════════════════════════════════════════════════════════

Thin proxy layer that fetches convergence-narrative data from the ME
backend (where convergence_registry.py lives), caches it in Asia's
Upstash Redis with a 12-hour TTL, and exposes Asia-native endpoints
for stability page + Asia BLUF consumption.

Mirrors the architecture of commodity_proxy_europe.py exactly.

ARCHITECTURE:
  Frontend (japan-stability.html, china-stability.html, taiwan-stability.html, rhetoric-asia.html)
    └─→ Asia backend /api/asia/convergence/<id>
          └─→ Asia Redis cache (12hr TTL)
                └─[on miss]─→ ME backend /api/convergence/<id>
                                └─→ Asia Redis (write-through)

WHY 12 HOURS:
  - Convergence narratives are structural — they describe compound risks
    that emerge when otherwise-independent signals fire simultaneously.
  - Underlying signal counts inside the convergence body update slowly
    enough that 12h freshness is fine for stability-page context.
  - Reduces ME backend load.

CONVERGENCES SUPPORTED:
  Whatever ME backend's CONVERGENCE_REGISTRY has registered.
  Phase 1 (May 2026):
    - wheat_lebanon (ME → Lebanon stability)
    - pla_pressure_japan_response (ME → Asia BLUF)
    - taiwan_alliance_convergence (ME → Asia BLUF)
    - hormuz_china_oil_dependency (ME → China stability + Asia BLUF)

  When ME backend extends the registry, this proxy automatically
  supports the new convergences (no Asia code change required).

ENDPOINTS REGISTERED:
  GET /api/asia/convergence/<id>             — single convergence, cached
  GET /api/asia/convergence/<id>?force=true  — bypass Asia cache
  GET /api/asia/convergence-all              — all registered convergences
  GET /api/asia/convergence-debug            — proxy status diagnostic

USAGE FROM app.py:
    from convergence_proxy_asia import register_convergence_proxy
    register_convergence_proxy(app)

CONSUMERS (Asia backend):
  - asia_regional_bluf.py — surface Asia convergences in regional BLUF prose
  - Frontend stability pages (japan/china/taiwan) — show convergence cards
  - global_pressure_index.py (when GPI integrates Asia-side convergences)
"""

import os
import json
import time
import threading
import requests
from datetime import datetime, timezone
from flask import jsonify, request

# ────────────────────────────────────────────────────────────
# CONFIGURATION
# ────────────────────────────────────────────────────────────

UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN')

# ME backend lives at this address (per project memory).
# Override with env var if needed for staging environments.
ME_BACKEND_URL = os.environ.get(
    'ME_BACKEND_URL',
    'https://asifah-backend.onrender.com'
)

# 12-hour TTL per project requirement (convergence narratives are structural).
CONVERGENCE_CACHE_TTL_SECONDS = 12 * 3600

# Per-convergence Redis key namespace.
def _redis_key(conv_id):
    return f"asia:convergence:{conv_id.lower()}"


def _redis_key_all():
    return "asia:convergence:all"


# ────────────────────────────────────────────────────────────
# REDIS CACHE HELPERS
# ────────────────────────────────────────────────────────────

def _load_from_redis(redis_key):
    """Load cached convergence data from Upstash Redis."""
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return None
    try:
        resp = requests.get(
            f"{UPSTASH_REDIS_URL}/get/{redis_key}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            timeout=5
        )
        data = resp.json()
        if data.get("result"):
            return json.loads(data["result"])
    except Exception as e:
        print(f"[Convergence Proxy] Redis load error for {redis_key}: {e}")
    return None


def _save_to_redis(redis_key, payload, ttl=CONVERGENCE_CACHE_TTL_SECONDS):
    """Save convergence data to Upstash Redis with TTL."""
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return False
    try:
        resp = requests.post(
            f"{UPSTASH_REDIS_URL}/setex/{redis_key}/{ttl}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            data=json.dumps(payload),
            timeout=8
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"[Convergence Proxy] Redis save error for {redis_key}: {e}")
        return False


# ────────────────────────────────────────────────────────────
# UPSTREAM FETCHERS
# ────────────────────────────────────────────────────────────

def _fetch_from_me_backend(conv_id):
    """Fetch single convergence from ME backend."""
    url = f"{ME_BACKEND_URL}/api/convergence/{conv_id}"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        print(f"[Convergence Proxy] ME backend HTTP {resp.status_code} for {conv_id}")
    except requests.exceptions.Timeout:
        print(f"[Convergence Proxy] ME backend timeout for {conv_id}")
    except Exception as e:
        print(f"[Convergence Proxy] ME backend error for {conv_id}: {e}")
    return None


def _fetch_all_from_me_backend():
    """Fetch full convergence registry from ME backend."""
    url = f"{ME_BACKEND_URL}/api/convergence/all"
    try:
        resp = requests.get(url, timeout=12)
        if resp.status_code == 200:
            return resp.json()
        print(f"[Convergence Proxy] ME backend /all HTTP {resp.status_code}")
    except requests.exceptions.Timeout:
        print(f"[Convergence Proxy] ME backend /all timeout")
    except Exception as e:
        print(f"[Convergence Proxy] ME backend /all error: {e}")
    return None


# ────────────────────────────────────────────────────────────
# PUBLIC HELPERS (for use by asia_regional_bluf.py et al.)
# ────────────────────────────────────────────────────────────

def get_convergence(conv_id, force=False):
    """
    Get a single convergence narrative (cached or fresh).
    Returns the convergence dict, or None on full miss.

    This is the primary helper that asia_regional_bluf.py should use.
    """
    if not force:
        cached = _load_from_redis(_redis_key(conv_id))
        if cached:
            return cached

    fresh = _fetch_from_me_backend(conv_id)
    if fresh:
        # Tag with proxy metadata
        fresh['_proxy_cached_at'] = datetime.now(timezone.utc).isoformat()
        fresh['_proxy_source']    = 'me_backend'
        _save_to_redis(_redis_key(conv_id), fresh)
        return fresh
    return None


def get_all_convergences(force=False):
    """
    Get all registered convergences. Returns dict of {conv_id: data}.
    """
    if not force:
        cached = _load_from_redis(_redis_key_all())
        if cached:
            return cached

    fresh = _fetch_all_from_me_backend()
    if fresh:
        fresh['_proxy_cached_at'] = datetime.now(timezone.utc).isoformat()
        fresh['_proxy_source']    = 'me_backend'
        _save_to_redis(_redis_key_all(), fresh)
        return fresh
    return None


def find_convergences_for_country_proxy(country):
    """
    Convenience helper for stability pages.
    Returns list of convergence dicts that match the given country.

    Usage from BLUF/frontend:
      convergences = find_convergences_for_country_proxy('japan')
      → returns Japan-relevant convergences (e.g. taiwan_alliance, pla_pressure_japan)
    """
    all_data = get_all_convergences()
    if not all_data:
        return []

    registry = all_data.get('registry', []) or all_data.get('convergences', [])
    if not isinstance(registry, list):
        return []

    matches = [
        entry for entry in registry
        if entry.get('country') == country.lower()
        or country.lower() in (entry.get('regions') or [])
    ]
    return matches


# ────────────────────────────────────────────────────────────
# FLASK ENDPOINT REGISTRATION
# ────────────────────────────────────────────────────────────

def register_convergence_proxy(app):
    """
    Register all convergence proxy endpoints on the Flask app.
    Call this from app.py during boot:
        from convergence_proxy_asia import register_convergence_proxy
        register_convergence_proxy(app)
    """

    @app.route('/api/asia/convergence/<conv_id>', methods=['GET'])
    def asia_convergence_single(conv_id):
        force = request.args.get('force', '').lower() in ('true', '1', 'yes')
        try:
            data = get_convergence(conv_id, force=force)
            if data is None:
                return jsonify({
                    'success': False,
                    'error':   f'Convergence "{conv_id}" not found or upstream unavailable',
                    'id':      conv_id,
                }), 404
            return jsonify(data)
        except Exception as e:
            print(f"[Convergence Proxy] Endpoint error for {conv_id}: {e}")
            return jsonify({'success': False, 'error': str(e)[:200]}), 500

    @app.route('/api/asia/convergence-all', methods=['GET'])
    def asia_convergence_all():
        force = request.args.get('force', '').lower() in ('true', '1', 'yes')
        try:
            data = get_all_convergences(force=force)
            if data is None:
                return jsonify({
                    'success': False,
                    'error':   'Upstream registry unavailable',
                    'registry': [],
                }), 503
            return jsonify(data)
        except Exception as e:
            print(f"[Convergence Proxy] /all endpoint error: {e}")
            return jsonify({'success': False, 'error': str(e)[:200]}), 500

    @app.route('/api/asia/convergence-debug', methods=['GET'])
    def asia_convergence_debug():
        """Diagnostic endpoint for the proxy itself."""
        return jsonify({
            'me_backend_url':       ME_BACKEND_URL,
            'cache_ttl_hours':      CONVERGENCE_CACHE_TTL_SECONDS / 3600,
            'redis_configured':     bool(UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN),
            'cached_keys_pattern':  'asia:convergence:*',
            'version':              '1.0.0',
            'endpoints':            [
                '/api/asia/convergence/<id>',
                '/api/asia/convergence-all',
                '/api/asia/convergence-debug',
            ],
        })

    print("[Convergence Proxy] ✅ Asia convergence proxy registered "
          "(/api/asia/convergence/<id>, /convergence-all, /convergence-debug)")
