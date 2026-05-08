"""
Asifah Analytics -- Japan Signal Interpreter
v1.0.0 -- May 2026

Generates the "So What" analytical narrative for Japan rhetoric tracker.
Dual-dashboard interpretation:
  - Inbound: pressure FROM China/DPRK/Russia/Senkaku/Okinawa/Taiwan-spillover
  - Outbound: Japan's military and constitutional posture (PM/MOFA/MoD/LDP/US)

Output structure (canonical across all signal interpreters):
  {
    'scenario':         str,      # Top-line narrative tag
    'scenario_color':   str,      # Hex
    'scenario_icon':    str,      # Emoji
    'situation':        str,      # 1-2 sentence current state summary
    'key_indicators':   [str],    # 3-5 bullet points (high-priority signals)
    'assessment':       str,      # 1-2 sentence interpretation/forecast
    'watch_list':       [str],    # 3-5 things to watch next
    'red_lines':        [str],    # Tripwires that would change assessment
    'historical_match': dict,     # Optional historical analog
    'confidence_note':  str,
    'generated_at':     str,
  }
"""

from datetime import datetime, timezone


# ============================================
# SCENARIOS
# ============================================
SCENARIOS = {
    'baseline': {
        'name': 'Baseline Posture',
        'color': '#6b7280',
        'icon': '○',
        'description': 'No active escalation; routine institutional rhetoric.',
    },
    'rhetoric_spike': {
        'name': 'Rhetoric Spike',
        'color': '#3b82f6',
        'icon': '◐',
        'description': 'Statements above baseline; no operational follow-through yet.',
    },
    'inbound_pressure': {
        'name': 'Inbound Pressure',
        'color': '#f59e0b',
        'icon': '▼',
        'description': 'External actors (China/DPRK/Russia) escalating against Japan.',
    },
    'outbound_posture': {
        'name': 'Outbound Posture Shift',
        'color': '#f97316',
        'icon': '▲',
        'description': 'Japan moving toward active military/constitutional commitment.',
    },
    'dual_escalation': {
        'name': 'Dual-Track Escalation',
        'color': '#ef4444',
        'icon': '⚠',
        'description': 'Simultaneous inbound pressure AND Japan posture hardening.',
    },
    'article9_active': {
        'name': 'Article 9 Crisis',
        'color': '#dc2626',
        'icon': '🚨',
        'description': 'Constitutional reinterpretation in active legislative motion.',
    },
    'kinetic': {
        'name': 'Kinetic Activity',
        'color': '#991b1b',
        'icon': '🔥',
        'description': 'Active military force in use against Japan or by Japan.',
    },
}


# ============================================
# HELPERS
# ============================================
def _get_actor(scan_data, actor_key):
    """Safely get an actor dict from scan_data."""
    return (scan_data.get('actors', {}) or {}).get(actor_key, {}) or {}


def _actor_level(scan_data, actor_key):
    return int(_get_actor(scan_data, actor_key).get('level', 0) or 0)


def _actor_tripwires(scan_data, actor_key):
    return _get_actor(scan_data, actor_key).get('tripwires', {}) or {}


def _check_article9_state(scan_data):
    """Determine Article 9 escalation state from PM and Diet tripwires."""
    pm_tw = _actor_tripwires(scan_data, 'pm_cabinet')
    diet_tw = _actor_tripwires(scan_data, 'ldp_diet')

    if pm_tw.get('article9_l5'):
        return 'kinetic'
    if pm_tw.get('article9_l4') or diet_tw.get('article9_l4'):
        return 'diet_vote'
    if pm_tw.get('article9_l3') or diet_tw.get('article9_l3'):
        return 'cabinet_decision'
    if pm_tw.get('article9_l2'):
        return 'rhetoric'
    return 'dormant'


def _check_taiwan_defense_state(scan_data):
    """Is Japan publicly committing to Taiwan defense?"""
    pm_tw = _actor_tripwires(scan_data, 'pm_cabinet')
    if pm_tw.get('taiwan_defense_l4'):
        return 'invoked'
    if pm_tw.get('taiwan_defense_l3'):
        return 'committed'
    return 'baseline'


