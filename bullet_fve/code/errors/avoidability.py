#!/usr/bin/env python
"""Avoidability of Oracle-Lens hallucinations on the fully judged development pilot (exploratory).

For 72 Hallucination (chat) cells (8 development chats x 3 read sites x layers 20/44/60) every one
of the 32 lens samples (capped to <=4 bullets / 256 tokens) was judged by the project judge
(GPT-6 Luna, prompt v5c-chat, stage 2 v5c-chat-verify-v1).  This script

  1. verifies the judge pins / prompt hashes against the full-bank (expansion-v1) judgments,
     that judged texts == exact-FVE score texts, that the pilot's raw lens samples are the same
     texts as the full-grid development pool, and that sample 0 / the FVE winner reproduce the
     full-bank "Original" and "Best of 32" readouts;
  2. per cell: label counts over the 32 samples, P(random sample hallucinated), whether a clean
     (= judge class "consistent", i.e. asserting with no wrong / off-topic span) sample exists,
     whether the highest-FVE sample is clean, rank of the best clean sample by FVE, cell class;
  3. per verified wrong span: judge-verified recurrence in OTHER samples of the same cell, and per
     key element (novel name / number / content word): samples where it appears flagged vs
     appears unflagged (judge inconsistency);
  4. summaries by layer and source with chat-level bootstrap CIs (8 chats only);
  5. relation to the full bank: share of Original's hallucinations a perfect selector among the
     32 samples would have avoided, and the observable lower bound from the 3 judged settings.

Read-only on all inputs.  Writes avoidability.json and avoidability_cells.jsonl next to itself.
No model or API calls.  Run: <runtime python> -B avoidability.py
"""
import collections
import hashlib
import json
import random
import re
import statistics
import sys
import unicodedata
from pathlib import Path

ROOT = Path('${OLENS_DATA_ROOT}')
PILOT = ROOT / 'runs/development-shared-pilot-v2/judgments-all-candidates'
SCORES = ROOT / 'diagnostics/all-candidate-scores-v1/scores.jsonl'
QA = ROOT / 'diagnostics/all-candidate-scores-v1/quality-analysis-v2.json'
PILOT_SAMPLES = ROOT / 'runs/development-shared-pilot-v2/pilot189-samples-v1.jsonl'
DEV_FLAT = ROOT / 'runs/development-full-grid-v2/samples-n32.jsonl'
EXP_J = ROOT / 'expansion-v1/judgments'
MANIFEST = Path('${OLENS_REPO_ROOT}/configs/expansion_manifest_v1.json')
BENCH = Path('${OLENS_SOURCE_ROOT}/scratch/repos/workspace-bench-v2')
BASE = Path('${OLENS_SCRATCH}/olens-bullet-fve')
PAGE = BASE / 'page/data'
THREE = BASE / 'inputs/hall_three_settings.jsonl'
OUT = BASE / 'errors'
LINK = 'https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#'
LABELS = ['consistent', 'hallucinated', 'off_topic', 'generic', 'empty']  # page label codes
SETTINGS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
N = 32
SEED = 20261015
BOOT = 2000

# ---------------------------------------------------------------- text helpers
_WS = re.compile(r'\s+')
_QUOTES = str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'", '«': '"', '»': '"'})


def bench_norm(s):  # == wsbench.evals.hallucination.judge.normalize_ws
    return _WS.sub(' ', s.translate(_QUOTES)).strip().lower()


_CJK = re.compile(r'[぀-ヿ㐀-䶿一-鿿가-힯＀-￯]')


def norm2(s):
    """Benchmark normalisation, then NFKC, punctuation/symbols dropped (CJK kept)."""
    s = unicodedata.normalize('NFKC', bench_norm(s))
    s = ''.join(ch if (ch.isalnum() or ch.isspace() or _CJK.match(ch)) else ' ' for ch in s)
    return _WS.sub(' ', s).strip()


_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*[A-Za-z]|[A-Za-z]")
_NUM = re.compile(r'\d+(?:[.,:/]\d+)*')
STOP = set("""a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further had has have having
he her here hers herself him himself his how i if in into is it its itself just let me more most my myself no nor
not now of off on once only or other our ours ourselves out over own same she should so some such than that the
their theirs them themselves then there these they this those through to too under until up very was we were what
when where which while who whom why will with would you your yours yourself yourselves i'm i’m it's that's don't
can't i'll i've i'd you're you'll you've we're they're there's here's let's isn't aren't wasn't won't
yes no oh okay ok well sure hello hi hey dear thanks thank please really just like get got make made one also
however actually still even much many well good great""".split())
# capitalised words that are not names even when capitalised
NOT_NAME = set("""I The A An It This That These Those My Your Our Their His Her Its Yes No Oh Hi Hello Hey Thank Thanks
Please Good Well So But And Or If When What How Why Who Where Here There We You He She They Let Sure OK Okay Dear
Also However Actually Great Wow Ah Hmm Absolutely Certainly Of Since While As For In On At To From With By After
Before Then Now Just Maybe Perhaps Although Though Because Not Do Does Did Is Are Was Were Be Can Could Would Should
Will May Might Must Have Has Had Mr Mrs Ms Miss Dr Note Step Here's There's It's I'm I've I'd I'll That's What's
Let's Don't Can't Yes, Hello, Today Tomorrow Yesterday Monday Tuesday Wednesday Thursday Friday Saturday Sunday
English Chinese AI Qwen Alibaba Answer Unlike Recommended Founded Fixed Class Section Middle Limited Risk Segments
Summary Conclusion Example Key Important Overview Introduction Features Benefits Additionally Furthermore Overall
Finally First Second Third Other Some Many Most Each Every""".split())
FIRST_PERSON = re.compile(r"(?:^|[^A-Za-z])(I|I'm|I’m|I've|I’ve|I'd|I’d|I'll|I’ll|my|My|me|mine|myself)(?=$|[^A-Za-z])")


def words(s):
    return [w.replace('’', "'") for w in _WORD.findall(s)]


def nums(s):
    return [n.replace(',', '') for n in _NUM.findall(s)]


def has_word(text, w):
    """Whole-word, case-insensitive containment (w is a single ASCII word or number)."""
    return re.search(r'(?<![A-Za-z0-9])' + re.escape(w.lower()) + r'(?![A-Za-z0-9])', text.lower().replace('’', "'")) is not None


def content_tokens(s):
    """Content tokens for overlap: lowercase non-stopwords (len>=3), numbers, CJK bigrams."""
    t = norm2(s)
    toks = {w.lower() for w in words(t) if w.lower() not in STOP and len(w) >= 3}
    toks |= set(nums(t))
    for run in re.findall(r'[㐀-鿿]+', t):
        toks |= {run[i:i + 2] for i in range(max(1, len(run) - 1))}
    return toks


def texts_overlap(a, b):
    """'Normalised-overlapping text': containment of the normalised strings (shorter >= 4 chars)
    or content-token Jaccard >= 0.5 with >= 2 shared tokens."""
    na, nb = norm2(a), norm2(b)
    if not na or not nb:
        return False
    short, long_ = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(short) >= 4 and short in long_:
        return True
    ta, tb = content_tokens(a), content_tokens(b)
    inter = ta & tb
    return len(inter) >= 2 and len(inter) / len(ta | tb) >= 0.5


