#!/usr/bin/env python
"""Text-buffer hypothesis test: next-token entropy vs joint FVE, continuation-ness and
hallucination of Oracle Lens readouts (WorkspaceBench "Hallucination (chat)").

Hypothesis (user's "text buffer" idea): at low-entropy positions the next token is easy,
so the residual stream has spare room for non-continuation computation (thinking,
planning, summarising); at high-entropy positions it is busy with the continuation.
The activation reconstructor (AR) behind joint FVE was trained to predict the activation
that PRECEDES a text span from that span, so FVE = "how well is this activation explained
as the start of some continuation text". Predictions under the hypothesis:
  * FVE lower at low entropy (extra non-continuation content the AR cannot express)
  * readouts less continuation-like (less NEXT, more NONE / meta) at low entropy
  * both effects larger at deeper layers.

Inputs (read-only):
  entropy/site_entropy.jsonl      logit lens (final RMSNorm + lm_head) on the L60 / L52 rows
  entropy/continuation.jsonl      lexical continuation classes per bullet / readout
  entropy/validation_sample.json  120 readouts used to validate the classifier
  entropy/hand_labels/*           blind hand labels for those 120 readouts (3 readers)
  page/data/index.json, items/*.json   FVE, judge labels, spans/claims, reply text

Unit of analysis: a cell = (chat, read site, layer); one readout per setting.
Entropy is a site property (H_L60), shared by the 5 layers of a site.

Statistics
  exposure x     percentile rank of H_L60 among the 1,123 sites (0 = lowest, 1 = highest),
                 so a slope is "highest- minus lowest-entropy site" on a linear scale.
  specs          raw:   y ~ 1 + x
                 chat:  chat fixed effects (demeaned within chat) + x
                 full:  chat FE + x + site kind + relpos + relpos^2 + log1p(words left)
                        (relpos = char offset / reply length, UTF-16 units)
                 pooled: full, all 5 layers stacked, + layer dummies
  correlations   Spearman = Pearson on full-sample ranks; "within-chat" = on ranks
                 demeaned by chat.
  quintiles      H_L60 quintiles over sites; Q5 - Q1 (high minus low entropy).
  CIs            chat-level cluster bootstrap, 149 chats, B = 2000 multinomial
                 reweightings (the same draws for every statistic, so differences such as
                 L60 - L20 get joint CIs). 95% percentile intervals.
  Sign convention: every effect is "high-entropy minus low-entropy". The buffer
  hypothesis predicts > 0 for FVE and NEXT share, < 0 for NONE share.

Outputs: entropy/analysis_results.json (everything), entropy/entropy_page.json (compact,
for a page section). ENTROPY.md is written by hand from these numbers.

Run:  python -B analysis.py            (about 1 CPU-minute)
      python -B analysis.py candidates (prints example-site candidates only)
"""
from __future__ import annotations

import ast
import glob
import json
import math
import re
import sys
import time
import unicodedata
from collections import Counter, defaultdict

import numpy as np
from scipy import stats

BASE = "${OLENS_SCRATCH}/olens-bullet-fve"
ENT = f"{BASE}/entropy"
PAGE = f"{BASE}/page/data"
LINK = "https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#"
SETTINGS = ["capped_n1-n1", "best_n_exact-n32", "pooled_greedy_swap-n32"]
SHORT = ["Original", "Best of 32", "Combine 32"]
LAYERS = [20, 36, 44, 52, 60]
KINDS = ["clause", "sentence", "markup", "newline", "quote"]
CLASSES = ["NEXT", "LATER", "BEFORE", "NONE"]
B = 2000
SEED = 20261015
t0 = time.time()


def log(msg):
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def r4(v, d=4):
    if v is None:
        return None
    if isinstance(v, (list, tuple, np.ndarray)):
        return [r4(u, d) for u in v]
    v = float(v)
    return None if not math.isfinite(v) else round(v, d)


def u16len(s):
    return len(s.encode("utf-16-le")) // 2


# ======================================================================= load sites
site_rows = [json.loads(l) for l in open(f"{ENT}/site_entropy.jsonl")]
idx = json.load(open(f"{PAGE}/index.json"))
item_ids = [it["id"] for it in idx["items"]]
G = len(item_ids)
chat_of = {iid: j for j, iid in enumerate(item_ids)}

items = {}
for iid in item_ids:
    items[iid] = json.load(open(f"{PAGE}/items/{iid}.json"))

sites = sorted(((r["item_id"], int(r["pos"])) for r in site_rows), key=lambda t: (chat_of[t[0]], t[1]))
S = len(sites)
sidx = {s: j for j, s in enumerate(sites)}
ent = {(r["item_id"], int(r["pos"])): r for r in site_rows}

# site-level arrays
s_chat = np.array([chat_of[s[0]] for s in sites])
s_kind = np.array([KINDS.index(ent[s]["site_kind"]) for s in sites])
s_tok = [ent[s]["token"] for s in sites]
H60 = np.array([ent[s]["H_L60"] for s in sites], float)
H52 = np.array([ent[s]["H_L52"] for s in sites], float)
PTOP = np.array([ent[s]["p_top1"] for s in sites], float)
SURP = np.array([np.nan if ent[s]["surprisal_next_L60"] is None else ent[s]["surprisal_next_L60"]
                 for s in sites], float)
RANKN = np.array([np.nan if ent[s]["rank_next"] is None else ent[s]["rank_next"] for s in sites], float)
TOP1OK = np.array([np.nan if ent[s]["next_token"] is None else float(ent[s]["top1_correct"]) for s in sites])

# relative position (char / reply length, UTF-16 units like the page offsets)
site_char = {}
for iid in item_ids:
    for st in items[iid]["item"]["sites"]:
        site_char[(iid, int(st["pos"]))] = int(st["char"])
RELPOS = np.array([site_char[s] / u16len(items[s[0]]["item"]["response"]) for s in sites])
RELPOS_TOK = np.array([ent[s]["rel_pos"] / ent[s]["resp_len"] for s in sites])

# ======================================================================= load readouts
cont = {}  # (setting, k) -> readout row (with bullets)
for line in open(f"{ENT}/continuation.jsonl"):
    r = json.loads(line)
    cont[(r["setting"], r["k"])] = r
WORDS_AFTER = np.array([cont[("capped_n1-n1", f"{s[0]}.L20.p{s[1]}")]["n_words_after"] for s in sites], float)
I0 = np.array([cont[("capped_n1-n1", f"{s[0]}.L20.p{s[1]}")]["i0"] for s in sites], float)

cells = idx["cells"]
NC = len(cells)
c_site = np.array([sidx[(item_ids[c["i"]], int(c["p"]))] for c in cells])
c_layer = np.array([c["L"] for c in cells])
c_chat = s_chat[c_site]
c_key = [c["k"] for c in cells]

