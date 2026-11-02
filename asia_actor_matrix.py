"""
Asifah Analytics -- Asia Actor Matrix v1.1.0
November 2, 2026  (v1.1: Philippines rows + a clean China -> India LAC row)

The Asia sibling of the ME and Africa actor matrices. A READER, NOT A SCANNER:
every cell comes from a rhetoric tracker that already runs on the Asia backend
(asia_regional_bluf TRACKER_KEYS: China, Taiwan, Japan, Vietnam, Philippines,
India, Pakistan, Afghanistan, DPRK).

THE QUESTION THIS BOARD ANSWERS
  Asia's defining question is not "who is pressing whom" in general. It is:
  IS BEIJING PRESSING ON SEVERAL FRONTS AT ONCE, OR ONE AT A TIME?
  China -> Taiwan, China -> Japan (Senkaku / Okinawa), China -> the Philippines and
  China -> Vietnam (South China Sea), China -> India (the LAC) and China's
  economic coercion are read side by side. Simultaneous
  pressure stretches US and allied attention; rotating pressure probes for the
  weakest response. Either way, the reader sees the pattern -- no single-country
  card can show it.

  Around that core: who pushes back (Taiwan, Japan, Vietnam postures), who backs
  whom (US commitments; China -> Pakistan, China -> DPRK, Russia -> DPRK, the
  Gulf -> Pakistan, China -> Iran), and the region's other live dyads
  (India <-> Pakistan, Pakistan <-> Afghanistan / TTP, DPRK -> ROK & Japan).

KINDS
  pressure   who is pressing whom
  response   who is pushing back (the target's own posture)
  patron     who is backing whom
  dyad       rivalries where the tracker cannot split the two directions

HOW A CELL IS READ
  ('actor',  tracker, actor_id)  payload['actors'][id]['level' | 'escalation_level']
                                 or payload['actor_summaries'][id]['level'] (words or ints)
  ('vector', tracker, key)       payload['vector_levels'] (ints or words)
  ('pct',    tracker)            a 0-100 composite (the DPRK leverage score), converted
                                 <10 L0 <25 L1 <45 L2 <65 L3 else L4
  The cell takes the highest source, CAPPED at that tracker's own theatre level
  (overall_level / theatre_level / theatre_escalation_level).

  VOLUME READS ARE CAPPED. Some trackers set actor levels by article COUNT
  (Japan without a tripwire, DPRK, Afghanistan's low..surge words). Counting
  articles measures attention, not escalation, so a volume source tops out at
  L3 here and is labelled 'volume' in the cell. A percent source tops out at L4.
  Keyword counts never assert L5.

  No tracker -> 'unread'. Tracker read but the actor/vector absent -> 'not
  sensed'. Neither is ever L0. No tracker yet for South Korea -- named in the
  payload, not hidden. (v1.1: China -> India now reads the India tracker's
  china_lac VECTOR, so Pakistan voices no longer blend into the LAC row.)

ENDPOINTS
  /api/asia/actor-matrix                  all pairs + headline + So What lines
  /api/asia/actor-matrix?actor=taiwan     pairs touching one card
  /api/asia/actor-matrix/debug            per tracker: actors, vectors, which pairs read them

Cost: Redis reads only (9 trackers), cached 15 min. No external fetch, ever.
"""

import os
import json
import time
from datetime import datetime, timezone

import requests

MATRIX_VERSION = '1.1.0'   # Nov 2 2026 (pm): Philippines + China->India (LAC) rows
CACHE_KEY = 'actor_matrix:asia:latest'
PREV_KEY = 'actor_matrix:asia:previous_levels'
CACHE_SEC = 15 * 60
VOLUME_CAP = 3
PCT_CAP = 4

UPSTASH_REDIS_URL = os.environ.get('UPSTASH_REDIS_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN')

LADDER = {0: 'Monitoring', 1: 'Rhetoric', 2: 'Warning', 3: 'Confrontation',
          4: 'Coercion', 5: 'Active Conflict', 6: 'Red Line Breached'}
KIND_LABELS = {'pressure': 'Who is pressing whom', 'response': 'Who is pushing back',
               'patron': 'Who is backing whom', 'dyad': 'Rivalries (both directions)'}
