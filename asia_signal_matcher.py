"""
Asifah Analytics -- Asia Signal Matcher v1.0.0
November 2, 2026   (Asia backend; used by the Japan, China, Taiwan, Vietnam, Philippines and India trackers)

WHY THIS EXISTS
  Same defect the Africa trackers had (see africa_signal_matcher.py, Nov 2):
  actor levels come from EXACT PHRASES -- 'china warns japan', 'china coast
  guard vietnam', 'china incursion vanguard' -- that real headlines almost never
  contain word for word:
      "Chinese coast guard ships enter Japan's waters near Senkakus"
      "China water-cannons Philippine boat near Second Thomas Shoal"
  Live /debug read Nov 2 2026, with China's own PLA actor at L4 and Taiwan's
  PLA-pressure actor at L4:
      Japan  china_threat 0, senkaku_intrusion 0, okinawa_pressure 0, dprk_threat 0
      Vietnam china_scs_pressure 0, beijing_coercion 0, maritime_posture 0
  A broken sensor reporting calm.

WHAT IT DOES
  Two-part (co-occurrence) matching: a rule fires when EVERY one of its term
  groups appears in the same headline + summary. English plus Chinese,
  Japanese, Vietnamese and Filipino terms where the trackers fetch them.
  * Text is normalised (lowercase, accents stripped, apostrophes unified).
    Latin terms match whole words; 'stem*' matches a word start. CJK terms
    match as substrings (no word boundaries in those scripts).
  * CORROBORATION: L3+ needs 2+ different outlets at that level; one outlet
    alone tops out at L2. Same rule as the ME and Africa trackers.
  * It only ever RAISES an actor (or vector) level -- max(old, co-occurrence).
    Every raise is recorded: 'cooc:L<n>:<rule>' in matched_triggers, the
    headlines in top_articles (marked via='cooccurrence'), and a
    `cooccurrence` report on the payload.

  Two entry points:
    apply_actor_cooccurrence(tracker, articles, actor_results)   -- actor trackers
    vector_cooccurrence(tracker, articles)                        -- India: new
        vectors (china_lac, pakistan_loc, us_pressure) so the Actor Matrix can
        finally read China -> India on the LAC separately from Pakistan.
"""

import re
import unicodedata
from urllib.parse import urlparse

MATCHER_VERSION = '1.0.1'


# ----------------------------------------------------------------------------
# NORMALISATION + MATCHING
# ----------------------------------------------------------------------------
def norm(text):
    t = str(text or '').replace('’', "'").replace('‘', "'").replace('ʼ', "'")
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    # 'South China Sea' / 'East China Sea' are places, not the actor China.
    t = t.replace('south china sea', 'southchinasea').replace('east china sea', 'eastchinasea')
    return t


_NONLATIN = re.compile(r'[؀-ۿ぀-ヿ㐀-鿿가-힯]')
_RX = {}


def _term_rx(term):
    rx = _RX.get(term)
    if rx is None:
        t = norm(term)
        if _NONLATIN.search(t):
            rx = re.compile(re.escape(t))
        elif t.endswith('*'):
            rx = re.compile(r'(?<![a-z0-9])' + re.escape(t[:-1]))
        else:
            rx = re.compile(r'(?<![a-z0-9])' + re.escape(t) + r'(?![a-z0-9])')
        _RX[term] = rx
    return rx


def has_any(ntext, terms):
    for t in terms:
        if _term_rx(t).search(ntext):
            return t
    return None


def outlet_of(a):
    title = str(a.get('title') or '')
    if ' - ' in title:
        tail = title.rsplit(' - ', 1)[1].strip()
        if 0 < len(tail) <= 60:
            return tail.lower()
    src = a.get('source')
    if isinstance(src, dict):
        src = src.get('name')
    src = str(src or '').strip()
    if src and not src.lower().startswith(('gnews:', 'googlenews', 'gdelt')):
        return src.lower()
    host = urlparse(str(a.get('url') or '')).netloc.lower().replace('www.', '')
    return host or 'unknown'


def _text(a):
    return f"{a.get('title', '') or ''} {a.get('description', '') or ''} {a.get('content', '') or ''}"