# ----------------------------------------------------------------- error proxies
NUM_RE = re.compile(r"\d[\d,.]*\d|\d")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
SENT_SPLIT = re.compile(r"(?<=[.!?:;])\s+|\n+|^\s*[-*#>]+\s*")
NAME_SKIP = {"I", "AI", "OK", "Ok", "The", "A", "An"}


def norm_num(t):
    return t.strip(".,").replace(",", "")


def ctx_sets(iid):
    it = items[iid]["item"]
    txt = unicodedata.normalize("NFKC", it["prompt"] + "\n" + it["response"])
    nums = {norm_num(m) for m in NUM_RE.findall(txt)}
    words = {w.lower().strip("'’-") for w in WORD_RE.findall(txt)}
    return nums, words


CTX = {iid: ctx_sets(iid) for iid in item_ids}


def novelty(iid, bullets_text):
    nums, words = CTX[iid]
    has_num = nov_num = nov_name = 0
    for bt in bullets_text:
        bt = unicodedata.normalize("NFKC", bt)
        for m in NUM_RE.findall(bt):
            has_num = 1
            if norm_num(m) not in nums:
                nov_num = 1
        for sent in SENT_SPLIT.split(bt):
            toks = WORD_RE.findall(sent or "")
            for t in toks[1:]:
                if (t[0].isupper() and t not in NAME_SKIP and not t.startswith(("I'", "I’"))
                        and t.lower().strip("'’-") not in words):
                    nov_name = 1
    return has_num, nov_num, nov_name


# per setting, per cell outcomes
OUT_NAMES = ["fve", "halluc", "consistent", "offtopic", "NEXT", "LATER", "BEFORE", "NONE",
             "cont_excess", "cont_mean", "cont_score", "meta", "any_meta", "n_wrong", "true_share",
             "has_num", "novel_num", "novel_name"]
Y = {s: {o: np.full(NC, np.nan) for o in OUT_NAMES} for s in SETTINGS}
for ci, c in enumerate(cells):
    iid = item_ids[c["i"]]
    icell = items[iid]["cells"][c["k"]]
    for j, st in enumerate(SETTINGS):
        sv = c["s"][j]
        y = Y[st]
        y["fve"][ci] = sv["f"] if sv["f"] is not None else np.nan
        lab = sv["c"]
        if lab != 4:  # 4 = empty readout (3-4 per setting): excluded from label rates
            y["halluc"][ci] = float(lab == 1)
            y["consistent"][ci] = float(lab == 0)
            y["offtopic"][ci] = float(lab == 2)
        cr = cont[(st, c["k"])]
        if cr["n_scorable"] > 0:
            for cl in CLASSES:
                y[cl][ci] = cr["shares"][cl]
            y["cont_excess"][ci] = np.nan if cr["cont_excess"] is None else cr["cont_excess"]
            y["cont_mean"][ci] = cr["cont_mean"]
            y["cont_score"][ci] = cr["cont_score"]
        if cr["n_bullets"] > 0:
            y["meta"][ci] = cr["n_meta"] / cr["n_bullets"]
            y["any_meta"][ci] = float(cr["n_meta"] > 0)
            hn, nn, nm = novelty(iid, [b["text"] for b in cr["bullets"]])
            y["has_num"][ci], y["novel_num"][ci], y["novel_name"][ci] = hn, nn, nm
        sd = icell["settings"][st]
        nw = sum(1 for sp in sd.get("spans", []) if sp["type"] == "wrong" and sp.get("verified"))
        ntrue = sum(1 for cl in sd.get("claims", []) if cl.get("counted_as") == "true")
        nunv = sum(1 for cl in sd.get("claims", []) if cl.get("counted_as") == "unverifiable")
        if lab != 4:
            y["n_wrong"][ci] = nw
            den = ntrue + nunv + nw
            y["true_share"][ci] = ntrue / den if den else np.nan
log(f"loaded {S} sites, {NC} cells, {G} chats")

# ======================================================================= stats engine
rng = np.random.default_rng(SEED)
W = rng.multinomial(G, np.full(G, 1.0 / G), size=B).astype(float)  # (B, G)


def demean(M, g):
    M = np.asarray(M, float)
    two = M.ndim == 1
    if two:
        M = M[:, None]
    sums = np.zeros((G, M.shape[1]))
    np.add.at(sums, g, M)
    cnt = np.bincount(g, minlength=G).astype(float)
    out = M - (sums / np.maximum(cnt, 1)[:, None])[g]
    return out[:, 0] if two else out


def rankpct(v):
    v = np.asarray(v, float)
    out = np.full(len(v), np.nan)
    m = np.isfinite(v)
    out[m] = (stats.rankdata(v[m]) - 1) / (m.sum() - 1)
    return out


def ci(draws):
    d = np.asarray(draws)
    d = d[np.isfinite(d)]
    return [float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))]


def ols(y, X, g):
    """Point estimate + bootstrap draws of all coefficients (cluster bootstrap by chat)."""
    m = np.isfinite(y) & np.isfinite(X).all(1)
    y, X, g = y[m], X[m], g[m]
    p = X.shape[1]
    XtX = np.zeros((G, p, p))
    Xty = np.zeros((G, p))
    np.add.at(XtX, g, X[:, :, None] * X[:, None, :])
    np.add.at(Xty, g, X * y[:, None])
    ridge = 1e-9 * np.eye(p)
    beta = np.linalg.solve(XtX.sum(0) + ridge, Xty.sum(0))
    A = np.einsum("bg,gij->bij", W, XtX) + ridge
    c = np.einsum("bg,gi->bi", W, Xty)
    bb = np.linalg.solve(A, c[..., None])[..., 0]
    return beta, bb, int(m.sum())


def corr(x, y, g, within):
    m = np.isfinite(x) & np.isfinite(y)
    x, y, g = rankpct(x[m]), rankpct(y[m]), g[m]
    if within:
        x, y = demean(x, g), demean(y, g)
    cols = np.stack([np.ones_like(x), x, y, x * x, y * y, x * y], 1)
    Sg = np.zeros((G, 6))
    np.add.at(Sg, g, cols)

    def r_of(T):
        n, sx, sy, sxx, syy, sxy = [T[..., i] for i in range(6)]
        if within:
            return sxy / np.sqrt(sxx * syy)
        cov = sxy - sx * sy / n
        return cov / np.sqrt((sxx - sx ** 2 / n) * (syy - sy ** 2 / n))

    return float(r_of(Sg.sum(0))), r_of(W @ Sg)


