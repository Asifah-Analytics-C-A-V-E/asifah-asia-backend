"""
taiwan_signal_interpreter.py
Asifah Analytics -- Asia Backend Module
v1.0.0 -- April 2026

Signal interpretation engine for the Taiwan Deterrence Tracker.

Taiwan's analytical frame is fundamentally DEFENSIVE (mirror-image of China):

  1. Is deterrence HOLDING or FAILING?
     US partnership + Taiwan defense posture + diplomatic coalition +
     asymmetric resilience -- four vectors that together constitute the
     deterrence architecture. Any one weakening signals deterrence-at-risk.

  2. Is Taiwan's internal resolve holding?
     DPP-KMT unity (or breakdown), mass emigration signals, domestic
     debate about defense spending, conscription crisis. Resolve is the
     unseen prerequisite for deterrence to function.

  3. Is PRC pressure (inbound) converging with deterrence-gap moments?
     Read China fingerprint -- PLA pressure + Beijing coercion +
     economic pressure. Inbound pressure at the same time as coalition
     weakening is the genuine threshold-crossing scenario.

Unique to Taiwan: the "deterrence gap" metric -- difference between
inbound PRC pressure and outbound coalition response. A widening gap
is the single most important signal this tracker produces.

Author: RCGG / Asifah Analytics
"""

from datetime import datetime, timezone


# ============================================================
# RED LINE DEFINITIONS
# ============================================================
RED_LINES = [

    # ── Category A: Deterrence Failure ──────────────────────
    {
        'id':       'us_abandonment_signal',
        'label':    'US Abandonment Signal (Partnership Rollback)',
        'detail':   'US statements signaling reduced Taiwan defense commitment: AIT personnel cuts, '
                    'arms sale cancellations, "Taiwan must defend itself alone" rhetoric',
        'severity': 3,
        'color':    '#dc2626',
        'icon':     '📉',
        'category': 'deterrence_failure',
        'source':   'Deterrence collapses the moment Beijing concludes US will not fight. Historical '
                    'precedent: 1949 State Department "Loss of China" rhetoric preceded Korean War.',
    },
    {
        'id':       'us_arms_deal_cancellation',
        'label':    'Major Taiwan Arms Deal Cancellation',
        'detail':   'Announced F-16 / HIMARS / submarine / munitions package frozen, cancelled, '
                    'or reduced substantially; backlog increases rather than delivers',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '🛒',
        'category': 'deterrence_failure',
        'source':   '$19B+ arms backlog is the material bedrock of Taiwan deterrence. Cancellation '
                    'of any tranche would be read by Beijing as decoupling signal.',
    },

    # ── Category B: Asymmetric Threshold ────────────────────
    {
        'id':       'porcupine_abandoned',
        'label':    'Porcupine Strategy Abandoned (Symmetric Doctrine Returns)',
        'detail':   'Taiwan MND publicly deprioritizes asymmetric doctrine in favor of symmetric '
                    'platform procurement (big-ticket carriers, 4th-gen fighters without asymmetric pivot)',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '🦔',
        'category': 'asymmetric_threshold',
        'source':   'Porcupine/overall defense concept is Taiwan\'s only credible deterrence doctrine '
                    'given resource asymmetry. Symmetric-drift = deterrence-drift.',
    },
    {
        'id':       'conscription_crisis',
        'label':    'Taiwan Conscription / Reserve Crisis',
        'detail':   'Public crisis over conscription enforcement, reservist training failures, '
                    'or mass public opposition to extended military service obligations',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '🪖',
        'category': 'asymmetric_threshold',
        'source':   '1-year conscription restored 2024. Implementation fragility = manpower '
                    'fragility = deterrence fragility.',
    },

    # ── Category C: Coalition Cohesion ──────────────────────
    {
        'id':       'japan_taiwan_formalized',
        'label':    'Japan Formally Commits to Taiwan Defense (DETERRENCE-POSITIVE)',
        'detail':   'Tokyo announces formal Taiwan defense commitment: treaty, SDF stationing, '
                    'explicit collective defense language naming Taiwan',
        'severity': 1,
        'color':    '#22c55e',
        'icon':     '🗾',
        'category': 'coalition_cohesion',
        'source':   'This is a GREEN-LINE event -- strengthening deterrence. Would be generational '
                    'shift from Abe-era "Taiwan emergency = Japan emergency" doctrinal language.',
    },
    {
        'id':       'aukus_fracture',
        'label':    'AUKUS / QUAD Fracture on Taiwan',
        'detail':   'Public split in AUKUS or QUAD on Taiwan defense posture: Australia pulling back, '
                    'UK decoupling from Pacific role, India explicitly distancing from Taiwan question',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '💔',
        'category': 'coalition_cohesion',
        'source':   'Coalition optics matter enormously for Beijing calculus. Public divergence '
                    'is what Beijing waits for -- the wedge that makes coercion viable.',
    },

    # ── Category D: Domestic Resolve ────────────────────────
    {
        'id':       'dpp_kmt_unity_break',
        'label':    'DPP-KMT Unity Breakdown on Defense',
        'detail':   'Public political rupture on defense spending, conscription, or cross-strait '
                    'policy -- opposition party campaigning against deterrence posture',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '🗳️',
        'category': 'domestic_resolve',
        'source':   'Democratic-level divergence on deterrence posture telegraphs to Beijing that '
                    'wait-and-exploit is viable strategy. 2024 election showed this fragility.',
    },
    {
        'id':       'mass_emigration_signal',
        'label':    'Mass Elite Emigration Signal (Brain-Drain Spike)',
        'detail':   'Passport applications, property sales to overseas, semiconductor executives '
                    'relocating families abroad exceed baseline by 2x+',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '✈️',
        'category': 'domestic_resolve',
        'source':   'Hong Kong 2019-2021 pattern: elite exit precedes governance collapse by 12-24 '
                    'months. Leading indicator of resolve failure.',
    },

    # ── Category E: China Direct (inbound) ──────────────────
    {
        'id':       'prc_mobilization_orders',
        'label':    'PRC Mobilization Orders Visible',
        'detail':   'PLA mobilization, sealift staging, or Rocket Force alert status elevated '
                    '(detected via China tracker fingerprint or direct Taiwan-side reporting)',
        'severity': 3,
        'color':    '#dc2626',
        'icon':     '⚔️',
        'category': 'china_direct',
        'source':   'PRC mobilization is the single clearest invasion-imminence indicator. Taiwan '
                    'MND rapid-response doctrine activates at this threshold.',
    },
    {
        'id':       'prc_kinetic_incident',
        'label':    'PRC Kinetic Incident (Live Fire at Taiwan Target)',
        'detail':   'PLA Navy or Air Force opens fire on Taiwan vessel, aircraft, or infrastructure '
                    '(including Kinmen, Matsu, outlying islands)',
        'severity': 3,
        'color':    '#dc2626',
        'icon':     '🚨',
        'category': 'china_direct',
        'source':   'First-kinetic-exchange threshold. Crosses from coercion to active conflict. '
                    '1958 Taiwan Strait Crisis was the prior precedent.',
    },
]