def _R(name, level, groups, exclude=None):
    return {'name': name, 'level': level, 'groups': groups, 'exclude': exclude or []}


def fire_rules(ntext, rules):
    for r in sorted(rules, key=lambda x: -x['level']):
        if r.get('exclude') and has_any(ntext, r['exclude']):
            continue
        hits = []
        for g in r['groups']:
            h = has_any(ntext, g)
            if not h:
                break
            hits.append(h)
        else:
            return r['level'], r['name'], hits
    return 0, None, None


def corroborated_level(levels_by_outlet):
    for L in range(5, 0, -1):
        n = sum(1 for v in levels_by_outlet.values() if v >= L)
        if n >= (2 if L >= 3 else 1):
            return L
    return 0


# ----------------------------------------------------------------------------
# SHARED TERM SETS
# ----------------------------------------------------------------------------
CN = ['china', 'chinese', 'beijing', 'pla', "people's liberation army", 'prc', 'xi jinping', 'ccg',
      'china coast guard', 'chinese coast guard', 'maritime militia', 'chinese navy', 'plan',
      '中国', '中國', '解放军', '解放軍', '北京', '海警', 'trung quoc', 'trung quốc', 'tsina']
# China as the actor doing something physical. Bare 'china' is too loose for
# L3+ physical rules: "Japan drills to counter China" is not a Chinese drill.
CN_ACT = ['chinese', "china's", 'pla', "people's liberation army", 'ccg', 'china coast guard',
          'maritime militia', 'plan', 'china sends', 'china deploys', 'china dispatch*', 'china flies',
          'china sails', 'china conducts', 'china launches', 'china holds', 'china stages', 'china fires',
          'china rams', 'china blocks', 'china water-cannons', 'china water cannons', 'china seizes',
          'china harasses', 'china swarms', 'china survey*', 'china encircl*', 'china blockade*',
          '中国海警', '解放军', '解放軍', '海警', 'trung quoc', 'tsina']
WEATHER = ['typhoon*', 'storm*', 'flood*', 'landslide*', 'earthquake*', 'tsunami', 'cyclone*', 'monsoon',
           'capsiz*', 'missing at sea', 'heat wave', 'bagyo']
JP = ['japan', 'japanese', 'tokyo', 'jsdf', 'self-defense force*', 'self-defence force*', 'senkaku*',
      'okinawa', 'ryukyu', 'yonaguni', 'ishigaki', 'miyako', 'nansei', 'kyushu', 'hokkaido', '日本', '尖閣', '沖縄']
TW = ['taiwan', 'taiwanese', 'taipei', 'taiwan strait', 'lai ching-te', 'roc', 'kinmen', 'matsu', 'penghu',
      '台湾', '台灣', '台海']
VN = ['vietnam', 'vietnamese', 'hanoi', 'viet nam', 'việt nam', 'vanguard bank', 'tu chinh', 'tư chính']
PH = ['philippines', 'philippine', 'filipino', 'filipinos', 'manila', 'marcos', 'pilipinas', 'pinoy']
WPS = ['west philippine sea', 'scarborough', 'bajo de masinloc', 'panatag', 'second thomas', 'ayungin',
       'sierra madre', 'sabina', 'escoda', 'thitu', 'pag-asa', 'reed bank', 'recto bank', 'iroquois reef',
       'sandy cay', 'whitsun', 'julian felipe', 'huangyan', 'ren\'ai', 'xianbin', 'spratly', 'spratlys',
       '黄岩岛', '仁爱礁', '仙宾礁']
SCS = ['south china sea', 'east sea', 'bien dong', 'biển đông', 'spratly', 'spratlys', 'paracel*', 'truong sa',
       'trường sa', 'hoang sa', 'hoàng sa', '南海', '西沙', '南沙']
US = ['united states', 'u.s.', 'us forces', 'us military', 'us navy', 'american', 'washington', 'pentagon',
      'hegseth', 'trump', 'rubio', 'indopacom', 'indo-pacific command', '7th fleet', 'seventh fleet']
NK = ['north korea', 'north korean', 'dprk', 'pyongyang', 'kim jong un', 'kim yo jong', '北朝鮮', '북한', '朝鲜']
RU = ['russia', 'russian', 'moscow', 'kremlin']
IND = ['india', 'indian', 'new delhi', 'delhi', 'modi', 'jaishankar', 'rajnath', 'indian army']
PAK = ['pakistan', 'pakistani', 'islamabad', 'rawalpindi', 'shehbaz', 'munir', 'ispr', 'pakistan army']

