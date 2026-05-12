"""
Asifah Analytics — India Rhetoric & Coercion Tracker
v1.0.0 — May 2026

ANALYTICAL FRAME (this is the question this tracker answers):
==============================================================

  "Is India absorbing external pressure (economic, kinetic, diplomatic)
   without losing internal cohesion — and how is that absorption shaping
   its external posture?"

India is the platform's FIRST absorber-class tracker. This is a structural
departure from China (command-node, asks "will China take Taiwan?") and Iran
(command-node, asks "is Iran moving kinetic?"). India is downstream of the
command nodes — it ABSORBS pressure rather than originating it. The tracker
is built around this asymmetry.

THE THREE-DASHBOARD MODEL:
==========================

  OUTBOUND — "India's external posture signaling"
    Tracks: PMO/Modi rhetoric, MEA/Jaishankar foreign policy positioning,
            Armed Forces LAC/LoC/naval signaling, Economic Statecraft
            (RBI, MoF) outbound monetary diplomacy, Hindutva non-state
            ideological projection.

  INBOUND — "Pressure absorption signals from upstream theaters"
    Tracks: Pakistan LoC/Kashmir escalations, China LAC pressure, China
            tech/economic coercion, Iran/Hormuz oil pricing reverberations,
            US tariff/H-1B/Khalistan friction. Read from cross-theater
            fingerprints written by Iran, China, Pakistan, US trackers.

  INTERNAL — "Cohesion under absorption"
    Tracks: Opposition (INDIA bloc — Rahul Gandhi, Kharge, Mamata, Stalin)
            rhetorical posture (attacking vs aligned with government),
            communal/minority-stress signals, Hindutva ideological actor
            volatility (RSS, VHP, Bajrang Dal), regional federal friction.
            This is India's UNIQUE structural addition — China's CCP is
            rhetorically monolithic; India's chaotic democracy is its
            absorption-resilience analytical strength.

SEVEN ACTOR CLUSTERS:
=====================
  1. PMO                    — Modi, BJP HQ, BJP rallies, PMO India social
  2. MEA                    — Jaishankar, MEA spokesperson, ambassadors
  3. ARMED_FORCES           — CDS, service chiefs, Northern/Eastern Cmds
  4. ECONOMIC_STATECRAFT    — Sitharaman, RBI Gov, Goyal (Commerce), Puri
  5. OPPOSITION             — Rahul Gandhi, Kharge, INDIA bloc (Mamata, Stalin)
  6. HINDUTVA_IDEOLOGICAL   — RSS Bhagwat, VHP, Bajrang Dal, saffron voices
  7. ADVERSARY_CROSSREADS   — Pakistan official voices, China MFA/PLA on India,
                              Khalistan actors abroad (Canada/US/UK)

SCORING WEIGHTS:
================
  PMO                       weight 3.5  — top political signaling
  MEA                       weight 3.0  — strategic-autonomy doctrine voice
  Armed Forces              weight 2.5  — LAC/LoC/naval signaling
  Economic Statecraft       weight 2.0  — bridges to commodity layer
  Adversary Cross-reads     weight 2.0  — bidirectional inbound pressure
  Opposition                weight 1.5  — cohesion proxy
  Hindutva Ideological      weight 1.5  — non-state ideological vector

CROSS-THEATER ARCHITECTURE:
===========================
The platform has TWO key-naming conventions live in production. India must
play nicely with both:

  Convention A — shared dict at 'rhetoric:crosstheater:fingerprints' with
                 sub-keys per country.   Used by: Iran, China.
                 India will write to existing['india'] inside this dict.

  Convention B — per-country keys.       Used by: Pakistan, US.
                 India will also write to 'fingerprint:india:current'.

This dual-write means Iran/China readers (which look in the shared dict)
AND US/Pakistan readers (which look at per-country keys) both see India.

INDIA READS UPSTREAM FROM:
  iran     — shared dict, key 'iran'. Watches:
             theatre_score, irgc_level, iran_hormuz_pressure, named_targets,
             iran_gold_for_oil_active, iran_dedollarization_active,
             iran_brics_alignment_active, iran_opec_realignment_active
  china    — shared dict, key 'china'. Watches:
             level, outbound_score, xi_level, pla_level, econ_level,
             china_iran_axis_level, china_yuan_internationalization_active,
             china_brics_architect_active, china_sanctions_facilitator_active
  pakistan — per-country key 'crosstheater:pakistan:fingerprint'. Watches:
             theatre_level, theatre_score, kashmir_loc_level,
             nuclear_doctrine_level, pakistan_india_active,
             pakistan_nuclear_signaling, civil_military_friction_level,
             economic_stress_level
  us       — per-country key 'fingerprint:us:current'. Watches:
             us_active, us_composite_score, us_executive_score,
             us_executive_volatility, us_outbound_targets (looks for 'india'),
             us_dhs_enforcement_active, us_judicial_pushback_score

INDIA WRITES (its own fingerprint):
  to BOTH 'rhetoric:crosstheater:fingerprints'['india']
       AND 'fingerprint:india:current'

  Payload includes:
    is_command_node: False        # India is absorber, not commander
    is_absorber_node: True        # NEW — India is first absorber-class
    theatre_score, overall_level
    outbound_level, inbound_level, internal_level    (3-dashboard maxes)
    pmo_level, mea_level, armed_forces_level, ...    (per-actor levels)
    india_pakistan_active, india_china_lac_active,
    india_china_tech_friction_active, india_us_friction_active,
    india_russia_active                              (bidirectional flags)
    absorption_active, absorption_count,
    upstream_stressors, cohesion_stress_level        (Butterfly Build)
    modi_jawboning_active, rbi_fx_defense_active,
    communal_stress_active, opposition_alignment     (named signals)

ABSORPTION INTEGRATION (Butterfly Build Phase 2):
==================================================
This tracker is the platform's first dynamic consumer of absorption_detector.
After the main scan completes, it calls:

    from absorption_detector import detect_and_persist
    detect_and_persist(
        country='india',
        upstream_fingerprints={'iran':..., 'china':..., 'pakistan':..., 'us':...},
        own_signals={'modi_gold_jawboning':..., 'rbi_fx_defense':..., ...},
    )

The detector decides which absorption signatures fire, computes confidence,
and (when persisted) writes them to Redis via absorption_signatures.
The frontend Web Component <leader-signals-card detail="full"> then renders
the so_what_long analysis attached to each fired signature.

SOURCE STRATEGY:
================
  Primary RSS:  The Hindu, Hindustan Times, Indian Express, Mint,
                Business Standard, NDTV, Times of India, The Wire,
                Reuters India, The Print, Scroll, Indian Defence Review,
                The Diplomat (India coverage)
  Secondary:    GDELT (eng, hin, urd), Google News RSS (EN + HI + UR)
  Reddit:       r/india, r/IndianModerate, r/IndianEconomy, r/IndianDefense,
                r/Kashmir, r/pakistan, r/IndiaSpeaks, r/librandu,
                r/geopolitics, r/CredibleDefense
  Bluesky:      PMO India, MEA India, Jaishankar, Rahul Gandhi (TBD scouting)
  Telegram:     Routed through telegram_signals_asia shared cache

REDIS KEYS:
  Cache:                rhetoric:india:latest
  Legacy alias:         india_rhetoric_cache
  History:              rhetoric:india:history
  Baseline:             rhetoric_baseline:india
  Cross-theater (A):    rhetoric:crosstheater:fingerprints (WRITE sub-key 'india')
  Cross-theater (B):    fingerprint:india:current (WRITE direct)

ENDPOINTS:
  GET /api/rhetoric/india
  GET /api/rhetoric/india/summary
  GET /api/rhetoric/india/history
  GET /api/rhetoric/india/absorption    (NEW — exposes fired signatures)

CHANGELOG:
  v1.0.0 (2026-05-12): Initial build — three-dashboard absorber-node tracker.
                       Cross-theater reads from Iran/China/Pakistan/US.
                       First platform consumer of absorption_detector.

COPYRIGHT 2025-2026 Asifah Analytics. All rights reserved.
"""

