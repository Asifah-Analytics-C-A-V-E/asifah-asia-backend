"""
========================================
BLUESKY — Asia-Pacific Signal Monitor (v1.0.0)
========================================
Drop-in Asia-Pacific companion to bluesky_signals_europe.py (April 2026).

Addresses the Asia backend's 13/18 Telegram flood-wait problem by
providing an alternative path to monitor executive/government statements
relevant to Asia-Pacific conflict signals.

Bluesky's public AppView API (https://public.api.bsky.app) requires NO auth
and exposes a stable JSON endpoint at:
    /xrpc/app.bsky.feed.getAuthorFeed?actor={handle}&limit={N}

We track two types of accounts:
  1. Native Bluesky accounts — official gov/institutional accounts that
     migrated to Bluesky (State, POTUS, Pentagon, etc.)
  2. govmirrors.com mirrors — volunteer-run project that mirrors X posts
     to Bluesky for government accounts that haven't migrated (e.g., DPRK
     has no Bluesky presence; CENTCOM, INDOPACOM primarily on X).

Architecture mirrors bluesky_signals_europe.py exactly:
  - BLUESKY_ACCOUNTS_ASIA    (replaces Europe-specific list)
  - fetch_bluesky_account()  (identical to Europe version)
  - fetch_bluesky_for_target()  (Asia target keys instead of Europe)

Returns the same article dict shape so downstream Asia backend scoring
works unchanged.
"""

import requests
import time
from datetime import datetime, timezone, timedelta

# Public AppView — no auth required for read-only
BLUESKY_API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"

# Timeout for individual account fetches (seconds)
BLUESKY_TIMEOUT = 8