def norm_occurrences(hay_norm, needle):
    """(start, end) of every occurrence of bench_norm(needle) in an already bench-normalised text."""
    n = bench_norm(needle)
    out, i = [], hay_norm.find(n) if n else -1
    while i >= 0 and n:
        out.append((i, i + len(n)))
        i = hay_norm.find(n, i + 1)
    return out


def occurrence_status(hay_norm, needle, wrong, off_topic):
    """For a needle occurring in the text: 'wrong' if an occurrence overlaps a verified wrong span there,
    'off_topic' if it overlaps only an off-topic span, 'unflagged' otherwise, None if it does not occur."""
    occ = norm_occurrences(hay_norm, needle)
    if not occ:
        return None
    W = [iv for w in wrong for iv in norm_occurrences(hay_norm, w)]
    O = [iv for o in off_topic for iv in norm_occurrences(hay_norm, o)]
    ov = lambda a, b: a[0] < b[1] and b[0] < a[1]
    if any(ov(a, b) for a in occ for b in W):
        return 'wrong'
    if any(ov(a, b) for a in occ for b in O):
        return 'off_topic'
    return 'unflagged'


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def jl(path):
    with open(path) as f:
        return [json.loads(x) for x in f if x.strip()]


def u16_to_py(text, s, e):
    b = text.encode('utf-16-le')
    pre = b[:2 * s].decode('utf-16-le')
    mid = b[2 * s:2 * e].decode('utf-16-le')
    return len(pre), len(pre) + len(mid)


# ---------------------------------------------------------------- loading
def kfmt(item, layer, pos):
    return f'{item}.L{layer}.p{pos}'


def load_pilot():
    """Per (k, idx): text, class, kind, wrong[], off_topic[], claims, wrong span whys."""
    out = {}
    contracts = []
    for idx in range(N):
        root = PILOT / f'candidate_index_{idx:02d}-n32'
        cond = json.load(open(root / 'condition.json'))
        con = json.load(open(root / 'hallucination/project_contract.json'))
        res = json.load(open(root / 'hallucination/results.json'))
        contracts.append((idx, cond, con, res['config']))
        readouts = {kfmt(r['id'], r['layer'], r['pos']): r['samples'] for r in jl(root / 'hallucination.readouts.jsonl')}
        raw = {}
        for r in jl(root / 'hallucination/cells.jsonl'):
            if r.get('result') is not None:
                raw[r['key']] = r  # last non-null row per key wins
        for row in res['rows']:
            k = kfmt(row['id'], row['layer'], row['pos'])
            assert len(row['verdict']) == 1 and len(row['samples']) == 1
            v = row['verdict'][0]
            s1 = raw[row['key']]['result']['samples'][0]
            whys = collections.defaultdict(list)
            for sp in s1.get('spans', []):
                whys[(sp.get('type'), sp['text'])].append(sp.get('why', ''))
            wrong = []
            for t in v['wrong']:
                w = whys.get(('wrong', t)) or [x for (ty, tt), xs in whys.items() if tt == t and ty != 'off_topic' for x in xs]
                wrong.append({'text': t, 'why': w[0] if w else ''})
            out[(k, idx)] = {'text': row['samples'][0], 'readout_text': readouts[k][0], 'class': v['class'],
                             'kind': v['kind'], 'wrong': wrong, 'off_topic': list(v['off_topic']),
                             'claims': v['claims'], 'rationale': s1.get('rationale', ''),
                             'cache_origin': (raw[row['key']].get('shared_cache_hit') or {}).get('origin', {}).get('response_id')}
    return out, contracts


def load_scores():
    sc = {}
    with open(SCORES) as f:
        for line in f:
            if '"family": "hallucination"' not in line:
                continue
            r = json.loads(line)
            if r['family'] != 'hallucination':
                continue
            k = kfmt(r['item_id'], r['layer'], r['position'])
            sc[(k, r['source_sample_index'])] = {'text': r['text'], 'fve': r['fits']['exact']['fve'],
                                                 'a_eligible': r['a_eligible'], 'parser_flags': r['parser_flags'],
                                                 'token_count': r['token_count'], 'bullet_count': r['bullet_count'],
                                                 'truncated': any(a['truncated'] for a in r['atoms'])}
    return sc


def read_flat(path, keys=None):
    pools = collections.defaultdict(dict)
    with open(path, 'rb') as f:
        for line in f:
            if b'"family": "hallucination"' not in line:
                continue
            r = json.loads(line)
            if r.get('family') != 'hallucination':
                continue
            k = kfmt(r['item_id'], r['layer'], r['position'])
            if keys is not None and k not in keys:
                continue
            si = int(r['sample_index'])
            assert si not in pools[k], (k, si)
            pools[k][si] = r['text']
    return pools


