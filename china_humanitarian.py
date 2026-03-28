"""
Asifah Analytics — China Humanitarian & Human Rights Monitor
v1.0.0 — March 2026

ANALYTICAL FRAME:
China's humanitarian situation is analytically distinct from conflict-driven
humanitarian crises. The primary vectors are:

  1. STATE-DIRECTED REPRESSION — Xinjiang, Tibet, Hong Kong
  2. NATURAL DISASTERS — Floods, earthquakes, displacement (ReliefWeb)
  3. STRUCTURAL HUMAN RIGHTS — Surveillance state, labor, press freedom

This module does NOT claim to have real-time detention population data —
China does not permit independent verification. Instead it:
  - Scans live sources for new reporting, sanctions, and policy changes
  - Surfaces ReliefWeb natural disaster/displacement events
  - Maintains timestamped static reference data from authoritative sources
  - Links to HRW, Amnesty, UN OHCHR for full reports

DATA HONESTY PRINCIPLE:
Every static fact includes:
  - Source organization
  - Date of last known verification
  - Explicit note where China restricts independent verification

REDIS KEYS:
  Cache:          china:humanitarian:latest
  History:        china:humanitarian:history
  Disaster Cache: china:humanitarian:disasters

ENDPOINTS:
  GET /api/china/humanitarian
  GET /api/china/humanitarian/summary
  GET /api/china/humanitarian/disasters

COPYRIGHT 2025-2026 Asifah Analytics. All rights reserved.
"""

import os
import json
import time
import threading
import requests
import xml.etree.ElementTree as ET
import urllib.parse
from datetime import datetime, timezone, timedelta
from flask import jsonify, request

# ============================================
# CONFIG
# ============================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN') or os.environ.get('UPSTASH_REDIS_REST_TOKEN')
NEWSAPI_KEY         = os.environ.get('NEWSAPI_KEY')

CACHE_KEY           = 'china:humanitarian:latest'
HISTORY_KEY         = 'china:humanitarian:history'
DISASTER_CACHE_KEY  = 'china:humanitarian:disasters'
CACHE_TTL           = 8 * 3600    # 8 hours
SCAN_INTERVAL_HOURS = 12

_humanitarian_lock    = threading.Lock()
_humanitarian_running = False

RELIEFWEB_API = 'https://api.reliefweb.int/v1/reports'

# ============================================
# STATIC REFERENCE DATA
# Data honesty: every entry has source + date
# ============================================

