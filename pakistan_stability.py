"""
========================================
PAKISTAN STABILITY TRACKER (v1.0.0 — April 2026)
========================================

Multi-vector internal stability scoring for Pakistan.

Pakistan stability vectors (6):
    1. Sectarian violence (anti-Christian, anti-Ahmadi, anti-Hindu, anti-Shia)
    2. Karachi crime / urban chaos
    3. Balochistan insurgency (BLA, BLF, CPEC site security)
    4. Economic crisis (IMF, reserves, rupee, inflation)
    5. Climate / disaster (floods, heat, glacial melt — 2022 precedent)
    6. Civil-military legitimacy (Imran/PTI, judicial-military, election)

Stability label scale:
    Resilient        (score 0-19)
    Stressed         (score 20-39)
    Fractured        (score 40-59)
    Crisis Mode      (score 60-79)
    Constitutional   (score 80+) — system-failure threshold

This is intentionally separate from the rhetoric tracker — rhetoric
tracks INTENT (what actors are signaling); stability tracks STATE
(what's actually happening on the ground / in institutions).

Some vectors are shared with rhetoric (e.g., Balochistan insurgency
appears in both — rhetoric tracks BLA threats; stability tracks
attack frequency / severity / CPEC site count). The stability tracker
should pull from the rhetoric scan's cross-theater fingerprint when
available rather than re-fetching all source articles.
"""

import os
import json
import time
import threading
import requests
from datetime import datetime, timezone
from flask import jsonify, request

# ============================================
# CONFIG
# ============================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN') or os.environ.get('UPSTASH_REDIS_REST_TOKEN')

STABILITY_CACHE_KEY  = 'stability:pakistan:latest'
STABILITY_CACHE_TTL  = 12 * 60 * 60  # 12 hours
RHETORIC_CACHE_KEY   = 'rhetoric:pakistan:latest'  # for cross-read

_stability_lock    = threading.Lock()
_stability_running = False


# ============================================
# REDIS HELPERS
# ============================================
def _redis_get(key):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        r = requests.get(
            f'{UPSTASH_REDIS_URL}/get/{key}',
            headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'},
            timeout=5,
        )
        if r.status_code == 200:
            data = r.json().get('result')
            if data:
                return json.loads(data)
    except Exception as e:
        print(f'[Pakistan Stability] Redis GET {key} error: {e}')
    return None


def _redis_set(key, value, ttl=STABILITY_CACHE_TTL):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return False
    try:
        r = requests.post(
            f'{UPSTASH_REDIS_URL}/set/{key}?EX={ttl}',
            headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'},
            data=json.dumps(value),
            timeout=5,
        )
        return r.status_code == 200
    except Exception as e:
        print(f'[Pakistan Stability] Redis SET {key} error: {e}')
        return False


# ============================================
# STABILITY VECTOR DEFINITIONS
# ============================================
# Each vector returns a 0-100 score.
# Final stability score = weighted average of vectors.
# Higher score = LESS stable (instability index).

