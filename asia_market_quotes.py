"""
asia_market_quotes.py
Asifah Analytics — Asia backend market quotes
v1.0.0 — July 26, 2026

Server-side quote fetcher for Asian indices and currencies.

────────────────────────────────────────────────────────────────────────────
WHY SERVER-SIDE (this is the whole reason the module exists)
────────────────────────────────────────────────────────────────────────────
An earlier build put this in page JavaScript and it failed on every load. Two
reasons, both fatal to a browser call and both absent server-side:

  1. CORS. Yahoo's finance endpoints send no Access-Control-Allow-Origin for
     arbitrary origins, so the browser blocks the response before the page
     ever sees it.
  2. User-Agent. Yahoo 429s datacenter and non-browser UAs. From a page you
     cannot set it; from Python you can, which is exactly what
     us_stability.py already does for the NYSE card.

Market closure is NOT a failure mode here: the v8 chart endpoint returns
historical daily closes, so a Sunday request answers with Friday's close.
A blank card means the FETCH failed, never that the market is shut.

────────────────────────────────────────────────────────────────────────────
WHY BOTH THE NIKKEI AND THE YEN
────────────────────────────────────────────────────────────────────────────
The Nikkei alone is misleading. A weak yen mechanically lifts the index --
exporter earnings translate up -- so "Nikkei rising" can mean genuine strength
OR currency debasement, and the index cannot distinguish them.

The yen is the richer instrument because it reads TWO WAYS:
    weak yen   -> import-cost inflation, BOJ credibility pressure, MOF
                  intervention risk. DOMESTIC stress.
    strong yen -> safe-haven inflows. A GLOBAL RISK-OFF read that says little
                  about Japan, and the carry-trade unwind mechanism that
                  transmitted yen strength into a worldwide equity cascade in
                  August 2024.

So the analytic output is the DIVERGENCE, computed here rather than left to
the page:
    Nikkei up + yen down  -> currency effect, not strength
    Nikkei up + yen up    -> aligned, the durable version
    Nikkei down + yen up  -> risk-off signature, usually IMPORTED

────────────────────────────────────────────────────────────────────────────
GENERALISES TO MARKET WATCH
────────────────────────────────────────────────────────────────────────────
INSTRUMENTS below is a plain registry. Adding HKEX (^HSI), KOSPI (^KS11),
Sensex (^BSESN) or a currency pair is a dict entry, not new code. The same
pattern serves the Market Watch expansion (TASE, HKEX, Tadawul, NSE, MOEX)
without forking this file.

CACHE: asia:market:japan  (6h TTL — quotes move, but not per page load)
ENDPOINTS:
  GET /api/asia/market/japan
  GET /api/asia/market/japan?force=true
  GET /debug/asia-market

COPYRIGHT (c) 2025-2026 Asifah Analytics. All rights reserved.
"""

import os
import json
import requests
from datetime import datetime, timezone
from flask import jsonify, request

__version__ = '1.0.0'

UPSTASH_REDIS_URL = (os.environ.get('UPSTASH_REDIS_URL')
                     or os.environ.get('UPSTASH_REDIS_REST_URL'))
UPSTASH_REDIS_TOKEN = (os.environ.get('UPSTASH_REDIS_TOKEN')
                       or os.environ.get('UPSTASH_REDIS_REST_TOKEN'))

CACHE_KEY = 'asia:market:japan'
CACHE_TTL = 6 * 3600
TIMEOUT   = 12

# Yahoo 429s non-browser UAs. us_stability.py learned this the hard way.
BROWSER_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')

# Registry. Adding an instrument is a dict entry, not new code.
INSTRUMENTS = [
    {
        'key': 'nikkei', 'name': 'Nikkei 225', 'symbol': '^N225',
        'icon': '\U0001F4C8', 'unit': 'JPY', 'decimals': 0,
        'note': ('Tokyo Stock Exchange headline index. Exporter-heavy, so a '
                 'weaker yen mechanically lifts it -- read alongside USD/JPY, '
                 'never alone.'),
    },
    {
        'key': 'yen', 'name': 'USD/JPY', 'symbol': 'JPY=X',
        'icon': '\U0001F4B4', 'unit': 'JPY per USD', 'decimals': 2,
        'note': ('A RISING number means a WEAKER yen. MOF/BOJ intervention has '
                 'historically clustered in the 152-160 band; sustained moves '
                 'through it are observable events, not forecasts.'),
    },
]


