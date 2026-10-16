"""Chained intermediates (WorkspaceBench `chain_intermediates`): loader + bullet labels for the
per-bullet FVE study (generalises code/extract_hall.py and code/bullet_attrib_lib.py).

READ-ONLY on project data. Writes only into this directory (tasks/chain_intermediates/).
No judge/API calls: labels come from the saved judge records of the expanded run.

Python: ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B
        (PYTHONPATH=${OLENS_REPO_ROOT}/src)

Subcommands
  extract     stream the 3 frozen full-grid selector outputs -> chain_three_settings.jsonl,
              chain_vector_index.json, extract_summary.json. Same per-line schema as
              inputs/hall_three_settings.jsonl; the unchanged code/metrics_job.py runs on it via
              metrics_chain.py (symlinks in metrics_inputs/). Parses ~1,000 vector index JSONs:
              run under srun.
  verify_fve  recompute joint FVE (JointNNLS.from_raw, scipy_exact) for one cell per layer x
              3 settings from raw AR vectors + activation row + whitener; 11 eighs: run under srun.
  labels      join judge records (cells.jsonl, readouts.jsonl, results.json) + item bank ->
              chain_bullet_labels.jsonl, labels_summary.json. Light (seconds).
  check       self-tests (asserts) over the label file and the joins.
  examples    print verification cells (default 5 per setting) with bullets, quotes and labels.
  show        python -B load.py show <cell_id> <setting>   (one labelled readout)

Label columns (label / label_anchor / label_contains / label_named / label_stated): see
label_bullet, anchors_for and MAP.md section 5.

Library use:  import load as L;  for cell in L.iter_labelled(): ...
"""
from __future__ import annotations

import collections
import hashlib
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
FAMILY = 'chain_intermediates'
D = Path('${OLENS_DATA_ROOT}')
C = Path('${OLENS_COMPUTE_ROOT}')
BENCH = Path('${OLENS_SOURCE_ROOT}/scratch/repos/workspace-bench-v2')
BENCH_COMMIT = '92d763e722377f5bfae045e829a308ab5919a820'  # olens_improve.data.BENCH_COMMIT
BANK = BENCH / 'evals' / FAMILY / 'items.json'            # unchanged vs BENCH_COMMIT (git diff empty)
SELECTIONS = {
    'development': D / 'selections/development-full-grid-v4/merged/selections.jsonl',
    'validation': D / 'selections/validation-full-grid-v1/merged/selections.jsonl',
    'test': D / 'selections/test-full-grid-v1/merged/selections.jsonl',
}
CACHES = {  # the cache each stage's selector used (configs/expansion_manifest_v1.json stages.*.vector_cache)
    'development': C / 'vectors/shared-global-v1/a451cf49d28ac7447722',
    'validation': C / 'vectors/validation-catalog-v1',
    'test': C / 'vectors/test-catalog-v1',
}
FRESH = C / 'activations/core-v1/fresh_manifest_v2.json'
ACTS = C / 'activations/core-v1/activations.safetensors'
WHITENERS = C / ('cache/huggingface/hub/datasets--agu18dec--local-workspace/snapshots/'
                 '5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners')
CACHED_V2 = D / f'expansion-v1/selections/cached-v2/{FAMILY}.jsonl'
JUDGMENTS = D / 'expansion-v1/judgments'
CONTRACT = 'a451cf49d28ac74477229e74dfc738e51b8961b5376c688fd9e40abbd8c133b6'
LAYERS = list(range(20, 61, 4))  # olens_improve.data.LAYERS['chain_intermediates']
WANT = {('capped_n1', 1): 'capped_n1-n1', ('best_n_exact', 32): 'best_n_exact-n32',
        ('pooled_greedy_swap', 32): 'pooled_greedy_swap-n32'}
SETTINGS = tuple(WANT.values())
DISPLAY = {'capped_n1-n1': 'Original', 'best_n_exact-n32': 'Best of 32',
           'pooled_greedy_swap-n32': 'Combine 32'}
PREFIX = b'{"cell_id": "chain_intermediates|'
ATOM_KEEP = ('source_phrase_id', 'sample_index', 'text', 'scored_text', 'cache_key', 'status',
             'original_token_count', 'scored_token_count', 'truncated', 'scored_token_ids',
             'unscored_suffix_ids', 'parser_flags', 'span_start', 'span_end')

EXTRACT = HERE / 'chain_three_settings.jsonl'
VINDEX = HERE / 'chain_vector_index.json'
EXTRACT_SUMMARY = HERE / 'extract_summary.json'
LABELS = HERE / 'chain_bullet_labels.jsonl'
LABELS_SUMMARY = HERE / 'labels_summary.json'
VERIFY_FVE = HERE / 'verify_fve.json'

# ----------------------------------------------------------------------------------------------
# Mirror of the pinned judge's verification helpers (BENCH_COMMIT):
#   src/wsbench/mc.py fold; src/wsbench/family.py quote_in;
#   src/wsbench/evals/chain_intermediates/judge.py near_set, names_number, verdict; prompts.py NEAR,
#   MAX_VALUES. `labels` re-derives every readout's kind with these and asserts equality with the
#   saved results.json kind_by_layer / named_by_layer.
# ----------------------------------------------------------------------------------------------
NEAR = 3
MAX_VALUES = 3