# ============================================
# SO WHAT BUILDER
# ============================================
def _build_so_what(scan_data, red_lines_triggered=None, historical_matches=None):
    """Generate the analytical narrative for Japan."""
    if red_lines_triggered is None:
        red_lines_triggered = []
    if historical_matches is None:
        historical_matches = []

    overall = int(scan_data.get('overall_level', 0) or 0)
    inbound_max = int(scan_data.get('inbound_max_level', 0) or 0)
    outbound_max = int(scan_data.get('outbound_max_level', 0) or 0)

    # Per-actor levels
    china_lv = _actor_level(scan_data, 'china_threat')
    dprk_lv = _actor_level(scan_data, 'dprk_threat')
    russia_lv = _actor_level(scan_data, 'russia_threat')
    senkaku_lv = _actor_level(scan_data, 'senkaku_intrusion')
    okinawa_lv = _actor_level(scan_data, 'okinawa_pressure')
    taiwan_proximity_lv = _actor_level(scan_data, 'taiwan_strait_proximity')

    pm_lv = _actor_level(scan_data, 'pm_cabinet')
    mofa_lv = _actor_level(scan_data, 'mofa')
    mod_lv = _actor_level(scan_data, 'mod_jsdf')
    diet_lv = _actor_level(scan_data, 'ldp_diet')
    us_lv = _actor_level(scan_data, 'us_alliance')

    article9_state = _check_article9_state(scan_data)
    taiwan_defense_state = _check_taiwan_defense_state(scan_data)

    # ── Scenario selection ──
    if overall >= 5:
        scenario_key = 'kinetic'
    elif article9_state in ('cabinet_decision', 'diet_vote'):
        scenario_key = 'article9_active'
    elif inbound_max >= 3 and outbound_max >= 3:
        scenario_key = 'dual_escalation'
    elif outbound_max >= 3:
        scenario_key = 'outbound_posture'
    elif inbound_max >= 3:
        scenario_key = 'inbound_pressure'
    elif overall >= 1:
        scenario_key = 'rhetoric_spike'
    else:
        scenario_key = 'baseline'

    scenario = SCENARIOS[scenario_key]

    # ── Situation summary ──
    situation_parts = []
    if inbound_max >= 3:
        threat_actors = []
        if china_lv >= 3:
            threat_actors.append(f'China (L{china_lv})')
        if dprk_lv >= 3:
            threat_actors.append(f'DPRK (L{dprk_lv})')
        if russia_lv >= 3:
            threat_actors.append(f'Russia (L{russia_lv})')
        if senkaku_lv >= 3:
            threat_actors.append(f'Senkaku CCG incursions (L{senkaku_lv})')
        if okinawa_lv >= 3:
            threat_actors.append(f'Okinawa PLA pressure (L{okinawa_lv})')
        if threat_actors:
            situation_parts.append(f"Inbound pressure active from: {', '.join(threat_actors)}.")
    elif inbound_max == 0:
        situation_parts.append("No active inbound threat signals against Japan.")
    else:
        situation_parts.append(f"Inbound rhetoric below operational threshold (max L{inbound_max}).")

    if outbound_max >= 3:
        posture_actors = []
        if pm_lv >= 3:
            posture_actors.append(f'PM Cabinet (L{pm_lv})')
        if mod_lv >= 3:
            posture_actors.append(f'MoD/JSDF (L{mod_lv})')
        if diet_lv >= 3:
            posture_actors.append(f'LDP/Diet (L{diet_lv})')
        if posture_actors:
            situation_parts.append(f"Japan outbound posture hardening: {', '.join(posture_actors)}.")
    elif outbound_max == 0:
        situation_parts.append("Japan posture at baseline — no significant defense rhetoric spike.")

    if article9_state == 'cabinet_decision':
        situation_parts.append("Article 9 reinterpretation in active cabinet motion.")
    elif article9_state == 'diet_vote':
        situation_parts.append("⚠ Article 9 reinterpretation under Diet vote — major constitutional moment.")
    elif article9_state == 'rhetoric':
        situation_parts.append("Article 9 reinterpretation language present in PM rhetoric (sub-cabinet level).")

    if taiwan_defense_state == 'committed':
        situation_parts.append("PM has publicly committed to Taiwan defense scenarios.")
    elif taiwan_defense_state == 'invoked':
        situation_parts.append("⚠ Taiwan emergency / collective self-defense formally invoked.")

    situation = ' '.join(situation_parts)

    # ── Key indicators ──
    indicators = []

    if article9_state == 'diet_vote':
        indicators.append('Article 9 reinterpretation in Diet vote — historic constitutional escalation.')
    elif article9_state == 'cabinet_decision':
        indicators.append('Cabinet has approved (or is approving) new Article 9 interpretation.')

    if taiwan_defense_state == 'invoked':
        indicators.append('Japan has formally invoked Taiwan emergency / collective self-defense — alliance posture shift.')
    elif taiwan_defense_state == 'committed':
        indicators.append('PM has publicly committed Japan to Taiwan defense — represents threshold change vs. prior governments.')

    mod_tw = _actor_tripwires(scan_data, 'mod_jsdf')
    if mod_tw.get('strike_capability'):
        indicators.append('JSDF long-range strike capability deployment milestone — Tomahawk/Type-12 stand-off operational.')

    if china_lv >= 4:
        indicators.append(f'China inbound threat at L{china_lv} (Operational) — Eastern Theater Command in active patrol mode against Japan.')
    elif china_lv >= 3:
        indicators.append(f'China inbound at L{china_lv} (Directive) — sustained MFA/MoD pressure against Tokyo.')

    if senkaku_lv >= 3:
        indicators.append(f'China Coast Guard active in Senkaku waters (L{senkaku_lv}) — sustained sovereignty pressure.')

    if okinawa_lv >= 3:
        indicators.append(f'PLA pressure on Okinawa/Ryukyu southwest islands (L{okinawa_lv}).')

    if dprk_lv >= 3:
        indicators.append(f'North Korean missile threat against Japan elevated (L{dprk_lv}) — possible J-Alert event window.')

    if taiwan_proximity_lv >= 2:
        indicators.append(f'Taiwan Strait spillover into Japan ADIZ (L{taiwan_proximity_lv}).')

    if us_lv >= 3 and not mod_tw.get('brake_language'):
        indicators.append(f'US-Japan alliance signaling at L{us_lv} — INDOPACOM/treaty language reinforcing Japan posture.')

    # Trim to top 5
    indicators = indicators[:5]
    if not indicators:
        indicators = ['No high-priority indicators above baseline. Routine institutional rhetoric only.']

    # ── Assessment ──
    if scenario_key == 'kinetic':
        assessment = ("Active kinetic activity involving Japan or JSDF forces detected. "
                     "This represents the highest escalation tier and requires immediate authoritative-source verification.")
    elif scenario_key == 'article9_active':
        assessment = ("Constitutional reinterpretation is in active legislative motion — represents the most consequential "
                     "shift in Japan's defense posture since 2015 collective self-defense reinterpretation. Watch for "
                     "regional ally responses (US backing, China condemnation, ROK positioning) and Komeito coalition stability.")
    elif scenario_key == 'dual_escalation':
        assessment = ("Both inbound pressure and Japan's outbound posture are simultaneously elevated — classical "
                     "convergence pattern that historically precedes alliance-coordination cycles or crisis-management "
                     "summits. Watch for surge in US-Japan-Korea trilateral signaling.")
    elif scenario_key == 'outbound_posture':
        assessment = ("Japan is publicly hardening its defense posture without proportional inbound trigger — suggests "
                     "domestic political timing (Diet vote, election pressure) or anticipatory positioning ahead of "
                     "expected Taiwan/ECS contingencies.")
    elif scenario_key == 'inbound_pressure':
        assessment = ("External pressure on Japan is elevated; Japan's own posture remains comparatively measured. "
                     "Pattern suggests Japan in absorption/diplomatic mode rather than confrontation. Watch MOFA "
                     "statements and JCG/JSDF response language for shift to active counter-posturing.")
    elif scenario_key == 'rhetoric_spike':
        assessment = ("Rhetoric is above baseline but no operational follow-through detected. Pattern is consistent "
                     "with normal political-cycle posturing or response to a specific recent incident.")
    else:
        assessment = ("Japan's posture is at baseline. No actionable signals above routine institutional traffic.")

    # ── Watch list ──
    watch_items = []
    if scenario_key in ('article9_active', 'dual_escalation', 'outbound_posture'):
        watch_items.append('Komeito (LDP coalition partner) statements on Article 9 — they have historically been the restraining vector.')
        watch_items.append('Upcoming Diet sessions and committee schedules — watch for security legislation calendar.')
    if scenario_key in ('inbound_pressure', 'dual_escalation'):
        watch_items.append('China MFA daily briefings + Eastern Theater Command WeChat — escalation cadence.')
        watch_items.append('JCG dispatches in Senkaku waters and JASDF scramble counts.')
    if dprk_lv >= 2:
        watch_items.append('KCNA / Rodong Sinmun statements + missile test windows.')
    if russia_lv >= 2:
        watch_items.append('Russian Pacific Fleet movements + Hokkaido approach incidents.')
    if pm_lv >= 3:
        watch_items.append('Cabinet Secretary press briefings + Kantei.go.jp official statements.')
    if mod_lv >= 3:
        watch_items.append('JSDF deployment orders + MoD official press briefings.')

    # Default fallbacks
    if not watch_items:
        watch_items.append('PM Takaichi public statements + MOFA Diplomatic Bluebook updates.')
        watch_items.append('Diet defense committee schedules.')
        watch_items.append('CCG presence in Senkaku contiguous zone.')
    watch_items = watch_items[:5]

    # ── Red lines (tripwires that would change the picture) ──
    red_lines = [
        '🚨 PM formally invokes "potentially critical situation" for Taiwan — auto-escalates outbound to L4.',
        '🚨 Diet votes on Article 9 reinterpretation — historic constitutional escalation.',
        '🚨 PLA fires across median line into JADIZ — auto-escalates inbound to L4+.',
        '🚨 DPRK missile lands in Japan EEZ or territorial waters — auto-escalates DPRK threat to L4-L5.',
        '🚨 China Coast Guard fires at JCG vessels at Senkaku — kinetic threshold breach.',
        '🚨 First Tomahawk delivery operational — strike capability milestone.',
    ]

    # ── Confidence note ──
    confidence_note = (
        'This assessment is generated algorithmically from open-source signal data (RSS, GDELT, NewsAPI, '
        'Brave Search, BlueSky aggregation). It is not a prediction and should not be used as the sole basis '
        'for any decision. Cross-reference with authoritative sources (MOFA, Kantei, DoD official channels, '
        'Reuters/AP newswires).'
    )

    return {
        'scenario':         scenario['name'],
        'scenario_color':   scenario['color'],
        'scenario_icon':    scenario['icon'],
        'scenario_key':     scenario_key,
        'situation':        situation,
        'key_indicators':   indicators,
        'assessment':       assessment,
        'watch_list':       watch_items,
        'red_lines':        red_lines,
        'historical_match': None,  # Reserved for future historical-analog matching
        'confidence_note':  confidence_note,
        'generated_at':     datetime.now(timezone.utc).isoformat(),
    }


