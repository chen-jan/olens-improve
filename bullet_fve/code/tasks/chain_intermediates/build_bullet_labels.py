"""Flatten chain_bullet_labels.jsonl (MAP.md section 5 rules, made by `load.py labels`) into one row per
bullet with the evidence for every labelled bullet, join-check it against bullet_metrics.jsonl, and write
the label validation stats.

Reads (all inside this folder): chain_bullet_labels.jsonl, chain_three_settings.jsonl (scored_text for the
truncation check), bullet_metrics.jsonl (join check only), load.py (rules; nothing re-judged).
Writes: bullet_labels.jsonl (one line per bullet x setting), labels_validation.json.
No judge/API calls. Light (seconds); runs on the login node.

Evidence per bullet (field `evidence`; null for bullets that carry nothing under any column):
  carry_via      list of reasons the bullet carries the readout's verified top value under the PRIMARY
                 label: 'anchor:<anchor_source>' (the judge's quote is located here, by the judge's own
                 match rule) and/or 'lead:<how>' / 'derived' (top value in a computed position, string rule).
  quote          the judge's quote (verbatim, readout level).
  quote_matches  every occurrence of the quote that overlaps this bullet: the matched readout text
                 (verbatim, may cross into the next bullet), its char span in the readout, and the part
                 inside this bullet.
  value_matches  every whole-number occurrence of the top value in the bullet: span, +-40-char context,
                 whether it is the bullet's lead value / a derived value, and whether it falls inside the
                 scored (<=32-token) prefix the AR vector actually encodes.
  gold_matches   whole-number occurrences of any gold intermediate (for gold_named / states_intermediate).
  target         gold intermediates / answer / start and the judge's top value + role.
"""
import collections
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import load as L  # noqa: E402

# Reading audit (2026-10-15): 8 random bullets per class (random.Random(11) over bullet_labels.jsonl rows),
# read in full; verdict = does the primary label match what the bullet itself states?
AUDIT = {
    'hit_anchor': {'read': 8, 'agree': 6, 'disagree': [
        ['chain_intermediates|chain-w2-d2p-0238|L56|p00066', 'capped_n1-n1', 0, '13. **Sleepy, but hopeful',
         'list-index-like 13; bare-number quote "13" anchors every bullet with 13 (ambiguous_anchor=true)'],
        ['chain_intermediates|chain-w2-d2p-0238|L56|p00066', 'capped_n1-n1', 2,
         '12, "Goodnight, babe." (Note: In some regions, "13" can be a typo',
         '13 is a quoted echo, the bullet states 12 (ambiguous_anchor=true)']],
        'agree_examples': [
        ['chain_intermediates|chain-d2p-0231|L40|p00068', 'best_n_exact-n32', 2,
         '2** (Explanation: The number is halved three times: 16 -> 8 -> 4 -> 2.)'],
        ['chain_intermediates|chain-d2p-0295|L36|p00068', 'capped_n1-n1', 2,
         '18 ... 1. Divide 12 by 2 to get 6.  (lead is the answer 18; the hidden 6 is derived in the explanation)']]},
    'hit_non_anchor': {'read': 8, 'agree': 8, 'disagree': [], 'agree_examples': [
        ['chain_intermediates|chain-w2-d2p-0270|L48|p00063', 'best_n_exact-n32', 3,
         '24** (Explanation: First, the number is doubled to get 12. Then, 12 is tripled to get 36.)'],
        ['chain_intermediates|chain-w2-d2p-0203|L52|p00064', 'capped_n1-n1', 0, '18$ (since 6 × 3 = 1']]},
    'wrong_specific': {'read': 8, 'agree': 8, 'disagree': [], 'agree_examples': [
        ['chain_intermediates|chain-w2-d2p-0258|L52|p00062', 'best_n_exact-n32', 2,
         '260$$ (Since 130 multiplied by 2 equals 260)'],
        ['chain_intermediates|chain-w2-d2p-0108|L32|p00063', 'capped_n1-n1', 3,
         'The result is 12. (12 = start, wrong_role=start)']]},
    'miss_in_hit_readout': {'read': 8, 'agree': 8, 'disagree': [], 'agree_examples': [
        ['chain_intermediates|chain-d2p-0385|L48|p00066', 'capped_n1-n1', 1,
         '15 ``` (Since 20 divided by 2 equals 15)  (gold 10; states the answer 15)'],
        ['chain_intermediates|chain-d3p-0758|L48|p00069', 'pooled_greedy_swap-n32', 2,
         '25 ## Explanation: Start with 18, add 5, subtract 2']]},
}

