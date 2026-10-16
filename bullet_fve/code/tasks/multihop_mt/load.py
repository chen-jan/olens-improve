"""Loader + bullet labels for WorkspaceBench "Multihop (multi-token)" (family id multihop_mt).

One row per (cell, setting): the frozen full-grid selection (atoms, cache keys, saved exact NNLS
fit), the expansion judge's own verdict for that readout, and a label for every bullet.

The multihop_mt "judge" is NOT an LLM: it is the deterministic regex scorer of record
(wsbench.multitoken.regex, scorer_version mt-regex-2026-09-23, judge_model 'regex', $0). So a
bullet can be labelled with exactly the judge's rule by running the same scorer on the bullet
alone, and the readout-level verdict is reproduced by the union of its bullets (checked below).

Bullet labels (primary = the judge's strict rule on the REQUIRED bridge units):
  hit             the bullet alone hits >=1 required bridge unit (strict, scorer forms only)
  wrong-specific  no strict and no lenient hit of any required unit, but the bullet names >=1 of
                  the bank's MC distractors for a required unit (item['mc'][role]['distractors'])
  miss            everything else
Secondary flags per bullet: per-role strict hits + matched forms, lenient hits (all authored forms
incl. single-token ones + the bank's bridge 'answers' + mc gold), near_hit (lenient but not strict),
target_hit (optional final-answer unit, strict / lenient), distractors named, and whether each
strict hit lies inside the 32-token scored prefix that the AR vector actually encodes.

READ-ONLY on project data. Inputs: tasks/multihop_mt/inputs/multihop_mt_three_settings.jsonl
(built by extract_family.py from the frozen selections).

Usage:
  python -B load.py verify            # all joins / reproductions (asserts), prints counts
  python -B load.py examples [N]      # N cells per setting with verbatim bullets and labels
  python -B load.py write OUT.jsonl   # one labelled row per (cell, setting)
"""
import collections
import hashlib
import importlib.util
import json
import random
import sys
from pathlib import Path

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
TASK = ROOT / 'tasks/multihop_mt'
INPUTS = TASK / 'inputs'
FAMILY = 'multihop_mt'
DISPLAY = 'Multihop (multi-token)'
SETTINGS = {  # expansion condition id -> display name (olens-improve AGENTS.md / build_expansion_dashboard.py)
    'capped_n1-n1': 'Original, capped to four bullets',
    'best_n_exact-n32': 'Choose the best complete readout (32 samples)',
    'pooled_greedy_swap-n32': 'Combine original bullets (32 samples)',
}
SHORT = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32', 'pooled_greedy_swap-n32': 'Combine 32'}
WB = Path('${OLENS_SOURCE_ROOT}/scratch/repos/workspace-bench-v2')
BANK = WB / 'evals/multihop_mt/items.json'
REGEX_PY = WB / 'src/wsbench/multitoken/regex.py'
PINNED = {  # configs/test_hall_review_v1.json + configs/test_chain_multihop_review_v1.json (olens-improve)
    str(REGEX_PY): '71141736467231c2ad8d75900d1d67226b08c22752f62a7fcd2ef070622e0529',
    str(BANK): '8f34a6c5852e20c4c7b284eb8ca2055135ac32eb25a88931a27968e3d0704fb1',
}
JUDGMENTS = Path('${OLENS_DATA_ROOT}/expansion-v1/judgments')
TOKENIZER = ('${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/snapshots/'
             '6a9e13bd6fc8f0983b9b99948120bc37f49c13e9')