# ---------------------------------------------------------------- verification
def verify(pilot, contracts, scores, cells_keys, page_cells, three):
    v = {}
    # 1. judge identity
    exp_con = json.load(open(EXP_J / 'capped_n1-n1/hallucination/project_contract.json'))
    exp_cfg = json.load(open(EXP_J / 'capped_n1-n1/hallucination/results.json'))['config']
    pins = set()
    for idx, cond, con, cfg in contracts:
        pins.add(json.dumps({'commit': con['benchmark_commit'], 'hashes': con['runtime_source_hashes'],
                             'model': con['project_judge_model'], 'effort': con['project_reasoning_effort'],
                             'prompt': cfg['prompt_version'], 'verify': cfg['verify_prompt_version'],
                             'cfg_model': cfg['judge_model'], 'reasoning': cfg['reasoning']}, sort_keys=True))
        st2 = con['hallucination_stage2']
        assert st2['stage1_api_or_missing_readouts'] == 0 and st2['stage2_api_or_missing_readouts'] == 0, idx
        assert st2['judged_readouts'] == 72 and st2['claim_tallied_readouts'] == 72, idx
        assert cond['method'] == f'candidate_index_{idx:02d}' and cond['n'] == 32, idx
    assert len(pins) == 1
    pin = json.loads(pins.pop())
    exp_pin = {'commit': exp_con['benchmark_commit'], 'hashes': exp_con['runtime_source_hashes'],
               'model': exp_con['project_judge_model'], 'effort': exp_con['project_reasoning_effort'],
               'prompt': exp_cfg['prompt_version'], 'verify': exp_cfg['verify_prompt_version'],
               'cfg_model': exp_cfg['judge_model'], 'reasoning': exp_cfg['reasoning']}
    hall_src = {p: h for p, h in pin['hashes'].items() if 'hallucination' in p or p.endswith(('llm.py', 'mcjudge.py', 'cache.py'))}
    now = {p: sha256_file(BENCH / p) for p in hall_src}
    v['judge'] = {
        'pilot_conditions_with_identical_pins': 32,
        'judge_model': pin['model'], 'reasoning_effort': pin['effort'], 'prompt_version': pin['prompt'],
        'verify_prompt_version': pin['verify'], 'benchmark_commit': pin['commit'],
        'identical_to_full_bank_expansion_v1_pins': pin == exp_pin,
        'judge_source_hashes_match_repo_now': now == hall_src,
        'stage1_and_stage2_complete_all_32_conditions': True,
        'note': 'Same judge code (judge.py/prompts.py/score.py sha256), same model, prompt v5c-chat + v5c-chat-verify-v1, '
                'reasoning none, k=1 readout per call, as the page / full bank.',
    }
    # 2. judged text == exact FVE score text; sample index provenance
    mism = sum(pilot[(k, i)]['text'] != scores[(k, i)]['text'] or pilot[(k, i)]['readout_text'] != pilot[(k, i)]['text']
               for k in cells_keys for i in range(N))
    v['judged_text_equals_scored_text'] = {'mismatches': mism, 'candidates': len(cells_keys) * N}
    # 3. raw pool identity (pilot export vs full-grid development flat pool)
    man = json.load(open(MANIFEST))
    flat_man = json.load(open(str(DEV_FLAT).replace('.jsonl', '.manifest.json')))
    exp_dev = {s['path'].rsplit('/', 1)[1]: s['sha256'] for s in man['stages']['development']['samples']}
    flat_par = {p.rsplit('/', 1)[1]: h for p, h in flat_man['parent_journal_sha256'].items()}
    keys = set(cells_keys)
    pil = read_flat(PILOT_SAMPLES, keys)
    full = read_flat(DEV_FLAT, keys)
    same_cells = sum(all(pil[k].get(i) == full[k].get(i) for i in range(N)) for k in keys)
    same_samples = sum(pil[k].get(i) == full[k].get(i) and pil[k].get(i) is not None for k in keys for i in range(N))
    v['pool_identity'] = {
        'dev_flat_parents_equal_expansion_manifest_dev_samples': exp_dev == flat_par,
        'pilot_pool_global_id': json.load(open(str(PILOT_SAMPLES).replace('.jsonl', '.manifest.json')))['global_pool_id'],
        'full_grid_pool_global_id': flat_man.get('global_pool_id'),
        'cells_with_all_32_raw_texts_identical': same_cells, 'samples_identical': same_samples,
        'cells': len(keys), 'samples': len(keys) * N}
    # 4. reproduce full-bank Original (sample 0) and Best of 32 (FVE argmax) texts / scores
    orig_same = best_same = trace_ok = 0
    max_diff = 0.0
    for k in cells_keys:
        pc = page_cells[k]['settings']
        if pc['capped_n1-n1']['text'] == pilot[(k, 0)]['text']:
            orig_same += 1
        win = max(range(N), key=lambda i: (scores[(k, i)]['fve'], -i))
        if pc['best_n_exact-n32']['text'] == scores[(k, win)]['text']:
            best_same += 1
        tr = three[k]['settings']['best_n_exact-n32']['trace']
        tmap = {int(t['sample_id'].rsplit(':', 1)[1]): t['score'] for t in tr}
        d = max(abs(tmap[i] - scores[(k, i)]['fve']) for i in range(N))
        max_diff = max(max_diff, d)
        trace_ok += d < 1e-5
    v['full_bank_reproduction'] = {
        'original_text_equals_pilot_sample0': orig_same, 'best_of_32_text_equals_pilot_fve_winner': best_same,
        'cells_full_bank_trace_scores_equal_pilot_fve_within_1e-5': trace_ok, 'max_abs_fve_diff': max_diff,
        'cells': len(cells_keys)}
    # 5. are full-bank Original verdicts the same judge calls as pilot sample-0 verdicts?
    exp_orig = {}
    for r in jl(EXP_J / 'capped_n1-n1/hallucination/cells.jsonl'):
        if ':V' in r['key'] or r.get('result') is None:
            continue
        exp_orig[r['key']] = (r.get('shared_cache_hit') or {}).get('origin', {}).get('response_id')
    same_call = 0
    for k in cells_keys:
        item, L, p = k.split('.L')[0], int(k.split('.L')[1].split('.p')[0]), k.split('.p')[-1]
        jk = f'{item}__L{L:03d}__p{p}'
        same_call += exp_orig.get(jk) is not None and exp_orig.get(jk) == pilot[(k, 0)]['cache_origin']
    v['full_bank_original_verdict_is_same_judge_call_as_pilot_sample0'] = {'cells': same_call, 'of': len(cells_keys),
        'note': 'Shared exact-request cache: these are not independent judge repeats.'}
    # 6. within-cell duplicate texts (share one cached verdict)
    dup_cells = dup_samples = 0
    for k in cells_keys:
        c = collections.Counter(pilot[(k, i)]['text'] for i in range(N))
        extra = sum(n - 1 for n in c.values() if n > 1)
        dup_samples += extra
        dup_cells += extra > 0
    v['within_cell_duplicate_texts'] = {'cells_with_duplicates': dup_cells, 'duplicate_samples': dup_samples}
    return v


# ---------------------------------------------------------------- span / element analysis
def context_vocab(item):
    ctx = item['prompt'] + '\n' + item['response']
    return {w.lower() for w in words(ctx)} | set(nums(ctx)), ctx


def span_elements(text, vocab, lower_vocab_pool):
    """Key elements of a wrong span: novel names and novel numbers; else novel content words."""
    names, numbers, content = [], [], []
    for w in words(text):
        lw = w.lower()
        if lw in vocab:
            continue
        if w[0].isupper() and w not in NOT_NAME and w.rstrip("'s") not in NOT_NAME and lw not in STOP and len(w) >= 2 \
                and lw not in lower_vocab_pool:
            names.append(w)
        elif lw not in STOP and len(lw) >= 4:
            content.append(lw)
    for n in nums(text):
        if len(n) < 2:  # single digits are mostly list numbering
            continue
        if n not in vocab and n.rstrip('.') not in vocab:
            numbers.append(n)
    names = list(dict.fromkeys(names))
    numbers = list(dict.fromkeys(numbers))
    content = list(dict.fromkeys(content))
    if names or numbers:
        return [('name', x) for x in names] + [('number', x) for x in numbers]
    return [('content', x) for x in content]


def span_type(text, elems):
    t = []
    if any(e[0] == 'name' for e in elems):
        t.append('novel_name')
    if any(e[0] == 'number' for e in elems):
        t.append('novel_number')
    if FIRST_PERSON.search(text):
        t.append('first_person')
    if _CJK.search(text):
        t.append('cjk_text')
    return t or ['other']


