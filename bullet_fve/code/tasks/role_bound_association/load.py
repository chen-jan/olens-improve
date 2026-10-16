"""Role-bound association (role_bound_association): data map, join and bullet labels for the
per-bullet FVE study. READ-ONLY on project data; writes only under this task folder (DATA).

Generalises code/extract_hall.py (selection extract + AR-vector coverage) and reuses
code/bullet_attrib_lib.render_offsets (bullet char spans in the judged text). The extract has the
same per-line schema as inputs/hall_three_settings.jsonl, so code/metrics_job.py can run on it
by pointing its two input paths at DATA (and using layer 28 as well).

Usage (python = ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B,
PYTHONPATH=${OLENS_REPO_ROOT}/src):
  python load.py extract            # heavy: run through srun (streams 5.3 GB selections + vector indexes)
  python load.py selftest           # joins + label checks over all 3 x 11,400 readouts -> DATA/selftest.json
  python load.py show CELL_ID [COND]  # print one joined cell with judge answers and bullet labels
  python load.py examples           # the fixed verification sample used in MAP.md (5 cells per setting)

Library:
  load_bank()                 {item_id: item + 'options' (3 x 6 shown labels) + 'golds' + 'lex' aliases}
  load_judgments(cond)        {cell_id: judge record (choices, kinds, correct, pass, evidence, readout_class)}
  iter_cells(cells=None)      joined cells: extract row + per-setting judge + per-bullet features/labels
  label_readout(item, judge, atoms)  per-bullet features and labels (rule RBA-v1, see MAP.md)
"""
import collections
import hashlib
import json
import random
import re
import sys
import time
import unicodedata
from pathlib import Path

sys.path.insert(0, '${OLENS_REPO_ROOT}/src')
sys.path.insert(0, '${OLENS_SCRATCH}/olens-bullet-fve/code')

FAMILY = 'role_bound_association'
TASK = Path('${OLENS_SCRATCH}/olens-bullet-fve/tasks/role_bound_association')
DATA = TASK / 'data'
EXTRACT = DATA / 'rba_three_settings.jsonl'
VINDEX = DATA / 'rba_vector_index.json'
D = '${OLENS_DATA_ROOT}'
C = '${OLENS_COMPUTE_ROOT}'
WB = '${OLENS_SOURCE_ROOT}/scratch/repos/workspace-bench-v2'  # pinned commit 92d763e
BANK = f'{WB}/evals/role_bound_association/items.json'
GOLDEN_OPTIONS = f'{WB}/tests/golden/role_bound_association_options.json'
JUDGMENTS = f'{D}/expansion-v1/judgments'
SELECTIONS = {
    'development': f'{D}/selections/development-full-grid-v4/merged/selections.jsonl',
    'validation': f'{D}/selections/validation-full-grid-v1/merged/selections.jsonl',
    'test': f'{D}/selections/test-full-grid-v1/merged/selections.jsonl',
}
CACHES = {  # the cache each stage's selector used (configs/expansion_manifest_v1.json stages.*.vector_cache)
    'development': f'{C}/vectors/shared-global-v1/a451cf49d28ac7447722',
    'validation': f'{C}/vectors/validation-catalog-v1',
    'test': f'{C}/vectors/test-catalog-v1',
}
FRESH = f'{C}/activations/core-v1/fresh_manifest_v2.json'
CACHED_V2 = f'{D}/expansion-v1/selections/cached-v2/role_bound_association.jsonl'
CONTRACT = 'a451cf49d28ac74477229e74dfc738e51b8961b5376c688fd9e40abbd8c133b6'
SETTINGS = {  # condition id -> (method, n, short display, long display)
    'capped_n1-n1': ('capped_n1', 1, 'Original', 'Original, capped to four bullets'),
    'best_n_exact-n32': ('best_n_exact', 32, 'Best of 32', 'Choose the best complete readout (32 samples)'),
    'pooled_greedy_swap-n32': ('pooled_greedy_swap', 32, 'Combine 32', 'Combine original bullets (32 samples)'),
}
WANT = {(m, n): cond for cond, (m, n, _, _) in SETTINGS.items()}
PREFIX = b'{"cell_id": "role_bound_association|'
ATOM_KEEP = ('source_phrase_id', 'sample_index', 'text', 'scored_text', 'cache_key', 'status',
             'original_token_count', 'scored_token_count', 'truncated', 'scored_token_ids',
             'unscored_suffix_ids', 'parser_flags', 'span_start', 'span_end')
CANNOT = 'cannot tell from the readout'
DATASET_SEED = 20260810


def judge_key(item_id, layer, pos):
    return f'{item_id}__L{layer:03d}__p{pos}'


def cell_id(item_id, layer, pos):
    return f'{FAMILY}|{item_id}|L{layer}|p{pos:05d}'


def parse_cell_id(cid):
    fam, item, lay, pos = cid.split('|')
    return item, int(lay[1:]), int(pos[1:])