def binned(xbin, y, g, nb, within=False):
    m = np.isfinite(y) & (xbin >= 0)
    yy = y[m]
    if within:
        yy = demean(yy, g[m]) + np.nanmean(yy)
    Sy = np.zeros((G, nb))
    N = np.zeros((G, nb))
    np.add.at(Sy, (g[m], xbin[m]), yy)
    np.add.at(N, (g[m], xbin[m]), 1)
    pt = Sy.sum(0) / N.sum(0)
    bt = (W @ Sy) / (W @ N)
    return pt, bt, N.sum(0).astype(int)


# design pieces (site level)
KIND_D = np.stack([(s_kind == k).astype(float) for k in range(1, len(KINDS))], 1)  # vs clause
CTRL_SITE = np.column_stack([KIND_D, RELPOS, RELPOS ** 2, np.log1p(WORDS_AFTER)])
CTRL_NAMES = [f"kind_{k}" for k in KINDS[1:]] + ["relpos", "relpos2", "log1p_words_after"]

EXPOSURES = {
    "H": rankpct(H60),               # main
    "surprisal": rankpct(SURP),     # sec. 6
    "H_L52": rankpct(H52),
    "logH": (np.log(H60 + 1e-3) - np.log(H60 + 1e-3).mean()) / np.log(H60 + 1e-3).std(),
}
QCUTS = np.quantile(H60, [0.2, 0.4, 0.6, 0.8])
HQ = np.searchsorted(QCUTS, H60, side="right")  # 0..4, site level
SQ = np.full(S, -1)
mS = np.isfinite(SURP)
SQ[mS] = np.searchsorted(np.quantile(SURP[mS], [0.2, 0.4, 0.6, 0.8]), SURP[mS], side="right")


def design(rows_site, x_site, spec, extra=None, layer_rows=None):
    """X for cells whose site indices are rows_site. x first; FE by demeaning."""
    g = s_chat[rows_site]
    x = x_site[rows_site][:, None]
    cols = [x]
    if spec in ("full", "pooled"):
        cols.append(CTRL_SITE[rows_site])
    if extra is not None:
        cols.append(extra if extra.ndim == 2 else extra[:, None])
    if spec == "pooled":
        cols.append(np.stack([(layer_rows == L).astype(float) for L in LAYERS[1:]], 1))
    X = np.column_stack(cols)
    if spec == "raw":
        return np.column_stack([X, np.ones(len(X))]), g
    return X, g


def fit_effect(y_cells, cell_mask, x_site, spec, extra=None):
    rows = np.where(cell_mask)[0]
    X, g = design(c_site[rows], x_site, spec,
                  None if extra is None else extra[rows], c_layer[rows])
    y = y_cells[rows]
    if spec != "raw":
        m = np.isfinite(y) & np.isfinite(X).all(1)
        y = np.where(m, y, np.nan)
        Xd = np.full_like(X, np.nan)
        Xd[m] = demean(X[m], g[m])
        yd = np.full_like(y, np.nan)
        yd[m] = demean(y[m], g[m])
        X, y = Xd, yd
    beta, bb, n = ols(y, X, g)
    return beta, bb, n


def summarize(beta, bb, j=0):
    return {"b": r4(beta[j]), "ci": r4(ci(bb[:, j]))}


# ======================================================================= analyses
R = {"meta": {}}
R["meta"] = {
    "n_sites": S, "n_cells": NC, "n_chats": G, "B": B, "seed": SEED,
    "H_quintile_cuts": r4(QCUTS),
    "relpos_char_vs_token_spearman": r4(stats.spearmanr(RELPOS, RELPOS_TOK)[0]),
    "exposure": "percentile rank of H_L60 over the 1,123 sites; slopes = highest minus lowest entropy site",
    "sign": "all effects are high-entropy minus low-entropy",
}


def outcome_block(o, exposures=("H",), specs=("raw", "chat", "full"), extra=None, qbins=HQ):
    """Per setting x layer: Spearman (pooled, within-chat), quintile means, slopes."""
    res = {}
    for st, sh in zip(SETTINGS, SHORT):
        res[sh] = {}
        draws = {}
        for L in LAYERS + ["all"]:
            mask = (c_layer == L) if L != "all" else np.ones(NC, bool)
            y = Y[st][o]
            ent_ = {}
            for ex in exposures:
                xs = EXPOSURES[ex]
                e = {}
                if L != "all":
                    xc = xs[c_site[mask]]
                    r, rb = corr(xc, y[mask], c_chat[mask], False)
                    rw, rwb = corr(xc, y[mask], c_chat[mask], True)
                    e["rho"], e["rho_ci"] = r4(r), r4(ci(rb))
                    e["rho_within"], e["rho_within_ci"] = r4(rw), r4(ci(rwb))
                    for spec in specs:
                        beta, bb, n = fit_effect(y, mask, xs, spec, extra)
                        e[spec] = summarize(beta, bb)
                        e["n"] = n
                        draws[(ex, spec, L)] = bb[:, 0]
                else:
                    beta, bb, n = fit_effect(y, mask, xs, "pooled", extra)
                    e["pooled"] = summarize(beta, bb)
                    e["n"] = n
                    draws[(ex, "pooled", "all")] = bb[:, 0]
                ent_[ex] = e
            if L != "all" and qbins is not None:
                xb = qbins[c_site[mask]]
                pt, bt, nn = binned(xb, y[mask], c_chat[mask], 5)
                ptw, btw, _ = binned(xb, y[mask], c_chat[mask], 5, within=True)
                ent_["quintiles"] = {"mean": r4(pt), "within_chat_mean": r4(ptw), "n": nn.tolist(),
                                     "q5_minus_q1": r4(pt[4] - pt[0]), "q5_minus_q1_ci": r4(ci(bt[:, 4] - bt[:, 0])),
                                     "within_q5_minus_q1": r4(ptw[4] - ptw[0]),
                                     "within_q5_minus_q1_ci": r4(ci(btw[:, 4] - btw[:, 0]))}
            res[sh][str(L)] = ent_
        # deeper vs shallower: L60 - L20 slope (full spec, main exposure)
        for ex in exposures:
            if (ex, "full", 60) in draws:
                d = draws[(ex, "full", 60)] - draws[(ex, "full", 20)]
                pt = res[sh]["60"][ex]["full"]["b"] - res[sh]["20"][ex]["full"]["b"]
                res[sh][f"L60_minus_L20_{ex}_full"] = {"b": r4(pt), "ci": r4(ci(d))}
    return res


log("1. entropy vs FVE")
R["fve_vs_H"] = outcome_block("fve", exposures=("H", "logH", "H_L52"))

log("2. entropy vs continuation-ness")
R["cont_vs_H"] = {o: outcome_block(o, specs=("raw", "full"))
                  for o in ["NEXT", "NONE", "BEFORE", "LATER", "cont_excess", "cont_mean", "meta"]}

