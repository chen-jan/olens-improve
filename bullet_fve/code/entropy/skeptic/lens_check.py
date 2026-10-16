"""Skeptic re-check of the logit-lens entropy proxy (independent code).

Recomputes, for all 1,123 read sites and all 5 layers, the logit lens
(final RMSNorm with (1+w), untied lm_head), and records per site/layer:
  H         entropy (nats) over the 248,320 tokens
  H_merge   entropy after merging tokens with the same normalised surface string
            (NFKC, strip, lower; whitespace tokens -> <NL>/<SP>), so ' better' / 'better' /
            ' Better' count as one outcome
  H_ncjk    entropy renormalised over tokens with no CJK / kana / hangul characters
  p1, top1 string, exact-correct, tolerant-correct (top-1 surface string, stripped and lower-cased,
            is a prefix of the upcoming reply text, stripped and lower-cased)
  surp      surprisal of the actual next token
Writes skeptic/lens_sites.jsonl and skeptic/lens_summary.json. Read-only elsewhere.
"""
from __future__ import annotations

import json
import os
import time
import unicodedata

import numpy as np
import torch
from safetensors import safe_open
from tokenizers import Tokenizer

torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "8")))
OUT = "${OLENS_SCRATCH}/olens-bullet-fve/entropy/skeptic"
SNAP = ("${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/"
        "snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9")
MAN = "${OLENS_COMPUTE_ROOT}/activations/core-v1/fresh_manifest_v2.json"
ACTS = "${OLENS_COMPUTE_ROOT}/activations/core-v1/activations.safetensors"
LAYERS = [20, 36, 44, 52, 60]
t0 = time.time()


def log(m):
    print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)


cfg = json.load(open(f"{SNAP}/config.json"))["text_config"]
EPS = float(cfg["rms_norm_eps"])
wmap = json.load(open(f"{SNAP}/model.safetensors.index.json"))["weight_map"]
with safe_open(f"{SNAP}/{wmap['model.language_model.norm.weight']}", framework="pt") as f:
    nw = f.get_tensor("model.language_model.norm.weight").float()
with safe_open(f"{SNAP}/{wmap['lm_head.weight']}", framework="pt") as f:
    Wh = f.get_tensor("lm_head.weight").float()
V = Wh.shape[0]
log(f"lm_head {tuple(Wh.shape)}")
tok = Tokenizer.from_file(f"{SNAP}/tokenizer.json")
strs = [tok.decode([i], skip_special_tokens=False) for i in range(V)]
log("decoded vocab")


def is_cjk(s):
    return any(("　" <= ch <= "鿿") or ("가" <= ch <= "힯") or ("豈" <= ch <= "﫿") for ch in s)


def norm_s(s):
    t = unicodedata.normalize("NFKC", s)
    if t.strip() == "":
        return "<NL>" if "\n" in t else "<SP>"
    return t.strip().lower()


cls_of = {}
cls_id = np.empty(V, np.int64)
for i, s in enumerate(strs):
    cls_id[i] = cls_of.setdefault(norm_s(s), len(cls_of))
NCLS = len(cls_of)
cls_id_t = torch.from_numpy(cls_id)
ncjk_mask = torch.tensor([not is_cjk(s) for s in strs])
log(f"{NCLS} merged classes; non-CJK tokens {int(ncjk_mask.sum())}")

man = [c for c in json.load(open(MAN))["cells"] if c["family"] == "hallucination"]
rows, ctx = {}, {}
for c in man:
    key = (c["item_id"], int(c["position"]))
    rows.setdefault(key, {})[int(c["layer"])] = int(c["activation_row"])
    ex = c["capture_spec"]["extra"]
    ctx.setdefault(key, (ex["input_ids"], int(ex["prompt_len"])))
sites = sorted(rows)
log(f"{len(sites)} sites")
with safe_open(ACTS, framework="pt") as f:
    R = f.get_tensor("resid")

nxt = []
upcoming = []
for s in sites:
    ids, pl = ctx[s]
    p = s[1]
    nxt.append(ids[p + 1] if p + 1 < len(ids) else -1)
    upcoming.append(tok.decode(ids[p + 1:p + 9], skip_special_tokens=False))
nxt_t = torch.tensor(nxt)

res = {L: {} for L in LAYERS}
for L in LAYERS:
    ridx = torch.tensor([rows[s][L] for s in sites])
    H, Hm, Hn, p1, t1, surp, pn = [], [], [], [], [], [], []
    for a in range(0, len(sites), 96):
        x = R[ridx[a:a + 96]].float()
        y = x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + EPS) * (1.0 + nw)
        lp = torch.log_softmax((y @ Wh.T).double(), -1)
        p = lp.exp()
        H += (-(p * lp).sum(-1)).tolist()
        pm = torch.zeros(p.shape[0], NCLS, dtype=torch.float64).index_add_(1, cls_id_t, p)
        Hm += (-(pm * torch.log(pm.clamp_min(1e-300))).sum(-1)).tolist()
        q = p[:, ncjk_mask]
        q = q / q.sum(-1, keepdim=True)
        Hn += (-(q * torch.log(q.clamp_min(1e-300))).sum(-1)).tolist()
        pn += p[:, ~ncjk_mask].sum(-1).tolist()
        v, i = p.max(-1)
        p1 += v.tolist()
        t1 += i.tolist()
        nx = nxt_t[a:a + 96]
        sv = -lp.gather(1, nx.clamp(min=0)[:, None])[:, 0]
        surp += [float(z) if n >= 0 else None for z, n in zip(sv.tolist(), nx.tolist())]
    res[L] = dict(H=H, Hm=Hm, Hn=Hn, p1=p1, t1=t1, surp=surp, pcjk=pn)
    log(f"L{L} done")


