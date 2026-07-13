"""
═══════════════════════════════════════════════════════════════════════
  ASIFAH ANALYTICS — DPRK SIGNAL INTERPRETER
  dprk_signal_interpreter.py  ·  v1.0.0 (Jul 13 2026)  ·  Asia backend
═══════════════════════════════════════════════════════════════════════

THE INSTRUMENT: LEVERAGE INTEGRITY — and the read is INVERTED.

Third member of the instrument family:
    Kazakhstan -> is the HEDGE holding?
    Poland     -> is the CONSENSUS holding?
    DPRK       -> is the LEVERAGE holding -- and what does Pyongyang do when
                  it isn't?

The naive read says the DPRK is dangerous when it is strong and courted, riding
high on Russian patronage. That read is backwards, and getting it backwards is
the whole reason this file exists.

    THE DPRK ESCALATES WHEN ITS LEVERAGE DECAYS, NOT WHEN IT PEAKS.

A nuclear test is not a war signal. It is a RELEVANCE signal -- the way
Pyongyang forces itself back onto an agenda it has been left off. The DPRK's
entire power derives from what its patrons need from it. Kursk bought an
unprecedented windfall: money, missile technology, food, energy, legitimacy, a
seat at a table. A ceasefire does not reward Pyongyang. IT DEFUNDS IT.

So the dangerous condition is not being courted. It is being NEGOTIATED AROUND.

And the tells are already on the tape: Kim skipped Red Square while his own
soldiers marched through it. A ceremony was scrubbed of senior Russian presence.
A memorial wall carries 2,288 names for a war whose ending nobody is asking him
about. The war that pays him is winding down and he is not at the table.

CONSEQUENCE FOR THE SCORING (read this before touching any number below):
    leverage_integrity HIGH  -> the SAFE state. Green. A courted DPRK has no
                                reason to shout.
    leverage_integrity LOW   -> the DANGEROUS state. Red. Escalation pressure.
    composite_modifier = the INVERSE of leverage integrity.

Anyone who "fixes" that polarity because it looks upside-down will have broken
the instrument. It is upside-down on purpose. That is the finding.

CONTRACT WITH conflict_repricing_detector.py (theatre 'korea', mode='habituation'):
    This interpreter MUST emit, at the top level of its return dict:
        provocation_active   (bool)
        provocation_class    (nuclear_test|icbm|satellite|irbm|srbm|cruise|sub_threshold|None)
        leverage_integrity   (0-100 int, or None)
    The Korea repricing card reads these to ask whether the tape still flinches.
    Two sensors, opposite ends, same variable: the rhetoric layer measures
    whether the leverage is decaying; the market layer measures whether anyone
    is still listening when he shouts. Convergence in the doctrinal sense.

TEMPO: mode='actor'. Unlike Poland (where Russia never claims), the DPRK
ANNOUNCES. KCNA has a cadence. A claiming actor going quiet is the canonical
quiet-before-storm case, and it is why this tracker was worth building.
"""

from datetime import datetime, timezone, timedelta

INTERPRETER_VERSION = '1.0.0'

DISCLAIMER = ('This composite is a CONVERGENCE indicator, NOT a probability of '
              'action.')


# ════════════════════════════════════════════════════════════
# PRIMITIVE
# ════════════════════════════════════════════════════════════

def _corpus(scan_data):
    """Every text surface the scan collected, lowercased once."""
    out = []
    for key in ('articles_en', 'articles_ko', 'articles_ru', 'articles_zh'):
        for a in (scan_data.get(key) or []):
            out.append(((a.get('title') or '') + ' ' + (a.get('description') or '')).lower())
    for key in ('telegram_messages', 'bluesky_signals', 'reddit_signals'):
        for s in (scan_data.get(key) or []):
            out.append(((s.get('text') or s.get('title') or '')).lower())
    return out


def _check_keywords(scan_data, keywords):
    """Count corpus items matching any keyword. Returns (count, sample_titles)."""
    corpus = scan_data.get('_corpus')
    if corpus is None:
        corpus = _corpus(scan_data)
        scan_data['_corpus'] = corpus
    hits, samples = 0, []
    for text in corpus:
        if any(kw in text for kw in keywords):
            hits += 1
            if len(samples) < 3:
                samples.append(text[:150])
    return hits, samples


# ════════════════════════════════════════════════════════════
# VECTOR 1 — LEVERAGE INTEGRITY (the instrument)
# ════════════════════════════════════════════════════════════
# Two opposing keyword sets. PATRON ATTENTION credits the leverage; SIDELINING
# debits it. The score is what remains.

PATRON_ATTENTION = [
    # Russia needs him and says so
    'putin kim', 'kim putin', 'kim jong un putin', 'putin north korea visit',
    'russia north korea treaty', 'mutual defense treaty', 'comprehensive strategic partnership',
    'russia thanks north korea', 'putin praises north korean', 'russian delegation pyongyang',
    'lavrov pyongyang', 'shoigu pyongyang', 'russia north korea summit',
    'north korean troops praised', 'heroes of russia north korean',
    # The rent itself: what Pyongyang is being paid
    'russia oil north korea', 'russia food aid north korea', 'russia grain north korea',
    'missile technology transfer north korea', 'russia satellite help north korea',
    'air defense north korea russia', 'russia pays north korea',
    'north korea workers russia', 'labor agreement russia north korea',
    # China needs him
    'xi kim', 'kim xi jinping', 'china north korea friendship', 'china north korea trade',
    'chinese delegation pyongyang', 'china aid north korea',
    # A seat at a table
    'north korea talks', 'nuclear talks north korea', 'trump kim',
    'north korea diplomacy', 'engagement north korea', 'summit north korea',
    '\ubd81\ub7ec \uc815\uc0c1\ud68c\ub2f4',
]

