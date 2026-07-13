"""
═══════════════════════════════════════════════════════════════════════
  ASIFAH ANALYTICS — DPRK LEVERAGE TRACKER
  rhetoric_tracker_dprk.py  ·  v1.0.0 (Jul 13 2026)  ·  Asia backend
═══════════════════════════════════════════════════════════════════════

THE INSTRUMENT: LEVERAGE INTEGRITY — and the read is INVERTED.

    THE DPRK ESCALATES WHEN ITS LEVERAGE DECAYS, NOT WHEN IT PEAKS.

A nuclear test is not a war signal. It is a RELEVANCE signal -- the way
Pyongyang forces itself back onto an agenda it has been left off. The danger
condition is not being courted. It is being NEGOTIATED AROUND.

WHY THIS TRACKER IS THE CANONICAL TEMPO CASE (mode='actor')
------------------------------------------------------------------------
Poland runs mode='tape' because Russia NEVER claims its hybrid operations --
there is no claiming actor to fall silent, so we measure the tape instead.

The DPRK is the exact opposite, and it is why the tempo engine was worth
building. Pyongyang ANNOUNCES. KCNA has a cadence -- a rhythm of statements,
inspections, guidance visits, editorials. For a CLAIMING actor, silence is not
the absence of signal. Silence IS the signal. That is the canonical
quiet-before-storm case, and this is the tracker that finally exercises it.

WHAT IT READS (server-side, absence-honest)
  - Korea repricing  -> /api/conflict-repricing/korea (ME backend). The market
    layer measures whether Seoul's tape still FLINCHES when Pyongyang shouts.
    Same variable as leverage integrity, read from the opposite end: a
    provocation that buys no attention bought no leverage. Two independent
    sensors, and when they agree the compound read gets to say so.
  - Tempo baseline   -> mode='actor'. KCNA statement cadence vs a 30-day
    rolling window, with the corpus-health guard so a dead RSS feed cannot
    masquerade as Pyongyang going quiet.

WHAT IT WRITES
  - rhetoric:dprk:latest / :history
  - crosstheater:dprk:fingerprint
        node_class: 'peer'  on the Russia wheel (COMBATANT, not supplier --
                            troops in Kursk, a memorial wall with 2,288 names)
        node_class: 'client' on the China wheel (the dependency)
    THE CHINA SPOKE IS THE POINT. `spoke:china:kazakhstan` has been sitting in
    Redis written-but-unread because a reader for a one-spoke rim is premature.
    DPRK makes it TWO. Two spokes justify the reader, and China's tracker
    becomes a hub -- exactly the way Russia's did.
  - tempo:dprk:counts:{date}  (statements — the KCNA cadence)

CONTRACT (do not rename these three; the Korea Market Watch card reads them):
  provocation_active · provocation_class · leverage_integrity
"""

import os
import re
import json
import time
import threading
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

TRACKER_VERSION = '1.0.0'

UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN')

ASIA_BACKEND = 'https://asifah-asia-backend.onrender.com'
ME_BACKEND   = os.environ.get('ME_BACKEND_URL', 'https://asifah-backend.onrender.com')

REDIS_KEY_LATEST  = 'rhetoric:dprk:latest'
REDIS_KEY_HISTORY = 'rhetoric:dprk:history'
CACHE_TTL         = 12 * 3600
SCAN_LOCK_KEY     = 'lock:dprk:rhetoric:scan'

# ── Interpreter ──
try:
    from dprk_signal_interpreter import interpret_signals as _dprk_interpret
    _INTERPRETER_AVAILABLE = True
    print('[DPRK Rhetoric] ✅ Signal interpreter loaded')
except ImportError as e:
    _INTERPRETER_AVAILABLE = False
    _dprk_interpret = None
    print(f'[DPRK Rhetoric] ⚠️ Interpreter not available: {e}')

# ── Tempo engine: mode='actor'. THE canonical case. ──
try:
    from tempo_baseline import emit_counts as _tempo_emit, read_baseline as _tempo_read
    TEMPO_AVAILABLE = True
except ImportError:
    TEMPO_AVAILABLE = False
    _tempo_emit = None
    _tempo_read = None

try:
    from telegram_signals_asia import fetch_dprk_telegram_signals
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    fetch_dprk_telegram_signals = None

try:
    from bluesky_signals_asia import fetch_bluesky_for_target
    BLUESKY_AVAILABLE = True
