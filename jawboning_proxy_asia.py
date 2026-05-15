"""
Asifah Analytics — JAWBONING PROXY (Asia backend)
v1.0.0 — May 15, 2026

PLACEMENT: Asia backend (asifah-asia-backend.onrender.com).
Mirrors the absorption_proxy_asia.py + commodity_proxy_asia.py pattern.

PURPOSE:
========
Forwards jawboning-detection requests from Asia-side trackers (currently
just rhetoric_tracker_india.py, but future Pakistan/Japan/etc. trackers
can use the same proxy) to the ME backend, which owns:
  • jawboning_signatures.py    — the catalog of 13 signatures
  • jawboning_detector.py      — the detection logic + fingerprint writes
  • Redis fingerprints         — jawboning:{direction}:{country}:{target}

ARCHITECTURE:
=============

  Asia backend                              ME backend
  ──────────────                            ──────────────
  rhetoric_tracker_india.py
        │  (calls detect_jawboning_via_proxy)
        ▼
  jawboning_proxy_asia.py
        │   HTTPS POST
        ▼
                                  /api/jawboning/detect
                                  (jawboning_detector.py)
                                        │
                                        ▼
                                  Apply catalog logic per signature
                                        │
                                        ▼
                                  Redis fingerprint writes
                                  (24h TTL, envelope payload)

WHY HTTP PROXY (not local import):
==================================
Same reason as absorption + commodity: ONE detector implementation, ONE
catalog source-of-truth, ONE place to add new signatures (Xi, MBS, Erdogan)
without multi-backend redeploys. Cross-theater consumers (Iran, China,
Cuba, Russia trackers) read fingerprints from Redis directly — they never
call the detector.

PUBLIC API:
===========

  detect_jawboning_via_proxy(leader_id, country_id, actor_results, ...)
      → dict {signature_id: bool, ...}    on success
      → {}                                on failure / unreachable ME

  Callers should treat empty dict as "no signatures fired this scan"
  rather than failing the whole scan. The detector is INFORMATIONAL — its
  output drives display + cross-theater amplification, but a tracker scan
  should complete successfully even if jawboning detection times out.

STRANGLER FIG NOTE (Phase 3 — May 15, 2026):
============================================
For the Modi-on-gold + Modi-on-austerity migration, rhetoric_tracker_india.py
calls this proxy in PARALLEL with its inline computation. The Phase 3
observation period compares the two outputs in Render logs across ≥3 scan
cycles. Only after consistent `[Jawboning Compare] ✅` lines do we cut over
to primitive-only.

ENDPOINTS REGISTERED ON ASIA BACKEND:
=====================================
  POST /api/asia/jawboning/detect       — direct passthrough for testing
  GET  /api/asia/jawboning/debug        — ME reachability diagnostic

CALL FROM app.py:
=================
    from jawboning_proxy_asia import register_jawboning_proxy
    register_jawboning_proxy(app)

CALL FROM A TRACKER (e.g., rhetoric_tracker_india.py):
======================================================
    from jawboning_proxy_asia import detect_jawboning_via_proxy

    primitive_results = detect_jawboning_via_proxy(
        leader_id='modi',
        country_id='india',
        actor_results=<the 7-actor dict from this scan>,
        scan_id=<some scan identifier for log correlation>,
    )
    # primitive_results = {'modi_on_gold': True, 'modi_on_austerity': False}
    # or {} on ME unreachable

CHANGELOG:
==========
  v1.0.0 (2026-05-15): Initial build. Mirrors absorption_proxy_asia.py
                       pattern. POST-only; ME endpoint accepts POST and GET
                       but proxies always POST (write-path discipline).

COPYRIGHT 2025-2026 Asifah Analytics. All rights reserved.
"""

import os
import json
import requests
from datetime import datetime, timezone


# ────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────

# ME backend hosts the detector + catalog + Redis writes.
# Override with env var if needed for staging.
ME_BACKEND_URL = os.environ.get(
    'ME_BACKEND_URL',
    'https://asifah-backend.onrender.com'
)

# HTTP timeout for the detection round-trip. Render cold starts can be slow.
DETECT_TIMEOUT_SECONDS = 20


# ────────────────────────────────────────────────────────────
# PUBLIC API — called directly by Asia trackers
# ────────────────────────────────────────────────────────────

