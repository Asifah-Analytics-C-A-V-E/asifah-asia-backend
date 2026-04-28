"""
========================================
PAKISTAN SIGNAL INTERPRETER (v1.0.0 — April 2026)
========================================

Pakistan-specific signal interpretation:
- Red lines (severity-3 thresholds across all 7 vectors)
- Historical pattern matching (against major Pakistan crises)
- "So What" framing (analyst-level interpretation)
- Canonical top_signals[] emitter for Asia BLUF + GPI consumption

Pakistan emits canonical categories:
    red_line_breached
    nuclear_signaling             -- nuclear_doctrine_level >= 3
    kinetic_pressure              -- kashmir_loc_level / afghan_border_level >= 4
    theatre_high                  -- composite L4+ catch-all
    crosstheater_pakistan_iran    -- mediation OR border activity
    crosstheater_pakistan_china   -- CPEC tempo / Gwadar
    crosstheater_pakistan_india   -- LoC / Kashmir
    regime_fracture               -- civil_military_friction OR economic_stress L4+
    mediation_active              -- proxy_mediation_level >= 3 (POSITIVE signal)
    silence_anomaly               -- ISI / Army / civilian silence
"""

PAKISTAN_FLAG = '\U0001f1f5\U0001f1f0'  # 🇵🇰

_PAK_ESC_LABELS = {
    0: 'Monitoring',
    1: 'Routine',
    2: 'Elevated Rhetoric',
    3: 'Heightened Posture',
    4: 'Active Signaling',
    5: 'Active Conflict',
}


# ============================================================
# RED LINES SCORING
# ============================================================
def _score_red_lines(scan_data):
    """
    Check all 6 Pakistan red lines and return their status.
    """
    triggered = []
    breached_count = 0

    # Pull vector levels
    kashmir   = int(scan_data.get('kashmir_loc_level', 0) or 0)
    afghan    = int(scan_data.get('afghan_border_level', 0) or 0)
    nuclear   = int(scan_data.get('nuclear_doctrine_level', 0) or 0)
    baloch    = int(scan_data.get('balochistan_insurgency_level', 0) or 0)
    civmil    = int(scan_data.get('civil_military_friction_level', 0) or 0)
    economic  = int(scan_data.get('economic_stress_level', 0) or 0)

    red_lines_def = [
        ('kashmir_loc_war',         'Kashmir LoC Major Exchange',
         '🚨', 4, kashmir, 'kashmir_loc_level'),
        ('nuclear_doctrine_shift',  'Pakistan Nuclear Doctrine Signal',
         '☢️', 4, nuclear, 'nuclear_doctrine_level'),
        ('cross_border_war',        'Pakistan-Afghanistan Cross-Border War',
         '⚔️', 4, afghan, 'afghan_border_level'),
        ('cpec_strategic_attack',   'CPEC / Gwadar Strategic Attack',
         '🚇', 4, baloch, 'balochistan_insurgency_level'),
        ('civilian_collapse',       'Civilian Government Collapse',
         '🏛️', 5, civmil, 'civil_military_friction_level'),
        ('sovereign_default',       'Sovereign Default / Reserves Crisis',
         '💸', 5, economic, 'economic_stress_level'),
    ]

    for rl_id, label, icon, threshold, current, vector in red_lines_def:
        status = 'BREACHED' if current >= threshold else \
                 ('APPROACHING' if current == threshold - 1 else 'CLEAR')
        if status == 'BREACHED':
            breached_count += 1
        triggered.append({
            'id':        rl_id,
            'label':     label,
            'icon':      icon,
            'severity':  3,
            'status':    status,
            'threshold': threshold,
            'current':   current,
            'vector':    vector,
        })

    return {
        'triggered':       triggered,
        'breached_count':  breached_count,
    }


