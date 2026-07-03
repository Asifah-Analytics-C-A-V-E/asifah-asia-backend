"""
afghanistan_signal_interpreter.py -- Asifah Analytics Asia Backend -- v1.0.0 Jul 2026
Cloned from afghanistan_signal_interpreter.py (contract donor). The ANALYST LAYER for
the Afghanistan contested-node tracker: turns raw actor/vector/tripwire scans
into estimative prose -- top_signals, executive summary, So-What bullets, and
the NORMALIZATION-DRIFT read (isolation <-> recognition axis).

CONTRACT (imported by rhetoric_tracker_afghanistan.py):
  build_top_signals(actor_summaries, tripwires_global, commodity_pressure, crosstheater_amplifiers)
  build_executive_summary(actor_summaries, vector_scores, vector_levels, tripwires_global)
  build_so_what_factor(..., alignment_drift=None) -> [{bullet, weight}]
  score_alignment_drift(..., country='afghanistan') -> drift dict | None
  build_alignment_drift_top_signal(drift) -> signal | None

DOCTRINE: estimative voice only ("consistent with / historically precedes /
likely indicates"); every drift output carries the convergence disclaimer.
No probabilities, no dates, no "will". The reader completes the inference.
"""

import re
from datetime import datetime, timezone

# ============================================
# CONFIGURATION
# ============================================
LEVEL_ORDER = ['low', 'normal', 'elevated', 'high', 'surge']
ESCALATORY_LEVELS = {'elevated', 'high', 'surge'}

# Vector display names for prose
VECTOR_NAMES = {
    'kinetic_afpak':     'Af-Pak Kinetic',
    'repression_rights': 'Repression & Rights',
    'external_friction': 'External Wheels',
    'illicit_economy':   'Illicit Economy',
}

# Actor display names for prose (cleaner than the formal `name` field)
ACTOR_PROSE_NAMES = {
    'taliban_kabul':     'the Kabul cabinet',
    'taliban_kandahar':  'the Kandahar emirate (Akhundzada circle)',
    'haqqani_interior':  'Haqqani / Interior',
    'drug_economy':      'the illicit-economy watch',
    'iskp':              'ISIS-Khorasan',
    'ttp':               'TTP',
    'pakistan_state':    'Pakistan (state)',
    'iran_afghanistan':  'Iran (Afghanistan file)',
    'russia_engagement': 'Russia (engagement track)',
    'china_engagement':  'China (extraction track)',
    'un_rights':         'UN rights reporting',
}

# Off-ramp / de-escalation patterns (lowered urgency when present)
DEESCALATION_PATTERNS = [
    'talks', 'dialogue', 'negotiation', 'delegation', 'border reopen',
    'crossing reopen', 'ceasefire', 'agreement', 'aid resumption',
    'prisoner release', 'decree suspended', 'restrictions eased',
    'humanitarian exemption', 'trade resumed',
]

# ============================================
# HELPERS
# ============================================
def _level_rank(level):
    """Numeric rank for level comparison."""
    try:
        return LEVEL_ORDER.index(level)
    except ValueError:
        return 0


def _max_level(levels):
    """Return the highest level from a list."""
    if not levels:
        return 'low'
    return max(levels, key=_level_rank)


def _has_deescalation(actor_summary):
    """Check if an actor's articles contain de-escalation patterns."""
    text = ''
    for art in actor_summary.get('top_articles', []):
        text += ' ' + (art.get('title') or '').lower()
    return any(p in text for p in DEESCALATION_PATTERNS)


def _top_article_for_actor(actor_summary):
    """Get the single highest-scoring article for an actor (or None)."""
    arts = actor_summary.get('top_articles', [])
    return arts[0] if arts else None


def _format_source_pill(source_name, feed_type=''):
    """Return a tagged source string for citation."""
    feed_type = (feed_type or '').lower()
    if feed_type:
        return f"{source_name} ({feed_type})"
    return source_name


# ============================================
# TOP SIGNALS BUILDER
# ============================================
def _commodity_story_signal(commodity_pressure):
    """Composite pressure story signal -- mirrors the stability page's
    commodity alert banner so both pages tell one story. None when calm."""
    story = (commodity_pressure or {}).get('_pressure_story') or {}
    alert = (story.get('alert') or 'normal').lower()
    if alert == 'normal':
        return None
    LEVEL_MAP = {'elevated': 'elevated', 'high': 'high',
                 'critical': 'surge', 'surge': 'surge'}
    escalated = [c for c, a in (story.get('commodities') or {}).items()
                 if a and a != 'normal']
    esc_txt = (', '.join(sorted(escalated)) if escalated
               else 'tracked commodities')
    return {
        'category':   'commodity_coupling',
        'type':       'commodity_coupling',
        'level':      LEVEL_MAP.get(alert, 'elevated'),
        'icon':       '\u26cf\ufe0f',
        'short_text': ('Composite commodity pressure: ' + alert.upper() + ' -- '
                       + str(story.get('points', 0)) + ' pts \u00b7 '
                       + str(story.get('profile_count', 0)) + ' commodities tracked'),
        'long_text':  ('Composite news-signal pressure (weighted volume/severity '
                       'of matched reporting, NOT price) is at ' + alert.upper()
                       + ' across ' + esc_txt + '. Afghanistan supply-risk premium is '
                       'partly a political risk premium -- this composite and the '
                       'runoff count are stacking on the same window.'),
        'source_link': '/afghanistan-stability.html#commodities',
    }