except ImportError:
    BLUESKY_AVAILABLE = False
    fetch_bluesky_for_target = None


# ════════════════════════════════════════════════════════════
# SOURCES
# ════════════════════════════════════════════════════════════

RSS_FEEDS = [
    ('https://kcnawatch.org/feed/',                    'KCNA Watch',   1.00),
    ('https://www.nknews.org/feed/',                   'NK News',      1.00),
    ('https://www.38north.org/feed/',                  '38 North',     1.00),
    ('https://www.dailynk.com/english/feed/',          'Daily NK',     0.95),
    ('https://en.yna.co.kr/RSS/news.xml',              'Yonhap',       0.90),
    ('https://www.rfa.org/english/rss2.xml',           'RFA',          0.85),
    ('https://www.koreaherald.com/rss/020000000000.xml', 'Korea Herald', 0.85),
    ('https://www.reuters.com/arc/outboundfeeds/newsletter-asia/?outputType=xml', 'Reuters Asia', 0.85),
]

# kor = Korean (GDELT sourcelang). The Korean-language slice matters here in a
# way it does not for most theatres: ROK reporting on the North is faster and
# more granular than the English wires, and KCNA's own phrasing survives
# translation badly.
GDELT_QUERIES = [
    ('North Korea missile',        'eng'),
    ('North Korea nuclear test',   'eng'),
    ('Kim Jong Un',                'eng'),
    ('North Korea Russia troops',  'eng'),
    ('\ubd81\ud55c \ubbf8\uc0ac\uc77c',      'kor'),   # North Korea missile
    ('\uae40\uc815\uc740',                   'kor'),   # Kim Jong Un
    ('\ubd81\ud55c \ud575',                  'kor'),   # North Korea nuclear
]

REDDIT_SUBREDDITS = ['northkorea', 'korea', 'CredibleDefense', 'geopolitics']

_DPRK_GATE = re.compile(
    r'\b(north korea|dprk|pyongyang|kim jong|kcna|korean peninsula|inter-korean|punggye|yongbyon)\b',
    re.I)


# ════════════════════════════════════════════════════════════
# ACTORS — 7
# ════════════════════════════════════════════════════════════