WORD_LEVELS = {'low': 0, 'normal': 1, 'elevated': 2, 'high': 3, 'surge': 3, 'critical': 3,
               'baseline': 0, 'monitoring': 0}

DEFAULT_TRACKER_KEYS = {
    'china': 'rhetoric:china:latest', 'taiwan': 'rhetoric:taiwan:latest',
    'pakistan': 'rhetoric:pakistan:latest', 'japan': 'rhetoric:japan:latest',
    'india': 'rhetoric:india:latest', 'vietnam': 'rhetoric:vietnam:latest',
    'afghanistan': 'rhetoric:afghanistan:latest', 'dprk': 'rhetoric:dprk:latest',
    'philippines': 'rhetoric:philippines:latest',
}
# Trackers whose ACTOR levels are article counts unless a tripwire fired.
VOLUME_ACTOR_TRACKERS = {'japan', 'dprk', 'afghanistan'}

CN, TW, JP, VN, US, IN, PK, AF, KP, KR, RU, IR = (
    '🇨🇳', '🇹🇼', '🇯🇵', '🇻🇳', '🇺🇸', '🇮🇳', '🇵🇰', '🇦🇫', '🇰🇵', '🇰🇷', '🇷🇺', '🇮🇷')
GULF, GROUP = '🌐', '🏴'
PH = '🇵🇭'


def _P(pid, kind, actor, a_flag, target, t_flag, keys, sources, theatre, note=''):
    return {'id': pid, 'kind': kind, 'actor': actor, 'actor_flag': a_flag, 'target': target,
            'target_flag': t_flag, 'keys': keys, 'sources': sources, 'theatre': theatre, 'note': note}


CHINA_FRONTS = ['china>taiwan', 'china>japan', 'china>philippines', 'china>vietnam', 'china>india', 'china>economic']
FRONT_LABELS = {'china>taiwan': 'Taiwan', 'china>japan': 'Japan', 'china>philippines': 'the Philippines',
                'china>vietnam': 'Vietnam', 'china>india': 'India (LAC)', 'china>economic': 'economic coercion'}