def build_top_signals(actor_summaries, tripwires_global, commodity_pressure, crosstheater_amplifiers):
    """
    Build the canonical top_signals[] array for the Afghanistan rhetoric tracker.

    Each signal has the canonical schema:
      {
        'short_text':  one-line headline (≤120 chars)
        'long_text':   2-4 sentence elaboration
        'level':       one of low/normal/elevated/high/surge
        'type':        actor_signal | tripwire | convergence | commodity_coupling | crosstheater
        'actor':       actor_id (or None)
        'sources':     list of {title, url, source} (top 3)
      }

    Sorted by level (surge first), then by signal-richness.
    """
    signals = []

    # ── 1. Tripwire signals (highest priority) ──
    seen_tripwires = set()
    for tw in tripwires_global or []:
        tw_id = tw.get('id')
        if tw_id in seen_tripwires:
            continue
        seen_tripwires.add(tw_id)
        actor_id = tw.get('actor')
        actor_data = actor_summaries.get(actor_id, {}) if actor_id else {}
        top_art = _top_article_for_actor(actor_data) if actor_data else None
        sources = []
        if top_art:
            sources.append({
                'title':  top_art.get('title', ''),
                'url':    top_art.get('url', ''),
                'source': top_art.get('source', ''),
            })

        short, long_text = _tripwire_prose(tw_id, actor_id)
        signals.append({
            'short_text': short,
            'long_text':  long_text,
            'level':      tw.get('severity', 'high'),
            'type':       'tripwire',
            'actor':      actor_id,
            'sources':    sources,
        })

    # ── 2. Convergence signals ──
    # When ≥2 vectors are at elevated+, signal a convergence
    vector_levels = {}
    for actor_id, actor in actor_summaries.items():
        vec = actor.get('vector')
        lvl = actor.get('level', 'low')
        if vec:
            existing = vector_levels.get(vec, 'low')
            if _level_rank(lvl) > _level_rank(existing):
                vector_levels[vec] = lvl
    elevated_vectors = [v for v, lv in vector_levels.items() if lv in ESCALATORY_LEVELS]
    if len(elevated_vectors) >= 2:
        sig = _convergence_signal(elevated_vectors, vector_levels, actor_summaries)
        if sig:
            signals.append(sig)

    # ── 3. Per-actor signals (only at elevated+) ──
    for actor_id, actor in actor_summaries.items():
        level = actor.get('level', 'low')
        if level not in ESCALATORY_LEVELS:
            continue
        # Skip if a tripwire already covered this actor at the same/higher severity
        actor_tw_levels = [
            tw.get('severity') for tw in tripwires_global or []
            if tw.get('actor') == actor_id
        ]
        if actor_tw_levels and _level_rank(_max_level(actor_tw_levels)) >= _level_rank(level):
            continue

        sig = _actor_signal(actor_id, actor)
        if sig:
            signals.append(sig)

    # ── 4. Commodity coupling signals ──
    for commodity_id, risk in (commodity_pressure or {}).items():
        if commodity_id.startswith('_'):
            continue  # reserved keys (e.g. _pressure_story) are not commodities
        if risk.get('alert_level') in ESCALATORY_LEVELS:
            sig = _commodity_coupling_signal(commodity_id, risk, actor_summaries)
            if sig:
                signals.append(sig)

    # ── 5. Cross-theater amplifier signals ──
    for amp_label, amp_data in (crosstheater_amplifiers or {}).items():
        if not isinstance(amp_data, dict):
            continue
        if not amp_data.get('active'):
            continue
        sig = _crosstheater_signal(amp_label, amp_data)
        if sig:
            signals.append(sig)

    # Sort: surge → high → elevated → normal → low; within same level, signals with sources first
    signals.sort(
        key=lambda s: (-_level_rank(s['level']), -len(s.get('sources', [])))
    )
    # Composite commodity story rides high when escalated (mirrors stability page)
    _cs = _commodity_story_signal(commodity_pressure)
    if _cs:
        signals.insert(0, _cs)
    return signals[:12]   # cap at 12 -- UI shows ~8 by default