ACTORS = {
    'kim_jong_un': {
        'name': 'Kim Jong Un', 'flag': '\U0001f1f0\U0001f1f5', 'icon': '\U0001f451',
        'color': '#dc2626', 'weight': 1.2,
        'role': 'The principal. Presence is staged; ABSENCE is a choice, not an accident.',
        'keywords': [
            'kim jong un', 'kim jong-un', 'north korean leader', 'supreme leader north korea',
            'kim inspected', 'kim guided', 'kim visited', 'kim chaired', 'kim attended',
            'kim jong un speech', 'kim jong un statement', 'kim skips', 'kim absent',
            '\uae40\uc815\uc740',
        ],
    },
    'kim_yo_jong': {
        'name': 'Kim Yo Jong', 'flag': '\U0001f1f0\U0001f1f5', 'icon': '\U0001f5e3\ufe0f',
        'color': '#f59e0b', 'weight': 1.1,
        'role': 'The VOICE. Speaks when the principal wants deniability — a deliberate instrument, not a substitute.',
        'keywords': [
            'kim yo jong', 'kim yo-jong', 'vice department director kim',
            'kim yo jong statement', 'kim yo jong warned', 'kim yo jong dismissed',
            '\uae40\uc5ec\uc815',
        ],
    },
    'kcna_state_media': {
        'name': 'KCNA / State Media', 'flag': '\U0001f4e2', 'icon': '\U0001f4f0',
        'color': '#38bdf8', 'weight': 1.0,
        'role': 'The declaratory organ — AND THE TEMPO TARGET. Its cadence is the baseline; its silence is the signal.',
        'keywords': [
            'kcna', 'korean central news agency', 'rodong sinmun', 'north korean state media',
            'pyongyang times', 'uriminzokkiri', 'north korea said', 'pyongyang said',
            'north korea announced', 'north korea warned', 'north korea vowed',
            'north korea denounced', 'north korea statement',
            '\uc870\uc120\uc911\uc559\ud1b5\uc2e0', '\ub85c\ub3d9\uc2e0\ubb38',
        ],
    },
    'kpa_missile_forces': {
        'name': 'KPA / Missile Forces', 'flag': '\u2694\ufe0f', 'icon': '\U0001f680',
        'color': '#ef4444', 'weight': 1.1,
        'role': 'Korean People\'s Army, Missile Administration, nuclear complex.',
        'keywords': [
            'korean people\'s army', 'kpa', 'north korean military', 'missile administration',
            'north korea launched', 'north korea fired', 'north korea test-fired',
            'ballistic missile north korea', 'icbm', 'hwasong', 'punggye-ri', 'yongbyon',
            'sohae', 'tongchang-ri', 'north korea drill', 'north korea exercise',
            'nuclear weapons institute', 'general staff north korea',
            '\uc870\uc120\uc778\ubbfc\uad70', '\ud0c4\ub3c4\ubbf8\uc0ac\uc77c',
        ],
    },
    'russia_axis': {
        'name': 'Russia Axis (patron)', 'flag': '\U0001f1f7\U0001f1fa', 'icon': '\U0001f91d',
        'color': '#a855f7', 'weight': 1.2,
        'role': 'The patron — and the source of the war rent that a ceasefire switches OFF.',
        'keywords': [
            'north korea russia', 'russia north korea', 'putin kim', 'kim putin',
            'north korean troops russia', 'kursk north korean', 'north korea kursk',
            'mutual defense treaty', 'comprehensive strategic partnership',
            'north korea shells russia', 'munitions north korea russia',
            'lavrov pyongyang', 'shoigu pyongyang', 'russian delegation pyongyang',
            'north korean workers russia', 'russia oil north korea',
        ],
    },
    'china_axis': {
        'name': 'China Axis (lifeline)', 'flag': '\U0001f1e8\U0001f1f3', 'icon': '\U0001f409',
        'color': '#22c55e', 'weight': 1.0,
        'role': 'The economic lifeline — the dependency Beijing controls. SPOKE #2 on the China wheel.',
        'keywords': [
            'north korea china', 'china north korea', 'xi kim', 'kim xi jinping',
            'china north korea trade', 'dandong', 'sinuiju', 'yalu river',
            'chinese delegation pyongyang', 'china aid north korea',
            'beijing pyongyang', 'china north korea border', 'china dprk',
        ],
    },
    'rok_us_alliance': {
        'name': 'ROK / US Alliance', 'flag': '\U0001f1f0\U0001f1f7', 'icon': '\U0001f6e1\ufe0f',
        'color': '#0ea5e9', 'weight': 1.0,
        'role': 'The adversary set — and the audience most DPRK provocations are actually addressed to.',
        'keywords': [
            'south korea north korea', 'seoul pyongyang', 'rok military',
            'us forces korea', 'usfk', 'freedom shield', 'ulchi freedom',
            'joint exercise korea', 'extended deterrence korea',
            'south korean defense ministry', 'lee jae-myung', 'inter-korean',
            'dmz', 'panmunjom', 'nll', 'northern limit line',
            'trilateral japan korea us', 'b-1b korea', 'carrier korea',
        ],
    },
}


# ════════════════════════════════════════════════════════════
# REDIS
# ════════════════════════════════════════════════════════════

def _redis_get(key):
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return None
    try:
        r = requests.get(f'{UPSTASH_REDIS_URL}/get/{key}',
                         headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'}, timeout=6)
        d = r.json()
        if d.get('result'):
            return json.loads(d['result'])
    except Exception as e:
        print(f'[DPRK Rhetoric] Redis get error: {str(e)[:90]}')
    return None


def _redis_set(key, value, ttl=CACHE_TTL):
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return False
    try:
        r = requests.post(UPSTASH_REDIS_URL,
                          headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}',
                                   'Content-Type': 'application/json'},
                          json=['SET', key, json.dumps(value, default=str), 'EX', ttl],
                          timeout=10)
        return r.status_code == 200
    except Exception as e:
        print(f'[DPRK Rhetoric] Redis set error: {str(e)[:90]}')
        return False


def _redis_lpush_trim(key, value, keep=60):
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return
    try:
        h = {'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}', 'Content-Type': 'application/json'}
        requests.post(UPSTASH_REDIS_URL, headers=h,
                      json=['LPUSH', key, json.dumps(value, default=str)], timeout=8)
        requests.post(UPSTASH_REDIS_URL, headers=h,
                      json=['LTRIM', key, 0, keep - 1], timeout=8)
    except Exception as e:
        print(f'[DPRK Rhetoric] History push error: {str(e)[:90]}')


