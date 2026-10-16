"""Step 4b: does positive heat on punctuation / whitespace / the last token depend on the read-site kind
(clause, sentence, markup, newline, quote)? Per setting x site kind, bullet-averaged shares, item bootstrap."""
import collections
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from v4_heat_findings import piece_class, boot_mean, EPS  # noqa: E402

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')


def main():
    rng = np.random.default_rng(7)
    cells = {}
    for l in open(ROOT / 'inputs/hall_three_settings.jsonl'):
        c = json.loads(l)
        cells[c['cell_id']] = (c['item_id'], c['read_position_kind'])
    items = sorted({v[0] for v in cells.values()})
    ix = {it: i for i, it in enumerate(items)}
    acc = collections.defaultdict(lambda: collections.defaultdict(list))
    for line in open(ROOT / 'heat/token_heat.jsonl'):
        r = json.loads(line)
        if r['dup_in_readout']:
            continue
        h = np.clip(np.array(r['heat']), 0, None)
        if h.sum() <= EPS:
            continue
        sh = h / h.sum()
        cls = [piece_class(p) for p in r['pieces']]
        bnd = np.array([c in ('punct', 'whitespace') for c in cls])
        it, kind = cells[r['cell_id']]
        kind = kind.split(':')[-1]
        a = acc[(r['setting'], kind)]
        a['item'].append(ix[it])
        a['bnd_heat_minus_tok'].append(sh[bnd].sum() - bnd.mean())
        a['last_minus_uniform'].append(sh[-1] - 1 / len(sh))
        a['bnd_tok'].append(bnd.mean())
    out = {}
    for (st, kind), a in sorted(acc.items()):
        it = np.array(a['item'])
        out[f'{st}|{kind}'] = {'n': len(it),
                               'punct+ws_token_share': float(np.mean(a['bnd_tok'])),
                               'punct+ws_heat_minus_token_share': boot_mean(it, np.array(a['bnd_heat_minus_tok']), len(items), rng),
                               'last_token_share_minus_uniform': boot_mean(it, np.array(a['last_minus_uniform']), len(items), rng)}
    (Path(__file__).parent / 'v5_sitekind.json').write_text(json.dumps(out, indent=1) + '\n')
    for k, v in out.items():
        print(k, v['n'], round(v['punct+ws_token_share'], 3),
              '%.4f [%.4f, %.4f]' % tuple(v['punct+ws_heat_minus_token_share']),
              '%.4f [%.4f, %.4f]' % tuple(v['last_token_share_minus_uniform']))


if __name__ == '__main__':
    main()
