"""
afghanistan_humanitarian.py
Asifah Analytics -- WHA Backend Module
v1.0.0 -- July 2026

VENEZUELA HUMANITARIAN / DISASTER SENSOR (stability-page altitude).

DOCTRINE: This module is a SENSOR. It reports raw, sourced facts --
seismic events, disaster alerts, relief reporting, baseline figures --
with timestamps and attribution. It does NOT analyze. The ANALYST reads
live in rhetoric_tracker_afghanistan.py -- future build (L5 humanitarian gate + composite
disaster-strain component + top_signal emit) and in the interpreter.
Sensors below, analyst above. The reader completes the inference.

WHY THIS EXISTS (Jul 2026): back-to-back M7+ earthquakes hit Venezuela
in late June 2026. The worldwide humanitarian detector attributes
articles by COUNTRY-NAME matching, which is fragile for USGS place
strings ("25 km N of Carupano"). This module queries USGS by
BOUNDING BOX -- attribution by coordinates, not vocabulary.

DATA SOURCES
  1. USGS FDSN Event Query API -- authoritative seismic record,
     bounding-box filtered, last 30 days, M4.5+
     https://earthquake.usgs.gov/fdsnws/event/1/
  2. GDACS RSS -- multi-hazard alerts, filtered to Venezuela mentions
  3. ReliefWeb Reports API -- humanitarian reporting, country=Venezuela
  4. Static baseline dict -- pre-existing structural context, each entry
     carries source + source_url + data_as_of (data honesty standard)

REDIS
  humanitarian:afghanistan:latest   (TTL 14h -- outlasts the 12h refresh
                                   so the key never expires mid-cycle;
                                   cold-gap lesson, Jul 2026)
  lock:afghanistan_humanitarian     (SET NX EX cross-worker scheduler lock)

ENDPOINTS
  GET /api/afghanistan/humanitarian            (?force=true to rescan)
  GET /api/afghanistan/humanitarian/health

CONSUMERS
  - afghanistan-stability.html (raw dial rendering: seismic + refugee cards)
  - rhetoric_tracker_afghanistan.py (_read_disaster_sensor -> gate/composite/signal, when it ships)

Author: RCGG / Asifah Analytics
"""

import os
import json
import time
import threading
from datetime import datetime, timezone, timedelta

import requests

# ============================================================
# CONFIG
# ============================================================
# Redis env -- BOTH naming conventions (backends differ; Jul 2026 lesson)
UPSTASH_URL   = os.environ.get('UPSTASH_REDIS_REST_URL') or os.environ.get('UPSTASH_REDIS_URL', '')
UPSTASH_TOKEN = os.environ.get('UPSTASH_REDIS_REST_TOKEN') or os.environ.get('UPSTASH_REDIS_TOKEN', '')

CACHE_KEY          = 'humanitarian:afghanistan:latest'
LOCK_KEY           = 'lock:afghanistan_humanitarian'
REFRESH_HOURS      = 12
CACHE_TTL          = 14 * 3600     # 14h -- outlasts the 12h refresh interval
LOCK_TTL           = 20 * 60       # 20 min -- covers a slow scan
BOOT_DELAY_SECONDS = 75

# Venezuela bounding box (generous: covers Zulia to the Paria Peninsula
# and offshore Caribbean epicenters that shake the coast)
AF_BBOX = {
    'minlatitude':  29.0,
    'maxlatitude':  38.8,
    'minlongitude': 60.4,
    'maxlongitude': 75.0,
}
USGS_QUERY_URL = 'https://earthquake.usgs.gov/fdsnws/event/1/query'
USGS_MIN_MAG   = 4.5
USGS_WINDOW_D  = 30

GDACS_RSS_URL  = 'https://www.gdacs.org/xml/rss.xml'
GDACS_ALIASES  = ['afghanistan', 'kabul', 'herat', 'kandahar', 'jalalabad',
                  'kunduz', 'mazar-i-sharif', 'mazar i sharif', 'badakhshan',
                  'paktika', 'hindu kush', 'nangarhar', 'khost']