PAIRS = [
    # ---------------- CHINA'S FRONTS (the core question) ----------------
    _P('china>taiwan', 'pressure', 'China (PLA / TAO)', CN, 'Taiwan', TW, ['china', 'taiwan'],
       [('actor', 'taiwan', 'pla_pressure'), ('actor', 'taiwan', 'beijing_coercion'),
        ('actor', 'china', 'pla_operational'), ('actor', 'china', 'tao')], 'taiwan'),
    _P('china>japan', 'pressure', 'China (PLA / Coast Guard)', CN, 'Japan (Senkaku · Okinawa)', JP, ['china', 'japan'],
       [('actor', 'japan', 'china_threat'), ('actor', 'japan', 'senkaku_intrusion'),
        ('actor', 'japan', 'okinawa_pressure')], 'japan'),
    _P('china>philippines', 'pressure', 'China (Coast Guard / militia)', CN, 'Philippines (West Philippine Sea)', PH,
       ['china', 'philippines'],
       [('actor', 'philippines', 'china_scs_pressure'), ('actor', 'philippines', 'beijing_coercion')], 'philippines',
       note='The South China Sea front with a US treaty attached: Second Thomas, Scarborough, Sabina.'),
    _P('china>vietnam', 'pressure', 'China (South China Sea)', CN, 'Vietnam', VN, ['china', 'vietnam'],
       [('actor', 'vietnam', 'china_scs_pressure'), ('actor', 'vietnam', 'beijing_coercion')], 'vietnam'),
    _P('china>india', 'pressure', 'China (PLA on the LAC)', CN, 'India (Ladakh · Arunachal)', IN, ['china', 'india'],
       [('vector', 'india', 'china_lac')], 'india',
       note='Read from the India tracker\'s China-on-the-LAC vector (co-occurrence, 2-outlet rule), separate from Pakistan.'),
    _P('china>economic', 'pressure', 'China (economic coercion)', CN, 'Region (trade · rare earths · tourism)', '🌏',
       ['china', 'taiwan', 'vietnam', 'philippines'],
       [('actor', 'china', 'economic_coercion'), ('actor', 'taiwan', 'economic_pressure'),
        ('actor', 'vietnam', 'economic_pressure'), ('actor', 'philippines', 'economic_pressure')], 'china'),

    # ---------------- RESPONSES ----------------
    _P('taiwan>china', 'response', 'Taiwan (defence & resilience)', TW, 'China', CN, ['taiwan', 'china'],
       [('actor', 'taiwan', 'roc_defense'), ('actor', 'taiwan', 'asymmetric_resilience'),
        ('actor', 'china', 'taiwan_defense')], 'taiwan'),
    _P('japan>china', 'response', 'Japan (cabinet & JSDF posture)', JP, 'China', CN, ['japan', 'china'],
       [('actor', 'japan', 'pm_cabinet'), ('actor', 'japan', 'mod_jsdf'), ('actor', 'china', 'japan_regional')],
       'japan', note='Includes Takaichi-era Taiwan-contingency and counter-strike language.'),
    _P('philippines>china', 'response', 'Philippines (AFP / Coast Guard / DFA)', PH, 'China', CN, ['philippines', 'china'],
       [('actor', 'philippines', 'afp_pcg'), ('actor', 'philippines', 'marcos_state')], 'philippines'),
    _P('vietnam>china', 'response', 'Vietnam (maritime posture)', VN, 'China', CN, ['vietnam', 'china'],
       [('actor', 'vietnam', 'maritime_posture')], 'vietnam'),

    # ---------------- PATRONS / BACKERS ----------------
    _P('us>taiwan', 'patron', 'United States', US, 'Taiwan (commitment)', TW, ['taiwan', 'china'],
       [('actor', 'taiwan', 'us_partnership'), ('actor', 'china', 'us_commitment')], 'taiwan'),
    _P('us>japan', 'patron', 'United States', US, 'Japan (alliance)', JP, ['japan'],
       [('actor', 'japan', 'us_alliance')], 'japan'),
    _P('us>philippines', 'patron', 'United States (treaty ally)', US, 'Philippines (MDT · EDCA)', PH, ['philippines'],
       [('actor', 'philippines', 'us_alliance')], 'philippines',
       note='The only South China Sea claimant with a US defence treaty.'),
    _P('us>vietnam', 'patron', 'United States', US, 'Vietnam (partnership)', VN, ['vietnam'],
       [('actor', 'vietnam', 'us_partnership')], 'vietnam'),
    _P('china>pakistan', 'patron', 'China (CPEC, arms)', CN, 'Pakistan', PK, ['pakistan', 'china'],
       [('actor', 'pakistan', 'china_pakistan_axis')], 'pakistan'),
    _P('gulf>pakistan', 'patron', 'Saudi Arabia & Gulf', GULF, 'Pakistan (defence pact, money)', PK, ['pakistan'],
       [('actor', 'pakistan', 'gcc_pakistan')], 'pakistan'),
    _P('china>dprk', 'patron', 'China (the lifeline)', CN, 'North Korea', KP, ['north_korea', 'china'],
       [('actor', 'dprk', 'china_axis')], 'dprk'),
    _P('russia>dprk', 'patron', 'Russia (war rent)', RU, 'North Korea', KP, ['north_korea'],
       [('actor', 'dprk', 'russia_axis')], 'dprk',
       note='Troops in Kursk paid for in money, oil and technology; a Ukraine ceasefire switches the rent off.'),
    _P('china>iran', 'patron', 'China', CN, 'Iran (arms · ISR · dual-use)', IR, ['china'],
       [('actor', 'china', 'china_iran_axis')], 'china',
       note='The Asia-to-Middle-East bridge: what Beijing supplies Tehran.'),

    # ---------------- DYADS & OTHER PRESSURE ----------------
    _P('dprk>rok_japan', 'pressure', 'North Korea', KP, 'South Korea & Japan', KR, ['north_korea', 'south_korea', 'japan'],
       [('pct', 'dprk', None), ('actor', 'japan', 'dprk_threat')], 'dprk',
       note='DPRK reads INVERTED: Pyongyang escalates when its leverage decays, so a quiet tracker is not a calm one.'),
    _P('india<>pakistan', 'dyad', 'India', IN, 'Pakistan', PK, ['india', 'pakistan'],
       [('vector', 'india', 'pakistan_loc'), ('actor', 'pakistan', 'india_pakistan')], 'pakistan',
       note='Read from India\'s LoC/Pakistan vector and Pakistan\'s India actor; the higher of the two shows.'),
    _P('pakistan<>afghanistan', 'dyad', 'Pakistan', PK, 'Afghanistan (Taliban)', AF, ['pakistan', 'afghanistan'],
       [('actor', 'pakistan', 'afghanistan_pakistan'), ('actor', 'afghanistan', 'pakistan_state')], 'pakistan'),
    _P('ttp>pakistan', 'pressure', 'TTP (Pakistani Taliban)', GROUP, 'Pakistan', PK, ['pakistan', 'afghanistan'],
       [('actor', 'afghanistan', 'ttp')], 'afghanistan'),
    _P('iskp>region', 'pressure', 'ISKP', GROUP, 'Afghanistan & beyond', AF, ['afghanistan'],
       [('actor', 'afghanistan', 'iskp')], 'afghanistan'),
]