KINETIC_SEA = ['ram', 'rams', 'rammed', 'ramming', 'water cannon*', 'water-cannon*', 'collid*', 'collision',
               'laser*', 'boarded', 'boarding', 'seiz*', 'flares', 'injur*', 'assault*', 'opened fire',
               'warning shot*', 'blockade*', 'blocked', 'blocking', 'sideswip*']
GRAY = ['coast guard', 'ccg', 'militia', 'warship*', 'vessel*', 'ships', 'incursion*', 'intru*', 'harass*',
        'dangerous', 'swarm*', 'shadow*', 'survey ship*', 'survey vessel*', 'territorial waters',
        'contiguous zone', 'loiter*', 'anchored', 'tail*']
JOINT = ['joint patrol*', 'joint exercise*', 'joint drill*', 'joint sail*', 'cooperation agreement', 'hotline']
AIR = ['aircraft carrier', 'carrier', 'bomber*', 'drone*', 'fighter*', 'jets', 'warplane*', 'sortie*', 'adiz',
       'airspace', 'scramble*', 'radar lock', 'lock-on', 'transit*', 'passage']
WORDS = ['warn*', 'condemn*', 'protest*', 'summon*', 'threat*', 'retaliat*', 'demand*', 'oppose*', 'provocat*',
         'slam*', 'accus*', 'vow*', 'rebuk*', 'lodg*']
ECON = ['ban*', 'restrict*', 'tariff*', 'sanction*', 'export control*', 'export ban', 'rare earth*', 'halt*',
        'suspend*', 'boycott*', 'travel advisory', 'customs', 'anti-dumping', 'unreliable entity', 'import*']

# ----------------------------------------------------------------------------
# PROFILES -- keyed by the tracker's own actor ids
# ----------------------------------------------------------------------------
PROFILES = {}

