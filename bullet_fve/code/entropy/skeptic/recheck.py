"""Skeptic re-check of entropy/ENTROPY.md with independent code.

Inference: within-chat fixed effects (demeaning), CR1 cluster-robust SEs by chat (analytic) and a
chat-resampling bootstrap (B=1000, different seed from analysis.py) for the headline numbers.
Exposure: percentile rank of the site's entropy proxy over the 1,123 sites (0 lowest, 1 highest),
so slopes are "highest minus lowest entropy site". Same sign convention as ENTROPY.md.

Writes skeptic/recheck_results.json. Reads only; prints a digest.
"""
from __future__ import annotations

import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from scipy import stats

BASE = "${OLENS_SCRATCH}/olens-bullet-fve"
ENT = f"{BASE}/entropy"
OUT = f"{ENT}/skeptic"
SET = ["capped_n1-n1", "best_n_exact-n32", "pooled_greedy_swap-n32"]
SH = {"capped_n1-n1": "Original", "best_n_exact-n32": "Best of 32", "pooled_greedy_swap-n32": "Combine 32"}
LAYERS = [20, 36, 44, 52, 60]
KINDS = ["clause", "sentence", "markup", "newline", "quote"]
t0 = time.time()


def log(m):
    print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)


# ------------------------------------------------------------------ load
idx = json.load(open(f"{BASE}/page/data/index.json"))
items = {it["id"]: json.load(open(f"{BASE}/page/data/items/{it['id']}.json"))["item"] for it in idx["items"]}
iids = [it["id"] for it in idx["items"]]
src = {it["id"]: it["source"] for it in idx["items"]}

se = {(r["item_id"], r["pos"]): r for r in map(json.loads, open(f"{ENT}/site_entropy.jsonl"))}
lens = {}
try:
    for r in map(json.loads, open(f"{OUT}/lens_sites.jsonl")):
        lens[(r["item_id"], r["pos"])] = r
except FileNotFoundError:
    log("no lens_sites.jsonl yet; lens variants skipped")

cont = {}
for line in open(f"{ENT}/continuation.jsonl"):
    r = json.loads(line)
    if r["setting"] in SET:
        cont[(r["setting"], r["k"])] = r


def u16_to_py(s, u):
    n = 0
    for i, ch in enumerate(s):
        if n >= u:
            return i
        n += 2 if ord(ch) > 0xFFFF else 1
    return len(s)