def tolerant(t1, j):
    if nxt[j] < 0:
        return None
    a = unicodedata.normalize("NFKC", strs[t1]).strip().lower()
    b = unicodedata.normalize("NFKC", upcoming[j]).strip().lower()
    if a == "":
        return strs[t1] == strs[nxt[j]] or ("\n" in strs[t1] and "\n" in strs[nxt[j]])
    return b.startswith(a)


out = []
for j, s in enumerate(sites):
    rec = {"item_id": s[0], "pos": s[1], "next_id": nxt[j], "upcoming": upcoming[j]}
    for L in LAYERS:
        r = res[L]
        rec[f"L{L}"] = {"H": round(r["H"][j], 5), "Hm": round(r["Hm"][j], 5), "Hn": round(r["Hn"][j], 5),
                        "p1": round(r["p1"][j], 5), "t1": strs[r["t1"][j]], "pcjk": round(r["pcjk"][j], 5),
                        "exact": (r["t1"][j] == nxt[j]) if nxt[j] >= 0 else None,
                        "tol": tolerant(r["t1"][j], j),
                        "surp": None if r["surp"][j] is None else round(r["surp"][j], 5)}
    out.append(rec)
with open(f"{OUT}/lens_sites.jsonl", "w") as f:
    for r in out:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")


def spear(a, b):
    from scipy.stats import spearmanr
    return round(float(spearmanr(a, b)[0]), 4)


summ = {"n_sites": len(sites), "n_merged_classes": NCLS}
for L in LAYERS:
    v = [r[f"L{L}"] for r in out if r["next_id"] >= 0]
    H = np.array([x["H"] for x in v]); p1 = np.array([x["p1"] for x in v])
    ex_ = np.array([x["exact"] for x in v], float); to = np.array([x["tol"] for x in v], float)
    sp = np.array([x["surp"] for x in v])
    qs = np.quantile(H, [0.2, 0.4, 0.6, 0.8]); qb = np.searchsorted(qs, H, side="right")
    bins = np.array([0, .3, .5, .7, .9, .99, 1.0001]); bb = np.digitize(p1, bins) - 1
    ece_ex = sum(abs(ex_[bb == k].mean() - p1[bb == k].mean()) * (bb == k).mean() for k in range(6) if (bb == k).any())
    ece_to = sum(abs(to[bb == k].mean() - p1[bb == k].mean()) * (bb == k).mean() for k in range(6) if (bb == k).any())
    summ[f"L{L}"] = {
        "mean_H": round(float(H.mean()), 3), "mean_surprisal": round(float(sp.mean()), 3),
        "top1_exact": round(float(ex_.mean()), 4), "top1_tolerant": round(float(to.mean()), 4),
        "mean_p1": round(float(p1.mean()), 4), "ECE_exact": round(float(ece_ex), 4), "ECE_tolerant": round(float(ece_to), 4),
        "by_H_quintile": [{"mean_H": round(float(H[qb == k].mean()), 3), "mean_p1": round(float(p1[qb == k].mean()), 3),
                           "acc_exact": round(float(ex_[qb == k].mean()), 3), "acc_tol": round(float(to[qb == k].mean()), 3),
                           "mean_surp": round(float(sp[qb == k].mean()), 3)} for k in range(5)],
        "by_p1_bin": [{"bin": [float(bins[k]), float(bins[k + 1])], "n": int((bb == k).sum()),
                       "mean_p1": round(float(p1[bb == k].mean()), 3) if (bb == k).any() else None,
                       "acc_exact": round(float(ex_[bb == k].mean()), 3) if (bb == k).any() else None,
                       "acc_tol": round(float(to[bb == k].mean()), 3) if (bb == k).any() else None} for k in range(6)],
        "spearman_H_vs_surprisal": spear(H, sp),
        "mean_cjk_mass": round(float(np.mean([x["pcjk"] for x in v])), 4),
    }
allH = {L: np.array([r[f"L{L}"]["H"] for r in out]) for L in LAYERS}
summ["spearman_H_between_layers"] = {f"L{a}-L{b}": spear(allH[a], allH[b]) for a in LAYERS for b in LAYERS if a < b}
summ["spearman_L60_variants"] = {
    "H_vs_Hmerge": spear(allH[60], [r["L60"]["Hm"] for r in out]),
    "H_vs_Hncjk": spear(allH[60], [r["L60"]["Hn"] for r in out]),
}
json.dump(summ, open(f"{OUT}/lens_summary.json", "w"), indent=1, ensure_ascii=False)
log("done")
print(json.dumps(summ, indent=1)[:6000])
