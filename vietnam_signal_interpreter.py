# -*- coding: utf-8 -*-
"""
vietnam_signal_interpreter.py
Asifah Analytics -- Asia Backend Module
v1.0.0 -- June 2026

Signal interpretation engine for the Vietnam South China Sea Tracker.

Vietnam's analytical frame mirrors the Taiwan deterrence tracker, but the
central question is maritime-sovereignty rather than cross-strait invasion:

  1. What is China doing in the SCS against Vietnam right now?
     China Coast Guard (CCG) + maritime militia + survey-vessel incursions
     + Vanguard Bank standoffs + nine-dash-line enforcement. This is the
     INBOUND coercion vector -- read partly from the China fingerprint and
     partly from Vietnam's own SCS scan.

  2. Is Vietnam's response + coalition posture keeping pace?
     CPV/State sovereignty assertion + MOFA diplomacy/lawfare (UNCLOS, PCA)
     + Coast Guard / Navy maritime posture + US partnership + Indo-Pacific
     hedging (Philippines, Japan, India). The OUTBOUND response vector.

  3. Is there a COERCION-RESPONSE GAP?
     The Vietnam analog of Taiwan's deterrence gap: inbound Chinese SCS
     coercion minus Vietnam + coalition response. A widening gap is the
     single most important signal this tracker produces -- it is the window
     in which Beijing normalizes gray-zone control of contested features.

CROSS-COUNTRY / BUTTERFLY:
  - hormuz_vietnam_energy_dependency: Iran/Hormuz pressure x Vietnam's net
    energy-import exposure (read from the Iran fingerprint).
  - vietnam_indo_pacific_convergence: US + Japan/Philippines/India maritime
    alignment converts SCS pressure into broader deterrence signaling.
  - china_two_front_convergence: Beijing pressuring Taiwan AND Vietnam
    simultaneously (read from the Taiwan fingerprint) -- a regional
    multi-front coercion pattern no single tracker can see alone.

DISCIPLINE: convergence framing, NOT prediction. Every output reports which
signals are present, not whether kinetic action is imminent.

Author: RCGG / Asifah Analytics
"""

from datetime import datetime, timezone

VIETNAM_FLAG = '\U0001f1fb\U0001f1f3'  # flag emoji


