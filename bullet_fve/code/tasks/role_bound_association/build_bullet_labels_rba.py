"""Bullet labels (rule RBA-v1, MAP.md section 7) for every bullet of the three settings, one line per
bullet, plus validation statistics of the labels.

Labels come from load.label_readout unchanged (computed on the bullet's scored_text = the cleaned
bullet text, which is also what the judge read up to a leading '<think>' / trailing newline).
The AR vector, however, only sees the first <= 32 tokens (scored_token_ids); 7,537 atoms are
truncated. The same rule is therefore also run on the vector-visible text (Qwen3.6-27B decode of
scored_token_ids for truncated atoms, unchanged text otherwise) and stored as label_visible /
label_fine_visible, so analyses can drop bullets whose credited content lies past the 32 tokens.

No judge/API calls. READ-ONLY on project data; writes only:
  bullet_labels.jsonl                (one line per bullet, 136,684 lines)
  data/labels_validation.json        (coverage, counts per setting x label, ambiguity counts, checks)
  logs/labels_reading.txt            (fixed-seed reading sample, verbatim bullets with case keys)

Usage (inside srun): python -B build_bullet_labels_rba.py
"""
import collections
import json
import os
import random
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import load  # noqa: E402

OUT = HERE / 'bullet_labels.jsonl'
VAL = HERE / 'data' / 'labels_validation.json'
READING = HERE / 'logs' / 'labels_reading.txt'
SHORT = {c: v[2] for c, v in load.SETTINGS.items()}
CJK = lambda t: any('一' <= ch <= '鿿' for ch in t)  # noqa: E731
READ_SEED = 20261015
TOKENIZER = ('${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/snapshots/'
             '6a9e13bd6fc8f0983b9b99948120bc37f49c13e9')  # same snapshot multihop_mt used


def contrast_group(label_fine, has_vector, fve):
    """Suggested group for the FVE contrast (MAP.md section 10)."""
    if not has_vector or fve is None:
        return 'excluded_no_fit'
    if label_fine == 'unlocated':
        return 'excluded_unlocated'
    if label_fine.startswith('hit'):
        return 'hit'
    if label_fine in ('miss_none', 'miss_partial'):
        return 'clean_miss'
    if label_fine == 'miss_pass_other':
        return 'miss_pass_other'
    if label_fine == 'miss_wrong_readout':
        return 'miss_wrong_readout'
    if label_fine.startswith('wrong'):
        return 'wrong_specific'
    raise ValueError(label_fine)


def wrong_value(b, judge):
    """What wrong value of the right kind the bullet carries (wrong_specific only), with matched terms."""
    out = []
    for r in b['label_reasons']:
        if r.startswith('reversed'):
            out.append({'kind': r.split(':')[0], 'judge_q1': judge['choice_labels'][0],
                        'judge_q3': judge['choice_labels'][2],
                        'bullet_agent_terms': b['agent'], 'bullet_patient_terms': b['patient']})
        elif r.startswith('wrong_action:'):
            act = r.split(':', 1)[1]
            out.append({'kind': 'wrong_action', 'judge_choice': act, 'bullet_terms': b['distractor_actions'].get(act, [])})
        elif r.startswith('wrong_person:'):
            _, q, lab = r.split(':', 2)
            out.append({'kind': 'wrong_person', 'question': q, 'judge_choice': lab,
                        'bullet_terms': b['distractor_people'].get(lab, [])})
    return out


def cjk_only_parts(b):
    """Parts (agent/patient/action) matched ONLY through a Chinese alias."""
    return [k for k in ('agent', 'patient', 'action') if b[k] and all(CJK(t) for t in b[k])]


