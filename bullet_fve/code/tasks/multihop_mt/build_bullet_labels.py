"""Per-bullet labels with located evidence for Multihop (multi-token) (multihop_mt).

One JSON row per bullet (all 3 settings, 13,196 bullets). The label rule is load.label_text (MAP.md
section 6): the pinned regex judge's own strict rule applied to the bullet alone.
  hit             >=1 REQUIRED bridge unit hit by a strict (multi-token, scorer) form
  wrong-specific  no strict and no lenient hit of a required unit, but >=1 bank MC distractor named
  miss            everything else
Evidence: every strict / lenient / distractor / target form that fires is re-located in the bullet
text with the scorer's own matching rule (fold + word-boundary or substring), mapped back to raw
character offsets, and quoted verbatim. `evidence_primary` is what decides the label (strict
matches for hit, distractor matches for wrong-specific, empty for miss). Every located span is
checked to agree with the scorer's boolean matcher.

Also writes item_targets.json (per item: required roles, gold, strict forms, lenient aliases,
distractors, target) so each label can be audited against the bank.

READ-ONLY on project data. Usage: python -B build_bullet_labels.py   (run in a CPU allocation)
"""
import collections
import json
import re
import sys
from pathlib import Path

TASK = Path('${OLENS_SCRATCH}/olens-bullet-fve/tasks/multihop_mt')
sys.path.insert(0, str(TASK))
import load  # noqa: E402

RX = load.RX


def fold_map(raw):
    """fold(raw) built char by char + map folded index -> raw index. Returns (folded, idx) or None."""
    parts, idx = [], []
    for i, ch in enumerate(raw):
        f = RX.fold(ch)
        parts.append(f)
        idx.extend([i] * len(f))
    folded = ''.join(parts)
    return (folded, idx) if folded == RX.fold(raw) else None


def form_spans(form, sample):
    """All (start, end) raw-offset spans in `sample` where the scorer's matcher for `form` fires.
    Mirrors RX.unicode_word_matcher; numeric forms (none required in this bank) return None."""
    f = RX.fold(form)
    if re.fullmatch(r'\d+', f):
        return None
    fm = fold_map(sample)
    if fm is None:
        return None
    folded, idx = fm
    if RX._CJK_HANGUL.search(form) or not RX._WORDY.fullmatch(f):
        spans, i = [], folded.find(f)
        while i >= 0:
            spans.append((i, i + len(f)))
            i = folded.find(f, i + 1)
    else:
        parts = [re.escape(w) for w in re.split(r'[\s\-]+', f) if w]
        pat = re.compile(r'(?<![^\W_])' + r'[\s\-]+'.join(parts) + r'(?![^\W_])')
        spans = [(m.start(), m.end()) for m in pat.finditer(folded)]
    return [(idx[s], idx[e - 1] + 1) for s, e in spans]


def evidence(kind, role, forms, text, sample, sample_off, readout_off, stats):
    out = []
    for form in forms:
        spans = form_spans(form, sample)
        matcher_fires = RX.unicode_word_matcher(form)(sample)
        if spans is None:
            stats['evidence_unlocatable'] += 1
            out.append({'kind': kind, 'role': role, 'form': form, 'quote': None, 'span': None,
                        'readout_span': None, 'n_occurrences': None})
            continue
        assert bool(spans) == matcher_fires, (form, sample)
        assert spans, (kind, role, form, sample)
        s, e = spans[0]
        quote = sample[s:e]
        bs, be = s + sample_off, e + sample_off
        assert text[bs:be] == quote
        norm = lambda x: re.sub(r'[\s\-]+', ' ', RX.fold(x)).strip()  # noqa: E731
        stats['evidence_quote_equals_form_normalised' if norm(quote) == norm(form)
              else 'evidence_quote_differs_from_form'] += 1
        out.append({'kind': kind, 'role': role, 'form': form, 'quote': quote, 'span': [bs, be],
                    'readout_span': [bs + readout_off, be + readout_off], 'n_occurrences': len(spans)})
    return out


def gold_cut_at_end(text, spec, min_chars=4):
    """Heuristic flag: the bullet ENDS with a proper prefix (>= min_chars) of a strict or lenient
    required-role form that is not itself complete, e.g. 'Simula 6', 'Heitor Villa-Lob'."""
    tail = RX.fold(text.rstrip().rstrip('*_`"\''))

    def ends_with_word(s):
        j = len(tail) - len(s)
        return tail.endswith(s) and (j == 0 or not tail[j - 1].isalnum())

    hits, seen = [], set()
    for role in spec['required_roles']:
        forms = sorted({f for f, _ in spec['_strict_m'].get(role, [])} | {f for f, _ in spec['_lenient_m'].get(role, [])})
        # the bullet already ENDS with a complete strict or lenient form of this role (e.g. 'Akbar',
        # 'the Altair'): not a cut name
        if any(RX.fold(f) and ends_with_word(RX.fold(f)) for f in forms):
            continue
        for form in forms:
            f = RX.fold(form)
            for k in range(len(f) - 1, min_chars - 1, -1):
                pre = f[:k]
                if ends_with_word(pre):
                    if (role, pre) not in seen:
                        seen.add((role, pre))
                        hits.append({'role': role, 'form': form, 'cut': pre})
                    break
    return hits