SIDELINING_TELLS = [
    # The live ones, July 2026
    'kim skips', 'kim absent', 'kim did not attend', 'kim missed',
    'north korea sidelined', 'pyongyang sidelined', 'north korea excluded',
    'north korea snubbed', 'north korea left out', 'without north korea',
    'no north korean representative', 'ceremony without russian',
    # The war that pays him is ending
    'ukraine ceasefire', 'ukraine peace deal', 'ukraine war ends',
    'putin trump zelensky', 'peace negotiations ukraine', 'armistice ukraine',
    'russia ukraine settlement', 'end of the war ukraine',
    # The rent being switched off
    'north korea troops withdrawal', 'north korean troops return',
    'north korean troops home', 'russia reduces aid north korea',
    'north korea russia rift', 'dprk russia tension', 'russia distances north korea',
    'north korea no longer needed',
    # Diplomatic irrelevance
    'north korea ignored', 'talks without pyongyang', 'north korea not invited',
]


def _score_leverage_integrity(scan_data, food=None, tempo_baseline=None):
    """THE INSTRUMENT. High = safe. Low = dangerous. Do not 'fix' the polarity."""
    attention, att_s = _check_keywords(scan_data, PATRON_ATTENTION)
    sidelined, side_s = _check_keywords(scan_data, SIDELINING_TELLS)

    # Baseline 60: the DPRK's structural position is neither secure nor collapsed.
    score = 60
    score += min(28, attention * 3)     # patron attention credits leverage
    score -= min(45, sidelined * 5)     # sidelining debits it, and debits harder

    # FOOD SECURITY FEEDS THE INSTRUMENT (this is why the vector is not optional).
    # A hungrier DPRK NEEDS its patrons more, which means its leverage is worth
    # less to it in relative terms -- the same patronage buys less compliance.
    # Hunger does not make Pyongyang safer. It makes it more dependent, and a
    # dependent actor whose patron is walking away has further to fall.
    if food and food.get('band') in ('elevated', 'high'):
        score -= 8

    score = max(0, min(100, score))
    state = ('intact' if score >= 75 else 'eroding' if score >= 50
             else 'decaying' if score >= 25 else 'collapsed')

    if state == 'intact':
        reading = ('Patron attention is running ahead of sidelining signals. '
                   'Pyongyang is being courted rather than negotiated around -- '
                   'historically the QUIETER condition, because a DPRK with a seat '
                   'at the table has no need to force its way back to one.')
    elif state == 'eroding':
        reading = ('Patron attention and sidelining signals are roughly balanced. '
                   'The leverage is neither secure nor spent. This is the band where '
                   'the direction of travel matters more than the level.')
    elif state == 'decaying':
        reading = ('Sidelining signals are outrunning patron attention. The war rent '
                   'is being switched off while Pyongyang is not at the table. '
                   'Historically, this is the condition that PRECEDES a relevance '
                   'signal -- a test, a launch, a demonstration -- rather than the '
                   'condition that follows one.')
    else:
        reading = ('Leverage has collapsed on the available signal. Pyongyang is '
                   'being negotiated around on the question that pays it. The '
                   'historical pattern in this band is escalation FOR ATTENTION, not '
                   'escalation for advantage. Read any subsequent provocation as a '
                   'bid for relevance.')

    return {
        'integrity': score, 'state': state,
        'attention_signals': attention, 'sidelining_signals': sidelined,
        'food_drag': bool(food and food.get('band') in ('elevated', 'high')),
        'reading': reading,
        'samples': (side_s or att_s)[:2],
        'polarity_note': ('INVERTED: high integrity = safe. The DPRK escalates when '
                          'leverage DECAYS, not when it peaks.'),
    }


# ════════════════════════════════════════════════════════════
# VECTOR 2 — NUCLEAR SIGNALING (type x location x audience)
# ════════════════════════════════════════════════════════════
# LOCATION IS THE AUDIENCE. This is the whole point of the vector. A lofted ICBM
# is addressed to Washington. An SRBM into the East Sea is addressed to Seoul and
# Tokyo. A Sohae satellite launch is addressed to a domestic audience and to
# prestige. A seventh test at Punggye-ri is addressed to everyone at once.
#
# Collapsing these into "missile activity: elevated" throws away the message.

