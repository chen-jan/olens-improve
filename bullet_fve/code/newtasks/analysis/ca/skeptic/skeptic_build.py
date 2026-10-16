"""Skeptic pass for ca: build my own tables from the raw label/metric files (independent of analysis.py's prep).

Sources (all read-only):
  data/select/ca_three_settings.jsonl  bullets of the 3 selected readouts per cell (text, scored text, token counts)
  data/metrics/ca_bullet_metrics.L*.jsonl  per-bullet solo FVE / Shapley share / LOO drop (recomputed by metrics3)
  data/select/ca_pool.jsonl  every pool bullet (first 4 per sample x 32 samples) with its solo FVE
  data/judge/ca_labels/ca_llm_bullet_labels.jsonl  LLM labels (raw differs / shared / conflicts)
  data/labels/ca_lex_bullet_labels.jsonl  lexicon v1 (code/ca_lexicon.py) on selected + pool bullets
  analysis/ca/cache/tables.pkl  ONLY for the lex2 column (the analysis's refined lexicon), joined by key and text-checked
  data/judge/ca/cell/ca_cell_rows.jsonl  per-cell judge picks
Writes analysis/ca/skeptic/cache/sk_tables.pkl
"""
import collections
import json
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

NT = Path('${OLENS_SCRATCH}/olens-bullet-fve/newtasks')
sys.path.insert(0, str(NT / 'code'))
import ntcommon as C  # noqa: E402

D = NT / 'data'
OUT = NT / 'analysis/ca/skeptic/cache'
SETTINGS = ('capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32')

CJK = re.compile(r'[぀-ヿ㐀-䶿一-鿿가-힯]')
SCAF = re.compile(r'^\s*(?:\d+\s*[.:)]|\*\*|#+|<think>|</?\w+>|-\s|\(\w\))')
INSTR = re.compile(r'summar|one sentence|preceding|in one line|concise', re.I)
WORD = re.compile(r"[a-z][a-z'’]+")
STOP = set("""a an the and or but if of to in on at by for with from as is are was were be been being has have had do does did
not no nor so than that this these those there their they them he she his her hers him it its we our you your i me my
who whom whose which what when where why how all any each both few more most other some such only own same too very
can will just should now into over under after before while during about against between through up down out off again
further then once here also because until upon within without even still yet ever never one two three first last
""".split())


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def content_words(t):
    return {w.strip("'’") for w in WORD.findall(t.lower()) if len(w) >= 4 and w not in STOP}


def names(stim):
    # capitalized tokens not at sentence start are names (Nora, Dana); also keep any capitalized word in stimulus
    return {m.group(0).lower() for m in re.finditer(r'\b[A-Z][a-z]{2,}\b', stim)} - STOP