log("3. continuation vs FVE, and mediation")
R["fve_vs_cont"] = {}
R["mediation"] = {}
for st, sh in zip(SETTINGS, SHORT):
    R["fve_vs_cont"][sh] = {}
    R["mediation"][sh] = {}
    for L in LAYERS + ["all"]:
        mask = (c_layer == L) if L != "all" else np.ones(NC, bool)
        spec = "full" if L != "all" else "pooled"
        out = {}
        for cm in ["NEXT", "cont_excess", "NONE"]:
            ycont = Y[st][cm]
            fve = Y[st]["fve"]
            valid = mask & np.isfinite(ycont) & np.isfinite(fve)
            r, rb = corr(ycont[valid], fve[valid], c_chat[valid], False)
            rw, rwb = corr(ycont[valid], fve[valid], c_chat[valid], True)
            # continuation measure in natural units (share 0..1 or U score); columns are
            # x, controls..., extra, [layer dummies], so the extra regressor sits at jc
            b0, bb0, _ = fit_effect(fve, valid, EXPOSURES["H"], spec)                 # total effect
            b1, bb1, _ = fit_effect(fve, valid, EXPOSURES["H"], spec, extra=ycont)    # direct effect
            jc = 1 + CTRL_SITE.shape[1]
            bc, bbc, _ = fit_effect(ycont, valid, EXPOSURES["H"], spec)               # H -> cont
            out[cm] = {
                "rho_cont_fve": r4(r), "rho_cont_fve_ci": r4(ci(rb)),
                "rho_within": r4(rw), "rho_within_ci": r4(ci(rwb)),
                "fve_per_unit_cont_full": {"b": r4(b1[jc]), "ci": r4(ci(bb1[:, jc]))},
                "H_total": summarize(b0, bb0), "H_direct": summarize(b1, bb1),
                "H_to_cont": summarize(bc, bbc),
                "direct_minus_total": {"b": r4(b1[0] - b0[0]), "ci": r4(ci(bb1[:, 0] - bb0[:, 0]))},
            }
        R["mediation"][sh][str(L)] = out
        R["fve_vs_cont"][sh][str(L)] = {cm: {k: out[cm][k] for k in
                                             ["rho_cont_fve", "rho_cont_fve_ci", "rho_within", "rho_within_ci",
                                              "fve_per_unit_cont_full"]} for cm in out}

# FVE by continuation quintile (cont_excess), per setting pooled over layers, within layer demeaned
R["fve_by_cont_quintile"] = {}
for st, sh in zip(SETTINGS, SHORT):
    ce = Y[st]["cont_excess"]
    fve = Y[st]["fve"]
    row = {}
    for L in LAYERS:
        mask = (c_layer == L) & np.isfinite(ce) & np.isfinite(fve)
        q = np.full(NC, -1)
        q[mask] = np.searchsorted(np.quantile(ce[mask], [0.2, 0.4, 0.6, 0.8]), ce[mask], side="right")
        pt, bt, nn = binned(q[mask], fve[mask], c_chat[mask], 5)
        row[str(L)] = {"fve": r4(pt), "q5_minus_q1": r4(pt[4] - pt[0]), "ci": r4(ci(bt[:, 4] - bt[:, 0]))}
    R["fve_by_cont_quintile"][sh] = row

log("4. entropy vs hallucination and error proxies")
R["halluc_vs_H"] = {o: outcome_block(o, specs=("raw", "full"))
                    for o in ["halluc", "consistent", "offtopic", "n_wrong", "true_share",
                              "has_num", "novel_num", "novel_name"]}

log("5. site kinds")
sk = {"by_kind": {}, "fve_gap_vs_clause": {}}
for k, kn in enumerate(KINDS):
    m = s_kind == k
    pt, bt, nn = binned(np.where(m, 0, -1), H60, s_chat, 1)
    sk["by_kind"][kn] = {"n_sites": int(m.sum()), "H_mean": r4(H60[m].mean()), "H_mean_ci": r4(ci(bt[:, 0])),
                         "H_median": r4(np.median(H60[m])), "share_H_below_0.1": r4((H60[m] < 0.1).mean()),
                         "surprisal_mean": r4(np.nanmean(SURP[m])),
                         "share_in_H_Q1": r4((HQ[m] == 0).mean()), "share_in_H_Q5": r4((HQ[m] == 4).mean())}
# token-level groups
tokgroups = {"full stop '.'": lambda t: t.strip() == ".", "comma ','": lambda t: t.strip() == ",",
             "'!' or '?'": lambda t: t.strip() in ("!", "?"), "colon ':'": lambda t: t.strip() == ":"}
sk["by_token"] = {}
for name, fn in tokgroups.items():
    m = np.array([fn(t) for t in s_tok])
    fv = {sh: r4(np.nanmean(Y[st]["fve"][m[c_site]])) for st, sh in zip(SETTINGS, SHORT)}
    sk["by_token"][name] = {"n_sites": int(m.sum()), "H_mean": r4(H60[m].mean()), "H_median": r4(np.median(H60[m])),
                            "fve_mean_all_layers": fv}
# Does entropy explain the site-kind FVE gaps? FVE ~ kind (+chat FE, relpos, words left, layer)
# with and without H. Gap = kind coefficient vs clause.
for st, sh in zip(SETTINGS, SHORT):
    fve = Y[st]["fve"]
    out = {}
    for withH in (False, True):
        rows = np.arange(NC)
        g = c_chat
        cols = [CTRL_SITE[c_site]]
        names = list(CTRL_NAMES)
        if withH:
            cols.append(EXPOSURES["H"][c_site][:, None])
            names.append("H")
        cols.append(np.stack([(c_layer == L).astype(float) for L in LAYERS[1:]], 1))
        X = np.column_stack(cols)
        Xd, yd = demean(X, g), demean(fve, g)
        beta, bb, n = ols(yd, Xd, g)
        out["with_H" if withH else "without_H"] = {KINDS[1 + j]: summarize(beta, bb, j) for j in range(4)}
        if withH:
            out["H_coef"] = summarize(beta, bb, names.index("H"))
    # full stop vs comma (raw, all layers): FVE gap and H gap
    sk["fve_gap_vs_clause"][sh] = out
# per site kind: entropy-FVE spearman (Original, each layer) for heterogeneity
sk["within_kind_rho_fve_H"] = {}
for st, sh in zip(SETTINGS, SHORT):
    sk["within_kind_rho_fve_H"][sh] = {}
    for k, kn in enumerate(KINDS):
        row = {}
        for L in LAYERS:
            m = (c_layer == L) & (s_kind[c_site] == k)
            r, rb = corr(EXPOSURES["H"][c_site[m]], Y[st]["fve"][m], c_chat[m], False)
            row[str(L)] = [r4(r), r4(ci(rb))]
        sk["within_kind_rho_fve_H"][sh][kn] = row