PROVOCATION_CLASSES = {
    'nuclear_test': {
        'weight': 5.0, 'audience': 'everyone at once',
        'keywords': ['nuclear test', 'seventh nuclear test', '7th nuclear test',
                     'punggye-ri test', 'underground nuclear', 'detonation north korea',
                     '\ud575\uc2e4\ud5d8'],
    },
    'icbm': {
        'weight': 4.0, 'audience': 'Washington',
        'keywords': ['icbm', 'hwasong-17', 'hwasong-18', 'hwasong-19', 'hwasong-20',
                     'intercontinental ballistic', 'lofted trajectory', 'north korea lofted',
                     '\ub300\ub959\uac04\ud0c4\ub3c4\ubbf8\uc0ac\uc77c'],
    },
    'satellite': {
        'weight': 2.5, 'audience': 'a domestic audience, and prestige',
        'keywords': ['satellite launch', 'reconnaissance satellite', 'spy satellite',
                     'sohae', 'tongchang-ri', 'chollima-1', 'space launch vehicle'],
    },
    'irbm': {
        'weight': 3.0, 'audience': 'Guam and the US regional posture',
        'keywords': ['irbm', 'intermediate-range', 'hwasong-12', 'over japan',
                     'missile over japan', 'hypersonic north korea'],
    },
    'srbm': {
        'weight': 2.0, 'audience': 'Seoul and Tokyo',
        'keywords': ['short-range ballistic', 'srbm', 'kn-23', 'kn-24', 'kn-25',
                     'east sea missile', 'sea of japan missile', 'multiple rocket launcher'],
    },
    'cruise': {
        'weight': 1.5, 'audience': 'the operational, not the political, reader',
        'keywords': ['cruise missile north korea', 'hwasal', 'strategic cruise missile'],
    },
    'sub_threshold': {
        'weight': 1.0, 'audience': 'Seoul, cheaply',
        'keywords': ['trash balloon', 'gps jamming', 'loudspeaker', 'artillery firing',
                     'maritime buffer zone', 'drone incursion'],
    },
}


def _score_nuclear_signaling(scan_data):
    fired, weighted = {}, 0.0
    for cls, cfg in PROVOCATION_CLASSES.items():
        n, s = _check_keywords(scan_data, cfg['keywords'])
        if n:
            fired[cls] = {'signals': n, 'weight': cfg['weight'],
                          'audience': cfg['audience'], 'samples': s[:1]}
            weighted += n * cfg['weight']

    # The dominant class is the LOUDEST message, not the most frequent one --
    # one nuclear test outranks fifty balloon launches, and the ranking must
    # reflect that or the audience read collapses.
    dominant = max(fired, key=lambda c: PROVOCATION_CLASSES[c]['weight']) if fired else None

    band = ('high' if weighted >= 20 else 'elevated' if weighted >= 10
            else 'simmering' if weighted >= 3 else 'quiet')

    if dominant:
        aud = PROVOCATION_CLASSES[dominant]['audience']
        reading = (f"Dominant provocation class this cycle: {dominant.replace('_',' ')}. "
                   f"On the location-and-type read, that message is addressed to {aud}. "
                   f"Class, not count, carries the meaning.")
    else:
        reading = 'No provocation class active this cycle on the available corpus.'

    return {
        'band': band, 'weighted_score': round(weighted, 1),
        'classes_fired': fired, 'dominant_class': dominant,
        'last_class': dominant,
        'provocation_active': bool(dominant),
        'reading': reading,
    }


# ════════════════════════════════════════════════════════════
# NUCLEAR TRIPWIRE — the Black Swan
# ════════════════════════════════════════════════════════════
# Six tests, one tunnel complex. Punggye-ri tunnel 3 has been assessed ready
# since 2022. A SEVENTH TEST is discrete, unambiguous, and observable -- which
# is exactly what a Black Swan module needs and what most "risk" indicators lack.

TEST_PREP_SIGNALS = [
    'punggye-ri activity', 'punggye-ri tunnel', 'tunnel 3 punggye',
    'test site preparation', 'nuclear test preparation', 'test site activity',
    'excavation punggye', 'spoil pile punggye', 'imagery punggye',
    'nuclear test imminent', 'north korea ready to test', 'test could occur',
    'yongbyon reprocessing', 'plutonium reprocessing', 'enriched uranium north korea',
]
TEST_EXECUTED = [
    'north korea conducted nuclear test', 'seventh nuclear test conducted',
    'seismic event north korea', 'artificial earthquake north korea',
    'nuclear detonation north korea', 'north korea tests nuclear device',
]


def _score_nuclear_tripwire(scan_data, nuclear):
    executed, ex_s = _check_keywords(scan_data, TEST_EXECUTED)
    prep, prep_s = _check_keywords(scan_data, TEST_PREP_SIGNALS)

    if executed >= 2:
        state = 'BREACHED'
        reading = ('A seventh nuclear test appears to have been conducted. This is the '
                   'discrete event the tripwire exists for. Every downstream read on '
                   'this platform -- leverage, repricing, regional posture -- should '
                   'be treated as operating on a changed baseline from this point.')
    elif prep >= 4 or (prep >= 2 and nuclear.get('band') == 'high'):
        state = 'APPROACHING'
        reading = ('Test-site preparation signals are converging with elevated nuclear '
                   'signaling. This is consistent with the pattern that has historically '
                   'preceded a test -- it does not establish that one will occur.')
    elif prep >= 1:
        state = 'ELEVATED'
        reading = ('Test-site preparation signals present but not converging. '
                   'Punggye-ri has been assessed test-ready for years; activity there '
                   'is a necessary but not sufficient condition.')
    else:
        state = 'QUIET'
        reading = 'No test-preparation signals on the available corpus this cycle.'

    return {
        'state': state, 'prep_signals': prep, 'executed_signals': executed,
        'reading': reading, 'black_swan': state == 'BREACHED',
        'samples': (ex_s or prep_s)[:2],
    }


