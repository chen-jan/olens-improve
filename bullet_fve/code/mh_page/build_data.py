"""Data for the Multihop FVE Explorer (mh_page/index.html). Exploratory.

Re-derives the judged text of ALL 32 raw lens samples per cell exactly as
tasks/multihop_mt/baseline/baseline.py does (olens-improve selection.parse_bullets with the
Qwen3.6 token count and a 256-token cap, then render_bullets), judges each with the pinned regex
(tasks/multihop_mt/load.py RX), labels each bullet with load.label_text, and locates every
strict / lenient-only / distractor / final-answer form with the scorer's own fold + boundary rule
(same span logic as build_bullet_labels.form_spans, with the fold map computed once per text).

Checks (asserted unless noted, written to data/checks.json):
  * per-sample pass / eligible / FVE / bullet count == baseline/out.json (35,200 samples)
  * sample 0 text == Original text and Best-of-32-chosen sample text == Best of 32 text in
    inputs/multihop_mt_three_settings.jsonl (and their sha256), 1,100 cells each
  * Best of 32 index == argmax FVE over eligible samples (ties -> lower index)
  * every Combine 32 bullet is a bullet of the cell's 32-sample pool
  * readout pass of the three settings == judge (bullet_table readout_pass, Combine project_contract)
  * roles with a strict highlight span == the judge's unit hits (all samples + all readouts)
  * located spans agree with the scorer's boolean matcher for every form
  * totals 106 / 129 / 146, any-of-32 344, pool oracle 356, 4 longest pool bullets 137
  * no bank distractor is matched by a strict form of its own role
Display rules (not asserted, counted in checks.json):
  * a bank lenient alias that a strict form of the same role already matches (e.g. 'SIMULA 67',
    'Emperor Menelik II') is credited by the judge, so it is NOT listed or highlighted as
    "does not count" (kept as roles[].lenient_credited)
  * highlights are painted per whole match: all strict matches, then distractor / lenient / final
    answer matches that do not overlap a higher-priority match (no leftover fragments)
  * a sample or readout that passes although no single bullet names some bridge (a strict form
    matched across a bullet break) gets 'xb': 1
Output text replaces U+FFFD with U+25A1 (same length, so offsets are unchanged).
Offsets in the output are UTF-16 code units (JavaScript string indices).

READ-ONLY on everything outside mh_page/. Usage (CPU allocation): PY -B build_data.py
"""
import collections
import hashlib
import json
import math
import re
import sys
from pathlib import Path

PAGE = Path(__file__).resolve().parent
DATA = PAGE / 'data'
TASK = Path('${OLENS_SCRATCH}/olens-bullet-fve/tasks/multihop_mt')
BASE = TASK / 'baseline'
sys.path.insert(0, str(TASK))
sys.path.insert(0, '${OLENS_REPO_ROOT}/src')
import load  # noqa: E402
from olens_improve.selection import parse_bullets, render_bullets  # noqa: E402

sys.path.insert(0, str(load.ROOT / 'code'))
from bullet_attrib_lib import render_offsets  # noqa: E402

RX = load.RX
SET_KEYS = [('capped_n1-n1', 'orig'), ('best_n_exact-n32', 'best'), ('pooled_greedy_swap-n32', 'comb')]
LAB = {'hit': 'h', 'wrong-specific': 'w', 'miss': 'm'}
KIND_PRI = {'S': 4, 'D': 3, 'L': 2, 'T': 1}  # strict > distractor > lenient-only > final answer
FFFD, BOX = '\ufffd', '\u25a1'
st = collections.Counter()


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def clean(s):
    if s is None:
        return s
    st['fffd_replaced_chars'] += s.count(FFFD)
    return s.replace(FFFD, BOX)


def u16(text):
    """Python code-point offset -> UTF-16 offset table (None when the text is all BMP)."""
    if all(ord(c) < 0x10000 for c in text):
        return None
    out, n = [0], 0
    for c in text:
        n += 2 if ord(c) >= 0x10000 else 1
        out.append(n)
    st['texts_with_non_bmp'] += 1
    return out


def fold_map(raw):
    parts, idx = [], []
    for i, ch in enumerate(raw):
        f = RX.fold(ch)
        parts.append(f)
        idx.extend([i] * len(f))
    folded = ''.join(parts)
    return (folded, idx) if folded == RX.fold(raw) else None


_PAT = {}