# ============================================================
# REDIS
# ============================================================
def _redis_get(key):
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return None
    try:
        r = requests.get(f"{UPSTASH_REDIS_URL}/get/{key}",
                         headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
                         timeout=6)
        if r.status_code != 200:
            return None
        raw = r.json().get('result')
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _redis_set(key, value, ttl=CACHE_TTL):
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return False
    try:
        r = requests.post(f"{UPSTASH_REDIS_URL}/setex/{key}/{ttl}",
                          headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
                          data=json.dumps(value), timeout=8)
        return r.status_code == 200
    except Exception:
        return False


# ============================================================
# YAHOO FETCH  (query1 -> query2 failover, same as us_stability.py)
# ============================================================
def _fetch_quote(symbol):
    """One instrument, 1-month daily. Returns None on failure -- never a zero.

    Yahoo load-balances query1/query2 and rate-limits per host, so when one
    429s the other usually answers.
    """
    from urllib.parse import quote as urlquote
    sym = urlquote(symbol, safe='')
    for host in ('query1', 'query2'):
        try:
            r = requests.get(
                f"https://{host}.finance.yahoo.com/v8/finance/chart/{sym}",
                params={'range': '1mo', 'interval': '1d'},
                headers={'User-Agent': BROWSER_UA}, timeout=TIMEOUT)
            if r.status_code != 200:
                print(f"[Asia Market] {symbol} via {host}: HTTP {r.status_code}")
                continue
            res = ((r.json().get('chart') or {}).get('result') or [None])[0]
            if not res:
                continue
            meta = res.get('meta') or {}
            quotes = ((res.get('indicators') or {}).get('quote') or [{}])[0]
            closes = [c for c in (quotes.get('close') or []) if isinstance(c, (int, float))]
            if not closes:
                continue
            last = meta.get('regularMarketPrice') or closes[-1]
            prev = meta.get('chartPreviousClose') or (closes[-2] if len(closes) > 1 else last)
            first = closes[0]
            return {
                'price': round(float(last), 4),
                'change_1d': round(float(last) - float(prev), 4),
                'change_pct_1d': round(((last - prev) / prev) * 100, 2) if prev else 0.0,
                'change_pct_30d': round(((last - first) / first) * 100, 2) if first else 0.0,
                'spark': [round(float(c), 4) for c in closes[-21:]],
                'point_count': len(closes),
                'source': f'Yahoo/{host}',
            }
        except Exception as e:
            print(f"[Asia Market] {symbol} via {host}: {str(e)[:90]}")
    return None