# ============================================================
# HELPERS
# ============================================================
def _scan_actor_articles(actor_results, actor_keys, keywords):
    """Scan top_articles across the given actor(s) for any keyword match."""
    for aid in actor_keys:
        actor_data = actor_results.get(aid, {})
        for art in actor_data.get('top_articles', []):
            title = (art.get('title') or '').lower()
            desc  = (art.get('description') or '').lower()
            text  = f"{title} {desc}"
            if any(kw.lower() in text for kw in keywords):
                return True
    return False


def _rl(rl_id):
    """Fetch a red-line template by id."""
    for r in RED_LINES:
        if r['id'] == rl_id:
            return r
    return None


# ============================================================
# RED LINE EVALUATION
# ============================================================
def check_red_lines(articles, actor_results):
    """
    Evaluate all Taiwan red lines against scan data.
    Returns list of triggered red lines with 'status' = BREACHED or APPROACHING.
    """
    triggered = []

    def lvl(key):
        return actor_results.get(key, {}).get('level', 0)

    lai          = lvl('lai_presidential')
    roc_def      = lvl('roc_defense')
    us_part      = lvl('us_partnership')
    diplo        = lvl('diplomatic_posture')
    asymmetric   = lvl('asymmetric_resilience')
    pla_pressure = lvl('pla_pressure')
    beijing_coer = lvl('beijing_coercion')
    econ_pres    = lvl('economic_pressure')

    # ── US ABANDONMENT SIGNAL ───────────────────────────────
    abandonment_signal = _scan_actor_articles(
        actor_results,
        ['us_partnership'],
        ['us taiwan abandonment', 'ait personnel cut', 'ait closure',
         'taiwan defend itself alone', 'taiwan not our problem',
         'us walk back taiwan commitment', 'taiwan commitment reduced',
         'arms deal frozen taiwan', 'taiwan sale canceled'],
    )
    if abandonment_signal or us_part <= 1:
        triggered.append({
            **_rl('us_abandonment_signal'),
            'status':  'BREACHED' if abandonment_signal else 'APPROACHING',
            'trigger': f'US partnership L{us_part} -- '
                       f'{"abandonment language detected" if abandonment_signal else "partnership signal weak"}',
        })

    # ── ARMS DEAL CANCELLATION ──────────────────────────────
    arms_signal = _scan_actor_articles(
        actor_results,
        ['us_partnership', 'roc_defense'],
        ['taiwan arms deal canceled', 'taiwan arms sale halted', 'f-16 taiwan delayed cancel',
         'himars taiwan freeze', 'submarine deal taiwan canceled', 'taiwan munitions canceled',
         'arms backlog increase taiwan', 'arms delivery delayed taiwan'],
    )
    if arms_signal:
        triggered.append({
            **_rl('us_arms_deal_cancellation'),
            'status':  'BREACHED',
            'trigger': f'US partnership L{us_part} -- arms-deal cancellation language detected',
        })

    # ── PORCUPINE ABANDONED ─────────────────────────────────
    porcupine_signal = _scan_actor_articles(
        actor_results,
        ['roc_defense', 'asymmetric_resilience'],
        ['porcupine strategy abandoned', 'overall defense concept dropped', 'symmetric procurement taiwan',
         'abandon asymmetric doctrine', 'big ticket carrier taiwan', 'return to symmetric'],
    )
    if porcupine_signal or asymmetric <= 0:
        triggered.append({
            **_rl('porcupine_abandoned'),
            'status':  'BREACHED' if porcupine_signal else 'APPROACHING',
            'trigger': f'Asymmetric resilience L{asymmetric} -- '
                       f'{"doctrine-abandonment language detected" if porcupine_signal else "asymmetric signal weak"}',
        })

    # ── CONSCRIPTION CRISIS ─────────────────────────────────
    conscription_signal = _scan_actor_articles(
        actor_results,
        ['roc_defense', 'asymmetric_resilience', 'lai_presidential'],
        ['conscription crisis taiwan', 'reservist training failure', 'taiwan draft dodging',
         'conscription opposition mass', 'military service refuse taiwan',
         'reservist call up failure'],
    )
    if conscription_signal:
        triggered.append({
            **_rl('conscription_crisis'),
            'status':  'BREACHED',
            'trigger': f'ROC defense L{roc_def} -- conscription-crisis language detected',
        })

    # ── JAPAN FORMALIZED (GREEN LINE -- deterrence positive) ─
    japan_positive_signal = _scan_actor_articles(
        actor_results,
        ['diplomatic_posture', 'us_partnership'],
        ['japan taiwan defense treaty', 'sdf taiwan stationing', 'japan collective defense taiwan',
         'japan taiwan formal commitment', 'taiwan emergency formal japan'],
    )
    if japan_positive_signal:
        triggered.append({
            **_rl('japan_taiwan_formalized'),
            'status':  'BREACHED',  # in green-line context, "BREACHED" = event occurred
            'trigger': 'Japan formal Taiwan-defense commitment language detected -- deterrence-positive',
        })

    # ── AUKUS FRACTURE ──────────────────────────────────────
    aukus_fracture_signal = _scan_actor_articles(
        actor_results,
        ['us_partnership', 'diplomatic_posture'],
        ['aukus fracture taiwan', 'australia pull back taiwan', 'uk decouple pacific',
         'india distance taiwan', 'quad split taiwan', 'aukus disagreement taiwan'],
    )
    if aukus_fracture_signal:
        triggered.append({
            **_rl('aukus_fracture'),
            'status':  'BREACHED',
            'trigger': f'Diplomatic posture L{diplo} -- coalition-fracture language detected',
        })

    # ── DPP-KMT UNITY BREAKDOWN ─────────────────────────────
    unity_signal = _scan_actor_articles(
        actor_results,
        ['lai_presidential', 'roc_defense'],
        ['kmt defense opposition', 'dpp kmt rupture defense', 'opposition against conscription',
         'kmt oppose arms purchase', 'dpp kmt split defense', 'kmt pro beijing defense'],
    )
    if unity_signal:
        triggered.append({
            **_rl('dpp_kmt_unity_break'),
            'status':  'BREACHED',
            'trigger': f'Lai presidential L{lai} -- DPP-KMT defense rupture language detected',
        })

    # ── MASS EMIGRATION SIGNAL ──────────────────────────────
    emigration_signal = _scan_actor_articles(
        actor_results,
        ['lai_presidential', 'asymmetric_resilience'],
        ['taiwan passport applications surge', 'taiwan brain drain spike', 'semiconductor executive relocate',
         'tsmc family emigration', 'taiwan property sale overseas surge',
         'taiwan mass emigration'],
    )
    if emigration_signal:
        triggered.append({
            **_rl('mass_emigration_signal'),
            'status':  'BREACHED',
            'trigger': f'Asymmetric resilience L{asymmetric} -- mass emigration signal detected',
        })

    # ── PRC MOBILIZATION ORDERS ─────────────────────────────
    prc_mob_signal = _scan_actor_articles(
        actor_results,
        ['pla_pressure', 'beijing_coercion'],
        ['pla mobilization taiwan', 'amphibious assault taiwan', 'pla sealift accumulation',
         'rocket force alert', 'pla invasion preparations', 'pla staging taiwan imminent'],
    )
    if prc_mob_signal or pla_pressure >= 5:
        triggered.append({
            **_rl('prc_mobilization_orders'),
            'status':  'BREACHED' if (prc_mob_signal and pla_pressure >= 4) else 'APPROACHING',
            'trigger': f'PLA pressure L{pla_pressure} -- '
                       f'{"mobilization language detected" if prc_mob_signal else "approaching mobilization threshold"}',
        })

    # ── PRC KINETIC INCIDENT ────────────────────────────────
    kinetic_signal = _scan_actor_articles(
        actor_results,
        ['pla_pressure', 'beijing_coercion'],
        ['pla fire taiwan ship', 'pla strike taiwan', 'pla warship fire taiwan',
         'pla attack kinmen', 'pla attack matsu', 'pla fire on taiwan',
         'taiwan aircraft hit pla', 'pla kinetic incident taiwan'],
    )
    if kinetic_signal:
        triggered.append({
            **_rl('prc_kinetic_incident'),
            'status':  'BREACHED',
            'trigger': f'PLA pressure L{pla_pressure} -- kinetic-incident language detected',
        })

    return triggered