def form_pattern(form):
    if form not in _PAT:
        f = RX.fold(form)
        if re.fullmatch(r'\d+', f):
            _PAT[form] = None
        elif RX._CJK_HANGUL.search(form) or not RX._WORDY.fullmatch(f):
            _PAT[form] = ('sub', f)
        else:
            parts = [re.escape(w) for w in re.split(r'[\s\-]+', f) if w]
            _PAT[form] = ('re', re.compile(r'(?<![^\W_])' + r'[\s\-]+'.join(parts) + r'(?![^\W_])'))
    return _PAT[form]


_MATCHER = {}


def matcher(form):
    if form not in _MATCHER:
        _MATCHER[form] = RX.unicode_word_matcher(form)
    return _MATCHER[form]


def highlight(text, forms):
    """forms: list of (form, kind, role). Returns (runs, roles_with_strict_span).
    runs = [[start16, end16, kind, form_index]] non-overlapping, kind priority S > D > L > T."""
    fm = fold_map(text)
    if fm is None:
        st['fold_map_unavailable'] += 1
        return [], None
    folded, idx = fm
    sample = RX.extract_phrase(text)
    found = []  # (priority, start, end, form_index), code-point offsets in `text`
    strict_roles = set()
    for k, (form, kind, role) in enumerate(forms):
        pat = form_pattern(form)
        if pat is None:
            st['numeric_form_skipped'] += 1
            continue
        if pat[0] == 'sub':
            spans, i = [], folded.find(pat[1])
            while i >= 0:
                spans.append((i, i + len(pat[1])))
                i = folded.find(pat[1], i + 1)
        else:
            spans = [(m.start(), m.end()) for m in pat[1].finditer(folded)]
        fires = matcher(form)(sample)
        if bool(spans) != fires:
            st['span_vs_matcher_MISMATCH'] += 1
        if spans and kind == 'S':
            strict_roles.add(role)
        for s, e in spans:
            found.append((KIND_PRI[kind], idx[s], idx[e - 1] + 1, k))
    # Paint whole matches, highest priority first and longest first within a priority. Strict
    # matches are all painted (their union), so nothing that counts is hidden. A lower-priority
    # match (distractor / lenient alias / final answer) that overlaps any higher-priority match is
    # dropped whole, so no leftover fragment (e.g. 'the' of 'the Altair' next to a strict
    # 'Altair 8800') is shown in the lower kind's colour.
    best = [None] * len(text)  # (priority, form_index)
    for pri, a, b, k in sorted(found, key=lambda m: (-m[0], -(m[2] - m[1]), m[1], m[3])):
        if pri != KIND_PRI['S'] and any(best[j] is not None and best[j][0] > pri for j in range(a, b)):
            st['highlight_lower_match_dropped_overlap'] += 1
            continue
        for j in range(a, b):
            if best[j] is None:
                best[j] = (pri, k)
    runs = []
    for j, b in enumerate(best):
        if b is None:
            continue
        if runs and runs[-1][1] == j and runs[-1][3] == b[1]:
            runs[-1][1] = j + 1
        else:
            runs.append([j, j + 1, forms[b[1]][1], b[1]])
    m = u16(text)
    if m:
        for r in runs:
            r[0], r[1] = m[r[0]], m[r[1]]
    return runs, strict_roles


def spans16(text, spans):
    m = u16(text)
    return [[m[s], m[e]] for s, e in spans] if m else [list(x) for x in spans]


def judge(text, units):
    hits = RX.layer_unit_hits([RX.extract_phrase(text)], units)
    return {u.role: bool(hits[u.role]) for u in units if u.required}


