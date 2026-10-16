"""Skeptic pass for um: my own tables from the raw select / metric / label / judge files (independent of analysis.py).

Sources (read-only):
  data/select/um_three_settings.jsonl   cells + the 3 selected readouts (atoms -> pool phrase ids)
  data/select/um_pool.jsonl             every pool bullet (first 4 per sample x 32) with solo FVE
  data/metrics/um_bullet_metrics.L*.jsonl  per-bullet solo / Shapley share / LOO drop of selected readouts
  data/labels/um_text_labels.jsonl      lexicon v2 labels on the full text (key = sha(item \\0 text)[:20])
  data/judge/um/<setting>/um_cell_rows.jsonl  per-readout judge pick / basis
  WSB items.json + build_options        gold, distractors, prompt
The lexicon (code/um_lexicon.py) is the instrument: it is re-run only on the 32-token AR window of truncated bullets.
Echo flags, frame keys, surface features and every statistic are my own code. analysis.py is not imported.
Writes analysis/um/skeptic/cache/sk_tables.pkl
"""
import collections
import hashlib
import json
import pickle
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
sys.path.insert(0, str(NT / 'code'))
import ntcommon as C  # noqa: E402

C.setup_paths()
import um_lexicon as LEX  # noqa: E402

D = NT / 'data'
OUT = NT / 'analysis/um/skeptic/cache'
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')
CJKC = re.compile(r'[぀-ヿ㐀-䶿一-鿿가-힯]')
LIST_OPEN = re.compile(r'^\s*(?:[-*]\s*)?\d{1,2}\s*[.:)：]')
MARK_OPEN = re.compile(r'^\s*(?:\*\*|#+|<think>|</?\w+>|/|\(|（|-\s|:)')
WORDS = re.compile(r"[a-z][a-z'’]+")
STOPW = set("""a an the and or but if of to in on at by for with from as is are was were be been being has have had do does
did not no nor so than that this these those there their they them he she his her him it its we our you your i me my who
which what when where why how all any each both more most other some such only own same too very can will just should now
into over under after before while about also because here could would like make want need please help know think really
""".split())


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def fold(s):
    return ''.join(ch for ch in unicodedata.normalize('NFKD', s.lower()) if not unicodedata.combining(ch))


def tkey(item_id, text):
    return hashlib.sha256(f'{item_id}\x00{text}'.encode()).hexdigest()[:20]


class Prompt:
    def __init__(self, text):
        self.f = ' ' + re.sub(r"[^a-z0-9㐀-鿿]+", ' ', fold(text)) + ' '
        self.words = set(self.f.split())
        self.content = {w for w in WORDS.findall(fold(text)) if len(w) >= 4 and w not in STOPW}

    def has(self, surface):
        """My echo test: the folded surface occurs as a phrase of whole words, or (single word >= 6 letters) its
        first max(5, n-3) letters start a prompt word ('Ukrainian' ~ 'Ukraine', 'Paraguayan' ~ 'paraguaya')."""
        s = re.sub(r"[^a-z0-9㐀-鿿]+", ' ', fold(surface)).strip()
        if not s:
            return False
        if CJKC.search(s):
            return s in self.f
        if ' ' + s + ' ' in self.f or ' ' + s + 's ' in self.f:
            return True
        if ' ' not in s and len(s) >= 6:
            st = s[:max(5, len(s) - 3)]
            return any(w.startswith(st) for w in self.words)
        return False

    def overlap(self, text):
        ws = [w for w in WORDS.findall(fold(text)) if len(w) >= 4 and w not in STOPW]
        return sum(w in self.content for w in ws) / len(ws) if ws else 0.0


GRP = {'gold_exact': 'gold', 'gold_coarse': 'gold', 'wrong_value': 'wrong', 'mixed': 'mixed', 'frame_only': 'frame',
       'none': 'none', 'ambiguous': 'ambiguous'}