# ============================================================
# HISTORICAL ANALOG MATCHING
# ============================================================
def build_historical_matches(actor_results, vectors):
    """Match current Taiwan signal state to historical analogs."""
    matches = []

    deterrence_strength = vectors.get('deterrence_strength', 0)
    inbound_pressure    = vectors.get('inbound_pressure',    0)
    domestic_resolve    = vectors.get('domestic_resolve',    0)
    deterrence_gap      = vectors.get('deterrence_gap',      0)

    us_part    = actor_results.get('us_partnership', {}).get('level', 0)
    roc_def    = actor_results.get('roc_defense', {}).get('level', 0)
    asymmetric = actor_results.get('asymmetric_resilience', {}).get('level', 0)
    pla_press  = actor_results.get('pla_pressure', {}).get('level', 0)

    # 2022 Pelosi Response analog
    if pla_press >= 3 and us_part >= 3:
        matches.append({
            'label':      '2022 Post-Pelosi Crisis Management',
            'year':       2022,
            'similarity': 'Taiwan absorbed PLA coercion surge with coalition backstop. '
                          'Deterrence held -- framework of managed escalation worked.',
            'score':      80,
        })

    # 2024 Lai Inauguration / Joint Sword-A analog
    if pla_press >= 3 and roc_def >= 2:
        matches.append({
            'label':      '2024 Lai Inauguration + Joint Sword',
            'year':       2024,
            'similarity': 'Deterrence posture under post-inauguration PLA coercion. Coalition '
                          'statements + Taiwan MND restraint modeled current playbook.',
            'score':      75,
        })

    # 1995-96 Strait Crisis analog (from deterrence-success lens)
    if pla_press >= 4 and us_part >= 3:
        matches.append({
            'label':      '1995-96 Taiwan Strait Crisis (Deterrence Success)',
            'year':       1996,
            'similarity': 'US carrier deployment + Taiwan posture + democratic resolve combined to '
                          'defeat coercion cycle. Core deterrence doctrine reference.',
            'score':      70,
        })

    # Ukraine 2022 analog (resolve-under-invasion lesson)
    if pla_press >= 4 or deterrence_gap >= 3:
        matches.append({
            'label':      'Ukraine Resolve Under Invasion (Feb 2022+)',
            'year':       2022,
            'similarity': 'Instructive case for Taiwan resolve calibration: small-state defender '
                          'resisting large-power kinetic action. Mass mobilization + coalition '
                          'arms supply was decisive variable.',
            'score':      65,
        })

    # Hong Kong 2019-2020 analog (elite exit / brain drain)
    if domestic_resolve <= 1 or vectors.get('mass_emigration', 0) >= 2:
        matches.append({
            'label':      'Hong Kong Elite Exit (2019-2021)',
            'year':       2020,
            'similarity': 'Leading indicator of governance-collapse trajectory: elite professionals '
                          'and capital exited before sovereignty compromise. Negative-deterrence '
                          'analog for Taiwan.',
            'score':      55,
        })

    matches.sort(key=lambda m: -m.get('score', 0))
    return matches[:3]