STATIC_REFERENCE_DATA = {
    'xinjiang': {
        'title':       'Xinjiang — Uyghur Detention & Suppression',
        'region':      'Xinjiang Uyghur Autonomous Region (XUAR)',
        'icon':        '🔴',
        'facts': [
            {
                'label':        'Estimated Detention Population',
                'value':        '1.0M – 1.8M',
                'detail':       'Uyghurs and other Turkic Muslims held in "vocational education and training centers"',
                'source':       'UN OHCHR Assessment',
                'source_url':   'https://www.ohchr.org/en/documents/country-reports/ohchr-assessment-human-rights-concerns-xinjiang-uyghur-autonomous-region',
                'data_as_of':   'August 31, 2022',
                'caveat':       'China denies independent access to verification. Actual numbers may be higher.',
            },
            {
                'label':        'ASPI-Identified Detention Facilities',
                'value':        '380+',
                'detail':       'Detention camp facilities identified via satellite imagery across Xinjiang',
                'source':       'ASPI Xinjiang Data Project',
                'source_url':   'https://xjdp.aspi.org.au/',
                'data_as_of':   '2022',
                'caveat':       'Based on satellite imagery analysis. New construction ongoing.',
            },
            {
                'label':        'Genocide/Crimes Against Humanity Designations',
                'value':        '6+ governments',
                'detail':       'US, UK, Canada, Netherlands, Lithuania, Belgium have formally designated Chinese actions in Xinjiang as genocide or crimes against humanity',
                'source':       'Government official records',
                'source_url':   'https://www.state.gov/reports/2022-country-reports-on-human-rights-practices/china/',
                'data_as_of':   '2024',
                'caveat':       'China rejects all genocide designations.',
            },
            {
                'label':        'UFLPA Enforcement Actions',
                'value':        'Active',
                'detail':       'US Uyghur Forced Labor Prevention Act (UFLPA) bans imports with Xinjiang supply chain links; enforced by US CBP',
                'source':       'US Customs and Border Protection',
                'source_url':   'https://www.cbp.gov/trade/forced-labor/UFLPA',
                'data_as_of':   'Ongoing — see CBP link for current status',
                'caveat':       'Enforcement actions updated continuously by CBP.',
            },
            {
                'label':        'Passport Confiscation',
                'value':        'Systematic',
                'detail':       'Chinese authorities systematically confiscated passports of Uyghur residents, preventing international travel',
                'source':       'Human Rights Watch',
                'source_url':   'https://www.hrw.org/report/2022/04/05/they-dont-understand-law/chinas-violation-uyghur-rights',
                'data_as_of':   '2022',
                'caveat':       'Policy continues; degree of enforcement varies by area.',
            },
        ],
        'report_links': [
            {'label': 'UN OHCHR Xinjiang Assessment (2022)',
             'url': 'https://www.ohchr.org/en/documents/country-reports/ohchr-assessment-human-rights-concerns-xinjiang-uyghur-autonomous-region'},
            {'label': 'HRW — China/Xinjiang Reports',
             'url': 'https://www.hrw.org/asia/china'},
            {'label': 'Amnesty — China Annual Report',
             'url': 'https://www.amnesty.org/en/location/asia-and-the-pacific/east-asia/china/report-china/'},
            {'label': 'ASPI Xinjiang Data Project',
             'url': 'https://xjdp.aspi.org.au/'},
            {'label': 'RFA Uyghur Service',
             'url': 'https://www.rfa.org/english/news/uyghur/'},
        ],
    },

    'tibet': {
        'title':       'Tibet — Repression & Cultural Destruction',
        'region':      'Tibet Autonomous Region (TAR) and Tibetan areas',
        'icon':        '🟡',
        'facts': [
            {
                'label':        'Self-Immolations in Protest',
                'value':        '150+',
                'detail':       'Tibetans have self-immolated since 2009 in protest against Chinese rule; majority were monks, nuns, and young people',
                'source':       'Tibetan Centre for Human Rights and Democracy (TCHRD)',
                'source_url':   'https://tchrd.org/',
                'data_as_of':   'March 2024',
                'caveat':       'China controls access to Tibet; actual count may be higher.',
            },
            {
                'label':        'Panchen Lama Status',
                'value':        'Missing since 1995',
                'detail':       'Gedhun Choekyi Nyima, recognized as Panchen Lama by the Dalai Lama at age 6, disappeared 6 days after his recognition. China installed its own candidate.',
                'source':       'UN Committee on the Rights of the Child',
                'source_url':   'https://www.ohchr.org/en/press-releases/2020/01/un-experts-urge-china-reveal-whereabouts-panchen-lama-25-years-after-he',
                'data_as_of':   'January 2020',
                'caveat':       'China claims he is an ordinary citizen who wishes to protect his privacy.',
            },
            {
                'label':        'Foreign Visitor Restrictions',
                'value':        'Permit required',
                'detail':       'Foreign journalists and tourists require a special Tibet Travel Permit in addition to a Chinese visa; access frequently denied or revoked',
                'source':       'US State Department Tibet Report',
                'source_url':   'https://www.state.gov/reports/2022-country-reports-on-human-rights-practices/china-tibet/',
                'data_as_of':   '2023',
                'caveat':       'Restrictions tighten around sensitive anniversaries (March 10 Uprising Day).',
            },
            {
                'label':        'Monastery Surveillance',
                'value':        'Extensive',
                'detail':       'All monasteries subject to "patriotic education" campaigns requiring monks to denounce the Dalai Lama; surveillance cameras installed throughout',
                'source':       'Human Rights Watch',
                'source_url':   'https://www.hrw.org/asia/china',
                'data_as_of':   '2023',
                'caveat':       'Independent verification extremely difficult due to access restrictions.',
            },
        ],
        'report_links': [
            {'label': 'HRW — Tibet Reports',
             'url': 'https://www.hrw.org/tag/tibet'},
            {'label': 'Amnesty — Tibet',
             'url': 'https://www.amnesty.org/en/location/asia-and-the-pacific/east-asia/china/report-china/'},
            {'label': 'TCHRD Tibet Human Rights',
             'url': 'https://tchrd.org/'},
            {'label': 'RFA Tibet Service',
             'url': 'https://www.rfa.org/english/news/tibet/'},
            {'label': 'Free Tibet',
             'url': 'https://www.freetibet.org/'},
        ],
    },

    'hong_kong': {
        'title':       'Hong Kong — Civil Liberties Erosion',
        'region':      'Hong Kong Special Administrative Region',
        'icon':        '🟣',
        'facts': [
            {
                'label':        'National Security Law Arrests',
                'value':        '260+',
                'detail':       'People arrested under the National Security Law (NSL) since its imposition in June 2020; includes politicians, journalists, activists, and protesters',
                'source':       'Human Rights Watch / Hong Kong Watch',
                'source_url':   'https://www.hrw.org/tag/hong-kong',
                'data_as_of':   '2024',
                'caveat':       'Arrests ongoing; prosecution rate very high under NSL.',
            },
            {
                'label':        'Pro-Democracy Media Shuttered',
                'value':        '5+ major outlets',
                'detail':       'Apple Daily, Stand News, Citizen News, and others shut down under NSL pressure since 2021',
                'source':       'Committee to Protect Journalists (CPJ)',
                'source_url':   'https://cpj.org/asia/hong-kong/',
                'data_as_of':   '2023',
                'caveat':       'Press freedom index for HK declined sharply post-2020.',
            },
            {
                'label':        '"One Country, Two Systems" Deadline',
                'value':        '2047',
                'detail':       'Original 1997 Handover commitment for HK autonomy runs until 2047. Analysts argue NSL effectively ended the arrangement early.',
                'source':       'Sino-British Joint Declaration (1984)',
                'source_url':   'https://www.gov.uk/government/publications/sino-british-joint-declaration',
                'data_as_of':   'Ongoing',
                'caveat':       'UK government has stated China is in violation of the Joint Declaration.',
            },
            {
                'label':        'Electoral System Overhaul',
                'value':        '2021',
                'detail':       'Beijing restructured HK electoral system to ensure only "patriots" can hold office; opposition candidates effectively barred',
                'source':       'Human Rights Watch',
                'source_url':   'https://www.hrw.org/news/2021/03/11/china-overhauls-hong-kong-electoral-system',
                'data_as_of':   '2021',
                'caveat':       'New system fully in place; no competitive opposition elections held since.',
            },
        ],
        'report_links': [
            {'label': 'HRW — Hong Kong Reports',
             'url': 'https://www.hrw.org/tag/hong-kong'},
            {'label': 'Amnesty — Hong Kong',
             'url': 'https://www.amnesty.org/en/location/asia-and-the-pacific/east-asia/china/report-china/'},
            {'label': 'Hong Kong Watch',
             'url': 'https://www.hongkongwatch.org/'},
            {'label': 'CPJ — Hong Kong',
             'url': 'https://cpj.org/asia/hong-kong/'},
        ],
    },
}