# ============================================================
# HISTORICAL PATTERN MATCHING
# ============================================================
def _match_historical(scan_data):
    """
    Match current scan against major Pakistan crisis precedents.
    """
    matches = []

    kashmir  = int(scan_data.get('kashmir_loc_level', 0) or 0)
    afghan   = int(scan_data.get('afghan_border_level', 0) or 0)
    nuclear  = int(scan_data.get('nuclear_doctrine_level', 0) or 0)
    baloch   = int(scan_data.get('balochistan_insurgency_level', 0) or 0)
    civmil   = int(scan_data.get('civil_military_friction_level', 0) or 0)
    economic = int(scan_data.get('economic_stress_level', 0) or 0)
    mediation = int(scan_data.get('proxy_mediation_level', 0) or 0)

    # ── 2019 Balakot / Pulwama crisis ──
    bal_score = 0
    if kashmir >= 4: bal_score += 40
    if scan_data.get('pakistan_india_active'): bal_score += 20
    if afghan >= 1: bal_score += 5
    if civmil >= 2: bal_score += 5
    matches.append({
        'event':      '2019 Balakot Crisis (Pulwama → Indian Strike → Pakistan Response)',
        'date':       'Feb 2019',
        'similarity': min(bal_score, 95),
        'lesson':     ('India-Pakistan crises can spiral from terror attack → cross-border '
                       'strike → aerial dogfight → captured pilot in 4 days. Off-ramp came '
                       'via pilot return + US/Saudi backchannel.'),
    })

    # ── 2024 Iran-Pakistan Mutual Airstrikes ──
    iran_score = 0
    if scan_data.get('pakistan_iran_active'): iran_score += 30
    if afghan >= 2: iran_score += 10
    if baloch >= 2: iran_score += 20
    matches.append({
        'event':      '2024 Iran-Pakistan Airstrike Exchange (Jaish al-Adl)',
        'date':       'Jan 2024',
        'similarity': min(iran_score, 90),
        'lesson':     ('Iran struck Jaish al-Adl in Pakistan; Pakistan struck Baloch militants '
                       'in Iran 48h later. Both sides framed as counterterror against '
                       'non-state actors, allowing rapid de-escalation. Tit-for-tat with '
                       'symbolic precision works when both sides want off-ramp.'),
    })

    # ── 2022-23 IMF / Reserves Crisis ──
    imf_score = 0
    if economic >= 3: imf_score += 40
    if civmil >= 3: imf_score += 20
    if economic >= 4: imf_score += 30
    matches.append({
        'event':      '2022-23 Pakistan Reserves Crisis',
        'date':       'Late 2022',
        'similarity': min(imf_score, 90),
        'lesson':     ('Reserves dropped to <2 weeks of imports; rupee crashed 30%. '
                       'Required IMF EFF program + Saudi/UAE/China rollover deposits. '
                       'Civil-military friction during PTI removal compounded crisis.'),
    })

    # ── TTP Resurgence Post-2021 ──
    ttp_score = 0
    if afghan >= 3: ttp_score += 35
    if afghan >= 4: ttp_score += 30
    matches.append({
        'event':      'TTP Resurgence Post-US Withdrawal',
        'date':       '2021-present',
        'similarity': min(ttp_score, 90),
        'lesson':     ('Following US Afghanistan withdrawal Aug 2021, TTP attacks '
                       'inside Pakistan (esp KP) accelerated dramatically. Afghan Taliban '
                       'has refused to crack down on TTP, leading Pakistan to conduct '
                       'unprecedented strikes inside Afghanistan March 2024 and beyond.'),
    })

    # ── Pakistan as Iran-US Mediator (Apr 2026 — current) ──
    med_score = 0
    if mediation >= 3: med_score += 40
    if mediation >= 4: med_score += 35
    if scan_data.get('pakistan_mediating_iran_us'): med_score += 15
    matches.append({
        'event':      'Pakistan as Iran-US Mediation Channel',
        'date':       'April 2026',
        'similarity': min(med_score, 90),
        'lesson':     ('Pakistan hosting Witkoff-Kushner trip (since cancelled by Trump) '
                       'positioned Islamabad as primary Iran-US back-channel alongside '
                       'Oman. Mediation cancellation shifted leverage to Moscow channel. '
                       'Watch for Pakistan re-activation if Russia track stalls.'),
    })

    matches.sort(key=lambda m: m['similarity'], reverse=True)
    return matches