RELIEFWEB_URL  = 'https://api.reliefweb.int/v1/reports'

# Dynamic refugee/returns sources (Jul 2026). Both are attempted each sweep;
# whichever answers feeds refugee_state. Static baseline is the honest floor.
# NOTE: neither host is reachable from the build sandbox -- verify counts on
# first deploy via /api/afghanistan/humanitarian/health (same drill as USGS).
IOM_DTM_URL   = 'https://dtmapi.iom.int/api/idpAdmin0Data/GetAdmin0Datav2'
UNHCR_POP_URL = 'https://api.unhcr.org/population/v1/population/'

# Severity bands (peak-event driven; PAGER escalates)
#   catastrophic: M >= 7.0 OR PAGER red
#   major:        M >= 6.0 OR PAGER orange
#   minor:        M >= 5.0
#   none:         below
# Recency weight: 1.0 through day 7, linear decay to 0.0 at day 30.

STATIC_BASELINE = {
    'displacement_context': {
        'value':      'One of the world largest displacement crises: several million Afghans hosted in Iran and Pakistan, with mass deportations/returns since 2023 forcing reabsorption into a collapsed economy. Millions more internally displaced.',
        'source':     'UNHCR / IOM DTM composite reporting',
        'source_url': 'https://data.unhcr.org/en/situations/afghanistan',
        'data_as_of': '2025-12',
    },
    'aid_context': {
        'value':      'Aid architecture operating under severe constraint since Aug 2021: banking-sector isolation, frozen central-bank reserves (~$7B), donor pullbacks, and Taliban restrictions on female aid workers compressing delivery capacity.',
        'source':     'UN OCHA / World Bank Afghanistan monitors',
        'source_url': 'https://www.unocha.org/afghanistan',
        'data_as_of': '2025-12',
    },
    'seismic_context': {
        'value':      'Afghanistan sits on the Hindu Kush seismic zone, among the most active intermediate-depth earthquake regions on earth. Precedents: Herat sequence (Oct 2023, thousands killed), Paktika (Jun 2022). Rural mud-brick construction drives catastrophic fatality ratios at moderate magnitudes.',
        'source':     'USGS earthquake hazards program',
        'source_url': 'https://www.usgs.gov/programs/earthquake-hazards',
        'data_as_of': '2026-01',
    },
}
_refresh_thread = None


# ============================================================
# REDIS HELPERS
# ============================================================
def _redis_get(key):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return None
    try:
        resp = requests.get(f'{UPSTASH_URL}/get/{key}',
                            headers={'Authorization': f'Bearer {UPSTASH_TOKEN}'}, timeout=5)
        if resp.status_code != 200:
            return None
        result = resp.json().get('result')
        return json.loads(result) if result else None
    except Exception as e:
        print(f'[AFG Humanitarian] Redis GET error ({key}): {str(e)[:100]}')
        return None


def _redis_set(key, value, ttl=CACHE_TTL):
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return False
    try:
        resp = requests.post(f'{UPSTASH_URL}/set/{key}',
                             headers={'Authorization': f'Bearer {UPSTASH_TOKEN}',
                                      'Content-Type': 'application/json'},
                             data=json.dumps(value, default=str),
                             params={'EX': ttl}, timeout=5)
        return resp.json().get('result') == 'OK'
    except Exception as e:
        print(f'[AFG Humanitarian] Redis SET error ({key}): {str(e)[:100]}')
        return False


def _acquire_lock():
    """Cross-worker scheduler lock (SET NX EX). True = we own this cycle."""
    if not UPSTASH_URL or not UPSTASH_TOKEN:
        return True   # no Redis -> single-process fallback, just run
    try:
        resp = requests.get(f'{UPSTASH_URL}/set/{LOCK_KEY}/1',
                            headers={'Authorization': f'Bearer {UPSTASH_TOKEN}'},
                            params={'NX': 'true', 'EX': LOCK_TTL}, timeout=5)
        return resp.json().get('result') == 'OK'
    except Exception:
        return True