# ============================================
# PUBLIC ENTRY POINT
# ============================================
def interpret_japan_signals(scan_data):
    """Public entry — generate full interpretation from scan_data."""
    if not scan_data or not isinstance(scan_data, dict):
        return None
    try:
        return _build_so_what(scan_data)
    except Exception as e:
        print(f"[Japan Interpreter] Error: {str(e)[:200]}")
        return None


# ============================================================
# v2.1+ — TOP SIGNALS (BLUF / GPI consumable) + CONVERGENCES
# ============================================================
# May 7 2026 — Japan upgraded to canonical signal architecture.
# Previously Japan only emitted scenario+situation+assessment ("So What"),
# which was rich but not consumable by Asia Regional BLUF or GPI.
# This module brings Japan to parity with China and Taiwan.
#
# Canonical signal shape (matches china/taiwan):
# {
#     'priority':   int (0-15, higher = more important),
#     'category':   str,        # see Japan-specific categories below
#     'theatre':    'japan',
#     'level':      0-5,
#     'icon':       str (emoji),
#     'color':      str (hex),
#     'short_text': str (≤80 chars),
#     'long_text':  str (≤200 chars),
# }
#
# Japan-specific signal categories:
#   article9_active             — constitutional reinterpretation in motion
#   taiwan_defense_committed    — PM publicly committing to Taiwan defense
#   strike_capability_milestone — counterstrike doctrine hardening
#   senkaku_intrusion           — CCG incursions in disputed waters
#   okinawa_pressure            — PLA proximity to US bases
#   dprk_missile_threat         — DPRK launch / nuclear signaling
#   inbound_pressure_high       — composite inbound L4+
#   outbound_posture_high       — composite outbound L3+
#   theatre_high                — overall L4+
#   us_alliance_strong          — trilateral coordination signaling
#   hormuz_japan_oil_dependency — commodity convergence (Hormuz × ~99% oil import)
#   senkaku_ree_convergence     — commodity convergence (China REE × Senkaku tension)