def _tripwire_prose(tw_id, actor_id):
    """Generate (short, long) estimative prose for an Afghan tripwire."""
    map_ = {
        'iskp_external_attack': (
            "\U0001f4a3 ISKP external operation -- two-theater signal",
            "An ISKP attack or disrupted plot attributed to Afghan-based planning. By construction "
            "this raises pressure in TWO theaters at once: the target country and the Kabul "
            "relationship. The Crocus City Hall (Moscow) and Kerman (Iran) precedents show the "
            "pattern: external ISKP operations historically precede intensified counterterror "
            "engagement WITH the Taliban by the very powers the group struck -- normalization "
            "pressure through the back door. Watch: attribution language, Taliban denial cadence, "
            "and whether the struck power's next Kabul contact is punitive or cooperative."),
        'pakistan_strikes_afghanistan': (
            "\u2694\ufe0f Pakistani kinetic action inside Afghanistan",
            "Cross-border strikes are the sharp end of the TTP-sanctuary dispute. The historical "
            "pattern (2022, 2024 strike cycles): strikes -> Taliban protest + border closure -> "
            "TTP retaliation inside Pakistan -> talks -> relapse. A strike event is consistent "
            "with the cycle re-arming, not resolving. Watch: Torkham/Chaman status within 72h, "
            "ISPR framing (TTP camps vs 'terrorist infrastructure'), and whether Kabul's response "
            "invokes the Durand Line's non-recognition."),
        'border_closure': (
            "\U0001f6a7 Torkham/Chaman closure -- chokepoint event",
            "Crossing closures are simultaneously a trade weapon, a humanitarian constraint, and a "
            "deportation-pressure valve. Historically closures lasting beyond ~2 weeks transmit "
            "into Kabul food prices and transit-trade revenue -- pressure the Emirate cannot "
            "offset. Watch: reopening negotiations, wheat/fuel price reporting from Kabul markets, "
            "and whether closures coincide with deportation-wave announcements (the combined lever)."),
        'mass_repression_event': (
            "\u2696\ufe0f Mass repression event -- rights-vector spike",
            "Public executions, mass floggings, or new decrees erasing women from public life. "
            "Beyond the human toll, these events are the binding constraint on aid, recognition, "
            "and normalization -- each one historically resets Western engagement to zero and "
            "hands the isolation camp its argument. Watch: whether the decree originates in "
            "Kandahar (emir circle) over Kabul-cabinet objection -- the internal-fault-line tell."),
        'helmand_water_clash': (
            "\U0001f4a7 Iran border clash -- water friction gone kinetic",
            "Helmand/Hirmand water disputes have produced actual firefights (May 2023 precedent, "
            "Sasuli/Milak border). A clash event marks the friction wheel spiking from diplomatic "
            "to kinetic -- the pattern that historically precedes reinforced border deployments "
            "on both sides and Iranian water-rights ultimatums. Watch: Iranian MFA vs IRGC "
            "framing divergence, dam-release announcements, and Sistan-Baluchestan drought reporting."),
        'recognition_event': (
            "\U0001f91d Recognition event -- normalization milestone",
            "A state formally recognizing the Emirate (Russia 2025 = the precedent and the dam "
            "break). Each recognition historically lowers the cost of the next -- the cascade "
            "question is THE alignment story for this theater. Watch: which bloc moves next "
            "(Central Asia, Gulf, China), and whether recognition language couples to "
            "counterterrorism or extraction deliverables."),
        'mass_deportation_wave': (
            "\U0001f9ed Mass deportation wave -- forced-return reabsorption",
            "Iran or Pakistan announcing/executing mass returns of Afghans. The pressure is "
            "bidirectional by design: a lever on Kabul AND a reabsorption shock into a collapsed "
            "economy -- historically preceding urban labor-market strain and border-province "
            "instability. Watch: IOM/UNHCR flow counts (the platform sensor carries them), "
            "winter timing (reabsorption during frost is materially worse), and Taliban "
            "reception-capacity claims vs observed camp conditions."),
    }
    default = (
        f"\u26a1 Afghanistan tripwire: {tw_id.replace('_',' ')}",
        f"Pattern-level escalation event ({tw_id.replace('_',' ')}) detected this scan window. "
        f"Convergence indicator -- see the tracker feed for source articles.")
    return map_.get(tw_id, default)

def _convergence_signal(elevated_vectors, vector_levels, actor_summaries):
    """When 2+ vectors are at elevated+, build a convergence signal."""
    vec_names = [VECTOR_NAMES.get(v, v) for v in elevated_vectors]
    max_level = _max_level([vector_levels[v] for v in elevated_vectors])
    short = f"⚡ Convergence: {' + '.join(vec_names[:2])}{' + …' if len(vec_names) > 2 else ''} at {max_level}"
    long_parts = [f"Multiple analytical vectors are simultaneously elevated:"]
    for v in elevated_vectors:
        lvl = vector_levels[v]
        long_parts.append(f"• {VECTOR_NAMES.get(v, v).title()} at {lvl}")
    long_parts.append(
        "Convergence is more analytically significant than any individual vector — when "
        "domestic-stability pressure intersects with resource-sector or alignment vectors, "
        "Afghanistan's risk profile compounds across normally-independent dimensions."
    )
    long_text = ' '.join(long_parts) if False else '\n'.join(long_parts)
    return {
        'short_text': short,
        'long_text':  long_text,
        'level':      max_level,
        'type':       'convergence',
        'actor':      None,
        'sources':    [],
    }


