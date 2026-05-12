"""
Asifah Analytics — ABSORPTION PROXY (Asia backend)
v1.0.0 — May 2026

PLACEMENT: Asia backend (asifah-asia-backend.onrender.com).
Mirrors the commodity_proxy_asia.py pattern: proxies absorption-detection
requests to the ME backend, which owns the detector + storage + static catalog.

ARCHITECTURE:
=============

  Asia backend                              ME backend
  ──────────────                            ──────────────
  rhetoric_tracker_india.py
        │
        ▼
  absorption_proxy_asia.py
   detect_and_persist_via_proxy(...)
        │   HTTPS POST
        ▼
                                  /api/absorption/detect
                                  (absorption_signatures.py)
                                        │
                                        ▼
                                  absorption_detector.py
                                        │
                                        ▼
                                  absorption_signatures.
                                  write_absorption_signature(...)

WHY HTTP PROXY (not local import):
==================================
The detector + storage + static catalog (the "so_what_short / so_what_long"
human-written analysis) all live on the ME backend by design. Other backends
(Asia, Europe, WHA) call into ME via HTTP so that:

  1. Rules are maintained in ONE place. When we add rules for Mexico, Egypt,
     Turkey, we edit one file on one backend. No multi-backend syncing.
  2. The static catalog (with its rich so_what text) is single-source-of-truth.
  3. Storage decisions (Redis writes, decay, TTL) all happen in one place.

The HTTP latency is ~150-300ms per call. Trackers call this at most once
per scan (every 6h). Trivial cost; large architectural payoff.

PUBLIC API:
===========

  detect_via_proxy(country, upstream_fingerprints, own_signals)
      → list of fired absorption results (no persistence)

  detect_and_persist_via_proxy(country, upstream_fingerprints, own_signals)
      → list of fired absorption results (persisted on ME backend)

  Both return [] if the ME backend is unreachable. Callers should treat
  emptiness as "no absorption fired this scan" rather than failing the
  whole scan.

ENDPOINTS REGISTERED ON ASIA BACKEND:
=====================================
  POST /api/asia/absorption/detect    — accepts the same body shape as the
                                        ME endpoint; useful for testing +
                                        for any other Asia-side caller (e.g.,
                                        future rhetoric_tracker_pakistan
                                        absorption rules)

CALL FROM app.py:
=================
    from absorption_proxy_asia import register_absorption_proxy
    register_absorption_proxy(app)

CALL FROM A TRACKER (e.g., rhetoric_tracker_india.py):
======================================================
    from absorption_proxy_asia import detect_and_persist_via_proxy

    upstream = {
        'iran':     {...},   # from ME shared dict via _read_upstream_fingerprints()
        'china':    {...},
        'pakistan': {...},
        'us':       {...},
    }
    own = {
        'modi_gold_jawboning':  True,
        'rbi_fx_defense':       False,
        'mea_us_friction_active': False,
        'armed_forces_lac_active': False,
        'kashmir_loc_active':   False,
        'commerce_tariff_response': False,
    }
    absorption_results = detect_and_persist_via_proxy('india', upstream, own)
    # Returns list of fired signatures (possibly empty).

CHANGELOG:
==========
  v1.0.0 (2026-05-12): Initial build — pattern mirrors commodity_proxy_asia.py.

COPYRIGHT 2025-2026 Asifah Analytics. All rights reserved.
"""

import os
import json
import requests
from datetime import datetime, timezone

# ────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────

# ME backend hosts the detector + static catalog + storage.
# Override with env var if needed for staging environments.
ME_BACKEND_URL = os.environ.get(
    'ME_BACKEND_URL',
    'https://asifah-backend.onrender.com'
)

# HTTP timeout for the detection round-trip. Render cold starts can be slow.
DETECT_TIMEOUT_SECONDS = 20


# ────────────────────────────────────────────────────────────
# PUBLIC API — called directly by Asia trackers
# ────────────────────────────────────────────────────────────

def detect_via_proxy(country, upstream_fingerprints=None, own_signals=None):
    """
    Send a detection request to the ME backend WITHOUT persisting results.
    Useful for dry runs, testing, or callers that want to inspect results
    before deciding whether to write them.

    Args:
        country: lowercase country slug ('india', etc.)
        upstream_fingerprints: dict mapping theater → fingerprint dict
        own_signals: dict of caller-provided signal flags

    Returns:
        list[dict] — fired absorption results. Empty list on failure or
        when no rules fire.
    """
    return _post_detect(country, upstream_fingerprints, own_signals, persist=False)