# Annual report links — no API, links only
ANNUAL_REPORT_LINKS = [
    {
        'org':   'Human Rights Watch',
        'title': 'World Report — China Chapter',
        'url':   'https://www.hrw.org/world-report/2024/country-chapters/china',
        'year':  '2024',
        'icon':  '📋',
    },
    {
        'org':   'Amnesty International',
        'title': 'Annual Report — China',
        'url':   'https://www.amnesty.org/en/location/asia-and-the-pacific/east-asia/china/report-china/',
        'year':  '2023–24',
        'icon':  '📋',
    },
    {
        'org':   'UN OHCHR',
        'title': 'Xinjiang Assessment',
        'url':   'https://www.ohchr.org/en/documents/country-reports/ohchr-assessment-human-rights-concerns-xinjiang-uyghur-autonomous-region',
        'year':  '2022',
        'icon':  '🇺🇳',
    },
    {
        'org':   'US State Department',
        'title': 'China Human Rights Report',
        'url':   'https://www.state.gov/reports/2022-country-reports-on-human-rights-practices/china/',
        'year':  '2023',
        'icon':  '🇺🇸',
    },
    {
        'org':   'Freedom House',
        'title': 'Freedom in the World — China',
        'url':   'https://freedomhouse.org/country/china/freedom-world/2024',
        'year':  '2024',
        'icon':  '🗽',
    },
    {
        'org':   'ASPI',
        'title': 'Xinjiang Data Project',
        'url':   'https://xjdp.aspi.org.au/',
        'year':  '2022',
        'icon':  '🛰️',
    },
]

