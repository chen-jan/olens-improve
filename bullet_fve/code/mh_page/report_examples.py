"""Verbatim examples + derived counts for tasks/multihop_mt/baseline/REPORT.md. Exploratory.

Reads only mh_page/data (built by build_data.py from out.json, the three-settings file and the raw
samples) and baseline/out.json + analysis2.json. Writes mh_page/report_examples.json and prints a
plain-text dump of every quoted text, so each quote and number in REPORT.md can be traced.
Usage: PY -B report_examples.py
"""
import collections
import glob
import json
import statistics
from pathlib import Path

PAGE = Path(__file__).resolve().parent
BASE = Path('${OLENS_SCRATCH}/olens-bullet-fve/tasks/multihop_mt/baseline')
EXAMPLES = [
    ('A_answer_in_sample_best_missed', 'multihop_mt|mhh-pilgrim-monk-novelist|L20|p00037'),
    ('B_answer_in_sample_best_missed', 'multihop_mt|mhh-1973-triple-crown-stud-farm|L24|p00033'),
    ('C_combine_passes_best_fails', 'multihop_mt|mhh-adwa-victor-accord|L60|p00044'),
    ('C2_combine_passes_no_sample_passes', 'multihop_mt|mhh-vaneyck-goldenfleece|L60|p00050'),
    ('D_longest4_passes_combine_fails', 'multihop_mt|mhh-kalevala-smith-sender|L32|p00040'),
]
LAB = {'h': 'hit', 'w': 'wrong-specific', 'm': 'miss'}


def main():
    cells, specs = {}, {}
    for fn in sorted(glob.glob(str(PAGE / 'data/items_*.json'))):
        for iid, v in json.load(open(fn)).items():
            specs[iid] = v['spec']
            for c in v['cells'].values():
                cells[c['cell_id']] = c
    out = json.load(open(BASE / 'out.json'))
    a2 = json.load(open(BASE / 'analysis2.json'))
    orow = {r['cell_id']: r for r in out['rows']}

    # derived: where does the first passing sample sit when Best of 32 misses an available answer?
    ranks = []
    for cid, r in orow.items():
        if r['any_pass'] and not r['best32_pass']:
            rk = sorted(r['samples'], key=lambda s: (-s['fve'], s['i']))
            ranks.append(next(j for j, s in enumerate(rk) if s['pass']) + 1)
    assert len(ranks) == a2['cells_where_answer_in_some_sample_but_best32_fails'] == 215
    q = statistics.quantiles(ranks, n=4)
    idx = json.load(open(PAGE / 'data/index.json'))
    cnt = collections.Counter()
    for r in idx['cells']:
        cnt['comb_not_best'] += r['c'] and not r['b']
        cnt['best_not_comb'] += r['b'] and not r['c']
        cnt['best_not_orig'] += r['b'] and not r['o']
        cnt['orig_not_best'] += r['o'] and not r['b']
        cnt['long_not_comb'] += r['l'] and not r['c']
        cnt['comb_not_long'] += r['c'] and not r['l']
        cnt['comb_pass_no_sample_passes'] += r['c'] and not r['a']
        cnt['all_three'] += r['o'] and r['b'] and r['c']
    derived = {'first_passing_rank_when_best_misses': {'n': len(ranks), 'median': statistics.median(ranks),
                                                       'q1': q[0], 'q3': q[2], 'rank2': ranks.count(2),
                                                       'rank_ge_10': sum(x >= 10 for x in ranks)},
               'outcome_counts': dict(cnt)}

    ex = {}
    for name, cid in EXAMPLES:
        c = cells[cid]
        sp = specs[c['item']]
        rk = sorted(c['samples'], key=lambda s: (-s['f'], s['i']))
        rank = {s['i']: j + 1 for j, s in enumerate(rk)}
        first_pass = next((s for s in rk if s['p']), None)

        def sample(s):
            return {'i': s['i'], 'rank': rank[s['i']], 'fve': s['f'], 'pass': bool(s['p']),
                    'bullets': [{'label': LAB[b[2]], 'lenient_only': bool(b[3]), 'text': s['t'][b[0]:b[1]].rstrip()} for b in s['b']]}

        def readout(k):
            R = c['read'][k]
            return {'fve': R['f'], 'pass': bool(R['p']),
                    'bullets': [{'label': LAB[b['lab']], 'lenient_only': bool(b['near']), 'share': b['share'], 'solo': b['solo'],
                                 'drop': b['drop'], 'from_sample': b['src'], 'text': R['t'][b['s']:b['e']].rstrip()} for b in R['b']]}

        ex[name] = {
            'cell_id': cid, 'page_anchor': c['item'] + '.L' + str(c['layer']), 'subfamily': sp['sub'], 'prompt': sp['prompt'],
            'bridges': [{'role': u['role'], 'gold': u['gold'], 'accepted': u['strict'], 'lenient_only': u['lenient_only']} for u in sp['roles']],
            'target': sp['target'], 'n_pass_samples': c['stats']['n_pass'], 'pool': c['stats']['pool'], 'pool_hit': c['stats']['pool_hit'],
            'best_i': c['best_i'],
            'best_sample': sample(next(s for s in c['samples'] if s['i'] == c['best_i'])),
            'first_passing_sample': sample(first_pass) if first_pass else None,
            'original': readout('orig'), 'best32': readout('best'), 'combine32': readout('comb'),
            'longest4': {'pass': bool(c['long4']['p']), 'bullets': [{'label': LAB[b['lab']], 'hits': b['hits'], 'chars': b['chars'],
                                                                     'from': b['from'], 'text': b['t'].rstrip()} for b in c['long4']['b']]},
        }
        # cross-check against out.json
        o = orow[cid]
        assert o['n_pass_samples'] == c['stats']['n_pass'] and o['best32_pass'] == bool(c['read']['best']['p'])
        assert all(o['samples'][s['i']]['fve'] == s['f'] and o['samples'][s['i']]['pass'] == bool(s['p']) for s in c['samples'])
    json.dump({'derived': derived, 'examples': ex}, open(PAGE / 'report_examples.json', 'w'), indent=1, ensure_ascii=False)
    print(json.dumps(derived, indent=1))
    for name, e in ex.items():
        print('=' * 20, name, e['cell_id'], e['subfamily'], 'n_pass', e['n_pass_samples'], 'best_i', e['best_i'])
        print('prompt:', e['prompt'])
        print('bridges:', e['bridges'], 'target:', e['target'])
        for k in ('best_sample', 'first_passing_sample'):
            s = e[k]
            if s:
                print(f'-- {k}: #{s["i"]} rank {s["rank"]} FVE {s["fve"]:.4f} pass {s["pass"]}')
                for b in s['bullets']:
                    print(f'   [{b["label"]}{"*" if b["lenient_only"] else ""}] {b["text"]!r}')
        for k in ('original', 'best32', 'combine32'):
            R = e[k]
            print(f'-- {k}: FVE {R["fve"]:.4f} pass {R["pass"]}')
            for b in R['bullets']:
                print(f'   [{b["label"]}{"*" if b["lenient_only"] else ""} share {b["share"]:.3f} solo {b["solo"]:.3f} drop {b["drop"]:.3f} from #{b["from_sample"]}] {b["text"]!r}')
        print(f'-- longest4 pass {e["longest4"]["pass"]}')
        for b in e['longest4']['bullets']:
            print(f'   [{b["label"]} {b["chars"]} chars from sample #{b["from"][0]} bullet {b["from"][1]}] {b["text"]!r}')


if __name__ == '__main__':
    main()