def _gate_provocation_on_tripwire(nuclear, tripwire):
    """PREPARATION IS NOT EXECUTION. Caught in end-to-end testing, Jul 13 2026.

    The nuclear_test keyword net matches "nuclear test PREPARATION imagery" --
    the word 'test' sits inside the word 'test preparation'. Left alone, a
    satellite photo of a truck at Punggye-ri would set provocation_class =
    'nuclear_test', and conflict_repricing_detector.py would render, on the
    Market Watch page: "A nuclear test registered in the rhetoric layer this
    cycle." We would be telling readers the DPRK detonated a weapon because
    somebody photographed a tunnel entrance.

    The fix is structural rather than another keyword: THE TRIPWIRE IS THE
    EXECUTED-TEST DETECTOR. A real test trips it to BREACHED. So if the tripwire
    is not BREACHED, no test occurred, and 'nuclear_test' cannot be the
    provocation class no matter what the keywords matched. Demote to the next
    loudest class that actually fired; if none did, there is no provocation.

    Preparation still speaks -- through the tripwire, which is where it belongs.
    """
    if nuclear.get('dominant_class') != 'nuclear_test':
        return nuclear
    if tripwire.get('state') == 'BREACHED':
        return nuclear

    demoted = {c: v for c, v in (nuclear.get('classes_fired') or {}).items()
               if c != 'nuclear_test'}
    new_dominant = (max(demoted, key=lambda c: PROVOCATION_CLASSES[c]['weight'])
                    if demoted else None)

    nuclear = dict(nuclear)
    nuclear['classes_fired'] = demoted
    nuclear['dominant_class'] = new_dominant
    nuclear['last_class'] = new_dominant
    nuclear['provocation_active'] = bool(new_dominant)
    nuclear['nuclear_test_demoted'] = True
    if new_dominant:
        aud = PROVOCATION_CLASSES[new_dominant]['audience']
        nuclear['reading'] = (
            f"Nuclear-test language appears in the corpus but the tripwire is not "
            f"breached -- this is test PREPARATION reporting, not an executed test, "
            f"and it is read through the tripwire rather than as a provocation. "
            f"Dominant provocation class this cycle: {new_dominant.replace('_',' ')}, "
            f"addressed to {aud}."
        )
    else:
        nuclear['reading'] = (
            "Nuclear-test language appears in the corpus but the tripwire is not "
            "breached: this is test PREPARATION reporting, not an executed test. "
            "No provocation class is active this cycle. Preparation is tracked by "
            "the tripwire, where it belongs."
        )
    return nuclear


# ════════════════════════════════════════════════════════════
# VECTOR 3 — LEADERSHIP VISIBILITY (Pyongyangology)
# ════════════════════════════════════════════════════════════

KIM_VISIBILITY = ['kim jong un appeared', 'kim jong un attended', 'kim jong un visited',
                  'kim jong un inspected', 'kim jong un guided', 'kim jong un chaired',
                  'kim jong un speech', '\uae40\uc815\uc740']
KIM_ABSENCE = ['kim jong un absent', 'kim has not appeared', 'kim jong un missing',
               'kim jong un not seen', 'kim skips', 'kim did not attend',
               'kim jong un health', 'no public appearance kim']
KIM_YO_JONG = ['kim yo jong', 'kim yo-jong', '\uae40\uc5ec\uc815']
SUCCESSION = ['kim ju ae', 'kim ju-ae', 'kim jong un daughter', 'north korea heir',
              'succession north korea', 'hyangdo', '\uae40\uc8fc\uc560']
PURGE = ['north korea purge', 'north korea executed', 'north korea execution',
         'official removed north korea', 'demoted north korea', 'disappeared official',
         'ri pyong chol demoted', 'pak jong chon removed', 'reshuffle north korea',
         'choe son hui', 'jo yong won', 'politburo reshuffle']


def _score_leadership(scan_data):
    visible, _ = _check_keywords(scan_data, KIM_VISIBILITY)
    absent, abs_s = _check_keywords(scan_data, KIM_ABSENCE)
    yo_jong, _ = _check_keywords(scan_data, KIM_YO_JONG)
    succession, suc_s = _check_keywords(scan_data, SUCCESSION)
    purge, purge_s = _check_keywords(scan_data, PURGE)

    signals = absent * 3 + purge * 2 + succession + yo_jong
    band = ('high' if signals >= 12 else 'elevated' if signals >= 7
            else 'simmering' if signals >= 3 else 'quiet')

    notes = []
    if absent >= 2:
        notes.append('Kim absence from expected appearances is reported -- in a system '
                     'that stages its leader deliberately, absence is a choice, not an '
                     'accident')
    if yo_jong >= 3 and visible < 2:
        notes.append('Kim Yo Jong is carrying the public voice while Kim is not visible '
                     '-- historically the arrangement used when the principal wants '
                     'deniability, not when he is incapacitated')
    if succession:
        notes.append('Kim Ju Ae succession signaling present')
    if purge >= 2:
        notes.append('Elite reshuffle or purge signals present')

    return {
        'band': band, 'signals': signals,
        'kim_visible': visible, 'kim_absent': absent,
        'yo_jong_voice': yo_jong, 'succession_signals': succession, 'purge_signals': purge,
        'reading': ('; '.join(notes) + '.') if notes else
                   'Leadership presentation within normal parameters this cycle.',
        'samples': (abs_s or purge_s or suc_s)[:2],
    }


# ════════════════════════════════════════════════════════════
# VECTOR 4 — EXPEDITIONARY FOOTPRINT  ⭐
# ════════════════════════════════════════════════════════════
# The DPRK's most under-watched export is LABOR -- and where its workers and
# engineers appear, TUNNELS appear. Hezbollah's network in Lebanon. The Gaza
# tunnels. Now Kursk reconstruction.
#
# The instrument is a CONVERGENCE, not a keyword:
#     DPRK labor presence  x  malign-actor co-location  =  transfer signal
#
# Labor alone is a remittance story (sanctions-relevant, not military). A malign
# actor alone is somebody else's tracker. The two IN THE SAME PLACE is the read,
# and it is the read nobody else publishes.
#
# NOTE FOR THE FUTURE: this logic wants to become expeditionary_footprint.py --
# a generic, registry-driven detector that works for Wagner in the Sahel and
# IRGC advisers in Syria on day one. Built DPRK-shaped here to prove it; port it
# before a second actor needs it, not after.