PROFILES['japan'] = {
    'china_threat': [
        _R('kinetic_contact', 4, [CN_ACT, ['radar lock', 'lock-on', 'laser*', 'warning shot*', 'collid*', 'collision',
                                       'rammed', 'ramming', 'water cannon*', 'flares'], JP]),
        _R('military_presence', 3, [CN_ACT, AIR + ['warship*', 'incursion*', 'intru*', 'drill*', 'exercise*',
                                               'territorial waters', 'violat*'], JP], exclude=['japan-china summit']),
        _R('coercive_words', 2, [CN, WORDS + ECON + ['seafood', 'travel warning'], JP]),
        _R('tension', 1, [CN, JP, ['tension*', 'dispute*', 'row', 'spat', 'feud']]),
    ],
    'senkaku_intrusion': [
        _R('senkaku_contact', 4, [['senkaku*', 'diaoyu', '尖閣', '钓鱼岛'], ['rammed', 'ramming', 'collid*', 'water cannon*',
                                                                          'boarded', 'chased', 'expelled']]),
        _R('senkaku_incursion', 3, [['senkaku*', 'diaoyu', '尖閣', '钓鱼岛'],
                                    ['coast guard', 'ccg', 'vessel*', 'ships', 'incursion*', 'intru*',
                                     'territorial waters', 'contiguous zone', 'enter*', 'record']]),
        _R('senkaku_mention', 2, [['senkaku*', 'diaoyu', '尖閣', '钓鱼岛'], CN]),
    ],
    'okinawa_pressure': [
        _R('southwest_military', 3, [['okinawa', 'miyako', 'ryukyu', 'yonaguni', 'ishigaki', 'sakishima', 'nansei',
                                      'southwest islands', '沖縄', '宮古'], CN_ACT, AIR + ['warship*', 'exercise*',
                                                                                    'drill*', 'strait']]),
        _R('southwest_mention', 2, [['okinawa', 'miyako strait', 'yonaguni', 'ishigaki', 'sakishima', 'nansei'], CN]),
    ],
    'taiwan_strait_proximity': [
        _R('drills_near_japan', 3, [CN_ACT, TW, ['drill*', 'exercise*', 'blockade*', 'live-fire', 'encircl*', 'strait thunder',
                                         'joint sword'], ['yonaguni', 'japan', 'eez', 'okinawa', 'ishigaki']]),
    ],
    'dprk_threat': [
        _R('missile_at_japan', 4, [NK, ['missile*', 'icbm', 'ballistic', 'rocket*'],
                                   ['eez', 'over japan', 'j-alert', 'hokkaido', 'sea of japan', 'japan']]),
        _R('missile_launch', 3, [NK, ['missile*', 'icbm', 'ballistic', 'launch*', 'fired']]),
        _R('nk_threat_japan', 2, [NK, WORDS + ['nuclear'], JP]),
    ],
    'russia_threat': [
        _R('russia_military_japan', 3, [RU, AIR + ['warship*', 'fleet', 'drill*', 'exercise*', 'incursion*'],
                                        JP + ['kuril*', 'northern territories', 'soya', 'tsushima', 'la perouse']]),
        _R('russia_words_japan', 2, [RU, WORDS + ECON, JP]),
    ],
    'pm_cabinet': [
        _R('survival_threatening', 3, [['takaichi', 'prime minister', 'cabinet', 'kantei', '高市', 'chief cabinet'],
                                       ['survival-threatening', 'existential', 'collective self-defense',
                                        'collective self-defence', '存立危機', '集団的自衛権'], TW + CN]),
        _R('pm_on_china_taiwan', 2, [['takaichi', 'prime minister', 'cabinet', 'kantei', '高市'], TW + CN,
                                     ['defend*', 'contingency', 'deter*', 'counterstrike', 'counter-strike',
                                      'defense spending', 'defence spending', 'warn*', 'remark*', 'comment*']]),
    ],
    'mod_jsdf': [
        _R('deployment', 3, [['jsdf', 'self-defense force*', 'self-defence force*', 'jmsdf', 'jasdf', 'jgsdf',
                              'defense ministry', 'defence ministry', 'defense minister', 'koizumi', '自衛隊', '防衛省'],
                             ['deploy*', 'dispatch*', 'transit*', 'mobiliz*', 'missile unit*', 'tomahawk',
                              'counterstrike', 'stand-off missile*', 'long-range missile*'],
                             TW + CN + NK + RU + ['senkaku*', 'okinawa', 'yonaguni']]),
        _R('routine_response', 2, [['jsdf', 'self-defense force*', 'jmsdf', 'jasdf', 'defense ministry', '防衛省'],
                                   ['scramble*', 'intercept*', 'exercise*', 'drill*', 'monitor*'],
                                   CN + NK + RU]),
    ],
    'us_alliance': [
        _R('alliance_commitment', 3, [US, JP, ['article 5', 'article v', 'extended deterrence', 'deploy*',
                                               'typhon', 'nmesis', 'defend*', 'commit*']]),
        _R('alliance', 2, [US, JP, ['alliance', 'joint exercise*', 'summit', 'treaty']]),
    ],
}

_PLA_HEAVY = ['blockade*', 'live-fire', 'encircl*', 'joint sword', 'strait thunder', 'combat readiness patrol',
              'quarantine', 'decapitation']
_PLA_MED = ['drill*', 'exercise*', 'aircraft carrier', 'carrier', 'warship*', 'incursion*', 'median line', 'adiz',
            'sortie*', 'military aircraft', 'warplane*', 'balloon*', 'drone*', 'naval vessels']
_TW_OWN = ['han kuang', 'taiwan military holds', "taiwan's military holds", 'taiwanese military drill*',
           'taiwan army', 'taiwan navy', 'taiwan holds drill*', 'taiwan stages', 'taiwan conducts']
_TAO = ['taiwan affairs office', 'tao', 'chen binhua', 'zhu fenglian', 'song tao', '国台办', '國台辦']