def fold(s: str) -> str:
    s = unicodedata.normalize('NFKD', s)
    for a, b in (('‘', "'"), ('’', "'"), ('“', '"'), ('”', '"')):
        s = s.replace(a, b)
    return ''.join(c for c in s if not unicodedata.combining(c)).casefold()


def quote_in(quote: str, text: str) -> bool:
    q = fold(quote.strip())
    return bool(q) and q in fold(text)


def names_number(n: int, text: str) -> bool:
    """`n` appears in `text` as a whole number (not inside 10, 2019 or 10.83)."""
    return re.search(rf'(?<!\d)(?<!\d\.){n}(?!\d)(?!\.\d)', text) is not None


def near_set(gold, exclude=()):
    out = []
    for v in gold:
        out += [x for x in range(max(1, v - NEAR), v + NEAR + 1)
                if x not in gold and x not in exclude and x not in out]
    return out


def quote_ok(quote: str, text: str) -> bool:
    """The judge's quote check (digit-only quote must be a whole number in `text`)."""
    quote = quote.strip()
    if quote.isdigit():
        try:
            return names_number(int(quote), text)
        except ValueError:  # e.g. superscript digits; upstream would raise, never observed here
            return False
    return quote_in(quote, text)


def verdict(res, gold, near, readout):
    """Upstream verdict(): kind in hit/near/other/none/unverified/unavailable."""
    if res is None:
        return {'judged': False, 'kind': 'unavailable', 'values': [], 'hit': False}
    raw = res.get('values')
    values = ([int(v) for v in raw if isinstance(v, int) and not isinstance(v, bool)][:MAX_VALUES]
              if isinstance(raw, list) else [])
    if not values:
        return {'judged': True, 'kind': 'none', 'values': [], 'hit': False, 'basis': res.get('basis'),
                'quote': str(res.get('quote', '')).strip(), 'top_by_number': False, 'top_by_quote': False}
    top = values[0]
    quote = str(res.get('quote', '')).strip()
    by_quote = quote_ok(quote, readout)
    by_number = names_number(top, readout)
    verified = by_number or by_quote
    if not verified:
        kind = 'unverified'
    elif top in gold:
        kind = 'hit'
    elif top in near:
        kind = 'near'
    else:
        kind = 'other'
    return {'judged': True, 'kind': kind, 'values': values, 'hit': kind == 'hit',
            'any_of_3': verified and any(v in gold for v in values), 'basis': res.get('basis'),
            'quote': quote, 'top_by_number': by_number, 'top_by_quote': by_quote}


# ----------------------------------------------------------------------------------------------
# Small shared helpers
# ----------------------------------------------------------------------------------------------
WHOLE = re.compile(r'(?<!\d)(?<!\d\.)\d+(?!\d)(?!\.\d)')


def whole_numbers(text: str) -> list[int]:
    """Distinct whole numbers in order of first appearance (same boundary rule as names_number)."""
    out = []
    for m in WHOLE.finditer(text):
        try:
            v = int(m.group())
        except ValueError:
            continue
        if v not in out:
            out.append(v)
    return out


def render_offsets(bullet_texts):
    """Char ranges of each bullet body inside selection.render_bullets(...) output (the judged text)."""
    out, ranges = '', []
    for t in bullet_texts:
        if out and not out.endswith('\n'):
            out += '\n'
        out += '- '
        ranges.append((len(out), len(out) + len(t)))
        out += t
    return out, ranges


def judge_key(item_id: str, layer: int) -> str:
    return f'{item_id}|L{layer:03d}'


def load_bank():
    """{item_id: item}; upstream load_bank sets id = label_of(name) (== name for this bank)."""
    d = json.loads(BANK.read_text())
    items = {it['name']: it for it in d['items']}
    assert len(items) == 120
    return items


def item_gold(item):
    gold = [int(v) for v in item['intermediates']]
    return {'intermediates': gold, 'answer': int(item['answer']), 'start': int(item['start']),
            'depth': item['depth'], 'literals': [int(x) for x in item['literals']],
            'near': near_set(gold, (int(item['start']), int(item['answer']))),
            'steps': item['steps'], 'prompt': item['prompt']}


def load_judge(setting: str):
    """{(item, layer): {'result', 'readout_text', 'readout_pos', 'kind_saved', 'named_saved', 'basis_saved'}}
    plus {item: row} (pass, hitting_layers) from results.json."""
    base = JUDGMENTS / setting
    cells = {}
    with open(base / FAMILY / 'cells.jsonl') as fh:
        for line in fh:
            r = json.loads(line)
            assert r['key'] not in cells, r['key']
            cells[r['key']] = r
    readouts = {}
    with open(base / f'{FAMILY}.readouts.jsonl') as fh:
        for line in fh:
            r = json.loads(line)
            k = (r['id'], r['layer'])
            assert k not in readouts, k
            readouts[k] = r
    res = json.loads((base / FAMILY / 'results.json').read_text())
    rows = {r['id']: r for r in res['rows']}
    out = {}
    for (item, layer), r in readouts.items():
        rec = cells.get(judge_key(item, layer))
        row = rows[item]
        out[(item, layer)] = {
            'result': rec['result'] if rec else None, 'judge_key': judge_key(item, layer),
            'readout_text': '\n'.join(s for s in r['samples'] if s.strip()), 'readout_pos': r['pos'],
            'kind_saved': row['kind_by_layer'].get(str(layer)),
            'named_saved': row['named_by_layer'].get(str(layer)),
            'basis_saved': row['basis_by_layer'].get(str(layer)),
        }
    return out, rows, res