def detect_and_persist_via_proxy(country, upstream_fingerprints=None, own_signals=None):
    """
    Send a detection request to the ME backend AND persist any fired results.

    This is the normal entry point that rhetoric trackers call at the end of
    each scan. Persistence happens server-side (on ME) so the absorption
    signatures appear in the same Redis storage that the static catalog uses.

    Args:
        country: lowercase country slug ('india', etc.)
        upstream_fingerprints: dict mapping theater → fingerprint dict
        own_signals: dict of caller-provided signal flags

    Returns:
        list[dict] — fired absorption results, each with a 'persisted' bool.
        Empty list on failure or when no rules fire.
    """
    return _post_detect(country, upstream_fingerprints, own_signals, persist=True)


# ────────────────────────────────────────────────────────────
# INTERNAL HTTP TRANSPORT
# ────────────────────────────────────────────────────────────

def _post_detect(country, upstream_fingerprints, own_signals, persist):
    """Common POST logic for both public entry points."""
    if not country:
        print("[Absorption Proxy Asia] detect call missing 'country'")
        return []

    body = {
        'country':               (country or '').lower().strip(),
        'upstream_fingerprints': upstream_fingerprints or {},
        'own_signals':           own_signals or {},
        'persist':               bool(persist),
    }

    url = f"{ME_BACKEND_URL}/api/absorption/detect"

    try:
        resp = requests.post(
            url,
            json=body,
            timeout=DETECT_TIMEOUT_SECONDS,
            headers={'Content-Type': 'application/json'},
        )
    except requests.exceptions.Timeout:
        print(f"[Absorption Proxy Asia] Timeout calling ME detector for {country}")
        return []
    except Exception as e:
        print(f"[Absorption Proxy Asia] ME detector POST error for {country}: {e}")
        return []

    if resp.status_code != 200:
        print(f"[Absorption Proxy Asia] ME detector HTTP {resp.status_code} "
              f"for {country}: {resp.text[:200]}")
        return []

    try:
        data = resp.json()
    except Exception as e:
        print(f"[Absorption Proxy Asia] ME detector returned non-JSON: {e}")
        return []

    if not data.get('success'):
        print(f"[Absorption Proxy Asia] ME detector error for {country}: "
              f"{data.get('error', 'unknown')}")
        return []

    results = data.get('results') or []
    if results:
        print(f"[Absorption Proxy Asia] ✅ {len(results)} absorption result(s) "
              f"for {country}"
              f"{' (persisted)' if persist else ''}")
    return results


# ────────────────────────────────────────────────────────────
# FLASK ENDPOINTS — Asia-side passthrough + debug
# ────────────────────────────────────────────────────────────

def register_absorption_proxy(app):
    """
    Register absorption proxy endpoints on the Asia Flask app.
    Call from app.py:
        from absorption_proxy_asia import register_absorption_proxy
        register_absorption_proxy(app)
    """
    from flask import jsonify, request as flask_request

    @app.route('/api/asia/absorption/detect', methods=['POST', 'OPTIONS'])
    def api_asia_absorption_detect():
        """
        Asia-side passthrough to ME's /api/absorption/detect.
        Accepts the same JSON body shape as the ME endpoint. Useful for
        testing + for Asia-side callers other than the in-process trackers.
        """
        if flask_request.method == 'OPTIONS':
            return '', 200

        body = flask_request.get_json(silent=True) or {}
        country = (body.get('country') or '').lower().strip()
        if not country:
            return jsonify({
                'success': False,
                'error':   "Missing required field 'country' in request body.",
                'results': [],
            }), 400

        results = _post_detect(
            country=country,
            upstream_fingerprints=body.get('upstream_fingerprints'),
            own_signals=body.get('own_signals'),
            persist=bool(body.get('persist', False)),
        )

        return jsonify({
            'success':      True,
            'country':      country,
            'results':      results,
            'result_count': len(results),
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'proxy_layer':  'asia',
        })

    @app.route('/api/asia/absorption/debug', methods=['GET'])
    def api_asia_absorption_debug():
        """Diagnostic — confirms ME reachability + version."""
        from flask import jsonify
        debug = {
            'me_backend_url': ME_BACKEND_URL,
            'timeout_seconds': DETECT_TIMEOUT_SECONDS,
            'me_reachable': False,
            'me_endpoints': None,
        }
        try:
            r = requests.get(f"{ME_BACKEND_URL}/api/absorption-signatures",
                             timeout=5)
            debug['me_reachable'] = (r.status_code == 200)
            if r.status_code == 200:
                payload = r.json()
                debug['me_endpoints'] = {
                    'static_catalog_count': payload.get('count'),
                    'phase':                payload.get('phase'),
                }
        except Exception as e:
            debug['me_error'] = str(e)[:200]
        return jsonify(debug)

    print("[Absorption Proxy Asia] ✅ Endpoints registered:")
    print("  POST /api/asia/absorption/detect")
    print("  GET  /api/asia/absorption/debug")