def detect_jawboning_via_proxy(leader_id,
                               country_id,
                               actor_results,
                               articles=None,
                               write_fingerprints=True,
                               scan_id=None):
    """
    Send a jawboning-detection request to the ME backend.

    On success: returns the {signature_id: bool} dict the detector produced.
    On any failure: returns {} (empty dict). Callers should treat empty
    as "no signatures fired" rather than failing the scan.

    Args:
        leader_id: str — 'modi', 'trump', 'xi', etc.
        country_id: str — 'india', 'us', 'china', etc.
        actor_results: dict — per-actor scan output. Each cluster value should
                       contain 'level', 'matched_triggers', and 'top_articles'.
        articles: list — optional, currently unused by detector v1, reserved.
        write_fingerprints: bool — if True (default), ME writes Redis fingerprints
                            on positive detection. Set to False for dry-run
                            comparison logging (Phase 3 strangler-fig mode).
        scan_id: str — optional diagnostic identifier (correlates Asia scan
                 cycle with ME fingerprint writes in cross-backend logs).

    Returns:
        dict {signature_id: bool, ...} — possibly empty.
    """
    if not leader_id or not country_id:
        print("[Jawboning Proxy Asia] detect call missing leader_id or country_id")
        return {}

    body = {
        'leader_id':          leader_id,
        'country_id':         country_id,
        'actor_results':      actor_results or {},
        'articles':           articles or [],
        'write_fingerprints': bool(write_fingerprints),
    }
    if scan_id:
        body['scan_id'] = scan_id

    url = f"{ME_BACKEND_URL}/api/jawboning/detect"

    try:
        resp = requests.post(
            url,
            json=body,
            timeout=DETECT_TIMEOUT_SECONDS,
            headers={'Content-Type': 'application/json'},
        )
    except requests.exceptions.Timeout:
        print(f"[Jawboning Proxy Asia] Timeout calling ME detector for "
              f"{leader_id}/{country_id}")
        return {}
    except Exception as e:
        print(f"[Jawboning Proxy Asia] ME detector POST error for "
              f"{leader_id}/{country_id}: {e}")
        return {}

    if resp.status_code != 200:
        print(f"[Jawboning Proxy Asia] ME detector HTTP {resp.status_code} "
              f"for {leader_id}/{country_id}: {resp.text[:200]}")
        return {}

    try:
        data = resp.json()
    except Exception as e:
        print(f"[Jawboning Proxy Asia] ME detector returned non-JSON: {e}")
        return {}

    if not data.get('success'):
        print(f"[Jawboning Proxy Asia] ME detector error for "
              f"{leader_id}/{country_id}: {data.get('error', 'unknown')}")
        return {}

    results = data.get('results') or {}
    fired_count = data.get('fired_count', sum(1 for v in results.values() if v))
    if fired_count > 0:
        print(f"[Jawboning Proxy Asia] ✅ {fired_count} signature(s) fired "
              f"for {leader_id}/{country_id}"
              f"{' (wrote fingerprints)' if write_fingerprints else ' (dry-run)'}")
    return results


# ────────────────────────────────────────────────────────────
# FLASK ENDPOINTS — Asia-side passthrough + debug
# ────────────────────────────────────────────────────────────

def register_jawboning_proxy(app):
    """
    Register jawboning proxy endpoints on the Asia Flask app.
    Call from app.py:
        from jawboning_proxy_asia import register_jawboning_proxy
        register_jawboning_proxy(app)
    """
    from flask import jsonify, request as flask_request

    @app.route('/api/asia/jawboning/detect', methods=['POST', 'OPTIONS'])
    def api_asia_jawboning_detect():
        """
        Asia-side passthrough to ME's /api/jawboning/detect.
        Accepts the same JSON body shape. Useful for testing + for Asia-side
        callers other than the in-process trackers.
        """
        if flask_request.method == 'OPTIONS':
            return '', 200

        body = flask_request.get_json(silent=True) or {}
        leader_id  = body.get('leader_id')
        country_id = body.get('country_id')

        if not leader_id or not country_id:
            return jsonify({
                'success': False,
                'error':   "Missing required fields: leader_id, country_id",
                'results': {},
            }), 400

        results = detect_jawboning_via_proxy(
            leader_id=leader_id,
            country_id=country_id,
            actor_results=body.get('actor_results'),
            articles=body.get('articles'),
            write_fingerprints=bool(body.get('write_fingerprints', False)),
            scan_id=body.get('scan_id'),
        )

        return jsonify({
            'success':      True,
            'leader_id':    leader_id,
            'country_id':   country_id,
            'results':      results,
            'fired_count':  sum(1 for v in results.values() if v),
            'last_updated': datetime.now(timezone.utc).isoformat(),
            'proxy_layer':  'asia',
        })

    @app.route('/api/asia/jawboning/debug', methods=['GET'])
    def api_asia_jawboning_debug():
        """Diagnostic — confirms ME reachability + jawboning catalog count."""
        from flask import jsonify
        debug = {
            'me_backend_url':  ME_BACKEND_URL,
            'timeout_seconds': DETECT_TIMEOUT_SECONDS,
            'me_reachable':    False,
            'me_endpoints':    None,
        }
        try:
            r = requests.get(
                f"{ME_BACKEND_URL}/api/jawboning/signatures/count",
                timeout=5,
            )
            debug['me_reachable'] = (r.status_code == 200)
            if r.status_code == 200:
                payload = r.json()
                debug['me_endpoints'] = {
                    'catalog_count': payload.get('count'),
                    'success':       payload.get('success'),
                }
        except Exception as e:
            debug['me_error'] = str(e)[:200]
        return jsonify(debug)

    print("[Jawboning Proxy Asia] ✅ Endpoints registered:")
    print("  POST /api/asia/jawboning/detect")
    print("  GET  /api/asia/jawboning/debug")