# ----------------------------------------------------------------------------------------------
# Bullet labels
# ----------------------------------------------------------------------------------------------
LABELS_PRIMARY = ('hit', 'answer', 'wrong_specific', 'miss')  # also the classes of label_anchor
LABELS_NAMED = ('top_hit', 'gold_named', 'wrong_named', 'answer_named', 'none_named')
LABELS_STATED = ('states_intermediate', 'derives_intermediate', 'states_answer', 'states_other', 'states_none')


def fold_map(text: str):
    """fold(text) plus, per folded char, the index of the original char it came from."""
    parts, idx = [], []
    for i, ch in enumerate(text):
        f = fold(ch)
        parts.append(f)
        idx.extend([i] * len(f))
    return ''.join(parts), idx


def quote_spans(quote: str, text: str):
    """Original-char spans of every occurrence of the judge quote in `text`, by the judge's own rule:
    a digit-only quote = whole-number occurrences; otherwise a folded (case/accent/curly-quote)
    verbatim match. Returns [] when the quote is not in `text`."""
    quote = quote.strip()
    if not quote:
        return []
    if quote.isdigit():
        try:
            n = int(quote)
        except ValueError:
            return []
        return [m.span() for m in re.finditer(rf'(?<!\d)(?<!\d\.){n}(?!\d)(?!\.\d)', text)]
    q = fold(quote)
    if not q:
        return []
    ftext, idx = fold_map(text)
    assert ftext == fold(text)
    spans, i = [], ftext.find(q)
    while i >= 0:
        spans.append((idx[i], idx[i + len(q) - 1] + 1))
        i = ftext.find(q, i + 1)
    return spans


_LEAD_STRIP = re.compile(r'^[\s*$`#(\[>|_~\\]*')
_NOT_OPERAND = r'(?!\d)(?!\.\d)(?!\s*[x×*+\-/÷^]\s*\(?\d)'  # '8 x 2', '16 - 2': an operand, not a result
_LEAD_NUM = re.compile(r'(\d+)' + _NOT_OPERAND)
_LIST_INDEX = re.compile(r'(\d+)[.)]\s+[A-Za-z*]')
_PHRASE = re.compile(r'(?:answer|result|final number|final value|number is|value is|total)'
                     r'(?:\s*(?:is|:|=|would be|will be|of)|[^\d\n.]{0,60}?(?::|\bis\b))?'
                     r'\s*[:*$`\s]*(\d+)' + _NOT_OPERAND, re.I)  # '... final number following the steps: 16'
_BOLD = re.compile(r'\*\*\s*(\d+)(?!\d)(?!\.\d)\s*\.?\*\*')
_ALONE = re.compile(r'(?m)^\s*[*$`]*(\d+)(?!\d)(?!\.\d)[*$`.]*\s*$')
_DERIVED = re.compile(r'(?:=|→|->|equals|to get|gives|giving|results in|resulting in|becomes|is now|get|yields|yielding|'
                      r'produces|leaves|makes|(?:result|answer|total|sum|product|difference|output)[^\d\n.]{0,40}?(?::|\bis\b))'
                      r'\s*[*$`\s]*(\d+)' + _NOT_OPERAND, re.I)


def stated_values(btext: str):
    """Judge-free string rule. lead = the value the bullet itself puts forward as its result:
    (1) a leading integer (after markup), unless it is a list index ('7. Double ...'); else
    (2) the first 'answer/result/final number/total [<=60 chars] (is|:|=) N'; else (3) the first bold **N**;
    else (4) a line that is only a number. derived = numbers right after =, ->, equals, to get,
    gives, results in, becomes, yields, makes, or 'result/answer/total/sum/output [<=40 chars] (:|is)'
    (computed results inside the bullet's explanation, all occurrences)."""
    s = btext.strip()
    rest = _LEAD_STRIP.sub('', s)
    lead, how = None, None
    m = _LEAD_NUM.match(rest)
    if m and not _LIST_INDEX.match(rest):
        lead, how = int(m.group(1)), 'leading'
    else:
        for rx, name in ((_PHRASE, 'phrase'), (_BOLD, 'bold'), (_ALONE, 'alone')):
            m = rx.search(s)
            if m:
                lead, how = int(m.group(1)), name
                break
    derived = []
    for m in _DERIVED.finditer(s):
        x = int(m.group(1))
        if x not in derived:
            derived.append(x)
    return lead, how, derived