# ============================================================
# SOURCE FETCHERS
# ============================================================
def fetch_usgs_bbox():
    """Authoritative seismic record for the VZ bounding box, last 30d, M4.5+.
    Attribution by coordinates -- immune to place-string vocabulary."""
    events = []
    try:
        params = dict(AF_BBOX)
        params.update({
            'format':       'geojson',
            'starttime':    (datetime.now(timezone.utc) - timedelta(days=USGS_WINDOW_D)).strftime('%Y-%m-%d'),
            'minmagnitude': USGS_MIN_MAG,
            'orderby':      'magnitude',
            'limit':        50,
        })
        resp = requests.get(USGS_QUERY_URL, params=params, timeout=15)
        if resp.status_code != 200:
            print(f'[AFG Humanitarian] USGS query HTTP {resp.status_code}')
            return events
        for feat in (resp.json().get('features') or []):
            props = feat.get('properties') or {}
            geom  = (feat.get('geometry') or {}).get('coordinates') or [None, None, None]
            mag   = props.get('mag')
            t_ms  = props.get('time')
            if mag is None or t_ms is None:
                continue
            events.append({
                'ts':      datetime.fromtimestamp(t_ms / 1000.0, tz=timezone.utc).isoformat(),
                'mag':     round(float(mag), 1),
                'place':   props.get('place', ''),
                'depth_km': geom[2],
                'pager':   (props.get('alert') or '').lower(),   # green/yellow/orange/red or ''
                'tsunami': bool(props.get('tsunami')),
                'felt':    props.get('felt'),
                'url':     props.get('url', ''),
                'source':  'USGS/fdsn-bbox',
            })
        print(f'[AFG Humanitarian] USGS bbox: {len(events)} events M{USGS_MIN_MAG}+ in {USGS_WINDOW_D}d')
    except Exception as e:
        print(f'[AFG Humanitarian] USGS fetch failed: {type(e).__name__}: {str(e)[:120]}')
    return events


def fetch_gdacs_afg():
    """GDACS multi-hazard alerts mentioning Venezuela (title/description aliases)."""
    hits = []
    try:
        resp = requests.get(GDACS_RSS_URL, timeout=15)
        if resp.status_code != 200:
            return hits
        import re as _re
        items = _re.findall(r'<item>(.*?)</item>', resp.text, _re.DOTALL)
        for item in items[:120]:
            title = _re.search(r'<title>(.*?)</title>', item, _re.DOTALL)
            link  = _re.search(r'<link>(.*?)</link>', item, _re.DOTALL)
            desc  = _re.search(r'<description>(.*?)</description>', item, _re.DOTALL)
            blob  = ((title.group(1) if title else '') + ' ' + (desc.group(1) if desc else '')).lower()
            if any(a in blob for a in GDACS_ALIASES):
                hits.append({
                    'title':  (title.group(1).strip() if title else '')[:200],
                    'url':    (link.group(1).strip() if link else ''),
                    'source': 'GDACS',
                })
        print(f'[AFG Humanitarian] GDACS: {len(hits)} Venezuela-linked alerts')
    except Exception as e:
        print(f'[AFG Humanitarian] GDACS fetch failed: {type(e).__name__}: {str(e)[:120]}')
    return hits