# ============================================================
# SO WHAT FRAMING
# ============================================================
def _build_so_what(scan_data, red_lines_triggered, historical_matches):
    """
    Analyst-level "So What" interpretation. Pulls from vectors,
    cross-theater fingerprints, and historical pattern matches.
    """
    theatre_level   = int(scan_data.get('theatre_level', 0) or 0)
    theatre_score   = int(scan_data.get('theatre_score', 0) or 0)
    kashmir         = int(scan_data.get('kashmir_loc_level', 0) or 0)
    afghan          = int(scan_data.get('afghan_border_level', 0) or 0)
    nuclear         = int(scan_data.get('nuclear_doctrine_level', 0) or 0)
    mediation       = int(scan_data.get('proxy_mediation_level', 0) or 0)
    baloch          = int(scan_data.get('balochistan_insurgency_level', 0) or 0)
    civmil          = int(scan_data.get('civil_military_friction_level', 0) or 0)
    economic        = int(scan_data.get('economic_stress_level', 0) or 0)

    iran_active     = bool(scan_data.get('pakistan_iran_active', False))
    china_active    = bool(scan_data.get('pakistan_china_active', False))
    india_active    = bool(scan_data.get('pakistan_india_active', False))
    mediating       = bool(scan_data.get('pakistan_mediating_iran_us', False))

    breach_count = sum(1 for rl in red_lines_triggered if rl.get('status') == 'BREACHED')

    # Assemble narrative summary based on dominant vector
    if breach_count >= 2:
        scenario = 'Multi-vector crisis'
    elif kashmir >= 4 or afghan >= 4:
        scenario = 'Active border crisis'
    elif nuclear >= 4:
        scenario = 'Nuclear doctrine signaling'
    elif baloch >= 4:
        scenario = 'Balochistan / CPEC crisis'
    elif civmil >= 4 or economic >= 4:
        scenario = 'Internal stability crisis'
    elif mediation >= 3:
        scenario = 'Active mediation role'
    elif theatre_level >= 3:
        scenario = 'Elevated tempo'
    else:
        scenario = 'Routine baseline'

    # Strategic implications
    implications = []
    if india_active and kashmir >= 3:
        implications.append('Kashmir LoC tempo elevated — watch for ceasefire violation cascade.')
    if afghan >= 4:
        implications.append('TTP / cross-border activity at strike-precedent threshold.')
    if nuclear >= 3:
        implications.append('Pakistan nuclear signaling will trigger GPI nuclear_signaling_global narrative.')
    if mediating:
        implications.append('Pakistan active in Iran-US mediation — feeds ME mediation_substitution narrative.')
    if china_active and baloch >= 4:
        implications.append('CPEC stress activates China-Pakistan strategic anxiety; Beijing pressure on Islamabad rises.')
    if civmil >= 4:
        implications.append('Civilian government legitimacy crisis — military actor may reassert.')
    if economic >= 4:
        implications.append('Economic distress feeds civil-military friction AND reduces Pakistan diplomatic bandwidth.')

    if not implications:
        implications.append('Pakistan currently at routine baseline — monitor for cross-theater spillover.')

    return {
        'scenario':              scenario,
        'theatre_level':         theatre_level,
        'theatre_score':         theatre_score,
        'breach_count':          breach_count,
        'implications':          implications,
        'top_historical_match':  historical_matches[0] if historical_matches else None,
        # Boolean flags (consumed by build_top_signals)
        'iran_active':           iran_active,
        'china_active':          china_active,
        'india_active':          india_active,
        'mediating_iran_us':     mediating,
        'civmil_crisis':         civmil >= 4,
        'economic_crisis':       economic >= 4,
        'kashmir_crisis':        kashmir >= 4,
        'afghan_crisis':         afghan >= 4,
        'baloch_crisis':         baloch >= 4,
        'nuclear_active':        nuclear >= 3,
    }


# ============================================================
# MAIN INTERPRETER
# ============================================================
def interpret_signals(scan_data):
    """
    Main interpreter entry point. Returns structured analytical summary.
    """
    red_lines_block = _score_red_lines(scan_data)
    historical_matches = _match_historical(scan_data)
    so_what = _build_so_what(
        scan_data,
        red_lines_block['triggered'],
        historical_matches,
    )

    return {
        'so_what':            so_what,
        'red_lines':          red_lines_block,
        'historical_matches': historical_matches[:3],
    }