def label_bullet(btext: str, v: dict, g: dict, anchor: bool) -> dict:
    """Four label columns for one bullet (see MAP.md). `v` = re-derived readout verdict (judge's
    ranked values <=3, quote, kind); `anchor` = the bullet is where the judge's quote locates the
    top value (chosen by anchors_for).

    label (PRIMARY; the judge's verified top-1 integer located in the bullet). The bullet carries
      the readout's verified top value if it is an anchor (the judge's quote is located in it) or
      it contains the top value as a whole number (names_number, the judge's own rule) IN A
      COMPUTED POSITION by the string rule (its lead value, or right after =/to get/results in/...;
      stated_values). Plain echoes (operands 'Starting at 5', list indices '3) Genesis') do not
      carry. Carrying bullets get:
        'hit'            readout kind == 'hit' (top value is an intermediate; the official rule),
        'answer'         top value == the item's final answer (correct, but not the target),
        'wrong_specific' otherwise: a different integer presented as computed; wrong_role =
                         near (+-3 decoy) | start | literal (prompt operand) | other.
      All other bullets are 'miss' (incl. every bullet of none/unverified readouts).
    label_anchor (STRICT): same classes, but only anchor bullets carry (the bullet the judge's quote
      points to; a repeat of the value elsewhere is 'miss').
    label_contains (LOOSE, spec-literal 'the bullet contains the judge-verified value'): anchor or
      the top value anywhere in the bullet as a whole number. label_anchor <= label <= label_contains.
    label_named (LENIENT, all <=3 judge-named values, whole-number presence): top_hit (== primary
      hit) > gold_named (an intermediate the judge named but did not credit, any rank) >
      wrong_named (a named value that is neither intermediate nor answer) > answer_named > none_named.
    label_stated (JUDGE-FREE string rule, stated_values): states_intermediate (lead value is an
      intermediate) > derives_intermediate (an intermediate right after =/to get/...) >
      states_answer > states_other (lead value is another integer) > states_none.
    """
    gold, ans, start = g['intermediates'], g['answer'], g['start']
    values = v.get('values') or []
    top = values[0] if values else None
    verified = v.get('kind') in ('hit', 'near', 'other') and top is not None
    ranks_here = [r for r, x in enumerate(values) if names_number(x, btext)]
    lead, how, derived = stated_values(btext)
    top_number = 0 in ranks_here
    top_computed = top_number and (top == lead or top in derived)
    carries = verified and (anchor or top_computed)

    def classify(flag):
        if not flag:
            return 'miss', None, None
        if v['kind'] == 'hit':
            return 'hit', top, None
        if top == ans:
            return 'answer', top, None
        return 'wrong_specific', top, ('near' if top in g['near'] else 'start' if top == start
                                       else 'literal' if top in g['literals'] else 'other')

    label, lval, role = classify(carries)
    label_anchor = classify(verified and anchor)[0]
    label_contains = classify(verified and (anchor or top_number))[0]
    named_here = [values[r] for r in ranks_here]
    if label == 'hit':
        named = 'top_hit'
    elif any(x in gold for x in named_here):
        named = 'gold_named'
    elif any(x not in gold and x != ans for x in named_here) or label == 'wrong_specific':
        named = 'wrong_named'
    elif ans in named_here or label == 'answer':
        named = 'answer_named'
    else:
        named = 'none_named'
    if lead is not None and lead in gold:
        stated = 'states_intermediate'
    elif any(x in gold for x in derived):
        stated = 'derives_intermediate'
    elif lead is not None and lead == ans:
        stated = 'states_answer'
    elif lead is not None:
        stated = 'states_other'
    else:
        stated = 'states_none'
    return {'label': label, 'label_value': lval, 'wrong_role': role, 'anchor': anchor,
            'top_as_number': top_number, 'top_in_computed_position': top_computed,
            'label_anchor': label_anchor, 'label_contains': label_contains,
            'label_named': named, 'judge_ranks_here': ranks_here,
            'label_stated': stated, 'lead_value': lead, 'lead_how': how, 'derived_values': derived,
            'numbers': whole_numbers(btext), 'gold_mentioned': [x for x in gold if names_number(x, btext)]}


def anchors_for(v: dict, text: str, ranges):
    """Which bullets state the judge's top value. Bullet i owns readout chars [start_i - 2, end_i)
    (its '- ' marker + body). quote_bullets = bullets overlapping an occurrence of the judge quote
    (handles quotes that cross a bullet boundary, e.g. 'resulting in\\n- 15');
    number_bullets = bullets containing the top value as a whole number. Anchors =
      quote_bullets & number_bullets                 (source 'quote+number'), else
      quote_bullets if the top is not a whole number anywhere in the readout (numeral word,
                    decimal like '16.50**'; source 'quote'), else
      number_bullets                                  (source 'number': quote absent / elsewhere), else
      quote_bullets                                   (source 'quote').
    Unverified/none readouts have no anchors."""
    values = v.get('values') or []
    if v.get('kind') not in ('hit', 'near', 'other') or not values:
        return [], [], [], None
    top = values[0]
    occ = quote_spans(v.get('quote') or '', text)
    qb = sorted({i for i, (s0, s1) in enumerate(ranges) for (a, b) in occ if a < s1 and b > s0 - 2})
    nb = [i for i, (s0, s1) in enumerate(ranges) if names_number(top, text[s0:s1])]
    both = [i for i in qb if i in nb]
    if both:
        return both, qb, nb, 'quote+number'
    if qb and not v.get('top_by_number'):
        return qb, qb, nb, 'quote'
    if nb:
        return nb, qb, nb, 'number'
    return qb, qb, nb, ('quote' if qb else None)