def feats(r, pr, synth, gold):
    """Per-label features (my definitions)."""
    gh, wh = r['gold_hits'], r['wrong_hits']
    grp = GRP[r['label']]
    gname = any(h['match'] in ('exact', 'coarse') for h in gh)
    wname = any(h['kind'] in ('exact', 'coarse') for h in wh)
    g_surf_echo = [pr.has(h['surface']) for h in gh]
    # rule S (surface): echo iff the surface (or stem) is in the prompt
    gnovS = bool(gh) and not all(g_surf_echo)
    # rule V (analyst-like, my code): synthsys exact hits of the stated value are echoes too
    g_echoV = [e or (synth and h['match'] == 'exact' and h.get('value') == gold) for h, e in zip(gh, g_surf_echo)]
    gnovV = bool(gh) and not all(g_echoV)
    # rule X (strict): in synthsys every gold mention restates the stated attribute -> echo
    gnovX = gnovS and not synth
    gname_novV = any(h['match'] in ('exact', 'coarse') and not e for h, e in zip(gh, g_echoV))
    wvals = tuple(sorted({h.get('value') or 'coarse:' + h['surface'].lower() for h in wh}))
    gvals = tuple(sorted({h['surface'].lower() for h in gh}))
    spans = [tuple(h['span']) for h in gh + wh + r.get('ambiguous', [])]
    return dict(grp=grp, gname=gname, wname=wname, gnovS=gnovS, gnovV=gnovV, gnovX=gnovX, gname_novV=gname_novV,
                wdis=any(h.get('subtype') == 'distractor' for h in wh), wvals=wvals, gvals=gvals,
                gkind=min((h['match'] for h in gh), key=['exact', 'coarse', 'cue', 'pronoun'].index, default=''),
                spans=spans)


def masked_open(text, spans, k=4):
    t = text
    for s, e in sorted(spans, reverse=True):
        t = t[:s] + ' VAL ' + t[e:]
    w = re.findall(r"[\w']+", t.lower())
    return ' '.join(w[:k]) if len(w) >= k else None