CJK = re.compile(r"[　-鿿가-힯]")
rows = []
for c in idx["cells"]:
    iid = iids[c["i"]]
    it = items[iid]
    site = next(s for s in it["sites"] if s["pos"] == c["p"])
    resp = it["response"]
    ci = u16_to_py(resp, site["char"])
    e = se[(iid, c["p"])]
    rec = {"k": c["k"], "item": iid, "src": src[iid], "L": c["L"], "pos": c["p"], "kind": c["sk"], "tok": c["st"],
           "relpos": ci / max(1, len(resp)), "resp_chars": len(resp), "tok_index": e["rel_pos"],
           "resp_tokens": e["resp_len"], "H60": e["H_L60"], "H52": e["H_L52"], "p1": e["p_top1"],
           "surp": e["surprisal_next_L60"], "next_type": e["next_type"], "top1_ok": e["top1_correct"],
           "has_code": "```" in resp, "after_text": resp[ci:ci + 80]}
    if lens:
        lr = lens[(iid, c["p"])]
        for L in LAYERS:
            rec[f"Hl{L}"] = lr[f"L{L}"]["H"]
        rec["Hm60"] = lr["L60"]["Hm"]
        rec["Hn60"] = lr["L60"]["Hn"]
        rec["tol60"] = lr["L60"]["tol"]
        rec["pcjk60"] = lr["L60"]["pcjk"]
        rec["H52_mine"] = lr["L52"]["H"]
    for j, st in enumerate(SET):
        sv = c["s"][j]
        sh = SH[st]
        cr = cont[(st, c["k"])]
        rec[f"fve|{sh}"] = np.nan if sv["f"] is None else sv["f"]
        rec[f"lab|{sh}"] = sv["c"]
        rec[f"hall|{sh}"] = np.nan if sv["c"] == 4 else float(sv["c"] == 1)
        rec[f"off|{sh}"] = np.nan if sv["c"] == 4 else float(sv["c"] == 2)
        ok = cr["n_scorable"] > 0
        for cl in ["NEXT", "NONE", "BEFORE", "LATER"]:
            rec[f"{cl}|{sh}"] = cr["shares"][cl] if ok else np.nan
        rec[f"cex|{sh}"] = np.nan if (not ok or cr["cont_excess"] is None) else cr["cont_excess"]
        bl = cr["bullets"]
        rec[f"nbul|{sh}"] = len(bl)
        rec[f"nw|{sh}"] = np.mean([b["nw"] for b in bl]) if bl else np.nan
        rec[f"na|{sh}"] = cr["n_na"] / len(bl) if bl else np.nan
        rec[f"cjk|{sh}"] = np.mean([bool(CJK.search(b["text"])) for b in bl]) if bl else np.nan
        rec[f"meta|{sh}"] = cr["n_meta"] / len(bl) if bl else np.nan
        rec[f"wa"] = cr["n_words_after"]
        # bullet-level solo FVE aligned with classifier classes (same order: page bullets)
        so = sv.get("so") or []
        if len(so) == len(bl):
            rec[f"bul|{sh}"] = [(b["cls"], so[q], b["nw"]) for q, b in enumerate(bl)]
        else:
            rec[f"bul|{sh}"] = None
    rows.append(rec)
D = pd.DataFrame(rows)
log(f"{len(D)} cells, {D.item.nunique()} chats, {D.groupby(['item','pos']).ngroups} sites")

# site-level ranks
sites = D.drop_duplicates(["item", "pos"]).copy()


def prank(v):
    v = np.asarray(v, float)
    out = np.full(len(v), np.nan)
    m = np.isfinite(v)
    out[m] = (stats.rankdata(v[m]) - 1) / (m.sum() - 1)
    return out


proxies = ["H60", "H52", "surp", "p1"] + ([f"Hl{L}" for L in LAYERS] + ["Hm60", "Hn60"] if lens else [])
for p in proxies:
    sites[f"r_{p}"] = prank(-sites[p] if p == "p1" else sites[p])  # p1: 1 - confidence direction
D = D.merge(sites[["item", "pos"] + [f"r_{p}" for p in proxies]], on=["item", "pos"])
D["chat"] = D["item"].map({iid: j for j, iid in enumerate(iids)})
D["lwa"] = np.log1p(D["wa"])
for kn in KINDS[1:]:
    D[f"k_{kn}"] = (D.kind == kn).astype(float)
for L in LAYERS[1:]:
    D[f"l_{L}"] = (D.L == L).astype(float)
D["relpos2"] = D.relpos ** 2
NT_LEV = [t for t, _ in Counter(D.next_type).most_common() if t != "word_space"]
for t in NT_LEV:
    D[f"nt_{t}"] = (D.next_type == t).astype(float)
CTRL = [f"k_{k}" for k in KINDS[1:]] + ["relpos", "relpos2", "lwa"]
LD = [f"l_{L}" for L in LAYERS[1:]]
NTD = [f"nt_{t}" for t in NT_LEV]
G = D.chat.nunique()

# ------------------------------------------------------------------ estimator
RNG = np.random.default_rng(777)
B = 1000
BW = RNG.multinomial(G, np.full(G, 1 / G), size=B).astype(float)