PROFILES['china'] = {
    'pla_operational': [
        _R('pla_heavy', 4, [CN_ACT, _PLA_HEAVY, TW + ['taiwan strait']], exclude=_TW_OWN),
        _R('pla_presence', 3, [CN_ACT, _PLA_MED, TW + JP + PH + VN + ['south china sea', 'taiwan strait']], exclude=_TW_OWN + JOINT),
    ],
    'tao': [
        _R('tao_threat', 3, [_TAO, ['separatis*', 'punish*', 'sanction*', 'die-hard', 'independence', 'bounty',
                                    'wanted', 'warn*']]),
        _R('tao_statement', 2, [_TAO, TW]),
    ],
    'economic_coercion': [
        _R('econ_measure', 3, [CN, ECON, ['japan', 'taiwan', 'philippines', 'vietnam', 'united states', 'u.s.',
                                          'eu', 'europe', 'lithuania', 'australia', 'india', 'korea', 'netherlands']]),
        _R('econ_pressure', 2, [CN, ['trade', 'export*', 'import*'], ['retaliat*', 'pressure', 'coerc*', 'weaponi*']]),
    ],
    'us_commitment': [
        _R('us_arms_taiwan', 3, [US, TW, ['arms sale*', 'arms package', 'weapons', 'defend*', 'commit*',
                                          'transit*', 'deploy*', 'troops', 'trainers', 'six assurances']]),
        _R('us_taiwan', 2, [US, TW, ['support', 'partnership', 'visit*', 'delegation', 'policy']]),
    ],
    'taiwan_defense': [
        _R('taiwan_military', 3, [TW, ['military', 'armed forces', 'defense', 'defence', 'coast guard', 'han kuang',
                                       'reserv*', 'missile*', 'special budget', 'conscript*'],
                                  ['china', 'chinese', 'pla', 'beijing', 'invasion', 'blockade']]),
    ],
    'japan_regional': [
        _R('japan_on_taiwan', 3, [['japan', 'japanese', 'tokyo', 'takaichi', 'jsdf'], TW + ['china', 'chinese'],
                                  ['defend*', 'contingency', 'survival-threatening', 'deploy*', 'missile*',
                                   'counterstrike', 'transit*']]),
        _R('japan_china_friction', 2, [['japan', 'japanese', 'tokyo', 'takaichi'], ['china', 'chinese', 'beijing'],
                                       WORDS + ['dispute*', 'tension*', 'row']]),
    ],
    'china_iran_axis': [
        _R('china_iran_materiel', 3, [CN, ['iran', 'iranian', 'tehran', 'irgc'],
                                      ['weapons', 'missile*', 'drone*', 'satellite*', 'radar*', 'components', 'dual-use',
                                       'propellant', 'perchlorate', 'arms', 'beidou', 'ships']]),
        _R('china_iran_ties', 2, [CN, ['iran', 'iranian', 'tehran'], ['oil', 'crude', 'sanction*', 'ties', 'talks',
                                                                    'cooperation', 'visit*']]),
    ],
}

PROFILES['taiwan'] = {
    'pla_pressure': PROFILES['china']['pla_operational'],
    'beijing_coercion': [
        _R('beijing_threat', 3, [CN + _TAO, ['separatis*', 'punish*', 'reunification', 'reunify', 'sanction*',
                                             'die-hard', 'bounty', 'wanted list', 'warn*'], TW]),
        _R('beijing_words', 2, [CN + _TAO, WORDS, TW]),
    ],
    'economic_pressure': [
        _R('econ_on_taiwan', 3, [CN, ECON + ['ecfa'], TW]),
    ],
    'us_partnership': PROFILES['china']['us_commitment'],
    'roc_defense': PROFILES['china']['taiwan_defense'],
    'asymmetric_resilience': [
        _R('resilience', 2, [TW, ['civil defense', 'civil defence', 'whole-of-society', 'resilience', 'reservist*',
                                  'asymmetric', 'urban resilience', 'han kuang', 'drone*']]),
    ],
}