# ============================================
# REDIS HELPERS
# ============================================

def _redis_get(key):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return None
    try:
        resp = requests.get(
            f"{UPSTASH_REDIS_URL}/get/{key}",
            headers={"Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}"},
            timeout=5
        )
        data = resp.json()
        if data.get('result'):
            return json.loads(data['result'])
    except Exception as e:
        print(f"[China Humanitarian] Redis GET error: {str(e)[:80]}")
    return None


def _redis_set(key, value, ttl=None):
    if not UPSTASH_REDIS_URL or not UPSTASH_REDIS_TOKEN:
        return False
    try:
        payload = json.dumps(value, default=str)
        cmd = ["SET", key, payload]
        if ttl:
            cmd += ["EX", ttl]
        requests.post(
            UPSTASH_REDIS_URL,
            headers={
                "Authorization": f"Bearer {UPSTASH_REDIS_TOKEN}",
                "Content-Type": "application/json"
            },
            json=cmd,
            timeout=5
        )
        return True
    except Exception as e:
        print(f"[China Humanitarian] Redis SET error: {str(e)[:80]}")
    return False


# ============================================
# MODULE 1 — RELIEFWEB NATURAL DISASTERS
# ============================================

def _fetch_reliefweb_disasters():
    """Fetch recent natural disaster / displacement reports for China from ReliefWeb API."""
    disasters = []
    try:
        params = {
            'appname':                 'asifah-analytics',
            'filter[operator]':        'AND',
            'filter[conditions][0][field]':  'country.iso3',
            'filter[conditions][0][value]':  'CHN',
            'filter[conditions][1][field]':  'theme.name',
            'filter[conditions][1][value]':  'Disaster Management',
            'sort[0][field]':          'date.created',
            'sort[0][direction]':      'desc',
            'limit':                   10,
            'fields[include][0]':      'title',
            'fields[include][1]':      'date',
            'fields[include][2]':      'source',
            'fields[include][3]':      'theme',
            'fields[include][4]':      'url',
            'fields[include][5]':      'body-html',
        }
        resp = requests.get(RELIEFWEB_API, params=params, timeout=(5, 15))
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get('data', []):
                fields = item.get('fields', {})
                disasters.append({
                    'title':   fields.get('title', ''),
                    'date':    fields.get('date', {}).get('created', ''),
                    'source':  fields.get('source', [{}])[0].get('name', 'ReliefWeb') if fields.get('source') else 'ReliefWeb',
                    'url':     fields.get('url', ''),
                    'themes':  [t.get('name', '') for t in fields.get('theme', [])],
                })
            print(f"[China Humanitarian] ReliefWeb disasters: {len(disasters)} reports")
        else:
            print(f"[China Humanitarian] ReliefWeb HTTP {resp.status_code}")
    except Exception as e:
        print(f"[China Humanitarian] ReliefWeb error: {str(e)[:80]}")

    # Also try a broader China query if disaster-specific returns nothing
    if not disasters:
        try:
            params2 = {
                'appname':           'asifah-analytics',
                'filter[field]':     'country.iso3',
                'filter[value]':     'CHN',
                'sort[0][field]':    'date.created',
                'sort[0][direction]':'desc',
                'limit':             8,
                'fields[include][0]':'title',
                'fields[include][1]':'date',
                'fields[include][2]':'source',
                'fields[include][3]':'url',
            }
            resp2 = requests.get(RELIEFWEB_API, params=params2, timeout=(5, 15))
            if resp2.status_code == 200:
                for item in resp2.json().get('data', []):
                    fields = item.get('fields', {})
                    disasters.append({
                        'title':  fields.get('title', ''),
                        'date':   fields.get('date', {}).get('created', ''),
                        'source': fields.get('source', [{}])[0].get('name', 'ReliefWeb') if fields.get('source') else 'ReliefWeb',
                        'url':    fields.get('url', ''),
                        'themes': [],
                    })
                print(f"[China Humanitarian] ReliefWeb (broad): {len(disasters)} reports")
        except Exception as e:
            print(f"[China Humanitarian] ReliefWeb broad error: {str(e)[:80]}")

    return disasters