DPRK_LABOR = [
    'north korean workers', 'dprk workers', 'north korean laborers', 'dprk laborers',
    'north korean engineers', 'dprk engineers', 'north korean overseas workers',
    'north korean construction workers', 'north korean advisers', 'dprk advisers',
    'north korean technicians', 'north korean military advisers',
    '\ubd81\ud55c \ub178\ub3d9\uc790',
]
TUNNEL_WORK = [
    'tunnel construction', 'underground facility', 'tunnel network', 'tunnel expertise',
    'underground bunker', 'fortification construction', 'hardened shelter',
    'tunnel digging', 'subterranean',
]
MALIGN_HOSTS = {
    'hezbollah':  ['hezbollah', 'lebanon tunnel', 'south lebanon'],
    'hamas':      ['hamas', 'gaza tunnel', 'gaza'],
    'russia':     ['kursk', 'russia reconstruction', 'russian territory', 'donbas'],
    'iran':       ['iran', 'irgc', 'tehran'],
    'syria':      ['syria', 'damascus'],
    'africa':     ['africa', 'congo', 'mali', 'sahel', 'uganda', 'namibia'],
}


def _score_expeditionary(scan_data):
    labor, labor_s = _check_keywords(scan_data, DPRK_LABOR)
    tunnels, tun_s = _check_keywords(scan_data, TUNNEL_WORK)

    hosts = []
    for host, kws in MALIGN_HOSTS.items():
        n, _ = _check_keywords(scan_data, kws)
        if n and labor:            # co-location gate: labor MUST be present
            hosts.append({'host': host, 'signals': n})
    hosts.sort(key=lambda h: -h['signals'])

    # The convergence gate. Labor alone is a remittance story. A host alone is
    # someone else's tracker. Labor + host is the transfer signal.
    converged = bool(labor and hosts)
    tunnel_convergence = bool(labor and tunnels and hosts)

    if tunnel_convergence:
        band = 'high'
    elif converged and labor >= 3:
        band = 'elevated'
    elif converged or labor >= 2:
        band = 'simmering'
    else:
        band = 'quiet'

    if tunnel_convergence:
        hn = ', '.join(h['host'] for h in hosts[:3])
        reading = (f'DPRK labor presence, tunnel or underground-construction language, and '
                   f'malign-actor co-location ({hn}) are appearing together on the same '
                   f'corpus. This is the compound pattern that has historically preceded '
                   f'documented transfers of DPRK tunnelling and hardened-facility '
                   f'expertise -- the Hezbollah and Gaza networks are the precedent. '
                   f'Labor alone would be a remittance story; labor plus a host plus '
                   f'underground construction is a capability-transfer story.')
    elif converged:
        hn = ', '.join(h['host'] for h in hosts[:3])
        reading = (f'DPRK labor presence reported alongside malign-actor co-location '
                   f'({hn}), without underground-construction language this cycle. '
                   f'Consistent with a remittance and access footprint; not yet the '
                   f'transfer pattern.')
    elif labor:
        reading = ('DPRK overseas labor signals present with no malign-actor co-location '
                   'on the corpus. Sanctions-relevant; not a transfer read.')
    else:
        reading = 'No DPRK expeditionary labor signals this cycle.'

    return {
        'band': band, 'labor_signals': labor, 'tunnel_signals': tunnels,
        'hosts': [h['host'] for h in hosts], 'host_detail': hosts,
        'converged': converged, 'tunnel_convergence': tunnel_convergence,
        'reading': reading, 'samples': (labor_s or tun_s)[:2],
    }


# ════════════════════════════════════════════════════════════
# VECTOR 5 — BORDER DYADS (two borders, two different questions)
# ════════════════════════════════════════════════════════════

DMZ_SIGNALS = ['dmz', 'demilitarized zone', 'inter-korean', 'mdl crossing',
               'loudspeaker broadcast', 'jsa', 'panmunjom', 'north korean soldiers crossed',
               'warning shots dmz', 'gps jamming south korea', 'trash balloon',
               'south korea north korea border', 'maritime buffer zone', 'nll',
               'northern limit line', '\ube44\ubb34\uc7a5\uc9c0\ub300']
CHINA_BORDER = ['yalu river', 'tumen river', 'north korea china border', 'dandong',
                'sinuiju', 'north korean defector', 'defectors china',
                'north korea china trade', 'border reopening north korea',
                'repatriated defectors', 'cross-border smuggling north korea']


def _score_border_dyads(scan_data):
    dmz, dmz_s = _check_keywords(scan_data, DMZ_SIGNALS)
    china, china_s = _check_keywords(scan_data, CHINA_BORDER)

    total = dmz + china
    band = ('high' if total >= 14 else 'elevated' if total >= 8
            else 'simmering' if total >= 3 else 'quiet')
    dominant = 'dmz' if dmz > china else 'china' if china > dmz else None

    notes = []
    if dmz >= 3:
        notes.append('DMZ / inter-Korean friction active -- the southern border is where '
                     'Pyongyang buys attention cheaply')
    if china >= 3:
        notes.append('Yalu-Tumen activity reported -- the northern border is a dependency '
                     'gauge, not a threat gauge: it measures how much of the regime\'s '
                     'oxygen Beijing controls')

    return {
        'band': band, 'dmz_signals': dmz, 'china_signals': china,
        'dominant': dominant, 'signals': total,
        'reading': ('; '.join(notes) + '.') if notes else
                   'Both borders quiet on the available corpus this cycle.',
        'samples': (dmz_s or china_s)[:2],
    }