def analyse_cell_errors(k, samples, vocab):
    """samples: list of 32 dicts {text, class, wrong[{text,why}], off_topic[]}."""
    # words that appear lowercased somewhere in the 32 texts are ordinary words, not names
    lower_pool = set()
    for s in samples:
        lower_pool |= {w for w in words(s['text']) if w.islower()}
    texts = [s['text'] for s in samples]
    norm_texts = [bench_norm(t) for t in texts]
    spans = []
    for i, s in enumerate(samples):
        for w in s['wrong']:
            el = span_elements(w['text'], vocab, lower_pool)
            spans.append({'sample': i, 'text': w['text'], 'why': w['why'], 'elements': el, 'types': span_type(w['text'], el)})
    # span-level recurrence
    for sp in spans:
        i = sp['sample']
        rec, rec_ident, appear_unflagged, appear_off, absent = [], 0, [], [], 0
        for j in range(N):
            if j == i:
                continue
            if texts[j] == texts[i]:
                rec_ident += 1  # same text -> same cached verdict; not counted
                continue
            st = occurrence_status(norm_texts[j], sp['text'], [w['text'] for w in samples[j]['wrong']],
                                   samples[j]['off_topic'])
            hit = st == 'wrong'
            for w2 in ([] if hit else samples[j]['wrong']):
                if texts_overlap(sp['text'], w2['text']) or any(
                        has_word(w2['text'], e[1]) for e in sp['elements'] if e[0] in ('name', 'number')):
                    hit = True
                    break
            if hit:
                rec.append(j)
                continue
            ns = bench_norm(sp['text'])
            if st == 'off_topic' and len(ns) >= 3:
                appear_off.append(j)
                continue
            appears = (len(ns) >= 3 and ns in norm_texts[j]) or any(
                has_word(texts[j], e[1]) for e in sp['elements'] if e[0] in ('name', 'number'))
            if appears:
                appear_unflagged.append(j)
            else:
                absent += 1
        sp['recur_flagged_other'] = rec
        sp['appears_unflagged_other'] = appear_unflagged
        sp['appears_off_topic_flagged_other'] = appear_off
        sp['identical_text_other'] = rec_ident
    # element-level judge (in)consistency: names/numbers/content words, distinct texts only
    elements = collections.OrderedDict()
    for sp in spans:
        for e in sp['elements']:
            elements.setdefault(e, []).append(sp)
    el_rows = []
    seen_text = {}
    for i, t in enumerate(texts):
        seen_text.setdefault(t, i)
    distinct = sorted(set(seen_text.values()))
    for (etype, e), sps in elements.items():
        flagged, unflagged, offtopic_only = [], [], []
        for j in distinct:
            if not has_word(texts[j], e):
                continue
            in_wrong = any(has_word(w['text'], e) for w in samples[j]['wrong'])
            in_off = any(has_word(o, e) for o in samples[j]['off_topic'])
            if in_wrong:
                flagged.append(j)
            elif in_off:
                offtopic_only.append(j)
            else:
                unflagged.append(j)
        el_rows.append({'element': e, 'type': etype, 'appears_distinct_samples': len(flagged) + len(unflagged) + len(offtopic_only),
                        'flagged_wrong': flagged, 'flagged_off_topic_only': offtopic_only, 'unflagged': unflagged,
                        'example_span': sps[0]['text'], 'example_sample': sps[0]['sample'], 'example_why': sps[0]['why']})
    return spans, el_rows


# ---------------------------------------------------------------- bootstrap
def boot_ratio(rows, num, den, groups_key='item', reps=BOOT, seed=SEED):
    """Chat-level cluster bootstrap of sum(num)/sum(den). rows: list of dicts."""
    by = collections.defaultdict(list)
    for r in rows:
        by[r[groups_key]].append(r)
    g = sorted(by)
    tot_n = sum(num(r) for r in rows)
    tot_d = sum(den(r) for r in rows)
    est = tot_n / tot_d if tot_d else None
    if len(g) < 2 or not tot_d:
        return {'estimate': est, 'num': tot_n, 'den': tot_d, 'ci95': None, 'chats': len(g)}
    rng = random.Random(seed)
    vals = []
    for _ in range(reps):
        pick = [rng.choice(g) for _ in g]
        n_ = sum(num(r) for c in pick for r in by[c])
        d_ = sum(den(r) for c in pick for r in by[c])
        if d_:
            vals.append(n_ / d_)
    vals.sort()
    lo, hi = vals[int(0.025 * len(vals))], vals[min(len(vals) - 1, int(0.975 * len(vals)))]
    return {'estimate': est, 'num': tot_n, 'den': tot_d, 'ci95': [lo, hi], 'chats': len(g),
            'defined_draws': len(vals)}