def _actor_signal(actor_id, actor):
    """Build a per-actor signal at elevated+."""
    name = ACTOR_PROSE_NAMES.get(actor_id, actor.get('name', actor_id))
    level = actor.get('level', 'normal')
    score = actor.get('score', 0)
    article_count = actor.get('article_count', 0)
    icon = actor.get('icon', '📊')

    # Detect de-escalation
    deescalation = _has_deescalation(actor)

    # Build short_text
    if deescalation and level in ('elevated', 'high'):
        short = f"{icon} {name} — {level} but with de-escalatory rhetoric (dialogue / consulta previa)"
    elif level == 'surge':
        short = f"{icon} {name} — SURGE-level rhetoric ({article_count} signals)"
    elif level == 'high':
        short = f"{icon} {name} — high-level rhetoric tempo ({article_count} signals)"
    else:
        short = f"{icon} {name} — elevated rhetoric tempo ({article_count} signals)"

    # Build long_text — actor-specific framing
    long_text = _actor_specific_long_text(actor_id, actor, deescalation)

    # Sources
    sources = []
    for art in actor.get('top_articles', [])[:3]:
        sources.append({
            'title':  art.get('title', ''),
            'url':    art.get('url', ''),
            'source': art.get('source', ''),
        })

    return {
        'short_text': short,
        'long_text':  long_text,
        'level':      level,
        'type':       'actor_signal',
        'actor':      actor_id,
        'sources':    sources,
    }


def _actor_specific_long_text(actor_id, actor, deescalation):
    """Per-actor analytical long text -- the estimative read behind each signal."""
    level = actor.get('level', 'normal')
    prose = {
        'taliban_kabul':
            "Kabul-cabinet rhetoric is the Emirate's engagement instrument -- spokesman tempo and "
            "FM Muttaqi's travel/meeting cadence historically track normalization momentum. "
            "Elevated output here alongside QUIET Kandahar decrees is consistent with the "
            "pragmatist track running room; the reverse pattern (Kabul quiet, Kandahar loud) "
            "has historically preceded engagement freezes.",
        'taliban_kandahar':
            "Decree flow from the Akhundzada circle is the repression driver and the "
            "normalization ceiling. Every major edict cycle (education bans, morality law, "
            "media restrictions) has historically reset Western engagement and triggered "
            "UN-reporting surges within weeks. Sustained decree tempo is consistent with the "
            "clerical track consolidating against the Kabul pragmatists.",
        'haqqani_interior':
            "Haqqani-track statements carry double signal value: security posture (ISKP "
            "counterops) AND the internal fault line. Public Haqqani criticism of Kandahar "
            "-- the pattern of 2023-2024 speeches -- is the platform's primary observable "
            "for regime-cohesion stress and the standing succession-risk watch item.",
        'drug_economy':
            "Post-ban economy signals: meth seizures rising along Iran/Pakistan corridors, "
            "opium stockpile-drawdown pricing, and farmer-immiseration reporting from former "
            "poppy provinces. Seizure-volume surges are consistent with corridor throughput "
            "rising regardless of Kabul's enforcement claims -- trafficking revenue is "
            "polity-agnostic.",
        'iskp':
            "ISKP activity is the theater's terror-export vector and the Taliban's principal "
            "armed rival. Attack tempo inside Afghanistan reads as regime-security pressure; "
            "EXTERNAL attribution (Moscow, Kerman, Europe precedents) reads as global pressure "
            "and, paradoxically, normalization fuel -- struck powers historically deepen "
            "Kabul security engagement afterward.",
        'ttp':
            "TTP claim tempo is the leading indicator of the Af-Pak kinetic cycle. Sustained "
            "surges have historically preceded Pakistani cross-border action within weeks "
            "(2022, 2024 cycles). Watch claim geography: attacks beyond KP/Balochistan into "
            "Punjab historically mark cycle escalation.",
        'pakistan_state':
            "Islamabad's Afghanistan rhetoric runs the kinetic wheel: ISPR strike framing, "
            "deportation-wave announcements, and crossing closures operate as a combined "
            "pressure lever. Escalatory ISPR language plus deportation acceleration is the "
            "pattern that has historically preceded kinetic events.",
        'iran_afghanistan':
            "Tehran's Afghanistan file is friction-tier by design: Helmand water rights, "
            "deportation waves, and border incidents pull one way; fuel trade and "
            "anti-ISKP alignment pull the other. Water-rhetoric surges during Sistan drought "
            "cycles have historically preceded border incidents -- the May 2023 clash is the "
            "precedent.",
        'russia_engagement':
            "Moscow's engagement track (recognition 2025, Kabulov channel) is the "
            "normalization wheel's leading edge. Elevated Russian statement tempo is "
            "consistent with recognition-cascade advocacy -- each Moscow-Kabul deliverable "
            "historically lowers the next state's recognition cost.",
        'china_engagement':
            "Beijing's track is extraction-first: Mes Aynak milestones, Amu Darya oil, and "
            "Wakhan security understandings. Chinese statement surges coupled to project "
            "milestones are consistent with economic-foothold deepening -- the dependency "
            "channel that outlasts any single government.",
        'un_rights':
            "UNAMA/OHCHR reporting is the repression-evidence stream: report cycles and "
            "special-rapporteur statements historically lag decree events by 2-6 weeks and "
            "anchor the isolation camp's case. Surges here without new decrees are consistent "
            "with cumulative documentation reaching publication -- pressure with a delay fuse.",
    }
    base = prose.get(actor_id,
        f"{ACTOR_PROSE_NAMES.get(actor_id, actor_id)} scanning at {level} -- elevated "
        f"statement tempo/severity versus baseline this window.")
    if deescalation:
        base += (" NOTE: de-escalatory vocabulary detected in this window (talks/reopening/"
                 "easing) -- the level reflects tempo, but polarity may be softening; "
                 "convergence read, not prediction.")
    return base