def fe_fit(d, y, xs, fe="chat", boot=False):
    """OLS of y on xs after demeaning within fe groups; CR1 SE clustered by chat; optional bootstrap."""
    cols = [y] + xs
    d = d[cols + ["chat"] + ([fe] if fe != "chat" else [])].dropna()
    if len(d) < len(xs) + 5:
        return None
    grp = d[fe] if fe != "chat" else d["chat"]
    Z = d[cols].astype(float)
    Z = Z - Z.groupby(grp.values).transform("mean")
    yv = Z[y].values
    X = Z[xs].values
    keep = X.std(0) > 1e-12
    X = X[:, keep]
    xs_k = [x for x, k in zip(xs, keep) if k]
    XtX = X.T @ X
    XtXi = np.linalg.pinv(XtX)
    b = XtXi @ X.T @ yv
    e = yv - X @ b
    g = d["chat"].values
    n, kx = X.shape
    ng = len(np.unique(g))
    S = np.zeros((ng, kx))
    _, gi = np.unique(g, return_inverse=True)
    np.add.at(S, gi, X * e[:, None])
    V = XtXi @ (S.T @ S) @ XtXi * ng / (ng - 1) * (n - 1) / max(1, n - kx)
    seb = np.sqrt(np.diag(V))
    out = {x: {"b": float(b[i]), "se": float(seb[i]), "ci": [float(b[i] - 1.96 * seb[i]), float(b[i] + 1.96 * seb[i])],
               "p": float(2 * stats.t.sf(abs(b[i] / seb[i]), ng - 1))} for i, x in enumerate(xs_k)}
    out["_n"] = int(n)
    out["_chats"] = int(ng)
    if boot:
        # chat bootstrap via reweighting chat-level cross products (FE demeaning is chat-local when fe=chat)
        A = np.zeros((G, kx, kx)); c_ = np.zeros((G, kx))
        np.add.at(A, d["chat"].values, X[:, :, None] * X[:, None, :])
        np.add.at(c_, d["chat"].values, X * yv[:, None])
        bb = np.linalg.solve(np.einsum("bg,gij->bij", BW, A) + 1e-9 * np.eye(kx), np.einsum("bg,gi->bi", BW, c_)[..., None])[..., 0]
        for i, x in enumerate(xs_k):
            out[x]["boot_ci"] = [float(np.percentile(bb[:, i], 2.5)), float(np.percentile(bb[:, i], 97.5))]
            out[x]["_draws"] = bb[:, i]
    return out


def fmt(o, x):
    if o is None or x not in o:
        return "NA"
    r = o[x]
    s = f"{r['b']:+.3f} [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}] p={r['p']:.3f}"
    if "boot_ci" in r:
        s += f" boot[{r['boot_ci'][0]:+.3f}, {r['boot_ci'][1]:+.3f}]"
    return s


RES = {}


def put(key, o, x):
    RES[key] = None if o is None or x not in o else {k: v for k, v in o[x].items() if k != "_draws"} | {"n": o["_n"]}
    print(f"  {key:70s} {fmt(o, x)}")


# ------------------------------------------------------------------ 1. headline replication
log("1. replicate headline numbers")
for sh in SH.values():
    o = fe_fit(D, f"fve|{sh}", ["r_H60"] + CTRL + LD, boot=True)
    put(f"fve_pooled|{sh}", o, "r_H60")
per_layer_draws = {}
for sh in ["Original", "Best of 32"]:
    for L in LAYERS:
        o = fe_fit(D[D.L == L], f"fve|{sh}", ["r_H60"] + CTRL, boot=True)
        put(f"fve_L{L}|{sh}", o, "r_H60")
        per_layer_draws[(sh, L)] = (o["r_H60"]["b"], o["r_H60"]["_draws"])
    b60, d60 = per_layer_draws[(sh, 60)]
    b20, d20 = per_layer_draws[(sh, 20)]
    dd = d60 - d20
    RES[f"fve_L60_minus_L20|{sh}"] = {"b": b60 - b20, "boot_ci": [float(np.percentile(dd, 2.5)), float(np.percentile(dd, 97.5))],
                                      "boot_p": float(2 * min((dd > 0).mean(), (dd < 0).mean()))}
    print(f"  fve_L60_minus_L20|{sh:12s} {b60-b20:+.3f} boot[{np.percentile(dd,2.5):+.3f}, {np.percentile(dd,97.5):+.3f}]")