R["site_kinds"] = sk

log("6. surprisal of the actual next token")
R["surprisal"] = {o: outcome_block(o, exposures=("surprisal",), specs=("raw", "full"), qbins=SQ)
                  for o in ["fve", "NEXT", "NONE", "cont_excess", "halluc", "novel_num", "novel_name"]}
R["surprisal_meta"] = {
    "spearman_H_surprisal": r4(stats.spearmanr(H60[mS], SURP[mS])[0]),
    "surprisal_quintile_cuts": r4(np.quantile(SURP[mS], [0.2, 0.4, 0.6, 0.8])),
}
# joint model: H and surprisal together (full spec), FVE / NEXT / halluc, Original+Best
R["joint_H_surprisal"] = {}
for st, sh in zip(SETTINGS, SHORT):
    R["joint_H_surprisal"][sh] = {}
    for o in ["fve", "NEXT", "halluc"]:
        row = {}
        for L in [20, 44, 60, "all"]:
            mask = ((c_layer == L) if L != "all" else np.ones(NC, bool)) & np.isfinite(SURP[c_site])
            spec = "full" if L != "all" else "pooled"
            beta, bb, n = fit_effect(Y[st][o], mask, EXPOSURES["H"], spec, extra=EXPOSURES["surprisal"][c_site])
            jc = 1 + CTRL_SITE.shape[1]
            row[str(L)] = {"H": summarize(beta, bb, 0), "surprisal": summarize(beta, bb, jc), "n": n}
        R["joint_H_surprisal"][sh][o] = row

log("6b. robustness: near-deterministic sites, next-token type, per-kind slopes")
NT = [ent[s]["next_type"] for s in sites]
NT_LEVELS = [t for t, _ in Counter(NT).most_common() if t != "word_space"]
NEXTTYPE_D = np.stack([np.array([t == lv for t in NT], float) for lv in NT_LEVELS], 1)
EXPOSURES["H_ge_0.1"] = (H60 >= 0.1).astype(float)   # 1 = not near-deterministic
EXPOSURES["H_ge_0.5"] = (H60 >= 0.5).astype(float)
rob = {"next_type_levels": ["word_space (ref)"] + NT_LEVELS,
       "n_sites_H_below_0.1": int((H60 < 0.1).sum()), "n_sites_H_below_0.5": int((H60 < 0.5).sum())}
for st, sh in zip(SETTINGS, SHORT):
    rr = {}
    for L in LAYERS + ["all"]:
        mask = (c_layer == L) if L != "all" else np.ones(NC, bool)
        spec = "full" if L != "all" else "pooled"
        row = {}
        fve = Y[st]["fve"]
        for ex in ["H_ge_0.1", "H_ge_0.5"]:
            beta, bb, n = fit_effect(fve, mask, EXPOSURES[ex], spec)
            row[ex] = summarize(beta, bb)
        for ex in ["H", "surprisal"]:
            beta, bb, n = fit_effect(fve, mask, EXPOSURES[ex], spec, extra=NEXTTYPE_D[c_site])
            row[f"{ex}_plus_nexttype"] = summarize(beta, bb)
        # where is the near-deterministic dip? drop block boundaries / short tails
        boundary = np.array([t in ("newline", "none") for t in NT])  # next token is a newline or end of reply
        for nm, keep in [("H_ge_0.1_no_boundary", ~boundary), ("H_ge_0.1_words_after_ge40", WORDS_AFTER >= 40),
                         ("H_ge_0.1_next_is_word", np.array([t in ("word_space", "word_nospace") for t in NT]))]:
            beta, bb, n = fit_effect(fve, mask & keep[c_site], EXPOSURES["H_ge_0.1"], spec)
            row[nm] = summarize(beta, bb)
            row[nm]["n_low_sites"] = int(((H60 < 0.1) & keep).sum())
            beta, bb, n = fit_effect(fve, mask & keep[c_site], EXPOSURES["H"], spec)
            row[nm.replace("H_ge_0.1", "H_rank")] = summarize(beta, bb)
        mS_c = mask & np.isfinite(SURP[c_site])
        beta, bb, n = fit_effect(fve, mS_c, EXPOSURES["H"], spec,
                                 extra=np.column_stack([EXPOSURES["surprisal"][c_site], NEXTTYPE_D[c_site]]))
        row["joint_nexttype"] = {"H": summarize(beta, bb, 0), "surprisal": summarize(beta, bb, 1 + CTRL_SITE.shape[1])}
        rr[str(L)] = row
    # per-kind slopes (full spec), FVE
    pk = {}
    for k, kn in enumerate(KINDS):
        pk[kn] = {}
        for L in LAYERS + ["all"]:
            mask = ((c_layer == L) if L != "all" else np.ones(NC, bool)) & (s_kind[c_site] == k)
            beta, bb, n = fit_effect(Y[st]["fve"], mask, EXPOSURES["H"], "full" if L != "all" else "pooled")
            pk[kn][str(L)] = summarize(beta, bb)
    rr["per_kind_full_slope"] = pk
    # FVE by H decile, within-chat demeaned, pooled over layers after removing layer means
    fve = Y[st]["fve"].copy()
    for L in LAYERS:
        m = c_layer == L
        fve[m] = fve[m] - np.nanmean(fve[m])
    dec = np.searchsorted(np.quantile(H60, np.linspace(0.1, 0.9, 9)), H60, side="right")
    pt, bt, nn = binned(dec[c_site], fve, c_chat, 10, within=True)
    rr["fve_by_H_decile_within_chat_layer_centred"] = {"mean": r4(pt), "ci": [r4(ci(bt[:, j])) for j in range(10)],
                                                       "decile_upper_H": r4(np.quantile(H60, np.linspace(0.1, 1, 10)))}
    rob[sh] = rr
# FVE at near-deterministic sites split by what comes next (raw means, Original / Best of 32, L36-L60 pooled)
lowsplit = {}
for nm, sel in [("next newline (block boundary)", lambda t: t == "newline"), ("end of reply", lambda t: t == "none"),
                ("next is a word", lambda t: t in ("word_space", "word_nospace")),
                ("other (markup, code fence, punct)", lambda t: t not in ("newline", "none", "word_space", "word_nospace"))]:
    m_site = np.array([sel(t) for t in NT])
    row = {"n_low_sites": int((m_site & (H60 < 0.1)).sum()), "n_other_sites": int((m_site & (H60 >= 0.1)).sum())}
    for st, sh in zip(SETTINGS[:2], SHORT[:2]):
        deep = c_layer >= 36
        lo = deep & m_site[c_site] & (H60[c_site] < 0.1)
        hi = deep & m_site[c_site] & (H60[c_site] >= 0.1)
        row[sh] = {"fve_low": r4(np.nanmean(Y[st]["fve"][lo]), 3), "fve_rest": r4(np.nanmean(Y[st]["fve"][hi]), 3)}
    lowsplit[nm] = row