def _commodity_coupling_signal(commodity_id, risk, actor_summaries):
    """Build a commodity-coupling signal from a supply-risk fingerprint."""
    role = risk.get('role', 'producer')
    rank = risk.get('rank')
    rank_str = f" (#{rank} globally)" if rank else ""
    alert = risk.get('alert_level', 'normal')
    sig_count = risk.get('signal_count', 0)
    top_signal = risk.get('top_signal') or {}

    short = f"⛏️ Commodity coupling: {commodity_id} {role}{rank_str} — {alert} pressure from sector signals"
    long_text = (
        f"The commodity tracker is reporting {alert}-level pressure on Afghanistan's {commodity_id} "
        f"sector (Afghanistan is a {role}{rank_str}). {sig_count} cross-tracker signals flagged. "
        f"This is a coupling event — what the rhetoric tracker observes in illicit_economy / "
        f"wheat/corridor channels has a direct supply-side implication for global {commodity_id} "
        f"markets. Watch for sector-rhetoric and price-impact alignment."
    )
    sources = []
    if top_signal.get('title'):
        sources.append({
            'title':  top_signal.get('title', ''),
            'url':    top_signal.get('url', ''),
            'source': top_signal.get('source', ''),
        })

    return {
        'short_text': short,
        'long_text':  long_text,
        'level':      alert,
        'type':       'commodity_coupling',
        'actor':      'drug_economy',
        'sources':    sources,
    }


def _crosstheater_signal(amp_label, amp_data):
    """Signal for an active sibling-wheel fingerprint (absence-honest: only called when present)."""
    prose = {
        'pakistan_fingerprint': (
            '\U0001f1f5\U0001f1f0 Pakistan wheel active -- kinetic-side amplification',
            'The Pakistan tracker\'s crosstheater fingerprint is live and elevated. For Afghanistan '
            'this amplifies the Af-Pak kinetic vector: Pakistani domestic pressure has historically '
            'transmitted into harder Afghanistan policy (strikes, closures, deportation waves).'),
        'iran_fingerprint': (
            '\U0001f1ee\U0001f1f7 Iran wheel active -- friction-side amplification',
            'The Iran tracker\'s crosstheater fingerprint is live. Elevated Iranian theater pressure '
            'has historically hardened Tehran\'s Afghanistan file (water ultimatums, deportation '
            'acceleration, border posture) -- friction-spoke amplification on the contested node.'),
        'china_fingerprint': (
            '\U0001f1e8\U0001f1f3 China wheel active -- extraction-track amplification',
            'The China tracker\'s crosstheater fingerprint is live. Elevated Chinese theater activity '
            'is consistent with accelerated extraction-track positioning in Kabul (Mes Aynak, Amu '
            'Darya) -- the dependency channel of the normalization-drift read.'),
    }
    short, long = prose.get(amp_label, (
        f'\U0001f6de Sibling-wheel fingerprint active: {amp_label}',
        f'A sibling tracker fingerprint ({amp_label}) is live -- crosstheater amplification on the contested node.'))
    return {
        'level': 'elevated', 'type': 'crosstheater', 'priority': 6,
        'category': 'crosstheater', 'theatre': 'afghanistan',
        'pressure_type': 'diplomatic',
        'short_text': short, 'long_text': long,
    }
def build_executive_summary(actor_summaries, vector_scores, vector_levels, tripwires_global):
    """
    Generate a 2-4 sentence executive summary capturing the headline narrative.
    Calibrated to the 4-vector frame.
    """
    parts = []

    # Identify top vector + level
    sorted_vectors = sorted(
        vector_scores.items(),
        key=lambda x: (-_level_rank(vector_levels.get(x[0], 'low')), -x[1])
    )
    top_vector_id, top_vector_score = sorted_vectors[0] if sorted_vectors else (None, 0)
    top_vector_level = vector_levels.get(top_vector_id, 'low') if top_vector_id else 'low'

    elevated_vectors = [v for v, lv in vector_levels.items() if lv in ESCALATORY_LEVELS]

    # Sentence 1 — top vector framing
    if top_vector_level == 'low':
        parts.append(
            "Afghanistan's rhetoric environment is at baseline across all four analytical vectors "
            "(domestic stability, resource-sector politics, US alignment, China alignment). "
            "No structural pressure events detected this scan."
        )
    elif top_vector_level == 'normal':
        parts.append(
            f"Afghanistan's rhetoric environment is normal-tempo, with {VECTOR_NAMES.get(top_vector_id, top_vector_id)} "
            f"showing the most signal volume but no escalatory pattern."
        )
    else:
        parts.append(
            f"Afghanistan's rhetoric environment is elevated, led by {VECTOR_NAMES.get(top_vector_id, top_vector_id)} "
            f"at {top_vector_level} ({round(top_vector_score, 1)} weighted score)."
        )

    # Sentence 2 — convergence note
    if len(elevated_vectors) >= 2:
        vec_names = [VECTOR_NAMES.get(v, v) for v in elevated_vectors]
        parts.append(
            f"Cross-vector convergence is underway: {' + '.join(vec_names[:3])} "
            f"are simultaneously above baseline, compounding Afghanistan's risk profile."
        )

    # Sentence 3 — tripwire mention
    if tripwires_global:
        unique_tw = list({tw.get('id') for tw in tripwires_global})
        tw_count = len(unique_tw)
        if tw_count == 1:
            parts.append(
                f"One tripwire event detected this scan: {unique_tw[0].replace('_', ' ')}. "
                f"See top signals for context."
            )
        else:
            parts.append(
                f"{tw_count} tripwire events detected this scan: {', '.join(t.replace('_', ' ') for t in unique_tw[:3])}. "
                f"See top signals for context."
            )

    # Sentence 4 — top-actor breadcrumb
    sorted_actors = sorted(
        actor_summaries.items(),
        key=lambda x: (-_level_rank(x[1].get('level', 'low')), -x[1].get('score', 0))
    )
    top_actor_id, top_actor = sorted_actors[0] if sorted_actors else (None, None)
    if top_actor and top_actor.get('level') in ESCALATORY_LEVELS:
        parts.append(
            f"Highest-tempo actor this scan: {ACTOR_PROSE_NAMES.get(top_actor_id, top_actor_id)} "
            f"at {top_actor.get('level')} ({top_actor.get('article_count', 0)} signals)."
        )

    return ' '.join(parts)