STABILITY_VECTORS = {
    'sectarian_violence': {
        'name': 'Sectarian / Religious Violence',
        'weight': 1.2,   # higher weight — sectarian crises spread fast
        'description': (
            'Attacks on religious minorities (Christians, Ahmadis, Hindus, '
            'Shia Muslims), blasphemy law abuses, mob violence, '
            'TTP / ISIS-K targeting of Shia mosques.'
        ),
        'reference_keywords': [
            'church attack pakistan', 'christian killed pakistan',
            'ahmadi attack pakistan', 'hindu temple pakistan',
            'shia mosque pakistan', 'blasphemy mob pakistan',
            'sectarian violence pakistan', 'ttp shia attack',
            'iskp pakistan', 'isis-k pakistan',
            # Urdu
            'فرقہ وارانہ حملہ', 'مسجد حملہ',
        ],
    },
    'karachi_crime': {
        'name': 'Karachi Crime / Urban Chaos',
        'weight': 0.9,
        'description': (
            'Karachi-specific street crime, gang violence, target killings, '
            'kidnapping for ransom, MQM-political violence, Rangers operations.'
        ),
        'reference_keywords': [
            'karachi crime', 'karachi violence', 'karachi target killing',
            'karachi kidnapping', 'karachi gang', 'rangers karachi operation',
            'mqm violence', 'street crime karachi',
            'کراچی جرم', 'کراچی ٹارگٹ کلنگ',
        ],
    },
    'balochistan_insurgency': {
        'name': 'Balochistan Insurgency',
        'weight': 1.1,
        'description': (
            'BLA / BLF attack frequency, CPEC site security incidents, '
            'Gwadar tensions, Baloch missing-persons protests, '
            'Pakistani security operations in Balochistan.'
        ),
        'reference_keywords': [
            'balochistan attack', 'bla attack', 'blf attack',
            'cpec attack', 'gwadar attack', 'chinese workers killed',
            'baloch missing persons', 'balochistan protest',
            'pakistan army balochistan',
            'بلوچستان حملہ',
        ],
        # Cross-read from rhetoric tracker fingerprint
        'cross_read_field': 'balochistan_insurgency_level',
    },
    'economic_crisis': {
        'name': 'Economic Crisis / IMF',
        'weight': 1.3,   # highest weight — economic crisis underlies everything
        'description': (
            'IMF program status, foreign reserves level, rupee exchange rate, '
            'fuel/food inflation, energy crisis, sovereign default risk.'
        ),
        'reference_keywords': [
            'pakistan imf', 'pakistan reserves', 'rupee fall',
            'pakistan inflation', 'pakistan default',
            'pakistan fuel crisis', 'pakistan power crisis',
            'pakistan economic crisis',
        ],
        'cross_read_field': 'economic_stress_level',
    },
    'climate_disaster': {
        'name': 'Climate / Disaster Vulnerability',
        'weight': 0.8,
        'description': (
            'Flooding (2022 precedent: 33M displaced), heat wave deaths, '
            'glacial lake outburst floods, drought, monsoon failures, '
            'climate-induced internal displacement.'
        ),
        'reference_keywords': [
            'pakistan floods', 'pakistan heat wave', 'glof pakistan',
            'pakistan monsoon', 'pakistan drought',
            'pakistan climate', 'pakistan displaced',
        ],
    },
    'civil_military_legitimacy': {
        'name': 'Civil-Military Legitimacy',
        'weight': 1.1,
        'description': (
            'Imran Khan / PTI suppression, judicial-military clashes, '
            'election legitimacy disputes, post-2024 election aftermath, '
            'civil society / journalist crackdowns.'
        ),
        'reference_keywords': [
            'imran khan jail', 'pti suppression', 'pti banned',
            'pakistan election rigging', 'pakistan judicial crisis',
            'pakistan supreme court army',
            'journalist killed pakistan', 'civil society pakistan',
        ],
        'cross_read_field': 'civil_military_friction_level',
    },
}


# ============================================
# STABILITY LABEL THRESHOLDS
# ============================================
def stability_label(score):
    """Return (label, color) tuple for a given instability score."""
    if score >= 80:
        return ('Constitutional Crisis', '#7f1d1d')
    elif score >= 60:
        return ('Crisis Mode', '#dc2626')
    elif score >= 40:
        return ('Fractured', '#f97316')
    elif score >= 20:
        return ('Stressed', '#f59e0b')
    else:
        return ('Resilient', '#16a34a')