# slope-by-layer trend test (linear in layer index), Original: interaction r_H60 x layer_z
D["layer_z"] = (D.L - 44) / 16
D["rH_x_layer"] = D.r_H60 * D.layer_z
for sh in SH.values():
    o = fe_fit(D, f"fve|{sh}", ["r_H60", "rH_x_layer"] + CTRL + LD + [f"{c}_xl" for c in []], boot=True)
    put(f"fve_H_x_layer_trend(per 16 layers)|{sh}", o, "rH_x_layer")

D["neardet"] = (D.H60 < 0.1).astype(float)
D["not_neardet"] = 1 - D.neardet
boundary = D.next_type.isin(["newline", "none"])
nextword = D.next_type.isin(["word_space", "word_nospace"])
for sh in ["Original", "Best of 32"]:
    put(f"neardet_rest_minus_low_all|{sh}", fe_fit(D, f"fve|{sh}", ["not_neardet"] + CTRL + LD, boot=True), "not_neardet")
    put(f"neardet_rest_minus_low_noboundary|{sh}", fe_fit(D[~boundary], f"fve|{sh}", ["not_neardet"] + CTRL + LD, boot=True), "not_neardet")
    put(f"neardet_rest_minus_low_nextword|{sh}", fe_fit(D[nextword], f"fve|{sh}", ["not_neardet"] + CTRL + LD, boot=True), "not_neardet")
RES["n_neardet_sites"] = int(D[D.L == 20].neardet.sum())
RES["n_neardet_boundary_sites"] = int(D[(D.L == 20) & boundary].neardet.sum())
print("  near-det sites", RES["n_neardet_sites"], "of which boundary", RES["n_neardet_boundary_sites"])

for o_ in ["NEXT", "NONE", "cex"]:
    for sh in SH.values():
        put(f"{o_}_pooled|{sh}", fe_fit(D, f"{o_}|{sh}", ["r_H60"] + CTRL + LD, boot=True), "r_H60")
for sh in SH.values():
    put(f"halluc_pooled|{sh}", fe_fit(D, f"hall|{sh}", ["r_H60"] + CTRL + LD, boot=True), "r_H60")
    put(f"offtopic_pooled|{sh}", fe_fit(D, f"off|{sh}", ["r_H60"] + CTRL + LD, boot=True), "r_H60")
    put(f"surprisal_fve_pooled|{sh}", fe_fit(D, f"fve|{sh}", ["r_surp"] + CTRL + LD, boot=True), "r_surp")
    o = fe_fit(D, f"fve|{sh}", CTRL + LD)
    o2 = fe_fit(D, f"fve|{sh}", CTRL + ["r_H60"] + LD)
    put(f"sentence_gap_noH|{sh}", o, "k_sentence")
    put(f"sentence_gap_withH|{sh}", o2, "k_sentence")
    m = D[[f"NEXT|{sh}", f"fve|{sh}"]].dropna()
    RES[f"spearman_NEXT_FVE|{sh}"] = float(stats.spearmanr(m.iloc[:, 0], m.iloc[:, 1])[0])
    print(f"  spearman NEXT-FVE {sh}: {RES[f'spearman_NEXT_FVE|{sh}']:.3f}")
    put(f"mediation_direct_with_NEXT|{sh}", fe_fit(D, f"fve|{sh}", ["r_H60", f"NEXT|{sh}"] + CTRL + LD), "r_H60")