# ============================================
# SO WHAT FACTOR BUILDER
# ============================================
# ============================================================
# ELECTION RUNOFF WATCH (Jun 2026 cycle)
# ============================================================
# Convergence module for the Fujimori-Sanchez runoff. Reports WHICH counting
# and candidate signals are present in the current scan -- it NEVER predicts
# a winner. Market polarity per candidate is an analytical READ of policy
# posture (engagement/repression), not an endorsement or forecast.

DRIFT_BAND_META = {
    'US-anchored': {'level': 1, 'color': '#38bdf8', 'priority': 8},
    'Contested':   {'level': 3, 'color': '#f59e0b', 'priority': 12},
    'Drifting':    {'level': 4, 'color': '#f97316', 'priority': 13},
    'Realigning':  {'level': 5, 'color': '#dc2626', 'priority': 14},
}

DRIFT_PROFILES = {
    'afghanistan': {
        'flag':            '\U0001F1E6\U0001F1EB',
        'inroad_power':    'the normalization bloc (Russia/China-led)',
        'incumbent_power': 'the isolation architecture (rights-conditioned non-recognition)',
        'inroad_actor':    'russia_engagement',
        'counter_actor':   'un_rights',
        'inroad_tripwires':  ('recognition_event',),
        'counter_tripwires': ('mass_repression_event',),
        'dependency_channel': "Russia's 2025 recognition precedent plus Mes Aynak/Amu Darya extraction contracts",
        'commodity_keys':     ('copper', 'lithium'),
        'crosstheater_amp':   'china_fingerprint',
        'structural_dependency_baseline': True,   # recognition precedent set (Russia 2025) -- not reversed
        'precedents': ("Russia's formal recognition of the Emirate (2025) -- the first and the dam-break "
                       "precedent; China's accredited-ambassador model as recognition-without-recognition"),
        'leading_indicators': [
            'Next-mover recognition signals (Central Asia, Gulf states, China formalization)',
            'Mes Aynak mobilization milestones and Amu Darya output announcements',
            'Kandahar decree tempo (each major edict resets the Western track)',
            'ISKP external attacks (paradoxical normalization fuel via counterterror engagement)',
            'UNAMA report cycles and rights-conditioned aid decisions',
        ],
    },
}

_DRIFT_LEVEL_RANK = {'low': 0, 'normal': 1, 'elevated': 2, 'high': 3, 'surge': 4}