# ════════════════════════════════════════════════════════════
# VECTOR 6 — ILLICIT FLOWS (where the commodity story lives)
# ════════════════════════════════════════════════════════════
# The DPRK is NOT on the commodities page, and that was the right call: sanctions
# severed its reserves from any market, so there is no price to track. Magnesite,
# graphite, tungsten, rare earths -- world-class deposits, all stranded. Reserves
# are not flows, and the commodity tracker measures pressure on flows.
#
# But the flows exist. They are just illicit. So they live HERE.

ILLICIT = [
    'coal smuggling north korea', 'north korea coal exports', 'ship-to-ship transfer',
    'sanctions evasion north korea', 'dprk sanctions evasion', 'oil cap north korea',
    'refined petroleum cap', 'sanctioned vessel north korea', 'shadow fleet north korea',
    'north korea illicit', 'panel of experts north korea', 'msmt report',
    'north korea crypto theft', 'lazarus group', 'dprk crypto', 'cyber heist north korea',
    'north korea it workers', 'fraudulent it workers',
    'arms transfer north korea russia', 'munitions north korea russia',
    'shells north korea russia', 'containers north korea russia',
]


def _score_illicit_flows(scan_data):
    n, s = _check_keywords(scan_data, ILLICIT)
    band = ('high' if n >= 10 else 'elevated' if n >= 6
            else 'simmering' if n >= 2 else 'quiet')
    reading = (
        'Illicit-flow reporting is elevated. This is where the DPRK commodity story '
        'actually lives: sanctions severed world-class magnesite, graphite and rare-earth '
        'reserves from any market, so there is no price to track -- only flows, and the '
        'flows are smuggled. Read this as the revenue side of the leverage instrument.'
        if band in ('elevated', 'high') else
        'Illicit-flow reporting at baseline this cycle.'
    )
    return {'band': band, 'signals': n, 'reading': reading, 'samples': s[:2]}


# ════════════════════════════════════════════════════════════
# VECTOR 7 — FOOD SECURITY (a leverage variable, not just a humanitarian one)
# ════════════════════════════════════════════════════════════

FOOD = [
    'north korea famine', 'north korea food shortage', 'north korea food crisis',
    'north korea harvest', 'north korea malnutrition', 'north korea starvation',
    'food aid north korea', 'wfp north korea', 'fao north korea',
    'north korea grain imports', 'rice price north korea', 'market price north korea',
    'north korea hunger', '\uc2dd\ub7c9\ub09c',
]


def _score_food_security(scan_data):
    n, s = _check_keywords(scan_data, FOOD)
    band = ('high' if n >= 8 else 'elevated' if n >= 4
            else 'simmering' if n >= 2 else 'quiet')
    reading = (
        'Food-security stress is reported. On this platform that is not only a '
        'humanitarian sensor -- it is an input to the leverage instrument. A hungrier '
        'DPRK NEEDS its patrons more, which means the same patronage buys more '
        'compliance and its withdrawal costs more. Hunger does not make Pyongyang '
        'safer; it makes it more dependent, and a dependent actor whose patron is '
        'walking away has further to fall.'
        if band in ('elevated', 'high') else
        'Food-security reporting at baseline this cycle.'
    )
    return {'band': band, 'signals': n, 'reading': reading, 'samples': s[:2]}


# ════════════════════════════════════════════════════════════
# TEMPO DEVIATION (mode='actor' — the canonical quiet-before-storm case)
# ════════════════════════════════════════════════════════════

def _read_tempo(tempo_baseline):
    """The DPRK ANNOUNCES. KCNA has a cadence. A claiming actor going quiet is
    the signal -- which is exactly what mode='actor' is for, and why the DPRK is
    the case the tempo engine was designed around.

    Absence-honest, twice over: no baseline -> no call; sick corpus -> no QUIET
    call (we cannot tell KCNA falling silent from our own feeds dying)."""
    if not tempo_baseline or not tempo_baseline.get('ready'):
        return {'ready': False,
                'read': ('Tempo baseline accumulating -- no deviation call until a '
                         'normal exists to deviate from.')}
    dev = tempo_baseline.get('deviation') or {}
    direction = dev.get('direction')
    if tempo_baseline.get('suppress_quiet') and direction == 'quiet':
        return {'ready': True, 'suppressed': True,
                'read': ('Statement tempo is below baseline, but corpus health is '
                         'degraded this cycle -- the quiet call is SUPPRESSED. We '
                         'cannot distinguish Pyongyang going quiet from our own '
                         'sources going dark, and inventing menace out of our own '
                         'outage is the failure this guard exists to prevent.')}
    if direction == 'quiet':
        return {'ready': True, 'direction': 'quiet', 'z': dev.get('z'),
                'read': ('KCNA statement tempo has fallen materially below its 30-day '
                         'baseline while the corpus remains healthy. For a CLAIMING '
                         'actor, silence is not absence of signal -- it is signal. '
                         'This is the pattern the quiet-before-storm literature '
                         'describes; it is not a prediction that anything follows.')}
    if direction == 'surge':
        return {'ready': True, 'direction': 'surge', 'z': dev.get('z'),
                'read': ('KCNA statement tempo is running materially above its 30-day '
                         'baseline. Elevated declaratory output.')}
    return {'ready': True, 'direction': 'normal',
            'read': 'Statement tempo within normal bounds against the 30-day baseline.'}


