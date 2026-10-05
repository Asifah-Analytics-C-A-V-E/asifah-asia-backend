# asifah-asia-backend

**Asia & Pacific theatre backend for [Asifah Analytics](https://asifahanalytics.com)**

Open-source monitoring of geopolitical pressure, conflict escalation and
humanitarian stress across the Asia-Pacific theatre. Sister backends cover the
Middle East & North Africa, Europe, Africa and the Western Hemisphere.

> **What this is.** A one-person project, built on nights and weekends, running
> on free tiers and stubbornness. No affiliation with or endorsement by any
> government or organisation. If it has been useful to you,
> ☕ [a coffee](https://buymeacoffee.com/asifahanalytics) pays for the hosting
> that keeps it up.

> 🚨 **Not for operational use.** Analytical and research purposes only. See
> [`LICENSE`](./LICENSE).

---

## 🌏 Coverage

Two tiers, and the difference matters: a threat target is scored from article
volume and keyword weighting. A **rhetoric tracker** is a purpose-built sensor
with its own actor roster, escalation ladder, red lines and interpreter, and
only tracked countries reach the regional BLUF and the Global Pressure Index.

| Country | Rhetoric tracker | Interpreter | Role |
|---|---|---|---|
| 🇨🇳 China | ✅ | ✅ | Resident hub — also carries stability and humanitarian modules |
| 🇹🇼 Taiwan | ✅ | ✅ | Primary contested node |
| 🇵🇰 Pakistan | ✅ | ✅ | Also carries a stability module |
| 🇯🇵 Japan | ✅ | ✅ | Also carries the market-quote module |
| 🇮🇳 India | ✅ | — | Absorber-class tracker (May 2026) |
| 🇻🇳 Vietnam | ✅ | ✅ | South China Sea coercion-response tracker (Jun 2026) |
| 🇦🇫 Afghanistan | ✅ | ✅ | Four-wheel contested node (Jul 2026); humanitarian + article modules |
| 🇰🇵 DPRK | ✅ | ✅ | Leverage-integrity tracker (Jul 2026) — **inverted read** |

**Threat-scored but not tracked:** 🇰🇷 South Korea. It appears in
`/api/asia/threat/<target>` and the dashboard, but has no rhetoric tracker, so it
does not reach the regional BLUF. Scored, not sensed — those are different things
and the platform does not blur them.

**Resident hubs:** `china` and `dprk`. Unlike Africa, Asia hosts hubs of its own,
so the convergence panel renders both resident wheels and emanating spokes.

**Next in the queue:** Philippines (slot reserved in `asia_regional_bluf.py`).

---

## 🏗 Architecture

- **Flask + gunicorn** on Render
- **Shared Upstash Redis** for cross-theatre fingerprints and per-tracker caches,
  plus an in-memory layer with a 4-hour TTL
- **Background refresh thread** rebuilds all country caches every 4 hours
- **Multi-source OSINT ingestion** — GDELT (six languages), NewsAPI, Brave Search,
  Google News RSS, Reddit, Telegram, Bluesky
- **GDELT languages:** English, Mandarin (`zho`), Korean (`kor`), Urdu (`urd`),
  Dari (`prs`), Japanese (`jpn`)

### Modules

| Area | Files |
|---|---|
| Rhetoric trackers | `rhetoric_tracker_china.py`, `_taiwan`, `_pakistan`, `_japan`, `_india`, `_vietnam`, `_afghanistan`, `_dprk` |
| Interpreters | `china_signal_interpreter.py`, `taiwan_`, `pakistan_`, `japan_`, `vietnam_`, `afghanistan_`, `dprk_` |
| Regional synthesis | `asia_regional_bluf.py` |
| Country modules | `china_stability.py`, `china_humanitarian.py`, `pakistan_stability.py`, `afghanistan_humanitarian.py`, `afghanistan_articles.py`, `asia_market_quotes.py` |
| Proxies to ME canon | `commodity_proxy_asia.py`, `convergence_proxy_asia.py`, `absorption_proxy_asia.py`, `butterfly_proxy_asia.py`, `jawboning_proxy_asia.py` |
| Ingestion | `gdelt_gateway.py`, `brave_gateway.py`, `telegram_signals_asia.py`, `bluesky_signals_asia.py` |
| Shared libraries | `spoke_wheel_reader.py`, `trajectory_reader.py`, `theatre_state.py`, `feed_health.py` |

**Shared libraries deploy byte-identical to every backend.** `spoke_wheel_reader.py`
and `trajectory_reader.py` are library code, not data — the proxy pattern governs
producers, not libraries. If you change one here, change it everywhere.

**Proxies front the ME backend's canonical registries.** Commodity, convergence,
absorption, butterfly and jawboning all have exactly one producer, on the ME
backend. Asia reads through a proxy rather than keeping a second copy. One
writer, many readers.

---

## 🚀 Deployment

Deploys to Render via GitHub auto-deploy.

### Required environment variables

| Variable | Purpose |
|---|---|
| `UPSTASH_REDIS_URL` | Upstash Redis REST endpoint |
| `UPSTASH_REDIS_TOKEN` | Upstash Redis REST bearer token |
| `NEWSAPI_KEY` | NewsAPI.org API key |
| `BRAVE_API_KEY` | Brave Search API key (tertiary OSINT fallback) |
| `TELEGRAM_API_ID` | Telegram MTProto API ID |
| `TELEGRAM_API_HASH` | Telegram MTProto API hash |
| `TELEGRAM_PHONE` | Telegram account phone number |
| `TELEGRAM_SESSION_BASE64` | Base64-encoded Telethon session file |
| `PYTHONUNBUFFERED` | Set to `1` — forces stdout flush for Render Live Tail visibility |

### Render configuration

```
Language:        Python 3
Build Command:   pip install -r requirements.txt
Start Command:   gunicorn app:app --timeout 300 --workers 2
Health Check:    /health
```

> ⚠️ **CRITICAL:** the start command MUST include `--timeout 300 --workers 2`.
> Render's default 30-second timeout is shorter than a full scan cycle, and this
> is the single most common deploy bug across Asifah backends.

An UptimeRobot monitor on `/health` keeps the service from cold-starting.

### Manual redeploy

Auto-deploy is enabled, but the canonical practice is to confirm each deploy
manually in the Render dashboard so the deploy log can be read before scans run.

> On a 404 after deploy, read the **startup sequence** in the log, not the tail.
> An import error prints its traceback at boot and has usually scrolled away by
> the time you look.

---

## 📡 Endpoints

72 routes are registered; full inventory at `/debug/routes`. The ones used most:

| Endpoint | Purpose |
|---|---|
| `/api/rhetoric/<country>` | Country tracker. All eight: china, taiwan, pakistan, japan, india, vietnam, afghanistan, dprk |
| `/api/rhetoric/<country>/history` | Scan history, newest first. **Six only** — china, taiwan, pakistan, india, vietnam, dprk. Japan and Afghanistan have none |
| `/api/rhetoric/<country>/summary` | Compact read for card rendering. **Seven** — all but Afghanistan |
| `/api/rhetoric/japan/articles` · `/api/rhetoric/india/absorption` · `/api/rhetoric/afghanistan/debug` | Tracker-specific extras |
| `/api/rhetoric/asia/bluf` | Regional BLUF — `?force=true` rebuilds |
| `/api/rhetoric/asia/bluf/debug` | Cache state and per-tracker inventory |
| `/api/asia/dashboard` | All threat scores in one call |
| `/api/asia/threat/<target>` | Threat score for one target (includes South Korea) |
| `/api/asia/commodity/<target>` | Commodity proxy to the ME backend |
| `/api/asia/convergence-all` | Convergence proxy |
| `/api/asia/absorption/detect` · `/api/asia/jawboning/detect` | Absorption and jawboning detectors |
| `/api/asia/butterfly/<consumer_theater>` | Butterfly (second-order effect) read |
| `/api/asia/leader-interventions` | Leader intervention signals |
| `/api/china/stability` · `/api/stability/pakistan` | Country stability modules |
| `/api/china/humanitarian` · `/api/afghanistan/humanitarian` | Humanitarian reads |
| `/api/military/posture` | Military posture |
| `/api/asia/market/japan` | Japan market quotes |
| `/api/asia/notams` · `/api/asia/flights` · `/api/asia/travel-advisories` | Aviation notices, flight disruption, official U.S. travel advisories (public feed: `cadataapi.state.gov`) |
| `/api/asia/cache-status` · `/health` · `/debug/routes` | Operational |

`?force=true` bypasses the cache and runs a live scan.

> ⚠️ `?force=true` on a cold service can exceed a five-minute client timeout.
> Prefer the cached read unless a rebuild is genuinely needed.

---

## 🤝 Cross-backend integration

Asia sits in the three-altitude architecture: sensors below, analyst in the
middle, global index above.

```
Per-country rhetoric trackers (China, Taiwan, Pakistan, Japan,
                               India, Vietnam, Afghanistan, DPRK)
              │
              ▼
    asia_regional_bluf.py  ─────►  Global Pressure Index (GPI)
              ▲                              ▲
              │                              │
   commodity / convergence / absorption / butterfly / jawboning proxies
              ▲
              │
        ME backend's canonical registries
```

---

## 📋 Working practices

**Doctrine.** Every module here follows the platform-wide analytical discipline:

- **Convergence, not prediction.** Report the signals that are present. Never
  assert that an outcome is imminent, likely, or dated.
- **`unknown` is a state, never a silence.** A sensor that could not read
  something says so. It does not emit a zero.
- **A real zero is not an unread zero.** "Measured, found nothing" and "nobody
  measured" are different findings and render differently.
- **Absence is reported, not inferred.** A country without a tracker is absent
  from the regional read, not assessed as quiet.
- **Silence can be the signal.** For claiming actors, quiet against their own
  baseline is a tempo change, not calm.
- **Claims are labelled as claims.** Where a reading rests on an interested
  party's unconfirmed assertions, it is reported as claimed, not established.
- **One writer, many readers.** Data has exactly one producer; everything else
  proxies to it.

**Engineering.**

- Surgical find/replace edits preferred over full-file rewrites
- AST validation before every deploy is mandatory:
  `python3 -c "import ast; ast.parse(open('FILE.py').read()); print('ok')"`
- Static reference data carries `source`, source URL and a `data_as_of` date —
  date-stamp rather than hardcode, so staleness is visible rather than assumed
- A diagnostic that lies is worse than no diagnostic. A health check that cannot
  fail is not a health check.

---

## 📞 Contact

Built and maintained by RCGG / Asifah Analytics. Licensing: see
[`LICENSE`](./LICENSE).

- ☕ [Buy Me a Coffee](https://buymeacoffee.com/asifahanalytics) — pays for hosting
- [asifahanalytics.com](https://asifahanalytics.com) · *Not for operational use*

Donations support running costs. They buy no licence, no warranty, no support
obligation and no influence over what gets built.

---

*© 2025–2026 RCGG / Asifah Analytics. All rights reserved.*

*Last updated: 5 October 2026*