def _acquire_scan_lock(ttl=1800):
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return True
    try:
        r = requests.post(UPSTASH_REDIS_URL,
                          headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}',
                                   'Content-Type': 'application/json'},
                          json=['SET', SCAN_LOCK_KEY, datetime.now(timezone.utc).isoformat(),
                                'NX', 'EX', ttl], timeout=8)
        return (r.json() or {}).get('result') == 'OK'
    except Exception:
        return True


# ════════════════════════════════════════════════════════════
# FETCHERS
# ════════════════════════════════════════════════════════════

_UA = {'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')}


def _fetch_rss(url, source, weight=0.85, max_items=25):
    out = []
    try:
        r = requests.get(url, timeout=12, headers=_UA)
        if r.status_code != 200:
            print(f'[DPRK RSS] {source}: HTTP {r.status_code}')
            return out
        feed = feedparser.parse(r.content)
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        for e in feed.entries[:max_items]:
            title = (e.get('title') or '').strip()
            desc = (e.get('summary') or e.get('description') or '')[:600]
            if not title:
                continue
            # Broad wires get gated to DPRK content; the dedicated DPRK outlets
            # (KCNA Watch, NK News, 38 North, Daily NK) do not -- everything they
            # publish is on-target by construction.
            if source in ('Yonhap', 'RFA', 'Korea Herald', 'Reuters Asia'):
                if not _DPRK_GATE.search(title + ' ' + desc):
                    continue
            pub = None
            try:
                if e.get('published_parsed'):
                    pub = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
                    if pub < cutoff:
                        continue
            except Exception:
                pass
            out.append({
                'title': title, 'description': desc, 'url': e.get('link', ''),
                'source': source, 'source_type': 'rss', 'weight': weight,
                'published': pub.isoformat() if pub else None,
            })
    except Exception as e:
        print(f'[DPRK RSS] {source}: {str(e)[:70]}')
    return out


def _fetch_gdelt(query, language='eng', days=7, max_records=25):
    out = []
    try:
        r = requests.get('https://api.gdeltproject.org/api/v2/doc/doc', params={
            'query': f'{query} sourcelang:{language}', 'mode': 'ArtList',
            'maxrecords': max_records, 'format': 'json', 'timespan': f'{days * 24}h',
        }, timeout=(5, 15), headers=_UA)
        if r.status_code != 200:
            return out
        for a in (r.json().get('articles') or []):
            out.append({
                'title': a.get('title', ''), 'description': '',
                'url': a.get('url', ''), 'source': a.get('domain', 'GDELT'),
                'source_type': 'gdelt', 'weight': 0.75,
                'published': a.get('seendate'), 'lang': language,
            })
    except Exception as e:
        print(f'[DPRK GDELT] {query[:24]} ({language}): {str(e)[:60]}')
    return out


def _fetch_reddit():
    out = []
    for sub in REDDIT_SUBREDDITS:
        try:
            r = requests.get(f'https://www.reddit.com/r/{sub}/new.json?limit=25',
                             timeout=10, headers=_UA)
            if r.status_code != 200:
                continue
            for c in (r.json().get('data', {}).get('children') or []):
                p = c.get('data', {})
                title = p.get('title', '')
                body = (p.get('selftext') or '')[:400]
                if sub != 'northkorea' and not _DPRK_GATE.search(title + ' ' + body):
                    continue
                out.append({
                    'title': title, 'text': title + ' ' + body,
                    'url': f"https://reddit.com{p.get('permalink', '')}",
                    'source': f'reddit-{sub}', 'source_type': 'reddit', 'weight': 0.4,
                })
        except Exception:
            continue
    print(f'[DPRK Reddit] {len(out)} posts')
    return out


# ════════════════════════════════════════════════════════════
# SERVER-SIDE READS
# ════════════════════════════════════════════════════════════

def _read_repricing():
    """The market layer, read back into the rhetoric layer.

    Seoul's tape is the scoreboard for whether Pyongyang's provocations still buy
    attention. Same variable as leverage integrity, opposite end. When both agree
    -- a provocation fired and nothing moved -- the compound read gets to say so,
    and that is two independently-sourced layers converging, not an echo."""
    try:
        r = requests.get(f'{ME_BACKEND}/api/conflict-repricing/korea', timeout=12)
        if not r.ok:
            return None
        d = r.json() or {}
        return {
            'state': d.get('state'),
            'market_read': (d.get('market_read') or d.get('read') or '')[:400],
            'instruments_moved': sum(1 for s in (d.get('instruments') or [])
                                     if s.get('vote') in ('peace', 'escalation')),
        }
    except Exception as e:
        print(f'[DPRK Rhetoric] Repricing read failed (non-fatal): {str(e)[:70]}')
        return None