import os
import json
import threading
import time
import requests
import xml.etree.ElementTree as ET
import urllib.parse
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from flask import jsonify, request


# ============================================================================
# CONFIG
# ============================================================================
UPSTASH_REDIS_URL   = os.environ.get('UPSTASH_REDIS_URL') or os.environ.get('UPSTASH_REDIS_REST_URL')
UPSTASH_REDIS_TOKEN = os.environ.get('UPSTASH_REDIS_TOKEN') or os.environ.get('UPSTASH_REDIS_REST_TOKEN')
NEWSAPI_KEY         = os.environ.get('NEWSAPI_KEY')
BRAVE_API_KEY       = os.environ.get('BRAVE_API_KEY')
GDELT_BASE_URL      = 'https://api.gdeltproject.org/api/v2/doc/doc'

# Optional Telegram bridge
try:
    from telegram_signals_asia import fetch_asia_telegram_signals
    TELEGRAM_AVAILABLE = True
    print("[India Rhetoric] Telegram signals available")
except ImportError:
    TELEGRAM_AVAILABLE = False
    print("[India Rhetoric] Telegram signals not available — RSS/GDELT only")

# Optional absorption detector + storage (Butterfly Build Phase 2)
try:
    from absorption_detector import detect_and_persist as detect_absorption_and_persist
    ABSORPTION_DETECTOR_AVAILABLE = True
    print("[India Rhetoric] ✅ Absorption detector available")