# ============================================================
# SO WHAT FACTOR
# ============================================================
def build_so_what(scan_data, red_lines_triggered, historical_matches):
    """
    Generate Taiwan deterrence assessment.
    Five-level scenario ladder tuned for defensive/deterrence dynamics.
    """
    actors = scan_data.get('actors', {})

    def lvl(key):
        return actors.get(key, {}).get('level', 0)

    lai          = lvl('lai_presidential')
    roc_def      = lvl('roc_defense')
    us_part      = lvl('us_partnership')
    diplo        = lvl('diplomatic_posture')
    asymmetric   = lvl('asymmetric_resilience')
    pla_pressure = lvl('pla_pressure')
    beijing_coer = lvl('beijing_coercion')
    econ_pres    = lvl('economic_pressure')

    # Composite vectors
    deterrence_strength = max(us_part, roc_def, diplo)
    inbound_pressure    = max(pla_pressure, beijing_coer, econ_pres)
    domestic_resolve    = max(lai, asymmetric)
    # DETERRENCE GAP = inbound pressure - coalition response
    # Positive gap = deterrence weakening under rising pressure
    deterrence_gap      = max(0, inbound_pressure - deterrence_strength)

    breached_count    = sum(1 for r in red_lines_triggered if r.get('status') == 'BREACHED')
    approaching_count = sum(1 for r in red_lines_triggered if r.get('status') == 'APPROACHING')

    # ── Scenario label ──
    # Taiwan scenarios are defensive -- calibrated for deterrence failure not Taiwan aggression
    if breached_count >= 2 or pla_pressure >= 5:
        scenario       = 'CRITICAL -- Deterrence Failure or Active PRC Kinetic Threshold'
        scenario_color = '#dc2626'
        scenario_icon  = '🔴'
    elif breached_count >= 1 or deterrence_gap >= 3:
        scenario       = 'ELEVATED -- Red Line Breached or Deterrence Gap Widening'
        scenario_color = '#f97316'
        scenario_icon  = '🟠'
    elif inbound_pressure >= 3 or deterrence_gap >= 2:
        scenario       = 'WARNING -- Inbound Pressure Rising or Coalition Signal Weakening'
        scenario_color = '#f59e0b'
        scenario_icon  = '🟡'
    elif inbound_pressure >= 2 or deterrence_strength >= 3:
        scenario       = 'MONITORING -- Baseline Elevated, Deterrence Active'
        scenario_color = '#3b82f6'
        scenario_icon  = '🔵'
    else:
        scenario       = 'BASELINE -- Routine Rhetoric, Deterrence Holding'
        scenario_color = '#6b7280'
        scenario_icon  = '⚪'

    # ── Situation ──
    situation_parts = []

    if deterrence_strength >= 2:
        situation_parts.append(
            f'Deterrence vector at L{deterrence_strength}: '
            f'US partnership L{us_part}, ROC defense L{roc_def}, diplomatic L{diplo}. '
            f'{"Deterrence architecture at strong signaling level." if deterrence_strength >= 4 else "Baseline deterrence posture active."}'
        )

    if inbound_pressure >= 2:
        situation_parts.append(
            f'Inbound PRC pressure at L{inbound_pressure}: '
            f'PLA L{pla_pressure}, Beijing coercion L{beijing_coer}, economic L{econ_pres}. '
            f'{"Pressure at pre-kinetic threshold." if inbound_pressure >= 4 else "Coercion signaling active."}'
        )

    if deterrence_gap >= 2:
        situation_parts.append(
            f'⚠️ Deterrence gap at L{deterrence_gap}: inbound pressure exceeding coalition response. '
            f'{"This is the dangerous convergence -- Beijing reads gap as permission window." if deterrence_gap >= 3 else "Gap warrants coalition signaling reinforcement."}'
        )

    if domestic_resolve >= 2:
        situation_parts.append(
            f'Domestic resolve at L{domestic_resolve}: Lai leadership L{lai}, '
            f'asymmetric resilience L{asymmetric}. '
            f'{"Internal cohesion reinforcing deterrence." if domestic_resolve >= 3 else "Resolve at baseline."}'
        )

    # ── Indicators ──
    indicators = []
    for rl in red_lines_triggered:
        if rl.get('status') == 'BREACHED':
            icon = '🟢' if rl.get('color') == '#22c55e' else '🔴'  # green-line events get green
            indicators.append({'icon': icon, 'text': f"{'DETERRENCE-POSITIVE EVENT' if icon == '🟢' else 'RED LINE BREACHED'}: {rl.get('label', '')}"})
        elif rl.get('status') == 'APPROACHING':
            indicators.append({'icon': '🟠', 'text': f"Approaching: {rl.get('label', '')}"})

    for hm in (historical_matches or [])[:2]:
        indicators.append({
            'icon': '🕰️',
            'text': f"Historical analog: {hm.get('label', '')} ({hm.get('score', 0)}% pattern match)",
        })

    # ── Assessment ──
    if breached_count >= 2:
        assessment = (
            'Taiwan is in a multi-breach scenario. Deterrence architecture under stress from '
            'multiple directions simultaneously. Coalition coordination tempo becomes decisive. '
            'Cross-reference China tracker for mirrored coercion-convergence signals.'
        )
    elif pla_pressure >= 4 and deterrence_strength <= 2:
        assessment = (
            'PRC pressure rising with coalition response lagging -- classic deterrence-failure '
            'pattern. 1995-96 Strait Crisis was arrested by explicit US carrier deployment; '
            'equivalent high-visibility US/Japan signaling may be required now.'
        )
    elif deterrence_gap >= 3:
        assessment = (
            'Deterrence gap at L3+ -- inbound pressure meaningfully exceeding coalition response. '
            'This is the single most dangerous reading this tracker produces. Beijing '
            'systematically tests for gap-opening moments.'
        )
    elif breached_count >= 1 and any(rl.get('color') == '#22c55e' for rl in red_lines_triggered):
        assessment = (
            'Deterrence-positive event detected (coalition strengthening). Japan formal commitment '
            'or similar coalition consolidation would push Beijing calculus toward caution. '
            'Watch for retaliatory rhetoric spike in China tracker.'
        )
    elif breached_count >= 1:
        assessment = (
            'One red line breached. Single-vector deterrence degradation underway. Adjacent '
            'categories warrant elevated watch for cascade -- coalition + domestic + doctrine '
            'triad can mutually erode quickly.'
        )
    elif inbound_pressure >= 3 and deterrence_strength >= 3:
        assessment = (
            'Mutual escalation -- inbound pressure AND coalition response both rising. '
            'Healthy deterrence dynamic assuming Beijing reads signals accurately. Watch for '
            'misperception risk: strong deterrence unread can accidentally escalate.'
        )
    elif domestic_resolve <= 1 and inbound_pressure >= 2:
        assessment = (
            'Domestic resolve weakening while inbound pressure rises. Hong Kong 2019-2021 pattern '
            'warrants watch -- elite exit + asymmetric-doctrine drift + conscription fragility '
            'can precede governance-collapse by 12-24 months.'
        )
    elif deterrence_strength >= 3 and inbound_pressure <= 2:
        assessment = (
            'Deterrence strong, pressure low. Ideal posture. Routine monitoring of coalition '
            'cohesion + asymmetric doctrine implementation tempo.'
        )
    else:
        assessment = 'Taiwan below convergence threshold. Deterrence holding, routine monitoring.'

    # ── Watch list ──
    watch_list = []
    if pla_pressure >= 3:
        watch_list.append('Taiwan MND daily PLA air-sortie + median-line crossing counts')
    if pla_pressure >= 2:
        watch_list.append('China tracker -- cross-strait fingerprint for outbound coercion signals')
    if us_part >= 2 or us_part <= 1:
        watch_list.append('AIT director statements + Congressional Taiwan caucus activity')
    if deterrence_gap >= 2:
        watch_list.append('Coalition response tempo -- US/Japan/Australia joint statements')
    if roc_def >= 2:
        watch_list.append('Taiwan MND weapons delivery timelines + asymmetric procurement')
    if asymmetric <= 1:
        watch_list.append('Porcupine/overall defense concept implementation signals')
    if lai >= 2:
        watch_list.append('DPP-KMT legislative dynamics -- defense budget + conscription bills')
    if diplo >= 2:
        watch_list.append('Taiwan diplomatic passport holder statistics + allies count')
    if beijing_coer >= 2:
        watch_list.append('TAO press conference cadence (weekly Wednesday) -- tone and demands')

    if not watch_list:
        watch_list.append('Routine monitoring -- no elevated-attention signals')

    return {
        'scenario':         scenario,
        'scenario_color':   scenario_color,
        'scenario_icon':    scenario_icon,
        'situation':        ' '.join(situation_parts) if situation_parts else 'All vectors below monitoring threshold. Taiwan deterrence holding baseline.',
        'indicators':       indicators,
        'assessment':       assessment,
        'watch_list':       watch_list,
        # Vector readout
        'deterrence_strength': deterrence_strength,
        'inbound_pressure':    inbound_pressure,
        'domestic_resolve':    domestic_resolve,
        'deterrence_gap':      deterrence_gap,
        # Historical context
        'historical_matches':  historical_matches or [],
        'confidence_note':     'Analysis based on OSINT signal aggregation. Does not reflect classified '
                               'intelligence. Deterrence-gap framework is Asifah-specific methodology '
                               'and should not be cited as official assessment.',
    }