# ============================================
# MODULE 2 — HUMAN RIGHTS MONITORING (LIVE)
# ============================================

def _fetch_hrw_rss():
    """Fetch HRW RSS feed and filter for China/Xinjiang/Tibet/HK articles."""
    articles = []
    china_keywords = [
        'china', 'xinjiang', 'uyghur', 'tibet', 'hong kong',
        'uighur', 'tibetan', 'prc', 'ccp',
    ]
    try:
        resp = requests.get(
            'https://www.hrw.org/rss/news',
            timeout=(5, 15),
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall('.//item')[:50]:
                title_el = item.find('title')
                link_el  = item.find('link')
                desc_el  = item.find('description')
                pub_el   = item.find('pubDate')
                if not title_el or not title_el.text:
                    continue
                title = title_el.text.lower()
                desc  = (desc_el.text or '').lower() if desc_el is not None else ''
                if any(kw in title or kw in desc for kw in china_keywords):
                    articles.append({
                        'title':       title_el.text,
                        'url':         link_el.text if link_el is not None else '',
                        'description': desc_el.text if desc_el is not None else '',
                        'publishedAt': pub_el.text if pub_el is not None else '',
                        'source':      {'name': 'Human Rights Watch'},
                        'language':    'en',
                        'category':    'human_rights',
                    })
            print(f"[China Humanitarian] HRW RSS: {len(articles)} China articles")
        else:
            print(f"[China Humanitarian] HRW RSS HTTP {resp.status_code}")
    except Exception as e:
        print(f"[China Humanitarian] HRW RSS error: {str(e)[:80]}")
    return articles


def _fetch_rfa_rss():
    """Fetch Radio Free Asia feeds for Uyghur and Tibet coverage."""
    articles = []
    feeds = [
        ('https://www.rfa.org/english/news/uyghur/rss2',  'RFA Uyghur'),
        ('https://www.rfa.org/english/news/tibet/rss2',   'RFA Tibet'),
        ('https://www.rfa.org/english/news/china/rss2',   'RFA China'),
    ]
    for url, label in feeds:
        try:
            resp = requests.get(url, timeout=(5, 15),
                                headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                count = 0
                for item in root.findall('.//item')[:15]:
                    title_el = item.find('title')
                    link_el  = item.find('link')
                    desc_el  = item.find('description')
                    pub_el   = item.find('pubDate')
                    if title_el and title_el.text:
                        articles.append({
                            'title':       title_el.text.strip(),
                            'url':         link_el.text if link_el is not None else '',
                            'description': (desc_el.text or '')[:200] if desc_el is not None else '',
                            'publishedAt': pub_el.text if pub_el is not None else '',
                            'source':      {'name': label},
                            'language':    'en',
                            'category':    'human_rights',
                        })
                        count += 1
                print(f"[China Humanitarian] {label}: {count} articles")
            else:
                print(f"[China Humanitarian] {label} HTTP {resp.status_code}")
            time.sleep(0.3)
        except Exception as e:
            print(f"[China Humanitarian] {label} error: {str(e)[:80]}")
    return articles


def _fetch_google_news_hr():
    """Fetch Google News RSS for human rights keyword queries."""
    articles = []
    queries = [
        ('Xinjiang Uyghur detention human rights 2026', 'GNews:Xinjiang'),
        ('Tibet protest crackdown China 2026',           'GNews:Tibet'),
        ('Hong Kong National Security Law arrests 2026', 'GNews:HongKong'),
        ('China forced labor supply chain sanctions',    'GNews:ForcedLabor'),
    ]
    for query, label in queries:
        try:
            encoded = urllib.parse.quote(query)
            url  = f"https://news.google.com/rss/search?q={encoded}&hl=en&gl=US&ceid=US:en"
            resp = requests.get(url, timeout=(5, 12),
                                headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                root  = ET.fromstring(resp.content)
                count = 0
                for item in root.findall('.//item')[:10]:
                    title_el = item.find('title')
                    link_el  = item.find('link')
                    pub_el   = item.find('pubDate')
                    if title_el and title_el.text:
                        articles.append({
                            'title':       title_el.text.strip(),
                            'url':         link_el.text if link_el is not None else '',
                            'description': title_el.text.strip(),
                            'publishedAt': pub_el.text if pub_el is not None else '',
                            'source':      {'name': label},
                            'language':    'en',
                            'category':    'human_rights',
                        })
                        count += 1
                print(f"[China Humanitarian] {label}: {count} articles")
            time.sleep(0.3)
        except Exception as e:
            print(f"[China Humanitarian] GNews {label} error: {str(e)[:80]}")
    return articles


def _fetch_newsapi_hr():
    """NewsAPI fallback for human rights articles."""
    if not NEWSAPI_KEY:
        return []
    articles = []
    queries = [
        'Xinjiang Uyghur China human rights 2026',
        'Tibet China protest crackdown',
        'Hong Kong National Security Law',
    ]
    for query in queries:
        try:
            from_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
            resp = requests.get(
                'https://newsapi.org/v2/everything',
                params={
                    'q': query, 'from': from_date,
                    'sortBy': 'publishedAt', 'language': 'en',
                    'pageSize': 10, 'apiKey': NEWSAPI_KEY,
                },
                timeout=(5, 15)
            )
            if resp.status_code == 200:
                for a in resp.json().get('articles', []):
                    articles.append({
                        'title':       a.get('title', ''),
                        'description': a.get('description', '') or '',
                        'url':         a.get('url', ''),
                        'publishedAt': a.get('publishedAt', ''),
                        'source':      {'name': a.get('source', {}).get('name', 'NewsAPI')},
                        'language':    'en',
                        'category':    'human_rights',
                    })
            time.sleep(0.3)
        except Exception as e:
            print(f"[China Humanitarian] NewsAPI error: {str(e)[:80]}")
    print(f"[China Humanitarian] NewsAPI: {len(articles)} articles")
    return articles


# ============================================
# ALERT SIGNAL DETECTION
# ============================================

ALERT_KEYWORDS = {
    'xinjiang': [
        'xinjiang crackdown', 'uyghur detained', 'uyghur arrested',
        'xinjiang new camps', 'xinjiang expansion', 'uyghur forced',
        'xinjiang sanctions', 'uyghur genocide', 'uflpa enforcement',
    ],
    'tibet': [
        'tibet protest', 'tibet crackdown', 'tibet self-immolation',
        'dalai lama', 'tibet monastery', 'tibet arrested',
        'lhasa protest', 'tibet unrest',
    ],
    'hong_kong': [
        'hong kong arrested', 'hong kong nsl', 'hong kong national security',
        'hong kong protest', 'hong kong crackdown', 'hong kong sentenced',
        'hong kong opposition', 'hong kong media',
    ],
    'forced_labor': [
        'uflpa', 'xinjiang cotton', 'forced labor china',
        'supply chain xinjiang', 'uyghur forced labor',
        'xinjiang solar', 'xinjiang polysilicon',
    ],
}


def _detect_alerts(articles):
    """Scan articles for alert-level signals. Returns list of active alerts."""
    alerts = []
    matched_keys = set()

    for article in articles:
        title   = (article.get('title', '') or '').lower()
        desc    = (article.get('description', '') or '').lower()
        text    = f"{title} {desc}"

        for category, keywords in ALERT_KEYWORDS.items():
            for kw in keywords:
                if kw in text and f"{category}:{kw}" not in matched_keys:
                    matched_keys.add(f"{category}:{kw}")
                    alerts.append({
                        'category': category,
                        'keyword':  kw,
                        'headline': article.get('title', ''),
                        'url':      article.get('url', ''),
                        'source':   article.get('source', {}).get('name', ''),
                        'date':     article.get('publishedAt', ''),
                    })

    # Deduplicate by category — keep most recent per category
    by_category = {}
    for alert in alerts:
        cat = alert['category']
        if cat not in by_category:
            by_category[cat] = alert

    result = list(by_category.values())
    print(f"[China Humanitarian] Active alert signals: {len(result)} categories")
    return result


# ============================================
# MAIN SCAN
# ============================================

def run_china_humanitarian_scan():
    """Full humanitarian scan — disasters, human rights monitoring, static reference."""
    scan_start = time.time()
    print(f"\n[China Humanitarian] Starting scan at {datetime.now(timezone.utc).isoformat()}")

    # Module 1 — Natural disasters
    disasters = _fetch_reliefweb_disasters()

    # Module 2 — Human rights live monitoring
    hr_articles = []
    hr_articles.extend(_fetch_hrw_rss())
    hr_articles.extend(_fetch_rfa_rss())
    hr_articles.extend(_fetch_google_news_hr())
    if len(hr_articles) < 10:
        hr_articles.extend(_fetch_newsapi_hr())

    # Deduplicate HR articles
    seen_urls = set()
    deduped_hr = []
    for a in hr_articles:
        url = (a.get('url', '') or '').split('?')[0].rstrip('/')
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        deduped_hr.append(a)
    hr_articles = deduped_hr
    print(f"[China Humanitarian] Total HR articles after dedup: {len(hr_articles)}")

    # Detect alerts
    alerts = _detect_alerts(hr_articles)

    # Humanitarian signal level (0-3: none/low/medium/high)
    if len(alerts) >= 3:   hr_signal = 3
    elif len(alerts) >= 2: hr_signal = 2
    elif len(alerts) >= 1: hr_signal = 1
    else:                   hr_signal = 0

    scan_time = round(time.time() - scan_start, 1)

    result = {
        'success':           True,
        'scanned_at':        datetime.now(timezone.utc).isoformat(),
        'scan_time_seconds': scan_time,

        # Module 1 — Disasters
        'disasters':         disasters,
        'disaster_count':    len(disasters),

        # Module 2 — HR monitoring
        'hr_articles':       hr_articles[:30],
        'hr_article_count':  len(hr_articles),
        'alerts':            alerts,
        'hr_signal_level':   hr_signal,

        # Module 3 — Static reference
        'static_data':       STATIC_REFERENCE_DATA,
        'annual_reports':    ANNUAL_REPORT_LINKS,

        # Meta
        'total_articles':    len(hr_articles),
        'version':           '1.0.0-china-humanitarian',
    }

    # Cache to Redis
    _redis_set(CACHE_KEY, result, ttl=CACHE_TTL)

    # Cache disasters separately for quick frontend load
    _redis_set(DISASTER_CACHE_KEY, {
        'disasters':   disasters,
        'scanned_at':  result['scanned_at'],
    }, ttl=CACHE_TTL)

    print(f"[China Humanitarian] Scan complete in {scan_time}s | "
          f"Disasters: {len(disasters)} | HR articles: {len(hr_articles)} | "
          f"Alerts: {len(alerts)} | Signal: L{hr_signal}")
    return result


# ============================================
# BACKGROUND REFRESH
# ============================================

def _background_loop():
    print("[China Humanitarian] Background thread started (12h cycle)")
    time.sleep(360)   # 6 min stagger after boot — after stability module
    while True:
        try:
            run_china_humanitarian_scan()
        except Exception as e:
            print(f"[China Humanitarian] Background scan error: {str(e)[:200]}")
        time.sleep(SCAN_INTERVAL_HOURS * 3600)


# ============================================
# FLASK ENDPOINT REGISTRATION
# ============================================

def register_china_humanitarian_endpoints(app):
    """Register China humanitarian endpoints on the Flask app."""

    @app.route('/api/china/humanitarian', methods=['GET'])
    def api_china_humanitarian():
        """
        Full China humanitarian data — disasters, HR monitoring, static reference.
        ?force=true to bypass cache.
        """
        force = request.args.get('force', 'false').lower() == 'true'

        if not force:
            cached = _redis_get(CACHE_KEY)
            if cached:
                cached['from_cache'] = True
                return jsonify(cached)

        global _humanitarian_running
        with _humanitarian_lock:
            if _humanitarian_running:
                cached = _redis_get(CACHE_KEY)
                if cached:
                    cached['from_cache'] = True
                    cached['scan_in_progress'] = True
                    return jsonify(cached)
                return jsonify({'success': False, 'error': 'Scan in progress'}), 202
            _humanitarian_running = True

        try:
            result = run_china_humanitarian_scan()
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)[:200]}), 500
        finally:
            with _humanitarian_lock:
                _humanitarian_running = False

    @app.route('/api/china/humanitarian/summary', methods=['GET'])
    def api_china_humanitarian_summary():
        """Lightweight summary for frontend card — alerts + signal level only."""
        cached = _redis_get(CACHE_KEY)
        if not cached:
            return jsonify({
                'success': False,
                'error':   'No data yet — run /api/china/humanitarian?force=true'
            }), 404
        return jsonify({
            'success':          True,
            'scanned_at':       cached.get('scanned_at'),
            'hr_signal_level':  cached.get('hr_signal_level', 0),
            'alerts':           cached.get('alerts', []),
            'hr_article_count': cached.get('hr_article_count', 0),
            'disaster_count':   cached.get('disaster_count', 0),
            'annual_reports':   cached.get('annual_reports', ANNUAL_REPORT_LINKS),
            'static_data':      cached.get('static_data', STATIC_REFERENCE_DATA),
            'version':          '1.0.0-china-humanitarian',
        })

    @app.route('/api/china/humanitarian/disasters', methods=['GET'])
    def api_china_humanitarian_disasters():
        """ReliefWeb natural disaster reports for China."""
        cached = _redis_get(DISASTER_CACHE_KEY)
        if not cached:
            # Try to pull from full cache
            full = _redis_get(CACHE_KEY)
            if full:
                return jsonify({
                    'success':    True,
                    'scanned_at': full.get('scanned_at'),
                    'disasters':  full.get('disasters', []),
                    'count':      full.get('disaster_count', 0),
                })
            return jsonify({'success': False, 'error': 'No disaster data yet'}), 404
        return jsonify({
            'success':    True,
            'scanned_at': cached.get('scanned_at'),
            'disasters':  cached.get('disasters', []),
            'count':      len(cached.get('disasters', [])),
        })

    @app.route('/api/china/humanitarian/hr-articles', methods=['GET'])
    def api_china_humanitarian_hr_articles():
        """Live HR monitoring articles for tabbed display."""
        cached = _redis_get(CACHE_KEY)
        if not cached:
            return jsonify({'success': False, 'error': 'No data yet'}), 404
        return jsonify({
            'success':     True,
            'scanned_at':  cached.get('scanned_at'),
            'articles':    cached.get('hr_articles', []),
            'count':       cached.get('hr_article_count', 0),
            'alerts':      cached.get('alerts', []),
        })

    # Start background thread
    bg = threading.Thread(target=_background_loop, daemon=True)
    bg.start()

    print("[China Humanitarian] Endpoints registered: "
          "/api/china/humanitarian, /api/china/humanitarian/summary, "
          "/api/china/humanitarian/disasters, /api/china/humanitarian/hr-articles")