# ════════════════════════════════════════════════════════════
# CLASSIFY
# ════════════════════════════════════════════════════════════

def _classify(articles, telegram, bluesky, reddit):
    summaries = {}
    for aid, cfg in ACTORS.items():
        summaries[aid] = {
            'id': aid, 'name': cfg['name'], 'flag': cfg['flag'], 'icon': cfg['icon'],
            'color': cfg['color'], 'role': cfg['role'], 'weight': cfg['weight'],
            'statement_count': 0, 'level': 0, 'articles': [],
        }

    pool = []
    for a in articles:
        pool.append((a, (a.get('title', '') + ' ' + a.get('description', '')).lower()))
    for s in (telegram or []) + (bluesky or []) + (reddit or []):
        pool.append((s, (s.get('text') or s.get('title') or '').lower()))

    for item, text in pool:
        if not text:
            continue
        for aid, cfg in ACTORS.items():
            if any(kw in text for kw in cfg['keywords']):
                summaries[aid]['statement_count'] += 1
                if len(summaries[aid]['articles']) < 8:
                    summaries[aid]['articles'].append({
                        'title': item.get('title', '')[:180],
                        'url': item.get('url', ''),
                        'source': item.get('source', ''),
                    })

    for aid, s in summaries.items():
        n = s['statement_count']
        s['level'] = (5 if n >= 25 else 4 if n >= 15 else 3 if n >= 8
                      else 2 if n >= 4 else 1 if n >= 1 else 0)
    return summaries


# ════════════════════════════════════════════════════════════
# CROSS-THEATER FINGERPRINT — the spokes
# ════════════════════════════════════════════════════════════

def _write_crosstheater_fingerprint(result, interp):
    """Emit once, consume many.

    RUSSIA WHEEL: node_class 'peer'. The DPRK was rated a supplier when it was
    shipping shells. It is now a COMBATANT -- troops in Kursk, a memorial wall
    with 2,288 names. Peers are read wheel-to-wheel, not counted as spokes.

    CHINA WHEEL: node_class 'client'. THIS IS THE ONE THAT MATTERS ARCHITECTURALLY.
    `spoke:china:kazakhstan` has been sitting in Redis written-but-unread, because
    building a reader for a one-spoke rim is premature. This is spoke #2. Two
    spokes justify the reader -- and China's tracker gets to become a hub.
    """
    try:
        lev  = interp.get('leverage_integrity') or {}
        nuc  = interp.get('nuclear_signaling') or {}
        trip = interp.get('nuclear_tripwire') or {}
        exp  = interp.get('expeditionary_footprint') or {}
        lead = interp.get('leadership') or {}
        tempo = interp.get('tempo_deviation') or {}

        fingerprint = {
            'ts':      datetime.now(timezone.utc).isoformat(),
            'theatre': 'dprk',
            'level':   result.get('theatre_score', 0),
            'alert':   result.get('alert_level', 'normal'),

            # ── The instrument (INVERTED: low = dangerous) ──
            'leverage_integrity': lev.get('integrity'),
            'leverage_state':     lev.get('state'),
            'polarity_note': ('INVERTED -- the DPRK escalates when leverage DECAYS. '
                              'Low integrity = HIGH escalation pressure. Do not read '
                              'this as a stability score.'),

            # ── Provocation (the repricing contract, mirrored here) ──
            'provocation_active': interp.get('provocation_active'),
            'provocation_class':  interp.get('provocation_class'),
            'provocation_band':   nuc.get('band'),

            # ── Black Swan ──
            'nuclear_tripwire': trip.get('state'),
            'black_swan':       trip.get('black_swan', False),

            # ── The expeditionary read (portable: this is what a future
            #     expeditionary_footprint.py registry will consume) ──
            'expeditionary_band':  exp.get('band'),
            'expeditionary_hosts': exp.get('hosts', []),
            'tunnel_convergence':  exp.get('tunnel_convergence', False),

            'leadership_band': lead.get('band'),
            'tempo_direction': tempo.get('direction'),

            # ── SPOKE READS ──
            'spokes': {
                'russia': {
                    'node_class': 'peer',
                    'note': ('COMBATANT, not supplier. Troops committed to Kursk; '
                             'casualties in the thousands. Read wheel-to-wheel; do NOT '
                             'count toward any proxy-activation ladder.'),
                },
                'china': {
                    'node_class': 'client',
                    'note': ('Economic lifeline and dependency. SPOKE #2 on the China '
                             'rim -- with Kazakhstan, this is the pair that justifies '
                             'building the China wheel reader.'),
                },
                'iran': {
                    'node_class': 'dyad',
                    'note': 'Missile-technology dyad, historical. Thin; surface only.',
                },
            },
        }
        _redis_set('crosstheater:dprk:fingerprint', fingerprint, ttl=30 * 3600)
        # The China-rim spoke key, in the same shape Kazakhstan writes.
        _redis_set('spoke:china:dprk', {
            'ts': fingerprint['ts'], 'spoke': 'dprk', 'node_class': 'client',
            'level': result.get('theatre_score', 0),
            'leverage_integrity': lev.get('integrity'),
            'dependency_note': 'China controls the oxygen: trade, oil, the Yalu-Tumen border.',
        }, ttl=30 * 3600)
        print(f"[DPRK Rhetoric] ✅ Fingerprint written (leverage "
              f"{lev.get('integrity')}/100 {lev.get('state')}) + spoke:china:dprk "
              f"[SPOKE #2 — the China wheel reader is now justified]")
    except Exception as e:
        print(f'[DPRK Rhetoric] Fingerprint write error: {str(e)[:110]}')


