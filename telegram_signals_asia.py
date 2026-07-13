"""
Telegram Signal Source for Asia-Pacific Conflict Dashboard
v1.0.0 — March 2026

Bridges Telethon (async) with Flask (sync) to pull messages
from monitored Telegram channels and feed them into the
Asia-Pacific conflict probability scanner.

Channels monitored:
- Taiwan Strait / PLA activity watchers
- North Korea missile/nuclear monitoring
- Afghanistan/Taliban/ISIS-K reporting
- Pakistan military and border conflict
- India-Pakistan / India-China border
- Japan/South Korea defense
- OSINT aggregators covering Indo-Pacific theatre

Usage:
    from telegram_signals_asia import fetch_asia_telegram_signals
    messages = fetch_asia_telegram_signals(hours_back=24)
    # Returns list of dicts with 'title', 'url', 'published', 'source' keys
"""

import os
import asyncio
import base64
from datetime import datetime, timezone, timedelta

# Telethon import with graceful fallback
try:
    from telethon import TelegramClient
    from telethon.errors import FloodWaitError, UsernameInvalidError, UsernameNotOccupiedError
    from telethon.tl.functions.messages import GetHistoryRequest
    TELETHON_AVAILABLE = True
except ImportError:
    TELETHON_AVAILABLE = False
    print("[Telegram Asia] ⚠️ telethon not installed — Telegram signals disabled")


# ========================================
# CONFIGURATION
# ========================================

TELEGRAM_API_ID = os.environ.get('TELEGRAM_API_ID')
TELEGRAM_API_HASH = os.environ.get('TELEGRAM_API_HASH')
TELEGRAM_PHONE = os.environ.get('TELEGRAM_PHONE')
SESSION_NAME = 'asifah_session'

# Core Asia-Pacific conflict channels — verified working March 2026
ASIA_CHANNELS = [
    # OSINT aggregators — high volume, high signal
    'IntelSlava',              # Intel Slava — broad OSINT incl. Indo-Pacific
    'OSINTdefender',           # OSINT Defender — high signal, covers Asia
    'ClashReport',             # Clash Report — global conflict monitoring
    'WarMonitors',             # War Monitor — multilingual conflict
    'C_Military1',             # Military conflict OSINT

    # Afghanistan / Taliban / ISIS-K
    'AfghanistanInternational', # Afghanistan Intl — exile media, active
    'kabulnow',                # Kabul Now — Afghan ground reporting
    'AfghanistanTaliban',      # Taliban activity monitoring
    'AfghanOSINT',             # Afghan OSINT aggregator

    # Pakistan
    'GeoNews',                 # Geo News Pakistan
    'dawn_official',           # Dawn — Pakistan's paper of record
    'thenews_intl',            # The News International
    'ARYNEWSOfficial',         # ARY News — Pakistan

    # Japan
    'NHKWorldNews',            # NHK World — Japan public broadcaster

    # South Korea
    'yonhapnewsagency',        # Yonhap News Agency — South Korea wire

    # General English news
    'BBCBreaking',             # BBC Breaking News
    'HMIntelligence',          # HM Intelligence -- OSINT aggregator, China coverage
]

# Extended channels — deeper regional coverage (verified or best-guess replacements)
EXTENDED_ASIA_CHANNELS = [
    # North Korea — replacements for dead nknewsorg/northkoreatech
    'NorthKoreaNews',          # NK news aggregator

    # Taiwan / China
    'Taiwan_News',             # Taiwan news
    'StraitsTimesSG',          # Straits Times — Singapore, covers Taiwan Strait
    'scmpnews',                # South China Morning Post

    # India / Pakistan / Afghanistan
    'thenewsinternational',    # The News International — Pakistan
    'PIB_India',               # Press Information Bureau — official GoI press release wire

    # ── v1.1 — Pakistan-specific extended (Apr 2026) ──
    'ISPR_Official',           # Inter-Services Public Relations (Army)
    'PakistanArmy',            # Pakistan Army channel
    'KashmirOSINT',            # Kashmir OSINT — LoC / militant tracking
    'BalochOSINT',             # Baloch OSINT — BLA / Gwadar tracking
    'TTPMonitor',              # TTP attack tracker (best-guess; verify)
    'PakistanDefence',          # Pakistan Defence forum signals

    # Myanmar

    # Broader Indo-Pacific
]


