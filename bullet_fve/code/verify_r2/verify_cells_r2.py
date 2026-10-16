#!/usr/bin/env python3
"""Round-2 independent verifier: re-derive every page field for a few cells from the ORIGINAL sources
(full-grid selections.jsonl, activations.safetensors + manifest, whitener moments, raw AR vector tensors,
judge results.json / cells.jsonl, cached-v2 raw_n1 text, benchmark items.json, tokenizer) with an
independent numpy/scipy implementation, then compare to page/data/index.json + items/<id>.json.

Usage: python -B verify_cells_r2.py OUT.json [--n 10] [--seed S] [--extra k1 k2 ...]
Read-only on everything except OUT.json.
"""
import argparse, collections, hashlib, itertools, json, math, random, re, sys, time
from pathlib import Path
import numpy as np
from scipy.optimize import nnls

T0 = time.time()
ROOT = Path('${OLENS_SCRATCH}/olens-bullet-fve')
PAGE = ROOT / 'page/data'
SEL = {'development': '${OLENS_DATA_ROOT}/selections/development-full-grid-v4/merged/selections.jsonl',
       'validation': '${OLENS_DATA_ROOT}/selections/validation-full-grid-v1/merged/selections.jsonl',
       'test': '${OLENS_DATA_ROOT}/selections/test-full-grid-v1/merged/selections.jsonl'}
ACTS = '${OLENS_COMPUTE_ROOT}/activations/core-v1/activations.safetensors'
MANIFEST = '${OLENS_COMPUTE_ROOT}/activations/core-v1/fresh_manifest_v2.json'
WH = ('${OLENS_COMPUTE_ROOT}/cache/huggingface/hub/datasets--agu18dec--local-workspace/snapshots/'
      '5653a7fead43ecbd87e3b6d2a2990a98b32843ca/ckpts/ar/ptag/whiteners/whitening_iolens_pooled_L{}.safetensors')
JUD = '${OLENS_DATA_ROOT}/expansion-v1/judgments/{}/hallucination'
CACHED = '${OLENS_DATA_ROOT}/expansion-v1/selections/cached-v2/hallucination.jsonl'
BANK = '${OLENS_SOURCE_ROOT}/scratch/repos/workspace-bench-v2/evals/hallucination/items.json'
TOK = ('${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/snapshots/'
       '6a9e13bd6fc8f0983b9b99948120bc37f49c13e9')
VINDEX = ROOT / 'inputs/hall_vector_index.json'
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
MN = {'capped_n1-n1': ('capped_n1', 1), 'best_n_exact-n32': ('best_n_exact', 32),
      'pooled_greedy_swap-n32': ('pooled_greedy_swap', 32)}
CODES = ['consistent', 'hallucinated', 'off_topic', 'generic', 'empty']

# ---------------------------------------------------------------- judge rules (re-typed from wsbench judge.py)
_WS = re.compile(r'\s+')
_Q = str.maketrans({'“': '"', '”': '"', '‘': "'", '’': "'", '«': '"', '»': '"'})


def nws(s):
    return _WS.sub(' ', s.translate(_Q)).strip().lower()


def vq(q, hay):
    q = nws(q)
    return len(q) >= 3 and any(q in nws(h) for h in hay)


def norm_map(text):
    """normalised string + map from each normalised char to source code-point index (own implementation)."""
    out, idx = [], []
    prev_space = True  # strip leading
    for i, ch in enumerate(text):
        ch = ch.translate(_Q)
        if ch.isspace() or _WS.match(ch):
            if not prev_space:
                out.append(' '); idx.append(i)
            prev_space = True
            continue
        low = ch.lower()
        for c in low:
            out.append(c); idx.append(i)
        prev_space = False
    while out and out[-1] == ' ':
        out.pop(); idx.pop()
    return ''.join(out), idx