# ════════════════════════════════════════════════════════════
# THE SCAN
# ════════════════════════════════════════════════════════════

def run_dprk_rhetoric_scan(force=False):
    started = time.time()
    print('[DPRK Rhetoric] Starting scan...')

    articles = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_fetch_rss, u, s, w) for u, s, w in RSS_FEEDS]
        futs += [ex.submit(_fetch_gdelt, q, lang) for q, lang in GDELT_QUERIES]
        for f in as_completed(futs):
            try:
                articles.extend(f.result() or [])
            except Exception:
                continue

    seen, deduped = set(), []
    for a in articles:
        u = (a.get('url') or '').strip()
        if u and u in seen:
            continue
        if u:
            seen.add(u)
        deduped.append(a)
    articles = deduped
    print(f'[DPRK Rhetoric] Articles: {len(articles)}')

    telegram = []
    if TELEGRAM_AVAILABLE and fetch_dprk_telegram_signals:
        try:
            telegram = fetch_dprk_telegram_signals() or []
        except Exception as e:
            print(f'[DPRK Rhetoric] Telegram failed: {str(e)[:70]}')

    bluesky = []
    if BLUESKY_AVAILABLE and fetch_bluesky_for_target:
        try:
            bluesky = fetch_bluesky_for_target('north_korea') or []
        except Exception as e:
            print(f'[DPRK Rhetoric] Bluesky failed: {str(e)[:70]}')

    reddit = _fetch_reddit()
    print(f'[DPRK Rhetoric] Telegram: {len(telegram)} · Bluesky: {len(bluesky)} · '
          f'Reddit: {len(reddit)}')

    repricing = _read_repricing()

    # ── CORPUS HEALTH — the denominator ──
    # Without this, a dead RSS feed drives statement_count to zero and the tracker
    # announces "unusual quiet -- possible operational security," i.e. hallucinates
    # menace out of our own outage. The engine refuses the quiet call when the
    # corpus is sick. For a mode='actor' target this guard is not optional: the
    # entire value of the tracker is its ability to call silence, and a silence
    # call built on a broken denominator is worse than no call at all.
    sources_live = len({a.get('source') for a in articles if a.get('source')})
    live_corpus = {'articles': len(articles), 'sources_live': sources_live,
                   'sources_total': len(RSS_FEEDS)}

    tempo_baseline = None
    if TEMPO_AVAILABLE and _tempo_read:
        try:
            tempo_baseline = _tempo_read('dprk', live_corpus=live_corpus)
        except Exception as e:
            print(f'[DPRK Rhetoric] Tempo read failed (non-fatal): {str(e)[:70]}')

    articles_en = [a for a in articles if a.get('lang') != 'kor']
    articles_ko = [a for a in articles if a.get('lang') == 'kor']

    actor_summaries = _classify(articles, telegram, bluesky, reddit)

    scan_data = {
        'articles_en': articles_en, 'articles_ko': articles_ko, 'articles_ru': [],
        'reddit_signals': reddit, 'telegram_messages': telegram,
        'bluesky_signals': bluesky, 'actor_summaries': actor_summaries,
        'repricing_snapshot': repricing, 'tempo_baseline': tempo_baseline,
    }

    interp = {}
    if _INTERPRETER_AVAILABLE and _dprk_interpret:
        try:
            interp = _dprk_interpret(scan_data) or {}
        except Exception as e:
            print(f'[DPRK Rhetoric] Interpreter error: {str(e)[:110]}')

    lev = interp.get('leverage_integrity') or {}
    trip = interp.get('nuclear_tripwire') or {}
    score = interp.get('composite_modifier', 0)   # INVERSE of leverage

    if trip.get('black_swan'):
        alert = 'critical'
    elif score >= 65 or lev.get('state') in ('decaying', 'collapsed'):
        alert = 'high'
    elif score >= 45 or lev.get('state') == 'eroding':
        alert = 'elevated'
    else:
        alert = 'normal'

    elapsed = round(time.time() - started, 1)
    result = {
        'theatre':           'dprk',
        'flag':              '\U0001f1f0\U0001f1f5',
        'display_name':      'North Korea',
        'theatre_score':     score,
        'alert_level':       alert,
        'pressure_score':    score,
        'tracker_version':   TRACKER_VERSION,
        'cached_at':         datetime.now(timezone.utc).isoformat(),
        'scan_duration_sec': elapsed,
        'cache_status':      'fresh',
        'total_articles':    len(articles),
        'telegram_count':    len(telegram),
        'bluesky_count':     len(bluesky),
        'reddit_count':      len(reddit),
        'articles_en':       articles_en[:60],
        'articles_ko':       articles_ko[:40],
        'actor_summaries':   actor_summaries,

        # ── The instrument ──
        'leverage_integrity': lev,

        # ── Vectors ──
        'nuclear_signaling':       interp.get('nuclear_signaling'),
        'nuclear_tripwire':        trip,
        'leadership':              interp.get('leadership'),
        'expeditionary_footprint': interp.get('expeditionary_footprint'),
        'border_dyads':            interp.get('border_dyads'),
        'illicit_flows':           interp.get('illicit_flows'),
        'food_security':           interp.get('food_security'),
        'tempo_deviation':         interp.get('tempo_deviation'),

        # ── CONTRACT: the Korea Market Watch card reads these three. ──
        'provocation_active': interp.get('provocation_active', False),
        'provocation_class':  interp.get('provocation_class'),

        'repricing_snapshot': repricing,
        'corpus_health':      live_corpus,
        'tempo_baseline':     tempo_baseline,

        'so_what':            interp.get('so_what'),
        'top_signals':        interp.get('top_signals') or [],
        'composite_modifier': score,
        'interpreter_version': interp.get('interpreter_version'),
        'disclaimer': ('This composite is a CONVERGENCE indicator, NOT a probability '
                       'of action.'),
    }

    _redis_set(REDIS_KEY_LATEST, result)
    _write_crosstheater_fingerprint(result, interp)
    _redis_lpush_trim(REDIS_KEY_HISTORY, {
        'cached_at': result['cached_at'], 'theatre_score': score, 'alert_level': alert,
        'leverage_integrity': lev.get('integrity'),
        'provocation_class': result['provocation_class'],
        'top_signals': result['top_signals'][:5],
    })

    # ── TEMPO EMITTER — mode='actor'. THE CANONICAL CASE. ──
    # Pyongyang ANNOUNCES. KCNA has a cadence. For a claiming actor, silence is
    # not the absence of signal -- silence IS the signal. This is the emitter the
    # tempo engine was built for.
    if TEMPO_AVAILABLE and _tempo_emit:
        try:
            kcna = (actor_summaries.get('kcna_state_media') or {}).get('statement_count', 0)
            kim  = (actor_summaries.get('kim_jong_un') or {}).get('statement_count', 0)
            _tempo_emit('dprk',
                        streams={'statements': kcna, 'principal_appearances': kim},
                        corpus=live_corpus)
        except Exception as e:
            print(f'[DPRK Rhetoric] Tempo emit failed (non-fatal): {str(e)[:90]}')

    print(f"[DPRK Rhetoric] ✅ Scan complete in {elapsed}s — leverage "
          f"{lev.get('integrity','--')}/100 ({lev.get('state','--')}), "
          f"pressure {score}, alert {alert}, "
          f"provocation={result['provocation_class'] or 'none'}, "
          f"{len(result['top_signals'])} top_signals")
    return result