sys.path.insert(0, str(ROOT / 'code'))
from bullet_attrib_lib import render_offsets  # noqa: E402  (same render convention as the Hallucination study)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_regex():
    """The pinned scorer module, loaded by file path (no wsbench package import), hash-checked."""
    assert _sha(REGEX_PY) == PINNED[str(REGEX_PY)], 'regex.py differs from the pinned scorer'
    spec = importlib.util.spec_from_file_location('wsbench_mt_regex_pinned', REGEX_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.SCORER_VERSION == 'mt-regex-2026-09-23'
    return mod


RX = load_regex()


def _dedup(xs):
    out = []
    for x in xs:
        if x not in out:
            out.append(x)
    return out


def load_bank():
    """item_id -> spec: prompt, target, subfamily, intermediates, strict scored units (the judge's
    own, via RX.scored_units), lenient alias lists, MC distractors, matchers."""
    assert _sha(BANK) == PINNED[str(BANK)], 'items.json differs from the pinned bank'
    bank = json.loads(BANK.read_text())
    contract = RX.contract_for(bank, str(bank.get('family', FAMILY)))
    out = {}
    for it in bank['items']:
        units = RX.scored_units(it, contract)
        required = [u.role for u in units if u.required]
        lenient = {}
        for raw in it['units']:
            role = raw['role']
            forms = [f for fs in raw['forms'].values() for f in fs]
            answers = [a for b in it.get('bridges', []) if role in b['units'] for a in b['answers']]
            gold = [(it.get('mc') or {}).get(role, {}).get('gold')] if role in (it.get('mc') or {}) else []
            lenient[role] = _dedup([*forms, *answers, *[g for g in gold if g]])
        lenient['target'] = _dedup([it['target'], *it.get('target_alts', [])])
        mc_distractors = {role: list(b['distractors']) for role, b in (it.get('mc') or {}).items()}
        strict_forms = {f for u in units for f in u.all_forms()}
        strict_by_role = {u.role: [RX.unicode_word_matcher(f) for f in u.all_forms()] for u in units}
        len_by_role = {r: [RX.unicode_word_matcher(f) for f in fs] for r, fs in lenient.items()}
        # (1) Effective wrong values. In 3-hop items the MC distractors of one bridge include the
        # OTHER bridge's gold (e.g. bridge1 distractor 'Juan Sebastián Elcano' = bridge2 gold);
        # naming it is correct content, not a wrong value. Drop a distractor when any strict form
        # (any role, incl. the optional target) or a lenient alias of ANOTHER role fires on it.
        distractors, distractors_removed = {}, {}
        for role, ds in mc_distractors.items():
            keep = []
            for d in ds:
                cross = any(m(d) for ms in strict_by_role.values() for m in ms) or any(
                    m(d) for r, ms in len_by_role.items() if r != role for m in ms)
                (distractors_removed.setdefault(role, []) if cross else keep).append(d)
            distractors[role] = keep
        # (2) A non-strict lenient alias that would also fire on an effective distractor (bare
        # 'Brontë' inside 'Emily Brontë' when the gold is Charlotte Brontë) is ambiguous: drop it.
        # Strict (scorer) forms are never dropped.
        all_distr = [d for ds in distractors.values() for d in ds]
        lenient_dropped = {}
        for role, fs in lenient.items():
            keep = []
            for f in fs:
                m = RX.unicode_word_matcher(f)
                if f not in strict_forms and any(m(d) for d in all_distr):
                    lenient_dropped.setdefault(role, []).append(f)
                else:
                    keep.append(f)
            lenient[role] = keep
        spec = {
            'item_id': it['name'], 'subfamily': it['subfamily'], 'prompt': it['prompt'],
            'target': it['target'], 'target_alts': it.get('target_alts', []),
            'intermediates': it.get('intermediates', []), 'required_roles': required,
            'strict_units': [u.to_json() for u in units],
            'lenient': lenient, 'lenient_dropped': lenient_dropped, 'distractors': distractors,
            'distractors_removed_cross_role': distractors_removed,
            '_units': units,
            '_strict_m': {u.role: [(f, RX.unicode_word_matcher(f)) for f in u.all_forms()] for u in units},
            '_lenient_m': {r: [(f, RX.unicode_word_matcher(f)) for f in fs] for r, fs in lenient.items()},
            '_distr_m': {r: [(f, RX.unicode_word_matcher(f)) for f in fs] for r, fs in distractors.items()},
        }
        out[it['name']] = spec
    return out


def _matched(matchers, text):
    return [f for f, m in matchers if m(text)]


def label_text(text, spec, scored_prefix=None):
    """Label one bullet (or any text) with the judge's rule. `text` is the bullet body as rendered
    in the judged readout; `scored_prefix` = decode(scored_token_ids) when the atom was truncated."""
    sample = RX.extract_phrase(text)
    strict = {role: _matched(ms, sample) for role, ms in spec['_strict_m'].items()}
    lenient = {role: _matched(ms, sample) for role, ms in spec['_lenient_m'].items()}
    distr = {role: _matched(ms, sample) for role, ms in spec['_distr_m'].items()}
    req = spec['required_roles']
    strict_req = [r for r in req if strict.get(r)]
    lenient_req = [r for r in req if lenient.get(r)]
    distr_req = [r for r in req if distr.get(r)]
    if strict_req:
        label = 'hit'
    elif not lenient_req and distr_req:
        label = 'wrong-specific'
    else:
        label = 'miss'
    rec = {
        'label': label,
        'label_lenient': 'hit' if lenient_req else label,
        'near_hit': bool(lenient_req) and not strict_req,
        'strict_roles': strict_req,
        'strict_forms': {r: strict[r] for r in strict if strict[r]},
        'lenient_roles': lenient_req,
        'lenient_forms': {r: lenient[r] for r in lenient if lenient[r]},
        'distractor_roles': distr_req,
        'distractors_named': {r: distr[r] for r in distr if distr[r]},
        'target_hit_strict': bool(strict.get('target')),
        'target_hit_lenient': bool(lenient.get('target')),
        'hedge': any(strict.get(r) and distr.get(r) for r in req),  # same role: gold AND a wrong value
    }
    if scored_prefix is not None:
        p = RX.extract_phrase(scored_prefix)
        rec['strict_roles_in_scored_prefix'] = [r for r in strict_req if _matched(spec['_strict_m'][r], p)]
        rec['target_hit_strict_in_scored_prefix'] = bool(_matched(spec['_strict_m'].get('target', []), p))
    else:
        rec['strict_roles_in_scored_prefix'] = list(strict_req)
        rec['target_hit_strict_in_scored_prefix'] = rec['target_hit_strict']
    return rec


def load_cells(path=None):
    """Yield the extracted cells (one per item x layer; 1,100) with the three settings."""
    with open(path or INPUTS / f'{FAMILY}_three_settings.jsonl') as fh:
        for line in fh:
            yield json.loads(line)


def load_judgments(cond):
    """(item_id, layer, pos) -> judged text, per-role unit hits, cell pass, item pass.
    Sources: <cond>/multihop_mt.readouts.jsonl (what was scored), <cond>/multihop_mt/results.json
    (per item x layer unit hits), <cond>/multihop_mt/project_contract.json (cell pass)."""
    base = JUDGMENTS / cond
    texts = {}
    with open(base / f'{FAMILY}.readouts.jsonl') as fh:
        for line in fh:
            r = json.loads(line)
            assert len(r['samples']) == 1
            texts[(r['id'], r['layer'], r['pos'])] = r['samples'][0]
    res = json.loads((base / FAMILY / 'results.json').read_text())
    assert res['config']['scorer_version'] == RX.SCORER_VERSION and res['config']['judge_model'] == 'regex'
    contract = json.loads((base / FAMILY / 'project_contract.json').read_text())
    cell_pass = {(r['item_id'], r['layer'], r['position']): r['pass'] for r in contract['cell_diagnostic']['rows']}
    pos_of = {(i, l): p for (i, l, p) in texts}
    out = {}
    for row in res['rows']:
        for L, v in row['layers'].items():
            key = (row['id'], int(L), pos_of[(row['id'], int(L))])
            out[key] = {
                'judged_text': texts[key], 'unit_hits': v['hits'], 'empty': v['empty'],
                'required_roles': row['roles'], 'optional_roles': row['optional_roles'],
                'cell_pass': cell_pass[key], 'item_pass': row['pass'], 'item_passing_layers': row['passing_layers'],
            }
    assert set(out) == set(texts) == set(cell_pass)
    meta = {'numbers': res['numbers'], 'cell_diagnostic': {k: v for k, v in contract['cell_diagnostic'].items() if k != 'rows'}}
    return out, meta


_TOK = None


def tokenizer():
    global _TOK
    if _TOK is None:
        from transformers import AutoTokenizer
        _TOK = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)
    return _TOK


