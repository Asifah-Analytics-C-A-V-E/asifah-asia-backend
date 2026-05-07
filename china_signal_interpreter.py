"""
china_signal_interpreter.py
Asifah Analytics -- Asia Backend Module
v1.0.0 -- April 2026

Signal interpretation engine for the China Coercion Tracker.

China's analytical frame answers three questions simultaneously:

  1. Is PRC coercion rising toward operational thresholds against Taiwan?
     Xi/CMC political signaling + PLA Eastern Theater activity + MFA/Global
     Times rhetoric + TAO (Taiwan Affairs Office) posture -- four vectors
     that must converge before a kinetic option becomes real.

  2. Is Beijing escalating economic coercion beyond rhetoric?
     Rare earth export controls, SWIFT-equivalent deployment, Taiwan trade
     embargo signals, chip supply chain weaponization.

  3. Is the US + allied coalition holding or fracturing?
     US commitment signaling, Taiwan defense posture, Japan regional
     involvement. Coalition breakdown is what makes Beijing's coercion
     calculus tip toward action.

Plus hidden Q4: domestic fracture signals inside China that could either
accelerate adventurism (Taiwan-as-distraction) OR foreclose it (regime
self-preservation dominates).

Author: RCGG / Asifah Analytics
"""

from datetime import datetime, timezone