JAPAN_FLAG = '\U0001f1ef\U0001f1f5'  # 🇯🇵


def build_commodity_convergence_signals(scan_data):
    """
    Inject commodity-derived convergence signals into Japan's top_signals.
    Reads cross-theater amplifiers from scan_data and emits signals when
    structural commodity dependencies intersect with active geopolitical pressure.

    Japan-specific convergences:

      1. HORMUZ-JAPAN OIL CONVERGENCE — Japan's ~99% oil import dependency
         (mostly from Middle East via Hormuz) creates compound energy security
         risk when Iran pressures Hormuz. Strategic petroleum reserve ~240 days
         (largest IEA stockpile) provides better cushion than Taiwan's ~140 days,
         but still meaningful exposure.

      2. SENKAKU-REE CONVERGENCE — When China outbound is at L3+ AND Senkaku
         CCG intrusions are active, Japan's REE import dependency (~60% China-
         sourced for heavy rare earths) becomes acute. Historical analog:
         2010 Senkaku dispute → China REE export embargo. JOGMEC stockpile +
         Lynas Australia partnership are mitigation but not full insurance.

    Returns list of signal dicts. Empty list if no convergence is currently active.
    """
    signals = []

    amps = scan_data.get('crosstheater_amplifiers', {}) or {}
    iran_hormuz_active = amps.get('iran_hormuz_pressure', False)
    iran_score         = amps.get('iran_theatre_score', 0) or 0
    iran_irgc          = amps.get('iran_irgc_level', 0) or 0
    china_outbound_max = amps.get('china_outbound_max', 0) or 0
    senkaku_active     = amps.get('senkaku_active', False)

    # ── HORMUZ-JAPAN OIL CONVERGENCE ──
    if iran_hormuz_active:
        signals.append({
            'priority':   13,
            'category':   'hormuz_japan_oil_dependency',
            'theatre':    'japan',
            'level':      max(3, min(5, int(iran_score / 20))),
            'icon':       '🛢️',
            'color':      '#f59e0b',
            'short_text': f'{JAPAN_FLAG} JAPAN: Hormuz oil convergence — ~99% oil import dep',
            'long_text':  (
                f'JAPAN oil supply convergence — Iran posture (score {iran_score}, '
                f'IRGC L{iran_irgc}) compounds Japan\'s ~99% crude oil import dependency '
                f'(~90% from Middle East). ~240-day strategic petroleum reserve provides '
                f'cushion but Hormuz disruption stresses energy security framing of '
                f'US-Japan alliance. Watch ENEOS/Idemitsu reserve announcements, METI '
                f'energy security briefings, alliance coordination on alternative routing.'
            ),
            'hormuz_japan_oil_dependency_active': True,
            'convergence_states': {
                'hormuz_japan_oil_dependency': {
                    'active':       True,
                    'iran_score':   iran_score,
                    'iran_irgc':    iran_irgc,
                    'alert_level':  'elevated' if iran_score < 70 else ('high' if iran_score < 85 else 'surge'),
                },
            },
        })

    # ── SENKAKU-REE CONVERGENCE ──
    # Fires when China outbound is hardening AND Senkaku tensions are active.
    # Historical analog: 2010 Senkaku boat collision → China REE embargo.
    if china_outbound_max >= 3 and senkaku_active:
        signals.append({
            'priority':   12,
            'category':   'senkaku_ree_convergence',
            'theatre':    'japan',
            'level':      max(3, china_outbound_max),
            'icon':       '⚗️',
            'color':      '#f97316',
            'short_text': f'{JAPAN_FLAG} JAPAN: Senkaku × China REE leverage convergence',
            'long_text':  (
                f'JAPAN supply chain convergence — China outbound at L{china_outbound_max} '
                f'+ active Senkaku CCG intrusions creates classic 2010-pattern leverage '
                f'risk. Japan ~60% China-dependent for heavy rare earths despite Lynas '
                f'Australia partnership and JOGMEC stockpile. Historical analog: 2010 '
                f'Senkaku boat collision triggered de facto China REE export embargo. '
                f'Watch METI export-control statements, JOGMEC stockpile announcements, '
                f'Lynas/REE alternative-supply news.'
            ),
            'senkaku_ree_convergence_active': True,
            'convergence_states': {
                'senkaku_ree_convergence': {
                    'active':              True,
                    'china_outbound_max':  china_outbound_max,
                    'senkaku_active':      True,
                    'alert_level':         'high' if china_outbound_max >= 4 else 'elevated',
                },
            },
        })

    return signals