# ----------------------------------------------------------------------------------------------
# 1. Extract (heavy: srun). Same schema as code/extract_hall.py output.
# ----------------------------------------------------------------------------------------------
def extract(out=DATA):
    from olens_improve.ar_cache import vector_key
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    summary = collections.OrderedDict()
    fresh = {c['cell_id']: c for c in json.load(open(FRESH))['cells'] if c['family'] == FAMILY}
    summary['fresh_cells'] = len(fresh)
    expansion = {}
    with open(CACHED_V2) as f:
        for line in f:
            r = json.loads(line)
            for s in r['selections']:
                cond = WANT.get((s['method'], s['n']))
                if cond:
                    expansion[(r['cell_id'], cond)] = (hashlib.sha256(s['text'].encode()).hexdigest(),
                                                       s['token_count'], s['bullet_count'])
    summary['cached_v2_pairs'] = len(expansion)
    needed = {stage: set() for stage in SELECTIONS}
    stats = collections.Counter()
    seen = set()
    tmp = out / (EXTRACT.name + '.tmp')
    with open(tmp, 'w') as fo:
        for stage, path in SELECTIONS.items():
            with open(path, 'rb') as f:
                for raw in f:
                    if not raw.startswith(PREFIX):
                        continue
                    row = json.loads(raw)
                    cid = row['cell_id']
                    cell = fresh[cid]
                    assert cid not in seen, cid
                    seen.add(cid)
                    assert row['split'] == stage == cell['split'], (cid, row['split'], stage)
                    for k in ('family', 'item_id', 'layer', 'position', 'activation_sha256'):
                        assert row[k] == cell[k], (cid, k)
                    settings = {}
                    for s in row['selections']:
                        cond = WANT.get((s['method'], s['n']))
                        if not cond:
                            continue
                        exact = (s.get('fits') or {}).get('exact')
                        if exact is None:
                            stats[f'no_exact_fit[{cond}]'] += 1
                            exact = {'fve': None, 'coefficients': None, 'atom_ids': s['phrase_ids'], 'solver': None}
                        else:
                            assert exact['solver'] == 'scipy_exact', (cid, cond)
                        assert list(exact['atom_ids']) == s['phrase_ids'], (cid, cond)
                        assert [a['source_phrase_id'] for a in s['atoms']] == s['phrase_ids'], (cid, cond)
                        tsha = hashlib.sha256(s['text'].encode()).hexdigest()
                        if expansion.get((cid, cond)) != (tsha, s['token_count'], s['bullet_count']):
                            stats[f'expansion_text_mismatch[{cond}]'] += 1
                        atoms = [{k: a.get(k) for k in ATOM_KEEP} for a in s['atoms']]
                        for a in atoms:
                            stats[f'atoms[{cond}]'] += 1
                            if a['cache_key'] is None:
                                stats[f'atoms_without_key[{cond}]'] += 1
                            else:
                                needed[stage].add(a['cache_key'])
                            if a['truncated']:
                                stats[f'atoms_truncated_gt32[{cond}]'] += 1
                        keys = [a['cache_key'] for a in atoms]
                        if len(set(keys)) != len(keys):
                            stats[f'readouts_with_shared_vector[{cond}]'] += 1
                        stats[f'bullets={len(atoms)}[{cond}]'] += 1
                        stats[f'reason={s["reason"]}[{cond}]'] += 1
                        rel = (s.get('fits') or {}).get('released80') or {}
                        settings[cond] = {
                            'method': s['method'], 'n': s['n'], 'text': s['text'], 'text_sha256': tsha,
                            'token_count': s['token_count'], 'bullet_count': s['bullet_count'],
                            'reason': s['reason'], 'fits_scope': s['fits_scope'], 'phrase_ids': s['phrase_ids'],
                            'fve': exact['fve'], 'coefficients': exact['coefficients'],
                            'released80_fve': rel.get('fve'), 'trace': s['trace'], 'atoms': atoms,
                        }
                    assert set(settings) == set(SETTINGS), (cid, sorted(settings))
                    fo.write(json.dumps({
                        'cell_id': cid, 'family': FAMILY, 'item_id': row['item_id'],
                        'group_id': cell['group_id'], 'layer': row['layer'], 'position': row['position'],
                        'split': stage, 'token': cell.get('token'), 'read_position_kind': cell.get('read_position_kind'),
                        'activation_row': cell['activation_row'], 'activation_sha256': cell['activation_sha256'],
                        'global_pool_id': row['global_pool_id'], 'vector_cache': CACHES[stage],
                        'source_selections': path, 'settings': settings,
                    }, ensure_ascii=False) + '\n')
                    stats[f'cells[{stage}]'] += 1
                    stats[f'cells[L{row["layer"]}]'] += 1
            print(stage, 'done', round(time.time() - t0, 1), 's', flush=True)
    tmp.replace(out / EXTRACT.name)
    summary['cells_extracted'] = len(seen)
    summary['missing_vs_fresh'] = sorted(set(fresh) - seen)[:20]
    summary['stats'] = dict(sorted(stats.items()))

    index, cov, found_meta, tags = {}, {}, {}, {}
    for stage, directory in CACHES.items():
        contract = json.load(open(Path(directory) / 'contract.json'))
        assert contract['sha256'] == CONTRACT
        want = needed[stage]
        found = {}
        files = sorted(Path(directory).glob('raw_*.index.json'))
        for p in files:
            info = json.load(open(p))
            assert info['contract_sha256'] == CONTRACT
            for v in info['vectors']:
                k = v['cache_key']
                if k in want:
                    assert k not in found, ('duplicate key in one cache', k)
                    assert vector_key(CONTRACT, v['tag_ids'], v['scored_token_ids']) == k
                    assert tags.setdefault(v['layer'], v['tag_ids']) == v['tag_ids']
                    found[k] = [info['tensor_path'], v['row'], v['layer'], len(v['scored_token_ids'])]
        index[stage] = {k: v[:2] for k, v in found.items()}
        found_meta[stage] = found
        cov[stage] = {'index_files': len(files), 'needed_keys': len(want), 'found_keys': len(found),
                      'missing_keys': sorted(want - set(found))[:20],
                      'tensor_files_touched': len({v[0] for v in found.values()})}
        print(stage, cov[stage]['needed_keys'], cov[stage]['found_keys'], round(time.time() - t0, 1), 's', flush=True)
    summary['coverage'] = cov
    checks = collections.Counter()
    with open(out / EXTRACT.name) as f:
        for line in f:
            r = json.loads(line)
            for cond, s in r['settings'].items():
                for a in s['atoms']:
                    k = a['cache_key']
                    if k is None or k not in found_meta[r['split']]:
                        continue
                    meta = found_meta[r['split']][k]
                    checks['layer_ok' if meta[2] == r['layer'] else 'layer_mismatch'] += 1
                    ok = vector_key(CONTRACT, tags[r['layer']], a['scored_token_ids']) == k
                    checks['atom_tokens_reproduce_key' if ok else 'atom_tokens_key_mismatch'] += 1
                    checks['scored_le_32' if len(a['scored_token_ids']) <= 32 else 'scored_gt_32'] += 1
    summary['atom_key_checks'] = dict(checks)
    summary['tag_ids_by_layer'] = {str(k): v for k, v in sorted(tags.items())}
    summary['seconds'] = time.time() - t0
    json.dump(index, open(out / VINDEX.name, 'w'))
    json.dump(summary, open(out / 'extract_summary.json', 'w'), indent=1)
    print(json.dumps(summary, indent=1)[:6000])


# ----------------------------------------------------------------------------------------------
# 2. Item bank + the judge's option lists (golden file == port of wsbench judge.build_block)
# ----------------------------------------------------------------------------------------------
def _seed_int(s):
    return int.from_bytes(hashlib.sha256(s.encode()).digest()[:8], 'big')


def _seeded_shuffle(items, seed):
    out = list(items)
    random.Random(_seed_int(seed)).shuffle(out)
    return out


def build_options(it, items):
    """Port of wsbench/evals/role_bound_association/judge.py build_block (sha 2615694e...): the three
    shown 6-option lists (5 seeded-shuffled + CANNOT last) and the 1-based golds."""
    a_lab = f"{it['names']['a']}, the {it['role_a']}"
    b_lab = f"{it['names']['b']}, the {it['role_b']}"
    rng = random.Random(_seed_int(f"{DATASET_SEED}:d:{it['id']}"))
    other = [x for x in items if x['pair_id'] != it['pair_id']]
    dist_people = [f"{x['names']['a']}, the {x['role_a']}" for x in rng.sample(other, 3)]
    people = [a_lab, b_lab, *dist_people]
    actions = [it['action'], *rng.sample(sorted({x['action'] for x in other} - {it['action']}), 4)]
    subj, obj = (a_lab, b_lab) if it['direction'] == 'ab' else (b_lab, a_lab)
    shown, golds = [], []
    for q, opts, gold in (('q1', people, subj), ('q2', actions, it['action']), ('q3', people, obj)):
        s = [*_seeded_shuffle(opts, f"{DATASET_SEED}:{it['id']}:{q}"), CANNOT]
        shown.append(s)
        golds.append(s.index(gold) + 1)
    return shown, golds, a_lab, b_lab