# ────────────────────────────────────────────────────────────────
# ASIA-PACIFIC ACCOUNT DIRECTORY
# ────────────────────────────────────────────────────────────────
# (handle, weight, targets[], description)
#
# handle:  Bluesky handle WITHOUT the @ prefix
#          e.g. "state-department.bsky.social"
#          govmirrors: "potus.govmirrors.com" (mirror of @POTUS)
#
# weight:  1.2 = head of state / direct govt statement
#          1.1 = minister / senior official / MFA
#          1.0 = institutional / military command (INDOPACOM, CENTCOM)
#          0.9 = analytical / OSINT / regional specialist
#          0.85 = partner/allied defense accounts
#
# targets: list of Asia backend target keys this account is relevant to.
#          Asia backend targets: afghanistan, china, india, japan,
#          north_korea, pakistan, south_korea, taiwan
#          Use ['*'] for all targets (global scope / USG).
# ────────────────────────────────────────────────────────────────
BLUESKY_ACCOUNTS_ASIA = [
    # ── US Government — native Bluesky (global scope) ───────────
    ('state-department.bsky.social',  1.0, ['*'],
        'US State Department (official) — travel advisories, diplomatic signals'),

    # ── US Government — govmirrors.com (X-sourced) ──────────────
    # INDOPACOM and regional commands are primarily on X; mirrors enable
    # monitoring without auth. If a mirror goes dark, comment it out.
    ('potus.govmirrors.com',          1.2, ['*'],
        'POTUS (X mirror) — White House executive statements on Asia'),
    ('realdonaldtrump.govmirrors.com', 1.2, ['*'],
        'Trump (X mirror) — Iran/China/DPRK/Pakistan statements'),
    ('secdef.govmirrors.com',          1.1, ['*'],
        'US SecDef (X mirror) — deployment and posture signals'),
    ('secrubio.govmirrors.com',        1.1, ['*'],
        'US SecState Rubio (X mirror) — Asia policy'),
    ('statedept.govmirrors.com',       0.9, ['*'],
        'StateDept (X mirror) — redundant with native, kept as backup'),

    # ── Regional Combatant Commands ─────────────────────────────
    ('indopacom.govmirrors.com',       1.0, ['china', 'taiwan', 'south_korea', 'japan', 'north_korea'],
        'US INDOPACOM (X mirror) — Pacific military posture'),
    ('centcom.govmirrors.com',         1.0, ['afghanistan', 'pakistan'],
        'US CENTCOM (X mirror) — Afghan/Pakistan/Iran AOR'),

    # ── DPRK-specific analytical accounts ───────────────────────
    # NK News, 38 North, and NK Leadership Watch are the gold standard
    # for DPRK OSINT. Most have native Bluesky presence.
    ('nknewsorg.bsky.social',          0.95, ['north_korea'],
        'NK News — DPRK specialist, breaking news on missile tests'),
    ('38northorg.bsky.social',         0.95, ['north_korea'],
        '38 North (Stimson Center) — DPRK analysis, satellite imagery'),
    ('nkleadershipwatch.bsky.social',  0.9, ['north_korea'],
        'NK Leadership Watch — Kim family activity tracking'),
    ('dailynkenglish.bsky.social',     0.9, ['north_korea'],
        'Daily NK (English) — defector-sourced DPRK reporting'),

    # ── China / Taiwan analytical accounts ──────────────────────
    ('plaprimer.bsky.social',          0.9, ['china', 'taiwan'],
        'PLA Primer — PLA analysis (if native)'),
    ('chinatalk.bsky.social',          0.85, ['china', 'taiwan'],
        'ChinaTalk (Jordan Schneider) — PRC/tech/security commentary'),
    ('sinocism.bsky.social',           0.85, ['china'],
        'Sinocism (Bill Bishop) — China watcher, Xi/PRC statements'),

    # ── Pakistan / Afghanistan analytical ───────────────────────
    ('adam-weinstein.bsky.social',     0.85, ['pakistan', 'afghanistan'],
        'Adam Weinstein (Quincy) — Pakistan/Afghan analyst'),
    ('steveinmans.bsky.social',        0.85, ['afghanistan', 'pakistan'],
        'Steve Inskeep / NPR — Afghan-Pak conflict coverage (if native)'),

    # ── India / Pakistan / South Asia ───────────────────────────
    ('anildayal.bsky.social',          0.85, ['india', 'pakistan'],
        'India-Pakistan analyst (if native)'),

    # ── OSINT aggregators (global, high signal) ─────────────────
    ('osintdefender.bsky.social',      0.9, ['*'],
        'OSINT Defender — global conflict monitoring'),
    ('wartranslated.bsky.social',      0.85, ['*'],
        'WarTranslated — Russia/global military translation'),

    # ── Japan / South Korea partner statements ──────────────────
    # Most East Asian government accounts are on X; mirrors only where
    # the account actually exists in govmirrors.
    ('mofa-japan.govmirrors.com',      0.9, ['china', 'north_korea', 'taiwan', 'japan'],
        'Japan MOFA (X mirror) — East China Sea, DPRK, Taiwan'),

    # ── Taiwan government statements ────────────────────────────
    ('taiwanmnd.govmirrors.com',       0.95, ['taiwan', 'china'],
        'Taiwan MND (X mirror) — daily ADIZ violation reports'),
    ('mofa-taiwan.govmirrors.com',     0.9, ['taiwan', 'china'],
        'Taiwan MOFA (X mirror) — diplomatic response to PRC pressure'),

    # ── DPRK / South Korea inter-Korean signals ─────────────────
    # South Korea's MND and MOFA are on X; mirrors enable tracking.
    ('mndkorea.govmirrors.com',        0.9, ['north_korea', 'south_korea'],
        'ROK MND (X mirror) — DPRK missile tracking, inter-Korean'),
]