except ImportError:
    ABSORPTION_DETECTOR_AVAILABLE = False
    print("[India Rhetoric] ⚠️ Absorption detector not importable — skipping Butterfly write")

# Redis keys
RHETORIC_CACHE_KEY        = 'rhetoric:india:latest'
RHETORIC_CACHE_KEY_LEGACY = 'india_rhetoric_cache'
HISTORY_KEY               = 'rhetoric:india:history'
BASELINE_KEY              = 'rhetoric_baseline:india'

# Cross-theater key conventions — India writes to BOTH for max compatibility
CROSSTHEATER_SHARED_KEY   = 'rhetoric:crosstheater:fingerprints'    # Convention A (Iran/China read)
CROSSTHEATER_INDIA_KEY    = 'fingerprint:india:current'             # Convention B (US/Pakistan readers)

# Cross-theater key conventions — India READS from each upstream's home key
UPSTREAM_KEYS = {
    'iran':     ('shared',   'iran'),                          # shared dict, sub-key
    'china':    ('shared',   'china'),                         # shared dict, sub-key
    'pakistan': ('direct',   'crosstheater:pakistan:fingerprint'),   # per-country key
    'us':       ('direct',   'fingerprint:us:current'),        # per-country key
}

RHETORIC_CACHE_TTL  = 6 * 3600
SCAN_INTERVAL_HOURS = 6
HISTORY_MAX_ENTRIES = 336   # 84 days at 6h cadence

_rhetoric_running = False
_rhetoric_lock    = threading.Lock()


# ============================================================================
# ESCALATION LEVELS  (canonical 0–5 scale used across the platform)
# ============================================================================
ESCALATION_LEVELS = {
    0: {'label': 'Baseline',         'color': '#6b7280',
        'description': 'Routine statements, no significant absorption signals'},
    1: {'label': 'Rhetoric',         'color': '#3b82f6',
        'description': 'Standard policy positioning, formulaic warnings, baseline cohesion'},
    2: {'label': 'Warning',          'color': '#f59e0b',
        'description': 'Elevated rhetoric on Pakistan/China/Khalistan; minor absorption flagged'},
    3: {'label': 'Confrontation',    'color': '#f97316',
        'description': 'Named adversary signaling, active absorption (Modi-class jawboning), opposition attacks rising'},
    4: {'label': 'Coercion',         'color': '#ef4444',
        'description': 'Multiple-axis absorption converging, communal/cohesion stress, deferred policy moves probable'},
    5: {'label': 'Active Crisis',    'color': '#dc2626',
        'description': 'Kinetic or BoP-class events: LoC/LAC clash, formal duty/control measures, communal violence at scale'},
}


# ============================================================================
# THREE DASHBOARDS — actor membership map
# ============================================================================
# Each actor declares which dashboard(s) it participates in. An actor can
# belong to multiple dashboards (e.g., Armed Forces contribute to OUTBOUND
# signaling AND to INBOUND when Pakistan/China are firing back).
DASHBOARDS = ('outbound', 'inbound', 'internal')