def iter_rows(bank=None, judgments=None, with_prefix=True):
    """One labelled row per (cell, setting). Bullet order = phrase_ids order = fit order."""
    bank = bank or load_bank()
    judgments = judgments or {c: load_judgments(c)[0] for c in SETTINGS}
    tok = tokenizer() if with_prefix else None
    for cell in load_cells():
        spec = bank[cell['item_id']]
        key = (cell['item_id'], cell['layer'], cell['position'])
        for cond in SETTINGS:
            s = cell['settings'][cond]
            j = judgments[cond][key]
            text, spans = render_offsets([a['text'] for a in s['atoms']])
            bullets = []
            for i, (a, (st, en), coef) in enumerate(zip(s['atoms'], spans, s['coefficients'])):
                prefix = tok.decode(a['scored_token_ids']) if (with_prefix and a['truncated']) else None
                lab = label_text(a['text'], spec, prefix)
                bullets.append({'index': i, 'phrase_id': a['source_phrase_id'], 'cache_key': a['cache_key'],
                                'sample_index': a['sample_index'], 'text': a['text'], 'char_span': [st, en],
                                'truncated': a['truncated'], 'saved_coefficient': coef, **lab})
            yield {
                'cell_id': cell['cell_id'], 'item_id': cell['item_id'], 'group_id': cell['group_id'],
                'layer': cell['layer'], 'position': cell['position'], 'split': cell['split'],
                'subfamily': spec['subfamily'], 'setting': cond, 'setting_display': SETTINGS[cond],
                'text': s['text'], 'rendered_text': text, 'fve': s['fve'], 'bullet_count': s['bullet_count'],
                'judge': {k: j[k] for k in ('unit_hits', 'required_roles', 'optional_roles', 'cell_pass',
                                            'item_pass', 'item_passing_layers', 'empty')},
                'judged_text_equals_selection': j['judged_text'] == s['text'],
                'bullets': bullets,
            }