def fetch_bluesky_account(handle, weight=1.0, limit=20, timeout=BLUESKY_TIMEOUT):
    """
    Fetch recent posts from a single Bluesky account.

    Uses the public AppView API — no authentication required.
    Returns list of article dicts matching the Asia backend schema.

    On 404 (handle doesn't exist) → logs and returns []
    On 429 (rate limit) → logs and returns []
    On network/parse error → logs and returns []
    """
    headers = {
        'User-Agent': 'AsifahAnalytics-Asia/1.0 (+https://asifahanalytics.com)',
        'Accept': 'application/json',
    }
    params = {'actor': handle, 'limit': limit}

    try:
        resp = requests.get(BLUESKY_API, headers=headers, params=params, timeout=timeout)

        if resp.status_code == 404:
            # 404 means handle doesn't exist. Log once — we won't retry.
            print(f'[Bluesky Asia] @{handle}: handle not found (404) — consider removing from list')
            return []
        if resp.status_code == 429:
            print(f'[Bluesky Asia] @{handle}: rate-limited (429) — backing off')
            return []
        if resp.status_code != 200:
            print(f'[Bluesky Asia] @{handle}: HTTP {resp.status_code}')
            return []

        data = resp.json()
        feed = data.get('feed', [])
        articles = []

        for item in feed:
            post = item.get('post', {})
            record = post.get('record', {})
            author = post.get('author', {})

            text = record.get('text', '') or ''
            if not text.strip():
                continue

            # Bluesky timestamps are ISO-8601 UTC
            pub = record.get('createdAt') or post.get('indexedAt') or ''

            # Construct canonical post URL from DID + rkey
            # Format: https://bsky.app/profile/{handle}/post/{rkey}
            post_uri = post.get('uri', '')
            rkey = post_uri.rsplit('/', 1)[-1] if post_uri else ''
            url = f'https://bsky.app/profile/{handle}/post/{rkey}' if rkey else f'https://bsky.app/profile/{handle}'

            # Description = first 400 chars of text (Bluesky is short-form)
            desc = text[:400]

            articles.append({
                'title':       text[:200],
                'description': desc,
                'url':         url,
                'publishedAt': pub,
                'source':      {'name': f'Bluesky @{handle}'},
                'content':     text[:500],
                'language':    'en',
                'source_weight_override': weight,
                '_bluesky_author':  author.get('displayName', handle),
            })

        if articles:
            print(f'[Bluesky Asia] @{handle}: {len(articles)} posts')
        return articles

    except requests.exceptions.Timeout:
        print(f'[Bluesky Asia] @{handle}: timeout after {timeout}s')
        return []
    except Exception as e:
        print(f'[Bluesky Asia] @{handle}: {str(e)[:80]}')
        return []


def fetch_bluesky_for_target(target, days=7, max_posts_per_account=20):
    """
    Fetch Bluesky posts relevant to a specific Asia-Pacific target.

    Filters by:
      - target key (account must have '*' or target in its targets list)
      - recency (post must be within last {days} days)
      - deduplication (URL-based)

    Returns list of article dicts ready for downstream scoring.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    all_posts = []
    seen_urls = set()
    accounts_queried = 0

    for handle, weight, targets, desc in BLUESKY_ACCOUNTS_ASIA:
        # Skip accounts not relevant to this target
        if '*' not in targets and target not in targets:
            continue

        accounts_queried += 1
        posts = fetch_bluesky_account(handle, weight=weight, limit=max_posts_per_account)

        for p in posts:
            if p['url'] in seen_urls:
                continue

            # Recency filter
            try:
                pub_str = p['publishedAt'].replace('Z', '+00:00')
                pub = datetime.fromisoformat(pub_str)
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if pub < cutoff:
                    continue
            except Exception:
                # If date parsing fails, keep the post (better than losing signal)
                pass

            seen_urls.add(p['url'])
            all_posts.append(p)

        # Light politeness delay — Bluesky public API is fast but we
        # don't want to look abusive
        time.sleep(0.2)

    print(f'[Bluesky Asia] {target}: {len(all_posts)} posts from {accounts_queried} accounts queried')
    return all_posts