# ---------------------------------------------------------------- main
def main():
    pilot, contracts = load_pilot()
    scores = load_scores()
    cells_keys = sorted({k for k, _ in pilot})
    assert len(cells_keys) == 72 and len(pilot) == 72 * N and all((k, i) in scores for k in cells_keys for i in range(N))
    index = json.load(open(PAGE / 'index.json'))
    page_idx = {c['k']: c for c in index['cells']}
    items = {}
    page_cells = {}
    for it in sorted({k.split('.L')[0] for k in cells_keys}):
        d = json.load(open(PAGE / 'items' / f'{it}.json'))
        items[it] = d['item']
        page_cells.update(d['cells'])
    three = {}
    with open(THREE) as f:
        for line in f:
            r = json.loads(line)
            k = kfmt(r['item_id'], r['layer'], r['position'])
            if k in set(cells_keys):
                three[k] = r
    ver = verify(pilot, contracts, scores, cells_keys, page_cells, three)
    print(json.dumps(ver, indent=1), flush=True)

    cell_rows = []
    all_spans = []
    all_elems = []
    for k in cells_keys:
        item_id = k.split('.L')[0]
        it = items[item_id]
        layer = int(k.split('.L')[1].split('.p')[0])
        pos = int(k.split('.p')[-1])
        site = {s['pos']: s for s in it['sites']}[pos]
        resp = it['response']
        c = max(0, min(int(site['char']), len(resp)))
        vocab, _ = context_vocab(it)
        samples = []
        for i in range(N):
            p, s = pilot[(k, i)], scores[(k, i)]
            samples.append({'idx': i, 'text': p['text'], 'class': p['class'], 'kind': p['kind'], 'wrong': p['wrong'],
                            'off_topic': p['off_topic'], 'claims': p['claims'], 'fve': s['fve'],
                            'a_eligible': s['a_eligible'], 'rationale': p['rationale']})
        cnt = collections.Counter(s['class'] for s in samples)
        elig = [s for s in samples if s['a_eligible']]
        ecnt = collections.Counter(s['class'] for s in elig)
        order = sorted(elig, key=lambda s: (-s['fve'], s['idx']))  # selector tie-break: lowest index
        top = order[0]
        rank_clean = next((r + 1 for r, s in enumerate(order) if s['class'] == 'consistent'), None)
        rank_nonwrong = next((r + 1 for r, s in enumerate(order) if s['class'] != 'hallucinated'), None)
        distinct = len({s['text'] for s in samples})
        n_h, n_c = cnt['hallucinated'], cnt['consistent']
        if n_c == 0:
            cls = 'unavoidable'
        elif n_h >= 0.75 * N:
            cls = 'hard'
        elif n_c > N / 2:
            cls = 'easy'
        else:
            cls = 'mixed'
        # sensitivity: 'clean' = any non-hallucinated (off-topic / generic allowed)
        n_nw = N - n_h
        cls_nw = 'unavoidable' if n_nw == 0 else 'hard' if n_h >= 0.75 * N else 'easy' if n_nw > N / 2 else 'mixed'
        spans, el_rows = analyse_cell_errors(k, samples, vocab)
        # 'suspect clean': a consistent sample containing (i) verbatim (normalised, >=8 chars) a wrong span the
        # judge verified in another sample of this cell, or (ii) a novel name/number flagged wrong in >=2 other samples
        flagged_el = collections.Counter()
        for e in el_rows:
            if e['type'] in ('name', 'number'):
                flagged_el[e['element']] = len(e['flagged_wrong'])
        suspect, suspect_el = {}, {}
        for s in samples:
            if s['class'] != 'consistent':
                continue
            nt = bench_norm(s['text'])
            why = None
            for sp in spans:
                if sp['sample'] != s['idx'] and len(bench_norm(sp['text'])) >= 8 and bench_norm(sp['text']) in nt:
                    why = {'reason': 'contains_span_flagged_elsewhere', 'span': sp['text'], 'flagged_in_sample': sp['sample'],
                           'why_there': sp['why']}
                    break
            if why is not None:
                suspect[s['idx']] = why
                continue
            for e in el_rows:
                if e['type'] in ('name', 'number') and len([j for j in e['flagged_wrong'] if j != s['idx']]) >= 2 \
                        and has_word(s['text'], e['element']):
                    suspect_el[s['idx']] = {'reason': 'contains_element_flagged_in_>=2_other_samples', 'element': e['element'],
                                            'flagged_in_samples': e['flagged_wrong'][:10], 'example_span': e['example_span']}
                    break
        n_c_strict = n_c - len(suspect)
        n_c_loose = n_c - len(suspect) - len(suspect_el)
        if n_c_strict == 0:
            cls_strict = 'unavoidable'
        elif n_h >= 0.75 * N:
            cls_strict = 'hard'
        elif n_c_strict > N / 2:
            cls_strict = 'easy'
        else:
            cls_strict = 'mixed'
        for sp in spans:
            sp.update({'k': k, 'item': item_id, 'layer': layer, 'source': it['source'], 'cell_class': cls,
                       'sample_class': samples[sp['sample']]['class']})
        for e in el_rows:
            e.update({'k': k, 'item': item_id, 'layer': layer, 'source': it['source'], 'cell_class': cls})
        all_spans += spans
        all_elems += el_rows
        pc = page_cells[k]['settings']
        full_bank = {sid: pc[sid]['label'] for sid in SETTINGS}
        full_bank['raw_n1-n1'] = pc.get('raw_n1-n1', {}).get('label')
        ex_h = next((s for s in sorted(samples, key=lambda s: -len(s['wrong'])) if s['class'] == 'hallucinated'), None)
        ex_c = next((s for s in order if s['class'] == 'consistent'), None)
        row = {
            'k': k, 'link': LINK + k, 'item': item_id, 'source': it['source'], 'layer': layer, 'pos': pos,
            'site_kind': site['kind'], 'read_token': site['token'],
            'prompt': it['prompt'][:600], 'before': resp[max(0, c - 300):c], 'after': resp[c:c + 200],
            'counts': {x: cnt.get(x, 0) for x in ('hallucinated', 'consistent', 'off_topic', 'generic', 'empty')},
            'counts_eligible': {x: ecnt.get(x, 0) for x in ('hallucinated', 'consistent', 'off_topic', 'generic', 'empty')},
            'n_samples': N, 'n_eligible': len(elig), 'distinct_texts': distinct,
            'p_random_hallucinated': n_h / N,
            'p_random_hallucinated_among_asserting': n_h / max(1, n_h + n_c + cnt['off_topic']),
            'consistent_asserting_available': n_c > 0,
            'nonhallucinated_available': n_nw > 0,
            'consistent_not_suspect': n_c_strict, 'consistent_available_strict': n_c_strict > 0,
            'suspect_clean_samples': {str(i): w for i, w in suspect.items()},
            'consistent_available_strict_plus_elements': n_c_loose > 0,
            'suspect_clean_samples_element_rule_only': {str(i): w for i, w in suspect_el.items()},
            'cell_class_strict': cls_strict,
            'top_fve_sample': top['idx'], 'top_fve': top['fve'], 'top_fve_class': top['class'],
            'top_fve_is_clean': top['class'] == 'consistent',
            'best_clean_rank_by_fve': rank_clean, 'best_nonwrong_rank_by_fve': rank_nonwrong,
            'best_clean_sample': next((s['idx'] for s in order if s['class'] == 'consistent'), None),
            'cell_class': cls, 'cell_class_if_offtopic_or_generic_counts_as_clean': cls_nw,
            'unavoidable_reason': None if cls != 'unavoidable' else (
                'all_32_hallucinated' if n_h == N else '>=75%_hallucinated_rest_off_topic_or_generic' if n_h >= 0.75 * N
                else 'off_topic_heavy'),
            'original_sample0_class': samples[0]['class'],
            'full_bank_labels': full_bank,
            'error_elements': [{x: e[x] for x in ('element', 'type', 'appears_distinct_samples', 'flagged_wrong',
                                                   'flagged_off_topic_only', 'unflagged', 'example_span', 'example_sample',
                                                   'example_why')} for e in el_rows],
            'wrong_spans': [{x: sp[x] for x in ('sample', 'text', 'why', 'elements', 'types', 'recur_flagged_other',
                                                'appears_unflagged_other', 'appears_off_topic_flagged_other',
                                                'identical_text_other')} for sp in spans],
            'example_hallucinated_sample': None if ex_h is None else {
                'idx': ex_h['idx'], 'fve': ex_h['fve'], 'text': ex_h['text'], 'wrong': ex_h['wrong'],
                'off_topic': ex_h['off_topic']},
            'example_clean_sample': None if ex_c is None else {'idx': ex_c['idx'], 'fve': ex_c['fve'], 'text': ex_c['text'],
                                                                 'claims': ex_c['claims']},
            'samples': [{'idx': s['idx'], 'class': s['class'], 'fve': round(s['fve'], 5), 'a_eligible': s['a_eligible'],
                         'wrong': [w['text'] for w in s['wrong']], 'off_topic': s['off_topic'], 'text': s['text']}
                        for s in samples],
        }
        cell_rows.append(row)

    # ------------------------------------------------ summaries
    def summarise(rows):
        n = len(rows)
        cls = collections.Counter(r['cell_class'] for r in rows)
        cls_nw = collections.Counter(r['cell_class_if_offtopic_or_generic_counts_as_clean'] for r in rows)
        tot = collections.Counter()
        for r in rows:
            tot.update(r['counts'])
        o_h = [r for r in rows if r['original_sample0_class'] == 'hallucinated']
        return {
            'cells': n, 'chats': len({r['item'] for r in rows}),
            'sample_label_totals': dict(tot),
            'cell_classes': {c: cls.get(c, 0) for c in ('easy', 'mixed', 'hard', 'unavoidable')},
            'cell_classes_if_offtopic_or_generic_counts_as_clean': {c: cls_nw.get(c, 0) for c in ('easy', 'mixed', 'hard', 'unavoidable')},
            'p_random_hallucinated': boot_ratio(rows, lambda r: r['counts']['hallucinated'], lambda r: N),
            'original_hallucinated': boot_ratio(rows, lambda r: r['original_sample0_class'] == 'hallucinated', lambda r: 1),
            'top_fve_hallucinated': boot_ratio(rows, lambda r: r['top_fve_class'] == 'hallucinated', lambda r: 1),
            'top_fve_clean': boot_ratio(rows, lambda r: r['top_fve_is_clean'], lambda r: 1),
            'consistent_available': boot_ratio(rows, lambda r: r['consistent_asserting_available'], lambda r: 1),
            'share_unavoidable': boot_ratio(rows, lambda r: r['cell_class'] == 'unavoidable', lambda r: 1),
            'share_hard_or_unavoidable': boot_ratio(rows, lambda r: r['cell_class'] in ('hard', 'unavoidable'), lambda r: 1),
            'share_easy': boot_ratio(rows, lambda r: r['cell_class'] == 'easy', lambda r: 1),
            'original_halluc_avoidable_by_perfect_selector_clean': boot_ratio(
                rows, lambda r: r['original_sample0_class'] == 'hallucinated' and r['consistent_asserting_available'],
                lambda r: r['original_sample0_class'] == 'hallucinated'),
            'original_halluc_avoidable_any_nonwrong': boot_ratio(
                rows, lambda r: r['original_sample0_class'] == 'hallucinated' and r['nonhallucinated_available'],
                lambda r: r['original_sample0_class'] == 'hallucinated'),
            'consistent_available_strict': boot_ratio(rows, lambda r: r['consistent_available_strict'], lambda r: 1),
            'original_halluc_avoidable_by_perfect_selector_clean_strict': boot_ratio(
                rows, lambda r: r['original_sample0_class'] == 'hallucinated' and r['consistent_available_strict'],
                lambda r: r['original_sample0_class'] == 'hallucinated'),
            'cell_classes_strict': {c: collections.Counter(r['cell_class_strict'] for r in rows).get(c, 0)
                                    for c in ('easy', 'mixed', 'hard', 'unavoidable')},
            'consistent_samples': sum(r['counts']['consistent'] for r in rows),
            'consistent_samples_suspect': sum(len(r['suspect_clean_samples']) for r in rows),
            'consistent_samples_suspect_element_rule_only': sum(len(r['suspect_clean_samples_element_rule_only']) for r in rows),
            'consistent_available_strict_plus_elements': boot_ratio(rows, lambda r: r['consistent_available_strict_plus_elements'], lambda r: 1),
            'original_halluc_avoidable_strict_plus_elements': boot_ratio(
                rows, lambda r: r['original_sample0_class'] == 'hallucinated' and r['consistent_available_strict_plus_elements'],
                lambda r: r['original_sample0_class'] == 'hallucinated'),
            'perfect_selector_output_hallucinated': boot_ratio(rows, lambda r: not r['nonhallucinated_available'], lambda r: 1),
            'original_hallucinated_cells': len(o_h),
            'best_clean_rank_median_where_available': statistics.median([r['best_clean_rank_by_fve'] for r in rows
                                                                         if r['best_clean_rank_by_fve']]) if any(r['best_clean_rank_by_fve'] for r in rows) else None,
        }

    by_layer = {L: summarise([r for r in cell_rows if r['layer'] == L]) for L in (20, 44, 60)}
    by_source = {s: summarise([r for r in cell_rows if r['source'] == s]) for s in ('dailydialog', 'lmsys')}
    overall = summarise(cell_rows)
    by_chat = {}
    for it in sorted({r['item'] for r in cell_rows}):
        rr = [r for r in cell_rows if r['item'] == it]
        by_chat[it] = {'source': rr[0]['source'], 'prompt_short': rr[0]['prompt'][:80],
                       'p_random_hallucinated': sum(r['counts']['hallucinated'] for r in rr) / (N * len(rr)),
                       'classes': dict(collections.Counter(r['cell_class'] for r in rr))}

    # rank distribution of best clean sample
    ranks = [r['best_clean_rank_by_fve'] for r in cell_rows if r['best_clean_rank_by_fve']]
    rank_dist = {'n_cells_with_clean': len(ranks), 'rank1': sum(x == 1 for x in ranks),
                 'rank_le_3': sum(x <= 3 for x in ranks), 'rank_le_5': sum(x <= 5 for x in ranks),
                 'rank_gt_10': sum(x > 10 for x in ranks),
                 'median': statistics.median(ranks) if ranks else None,
                 'expected_rank_if_fve_uninformative_median': statistics.median(
                     [(N + 1) / (r['counts']['consistent'] + 1) for r in cell_rows if r['counts']['consistent']]),
                 'mean_observed': statistics.mean(ranks) if ranks else None,
                 'mean_expected_if_fve_uninformative': statistics.mean(
                     [(N + 1) / (r['counts']['consistent'] + 1) for r in cell_rows if r['counts']['consistent']]),
                 'top_fve_clean_observed_cells': sum(r['top_fve_is_clean'] for r in cell_rows),
                 'top_fve_clean_expected_random_pick': sum(r['counts']['consistent'] / N for r in cell_rows),
                 'top_fve_hallucinated_observed_cells': sum(r['top_fve_class'] == 'hallucinated' for r in cell_rows),
                 'top_fve_hallucinated_expected_random_pick': sum(r['counts']['hallucinated'] / N for r in cell_rows),
                 'note': 'Expected rank of the best of c clean samples placed at random among 32 = 33/(c+1).'}

    # ------------------------------------------------ span / element summaries
    def span_summary(spans):
        n = len(spans)
        rec_any = sum(bool(s['recur_flagged_other']) for s in spans)
        rec_counts = [len(s['recur_flagged_other']) for s in spans]
        types = collections.Counter(t for s in spans for t in s['types'])
        return {'wrong_spans': n, 'recur_in_>=1_other_sample': rec_any,
                'recur_in_>=4_other_samples': sum(x >= 4 for x in rec_counts),
                'singletons_no_recurrence': n - rec_any,
                'mean_other_samples_flagged': statistics.mean(rec_counts) if rec_counts else None,
                'median_other_samples_flagged': statistics.median(rec_counts) if rec_counts else None,
                'spans_also_appearing_unflagged_in_other_samples': sum(bool(s['appears_unflagged_other']) for s in spans),
                'types': dict(types)}

    span_by_cls = {c: span_summary([s for s in all_spans if s['cell_class'] == c]) for c in ('easy', 'mixed', 'hard', 'unavoidable')}
    span_by_type = {}
    for t in ('novel_name', 'novel_number', 'first_person', 'cjk_text', 'other'):
        ss = [s for s in all_spans if t in s['types']]
        span_by_type[t] = span_summary(ss)
    named = [e for e in all_elems if e['type'] in ('name', 'number')]
    multi = [e for e in named if e['appears_distinct_samples'] >= 2]
    incons = [e for e in multi if e['flagged_wrong'] and e['unflagged']]
    el_summary = {
        'elements_all_types': len(all_elems),
        'name_number_elements': len(named),
        'name_number_elements_appearing_in_>=2_distinct_samples': len(multi),
        'of_those_flagged_in_some_unflagged_in_others': len(incons),
        'appearances_flagged_wrong': sum(len(e['flagged_wrong']) for e in multi),
        'appearances_flagged_off_topic_only': sum(len(e['flagged_off_topic_only']) for e in multi),
        'appearances_unflagged': sum(len(e['unflagged']) for e in multi),
        'flag_rate_given_appearance': (sum(len(e['flagged_wrong']) for e in multi) /
                                       max(1, sum(e['appears_distinct_samples'] for e in multi))),
        'content_word_elements': len([e for e in all_elems if e['type'] == 'content']),
        'content_word_elements_appearing_in_>=2': len([e for e in all_elems if e['type'] == 'content' and e['appears_distinct_samples'] >= 2]),
        'content_word_flag_rate_given_appearance': (
            sum(len(e['flagged_wrong']) for e in all_elems if e['type'] == 'content' and e['appears_distinct_samples'] >= 2) /
            max(1, sum(e['appears_distinct_samples'] for e in all_elems if e['type'] == 'content' and e['appears_distinct_samples'] >= 2))),
    }
    # exact-text span recurrence (cleanest judge-consistency check): a verified wrong span whose
    # normalised text occurs verbatim in another distinct-text sample: flagged there or not?
    ex_flag = ex_unflag = ex_off = 0
    ex_examples = []
    for r in cell_rows:
        texts = [s['text'] for s in r['samples']]
        firsts = {}
        for i, t in enumerate(texts):
            firsts.setdefault(t, i)
        dist = sorted(set(firsts.values()))
        seen = set()
        for s in r['samples']:
            for w in s['wrong']:
                nw = bench_norm(w)
                if len(nw) < 8 or (nw, s['idx']) in seen:
                    continue
                seen.add((nw, s['idx']))
                for j in dist:
                    if texts[j] == s['text']:
                        continue
                    st = occurrence_status(bench_norm(texts[j]), w, r['samples'][j]['wrong'], r['samples'][j]['off_topic'])
                    if st is not None:
                        if st == 'wrong':
                            ex_flag += 1
                        elif st == 'off_topic':
                            ex_off += 1
                        else:
                            ex_unflag += 1
                            if len(ex_examples) < 400:
                                ex_examples.append({'k': r['k'], 'span': w, 'flagged_in_sample': s['idx'],
                                                    'unflagged_in_sample': j, 'class_there': r['samples'][j]['class']})
    exact_rec = {'pairs_flagged_wrong_again': ex_flag, 'pairs_flagged_off_topic_instead': ex_off,
                 'pairs_not_flagged': ex_unflag,
                 'wrong_flag_rate': ex_flag / max(1, ex_flag + ex_unflag + ex_off),
                 'manual_check': 'Read 24 random unflagged pairs (pre-fix version of this check): 19 were the same claim in the same role left '
                                 'unflagged, 2 were flagged off_topic instead, 1 was actually flagged (overlap check, since fixed), 1 differed '
                                 "legitimately in context (\"developed by Alibaba Group's Tongyi Lab\"), 1 had a wrong original flag.",
                 'note': 'Unit = (wrong span of >=8 normalised chars, other distinct-text sample of the same cell whose text contains it verbatim). '
                         'Directional pairs, so a span flagged in A and present in B counts once from A.'}

    # ------------------------------------------------ full-bank relation
    pilot_keys = set(cells_keys)
    fb = {'all': collections.Counter(), 'dev_L20_44_60': collections.Counter(), 'pilot72': collections.Counter()}
    for c in index['cells']:
        lab = [LABELS[s['c']] if s['c'] is not None else None for s in c['s']]
        if lab[0] != 'hallucinated':
            continue
        it = index['items'][c['i']]
        groups = ['all']
        if it['split'] == 'development' and c['L'] in (20, 44, 60):
            groups.append('dev_L20_44_60')
        if c['k'] in pilot_keys:
            groups.append('pilot72')
        rescued_c = 'consistent' in lab[1:]
        rescued_nw = any(x is not None and x != 'hallucinated' for x in lab[1:])
        for g in groups:
            fb[g]['original_hallucinated'] += 1
            fb[g]['best_or_combine_consistent'] += rescued_c
            fb[g]['best_or_combine_not_hallucinated'] += rescued_nw
            fb[g]['best_consistent'] += lab[1] == 'consistent'
            fb[g]['combine_consistent'] += lab[2] == 'consistent'
    tot_specific = sum(1 for c in index['cells'] if c['s'][0]['c'] is not None and LABELS[c['s'][0]['c']] in ('hallucinated', 'consistent', 'off_topic'))
    o_h_rows = [r for r in cell_rows if r['original_sample0_class'] == 'hallucinated']
    pil_ceiling = sum(r['consistent_asserting_available'] for r in o_h_rows)
    pil_lb = fb['pilot72']['best_or_combine_consistent']
    full_lb = fb['all']['best_or_combine_consistent'] / fb['all']['original_hallucinated']
    dev_rate = sum(1 for c in index['cells'] if index['items'][c['i']]['split'] == 'development' and c['L'] in (20, 44, 60)
                   and c['s'][0]['c'] is not None and LABELS[c['s'][0]['c']] == 'hallucinated')
    dev_spec = sum(1 for c in index['cells'] if index['items'][c['i']]['split'] == 'development' and c['L'] in (20, 44, 60)
                   and c['s'][0]['c'] is not None and LABELS[c['s'][0]['c']] in ('hallucinated', 'consistent', 'off_topic'))
    full_bank_rel = {
        'full_bank_counts': {g: dict(v) for g, v in fb.items()},
        'full_bank_original_hallucinated_of_specific': [fb['all']['original_hallucinated'], tot_specific],
        'observed_lower_bound_full_bank': {
            'share_of_original_halluc_where_best32_or_combine32_is_consistent': full_lb,
            'dev_L20_44_60': fb['dev_L20_44_60']['best_or_combine_consistent'] / max(1, fb['dev_L20_44_60']['original_hallucinated'])},
        'pilot': {
            'original_hallucinated_cells': len(o_h_rows),
            'perfect_selector_among_32_clean_available': pil_ceiling,
            'perfect_selector_among_32_nonwrong_available': sum(r['nonhallucinated_available'] for r in o_h_rows),
            'best32_or_combine32_consistent_(observable_lower_bound)': pil_lb,
            'ceiling_share': pil_ceiling / len(o_h_rows),
            'perfect_selector_among_32_clean_available_strict': sum(r['consistent_available_strict'] for r in o_h_rows),
            'lower_bound_share': pil_lb / len(o_h_rows),
            'top_fve_selector_(=Best of 32)_consistent': sum(r['top_fve_class'] == 'consistent' for r in o_h_rows),
            'top_fve_selector_hallucinated': sum(r['top_fve_class'] == 'hallucinated' for r in o_h_rows),
        },
        'representativeness': {
            'original_hallucinated_of_specific': {'pilot72': [sum(r['original_sample0_class'] == 'hallucinated' for r in cell_rows),
                                                              sum(r['original_sample0_class'] in ('hallucinated', 'consistent', 'off_topic') for r in cell_rows)],
                                                  'dev_L20_44_60': [dev_rate, dev_spec],
                                                  'full_bank': [fb['all']['original_hallucinated'], tot_specific]},
            'lower_bound_share': {'pilot72': pil_lb / len(o_h_rows), 'dev_L20_44_60': fb['dev_L20_44_60']['best_or_combine_consistent'] / max(1, fb['dev_L20_44_60']['original_hallucinated']),
                                  'full_bank': full_lb},
            'note': 'The pilot chats hallucinate more than the bank average and their observable lower bound is lower, so the pilot ceiling is '
                    'unlikely to overstate the bank-wide ceiling for that reason; it is still judge-optimistic (see strict). '
                    'A ratio extrapolation (bank lower bound x pilot ceiling/lower bound) saturates near 1 and is not reported.'},
    }

    # ------------------------------------------------ examples
    def pick(cls, key):
        rows = [r for r in cell_rows if r['cell_class'] == cls]
        return sorted(rows, key=key)[0] if rows else None

    examples = {
        'easy': pick('easy', lambda r: (-r['counts']['consistent'], r['original_sample0_class'] != 'hallucinated', r['k'])),
        'hard': pick('hard', lambda r: (-r['counts']['hallucinated'], r['k'])),
        'unavoidable': pick('unavoidable', lambda r: (-r['counts']['hallucinated'], r['k'])),
    }
    # prefer an easy example where Original (sample 0) hallucinated, to show an avoidable error
    easy_h = [r for r in cell_rows if r['cell_class'] == 'easy' and r['original_sample0_class'] == 'hallucinated']
    if easy_h:
        examples['easy_with_original_hallucinated'] = sorted(easy_h, key=lambda r: (-r['counts']['consistent'], r['k']))[0]
    # hand-picked after reading (see report): easy = Original's one-off error, fixed by Best of 32; hard = 30/32 wrong,
    # the 2 clean samples rank 21st+ by FVE; unavoidable = systematic wrong relation / location / number
    rowmap = {r['k']: r for r in cell_rows}
    for name, k in (('hand_easy', 'chat-dailydialog-0047.L20.p182'), ('hand_hard', 'chat-lmsys-0026.L20.p471'),
                    ('hand_unavoidable_relation', 'chat-lmsys-0023.L20.p464'),
                    ('hand_unavoidable_location', 'chat-lmsys-0025.L60.p80'),
                    ('hand_unavoidable_number', 'chat-lmsys-0052.L44.p428'),
                    ('hand_hard_judge_misses', 'chat-dailydialog-0002.L44.p20')):
        if k in rowmap:
            examples[name] = rowmap[k]
    ex_out = {}
    for name, r in examples.items():
        if r is None:
            continue
        ex_out[name] = {x: r[x] for x in ('k', 'link', 'source', 'layer', 'site_kind', 'read_token', 'prompt', 'before', 'after',
                                         'counts', 'p_random_hallucinated', 'top_fve_sample', 'top_fve_class', 'best_clean_rank_by_fve',
                                         'original_sample0_class', 'full_bank_labels', 'example_hallucinated_sample',
                                         'example_clean_sample', 'cell_class', 'cell_class_strict', 'consistent_not_suspect',
                                         'suspect_clean_samples')}
        ex_out[name]['top_elements'] = sorted(r['error_elements'], key=lambda e: -len(e['flagged_wrong']))[:5]

    result = {
        'meta': {
            'status': 'exploratory', 'generated_by': str(OUT / 'avoidability.py'),
            'sources': {'pilot_judgments': str(PILOT), 'scores': str(SCORES), 'pilot_samples': str(PILOT_SAMPLES),
                        'dev_full_grid_pool': str(DEV_FLAT), 'full_bank_judgments': str(EXP_J), 'page_data': str(PAGE)},
            'cells': len(cell_rows), 'chats': len(by_chat), 'layers': [20, 44, 60], 'split': 'development',
            'definitions': {
                'clean': "judge class 'consistent' (asserting readout with no verified wrong span and no off-topic span)",
                'asserting': 'class in {hallucinated, consistent, off_topic}',
                'p_random_hallucinated': 'hallucinated samples / 32 (sample multiplicity kept; duplicate texts share one cached verdict)',
                'cell_class': "priority order: unavoidable (0 consistent of 32) > hard (>=24/32 hallucinated) > easy (>16/32 consistent) > mixed",
                'top_fve_sample': 'highest exact joint FVE among A-eligible samples, ties -> lowest index (= Best of 32)',
                'best_clean_rank_by_fve': '1-based rank of the highest-FVE consistent sample among eligible samples sorted by FVE desc',
                'key_elements': 'per wrong span: novel capitalised words (not in prompt/reply, not a stop/sentence word, never lowercase in the cell\'s 32 samples) and novel numbers; if none, novel content words (len>=4, not stopword, not in prompt/reply)',
                'recur_flagged_other': "other distinct-text samples of the same cell with a verified wrong span that shares a name/number key element or normalised-overlaps the span text (containment >=4 chars, or content-token Jaccard>=0.5 with >=2 shared)",
                'appears_unflagged_other': 'other distinct-text samples where the span text (normalised) or a name/number key element occurs but no overlapping wrong span was flagged',
                'element_flagged_wrong / unflagged': 'distinct-text samples whose text contains the element (whole word); flagged if inside a verified wrong span',
                'suspect_clean / strict': "a consistent sample is 'suspect' if it contains verbatim (normalised, >=8 chars) a wrong span the judge verified in another sample of the same cell (by the judge's own standard it should have been flagged); strict availability / class counts only non-suspect consistent samples. The looser 'strict_plus_elements' variant also drops consistent samples containing a novel name/number flagged wrong in >=2 other samples (noisier: the flagged span's error may lie elsewhere).",
                'name type': "'name' elements are capitalised novel terms (person/company/model names, acronyms); a few capitalised ordinary words remain",
            },
            'caveats': [
                '72 cells from only 8 development chats (3 dailydialog, 5 lmsys) at 3 layers; chat-level bootstrap CIs with 8 clusters (3/5 within source) are rough and can be degenerate.',
                'All 149 chats were inspected before; nothing here is a held-out test.',
                'Judge labels are noisy (see element and exact-span consistency); availability of a clean sample is a judge-backed optimistic ceiling.',
                'Identical texts share one cached judge verdict; recurrence/inconsistency counts use distinct texts only.',
                "The page link shows only Original / Best of 32 / Combine 32 for a cell; the other pilot samples' texts are in avoidability_cells.jsonl.",
                'Key-element extraction is a regex heuristic: names in non-Latin script are not extracted; some capitalised ordinary words slip through.',
            ],
        },
        'verification': ver,
        'cross_check_quality_analysis_v2': {},
        'overall': overall, 'by_layer': by_layer, 'by_source': by_source, 'by_chat': by_chat,
        'best_clean_rank_distribution': rank_dist,
        'wrong_span_recurrence_by_cell_class': span_by_cls,
        'wrong_span_recurrence_by_type': span_by_type,
        'all_wrong_spans': span_summary(all_spans),
        'unavoidable_reasons': dict(collections.Counter(r['unavoidable_reason'] for r in cell_rows if r['unavoidable_reason'])),
        'judge_consistency_elements': el_summary,
        'judge_consistency_exact_span_text': exact_rec,
        'exact_span_unflagged_examples': ex_examples[:60],
        'inconsistent_element_examples': [
            {x: e[x] for x in ('k', 'element', 'type', 'flagged_wrong', 'unflagged', 'flagged_off_topic_only', 'example_span', 'example_sample', 'example_why')}
            for e in incons[:80]],
        'full_bank_relation': full_bank_rel,
        'examples': ex_out,
    }
    # cross-check against the project's own analysis
    qa = json.load(open(QA))
    h = qa['families']['hallucination']
    result['cross_check_quality_analysis_v2'] = {
        'consistent_available_cells': [h['consistent_available_cells'], sum(r['consistent_asserting_available'] for r in cell_rows)],
        'selected_classes': [h['selected_classes'], dict(collections.Counter(r['top_fve_class'] for r in cell_rows))],
        'all_wrong_asserting_cells': [h['all_wrong_asserting_cells'],
                                      sum(r['counts']['consistent'] + r['counts']['off_topic'] == 0 for r in cell_rows)],
        'note': '[project quality-analysis-v2 value, this script value]'}
    with open(OUT / 'avoidability_cells.jsonl', 'w') as f:
        for r in cell_rows:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')
    with open(OUT / 'avoidability.json', 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: result[k] for k in ('overall', 'cross_check_quality_analysis_v2')}, indent=1, ensure_ascii=False)[:6000])


if __name__ == '__main__':
    sys.exit(main())