# ============================================================
# TOP-LEVEL INTERPRETER
# ============================================================
def interpret_signals(scan_data):
    """
    Given scan_data from rhetoric_tracker_taiwan, returns:
      {'red_lines': [...], 'so_what': {...}, 'historical_matches': [...]}
    """
    actor_results = scan_data.get('actors', {})
    articles      = scan_data.get('articles', [])

    red_lines_triggered = check_red_lines(articles, actor_results)

    def lvl(key):
        return actor_results.get(key, {}).get('level', 0)

    deterrence_strength = max(lvl('us_partnership'), lvl('roc_defense'), lvl('diplomatic_posture'))
    inbound_pressure    = max(lvl('pla_pressure'), lvl('beijing_coercion'), lvl('economic_pressure'))
    domestic_resolve    = max(lvl('lai_presidential'), lvl('asymmetric_resilience'))

    vectors = {
        'deterrence_strength': deterrence_strength,
        'inbound_pressure':    inbound_pressure,
        'domestic_resolve':    domestic_resolve,
        'deterrence_gap':      max(0, inbound_pressure - deterrence_strength),
        'mass_emigration':     scan_data.get('mass_emigration', 0),
    }
    historical_matches = build_historical_matches(actor_results, vectors)
    so_what = build_so_what(scan_data, red_lines_triggered, historical_matches)

    return {
        'red_lines':          red_lines_triggered,
        'so_what':            so_what,
        'historical_matches': historical_matches,
    }