# ============================================================
# RED LINE DEFINITIONS
# ============================================================
RED_LINES = [

    # ── Category A: Cross-Strait Kinetic Thresholds ─────────
    {
        'id':       'pla_invasion_mobilization',
        'label':    'PLA Large-Scale Invasion Mobilization Signals',
        'detail':   'PLA Eastern Theater announces or conducts mobilization consistent with amphibious '
                    'assault prep (not routine exercise): multi-division staging, cross-strait sealift '
                    'accumulation, Rocket Force alert status elevated',
        'severity': 3,
        'color':    '#dc2626',
        'icon':     '⚔️',
        'category': 'cross_strait_kinetic',
        'source':   'Invasion mobilization crosses from coercion to pre-kinetic. Analogous to 1995-96 '
                    'Strait Crisis but at a scale requiring US strategic decision within days.',
    },
    {
        'id':       'pla_taiwan_blockade_active',
        'label':    'PLA Announces Active Blockade of Taiwan',
        'detail':   'PLA Navy declares quarantine, maritime exclusion zone, or active blockade around '
                    'Taiwan -- not routine exercise language, but operational interdiction posture',
        'severity': 3,
        'color':    '#dc2626',
        'icon':     '🚢',
        'category': 'cross_strait_kinetic',
        'source':   'Blockade is an act of war under international law. 2022 post-Pelosi exercises '
                    'were the closest precedent; true blockade crosses a threshold not seen since 1958.',
    },
    {
        'id':       'median_line_permanent_violation',
        'label':    'Permanent Median Line Erosion (Institutionalized Crossings)',
        'detail':   'Beijing formally declares the Taiwan Strait median line extinct, or establishes '
                    'permanent PLA presence east of it, converting coercion into ongoing occupation',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '📍',
        'category': 'cross_strait_kinetic',
        'source':   'Median line has held since 1954. Permanent violation is a structural gray-zone '
                    'victory -- changes the coercion baseline without triggering US tripwire.',
    },

    # ── Category B: Economic Coercion ───────────────────────
    {
        'id':       'rare_earth_export_halt',
        'label':    'Rare Earth Export Halt to Taiwan or US',
        'detail':   'China suspends or formally restricts rare earth element exports targeting '
                    'Taiwan or US semiconductor supply chains (neodymium, dysprosium, gallium)',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '⚙️',
        'category': 'economic_coercion',
        'source':   'Rare earth chokehold is Beijing\'s clearest non-kinetic coercion lever. 2010 '
                    'Senkaku-era embargo to Japan was the prior precedent. Global supply chain shock.',
    },
    {
        'id':       'taiwan_economic_blockade',
        'label':    'Economic Blockade of Taiwan (Customs / Shipping)',
        'detail':   'China imposes extraordinary customs inspections, port quarantines, or trade '
                    'blacklisting aimed at choking Taiwan\'s economy without kinetic action',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '📦',
        'category': 'economic_coercion',
        'source':   'ECFA rollback, pineapple/mango bans, fish blacklisting are the graduated '
                    'precedents. Full blockade would disrupt 40%+ of Taiwan\'s exports.',
    },

    # ── Category C: US-China Decoupling ─────────────────────
    {
        'id':       'us_china_chip_escalation',
        'label':    'US-China Chip War Escalation Beyond CHIPS Act Baseline',
        'detail':   'Beijing formally bans Nvidia/AMD/Intel chips from Chinese markets, OR US imposes '
                    'total ban on chip equipment sales including legacy nodes. Decoupling full-spectrum.',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '💾',
        'category': 'us_china_decoupling',
        'source':   'Current regime is export controls on bleeding-edge only. Full decoupling '
                    'removes the mutual-deterrent industrial entanglement -- destabilizing.',
    },
    {
        'id':       'us_strategic_ambiguity_end',
        'label':    'US Strategic Ambiguity Officially Abandoned',
        'detail':   'US executive or legislative branch formally declares commitment to defend Taiwan '
                    '(ending 40+ years of strategic ambiguity doctrine)',
        'severity': 3,
        'color':    '#dc2626',
        'icon':     '🎯',
        'category': 'us_china_decoupling',
        'source':   'Biden made 4 ambiguity-breaking statements 2021-22, all walked back by staff. '
                    'Formal doctrine change would force Beijing to recalculate coercion tempo.',
    },

    # ── Category D: Domestic Fracture ───────────────────────
    {
        'id':       'pla_top_brass_purge',
        'label':    'PLA Top Brass Purge (Minister / Rocket Force CC)',
        'detail':   'Defense Minister or Rocket Force commander publicly removed/disappeared; signals '
                    'regime instability or pre-war loyalty consolidation',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '🪖',
        'category': 'domestic_fracture',
        'source':   'Li Shangfu removal (Oct 2023), Wei Fenghe disappearance (2023), Rocket Force '
                    'purges (2023-24) are all recent. Pattern cuts both ways -- instability OR '
                    'Stalinist pre-war consolidation.',
    },
    {
        'id':       'xi_succession_signal',
        'label':    'Xi Succession / Health / Power Dilution Signal',
        'detail':   'Public indicators of Xi succession activation: Politburo reshuffles, state media '
                    'repositioning, Hu-Jintao-style ceremonial removal, prolonged absence from public view',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '🏛️',
        'category': 'domestic_fracture',
        'source':   'Hu Jintao removal from 20th Congress (Oct 2022) is the canonical example of '
                    'power-signaling via public ceremony. Xi succession opacity is historically '
                    'unprecedented and a major tail-risk variable.',
    },

    # ── Category E: Alliance Pressure ───────────────────────
    {
        'id':       'japan_taiwan_treaty',
        'label':    'Japan Explicitly Commits to Taiwan Defense',
        'detail':   'Tokyo formally announces collective defense arrangement including Taiwan, '
                    'or stations SDF on Taiwan or in direct Taiwan-defense configuration',
        'severity': 2,
        'color':    '#ef4444',
        'icon':     '🗾',
        'category': 'alliance_pressure',
        'source':   'Abe-era "Taiwan emergency = Japan emergency" was doctrinal; formal treaty '
                    'would be a generational shift. Changes PLA operational calculus significantly.',
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
    Evaluate all China red lines against scan data.
    Returns list of triggered red lines with 'status' = BREACHED or APPROACHING.
    """
    triggered = []

    def lvl(key):
        return actor_results.get(key, {}).get('level', 0)

    xi       = lvl('xi_cmc')
    pla      = lvl('pla_operational')
    mfa      = lvl('mfa_globaltimes')
    tao      = lvl('tao')
    econ     = lvl('economic_coercion')
    tw_def   = lvl('taiwan_defense')
    us_cmt   = lvl('us_commitment')
    japan    = lvl('japan_regional')

    # ── PLA INVASION MOBILIZATION ───────────────────────────
    invasion_signal = _scan_actor_articles(
        actor_results,
        ['pla_operational', 'xi_cmc'],
        ['pla mobilization taiwan', 'amphibious assault taiwan', 'pla sealift',
         'pla cross strait mobilization', 'rocket force alert', 'pla invasion preparations',
         'pla staging taiwan', 'taiwan invasion imminent', 'pla war footing'],
    )
    if invasion_signal or pla >= 5:
        triggered.append({
            **_rl('pla_invasion_mobilization'),
            'status':  'BREACHED' if (invasion_signal and pla >= 4) else 'APPROACHING',
            'trigger': f'PLA operational L{pla} -- '
                       f'{"mobilization language detected" if invasion_signal else "approaching threshold"}',
        })

    # ── PLA TAIWAN BLOCKADE ACTIVE ──────────────────────────
    blockade_signal = _scan_actor_articles(
        actor_results,
        ['pla_operational', 'mfa_globaltimes', 'tao'],
        ['blockade taiwan', 'quarantine taiwan', 'maritime exclusion zone taiwan',
         'pla navy quarantine', 'taiwan blockade announced', 'interdiction taiwan shipping'],
    )
    if blockade_signal or (pla >= 4 and econ >= 3):
        triggered.append({
            **_rl('pla_taiwan_blockade_active'),
            'status':  'BREACHED' if blockade_signal else 'APPROACHING',
            'trigger': f'PLA L{pla}, economic coercion L{econ} -- '
                       f'{"blockade language detected" if blockade_signal else "blockade-convergence pattern"}',
        })

    # ── MEDIAN LINE PERMANENT VIOLATION ─────────────────────
    median_line_signal = _scan_actor_articles(
        actor_results,
        ['pla_operational', 'mfa_globaltimes', 'tao'],
        ['median line no longer exists', 'median line extinct', 'median line invalid',
         'no such thing as median line', 'median line abolished', 'permanent pla presence east',
         'permanent median line crossing'],
    )
    if median_line_signal:
        triggered.append({
            **_rl('median_line_permanent_violation'),
            'status':  'BREACHED',
            'trigger': 'Median line denial / permanence language detected',
        })
    elif pla >= 3 and mfa >= 3:
        triggered.append({
            **_rl('median_line_permanent_violation'),
            'status':  'APPROACHING',
            'trigger': f'PLA L{pla} + MFA L{mfa} pattern consistent with normalization-of-crossing doctrine',
        })

    # ── RARE EARTH EXPORT HALT ──────────────────────────────
    rare_earth_signal = _scan_actor_articles(
        actor_results,
        ['economic_coercion', 'mfa_globaltimes'],
        ['rare earth export ban', 'rare earth export halt', 'gallium germanium ban',
         'neodymium export restriction', 'dysprosium ban', 'rare earth weaponize',
         'rare earth export suspended', 'rare earth retaliation'],
    )
    if rare_earth_signal or econ >= 5:
        triggered.append({
            **_rl('rare_earth_export_halt'),
            'status':  'BREACHED' if rare_earth_signal else 'APPROACHING',
            'trigger': f'Economic coercion L{econ} -- '
                       f'{"rare earth restriction language detected" if rare_earth_signal else "approaching export-control threshold"}',
        })

    # ── TAIWAN ECONOMIC BLOCKADE ────────────────────────────
    econ_blockade_signal = _scan_actor_articles(
        actor_results,
        ['economic_coercion', 'mfa_globaltimes', 'tao'],
        ['ecfa terminated', 'ecfa cancelled', 'taiwan trade ban', 'taiwan customs inspections',
         'taiwan port quarantine', 'taiwan shipping blockade', 'taiwan export ban china'],
    )
    if econ_blockade_signal or econ >= 4:
        triggered.append({
            **_rl('taiwan_economic_blockade'),
            'status':  'BREACHED' if (econ_blockade_signal and econ >= 3) else 'APPROACHING',
            'trigger': f'Economic coercion L{econ} -- '
                       f'{"economic blockade language detected" if econ_blockade_signal else "graduated trade pressure rising"}',
        })

    # ── US-CHINA CHIP ESCALATION ────────────────────────────
    chip_signal = _scan_actor_articles(
        actor_results,
        ['economic_coercion', 'mfa_globaltimes'],
        ['nvidia ban china', 'amd ban china', 'intel ban china', 'chip war escalation',
         'us chip export total ban', 'legacy chip ban', 'asml ban china', 'semiconductor total embargo'],
    )
    if chip_signal:
        triggered.append({
            **_rl('us_china_chip_escalation'),
            'status':  'BREACHED' if econ >= 3 else 'APPROACHING',
            'trigger': f'Chip-war escalation language detected; economic coercion L{econ}',
        })

    # ── US STRATEGIC AMBIGUITY END ──────────────────────────
    ambiguity_signal = _scan_actor_articles(
        actor_results,
        ['us_commitment'],
        ['end strategic ambiguity', 'formal taiwan defense commitment',
         'us will defend taiwan militarily', 'taiwan defense treaty',
         'strategic clarity taiwan', 'end ambiguity doctrine'],
    )
    if ambiguity_signal:
        triggered.append({
            **_rl('us_strategic_ambiguity_end'),
            'status':  'BREACHED',
            'trigger': f'US commitment L{us_cmt} -- formal ambiguity-end language detected',
        })

    # ── PLA TOP BRASS PURGE ─────────────────────────────────
    purge_signal = _scan_actor_articles(
        actor_results,
        ['xi_cmc', 'pla_operational'],
        ['defense minister removed', 'defense minister disappeared', 'rocket force commander purge',
         'pla general removed', 'cmc reshuffle', 'pla corruption purge', 'pla commander detained'],
    )
    if purge_signal:
        triggered.append({
            **_rl('pla_top_brass_purge'),
            'status':  'BREACHED',
            'trigger': f'PLA senior leadership purge language detected; Xi L{xi}',
        })

    # ── XI SUCCESSION SIGNAL ────────────────────────────────
    succession_signal = _scan_actor_articles(
        actor_results,
        ['xi_cmc'],
        ['xi health', 'xi succession', 'xi stroke', 'xi absent public',
         'xi power dilution', 'politburo reshuffle xi', 'xi stepping back',
         'xi removed ceremony', 'xi successor named'],
    )
    if succession_signal:
        triggered.append({
            **_rl('xi_succession_signal'),
            'status':  'BREACHED' if xi <= 1 else 'APPROACHING',
            'trigger': f'Xi signal L{xi} -- succession / power-dilution language detected',
        })

    # ── JAPAN TAIWAN TREATY ─────────────────────────────────
    japan_signal = _scan_actor_articles(
        actor_results,
        ['japan_regional', 'us_commitment'],
        ['japan taiwan defense treaty', 'sdf on taiwan', 'japan taiwan collective defense',
         'taiwan emergency japan emergency formalized', 'japan taiwan mutual defense'],
    )
    if japan_signal:
        triggered.append({
            **_rl('japan_taiwan_treaty'),
            'status':  'BREACHED',
            'trigger': f'Japan regional L{japan} -- formal Taiwan defense commitment language detected',
        })
    elif japan >= 4:
        triggered.append({
            **_rl('japan_taiwan_treaty'),
            'status':  'APPROACHING',
            'trigger': f'Japan regional L{japan} -- approaching explicit-commitment threshold',
        })

    return triggered


# ============================================================
# HISTORICAL ANALOG MATCHING
# ============================================================
def build_historical_matches(actor_results, vectors):
    """
    Match current China signal state to historical analogs.
    Returns top 3 matches.
    """
    matches = []

    kinetic     = vectors.get('kinetic_pressure',   0)
    economic    = vectors.get('economic_pressure',  0)
    domestic    = vectors.get('domestic_fracture',  0)

    xi    = actor_results.get('xi_cmc', {}).get('level', 0)
    pla   = actor_results.get('pla_operational', {}).get('level', 0)
    mfa   = actor_results.get('mfa_globaltimes', {}).get('level', 0)
    econ  = actor_results.get('economic_coercion', {}).get('level', 0)

    # 2022 Pelosi Visit analog
    if pla >= 3 and mfa >= 3:
        matches.append({
            'label':      '2022 Pelosi Visit Response',
            'year':       2022,
            'similarity': 'PLA exercises + MFA threat language + median-line crossings. Aug 2022 '
                          'post-Pelosi response was the template for current coercion architecture.',
            'score':      80,
        })

    # 1995-96 Taiwan Strait Crisis
    if pla >= 4 or (pla >= 3 and econ >= 3):
        matches.append({
            'label':      '1995-96 Taiwan Strait Crisis',
            'year':       1996,
            'similarity': 'PLA missile tests + US carrier deployment. Classic coercion-signaling '
                          'episode. Ended with US strategic clarity + Taiwan Lee Teng-hui election.',
            'score':      75,
        })

    # 2024 Joint Sword analog
    if pla >= 3 and mfa >= 2:
        matches.append({
            'label':      '2024 Joint Sword Exercises',
            'year':       2024,
            'similarity': 'Joint Sword-2024A (May, post-Lai inauguration) + 2024B (Oct) were '
                          'doctrinal "punishment" exercises. Coercion-normalization pattern.',
            'score':      70,
        })

    # Hu Jintao removal 2022 analog
    if domestic >= 2 or xi <= 1:
        matches.append({
            'label':      'Hu Jintao 20th Congress Removal (Oct 2022)',
            'year':       2022,
            'similarity': 'Public ceremony of internal power consolidation. Succession opacity + '
                          'party-state signaling. Warrants watch if Xi signals change.',
            'score':      60,
        })

    # 2010 Senkaku Rare Earth Embargo
    if econ >= 3:
        matches.append({
            'label':      '2010 Senkaku Rare Earth Embargo',
            'year':       2010,
            'similarity': 'China halted rare earth exports to Japan over Senkaku territorial dispute. '
                          'Established rare-earth-as-coercion precedent that US/Taiwan calibrate against.',
            'score':      65,
        })

    # 1979 Sino-Vietnamese War analog
    if pla >= 4 and domestic >= 2:
        matches.append({
            'label':      'Sino-Vietnamese War (Feb 1979)',
            'year':       1979,
            'similarity': 'Limited "teach a lesson" war. Applicable if Beijing opts for scope-limited '
                          'coercion rather than full invasion. Deng-era pattern of controlled-use-of-force.',
            'score':      55,
        })

    matches.sort(key=lambda m: -m.get('score', 0))
    return matches[:3]


# ============================================================
# SO WHAT FACTOR
# ============================================================
def build_so_what(scan_data, red_lines_triggered, historical_matches):
    """
    Generate China coercion assessment.
    Five-level scenario ladder tuned for cross-strait dynamics.
    """
    actors = scan_data.get('actors', {})

    def lvl(key):
        return actors.get(key, {}).get('level', 0)

    xi       = lvl('xi_cmc')
    pla      = lvl('pla_operational')
    mfa      = lvl('mfa_globaltimes')
    tao      = lvl('tao')
    econ     = lvl('economic_coercion')
    tw_def   = lvl('taiwan_defense')
    us_cmt   = lvl('us_commitment')
    japan    = lvl('japan_regional')

    # Four composite vectors
    kinetic_pressure   = max(pla, xi if xi >= 3 else 0)
    economic_pressure  = econ
    domestic_fracture  = scan_data.get('domestic_fracture', 0)
    coalition_pushback = max(us_cmt, tw_def, japan)

    breached_count    = sum(1 for r in red_lines_triggered if r.get('status') == 'BREACHED')
    approaching_count = sum(1 for r in red_lines_triggered if r.get('status') == 'APPROACHING')

    # ── Scenario label ──
    if breached_count >= 2 or pla >= 5:
        scenario       = 'CRITICAL -- Multiple Red Lines Breached or PLA at Active-Operations Threshold'
        scenario_color = '#dc2626'
        scenario_icon  = '🔴'
    elif breached_count >= 1 or kinetic_pressure >= 4:
        scenario       = 'ELEVATED -- Red Line Breached or PLA at Coercion Level'
        scenario_color = '#f97316'
        scenario_icon  = '🟠'
    elif kinetic_pressure >= 3 or economic_pressure >= 3:
        scenario       = 'WARNING -- One Vector Above Confrontation Threshold'
        scenario_color = '#f59e0b'
        scenario_icon  = '🟡'
    elif kinetic_pressure >= 2 or economic_pressure >= 2 or mfa >= 3:
        scenario       = 'MONITORING -- Baseline Elevated, Coercion Signaling Active'
        scenario_color = '#3b82f6'
        scenario_icon  = '🔵'
    else:
        scenario       = 'BASELINE -- Routine Rhetoric, No Convergence'
        scenario_color = '#6b7280'
        scenario_icon  = '⚪'

    # ── Situation ──
    situation_parts = []

    if kinetic_pressure >= 2:
        situation_parts.append(
            f'Kinetic pressure vector at L{kinetic_pressure}: '
            f'PLA operational L{pla}, Xi/CMC L{xi}, TAO L{tao}. '
            f'{"PLA posture at pre-kinetic signaling threshold." if kinetic_pressure >= 4 else "Coercion signaling active but below operational threshold."}'
        )

    if economic_pressure >= 2:
        situation_parts.append(
            f'Economic coercion vector at L{economic_pressure}: '
            f'{"Supply chain weaponization language active -- rare earth, chips, trade lever pulls in play." if economic_pressure >= 4 else "Graduated economic pressure signaling, below full-coercion threshold."}'
        )

    if coalition_pushback >= 2:
        active = []
        if us_cmt  >= 3: active.append(f'US (L{us_cmt})')
        if tw_def  >= 3: active.append(f'Taiwan (L{tw_def})')
        if japan   >= 3: active.append(f'Japan (L{japan})')
        situation_parts.append(
            f'Coalition pushback at L{coalition_pushback}: '
            f'{"active counter-signaling from " + ", ".join(active) + "." if active else "monitoring, below confrontation."}'
        )

    if mfa >= 3 and kinetic_pressure < 3:
        situation_parts.append(
            f'MFA/Global Times rhetoric at L{mfa} while kinetic vector remains below L3 -- '
            f'classic "wolf warrior + operational restraint" pattern. Rhetoric-ahead-of-action.'
        )

    # ── Indicators ──
    indicators = []
    for rl in red_lines_triggered:
        if rl.get('status') == 'BREACHED':
            indicators.append({'icon': '🔴', 'text': f"RED LINE BREACHED: {rl.get('label', '')}"})
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
            'China is in a multi-breach scenario. Cross-strait crisis convergence active. '
            'Monitor Asia backend for Taiwan defense response tempo and US/Japan coordination '
            'signals. Tail-risk window for misjudgment is compressed.'
        )
    elif breached_count >= 1:
        assessment = (
            'One red line breached. Beijing has crossed a single-category threshold. Adjacent '
            'categories warrant elevated monitoring for cascade -- economic-military-alliance '
            'triad can mutually reinforce quickly.'
        )
    elif kinetic_pressure >= 4 and coalition_pushback <= 2:
        assessment = (
            'PLA coercion rising while coalition pushback is weak. Historically the most '
            'dangerous convergence -- Beijing reads soft response as permission. 1995-96 '
            'Strait Crisis was arrested by US carrier deployment; similar deterrence signal '
            'may be required here.'
        )
    elif kinetic_pressure >= 3 and economic_pressure >= 3:
        assessment = (
            'Kinetic + economic coercion rising together. Beijing executing classic dual-track '
            'coercion doctrine. Taiwan economy + security both under compression. 2024 Joint '
            'Sword + ECFA rollback pattern warrants close watch.'
        )
    elif domestic_fracture >= 3:
        assessment = (
            'Domestic fracture signals elevated inside China. Historically pattern cuts both ways: '
            'can accelerate external adventurism (distraction dynamic) OR foreclose it '
            '(self-preservation dominates). Watch Xi public-appearance cadence + Politburo reshuffles.'
        )
    elif mfa >= 3 and kinetic_pressure < 3:
        assessment = (
            'Rhetoric leading, action restrained. Classic coercion-signaling-without-commitment '
            'pattern. Beijing testing coalition resolve, pricing deterrence. Watch for 48-72 '
            'hour cycles of provocation-and-observation.'
        )
    elif coalition_pushback >= 3:
        assessment = (
            'Coalition pushback leading. US + Taiwan + Japan signaling elevated. Healthy '
            'deterrence posture, assuming Beijing reads signals accurately. Watch for '
            'miscommunication risk -- strong deterrence unread can accidentally escalate.'
        )
    else:
        assessment = 'China below convergence threshold. Routine monitoring mode.'

    # ── Watch list ──
    watch_list = []
    if pla >= 3:
        watch_list.append('PLA Eastern Theater exercise announcements -- tempo and scope signals')
    if pla >= 2:
        watch_list.append('Taiwan MND daily air-sortie bulletins -- median-line crossing counts')
    if econ >= 2:
        watch_list.append('MOFCOM export-control announcements -- rare earth / chip measures')
    if xi >= 2 or domestic_fracture >= 2:
        watch_list.append('Xi public appearance cadence -- gaps, venue changes, succession signals')
    if us_cmt >= 2:
        watch_list.append('AIT director statements + DoS Taiwan travel warnings')
    if japan >= 2:
        watch_list.append('JSDF Yonaguni / Miyako deployment posture + Ishigaki movements')
    if tao >= 2:
        watch_list.append('TAO press conference cadence -- weekly Wednesday tempo + content tone')
    if mfa >= 2:
        watch_list.append('Global Times editorials + Hu Xijin posts -- proxy for regime mood')

    if not watch_list:
        watch_list.append('Routine monitoring -- no elevated-attention signals')

    return {
        'scenario':         scenario,
        'scenario_color':   scenario_color,
        'scenario_icon':    scenario_icon,
        'situation':        ' '.join(situation_parts) if situation_parts else 'All vectors below monitoring threshold. China in baseline coercion posture.',
        'indicators':       indicators,
        'assessment':       assessment,
        'watch_list':       watch_list,
        # Vector readout
        'kinetic_pressure':   kinetic_pressure,
        'economic_pressure':  economic_pressure,
        'domestic_fracture':  domestic_fracture,
        'coalition_pushback': coalition_pushback,
        # Historical context
        'historical_matches': historical_matches or [],
        'confidence_note':    'Analysis based on OSINT signal aggregation. Does not reflect classified '
                              'intelligence. Four-vector framework is Asifah-specific methodology and '
                              'should not be cited as official assessment.',
    }


# ============================================================
# TOP-LEVEL INTERPRETER
# ============================================================
def interpret_signals(scan_data):
    """
    Given scan_data from rhetoric_tracker_china, returns:
      {'red_lines': [...], 'so_what': {...}, 'historical_matches': [...]}
    """
    actor_results = scan_data.get('actors', {})
    articles      = scan_data.get('articles', [])

    red_lines_triggered = check_red_lines(articles, actor_results)

    def lvl(key):
        return actor_results.get(key, {}).get('level', 0)

    vectors = {
        'kinetic_pressure':  max(lvl('pla_operational'), lvl('xi_cmc') if lvl('xi_cmc') >= 3 else 0),
        'economic_pressure': lvl('economic_coercion'),
        'domestic_fracture': scan_data.get('domestic_fracture', 0),
        'us_commitment':     lvl('us_commitment'),
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
# Canonical signal shape:
# {
#     'priority':   int (0-15, higher = more important),
#     'category':   str,        # red_line_breached | theatre_high | kinetic_pressure |
#                               # economic_pressure | domestic_fracture | coalition_pushback |
#                               # silence_anomaly | influence_high
#     'theatre':    'china',
#     'level':      0-5,
#     'icon':       str (emoji),
#     'color':      str (hex),
#     'short_text': str (≤80 chars),
#     'long_text':  str (≤200 chars),
# }

CHINA_FLAG = '\U0001f1e8\U0001f1f3'  # 🇨🇳


# ============================================================
# v2.2+ — COMMODITY CONVERGENCE INJECTION
# ============================================================
# Reads commodity context from scan_data (populated by rhetoric_tracker_china
# via _read_crosstheater_amplifiers). When Iran/Hormuz pressure is active AND
# China's oil import dependency creates compound risk, emit a high-priority
# convergence signal that flows into BLUF prose and up to GPI.
#
# This is THE structural reason China cares about Iran — encoded as analysis,
# not as a static fact. The rhetoric reads as: "Iran/Hormuz pressure compounded
# by China's ~50% oil import dependency through the Strait."
#
# Mirrors the wheat-Lebanon convergence pattern (humanitarian crisis × commodity
# pressure × import dependency = compound risk).

def build_commodity_convergence_signals(scan_data):
    """
    Inject commodity-derived convergence signals into China's top_signals.
    Reads cross-theater amplifiers from scan_data and emits signals when
    structural commodity dependencies intersect with active geopolitical pressure.

    Returns list of signal dicts (same canonical shape as build_top_signals).
    Empty list if no convergence is currently active.
    """
    signals = []

    # crosstheater_amplifiers is written by rhetoric_tracker_china into result dict
    amps = scan_data.get('crosstheater_amplifiers', {}) or {}
    iran_hormuz_active = amps.get('iran_hormuz_pressure', False)
    iran_score         = amps.get('iran_theatre_score', 0) or 0
    iran_irgc          = amps.get('iran_irgc_level', 0) or 0

    # ── HORMUZ-CHINA OIL CONVERGENCE ──
    # Fires when Iran posture is at operational levels AND China's structural
    # ~50% oil import dependency through Hormuz is therefore stressed.
    # Priority 13 — sits ABOVE most country-internal signals because this is
    # a compound, cross-regional risk that GPI should surface.
    if iran_hormuz_active:
        signals.append({
            'priority':   13,
            'category':   'hormuz_china_oil_dependency',
            'theatre':    'china',
            'level':      max(3, min(5, int(iran_score / 20))),  # rough mapping: score 60→L3, 80→L4, 100→L5
            'icon':       '🛢️',
            'color':      '#f59e0b',
            'short_text': f'{CHINA_FLAG} CHINA: Hormuz oil convergence — Iran pressure × import dep',
            'long_text':  (
                f'CHINA oil supply convergence — Iran posture (score {iran_score}, '
                f'IRGC L{iran_irgc}) compounds China\'s ~50% crude import dependency '
                f'through Strait of Hormuz. Watch China MFA "stability" framing, '
                f'BRI/CPEC investment cadence, RU/Central Asia substitution moves, '
                f'yuan settlement deal news. Cross-regional pressure on energy security.'
            ),
            # Convergence flags for downstream consumers (regional BLUF, GPI, frontend)
            'hormuz_china_oil_dependency_active': True,
            'convergence_states': {
                'hormuz_china_oil_dependency': {
                    'active':       True,
                    'iran_score':   iran_score,
                    'iran_irgc':    iran_irgc,
                    'alert_level':  'elevated' if iran_score < 70 else ('high' if iran_score < 85 else 'surge'),
                },
            },
        })

    return signals


# ============================================================
# v2.0+ — TOP SIGNALS (BLUF / GPI consumable)
# ============================================================
# Emits a pre-prioritized list of signal dicts that the Asia Regional BLUF
# (and ultimately the Global Pressure Index) consume directly.
#
# Canonical signal shape:
# {
#     'priority':   int (0-15, higher = more important),
#     'category':   str,        # red_line_breached | theatre_high | kinetic_pressure |
#                               # economic_pressure | domestic_fracture | coalition_pushback |
#                               # silence_anomaly | influence_high | hormuz_china_oil_dependency
#     'theatre':    'china',
#     'level':      0-5,
#     'icon':       str (emoji),
#     'color':      str (hex),
#     'short_text': str (≤80 chars),
#     'long_text':  str (≤200 chars),
# }

def build_top_signals(scan_data):
    """
    Build China's top_signals[] for BLUF/GPI consumption.
    Reads from scan_data dict (post-interpret_signals output).
    Returns sorted list (descending priority).
    """
    signals = []

    actor_results = scan_data.get('actors', {}) or {}
    so_what       = scan_data.get('so_what', {}) or {}
    red_lines     = scan_data.get('red_lines', []) or []

    overall_level = scan_data.get('overall_level', 0) or 0
    overall_score = scan_data.get('theatre_score',
                    scan_data.get('overall_score', 0)) or 0

    # Vector readouts from so_what
    kinetic_pressure   = so_what.get('kinetic_pressure', 0) or 0
    economic_pressure  = so_what.get('economic_pressure', 0) or 0
    domestic_fracture  = so_what.get('domestic_fracture', 0) or 0
    coalition_pushback = so_what.get('coalition_pushback', 0) or 0

    # Actor-specific levels
    pla_level = actor_results.get('pla_operational', {}).get('level', 0) or 0
    xi_level  = actor_results.get('xi_cmc',           {}).get('level', 0) or 0
    econ_level = actor_results.get('economic_coercion', {}).get('level', 0) or 0

    # ============================================
    # 1. RED LINES BREACHED (highest priority)
    # ============================================
    for rl in red_lines:
        if not isinstance(rl, dict): continue
        status = rl.get('status', '')
        label  = rl.get('label', 'Red line')
        if status == 'BREACHED':
            signals.append({
                'priority':   12,
                'category':   'red_line_breached',
                'theatre':    'china',
                'level':      overall_level,
                'icon':       rl.get('icon', '🚨'),
                'color':      '#dc2626',
                'short_text': f'{CHINA_FLAG} CHINA: BREACH — {label[:55]}',
                'long_text':  f'CHINA red line breached at L{overall_level}: {label}.',
            })
        elif status == 'APPROACHING':
            signals.append({
                'priority':   8,
                'category':   'red_line_approaching',
                'theatre':    'china',
                'level':      overall_level,
                'icon':       '🟠',
                'color':      '#f97316',
                'short_text': f'{CHINA_FLAG} CHINA: Approaching — {label[:50]}',
                'long_text':  f'CHINA approaching red line: {label}.',
            })

    # ============================================
    # 2. THEATRE-HIGH (overall L4+)
    # ============================================
    if overall_level >= 4:
        signals.append({
            'priority':   9 + overall_level,
            'category':   'theatre_high',
            'theatre':    'china',
            'level':      overall_level,
            'icon':       '🔴',
            'color':      '#dc2626' if overall_level >= 5 else '#ef4444',
            'short_text': f'{CHINA_FLAG} CHINA L{overall_level} — Coercion posture',
            'long_text':  f'CHINA at L{overall_level} — composite coercion posture (score {overall_score}/100). Multi-vector pressure across kinetic, economic, and political channels.',
        })

    # ============================================
    # 3. KINETIC PRESSURE (PLA operational)
    # ============================================
    if kinetic_pressure >= 4:
        signals.append({
            'priority':   10,
            'category':   'kinetic_pressure',
            'theatre':    'china',
            'level':      kinetic_pressure,
            'icon':       '⚔️',
            'color':      '#dc2626',
            'short_text': f'{CHINA_FLAG} CHINA: Kinetic L{kinetic_pressure} (PLA L{pla_level})',
            'long_text':  f'CHINA kinetic pressure L{kinetic_pressure} — PLA operational level L{pla_level}; cross-strait coercion at incident-level tempo.',
        })
    elif kinetic_pressure >= 3:
        signals.append({
            'priority':   8,
            'category':   'kinetic_pressure',
            'theatre':    'china',
            'level':      kinetic_pressure,
            'icon':       '⚔️',
            'color':      '#ef4444',
            'short_text': f'{CHINA_FLAG} CHINA: Kinetic L{kinetic_pressure} (PLA L{pla_level})',
            'long_text':  f'CHINA kinetic pressure L{kinetic_pressure} — PLA operational L{pla_level}; cross-strait coercion active.',
        })
    elif kinetic_pressure >= 2:
        signals.append({
            'priority':   5,
            'category':   'kinetic_pressure',
            'theatre':    'china',
            'level':      kinetic_pressure,
            'icon':       '🔶',
            'color':      '#f59e0b',
            'short_text': f'{CHINA_FLAG} CHINA: Kinetic signaling L{kinetic_pressure}',
            'long_text':  f'CHINA kinetic signaling L{kinetic_pressure} — below operational threshold.',
        })

    # ============================================
    # 4. ECONOMIC PRESSURE
    # ============================================
    if economic_pressure >= 3:
        signals.append({
            'priority':   7 + economic_pressure,
            'category':   'economic_pressure',
            'theatre':    'china',
            'level':      economic_pressure,
            'icon':       '💰',
            'color':      '#f97316',
            'short_text': f'{CHINA_FLAG} CHINA: Economic coercion L{economic_pressure}',
            'long_text':  f'CHINA economic coercion L{economic_pressure} — trade/investment pressure tools active (level {econ_level}).',
        })

    # ============================================
    # 5. KINETIC + ECONOMIC CONVERGENCE (special signal)
    # ============================================
    if kinetic_pressure >= 3 and economic_pressure >= 3:
        signals.append({
            'priority':   11,
            'category':   'kinetic_economic_convergence',
            'theatre':    'china',
            'level':      max(kinetic_pressure, economic_pressure),
            'icon':       '🌀',
            'color':      '#dc2626',
            'short_text': f'{CHINA_FLAG} CHINA: Kinetic+Economic convergence',
            'long_text':  f'CHINA dual-vector pressure — kinetic L{kinetic_pressure} converging with economic L{economic_pressure}; coercion campaign coordinated across channels.',
        })

    # ============================================
    # 6. DOMESTIC FRACTURE
    # ============================================
    if domestic_fracture >= 3:
        signals.append({
            'priority':   6 + domestic_fracture,
            'category':   'domestic_fracture',
            'theatre':    'china',
            'level':      domestic_fracture,
            'icon':       '🏚️',
            'color':      '#a855f7',
            'short_text': f'{CHINA_FLAG} CHINA: Domestic fracture L{domestic_fracture}',
            'long_text':  f'CHINA domestic fracture indicators L{domestic_fracture} — internal stress (economic, demographic, political) accelerating; external posturing risk elevated.',
        })

    # ============================================
    # 7. XI/CMC POLITICAL SIGNALING (high)
    # ============================================
    if xi_level >= 4:
        signals.append({
            'priority':   8,
            'category':   'xi_cmc_signaling',
            'theatre':    'china',
            'level':      xi_level,
            'icon':       '🏛️',
            'color':      '#dc2626',
            'short_text': f'{CHINA_FLAG} CHINA: Xi/CMC L{xi_level} signaling',
            'long_text':  f'CHINA Xi Jinping / Central Military Commission political signaling L{xi_level} — top-level direction language detected.',
        })

    # ============================================
    # 8. COALITION PUSHBACK (positive signal — de-escalating)
    # ============================================
    if coalition_pushback >= 3:
        signals.append({
            'priority':   5 + coalition_pushback,
            'category':   'coalition_pushback',
            'theatre':    'china',
            'level':      coalition_pushback,
            'icon':       '🛡️',
            'color':      '#10b981',
            'short_text': f'{CHINA_FLAG} CHINA: Coalition pushback L{coalition_pushback}',
            'long_text':  f'CHINA-facing coalition response L{coalition_pushback} — US/Japan/Australia/EU coordinated signaling detected; deterrence posture firming.',
        })

    # ============================================
    # 9. COMMODITY CONVERGENCE (cross-regional)
    # ============================================
    # Hormuz-China oil dependency, etc. — fires when structural commodity
    # exposure intersects with active geopolitical pressure from another
    # theater. These are HIGH priority because they're cross-regional
    # compound risks that would otherwise be invisible from a China-only
    # view of the world.
    try:
        convergence_signals = build_commodity_convergence_signals(scan_data)
        if convergence_signals:
            signals.extend(convergence_signals)
            print(f"[China Interpreter] Commodity convergence: {len(convergence_signals)} signal(s) emitted")
    except Exception as e:
        print(f"[China Interpreter] Commodity convergence error: {e}")

    # Sort descending; BLUF will dedupe + globally rank
    signals.sort(key=lambda s: s['priority'], reverse=True)
    return signals
