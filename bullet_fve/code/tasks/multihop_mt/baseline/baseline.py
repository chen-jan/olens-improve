"""Multihop: does FVE (AR) selection beat chance, scored over ALL 32 samples per cell?

The Multihop judge is the deterministic regex scorer, so every one of the 32 raw lens samples
per cell can be judged exactly, for free. Each sample is parsed and capped exactly as
olens-improve does (parse_bullets: dash blocks, <=4 bullets, <=256 Qwen tokens; parsing-uncertain
samples are ineligible for Best of N), rendered with render_bullets, and judged with the pinned
regex on extract_phrase(text). Checks: the rendered text of the sample Best of 32 chose and of
sample 0 (Original) must match the frozen selection hashes, and the recomputed passes must
reproduce 106 / 129 of 1,100.

Baselines:
  Best of 32  vs  one random eligible sample (exact mean), best-of-k by FVE (exact expectation
              over random k-subsets), any-of-32 oracle.
  Combine 32  vs  4 random distinct pool bullets (exact hypergeometric, inclusion-exclusion over
              required units), pool oracle (pool contains a hit for every required unit).

Usage: PY -B baseline.py OUT.json
"""
import collections
import hashlib
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASK = HERE.parent
sys.path.insert(0, str(TASK))
sys.path.insert(0, '${OLENS_REPO_ROOT}/src')
import load  # noqa: E402  (pinned regex, bank, tokenizer path)
from olens_improve.selection import parse_bullets, render_bullets  # noqa: E402

RX = load.RX
bank = json.loads(load.BANK.read_text())
contract = RX.contract_for(bank, str(bank.get('family', load.FAMILY)))
UNITS = {it['name']: RX.scored_units(it, contract) for it in bank['items']}

from transformers import AutoTokenizer  # noqa: E402
TOK = AutoTokenizer.from_pretrained(load.TOKENIZER, local_files_only=True)


def ntok(s):
    return len(TOK(s, add_special_tokens=False)['input_ids'])


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def judge(text, units):
    hits = RX.layer_unit_hits([RX.extract_phrase(text)], units)
    return {u.role: bool(hits[u.role]) for u in units if u.required}


# --- raw samples ---
raw = collections.defaultdict(dict)
for line in open(HERE / 'raw_lines.jsonl'):
    for r in json.loads(line)['records']:
        if r['family'] == 'multihop_mt':
            raw[r['cell_id']][r['sample_index']] = r

cand = {}
for line in open(TASK / 'inputs/multihop_mt_candidates.jsonl'):
    o = json.loads(line)
    cand[o['cell_id']] = o

rows, checks = [], collections.Counter()
for cid in sorted(raw):
    c = cand[cid]
    units = UNITS[c['item_id']]
    req = [u.role for u in units if u.required]
    fve = {t['sample_index']: t.get('score') for t in c['trace32']}
    sel = {s['cond']: s for s in c['selections']}
    samples = []
    pool = {}  # exact bullet text -> per-role hit dict
    pool_info = {}
    for i in range(32):
        r = raw[cid][i]
        smp = parse_bullets(r['text'], f'{cid}:{i}', i, 4, token_count=ntok, max_output_tokens=256)
        text = render_bullets(smp.bullets)
        u = judge(text, units)
        samples.append({'i': i, 'eligible': not smp.parsing_uncertain and len(smp.bullets) > 0,
                        'pass': all(u.values()), 'units': u, 'fve': fve.get(i), 'sha': sha(text),
                        'n_bullets': len(smp.bullets)})
        if not smp.parsing_uncertain:
            for b in smp.bullets:
                if b.text not in pool:
                    pool[b.text] = judge('- ' + b.text, units)
                    pool_info[b.text] = {'chars': len(b.text.strip()), 'freq': 0, 'first': (i, b.position)}
                pool_info[b.text]['freq'] += 1
    # checks against frozen selections
    o, b32 = sel['capped_n1-n1'], sel['best_n_exact-n32']
    checks['orig_sha_ok'] += samples[0]['sha'] == o['text_sha256']
    bi = b32['samples'][0]
    checks['best32_sha_ok'] += samples[bi]['sha'] == b32['text_sha256']
    elig = [s for s in samples if s['eligible'] and s['fve'] is not None]
    argmax = max(elig, key=lambda s: (s['fve'], -s['i'])) if elig else None
    checks['best32_argmax_ok'] += (argmax is not None and argmax['i'] == bi)
    # best-of-k exact expectation over random k-subsets of the 32 indices (ineligible never win;
    # a subset with no eligible sample counts as fail)
    ranked = sorted(elig, key=lambda s: (-s['fve'], s['i']))
    bok = {}
    for k in (1, 2, 4, 8, 16, 32):
        tot = math.comb(32, k)
        p = 0.0
        for rnk, s in enumerate(ranked):  # s wins iff in subset and the rnk higher-ranked eligible are not
            free = 32 - rnk - 1
            if free >= k - 1:
                p += s['pass'] * math.comb(free, k - 1) / tot
        bok[k] = p
    # random 4 distinct pool bullets: P(all required roles hit)
    M = len(pool)
    m = min(4, M)

    def p_none(mask_roles):
        bad = sum(1 for h in pool.values() if not any(h[r] for r in mask_roles))
        return math.comb(bad, m) / math.comb(M, m) if M else 1.0

    if len(req) == 1:
        p_rand4 = 1 - p_none(req)
    else:
        a, b = req
        p_rand4 = 1 - p_none([a]) - p_none([b]) + p_none([a, b])
    rows.append({
        'cell_id': cid, 'item_id': c['item_id'], 'layer': c['layer'], 'split': c['split'],
        'n_eligible': len(elig),
        'orig_pass': samples[0]['pass'], 'best32_pass': samples[bi]['pass'],
        'rand1_pass': sum(s['pass'] for s in elig) / len(elig) if elig else 0.0,
        'any_pass': any(s['pass'] for s in elig),
        'n_pass_samples': sum(s['pass'] for s in elig),
        'best_of_k': bok,
        'pool_size': M, 'pool_hit_bullets': sum(1 for h in pool.values() if any(h.values())),
        'pool_oracle': all(any(h[r] for h in pool.values()) for r in req),
        'rand4_pool_pass': p_rand4,
        'samples': [{k: s[k] for k in ('i', 'eligible', 'pass', 'fve', 'n_bullets')} for s in samples],
        'req': req,
        'pool': [{**pool_info[t], 'hits': [r for r in req if pool[t][r]]} for t in pool],
    })

N = len(rows)
summ = {
    'cells': N, 'checks': dict(checks),
    'original_pass': sum(r['orig_pass'] for r in rows),
    'best32_pass_recomputed': sum(r['best32_pass'] for r in rows),
    'random_single_sample_expected': round(sum(r['rand1_pass'] for r in rows), 1),
    'best_of_k_expected': {k: round(sum(r['best_of_k'][k] for r in rows), 1) for k in (1, 2, 4, 8, 16, 32)},
    'any_of_32_oracle': sum(r['any_pass'] for r in rows),
    'random4_pool_expected': round(sum(r['rand4_pool_pass'] for r in rows), 1),
    'pool_oracle': sum(r['pool_oracle'] for r in rows),
}
json.dump({'summary': summ, 'rows': rows}, open(sys.argv[1], 'w'))
print(json.dumps(summ, indent=1))