# ============================================
# MAIN SCAN FUNCTION (skeleton)
# ============================================
def run_pakistan_stability_scan():
    """
    Run Pakistan stability scan.

    Strategy:
      1. Cross-read the rhetoric scan from Redis (no double-fetch)
      2. For vectors not in rhetoric (sectarian, Karachi, climate), fetch
         fresh from sources (TODO — implement using existing patterns)
      3. Compute per-vector 0-100 scores
      4. Compute weighted-average instability score
      5. Cache and return

    NOTE (v1.0): Architectural skeleton. Vector scoring is currently
    placeholder logic (cross-read where available, zero elsewhere). Full
    article-fetch + scoring should match china_stability.py / etc.
    """
    print("[Pakistan Stability] Starting scan...")
    scan_start = time.time()

    # ── 1. Cross-read rhetoric tracker for shared vectors ──
    rhetoric = _redis_get(RHETORIC_CACHE_KEY) or {}

    # ── 2. Compute per-vector scores ──
    vector_scores = {}
    for vec_id, vec_def in STABILITY_VECTORS.items():
        cross_field = vec_def.get('cross_read_field')
        if cross_field and rhetoric.get(cross_field) is not None:
            # Translate rhetoric level (0-5) to stability score (0-100)
            level = int(rhetoric.get(cross_field, 0) or 0)
            score = level * 20   # L0=0, L5=100
        else:
            # TODO: implement direct article fetch / scoring for vectors
            # not covered by the rhetoric tracker (sectarian, karachi,
            # climate). For now, placeholder zero.
            score = 0

        vector_scores[vec_id] = {
            'name':   vec_def['name'],
            'score':  score,
            'weight': vec_def['weight'],
            'top_articles': [],   # TODO: fill from source fetch
        }

    # ── 3. Compute weighted-average instability score ──
    total_weighted = sum(v['score'] * v['weight'] for v in vector_scores.values())
    total_weight   = sum(v['weight'] for v in vector_scores.values())
    composite_score = round(total_weighted / total_weight, 1) if total_weight else 0

    label, color = stability_label(composite_score)

    # ── 4. Build result ──
    result = {
        'success':              True,
        'generated_at':         datetime.now(timezone.utc).isoformat(),
        'country':              'pakistan',
        'composite_score':      composite_score,
        'composite_label':      label,
        'composite_color':      color,
        'vectors':              vector_scores,
        # Cross-fingerprint useful flags
        'rhetoric_theatre_level': rhetoric.get('theatre_level', 0),
        'pakistan_iran_active':   rhetoric.get('pakistan_iran_active', False),
        'pakistan_china_active':  rhetoric.get('pakistan_china_active', False),
        'pakistan_india_active':  rhetoric.get('pakistan_india_active', False),
        'pakistan_mediating_iran_us': rhetoric.get('pakistan_mediating_iran_us', False),
    }

    # ── 5. Cache + return ──
    _redis_set(STABILITY_CACHE_KEY, result, ttl=STABILITY_CACHE_TTL)

    elapsed = time.time() - scan_start
    print(f"[Pakistan Stability] ✅ Scan complete in {elapsed:.1f}s "
          f"(score {composite_score}, {label})")

    return result


# ============================================
# FLASK ENDPOINT REGISTRATION
# ============================================
def register_pakistan_stability_endpoints(app):
    """Register Pakistan stability endpoints on the Flask app."""

    @app.route('/api/stability/pakistan', methods=['GET'])
    def api_pakistan_stability():
        force = request.args.get('force', 'false').lower() == 'true'
        if not force:
            cached = _redis_get(STABILITY_CACHE_KEY)
            if cached:
                cached['from_cache'] = True
                return jsonify(cached)

        with _stability_lock:
            global _stability_running
            if _stability_running:
                cached = _redis_get(STABILITY_CACHE_KEY)
                if cached:
                    cached['from_cache']        = True
                    cached['scan_in_progress']  = True
                    return jsonify(cached)
                return jsonify({'success': False, 'error': 'Scan in progress'}), 202
            _stability_running = True

        try:
            result = run_pakistan_stability_scan()
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200]}), 500
        finally:
            with _stability_lock:
                _stability_running = False


# ============================================
# STANDALONE TEST
# ============================================
if __name__ == '__main__':
    print("=" * 60)
    print("PAKISTAN STABILITY TRACKER — STANDALONE TEST")
    print("=" * 60)
    result = run_pakistan_stability_scan()
    print(f"\n  Composite score:  {result['composite_score']}/100")
    print(f"  Composite label:  {result['composite_label']}")
    print(f"\n  Per-vector scores:")
    for vec_id, vec in result['vectors'].items():
        print(f"    {vec['name']:42} {vec['score']:>5} (weight {vec['weight']})")