def _parse_golden_block(block):
    qs = re.split(r'\n\n(?=Q\d\. )', block)[1:]
    return [[re.match(r'  (\d)\. (.*)$', ln).group(2) for ln in q.split('\n')[1:]] for q in qs]


_BANK = None


def load_bank():
    global _BANK
    if _BANK is not None:
        return _BANK
    items = json.load(open(BANK))
    golden = json.load(open(GOLDEN_OPTIONS))
    bank = {}
    for it in items:
        shown, golds, a_lab, b_lab = build_options(it, items)
        assert shown == _parse_golden_block(golden[it['id']]['block']), it['id']
        assert golds == golden[it['id']]['golds'], it['id']
        it = dict(it)
        it['options'], it['golds'] = shown, golds
        it['label_a'], it['label_b'] = a_lab, b_lab
        it['agent_side'] = 'a' if it['direction'] == 'ab' else 'b'
        it['patient_side'] = 'b' if it['direction'] == 'ab' else 'a'
        it['lex'] = build_lexicon(it, items)
        bank[it['id']] = it
    _BANK = bank
    return bank


# ----------------------------------------------------------------------------------------------
# 3. Lexicon (transparent string rules; see MAP.md "Bullet labels")
# ----------------------------------------------------------------------------------------------
# Role words that are also everyday adjectives/nouns: counted only after a determiner/possessive.
AMBIGUOUS_ROLE_WORDS = {'general', 'private', 'local', 'patient', 'official', 'source', 'security',
                        'star', 'native', 'resident', 'reader', 'bench', 'chief', 'owner', 'guest',
                        'server', 'famous', 'reserve', 'heir', 'father', 'counsel', 'player'}
DETERMINERS = r"(?:the|a|an|his|her|their|its|this|that|one|another|our|my|your|young|old|elderly|new)"
ACTION_STOP = {'to', 'at', 'on', 'for', 'about', 'was', 'were', 'is', 'the', 'a', 'an', 'up'}
IRREGULAR = {
    'fed': {'feed', 'feeds', 'feeding', 'fed'},
    'spied': {'spy', 'spies', 'spying', 'spied'},
    'forgave': {'forgive', 'forgives', 'forgiving', 'forgiven', 'forgave', 'forgiveness'},
    'lied': {'lie', 'lies', 'lying', 'lied', 'liar', 'liars'},
}
# multiword actions -> regex on folded text
JUNK_FORMS = {'fin', 'fins', 'teas'}  # wrong '-ed' stems that are real words (fined -> fin, teased -> teas)
ACTION_DROP = {'fined': {'fine'}}  # bare 'fine' is mostly the adjective; the noun needs a determiner
ACTION_EXTRA_PHRASES = {'fined': [r'\b(?:a|the|late|overdue|library)\s+fines?\b']}
ACTION_PHRASES = {
    'looked down on': r'\blook(?:s|ed|ing)? down (?:on|upon)\b',
    'asked for directions': r'\bask(?:s|ed|ing)? (?:\w+ ){0,3}(?:for )?directions?\b',
}


def fold(s):
    """wsbench.mc.fold: accent-, case- and curly-quote-insensitive."""
    s = unicodedata.normalize('NFKD', s)
    for a, b in (('‘', "'"), ('’', "'"), ('“', '"'), ('”', '"')):
        s = s.replace(a, b)
    return ''.join(c for c in s if not unicodedata.combining(c)).casefold()


def base_forms(b):
    """Inflections of a verb/noun base: b, b+s/es, b+ed/d, b+ing (e-drop), y -> ies/ied."""
    out = {b, b + 's', b + 'ing'}
    if b.endswith('e'):
        out |= {b + 'd', b[:-1] + 'ing'}
    else:
        out.add(b + 'ed')
    if b.endswith('y') and len(b) > 3 and b[-2] not in 'aeiou':
        out |= {b[:-1] + 'ies', b[:-1] + 'ied'}
    if b.endswith(('s', 'sh', 'ch', 'x')):
        out.add(b + 'es')
    return out


def verb_forms(word):
    """Forms of the verb behind a past-tense item action ('chased' -> chase/chases/chased/chasing).
    The base is unknown (chased -> chase, scolded -> scold, hugged -> hug), so every candidate
    base is expanded; wrong candidates give non-words except JUNK_FORMS, which are removed."""
    w = word.lower()
    if w in IRREGULAR:
        return set(IRREGULAR[w])
    bases = {w}
    if w.endswith('ied'):
        bases.add(w[:-3] + 'y')
    elif w.endswith('ed'):
        bases |= {w[:-2], w[:-1]}
        if len(w) > 4 and w[-3] == w[-4]:
            bases.add(w[:-3])  # hugged -> hug
    out = {w}
    for b in bases - {w}:
        if len(b) >= 3:
            out |= base_forms(b)
    return out - JUNK_FORMS - ACTION_DROP.get(w, set())


def action_terms(action, extra=()):
    """(word set, phrase regexes) for one action string + optional blocklist synonyms (taken
    as listed, plus their regular inflections)."""
    words, phrases = set(), []
    if action in ACTION_PHRASES:
        phrases.append(ACTION_PHRASES[action])
    else:
        content = [w for w in action.lower().split() if w not in ACTION_STOP]
        if content[:1] == ['angry']:
            words |= {'angry', 'anger', 'angered', 'angrily'}
        else:
            words |= verb_forms(content[0])
            phrases += ACTION_EXTRA_PHRASES.get(content[0], [])
    for x in extra:
        x = x.lower()
        if ' ' in x:
            phrases.append(r'\b' + r'\s+'.join(re.escape(p) for p in x.split()) + r'\b')
        else:
            words |= base_forms(x) - JUNK_FORMS
    return words, phrases


def _split_blocklist_roles(it):
    roles = [r for r in it['blocklist']['roles']]
    b_words = set(it['role_b'].lower().split())
    for i, r in enumerate(roles):
        if r.lower() in b_words or r.lower() == it['role_b'].lower():
            return roles[:i], roles[i:]
    raise AssertionError(('cannot split blocklist', it['id']))


