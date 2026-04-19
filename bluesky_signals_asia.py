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
    # v1.0.1 (April 2026) — Handle list pruned based on live-scan evidence.
    # Previous version had ~15 handles returning HTTP 400. This version keeps
    # ONLY handles confirmed to return 200 OK in production scans, plus a
    # small number of well-known accounts likely to work.
    #
    # Lessons learned from first deployment:
    #   - govmirrors has SOME accounts but not all (potus, secdef, centcom,
    #     indopacom, mndkorea all return 400 — they don't exist there)
    #   - Analyst handles I guessed at (adam-weinstein, anildayal) don't exist
    #   - Official "native" Bluesky handles we assumed (osintdefender) don't exist
    #   - Custom domain handles work IF the domain is configured
    #
    # Rule going forward: only add a handle after verifying it returns 200 OK.

    # ── CONFIRMED WORKING (returned 200 OK in production scans) ──
    ('state-department.bsky.social',   1.0,  ['*'],
        'US State Department (official native) — travel advisories, diplomatic'),
    ('statedept.govmirrors.com',       0.9,  ['*'],
        'StateDept (X mirror via govmirrors) — backup to native'),
    ('realdonaldtrump.govmirrors.com', 1.2,  ['*'],
        'Trump (X mirror) — Iran/China/DPRK/Pakistan statements'),
    ('wartranslated.bsky.social',      0.85, ['*'],
        'WarTranslated — Russia/DPRK/global military translation'),
]

# v1.0.1 — Aspirational handles to verify manually before adding:
# - @rferl.org (Radio Free Europe/Radio Liberty)
# - @voiceofamerica.bsky.social (or custom domain)
# - Japan MOFA, ROK MND, Taiwan MND — verify existence on Bluesky directly
# - NK News, 38 North, Daily NK — verify if they've migrated to Bluesky
#
# To check a handle before adding: visit https://bsky.app/profile/{handle}
# and confirm the account exists. Then add with confidence.


# v1.0.1 — Handle failure cache to avoid re-requesting known-dead handles.
# When a handle returns 400 or 404, we remember it for 1 hour. This prevents
# the 10+ dead handles from each eating a 500ms round-trip on every scan,
# saving ~5 seconds per scan across 8 countries.
_BLUESKY_HANDLE_FAILURES = {}  # handle -> unix_timestamp_retry_after
_BLUESKY_HANDLE_FAILURE_COOLDOWN = 60 * 60  # 1 hour


def fetch_bluesky_account(handle, weight=1.0, limit=20, timeout=BLUESKY_TIMEOUT):
    """
    Fetch recent posts from a single Bluesky account.

    Uses the public AppView API — no authentication required.
    Returns list of article dicts matching the Asia backend schema.

    On 400/404 (handle doesn't exist) → caches failure for 1h, returns []
    On 429 (rate limit) → logs and returns []
    On network/parse error → logs and returns []
    """
    # ── v1.0.1 — Skip handles we've already confirmed are dead ──
    now_ts = time.time()
    retry_after = _BLUESKY_HANDLE_FAILURES.get(handle, 0)
    if retry_after > now_ts:
        # Silently skip — don't spam logs for every scan
        return []

    headers = {
        'User-Agent': 'AsifahAnalytics-Asia/1.0 (+https://asifahanalytics.com)',
        'Accept': 'application/json',
    }
    params = {'actor': handle, 'limit': limit}

    try:
        resp = requests.get(BLUESKY_API, headers=headers, params=params, timeout=timeout)

        if resp.status_code == 400:
            # 400 usually means "invalid handle" — same as 404 for our purposes
            print(f'[Bluesky Asia] @{handle}: HTTP 400 (invalid handle) — caching failure for 1h')
            _BLUESKY_HANDLE_FAILURES[handle] = now_ts + _BLUESKY_HANDLE_FAILURE_COOLDOWN
            return []
        if resp.status_code == 404:
            print(f'[Bluesky Asia] @{handle}: handle not found (404) — caching failure for 1h')
            _BLUESKY_HANDLE_FAILURES[handle] = now_ts + _BLUESKY_HANDLE_FAILURE_COOLDOWN
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