def main():
    t0 = time.time()
    from transformers import AutoTokenizer
    from olens_improve.reconstruction import ar_token_ids
    from wsbench.evals.user_modeling.judge import build_options
    bank = C.load_bank('user_modeling')
    opts = build_options(list(bank.values()))
    ctx = {}
    for k, it in bank.items():
        c = LEX.item_context(it, opts[k])
        c['P'] = Prompt(c['prompt'])
        c['synth'] = it['subfamily'] == 'synthsys'
        c['group'] = f"{it['attr_class']}:{it['attr']}"
        c['sub'] = it['subfamily']
        ctx[k] = c
    tok = AutoTokenizer.from_pretrained(str(C.BASE))

    log('labels')
    lab = {}
    with open(D / 'labels/um_text_labels.jsonl') as f:
        for ln in f:
            r = json.loads(ln)
            c = ctx[r['item_id']]
            lab[r['key']] = feats(r, c['P'], c['synth'], c['gold'])
    log('labels', len(lab))

    cells = {}
    for r in C.read_jsonl(D / 'select/um_three_settings.jsonl'):
        cells[r['cell_id']] = r
    rows = []
    for pe in C.read_jsonl(D / 'select/um_pool.jsonl'):
        m = cells[pe['cell_id']]
        for b in pe['bullets']:
            rows.append((pe['cell_id'], m['item_id'], m['layer'], m['position'], m['read_position_kind'],
                         b['sample_index'], b['pos'], b['phrase_id'], b['cache_key'], b['solo_fve'], b['text']))
    pool = pd.DataFrame(rows, columns=['cell_id', 'item_id', 'layer', 'position', 'site', 'sample_index', 'pos',
                                       'phrase_id', 'cache_key', 'solo', 'text'])
    log('pool rows', len(pool))

    # AR window (the method's own tokenization, then the 32-token span cap)
    uniq = pool.text.unique()
    win = {}
    for t in uniq:
        cleaned, ids = ar_token_ids(tok, t)
        win[t] = (min(len(ids), 32), len(ids) > 32, tok.decode(ids[:32]) if len(ids) > 32 else cleaned)
    log('tokenized', len(uniq))
    pool['stok'] = pool.text.map(lambda t: win[t][0])
    pool['trunc'] = pool.text.map(lambda t: win[t][1])
    pool['window'] = pool.text.map(lambda t: win[t][2])

    # labels: full text from the file; window = lexicon re-run on the window of truncated bullets
    FCOLS = ['grp', 'gname', 'wname', 'gnovS', 'gnovV', 'gnovX', 'gname_novV', 'wdis', 'wvals', 'gvals', 'gkind', 'spans']
    fullf, winf = [], []
    wcache = {}
    miss = 0
    for it, t, (stok, trunc, w) in zip(pool.item_id, pool.text, (win[t] for t in pool.text)):
        k = tkey(it, t)
        f = lab.get(k)
        if f is None:
            miss += 1
            f = {c: None for c in FCOLS}
        fullf.append(f)
        if trunc:
            kk = (it, w)
            if kk not in wcache:
                c = ctx[it]
                wcache[kk] = feats(LEX.label_bullet(w, c['cls'], c['gold'], c['distractors'], c['prompt']),
                                   c['P'], c['synth'], c['gold'])
            winf.append(wcache[kk])
        else:
            winf.append(f)
    log('label join missing', miss, 'windows relabelled', len(wcache))
    for c in FCOLS:
        pool[c + 'F'] = [f[c] for f in fullf]
        pool[c] = [f[c] for f in winf]
    pool['group'] = pool.item_id.map(lambda i: ctx[i]['group'])
    pool['sub'] = pool.item_id.map(lambda i: ctx[i]['sub'])
    pool['cls'] = pool.item_id.map(lambda i: ctx[i]['cls'])
    pool['cjk_lead'] = pool.window.map(lambda w: bool(CJKC.match(w.lstrip())))
    pool['cjk_any'] = pool.window.map(lambda w: bool(CJKC.search(w)))
    pool['list_open'] = pool.window.map(lambda w: bool(LIST_OPEN.match(w)))
    pool['mark_open'] = pool.window.map(lambda w: bool(MARK_OPEN.match(w)))
    pool['overlap'] = [ctx[i]['P'].overlap(w) for i, w in zip(pool.item_id, pool.window)]
    pool['mopen4'] = [masked_open(w, s or []) for w, s in zip(pool.window, pool.spans)]
    pool['mopen3'] = [masked_open(w, s or [], 3) for w, s in zip(pool.window, pool.spans)]
    pool['site_kind'] = pool.site

    # selected readouts
    pidx = {p: i for i, p in enumerate(pool.phrase_id)}
    met = {}
    for L in (20, 36, 44, 52, 60):
        for r in C.read_jsonl(D / f'metrics/um_bullet_metrics.L{L}.jsonl'):
            for sid, s in r['settings'].items():
                for b in s.get('bullets') or []:
                    met[(r['cell_id'], sid, b['phrase_id'])] = b
    judge = {}
    for sid in SETTINGS:
        for v in C.read_jsonl(D / f'judge/um/{sid}/um_cell_rows.jsonl'):
            judge[(v['cell_id'], sid)] = (v['pick'], v['basis'])
    srows = []
    nmiss = 0
    for cid, r in cells.items():
        for sid in SETTINGS:
            atoms = r['settings'][sid]['atoms']
            pk, bs = judge.get((cid, sid), (None, None))
            for i, a in enumerate(atoms):
                k = pidx.get(a['source_phrase_id'])
                b = met.get((cid, sid, a['source_phrase_id']))
                if k is None:
                    nmiss += 1
                    continue
                srows.append((k, cid, sid, i, len(atoms), b['solo_fve'] if b else np.nan,
                              b['shapley_share'] if b else np.nan, b['loo_drop'] if b else np.nan, pk, bs,
                              a['text'].strip() == pool.text.iat[k].strip()))
    sel = pd.DataFrame(srows, columns=['pidx', 'cell_id', 'setting', 'idx', 'nb', 'solo_m', 'share', 'drop',
                                       'pick', 'basis', 'text_ok'])
    log('selected', len(sel), 'missing pool', nmiss, 'text mismatches', int((~sel.text_ok).sum()))
    # sample-level joint FVE from the Best of 32 trace
    samp = []
    for cid, r in cells.items():
        for t in r['settings']['best_n_exact-n32']['trace']:
            samp.append((cid, int(t['sample_id'].rsplit(':', 1)[1]), t.get('score')))
    samp = pd.DataFrame(samp, columns=['cell_id', 'sample_index', 'joint'])
    meta = {'pool_rows': len(pool), 'selected_rows': len(sel), 'label_missing': miss, 'selected_missing': nmiss,
            'windows_relabelled': len(wcache), 'truncated_share': float(pool.trunc.mean())}
    OUT.mkdir(parents=True, exist_ok=True)
    pool = pool.drop(columns=['spans', 'spansF'])
    with open(OUT / 'sk_tables.pkl', 'wb') as f:
        pickle.dump({'pool': pool, 'sel': sel, 'samples': samp, 'meta': meta,
                     'items': {k: {'group': c['group'], 'sub': c['sub'], 'cls': c['cls'], 'gold': c['gold'],
                                   'distractors': c['distractors'], 'prompt': c['prompt']} for k, c in ctx.items()}},
                    f, protocol=5)
    log('done', f'{time.time() - t0:.0f}s', meta)
    print(pool.grp.value_counts().to_string())
    print(pd.crosstab(pool.grpF, pool.grp).to_string())


if __name__ == '__main__':
    main()