def label_readout(sel: dict, j: dict, g: dict) -> dict:
    """One setting of one cell: verdict re-derived from the saved judge result + per-bullet labels."""
    text = sel['text']
    rendered, ranges = render_offsets([a['text'] for a in sel['atoms']])
    v = verdict(j['result'], g['intermediates'], g['near'], j['readout_text']) if j and j['result'] else None
    anchors, qb, nb, src = anchors_for(v, text, ranges) if v else ([], [], [], None)
    bullets = []
    for i, (a, (s0, s1)) in enumerate(zip(sel['atoms'], ranges)):
        b = {'index': i, 'phrase_id': a['source_phrase_id'], 'sample_index': a['sample_index'],
             'char_start': s0, 'char_end': s1, 'text': a['text'], 'truncated': a['truncated'],
             'cache_key': a['cache_key']}
        b.update(label_bullet(a['text'], v or {}, g, i in anchors))
        bullets.append(b)
    judge = None
    if v is not None:
        judge = {'judge_key': j['judge_key'], 'values': v['values'], 'quote': v.get('quote') or '',
                 'basis': v.get('basis'), 'states_value': j['result'].get('states_value'),
                 'kind': v['kind'], 'kind_saved': j['kind_saved'], 'named_saved': j['named_saved'],
                 'top': v['values'][0] if v['values'] else None,
                 'top_by_number': v.get('top_by_number'), 'top_by_quote': v.get('top_by_quote'),
                 'any_of_3': v.get('any_of_3', False), 'anchor_bullets': anchors, 'anchor_source': src,
                 'quote_bullets': qb, 'top_number_bullets': nb,
                 'readout_pos': j['readout_pos'], 'text_matches_selection': j['readout_text'] == text}
    return {'rendered_ok': rendered == text, 'judge': judge, 'bullets': bullets}


# ----------------------------------------------------------------------------------------------
# Subcommand: extract
# ----------------------------------------------------------------------------------------------
def cmd_extract():
    sys.path.insert(0, '${OLENS_REPO_ROOT}/src')
    from olens_improve.ar_cache import vector_key
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
    tmp = EXTRACT.with_suffix('.jsonl.tmp')
    with open(tmp, 'w') as out:
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
                        assert exact is not None and exact['solver'] == 'scipy_exact', (cid, cond)
                        assert list(exact['atom_ids']) == s['phrase_ids'], (cid, cond)
                        assert [a['source_phrase_id'] for a in s['atoms']] == s['phrase_ids'], (cid, cond)
                        tsha = hashlib.sha256(s['text'].encode()).hexdigest()
                        if expansion[(cid, cond)] != (tsha, s['token_count'], s['bullet_count']):
                            stats['expansion_text_mismatch'] += 1
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
                        rel = (s.get('fits') or {}).get('released80') or {}
                        settings[cond] = {
                            'method': s['method'], 'n': s['n'], 'text': s['text'], 'text_sha256': tsha,
                            'token_count': s['token_count'], 'bullet_count': s['bullet_count'],
                            'reason': s['reason'], 'fits_scope': s['fits_scope'], 'phrase_ids': s['phrase_ids'],
                            'fve': exact['fve'], 'coefficients': exact['coefficients'],
                            'released80_fve': rel.get('fve'), 'trace': s['trace'], 'atoms': atoms,
                        }
                    assert set(settings) == set(SETTINGS), (cid, sorted(settings))
                    out.write(json.dumps({
                        'cell_id': cid, 'family': FAMILY, 'item_id': row['item_id'],
                        'group_id': cell['group_id'], 'layer': row['layer'], 'position': row['position'],
                        'split': stage, 'token': cell.get('token'), 'read_position_kind': cell.get('read_position_kind'),
                        'activation_row': cell['activation_row'], 'activation_sha256': cell['activation_sha256'],
                        'global_pool_id': row['global_pool_id'], 'vector_cache': str(CACHES[stage]),
                        'source_selections': str(path), 'settings': settings,
                    }, ensure_ascii=False) + '\n')
                    stats[f'cells[{stage}]'] += 1
                    stats[f'cells[L{row["layer"]}]'] += 1
            print(stage, 'done', round(time.time() - t0, 1), 's', flush=True)
    tmp.replace(EXTRACT)
    summary['cells_extracted'] = len(seen)
    summary['missing_vs_fresh'] = sorted(set(fresh) - seen)[:20]
    summary['stats'] = dict(sorted(stats.items()))
    index, cov, found_meta, tags = {}, {}, {}, {}
    for stage, directory in CACHES.items():
        contract = json.load(open(directory / 'contract.json'))
        assert contract['sha256'] == CONTRACT
        want = needed[stage]
        found = {}
        files = sorted(directory.glob('raw_*.index.json'))
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
    fve = collections.defaultdict(list)
    with open(EXTRACT) as f:
        for line in f:
            r = json.loads(line)
            for cond, s in r['settings'].items():
                fve[cond].append(s['fve'])
                for a in s['atoms']:
                    k = a['cache_key']
                    if k is None or k not in found_meta[r['split']]:
                        continue
                    meta = found_meta[r['split']][k]
                    checks['layer_ok' if meta[2] == r['layer'] else 'layer_mismatch'] += 1
                    ok = vector_key(CONTRACT, tags[r['layer']], a['scored_token_ids']) == k
                    checks['atom_tokens_reproduce_key' if ok else 'atom_tokens_key_mismatch'] += 1
    summary['atom_key_checks'] = dict(checks)
    summary['mean_saved_fve_pct'] = {k: round(100 * sum(v) / len(v), 2) for k, v in fve.items()}
    summary['tag_ids_by_layer'] = {str(k): v for k, v in sorted(tags.items())}
    summary['seconds'] = round(time.time() - t0, 1)
    json.dump(index, open(VINDEX, 'w'))
    json.dump(summary, open(EXTRACT_SUMMARY, 'w'), indent=1)
    print(json.dumps(summary, indent=1)[:5000])


