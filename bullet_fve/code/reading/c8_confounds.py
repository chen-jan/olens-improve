"""C8 (kinds of hallucination) confound checks. Exploratory, read-only on data.

Reuses the loader/feature code of synth_tests.py (lines before T1) and then tests:
 1. like-for-like kind pair rates: wrong bullets of a surface kind vs clean bullets that share the surface feature
    (novel name / novel number / first person in the scored part) and vs clean bullets without it;
 2. first-person base rates by source among clean vs wrong bullets, and P(wrong | first-person bullet);
 3. population rate of judge OFF-TOPIC bullets / readouts;
 4. reading records: reader verdict class by proxy kind for judge-WRONG focus bullets;
 5. reader relation codes among reader-confirmed errors (slot/swap vs added detail).
Run: ${OLENS_COMPUTE_ROOT}/envs/runtime/bin/python -B c8_confounds.py
"""
import os, sys, json, collections, math
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, 'synth_tests.py')).read().split('\n')
cut = next(i for i, l in enumerate(src) if 'T1 no separation anywhere' in l)
g = {'__file__': os.path.join(HERE, 'synth_tests.py'), '__name__': 'c8'}
exec(compile('\n'.join(src[:cut]), 'synth_head', 'exec'), g)
rows, LAB, by_ro, readouts, recs = g['rows'], g['LAB'], g['by_ro'], g['readouts'], g['recs']
FP, novel_caps, NUM = g['FP'], g['novel_caps'], g['NUM']
label_pair_rate, prop, ratio_ci, per_item, win = g['label_pair_rate'], g['prop'], g['ratio_ci'], g['per_item'], g['win']
SIDS, SHORT, OB = g['SIDS'], g['SHORT'], g['OB']
np = g['np']

# scored-part first person
for r in rows:
    r['fp_scored'] = 0.0
for (k, sid), ro in readouts.items():
    pass
for r in rows:
    # text is full bullet; scored part is first scored_len UTF-16 units
    tb = r['text'].encode('utf-16-le')
    scored = tb[:2 * r['scored_len']].decode('utf-16-le', errors='replace')
    r['fp_scored'] = float(bool(FP.search(scored)))
    r['fp_any'] = float(bool(FP.search(r['text'])))

out = {}
# ---------------------------------------------------------------- 1 like-for-like
t1 = {}
for sid in SIDS:
    sc = 'solo_pa' if sid in OB else 'solo'
    d = {}
    for nm, wsel, feat in [
        ('novel_name', lambda r: r.get('wkind') == 'novel_capitalised_name', 'b_novel_name'),
        ('novel_number', lambda r: r.get('wkind') == 'novel_number', 'b_novel_num'),
        ('first_person', lambda r: r.get('wkind') == 'first_person', 'fp_any'),
        ('long_other', lambda r: r.get('wkind') == 'long_other', None),
    ]:
        d[nm] = {'vs_all_clean': label_pair_rate([sid], sc, sel_w=wsel)}
        if feat:
            d[nm]['vs_clean_WITH_feature'] = label_pair_rate([sid], sc, sel_w=wsel, sel_c=lambda r, f=feat: r[f] == 1)
            d[nm]['vs_clean_WITHOUT_feature'] = label_pair_rate([sid], sc, sel_w=wsel, sel_c=lambda r, f=feat: r[f] == 0)
            # bullet-level feature regardless of span kind: wrong-with-feature vs clean-with-feature
            d[nm]['bulletfeat_wrong_vs_clean_both_with_feature'] = label_pair_rate(
                [sid], sc, sel_w=lambda r, f=feat: r[f] == 1, sel_c=lambda r, f=feat: r[f] == 1)
            d[nm]['bulletfeat_wrong_vs_clean_both_without_feature'] = label_pair_rate(
                [sid], sc, sel_w=lambda r, f=feat: r[f] == 0, sel_c=lambda r, f=feat: r[f] == 0)
    # same with raw solo too
    d['raw_solo_all_wrong'] = label_pair_rate([sid], 'solo')
    d['offtopic_vs_clean'] = label_pair_rate([sid], sc, wlab='o')
    d['offtopic_vs_clean_raw_solo'] = label_pair_rate([sid], 'solo', wlab='o')
    d['offtopic_vs_wrong'] = label_pair_rate([sid], sc, wlab='o', clab='w')
    t1[SHORT[sid]] = d
out['1_like_for_like_pair_rates'] = t1