def main():
    t0 = time.time()
    bank = load.load_bank()
    js = {c: load.load_judgments(c) for c in load.SETTINGS}
    for j in js.values():
        j.pop('__meta__', None)
    # item pass per setting (any of its 114 sites passes)
    item_pass = {c: {load.parse_cell_id(cid)[0] for cid, r in j.items() if r['pass']} for c, j in js.items()}

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(TOKENIZER, local_files_only=True)
    st = collections.Counter()
    lab_n, fine_n, relaxed_n, full_n, comp_n, group_n = (collections.Counter() for _ in range(6))
    hits_per_pass_readout = collections.Counter()
    amb = collections.Counter()
    pools = collections.defaultdict(list)  # (cond, bucket) -> [(cell_id, idx)] for the reading sample
    tmp = OUT.with_suffix('.jsonl.tmp')
    with open(tmp, 'w') as fo:
        for row in load.iter_cells(judgments=js):
            it = bank[row['item_id']]
            st['cells'] += 1
            for cond, s in row['settings'].items():
                j = s['judge']
                assert j is not None, (row['cell_id'], cond)
                # same rule on the vector-visible text (first <= 32 scored tokens)
                vis_atoms = []
                for a in s['atoms']:
                    if a['truncated']:
                        vis = tok.decode(a['scored_token_ids'])
                        full = tok.decode(a['scored_token_ids'] + (a['unscored_suffix_ids'] or []))
                        st['truncated_decode_full_equals_scored_text'] += full == a['scored_text']
                        st['truncated_decode_full_differs'] += full != a['scored_text']
                        st['truncated_visible_is_prefix'] += a['scored_text'].startswith(vis)
                        vis_atoms.append(dict(a, scored_text=vis))
                    else:
                        vis_atoms.append(a)
                _, feats_full = load.label_readout(it, j, vis_atoms)
                st[f'readouts[{cond}]'] += 1
                n_hit = sum(b['label'] == 'hit' for b in s['bullets'])
                if j['pass']:
                    hits_per_pass_readout[(cond, n_hit)] += 1
                    ev_best = sum(b['evidence_best'] for b in s['bullets'])
                    amb[(cond, 'pass_readouts_evidence_best_tied')] += ev_best > 1
                agent_lab = it['label_a'] if it['agent_side'] == 'a' else it['label_b']
                patient_lab = it['label_b'] if it['agent_side'] == 'a' else it['label_a']
                for i, (b, a, ff, va) in enumerate(zip(s['bullets'], s['atoms'], feats_full, vis_atoms)):
                    ff_text = va['scored_text']
                    group = contrast_group(b['label_fine'], b['has_vector'], s['fve'])
                    cjk_parts = cjk_only_parts(b)
                    overlap_terms = sorted(set(b['agent']) & set(b['patient']))
                    rec = {
                        'cell_id': row['cell_id'], 'setting': cond, 'setting_short': SHORT[cond],
                        'index': i, 'n_bullets': len(s['bullets']), 'phrase_id': b['phrase_id'],
                        'cache_key': b['cache_key'], 'has_vector': b['has_vector'],
                        'item_id': row['item_id'], 'group_id': row['group_id'], 'pair_id': it['pair_id'],
                        'direction': it['direction'], 'stereotypicality': it['stereotypicality'],
                        'layer': row['layer'], 'position': row['position'], 'split': row['split'],
                        'token': row['token'],
                        'text': a['text'], 'scored_text': a['scored_text'], 'char_span': b['span'],
                        'truncated': a['truncated'], 'atom_status': a['status'],
                        'label': b['label'], 'label_fine': b['label_fine'], 'label_relaxed': b['label_relaxed'],
                        'label_reasons': b['label_reasons'], 'component': b['component'],
                        'label_visible': ff['label'], 'label_fine_visible': ff['label_fine'],
                        'visible_text': ff_text if a['truncated'] else None,
                        'matched_terms_visible': {'agent': ff['agent'], 'patient': ff['patient'], 'action': ff['action']},
                        'contrast_group': group,
                        'binding': b['binding'], 'n_components': b['n_components'], 'order': b['order'],
                        'evidence': {
                            'matched_terms': {'agent': b['agent'], 'patient': b['patient'], 'action': b['action']},
                            'cjk_only_parts': cjk_parts,
                            'judge_evidence': j['evidence'],
                            'evidence_quotes_in_bullet': b['evidence_quotes_in_bullet'],
                            'evidence_overlap': b['evidence_overlap'], 'evidence_best': b['evidence_best'],
                            'wrong_value': wrong_value(b, j) if b['label'] == 'wrong_specific' else [],
                            'distractor_people_terms': b['distractor_people'],
                            'distractor_action_terms': b['distractor_actions'],
                        },
                        'gold': {'agent': agent_lab, 'action': it['action'], 'patient': patient_lab,
                                 'gold_label': it['gold_label']},
                        'judge': {'choice_labels': j['choice_labels'], 'kinds': j['kinds'], 'correct': j['correct'],
                                  'pass': j['pass'], 'readout_class': j['readout_class']},
                        'readout_fve_saved': s['fve'], 'readout_n_hit_bullets': n_hit,
                        'item_pass': row['item_id'] in item_pass[cond],
                    }
                    fo.write(json.dumps(rec, ensure_ascii=False) + '\n')
                    # ---- tallies
                    st['bullets'] += 1
                    st[f'bullets[{cond}]'] += 1
                    st[f'bullets_without_vector[{cond}]'] += not b['has_vector']
                    st[f'bullets_in_readout_without_fit[{cond}]'] += s['fve'] is None
                    lab_n[(cond, b['label'])] += 1
                    fine_n[(cond, b['label_fine'])] += 1
                    relaxed_n[(cond, b['label_relaxed'])] += 1
                    group_n[(cond, group)] += 1
                    full_n[(cond, b['label'], ff['label'])] += 1
                    for k, v in b['component'].items():
                        if v:
                            comp_n[(cond, k, v)] += 1
                    lab = b['label']
                    if lab == 'hit':
                        amb[(cond, 'hit_with_cjk_only_part')] += bool(cjk_parts)
                        amb[(cond, 'hit_patient_mentioned_first')] += b['order'] == 'patient_first'
                        amb[(cond, 'hit_same_term_matches_agent_and_patient')] += bool(overlap_terms)
                        amb[(cond, 'hit_not_evidence_best')] += not b['evidence_best']
                        amb[(cond, 'hit_in_readout_with_>1_hit')] += n_hit > 1
                        amb[(cond, 'hit_without_vector')] += not b['has_vector']
                        amb[(cond, 'hit_truncated_atom')] += bool(a['truncated'])
                    if lab == 'wrong_specific':
                        amb[(cond, 'wrong_specific_multi_reason')] += len(b['label_reasons']) > 1
                    if lab == 'miss' and b['n_components'] == 3 and not j['pass']:
                        amb[(cond, 'miss_failed_readout_names_A+P+V')] += 1
                        pools[(cond, 'miss_failed_A+P+V')].append((row['cell_id'], i))
                    if b['label'] != ff['label']:
                        amb[(cond, f"label_changes_on_visible_text:{b['label']}->{ff['label']}")] += 1
                        pools[(cond, 'label_changes_on_visible_text')].append((row['cell_id'], i))
                    if lab == 'hit' and b['binding'] != ff['binding']:
                        amb[(cond, 'hit_with_part_past_32_tokens')] += 1
                    pools[(cond, b['label_fine'])].append((row['cell_id'], i))
    os.replace(tmp, OUT)

    # ---- consistency with the map's selftest (same rule, same data)
    selftest = json.load(open(HERE / 'data' / 'selftest.json'))
    mine = {f'{c}|{k}': v for (c, k), v in sorted(fine_n.items())}
    assert mine == selftest['bullet_labels_fine'], 'label_fine counts differ from data/selftest.json'
    assert {f'{c}|{k}': v for (c, k), v in sorted(lab_n.items())} == selftest['bullet_labels']
    assert {f'{c}|{k}': v for (c, k), v in sorted(relaxed_n.items())} == selftest['bullet_labels_relaxed']

    conds = list(load.SETTINGS)
    res = collections.OrderedDict()
    res['rule'] = 'RBA-v1 (MAP.md section 7), load.label_readout on scored_text; label_visible = same rule on the decoded <=32 scored tokens'
    res['counts'] = dict(st)
    res['equals_selftest_counts'] = True
    res['labels'] = {c: {k: n for (cc, k), n in sorted(lab_n.items()) if cc == c} for c in conds}
    res['labels_fine'] = {c: {k: n for (cc, k), n in sorted(fine_n.items()) if cc == c} for c in conds}
    res['labels_relaxed'] = {c: {k: n for (cc, k), n in sorted(relaxed_n.items()) if cc == c} for c in conds}
    res['contrast_groups'] = {c: {k: n for (cc, k), n in sorted(group_n.items()) if cc == c} for c in conds}
    res['component'] = {c: {f'{k}|{v}': n for (cc, k, v), n in sorted(comp_n.items()) if cc == c} for c in conds}
    res['scored_vs_visible_label'] = {c: {f'{a}->{b}': n for (cc, a, b), n in sorted(full_n.items()) if cc == c and a != b}
                                       for c in conds}
    res['hits_per_passing_readout'] = {c: {str(k): n for (cc, k), n in sorted(hits_per_pass_readout.items()) if cc == c}
                                       for c in conds}
    res['ambiguity'] = {c: {k: n for (cc, k), n in sorted(amb.items()) if cc == c} for c in conds}
    pass_n = {c: sum(n for (cc, k), n in hits_per_pass_readout.items() if cc == c) for c in conds}
    located = {c: sum(n for (cc, k), n in hits_per_pass_readout.items() if cc == c and k > 0) for c in conds}
    res['coverage'] = {c: {
        'bullets': st[f'bullets[{c}]'],
        'passing_readouts': pass_n[c], 'passing_readouts_located': located[c],
        'located_share': round(located[c] / pass_n[c], 4),
        'bullets_in_passing_readouts': sum(n for (cc, k), n in fine_n.items() if cc == c and
                                           (k.startswith('hit') or k in ('miss_pass_other', 'unlocated'))),
        'unlocated_bullets': fine_n[(c, 'unlocated')],
        'bullets_excluded_no_fit': group_n[(c, 'excluded_no_fit')],
        'bullets_usable_for_fve_contrast': sum(n for (cc, k), n in group_n.items() if cc == c and not k.startswith('excluded')),
    } for c in conds}
    res['label_precision_from_reading_MAP_section_9'] = {
        'hit (strict+evidence+anchor)': '31/32 carry the judged binding (1 judge error)',
        'wrong_action+wrong_person': '10/10', 'wrong_reversed': 'about 4-5/8 (2/8 judge reversed a correct bullet)',
        'wrong_reversed_partial': 'about 50%: sensitivity only'}
    res['seconds'] = round(time.time() - t0, 1)
    VAL.write_text(json.dumps(res, indent=1))

    # ---- fixed-seed reading sample from the written file
    rng = random.Random(READ_SEED)
    want = {}
    for cond in conds:
        for bucket, k in (('hit_strict', 3), ('hit_evidence', 3), ('hit_anchor', 2), ('miss_pass_other', 2),
                          ('unlocated', 2), ('wrong_reversed', 2), ('wrong_action', 1), ('wrong_person', 1),
                          ('miss_failed_A+P+V', 3), ('label_changes_on_visible_text', 2), ('miss_partial', 1)):
            pool = pools.get((cond, bucket), [])
            for cid, i in rng.sample(pool, min(k, len(pool))):
                want[(cid, cond, i)] = bucket
    lines = []
    with open(OUT) as f:
        for line in f:
            r = json.loads(line)
            key = (r['cell_id'], r['setting'], r['index'])
            if key in want:
                lines.append((want[key], r))
    order = {b: n for n, b in enumerate(['hit_strict', 'hit_evidence', 'hit_anchor', 'miss_pass_other', 'unlocated',
                                         'wrong_reversed', 'wrong_action', 'wrong_person', 'miss_failed_A+P+V',
                                         'label_changes_on_visible_text', 'miss_partial'])}
    lines.sort(key=lambda x: (conds.index(x[1]['setting']), order[x[0]], x[1]['cell_id'], x[1]['index']))
    with open(READING, 'w') as fo:
        for bucket, r in lines:
            e = r['evidence']
            fo.write(f"## [{bucket}] {r['setting_short']} | {r['cell_id']} | bullet {r['index']}\n")
            fo.write(f"   gold: {r['gold']['gold_label']}  ({r['gold']['agent']} -> {r['gold']['action']} -> {r['gold']['patient']})\n")
            fo.write(f"   judge: {r['judge']['choice_labels']} kinds={r['judge']['kinds']} class={r['judge']['readout_class']}\n")
            fo.write(f"   evidence: {e['judge_evidence']}\n")
            fo.write(f"   label={r['label']} fine={r['label_fine']} relaxed={r['label_relaxed']} visible={r['label_visible']} "
                     f"reasons={r['label_reasons']} A={e['matched_terms']['agent']} P={e['matched_terms']['patient']} "
                     f"V={e['matched_terms']['action']} ev={e['evidence_overlap']}{'*' if e['evidence_best'] else ''} "
                     f"wrong={e['wrong_value']}\n")
            fo.write(f"   scored: {r['scored_text']!r}\n")
            if r['visible_text'] is not None:
                fo.write(f"   vector-visible (32 tok): {r['visible_text']!r}\n")
            fo.write('\n')
    print(json.dumps({k: res[k] for k in ('counts', 'labels', 'coverage', 'ambiguity', 'scored_vs_visible_label',
                                          'hits_per_passing_readout', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