# ============================================================================
# ACTORS  (7 clusters — Tier 1 + Tier 2 + Tier 3 from build memo)
# ============================================================================
ACTORS = {

    # ──────────────────────────────────────────────────────────────────────
    # 1. PMO  (OUTBOUND + INTERNAL)
    #    Modi, BJP HQ, PMO India social, BJP rallies.
    # ──────────────────────────────────────────────────────────────────────
    'pmo': {
        'name': 'PMO / Modi / BJP Leadership',
        'flag': '🇮🇳',
        'icon': '🏛️',
        'color': '#f97316',
        'dashboards': ['outbound', 'internal'],
        'weight': 3.5,
        'role': 'Apex Political Signaling',
        'description': (
            'Modi himself + BJP party machinery + PMO India official voice. '
            'Highest-value rhetoric in the tracker. Modi-class jawboning '
            '(e.g., May 2026 gold call) writes directly into absorption layer.'
        ),
        'keywords': [
            # Modi-direct
            'narendra modi', 'pm modi', 'prime minister modi', 'modi ji',
            'modi says', 'modi warns', 'modi addresses', 'modi tells',
            'modi calls on', 'modi urges', 'modi appeals',
            'mann ki baat', 'modi mann ki baat', 'pmo india',
            'modi rally', 'modi speech', 'modi independence day',
            'modi red fort', 'modi parliament',
            # Modi jawboning markers (commodity / discretionary import)
            'avoid buying gold', 'suspend gold purchases', 'cut gold imports',
            'foreign travel', 'discretionary imports', 'aatmanirbhar',
            'self-reliance', 'self reliance', 'vocal for local', 'make in india',
            # BJP party
            'bjp president', 'bjp leader', 'bharatiya janata party',
            'amit shah', 'jp nadda', 'home minister shah',
            'bjp rally', 'bjp manifesto',
            # Hindi
            'मोदी', 'प्रधानमंत्री', 'भाजपा', 'मन की बात',
            # Urdu
            'مودی', 'وزیر اعظم', 'بھارتیہ جنتا پارٹی',
        ],
        'baseline_statements_per_week': 12,
        'tripwires': [
            'modi addresses nation emergency',
            'modi announces formal duty hike on gold',
            'modi suspends foreign visits',
        ],
    },

    # ──────────────────────────────────────────────────────────────────────
    # 2. MEA  (OUTBOUND)
    #    External Affairs — Jaishankar, MEA spokesperson, key ambassadors.
    # ──────────────────────────────────────────────────────────────────────
    'mea': {
        'name': 'MEA / Jaishankar / Ambassadors',
        'flag': '🇮🇳',
        'icon': '🌐',
        'color': '#0ea5e9',
        'dashboards': ['outbound'],
        'weight': 3.0,
        'role': 'Foreign Policy Doctrine Voice',
        'description': (
            'External Affairs Ministry rhetoric architect. Jaishankar is the '
            'public voice of "strategic autonomy" doctrine. MEA spokesperson '
            'briefings and senior ambassador statements (Washington, Beijing, '
            'Islamabad, Tehran, Moscow) round out the cluster.'
        ),
        'keywords': [
            's jaishankar', 'jaishankar', 'eam jaishankar',
            'external affairs minister', 'minister of external affairs',
            'mea spokesperson', 'arindam bagchi', 'randhir jaiswal',
            'ministry of external affairs', 'south block',
            # Doctrine markers
            'strategic autonomy', 'multipolar', 'multi-alignment',
            'civilisational state', 'civilizational state',
            'global south', 'voice of global south',
            'india first', 'national interest', 'realpolitik',
            # Key counterpart relationships
            'india china talks', 'india pakistan talks', 'india us talks',
            'india russia', 'india iran', 'india israel',
            'sushma swaraj bhavan', 'raisina dialogue',
            # Hindi
            'विदेश मंत्री', 'जयशंकर', 'विदेश मंत्रालय',
            # Urdu
            'وزیر خارجہ', 'جے شنکر', 'وزارت خارجہ',
        ],
        'baseline_statements_per_week': 8,
        'tripwires': [
            'india recalls ambassador',
            'mea summons envoy',
            'india suspends bilateral mechanism',
        ],
    },

    # ──────────────────────────────────────────────────────────────────────
    # 3. ARMED FORCES  (OUTBOUND + INBOUND)
    #    CDS, three service chiefs, Northern/Eastern Army Commands, Navy.
    # ──────────────────────────────────────────────────────────────────────
    'armed_forces': {
        'name': 'Armed Forces / CDS / Service Chiefs',
        'flag': '🇮🇳',
        'icon': '🎖️',
        'color': '#a855f7',
        'dashboards': ['outbound', 'inbound'],
        'weight': 2.5,
        'role': 'Military Posture & Operational Signaling',
        'description': (
            'CDS Anil Chauhan, three service chiefs, Northern Command '
            '(Kashmir/LoC + Ladakh/LAC), Eastern Command (Arunachal), Naval '
            'Western/Eastern fleets, Andaman & Nicobar Command. LAC and LoC '
            'tactical statements are the primary signal class.'
        ),
        'keywords': [
            'chief of defence staff', 'cds anil chauhan', 'cds chauhan',
            'army chief', 'navy chief', 'air chief marshal',
            'general manoj pande', 'admiral hari kumar', 'chief of naval staff',
            'air chief marshal', 'iaf chief',
            'northern command', 'eastern command', 'western command',
            'southern command', 'training command',
            'andaman nicobar command', 'tri-services command',
            'eastern naval command', 'western naval command',
            'ins vikrant', 'ins vikramaditya',
            # Operational language
            'lac', 'line of actual control', 'galwan', 'depsang', 'demchok',
            'tawang', 'arunachal', 'ladakh', 'siachen',
            'loc', 'line of control', 'uri', 'pathankot', 'pulwama',
            'cross-border', 'surgical strike', 'pre-emptive',
            'forward posture', 'mobilization', 'mobilisation',
            'integrated theatre command', 'jointness',
            'rafale', 's-400', 'tejas', 'brahmos',
            # Hindi
            'सेनाध्यक्ष', 'थलसेना', 'वायुसेना', 'नौसेना', 'नियंत्रण रेखा',
            # Urdu
            'فوج کے سربراہ', 'لائن آف کنٹرول', 'فوجی',
        ],
        'baseline_statements_per_week': 6,
        'tripwires': [
            'lac forward troop movement',
            'loc ceasefire violation cluster',
            'army moves troops to forward positions',
            'naval task force deployed',
        ],
    },

    # ──────────────────────────────────────────────────────────────────────
    # 4. ECONOMIC STATECRAFT  (OUTBOUND + INBOUND)
    #    Sitharaman, RBI Governor, Goyal (Commerce), Puri (Petroleum).
    # ──────────────────────────────────────────────────────────────────────
    'economic_statecraft': {
        'name': 'MoF / RBI / Commerce / Petroleum',
        'flag': '🇮🇳',
        'icon': '🪙',
        'color': '#eab308',
        'dashboards': ['outbound', 'inbound'],
        'weight': 2.0,
        'role': 'Monetary & Trade Statecraft',
        'description': (
            'Finance Minister Sitharaman, RBI Governor, Commerce Minister '
            'Goyal, Petroleum Minister Puri. This cluster bridges to the '
            'commodity tracker — every signal here is a candidate input to '
            'absorption_detector. RBI gold accumulation, rupee internationalization, '
            'oil-import diversification rhetoric, BRICS payments, all live here.'
        ),
        'keywords': [
            # Sitharaman
            'nirmala sitharaman', 'finance minister sitharaman',
            'sitharaman budget', 'sitharaman parliament', 'finance ministry',
            # RBI
            'shaktikanta das', 'rbi governor', 'reserve bank of india',
            'rbi monetary policy', 'mpc', 'monetary policy committee',
            'rbi intervention', 'rbi gold reserves',
            # Commerce / Petroleum
            'piyush goyal', 'commerce minister goyal',
            'hardeep puri', 'petroleum minister puri', 'oil minister puri',
            # Statecraft markers
            'forex reserves', 'foreign exchange reserves', 'fx reserves',
            'rupee internationalization', 'rupee trade', 'rupee invoicing',
            'oil import diversification', 'energy security',
            'brics payments', 'brics pay', 'mbridge',
            'import duty', 'tariff', 'export duty', 'safeguard duty',
            'self-reliance', 'aatmanirbhar bharat', 'production linked incentive',
            'pli scheme', 'make in india',
            # Hindi
            'सीतारमण', 'वित्त मंत्री', 'भारतीय रिजर्व बैंक', 'विदेशी मुद्रा भंडार',
            # Urdu
            'سیتارمن', 'وزیر خزانہ', 'ریزرو بینک', 'زر مبادلہ',
        ],
        'baseline_statements_per_week': 7,
        'tripwires': [
            'rbi raises rates emergency',
            'gold import duty hike announced',
            'forex reserves drop below 580 billion',
            'capital controls signaled',
        ],
    },

    # ──────────────────────────────────────────────────────────────────────
    # 5. OPPOSITION  (INTERNAL)
    #    Rahul Gandhi, Kharge, INDIA bloc (Mamata, Stalin, others).
    # ──────────────────────────────────────────────────────────────────────
    # NOTE on scoring inversion: higher OPPOSITION activity = LOWER cohesion.
    # When opposition is aligned with government (post-terror-attack, on China
    # at LAC) → low opposition_attack_score = high cohesion signal.
    # When opposition is attacking on FX/unemployment/Manipur/communal →
    # high opposition_attack_score = cohesion stress signal.
    'opposition': {
        'name': 'Congress / INDIA Bloc Opposition',
        'flag': '🇮🇳',
        'icon': '⚖️',
        'color': '#3b82f6',
        'dashboards': ['internal'],
        'weight': 1.5,
        'role': 'Internal Cohesion Proxy (inverse-scored)',
        'description': (
            'Rahul Gandhi (Congress), Mallikarjun Kharge (Congress President), '
            'Mamata Banerjee (TMC/Bengal), MK Stalin (DMK/Tamil Nadu), '
            'Akhilesh Yadav (SP/UP), Tejashwi Yadav (RJD/Bihar). When this '
            'cluster goes loud on FX/unemployment/communal/Manipur → cohesion '
            'stress. When it goes quiet or aligns post-attack → cohesion strong.'
        ),
        'keywords': [
            # Congress / INDIA bloc top voices
            'rahul gandhi', 'mallikarjun kharge', 'congress president kharge',
            'sonia gandhi', 'priyanka gandhi', 'inc president',
            'indian national congress', 'congress party',
            'india bloc', 'i.n.d.i.a alliance', 'opposition alliance',
            # Regional chief ministers (opposition / non-BJP)
            'mamata banerjee', 'trinamool congress', 'tmc bengal',
            'mk stalin', 'dmk tamil nadu', 'dmk chief',
            'akhilesh yadav', 'samajwadi party', 'sp uttar pradesh',
            'tejashwi yadav', 'rjd bihar',
            'revanth reddy', 'congress telangana',
            'aap kejriwal', 'arvind kejriwal',
            # Opposition rhetoric markers
            'modi government failure', 'bjp failure',
            'unemployment crisis', 'economic mismanagement',
            'attack on democracy', 'institutional capture',
            'manipur', 'manipur violence', 'gyanvapi', 'love jihad',
            'inflation modi', 'rupee fall',
            'electoral bonds', 'pegasus',
            # Hindi
            'राहुल गांधी', 'कांग्रेस', 'विपक्ष', 'ममता बनर्जी',
            # Urdu
            'راہول گاندھی', 'کانگریس', 'حزب اختلاف',
        ],
        'baseline_statements_per_week': 10,
        'tripwires': [
            'no-confidence motion filed',
            'opposition walkout sustained',
            'opposition unified statement on emergency',
        ],
    },

    # ──────────────────────────────────────────────────────────────────────
    # 6. HINDUTVA IDEOLOGICAL  (INTERNAL)
    #    RSS, VHP, Bajrang Dal, prominent saffron voices.
    # ──────────────────────────────────────────────────────────────────────
    'hindutva_ideological': {
        'name': 'RSS / VHP / Saffron Voices',
        'flag': '🇮🇳',
        'icon': '🕉️',
        'color': '#dc2626',
        'dashboards': ['internal'],
        'weight': 1.5,
        'role': 'Non-state Ideological Vector',
        'description': (
            'RSS (Mohan Bhagwat), VHP, Bajrang Dal, prominent saffron voices '
            '(Yogi Adityanath when speaking in ideological-rather-than-CM '
            'mode, godmen with mass followings). Tracks Hindutva projection, '
            'minority-stress rhetoric, communal flashpoint signaling. When '
            'this cluster goes loud, government has to choose alignment or '
            'disavowal — both are signal.'
        ),
        'keywords': [
            # RSS
            'mohan bhagwat', 'rss chief', 'rashtriya swayamsevak sangh',
            'sarsanghchalak', 'rss vijayadashami',
            'sangh parivar', 'pracharak',
            # VHP / Bajrang Dal
            'vishwa hindu parishad', 'vhp', 'bajrang dal',
            'hindu jagran manch',
            # Yogi (when speaking ideologically)
            'yogi adityanath', 'cm yogi', 'up chief minister',
            'ajay singh bisht',
            # Hindutva markers
            'hindutva', 'hindu rashtra', 'sanatan dharma',
            'love jihad', 'land jihad', 'urban naxal',
            'gyanvapi', 'kashi vishwanath', 'mathura',
            'ayodhya', 'ram mandir', 'pran pratishtha',
            'cow vigilante', 'gau rakshak',
            'ghar wapsi', 'religious conversion',
            'uniform civil code', 'ucc',
            # Hindi
            'मोहन भागवत', 'राष्ट्रीय स्वयंसेवक संघ', 'हिंदुत्व',
            'विश्व हिंदू परिषद', 'बजरंग दल',
            # Urdu
            'موہن بھاگوت', 'آر ایس ایس', 'ہندوتوا',
        ],
        'baseline_statements_per_week': 8,
        'tripwires': [
            'rss chief major doctrinal speech',
            'temple/mosque flashpoint violence',
            'mass communal incident',
            'bhagwat names specific country/group',
        ],
    },

    # ──────────────────────────────────────────────────────────────────────
    # 7. ADVERSARY CROSS-READS  (INBOUND)
    #    Pakistan official voices, China MFA/PLA on India, Khalistan abroad.
    # ──────────────────────────────────────────────────────────────────────
    'adversary_crossreads': {
        'name': 'Adversary Voices on India',
        'flag': '🌐',
        'icon': '📡',
        'color': '#7c3aed',
        'dashboards': ['inbound'],
        'weight': 2.0,
        'role': 'Bidirectional Inbound Pressure',
        'description': (
            'Pakistan PM/army/MOFA statements ABOUT India. China MFA/PLA/ '
            'Global Times statements about India. Khalistan actors abroad '
            '(SFJ Pannun, allied diaspora orgs in Canada/US/UK). US officials '
            'making India-targeted statements (tariffs, H-1B, Khalistan '
            'indictments, defense deal language). This cluster ALSO reads '
            'from cross-theater fingerprints — see _read_upstream_fingerprints.'
        ),
        'keywords': [
            # Pakistan voices on India
            'pakistan army', 'asim munir', 'general munir',
            'shehbaz sharif on india', 'bilawal bhutto on india',
            'isi', 'ispr', 'gen syed asim munir',
            'pakistan mofa india', 'islamabad warns india',
            # China voices on India
            'china mfa india', 'mao ning india', 'lin jian india',
            'global times india', 'china daily india',
            'wang yi india', 'pla western theater',
            'zangnan', 'south tibet',
            # Khalistan
            'khalistan', 'sikhs for justice', 'sfj', 'gurpatwant singh pannun',
            'nijjar', 'hardeep singh nijjar', 'amritpal singh',
            'referendum 2020',
            # US-on-India (target language)
            'trump tariff india', 'trump h-1b', 'trump h1b',
            'tariff india', 'us sanctions india', 'state department india',
            'us trade representative india',
            # Hindi
            'पाकिस्तान फौज', 'चीन ने कहा', 'खालिस्तान',
            # Urdu
            'پاکستانی فوج', 'عاصم منیر', 'بلاول بھٹو',
        ],
        'baseline_statements_per_week': 9,
        'tripwires': [
            'pakistan nuclear signaling toward india',
            'china names indian territorial claim',
            'khalistan actor assassination/indictment',
            'us imposes tariff on indian sector',
        ],
    },
}