def score_alignment_drift(actor_summaries, tripwires_global,
                          commodity_pressure, crosstheater_amplifiers,
                          country='afghanistan', profile=None):
    """Portable great-power alignment-drift convergence read ("BRI writ large").
    Nets challenger (China/BRI) inroad pressure against incumbent (US) counter-
    pressure: US-anchored -> Contested -> Drifting -> Realigning. Registry-shaped
    output (id: bri_inroad_<country>). CONVERGENCE, not prediction."""
    prof = profile or DRIFT_PROFILES.get((country or '').lower())
    if not prof:
        return None

    asum = actor_summaries or {}
    inroad_lvl  = _DRIFT_LEVEL_RANK.get((asum.get(prof['inroad_actor'])  or {}).get('level', 'low'), 0)
    counter_lvl = _DRIFT_LEVEL_RANK.get((asum.get(prof['counter_actor']) or {}).get('level', 'low'), 0)

    tw_ids = {tw.get('id') for tw in (tripwires_global or [])}
    inroad_tw  = [t for t in prof['inroad_tripwires']  if t in tw_ids]
    counter_tw = [t for t in prof['counter_tripwires'] if t in tw_ids]

    # structural dependency lever: standing baseline (operational megaport) OR a live commodity surge
    dep_active = bool(prof.get('structural_dependency_baseline', False))
    if not dep_active:
        for ck in prof.get('commodity_keys', ()):
            cp = (commodity_pressure or {}).get(ck) or {}
            if isinstance(cp, dict) and (cp.get('active') or cp.get('level') in ('elevated', 'high', 'surge')):
                dep_active = True
                break

    amp_active = bool((crosstheater_amplifiers or {}).get(prof.get('crosstheater_amp', '')))

    inroad  = inroad_lvl + len(inroad_tw) + (1 if dep_active else 0) + (1 if amp_active else 0)
    counter = counter_lvl + len(counter_tw)

    # ── band the NET drift ──
    if inroad <= 1:
        band = 'US-anchored'
    elif inroad >= 2 and counter >= 2:
        band = 'Contested'
    elif inroad >= 5 and counter <= 1 and dep_active:
        band = 'Realigning'
    elif (inroad - counter) >= 2:
        band = 'Drifting'
    elif counter >= 2:
        band = 'Contested'
    else:
        band = 'US-anchored'

    # structural-dependency floor: an entrenched, operational inroad means the
    # alignment has already structurally landed -- at minimum 'Drifting'.
    if prof.get('structural_dependency_baseline') and band == 'US-anchored':
        band = 'Drifting'

    ip = prof['inroad_power']; cp_ = prof['incumbent_power']; cc = (country or '').title()
    if band == 'US-anchored':
        so_what = (ip + "'s inroads into " + cc + " read as routine commercial presence rather than a "
                   "converging displacement pattern; " + cp_ + "'s position is uncontested this cycle.")
    elif band == 'Contested':
        so_what = (ip + " inroads and " + cp_ + " counter-pressure are both active -- a contested "
                   "tug-of-war consistent with " + prof['precedents'] + ". The alignment is being "
                   "fought over, not conceded.")
    elif band == 'Drifting':
        so_what = (ip + " inroads are outpacing " + cp_ + " counter-pressure; with " +
                   prof['dependency_channel'] + " already entrenched, the pattern is consistent with "
                   "alignment drift toward " + ip + "'s pole, advancing faster than it is being contested.")
    else:  # Realigning
        so_what = ("Sustained " + ip + " inroads, structural dependency (" + prof['dependency_channel'] +
                   "), and limited " + cp_ + " counter are consistent with the alignment entrenching "
                   "toward " + ip + "'s pole.")

    disclaimer = ("This is a CONVERGENCE / influence indicator, NOT a prediction of realignment. It "
                  "measures whether " + ip + "-displacement signals are outpacing " + cp_ +
                  " counter-pressure; " + cc + " retains full agency over its partners.")

    meta = DRIFT_BAND_META[band]
    return {
        'id':                'bri_inroad_' + (country or '').lower(),
        'country':           (country or '').lower(),
        'flag':              prof.get('flag', ''),
        'band':              band,
        'inroad_power':      ip,
        'incumbent_power':   cp_,
        'inroad_score':      inroad,
        'counter_score':     counter,
        'net':               inroad - counter,
        'active_inroad_tripwires':  inroad_tw,
        'active_counter_tripwires': counter_tw,
        'dependency_active': dep_active,
        'regional_amp_active': amp_active,
        'so_what_factor':    so_what,
        'leading_indicators': list(prof['leading_indicators']),
        'precedent':         prof['precedents'],
        'disclaimer':        disclaimer,
        'level':             meta['level'],
        'priority':          meta['priority'],
        'color':             meta['color'],
        'icon':              '\U0001F9ED',       # compass
    }


def build_alignment_drift_top_signal(drift):
    """Canonical-schema top_signal for the alignment-drift read -> regional BLUF / GPI.
    Returns None for US-anchored (calm baseline)."""
    if not drift or drift.get('band') in (None, 'US-anchored'):
        return None
    return {
        'priority':   drift['priority'],
        'category':   'alignment_drift',
        'theatre':    drift['country'],
        'level':      drift['level'],
        'icon':       drift['icon'],
        'color':      drift['color'],
        'short_text': (drift['flag'] + ' ' + drift['country'].upper() + ': ' +
                       drift['inroad_power'] + ' alignment drift -- ' + drift['band']),
        'long_text':  ((drift['so_what_factor'] + ' ' + drift['disclaimer'])[:480]),
    }