COVERAGE_GAPS = [
    'No tracker yet: South Korea (DPRK pressure on Seoul is read only through the DPRK tracker).',
]

CARD_ALIASES = {'dprk': 'north_korea', 'northkorea': 'north_korea', 'southkorea': 'south_korea'}


# ----------------------------------------------------------------------------
# REDIS (Upstash REST, read path + simple SET for the cache)
# ----------------------------------------------------------------------------
def _rget(key):
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return None
    try:
        r = requests.get(f'{UPSTASH_REDIS_URL}/get/{key}',
                         headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'}, timeout=6)
        res = r.json().get('result')
        return json.loads(res) if res else None
    except Exception as e:
        print(f'[Asia Matrix] Redis get {key}: {str(e)[:100]}')
        return None


def _rset(key, value, ttl=7 * 86400):
    if not (UPSTASH_REDIS_URL and UPSTASH_REDIS_TOKEN):
        return False
    try:
        r = requests.post(UPSTASH_REDIS_URL, headers={'Authorization': f'Bearer {UPSTASH_REDIS_TOKEN}'},
                          json=['SET', key, json.dumps(value, default=str), 'EX', str(ttl)], timeout=8)
        return r.status_code == 200
    except Exception as e:
        print(f'[Asia Matrix] Redis set {key}: {str(e)[:100]}')
        return False


def _tracker_keys():
    try:
        import asia_regional_bluf as b
        return dict(b.TRACKER_KEYS)
    except Exception:
        return dict(DEFAULT_TRACKER_KEYS)


# ----------------------------------------------------------------------------
# NORMALISE ONE TRACKER PAYLOAD
# ----------------------------------------------------------------------------
def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return max(0, min(6, int(v)))
    if isinstance(v, str):
        s = v.strip().lower()
        if s.lstrip('-').isdigit():
            return max(0, min(6, int(s)))
        if s in WORD_LEVELS:
            return WORD_LEVELS[s]
    return None


def theatre_level(raw):
    for k in ('overall_level', 'theatre_level', 'theatre_escalation_level', 'composite_level'):
        v = _num(raw.get(k))
        if v is not None:
            return v
    return None


def _tripwire_fired(rec):
    tw = rec.get('tripwires')
    if isinstance(tw, dict):
        return any(bool(v) for k, v in tw.items() if k not in ('reporting_language', 'brake_language'))
    return False


def normalise(name, raw):
    actors, volume = {}, set()
    for block in ('actors', 'actor_summaries'):
        a = raw.get(block)
        if not isinstance(a, dict):
            continue
        for aid, rec in a.items():
            if not isinstance(rec, dict) or aid in actors:
                continue
            word = isinstance(rec.get('level'), str) and not str(rec.get('level')).strip().isdigit()
            lv = _num(rec.get('level'))
            if lv is None:
                lv = _num(rec.get('escalation_level'))
            if lv is None:
                continue
            actors[aid] = lv
            if word or (name in VOLUME_ACTOR_TRACKERS and not _tripwire_fired(rec)):
                volume.add(aid)
    vectors = {}
    vl = raw.get('vector_levels_platform') if isinstance(raw.get('vector_levels_platform'), dict) else None
    for k, v in (vl or raw.get('vector_levels') or {}).items():
        lv = _num(v)
        if lv is not None:
            vectors[k] = lv
    pct = raw.get('theatre_score')
    pct = float(pct) if isinstance(pct, (int, float)) and not isinstance(pct, bool) else None
    th = theatre_level(raw)
    return {'threat': th, 'actors': actors, 'volume_actors': volume, 'vectors': vectors, 'pct': pct,
            'scanned_at': raw.get('scanned_at') or raw.get('updated_at') or raw.get('cached_at')
            or raw.get('scan_date') or ''}


def read_trackers(redis_get=None):
    rget = redis_get or _rget
    out, missing = {}, []
    for th, key in _tracker_keys().items():
        raw = rget(key)
        if isinstance(raw, dict) and raw:
            n = normalise(th, raw)
            n['freshness'] = 'stale' if raw.get('stale') else 'live'
            out[th] = n
        else:
            missing.append(th)
    return out, missing


def pct_to_level(p):
    p = float(p or 0)
    return 0 if p < 10 else 1 if p < 25 else 2 if p < 45 else 3 if p < 65 else 4


# ----------------------------------------------------------------------------
# CELL + MATRIX
# ----------------------------------------------------------------------------
def read_pair(pair, trackers):
    best, tried, unread = None, [], []
    for kind, th, sid in pair['sources']:
        t = trackers.get(th)
        if not t:
            unread.append(th)
            continue
        tried.append(th)
        basis = 'tracker'
        if kind == 'pct':
            if t['pct'] is None:
                continue
            lv = min(PCT_CAP, pct_to_level(t['pct']))
            basis, sid = 'percent', f"composite {t['pct']:.0f}"
        else:
            lv = (t['actors'] if kind == 'actor' else t['vectors']).get(sid)
            if lv is None:
                continue
            if kind == 'actor' and sid in t['volume_actors']:
                lv, basis = min(VOLUME_CAP, lv), 'volume'
        cap = t['threat'] if t['threat'] is not None else 6
        capped = min(lv, cap)
        cand = {'level': capped, 'raw_level': lv, 'tracker': th, 'kind': kind, 'id': sid, 'basis': basis,
                'capped': capped < lv, 'freshness': t['freshness']}
        if best is None or cand['level'] > best['level']:
            best = cand
    cell = {k: pair[k] for k in ('id', 'kind', 'actor', 'actor_flag', 'target', 'target_flag', 'keys', 'theatre', 'note')}
    cell['kind_label'] = KIND_LABELS[pair['kind']]
    if best:
        cell.update(state='read', level=best['level'], word=LADDER[best['level']], source=best)
    elif tried:
        cell.update(state='not_sensed', level=None, word='Not sensed',
                    source={'trackers_read': sorted(set(tried)), 'reason': 'tracker read; this actor/vector absent'})
    else:
        cell.update(state='unread', level=None, word='Unread', source={'trackers_missing': sorted(set(unread))})
    return cell


def _name(c):
    return f"{c['actor']} → {c['target']}"


def build_lines(cells, prev):
    lines = []
    by = {c['id']: c for c in cells}
    read = [c for c in cells if c['state'] == 'read']
    if read:
        top = max(c['level'] for c in read)
        tops = [c for c in read if c['level'] == top]
        if top >= 3:
            lines.append(f"Highest pressure: {'; '.join(_name(c) for c in tops[:3])} at L{top} {LADDER[top]}.")
        else:
            lines.append(f"No pair above L{top} {LADDER[top]} -- pressure is rhetorical, not yet confrontational.")

    # THE CORE QUESTION: how many Chinese fronts are hot at once?
    fronts = [by[i] for i in CHINA_FRONTS if i in by and by[i]['state'] == 'read']
    hot = [c for c in fronts if c['level'] >= 3]
    if len(hot) >= 2:
        lines.append(f"Beijing is pressing on {len(hot)} fronts at once ("
                     + ', '.join(f"{FRONT_LABELS[c['id']]} L{c['level']}" for c in hot)
                     + ") -- simultaneous pressure stretches US and allied attention; the question is whether it is "
                       "coordinated or opportunistic.")
    elif len(hot) == 1 and len(fronts) >= 2:
        h = hot[0]
        rest = [c for c in fronts if c is not h]
        lines.append(f"China's pressure is concentrated on {FRONT_LABELS[h['id']]} (L{h['level']}); "
                     + ', '.join(f"{FRONT_LABELS[c['id']]} L{c['level']}" for c in rest)
                     + ' -- one front at a time, which is how pressure probes for the weakest response.')
    elif fronts:
        lines.append('No Chinese front above L2 this cycle -- ' + ', '.join(
            f"{FRONT_LABELS[c['id']]} L{c['level']}" for c in fronts) + '.')

    # Pressure vs response on each front
    for p_id, r_id in (('china>taiwan', 'taiwan>china'), ('china>japan', 'japan>china'),
                       ('china>vietnam', 'vietnam>china'), ('china>philippines', 'philippines>china')):
        p, r = by.get(p_id), by.get(r_id)
        if not (p and r and p['state'] == r['state'] == 'read'):
            continue
        tgt = p['target'].split(' (')[0]
        if p['level'] >= 3 and r['level'] <= 1:
            lines.append(f"{tgt} is absorbing: China's pressure at L{p['level']}, {tgt}'s own posture at "
                         f"L{r['level']} -- restraint or limited options; watch which.")
        elif r['level'] - p['level'] >= 2:
            lines.append(f"{tgt}'s posture (L{r['level']}) is running ahead of China's pressure (L{p['level']}) "
                         f"-- watch for Beijing's answer.")

    # The treaty question: contact at sea against the one claimant with a US treaty
    pp, up = by.get('china>philippines'), by.get('us>philippines')
    if pp and pp['state'] == 'read' and pp['level'] >= 4:
        if up and up['state'] == 'read' and up['level'] >= 3:
            lines.append(f"China is in contact with Philippine vessels (L{pp['level']}) and the US alliance is active "
                         f"(L{up['level']}) -- this is the band where the Mutual Defense Treaty stops being background.")
        else:
            lines.append(f"China is in contact with Philippine vessels (L{pp['level']}) while the US alliance reads quiet "
                         "-- watch Washington's wording on Article IV.")

    u, c = by.get('us>taiwan'), by.get('china>taiwan')
    if u and c and u['state'] == c['state'] == 'read' and u['level'] >= 3 and c['level'] >= 3:
        lines.append('US commitment to Taiwan and PLA pressure on Taiwan are both at Confrontation or above -- '
                     'the spiral pattern, where each side reads the other\'s move as provocation.')

    moved = [f"{_name(x)} (L{prev[x['id']]}→L{x['level']})" for x in read
             if isinstance((prev or {}).get(x['id']), int) and x['level'] - prev[x['id']] >= 2]
    if moved:
        lines.append('Sharp moves since the last read: ' + '; '.join(moved[:3]) + '.')
    gaps = [x for x in cells if x['state'] != 'read']
    if gaps:
        lines.append(f"{len(gaps)} of {len(cells)} pairs not read this cycle -- shown as gaps, not as calm.")
    return lines[:6]


def build_matrix(redis_get, redis_set, trackers=None, missing=None):
    if trackers is None:
        trackers, missing = read_trackers(redis_get)
    cells = [read_pair(p, trackers) for p in PAIRS]
    prev = redis_get(PREV_KEY) or {}
    if not isinstance(prev, dict):
        prev = {}
    for c in cells:
        p = prev.get(c['id'])
        c['previous_level'] = p if isinstance(p, int) else None
        c['delta'] = (c['level'] - p) if (c['state'] == 'read' and isinstance(p, int)) else None
    read = [c for c in cells if c['state'] == 'read']
    head = max(read, key=lambda c: c['level']) if read else None
    fronts = [c for c in cells if c['id'] in CHINA_FRONTS and c['state'] == 'read']
    payload = {
        'success': True, 'version': MATRIX_VERSION, 'region': 'asia', 'built_at': datetime.now(timezone.utc).isoformat(),
        'headline': ({'pair': _name(head), 'level': head['level'], 'word': head['word'], 'kind': head['kind']}
                     if head else None),
        'china_fronts': {'read': len(fronts), 'hot': sum(1 for c in fronts if c['level'] >= 3),
                         'levels': {c['id']: c['level'] for c in fronts}},
        'pairs': cells,
        'kinds': KIND_LABELS,
        'lines': build_lines(cells, prev),
        'trackers_read': sorted(trackers), 'trackers_missing': sorted(missing or []),
        'coverage': {'tracked_countries': sorted(_tracker_keys()), 'gaps': COVERAGE_GAPS},
        'method': ('Each pair reads the rhetoric tracker(s) that watch it and takes the highest reading, capped at '
                   'that tracker\'s own theatre level. Article-count (volume) readings cap at L3 and percent '
                   'composites at L4 -- counting coverage is not the same as escalation. Nothing here is scanned '
                   'separately. Unread and not-sensed pairs are gaps, never L0.'),
    }
    if read:
        redis_set(PREV_KEY, {c['id']: c['level'] for c in read})
    return payload


def filter_for_actor(payload, actor):
    a = CARD_ALIASES.get(actor, actor)
    pairs = [c for c in payload.get('pairs', []) if a in c['keys']]
    out = dict(payload)
    out['pairs'], out['actor'] = pairs, a
    read = [c for c in pairs if c['state'] == 'read']
    head = max(read, key=lambda c: c['level']) if read else None
    out['headline'] = ({'pair': _name(head), 'level': head['level'], 'word': head['word'], 'kind': head['kind']}
                       if head else None)
    out['lines'] = build_lines(pairs, {c['id']: c.get('previous_level') for c in pairs}) if pairs else []
    return out


# ----------------------------------------------------------------------------
# FLASK
# ----------------------------------------------------------------------------
def register_asia_actor_matrix(app):
    from flask import jsonify, request
    _mem = {'payload': None, 'at': 0}

    def current():
        if _mem['payload'] and time.time() - _mem['at'] < CACHE_SEC:
            return _mem['payload']
        cached = _rget(CACHE_KEY)
        if isinstance(cached, dict) and time.time() - cached.get('_at', 0) < CACHE_SEC:
            _mem.update(payload=cached, at=cached['_at'])
            return cached
        payload = build_matrix(_rget, _rset)
        payload['_at'] = time.time()
        _rset(CACHE_KEY, payload, ttl=CACHE_SEC * 4)
        _mem.update(payload=payload, at=time.time())
        return payload

    def api_matrix():
        try:
            data = current()
            actor = (request.args.get('actor') or '').strip().lower()
            return jsonify(filter_for_actor(data, actor) if actor else data)
        except Exception as e:
            return jsonify({'success': False, 'version': MATRIX_VERSION, 'state': 'unread',
                            'error': f'{type(e).__name__}: {str(e)[:200]}', 'pairs': []}), 200

    def api_debug():
        try:
            trackers, missing = read_trackers()
        except Exception as e:
            return jsonify({'error': f'{type(e).__name__}: {e}'}), 200
        rows = {}
        for th, t in trackers.items():
            used_a = {s[2] for p in PAIRS for s in p['sources'] if s[1] == th and s[0] == 'actor'}
            used_v = {s[2] for p in PAIRS for s in p['sources'] if s[1] == th and s[0] == 'vector'}
            rows[th] = {'theatre_level': t['threat'], 'theatre_pct': t['pct'], 'freshness': t['freshness'],
                        'actors': t['actors'], 'volume_actors': sorted(t['volume_actors']), 'vectors': t['vectors'],
                        'unused_actors': sorted(set(t['actors']) - used_a),
                        'expected_but_absent': sorted((used_a - set(t['actors'])) | (used_v - set(t['vectors'])))}
        return jsonify({'version': MATRIX_VERSION, 'trackers': rows, 'missing': missing,
                        'pairs_by_source': {p['id']: [f'{k}:{th}:{sid}' for k, th, sid in p['sources']] for p in PAIRS}})

    app.add_url_rule('/api/asia/actor-matrix', 'asia_actor_matrix', api_matrix, methods=['GET'])
    app.add_url_rule('/api/asia/actor-matrix/debug', 'asia_actor_matrix_debug', api_debug, methods=['GET'])
    print(f"[Asia Matrix] ✅ /api/asia/actor-matrix (+ /debug) -- {len(PAIRS)} pairs, reader only")