PROFILES['vietnam'] = {
    'china_scs_pressure': [
        _R('lethal', 5, [CN_ACT, ['killed', 'sank', 'sunk', 'dead'], VN + ['fishermen', 'fishing boat*']], exclude=WEATHER),
        _R('contact', 4, [CN_ACT, KINETIC_SEA + ['beaten', 'detain*'], VN + ['fishermen', 'fishing boat*']], exclude=WEATHER + JOINT),
        _R('gray_zone', 3, [CN_ACT, GRAY + ['haiyang dizhi', 'oil rig'], VN], exclude=JOINT),
        _R('scs_presence', 2, [CN, SCS, VN]),
    ],
    'beijing_coercion': [
        _R('sovereignty_claim', 3, [CN, ['sovereignty', 'indisputable', 'historic rights', 'nine-dash', 'ten-dash',
                                         'baseline*', 'jurisdiction'], VN + ['paracel*', 'spratly', 'spratlys']]),
        _R('beijing_words', 2, [CN, WORDS, VN]),
    ],
    'economic_pressure': [
        _R('econ_measure', 3, [CN, ECON + ['border gate*', 'durian*'], VN]),
    ],
    'maritime_posture': [
        _R('vn_maritime_action', 3, [VN, ['coast guard', 'navy', 'naval', 'fisheries surveillance', 'militia'],
                                     ['deploy*', 'patrol*', 'escort*', 'expel*', 'drive away', 'drove away',
                                      'reclamation', 'build*', 'outpost*', 'island-building', 'dredg*']]),
        _R('vn_sovereignty', 2, [VN, SCS, ['sovereignty', 'protest*', 'defend*', 'reject*', 'oppose*']]),
    ],
    'us_partnership': [
        _R('us_vn_security', 3, [US, VN, ['defense', 'defence', 'military', 'navy', 'coast guard', 'cutter*',
                                          'port call', 'carrier', 'arms', 'security']]),
        _R('us_vn', 2, [US, VN, ['partnership', 'cooperation', 'visit*', 'trade']]),
    ],
}

PH_MIL = ['philippine navy', 'philippine coast guard', 'pcg', 'armed forces of the philippines', 'philippine military',
          'philippine troops', 'bfar', 'tarriela', 'brawner', 'teodoro', 'philippine air force', 'philippine marines']
PH_GOV = ['marcos', 'malacanang', 'malacañang', 'dfa', 'department of foreign affairs', 'manalo', 'lazaro',
          'national security council', 'nsc', 'national maritime council', 'palace']

PROFILES['philippines'] = {
    'china_scs_pressure': [
        _R('lethal', 5, [CN_ACT, ['killed', 'sank', 'sunk', 'dead', 'drown*'], PH + WPS], exclude=WEATHER),
        _R('contact', 4, [CN_ACT, KINETIC_SEA + ['dangerous maneuver*', 'dangerous manoeuvre*'], PH + WPS], exclude=WEATHER + JOINT),
        _R('gray_zone', 3, [CN_ACT, GRAY, WPS + PH], exclude=JOINT),
        _R('wps_presence', 2, [CN_ACT, WPS]),
    ],
    'beijing_coercion': [
        _R('sovereignty_claim', 3, [CN, ['sovereignty', 'nature reserve', 'baseline*', 'indisputable', 'territorial sea',
                                         'jurisdiction', 'administrative', 'historic rights', 'arbitral'],
                                    WPS + PH]),
        _R('beijing_words', 2, [CN, WORDS, PH]),
    ],
    'economic_pressure': [
        _R('econ_measure', 3, [CN, ECON + ['banana*', 'tourism', 'pogo'], PH]),
        _R('econ_link', 2, [CN, PH, ['trade', 'investment*', 'loan*', 'belt and road']]),
    ],
    'marcos_state': [
        _R('diplomatic_protest', 3, [PH_GOV + PH, ['diplomatic protest', 'protest*', 'summon*', 'note verbale',
                                                  'arbitral', 'unclos', '2016 ruling', 'reject*'],
                                     CN + WPS]),
        _R('state_on_china', 2, [PH_GOV, CN + WPS + ['south china sea']]),
    ],
    'afp_pcg': [
        _R('posture_action', 3, [PH_MIL, ['resupply', 'rotation and resupply', 'deploy*', 'patrol*', 'escort*',
                                          'maritime cooperative activit*', 'joint sail*', 'exercise*', 'missile*',
                                          'brahmos', 'typhon', 'nmesis', 'drill*'], WPS + CN + ['south china sea']]),
        _R('posture_monitor', 2, [PH_MIL, CN, ['monitor*', 'track*', 'shadow*', 'challenge*', 'warn*', 'radio*']]),
    ],
    'us_alliance': [
        _R('mdt_invoked', 4, [US, PH, ['invok* the mutual defense', 'invok* mutual defense', 'article iv invoked']]),
        _R('alliance_military', 3, [US, PH, ['mutual defense treaty', 'mdt', 'article iv', 'article 4', 'typhon',
                                             'nmesis', 'edca', 'balikatan', 'kamandag', 'deploy*', 'troops',
                                             'missile system*', 'task force']]),
        _R('alliance', 2, [US, PH, ['alliance', 'partnership', 'visit*', 'joint statement', 'aid']]),
    ],
    'regional_partners': [
        _R('partner_military', 3, [['japan', 'japanese', 'australia', 'australian', 'vietnam', 'india', 'indian',
                                    'south korea', 'canada', 'france', 'new zealand', 'uk', 'britain'], PH,
                                   ['reciprocal access agreement', 'raa', 'visiting forces', 'sofa', 'sofva',
                                    'joint exercise*', 'joint sail*', 'maritime cooperative activit*',
                                    'patrol vessel*', 'defense pact', 'defence pact', 'brahmos']]),
        _R('partner_security', 2, [['japan', 'australia', 'vietnam', 'india', 'south korea', 'canada', 'france'], PH,
                                   ['defense', 'defence', 'security', 'maritime', 'coast guard']]),
    ],
    'duterte_faction': [
        _R('fracture', 3, [['duterte'], ['impeach*', 'icc', 'arrest*', 'extradit*', 'destabiliz*', 'coup',
                                         'rally', 'protest*', 'the hague']]),
        _R('faction', 2, [['duterte'], ['china', 'pro-china', 'election*', 'senate', 'marcos']]),
    ],
}