def main():
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(load.TOKENIZER, local_files_only=True)

    def ntok(s):
        return len(tok(s, add_special_tokens=False)['input_ids'])

    bank = load.load_bank()
    raw_bank = json.loads(load.BANK.read_text())
    contract = RX.contract_for(raw_bank, str(raw_bank.get('family', load.FAMILY)))
    UNITS = {it['name']: RX.scored_units(it, contract) for it in raw_bank['items']}

    # --- item specs + highlight form lists
    items = {}
    FORMS = {}
    for iid, spec in bank.items():
        forms, roles = [], []
        strict = {u.role: u.all_forms() for u in spec['_units']}
        for k, role in enumerate(spec['required_roles']):
            s = strict[role]
            # A bank lenient alias that one of the role's strict forms already matches (case or accent
            # variant, or an alias that contains a strict form, e.g. 'Emperor Menelik II') IS credited
            # by the judge, so it must not be listed or highlighted as "does not count".
            smatch = [matcher(f) for f in s]
            len_all = [f for f in spec['lenient'].get(role, []) if f not in s]
            len_credited = [f for f in len_all if any(m(RX.extract_phrase(f)) for m in smatch)]
            len_only = [f for f in len_all if f not in len_credited]
            st['lenient_alias_credited_by_strict_form'] += len(len_credited)
            ds = spec['distractors'].get(role, [])
            for f in ds:
                if any(m(RX.extract_phrase(f)) for m in smatch):
                    st['distractor_matched_by_strict_form_MISMATCH'] += 1
            roles.append({'role': role, 'gold': spec['intermediates'][k] if k < len(spec['intermediates']) else None,
                          'strict': s, 'lenient_only': len_only, 'lenient_credited': len_credited, 'distractors': ds,
                          'lenient_dropped': spec['lenient_dropped'].get(role, []),
                          'distractors_removed': spec['distractors_removed_cross_role'].get(role, [])})
            forms += [(f, 'S', role) for f in s] + [(f, 'L', role) for f in len_only] + [(f, 'D', role) for f in ds]
        tforms = strict.get('target', [])
        forms += [(f, 'T', 'target') for f in tforms]
        FORMS[iid] = forms
        items[iid] = {'id': iid, 'sub': spec['subfamily'], 'prompt': spec['prompt'], 'target': spec['target'],
                      'target_alts': spec['target_alts'], 'target_forms': tforms, 'roles': roles,
                      'forms': [[f, k, r] for f, k, r in forms]}

    # --- inputs
    raw = collections.defaultdict(dict)
    for line in open(BASE / 'raw_lines.jsonl'):
        for r in json.loads(line)['records']:
            if r['family'] == 'multihop_mt':
                raw[r['cell_id']][r['sample_index']] = r
    cand = {}
    for line in open(TASK / 'inputs/multihop_mt_candidates.jsonl'):
        o = json.loads(line)
        cand[o['cell_id']] = o
    three = {}
    for line in open(TASK / 'inputs/multihop_mt_three_settings.jsonl'):
        o = json.loads(line)
        three[o['cell_id']] = o
    btab = collections.defaultdict(list)
    for line in open(TASK / 'bullet_table.jsonl'):
        o = json.loads(line)
        btab[(o['cell_id'], o['setting'])].append(o)
    out = json.load(open(BASE / 'out.json'))
    orows = {r['cell_id']: r for r in out['rows']}
    a2 = json.load(open(BASE / 'analysis2.json'))
    comb_pass = {(r['item_id'], r['layer']): r['pass'] for r in json.load(open(
        '${OLENS_DATA_ROOT}/expansion-v1/judgments/pooled_greedy_swap-n32/multihop_mt/'
        'project_contract.json'))['cell_diagnostic']['rows']}

    assert len(raw) == len(cand) == len(three) == len(orows) == 1100
    by_item = collections.defaultdict(dict)
    index_rows = []
    tot = collections.Counter()
    for cid in sorted(raw):
        c, t3, orow = cand[cid], three[cid], orows[cid]
        iid, layer = c['item_id'], c['layer']
        spec, units, forms = bank[iid], UNITS[iid], FORMS[iid]
        req = [u.role for u in units if u.required]
        assert req == spec['required_roles'] == orow['req']
        fve = {tr['sample_index']: tr.get('score') for tr in c['trace32']}
        sel = {s['cond']: s for s in c['selections']}
        best_i = sel['best_n_exact-n32']['samples'][0]

        samples, pool, pool_info = [], {}, {}
        for i in range(32):
            r = raw[cid][i]
            smp = parse_bullets(r['text'], f'{cid}:{i}', i, 4, token_count=ntok, max_output_tokens=256)
            text = render_bullets(smp.bullets)
            rtext, offs = render_offsets([b.text for b in smp.bullets])
            assert rtext == text
            u = judge(text, units)
            eligible = not smp.parsing_uncertain and len(smp.bullets) > 0
            o = orow['samples'][i]
            ok = (o['i'] == i and o['eligible'] == eligible and o['pass'] == all(u.values())
                  and o['fve'] == fve.get(i) and o['n_bullets'] == len(smp.bullets))
            st['sample_vs_out_json_ok' if ok else 'sample_vs_out_json_MISMATCH'] += 1
            runs, sroles = highlight(text, forms)
            if sroles is not None:
                st['sample_strict_spans_eq_judge_ok' if sroles == {k for k, v in u.items() if v}
                   else 'sample_strict_spans_eq_judge_MISMATCH'] += 1
            bl = []
            m16 = spans16(text, offs)
            covered = set()
            for b, (s16, e16) in zip(smp.bullets, m16):
                lab = load.label_text(b.text, spec)
                bl.append([s16, e16, LAB[lab['label']], int(lab['near_hit'])])
                covered |= set(lab['strict_roles'])
                st[f'sample_bullet_label={lab["label"]}'] += 1
            rec = {'i': i, 'el': int(eligible), 'p': int(all(u.values())), 'f': fve.get(i), 'u': [int(u[k]) for k in req],
                   't': clean(text), 'b': bl, 'h': runs}
            # judge quirk: the whole judged text passes, but no bullet on its own names some bridge
            # (a strict form matches across a bullet break, e.g. 'the\n- Great Dying')
            if rec['p'] and not set(req) <= covered:
                rec['xb'] = 1
                st['sample_pass_only_across_bullet_break'] += 1
            if not rec['p'] and set(req) <= covered:
                st['sample_bullets_cover_all_bridges_but_text_fails'] += 1
            flags = [f for f in smp.flags]
            if flags:
                rec['fl'] = flags
            if r['text'] != text:
                rec['raw'] = clean(r['text'])
                st['samples_raw_differs_from_judged'] += 1
            if r.get('truncated'):
                rec['gen_trunc'] = 1
            samples.append(rec)
            if i == 0:
                assert text == t3['settings']['capped_n1-n1']['text'], cid
                assert sha(text) == t3['settings']['capped_n1-n1']['text_sha256']
                st['original_text_eq_sample0'] += 1
            if i == best_i:
                assert text == t3['settings']['best_n_exact-n32']['text'], cid
                assert sha(text) == t3['settings']['best_n_exact-n32']['text_sha256']
                st['best32_text_eq_chosen_sample'] += 1
            if not smp.parsing_uncertain:
                for b in smp.bullets:
                    if b.text not in pool:
                        pool[b.text] = judge('- ' + b.text, units)
                        pool_info[b.text] = {'chars': len(b.text.strip()), 'freq': 0, 'first': (i, b.position)}
                    pool_info[b.text]['freq'] += 1
        elig = [s for s in samples if s['el'] and s['f'] is not None]
        argmax = max(elig, key=lambda s: (s['f'], -s['i']))
        assert argmax['i'] == best_i, cid
        # pool checks vs out.json
        assert [pool_info[t]['chars'] for t in pool] == [p['chars'] for p in orow['pool']]
        assert [[r_ for r_ in req if pool[t][r_]] for t in pool] == [p['hits'] for p in orow['pool']]
        # 4 longest pool bullets (no FVE), as analysis2.topk_baseline
        order = sorted(pool, key=lambda t: (-pool_info[t]['chars'], pool_info[t]['first']))[:4]
        long_pass = all(any(pool[t][r_] for t in order) for r_ in req) if pool else False
        long4 = []
        for t in order:
            runs, _ = highlight(t, forms)
            long4.append({'t': clean(t), 'h': runs, 'hits': [r_ for r_ in req if pool[t][r_]],
                          'chars': pool_info[t]['chars'], 'from': list(pool_info[t]['first']),
                          'lab': LAB[load.label_text(t, spec)['label']]})

        # three readouts
        reads = {}
        for cond, key in SET_KEYS:
            s = t3['settings'][cond]
            text, offs = render_offsets([a['text'] for a in s['atoms']])
            assert text == s['text']
            rows = sorted(btab[(cid, cond)], key=lambda x: x['index'])
            assert len(rows) == len(s['atoms'])
            rpass = rows[0]['readout_pass']
            if key == 'comb':
                assert rpass == comb_pass[(iid, layer)]
                for a in s['atoms']:
                    st['comb_bullet_in_pool_ok' if a['text'] in pool else 'comb_bullet_in_pool_MISS'] += 1
            u = judge(text, units)
            assert all(u.values()) == rpass, (cid, cond)
            runs, sroles = highlight(text, forms)
            if sroles is not None:
                st['readout_strict_spans_eq_judge_ok' if sroles == {k for k, v in u.items() if v}
                   else 'readout_strict_spans_eq_judge_MISMATCH'] += 1
            m16 = spans16(text, offs)
            bl = []
            for b, a, (s16, e16) in zip(rows, s['atoms'], m16):
                assert b['text'] == a['text']
                bl.append({'s': s16, 'e': e16, 'lab': LAB[b['label']], 'near': int(b['near_hit']),
                           'share': b['shapley_share'], 'solo': b['solo_fve'], 'drop': b['loo_drop'],
                           'coef': b['coefficient'], 'src': a['sample_index'], 'trunc': int(b['truncated']),
                           'vis': int(b['hit_visible_to_vector']), 'cut': int(bool(b['gold_cut_at_end'])),
                           'dup': int(bool(b['dup']))})
            reads[key] = {'t': clean(text), 'f': s['fve'], 'p': int(rpass), 'u': [int(u[k]) for k in req],
                          'b': bl, 'h': runs}
            rcov = set()
            for a in s['atoms']:
                rcov |= set(load.label_text(a['text'], spec)['strict_roles'])
            if rpass and not set(req) <= rcov:
                reads[key]['xb'] = 1
                st[f'readout_pass_only_across_bullet_break[{key}]'] += 1
            tot[key] += rpass
        orig_p, best_p, comb_p = reads['orig']['p'], reads['best']['p'], reads['comb']['p']
        assert orig_p == orow['orig_pass'] and best_p == orow['best32_pass']
        tot['any'] += orow['any_pass']
        tot['pool_oracle'] += orow['pool_oracle']
        tot['long4'] += long_pass
        cell = {'cell_id': cid, 'item': iid, 'layer': layer, 'pos': c['position'], 'split': c['split'],
                'token': clean(t3['token']), 'best_i': best_i, 'req': req,
                'read': reads, 'long4': {'p': int(long_pass), 'b': long4}, 'samples': samples,
                'stats': {'n_el': orow['n_eligible'], 'n_pass': orow['n_pass_samples'], 'rand1': orow['rand1_pass'],
                          'rand4': orow['rand4_pool_pass'], 'pool': orow['pool_size'],
                          'pool_hit': orow['pool_hit_bullets'], 'pool_oracle': int(orow['pool_oracle']),
                          'any': int(orow['any_pass'])}}
        by_item[iid][layer] = cell
        fv = [s['f'] for s in elig]
        index_rows.append({'id': cid, 'it': iid, 'L': layer, 'sub': spec['subfamily'], 'sp': c['split'],
                           'o': orig_p, 'b': best_p, 'c': comb_p, 'a': int(orow['any_pass']), 'l': int(long_pass),
                           'np': orow['n_pass_samples'], 'ne': orow['n_eligible'],
                           'fo': reads['orig']['f'], 'fb': reads['best']['f'], 'fc': reads['comb']['f']})

    assert tot['orig'] == 106 and tot['best'] == 129 and tot['comb'] == 146, tot
    assert tot['any'] == 344 and tot['pool_oracle'] == 356 and tot['long4'] == round(a2['long4']['cells']), tot
    assert not any('MISMATCH' in k or k.endswith('_MISS') for k in st), dict(st)

    # --- write chunks (10 items per file, sorted item ids)
    DATA.mkdir(parents=True, exist_ok=True)
    order = sorted(by_item)
    chunk_of = {}
    files = []
    for k in range(0, len(order), 10):
        name = f'items_{k // 10:02d}.json'
        part = {iid: {'spec': items[iid], 'cells': {str(L): by_item[iid][L] for L in sorted(by_item[iid])}}
                for iid in order[k:k + 10]}
        s = json.dumps(part, ensure_ascii=False, separators=(',', ':'))
        assert FFFD not in s
        (DATA / name).write_text(s)
        files.append((name, len(s.encode())))
        for iid in order[k:k + 10]:
            chunk_of[iid] = name
    idx = {'analysis2': a2, 'out_summary': out['summary'],
           'items': [{'id': iid, 'sub': items[iid]['sub'], 'chunk': chunk_of[iid],
                      'gold': [r['gold'] for r in items[iid]['roles']], 'target': items[iid]['target'],
                      'prompt': items[iid]['prompt']} for iid in order],
           'cells': index_rows,
           'checks': {k: v for k, v in sorted(st.items())}, 'totals': dict(tot)}
    s = json.dumps(idx, ensure_ascii=False, separators=(',', ':'))
    assert FFFD not in s
    (DATA / 'index.json').write_text(s)
    files.append(('index.json', len(s.encode())))
    json.dump({'checks': dict(sorted(st.items())), 'totals': dict(tot), 'files': files},
              open(DATA / 'checks.json', 'w'), indent=1)
    print(json.dumps({'checks': dict(sorted(st.items())), 'totals': dict(tot), 'files': files,
                      'total_mb': round(sum(b for _, b in files) / 1e6, 2)}, indent=1))


if __name__ == '__main__':
    main()