# quintile tables (raw), for checking the quoted numbers
q = np.quantile(sites.H60, [0.2, 0.4, 0.6, 0.8])
D["HQ"] = np.searchsorted(q, D.H60, side="right")
RES["quintile_cuts"] = q.tolist()
for sh in ["Original"]:
    RES[f"NEXT_by_Q_L60|{sh}"] = D[D.L == 60].groupby("HQ")[f"NEXT|{sh}"].mean().round(3).tolist()
    RES[f"fve_by_Q_L60|{sh}"] = D[D.L == 60].groupby("HQ")[f"fve|{sh}"].mean().round(3).tolist()
    RES[f"hall_by_Q|{sh}"] = D.groupby("HQ")[f"hall|{sh}"].mean().round(3).tolist()
    print("  NEXT by Q L60", RES[f"NEXT_by_Q_L60|{sh}"], " FVE by Q L60", RES[f"fve_by_Q_L60|{sh}"])

# ------------------------------------------------------------------ 2. proxy validity: other entropy proxies
log("2. alternative entropy proxies")
for p in proxies:
    if p in ("H60",):
        continue
    for sh in ["Original", "Best of 32"]:
        put(f"fve_pooled_proxy_{p}|{sh}", fe_fit(D, f"fve|{sh}", [f"r_{p}"] + CTRL + LD), f"r_{p}")
        put(f"NEXT_pooled_proxy_{p}|{sh}", fe_fit(D, f"NEXT|{sh}", [f"r_{p}"] + CTRL + LD), f"r_{p}")
if lens:
    # per layer: the lens of the SAME layer as the readout (activation-local readability) vs FVE
    for sh in ["Original"]:
        for L in LAYERS:
            put(f"fve_L{L}_own_layer_lens_H|{sh}", fe_fit(D[D.L == L], f"fve|{sh}", [f"r_Hl{L}"] + CTRL), f"r_Hl{L}")
    # restrict to sites where the L60 lens top-1 is (tolerantly) right: there its confidence is more trustworthy
    Dt = D[D.tol60 == True]
    RES["n_sites_tolerant_correct"] = int(Dt[Dt.L == 20].shape[0])
    for sh in ["Original", "Best of 32"]:
        put(f"fve_pooled_tolcorrect_only|{sh}", fe_fit(Dt, f"fve|{sh}", ["r_H60"] + CTRL + LD, boot=True), "r_H60")
        put(f"NEXT_pooled_tolcorrect_only|{sh}", fe_fit(Dt, f"NEXT|{sh}", ["r_H60"] + CTRL + LD, boot=True), "r_H60")