rob["near_deterministic_split_L36_L60"] = lowsplit
R["robustness"] = rob

log("7. hand-labelled validation sample")
val = json.load(open(f"{ENT}/validation_sample.json"))["readouts"]


def norm_lab(t):
    t = t.split(":")[0].strip()
    m = re.match(r"NA\((\w+)\)", t)
    if m:
        t = m.group(1)
    sub = None
    if t.startswith("NONE-"):
        sub = {"inv": "invented", "meta": "meta", "gen": "generic", "plan": "planning"}.get(t[5:], t[5:])
        t = "NONE"
    code = {"N": "NEXT", "B": "BEFORE", "L": "LATER", "Xi": "NONE", "Xm": "NONE", "Xp": "NONE"}
    if t in code:
        sub = {"Xi": "invented", "Xm": "meta", "Xp": "planning"}.get(t)
        t = code[t]
    return t, sub


hand = defaultdict(dict)  # idx -> b -> (label, subtype)
for line in open(f"{ENT}/hand_labels/reader_0_39.txt"):
    if line.startswith("#") or not line.strip():
        continue
    p = line.split()
    lab, sub = norm_lab(p[2])
    if lab == "NONE" and len(p) > 4:
        sub = p[4]
    hand[int(p[0])][int(p[1])] = (lab, sub)
for line in open(f"{ENT}/hand_labels/reader_40_79.txt"):
    p = line.split("#")[0].split()
    if len(p) < 3:
        continue
    hand[int(p[0])][int(p[1])] = norm_lab(p[2])
src = open(f"{ENT}/hand_labels/reader_80_119.py").read()
Ld = ast.literal_eval(src[src.index("{"):src.rindex("}") + 1])
for i, s in Ld.items():
    for b, t in enumerate(s.split()):
        hand[int(i)][b] = norm_lab(t)
hrows = []
for i, r in enumerate(val):
    item, Ls, ps = r["k"].rsplit(".", 2)
    site = sidx[(item, int(ps[1:]))]
    labs = [hand[i][b] for b in sorted(hand[i])]
    cls_ = [b["cls"] for b in r["bullets"]]
    hrows.append({"i": i, "k": r["k"], "setting": r["setting_short"], "site": site, "chat": int(s_chat[site]),
                  "H": float(H60[site]), "Hq": int(HQ[site]), "n": len(labs),
                  "h_next": np.mean([l[0] == "NEXT" for l in labs]),
                  "h_none": np.mean([l[0] == "NONE" for l in labs]),
                  "h_none_noninvented": np.mean([l[0] == "NONE" and l[1] not in ("invented", None) for l in labs]),
                  "h_contshape": np.mean([l[0] == "NEXT" or (l[0] == "NONE" and l[1] in ("invented", None))
                                          for l in labs]),
                  "c_next": np.mean([c == "NEXT" for c in cls_]) if cls_ else np.nan,
                  "c_none": np.mean([c == "NONE" for c in cls_]) if cls_ else np.nan,
                  "recall_next": (np.mean([c == "NEXT" for c, l in zip(cls_, labs) if l[0] == "NEXT"])
                                  if any(l[0] == "NEXT" for l in labs) else np.nan),
                  "subtypes": [l[1] for l in labs if l[0] == "NONE"]})
hx = np.array([h["H"] for h in hrows])
hg = np.array([h["chat"] for h in hrows])
hq3 = np.searchsorted(np.quantile(H60, [1 / 3, 2 / 3]), hx, side="right")
hv = {"n_readouts": len(hrows), "n_bullets": int(sum(h["n"] for h in hrows)),
      "none_subtypes": dict(Counter(s for h in hrows for s in h["subtypes"])),
      "tercile_cuts_H": r4(np.quantile(H60, [1 / 3, 2 / 3]))}
hv["noninvented_none_examples"] = [{"k": h["k"], "setting": h["setting"], "H": r4(h["H"], 3),
                                    "subtypes": h["subtypes"]} for h in hrows
                                   if any(s not in ("invented", None) for s in h["subtypes"])]
hv["by_setting_h_next"] = {sname: r4(np.mean([h["h_next"] for h in hrows if h["setting"] == sname]))
                           for sname in sorted({h["setting"] for h in hrows})}
for key in ["h_next", "h_none", "h_contshape", "c_next", "c_none", "recall_next"]:
    yv = np.array([h[key] for h in hrows], float)
    r, rb = corr(hx, yv, hg, False)
    pt, bt, nn = binned(hq3, yv, hg, 3)
    hv[key] = {"rho_H": r4(r), "rho_H_ci": r4(ci(rb)), "tercile_mean": r4(pt), "tercile_n": nn.tolist(),
               "t3_minus_t1": r4(pt[2] - pt[0]), "t3_minus_t1_ci": r4(ci(bt[:, 2] - bt[:, 0]))}
R["hand_labels"] = hv

log("8. descriptive: layer x entropy quintile FVE table, labels by quintile")
R["descriptive"] = {"fve_by_layer_quintile": {}, "label_by_quintile": {}}
for st, sh in zip(SETTINGS, SHORT):
    tab = {}
    for L in LAYERS:
        m = c_layer == L
        tab[str(L)] = r4([np.nanmean(Y[st]["fve"][m & (HQ[c_site] == q)]) for q in range(5)])
    R["descriptive"]["fve_by_layer_quintile"][sh] = tab
    R["descriptive"]["label_by_quintile"][sh] = {
        o: r4([np.nanmean(Y[st][o][HQ[c_site] == q]) for q in range(5)]) for o in
        ["halluc", "consistent", "offtopic", "NEXT", "NONE", "BEFORE", "cont_excess", "meta", "novel_num", "novel_name"]}
# where does a bullet start? first word of the bullet vs the first 6 reply words after the site
AW_RE = re.compile(r"[a-z0-9]+")


def _words(s):
    return AW_RE.findall(unicodedata.normalize("NFKC", s).lower())


AFTER_WORDS = []
for s in sites:
    resp16 = items[s[0]]["item"]["response"].encode("utf-16-le")
    AFTER_WORDS.append(_words(resp16[2 * site_char[s]:].decode("utf-16-le"))[:6])
