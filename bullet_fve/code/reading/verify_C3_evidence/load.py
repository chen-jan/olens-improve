# Independent re-implementation (verifier for claim C3). Builds a per-bullet table and pickles it.
import json, glob, re, os, pickle, math
import numpy as np
DATA = '${OLENS_SCRATCH}/olens-bullet-fve/page/data'
SIDS = ['capped_n1-n1', 'best_n_exact-n32', 'pooled_greedy_swap-n32']
CJK = re.compile('[㐀-䶿一-鿿豈-﫿]')
WORD = re.compile(r"[A-Za-z0-9]+|[㐀-䶿一-鿿豈-﫿]")
NUMOPEN = re.compile(r'^\s*[\W_]{0,4}\s*(\d+)\s*[.):]')

def s16(t, a, b):
    bb = t.encode('utf-16-le'); return bb[2*max(0,a):2*max(0,b)].decode('utf-16-le', errors='replace')

rows = []; items = []
for f in sorted(glob.glob(DATA + '/items/*.json')):
    d = json.load(open(f)); it = d['item']; iid = it['id']; items.append(iid)
    resp = it['response']
    for k, c in d['cells'].items():
        after = s16(resp, c['char'], c['char'] + 600)
        before = s16(resp, c['char'] - 2000, c['char'])
        next_starts_digit = bool(re.match(r'^[\W_]{0,6}\d', after))
        # list numbers the reply uses as markers anywhere (line-initial "N." / "N)")
        reply_nums = set(re.findall(r'(?m)^\s*(?:[#*>-]+\s*)?(\d+)[.)]', resp))
        aw = [w.lower() for w in WORD.findall(after)][:40]
        bw = [w.lower() for w in WORD.findall(before)]
        bw40 = bw[-40:]
        b3 = set(zip(bw, bw[1:], bw[2:]))
        a3 = set(zip(aw, aw[1:], aw[2:]))
        for sid in SIDS:
            s = c['settings'][sid]; txt = s['text'] or ''
            for j, b in enumerate(s['bullets'] or []):
                full = s16(txt, b['start'], b['end']); sc = s16(txt, b['start'], b['scored_end'])
                ns = [ch for ch in sc if not ch.isspace()]
                cjkf = sum(bool(CJK.match(ch)) for ch in ns) / len(ns) if ns else 0.0
                first = next((ch for ch in sc if ch.isalnum() or CJK.match(ch)), '')
                ws = [w.lower() for w in WORD.findall(sc)]
                head = ws[:8]
                m = NUMOPEN.match(sc)
                g3 = list(zip(ws, ws[1:], ws[2:]))
                rows.append(dict(item=iid, k=k, sid=sid, j=j, n=len(s['bullets']), label=b['label'],
                    solo=b['solo'], share=b['shap_share'], coef=b['coef'], dup=b['dup'], drop=b['drop'],
                    L=c['layer'], ro_label=s['label'], fve=s['fve'],
                    len16=b['end'] - b['start'], slen16=b['scored_end'] - b['start'], nwords=len(WORD.findall(full)),
                    cjk=cjkf, lead_cjk=bool(first) and bool(CJK.match(first)),
                    numopen=bool(m), num_mis=bool(m) and not next_starts_digit,
                    num_unused=bool(m) and (m.group(1) not in reply_nums),
                    prv_ov=(sum(w in set(bw40) for w in head) / len(head)) if head else float('nan'),
                    nxt_ov=(sum(w in set(aw) for w in head) / len(head)) if head else float('nan'),
                    recap3=(sum(g in b3 and g not in a3 for g in g3) / len(g3)) if g3 else float('nan'),
                    text=full))
pickle.dump({'rows': rows, 'items': items}, open('${OLENS_SCRATCH}/olens-bullet-fve/reading/verify_C3_evidence/rows.pkl', 'wb'))
print(len(rows), len(items))