def occurrences(text, span):
    """All occurrences under normalisation (superset of exact), plus exact ones; code points."""
    exact = []
    if span:
        i = text.find(span)
        while i != -1:
            exact.append((i, i + len(span))); i = text.find(span, i + 1)
    q = nws(span or '')
    normh = []
    if len(q) >= 3:
        norm, idx = norm_map(text)
        j = norm.find(q)
        while j != -1:
            normh.append((idx[j], idx[j + len(q) - 1] + 1)); j = norm.find(q, j + 1)
    return exact, normh


def u16map(text):
    m = [0]
    for ch in text:
        m.append(m[-1] + (2 if ord(ch) > 0xFFFF else 1))
    return m


# ---------------------------------------------------------------- numerics
def st_header(path):
    with open(path, 'rb') as f:
        n = int.from_bytes(f.read(8), 'little'); h = json.loads(f.read(n))
    return n, h


def st_row(path, key, row):
    n, h = st_header(path)
    e = h[key]; shape = e['shape']; assert e['dtype'] == 'F32'
    mm = np.memmap(path, dtype='<f4', mode='r', offset=8 + n + e['data_offsets'][0], shape=tuple(shape))
    return np.array(mm[row])


def st_full(path, key):
    n, h = st_header(path)
    e = h[key]; assert e['dtype'] == 'F32'
    mm = np.memmap(path, dtype='<f4', mode='r', offset=8 + n + e['data_offsets'][0], shape=tuple(e['shape']))
    return np.array(mm)


_WCACHE = {}


def whitener(layer):
    if layer not in _WCACHE:
        mu = st_full(WH.format(layer), 'mu'); cov = st_full(WH.format(layer), 'cov').astype(np.float64)
        cov = (cov + cov.T) * 0.5
        ridge = max(0.1 * cov.diagonal().mean(), 1e-12)
        ev, V = np.linalg.eigh(cov)
        sc = 1.0 / np.sqrt(np.clip(ev, 0, None) + ridge)
        W = ((V * sc[None, :]) @ V.T).astype(np.float32)
        _WCACHE[layer] = (mu.astype(np.float32), W)
    return _WCACHE[layer]


def whiten(x, layer):
    mu, W = whitener(layer)
    return ((x.astype(np.float32) - mu) @ W.T).astype(np.float32)


def fve_of(A, t):
    """A: k x d unit rows (float64), t: d (float64). Returns (coef, fve)."""
    if A.shape[0] == 0:
        return np.zeros(0), 0.0
    c, r = nnls(A.T, t)
    return c, 1.0 - r ** 2 / max(float(t @ t), 1e-12)


def bullet_scores(A, t):
    k = A.shape[0]
    v = {}
    for r in range(k + 1):
        for S in itertools.combinations(range(k), r):
            v[S] = fve_of(A[list(S)], t)[1] if S else 0.0
    full = tuple(range(k))
    joint = v[full]
    coef = fve_of(A, t)[0]
    solo = [v[(i,)] for i in range(k)]
    drop = [joint - v[tuple(j for j in full if j != i)] for i in range(k)]
    shap = []
    for i in range(k):
        others = [j for j in full if j != i]
        s = 0.0
        for r in range(len(others) + 1):
            w = math.factorial(r) * math.factorial(k - r - 1) / math.factorial(k)
            for S in itertools.combinations(others, r):
                s += w * (v[tuple(sorted(S + (i,)))] - v[S])
        shap.append(s)
    return joint, coef, solo, drop, shap


# ---------------------------------------------------------------- compare helpers
FAILS = []
NCHECK = collections.Counter()


def chk(ok, where, msg):
    NCHECK['total'] += 1
    if not ok:
        FAILS.append(f'{where}: {msg}')