OUT = HERE / 'bullet_labels.jsonl'
VALID = HERE / 'labels_validation.json'
CTX = 40


def num_spans(n, text):
    return [m.span() for m in re.finditer(rf'(?<!\d)(?<!\d\.){n}(?!\d)(?!\.\d)', text)]


def stated_spans(btext):
    """stated_values() with char spans (relative to btext): (lead, how, lead_span), [(value, span)]."""
    off0 = len(btext) - len(btext.lstrip())
    s = btext.strip()
    rest = L._LEAD_STRIP.sub('', s)
    k = len(s) - len(rest)
    lead = how = span = None
    m = L._LEAD_NUM.match(rest)
    if m and not L._LIST_INDEX.match(rest):
        lead, how, span = int(m.group(1)), 'leading', (off0 + k + m.start(1), off0 + k + m.end(1))
    else:
        for rx, name in ((L._PHRASE, 'phrase'), (L._BOLD, 'bold'), (L._ALONE, 'alone')):
            m = rx.search(s)
            if m:
                lead, how, span = int(m.group(1)), name, (off0 + m.start(1), off0 + m.end(1))
                break
    derived = [(int(m.group(1)), (off0 + m.start(1), off0 + m.end(1))) for m in L._DERIVED.finditer(s)]
    return lead, how, span, derived