# ════════════════════════════════════════════════════════════
# SO WHAT
# ════════════════════════════════════════════════════════════

def _build_so_what(lev, nuclear, tripwire, leadership, exped, borders,
                   illicit, food, tempo, repricing=None):
    state = lev['state']
    scenario_map = {
        'intact':    'Leverage Intact -- Pyongyang Courted',
        'eroding':   'Leverage Eroding -- Direction of Travel Is the Read',
        'decaying':  'Leverage Decaying -- The Relevance-Signal Band',
        'collapsed': 'Leverage Collapsed -- Negotiated Around',
    }
    scenario = scenario_map[state]

    situation = [lev['reading']]
    if nuclear['dominant_class']:
        situation.append(nuclear['reading'])
    if leadership['band'] != 'quiet':
        situation.append(leadership['reading'])
    if exped['band'] in ('elevated', 'high'):
        situation.append(exped['reading'])

    # THE COMPOUND READ. This is the sentence the whole tracker exists to produce.
    assessment = []
    if state in ('decaying', 'collapsed') and nuclear['dominant_class']:
        aud = PROVOCATION_CLASSES[nuclear['dominant_class']]['audience']
        assessment.append(
            f"Decaying leverage and active {nuclear['dominant_class'].replace('_',' ')} "
            f"signaling are stacking on the same window. Read together, this is "
            f"consistent with a BID FOR RELEVANCE addressed to {aud} -- an actor "
            f"forcing its way back onto an agenda it has been left off -- rather than "
            f"with preparation for advantage. The provocation follows the sidelining; "
            f"historically it has not preceded it."
        )
    elif state in ('decaying', 'collapsed'):
        assessment.append(
            "Leverage is decaying without a provocation class yet active. On the "
            "historical pattern this is the band in which relevance signals have "
            "originated -- the quiet stretch before the demonstration, not after it. "
            "The absence of a provocation today is not evidence of its absence next "
            "cycle; it is the condition under which one has typically been generated."
        )
    elif state == 'eroding' and nuclear['dominant_class']:
        # The ambiguous band. A provocation is active and the leverage is neither
        # secure nor spent, so the strong precedent claim is NOT available -- but
        # saying nothing here would be a worse error than saying it carefully.
        # Estimative discipline: name the pattern, flag the ambiguity, hand the
        # inference to the reader rather than manufacturing confidence we lack.
        aud = PROVOCATION_CLASSES[nuclear['dominant_class']]['audience']
        assessment.append(
            f"Eroding leverage and active "
            f"{nuclear['dominant_class'].replace('_',' ')} signaling are co-occurring, "
            f"with the message addressed to {aud}. In this band the DIRECTION of travel "
            f"carries the read, not the level: if the sidelining tells deepen, this "
            f"pattern is consistent with the opening of a relevance-signal sequence; if "
            f"patron attention recovers, it reads instead as routine declaratory "
            f"posture. The signals do not yet discriminate between those two, and this "
            f"assessment does not pretend otherwise."
        )
    elif state == 'intact' and nuclear['band'] in ('elevated', 'high'):
        assessment.append(
            "Provocation signaling is active while leverage reads intact. This "
            "combination sits AGAINST the historical pattern and deserves scrutiny: "
            "either the courtship is thinner than the attention signals suggest, or "
            "this provocation is serving an audience other than the patron."
        )
    if tripwire['state'] in ('APPROACHING', 'BREACHED'):
        assessment.append(tripwire['reading'])
    if exped['tunnel_convergence']:
        assessment.append(exped['reading'])
    if tempo.get('direction') == 'quiet':
        assessment.append(tempo['read'])
    if repricing and repricing.get('state') == 'numb':
        assessment.append(
            "The market layer corroborates from the opposite end: a provocation "
            "registered and Seoul's tape did not move. A provocation that buys no "
            "attention bought no leverage -- the rhetoric and the tape are reading the "
            "same variable and agreeing."
        )
    if not assessment:
        assessment.append(
            "No compound convergence this cycle. Vectors are not stacking on the same "
            "window; the individual readings stand on their own."
        )

    watch = []
    if state in ('eroding', 'decaying'):
        watch.append('whether patron-attention signals recover or the sidelining tells deepen')
    if tripwire['state'] != 'QUIET':
        watch.append('Punggye-ri test-site preparation')
    if exped['converged']:
        watch.append('underground-construction language co-occurring with the DPRK labor footprint')
    if not watch:
        watch.append('KCNA statement tempo against baseline; patron-attention signals')

    return {
        'scenario': scenario,
        'situation': ' '.join(situation),
        'assessment': ' '.join(assessment),
        'watch': 'Watch: ' + '; '.join(watch) + '.',
        'disclaimer': DISCLAIMER,
    }


# ════════════════════════════════════════════════════════════
# TOP SIGNALS (canonical schema)
# ════════════════════════════════════════════════════════════