# ============================================================================
# SOURCES — RSS feeds, Reddit subs, GDELT queries, Brave queries
# ============================================================================

RSS_FEEDS = [
    # ── English-language Indian press ──
    {'url': 'https://www.thehindu.com/news/feeder/default.rss',
     'source': 'The Hindu', 'weight': 0.95, 'language': 'en'},
    {'url': 'https://www.thehindu.com/news/national/feeder/default.rss',
     'source': 'The Hindu — National', 'weight': 0.95, 'language': 'en'},
    {'url': 'https://www.thehindu.com/business/feeder/default.rss',
     'source': 'The Hindu — Business', 'weight': 0.95, 'language': 'en'},
    {'url': 'https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml',
     'source': 'Hindustan Times', 'weight': 0.90, 'language': 'en'},
    {'url': 'https://indianexpress.com/section/india/feed/',
     'source': 'Indian Express', 'weight': 0.92, 'language': 'en'},
    {'url': 'https://www.livemint.com/rss/news',
     'source': 'Mint', 'weight': 0.92, 'language': 'en'},
    {'url': 'https://www.business-standard.com/rss/home_page_top_stories.rss',
     'source': 'Business Standard', 'weight': 0.90, 'language': 'en'},
    {'url': 'https://feeds.feedburner.com/ndtvnews-india-news',
     'source': 'NDTV', 'weight': 0.85, 'language': 'en'},
    {'url': 'https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms',
     'source': 'Times of India', 'weight': 0.75, 'language': 'en'},
    {'url': 'https://thewire.in/rss',
     'source': 'The Wire', 'weight': 0.85, 'language': 'en'},
    {'url': 'https://theprint.in/feed/',
     'source': 'The Print', 'weight': 0.85, 'language': 'en'},
    {'url': 'https://scroll.in/feed.xml',
     'source': 'Scroll', 'weight': 0.80, 'language': 'en'},
    {'url': 'https://www.reuters.com/world/india/rss',
     'source': 'Reuters India', 'weight': 0.98, 'language': 'en'},
    {'url': 'https://www.indiatoday.in/rss/home',
     'source': 'India Today', 'weight': 0.80, 'language': 'en'},

    # ── Defense / strategic ──
    {'url': 'https://idsa.in/rss/idsa-comments',
     'source': 'IDSA (MP-IDSA)', 'weight': 0.90, 'language': 'en'},
    {'url': 'https://www.orfonline.org/feed/',
     'source': 'ORF', 'weight': 0.92, 'language': 'en'},
    {'url': 'https://carnegieindia.org/rss/all',
     'source': 'Carnegie India', 'weight': 0.92, 'language': 'en'},
]