# ============================================================
# v2.0+ — TOP SIGNALS (BLUF / GPI consumable)
# ============================================================
# Emits a pre-prioritized list of signal dicts that the Asia Regional BLUF
# (and ultimately the Global Pressure Index) consume directly.
#
# Taiwan-specific categories:
#   red_line_breached, theatre_high, deterrence_gap, coalition_strong,
#   domestic_resolve, mass_emigration, silence_anomaly

TAIWAN_FLAG = '\U0001f1f9\U0001f1fc'  # 🇹🇼

def build_top_signals(scan_data):
    """
    Build Taiwan's top_signals[] for BLUF/GPI consumption.
    Reads from scan_data (post-interpret_signals output).
    """
    signals = []

    actor_results = scan_data.get('actors', {}) or {}
    so_what       = scan_data.get('so_what', {}) or {}
    red_lines     = scan_data.get('red_lines', []) or []

    overall_level = scan_data.get('overall_level', 0) or 0
    overall_score = scan_data.get('theatre_score',
                    scan_data.get('overall_score', 0)) or 0

    # Vector readouts from so_what
    deterrence_strength = so_what.get('deterrence_strength', 0) or 0
    inbound_pressure    = so_what.get('inbound_pressure', 0) or 0
    domestic_resolve    = so_what.get('domestic_resolve', 0) or 0
    deterrence_gap      = so_what.get('deterrence_gap', 0) or 0

    # Actor-specific levels
    us_partnership   = actor_results.get('us_partnership',   {}).get('level', 0) or 0
    roc_defense      = actor_results.get('roc_defense',      {}).get('level', 0) or 0
    pla_pressure     = actor_results.get('pla_pressure',     {}).get('level', 0) or 0
    lai_presidential = actor_results.get('lai_presidential', {}).get('level', 0) or 0

    mass_emigration = scan_data.get('mass_emigration', 0) or 0

    # ============================================
    # 1. RED LINES BREACHED — BUT distinguish positive vs negative
    # ============================================
    for rl in red_lines:
        if not isinstance(rl, dict): continue
        status = rl.get('status', '')
        label  = rl.get('label', 'Red line')
        is_positive = (rl.get('color') == '#22c55e')
        if status == 'BREACHED':
            if is_positive:
                # Taiwan-specific: deterrence-positive red lines are GOOD news
                signals.append({
                    'priority':   9,
                    'category':   'green_line_active',
                    'theatre':    'taiwan',
                    'level':      overall_level,
                    'icon':       '🟢',
                    'color':      '#22c55e',
                    'short_text': f'{TAIWAN_FLAG} TAIWAN: Deterrence-positive — {label[:50]}',
                    'long_text':  f'TAIWAN deterrence-positive signal: {label} — coalition / domestic resolve breach in favorable direction.',
                })
            else:
                signals.append({
                    'priority':   12,
                    'category':   'red_line_breached',
                    'theatre':    'taiwan',
                    'level':      overall_level,
                    'icon':       rl.get('icon', '🚨'),
                    'color':      '#dc2626',
                    'short_text': f'{TAIWAN_FLAG} TAIWAN: BREACH — {label[:55]}',
                    'long_text':  f'TAIWAN red line breached at L{overall_level}: {label}.',
                })
        elif status == 'APPROACHING':
            signals.append({
                'priority':   8,
                'category':   'red_line_approaching',
                'theatre':    'taiwan',
                'level':      overall_level,
                'icon':       '🟠',
                'color':      '#f97316',
                'short_text': f'{TAIWAN_FLAG} TAIWAN: Approaching — {label[:50]}',
                'long_text':  f'TAIWAN approaching red line: {label}.',
            })

    # ============================================
    # 2. THEATRE-HIGH (overall L4+)
    # ============================================
    if overall_level >= 4:
        signals.append({
            'priority':   9 + overall_level,
            'category':   'theatre_high',
            'theatre':    'taiwan',
            'level':      overall_level,
            'icon':       '🔴',
            'color':      '#dc2626' if overall_level >= 5 else '#ef4444',
            'short_text': f'{TAIWAN_FLAG} TAIWAN L{overall_level} — Composite pressure',
            'long_text':  f'TAIWAN at L{overall_level} composite pressure (score {overall_score}/100). Multi-vector activity across PLA pressure, deterrence, and domestic signaling.',
        })

    # ============================================
    # 3. DETERRENCE GAP (Taiwan-specific KEY signal)
    # ============================================
    if deterrence_gap >= 3:
        signals.append({
            'priority':   11,
            'category':   'deterrence_gap',
            'theatre':    'taiwan',
            'level':      deterrence_gap,
            'icon':       '⚠️',
            'color':      '#dc2626',
            'short_text': f'{TAIWAN_FLAG} TAIWAN: Deterrence gap L{deterrence_gap}',
            'long_text':  f'TAIWAN deterrence gap L{deterrence_gap} — inbound pressure L{inbound_pressure} exceeds coalition response L{deterrence_strength}. Coercion-into-weakness pattern.',
        })
    elif deterrence_gap >= 2:
        signals.append({
            'priority':   7,
            'category':   'deterrence_gap',
            'theatre':    'taiwan',
            'level':      deterrence_gap,
            'icon':       '📉',
            'color':      '#f59e0b',
            'short_text': f'{TAIWAN_FLAG} TAIWAN: Deterrence gap L{deterrence_gap}',
            'long_text':  f'TAIWAN deterrence gap L{deterrence_gap} — inbound L{inbound_pressure} > coalition response L{deterrence_strength}. Reinforcement window open.',
        })

    # ============================================
    # 4. INBOUND PRESSURE HIGH (PLA pressure on Taiwan)
    # ============================================
    if inbound_pressure >= 4:
        signals.append({
            'priority':   9,
            'category':   'inbound_pressure_high',
            'theatre':    'taiwan',
            'level':      inbound_pressure,
            'icon':       '🎯',
            'color':      '#dc2626',
            'short_text': f'{TAIWAN_FLAG} TAIWAN: Inbound pressure L{inbound_pressure}',
            'long_text':  f'TAIWAN inbound pressure L{inbound_pressure} — PLA pressure level L{pla_pressure}; coercion tempo elevated.',
        })

    # ============================================
    # 5. COALITION STRENGTH (positive signal)
    # ============================================
    if us_partnership >= 3 and roc_defense >= 3 and deterrence_gap < 2:
        signals.append({
            'priority':   6,
            'category':   'coalition_strong',
            'theatre':    'taiwan',
            'level':      max(us_partnership, roc_defense),
            'icon':       '🤝',
            'color':      '#10b981',
            'short_text': f'{TAIWAN_FLAG} TAIWAN: Coalition strong (US L{us_partnership}, ROC L{roc_defense})',
            'long_text':  f'TAIWAN coalition posture strong — US partnership L{us_partnership}, ROC defense L{roc_defense}; deterrence coordinated.',
        })

    # ============================================
    # 6. DOMESTIC RESOLVE (Lai presidential + asymmetric)
    # ============================================
    if domestic_resolve >= 4:
        signals.append({
            'priority':   6,
            'category':   'domestic_resolve',
            'theatre':    'taiwan',
            'level':      domestic_resolve,
            'icon':       '🏛️',
            'color':      '#0ea5e9',
            'short_text': f'{TAIWAN_FLAG} TAIWAN: Domestic resolve L{domestic_resolve}',
            'long_text':  f'TAIWAN domestic resolve L{domestic_resolve} — Lai presidential signaling L{lai_presidential} aligned with asymmetric resilience posture.',
        })

    # ============================================
    # 7. MASS EMIGRATION SIGNAL (escape pattern)
    # ============================================
    if mass_emigration >= 3:
        signals.append({
            'priority':   8,
            'category':   'mass_emigration',
            'theatre':    'taiwan',
            'level':      mass_emigration,
            'icon':       '✈️',
            'color':      '#a855f7',
            'short_text': f'{TAIWAN_FLAG} TAIWAN: Mass emigration L{mass_emigration}',
            'long_text':  f'TAIWAN mass emigration signal L{mass_emigration} — flight pattern indicates domestic confidence erosion; forward indicator of coercion success.',
        })

    # Sort descending; BLUF will dedupe + globally rank
    signals.sort(key=lambda s: s['priority'], reverse=True)
    return signals