def _plural(w):
    if w.endswith('y') and len(w) > 3 and w[-2] not in 'aeiou':
        return {w, w[:-1] + 'ies'}
    if w.endswith(('s', 'sh', 'ch', 'x')):
        return {w, w + 'es'}
    if w.endswith('man'):
        return {w, w[:-3] + 'men'}
    if w.endswith('f'):
        return {w, w + 's', w[:-1] + 'ves'}
    return {w, w + 's'}


def role_terms(role, synonyms):
    terms = set()
    for x in [role, *synonyms, role.split()[-1]]:
        x = x.lower()
        if ' ' in x:
            terms.add(x)
            terms.add(x + 's')
        else:
            terms |= _plural(x)
    return terms


def build_lexicon(it, items):
    a_syn, b_syn = _split_blocklist_roles(it)
    lex = {
        'name': {'a': it['names']['a'], 'b': it['names']['b']},
        'role': {'a': sorted(role_terms(it['role_a'], a_syn)), 'b': sorted(role_terms(it['role_b'], b_syn))},
    }
    w, p = action_terms(it['action'], it['blocklist']['action'])
    lex['action'] = {'words': sorted(w), 'phrases': p}
    own_roles = set(lex['role']['a']) | set(lex['role']['b'])
    own_action = set(w)
    # judge distractors (the 3 other people and 4 other actions it was shown)
    people = [o for o in it['options'][0] if o not in (CANNOT, it['label_a'], it['label_b'])]
    lex['role_cjk'] = {'a': CJK_ROLES[it['role_a']], 'b': [t for t in CJK_ROLES[it['role_b']] if t not in CJK_ROLES[it['role_a']]]}
    lex['action_cjk'] = CJK_ACTIONS[it['action']]
    own_cjk = set(lex['role_cjk']['a']) | set(lex['role_cjk']['b'])
    lex['distractor_people'] = {}
    lex['distractor_people_cjk'] = {}
    for lab in people:
        role = lab.split(', the ', 1)[1]
        syn = set()  # the a-side blocklist synonyms of the bank item(s) this distractor label comes from
        for x in items:
            if f"{x['names']['a']}, the {x['role_a']}" == lab:
                syn |= set(_split_blocklist_roles(x)[0])
        lex['distractor_people'][lab] = sorted(role_terms(role, sorted(syn)) - own_roles)
        lex['distractor_people_cjk'][lab] = [t for t in CJK_ROLES[role] if t not in own_cjk]
    lex['distractor_actions'] = {}
    for act in it['options'][1]:
        if act in (CANNOT, it['action']):
            continue
        dw, dp = action_terms(act)
        lex['distractor_actions'][act] = {'words': sorted(set(dw) - own_action), 'phrases': dp,
                                          'cjk': [t for t in CJK_ACTIONS[act] if t not in lex['action_cjk']]}
    return lex


# Chinese aliases (the lens often opens a bullet with a CJK token; the judge reads it). Hand-made,
# substring match, 2+ characters except a few unambiguous single characters. Recorded in the
# bullet's term lists, so analyses can drop CJK-only matches.
CJK_ROLES = {
    'CEO': ['首席执行官', '总裁'], 'accountant': ['会计'], 'athlete': ['运动员', '选手'],
    'babysitter': ['保姆'], 'benchwarmer': ['替补'], 'borrower': ['借阅者', '借书人', '读者'],
    'boss': ['老板', '上司'], 'bouncer': ['保安', '门卫'], 'bride': ['新娘'], 'brother': ['哥哥', '弟弟', '兄弟'],
    'burglar': ['窃贼', '小偷', '盗贼', '贼'], 'butler': ['管家'], 'bystander': ['路人', '旁观者', '目击者'],
    'caterer': ['厨师', '餐饮', '承办'], 'celebrity': ['明星', '名人'], 'child': ['孩子', '小孩', '孙子', '孙女'],
    'client': ['客户', '顾客', '客人'], 'coach': ['教练'], 'comedian': ['喜剧演员', '喜剧'], 'critic': ['评论家', '乐评'],
    'customer': ['顾客', '客人', '客户'], 'daughter': ['女儿'], 'dean': ['院长', '系主任'], 'detective': ['侦探', '警探'],
    'doctor': ['医生', '大夫'], 'driver': ['司机', '车主'], 'employee': ['员工', '雇员', '职员'], 'fan': ['粉丝', '影迷', '歌迷'],
    'father': ['父亲', '爸爸'], 'firefighter': ['消防员'], 'general': ['将军'],
    'grandmother': ['祖母', '奶奶', '外婆', '老奶奶'], 'grandparent': ['祖父母', '祖母', '祖父', '爷爷', '奶奶', '外公', '外婆'],
    'grandson': ['孙子', '外孙'], 'guard': ['狱警', '看守', '警卫'], 'hairdresser': ['理发师', '发型师'],
    'heckler': ['起哄'], 'heiress': ['女继承人', '继承人'], 'homeowner': ['房主', '屋主', '业主'], 'husband': ['丈夫', '老公'],
    'informant': ['线人', '告密者'], 'intern': ['实习生'], 'janitor': ['清洁工', '保洁'], 'journalist': ['记者'],
    'king': ['国王'], 'landlord': ['房东'], 'lawyer': ['律师'], 'librarian': ['图书管理员', '馆员'], 'local': ['当地人', '本地人'],
    'manager': ['经理', '主管'], 'mechanic': ['修理工', '技师', '机修工'], 'mother': ['母亲', '妈妈'],
    'musician': ['音乐家', '乐手', '歌手'], 'neighbor': ['邻居'], 'nurse': ['护士'], 'paramedic': ['急救员', '医护人员'],
    'parent': ['家长', '父母'], 'parishioner': ['教友', '信徒', '教徒'], 'passenger': ['乘客'], 'patient': ['病人', '患者'],
    'patron': ['顾客', '客人'], 'pilot': ['飞行员', '机长'], 'player': ['球员', '选手'], 'plumber': ['水管工'],
    'police officer': ['警察', '警官', '巡警'], 'politician': ['政客', '政治家', '议员'], 'priest': ['神父', '牧师'],
    'principal': ['校长'], 'prisoner': ['囚犯', '犯人', '囚徒'], 'professor': ['教授'], 'recruit': ['新兵', '新人', '新手'],
    'referee': ['裁判'], 'security guard': ['保安', '警卫'], 'servant': ['仆人', '侍从'], 'shop owner': ['店主', '老板娘'],
    'sister': ['姐姐', '妹妹', '姐妹'], 'soldier': ['士兵', '军人'], 'son': ['儿子'], 'star starter': ['首发', '主力'],
    'student': ['学生'], 'supplier': ['供应商', '供货商'], 'suspect': ['嫌疑人', '嫌犯'], 'teacher': ['老师', '教师'],
    'tenant': ['租客', '房客', '租户'], 'thief': ['小偷', '窃贼', '盗贼', '贼'], 'toddler': ['幼儿', '孩子', '小孩', '宝宝'],
    'tourist': ['游客', '旅客'], 'troublemaker': ['捣蛋', '问题学生'], 'veteran': ['老兵', '老手'], 'visitor': ['访客', '来访者', '游客'],
    'waiter': ['服务员'], 'wife': ['妻子', '老婆', '太太'], 'witness': ['证人', '目击者'],
}
CJK_ACTIONS = {
    'admired': ['钦佩', '敬佩', '欣赏', '崇拜'], 'apologized to': ['道歉'], 'asked for directions': ['问路'],
    'avoided': ['躲避', '回避', '避开', '躲着'], 'billed': ['账单', '收费'], 'blamed': ['指责', '责怪', '责备', '归咎'],
    'bowed to': ['鞠躬'], 'chased': ['追赶', '追捕', '追逐'], 'cheated': ['欺骗', '诈骗', '骗了'], 'comforted': ['安慰'],
    'complimented': ['称赞', '夸奖', '赞美'], 'deceived': ['欺骗', '骗了', '蒙骗'], 'distrusted': ['不信任', '怀疑'],
    'dreaded': ['畏惧', '害怕', '恐惧'], 'ejected': ['驱逐', '赶出', '轰出'], 'envied': ['嫉妒', '羡慕'],
    'feared': ['害怕', '恐惧', '畏惧'], 'fed': ['喂'], 'fined': ['罚款', '罚金'], 'followed': ['跟踪', '尾随'],
    'forgave': ['原谅', '宽恕'], 'hugged': ['拥抱'], 'humiliated': ['羞辱', '侮辱', '出丑'], 'indulged': ['溺爱', '纵容', '宠爱', '宠溺'],
    'instructed': ['指示', '指导', '吩咐'], 'interrogated': ['审问', '盘问', '质问'], 'interviewed': ['采访'],
    'lied to': ['撒谎', '说谎', '谎言'], 'looked down on': ['看不起', '轻视', '蔑视', '瞧不起'], 'mocked': ['嘲笑', '嘲讽', '讥讽'],
    'overcharged': ['多收', '高价', '宰客'], 'photographed': ['拍照', '拍摄', '合影'], 'pitied': ['同情', '怜悯', '可怜'],
    'protected': ['保护'], 'reassured': ['安抚', '安慰'], 'reported': ['举报', '告发'], 'rescued': ['营救', '救出', '救援'],
    'resented': ['怨恨', '埋怨', '憎恨'], 'saluted': ['敬礼', '致敬', '致意'], 'scolded': ['责骂', '训斥', '斥责', '批评'],
    'searched': ['搜查', '搜身'], 'spied on': ['监视', '窥视', '偷看'], 'suspected': ['怀疑'],
    'teased': ['取笑', '戏弄', '逗弄', '嘲弄'], 'thanked': ['感谢', '道谢'], 'underestimated': ['低估', '小看', '轻视'],
    'warned': ['警告'], 'was angry at': ['生气', '愤怒', '发火'], 'worried about': ['担心', '担忧'],
    'yelled at': ['大喊', '吼', '大骂', '呵斥'],
}