def main():
    bank = load.load_bank()
    judgments = {c: load.load_judgments(c)[0] for c in load.SETTINGS}
    stats = collections.Counter()
    out_path = TASK / 'bullet_labels.jsonl'
    tmp = out_path.with_suffix('.jsonl.tmp')
    with open(tmp, 'w') as out:
        for row in load.iter_rows(bank, judgments):
            spec = bank[row['item_id']]
            j = row['judge']
            gold = {r: (spec['intermediates'][k] if k < len(spec['intermediates']) else None)
                    for k, r in enumerate(spec['required_roles'])}
            for b in row['bullets']:
                text = b['text']
                sample = RX.extract_phrase(text)
                sample_off = text.find(sample) if sample else 0
                if sample != text.strip():
                    stats['sample_differs_from_stripped_text'] += 1
                readout_off = b['char_span'][0]
                assert row['text'][b['char_span'][0]:b['char_span'][1]] == text
                ev = []
                for role, forms in b['strict_forms'].items():
                    ev += evidence('strict' if role != 'target' else 'target_strict', role, forms, text, sample,
                                   sample_off, readout_off, stats)
                for role, forms in b['lenient_forms'].items():
                    strict_here = set(b['strict_forms'].get(role, []))
                    extra = [f for f in forms if f not in strict_here]
                    if extra:
                        ev += evidence('lenient' if role != 'target' else 'target_lenient', role, extra, text,
                                       sample, sample_off, readout_off, stats)
                for role, forms in b['distractors_named'].items():
                    ev += evidence('distractor', role, forms, text, sample, sample_off, readout_off, stats)
                if b['label'] == 'hit':
                    prim = [e for e in ev if e['kind'] == 'strict' and e['role'] in spec['required_roles']]
                elif b['label'] == 'wrong-specific':
                    prim = [e for e in ev if e['kind'] == 'distractor']
                else:
                    prim = []
                cut = gold_cut_at_end(text, spec)
                rec = {
                    'cell_id': row['cell_id'], 'setting': row['setting'], 'setting_short': load.SHORT[row['setting']],
                    'index': b['index'], 'phrase_id': b['phrase_id'], 'cache_key': b['cache_key'],
                    'item_id': row['item_id'], 'group_id': row['group_id'], 'subfamily': row['subfamily'],
                    'layer': row['layer'], 'position': row['position'], 'split': row['split'],
                    'text': text, 'char_span': b['char_span'], 'truncated': b['truncated'],
                    'label': b['label'], 'label_lenient': b['label_lenient'], 'near_hit': b['near_hit'],
                    'strict_roles': b['strict_roles'], 'lenient_roles': b['lenient_roles'],
                    'distractor_roles': b['distractor_roles'], 'hedge': b['hedge'],
                    'target_hit_strict': b['target_hit_strict'], 'target_hit_lenient': b['target_hit_lenient'],
                    'strict_roles_in_scored_prefix': b['strict_roles_in_scored_prefix'],
                    'hit_visible_to_vector': (b['label'] != 'hit') or bool(b['strict_roles_in_scored_prefix']),
                    'gold_cut_at_end': cut,
                    'evidence_primary': prim, 'evidence': ev,
                    'gold': gold, 'required_roles': spec['required_roles'],
                    'readout_fve_saved': row['fve'], 'readout_pass': j['cell_pass'],
                    'readout_unit_hits': {r: bool(v) for r, v in j['unit_hits'].items()},
                    'item_pass': j['item_pass'], 'n_bullets_in_readout': len(row['bullets']),
                }
                out.write(json.dumps(rec, ensure_ascii=False) + '\n')
                stats['bullets'] += 1
                stats[f'label={b["label"]}'] += 1
                if b['label'] != 'miss':
                    stats['labelled_non_miss_with_primary_evidence' if prim else 'labelled_non_miss_WITHOUT_evidence'] += 1
    tmp.replace(out_path)

    items = {}
    for iid, spec in bank.items():
        items[iid] = {k: v for k, v in spec.items() if not k.startswith('_') and k != 'prompt'}
        items[iid]['prompt'] = spec['prompt']
        items[iid]['gold'] = {r: (spec['intermediates'][k] if k < len(spec['intermediates']) else None)
                              for k, r in enumerate(spec['required_roles'])}
        items[iid]['strict_forms'] = {u.role: u.all_forms() for u in spec['_units']}
    (TASK / 'item_targets.json').write_text(json.dumps(items, indent=1, ensure_ascii=False))
    print(json.dumps(dict(sorted(stats.items())), indent=1))
    assert stats['labelled_non_miss_WITHOUT_evidence'] == 0


if __name__ == '__main__':
    main()