# ============================================================
# CANONICAL SIGNAL EMITTER (v1.0)
# ============================================================
def build_top_signals(scan_data):
    """
    Convert Pakistan scan_data into canonical top_signals[] for Asia
    regional BLUF and Global Pressure Index. Returns list sorted by
    priority desc.
    """
    signals = []

    interp        = scan_data.get('interpretation') or {}
    so_what       = interp.get('so_what') or {}
    rl_block      = interp.get('red_lines') or {}
    triggered_rls = rl_block.get('triggered') or []

    theatre_level   = int(scan_data.get('theatre_level', 0) or 0)
    theatre_score   = int(scan_data.get('theatre_score', 0) or 0)
    kashmir         = int(scan_data.get('kashmir_loc_level', 0) or 0)
    afghan          = int(scan_data.get('afghan_border_level', 0) or 0)
    nuclear         = int(scan_data.get('nuclear_doctrine_level', 0) or 0)
    mediation       = int(scan_data.get('proxy_mediation_level', 0) or 0)
    baloch          = int(scan_data.get('balochistan_insurgency_level', 0) or 0)
    civmil          = int(scan_data.get('civil_military_friction_level', 0) or 0)
    economic        = int(scan_data.get('economic_stress_level', 0) or 0)

    iran_active     = bool(scan_data.get('pakistan_iran_active', False))
    china_active    = bool(scan_data.get('pakistan_china_active', False))
    india_active    = bool(scan_data.get('pakistan_india_active', False))
    mediating       = bool(scan_data.get('pakistan_mediating_iran_us', False))

    actors          = scan_data.get('actors') or {}
    silence_alerts  = scan_data.get('silence_anomalies') or []

    def lvl_color(lvl):
        return {0:'#6b7280', 1:'#16a34a', 2:'#facc15', 3:'#f59e0b',
                4:'#f97316', 5:'#dc2626'}.get(int(lvl), '#6b7280')

    # ── 1. Red lines BREACHED ────────────────────────────────────────
    for rl in triggered_rls:
        if not isinstance(rl, dict):
            continue
        if rl.get('status') != 'BREACHED':
            continue
        rl_id = str(rl.get('id', '')).lower()
        label = str(rl.get('label', 'Red line'))[:55]

        # Nuclear gets nuclear_signaling category
        if 'nuclear' in rl_id:
            signals.append({
                'priority':   13,
                'category':   'nuclear_signaling',
                'theatre':    'pakistan',
                'level':      max(theatre_level, 4),
                'icon':       '☢️',
                'color':      '#dc2626',
                'short_text': f'{PAKISTAN_FLAG} PAKISTAN: Nuclear doctrine signal — {label[:30]}',
                'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN nuclear red line breached: '
                               f'{rl.get("label", "")[:140]}'),
            })
            continue
        # Generic breach
        signals.append({
            'priority':   12,
            'category':   'red_line_breached',
            'theatre':    'pakistan',
            'level':      max(theatre_level, 4),
            'icon':       rl.get('icon', '🚨'),
            'color':      '#dc2626',
            'short_text': f'{PAKISTAN_FLAG} PAKISTAN: BREACH — {label}',
            'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN red line breached: '
                           f'{rl.get("label", "")[:140]}'),
        })

    # ── 2. Nuclear signaling (vector path, even without red-line breach) ──
    if nuclear >= 3 and not any(s.get('category') == 'nuclear_signaling' for s in signals):
        signals.append({
            'priority':   10 + nuclear,   # L3=13, L4=14, L5=15
            'category':   'nuclear_signaling',
            'theatre':    'pakistan',
            'level':      nuclear,
            'icon':       '☢️',
            'color':      lvl_color(nuclear),
            'short_text': f'{PAKISTAN_FLAG} PAKISTAN: Nuclear posture L{nuclear}',
            'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN nuclear vector L{nuclear} '
                           f'({_PAK_ESC_LABELS.get(nuclear, "")}) — '
                           f'NCA / missile test / doctrine language elevated. '
                           f'Pakistan = no-first-use rejection, full-spectrum deterrence.'),
        })

    # ── 3. Kinetic pressure: Kashmir LoC OR Afghan border L4+ ──
    kinetic_lvl = max(kashmir, afghan)
    if kinetic_lvl >= 4:
        if kashmir >= afghan:
            vec = 'Kashmir LoC'
            icon = '⚔️'
        else:
            vec = 'Afghan border'
            icon = '🏔️'
        signals.append({
            'priority':   9 + kinetic_lvl,    # L4=13, L5=14
            'category':   'kinetic_pressure',
            'theatre':    'pakistan',
            'level':      kinetic_lvl,
            'icon':       icon,
            'color':      lvl_color(kinetic_lvl),
            'short_text': f'{PAKISTAN_FLAG} PAKISTAN: {vec} L{kinetic_lvl}',
            'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN kinetic vector — Kashmir L{kashmir}, '
                           f'Afghan border L{afghan}. Composite L{kinetic_lvl} '
                           f'({_PAK_ESC_LABELS.get(kinetic_lvl, "")}).'),
        })

    # ── 4. Cross-theater: Pakistan-India (Kashmir / LoC) ──
    if india_active or kashmir >= 3:
        signals.append({
            'priority':   10,
            'category':   'crosstheater_pakistan_india',
            'theatre':    'pakistan',
            'level':      max(kashmir, 3),
            'icon':       '🇮🇳',
            'color':      '#7c3aed',
            'short_text': f'{PAKISTAN_FLAG} PAKISTAN: India-axis active L{max(kashmir, 3)}',
            'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN-India axis active — Kashmir L{kashmir}, '
                           f'LoC tempo elevated. Read by future India tracker.'),
        })

    # ── 5. Cross-theater: Pakistan-Iran (border / mediation) ──
    if iran_active:
        # Distinguish: mediation (positive) vs. border (threat)
        is_mediation = mediating and mediation > kashmir
        signals.append({
            'priority':   10,
            'category':   'crosstheater_pakistan_iran',
            'theatre':    'pakistan',
            'level':      max(mediation, 3),
            'icon':       '🤝' if is_mediation else '🇮🇷',
            'color':      '#10b981' if is_mediation else '#7c3aed',
            'short_text': (f'{PAKISTAN_FLAG} PAKISTAN: Iran '
                           f'{"mediation" if is_mediation else "border"} '
                           f'L{max(mediation, 3)}'),
            'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN-Iran axis active — '
                           f'mediation L{mediation}, border activity '
                           f'(Jaish al-Adl precedent active).'),
        })

    # ── 6. Cross-theater: Pakistan-China (CPEC tempo) ──
    if china_active:
        cpec_stress = baloch >= 4
        signals.append({
            'priority':   10,
            'category':   'crosstheater_pakistan_china',
            'theatre':    'pakistan',
            'level':      max(baloch, 3),
            'icon':       '🇨🇳',
            'color':      '#7c3aed',
            'short_text': (f'{PAKISTAN_FLAG} PAKISTAN: China-axis active'
                           f'{" (CPEC stress)" if cpec_stress else ""}'),
            'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN-China axis active — '
                           f'CPEC / Gwadar / strategic. '
                           f'Balochistan vector L{baloch}.'),
        })

    # ── 7. Mediation active (POSITIVE signal) ──
    if mediation >= 3:
        prio = 8 + min(mediation - 3, 2)   # L3=8, L4=9, L5=10
        signals.append({
            'priority':   prio,
            'category':   'mediation_active',
            'theatre':    'pakistan',
            'level':      mediation,
            'icon':       '🕊️',
            'color':      '#10b981',
            'short_text': f'{PAKISTAN_FLAG} PAKISTAN: Mediating Iran-US L{mediation}',
            'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN actively mediating Iran-US — '
                           f'L{mediation}. Feeds ME mediation_substitution narrative '
                           f'when paired with Russia mediation channel.'),
        })

    # ── 8. Theatre composite high (catch-all) ──
    if theatre_level >= 4 or theatre_score >= 70:
        signals.append({
            'priority':   9,
            'category':   'theatre_high',
            'theatre':    'pakistan',
            'level':      theatre_level,
            'icon':       '🔴' if theatre_level >= 4 else '🟠',
            'color':      lvl_color(theatre_level),
            'short_text': f'{PAKISTAN_FLAG} PAKISTAN L{theatre_level} — {_PAK_ESC_LABELS.get(theatre_level, "")}',
            'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN theatre composite L{theatre_level} '
                           f'(score {theatre_score}/100).'),
        })

    # ── 9. Regime fracture: civil-military OR economic L4+ ──
    if civmil >= 4 or economic >= 4:
        worst = max(civmil, economic)
        kind = 'Civil-military' if civmil >= economic else 'Economic'
        signals.append({
            'priority':   9,
            'category':   'regime_fracture',
            'theatre':    'pakistan',
            'level':      worst,
            'icon':       '🏛️' if civmil >= economic else '💸',
            'color':      lvl_color(worst),
            'short_text': f'{PAKISTAN_FLAG} PAKISTAN: {kind} stress L{worst}',
            'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN regime stress — '
                           f'civil-military L{civmil}, economic L{economic}. '
                           f'Reduces diplomatic / strategic bandwidth.'),
        })

    # ── 10. Balochistan / CPEC stress ──
    if baloch >= 4:
        signals.append({
            'priority':   10,
            'category':   'kinetic_pressure',
            'theatre':    'pakistan',
            'level':      baloch,
            'icon':       '🚇',
            'color':      lvl_color(baloch),
            'short_text': f'{PAKISTAN_FLAG} PAKISTAN: BLA / CPEC stress L{baloch}',
            'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN Balochistan insurgency L{baloch} — '
                           f'BLA targeting CPEC sites / Chinese workers / Gwadar. '
                           f'Activates China-Pakistan strategic anxiety.'),
        })

    # ── 11. Silence anomalies ──
    for sa in silence_alerts[:2]:
        if not isinstance(sa, dict):
            continue
        actor_id   = sa.get('actor_id', 'actor')
        actor_name = sa.get('actor_name', actor_id)
        # ISI silence is normal but Army silence during high tempo is significant
        is_critical = ('army' in str(actor_id).lower() or
                       'coas' in str(actor_id).lower())
        signals.append({
            'priority':   11 if is_critical else 8,
            'category':   'silence_anomaly',
            'theatre':    'pakistan',
            'level':      4 if is_critical else 3,
            'icon':       '🔇',
            'color':      '#dc2626' if is_critical else '#f59e0b',
            'short_text': f'{PAKISTAN_FLAG} PAKISTAN: Silence — {actor_name[:35]}',
            'long_text':  (f'{PAKISTAN_FLAG} PAKISTAN unusual silence from '
                           f'{actor_name}. '
                           f'{"Army silence during active tempo = pre-action indicator." if is_critical else "May indicate message coordination or internal stress."}'),
        })

    signals.sort(key=lambda s: s.get('priority', 0), reverse=True)
    return signals


# ============================================================
# STANDALONE TEST
# ============================================================
if __name__ == '__main__':
    test = {
        'theatre_level':                  4,
        'theatre_score':                  62,
        'kashmir_loc_level':              3,
        'afghan_border_level':            4,
        'nuclear_doctrine_level':         3,
        'proxy_mediation_level':          4,   # active mediation (Witkoff context)
        'balochistan_insurgency_level':   3,
        'civil_military_friction_level':  3,
        'economic_stress_level':          2,
        'pakistan_iran_active':           True,
        'pakistan_china_active':          True,
        'pakistan_india_active':          True,
        'pakistan_mediating_iran_us':     True,
        'pakistan_nuclear_signaling':     True,
        'actors':                         {},
        'silence_anomalies':              [],
    }
    test['interpretation'] = interpret_signals(test)
    sigs = build_top_signals(test)
    print(f"Emitted {len(sigs)} signals:")
    for s in sigs:
        print(f'  P{s["priority"]:2} L{s["level"]} [{s["category"]:32}] {s["short_text"]}')