def _find_cjk(text, terms):
    hits = []
    for t in terms:
        i = text.find(t)
        while i >= 0:
            hits.append((i, t))
            i = text.find(t, i + 1)
    return hits


_WORD = re.compile(r"[a-z]+(?:-[a-z]+)*")
_CAP = re.compile(r"\b([A-Z][a-z]{2,})")


def _find_words(ftext, terms):
    """Exact folded whole-word / phrase occurrences of terms; ambiguous words need a determiner."""
    hits = []
    for t in terms:
        if ' ' in t:
            pat = r'\b' + r'\s+'.join(re.escape(x) for x in t.split()) + r'\b'
        elif t in AMBIGUOUS_ROLE_WORDS or (t.endswith('s') and t[:-1] in AMBIGUOUS_ROLE_WORDS):
            pat = r'\b' + DETERMINERS + r'\s+(?:[a-z-]+\s+)?' + re.escape(t) + r'\b'
        else:
            pat = r'(?<![a-z-])' + re.escape(t) + r'(?![a-z])'
        for m in re.finditer(pat, ftext):
            hits.append((m.end() - len(t), t))
    return hits


def _find_name(text, name):
    """Capitalised token equal to the name, a >=4-char prefix of it ('Marc'), or name + 's / s."""
    hits = []
    for m in _CAP.finditer(text):
        tok = m.group(1)
        if tok == name or (len(tok) >= 4 and name.startswith(tok)) or (tok.startswith(name) and tok[len(name):] in ('s',)):
            hits.append((m.start(), tok))
    return hits


def _find_action(ftext, words, phrases):
    hits = []
    for m in _WORD.finditer(ftext):
        if m.group(0) in words:
            hits.append((m.start(), m.group(0)))
    for p in phrases:
        for m in re.finditer(p, ftext):
            hits.append((m.start(), m.group(0)))
    return hits


def bullet_features(it, text):
    """Lexical features of one bullet's scored text for its item."""
    lex = it['lex']
    ft = fold(text)
    side = {}
    for s in ('a', 'b'):
        hits = _find_name(text, lex['name'][s]) + _find_words(ft, lex['role'][s]) + _find_cjk(text, lex['role_cjk'][s])
        side[s] = sorted(hits)
    act = sorted(_find_action(ft, set(lex['action']['words']), lex['action']['phrases']) + _find_cjk(text, lex['action_cjk']))
    ag, pa = side[it['agent_side']], side[it['patient_side']]
    order = None
    if ag and pa:
        order = 'agent_first' if ag[0][0] < pa[0][0] else 'patient_first'
    dpeople = {lab: sorted(_find_words(ft, terms) + _find_cjk(text, lex['distractor_people_cjk'][lab]))
               for lab, terms in lex['distractor_people'].items()}
    dact = {a: sorted(_find_action(ft, set(v['words']), v['phrases']) + _find_cjk(text, v['cjk']))
            for a, v in lex['distractor_actions'].items()}
    return {
        'agent': [t for _, t in ag], 'patient': [t for _, t in pa], 'action': [t for _, t in act],
        'order': order,
        'distractor_people': {k: [t for _, t in v] for k, v in dpeople.items() if v},
        'distractor_actions': {k: [t for _, t in v] for k, v in dact.items() if v},
    }