def close(a, b, tol):
    if a is None or b is None:
        return a is None and b is None
    return abs(float(a) - float(b)) <= tol


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--n', type=int, default=10)
    ap.add_argument('--seed', type=int, default=777015)
    ap.add_argument('--extra', nargs='*', default=[])
    args = ap.parse_args()

    index = json.load(open(PAGE / 'index.json'))
    cells_idx = {c['k']: c for c in index['cells']}
    rng = random.Random(args.seed)
    keys = rng.sample(sorted(cells_idx), args.n) + [k for k in args.extra if k in cells_idx]
    print('cells:', keys, flush=True)
    want = {}
    for k in keys:
        m = re.match(r'^([a-z0-9-]+)\.L(\d+)\.p(\d+)$', k)
        it, L, p = m[1], int(m[2]), int(m[3])
        want[f'hallucination|{it}|L{L:02d}|p{p:05d}'] = k

    # ---- original selections (stream)
    sel = {}
    for split, path in SEL.items():
        with open(path, 'rb') as fh:
            for line in fh:
                if not line.startswith(b'{"cell_id": "hallucination|'):
                    continue
                cid = line[13:line.index(b'"', 13)].decode()
                if cid in want:
                    sel[cid] = json.loads(line)
    print('selections found', len(sel), 'of', len(want), f'{time.time()-T0:.0f}s', flush=True)
    assert len(sel) == len(want)

    # ---- manifest -> activation rows
    man = json.load(open(MANIFEST))['cells']
    by_sha = {}
    for i, c in enumerate(man):
        if c.get('family') == 'hallucination':
            by_sha[c['activation_sha256']] = (i, c)
    del man
    bank = {it['id']: it for it in json.load(open(BANK))['items']}
    # judge
    J = {}
    for sid in SIDS + ['raw_n1-n1']:
        res = json.load(open(JUD.format(sid) + '/results.json'))
        rows = {r['key']: r for r in res['rows']}
        s1, s2 = {}, {}
        with open(JUD.format(sid) + '/cells.jsonl') as fh:
            for line in fh:
                r = json.loads(line)
                if r.get('result') is None:
                    continue
                (s2 if r['key'].endswith(':V') else s1)[r['key'].removesuffix(':V')] = r
        J[sid] = (rows, s1, s2)
    raw_ref = {}
    with open(CACHED) as fh:
        for line in fh:
            r = json.loads(line)
            cid = r['cell_id']
            if cid in want:
                for s in r['selections']:
                    if (s['method'], s['n']) == ('raw_n1', 1):
                        raw_ref[cid] = s
                    for sid in SIDS:
                        if (s['method'], s['n']) == MN[sid]:
                            raw_ref.setdefault(cid + '#' + sid, s)
    vindex = json.load(open(VINDEX))
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(TOK, local_files_only=True)
    print('loaded inputs', f'{time.time()-T0:.0f}s', flush=True)
    idx_cache = {}

    report = {}
    for cid in sorted(want, key=lambda c: int(c.split('|L')[1][:2])):
        k = want[cid]
        line = sel[cid]
        it, L, p = line['item_id'], line['layer'], line['position']
        split = line['split']
        W = f'{k}'
        ic = cells_idx[k]
        page_item = json.load(open(PAGE / 'items' / f'{it}.json'))
        pc = page_item['cells'][k]
        # ---- item / site
        b = bank[it]
        chk(page_item['item']['prompt'] == b['prompt'] and page_item['item']['response'] == b['response'], W, 'item text')
        chk(page_item['item']['split'] == split and index['items'][ic['i']]['id'] == it and index['items'][ic['i']]['split'] == split, W, 'split / item index')
        site = {s['pos']: s for s in b['sites']}[p]
        rm = u16map(b['response'])
        chk(pc['char'] == rm[site['char']] and pc['site_kind'] == site['kind'] and ic['sk'] == site['kind'] and ic['st'] == site['token'], W, f'site char/kind/token page {pc["char"]} vs {rm[site["char"]]}')
        chk(b['response'][:site['char']].endswith(site['token']), W, 'site token at char')
        chk(ic['L'] == L and ic['p'] == p and pc['layer'] == L and pc['pos'] == p, W, 'layer/pos')
        # ---- target
        ai, mc = by_sha[line['activation_sha256']]
        arow = mc['activation_row']
        tgt = st_row(ACTS, 'resid', arow)
        chk(hashlib.sha256(tgt.astype('<f4').tobytes()).hexdigest() == line['activation_sha256'], W, 'activation sha')
        t = whiten(tgt[None, :], L)[0].astype(np.float64)
        rep = {'split': split, 'layer': L, 'settings': {}}
        for j, sid in enumerate(SIDS):
            WS = f'{k} {sid}'
            m, n = MN[sid]
            s = [x for x in line['selections'] if (x['method'], x['n']) == (m, n)]
            assert len(s) == 1
            s = s[0]
            ps = pc['settings'][sid]
            ics = ic['s'][j]
            text = s['text']
            chk(ps['text'] == text, WS, 'text')
            chk(raw_ref[cid + '#' + sid]['text'] == text, WS, 'cached-v2 text == full-grid text')
            atoms = s['atoms']
            # render + bullet offsets
            out, spans = '', []
            for a in atoms:
                if out and not out.endswith('\n'):
                    out += '\n'
                out += '- '
                spans.append((len(out), len(out) + len(a['text'].strip())))
                out += a['text']
            chk(out == text, WS, 'render')
            um = u16map(text)
            pb = ps['bullets']
            chk(len(pb) == len(atoms) == ics['n'], WS, f'n bullets page {len(pb)} idx {ics["n"]} atoms {len(atoms)}')
            sc_end = []
            for bi, (a, (cs, ce)) in enumerate(zip(atoms, spans)):
                assert text[cs:ce] == a['scored_text']
                if a['truncated']:
                    dec = tok.decode(a['scored_token_ids'])
                    st = a['scored_text']
                    n_ = 0
                    while n_ < min(len(dec), len(st)) and dec[n_] == st[n_]:
                        n_ += 1
                    se = cs + n_
                else:
                    se = ce
                full_ids = tok(a['scored_text'], add_special_tokens=False)['input_ids']
                chk(bool(a['truncated']) == (len(full_ids) > 32), WS, f'b{bi} truncated flag vs tokenizer ({len(full_ids)})')
                sc_end.append(se)
                pbb = pb[bi]
                chk(pbb['start'] == um[cs] and pbb['end'] == um[ce] and pbb['scored_end'] == um[se], WS,
                    f'b{bi} offsets page {pbb["start"]},{pbb["end"]},{pbb["scored_end"]} mine {um[cs]},{um[ce]},{um[se]}')
                chk(pbb['truncated'] == bool(a['truncated']) and pbb['sample_index'] == a['sample_index'], WS, f'b{bi} truncated/sample')
            # ---- vectors (verify locator against the tensor's own index json)
            vecs = []
            for a in atoms:
                tp, row = vindex[split][a['cache_key']]
                ijp = tp.replace('.safetensors', '.index.json')
                if ijp not in idx_cache:
                    ij = json.load(open(ijp))
                    assert ij['tensor_path'] == tp, (ijp, ij['tensor_path'])
                    idx_cache[ijp] = {v['cache_key']: (v['row'], v['layer'], v['scored_token_ids']) for v in ij['vectors']}
                r_, l_, ids_ = idx_cache[ijp][a['cache_key']]
                chk(r_ == row and l_ == L and ids_ == a['scored_token_ids'], WS, 'vector locator/index mismatch')
                v = st_row(tp, 'vectors', row)
                w = whiten(v[None, :], L)[0]
                w = w / (np.linalg.norm(w) + 1e-9)
                vecs.append(w.astype(np.float64))
            A = np.array(vecs) if vecs else np.zeros((0, t.shape[0]))
            joint, coef, solo, drop, shap = bullet_scores(A, t)
            saved = s['fits']['exact']['fve']
            share = [x / joint if joint > 0 else None for x in shap]
            chk(abs(joint - saved) < 2e-6, WS, f'my joint {joint:.8f} vs saved {saved:.8f}')
            chk(close(ps['fve'], saved, 0.51e-5) and close(ics['f'], saved, 0.51e-5), WS, f'fve page {ps["fve"]} idx {ics["f"]} saved {saved}')
            chk(close(ps['fve_recomputed'], joint, 0.51e-5 + 2e-6), WS, f'fve_recomputed {ps["fve_recomputed"]} mine {joint}')
            if atoms:
                chk(abs(sum(shap) - joint) < 1e-9, WS, 'efficiency')
            keys_ = [a['cache_key'] for a in atoms]
            for bi in range(len(atoms)):
                pbb = pb[bi]
                dup = keys_.count(keys_[bi]) > 1 or [a['scored_text'] for a in atoms].count(atoms[bi]['scored_text']) > 1
                chk(pbb['dup'] == dup, WS, f'b{bi} dup page {pbb["dup"]} mine {dup}')
                if not dup:
                    chk(close(pbb['coef'], s['fits']['exact']['coefficients'][bi], 0.51e-4) and abs(coef[bi] - s['fits']['exact']['coefficients'][bi]) < 1e-3 * max(1, abs(coef[bi])), WS,
                        f'b{bi} coef page {pbb["coef"]} saved {s["fits"]["exact"]["coefficients"][bi]} mine {coef[bi]}')
                chk(close(pbb['solo'], solo[bi], 0.51e-5 + 2e-6), WS, f'b{bi} solo page {pbb["solo"]} mine {solo[bi]:.7f}')
                chk(close(pbb['drop'], drop[bi], 0.51e-5 + 2e-6), WS, f'b{bi} drop page {pbb["drop"]} mine {drop[bi]:.7f}')
                chk(close(pbb['shap'], shap[bi], 1.01e-5 + 2e-6), WS, f'b{bi} shap page {pbb["shap"]} mine {shap[bi]:.7f}')
                chk(close(pbb['shap_share'], share[bi], 1.01e-5 + 1e-5), WS, f'b{bi} share page {pbb["shap_share"]} mine {share[bi]}')
                chk(close(ics['sh'][bi], shap[bi], 1.01e-5 + 2e-6), WS, f'b{bi} idx sh {ics["sh"][bi]} mine {shap[bi]:.7f}')
                chk(close(ics['ss'][bi], share[bi], 1.01e-4 + 1e-5), WS, f'b{bi} idx ss {ics["ss"][bi]} mine {share[bi]}')
                chk(close(ics['so'][bi], solo[bi], 0.51e-4 + 2e-6), WS, f'b{bi} idx so {ics["so"][bi]} mine {solo[bi]:.7f}')
                chk(close(ics['dr'][bi], drop[bi], 0.51e-4 + 2e-6), WS, f'b{bi} idx dr {ics["dr"][bi]} mine {drop[bi]:.7f}')
            # ---- judge
            rows, s1, s2 = J[sid]
            jk = f'{it}__L{L:03d}__p{p}'
            row = rows.get(jk)
            if row is None:
                chk(not text.strip(), WS, 'missing judge row for non-empty readout')
                chk(ps['label'] is None and ics['c'] == 4 and ps['spans'] == [] and ps['claims'] == [], WS, 'empty readout fields')
                lab = None
            else:
                chk(row['samples'][0] == text and s1[jk]['meta']['samples'][0] == text, WS, 'judged text')
                raw1 = s1[jk]['result']['samples'][0]
                raw2 = s2[jk]['result']['samples'][0]
                kind = str(raw1.get('kind') or '').strip().lower()
                kind = kind if kind in ('specific', 'generic', 'empty') else 'specific'
                wrong, off, myspans = [], [], []
                for sp in raw1.get('spans') or []:
                    st_ = str(sp.get('text') or '')
                    ok = vq(st_, [text])
                    typ = 'off_topic' if str(sp.get('type') or '').strip().lower() == 'off_topic' else 'wrong'
                    if ok:
                        (off if typ == 'off_topic' else wrong).append(st_)
                    ex, nh = occurrences(text, st_)
                    myspans.append((st_, typ, ok, ex, nh, sp.get('why')))
                lab = 'hallucinated' if wrong else ('generic' if kind in ('generic', 'empty') else ('off_topic' if off else 'consistent'))
                chk(lab == row['verdict'][0]['class'] == ps['label'] and CODES[ics['c']] == lab, WS, f'label mine {lab} results {row["verdict"][0]["class"]} page {ps["label"]} idx {CODES[ics["c"]]}')
                chk(ics['w'] == len(wrong) and ics['o'] == len(off), WS, f'w/o counts idx {ics["w"]},{ics["o"]} mine {len(wrong)},{len(off)}')
                chk(ps['judge_kind'] == raw1.get('kind') or ps['judge_kind'] == kind, WS, f'judge_kind {ps["judge_kind"]} raw {raw1.get("kind")}')
                chk(ps['rationale'] == raw1.get('rationale') and ps['verify_rationale'] == raw2.get('rationale'), WS, 'rationales')
                chk(len(ps['spans']) == len(myspans), WS, f'n spans page {len(ps["spans"])} mine {len(myspans)}')
                # bullet labels
                cont = [(sp_[0], sp_[1]) for sp_ in spans]
                def ov(a, e):
                    return [bi for bi, (bs, be) in enumerate(cont) if a < be and e > bs]
                mybl = []
                for bi in range(len(atoms)):
                    if lab in ('hallucinated', 'consistent', 'off_topic'):
                        hw = any(ok and typ == 'wrong' and bi in ov(a, e) for (_, typ, ok, ex, nh, _w) in myspans for a, e in nh + ex)
                        ho = any(ok and typ == 'off_topic' and bi in ov(a, e) for (_, typ, ok, ex, nh, _w) in myspans for a, e in nh + ex)
                        mybl.append('w' if hw else ('o' if ho else 'c'))
                    else:
                        mybl.append('x')
                chk(mybl == [x['label'] for x in pb] == ics['bl'], WS, f'bullet labels mine {mybl} page {[x["label"] for x in pb]} idx {ics["bl"]}')
                for si, ((st_, typ, ok, ex, nh, why), pspan) in enumerate(zip(myspans, ps['spans'])):
                    chk(pspan['text'] == st_ and pspan['type'] == typ and pspan['verified'] == ok and pspan['why'] == why, WS, f'span {si} text/type/verified/why')
                    poff = [tuple(o) for o in pspan['offsets']]
                    ex16 = [(um[a], um[e]) for a, e in ex]
                    allocc = sorted(set(ex) | set(nh))
                    chk(all(o in poff for o in ex16), WS, f'span {si} exact offsets {ex16} not all in page {poff}')
                    # every normalised occurrence is represented (overlapped) by some page offset
                    chk(all(any(um[a] < pe and um[e] > psn for psn, pe in poff) for a, e in nh), WS, f'span {si} normalised occurrence missing; mine {nh} page {poff}')
                    chk(len(poff) == len(nh) if nh else len(poff) == len(ex), WS, f'span {si} n occurrences page {len(poff)} mine norm {len(nh)} exact {len(ex)}')
                    # bullets + in_unscored computed from page offsets mapped back via my u16 map
                    inv = {v: i for i, v in enumerate(um)}
                    cp = [(inv[a], inv[e]) for a, e in poff]
                    myb = sorted({bi for a, e in cp for bi in ov(a, e)})
                    chk(pspan.get('bullets') == myb, WS, f'span {si} bullets page {pspan.get("bullets")} mine {myb}')
                    uns = [bool(ov(a, e)) and all(max(a, cont[bi][0]) >= sc_end[bi] for bi in ov(a, e)) for a, e in cp]
                    myun = bool(uns) and all(uns)
                    chk(pspan.get('in_unscored') == myun, WS, f'span {si} in_unscored page {pspan.get("in_unscored")} mine {myun}')
                # claims
                wn = [nws(x) for x in wrong]
                tally = dict(false=len(wrong), true=0, unverifiable=0, disputed=0, off_topic=0, n_unverified=0)
                mycl = []
                for cl in raw2.get('claims') or []:
                    q = str(cl.get('quote') or '')
                    if not q or not vq(q, [text]):
                        ca = 'n_unverified'; tally['n_unverified'] += 1
                    elif any(x in nws(q) or nws(q) in x for x in wn):
                        ca = 'skipped_overlaps_false'
                    else:
                        st_ = str(cl.get('status') or '').strip().lower()
                        if st_ == 'true':
                            ca = 'true'; tally['true'] += 1
                        elif st_ == 'off_topic':
                            ca = 'off_topic'; tally['off_topic'] += 1
                        elif st_ == 'disputed':
                            ca = 'disputed'; tally['disputed'] += 1; tally['unverifiable'] += 1
                        else:
                            ca = 'unverifiable'; tally['unverifiable'] += 1
                    mycl.append((q, cl.get('status'), ca, cl.get('why')))
                chk(tally == row['verdict'][0]['claims'] == ps['claim_tally'], WS, f'claim tally mine {tally} results {row["verdict"][0]["claims"]} page {ps["claim_tally"]}')
                chk(len(mycl) == len(ps['claims']), WS, 'n claims')
                for ci_, (mc_, pcl) in enumerate(zip(mycl, ps['claims'])):
                    chk((pcl['quote'], pcl['status'], pcl['counted_as'], pcl['why']) == mc_, WS, f'claim {ci_} fields')
                    ex, nh = occurrences(text, mc_[0])
                    poff = [tuple(o) for o in pcl['offsets']]
                    chk(all((um[a], um[e]) in poff for a, e in ex), WS, f'claim {ci_} offsets')
            # trace
            if sid == 'best_n_exact-n32':
                scores = [None] * 32
                for tr in s['trace']:
                    scores[int(tr['sample_id'].rsplit(':', 1)[1])] = tr.get('score')
                pt = ps['trace']
                chk(all((a is None and b is None) or (a is not None and b is not None and abs(a - b) <= 0.51e-5) for a, b in zip(pt['scores'], scores)), WS, 'trace scores')
                ch = sorted({a['sample_index'] for a in atoms})
                chk(pt['chosen_sample'] == (ch[0] if ch else None), WS, 'chosen sample')
                if ch:
                    best = max(x for x in scores if x is not None)
                    chk(abs(scores[ch[0]] - saved) < 1e-9 and abs(best - saved) < 1e-9, WS, f'chosen sample score {scores[ch[0]]} best {best} saved {saved}')
            rep['settings'][sid] = {'label': lab, 'joint_saved': saved, 'joint_mine': joint,
                                    'bullets': [{'label': pb[bi]['label'], 'solo': solo[bi], 'drop': drop[bi], 'shap': shap[bi],
                                                 'share': share[bi], 'coef': float(coef[bi]), 'truncated': bool(atoms[bi]['truncated'])}
                                                for bi in range(len(atoms))]}
        # reference
        rs = raw_ref[cid]
        pr = pc['settings'].get('raw_n1-n1')
        rows, s1, s2 = J['raw_n1-n1']
        jk = f'{it}__L{L:03d}__p{p}'
        rrow = rows.get(jk)
        rl = rrow['verdict'][0]['class'] if rrow else None
        chk(pr is not None and pr['text'] == rs['text'] and pr['label'] == rl and ic['r'] == (CODES.index(rl) if rl else 4), k + ' ref', f'reference page {pr and pr["label"]} idx {ic["r"]} mine {rl}')
        if rrow:
            chk(rrow['samples'][0] == rs['text'], k + ' ref', 'reference judged text')
        report[k] = rep
        print('done', k, f'{time.time()-T0:.0f}s', 'fails so far', len(FAILS), flush=True)

    res = {'cells': keys, 'n_checks': NCHECK['total'], 'n_fail': len(FAILS), 'fails': FAILS, 'report': report,
           'wall_s': round(time.time() - T0, 1)}
    json.dump(res, open(args.out, 'w'), indent=1)
    print('checks', NCHECK['total'], 'fails', len(FAILS))
    for f in FAILS[:80]:
        print('FAIL', f)


if __name__ == '__main__':
    main()