# ============================================================
# RED LINE DEFINITIONS  (South China Sea frame)
# ============================================================
RED_LINES = [

    # -- Category A: Sovereignty Erosion (China establishes control) --
    {
        'id':       'china_feature_militarization_vanguard',
        'label':    'China Militarizes / Occupies Feature in Vietnam EEZ',
        'detail':   'China establishes a permanent presence, structure, or garrison on a feature '
                    'inside Vietnam\'s claimed EEZ (Vanguard Bank / Bai Tu Chinh, or a previously '
                    'unoccupied Spratly feature)',
        'severity': 3,
        'color':    '#dc2626',
        'icon':     '🏝️',
        'category': 'sovereignty_erosion',
        'source':   'A new permanent Chinese presence inside the Vietnamese EEZ would convert '
                    'gray-zone pressure into a fait accompli. 1995 Mischief Reef (vs. Philippines) '
                    'is the canonical precedent for this pattern.',
    },
    {
        'id':       'china_oil_gas_blockade',
        'label':    'China Blocks Vietnam Oil/Gas Operations in Its Own EEZ',
        'detail':   'CCG / maritime militia forces suspension of a Vietnamese hydrocarbon project '
                    '(Block 06-01, Nam Con Son basin, Ca Rong Do / Red Emperor) through standoff or '
                    'coercion of contractors (Rosneft, ExxonMobil-type withdrawal)',
        'severity': 3,
        'color':    '#dc2626',
        'icon':     '🛢️',
        'category': 'sovereignty_erosion',
        'source':   'Vietnam shelved Red Emperor (2018) and Ca Rong Do under Chinese pressure. '
                    'Each suspension cedes economic sovereignty in the EEZ without a shot fired.',
    },

    # -- Category B: Kinetic Threshold --
    {
        'id':       'ccg_ramming_casualty',
        'label':    'CCG / Militia Ramming With Casualties or Vessel Sinking',
        'detail':   'China Coast Guard or maritime militia rams, water-cannons, or sinks a '
                    'Vietnamese vessel resulting in casualties or loss of the vessel',
        'severity': 3,
        'color':    '#dc2626',
        'icon':     '🚨',
        'category': 'kinetic_threshold',
        'source':   'Crosses from gray-zone coercion to lethal incident. 1988 Johnson South Reef '
                    '(64 Vietnamese sailors killed) is the historical kinetic precedent.',
    },
    {
        'id':       'china_survey_rig_deployment',
        'label':    'China Deploys Survey Fleet / Oil Rig Into Vietnam EEZ',
        'detail':   'China moves a HYSY-981-class rig or a Haiyang Dizhi survey vessel with CCG '
                    'escort into Vietnam\'s EEZ (Vanguard Bank-type incursion)',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '⚓',
        'category': 'kinetic_threshold',
        'source':   'HD-981 (2014) and Haiyang Dizhi 8 (2019) are the defining Vietnam-China '
                    'standoff precedents. Rig/survey deployment is the recurring escalation trigger.',
    },

    # -- Category C: Coalition / Partnership --
    {
        'id':       'us_vietnam_strategic_upgrade',
        'label':    'US-Vietnam Security Upgrade (DETERRENCE-POSITIVE)',
        'detail':   'Major US-Vietnam defense step: carrier port call, coast-guard cutter transfer, '
                    'maritime-domain-awareness package, or upgrade of the Comprehensive Strategic '
                    'Partnership toward security cooperation',
        'severity': 1,
        'color':    '#22c55e',
        'icon':     '🤝',
        'category': 'coalition_cohesion',
        'source':   'GREEN-LINE event. Vietnam-US CSP (Sept 2023) and carrier visits (2018, 2020, '
                    '2025) raise the cost of Chinese coercion without a formal alliance.',
    },
    {
        'id':       'asean_coc_collapse',
        'label':    'ASEAN / Code of Conduct Collapse on SCS',
        'detail':   'ASEAN fails to issue an SCS statement, or the China-ASEAN Code of Conduct '
                    'negotiation visibly collapses or is captured on Beijing\'s terms',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '💔',
        'category': 'coalition_cohesion',
        'source':   '2012 Phnom Penh (no ASEAN communique for the first time) showed Beijing can '
                    'split ASEAN. A captured or dead COC leaves Vietnam exposed bilaterally.',
    },

    # -- Category D: Domestic / Hedging --
    {
        'id':       'vietnam_china_accommodation',
        'label':    'Vietnam Visibly Accommodates Beijing on SCS',
        'detail':   'Hanoi defers, suspends a protest, or tilts its "bamboo diplomacy" hedge toward '
                    'Beijing on a sovereignty question (party-to-party reassurance over EEZ defense)',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '🎋',
        'category': 'hedging_balance',
        'source':   'Vietnam hedges between deterrence and accommodation. A visible tilt to Beijing '
                    'signals Hanoi assesses the coercion-response gap as unwinnable -- a leading '
                    'indicator of conceded sovereignty.',
    },
    {
        'id':       'anti_china_unrest',
        'label':    'Mass Anti-China Unrest in Vietnam',
        'detail':   'Large-scale anti-China protests or riots in Vietnam tied to an SCS incident '
                    '(2014 HD-981 riot pattern: factories burned, evacuations)',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '🪧',
        'category': 'hedging_balance',
        'source':   '2014 HD-981 crisis triggered deadly anti-China riots. Domestic nationalism '
                    'constrains CPV room to maneuver and can force escalation against its hedge.',
    },

    # -- Category E: China Direct (inbound) --
    {
        'id':       'china_nine_dash_enforcement',
        'label':    'China Formalizes / Enforces Nine-Dash Line or SCS ADIZ',
        'detail':   'Beijing declares an SCS Air Defense Identification Zone, codifies the '
                    'nine/ten-dash line in enforceable law, or applies the CCG Law to detain '
                    'foreign vessels in contested waters',
        'severity': 3,
        'color':    '#dc2626',
        'icon':     '🚫',
        'category': 'china_direct',
        'source':   'The 2021 CCG Law authorizes force in "jurisdictional waters." A declared SCS '
                    'ADIZ or systematic detentions would be a structural escalation of enforcement.',
    },
    {
        'id':       'china_fishing_ban_enforcement',
        'label':    'China Enforces Unilateral SCS Fishing Ban With Seizures',
        'detail':   'Beijing enforces its annual unilateral summer fishing moratorium against '
                    'Vietnamese fishermen through seizures, detentions, or sinkings',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '🎣',
        'category': 'china_direct',
        'source':   'The annual fishing ban (May-Aug) over waters Vietnam claims is a recurring '
                    'enforcement flashpoint affecting tens of thousands of Vietnamese fishers.',
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
    Evaluate SCS red lines against the current scan. Returns a list of
    red-line dicts with a 'status' of BREACHED or APPROACHING.
    """
    triggered = []

    # keyword sets per red line id
    breach_keywords = {
        'china_feature_militarization_vanguard': [
            'china occupies', 'china militarizes', 'china garrison vanguard',
            'china structure vanguard', 'china builds vanguard', 'china seizes feature',
            'china permanent presence', 'china outpost vietnam eez',
        ],
        'china_oil_gas_blockade': [
            'vietnam suspends oil', 'vietnam halts gas', 'vietnam shelves block',
            'rosneft withdraws', 'exxon withdraws vietnam', 'red emperor suspended',
            'ca rong do', 'block 06-01 standoff', 'china blocks vietnam oil',
        ],
        'ccg_ramming_casualty': [
            'china rams vietnamese', 'vietnamese fishermen killed', 'vietnamese vessel sunk',
            'coast guard rams vietnam', 'vietnamese sailors killed', 'water cannon injures',
        ],
        'china_survey_rig_deployment': [
            'haiyang dizhi', 'hysy-981', 'hd-981', 'china oil rig vietnam',
            'survey vessel vanguard', 'china rig vietnam eez', 'china survey vietnam waters',
        ],
        'us_vietnam_strategic_upgrade': [
            'us carrier vietnam', 'carrier visits da nang', 'coast guard cutter vietnam',
            'us vietnam defense', 'comprehensive strategic partnership', 'us vietnam security',
            'maritime domain awareness vietnam',
        ],
        'asean_coc_collapse': [
            'asean no statement', 'asean split south china sea', 'code of conduct collapse',
            'coc negotiation fails', 'asean fails scs', 'no asean communique',
        ],
        'vietnam_china_accommodation': [
            'vietnam reassures china', 'vietnam defers china', 'vietnam suspends protest',
            'party to party china vietnam', 'vietnam tilts beijing',
        ],
        'anti_china_unrest': [
            'anti-china protest vietnam', 'anti china riot', 'vietnam factory burned',
            'vietnam anti-china demonstration', 'hanoi protest china',
        ],
        'china_nine_dash_enforcement': [
            'south china sea adiz', 'scs adiz', 'nine-dash line law', 'ten-dash line',
            'china coast guard law', 'ccg law detain', 'china detains vietnamese',
        ],
        'china_fishing_ban_enforcement': [
            'china fishing ban', 'fishing moratorium south china sea', 'china seizes fishing boat',
            'vietnamese fishermen detained', 'china sinks fishing boat',
        ],
    }

    # actor groups to scan for each red line
    rl_actor_scope = {
        'china_feature_militarization_vanguard': ['china_scs_pressure', 'maritime_posture'],
        'china_oil_gas_blockade':                ['china_scs_pressure', 'maritime_posture', 'economic_pressure'],
        'ccg_ramming_casualty':                  ['china_scs_pressure', 'maritime_posture'],
        'china_survey_rig_deployment':           ['china_scs_pressure', 'maritime_posture'],
        'us_vietnam_strategic_upgrade':          ['us_partnership'],
        'asean_coc_collapse':                    ['mofa_diplomacy', 'regional_partners'],
        'vietnam_china_accommodation':           ['cpv_state', 'mofa_diplomacy'],
        'anti_china_unrest':                     ['cpv_state', 'china_scs_pressure'],
        'china_nine_dash_enforcement':           ['china_scs_pressure', 'beijing_coercion'],
        'china_fishing_ban_enforcement':         ['china_scs_pressure', 'economic_pressure'],
    }

    for rl_id, kws in breach_keywords.items():
        template = _rl(rl_id)
        if not template:
            continue
        scope = rl_actor_scope.get(rl_id, list(actor_results.keys()))
        hit = _scan_actor_articles(actor_results, scope, kws)
        if hit:
            entry = dict(template)
            entry['status'] = 'BREACHED'
            triggered.append(entry)
            continue
        # APPROACHING: the relevant inbound/outbound actor is already elevated (L3+)
        # even if the specific breach keyword has not appeared yet
        elevated = any(
            actor_results.get(a, {}).get('level', 0) >= 3 for a in scope
        )
        if elevated and template['color'] != '#22c55e':
            entry = dict(template)
            entry['status'] = 'APPROACHING'
            triggered.append(entry)

    return triggered


# ============================================================
# HISTORICAL ANALOG MATCHING  (Vietnam-China SCS)
# ============================================================
def build_historical_matches(actor_results, vectors):
    """Match current Vietnam SCS signal state to historical analogs."""
    matches = []

    inbound_pressure   = vectors.get('inbound_pressure', 0)
    response_strength  = vectors.get('response_strength', 0)
    coercion_gap       = vectors.get('coercion_gap', 0)
    partner_strength   = vectors.get('partner_strength', 0)

    china_scs = actor_results.get('china_scs_pressure', {}).get('level', 0)
    maritime  = actor_results.get('maritime_posture', {}).get('level', 0)
    us_part   = actor_results.get('us_partnership', {}).get('level', 0)

    # 2014 HD-981 oil rig crisis -- the canonical Vietnam-China SCS standoff
    if china_scs >= 3:
        matches.append({
            'label':      '2014 HD-981 Oil Rig Crisis',
            'year':       2014,
            'similarity': 'China parked a deep-water rig inside Vietnam\'s EEZ for ~10 weeks; '
                          'CCG/militia ramming standoff + deadly anti-China riots ashore. The '
                          'reference case for rig-deployment coercion and domestic-nationalism blowback.',
            'score':      82,
        })

    # 2019 Vanguard Bank standoff (Haiyang Dizhi 8)
    if china_scs >= 3 and maritime >= 2:
        matches.append({
            'label':      '2019 Vanguard Bank Standoff (Haiyang Dizhi 8)',
            'year':       2019,
            'similarity': 'Months-long survey-vessel + CCG incursion into Block 06-01 waters; '
                          'Vietnam Coast Guard shadowed but could not expel. Gray-zone '
                          'normalization of pressure on Vietnamese hydrocarbon operations.',
            'score':      78,
        })

    # 1988 Johnson South Reef (the kinetic precedent)
    if china_scs >= 4 or coercion_gap >= 3:
        matches.append({
            'label':      '1988 Johnson South Reef Skirmish',
            'year':       1988,
            'similarity': 'China seized Spratly features and killed 64 Vietnamese sailors -- the '
                          'lethal-threshold precedent. Instructive for how fast gray-zone pressure '
                          'can cross into kinetic exchange over a single feature.',
            'score':      70,
        })

    # 2016 PCA ruling (lawfare analog)
    if actor_results.get('mofa_diplomacy', {}).get('level', 0) >= 3:
        matches.append({
            'label':      '2016 PCA South China Sea Ruling',
            'year':       2016,
            'similarity': 'The tribunal rejected the nine-dash line; China refused to comply. '
                          'The lawfare ceiling -- legal victory without enforcement -- frames '
                          'Vietnam\'s UNCLOS/note-verbale diplomatic track.',
            'score':      62,
        })

    # 2012 Scarborough Shoal (cautionary: how a claimant loses a feature)
    if coercion_gap >= 2 and partner_strength <= 2:
        matches.append({
            'label':      '2012 Scarborough Shoal (Philippines lost control)',
            'year':       2012,
            'similarity': 'A standoff Manila "won" diplomatically but lost on the water -- China '
                          'retained control after a brokered mutual withdrawal. The cautionary '
                          'analog for a coercion-response gap with weak coalition backing.',
            'score':      58,
        })

    matches.sort(key=lambda m: -m.get('score', 0))
    return matches[:3]


# ============================================================
# SO WHAT FACTOR  (coercion-response gap frame)
# ============================================================
def build_so_what(scan_data, red_lines_triggered, historical_matches):
    """
    Generate Vietnam SCS assessment.
    Five-level scenario ladder tuned for maritime-sovereignty coercion dynamics.
    """
    actors = scan_data.get('actors', {})

    def lvl(key):
        return actors.get(key, {}).get('level', 0)

    cpv          = lvl('cpv_state')
    mofa         = lvl('mofa_diplomacy')
    maritime     = lvl('maritime_posture')
    us_part      = lvl('us_partnership')
    regional     = lvl('regional_partners')
    china_scs    = lvl('china_scs_pressure')
    beijing_coer = lvl('beijing_coercion')
    econ_pres    = lvl('economic_pressure')

    # Composite vectors
    # Vietnam's response = its own maritime/sovereignty posture, coalition is separate
    sovereignty_response = max(maritime, mofa, cpv)
    partner_strength     = max(us_part, regional)
    response_strength    = max(sovereignty_response, partner_strength)
    inbound_pressure     = max(china_scs, beijing_coer, econ_pres)
    # COERCION-RESPONSE GAP = inbound Chinese SCS pressure - Vietnam+coalition response
    coercion_gap         = max(0, inbound_pressure - response_strength)

    breached_count    = sum(1 for r in red_lines_triggered if r.get('status') == 'BREACHED')
    approaching_count = sum(1 for r in red_lines_triggered if r.get('status') == 'APPROACHING')
    # Separate deterrence-POSITIVE (green-line) breaches from negative ones, so a
    # favorable coalition event does not inflate the scenario into the alarm bands.
    negative_breached = sum(1 for r in red_lines_triggered
                            if r.get('status') == 'BREACHED' and r.get('color') != '#22c55e')
    positive_breached = breached_count - negative_breached

    # -- Scenario label --
    if negative_breached >= 2 or china_scs >= 5:
        scenario       = 'CRITICAL -- Multi-Vector SCS Pressure or Kinetic Threshold'
        scenario_color = '#dc2626'
        scenario_icon  = '🔴'
    elif negative_breached >= 1 or coercion_gap >= 3:
        scenario       = 'ELEVATED -- Red Line Breached or Coercion Gap Widening'
        scenario_color = '#f97316'
        scenario_icon  = '🟠'
    elif inbound_pressure >= 3 or coercion_gap >= 2:
        scenario       = 'WARNING -- SCS Coercion Rising or Response Lagging'
        scenario_color = '#f59e0b'
        scenario_icon  = '🟡'
    elif inbound_pressure >= 2 or response_strength >= 3 or positive_breached >= 1:
        scenario       = 'MONITORING -- Baseline Elevated, Posture Active'
        scenario_color = '#3b82f6'
        scenario_icon  = '🔵'
    else:
        scenario       = 'BASELINE -- Routine SCS Activity'
        scenario_color = '#6b7280'
        scenario_icon  = '⚪'

    # -- Situation --
    situation_parts = []
    if inbound_pressure >= 2:
        situation_parts.append(
            f'Inbound China SCS pressure at L{inbound_pressure}: '
            f'CCG/militia L{china_scs}, Beijing coercion L{beijing_coer}, economic L{econ_pres}. '
            f'{"Pressure at pre-kinetic gray-zone threshold." if inbound_pressure >= 4 else "Coercion signaling active."}'
        )
    if sovereignty_response >= 2:
        situation_parts.append(
            f'Vietnam response at L{sovereignty_response}: '
            f'maritime posture L{maritime}, MOFA/lawfare L{mofa}, CPV/State L{cpv}. '
            f'{"Assertive sovereignty posture." if sovereignty_response >= 4 else "Baseline sovereignty posture active."}'
        )
    if partner_strength >= 2:
        situation_parts.append(
            f'Coalition/hedge at L{partner_strength}: US partnership L{us_part}, '
            f'Indo-Pacific partners L{regional}. '
            f'{"Visible coalition backstop." if partner_strength >= 3 else "Hedge active at baseline."}'
        )
    if coercion_gap >= 2:
        situation_parts.append(
            f'⚠️ Coercion-response gap at L{coercion_gap}: Chinese SCS pressure exceeding '
            f'Vietnam + coalition response. '
            f'{"This is the dangerous window -- Beijing normalizes gray-zone control when the gap opens." if coercion_gap >= 3 else "Gap warrants response + coalition reinforcement."}'
        )

    # -- Indicators --
    indicators = []
    for rl in red_lines_triggered:
        if rl.get('status') == 'BREACHED':
            icon = '🟢' if rl.get('color') == '#22c55e' else '🔴'
            indicators.append({'icon': icon, 'text': f"{'DETERRENCE-POSITIVE EVENT' if icon == '🟢' else 'RED LINE BREACHED'}: {rl.get('label', '')}"})
        elif rl.get('status') == 'APPROACHING':
            indicators.append({'icon': '🟠', 'text': f"Approaching: {rl.get('label', '')}"})
    for hm in (historical_matches or [])[:2]:
        indicators.append({
            'icon': '🕰️',
            'text': f"Historical analog: {hm.get('label', '')} ({hm.get('score', 0)}% pattern match)",
        })

    # -- Assessment --
    if negative_breached >= 2:
        assessment = (
            'Vietnam is in a multi-breach SCS scenario -- pressure from several directions at once. '
            'Coalition coordination tempo and CPV willingness to absorb domestic nationalism become '
            'decisive. Cross-reference the China and Taiwan trackers for a multi-front coercion pattern.'
        )
    elif china_scs >= 4 and response_strength <= 2:
        assessment = (
            'Chinese SCS pressure rising with Vietnamese + coalition response lagging -- the '
            'classic gray-zone normalization pattern. 2019 Vanguard Bank showed Vietnam can shadow '
            'but not expel; sustained high-visibility coalition presence is what changes the cost calculus.'
        )
    elif coercion_gap >= 3:
        assessment = (
            'Coercion-response gap at L3+ -- Chinese SCS pressure meaningfully exceeding Vietnam + '
            'coalition response. This is the single most dangerous reading this tracker produces; '
            'Beijing systematically tests for gap-opening moments to normalize control of contested features.'
        )
    elif breached_count >= 1 and any(rl.get('color') == '#22c55e' for rl in red_lines_triggered):
        assessment = (
            'Deterrence-positive event detected (US-Vietnam security deepening). Coalition '
            'consolidation raises the cost of Chinese coercion. Watch for a Beijing rhetoric spike '
            'in the China tracker framed as opposition to "external interference."'
        )
    elif breached_count >= 1:
        assessment = (
            'One SCS red line breached. Single-vector escalation underway. Adjacent categories '
            '(oil/gas operations, fishing enforcement, feature presence) warrant elevated watch '
            'for cascade -- gray-zone pressure compounds quickly across the EEZ.'
        )
    elif inbound_pressure >= 3 and response_strength >= 3:
        assessment = (
            'Mutual escalation -- Chinese pressure AND Vietnamese/coalition response both rising. '
            'A functioning deterrence dynamic if Beijing reads the signals; watch for misperception '
            'risk and for Hanoi\'s hedge tilting under domestic-nationalist pressure.'
        )
    elif response_strength >= 3 and inbound_pressure <= 2:
        assessment = (
            'Response posture strong, pressure low. Favorable posture. Routine monitoring of CCG '
            'patrol cadence near Vanguard Bank and the Spratlys, and of coalition tempo.'
        )
    else:
        assessment = 'Vietnam below convergence threshold. SCS posture holding, routine monitoring.'

    # -- Watch list --
    watch_list = []
    if china_scs >= 3:
        watch_list.append('CCG / maritime-militia cadence near Vanguard Bank + Spratly features (CSIS AMTI imagery)')
    if china_scs >= 2:
        watch_list.append('China tracker -- cross-strait/SCS fingerprint for outbound coercion signals')
    if maritime >= 2:
        watch_list.append('Vietnam Coast Guard / fisheries-surveillance deployment + survey-escort activity')
    if coercion_gap >= 2:
        watch_list.append('Coalition response tempo -- US/Japan/Philippines/India joint statements + port calls')
    if mofa >= 2:
        watch_list.append('Vietnam MOFA note-verbale cadence at the UN + UNCLOS/PCA invocations')
    if econ_pres >= 2:
        watch_list.append('China-Vietnam trade/rare-earth/tourism leverage + border-crossing friction')
    if cpv >= 2:
        watch_list.append('CPV Politburo SCS language + To Lam balancing signals (Beijing vs. Washington)')
    if regional >= 2:
        watch_list.append('Vietnam-Philippines coast-guard MOU + Vietnam-Japan/India maritime cooperation')

    if not watch_list:
        watch_list.append('Routine monitoring -- no elevated-attention signals')

    return {
        'scenario':         scenario,
        'scenario_color':   scenario_color,
        'scenario_icon':    scenario_icon,
        'situation':        ' '.join(situation_parts) if situation_parts else 'All vectors below monitoring threshold. Vietnam SCS posture holding baseline.',
        'indicators':       indicators,
        'assessment':       assessment,
        'watch_list':       watch_list,
        # Vector readout (mirrors Taiwan naming where shared, plus Vietnam-specific)
        'response_strength':  response_strength,
        'sovereignty_response': sovereignty_response,
        'partner_strength':   partner_strength,
        'inbound_pressure':   inbound_pressure,
        'coercion_gap':       coercion_gap,
        'historical_matches': historical_matches or [],
        'confidence_note':    'Analysis based on OSINT signal aggregation. Does not reflect classified '
                              'intelligence. The coercion-response gap is Asifah-specific methodology. '
                              'This is a CONVERGENCE indicator, NOT a probability of action.',
    }


# ============================================================
# COMMODITY + CROSS-COUNTRY CONVERGENCE INJECTION
# ============================================================
def build_commodity_convergence_signals(scan_data):
    """
    Inject convergence signals into Vietnam's top_signals. Reads cross-theater
    amplifiers from scan_data and emits signals when structural exposures
    intersect with active geopolitical pressure from other theaters.

    Vietnam convergences:
      1. hormuz_vietnam_energy_dependency   (Iran/Hormuz x Vietnam energy import)
      2. vietnam_indo_pacific_convergence   (US + Japan/Philippines/India alignment)
      3. china_two_front_convergence        (Beijing pressuring Taiwan AND Vietnam)
    """
    signals = []

    amps = scan_data.get('crosstheater_amplifiers', {}) or {}
    iran_hormuz_active = amps.get('iran_hormuz_pressure', False)
    iran_score         = amps.get('iran_theatre_score', 0) or 0
    iran_irgc          = amps.get('iran_irgc_level', 0) or 0
    partner_outbound   = amps.get('partner_outbound_max', 0) or 0
    indo_pac_active    = amps.get('indo_pacific_active', False)
    taiwan_inbound     = amps.get('taiwan_inbound_max', 0) or 0
    china_scs_level    = amps.get('china_scs_level', 0) or 0

    # -- 1. HORMUZ-VIETNAM ENERGY CONVERGENCE --
    # Vietnam is a net energy importer with refining reliance (Dung Quat, Nghi Son).
    # Hormuz/oil shocks raise input costs for an export-driven economy and add
    # friction to SCS oil/gas operations.
    if iran_hormuz_active:
        signals.append({
            'priority':   13,
            'category':   'hormuz_vietnam_energy_dependency',
            'theatre':    'vietnam',
            'level':      max(3, min(5, int(iran_score / 20))),
            'icon':       '🛢️',
            'color':      '#f59e0b',
            'short_text': f'{VIETNAM_FLAG} VIETNAM: Energy/oil convergence -- Hormuz x import reliance',
            'long_text':  (
                f'VIETNAM energy convergence -- Iran/Hormuz posture (score {iran_score}, '
                f'IRGC L{iran_irgc}) compounds Vietnam\'s net crude-import and refining reliance '
                f'(Dung Quat, Nghi Son). Crude and shipping shocks raise input costs for an '
                f'export-driven economy and add friction to South China Sea oil and gas operations. '
                f'Watch PetroVietnam output, refinery runs, fuel-import invoicing, and Vanguard '
                f'Bank survey activity.'
            ),
            'hormuz_vietnam_energy_dependency_active': True,
            'convergence_states': {
                'hormuz_vietnam_energy_dependency': {
                    'active':      True,
                    'iran_score':  iran_score,
                    'iran_irgc':   iran_irgc,
                    'alert_level': 'elevated' if iran_score < 70 else ('high' if iran_score < 85 else 'surge'),
                },
            },
        })

    # -- 2. INDO-PACIFIC PARTNERSHIP CONVERGENCE --
    # US + Japan/Philippines/India deepening maritime-security ties with Vietnam
    # converts SCS pressure into broader Indo-Pacific deterrence signaling.
    if indo_pac_active and partner_outbound >= 3:
        signals.append({
            'priority':   14,
            'category':   'vietnam_indo_pacific_convergence',
            'theatre':    'vietnam',
            'level':      max(3, partner_outbound),
            'icon':       '🤝',
            'color':      '#0ea5e9',
            'short_text': f'{VIETNAM_FLAG} VIETNAM: Indo-Pacific partnership convergence -- US + partners',
            'long_text':  (
                f'VIETNAM Indo-Pacific convergence -- US and partners (Japan, Philippines, India) '
                f'deepening maritime-security ties with Vietnam (partner outbound L{partner_outbound}). '
                f'Converts South China Sea pressure into broader Indo-Pacific deterrence signaling '
                f'without a formal alliance, consistent with Vietnam\'s "bamboo diplomacy." Watch '
                f'coast-guard cooperation, port calls, Comprehensive Strategic Partnership upgrades, '
                f'and MFA statements on "external interference."'
            ),
            'vietnam_indo_pacific_convergence_active': True,
            'convergence_states': {
                'vietnam_indo_pacific_convergence': {
                    'active':              True,
                    'partner_outbound_max': partner_outbound,
                    'alert_level':         'high' if partner_outbound >= 4 else 'elevated',
                },
            },
        })

    # -- 3. CHINA TWO-FRONT CONVERGENCE (cross-country pattern) --
    # If Beijing is pressuring Taiwan AND Vietnam simultaneously, that is a
    # regional multi-front coercion pattern no single tracker sees alone.
    if taiwan_inbound >= 3 and china_scs_level >= 3:
        combined = max(taiwan_inbound, china_scs_level)
        signals.append({
            'priority':   15,
            'category':   'china_two_front_convergence',
            'theatre':    'vietnam',
            'level':      combined,
            'icon':       '🧭',
            'color':      '#dc2626',
            'short_text': f'{VIETNAM_FLAG} VIETNAM: China two-front pressure -- Taiwan + SCS active',
            'long_text':  (
                f'CHINA two-front convergence -- Beijing pressure is elevated on BOTH the Taiwan '
                f'theatre (inbound L{taiwan_inbound}) and the South China Sea against Vietnam '
                f'(CCG/militia L{china_scs_level}) simultaneously. A multi-front coercion pattern '
                f'stretches regional coalition attention and complicates any single claimant\'s '
                f'response. Convergence indicator only -- it reports correlated pressure, not '
                f'coordinated intent. Watch whether PLA Eastern-Theatre tempo and SCS CCG cadence '
                f'rise and fall together.'
            ),
            'china_two_front_convergence_active': True,
            'convergence_states': {
                'china_two_front_convergence': {
                    'active':         True,
                    'taiwan_inbound': taiwan_inbound,
                    'china_scs_level': china_scs_level,
                    'alert_level':    'high' if combined >= 4 else 'elevated',
                },
            },
        })

    return signals


# ============================================================
# TOP SIGNALS
# ============================================================
def build_top_signals(scan_data):
    """
    Build Vietnam's top_signals[] for the stability-page rhetoric card,
    Asia Regional BLUF, and GPI consumption. Reads from scan_data (the
    full result dict assembled by rhetoric_tracker_vietnam).
    """
    signals = []

    actor_results = scan_data.get('actors', {}) or {}
    so_what       = scan_data.get('so_what', {}) or {}
    red_lines     = scan_data.get('red_lines', []) or []

    overall_level = scan_data.get('overall_level', 0) or 0
    overall_score = scan_data.get('theatre_score',
                    scan_data.get('outbound_score', 0)) or 0

    response_strength = so_what.get('response_strength', 0) or 0
    inbound_pressure  = so_what.get('inbound_pressure', 0) or 0
    partner_strength  = so_what.get('partner_strength', 0) or 0
    coercion_gap      = so_what.get('coercion_gap', 0) or 0

    china_scs    = actor_results.get('china_scs_pressure', {}).get('level', 0) or 0
    maritime     = actor_results.get('maritime_posture', {}).get('level', 0) or 0
    us_part      = actor_results.get('us_partnership', {}).get('level', 0) or 0
    cpv          = actor_results.get('cpv_state', {}).get('level', 0) or 0

    # 1. RED LINES (positive vs negative)
    for rl in red_lines:
        if not isinstance(rl, dict):
            continue
        status = rl.get('status', '')
        label  = rl.get('label', 'Red line')
        is_positive = (rl.get('color') == '#22c55e')
        if status == 'BREACHED':
            if is_positive:
                signals.append({
                    'priority':   9,
                    'category':   'green_line_active',
                    'theatre':    'vietnam',
                    'level':      overall_level,
                    'icon':       '🟢',
                    'color':      '#22c55e',
                    'short_text': f'{VIETNAM_FLAG} VIETNAM: Coalition-positive -- {label[:48]}',
                    'long_text':  f'VIETNAM deterrence-positive signal: {label} -- coalition/partnership breach in a favorable direction.',
                })
            else:
                signals.append({
                    'priority':   12,
                    'category':   'red_line_breached',
                    'theatre':    'vietnam',
                    'level':      overall_level,
                    'icon':       rl.get('icon', '🚨'),
                    'color':      '#dc2626',
                    'short_text': f'{VIETNAM_FLAG} VIETNAM: BREACH -- {label[:54]}',
                    'long_text':  f'VIETNAM red line breached at L{overall_level}: {label}.',
                })
        elif status == 'APPROACHING':
            signals.append({
                'priority':   8,
                'category':   'red_line_approaching',
                'theatre':    'vietnam',
                'level':      overall_level,
                'icon':       '🟠',
                'color':      '#f97316',
                'short_text': f'{VIETNAM_FLAG} VIETNAM: Approaching -- {label[:48]}',
                'long_text':  f'VIETNAM approaching red line: {label}.',
            })

    # 2. THEATRE-HIGH (overall L4+)
    if overall_level >= 4:
        signals.append({
            'priority':   9 + overall_level,
            'category':   'theatre_high',
            'theatre':    'vietnam',
            'level':      overall_level,
            'icon':       '🔴',
            'color':      '#dc2626' if overall_level >= 5 else '#ef4444',
            'short_text': f'{VIETNAM_FLAG} VIETNAM L{overall_level} -- Composite SCS pressure',
            'long_text':  f'VIETNAM at L{overall_level} composite pressure (score {overall_score}/100). Multi-vector activity across CCG/militia pressure, sovereignty posture, and coalition signaling.',
        })

    # 3. COERCION-RESPONSE GAP (Vietnam-specific KEY signal)
    if coercion_gap >= 3:
        signals.append({
            'priority':   11,
            'category':   'coercion_gap',
            'theatre':    'vietnam',
            'level':      coercion_gap,
            'icon':       '⚠️',
            'color':      '#dc2626',
            'short_text': f'{VIETNAM_FLAG} VIETNAM: Coercion-response gap L{coercion_gap}',
            'long_text':  f'VIETNAM coercion-response gap L{coercion_gap} -- inbound China SCS pressure L{inbound_pressure} exceeds Vietnam+coalition response L{response_strength}. Gray-zone normalization window.',
        })
    elif coercion_gap >= 2:
        signals.append({
            'priority':   7,
            'category':   'coercion_gap',
            'theatre':    'vietnam',
            'level':      coercion_gap,
            'icon':       '📉',
            'color':      '#f59e0b',
            'short_text': f'{VIETNAM_FLAG} VIETNAM: Coercion-response gap L{coercion_gap}',
            'long_text':  f'VIETNAM coercion-response gap L{coercion_gap} -- inbound L{inbound_pressure} > response L{response_strength}. Reinforcement window open.',
        })

    # 4. INBOUND SCS PRESSURE HIGH
    if inbound_pressure >= 4:
        signals.append({
            'priority':   9,
            'category':   'inbound_pressure_high',
            'theatre':    'vietnam',
            'level':      inbound_pressure,
            'icon':       '🎯',
            'color':      '#dc2626',
            'short_text': f'{VIETNAM_FLAG} VIETNAM: China SCS pressure L{inbound_pressure}',
            'long_text':  f'VIETNAM inbound pressure L{inbound_pressure} -- China Coast Guard / maritime-militia level L{china_scs}; gray-zone coercion tempo elevated.',
        })

    # 5. COALITION / PARTNERSHIP STRENGTH (positive)
    if us_part >= 3 and maritime >= 3 and coercion_gap < 2:
        signals.append({
            'priority':   6,
            'category':   'partnership_strong',
            'theatre':    'vietnam',
            'level':      max(us_part, maritime),
            'icon':       '🤝',
            'color':      '#10b981',
            'short_text': f'{VIETNAM_FLAG} VIETNAM: Posture strong (US L{us_part}, maritime L{maritime})',
            'long_text':  f'VIETNAM posture strong -- US partnership L{us_part}, maritime/sovereignty L{maritime}; response coordinated against SCS pressure.',
        })

    # 6. SOVEREIGNTY RESOLVE (CPV/State + maritime)
    sovereignty_resolve = max(cpv, maritime)
    if sovereignty_resolve >= 4:
        signals.append({
            'priority':   6,
            'category':   'sovereignty_resolve',
            'theatre':    'vietnam',
            'level':      sovereignty_resolve,
            'icon':       '🏛️',
            'color':      '#0ea5e9',
            'short_text': f'{VIETNAM_FLAG} VIETNAM: Sovereignty resolve L{sovereignty_resolve}',
            'long_text':  f'VIETNAM sovereignty resolve L{sovereignty_resolve} -- CPV/State signaling L{cpv} aligned with maritime-posture assertion L{maritime}.',
        })

    # CONVERGENCES (cross-regional + cross-country)
    try:
        convergence_signals = build_commodity_convergence_signals(scan_data)
        if convergence_signals:
            signals.extend(convergence_signals)
            print(f"[Vietnam Interpreter] Convergence: {len(convergence_signals)} signal(s) emitted")
    except Exception as e:
        print(f"[Vietnam Interpreter] Convergence error: {e}")

    signals.sort(key=lambda s: s['priority'], reverse=True)
    return signals


# ============================================================
# BLUF + WATCH INDICATORS  (Gold Standard card native fields)
# ============================================================
def build_bluf(scan_data):
    """
    One-to-two sentence bottom-line-up-front for the stability-page rhetoric
    card. Synthesized from so_what + the highest-priority top signal.
    Convergence framing -- describes what is present, not what will happen.
    """
    so_what   = scan_data.get('so_what', {}) or {}
    signals   = scan_data.get('top_signals', []) or []
    inbound   = so_what.get('inbound_pressure', 0) or 0
    response  = so_what.get('response_strength', 0) or 0
    gap       = so_what.get('coercion_gap', 0) or 0
    overall   = scan_data.get('overall_level', 0) or 0

    # Lead clause: China SCS pressure vs Vietnam response
    if inbound >= 4:
        lead = 'China SCS coercion is elevated (CCG / maritime-militia pressure)'
    elif inbound >= 2:
        lead = 'China SCS coercion is active but below the gray-zone threshold'
    else:
        lead = 'China SCS activity is at baseline'

    if response >= 4:
        resp = 'Vietnam + coalition response is firm'
    elif response >= 2:
        resp = 'Vietnam + coalition response is engaged'
    else:
        resp = 'Vietnam + coalition response is muted'

    gap_clause = ''
    if gap >= 3:
        gap_clause = f' A coercion-response gap (L{gap}) is open -- the window in which Beijing normalizes gray-zone control.'
    elif gap >= 2:
        gap_clause = f' A coercion-response gap (L{gap}) is emerging.'

    # If a convergence signal is the headline, surface it
    conv = next((s for s in signals if s.get('category', '').endswith('_convergence')
                 or s.get('category') == 'china_two_front_convergence'), None)
    conv_clause = ''
    if conv and conv.get('category') == 'china_two_front_convergence':
        conv_clause = ' Beijing is pressuring Taiwan and the SCS simultaneously (two-front pattern).'

    if overall == 0 and inbound == 0:
        return 'No significant South China Sea signals; Vietnam posture at baseline.'

    return f'{lead}; {resp}.{gap_clause}{conv_clause}'


def build_watch_indicators(scan_data):
    """
    One-line WATCH string for the Gold Standard card. Prefers the top
    so_what watch_list item; falls back to a band-appropriate template.
    """
    so_what = scan_data.get('so_what', {}) or {}
    watch_list = so_what.get('watch_list', []) or []
    # Drop the generic "routine monitoring" filler if real items exist
    real = [w for w in watch_list if 'Routine monitoring' not in w]
    if real:
        # Lead with the SCS imagery / cadence indicator when present
        lead = real[0]
        if len(real) >= 2:
            return f'SCS posture watch -- {lead}; and {real[1]}.'
        return f'SCS posture watch -- {lead}.'

    inbound = so_what.get('inbound_pressure', 0) or 0
    band_templates = {
        0: 'Baseline -- watch CCG patrol cadence near Vanguard Bank and the Spratlys, and the first shift from routine to survey-escort activity.',
        1: 'Low-level -- watch for rising CCG/militia presence and any MOFA note-verbale activity.',
        2: 'Elevated -- watch for survey-vessel incursions, fishing-ban enforcement, and coalition response tempo.',
        3: 'Confrontation -- watch for oil/gas-operation standoffs, rig/survey deployment, and ASEAN/coalition signaling.',
        4: 'High -- watch for ramming incidents, feature-presence changes, and US/Japan/Philippines port-call cadence.',
        5: 'Active -- watch for kinetic exchange, casualty reports, and any abrupt CPV messaging shift.',
    }
    return band_templates.get(min(5, inbound), band_templates[0])


# ============================================================
# CONVENIENCE: full interpret pass (optional)
# ============================================================
def interpret_signals(scan_data):
    """Convenience wrapper returning the full interpreted bundle."""
    actor_results = scan_data.get('actors', {}) or {}
    articles      = scan_data.get('articles', []) or []
    red_lines     = check_red_lines(articles, actor_results)

    def _lvl(key):
        return actor_results.get(key, {}).get('level', 0)

    vectors = {
        'inbound_pressure':   max(_lvl('china_scs_pressure'), _lvl('beijing_coercion'), _lvl('economic_pressure')),
        'response_strength':  max(_lvl('maritime_posture'), _lvl('mofa_diplomacy'), _lvl('cpv_state'),
                                  _lvl('us_partnership'), _lvl('regional_partners')),
        'partner_strength':   max(_lvl('us_partnership'), _lvl('regional_partners')),
    }
    vectors['coercion_gap'] = max(0, vectors['inbound_pressure'] - vectors['response_strength'])

    historical = build_historical_matches(actor_results, vectors)
    so_what    = build_so_what(scan_data, red_lines, historical)
    return {
        'red_lines':          red_lines,
        'historical_matches': historical,
        'so_what':            so_what,
    }