# India: VECTORS, not actors (the actor 'adversary_crossreads' blends four adversaries).
HISTORY = ['anniversary', 'years after', 'years since', 'memorial', 'film', 'movie', 'book', 'remembers', 'documentary']
LAC = ['lac', 'line of actual control', 'ladakh', 'galwan', 'arunachal', 'depsang', 'demchok', 'doklam', 'sikkim',
       'tawang', 'eastern ladakh', 'yangtse', 'chumar']
LOC = ['loc', 'line of control', 'kashmir', 'pahalgam', 'poonch', 'kupwara', 'uri', 'rajouri', 'jammu',
       'pok', 'pakistan-occupied kashmir', 'azad kashmir']
INDIA_VECTORS = {
    'china_lac': [
        _R('lac_clash', 4, [CN, ['clash*', 'killed', 'skirmish*', 'firing', 'brawl*', 'scuffle*'], LAC],
           exclude=HISTORY),
        _R('lac_buildup', 3, [CN, ['troops', 'standoff', 'face-off', 'incursion*', 'transgress*', 'buildup',
                                   'build-up', 'deploy*', 'infrastructure', 'village*'], LAC],
           exclude=HISTORY + ['disengagement complete', 'patrolling resumed', 'patrolling arrangement']),
        _R('china_claims', 2, [CN, ['zangnan', 'renam*', 'stapled visa', 'yarlung', 'brahmaputra', 'medog', 'dam'],
                               IND + ['arunachal']]),
        _R('china_india_tension', 2, [CN, IND, ['border', 'tension*', 'warn*', 'protest*', 'dispute*']]),
    ],
    'pakistan_loc': [
        _R('cross_border_strikes', 5, [PAK + IND, ['airstrike*', 'air strike*', 'missile strike*', 'drone strike*',
                                                   'operation sindoor', 'precision strike*'],
                                       ['killed', 'dead', 'casualt*'], PAK]),
        _R('loc_fire', 4, [LOC, ['firing', 'ceasefire violation*', 'shelling', 'infiltrat*', 'encounter',
                                 'killed', 'militant*', 'terror attack*', 'attack*']]),
        _R('india_pak_threat', 3, [PAK, IND, ['warn*', 'threat*', 'indus waters', 'water treaty', 'retaliat*',
                                              'airspace', 'expel*', 'downgrad*', 'mobiliz*']]),
        _R('india_pak_tension', 2, [PAK, IND, ['tension*', 'border', 'talks', 'dispute*']]),
    ],
    'us_pressure': [
        _R('us_trade_coercion', 3, [US, IND, ['tariff*', 'sanction*', 'h-1b', 'h1b', 'penalt*']]),
        _R('us_india_trade', 2, [US, IND, ['trade', 'deal', 'talks']]),
    ],
}


