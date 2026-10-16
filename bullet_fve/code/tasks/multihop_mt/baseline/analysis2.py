"""CIs and no-FVE baselines for the Multihop all-32-samples rescoring (reads out.json)."""
import json, math, random, collections
import numpy as np
D = json.load(open('out.json')); rows = D['rows']
comb = {(r['item_id'], r['layer']): r['pass'] for r in json.load(open(
    '${OLENS_DATA_ROOT}/expansion-v1/judgments/pooled_greedy_swap-n32/multihop_mt/project_contract.json'))['cell_diagnostic']['rows']}
for r in rows: r['comb_pass'] = comb[(r['item_id'], r['layer'])]
items = sorted({r['item_id'] for r in rows}); by_item = collections.defaultdict(list)
for r in rows: by_item[r['item_id']].append(r)
rng = np.random.default_rng(0)

def p_all(pool, req, chosen_idx):
    return all(any(rr in pool[j]['hits'] for j in chosen_idx) for rr in req)

def topk_baseline(r, key):
    pool = r['pool']
    if not pool: return 0.0
    order = sorted(range(len(pool)), key=key(pool))
    return float(p_all(pool, r['req'], order[:4]))

def rand_long(r, draws=400):
    pool = r['pool']
    if not pool: return 0.0
    med = np.median([b['chars'] for b in pool]); idx = [j for j, b in enumerate(pool) if b['chars'] >= med]
    m = min(4, len(idx)); return np.mean([p_all(pool, r['req'], rng.choice(idx, m, replace=False)) for _ in range(draws)])

for r in rows:
    r['freq4'] = topk_baseline(r, lambda P: (lambda j: (-P[j]['freq'], P[j]['first'])))
    r['long4'] = topk_baseline(r, lambda P: (lambda j: (-P[j]['chars'], P[j]['first'])))
    r['randlong4'] = rand_long(r)

def boot(f, reps=2000):
    vals = []
    for _ in range(reps):
        pick = rng.choice(len(items), len(items), replace=True)
        rs = [x for k in pick for x in by_item[items[k]]]
        vals.append(f(rs))
    return np.percentile(vals, [2.5, 97.5])

def tot(key): return lambda rs: sum(float(x[key]) if not isinstance(x[key], dict) else 0 for x in rs) / len(rs) * 100
def diff(a, b): return lambda rs: (sum(float(x[a]) for x in rs) - sum(float(x[b]) for x in rs)) / len(rs) * 100
N = len(rows); out = {}
for k in ['orig_pass', 'rand1_pass', 'best32_pass', 'comb_pass', 'rand4_pool_pass', 'freq4', 'long4', 'randlong4', 'any_pass', 'pool_oracle']:
    out[k] = {'cells': round(sum(float(r[k]) for r in rows), 1), 'pct': round(sum(float(r[k]) for r in rows) / N * 100, 2)}
for a, b in [('best32_pass', 'rand1_pass'), ('orig_pass', 'rand1_pass'), ('best32_pass', 'orig_pass'), ('comb_pass', 'rand4_pool_pass'),
             ('comb_pass', 'freq4'), ('comb_pass', 'long4'), ('comb_pass', 'randlong4'), ('comb_pass', 'best32_pass'), ('comb_pass', 'rand1_pass')]:
    f = diff(a, b); lo, hi = boot(f); out[f'{a} - {b}'] = [round(f(rows), 2), round(lo, 2), round(hi, 2)]
# within-cell AUROC of FVE: passing vs failing eligible samples, same cell, all 32 samples
num = den = 0.0; cells_mixed = 0; quart = collections.Counter(); quartn = collections.Counter()
for r in rows:
    el = [s for s in r['samples'] if s['eligible'] and s['fve'] is not None]
    P = [s['fve'] for s in el if s['pass']]; F = [s['fve'] for s in el if not s['pass']]
    if P and F:
        cells_mixed += 1
        for p in P:
            for q in F: num += (p > q) + 0.5 * (p == q); den += 1
    rk = sorted(el, key=lambda s: -s['fve'])
    for j, s in enumerate(rk):
        qq = min(3, j * 4 // max(1, len(rk))); quart[qq] += s['pass']; quartn[qq] += 1
out['within_cell_auroc_all32'] = {'auroc': round(num / den, 3), 'pairs': int(den), 'mixed_cells': cells_mixed}
out['pass_rate_by_fve_quartile_top_to_bottom_pct'] = [round(quart[q] / quartn[q] * 100, 2) for q in range(4)]
out['cells_where_answer_in_some_sample_but_best32_fails'] = sum(1 for r in rows if r['any_pass'] and not r['best32_pass'])
out['mean_pass_samples_in_mixed_cells'] = round(np.mean([r['n_pass_samples'] for r in rows if 0 < r['n_pass_samples'] < r['n_eligible']]), 2)
json.dump(out, open('analysis2.json', 'w'), indent=1); print(json.dumps(out, indent=1))