def verify():
    bank = load_bank()
    js, metas = {}, {}
    for c in SETTINGS:
        js[c], metas[c] = load_judgments(c)
    st = collections.Counter()
    item_layers = collections.defaultdict(dict)
    overlap = []
    for iid, spec in bank.items():  # distractor / gold ambiguity in the bank itself
        for role, ms in spec['_distr_m'].items():
            for d, m in ms:
                for g in spec['lenient'][role]:
                    if m(g) or any(mm(d) for _, mm in spec['_lenient_m'][role]):
                        overlap.append((iid, role, d, g))
        for role, ms in spec['_strict_m'].items():
            if any(m(spec['prompt']) for _, m in ms):
                st[f'strict_form_in_prompt[{role}]'] += 1
        for role, ms in spec['_distr_m'].items():
            if any(m(spec['prompt']) for _, m in ms):
                st[f'distractor_in_prompt[{role}]'] += 1
    for row in iter_rows(bank, js):
        cond = row['setting']
        st[f'readouts[{cond}]'] += 1
        assert row['rendered_text'] == row['text'], row['cell_id']
        assert row['judged_text_equals_selection'], (row['cell_id'], cond)
        j = row['judge']
        roles_all = j['required_roles'] + j['optional_roles']
        # 1) union of per-bullet strict hits == the judge's per-unit verdict on the whole readout
        for role in roles_all:
            judge_hit = bool(j['unit_hits'].get(role))
            union = any(role in b['strict_roles'] or (role == 'target' and b['target_hit_strict'])
                        for b in row['bullets'])
            st[f'unit_union_{"ok" if judge_hit == union else "MISMATCH"}'] += 1
            if judge_hit != union:
                print('MISMATCH', row['cell_id'], cond, role, judge_hit, union)
        # 2) recompute cell pass from bullets
        cell_pass = all(any(r in b['strict_roles'] for b in row['bullets']) for r in j['required_roles'])
        st['cell_pass_' + ('ok' if cell_pass == j['cell_pass'] else 'MISMATCH')] += 1
        item_layers[(cond, row['item_id'])][row['layer']] = (cell_pass, j['item_pass'])
        st[f'cell_pass[{cond}]'] += cell_pass
        for b in row['bullets']:
            st[f'bullets[{cond}]'] += 1
            st[f'label={b["label"]}[{cond}]'] += 1
            st[f'label_lenient={b["label_lenient"]}[{cond}]'] += 1
            st[f'near_hit[{cond}]'] += b['near_hit']
            st[f'target_hit_strict[{cond}]'] += b['target_hit_strict']
            st[f'hedge[{cond}]'] += b['hedge']
            if b['label'] == 'hit' and set(b['strict_roles_in_scored_prefix']) != set(b['strict_roles']):
                st[f'hit_outside_scored_prefix[{cond}]'] += 1
            if b['label'] == 'hit' and not b['strict_roles_in_scored_prefix']:
                st[f'hit_entirely_outside_scored_prefix[{cond}]'] += 1
        n_hit = sum(b['label'] == 'hit' for b in row['bullets'])
        st[f'readouts_with_{min(n_hit, 2)}{"+" if n_hit >= 2 else ""}_hit_bullets[{cond}]'] += 1
    # 3) item-level pass (any layer) reproduces the reported question-level rate (34/40/41 of 100)
    item_pass = collections.Counter()
    for (cond, iid), layers in item_layers.items():
        reps = {v[1] for v in layers.values()}
        assert len(reps) == 1 and len(layers) == 11, (cond, iid)
        rep = reps.pop()
        mine = any(v[0] for v in layers.values())
        st['item_pass_' + ('ok' if mine == rep else 'MISMATCH')] += 1
        item_pass[cond] += mine
    for c in SETTINGS:
        assert abs(item_pass[c] / 100 - metas[c]['numbers']['value']) < 1e-12, (c, item_pass[c])
        assert st[f'cell_pass[{c}]'] == metas[c]['cell_diagnostic']['passed_cells'], c
    assert not any('MISMATCH' in k for k in st), {k: v for k, v in st.items() if 'MISMATCH' in k}
    summary = {'counts': dict(sorted(st.items())), 'item_pass_of_100': dict(item_pass),
               'reported': {c: {'item_pass_rate': metas[c]['numbers']['value'],
                                'cell_passed': metas[c]['cell_diagnostic']['passed_cells']} for c in SETTINGS},
               'distractor_gold_overlaps': overlap}
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return summary