REDDIT_SUBREDDITS = [
    # India domestic
    'india', 'IndiaSpeaks', 'IndianModerate', 'librandu',
    'IndianEconomy', 'IndianDefense', 'IndianDefence',
    'IndianHistory', 'unitedstatesofindia',
    # Kashmir / Pakistan / China cross-reads
    'Kashmir', 'pakistan', 'china',
    # Regional / global context
    'geopolitics', 'CredibleDefense', 'LessCredibleDefence',
    'IndiaInvestments',
]


# GDELT theme/keyword query templates — fed at scan time with language codes
GDELT_QUERIES = {
    'en': [
        '(india OR modi OR jaishankar) AND (china OR pakistan OR taiwan OR kashmir)',
        '(india OR rbi) AND (rupee OR gold OR oil OR import OR forex)',
        '(india OR khalistan) AND (canada OR pannun OR diaspora)',
        '(modi OR bjp) AND (rss OR hindutva OR manipur OR ayodhya)',
        '(india OR jaishankar) AND (russia OR putin OR brics OR opec)',
    ],
    'hi': [
        'मोदी',
        'भारत चीन',
        'भारत पाकिस्तान',
        'विदेशी मुद्रा',
    ],
    'ur': [
        'مودی بھارت',
        'بھارت پاکستان',
        'بھارت چین',
    ],
}


# Brave Search — used as tertiary fallback (only when GDELT + NewsAPI return
# fewer than ~10 articles for a query slot). Per-month quota: 2000.
BRAVE_QUERIES = [
    'modi statement india foreign policy site:thehindu.com OR site:livemint.com',
    'jaishankar india china relations',
    'rbi rupee defense forex reserves india',
    'india khalistan canada news',
    'india pakistan loc ceasefire violation',
]


# ============================================================================
# END OF PATCH 1-3 SCAFFOLD
# ============================================================================
# Patches that follow will add:
#   Patch 4 — Detection + scoring functions
#   Patch 5 — Cross-theater READ (Iran/China/Pakistan/US)
#   Patch 6 — Cross-theater WRITE (dual-key India fingerprint)
#   Patch 7 — Absorption integration (call into absorption_detector)
#   Patch 8 — Main scan orchestration + endpoints + registration
#   Patch 9 — US tracker patch (add 'india' to outbound keyword dict)
#   Patch 10 — Asia app.py registration