# ----------------------------------------------------------------------------------------------
# Subcommand: verify_fve (one cell per layer x 3 settings; recompute from raw vectors)
# ----------------------------------------------------------------------------------------------
def rows_memmap(path, key):
    import numpy as np
    with open(path, 'rb') as f:
        n = int.from_bytes(f.read(8), 'little')
        header = json.loads(f.read(n))
    info = header[key]
    assert info['dtype'] == 'F32'
    return np.memmap(path, dtype='<f4', mode='r', offset=8 + n + info['data_offsets'][0],
                     shape=tuple(info['shape']))


def cmd_verify_fve():
    import random
    import numpy as np
    import torch
    sys.path.insert(0, '${OLENS_REPO_ROOT}/src')
    from olens_improve.reconstruction import JointNNLS, Whitener
    torch.set_num_threads(8)
    rng = random.Random(20261015)
    by_layer = collections.defaultdict(list)
    for c in iter_extract():
        by_layer[c['layer']].append(c)
    vindex = json.load(open(VINDEX))
    acts = rows_memmap(ACTS, 'resid')
    out = []
    for layer in LAYERS:
        c = rng.choice(by_layer[layer])
        w = Whitener.load(str(WHITENERS / f'whitening_iolens_pooled_L{layer}.safetensors'))
        target = torch.from_numpy(np.array(acts[c['activation_row']]))
        assert hashlib.sha256(target.numpy().tobytes()).hexdigest() == c['activation_sha256']
        for sid in SETTINGS:
            s = c['settings'][sid]
            vecs = {}
            for a in s['atoms']:
                path, row = vindex[c['split']][a['cache_key']]
                vecs[a['source_phrase_id']] = torch.from_numpy(np.array(rows_memmap(path, 'vectors')[row]))
            fit = JointNNLS.from_raw(target, vecs, w, solver='scipy_exact').fit(s['phrase_ids'])
            out.append({'cell_id': c['cell_id'], 'split': c['split'], 'setting': sid, 'saved': s['fve'],
                        'recomputed': fit.fve, 'abs_diff': abs(fit.fve - s['fve'])})
            print(out[-1], flush=True)
    res = {'fits': out, 'max_abs_diff': max(r['abs_diff'] for r in out), 'n_fits': len(out)}
    VERIFY_FVE.write_text(json.dumps(res, indent=1))
    print('max_abs_diff', res['max_abs_diff'])


# ----------------------------------------------------------------------------------------------
# Subcommand: labels
# ----------------------------------------------------------------------------------------------
def iter_extract():
    with open(EXTRACT) as fh:
        for line in fh:
            yield json.loads(line)


def iter_labelled():
    with open(LABELS) as fh:
        for line in fh:
            yield json.loads(line)


def cmd_labels():
    t0 = time.time()
    bank = load_bank()
    judges, rows, results = {}, {}, {}
    for sid in SETTINGS:
        judges[sid], rows[sid], results[sid] = load_judge(sid)
    st = collections.Counter()
    agree = collections.Counter()
    tmp = LABELS.with_suffix('.jsonl.tmp')
    with open(tmp, 'w') as out:
        for c in iter_extract():
            item, layer = c['item_id'], c['layer']
            g = item_gold(bank[item])
            rec = {k: c[k] for k in ('cell_id', 'item_id', 'group_id', 'layer', 'position', 'split')}
            rec['gold'] = {k: g[k] for k in ('intermediates', 'answer', 'start', 'depth', 'literals', 'near')}
            rec['settings'] = {}
            for sid in SETTINGS:
                sel = c['settings'][sid]
                j = judges[sid].get((item, layer))
                assert j is not None, (sid, item, layer)
                assert j['readout_pos'] == c['position'], (sid, c['cell_id'], j['readout_pos'])
                lab = label_readout(sel, j, g)
                st[f'rendered_ok[{sid}]'] += lab['rendered_ok']
                jd = lab['judge']
                if jd is None:
                    st[f'unjudged[{sid}]'] += 1
                else:
                    st[f'text_match[{sid}]'] += jd['text_matches_selection']
                    st[f'kind_match[{sid}]'] += jd['kind'] == jd['kind_saved']
                    st[f'named_match[{sid}]'] += jd['values'] == jd['named_saved']
                    st[f'kind={jd["kind"]}[{sid}]'] += 1
                    if jd['anchor_bullets']:
                        st[f'anchor_source={jd["anchor_source"]}[{sid}]'] += 1
                        st[f'anchors_n={min(len(jd["anchor_bullets"]), 3)}[{sid}]'] += 1
                        st[f'top_number_bullets_n={min(len(jd["top_number_bullets"]), 3)}[{sid}]'] += 1
                    elif jd['kind'] in ('hit', 'near', 'other'):
                        st[f'verified_without_anchor[{sid}]'] += 1
                for b in lab['bullets']:
                    st[f'label={b["label"]}[{sid}]'] += 1
                    st[f'label_anchor={b["label_anchor"]}[{sid}]'] += 1
                    st[f'label_contains={b["label_contains"]}[{sid}]'] += 1
                    st[f'label_named={b["label_named"]}[{sid}]'] += 1
                    st[f'label_stated={b["label_stated"]}[{sid}]'] += 1
                    if b['label'] == 'wrong_specific':
                        st[f'wrong_role={b["wrong_role"]}[{sid}]'] += 1
                    if b['anchor']:  # does the string rule's lead value agree with the judge's top?
                        agree[f'anchor_lead={"none" if b["lead_value"] is None else "eq_top" if b["lead_value"] == b["label_value"] else "ne_top"}'] += 1
                    # cross-tab primary x stated (all settings pooled)
                    agree[f'{b["label"]} x {b["label_stated"]}'] += 1
                rec['settings'][sid] = {
                    'display': DISPLAY[sid], 'fve': sel['fve'], 'coefficients': sel['coefficients'],
                    'text': sel['text'], 'text_sha256': sel['text_sha256'], 'bullet_count': sel['bullet_count'],
                    'reason': sel['reason'], 'item_pass': rows[sid][item]['pass'],
                    'item_hitting_layers': rows[sid][item]['hitting_layers'],
                    'rendered_ok': lab['rendered_ok'], 'judge': lab['judge'], 'bullets': lab['bullets'],
                }
            out.write(json.dumps(rec, ensure_ascii=False) + '\n')
            st['cells'] += 1
    tmp.replace(LABELS)
    summary = {'counts': dict(sorted(st.items())), 'agreement_pooled': dict(sorted(agree.items())),
               'seconds': round(time.time() - t0, 1),
               'saved_item_pass': {sid: sum(bool(r['pass']) for r in rows[sid].values()) for sid in SETTINGS},
               'saved_kinds': {sid: results[sid]['numbers']['extras']['kinds'] for sid in SETTINGS}}
    LABELS_SUMMARY.write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