# ----------------------------------------------------------------------------------------------
# 4. Judge outputs
# ----------------------------------------------------------------------------------------------
QUOTE_RE = re.compile(r'"([^"]{3,}?)"|“([^”]{3,}?)”|‘([^’]{3,}?)’')
EV_STOP = set('''the a an and or of to in on at for with by from as is are was were be been being this that
these those it its his her their they them he she him which who whom whose readout readouts describe describes
described says say said mentions mention mentioned supports support supported implies imply implied suggests
suggest option options answer answers choice choices agent patient action person people listed identify
identifies identified only does not no any clear clearly there here than then so also but because while
q1 q2 q3 cannot tell one two both other another same into about over under'''.split())


def _content_words(s):
    return [w for w in _WORD.findall(fold(s)) if w not in EV_STOP and len(w) > 2]


def choice_kinds(it, choices):
    """Per question: gold | reversed (q1 = the patient / q3 = the agent, with q1 != q3) |
    same_person (q1 and q3 name the same person; the non-gold one of the two) | distractor |
    cannot_tell | invalid."""
    agent_lab = it['label_a'] if it['agent_side'] == 'a' else it['label_b']
    patient_lab = it['label_b'] if it['agent_side'] == 'a' else it['label_a']
    kinds, labels = [], []
    for qi, c in enumerate(choices):
        opts = it['options'][qi]
        if isinstance(c, bool) or not isinstance(c, int) or not 1 <= c <= len(opts):
            kinds.append('invalid')
            labels.append(None)
            continue
        lab = opts[c - 1]
        labels.append(lab)
        if c == len(opts):
            kinds.append('cannot_tell')
        elif c == it['golds'][qi]:
            kinds.append('gold')
        elif qi == 0 and lab == patient_lab or qi == 2 and lab == agent_lab:
            kinds.append('reversed')
        else:
            kinds.append('distractor')
    if labels[0] is not None and labels[0] == labels[2] and labels[0] != CANNOT:
        for qi in (0, 2):  # one person in both roles: not a reversed binding, the other role is unresolved
            if kinds[qi] == 'reversed':
                kinds[qi] = 'same_person'
    return kinds, labels


def readout_class(kinds):
    """pass | reversed_binding (q1 and q3 both reversed) | wrong_other (any reversed or distractor) |
    partial (>=1 gold, nothing wrong) | none (all cannot tell) | invalid."""
    if all(k == 'gold' for k in kinds):
        return 'pass'
    if kinds[0] == 'reversed' and kinds[2] == 'reversed':
        return 'reversed_binding'
    if any(k in ('reversed', 'distractor') for k in kinds):
        return 'wrong_other'
    if any(k == 'gold' for k in kinds):
        return 'partial'
    if all(k in ('cannot_tell', 'same_person') for k in kinds):
        return 'none'
    return 'invalid'


def load_judgments(cond):
    """{cell_id: judge record} from cells.jsonl (raw MC answers) cross-checked with results.json rows."""
    bank = load_bank()
    base = f'{JUDGMENTS}/{cond}/{FAMILY}'
    raw = {}
    dup = 0
    with open(f'{base}/cells.jsonl') as f:
        for line in f:
            r = json.loads(line)
            if r['key'] in raw:
                dup += 1
            raw[r['key']] = r
    rows = {r['key']: r for r in json.load(open(f'{base}/results.json'))['rows']}
    texts = {}
    with open(f'{JUDGMENTS}/{cond}/{FAMILY}.readouts.jsonl') as f:
        for line in f:
            r = json.loads(line)
            texts[judge_key(r['id'], r['layer'], r['pos'])] = r['samples']
    out = {}
    for key, r in raw.items():
        m = r['meta']
        it = bank[m['id']]
        assert list(m['golds']) == it['golds'], key
        ch = [r['result'].get(f'q{i}_choice') for i in (1, 2, 3)]
        kinds, labels = choice_kinds(it, ch)
        correct = [c == g for c, g in zip(ch, it['golds'])]
        row = rows[key]
        assert row['correct'] == correct and row['pass'] == all(correct), key
        assert row['evidence'] == r['result'].get('evidence', ''), key
        ev = r['result'].get('evidence', '')
        quotes = [next(g for g in mm.groups() if g) for mm in QUOTE_RE.finditer(ev)]
        out[cell_id(m['id'], m['layer'], m['pos'])] = {
            'key': key, 'choices': ch, 'golds': it['golds'], 'choice_labels': labels, 'kinds': kinds,
            'correct': correct, 'pass': all(correct), 'readout_class': readout_class(kinds),
            'evidence': ev, 'evidence_quotes': quotes, 'judged_samples': texts.get(key),
        }
    out['__meta__'] = {'cells_jsonl_lines': len(raw) + dup, 'duplicate_keys': dup, 'results_rows': len(rows),
                       'readouts_rows': len(texts)}
    return out


# ----------------------------------------------------------------------------------------------
# 5. Bullet labels (rule RBA-v1)
# ----------------------------------------------------------------------------------------------
def _ev_overlap(ev_words, ftext):
    if not ev_words:
        return 0.0
    bw = set(_WORD.findall(ftext))
    return sum(1 for w in ev_words if w in bw) / len(ev_words)


ANCHOR_MIN_OVERLAP = 0.4


def _norm(s):
    return re.sub(r'\s+', ' ', fold(s)).strip(' .,;:')