# ---------------------------------------------------------------- 2 first-person base rates
t2 = {}
for sid in SIDS:
    R = [r for r in LAB if r['sid'] == sid]
    d = {}
    for s in ('dailydialog', 'lmsys'):
        d[s] = {
            'P(fp_any | clean)': prop(R, lambda r: r['fp_any'], lambda r, s=s: r['source'] == s and r['label'] == 'c'),
            'P(fp_any | wrong)': prop(R, lambda r: r['fp_any'], lambda r, s=s: r['source'] == s and r['label'] == 'w'),
            'P(wrong | fp_any)': prop(R, lambda r: r['label'] == 'w', lambda r, s=s: r['source'] == s and r['fp_any'] == 1),
            'P(wrong | no fp)': prop(R, lambda r: r['label'] == 'w', lambda r, s=s: r['source'] == s and r['fp_any'] == 0),
            'P(wrong | novel spec)': prop(R, lambda r: r['label'] == 'w',
                                          lambda r, s=s: r['source'] == s and (r['b_novel_num'] or r['b_novel_name'])),
            'P(wrong | no novel spec)': prop(R, lambda r: r['label'] == 'w',
                                             lambda r, s=s: r['source'] == s and not (r['b_novel_num'] or r['b_novel_name'])),
            'P(wrong) overall': prop(R, lambda r: r['label'] == 'w', lambda r, s=s: r['source'] == s),
        }
    t2[SHORT[sid]] = d
out['2_first_person_base_rates'] = t2

# ---------------------------------------------------------------- 3 off-topic population rates
t3 = {}
for sid in SIDS:
    R = [r for r in LAB if r['sid'] == sid]
    ros = [ro for (k, s2), ro in readouts.items() if s2 == sid]
    t3[SHORT[sid]] = {
        'n_labelled_bullets': len(R),
        'label_counts': dict(collections.Counter(r['label'] for r in R)),
        'P(off-topic bullet)': prop(R, lambda r: r['label'] == 'o'),
        'P(off-topic | not clean)': prop(R, lambda r: r['label'] == 'o', lambda r: r['label'] != 'c'),
        'readout_label_counts': dict(collections.Counter(ro['label'] for ro in ros)),
    }
out['3_offtopic_rates'] = t3

# ---------------------------------------------------------------- 4 reading records: reader class by proxy kind
rowmap = {(r['k'], r['sid'], r['j']): r for r in rows}
ct = collections.defaultdict(collections.Counter)
ct_bt = collections.defaultdict(collections.Counter)
for rec in recs:
    if rec['label'] != 'w':
        continue
    rr = rowmap.get((rec['k'], rec['setting'], rec['bullet']))
    kd = rr.get('wkind', 'missing') if rr else 'missing'
    ct[kd][rec['reader_class']] += 1
    ct_bt[kd][rec['blind_type']] += 1
out['4_reader_class_by_proxy_kind_judgeWRONG'] = {k: dict(v) for k, v in ct.items()}
out['4_blind_type_by_proxy_kind_judgeWRONG'] = {k: dict(v) for k, v in ct_bt.items()}

# ---------------------------------------------------------------- 5 reader codes among confirmed errors
err = [r for r in recs if r['reader_class'] == 'error']
c5 = collections.Counter()
for r in err:
    codes = set(r['rel_codes'])
    slot = bool(codes & {'right_frame_or_slot', 'filler_swapped'})
    add = 'adds_unsupported_detail' in codes
    c5[('slot_or_swap' if slot else 'no_slot') + '+' + ('adds' if add else 'no_add')] += 1
out['5_error_records_slot_vs_add_codes'] = dict(c5)
out['5_error_records_n'] = len(err)
bt5 = collections.defaultdict(collections.Counter)
for r in err:
    codes = set(r['rel_codes'])
    bt5[r['blind_type']]['slot_or_swap' if codes & {'right_frame_or_slot', 'filler_swapped'} else 'no_slot'] += 1
out['5_by_blind_type'] = {k: dict(v) for k, v in bt5.items()}
out['5_persona_records'] = [(r['k'], SHORT[r['setting']], r['bullet'], r['stratum'], r['source']) for r in recs
                            if r['blind_type'] == 'persona_or_self_claim']

json.dump(out, open(os.path.join(HERE, 'c8_confounds.json'), 'w'), indent=1, default=lambda x: x.item() if hasattr(x, 'item') else str(x))
print(json.dumps(out, indent=1, default=lambda x: x.item() if hasattr(x, 'item') else str(x)))