# ════════════════════════════════════════════════════════════
# BACKGROUND
# ════════════════════════════════════════════════════════════

def _bg_scan():
    time.sleep(180)
    while True:
        try:
            if _acquire_scan_lock():
                run_dprk_rhetoric_scan()
            else:
                print('[DPRK Rhetoric] Another worker owns the scan window — skipping')
        except Exception as e:
            print(f'[DPRK Rhetoric] Background scan error: {str(e)[:110]}')
        time.sleep(12 * 3600)


def start_dprk_rhetoric_scanner():
    threading.Thread(target=_bg_scan, daemon=True).start()
    print('[DPRK Rhetoric] Background scanner started (12h, cross-worker lock)')


# ════════════════════════════════════════════════════════════
# ENDPOINTS
# ════════════════════════════════════════════════════════════

def register_dprk_rhetoric_endpoints(app):
    from flask import jsonify, request

    @app.route('/api/rhetoric/dprk', methods=['GET'])
    def api_rhetoric_dprk():
        force = request.args.get('force', 'false').lower() == 'true'
        if not force:
            cached = _redis_get(REDIS_KEY_LATEST)
            if cached:
                cached['cache_status'] = 'cached'
                return jsonify(cached)
        return jsonify(run_dprk_rhetoric_scan(force=True))

    @app.route('/api/rhetoric/dprk/summary', methods=['GET'])
    def api_rhetoric_dprk_summary():
        d = _redis_get(REDIS_KEY_LATEST) or {}
        lev = d.get('leverage_integrity') or {}
        return jsonify({
            'theatre': 'dprk', 'flag': '\U0001f1f0\U0001f1f5',
            'theatre_score': d.get('theatre_score', 0),
            'alert_level': d.get('alert_level', 'normal'),
            'leverage_integrity': lev.get('integrity'),
            'leverage_state': lev.get('state'),
            'provocation_active': d.get('provocation_active'),
            'provocation_class': d.get('provocation_class'),
            'nuclear_tripwire': (d.get('nuclear_tripwire') or {}).get('state'),
            'top_signals': (d.get('top_signals') or [])[:3],
            'cached_at': d.get('cached_at'),
        })

    @app.route('/api/rhetoric/dprk/history', methods=['GET'])
    def api_rhetoric_dprk_history():
        try:
            r = requests.get(f'{UPSTASH_REDIS_URL}/lrange/{REDIS_KEY_HISTORY}/0/59',
                             headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'},
                             timeout=8)
            raw = (r.json() or {}).get('result') or []
            entries = []
            for item in raw:
                try:
                    e = json.loads(item)
                    entries.append({'date': e.get('cached_at'),
                                    'score': e.get('theatre_score', 0),
                                    'alert': e.get('alert_level'),
                                    'leverage_integrity': e.get('leverage_integrity')})
                except Exception:
                    continue
            entries.reverse()
            return jsonify({'theatre': 'dprk', 'entries': entries})
        except Exception as e:
            return jsonify({'theatre': 'dprk', 'entries': [], 'error': str(e)[:120]})

    @app.route('/debug/dprk-rhetoric', methods=['GET'])
    def debug_dprk_rhetoric():
        d = _redis_get(REDIS_KEY_LATEST) or {}
        return jsonify({
            'tracker_version':       TRACKER_VERSION,
            'interpreter_available': _INTERPRETER_AVAILABLE,
            'tempo_available':       TEMPO_AVAILABLE,
            'telegram_available':    TELEGRAM_AVAILABLE,
            'bluesky_available':     BLUESKY_AVAILABLE,
            'cached':                bool(d),
            'cached_at':             d.get('cached_at'),
            'total_articles':        d.get('total_articles'),
            'corpus_health':         d.get('corpus_health'),
            'leverage_integrity':    d.get('leverage_integrity'),
            'provocation_active':    d.get('provocation_active'),
            'provocation_class':     d.get('provocation_class'),
            'repricing_snapshot':    d.get('repricing_snapshot'),
            'tempo_baseline_ready':  (d.get('tempo_baseline') or {}).get('ready'),
            'top_signals_count':     len(d.get('top_signals') or []),
            'rss_feeds':             len(RSS_FEEDS),
            'actors':                list(ACTORS.keys()),
        })

    print('[DPRK Rhetoric] ✅ Endpoints registered: /api/rhetoric/dprk, /summary, '
          '/history, /debug/dprk-rhetoric')