def main():
    t0 = time.time()
    bank = C.load_bank('conjunctive_association')
    stim_cw = {k: content_words(it['stimulus']) for k, it in bank.items()}
    stim_names = {k: names(it['stimulus']) for k, it in bank.items()}

    three = list(C.read_jsonl(D / 'select/ca_three_settings.jsonl'))
    meta = {r['cell_id']: r for r in three}
    met = {}
    for L in (20, 36, 44, 52, 60):
        for r in C.read_jsonl(D / f'metrics/ca_bullet_metrics.L{L}.jsonl'):
            met[r['cell_id']] = r['settings']
    llm = {}
    for r in C.read_jsonl(D / 'judge/ca_labels/ca_llm_bullet_labels.jsonl'):
        llm[(r['cell_id'], r['text'])] = r
    lex1_sel, lex1_pool = {}, {}
    for r in C.read_jsonl(D / 'labels/ca_lex_bullet_labels.jsonl'):
        if r['source'] == 'pool':
            lex1_pool[r['phrase_id']] = r['label']
        else:
            lex1_sel[(r['cell_id'], r['source'], r['index'])] = r['label']
    judge = {(r['cell_id'], r['setting']): r for r in C.read_jsonl(D / 'judge/ca/cell/ca_cell_rows.jsonl')}
    log('loaded raw', len(three), len(met), len(llm), len(lex1_sel), len(lex1_pool), len(judge))

    def feats(item_id, text):
        cw = content_words(text)
        sw = stim_cw[item_id]
        echo = (len(cw & sw) / len(cw)) if cw else 0.0
        return {'cjk': bool(CJK.search(text)), 'cjk_lead': bool(CJK.search(text[:6])), 'scaf': bool(SCAF.match(text)),
                'instr': bool(INSTR.search(text)), 'echo': echo, 'n_cw': len(cw),
                'name': bool(set(w.lower() for w in re.findall(r'\b[A-Z][a-z]{2,}\b', text)) & stim_names[item_id])}

    rows = []
    for r in three:
        cid = r['cell_id']
        it = bank[r['item_id']]
        X = it['contrast_axis']
        for sid in SETTINGS:
            s = r['settings'][sid]
            ms = met[cid][sid]
            mb = ms.get('bullets') or []
            jr = judge.get((cid, sid), {})
            for i, a in enumerate(s['atoms']):
                text = a['text'].strip()
                b = mb[i] if i < len(mb) else None
                if b is not None:
                    assert b['phrase_id'] == a['source_phrase_id'], (cid, sid, i)
                lr = llm.get((cid, text))
                raw = lr['label'] if lr else None
                rows.append({
                    'cell_id': cid, 'item_id': r['item_id'], 'group': r['group_id'], 'layer': r['layer'],
                    'position': r['position'], 'site': r['read_position_kind'], 'rel_end': r['rel_from_end'],
                    'setting': sid, 'idx': i, 'nb': len(s['atoms']), 'text': text, 'scored_text': a['scored_text'],
                    'stok': a['scored_token_count'], 'cache_key': a['cache_key'], 'sample_index': a['sample_index'],
                    'solo': b['solo_fve'] if b else np.nan, 'share': b['shapley_share'] if b else np.nan,
                    'loo': b['loo_drop'] if b else np.nan, 'joint': ms.get('joint_fve_saved'),
                    'llm_raw': raw, 'llm_differs': lr['differs'] if lr else None,
                    'llm_conflicts': lr['conflicts'] if lr else None, 'llm_shared': lr['shared'] if lr else None,
                    'llm_quote': lr['quote'] if lr else None,
                    'lex1': lex1_sel.get((cid, sid, i)), 'X': X,
                    'judge_pick': jr.get('pick'), 'judge_qb': i in (jr.get('quote_bullets') or []),
                    **feats(r['item_id'], a['scored_text'] or text),
                })
    sel = pd.DataFrame(rows)
    log('sel rows', len(sel), 'llm missing', int(sel.llm_raw.isna().sum()), 'lex1 missing', int(sel.lex1.isna().sum()))

    # pool
    prow = []
    for pe in C.read_jsonl(D / 'select/ca_pool.jsonl'):
        r = meta[pe['cell_id']]
        for b in pe['bullets']:
            t = b['text'].strip()
            prow.append({'cell_id': pe['cell_id'], 'item_id': r['item_id'], 'group': r['group_id'], 'layer': r['layer'],
                         'site': r['read_position_kind'], 'sample_index': b['sample_index'], 'pos': b['pos'],
                         'text': t, 'cache_key': b['cache_key'], 'solo': b['solo_fve'],
                         'lex1': lex1_pool.get(b['phrase_id']), **feats(r['item_id'], t[:240])})
    pool = pd.DataFrame(prow)
    log('pool rows', len(pool), 'lex1 missing', int(pool.lex1.isna().sum()))

    # lex2 from the analysis cache, joined by key; verify texts
    with open(NT / 'analysis/ca/cache/tables.pkl', 'rb') as f:
        T = pickle.load(f)
    ts = T['sel'][['cell_id', 'setting', 'idx', 'text', 'lex2', 'stok']].rename(
        columns={'text': 'text_a', 'lex2': 'lex2', 'stok': 'stok_a'})
    sel = sel.merge(ts, on=['cell_id', 'setting', 'idx'], how='left')
    bad = int((sel.text != sel.text_a).sum())
    log('sel lex2 join: text mismatches', bad, 'lex2 missing', int(sel.lex2.isna().sum()),
        'stok mismatches', int((sel.stok != sel.stok_a).sum()))
    tp = T['pool'][['cell_id', 'sample_index', 'pos', 'text', 'lex2', 'stok', 'solo']].rename(
        columns={'text': 'text_a', 'solo': 'solo_a'})
    pool = pool.merge(tp, on=['cell_id', 'sample_index', 'pos'], how='left')
    log('pool lex2 join: text mismatches', int((pool.text != pool.text_a).sum()), 'lex2 missing',
        int(pool.lex2.isna().sum()), 'solo max abs diff', float(np.nanmax(np.abs(pool.solo - pool.solo_a))))
    sel = sel.drop(columns=['text_a', 'stok_a'])
    pool = pool.drop(columns=['text_a', 'solo_a'])
    samples = T['samples']
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / 'sk_tables.pkl', 'wb') as f:
        pickle.dump({'sel': sel, 'pool': pool, 'samples': samples}, f, protocol=5)
    log('wrote', OUT / 'sk_tables.pkl', f'{time.time() - t0:.0f}s')
    print(sel.groupby(['setting', 'llm_raw']).size().unstack(fill_value=0).to_string())
    print(pd.crosstab(pool.lex1, pool.lex2).to_string())
    print(pool[['cjk', 'scaf', 'instr', 'name']].mean().to_string(), pool.echo.describe().to_string())


if __name__ == '__main__':
    main()