def label_readout(it, judge, atoms):
    """Per-bullet features + labels for one readout, rule RBA-v1 (MAP.md, 'Bullet labels').

    label       hit | miss | wrong_specific | unlocated (pass readout, but no bullet can carry the
                credit) | unjudged
    label_fine  hit_strict | hit_evidence | hit_quote | hit_anchor | miss_pass_other | unlocated |
                wrong_reversed (judge reversed both roles) | wrong_reversed_partial (one role) |
                wrong_action | wrong_person | miss_wrong_readout | miss_partial | miss_none | unjudged
    component   {agent, action, patient: 'hit' | 'wrong' | None} judge-right/wrong component that
                the bullet names lexically
    """
    from bullet_attrib_lib import render_offsets
    rendered, spans = render_offsets([a['text'] for a in atoms])
    ev_words = sorted(set(_content_words(judge['evidence']))) if judge else []
    quotes = [_norm(q) for q in (judge or {}).get('evidence_quotes', [])]
    feats = []
    for a, sp in zip(atoms, spans):
        t = a['scored_text']
        f = bullet_features(it, t)
        nt = _norm(t)
        f['evidence_quotes_in_bullet'] = [q for q in quotes if len(q) >= 4 and q in nt]
        f['evidence_overlap'] = round(_ev_overlap(ev_words, fold(t)), 4)
        f['span'] = list(sp)
        f['has_vector'] = a['cache_key'] is not None
        A, P, V = bool(f['agent']), bool(f['patient']), bool(f['action'])
        f['binding'] = '+'.join(x for x, y in (('A', A), ('P', P), ('V', V)) if y) or '-'
        f['n_components'] = A + P + V
        feats.append(f)
    best = max((f['evidence_overlap'] for f in feats), default=0.0)
    for f in feats:
        f['evidence_best'] = best > 0 and f['evidence_overlap'] == best
    cls = judge['readout_class'] if judge else 'unjudged'
    kinds = judge['kinds'] if judge else [None] * 3
    picked = judge['choice_labels'] if judge else [None] * 3
    for f in feats:
        A, P, V = bool(f['agent']), bool(f['patient']), bool(f['action'])
        ev = f['evidence_best'] or bool(f['evidence_quotes_in_bullet'])
        label, fine, reasons = 'miss', None, []
        if judge is None:
            label, fine, reasons = 'unjudged', 'unjudged', ['unjudged']
        elif cls == 'pass':
            if A and P and V:
                label, fine, reasons = 'hit', 'hit_strict', ['pass:A+P+V']
            elif f['n_components'] >= 2 and ev:
                label, fine, reasons = 'hit', 'hit_evidence', [f'pass:{f["binding"]}+evidence']
            elif f['evidence_quotes_in_bullet']:
                label, fine, reasons = 'hit', 'hit_quote', [f'pass:evidence-quote({f["binding"]})']
        else:
            # direction is not readable lexically, so a reversal is put only on the bullet(s) the
            # judge's evidence text points at (best overlap or a verbatim evidence quote)
            r1, r3 = kinds[0] == 'reversed', kinds[2] == 'reversed'
            if r1 and r3 and A and P and ev:
                reasons.append('reversed:A+P+evidence')     # judge read the full reversed binding
            elif r1 and not r3 and P and ev:
                reasons.append('reversed_q1:P+evidence')    # judge took the patient as the agent
            elif r3 and not r1 and A and ev:
                reasons.append('reversed_q3:A+evidence')    # judge took the agent as the patient
            if kinds[1] == 'distractor' and picked[1] in f['distractor_actions']:
                reasons.append(f'wrong_action:{picked[1]}')
            for qi in (0, 2):
                if kinds[qi] == 'distractor' and picked[qi] in f['distractor_people']:
                    reasons.append(f'wrong_person:q{qi + 1}:{picked[qi]}')
            if reasons:
                label = 'wrong_specific'
                fine = ('wrong_reversed' if reasons[0].startswith('reversed:') else
                        'wrong_reversed_partial' if reasons[0].startswith('reversed_q') else
                        'wrong_action' if reasons[0].startswith('wrong_action') else 'wrong_person')
            elif cls in ('reversed_binding', 'wrong_other'):
                fine, reasons = 'miss_wrong_readout', [f'{cls}:no-wrong-content({f["binding"]})']
            else:
                fine, reasons = f'miss_{cls}', [cls]
        f['label'], f['label_fine'], f['label_reasons'] = label, fine, reasons
        comp = {}
        for qi, name, present, wrong_present in ((0, 'agent', A, P), (1, 'action', V, False), (2, 'patient', P, A)):
            k = kinds[qi]
            comp[name] = 'hit' if (k == 'gold' and present) else ('wrong' if (k == 'reversed' and wrong_present) else None)
        if judge is not None and kinds[1] == 'distractor' and picked[1] in f['distractor_actions']:
            comp['action'] = 'wrong'
        for qi, name in ((0, 'agent'), (2, 'patient')):
            if judge is not None and kinds[qi] == 'distractor' and picked[qi] in f['distractor_people']:
                comp[name] = 'wrong'
        f['component'] = comp
    if cls == 'pass':
        if not any(f['label'] == 'hit' for f in feats):
            # fallback: the bullet(s) the judge's evidence text overlaps most, if it names >=1 component
            for f in feats:
                if f['evidence_best'] and f['evidence_overlap'] >= ANCHOR_MIN_OVERLAP and f['n_components'] >= 1:
                    f['label'], f['label_fine'] = 'hit', 'hit_anchor'
                    f['label_reasons'] = [f'pass:evidence-anchor({f["binding"]})']
        located = any(f['label'] == 'hit' for f in feats)
        for f in feats:
            if f['label'] == 'miss':
                if located:
                    f['label_fine'], f['label_reasons'] = 'miss_pass_other', [f'pass:other-bullet({f["binding"]})']
                else:
                    f['label'], f['label_fine'] = 'unlocated', 'unlocated'
                    f['label_reasons'] = [f'pass:unlocated({f["binding"]})']
    # sensitivity variant: in a passing readout every bullet naming >=2 of agent/action/patient is a hit
    relaxed = [cls == 'pass' and (f['label'] == 'hit' or f['n_components'] >= 2) for f in feats]
    for f, rh in zip(feats, relaxed):
        if rh:
            f['label_relaxed'] = 'hit'
        elif cls == 'pass':
            f['label_relaxed'] = 'miss' if any(relaxed) else 'unlocated'
        else:
            f['label_relaxed'] = f['label']
    return rendered, feats


# ----------------------------------------------------------------------------------------------
# 6. Joined iterator
# ----------------------------------------------------------------------------------------------
def iter_extract(path=EXTRACT, cells=None):
    want = set(cells) if cells else None
    with open(path) as f:
        for line in f:
            if want is not None:
                cid = line[13:line.index('"', 13)]
                if cid not in want:
                    continue
            yield json.loads(line)


def iter_cells(cells=None, judgments=None):
    """Yield extract rows with per setting: 'judge' (or None for empty readouts) and 'bullets'
    (atoms + features + labels, in emitted order) and 'rendered' (== judged text)."""
    bank = load_bank()
    judgments = judgments or {cond: load_judgments(cond) for cond in SETTINGS}
    for row in iter_extract(cells=cells):
        it = bank[row['item_id']]
        row['pair_id'], row['direction'], row['stereotypicality'] = it['pair_id'], it['direction'], it['stereotypicality']
        for cond, s in row['settings'].items():
            j = judgments[cond].get(row['cell_id'])
            rendered, feats = label_readout(it, j, s['atoms'])
            s['judge'] = j
            s['rendered'] = rendered
            s['bullets'] = [dict(phrase_id=a['source_phrase_id'], cache_key=a['cache_key'], text=a['scored_text'],
                                 coefficient=(s['coefficients'] or [None] * len(s['atoms']))[i], **f)
                            for i, (a, f) in enumerate(zip(s['atoms'], feats))]
        yield row