# ------------------------------------------------------------------ 3. confounds
log("3. confounds")
for sh in ["Original", "Best of 32"]:
    # chat source
    for s_ in ["dailydialog", "lmsys"]:
        put(f"fve_pooled_src_{s_}|{sh}", fe_fit(D[D.src == s_], f"fve|{sh}", ["r_H60"] + CTRL + LD), "r_H60")
        put(f"NEXT_pooled_src_{s_}|{sh}", fe_fit(D[D.src == s_], f"NEXT|{sh}", ["r_H60"] + CTRL + LD), "r_H60")
    # code chats
    for nm, dd in [("nocode", D[~D.has_code]), ("code", D[D.has_code])]:
        put(f"fve_pooled_{nm}|{sh}", fe_fit(dd, f"fve|{sh}", ["r_H60"] + CTRL + LD), "r_H60")
    # absolute token index control and reply-length interaction
    D["ltok"] = np.log1p(D.tok_index)
    D["rH_x_lresp"] = D.r_H60 * (np.log(D.resp_tokens) - np.log(D.resp_tokens).mean())
    put(f"fve_pooled_plus_logtokindex|{sh}", fe_fit(D, f"fve|{sh}", ["r_H60", "ltok"] + CTRL + LD), "r_H60")
    put(f"fve_H_x_logresplen|{sh}", fe_fit(D, f"fve|{sh}", ["r_H60", "rH_x_lresp"] + CTRL + LD), "rH_x_lresp")
    # exclude the first 10% / last 10% of reply
    put(f"fve_pooled_mid80|{sh}", fe_fit(D[(D.relpos > 0.1) & (D.relpos < 0.9)], f"fve|{sh}", ["r_H60"] + CTRL + LD), "r_H60")
    # next-token type control
    put(f"fve_pooled_plus_nexttype|{sh}", fe_fit(D, f"fve|{sh}", ["r_H60"] + CTRL + LD + NTD), "r_H60")
    # chat x kind fixed effects (within chat AND within site kind)
    D["chat_kind"] = D.chat.astype(str) + "_" + D.kind
    put(f"fve_pooled_chatXkind_FE|{sh}", fe_fit(D, f"fve|{sh}", ["r_H60", "relpos", "relpos2", "lwa"] + LD, fe="chat_kind"), "r_H60")
    put(f"NEXT_pooled_chatXkind_FE|{sh}", fe_fit(D, f"NEXT|{sh}", ["r_H60", "relpos", "relpos2", "lwa"] + LD, fe="chat_kind"), "r_H60")
    # chat x layer FE
    D["chat_layer"] = D.chat.astype(str) + "_" + D.L.astype(str)
    put(f"fve_pooled_chatXlayer_FE|{sh}", fe_fit(D, f"fve|{sh}", ["r_H60"] + CTRL, fe="chat_layer"), "r_H60")
    # read-token FE (same punctuation token) on top of chat FE: within-token slope via token dummies
    toks = [t for t, n in Counter(D[D.L == 20].tok).most_common() if n >= 15]
    for t in toks[1:]:
        D[f"tk_{repr(t)}"] = (D.tok == t).astype(float)
    TKD = [f"tk_{repr(t)}" for t in toks[1:]] + ["tk_other"]
    D["tk_other"] = (~D.tok.isin(toks)).astype(float)
    put(f"fve_pooled_plus_readtoken_dummies|{sh}", fe_fit(D, f"fve|{sh}", ["r_H60"] + CTRL + LD + TKD), "r_H60")
    put(f"NEXT_pooled_plus_readtoken_dummies|{sh}", fe_fit(D, f"NEXT|{sh}", ["r_H60"] + CTRL + LD + TKD), "r_H60")

# per-kind slopes, and per-kind with boundaries dropped
for sh in ["Original"]:
    for kn in KINDS:
        dk = D[D.kind == kn]
        ctrl_k = ["relpos", "relpos2", "lwa"] + LD
        put(f"fve_pooled_kind_{kn}|{sh}", fe_fit(dk, f"fve|{sh}", ["r_H60"] + ctrl_k, boot=True), "r_H60")
        put(f"fve_pooled_kind_{kn}_noboundary|{sh}", fe_fit(dk[~dk.next_type.isin(['newline', 'none'])], f"fve|{sh}", ["r_H60"] + ctrl_k, boot=True), "r_H60")
        put(f"NEXT_pooled_kind_{kn}|{sh}", fe_fit(dk, f"NEXT|{sh}", ["r_H60"] + ctrl_k), "r_H60")
        RES[f"n_sites_kind_{kn}"] = int((dk.L == 20).sum())

# ------------------------------------------------------------------ 4. classifier bias
log("4. classifier bias")
for sh in ["Original", "Best of 32"]:
    # does entropy predict bullet length / NA share / CJK share?
    for v in ["nw", "na", "cjk", "nbul"]:
        put(f"{v}_pooled_vs_H|{sh}", fe_fit(D, f"{v}|{sh}", ["r_H60"] + CTRL + LD), "r_H60")
    # NEXT slope controlling bullet length, NA and CJK share
    put(f"NEXT_pooled_ctrl_len_na_cjk|{sh}", fe_fit(D, f"NEXT|{sh}", ["r_H60", f"nw|{sh}", f"na|{sh}", f"cjk|{sh}"] + CTRL + LD), "r_H60")
    # NEXT slope in non-code chats only, words after >= 40 (full NEXT window)
    put(f"NEXT_pooled_nocode_wa40|{sh}", fe_fit(D[(~D.has_code) & (D.wa >= 40)], f"NEXT|{sh}", ["r_H60"] + CTRL + LD), "r_H60")
    # NEXT vs FVE controlling bullet length
    put(f"fve_on_NEXT_ctrl_len|{sh}", fe_fit(D, f"fve|{sh}", [f"NEXT|{sh}", f"nw|{sh}", f"na|{sh}"] + CTRL + LD), f"NEXT|{sh}")
    put(f"fve_on_NEXT|{sh}", fe_fit(D, f"fve|{sh}", [f"NEXT|{sh}"] + CTRL + LD), f"NEXT|{sh}")