def examples(n=5, seed=0):
    """n cells per setting, stratified: pass readouts first, then wrong-specific / near-hit / miss."""
    rows = list(iter_rows())
    rng = random.Random(seed)
    for cond in SETTINGS:
        rs = [r for r in rows if r['setting'] == cond]
        buckets = [
            [r for r in rs if r['judge']['cell_pass']],
            [r for r in rs if not r['judge']['cell_pass'] and any(b['strict_roles'] for b in r['bullets'])],
            [r for r in rs if any(b['label'] == 'wrong-specific' for b in r['bullets'])],
            [r for r in rs if any(b['near_hit'] for b in r['bullets'])],
            [r for r in rs if all(b['label'] == 'miss' and not b['near_hit'] for b in r['bullets'])],
        ]
        print(f'===== {SHORT[cond]} = {cond}')
        for bucket in buckets[:n]:
            r = rng.choice(bucket)
            print(f'--- {r["cell_id"]} split={r["split"]} fve={r["fve"]:.4f} judge cell_pass={r["judge"]["cell_pass"]} '
                  f'unit_hits={json.dumps(r["judge"]["unit_hits"])} required={r["judge"]["required_roles"]}')
            for b in r['bullets']:
                extra = {k: b[k] for k in ('strict_forms', 'lenient_forms', 'distractors_named') if b[k]}
                print(f'  [{b["index"]}] {b["label"]:<14} near={int(b["near_hit"])} tgt={int(b["target_hit_strict"])} '
                      f'trunc={int(b["truncated"])} {json.dumps(b["text"].strip(), ensure_ascii=False)} {json.dumps(extra, ensure_ascii=False)}')


def write(path):
    with open(path, 'w') as out:
        for r in iter_rows():
            out.write(json.dumps(r, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    if cmd == 'verify':
        verify()
    elif cmd == 'examples':
        examples(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
    elif cmd == 'write':
        write(sys.argv[2])
    else:
        raise SystemExit(__doc__)