# ----------------------------------------------------------------------------------------------
# Subcommand: check (asserts; run after `labels`)
# ----------------------------------------------------------------------------------------------
def cmd_check():
    # unit tests of the mirrored helpers (upstream docstring cases) and the label rules
    assert names_number(5, 'is 5.') and not names_number(5, '15') and not names_number(10, '10.83')
    assert not names_number(19, '2019') and names_number(14, '16 - 2 = 14')
    assert quote_ok('16.50**', 'the answer is 16.50**') and not quote_ok('16', 'value 16.50')
    assert near_set([11, 5], (23, 2)) == [8, 9, 10, 12, 13, 14, 3, 4, 6, 7]
    assert whole_numbers('Step 1: 16 - 2 = 14, not 10.83 or 2019') == [1, 16, 2, 14, 2019]
    assert stated_values('18** (since 3 x 6 = 18)') == (18, 'leading', [18])
    assert stated_values('7. Double the result: 8 x 2 = 10')[:2] == (None, None)
    assert stated_values('Here is the final answer: **36**')[:2] == (36, 'phrase')
    assert stated_values('Here is the final number following the steps described: 16')[:2] == (16, 'phrase')
    assert stated_values('The answer is 11. To reach this result, we do 42 - 30 = 12')[:2] == (11, 'phrase')
    assert stated_values('Start with 8. Subtract 3 to get 5.')[2] == [5]
    assert stated_values('16 - 2 = 14')[:2] == (None, None) and stated_values('16 - 2 = 14')[2] == [14]
    assert quote_spans('resulting in\n- 15', 'x resulting in\n- 15 y') == [(2, 19)]
    assert quote_spans('ÉTÉ 3', 'un été 3') == [(3, 8)]
    g = {'intermediates': [16], 'answer': 14, 'start': 8, 'literals': [2, 8], 'near': near_set([16], (8, 14))}
    v = {'kind': 'hit', 'values': [16, 14], 'quote': 'double 8 to get 16', 'top_by_number': True}
    text, ranges = render_offsets(['We double 8 to get 16.\n', 'The answer is 14.\n', '16 again\n'])
    anc, qb, nb, src = anchors_for(v, text, ranges)
    assert (anc, qb, nb, src) == ([0], [0], [0, 2], 'quote+number')
    assert label_bullet('We double 8 to get 16.', v, g, True)['label'] == 'hit'
    rep = label_bullet('16 again', v, g, False)  # restates the credited value as its lead value
    assert rep['label'] == 'hit' and rep['label_anchor'] == 'miss' and rep['label_named'] == 'top_hit'
    echo = label_bullet('Starting at 16, add 3', v, g, False)  # operand echo of the value
    assert echo['label'] == 'miss' and echo['label_contains'] == 'hit' and echo['label_anchor'] == 'miss'
    assert label_bullet('16 again', {'kind': 'near', 'values': [17, 16], 'quote': '17'}, g, False)['label_named'] == 'gold_named'
    assert label_bullet('The answer is 14.', v, g, False)['label'] == 'miss'
    assert label_bullet('The answer is 14.', v, g, False)['label_named'] == 'answer_named'
    assert label_bullet('18 then 16', {'kind': 'unverified', 'values': [16], 'quote': 'x'}, g, False)['label'] == 'miss'
    v2 = {'kind': 'near', 'values': [17, 16], 'quote': '17', 'top_by_number': True}
    w = label_bullet('So we get 17.', v2, g, True)
    assert w['label'] == 'wrong_specific' and w['wrong_role'] == 'near' and w['label_value'] == 17
    v3 = {'kind': 'other', 'values': [14], 'quote': 'The answer is 14', 'top_by_number': True}
    assert label_bullet('The answer is 14.', v3, g, True)['label'] == 'answer'
    bank = load_bank()
    n = collections.Counter()
    pass_from_labels = {sid: collections.defaultdict(bool) for sid in SETTINGS}
    for c in iter_labelled():
        n['cells'] += 1
        g = item_gold(bank[c['item_id']])
        for sid, s in c['settings'].items():
            assert s['rendered_ok'], (c['cell_id'], sid)
            j = s['judge']
            assert j is not None, (c['cell_id'], sid)  # chain has no empty readouts
            assert j['text_matches_selection'], (c['cell_id'], sid)
            assert j['kind'] == j['kind_saved'], (c['cell_id'], sid, j['kind'], j['kind_saved'])
            assert j['values'] == j['named_saved'], (c['cell_id'], sid)
            labels = [b['label'] for b in s['bullets']]
            if j['kind'] in ('hit', 'near', 'other'):
                assert j['anchor_bullets'], (c['cell_id'], sid)  # every verified top is located
            else:
                assert not j['anchor_bullets'] and set(labels) == {'miss'}, (c['cell_id'], sid)
            assert ('hit' in labels) == (j['kind'] == 'hit'), (c['cell_id'], sid)
            assert ('hit' in [b['label_anchor'] for b in s['bullets']]) == (j['kind'] == 'hit')
            for b in s['bullets']:
                assert s['text'][b['char_start']:b['char_end']] == b['text']
                assert b['anchor'] == (b['index'] in j['anchor_bullets'])
                verified = j['kind'] in ('hit', 'near', 'other')
                assert (b['label_anchor'] != 'miss') == b['anchor'], (c['cell_id'], sid, b['index'])
                assert (b['label_contains'] != 'miss') == (verified and (b['anchor'] or names_number(j['top'], b['text'])))
                assert (b['label'] != 'miss') == (verified and (b['anchor'] or b['top_in_computed_position']))
                assert b['label_anchor'] in ('miss', b['label']) and b['label'] in ('miss', b['label_contains'])
                if b['label'] == 'hit':
                    assert b['label_value'] in g['intermediates'] and b['label_named'] == 'top_hit'
                if b['label'] == 'answer':
                    assert b['label_value'] == g['answer']
                if b['label'] == 'wrong_specific':
                    assert b['label_value'] not in g['intermediates'] + [g['answer']]
            pass_from_labels[sid][c['item_id']] |= 'hit' in labels
            n['readouts'] += 1
            n['bullets'] += len(s['bullets'])
    saved = json.loads(LABELS_SUMMARY.read_text())['saved_item_pass']
    for sid in SETTINGS:
        assert sum(pass_from_labels[sid].values()) == saved[sid], (sid, sum(pass_from_labels[sid].values()), saved[sid])
    assert n['cells'] == 1320 and n['readouts'] == 3960
    print('check OK', dict(n), 'item passes from bullet labels:', {sid: sum(pass_from_labels[sid].values()) for sid in SETTINGS})