# ----------------------------------------------------------------------------
# ENTRY POINTS
# ----------------------------------------------------------------------------
def _scan(articles, ladders):
    per = {k: {} for k in ladders}
    rule_at = {k: {} for k in ladders}
    examples = {k: [] for k in ladders}
    for a in articles:
        nt = norm(_text(a))
        outlet = outlet_of(a)
        for k, rules in ladders.items():
            lvl, rname, ev = fire_rules(nt, rules)
            if not lvl:
                continue
            if lvl > per[k].get(outlet, 0):
                per[k][outlet] = lvl
            rule_at[k].setdefault(lvl, rname)
            if len(examples[k]) < 5 and lvl >= 2:
                src = a.get('source')
                examples[k].append({'level': lvl, 'rule': rname, 'evidence': ev,
                                    'title': str(a.get('title', ''))[:150], 'outlet': outlet,
                                    'url': a.get('url', ''),
                                    'source': src.get('name', '') if isinstance(src, dict) else str(src or ''),
                                    'publishedAt': a.get('publishedAt') or a.get('published') or ''})
    out = {}
    for k in ladders:
        L = corroborated_level(per[k])
        peak = max(per[k].values()) if per[k] else 0
        out[k] = {'level': L, 'raw_peak': peak, 'outlets': len(per[k]), 'rule': rule_at[k].get(L) or '',
                  'held_back_for_corroboration': peak > L, 'examples': examples[k]}
    return out


def apply_actor_cooccurrence(tracker, articles, actor_results, level_labels=None):
    """Raise actor levels in place. actor_results: {actor_id: {'level': int, ...}}.
    level_labels: the tracker's ESCALATION_LEVELS ({n: {'label','color'}}), used to keep labels in sync.
    Returns the `cooccurrence` report for the payload."""
    ladders = {k: v for k, v in PROFILES.get(tracker, {}).items() if k in actor_results}
    reads = _scan(articles, ladders)
    report = {'version': MATCHER_VERSION, 'tracker': tracker, 'actors': {}}
    for aid, r in reads.items():
        ar = actor_results[aid]
        before = int(ar.get('level') or 0)
        after = max(before, r['level'])
        if after > before:
            ar['level'] = after
            if level_labels and after in level_labels:
                ar['level_label'] = level_labels[after].get('label', ar.get('level_label'))
                ar['level_color'] = level_labels[after].get('color', ar.get('level_color'))
            mt = ar.setdefault('matched_triggers', [])
            if isinstance(mt, list):
                mt.insert(0, f"cooc:L{after}:{r['rule']}")
            ta = ar.setdefault('top_articles', [])
            if isinstance(ta, list):
                for ex in r['examples'][:3]:
                    ta.insert(0, {'title': ex['title'], 'url': ex['url'], 'source': ex['source'],
                                  'publishedAt': ex['publishedAt'], 'level': ex['level'],
                                  'trigger': f"cooc:{ex['rule']}", 'via': 'cooccurrence'})
        ar['cooc_level'] = r['level']
        report['actors'][aid] = {'before': before, 'after': after, 'cooc_level': r['level'],
                                 'raw_peak': r['raw_peak'], 'outlets': r['outlets'],
                                 'held_back_for_corroboration': r['held_back_for_corroboration'],
                                 'examples': r['examples']}
    return report


def apply_levels_dict(tracker, articles, actor_levels):
    """Japan-style trackers keep {actor_id: level}. Raises in place; returns the report."""
    proxy = {k: {'level': v} for k, v in actor_levels.items()}
    report = apply_actor_cooccurrence(tracker, articles, proxy)
    for k, v in proxy.items():
        actor_levels[k] = v['level']
    return report


def vector_cooccurrence(tracker, articles):
    """-> (vector_levels {name: level}, report). Currently 'india'."""
    ladders = INDIA_VECTORS if tracker == 'india' else {}
    reads = _scan(articles, ladders)
    levels = {k: r['level'] for k, r in reads.items()}
    return levels, {'version': MATCHER_VERSION, 'tracker': tracker, 'vectors': reads}