# ============================================================
# DIVERGENCE READ  -- computed here, not left to the page
# ============================================================
def _divergence(nikkei, yen):
    """The reason both instruments are fetched.

    Thresholds are +/-1% over 30 days: below that the move is noise and
    claiming a divergence would be reading a rounding error.
    """
    if not (nikkei and yen):
        return {
            'state': 'incomplete',
            'color': '#6b7280',
            'text': ('Divergence read needs BOTH instruments and is suppressed '
                     'rather than estimated -- a partial read here would be '
                     'worse than none, since either alone is ambiguous.'),
        }
    n30 = nikkei['change_pct_30d']
    y30 = yen['change_pct_30d']          # USD/JPY up == yen WEAKER
    n_up, n_dn = n30 > 1, n30 < -1
    y_weak, y_strong = y30 > 1, y30 < -1

    if n_up and y_weak:
        return {'state': 'divergent_currency_effect', 'color': '#f59e0b',
                'text': (f'DIVERGENCE -- the Nikkei is up {n30:.1f}% over 30 days while the '
                         f'yen has weakened {y30:.1f}%. Read the index gain as largely '
                         f'CURRENCY EFFECT rather than underlying strength: a weaker yen '
                         f'mechanically lifts exporter earnings. Note the domestic read is '
                         f'the opposite of the market read -- a weak yen raises import costs '
                         f'for an economy importing ~99% of its oil.')}
    if n_up and y_strong:
        return {'state': 'aligned_strength', 'color': '#22c55e',
                'text': (f'ALIGNED -- the Nikkei is up {n30:.1f}% AND the yen has strengthened '
                         f'{abs(y30):.1f}%. Equity gains alongside a firming currency are not '
                         f'a translation effect, which makes this the more durable version of '
                         f'a rally.')}
    if n_dn and y_strong:
        return {'state': 'risk_off', 'color': '#dc2626',
                'text': (f'RISK-OFF SIGNATURE -- the Nikkei is down {abs(n30):.1f}% while the '
                         f'yen has strengthened {abs(y30):.1f}%. That pairing is the classic '
                         f'safe-haven inflow pattern and is usually IMPORTED rather than '
                         f'domestic. It is also the carry-trade unwind mechanism that '
                         f'transmitted yen strength into a global equity cascade in August '
                         f'2024 -- worth reading against the GPI, not only this page.')}
    if n_dn and y_weak:
        return {'state': 'both_weakening', 'color': '#f97316',
                'text': (f'BOTH WEAKENING -- equities down {abs(n30):.1f}% and the yen down '
                         f'{y30:.1f}%. Currency weakness failing to support the index is the '
                         f'combination that reads as domestic rather than translational stress.')}
    return {'state': 'no_divergence', 'color': '#6b7280',
            'text': (f'No meaningful divergence this cycle -- Nikkei {n30:+.1f}% and USD/JPY '
                     f'{y30:+.1f}% over 30 days. The pairing is the signal here; either '
                     f'instrument alone would be ambiguous.')}


# ============================================================
# BUILD
# ============================================================
def build_japan_market(force=False):
    if not force:
        cached = _redis_get(CACHE_KEY)
        if cached:
            cached['from_cache'] = True
            return cached

    out = {}
    for inst in INSTRUMENTS:
        q = _fetch_quote(inst['symbol'])
        out[inst['key']] = None if q is None else dict(q, **{
            'name': inst['name'], 'icon': inst['icon'], 'unit': inst['unit'],
            'decimals': inst['decimals'], 'note': inst['note'],
            'symbol': inst['symbol'],
        })

    live = [k for k, v in out.items() if v]
    payload = {
        'success': bool(live),
        'country': 'japan',
        'instruments': out,
        'live_count': len(live),
        'divergence': _divergence(out.get('nikkei'), out.get('yen')),
        'prose': ('Japan\'s financial read requires both instruments. A weak yen flatters '
                  'the Nikkei through exporter earnings, so the index alone cannot separate '
                  'genuine strength from currency effect -- the divergence between them is '
                  'the actual signal.'),
        'note': ('Source: Yahoo Finance (^N225, JPY=X), 1-month daily, fetched server-side. '
                 'USD/JPY rising = yen weakening. Market data is context for the stability '
                 'read, not a stability score in itself.'),
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'module_version': __version__,
    }
    if live:
        _redis_set(CACHE_KEY, payload)
    else:
        print("[Asia Market] All instruments failed -- cache NOT written "
              "(absence-honest: a blank card is a fetch failure, not a quiet market)")
    return payload


# ============================================================
# FLASK
# ============================================================
def register_asia_market_endpoints(app):
    @app.route('/api/asia/market/japan', methods=['GET'])
    def asia_market_japan():
        force = request.args.get('force', '').lower() in ('true', '1', 'yes')
        try:
            return jsonify(build_japan_market(force=force))
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200]}), 500

    @app.route('/debug/asia-market', methods=['GET'])
    def debug_asia_market():
        cached = _redis_get(CACHE_KEY) or {}
        return jsonify({
            'module': f'asia_market_quotes v{__version__}',
            'redis_url_set': bool(UPSTASH_REDIS_URL),
            'instruments_registered': [i['key'] for i in INSTRUMENTS],
            'cache_present': bool(cached),
            'cached_live_count': cached.get('live_count'),
            'cached_divergence': (cached.get('divergence') or {}).get('state'),
            'updated_at': cached.get('updated_at'),
        })

    print(f"[Asia Market] \u2705 Routes registered: /api/asia/market/japan "
          f"(+/debug/asia-market)")
