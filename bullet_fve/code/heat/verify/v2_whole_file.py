"""Step 2: whole-file structural checks of token_heat.jsonl against hall_three_settings.jsonl,
plus a full-file joint_0 cross-check against the independent bullet_metrics.jsonl (saved - loo_drop)
and an independent tokenizer-decode check of every token boundary (ends / pieces)."""
import collections
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
HEAT = ROOT / 'heat'
OUT = HEAT / 'verify'
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
TOK_PATH = ('${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/snapshots/'
            '6a9e13bd6fc8f0983b9b99948120bc37f49c13e9')
FFFD = '�'


def main():
    do_decode = '--no-decode' not in sys.argv
    cells = [json.loads(l) for l in open(ROOT / 'inputs/hall_three_settings.jsonl')]
    expect = {}
    empty_readouts = []
    for c in cells:
        for st in SETTINGS:
            s = c['settings'][st]
            if not s['atoms']:
                empty_readouts.append((c['cell_id'], st))
            keys = [a['cache_key'] for a in s['atoms']]
            for j, a in enumerate(s['atoms']):
                expect[(c['cell_id'], st, j)] = (c, s, a, keys.count(a['cache_key']) > 1)
    metrics = {}
    for line in open(ROOT / 'metrics/bullet_metrics.jsonl'):
        m = json.loads(line)
        for st, sm in m['settings'].items():
            for j, b in enumerate(sm['bullets']):
                metrics[(m['cell_id'], st, j)] = (sm, b)
    tok = None
    if do_decode:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(TOK_PATH, local_files_only=True)

    bad = collections.defaultdict(list)
    cnt = collections.Counter()
    seen = set()
    worst = collections.defaultdict(float)
    sumheat_minus_loo, drift_all, diff_sh_loo_minus_drift = [], [], []
    j0_vs_metrics = []
    n_lines = 0

    def flag(name, key, info=None):
        cnt['bad_' + name] += 1
        if len(bad[name]) < 8:
            bad[name].append([list(key), info])

    with open(HEAT / 'token_heat.jsonl') as f:
        for line in f:
            if not line.strip():
                cnt['blank_lines'] += 1
                continue
            n_lines += 1
            r = json.loads(line)
            key = (r['cell_id'], r['setting'], r['bullet'])
            if key in seen:
                flag('duplicate_key', key)
            seen.add(key)
            if key not in expect:
                flag('unexpected_key', key)
                continue
            c, s, a, dup = expect[key]
            text = a['scored_text']
            ids = a['scored_token_ids']
            n = r['n_scored']
            # identity fields
            for fld, want in (('phrase_id', a['source_phrase_id']), ('cache_key', a['cache_key']),
                              ('layer', c['layer']), ('split', c['split']), ('truncated', bool(a['truncated'])),
                              ('n_bullets', len(s['atoms'])), ('dup_in_readout', dup)):
                if r[fld] != want:
                    flag('field_' + fld, key, [r[fld], want])
            # lengths
            L = {'ids': len(ids), 'heat': len(r['heat']), 'solo': len(r['solo']), 'ends': len(r['ends_in_scored_text']),
                 'pieces': len(r['pieces']), 'joint-1': len(r['joint']) - 1}
            if any(v != n for v in L.values()):
                flag('lengths', key, L)
            joint = np.array(r['joint'])
            heat = np.array(r['heat'])
            solo = np.array(r['solo'])
            # telescoping and heat definition
            tele = abs(heat.sum() - (joint[-1] - joint[0]))
            worst['telescoping'] = max(worst['telescoping'], tele)
            if tele > 1e-9:
                flag('telescoping', key, tele)
            hd = np.abs(heat - np.round(np.diff(joint), 7)).max() if n else 0.0
            worst['heat_vs_diff_joint'] = max(worst['heat_vs_diff_joint'], hd)
            if hd > 1.5e-7:
                flag('heat_def', key, hd)
            # joint_cached vs saved readout FVE
            dcs = abs(r['joint_cached'] - s['fve'])
            worst['joint_cached_vs_saved'] = max(worst['joint_cached_vs_saved'], dcs)
            if dcs > 1e-6:
                flag('joint_cached_vs_saved', key, [r['joint_cached'], s['fve']])
            if abs(r['readout_fve_saved'] - s['fve']) > 1e-7:
                flag('readout_fve_saved_field', key, [r['readout_fve_saved'], s['fve']])
            dd = abs(r['drift'] - (joint[-1] - r['joint_cached']))
            worst['drift_field'] = max(worst['drift_field'], dd)
            if dd > 2e-7:
                flag('drift_field', key, dd)
            # NNLS monotonicity invariants: adding a column never lowers FVE
            #   joint_k >= joint_0, joint_k >= solo_k, joint_cached >= joint_0, all <= 1
            v1 = float((joint[0] - joint[1:]).max()) if n else 0.0
            v2 = float((solo - joint[1:]).max()) if n else 0.0
            v3 = joint[0] - r['joint_cached']
            worst['joint_k_below_joint0'] = max(worst['joint_k_below_joint0'], v1)
            worst['solo_above_joint_k'] = max(worst['solo_above_joint_k'], v2)
            worst['joint_cached_below_joint0'] = max(worst['joint_cached_below_joint0'], v3)
            if v1 > 2e-7:
                flag('joint_k_below_joint0', key, v1)
            if v2 > 2e-7:
                flag('solo_above_joint_k', key, v2)
            if v3 > 2e-7:
                flag('joint_cached_below_joint0', key, v3)
            if joint.max() > 1 + 1e-9 or solo.min() < 0 or solo.max() > 1 + 1e-9:
                flag('range', key)
            if dup and abs(r['joint_cached'] - joint[0]) > 1e-6:
                flag('dup_joint_cached_ne_joint0', key, [r['joint_cached'], joint[0]])
            # offsets / pieces
            ends = r['ends_in_scored_text']
            if any(e2 < e1 for e1, e2 in zip(ends, ends[1:])) or (ends and (ends[0] < 0 or ends[-1] > len(text))):
                flag('ends_order_or_range', key, ends)
            prev = 0
            pieces_ok = True
            for e, p in zip(ends, r['pieces']):
                if text[prev:e] != p:
                    pieces_ok = False
                prev = e
            if not pieces_ok:
                flag('piece_vs_slice', key)
            cat = ''.join(r['pieces'])
            if not text.startswith(cat) or (ends and cat != text[:ends[-1]]):
                flag('pieces_concat_not_prefix', key)
            if not a['truncated'] and ends and ends[-1] != len(text):
                flag('untruncated_not_full', key, [ends[-1], len(text)])
            if a['truncated']:
                cnt['truncated'] += 1
                cnt['truncated_scored_chars'] += ends[-1] if ends else 0
                cnt['truncated_total_chars'] += len(text)
            cnt['empty_pieces'] += sum(1 for p in r['pieces'] if p == '')
            cnt['tokens'] += n
            # independent decode check of every boundary: decode(ids[:k]) == text[:ends[k-1]] + (only U+FFFD)
            if tok is not None:
                for k in range(1, n + 1):
                    dec = tok.decode(ids[:k], clean_up_tokenization_spaces=False)
                    e = ends[k - 1]
                    if dec == text[:e]:
                        cnt['decode_exact'] += 1
                    elif dec.startswith(text[:e]) and set(dec[e:]) <= {FFFD} and \
                            not text[e:].startswith(dec[e:]):
                        cnt['decode_partial_char'] += 1
                    else:
                        flag('decode_boundary', key, [k, dec[-20:], text[max(0, e - 20):e + 5], e])
            # bullet_metrics cross-check (all occurrences): joint_0 vs saved - loo_drop, sum(heat) vs loo_drop
            if key in metrics:
                sm, b = metrics[key]
                if b['cache_key'] != a['cache_key']:
                    flag('metrics_key', key)
                j0_metrics = sm['joint_fve_recomputed'] - b['loo_drop']
                d0 = r['joint'][0] - j0_metrics
                j0_vs_metrics.append(d0)
                sh = float(heat.sum())
                sumheat_minus_loo.append(sh - b['loo_drop'])
                drift_all.append(r['drift'])
                diff_sh_loo_minus_drift.append((sh - b['loo_drop']) - r['drift'])
            else:
                flag('metrics_missing', key)
    missing = [k for k in expect if k not in seen]
    for k in missing[:8]:
        bad['missing_key'].append(list(k))
    cnt['bad_missing_key'] = len(missing)

    def q(x):
        x = np.asarray(x, float)
        ax = np.abs(x)
        return {'n': int(x.size), 'mean': float(x.mean()), 'median': float(np.median(x)),
                'abs_median': float(np.median(ax)), 'abs_p90': float(np.quantile(ax, .9)),
                'abs_p99': float(np.quantile(ax, .99)), 'abs_max': float(ax.max()),
                'min': float(x.min()), 'max': float(x.max())}

    out = {'lines': n_lines, 'expected_occurrences': len(expect), 'empty_readouts': empty_readouts,
           'unique_keys_seen': len(seen), 'counts': dict(cnt), 'worst': dict(worst),
           'joint0_minus_metrics_(joint_recomputed-loo_drop)': q(j0_vs_metrics),
           'sum_heat_minus_loo_drop': q(sumheat_minus_loo), 'drift': q(drift_all),
           '(sum_heat-loo_drop)-drift': q(diff_sh_loo_minus_drift),
           'corr_sumheat-loo_vs_drift': float(np.corrcoef(sumheat_minus_loo, drift_all)[0, 1]),
           'bad_examples': dict(bad), 'decode_checked': do_decode}
    (OUT / 'v2_whole_file.json').write_text(json.dumps(out, indent=1, ensure_ascii=False) + '\n')
    print(json.dumps({k: v for k, v in out.items() if k != 'bad_examples'}, indent=1, ensure_ascii=False))
    print(json.dumps(out['bad_examples'], indent=1, ensure_ascii=False)[:6000])


if __name__ == '__main__':
    main()