# ----------------------------------------------------------------------------------------------
# 7. Self test and examples
# ----------------------------------------------------------------------------------------------
def selftest():
    """Every join and identity check over all 3 x 11,400 readouts; label tallies -> DATA/selftest.json.
    Raises AssertionError on any failed check."""
    t0 = time.time()
    bank = load_bank()  # asserts the option-list port == wsbench golden for all 100 items
    res = collections.OrderedDict()
    res['bank_items'] = len(bank)
    res['options_port_equals_golden'] = True
    js = {cond: load_judgments(cond) for cond in SETTINGS}  # asserts golds/correct/pass/evidence == results.json
    res['judgment_files'] = {cond: j.pop('__meta__') for cond, j in js.items()}
    st = collections.Counter()
    for cond in SETTINGS:
        for k in ('render_mismatch', 'judged_text_mismatch', 'no_judgment', 'empty_readout', 'no_exact_fit',
                  'atoms_without_vector', 'readouts_with_atom_without_vector', 'same_person_readouts',
                  'span_slice_mismatch'):
            st[f'{k}[{cond}]'] = 0
    labels, fine, relaxed, reasons, comp, cls_n, located = (collections.Counter() for _ in range(7))
    item_pass = collections.defaultdict(set)
    fve = collections.defaultdict(list)
    for row in iter_cells(judgments=js):
        st['cells'] += 1
        st[f'cells[{row["split"]}]'] += 1
        st[f'cells[L{row["layer"]}]'] += 1
        for cond, s in row['settings'].items():
            j = s['judge']
            if s['fve'] is not None:
                fve[cond].append(s['fve'])
            else:
                st[f'no_exact_fit[{cond}]'] += 1
            nv = sum(1 for b in s['bullets'] if not b['has_vector'])
            st[f'atoms_without_vector[{cond}]'] += nv
            st[f'readouts_with_atom_without_vector[{cond}]'] += nv > 0
            if s['rendered'] != s['text']:
                st[f'render_mismatch[{cond}]'] += 1
            for b, a in zip(s['bullets'], s['atoms']):
                if s['text'][b['span'][0]:b['span'][1]] != a['text']:
                    st[f'span_slice_mismatch[{cond}]'] += 1
            if not s['atoms']:
                st[f'empty_readout[{cond}]'] += 1
            if j is None:
                st[f'no_judgment[{cond}]'] += 1
                continue
            if j['judged_samples'] is None or j['judged_samples'] != [s['text']]:
                st[f'judged_text_mismatch[{cond}]'] += 1
            st[f'same_person_readouts[{cond}]'] += 'same_person' in j['kinds']
            cls_n[(cond, j['readout_class'])] += 1
            if j['pass']:
                item_pass[cond].add(row['item_id'])
                located[(cond, any(b['label'] == 'hit' for b in s['bullets']))] += 1
            for b in s['bullets']:
                labels[(cond, b['label'])] += 1
                fine[(cond, b['label_fine'])] += 1
                relaxed[(cond, b['label_relaxed'])] += 1
                for r in b['label_reasons']:
                    reasons[(cond, re.sub(r'(:q\d)?:[^:(]*$', '', r) if r.startswith(('wrong_action', 'wrong_person')) else re.sub(r'\(.*\)$', '', r))] += 1
                for k, v in b['component'].items():
                    if v:
                        comp[(cond, k, v)] += 1
    for cond in SETTINGS:
        for k in ('render_mismatch', 'judged_text_mismatch', 'no_judgment', 'span_slice_mismatch'):
            assert st[f'{k}[{cond}]'] == 0, (k, cond, st[f'{k}[{cond}]'])
    assert st['cells'] == 11400
    res['counts'] = dict(sorted(st.items()))
    res['items_passing'] = {c: len(v) for c, v in item_pass.items()}
    res['mean_fve'] = {c: sum(v) / len(v) for c, v in fve.items()}
    res['n_fve'] = {c: len(v) for c, v in fve.items()}
    res['readout_class'] = {f'{c}|{k}': v for (c, k), v in sorted(cls_n.items())}
    res['pass_readouts_with_located_hit'] = {f'{c}|{k}': v for (c, k), v in sorted(located.items())}
    res['bullet_labels'] = {f'{c}|{k}': v for (c, k), v in sorted(labels.items())}
    res['bullet_labels_fine'] = {f'{c}|{k}': v for (c, k), v in sorted(fine.items())}
    res['bullet_labels_relaxed'] = {f'{c}|{k}': v for (c, k), v in sorted(relaxed.items())}
    res['bullet_label_reasons'] = {f'{c}|{k}': v for (c, k), v in sorted(reasons.items())}
    res['component_labels'] = {f'{c}|{k}|{v}': n for (c, k, v), n in sorted(comp.items())}
    res['seconds'] = round(time.time() - t0, 1)
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / 'selftest.json').write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))


def show(cid, conds=None):
    for row in iter_cells(cells=[cid]):
        it = load_bank()[row['item_id']]
        print(f"== {cid}  split={row['split']} token={row['token']!r}  gold: {it['gold_label']}  "
              f"(names a={it['names']['a']} b={it['names']['b']}, direction {it['direction']})")
        for cond, s in row['settings'].items():
            if conds and cond not in conds:
                continue
            j = s['judge']
            print(f"-- {SETTINGS[cond][2]} [{cond}] fve={s['fve']}")
            if j:
                print(f"   judge: choices={j['choices']} golds={j['golds']} kinds={j['kinds']} class={j['readout_class']}")
                print(f"   picked: {j['choice_labels']}")
                print(f"   evidence: {j['evidence']}")
            for i, b in enumerate(s['bullets']):
                print(f"   [{i}] {b['label']:<14} fine={b['label_fine']} relaxed={b['label_relaxed']} {b['label_reasons']} A={b['agent']} P={b['patient']} V={b['action']} "
                      f"order={b['order']} ev={b['evidence_overlap']}{'*' if b.get('evidence_best') else ''} "
                      f"dP={b['distractor_people']} dA={b['distractor_actions']} coef={b['coefficient']}")
                print(f"       {b['text']!r}")


EXAMPLE_SEED = 20261015


def examples(k=5):
    """5 cells per setting: 2 pass, 1 reversed/wrong, 1 partial, 1 none (stratified, fixed seed)."""
    js = {cond: load_judgments(cond) for cond in SETTINGS}
    for j in js.values():
        j.pop('__meta__', None)
    rng = random.Random(EXAMPLE_SEED)
    picks = {}
    for cond, j in js.items():
        by = collections.defaultdict(list)
        for cid, r in sorted(j.items()):
            by[r['readout_class']].append(cid)
        sel = rng.sample(by['pass'], 2) + rng.sample(by['reversed_binding'] + by['wrong_other'], 1) + \
            rng.sample(by['partial'], 1) + rng.sample(by['none'], 1)
        picks[cond] = sel[:k]
    for cond, cids in picks.items():
        for cid in cids:
            show(cid, conds=[cond])
    return picks


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'selftest'
    if cmd == 'extract':
        extract()
    elif cmd == 'selftest':
        selftest()
    elif cmd == 'show':
        show(sys.argv[2], sys.argv[3:] or None)
    elif cmd == 'examples':
        print(json.dumps(examples()))
    else:
        raise SystemExit(__doc__)