# bullet-level: solo FVE of NEXT vs NONE bullets WITHIN the same readout (AR continuation bias)
for sh in ["Original", "Best of 32"]:
    bl = []
    for r in D[["k", f"bul|{sh}", "r_H60", "L", "chat"]].itertuples(index=False):
        if r[1] is None:
            continue
        for q_, (cls, so, nw) in enumerate(r[1]):
            if cls in ("NEXT", "NONE", "BEFORE", "LATER"):
                bl.append({"k": r[0], "cls": cls, "so": so, "nw": nw, "rH": r[2], "L": r[3], "chat": r[4], "bpos": q_})
    Bd = pd.DataFrame(bl)
    Bd["isNEXT"] = (Bd.cls == "NEXT").astype(float)
    Bd["lnw"] = np.log1p(Bd.nw)
    for q_ in range(4):
        Bd[f"bp{q_}"] = (Bd.bpos == q_).astype(float)
    RES[f"bullets_n|{sh}"] = int(len(Bd))
    # within readout (FE = readout k)
    put(f"solo_fve_NEXT_minus_other_within_readout|{sh}", fe_fit(Bd, "so", ["isNEXT", "lnw", "bp1", "bp2", "bp3"], fe="k"), "isNEXT")
    Bd["isNEXT_x_rH"] = Bd.isNEXT * (Bd.rH - 0.5)
    put(f"solo_fve_NEXT_premium_x_H_within_readout|{sh}", fe_fit(Bd, "so", ["isNEXT", "isNEXT_x_rH", "lnw", "bp1", "bp2", "bp3"], fe="k"), "isNEXT_x_rH")
    put(f"solo_fve_vs_len_within_readout|{sh}", fe_fit(Bd, "so", ["lnw", "isNEXT", "bp1", "bp2", "bp3"], fe="k"), "lnw")

# ------------------------------------------------------------------ 5. multiple comparisons
log("5. multiple comparisons")
fam = {k: v for k, v in RES.items() if isinstance(v, dict) and "p" in v}
ps = np.array([v["p"] for v in fam.values()])
order = np.argsort(ps)
m = len(ps)
bh = np.empty(m)
prev = 1.0
for rank, i in enumerate(order[::-1]):
    rk = m - rank
    prev = min(prev, ps[i] * m / rk)
    bh[i] = prev
holm = np.empty(m)
run = 0
for rank, i in enumerate(order):
    run = max(run, min(1, ps[i] * (m - rank)))
    holm[i] = run
RES["_multiple_comparisons"] = {"n_tests_in_this_recheck": int(m),
                                "n_raw_p_lt_0.05": int((ps < 0.05).sum()),
                                "n_BH_q_lt_0.05": int((bh < 0.05).sum()),
                                "n_Holm_lt_0.05": int((holm < 0.05).sum()),
                                "survivors_BH": sorted([k for k, q_ in zip(fam, bh) if q_ < 0.05]),
                                "survivors_Holm": sorted([k for k, h in zip(fam, holm) if h < 0.05]),
                                "q_BH": {k: float(q_) for k, q_ in zip(fam, bh)}}
print(json.dumps({k: v for k, v in RES["_multiple_comparisons"].items() if k != "q_BH"}, indent=1))

json.dump(RES, open(f"{OUT}/recheck_results.json", "w"), indent=1, default=float)
D.drop(columns=[c for c in D.columns if c.startswith("bul|")]).to_pickle(f"{OUT}/cells.pkl")
log("done")