def fetch_reliefweb_afg():
    """Latest ReliefWeb humanitarian reports for Venezuela (context feed)."""
    reports = []
    try:
        payload = {
            'appname': 'asifah-analytics',
            'limit':   10,
            'sort':    ['date:desc'],
            'filter':  {'field': 'country', 'value': 'Afghanistan'},
            'fields':  {'include': ['title', 'date.created', 'url', 'source.name']},
        }
        resp = requests.post(RELIEFWEB_URL, json=payload, timeout=15)
        if resp.status_code != 200:
            print(f'[AFG Humanitarian] ReliefWeb HTTP {resp.status_code}')
            return reports
        for item in (resp.json().get('data') or []):
            f = item.get('fields') or {}
            src = f.get('source') or []
            reports.append({
                'title':   (f.get('title') or '')[:200],
                'date':    ((f.get('date') or {}).get('created') or ''),
                'url':     f.get('url', ''),
                'source':  (src[0].get('name') if src and isinstance(src[0], dict) else 'ReliefWeb'),
            })
        print(f'[AFG Humanitarian] ReliefWeb: {len(reports)} reports')
    except Exception as e:
        print(f'[AFG Humanitarian] ReliefWeb fetch failed: {type(e).__name__}: {str(e)[:120]}')
    return reports


# ============================================================
# DISASTER STATE (raw computed facts -- the dial the analyst reads)
# ============================================================
def fetch_iom_dtm():
    """IOM DTM Admin0 figures for Afghanistan (IDP/returns). Defensive parse:
    the DTM API schema varies by round; we keep whatever numeric totals and
    round metadata we can identify, plus the raw first record for the card."""
    try:
        r = requests.get(IOM_DTM_URL,
                         params={'CountryName': 'Afghanistan'},
                         headers={'Accept': 'application/json'}, timeout=15)
        if r.status_code != 200:
            print(f'[AFG Humanitarian] IOM DTM HTTP {r.status_code}')
            return None
        body = r.json()
        rows = body.get('result') if isinstance(body, dict) else body
        if not isinstance(rows, list) or not rows:
            return None
        rows_sorted = rows[-5:]
        latest = rows_sorted[-1] if rows_sorted else {}
        def _num(d, *keys):
            for k in keys:
                v = d.get(k)
                if isinstance(v, (int, float)):
                    return v
            return None
        out = {
            'idp_total':      _num(latest, 'numPresentIdpInd', 'idpTotal', 'totalIdps', 'individuals'),
            'returnee_total': _num(latest, 'returneeInd', 'returneesTotal', 'totalReturnees'),
            'round':          latest.get('roundNumber') or latest.get('round'),
            'reporting_date': latest.get('reportingDate') or latest.get('date') or '',
            'source':         'IOM DTM (dtmapi.iom.int)',
        }
        if out['idp_total'] is None and out['returnee_total'] is None:
            print('[AFG Humanitarian] IOM DTM answered but no recognizable totals -- schema drift, send payload for a field-name fix')
            return None
        print(f"[AFG Humanitarian] IOM DTM: idp={out['idp_total']}, returnees={out['returnee_total']}, round={out['round']}")
        return out
    except Exception as e:
        print(f'[AFG Humanitarian] IOM DTM fetch failed: {type(e).__name__}: {str(e)[:120]}')
        return None


def fetch_unhcr_population():
    """UNHCR population API: refugees originating from Afghanistan (coo=AFG),
    latest year, top asylum countries. Well-documented public API."""
    try:
        r = requests.get(UNHCR_POP_URL,
                         params={'coo': 'AFG', 'limit': 200, 'yearFrom': 2023},
                         headers={'Accept': 'application/json'}, timeout=15)
        if r.status_code != 200:
            print(f'[AFG Humanitarian] UNHCR HTTP {r.status_code}')
            return None
        items = (r.json() or {}).get('items') or []
        if not items:
            return None
        latest_year = max(int(i.get('year', 0) or 0) for i in items)
        rows = [i for i in items if int(i.get('year', 0) or 0) == latest_year]
        def _ref(i):
            v = i.get('refugees')
            return v if isinstance(v, (int, float)) else 0
        total = sum(_ref(i) for i in rows)
        hosts = sorted(rows, key=_ref, reverse=True)[:5]
        out = {
            'year':          latest_year,
            'refugees_total': int(total),
            'top_hosts':     [{'country': (h.get('coa_name') or h.get('coa') or '?'),
                               'refugees': int(_ref(h))} for h in hosts if _ref(h) > 0],
            'source':        'UNHCR Refugee Population API',
        }
        print(f"[AFG Humanitarian] UNHCR: {out['refugees_total']:,} refugees ({latest_year}), {len(out['top_hosts'])} top hosts")
        return out
    except Exception as e:
        print(f'[AFG Humanitarian] UNHCR fetch failed: {type(e).__name__}: {str(e)[:120]}')
        return None


