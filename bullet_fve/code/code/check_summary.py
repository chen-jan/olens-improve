#!/usr/bin/env python3
"""Independent cross-checks of summary.json (build_summary.py): AUROC vs scipy Mann-Whitney U, pair rate by brute
force, position-adjusted pair rate by brute force (with the raw-tie rule, writing-order settings only; null for
selection-ordered settings), bullet-order data check, shap = shap_share same-readout rate, label/position rates,
caveat quotes, bootstrap replicate 0 by explicit replication, strict counts, histogram totals, and summary
structure."""
import collections
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_summary as B  # noqa: E402

ROOT = B.ROOT
D = ROOT / 'page/data'
S = json.loads((D / 'summary.json').read_text())
meta, items, cells, sids, full, item_files = B.load(D, ROOT / 'metrics/bullet_metrics.jsonl')
arrays = B.bullet_rows(meta, items, cells, sids, full, item_files)
n_items = len(items)
bad = 0
for sid in sids:
    a = arrays[sid]
    w, c = a['lab'] == B.LAB['w'], a['lab'] == B.LAB['c']
    for sc in B.SCORES:
        u = mannwhitneyu(a[sc][c], a[sc][w], alternative='two-sided', method='asymptotic').statistic
        est = u / (c.sum() * w.sum())
        got = S['settings'][sid]['scores'][sc]['auroc']['est']
        raw = full_vals = None
        ok = abs(est - got) < 6e-5
        bad += not ok
        print(f'{sid:24s} {sc:10s} auroc summary {got} scipy {est:.5f} {"OK" if ok else "MISMATCH"}')
    # pair rate brute force (shap_share, solo, drop)
    for sc in ('shap_share', 'solo', 'drop'):
        by_r = collections.defaultdict(lambda: ([], []))
        for t in np.flatnonzero(w | c):
            by_r[a['readout'][t]][0 if w[t] else 1].append(a[sc][t])
        num = den = nr = 0
        for ws, cs in by_r.values():
            if ws and cs:
                nr += 1
                for x in ws:
                    for y in cs:
                        num += 1.0 if y > x else 0.5 if y == x else 0.0
                        den += 1
        pr = S['settings'][sid]['scores'][sc]['pair_rate']
        ok = abs(num / den - pr['est']) < 6e-5 and nr == pr['n_readouts'] and den == pr['n_pairs']
        bad += not ok
        print(f'   pair {sc:10s} summary {pr["est"]} brute {num / den:.5f} readouts {nr}/{pr["n_readouts"]} '
              f'pairs {den}/{pr["n_pairs"]} {"OK" if ok else "MISMATCH"}')
    # ---- confound statistics, recomputed without the builder's rlab / rsize / _pa arrays
    j = sids.index(sid)
    blk = S['settings'][sid]
    cell_of = a['readout'] // len(sids)
    rlab = np.array([cells[x]['s'][j]['c'] for x in cell_of])
    hall = rlab == meta['label_codes'].index('hallucinated')
    ok = not (w & ~hall).any()
    bad += not ok
    print(f'   wrong bullets all in hallucinated readouts: {"OK" if ok else "MISMATCH"}')
    for sc in B.SCORES:
        est = mannwhitneyu(a[sc][c & hall], a[sc][w], alternative='two-sided', method='asymptotic').statistic \
            / ((c & hall).sum() * w.sum())
        got = blk['scores'][sc]['auroc_clean_in_hallucinated']['est']
        ok = abs(est - got) < 6e-5
        bad += not ok
        print(f'   auroc_clean_in_hallucinated {sc:10s} summary {got} scipy {est:.5f} {"OK" if ok else "MISMATCH"}')
    codes = np.array([cc['s'][j]['c'] for cc in cells])
    fv = np.array([full[cc['k']][sid]['saved'] for cc in cells])
    est = mannwhitneyu(fv[codes == 0], fv[codes == 1], alternative='two-sided', method='asymptotic').statistic \
        / ((codes == 0).sum() * (codes == 1).sum())
    got = blk['readout_fve_auroc']['est']
    ok = abs(est - got) < 6e-5
    bad += not ok
    print(f'   readout_fve_auroc summary {got} scipy {est:.5f} {"OK" if ok else "MISMATCH"}')
    cb = {n: int((c & (rlab == k)).sum()) for k, n in enumerate(meta['label_codes']) if n in B.SPECIFIC}
    ok = cb == blk['clean_by_readout_label']
    bad += not ok
    print(f'   clean_by_readout_label {cb} {"OK" if ok else "MISMATCH"}')
    # mixed-readout positions
    rw, rc = set(a['readout'][w].tolist()), set(a['readout'][c].tolist())
    mx = np.array([r in rw and r in rc for r in a['readout'].tolist()])
    mp = blk['mixed_readout_position']
    ok = (len(rw & rc) == mp['n_readouts'] and abs(a['pos'][mx & w].mean() - mp['mean_bullet_index_wrong']) < 6e-5
          and abs(a['pos'][mx & c].mean() - mp['mean_bullet_index_clean']) < 6e-5)
    bad += not ok
    print(f'   mixed_readout_position {mp["mean_bullet_index_wrong"]} vs {mp["mean_bullet_index_clean"]} '
          f'brute {a["pos"][mx & w].mean():.4f} vs {a["pos"][mx & c].mean():.4f} {"OK" if ok else "MISMATCH"}')
    # bullet order: data check recomputed readout by readout
    bo = blk['bullet_order']
    sel = sid in B.SELECTION_ORDERED
    first_top = []
    for r in np.unique(a['readout']):
        idx = np.flatnonzero(a['readout'] == r)
        if len(idx) >= 2:
            so_ = a['solo'][idx]
            first_top.append(so_[a['pos'][idx] == 0][0] >= so_.max())
    ok = (abs(np.mean(first_top) - bo['first_bullet_highest_solo']) < 6e-5 and bo['kind'] == ('selection' if sel else
          'writing') and bo['position_adjusted'] == (not sel) and len(first_top) == bo['n_readouts_2plus'])
    bad += not ok
    print(f'   bullet_order {bo["kind"]} first_bullet_highest_solo {bo["first_bullet_highest_solo"]} brute '
          f'{np.mean(first_top):.4f} {"OK" if ok else "MISMATCH"}')
    # shap and shap_share: identical raw same-readout rates by construction (same point, interval and pairs)
    p1, p2 = blk['scores']['shap']['pair_rate'], blk['scores']['shap_share']['pair_rate']
    ok = p1 == p2 and blk['scores']['shap'].get('pair_rate_same_as') == 'shap_share'
    bad += not ok
    print(f'   shap pair_rate == shap_share pair_rate: {"OK" if ok else "MISMATCH"} {p1} {p2}')
    # label / position rates
    spec_r = np.isin(codes, [meta['label_codes'].index(x) for x in B.SPECIFIC])
    hr = (codes == meta['label_codes'].index('hallucinated')).sum() / spec_r.sum()
    ok = abs(hr - blk['hallucinated_rate_of_specific']) < 6e-6
    bad += not ok
    print(f'   hallucinated_rate_of_specific {blk["hallucinated_rate_of_specific"]} brute {hr:.5f} {"OK" if ok else "MISMATCH"}')
    labd = a['lab'] != B.LAB['x']
    wr = [float(((a["pos"] == q) & w).sum() / ((a["pos"] == q) & labd).sum()) for q in range(4)]
    ok = all(abs(x - p['wrong_rate']) < 6e-5 for x, p in zip(wr, blk['by_position']))
    bad += not ok
    print(f'   by_position wrong_rate {[p["wrong_rate"] for p in blk["by_position"]]} brute {[round(x, 4) for x in wr]} '
          f'{"OK" if ok else "MISMATCH"}')
    # position-adjusted pair rate: explicit percentile per bullet, then brute-force pairs; raw ties count 0.5
    size = np.bincount(a['readout'])[a['readout']]
    spec = a['lab'] != B.LAB['x']
    for sc in B.SCORES:
        pr = blk['scores'][sc]['pair_rate_pos_adj']
        if sel:
            ok = (pr is None and blk['scores'][sc]['pair_rate_pos_centred'] is None
                  and 'greedy selector' in blk['scores'][sc].get('pair_rate_pos_adj_note', '')
                  and all(v['pair_rate_pos_adj'] is None and v.get('pair_rate_pos_adj_note')
                          for v in blk['by_layer'].values())
                  and all(st_[sc]['pair_rate_pos_adj'] is None for st_ in [S['settings_strict'][sid]['scores']]))
            bad += not ok
            print(f'   pair_pos_adj {sc:10s} null with note (selection order): {"OK" if ok else "MISMATCH"}')
            continue
        pct = np.zeros(len(a['lab']))
        for q in range(4):
            for n in range(1, 5):
                m = (a['pos'] == q) & (size == n)
                ref = a[sc][m & spec]
                for t in np.flatnonzero(m & (w | c)):
                    pct[t] = np.mean(ref < a[sc][t]) + 0.5 * np.mean(ref == a[sc][t])
        by_r = collections.defaultdict(lambda: ([], []))
        for t in np.flatnonzero(w | c):
            by_r[a['readout'][t]][0 if w[t] else 1].append((round(pct[t], 9), a[sc][t]))
        num = num0 = den = tied = 0
        for ws, cs in by_r.values():
            if ws and cs:
                for x, xr in ws:
                    for y, yr in cs:
                        v0 = 1.0 if y > x else 0.5 if y == x else 0.0
                        num0 += v0
                        if yr == xr:
                            tied += 1
                            v0 = 0.5
                        num += v0
                        den += 1
        ok = (abs(num / den - pr['est']) < 6e-5 and den == pr['n_pairs'] and tied == pr['n_raw_tied_pairs']
              and abs(num0 / den - pr['est_without_tie_rule']) < 6e-5)
        bad += not ok
        print(f'   pair_pos_adj {sc:10s} summary {pr["est"]} brute {num / den:.5f} (raw-tied {tied}/{pr["n_raw_tied_pairs"]}, '
              f'no tie rule {num0 / den:.5f}/{pr["est_without_tie_rule"]}) {"OK" if ok else "MISMATCH"}')
    # the confound numbers quoted in the caveats are the summary's own
    cav = ' '.join(S['caveats'])
    short = {x['id']: x['short'] for x in meta['settings']}[sid]
    quotes = [f'{blk["readout_fve_auroc"]["est"]:.3f}', f'{mp["mean_bullet_index_wrong"]:.2f} vs '
              f'{mp["mean_bullet_index_clean"]:.2f}', f'{blk["scores"]["solo"]["auroc_clean_in_hallucinated"]["est"]:.3f}']
    zc = int((a['coef'] == 0).sum())
    nd = int(a['dup'].sum())
    quotes.append(f'{short} {zc:,} of {len(a["lab"]):,} bullets' if zc else f'{short} none (its selector')
    quotes.append(f'{short} {nd} bullets in' if nd else f'{short} none)')
    if sel:
        quotes.append(f'highest solo FVE in {bo["first_bullet_highest_solo"]:.0%} of its readouts')
        pr_ = blk['scores']['shap_share']['pair_rate']
        quotes.append(f'Shapley share {pr_["est"]:.3f} [{pr_["lo"]:.3f}, {pr_["hi"]:.3f}]')
    else:
        pa_ = blk['scores']['drop']['pair_rate_pos_adj']
        quotes.append(f'{short} {blk["scores"]["drop"]["pair_rate"]["est"]:.3f} to {pa_["est"]:.3f} '
                      f'[{pa_["lo"]:.3f}, {pa_["hi"]:.3f}]')
        quotes.append(f'{short} {pa_["n_raw_tied_pairs"]:,} pairs')
    for txt in quotes:
        ok = txt in cav
        bad += not ok
        print(f'   caveat quotes {txt!r}: {"OK" if ok else "MISSING"}')
    if sel:   # no position-adjusted numbers are quoted for a selection-ordered setting
        import re
        hits = re.findall(re.escape(short) + r' \d\.\d{3} to \d\.\d{3}', cav + ' ' + S['scope'])
        ok = not hits
        bad += not ok
        print(f'   no position-adjusted quote for {short}: {"OK" if ok else "FOUND " + str(hits)}')
    # bootstrap replicate 0, explicit replication of items, for shap_share AUROC
    rng = np.random.default_rng(0)
    draw = rng.integers(0, n_items, n_items)
    vw, vc = [], []
    for i in draw:
        m = a['item'] == i
        vw.append(a['shap_share'][m & w])
        vc.append(a['shap_share'][m & c])
    vw, vc = np.concatenate(vw), np.concatenate(vc)
    u = mannwhitneyu(vc, vw, alternative='two-sided', method='asymptotic').statistic / (len(vw) * len(vc))
    M = B.boot_matrix(n_items, 1, 0)
    A, nc, nw = B.auc_parts(a['shap_share'], w, c, a['item'], n_items)
    fast = float(M[0] @ A @ M[0] / ((M[0] @ nc) * (M[0] @ nw)))
    ok = abs(u - fast) < 1e-9
    bad += not ok
    print(f'   bootstrap rep0 shap_share AUROC explicit {u:.6f} fast {fast:.6f} {"OK" if ok else "MISMATCH"}')
    # structure / totals
    blk = S['settings'][sid]
    assert blk['n_readouts'] == 5615
    assert sum(blk['bullet_counts'].values()) == len(a['lab'])
    for sc in B.SCORES:
        h = blk['scores'][sc]['hist']
        assert len(h['edges']) == 21 and sum(h['wrong']) == blk['bullet_counts']['w'] \
            and sum(h['clean']) == blk['bullet_counts']['c'], (sid, sc)
        for key in ('auroc', 'pair_rate', 'auroc_clean_in_hallucinated', 'pair_rate_pos_adj', 'pair_rate_pos_centred'):
            v = blk['scores'][sc][key]
            if v is None:
                assert sid in B.SELECTION_ORDERED and key in ('pair_rate_pos_adj', 'pair_rate_pos_centred'), (sid, key)
                continue
            assert v['lo'] <= v['est'] <= v['hi'], (sid, sc, key, v)
    assert blk['readout_fve_auroc']['lo'] <= blk['readout_fve_auroc']['est'] <= blk['readout_fve_auroc']['hi']
    st = S['settings_strict'][sid]
    assert st['bullet_counts']['w'] + st['excluded_wrong']['total'] == blk['bullet_counts']['w']
    assert st['bullet_counts']['c'] == blk['bullet_counts']['c']
    assert set(blk) >= {'n_readouts', 'mean_fve', 'label_counts', 'bullet_counts', 'scores', 'by_layer',
                        'by_position', 'scored_vs_unscored'}
    assert len(blk['by_position']) == 4 and set(blk['by_layer']) == {'20', '36', '44', '52', '60'}
edges = {sc: S['settings'][sids[0]]['scores'][sc]['hist']['edges'] for sc in B.SCORES}
assert all(S['settings'][sid]['scores'][sc]['hist']['edges'] == edges[sc] for sid in sids for sc in B.SCORES)
assert set(S['definitions']) >= {'shap', 'shap_share', 'solo', 'drop', 'bullet_labels', 'auroc', 'pair_rate',
                                 'pair_rate_pos_adj', 'bullet_order', 'by_position', 'hallucinated_rate_of_specific'}
assert all(any(k in S['settings'][s] for k in ('bullet_order',)) for s in sids)
print('shared hist edges OK; structure OK')
print('CHECKS', 'PASSED' if bad == 0 else f'FAILED ({bad})')
sys.exit(1 if bad else 0)