def _build_top_signals(lev, nuclear, tripwire, leadership, exped, borders,
                       illicit, food, tempo):
    sigs = []

    if tripwire['black_swan']:
        sigs.append({'priority': 1, 'category': 'nuclear_tripwire',
                     'short_text': 'BLACK SWAN: seventh nuclear test signals detected',
                     'long_text': tripwire['reading']})
    elif tripwire['state'] == 'APPROACHING':
        sigs.append({'priority': 1, 'category': 'nuclear_tripwire',
                     'short_text': 'Nuclear tripwire APPROACHING -- test-prep signals converging',
                     'long_text': tripwire['reading']})

    if lev['state'] in ('decaying', 'collapsed'):
        sigs.append({'priority': 1, 'category': 'leverage_integrity',
                     'short_text': f"Leverage {lev['state'].upper()} ({lev['integrity']}/100) "
                                   f"-- the relevance-signal band",
                     'long_text': lev['reading']})
    else:
        sigs.append({'priority': 3, 'category': 'leverage_integrity',
                     'short_text': f"Leverage {lev['state']} ({lev['integrity']}/100)",
                     'long_text': lev['reading']})

    if nuclear['dominant_class']:
        aud = PROVOCATION_CLASSES[nuclear['dominant_class']]['audience']
        sigs.append({'priority': 1 if nuclear['band'] == 'high' else 2,
                     'category': 'nuclear_signaling',
                     'short_text': f"{nuclear['dominant_class'].replace('_',' ').title()} "
                                   f"signaling -- addressed to {aud}",
                     'long_text': nuclear['reading']})

    if exped['tunnel_convergence']:
        sigs.append({'priority': 1, 'category': 'expeditionary_footprint',
                     'short_text': f"Expeditionary CONVERGENCE: DPRK labor + tunnels + "
                                   f"{', '.join(exped['hosts'][:2])}",
                     'long_text': exped['reading']})
    elif exped['converged']:
        sigs.append({'priority': 2, 'category': 'expeditionary_footprint',
                     'short_text': f"DPRK labor footprint co-located with "
                                   f"{', '.join(exped['hosts'][:2])}",
                     'long_text': exped['reading']})

    if tempo.get('direction') == 'quiet':
        sigs.append({'priority': 1, 'category': 'tempo_deviation',
                     'short_text': 'KCNA tempo materially below baseline -- silence from a '
                                   'claiming actor',
                     'long_text': tempo['read']})

    if leadership['band'] in ('elevated', 'high'):
        sigs.append({'priority': 2, 'category': 'leadership',
                     'short_text': f"Leadership signals {leadership['band']}"
                                   + (' -- purge/reshuffle' if leadership['purge_signals'] >= 2 else '')
                                   + (' -- Kim absent' if leadership['kim_absent'] >= 2 else ''),
                     'long_text': leadership['reading']})

    for v, cat, label in [(borders, 'border_dyads', 'Border activity'),
                          (illicit, 'illicit_flows', 'Illicit-flow reporting'),
                          (food, 'food_security', 'Food-security stress')]:
        if v['band'] in ('elevated', 'high'):
            sigs.append({'priority': 3, 'category': cat,
                         'short_text': f"{label} {v['band']}",
                         'long_text': v['reading']})

    sigs.sort(key=lambda s: s['priority'])
    return sigs[:8]


# ════════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════════

def interpret_signals(scan_data):
    food     = _score_food_security(scan_data)
    lev      = _score_leverage_integrity(scan_data, food=food,
                                         tempo_baseline=scan_data.get('tempo_baseline'))
    nuclear  = _score_nuclear_signaling(scan_data)
    tripwire = _score_nuclear_tripwire(scan_data, nuclear)
    # PREPARATION IS NOT EXECUTION. Must run AFTER the tripwire, because the
    # tripwire is what tells us whether a test actually happened.
    nuclear  = _gate_provocation_on_tripwire(nuclear, tripwire)
    leader   = _score_leadership(scan_data)
    exped    = _score_expeditionary(scan_data)
    borders  = _score_border_dyads(scan_data)
    illicit  = _score_illicit_flows(scan_data)
    tempo    = _read_tempo(scan_data.get('tempo_baseline'))
    repricing = scan_data.get('repricing_snapshot')

    so_what = _build_so_what(lev, nuclear, tripwire, leader, exped, borders,
                             illicit, food, tempo, repricing)
    top_signals = _build_top_signals(lev, nuclear, tripwire, leader, exped, borders,
                                     illicit, food, tempo)

    # THE INVERSION, made concrete. Pressure is the INVERSE of leverage: as the
    # leverage decays, the escalation pressure rises. If this ever reads the
    # other way round, the instrument has been broken.
    composite = 100 - lev['integrity']
    if tripwire['black_swan']:
        composite = 100
    elif tripwire['state'] == 'APPROACHING':
        composite = min(100, composite + 15)

    return {
        'interpreter_version': INTERPRETER_VERSION,

        # ── The instrument ──
        'leverage_integrity': lev,

        # ── Vectors ──
        'nuclear_signaling':       nuclear,
        'nuclear_tripwire':        tripwire,
        'leadership':              leader,
        'expeditionary_footprint': exped,
        'border_dyads':            borders,
        'illicit_flows':           illicit,
        'food_security':           food,
        'tempo_deviation':         tempo,

        # ── CONTRACT with conflict_repricing_detector.py (theatre 'korea') ──
        # These three fields are read by the habituation detector to ask whether
        # Seoul's tape still flinches. Renaming them breaks the Market Watch card.
        'provocation_active': nuclear['provocation_active'],
        'provocation_class':  nuclear['dominant_class'],

        'composite_modifier': composite,
        'so_what':     so_what,
        'top_signals': top_signals,
        'disclaimer':  DISCLAIMER,
    }