def common_prefix(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def ctx(text, a, b):
    lo, hi = max(0, a - CTX), min(len(text), b + CTX)
    return ('…' if lo else '') + text[lo:a] + '⟦' + text[a:b] + '⟧' + text[b:hi] + ('…' if hi < len(text) else '')


def main():
    metrics = {}
    for line in open(HERE / 'bullet_metrics.jsonl'):
        r = json.loads(line)
        metrics[r['cell_id']] = r
    scored = {}
    for line in open(HERE / 'chain_three_settings.jsonl'):
        c = json.loads(line)
        for sid, s in c['settings'].items():
            for a in s['atoms']:
                scored[(c['cell_id'], a['source_phrase_id'])] = (a['scored_text'], a['truncated'],
                                                                 a['scored_token_count'], a['original_token_count'])

    st = collections.Counter()           # validation counts
    ex = collections.defaultdict(list)   # examples per check (cell_id, setting, bullet, text)
    lab_tab = {col: collections.defaultdict(collections.Counter)
               for col in ('label', 'label_anchor', 'label_contains', 'label_named', 'label_stated', 'wrong_role')}
    xt = collections.defaultdict(collections.Counter)  # sid -> 'label x label_named' etc.

    def add_ex(key, *row, k=6):
        if len(ex[key]) < k:
            ex[key].append(list(row))

    tmp = OUT.with_suffix('.jsonl.tmp')
    n_rows = 0
    with open(tmp, 'w') as out:
        for c in L.iter_labelled():
            g = c['gold']
            m = metrics[c['cell_id']]
            for sid in L.SETTINGS:
                s = c['settings'][sid]
                j = s['judge']
                text = s['text']
                kind = j['kind']
                verified = kind in ('hit', 'near', 'other')
                bl = s['bullets']
                mb = m['settings'][sid]['bullets']
                # ---- join check against metrics
                assert [b['phrase_id'] for b in bl] == [x['phrase_id'] for x in mb], (c['cell_id'], sid)
                assert [b['cache_key'] for b in bl] == [x['cache_key'] for x in mb], (c['cell_id'], sid)
                st[f'joined_readouts[{sid}]'] += 1
                top = j['top']
                occ = L.quote_spans(j['quote'] or '', text) if verified else []
                labels = [b['label'] for b in bl]
                bare_quote = bool(re.fullmatch(r'[\s\-*$`#.]*\d+[\s*$`.]*', j['quote'] or ''))
                multi_bare = verified and bare_quote and len(j['anchor_bullets']) > 1
                # ---- readout-level validation
                st[f'readouts[{sid}]'] += 1
                st[f'kind={kind}[{sid}]'] += 1
                if verified:
                    carriers = [b for b in bl if b['label'] != 'miss']
                    st[f'verified_with_carrier[{sid}]'] += bool(carriers)
                    st[f'verified[{sid}]'] += 1
                    na = len(j['anchor_bullets'])
                    st[f'anchors_n={min(na, 3)}{"+" if na >= 3 else ""}[{sid}]'] += 1
                    st[f'anchor_source={j["anchor_source"]}[{sid}]'] += 1
                    st[f'carriers_n={len(carriers)}[{sid}]'] += 1
                    if na > 1:
                        add_ex(f'multi_anchor[{sid}]', c['cell_id'], kind, j['values'], j['quote'], j['anchor_bullets'],
                               j['anchor_source'])
                        # a bare-number quote ('13', '- 13', '**13**') matches every bullet that has the number:
                        # the anchor does not single out the bullet the judge read
                        if re.fullmatch(r'[\s\-*$`#.]*\d+[\s*$`.]*', j['quote'] or ''):
                            st[f'multi_anchor_bare_number_quote[{sid}]'] += 1
                            st[f'multi_anchor_bare_number_quote[{kind}][{sid}]'] += 1
                            add_ex(f'multi_anchor_bare_quote[{sid}]', c['cell_id'], kind, j['values'], j['quote'],
                                   j['anchor_bullets'], [x['text'][:60] for x in bl])
                    if j['anchor_source'] == 'number':
                        st[f'quote_not_located_number_fallback[{sid}]'] += 1
                        add_ex(f'number_fallback[{sid}]', c['cell_id'], kind, j['values'], j['quote'],
                               j['anchor_bullets'])
                    if j['anchor_source'] == 'quote':
                        st[f'quote_only_top_not_numeral[{sid}]'] += 1
                        add_ex(f'quote_only[{sid}]', c['cell_id'], kind, j['values'], j['quote'], j['anchor_bullets'])
                    if len(occ) > 1:
                        st[f'quote_multiple_occurrences[{sid}]'] += 1
                    cross = [(a, b2) for (a, b2) in occ
                             if sum(1 for (s0, s1) in [(x['char_start'], x['char_end']) for x in bl]
                                    if a < s1 and b2 > s0 - 2) > 1]
                    if cross:
                        st[f'quote_crosses_bullet_boundary[{sid}]'] += 1
                        add_ex(f'quote_cross[{sid}]', c['cell_id'], kind, j['quote'], text[cross[0][0]:cross[0][1]])
                    if len(carriers) == len(bl):
                        st[f'all_bullets_carry[{sid}]'] += 1
                        if kind == 'hit':
                            st[f'hit_readout_no_contrast[{sid}]'] += 1
                    if kind == 'hit':
                        st[f'hit_readouts[{sid}]'] += 1
                        st[f'hit_readouts_with_hit_bullet[{sid}]'] += 'hit' in labels
                        st[f'hit_readouts_with_contrast[{sid}]'] += 0 < labels.count('hit') < len(bl)
                else:
                    st[f'unverified_or_none_all_miss[{sid}]'] += set(labels) == {'miss'}
                if top is not None and len(str(top)) == 1 and verified:
                    st[f'single_digit_top[{sid}]'] += 1
                # ---- per bullet rows
                for b, mm in zip(bl, mb):
                    sc_text, trunc, sc_n, orig_n = scored[(c['cell_id'], b['phrase_id'])]
                    pre = len(b['text']) if not trunc else common_prefix(b['text'], sc_text)
                    lead, how, lspan, derived = stated_spans(b['text'])
                    assert (lead, how) == (b['lead_value'], b['lead_how']), (c['cell_id'], sid, b['index'])
                    dvals = []
                    for v, _ in derived:
                        if v not in dvals:
                            dvals.append(v)
                    assert dvals == b['derived_values'], (c['cell_id'], sid, b['index'])
                    s0, s1 = b['char_start'], b['char_end']
                    any_label = (b['label'] != 'miss' or b['label_contains'] != 'miss'
                                 or b['label_named'] != 'none_named' or b['label_stated'] in ('states_intermediate', 'derives_intermediate'))
                    evidence = None
                    if any_label:
                        carry_via = []
                        if b['anchor']:
                            carry_via.append(f'anchor:{j["anchor_source"]}')
                        if b['top_in_computed_position']:
                            if top == b['lead_value']:
                                carry_via.append(f'lead:{b["lead_how"]}')
                            if top in b['derived_values']:
                                carry_via.append('derived')
                        qm = [{'readout_span': [a, e], 'matched': text[a:e],
                               'in_bullet': text[max(a, s0):min(e, s1)]}
                              for (a, e) in occ if a < s1 and e > s0 - 2]
                        vm = []
                        if top is not None:
                            for a, e in num_spans(top, b['text']):
                                vm.append({'span': [a, e], 'context': ctx(b['text'], a, e),
                                           'is_lead': lspan == (a, e),
                                           'is_derived': any(sp == (a, e) for v, sp in derived),
                                           'in_scored_prefix': e <= pre})
                        # the top value in a computed position (what top_in_computed_position used): the lead
                        # value (int('06') == 6, so its span need not be a whole-number match) and derived values
                        cm = []
                        if top is not None and b['top_in_computed_position']:
                            if lspan is not None and lead == top:
                                cm.append({'how': f'lead:{how}', 'span': list(lspan), 'context': ctx(b['text'], *lspan),
                                           'in_scored_prefix': lspan[1] <= pre})
                            for v, sp in derived:
                                if v == top:
                                    cm.append({'how': 'derived', 'span': list(sp), 'context': ctx(b['text'], *sp),
                                               'in_scored_prefix': sp[1] <= pre})
                        gm = []
                        for x in g['intermediates']:
                            for a, e in num_spans(x, b['text']):
                                gm.append({'value': x, 'span': [a, e], 'context': ctx(b['text'], a, e),
                                           'in_scored_prefix': e <= pre})
                        evidence = {
                            'carry_via': carry_via, 'quote': j['quote'], 'quote_matches': qm,
                            'value_matches': vm, 'computed_matches': cm, 'gold_matches': gm,
                            # every whole-number occurrence of the top value is the head of a comma-grouped
                            # number ('18,000' contains 18 under the judge's names_number rule)
                            'top_only_as_thousands_head': bool(vm) and all(
                                re.match(r',\d{3}(?!\d)', b['text'][v['span'][1]:]) for v in vm),
                            'target': {'intermediates': g['intermediates'], 'answer': g['answer'], 'start': g['start'],
                                       'judge_top': top, 'judge_values': j['values'], 'readout_kind': kind,
                                       'top_role': (None if top is None else 'intermediate' if top in g['intermediates']
                                                    else 'answer' if top == g['answer'] else 'near' if top in g['near']
                                                    else 'start' if top == g['start'] else 'literal' if top in g['literals']
                                                    else 'other')},
                        }
                        # is the carrying evidence inside the scored (<=32-token) prefix the AR vector encodes?
                        # anchor: the top value as a whole number, or (numeral word / decimal) the in-bullet
                        # part of the quote, starts inside the prefix; non-anchor: a lead/derived occurrence of
                        # the top value lies inside the prefix.
                        if b['label'] != 'miss':
                            if b['anchor']:
                                ok = (any(v['in_scored_prefix'] for v in vm)
                                      or (not vm and any(max(qq['readout_span'][0], s0) - s0 < pre for qq in qm)))
                            else:
                                ok = any(x['in_scored_prefix'] for x in cm)
                            evidence['in_scored_prefix'] = ok
                            if evidence['top_only_as_thousands_head']:
                                st[f'carrier_top_only_as_thousands_head[{sid}]'] += 1
                                st[f'carrier_top_only_as_thousands_head[{b["label"]}][{sid}]'] += 1
                                add_ex(f'thousands_head[{sid}]', c['cell_id'], b['index'], b['label'], top,
                                       carry_via, j['quote'], b['text'][:120])
                            st[f'carrier_evidence_in_scored_prefix={ok}[{sid}]'] += 1
                            if trunc:
                                st[f'carrier_truncated[{sid}]'] += 1
                            if not ok:
                                add_ex(f'evidence_beyond_scored_prefix[{sid}]', c['cell_id'], b['index'], b['label'], top,
                                       b['text'][:160], sc_text[-60:])
                    row = {
                        'cell_id': c['cell_id'], 'setting': sid, 'display': L.DISPLAY[sid],
                        'item_id': c['item_id'], 'group_id': c['group_id'], 'layer': c['layer'],
                        'position': c['position'], 'split': c['split'],
                        'bullet': b['index'], 'n_bullets': len(bl), 'phrase_id': b['phrase_id'],
                        'cache_key': b['cache_key'], 'text': b['text'], 'char_start': s0, 'char_end': s1,
                        'truncated': trunc, 'scored_token_count': sc_n, 'original_token_count': orig_n,
                        'scored_prefix_chars': pre, 'dup_vector': mm['dup'],
                        'readout_fve': s['fve'], 'readout_kind': kind, 'item_pass': s['item_pass'],
                        'judge_values': j['values'], 'judge_quote': j['quote'], 'judge_basis': j['basis'],
                        'anchor_source': j['anchor_source'], 'anchor_bullets': j['anchor_bullets'],
                        'gold_intermediates': g['intermediates'], 'gold_answer': g['answer'], 'gold_start': g['start'],
                        'depth': g['depth'],
                        'label': b['label'], 'label_value': b['label_value'], 'wrong_role': b['wrong_role'],
                        'is_anchor': b['anchor'], 'top_as_number': b['top_as_number'],
                        'top_in_computed_position': b['top_in_computed_position'],
                        'label_anchor': b['label_anchor'], 'label_contains': b['label_contains'],
                        'label_named': b['label_named'], 'judge_ranks_here': b['judge_ranks_here'],
                        'label_stated': b['label_stated'], 'lead_value': b['lead_value'], 'lead_how': b['lead_how'],
                        'derived_values': b['derived_values'], 'gold_mentioned': b['gold_mentioned'],
                        'numbers': b['numbers'],
                        # carries ONLY because a bare-number quote ('15', '- 15') matched several bullets and the
                        # value is not in a computed position here (often an operand echo): ambiguous attribution
                        'ambiguous_anchor': bool(multi_bare and b['anchor'] and not b['top_in_computed_position']),
                        'evidence': evidence,
                    }
                    out.write(json.dumps(row, ensure_ascii=False) + '\n')
                    n_rows += 1
                    # ---- per bullet validation
                    for col in ('label', 'label_anchor', 'label_contains', 'label_named', 'label_stated'):
                        lab_tab[col][sid][b[col]] += 1
                    if b['label'] == 'wrong_specific':
                        lab_tab['wrong_role'][sid][b['wrong_role']] += 1
                    xt[sid][f'{b["label"]} x {b["label_named"]}'] += 1
                    xt[sid][f'{b["label"]} x {b["label_stated"]}'] += 1
                    if row['ambiguous_anchor']:
                        st[f'ambiguous_anchor[{sid}]'] += 1
                        st[f'ambiguous_anchor[{b["label"]}][{sid}]'] += 1
                        add_ex(f'ambiguous_anchor[{sid}]', c['cell_id'], b['index'], b['label'], top, j['quote'],
                               b['text'][:140])
                    if b['label'] == 'hit':
                        st[f'hit_bullets_by_layer[L{c["layer"]}][{sid}]'] += 1
                        st[f'hit_via_anchor[{sid}]'] += b['anchor']
                        st[f'hit_non_anchor[{sid}]'] += not b['anchor']
                    if b['label'] != 'miss':
                        st[f'carrier_via_anchor[{sid}]'] += b['anchor']
                        st[f'carrier_non_anchor[{sid}]'] += not b['anchor']
                        st[f'carrier_dup_vector[{sid}]'] += mm['dup']
                        bare = re.fullmatch(r'[\s*$`#.\[\]()]*\d+[\s*$`#.\[\]()]*', b['text']) is not None
                        st[f'carrier_number_only[{sid}]'] += bare
                        if b['label'] == 'hit':
                            st[f'hit_number_only[{sid}]'] += bare
                            st[f'hit_dup_vector[{sid}]'] += mm['dup']
                    if b['label'] == 'miss' and b['label_contains'] != 'miss':
                        st[f'loose_only_echo[{sid}]'] += 1
                        add_ex(f'loose_only_echo[{sid}]', c['cell_id'], b['index'], b['label_contains'], top, b['text'][:160])
                    if b['label'] != 'miss' and not b['anchor']:
                        add_ex(f'non_anchor_carrier[{sid}]', c['cell_id'], b['index'], b['label'], top, j['quote'],
                               b['text'][:160])
                    if b['label'] == 'miss' and b['label_named'] == 'gold_named':
                        st[f'miss_but_gold_named[{sid}]'] += 1
                        add_ex(f'miss_but_gold_named[{sid}]', c['cell_id'], b['index'], kind, j['values'], b['text'][:160])
                    if b['label'] == 'miss' and b['label_stated'] == 'states_intermediate':
                        st[f'miss_but_states_intermediate[{sid}]'] += 1
                        add_ex(f'miss_but_states_intermediate[{sid}]', c['cell_id'], b['index'], kind, j['values'],
                               b['text'][:160])
                    if b['label'] != 'miss' and re.search(r'\d,\d{3}', b['text']):
                        st[f'carrier_thousands_separator[{sid}]'] += 1
                        add_ex(f'thousands_sep[{sid}]', c['cell_id'], b['index'], b['label'], top, b['text'][:160])
    os.replace(tmp, OUT)

    def per_sid(prefix):
        return {sid: st.get(f'{prefix}[{sid}]', 0) for sid in L.SETTINGS}

    keys = sorted({k.rsplit('[', 1)[0] for k in st})
    validation = {
        'rows': n_rows,
        'label_counts': {col: {sid: dict(sorted(v.items())) for sid, v in t.items()} for col, t in lab_tab.items()},
        'per_setting': {k: per_sid(k) for k in keys},
        'crosstab': {sid: dict(sorted(v.items())) for sid, v in xt.items()},
        'reading_audit': AUDIT,
        'examples': dict(ex),
    }
    VALID.write_text(json.dumps(validation, indent=1, ensure_ascii=False))
    print(json.dumps({k: validation[k] for k in ('rows', 'label_counts', 'per_setting')}, indent=1))


if __name__ == '__main__':
    main()