def compute_refugee_state(iom, unhcr):
    """Sensor dial for the stability page's IOM card. live=True when either
    dynamic source answered; static baseline is the rendering floor otherwise."""
    return {
        'live':        bool(iom or unhcr),
        'iom':         iom or {},
        'unhcr':       unhcr or {},
        'read_note':   'Displacement pressure is bidirectional: outflow hosting '
                       'pressure abroad AND forced-return reabsorption pressure '
                       'at home (Iran/Pakistan deportation waves since 2023).',
    }


def compute_disaster_state(usgs_events):
    """Sensor facts only: peak magnitude, counts, recency. The severity band
    and recency weight are DEFINED here (transparent thresholds); the meaning
    is assigned by the analyst layer."""
    state = {
        'active_disaster':        False,
        'severity_band':          'none',
        'event_count_30d':        0,
        'significant_count_30d':  0,     # M6.0+
        'peak_magnitude_30d':     None,
        'peak_event_place':       '',
        'peak_event_ts':          '',
        'peak_event_pager':       '',
        'most_recent_event_ts':   '',
        'days_since_peak_event':  None,
        'recency_weight':         0.0,
        'thresholds_note':        'catastrophic: M>=7.0 or PAGER red; major: M>=6.0 or PAGER orange; '
                                  'minor: M>=5.0. recency_weight 1.0 through day 7, linear to 0.0 at day 30.',
    }
    if not usgs_events:
        return state

    state['event_count_30d'] = len(usgs_events)
    state['significant_count_30d'] = sum(1 for e in usgs_events if (e.get('mag') or 0) >= 6.0)

    peak = max(usgs_events, key=lambda e: e.get('mag') or 0)
    state['peak_magnitude_30d'] = peak.get('mag')
    state['peak_event_place']   = peak.get('place', '')
    state['peak_event_ts']      = peak.get('ts', '')
    state['peak_event_pager']   = peak.get('pager', '')
    state['most_recent_event_ts'] = max(e.get('ts', '') for e in usgs_events)

    try:
        peak_dt = datetime.fromisoformat(state['peak_event_ts'])
        days = (datetime.now(timezone.utc) - peak_dt).total_seconds() / 86400.0
        state['days_since_peak_event'] = round(days, 1)
        if days <= 7:
            rw = 1.0
        elif days >= 30:
            rw = 0.0
        else:
            rw = (30.0 - days) / 23.0
        state['recency_weight'] = round(rw, 3)
    except Exception:
        state['days_since_peak_event'] = None
        state['recency_weight'] = 0.0

    mag   = state['peak_magnitude_30d'] or 0
    pager = state['peak_event_pager']
    if mag >= 7.0 or pager == 'red':
        state['severity_band'] = 'catastrophic'
    elif mag >= 6.0 or pager == 'orange':
        state['severity_band'] = 'major'
    elif mag >= 5.0:
        state['severity_band'] = 'minor'

    state['active_disaster'] = (state['severity_band'] in ('catastrophic', 'major')
                                and state['recency_weight'] > 0)
    return state