# ── DPRK channel list (v1.1.0 — Jul 13 2026) ──
# Used by rhetoric_tracker_dprk.py (mode='actor' tempo target).
#
# CURATION LOGIC — and the discipline here is the OPPOSITE of Poland's:
#
# Poland runs mode='tape' and its channel list is deliberately NARROW, because
# Russia never claims and war-OSINT pollution would corrupt the tempo baseline.
#
# The DPRK runs mode='actor', and the thing we are measuring is KCNA'S OWN
# CADENCE. So the list must be weighted toward DPRK-SPECIFIC monitors and
# state-media mirrors, not toward general conflict OSINT. A channel that posts
# about Ukraine forty times a day and Pyongyang twice a week will not corrupt
# the count -- because we count Pyongyang statements, not channel volume -- but
# it will drown the corpus-health denominator in noise and make the sources_live
# figure meaningless.
#
# HARD RULE INHERITED FROM HUNGARY v1.1.0: no generic war-OSINT feeds
# (IntelSlava, WarMonitors, OSINTdefender). They inflated Hungary's score 92%
# with Ukraine-war leakage. For a tempo target the cost is worse than an
# inflated score -- a polluted baseline is worse than no baseline, because every
# future deviation call is measured against it.
DPRK_CHANNELS = [
    # ── DPRK-specific monitors (the core — these ARE the corpus) ──
    'kcnawatch',           # KCNA Watch — the state-media mirror. THE tempo source.
    'nknewsorg',           # NK News — the paper of record for DPRK watchers
    'dailynk',             # Daily NK — inside-DPRK sourcing, defector network
    'northkoreatech',      # North Korea Tech — missile/satellite/technical

    # ── ROK wires (fastest on launches; the DMZ side of the dyad) ──
    'yonhapnewsagency',    # Yonhap — the ROK wire, first on most launches

    # ── Regional context (Japan is the other audience for an IRBM overflight) ──
    'NHKWorldNews',        # NHK World — Japan's read on overflights and alerts
]


def _telegram_available():
    """Check if Telegram integration is fully configured."""
    if not TELETHON_AVAILABLE:
        return False
    if not all([TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE]):
        print("[Telegram Asia] ⚠️ Missing environment variables")
        return False
    return True


def _ensure_session_file():
    """Decode session file from base64 env var if needed."""
    session_path = f'{SESSION_NAME}.session'
    if os.path.exists(session_path):
        return True

    session_b64 = os.environ.get('TELEGRAM_SESSION_BASE64')
    if session_b64:
        try:
            session_data = base64.b64decode(session_b64)
            with open(session_path, 'wb') as f:
                f.write(session_data)
            print(f"[Telegram Asia] ✅ Session file decoded ({len(session_data)} bytes)")
            return True
        except Exception as e:
            print(f"[Telegram Asia] ❌ Session decode error: {str(e)[:100]}")
            return False

    print("[Telegram Asia] ⚠️ No session file and no TELEGRAM_SESSION_BASE64 env var")
    return False


