"""
asia_market_quotes.py
Asifah Analytics — Asia backend market quotes
v1.1.0 — November 2, 2026   (v1.0.0 July 26, 2026)

v1.1.0 (Nov 2 2026):
  * Multi-country. COUNTRIES registry: japan (unchanged) + philippines
    (PSEi PSEI.PS, USD/PHP PHP=X, Brent BZ=F).
  * Every country payload now ALSO carries `financial_pulse` in the canonical
    Financial Pulse Card shape (tiles + market_status) used by China, Saudi,
    Qatar, UAE, Nigeria, Mexico -- so Market Watch and stability pages read
    one shape. `instruments` is kept unchanged for the Japan page.
  * market_status is recomputed at RESPONSE time, not cached: a 6h-old cache
    used to freeze the pill (Market Watch simply hard-coded Japan 'closed').
  * Polarity-aware tiers: a RISING USD/PHP or Brent is stress for an importer.
  * Sparkline points carry dates ({time, value}) like the China card.

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

CACHE: asia:market:<country>  (6h TTL — quotes move, but not per page load)
ENDPOINTS:
  GET /api/asia/market/<country>              japan | philippines
  GET /api/asia/market/<country>?force=true   refetch from Yahoo (free, no key)
  GET /debug/asia-market

COPYRIGHT (c) 2025-2026 Asifah Analytics. All rights reserved.
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta
from flask import jsonify, request

__version__ = '1.1.0'

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
            raw_close = quotes.get('close') or []
            stamps = res.get('timestamp') or []
            points = [{'time': datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat(),
                       'value': round(float(c), 4)}
                      for ts, c in zip(stamps, raw_close) if isinstance(c, (int, float))]
            closes = [c for c in raw_close if isinstance(c, (int, float))]
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
                'spark_points': points[-21:],
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
# COUNTRIES (v1.1.0) -- adding a market is a registry entry
# ============================================================
PH_INSTRUMENTS = [
    {
        'key': 'psei', 'name': 'PSEi', 'symbol': 'PSEI.PS', 'tile': 'PSEI',
        'icon': '\U0001F4C8', 'unit': 'PHP', 'decimals': 0, 'polarity': 'standard',
        'band': 1.0, 'session': 'pse',
        'note': ('Philippine Stock Exchange index, 30 blue chips (banks, property, '
                 'conglomerates, telecoms).'),
    },
    {
        'key': 'peso', 'name': 'USD / PHP', 'symbol': 'PHP=X', 'tile': 'USD_PHP',
        'icon': '\U0001F4B1', 'unit': 'PHP per USD', 'decimals': 2, 'polarity': 'inverted',
        'band': 0.5, 'session': 'fx',
        'note': ('A RISING number means a WEAKER peso. Record lows near 59 per dollar '
                 '(2022, 2024) drew central bank (BSP) intervention.'),
    },
    {
        'key': 'brent', 'name': 'Brent Crude', 'symbol': 'BZ=F', 'tile': 'BRENT',
        'icon': '\U0001F6E2\uFE0F', 'unit': 'USD/bbl', 'decimals': 2, 'polarity': 'inverted',
        'band': 1.0, 'session': 'fx',
        'note': 'Global oil benchmark. The Philippines imports nearly all of its oil.',
    },
]

# Japan keeps its v1.0 instruments and keys; tile ids/polarity added for the pulse.
for _inst in INSTRUMENTS:
    _inst.setdefault('tile', {'nikkei': 'NIKKEI', 'yen': 'USD_JPY'}.get(_inst['key'], _inst['key'].upper()))
    _inst.setdefault('polarity', 'inverted' if _inst['key'] == 'yen' else 'standard')
    _inst.setdefault('band', 0.5 if _inst['key'] == 'yen' else 1.0)
    _inst.setdefault('session', 'fx' if _inst['key'] == 'yen' else 'tse')

COUNTRIES = {
    'japan': {
        'instruments': INSTRUMENTS, 'cache_key': CACHE_KEY, 'code': 'JP',
        'card_label': 'Japan Financial Pulse',
        'source_note': ('Source: Yahoo Finance (^N225, JPY=X), 1-month daily, fetched server-side. '
                        'USD/JPY rising = yen weakening. Market data is context for the stability '
                        'read, not a stability score in itself.'),
    },
    'philippines': {
        'instruments': PH_INSTRUMENTS, 'cache_key': 'asia:market:philippines', 'code': 'PH',
        'card_label': 'Philippines Financial Pulse',
        'source_note': ('Source: Yahoo Finance (PSEI.PS, PHP=X, BZ=F), 1-month daily, fetched '
                        'server-side. USD/PHP rising = peso weakening. PSE session times are '
                        'approximate and do not account for Philippine holidays.'),
    },
}


# ============================================================
# MARKET STATUS -- computed at response time
# ============================================================
def _session_status(session, now=None):
    now = now or datetime.now(timezone.utc)
    if session == 'tse':        # Tokyo 09:00-11:30, 12:30-15:30 JST (UTC+9)
        local, windows = now.astimezone(timezone(timedelta(hours=9))), [(540, 690), (750, 930)]
        pre, post = (480, 540), (930, 1080)
    elif session == 'pse':      # Manila ~09:30-12:00, 13:00-15:00 PHT (UTC+8), approximate
        local, windows = now.astimezone(timezone(timedelta(hours=8))), [(570, 720), (780, 900)]
        pre, post = (540, 570), (900, 1020)
    else:                       # FX / Brent: weekday trading, weekend closed
        return 'open' if now.weekday() < 5 else 'closed'
    if local.weekday() >= 5:
        return 'closed'
    m = local.hour * 60 + local.minute
    if any(a <= m <= b for a, b in windows):
        return 'open'
    if pre[0] <= m < pre[1]:
        return 'pre-market'
    if windows[0][1] < m < windows[1][0] or post[0] < m <= post[1]:
        return 'after-hours'
    return 'closed'


def _aggregate_status(statuses):
    """Same rules as the China / Saudi cards: all-open -> open, all-closed -> closed, mixed -> partial."""
    u = set(statuses)
    if not u:
        return 'closed'
    if u == {'open'}:
        return 'open'
    if u == {'closed'}:
        return 'closed'
    if 'open' in u:
        return 'partial'
    if 'pre-market' in u:
        return 'pre-market'
    if 'after-hours' in u:
        return 'after-hours'
    return 'closed'


def _tier(chg, polarity, band):
    """stress / warning / stable / rally. band = the 'warning' move in %
    (1.0 for equities and oil, 0.5 for a currency, which moves less)."""
    chg = float(chg or 0)
    if polarity == 'inverted':
        chg = -chg
    if chg <= -2 * band:
        return 'stress'
    if chg <= -band:
        return 'warning'
    if chg >= 2 * band:
        return 'rally'
    return 'stable'


def build_financial_pulse(country, instruments_out, now=None):
    """Canonical Financial Pulse Card payload from fetched instruments."""
    cfg = COUNTRIES[country]
    tiles, statuses = {}, []
    for inst in cfg['instruments']:
        q = instruments_out.get(inst['key'])
        status = _session_status(inst['session'], now)
        if not q:
            continue
        statuses.append(status)
        tiles[inst['tile']] = {
            'name':           inst['name'],
            'ticker':         inst['symbol'],
            'value':          q.get('price'),
            'change_pct_24h': q.get('change_pct_1d', 0),
            'change_pct_30d': q.get('change_pct_30d', 0),
            'tier':           _tier(q.get('change_pct_1d', 0), inst['polarity'], inst['band']),
            'polarity':       inst['polarity'],
            'note':           inst['note'],
            'source':         'Yahoo Finance',
            'market_status':  status,
            'timestamp':      q.get('fetched_at'),
            'sparkline':      q.get('spark_points') or [],
        }
    return {
        'country':        cfg['code'],
        'card_label':     cfg['card_label'],
        'market_status':  _aggregate_status(statuses),
        'last_refreshed': datetime.now(timezone.utc).isoformat(),
        'tiles':          tiles,
        'tile_order':     [i['tile'] for i in cfg['instruments'] if i['tile'] in tiles],
    }


def _refresh_status(payload, country):
    """Cached payloads get a fresh market_status; prices stay as cached."""
    fp = payload.get('financial_pulse')
    if not isinstance(fp, dict):
        return payload
    sess = {i['tile']: i['session'] for i in COUNTRIES[country]['instruments']}
    st = []
    for k, t in (fp.get('tiles') or {}).items():
        t['market_status'] = _session_status(sess.get(k, 'fx'))
        st.append(t['market_status'])
    fp['market_status'] = _aggregate_status(st)
    return payload


# ============================================================
# BUILD
# ============================================================
def build_country_market(country, force=False):
    cfg = COUNTRIES[country]
    if not force:
        cached = _redis_get(cfg['cache_key'])
        if cached and cached.get('financial_pulse'):
            cached['from_cache'] = True
            return _refresh_status(cached, country)

    out = {}
    now_iso = datetime.now(timezone.utc).isoformat()
    for inst in cfg['instruments']:
        q = _fetch_quote(inst['symbol'])
        out[inst['key']] = None if q is None else dict(q, **{
            'name': inst['name'], 'icon': inst['icon'], 'unit': inst['unit'],
            'decimals': inst['decimals'], 'note': inst['note'],
            'symbol': inst['symbol'], 'fetched_at': now_iso,
        })

    live = [k for k, v in out.items() if v]
    payload = {
        'success': bool(live),
        'country': country,
        'instruments': out,
        'live_count': len(live),
        'expected_count': len(cfg['instruments']),
        'missing': [k for k, v in out.items() if not v],
        'financial_pulse': build_financial_pulse(country, out),
        'note': cfg['source_note'],
        'updated_at': now_iso,
        'module_version': __version__,
    }
    if country == 'japan':
        payload['divergence'] = _divergence(out.get('nikkei'), out.get('yen'))
        payload['prose'] = ('Japan\'s financial read requires both instruments. A weak yen flatters '
                            'the Nikkei through exporter earnings, so the index alone cannot separate '
                            'genuine strength from currency effect -- the divergence between them is '
                            'the actual signal.')
    if live:
        _redis_set(cfg['cache_key'], payload)
    else:
        print(f"[Asia Market] {country}: all instruments failed -- cache NOT written "
              "(absence-honest: a blank card is a fetch failure, not a quiet market)")
    return payload


def build_japan_market(force=False):
    """v1.0 name, kept for any caller that imports it."""
    return build_country_market('japan', force=force)


# ============================================================
# FLASK
# ============================================================
def register_asia_market_endpoints(app):
    @app.route('/api/asia/market/<country>', methods=['GET'])
    def asia_market_country(country):
        country = (country or '').lower()
        if country not in COUNTRIES:
            return jsonify({'success': False, 'error': f'unknown market {country}',
                            'available': sorted(COUNTRIES)}), 404
        force = request.args.get('force', '').lower() in ('true', '1', 'yes')
        try:
            return jsonify(build_country_market(country, force=force))
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200]}), 500

    @app.route('/debug/asia-market', methods=['GET'])
    def debug_asia_market():
        rows = {}
        for c, cfg in COUNTRIES.items():
            cached = _redis_get(cfg['cache_key']) or {}
            rows[c] = {
                'instruments_registered': [i['symbol'] for i in cfg['instruments']],
                'cache_present': bool(cached),
                'cached_live_count': cached.get('live_count'),
                'cached_missing': cached.get('missing'),
                'has_financial_pulse': bool(cached.get('financial_pulse')),
                'updated_at': cached.get('updated_at'),
            }
        return jsonify({'module': f'asia_market_quotes v{__version__}',
                        'redis_url_set': bool(UPSTASH_REDIS_URL), 'countries': rows})