# ----------------------------------------------------------------------------------------------
# Subcommand: examples
# ----------------------------------------------------------------------------------------------
def show(c, sid, width=220):
    s = c['settings'][sid]
    j = s['judge']
    print(f"\n== {c['cell_id']}  [{sid} / {DISPLAY[sid]}]  gold={c['gold']['intermediates']} "
          f"answer={c['gold']['answer']} start={c['gold']['start']}  fve={s['fve']:.4f}  item_pass={s['item_pass']}")
    print(f"   judge {j['judge_key']}: kind={j['kind']} values={j['values']} basis={j['basis']} "
          f"quote={j['quote']!r} anchors={j['anchor_bullets']} ({j['anchor_source']}) "
          f"quote_bullets={j['quote_bullets']} top_number_bullets={j['top_number_bullets']}")
    for b in s['bullets']:
        print(f"   [{b['index']}] {b['label']:<14} val={b['label_value']} role={b['wrong_role']} anchor={b['label_anchor']} contains={b['label_contains']} | "
              f"named={b['label_named']} | stated={b['label_stated']} lead={b['lead_value']}({b['lead_how']}) "
              f"derived={b['derived_values']}\n       {b['text'].strip()[:width]!r}")


def cmd_examples(n_per=5, seed=7):
    import random
    rng = random.Random(seed)
    cells = list(iter_labelled())
    for sid in SETTINGS:
        k = lambda c: c['settings'][sid]['judge']['kind']  # noqa: E731
        pools = [
            [c for c in cells if k(c) == 'hit'],
            [c for c in cells if k(c) == 'hit' and (c['settings'][sid]['judge']['anchor_source'] != 'quote+number' or any(
                b['label'] == 'hit' and b['label_anchor'] == 'miss' for b in c['settings'][sid]['bullets']))],
            [c for c in cells if k(c) in ('near', 'other') and any(
                b['label'] == 'wrong_specific' for b in c['settings'][sid]['bullets'])],
            [c for c in cells if any(b['label'] == 'answer' for b in c['settings'][sid]['bullets'])],
            [c for c in cells if any(b['label_named'] == 'gold_named' for b in c['settings'][sid]['bullets'])],
        ]
        print(f'\n######## {sid} ({DISPLAY[sid]})')
        for pool in pools[:n_per]:
            show(rng.choice(pool), sid)


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if cmd == 'show':  # python load.py show <cell_id> <setting>
        show(next(c for c in iter_labelled() if c['cell_id'] == sys.argv[2]), sys.argv[3])
    else:
        {'extract': cmd_extract, 'verify_fve': cmd_verify_fve, 'labels': cmd_labels, 'check': cmd_check,
         'examples': lambda: cmd_examples(int(sys.argv[2]) if len(sys.argv) > 2 else 5)}[cmd]()