# ============================================================
# SCAN ORCHESTRATION
# ============================================================
def run_afghanistan_humanitarian(force=False):
    """Full sensor sweep. Cache-first unless forced."""
    if not force:
        cached = _redis_get(CACHE_KEY)
        if cached and cached.get('updated_at'):
            try:
                age = (datetime.now(timezone.utc) -
                       datetime.fromisoformat(cached['updated_at'])).total_seconds()
                if age < REFRESH_HOURS * 3600:
                    cached['from_cache'] = True
                    return cached
            except Exception:
                pass

    print('[AFG Humanitarian] === Sensor sweep starting ===')
    t0 = time.time()
    usgs      = fetch_usgs_bbox()
    gdacs     = fetch_gdacs_afg()
    reliefweb = fetch_reliefweb_afg()
    iom       = fetch_iom_dtm()
    unhcr     = fetch_unhcr_population()
    state     = compute_disaster_state(usgs)
    refugees  = compute_refugee_state(iom, unhcr)

    payload = {
        'theatre':          'afghanistan',
        'module':           'afghanistan_humanitarian',
        'version':          '1.0.0',
        'disaster_state':   state,
        'refugee_state':    refugees,
        'usgs_events':      usgs[:20],
        'gdacs_alerts':     gdacs[:10],
        'reliefweb_reports': reliefweb,
        'static_baseline':  STATIC_BASELINE,
        'sources_health': {
            'usgs_count':      len(usgs),
            'gdacs_count':     len(gdacs),
            'reliefweb_count': len(reliefweb),
            'iom_live':        bool(iom),
            'unhcr_live':      bool(unhcr),
        },
        'elapsed_sec':      round(time.time() - t0, 2),
        'updated_at':       datetime.now(timezone.utc).isoformat(),
        'from_cache':       False,
    }
    _redis_set(CACHE_KEY, payload, ttl=CACHE_TTL)
    print(f"[AFG Humanitarian] === Sweep complete in {payload['elapsed_sec']}s -- "
          f"band={state['severity_band']}, peak=M{state['peak_magnitude_30d']}, "
          f"events={state['event_count_30d']}, recency={state['recency_weight']} ===")
    return payload


# ============================================================
# BACKGROUND REFRESH (cross-worker locked)
# ============================================================
def _background_refresh_loop():
    print('[AFG Humanitarian] Background refresh thread started')
    time.sleep(BOOT_DELAY_SECONDS)
    while True:
        try:
            if _acquire_lock():
                run_afghanistan_humanitarian(force=True)
            else:
                print('[AFG Humanitarian] Another worker owns this cycle -- skipping')
        except Exception as e:
            print(f'[AFG Humanitarian] Background refresh error: {str(e)[:150]}')
        time.sleep(REFRESH_HOURS * 3600)


def _start_background_refresh():
    global _refresh_thread
    if _refresh_thread is None or not _refresh_thread.is_alive():
        _refresh_thread = threading.Thread(target=_background_refresh_loop, daemon=True)
        _refresh_thread.start()


# ============================================================
# FLASK ENDPOINT REGISTRATION
# ============================================================
def register_afghanistan_humanitarian_endpoints(app):
    from flask import jsonify, request as flask_request

    @app.route('/api/afghanistan/humanitarian', methods=['GET'])
    def api_afghanistan_humanitarian():
        force = flask_request.args.get('force', '').lower() in ('true', '1', 'yes')
        try:
            return jsonify(run_afghanistan_humanitarian(force=force))
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200], 'theatre': 'afghanistan'}), 500

    @app.route('/api/afghanistan/humanitarian/health', methods=['GET'])
    def api_afghanistan_humanitarian_health():
        cached = _redis_get(CACHE_KEY) or {}
        return jsonify({
            'module':           'afghanistan_humanitarian',
            'version':          '1.0.0',
            'redis_configured': bool(UPSTASH_URL and UPSTASH_TOKEN),
            'cached_at':        cached.get('updated_at', ''),
            'disaster_state':   cached.get('disaster_state', {}),
            'refugee_state':    cached.get('refugee_state', {}),
            'sources_health':   cached.get('sources_health', {}),
            'refresh_hours':    REFRESH_HOURS,
            'cache_ttl_hours':  CACHE_TTL / 3600,
        })

    _start_background_refresh()
    print('[AFG Humanitarian] Endpoints registered: /api/afghanistan/humanitarian (+/health)')