def build_top_signals(scan_data):
    """
    Build Japan's top_signals[] for BLUF/GPI consumption.
    Reads from scan_data (post-interpret_japan_signals output + crosstheater_amplifiers).
    Returns sorted list (descending priority).
    """
    signals = []

    overall_level = int(scan_data.get('overall_level', 0) or 0)
    inbound_max   = int(scan_data.get('inbound_max_level', 0) or 0)
    outbound_max  = int(scan_data.get('outbound_max_level', 0) or 0)
    theatre_score = int(scan_data.get('theatre_score', 0) or 0)

    # Per-actor levels
    china_lv          = _actor_level(scan_data, 'china_threat')
    dprk_lv           = _actor_level(scan_data, 'dprk_threat')
    russia_lv         = _actor_level(scan_data, 'russia_threat')
    senkaku_lv        = _actor_level(scan_data, 'senkaku_intrusion')
    okinawa_lv        = _actor_level(scan_data, 'okinawa_pressure')
    taiwan_prox_lv    = _actor_level(scan_data, 'taiwan_strait_proximity')
    pm_lv             = _actor_level(scan_data, 'pm_cabinet')
    mod_lv            = _actor_level(scan_data, 'mod_jsdf')
    diet_lv           = _actor_level(scan_data, 'ldp_diet')
    us_lv             = _actor_level(scan_data, 'us_alliance')

    article9_state    = _check_article9_state(scan_data)
    taiwan_def_state  = _check_taiwan_defense_state(scan_data)

    # ============================================
    # 1. ARTICLE 9 STATE (Japan-unique constitutional watch)
    # ============================================
    if article9_state == 'kinetic':
        signals.append({
            'priority':   14,
            'category':   'article9_active',
            'theatre':    'japan',
            'level':      5,
            'icon':       '🚨',
            'color':      '#dc2626',
            'short_text': f'{JAPAN_FLAG} JAPAN: Article 9 kinetic invocation L5',
            'long_text':  f'JAPAN Article 9 reinterpretation at kinetic-invocation level — collective self-defense activated for active conflict scenario. Constitutional threshold breached.',
        })
    elif article9_state == 'diet_vote':
        signals.append({
            'priority':   13,
            'category':   'article9_active',
            'theatre':    'japan',
            'level':      4,
            'icon':       '🏛️',
            'color':      '#dc2626',
            'short_text': f'{JAPAN_FLAG} JAPAN: Article 9 Diet vote — L4 constitutional motion',
            'long_text':  f'JAPAN Article 9 reinterpretation at Diet-vote stage — legislative ratification of cabinet decision in active motion. Major postwar constitutional shift in progress.',
        })
    elif article9_state == 'cabinet_decision':
        signals.append({
            'priority':   11,
            'category':   'article9_active',
            'theatre':    'japan',
            'level':      3,
            'icon':       '🏛️',
            'color':      '#f97316',
            'short_text': f'{JAPAN_FLAG} JAPAN: Article 9 cabinet decision L3',
            'long_text':  f'JAPAN Article 9 cabinet-decision level — formal reinterpretation language; Diet ratification likely next step. 2015 collective self-defense analog.',
        })
    elif article9_state == 'rhetoric':
        signals.append({
            'priority':   6,
            'category':   'article9_active',
            'theatre':    'japan',
            'level':      2,
            'icon':       '📜',
            'color':      '#f59e0b',
            'short_text': f'{JAPAN_FLAG} JAPAN: Article 9 reinterpretation rhetoric L2',
            'long_text':  f'JAPAN Article 9 reinterpretation rhetoric L2 — political language signaling potential constitutional motion; below cabinet-decision threshold.',
        })

    # ============================================
    # 2. TAIWAN DEFENSE COMMITMENT (trilateral signal)
    # ============================================
    if taiwan_def_state == 'invoked':
        signals.append({
            'priority':   13,
            'category':   'taiwan_defense_committed',
            'theatre':    'japan',
            'level':      4,
            'icon':       '🤝',
            'color':      '#dc2626',
            'short_text': f'{JAPAN_FLAG} JAPAN: Taiwan defense L4 — collective self-defense invoked',
            'long_text':  f'JAPAN Taiwan defense at L4 — collective self-defense framework invoked for Taiwan contingency; trilateral US-Japan-Taiwan coordination signaling explicit. Major shift from strategic ambiguity.',
        })
    elif taiwan_def_state == 'committed':
        signals.append({
            'priority':   11,
            'category':   'taiwan_defense_committed',
            'theatre':    'japan',
            'level':      3,
            'icon':       '🤝',
            'color':      '#f97316',
            'short_text': f'{JAPAN_FLAG} JAPAN: Taiwan defense commitment L3',
            'long_text':  f'JAPAN Taiwan defense commitment at L3 — PM-level public commitment to Taiwan contingency. 2021 Suga-Biden statement analog. Historic threshold change vs prior governments.',
        })

    # ============================================
    # 3. THEATRE-HIGH (overall L4+)
    # ============================================
    if overall_level >= 4:
        signals.append({
            'priority':   9 + overall_level,
            'category':   'theatre_high',
            'theatre':    'japan',
            'level':      overall_level,
            'icon':       '🔴',
            'color':      '#dc2626' if overall_level >= 5 else '#ef4444',
            'short_text': f'{JAPAN_FLAG} JAPAN L{overall_level} — composite posture',
            'long_text':  f'JAPAN at L{overall_level} — composite posture (theatre score {theatre_score}/100). Inbound L{inbound_max} × outbound L{outbound_max}; multi-vector activation.',
        })

    # ============================================
    # 4. STRIKE CAPABILITY MILESTONE
    # ============================================
    mod_tw = _actor_tripwires(scan_data, 'mod_jsdf')
    pm_tw  = _actor_tripwires(scan_data, 'pm_cabinet')
    if mod_tw.get('strike_capability') or pm_tw.get('strike_capability'):
        signals.append({
            'priority':   10,
            'category':   'strike_capability_milestone',
            'theatre':    'japan',
            'level':      max(3, mod_lv, pm_lv),
            'icon':       '⚔️',
            'color':      '#f97316',
            'short_text': f'{JAPAN_FLAG} JAPAN: Counterstrike capability milestone',
            'long_text':  f'JAPAN counterstrike capability milestone — MoD/PM language indicating standoff/counterstrike doctrine hardening. Tomahawk procurement, hypersonic R&D, base-strike authorization signals.',
        })

    # ============================================
    # 5. SENKAKU INTRUSION (Japan-specific actor)
    # ============================================
    if senkaku_lv >= 4:
        signals.append({
            'priority':   10,
            'category':   'senkaku_intrusion',
            'theatre':    'japan',
            'level':      senkaku_lv,
            'icon':       '🌊',
            'color':      '#dc2626',
            'short_text': f'{JAPAN_FLAG} JAPAN: Senkaku CCG intrusion L{senkaku_lv}',
            'long_text':  f'JAPAN Senkaku Islands CCG intrusion at L{senkaku_lv} — sustained gray-zone presence in disputed waters; coast guard friction at operational tempo.',
        })
    elif senkaku_lv >= 3:
        signals.append({
            'priority':   7,
            'category':   'senkaku_intrusion',
            'theatre':    'japan',
            'level':      senkaku_lv,
            'icon':       '🌊',
            'color':      '#f97316',
            'short_text': f'{JAPAN_FLAG} JAPAN: Senkaku CCG intrusion L{senkaku_lv}',
            'long_text':  f'JAPAN Senkaku gray-zone activity L{senkaku_lv} — China Coast Guard presence above baseline; legal/political messaging vector.',
        })

    # ============================================
    # 6. OKINAWA PRESSURE (PLA proximity to US bases)
    # ============================================
    if okinawa_lv >= 3:
        signals.append({
            'priority':   8,
            'category':   'okinawa_pressure',
            'theatre':    'japan',
            'level':      okinawa_lv,
            'icon':       '🛡️',
            'color':      '#f97316',
            'short_text': f'{JAPAN_FLAG} JAPAN: Okinawa PLA pressure L{okinawa_lv}',
            'long_text':  f'JAPAN Okinawa pressure L{okinawa_lv} — PLA proximity to US Marine Corps bases; first-island-chain operational stress on alliance posture.',
        })

    # ============================================
    # 7. DPRK MISSILE THREAT
    # ============================================
    if dprk_lv >= 4:
        signals.append({
            'priority':   9,
            'category':   'dprk_missile_threat',
            'theatre':    'japan',
            'level':      dprk_lv,
            'icon':       '🚀',
            'color':      '#dc2626',
            'short_text': f'{JAPAN_FLAG} JAPAN: DPRK threat L{dprk_lv}',
            'long_text':  f'JAPAN DPRK threat at L{dprk_lv} — missile launch / nuclear signaling above warning threshold; J-Alert posture relevant.',
        })
    elif dprk_lv >= 3:
        signals.append({
            'priority':   6,
            'category':   'dprk_missile_threat',
            'theatre':    'japan',
            'level':      dprk_lv,
            'icon':       '🚀',
            'color':      '#f97316',
            'short_text': f'{JAPAN_FLAG} JAPAN: DPRK threat L{dprk_lv}',
            'long_text':  f'JAPAN DPRK threat L{dprk_lv} — missile launch cycle or nuclear rhetoric; Japan-specific exposure given trans-Sea-of-Japan range geometry.',
        })

    # ============================================
    # 8. INBOUND PRESSURE COMPOSITE (L4+)
    # ============================================
    if inbound_max >= 4:
        signals.append({
            'priority':   8,
            'category':   'inbound_pressure_high',
            'theatre':    'japan',
            'level':      inbound_max,
            'icon':       '⬇️',
            'color':      '#ef4444',
            'short_text': f'{JAPAN_FLAG} JAPAN: Inbound pressure L{inbound_max}',
            'long_text':  f'JAPAN inbound composite L{inbound_max} — multi-actor external pressure (China/DPRK/Russia/Senkaku/Okinawa); incident-level tempo.',
        })

    # ============================================
    # 9. OUTBOUND POSTURE COMPOSITE (L3+)
    # ============================================
    if outbound_max >= 3:
        signals.append({
            'priority':   7 + outbound_max,
            'category':   'outbound_posture_high',
            'theatre':    'japan',
            'level':      outbound_max,
            'icon':       '⬆️',
            'color':      '#f97316' if outbound_max < 4 else '#dc2626',
            'short_text': f'{JAPAN_FLAG} JAPAN: Outbound posture L{outbound_max}',
            'long_text':  f'JAPAN outbound posture L{outbound_max} — PM/MoD/Diet hardening across constitutional, military, and alliance vectors.',
        })

    # ============================================
    # 10. US ALLIANCE SIGNALING (positive trilateral indicator)
    # ============================================
    if us_lv >= 4:
        signals.append({
            'priority':   8,
            'category':   'us_alliance_strong',
            'theatre':    'japan',
            'level':      us_lv,
            'icon':       '🇺🇸',
            'color':      '#10b981',
            'short_text': f'{JAPAN_FLAG} JAPAN: US alliance signaling L{us_lv}',
            'long_text':  f'JAPAN-US alliance signaling at L{us_lv} — joint statements, base agreements, RAA updates, AUKUS Pillar 2 expansion. Trilateral coordination firming.',
        })

    # ============================================
    # 11. COMMODITY + ALLIANCE CONVERGENCES (cross-regional)
    # ============================================
    try:
        convergence_signals = build_commodity_convergence_signals(scan_data)
        if convergence_signals:
            signals.extend(convergence_signals)
            print(f"[Japan Interpreter] Convergence: {len(convergence_signals)} signal(s) emitted")
    except Exception as e:
        print(f"[Japan Interpreter] Convergence error: {e}")

    # Sort descending; BLUF will dedupe + globally rank
    signals.sort(key=lambda s: s['priority'], reverse=True)
    return signals