look = {}
for st, sh in zip(SETTINGS, SHORT):
    acc = defaultdict(lambda: [0, 0, 0])  # (L, q) -> [n, starts_w1, starts_w2..w6]
    for ci_, k in enumerate(c_key):
        si = c_site[ci_]
        aw = AFTER_WORDS[si]
        if len(aw) < 3:
            continue
        for b in cont[(st, k)]["bullets"]:
            bw = _words(b["text"])
            if not bw:
                continue
            a = acc[(int(c_layer[ci_]), int(HQ[si]))]
            a[0] += 1
            if bw[0] == aw[0]:
                a[1] += 1
            elif bw[0] in aw[1:6]:
                a[2] += 1
    look[sh] = {str(L): {"starts_next_word": r4([acc[(L, q)][1] / acc[(L, q)][0] for q in range(5)], 3),
                         "starts_2_to_6_words_ahead": r4([acc[(L, q)][2] / acc[(L, q)][0] for q in range(5)], 3)}
                for L in LAYERS}
R["descriptive"]["bullet_start_by_quintile"] = look
R["descriptive"]["H_quintile_mean_H"] = r4([H60[HQ == q].mean() for q in range(5)])
R["descriptive"]["H_quintile_top1_acc"] = r4([np.nanmean(TOP1OK[HQ == q]) for q in range(5)])
R["descriptive"]["H_quintile_kind_mix"] = {kn: r4([(s_kind[HQ == q] == k).mean() for q in range(5)])
                                           for k, kn in enumerate(KINDS)}
R["descriptive"]["H_quintile_relpos"] = r4([RELPOS[HQ == q].mean() for q in range(5)])
R["descriptive"]["H_quintile_words_after"] = r4([np.median(WORDS_AFTER[HQ == q]) for q in range(5)])

# ======================================================================= examples
def site_view(si):
    s = sites[si]
    e = ent[s]
    return {"token": e["token"], "kind": e["site_kind"], "H": r4(e["H_L60"], 3), "p_top1": r4(e["p_top1"], 3),
            "top5": [[t, r4(p, 3)] for t, p in e["top5"]], "next_token": e["next_token"],
            "surprisal": r4(e["surprisal_next_L60"], 2), "next_text": e["next_text8"],
            "relpos": r4(RELPOS[si], 2), "words_after": int(WORDS_AFTER[si])}


def readout_view(k, st):
    r = cont[(st, k)]
    return {"setting": SHORT[SETTINGS.index(st)], "fve": r["fve"], "label": r["label"],
            "bullets": [{"text": b["text"], "cls": b["cls"], "src": b["src"], "next": b["next"],
                         "before": b["before"], "meta": b["meta"]} for b in r["bullets"]]}


def candidates():
    st = "capped_n1-n1"
    rows = []
    for ci_, k in enumerate(c_key):
        si = c_site[ci_]
        r = cont[(st, k)]
        if r["n_scorable"] < 3:
            continue
        rows.append((k, si, c_layer[ci_], H60[si], r["fve"], r["shares"]["NEXT"], r["shares"]["NONE"],
                     r["n_meta"], r["label"], WORDS_AFTER[si]))
    print("low H (<0.15), NONE>=0.75 or meta, words_after>=40, L>=44")
    for x in sorted([r for r in rows if r[3] < 0.15 and (r[6] >= 0.75 or r[7] > 0) and r[9] >= 40 and r[2] >= 44],
                    key=lambda r: r[4])[:25]:
        print(" ", x[0], ent[sites[x[1]]]["token"].encode("unicode_escape").decode(), f"H={x[3]:.3f} fve={x[4]:.3f} "
              f"NEXT={x[5]:.2f} NONE={x[6]:.2f} meta={x[7]} {x[8]}")
    print("high H (>4), NEXT>=0.75, L>=44")
    for x in sorted([r for r in rows if r[3] > 4 and r[5] >= 0.75 and r[2] >= 44], key=lambda r: -r[4])[:25]:
        print(" ", x[0], ent[sites[x[1]]]["token"].encode("unicode_escape").decode(), f"H={x[3]:.3f} fve={x[4]:.3f} "
              f"NEXT={x[5]:.2f} NONE={x[6]:.2f} meta={x[7]} {x[8]}")
    print("counter: low H (<0.15), NEXT>=0.75, high fve, L>=44")
    for x in sorted([r for r in rows if r[3] < 0.15 and r[5] >= 0.75 and r[2] >= 44], key=lambda r: -r[4])[:15]:
        print(" ", x[0], ent[sites[x[1]]]["token"].encode("unicode_escape").decode(), f"H={x[3]:.3f} fve={x[4]:.3f} "
              f"NEXT={x[5]:.2f} NONE={x[6]:.2f} meta={x[7]} {x[8]}")
    print("counter: high H (>4), NONE>=0.75, L>=44, words_after>=40")
    for x in sorted([r for r in rows if r[3] > 4 and r[6] >= 0.75 and r[2] >= 44 and r[9] >= 40],
                    key=lambda r: r[4])[:15]:
        print(" ", x[0], ent[sites[x[1]]]["token"].encode("unicode_escape").decode(), f"H={x[3]:.3f} fve={x[4]:.3f} "
              f"NEXT={x[5]:.2f} NONE={x[6]:.2f} meta={x[7]} {x[8]}")
    print("meta bullets by H quintile (Original, all layers):",
          [int(np.nansum(Y[st]["any_meta"][HQ[c_site] == q])) for q in range(5)])


if len(sys.argv) > 1 and sys.argv[1] == "candidates":
    candidates()
    sys.exit(0)

# chosen after reading candidates (see ENTROPY.md); role, key, setting
EXAMPLES = json.load(open(f"{ENT}/examples_chosen.json")) if glob.glob(f"{ENT}/examples_chosen.json") else []
R["examples"] = []
for ex in EXAMPLES:
    k = ex["k"]
    item, Ls, ps = k.rsplit(".", 2)
    si = sidx[(item, int(ps[1:]))]
    R["examples"].append({"role": ex["role"], "k": k, "link": LINK + k, "layer": int(Ls[1:]), "note": ex.get("note", ""),
                          "site": site_view(si),
                          "fve_by_setting": {SHORT[j]: cont[(st, k)]["fve"] for j, st in enumerate(SETTINGS)},
                          "label_by_setting": {SHORT[j]: cont[(st, k)]["label"] for j, st in enumerate(SETTINGS)},
                          "readouts": [readout_view(k, st) for st in ex.get("settings", ["capped_n1-n1"])]})

json.dump(R, open(f"{ENT}/analysis_results.json", "w"), indent=1, ensure_ascii=False)
log("wrote analysis_results.json")

# ======================================================================= compact page json
def pick(block, sh, L, ex="H", spec="full"):
    e = block[sh][str(L)][ex]
    return {"rho": e["rho"], "rho_ci": e["rho_ci"], "rho_w": e["rho_within"], "rho_w_ci": e["rho_within_ci"],
            "b": e[spec]["b"], "b_ci": e[spec]["ci"]}