def build_so_what_factor(actor_summaries, vector_scores, vector_levels, tripwires_global, commodity_pressure, alignment_drift=None):
    """
    The 'So What' bullets for the rhetoric-afghanistan.html card.
    Returns [{bullet: str, weight: float}] -- plain-language implications,
    estimative voice, highest weight first. Names what each read MEASURES.
    """
    bullets = []
    lv = vector_levels or {}
    esc = ('elevated', 'high', 'surge')

    if lv.get('kinetic_afpak') in esc:
        bullets.append({'weight': 0.95, 'bullet':
            "Af-Pak kinetic vector is " + lv['kinetic_afpak'].upper() + " -- TTP/strike/closure "
            "signal tempo at this level has historically preceded cross-border action cycles. "
            "Watch Torkham/Chaman status and ISPR framing as the 72-hour tells."})
    if lv.get('repression_rights') in esc:
        bullets.append({'weight': 0.9, 'bullet':
            "Repression vector is " + lv['repression_rights'].upper() + " -- decree/enforcement "
            "signal volume at this tempo is the normalization ceiling in action: each cycle "
            "historically resets Western engagement and hands the isolation camp its case. "
            "Origin matters: Kandahar-sourced edicts over Kabul objection = the cohesion tell."})
    if lv.get('external_friction') in esc:
        bullets.append({'weight': 0.85, 'bullet':
            "External-wheels vector is " + lv['external_friction'].upper() + " -- multiple "
            "powers signaling on Kabul simultaneously. Mixed-polarity convergence (friction + "
            "normalization + extraction at once) is the contested-node pattern that has "
            "historically preceded competitive positioning cascades."})
    if lv.get('illicit_economy') in esc:
        bullets.append({'weight': 0.7, 'bullet':
            "Illicit-economy vector is " + lv['illicit_economy'].upper() + " -- seizure/"
            "trafficking signal volume (NOT price) rising along the Iran/Pakistan/Central Asia "
            "corridors. Post-ban, this measures meth throughput and stockpile drawdown -- "
            "revenue that reaches both regime-adjacent networks and their rivals."})

    # ISKP two-theater read
    _iskp = (actor_summaries or {}).get('iskp', {})
    if _iskp.get('level') in ('high', 'surge'):
        bullets.append({'weight': 0.92, 'bullet':
            "ISKP tempo is " + _iskp.get('level','high').upper() + " -- external attribution "
            "would be a two-theater event by construction (target country + Kabul relationship), "
            "and paradoxically normalization fuel: struck powers historically deepen Taliban "
            "security engagement afterward (Moscow/Kerman precedents)."})

    # tripwire callouts
    tw_ids = {(tw.get('tripwire') or tw.get('id')) for tw in (tripwires_global or []) if isinstance(tw, dict)}
    if 'recognition_event' in tw_ids:
        bullets.append({'weight': 0.88, 'bullet':
            "A recognition event fired this window -- each formal recognition historically "
            "lowers the next state's cost (Russia 2025 = the dam-break precedent). The cascade "
            "question is THE alignment story for this theater."})
    if 'mass_deportation_wave' in tw_ids:
        bullets.append({'weight': 0.8, 'bullet':
            "Deportation-wave signals active -- forced-return reabsorption into a collapsed "
            "economy. Bidirectional pressure: a lever on Kabul AND a humanitarian shock; the "
            "platform's displacement sensor carries the flow counts."})

    # normalization drift
    if alignment_drift and alignment_drift.get('band') in ('Drifting', 'Realigning'):
        bullets.append({'weight': 0.86, 'bullet':
            "Normalization drift reads " + alignment_drift['band'].upper() + " -- engagement-"
            "bloc inroads (recognition precedent, extraction contracts) are outpacing "
            "rights-conditioned counter-pressure. " + alignment_drift.get('disclaimer', '')})

    # commodity coupling (wheat = the humanitarian transmission line)
    if commodity_pressure and isinstance(commodity_pressure, dict):
        try:
            _keys = [k for k in ('wheat', 'oil') if k in str(commodity_pressure).lower()]
            if _keys:
                bullets.append({'weight': 0.65, 'bullet':
                    "Commodity news-signal pressure active on " + '/'.join(_keys) + " (weighted "
                    "news volume/severity, not price) -- for Afghanistan the wheat channel "
                    "transmits directly into food insecurity: the platform's tightest "
                    "commodity-to-humanitarian coupling."})
        except Exception:
            pass

    if not bullets:
        bullets.append({'weight': 0.3, 'bullet':
            "All four vectors at baseline this scan. Baseline for a contested node still means "
            "four wheels turning: Iran friction, Pakistan kinetic, Russia normalization, China "
            "extraction -- quiet is a posture here, not an absence."})

    bullets.sort(key=lambda b: -b['weight'])
    return bullets[:6]

def interpret_afghanistan_signals(scan_data):
    """
    Convenience wrapper — accepts a complete scan_data dict and returns the
    three derived analytical fields. Mirrors the Japan tracker's contract.
    """
    actor_summaries        = scan_data.get('actor_summaries', {}) or {}
    vector_scores          = scan_data.get('vector_scores', {}) or {}
    vector_levels          = scan_data.get('vector_levels', {}) or {}
    tripwires_global       = scan_data.get('tripwires_global', []) or []
    commodity_pressure     = scan_data.get('commodity_pressure', {}) or {}
    crosstheater_amplifiers = scan_data.get('crosstheater_amplifiers', {}) or {}

    drift = score_alignment_drift(actor_summaries, tripwires_global,
                                  commodity_pressure, crosstheater_amplifiers,
                                  country='afghanistan')
    return {
        'top_signals':       build_top_signals(actor_summaries, tripwires_global,
                                                commodity_pressure, crosstheater_amplifiers),
        'executive_summary': build_executive_summary(actor_summaries, vector_scores,
                                                     vector_levels, tripwires_global),
        'so_what':           build_so_what_factor(actor_summaries, vector_scores, vector_levels,
                                                   tripwires_global, commodity_pressure,
                                                   alignment_drift=drift),
        'alignment_drift':   drift,
    }


print("[Afghanistan Signal Interpreter] Module loaded — v1.0.0")