async def _async_fetch_messages(channels, hours_back=24):
    """
    Async function to fetch messages from Telegram channels.
    Returns list of messages compatible with Asia backend article format.
    """
    if not _ensure_session_file():
        return []

    messages = []
    since = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    try:
        client = TelegramClient(SESSION_NAME, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
        await client.connect()

        if not await client.is_user_authorized():
            print("[Telegram Asia] ❌ Session not authorized")
            await client.disconnect()
            return []

        print(f"[Telegram Asia] ✅ Connected, fetching from {len(channels)} channels...")

        for channel in channels:
            try:
                entity = await client.get_entity(channel)
                history = await client(GetHistoryRequest(
                    peer=entity,
                    limit=50,
                    offset_date=None,
                    offset_id=0,
                    max_id=0,
                    min_id=0,
                    add_offset=0,
                    hash=0
                ))

                channel_count = 0
                for msg in history.messages:
                    if msg.date and msg.date.replace(tzinfo=timezone.utc) > since and msg.message:
                        messages.append({
                            'title': msg.message[:500],
                            'body': msg.message[:500],
                            'url': f'https://t.me/{channel}/{msg.id}',
                            'published': msg.date.replace(tzinfo=timezone.utc).isoformat(),
                            'query': f'telegram_{channel}',
                            'source': f'Telegram @{channel}',
                            'views': getattr(msg, 'views', 0) or 0,
                            'forwards': getattr(msg, 'forwards', 0) or 0,
                        })
                        channel_count += 1

                print(f"[Telegram Asia] @{channel}: {channel_count} messages (last {hours_back}h)")

            except FloodWaitError as e:
                print(f"[Telegram Asia] @{channel} flood wait {e.seconds}s — skipping")
                continue
            except (UsernameInvalidError, UsernameNotOccupiedError):
                print(f"[Telegram Asia] @{channel} username invalid — skipping")
                continue
            except Exception as e:
                print(f"[Telegram Asia] @{channel} error: {str(e)[:100]}")
                continue

        await client.disconnect()
        print(f"[Telegram Asia] ✅ Total: {len(messages)} messages from {len(channels)} channels")

    except Exception as e:
        print(f"[Telegram Asia] ❌ Connection error: {str(e)[:200]}")
        try:
            await client.disconnect()
        except Exception:
            pass

    return messages


def fetch_asia_telegram_signals(hours_back=24, include_extended=True):
    """
    Synchronous wrapper to fetch Asia-Pacific Telegram messages.

    Args:
        hours_back: How many hours back to fetch (default 24)
        include_extended: Whether to include extended channel list

    Returns:
        List of dicts with keys: title, url, published, query, source, views, forwards
    """
    if not _telegram_available():
        print("[Telegram Asia] Signals unavailable — skipping")
        return []

    channels = ASIA_CHANNELS.copy()
    if include_extended:
        channels.extend(EXTENDED_ASIA_CHANNELS)

    # Bridge async to sync
    try:
        try:
            loop = asyncio.get_running_loop()
            print("[Telegram Asia] ⚠️ Event loop already running — using thread")
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _async_fetch_messages(channels, hours_back))
                return future.result(timeout=120)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_async_fetch_messages(channels, hours_back))
            finally:
                loop.close()
    except Exception as e:
        print(f"[Telegram Asia] ❌ fetch error: {str(e)[:200]}")
        return []


def fetch_dprk_telegram_signals(hours_back=72):
    """
    Fetch Telegram signals for the DPRK leverage tracker (v1.0.0, Jul 13 2026).

    72h window. The DPRK's declaratory rhythm is measured in DAYS, not hours --
    KCNA publishes on a cadence, not a news cycle -- and a 24h window would
    mistake an ordinary quiet Tuesday for an anomaly.

    Key signals:
      - KCNA / Rodong Sinmun statement CADENCE (this is the tempo stream itself:
        for a CLAIMING actor, a drop below baseline is the signal, not the noise)
      - Kim Jong Un appearances, and conspicuous absences from staged events
      - Kim Yo Jong statements -- she is the voice used when the principal wants
        deniability, so her carrying the message while he is unseen is itself a read
      - Missile launches: type, and LOCATION, which is the audience
      - Punggye-ri / Sohae site activity (feeds the nuclear tripwire)
      - Sidelining tells: skipped ceremonies, scrubbed Russian presence, exclusion
        from Ukraine settlement talks -- the leverage-decay instrument

    Returns [] on any failure. The tracker soft-imports this, so a Telegram
    outage degrades the corpus; it never breaks the scan.
    """
    if not _telegram_available():
        print("[Telegram DPRK] Signals unavailable — skipping")
        return []
    try:
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run,
                                     _async_fetch_messages(DPRK_CHANNELS, hours_back))
                return future.result(timeout=120)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    _async_fetch_messages(DPRK_CHANNELS, hours_back))
            finally:
                loop.close()
    except Exception as e:
        print(f"[Telegram DPRK] ❌ fetch error: {str(e)[:200]}")
        return []


def get_asia_telegram_status():
    """Return status info for health check / debugging."""
    return {
        'telethon_installed': TELETHON_AVAILABLE,
        'api_configured': bool(TELEGRAM_API_ID and TELEGRAM_API_HASH),
        'phone_configured': bool(TELEGRAM_PHONE),
        'session_available': os.path.exists(f'{SESSION_NAME}.session') or bool(os.environ.get('TELEGRAM_SESSION_BASE64')),
        'core_channels': ASIA_CHANNELS,
        'extended_channels': EXTENDED_ASIA_CHANNELS,
        'ready': _telegram_available() and (
            os.path.exists(f'{SESSION_NAME}.session') or
            bool(os.environ.get('TELEGRAM_SESSION_BASE64'))
        )
    }