page = {
    "about": ("Text-buffer hypothesis check. Entropy = logit-lens (final norm + lm_head) next-token entropy of the "
              "layer-60 residual at the read site, a proxy for the model's own next-token uncertainty. Effects are "
              "high-entropy minus low-entropy: 'b' = slope on the entropy percentile rank (lowest to highest site) "
              "with chat fixed effects, site kind, relative position and words left as controls; rho = Spearman; "
              "rho_w = within-chat Spearman. 95% CIs from a chat-level bootstrap (149 chats, 2000 draws)."),
    "H_quintile_cuts": R["meta"]["H_quintile_cuts"],
    "H_quintile_mean": R["descriptive"]["H_quintile_mean_H"],
    "fve": {sh: {str(L): pick(R["fve_vs_H"], sh, L) for L in LAYERS} for sh in SHORT},
    "fve_quintiles": {sh: {str(L): R["fve_vs_H"][sh][str(L)]["quintiles"]["mean"] for L in LAYERS} for sh in SHORT},
    "fve_q5_minus_q1_within": {sh: {str(L): [R["fve_vs_H"][sh][str(L)]["quintiles"]["within_q5_minus_q1"],
                                             R["fve_vs_H"][sh][str(L)]["quintiles"]["within_q5_minus_q1_ci"]]
                                    for L in LAYERS} for sh in SHORT},
    "fve_pooled": {sh: R["fve_vs_H"][sh]["all"]["H"]["pooled"] for sh in SHORT},
    "fve_L60_minus_L20": {sh: R["fve_vs_H"][sh]["L60_minus_L20_H_full"] for sh in SHORT},
    "continuation": {o: {sh: {str(L): pick(R["cont_vs_H"][o], sh, L) for L in LAYERS} for sh in SHORT}
                     for o in ["NEXT", "NONE", "cont_excess", "meta"]},
    "continuation_pooled": {o: {sh: R["cont_vs_H"][o][sh]["all"]["H"]["pooled"] for sh in SHORT}
                            for o in ["NEXT", "NONE", "BEFORE", "cont_excess", "meta"]},
    "mediation_pooled": {sh: {cm: {k: R["mediation"][sh]["all"][cm][k] for k in
                                   ["H_total", "H_direct", "H_to_cont", "direct_minus_total", "rho_cont_fve"]}
                              for cm in ["NEXT", "cont_excess"]} for sh in SHORT},
    "halluc": {o: {sh: R["halluc_vs_H"][o][sh]["all"]["H"]["pooled"] for sh in SHORT}
               for o in ["halluc", "offtopic", "n_wrong", "novel_num", "novel_name"]},
    "halluc_by_quintile": {sh: R["descriptive"]["label_by_quintile"][sh]["halluc"] for sh in SHORT},
    "site_kinds": {kn: {k: R["site_kinds"]["by_kind"][kn][k] for k in ["n_sites", "H_mean", "H_mean_ci", "H_median"]}
                   for kn in KINDS},
    "sentence_gap": {sh: {"without_H": R["site_kinds"]["fve_gap_vs_clause"][sh]["without_H"]["sentence"],
                          "with_H": R["site_kinds"]["fve_gap_vs_clause"][sh]["with_H"]["sentence"]} for sh in SHORT},
    "surprisal": {o: {sh: R["surprisal"][o][sh]["all"]["surprisal"]["pooled"] for sh in SHORT}
                  for o in ["fve", "NEXT", "NONE", "halluc", "novel_num"]},
    "hand_labels": {k: R["hand_labels"][k] for k in ["n_readouts", "n_bullets", "none_subtypes", "h_next", "h_none",
                                                     "h_contshape", "c_next", "recall_next"]},
    "fve_decile_within": {sh: R["robustness"][sh]["fve_by_H_decile_within_chat_layer_centred"] for sh in SHORT[:2]},
    "near_deterministic": {sh: {L: {k: R["robustness"][sh][L][k] for k in
                                    ["H_ge_0.1", "H_ge_0.1_no_boundary", "H_ge_0.1_next_is_word"]}
                                for L in ["36", "52", "60", "all"]} for sh in SHORT[:2]},
    "near_deterministic_split": R["robustness"]["near_deterministic_split_L36_L60"],
    "per_kind_slope_pooled": {sh: {kn: R["robustness"][sh]["per_kind_full_slope"][kn]["all"] for kn in KINDS[:4]}
                              for sh in SHORT[:2]},
    "fve_vs_H_L52": {sh: {str(L): R["fve_vs_H"][sh][str(L)]["H_L52"]["full"] for L in LAYERS} for sh in SHORT[:2]},
    "surprisal_plus_nexttype_pooled": {sh: R["robustness"][sh]["all"]["surprisal_plus_nexttype"] for sh in SHORT},
    "joint_H_surprisal_nexttype_pooled": {sh: R["robustness"][sh]["all"]["joint_nexttype"] for sh in SHORT},
    "bullet_start_L60_original": R["descriptive"]["bullet_start_by_quintile"]["Original"]["60"],
    "headline": [
        "Buffer prediction: lower FVE at low-entropy sites, more so at deeper layers. Observed: FVE is flat across "
        "entropy (lowest- vs highest-entropy site differs by about 0.01 FVE, CI includes 0), against a 0.25 rise "
        "across layers. The effect does not grow with depth: the slope is slightly positive at L20-L36 and slightly "
        "negative at L60.",
        "The only buffer-like dip is at near-deterministic sites (H < 0.1 nats, 85 of 1,123): about 0.03 lower FVE. "
        "It sits mostly at about 10 block boundaries (a full stop before a paragraph break, the end of the reply). "
        "Where the next token is a word, the dip is about 0.",
        "Readouts are more continuation-like at low entropy, not less: NEXT share is 51% in the lowest-entropy fifth "
        "vs 36% in the highest at L60 (Original). Planning or meta bullets are about 1% at every entropy level.",
        "Sentence ends are high-entropy sites (mean 2.26 nats; full stops 2.44) yet have the lowest FVE. Adding "
        "entropy to the model leaves the sentence gap unchanged (-0.045 to -0.046).",
        "Entropy does not predict hallucination. The surprisal of the actual next token does predict FVE (+0.05 to "
        "+0.06); entropy does not.",
    ],
    "examples": [{"role": e["role"], "k": e["k"], "note": e["note"], "token": e["site"]["token"], "kind": e["site"]["kind"],
                  "H": e["site"]["H"], "top5": e["site"]["top5"][:3], "next_text": e["site"]["next_text"],
                  "fve": e["readouts"][0]["fve"], "label": e["readouts"][0]["label"],
                  "bullets": [[b["text"][:160], b["cls"]] for b in e["readouts"][0]["bullets"]]}
                 for e in R["examples"]],
}
json.dump(page, open(f"{ENT}/entropy_page.json", "w"), separators=(",", ":"), ensure_ascii=False)
log("wrote entropy_page.json")
