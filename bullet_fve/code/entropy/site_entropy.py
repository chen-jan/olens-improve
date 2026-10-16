"""Logit-lens next-token entropy at the 1,123 Hallucination (chat) read sites.

For each read site (item, pos) take the layer-60 (and layer-52) residual row
(decoder-block output of blocks[L], no final norm), apply Qwen3.6's final
RMSNorm (Qwen3_5RMSNorm: x * rsqrt(mean(x^2)+eps) * (1 + w), zero-centred w)
and the untied lm_head, all in float32 (softmax statistics in float64), and
record the predicted distribution for token pos+1.

Alignment: the activation at index pos has seen tokens 0..pos, so its lm_head
output predicts input_ids[pos+1]. The read token's own surprisal (predicted at
pos-1) cannot be computed: no activation exists at pos-1.

Read-only on all inputs; writes only into this directory.
"""
from __future__ import annotations

import json
import math
import os
import string
import time
import unicodedata
from collections import Counter, defaultdict

import numpy as np
import torch
from safetensors import safe_open
from scipy import stats
from tokenizers import Tokenizer

torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "8")))

OUT_DIR = "${OLENS_SCRATCH}/olens-bullet-fve/entropy"
SNAP = ("${OLENS_SCRATCH}/workspace/hf_cache/hub/models--Qwen--Qwen3.6-27B/"
        "snapshots/6a9e13bd6fc8f0983b9b99948120bc37f49c13e9")
MANIFEST = "${OLENS_COMPUTE_ROOT}/activations/core-v1/fresh_manifest_v2.json"
ACTS = "${OLENS_COMPUTE_ROOT}/activations/core-v1/activations.safetensors"
PAGE = "${OLENS_SCRATCH}/olens-bullet-fve/page/data"
LINK = "https://claude.ai/artifact/Kbc6QXbwvTGD2SCdgG18J3#"
LAYERS = (60, 52)
SETTINGS = ["capped_n1-n1", "best_n_exact-n32", "pooled_greedy_swap-n32"]
SHORT = ["Original", "Best of 32", "Combine 32"]
LABELS = ["consistent", "hallucinated", "off_topic", "generic", "empty"]

t0 = time.time()


def log(msg):
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


# ---------------------------------------------------------------- inputs
cfg = json.load(open(f"{SNAP}/config.json"))["text_config"]
EPS = float(cfg["rms_norm_eps"])
V = int(cfg["vocab_size"])
assert cfg["tie_word_embeddings"] is False
wmap = json.load(open(f"{SNAP}/model.safetensors.index.json"))["weight_map"]
NORM_KEY, HEAD_KEY = "model.language_model.norm.weight", "lm_head.weight"

tok = Tokenizer.from_file(f"{SNAP}/tokenizer.json")

man = json.load(open(MANIFEST))["cells"]
hall = [c for c in man if c["family"] == "hallucination"]
log(f"manifest hallucination cells: {len(hall)}")
rows = {}  # (item, pos) -> {layer: row}
ctx = {}   # (item, pos) -> dict
for c in hall:
    key = (c["item_id"], int(c["position"]))
    assert int(c["pos"]) == int(c["position"])
    rows.setdefault(key, {})[int(c["layer"])] = int(c["activation_row"])
    ex = c["capture_spec"]["extra"]
    rec = ctx.setdefault(key, {"input_ids": ex["input_ids"], "prompt_len": int(ex["prompt_len"]),
                               "token": c["token"], "rpk": c["read_position_kind"], "split": c["split"]})
    assert rec["input_ids"] == ex["input_ids"]
sites = sorted(rows)
assert len(sites) == 1123, len(sites)
assert all(set(LAYERS) <= set(rows[s]) for s in sites)

idx = json.load(open(f"{PAGE}/index.json"))
item_ids = [it["id"] for it in idx["items"]]
cell_by = {(item_ids[c["i"]], c["p"], c["L"]): c for c in idx["cells"]}
items = {iid: json.load(open(f"{PAGE}/items/{iid}.json"))["item"] for iid in item_ids}
site_meta = {}
for iid, it in items.items():
    for s in it["sites"]:
        site_meta[(iid, int(s["pos"]))] = s
assert set(site_meta) == set(sites)

# ---------------------------------------------------------------- weights
log("loading final norm + lm_head")
with safe_open(f"{SNAP}/{wmap[NORM_KEY]}", framework="pt") as f:
    norm_w = f.get_tensor(NORM_KEY).float()
with safe_open(f"{SNAP}/{wmap[HEAD_KEY]}", framework="pt") as f:
    head_dtype = str(f.get_slice(HEAD_KEY).get_dtype())
    W = f.get_tensor(HEAD_KEY).float()  # [V, d]
assert W.shape == (V, 5120), W.shape
log(f"lm_head {tuple(W.shape)} stored {head_dtype}; norm w mean={norm_w.mean():.4f} "
    f"min={norm_w.min():.4f} max={norm_w.max():.4f}")

with safe_open(ACTS, framework="pt") as f:
    R = f.get_tensor("resid")
assert R.dtype == torch.float32 and R.shape[1] == 5120


def rmsnorm(x, plus_one=True):
    x = x.float()
    y = x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + EPS)
    return y * ((1.0 + norm_w) if plus_one else norm_w)


def lens(layer, nxt_ids, plus_one=True, chunk=128, keep_logp=False):
    """Return per-site stats for one layer (logits float32, softmax float64)."""
    out = defaultdict(list)
    logps = []
    ridx = torch.tensor([rows[s][layer] for s in sites])
    for a in range(0, len(sites), chunk):
        x = R[ridx[a:a + chunk]]
        logits = rmsnorm(x, plus_one) @ W.T  # float32
        lp = torch.log_softmax(logits.double(), dim=-1)
        p = lp.exp()
        H = -(p * lp).sum(-1)
        top = torch.topk(lp, 5, dim=-1)
        nx = torch.tensor(nxt_ids[a:a + chunk])
        valid = nx >= 0
        nxc = nx.clamp(min=0)
        lp_next = lp.gather(1, nxc[:, None])[:, 0]
        rank = (lp > lp_next[:, None]).sum(-1) + 1
        out["H"] += H.tolist()
        out["top_ids"] += top.indices.tolist()
        out["top_p"] += top.values.exp().tolist()
        out["surp"] += [(-v if ok else None) for v, ok in zip(lp_next.tolist(), valid.tolist())]
        out["rank"] += [(r if ok else None) for r, ok in zip(rank.tolist(), valid.tolist())]
        if keep_logp:
            logps.append(lp.float())
    if keep_logp:
        out["logp"] = torch.cat(logps)
    return out


# ---------------------------------------------------------------- next token
def tstr(i):
    return tok.decode([i], skip_special_tokens=False)


def next_type(i, s):
    if i is None:
        return "none"
    if i >= 248044:
        return "special"
    if s.strip() == "":
        return "newline" if "\n" in s else "space"
    core = s.lstrip(" ")
    lead = s[: len(s) - len(core)]
    c0 = core[0]
    if c0 == "�":
        return "emoji_or_bytes"
    if c0.isdigit():
        return "number"
    if c0.isalpha():
        return "word_space" if lead else "word_nospace"
    if all(ch in "*#-|`>_~=" for ch in core.strip()):
        return "markup"
    if all(unicodedata.category(ch).startswith("P") or ch in string.punctuation for ch in core.strip()):
        return "punct"
    return "emoji_or_bytes"


nxt_ids, nxt_s, nxt_t = [], [], []
align_ok = align_n = 0
for s in sites:
    ids, pos = ctx[s]["input_ids"], s[1]
    assert tstr(ids[pos]) == ctx[s]["token"], (s, tstr(ids[pos]), ctx[s]["token"])
    if pos + 1 < len(ids):
        ni = ids[pos + 1]
        nxt_ids.append(ni)
        st = tstr(ni)
        nxt_s.append(st)
        nxt_t.append(next_type(ni, st))
        if ni < 248044 and "�" not in st:
            align_n += 1
            sm = site_meta[s]
            rest = items[s[0]]["response"]
            # site['char'] is a UTF-16 exclusive end offset; convert to python index
            u16 = rest.encode("utf-16-le")
            py_end = len(u16[: 2 * sm["char"]].decode("utf-16-le"))
            align_ok += rest[py_end:].startswith(st)
    else:
        nxt_ids.append(-1)
        nxt_s.append(None)
        nxt_t.append("none")
log(f"next-token alignment vs response text: {align_ok}/{align_n}; "
    f"sites with no next token: {sum(1 for x in nxt_ids if x < 0)}")

# ---------------------------------------------------------------- lens
log("L60 lens")
L60 = lens(60, nxt_ids, keep_logp=True)
log("L52 lens")
L52 = lens(52, nxt_ids, keep_logp=True)
log("KL(L60 || L52)")
kl = []
for a in range(0, len(sites), 128):
    p60 = L60["logp"][a:a + 128].double()
    p52 = L52["logp"][a:a + 128].double()
    kl += (p60.exp() * (p60 - p52)).sum(-1).tolist()
del L60["logp"], L52["logp"]

# convention check on the first 256 sites: (1+w) vs w
log("norm convention check")
sub = 256
chk = {}
for plus in (True, False):
    ridx = torch.tensor([rows[s][60] for s in sites[:sub]])
    lg = rmsnorm(R[ridx], plus) @ W.T
    acc = float((lg.argmax(-1) == torch.tensor(nxt_ids[:sub])).float().mean())
    lp = torch.log_softmax(lg.double(), -1)
    chk["1+w" if plus else "w"] = {"top1_acc": round(acc, 4),
                                   "mean_entropy": round(float(-(lp.exp() * lp).sum(-1).mean()), 4)}
log(f"convention check (first {sub} sites, L60): {chk}")

# ---------------------------------------------------------------- write jsonl
recs = []
for j, s in enumerate(sites):
    iid, pos = s
    c = ctx[s]
    sm = site_meta[s]
    has = nxt_ids[j] >= 0
    rec = {
        "item_id": iid, "pos": pos, "k_L60": f"{iid}.L60.p{pos}", "split": c["split"],
        "site_kind": sm["kind"], "token": c["token"], "token_id": c["input_ids"][pos],
        "next_token": nxt_s[j], "next_token_id": nxt_ids[j] if has else None, "next_type": nxt_t[j],
        "rel_pos": pos - c["prompt_len"], "resp_len": len(c["input_ids"]) - c["prompt_len"],
        "H_L60": round(L60["H"][j], 5), "H_L52": round(L52["H"][j], 5),
        "p_top1": round(L60["top_p"][j][0], 5), "p_top1_L52": round(L52["top_p"][j][0], 5),
        "top5_mass": round(sum(L60["top_p"][j]), 5), "top5_mass_L52": round(sum(L52["top_p"][j]), 5),
        "surprisal_next_L60": None if L60["surp"][j] is None else round(L60["surp"][j], 5),
        "surprisal_next_L52": None if L52["surp"][j] is None else round(L52["surp"][j], 5),
        "rank_next": L60["rank"][j], "rank_next_L52": L52["rank"][j],
        "top1_correct": (L60["top_ids"][j][0] == nxt_ids[j]) if has else None,
        "top1_correct_L52": (L52["top_ids"][j][0] == nxt_ids[j]) if has else None,
        "kl_L60_L52": round(kl[j], 5),
        "top5": [[tstr(t), round(p, 5)] for t, p in zip(L60["top_ids"][j], L60["top_p"][j])],
        "top1_L52": [tstr(L52["top_ids"][j][0]), round(L52["top_p"][j][0], 5)],
        "next_text8": tok.decode(c["input_ids"][pos + 1: pos + 9], skip_special_tokens=False),
    }
    recs.append(rec)
with open(f"{OUT_DIR}/site_entropy.jsonl", "w") as f:
    for r in recs:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
log(f"wrote {len(recs)} rows")

# ---------------------------------------------------------------- summary
def desc(v):
    v = np.asarray([x for x in v if x is not None], float)
    if len(v) == 0:
        return {"n": 0}
    q = np.quantile(v, [0.1, 0.25, 0.5, 0.75, 0.9])
    return {"n": int(len(v)), "mean": round(float(v.mean()), 4),
            "p10": round(float(q[0]), 4), "p25": round(float(q[1]), 4), "median": round(float(q[2]), 4),
            "p75": round(float(q[3]), 4), "p90": round(float(q[4]), 4)}


def rate(v):
    v = [x for x in v if x is not None]
    return round(sum(map(bool, v)) / len(v), 4) if v else None


val = [r for r in recs if r["next_token_id"] is not None]
H60 = np.array([r["H_L60"] for r in recs])
H52 = np.array([r["H_L52"] for r in recs])
maj_tok, maj_n = Counter(r["next_token_id"] for r in val).most_common(1)[0]
# per-site-kind majority baseline (predict the most common next token for that site kind)
by_kind_next = defaultdict(Counter)
for r in val:
    by_kind_next[r["site_kind"]][r["next_token_id"]] += 1
kind_maj_correct = sum(c.most_common(1)[0][1] for c in by_kind_next.values())
# read-token -> majority next token baseline
by_tok_next = defaultdict(Counter)
for r in val:
    by_tok_next[r["token_id"]][r["next_token_id"]] += 1
tok_maj_correct = sum(c.most_common(1)[0][1] for c in by_tok_next.values())

summary = {
    "description": "Logit lens (final RMSNorm (1+w) + lm_head, float32) at the read sites of "
                   "WorkspaceBench Hallucination (chat); entropy in nats of the predicted next token.",
    "model": {"snapshot": SNAP, "rms_norm_eps": EPS, "vocab": V, "lm_head_stored_dtype": head_dtype,
              "norm_convention": "Qwen3_5RMSNorm: x*rsqrt(mean(x^2)+eps)*(1+w); w stored zero-centred",
              "norm_w_stats": {"mean": round(float(norm_w.mean()), 4), "min": round(float(norm_w.min()), 4),
                               "max": round(float(norm_w.max()), 4)},
              "convention_check_first256_L60": chk,
              "layer_meaning": "activation = output of blocks[L] (0-indexed forward hook), so L60 leaves 3 "
                               "blocks (61-63) before the final norm and L52 leaves 11"},
    "alignment": {"rule": "activation at pos predicts input_ids[pos+1]",
                  "read_token_equals_input_ids_pos": "1123/1123 (asserted)",
                  "next_token_matches_response_text": f"{align_ok}/{align_n}",
                  "sites_without_next_token": int(sum(1 for x in nxt_ids if x < 0)),
                  "own_surprisal": "not available: the read token's own surprisal needs the activation at "
                                   "pos-1, which was not captured (only read sites were)."},
    "n_sites": len(recs),
    "accuracy": {
        "top1_L60": rate([r["top1_correct"] for r in recs]),
        "top1_L52": rate([r["top1_correct_L52"] for r in recs]),
        "top5_L60": rate([r["rank_next"] <= 5 for r in val]),
        "top5_L52": rate([r["rank_next_L52"] <= 5 for r in val]),
        "baseline_uniform": round(1 / V, 8),
        "baseline_global_majority_next": {"token": tstr(maj_tok), "acc": round(maj_n / len(val), 4)},
        "baseline_site_kind_majority_next": round(kind_maj_correct / len(val), 4),
        "baseline_read_token_majority_next (in-sample, optimistic)": round(tok_maj_correct / len(val), 4),
        "median_rank_L60": float(np.median([r["rank_next"] for r in val])),
        "median_rank_L52": float(np.median([r["rank_next_L52"] for r in val])),
        "mean_surprisal_L60": round(float(np.mean([r["surprisal_next_L60"] for r in val])), 4),
        "mean_surprisal_L52": round(float(np.mean([r["surprisal_next_L52"] for r in val])), 4),
    },
    "entropy_L60": desc(H60), "entropy_L52": desc(H52),
    "p_top1_L60": desc([r["p_top1"] for r in recs]),
    "top5_mass_L60": desc([r["top5_mass"] for r in recs]),
    "frac_H_L60_below": {str(t): round(float((H60 < t).mean()), 4) for t in (0.01, 0.1, 0.5, 1.0, 2.0)},
    "L52_vs_L60": {
        "pearson_H": round(float(stats.pearsonr(H52, H60)[0]), 4),
        "spearman_H": round(float(stats.spearmanr(H52, H60)[0]), 4),
        "spearman_surprisal": round(float(stats.spearmanr([r["surprisal_next_L52"] for r in val],
                                                          [r["surprisal_next_L60"] for r in val])[0]), 4),
        "top1_agree": round(float(np.mean([r["top5"][0][0] == r["top1_L52"][0] for r in recs])), 4),
        "mean_H_L52_minus_L60": round(float((H52 - H60).mean()), 4),
        "KL_L60_L52": desc([r["kl_L60_L52"] for r in recs]),
    },
    "entropy_vs_surprisal_L60": {
        "spearman": round(float(stats.spearmanr([r["H_L60"] for r in val],
                                                [r["surprisal_next_L60"] for r in val])[0]), 4)},
}

by_kind = {}
for k in idx["meta"]["site_kinds"]:
    g = [r for r in recs if r["site_kind"] == k]
    gv = [r for r in g if r["next_token_id"] is not None]
    by_kind[k] = {"n": len(g), "H_L60": desc([r["H_L60"] for r in g]), "H_L52_mean": desc([r["H_L52"] for r in g])["mean"],
                  "top1_L60": rate([r["top1_correct"] for r in g]), "top1_L52": rate([r["top1_correct_L52"] for r in g]),
                  "mean_surprisal_L60": round(float(np.mean([r["surprisal_next_L60"] for r in gv])), 4),
                  "next_type_counts": dict(Counter(r["next_type"] for r in g).most_common())}
summary["by_site_kind"] = by_kind
kw = stats.kruskal(*[[r["H_L60"] for r in recs if r["site_kind"] == k] for k in idx["meta"]["site_kinds"]])
summary["by_site_kind_kruskal_H_L60"] = {"H": round(float(kw.statistic), 2), "p": float(kw.pvalue)}

by_nt = {}
for t, n in Counter(r["next_type"] for r in recs).most_common():
    g = [r for r in recs if r["next_type"] == t]
    by_nt[t] = {"n": n, "H_L60": desc([r["H_L60"] for r in g]), "top1_L60": rate([r["top1_correct"] for r in g]),
                "top1_L52": rate([r["top1_correct_L52"] for r in g]),
                "example_next_tokens": [x for x, _ in Counter(r["next_token"] for r in g).most_common(6)]}
summary["by_next_type"] = by_nt

by_tokn = {}
for t, n in Counter(r["token"] for r in recs).most_common(12):
    g = [r for r in recs if r["token"] == t]
    by_tokn[repr(t)] = {"n": n, "H_L60_mean": desc([r["H_L60"] for r in g])["mean"],
                        "H_L60_median": desc([r["H_L60"] for r in g])["median"],
                        "top1_L60": rate([r["top1_correct"] for r in g])}
summary["by_read_token_top12"] = by_tokn

# calibration of the L60 lens against the token the model actually produced. If the reply had been
# sampled at T=1 from the TRUE final distribution, mean surprisal would equal mean true entropy.
Hv = np.array([r["H_L60"] for r in val]); accv = np.array([bool(r["top1_correct"]) for r in val])
p1v = np.array([r["p_top1"] for r in val]); sv = np.array([r["surprisal_next_L60"] for r in val])
rkv = np.array([r["rank_next"] for r in val])
qs = np.quantile(Hv, np.linspace(0, 1, 6))
qb = np.clip(np.digitize(Hv, qs[1:-1]), 0, 4)
summary["calibration_L60"] = {
    "note": f"Lens is overconfident: mean surprisal of the actual token ({sv.mean():.2f}) >> mean lens "
            f"entropy ({Hv.mean():.2f}). If the reply was sampled with the default generation_config (T=1, top_k=20, top_p=0.95), every "
            "actual token is in the true top 20, so rank_next>20 marks sites where L60 disagrees with the "
            "final distribution. The reply decoding settings were not found, so this is conditional.",
    "frac_rank_next_gt20": round(float((rkv > 20).mean()), 4),
    "frac_rank_next_gt100": round(float((rkv > 100).mean()), 4),
    "by_H_quintile": [{"H_range": [round(float(Hv[qb == i].min()), 3), round(float(Hv[qb == i].max()), 3)],
                       "n": int((qb == i).sum()), "mean_H": round(float(Hv[qb == i].mean()), 3),
                       "top1_acc": round(float(accv[qb == i].mean()), 3),
                       "mean_p_top1": round(float(p1v[qb == i].mean()), 3),
                       "mean_surprisal": round(float(sv[qb == i].mean()), 3),
                       "frac_rank_gt20": round(float((rkv[qb == i] > 20).mean()), 3)} for i in range(5)],
    "by_p_top1_bin": [{"bin": [lo, hi], "n": int(((p1v >= lo) & (p1v < hi)).sum()),
                       "top1_acc": round(float(accv[(p1v >= lo) & (p1v < hi)].mean()), 3)}
                      for lo, hi in [(0, .3), (.3, .5), (.5, .7), (.7, .9), (.9, .99), (.99, 1.01)]],
}


# look-ahead: when L60 top-1 is wrong, is it a word that appears a few tokens later (semantic
# preview / different tokenisation of the coming word) rather than noise?
def norm_word(s):
    return s.strip().lower()


wrong = [r for r in val if not r["top1_correct"]]
def la_hit(top1, r):
    w = norm_word(top1)
    if len(w) < 2 or not any(ch.isalpha() for ch in w):
        return None
    return w in r["next_text8"].lower() or norm_word(r["next_token"]) != "" and w.startswith(norm_word(r["next_token"]))


hits = [la_hit(r["top5"][0][0], r) for r in wrong]
perm = np.random.default_rng(1).permutation(len(wrong))
base = [la_hit(wrong[perm[i]]["top5"][0][0], r) for i, r in enumerate(wrong)]
hv = [h for h in hits if h is not None]; bv = [h for h in base if h is not None]


def is_cjk(s):
    return any("一" <= ch <= "鿿" for ch in s)


summary["lookahead_L60"] = {
    "definition": "Among sites where L60 top-1 != actual next token and top-1 is a word (>=2 chars, has a "
                  "letter): top-1 (stripped, lowercased) occurs in the next 8 decoded reply tokens, or starts "
                  "with the actual next token (e.g. ' Ferm' vs 'F'). Baseline: same test with top-1 taken from "
                  "a random other wrong site.",
    "n_wrong": len(wrong), "n_word_top1": len(hv),
    "hit_rate": round(sum(hv) / len(hv), 4), "shuffled_baseline": round(sum(bv) / len(bv), 4),
    "frac_sites_with_CJK_in_top5_L60": round(float(np.mean([any(is_cjk(t) for t, _ in r["top5"]) for r in recs])), 4),
}
summary["examples_lookahead"] = [
    {"k": r["k_L60"], "link": LINK + r["k_L60"], "token": r["token"], "next_text8": r["next_text8"],
     "top5_L60": r["top5"][:3], "H_L60": r["H_L60"]}
    for r, h in zip(wrong, hits) if h and r["H_L60"] < 0.3][:8]

# within-item spread: is entropy mostly a site property or an item property?
it_means = defaultdict(list)
for r in recs:
    it_means[r["item_id"]].append(r["H_L60"])
summary["variance_share_between_items_H_L60"] = round(float(
    np.var([np.mean(it_means[r["item_id"]]) for r in recs]) / np.var(H60)), 4)

# ---------------------------------------------------------------- examples
def ex(r):
    return {"k": r["k_L60"], "link": LINK + r["k_L60"], "site_kind": r["site_kind"], "token": r["token"],
            "next_token": r["next_token"], "H_L60": r["H_L60"], "H_L52": r["H_L52"],
            "rank_next": r["rank_next"], "top5_L60": r["top5"], "top1_L52": r["top1_L52"]}


srt = sorted(recs, key=lambda r: r["H_L60"])
rng = np.random.default_rng(0)
summary["examples"] = {
    "lowest_entropy": [ex(r) for r in srt[:4]],
    "median_entropy": [ex(r) for r in srt[len(srt) // 2 - 2: len(srt) // 2 + 2]],
    "highest_entropy": [ex(r) for r in srt[-4:]],
    "random": [ex(recs[i]) for i in rng.choice(len(recs), 4, replace=False)],
    "top1_wrong_but_low_entropy": [ex(r) for r in srt if r["top1_correct"] is False][:4],
}

# ---------------------------------------------------------------- preview vs FVE / judge
# NOTE: descriptive preview only; another analysis should do this properly.
prev = {"note": "Preview only. Spearman of site entropy (H_L60) with joint FVE of each setting at each "
                "layer, pooled and within site kind (mean of within-kind rho weighted by n). "
                "Hallucination rate by H_L60 tercile (judge label == hallucinated)."}
terc = np.quantile(H60, [1 / 3, 2 / 3])
prev["H_L60_tercile_cuts"] = [round(float(x), 4) for x in terc]
for si, sid in enumerate(SETTINGS):
    block = {}
    for L in (20, 36, 44, 52, 60):
        f = np.array([cell_by[(r["item_id"], r["pos"], L)]["s"][si]["f"] for r in recs], float)
        lab = np.array([cell_by[(r["item_id"], r["pos"], L)]["s"][si]["c"] for r in recs])
        ok = ~np.isnan(f)
        rho = stats.spearmanr(H60[ok], f[ok])[0]
        within = []
        for k in idx["meta"]["site_kinds"]:
            m = ok & np.array([r["site_kind"] == k for r in recs])
            if m.sum() > 10:
                within.append((m.sum(), stats.spearmanr(H60[m], f[m])[0], k))
        wrho = sum(n * x for n, x, _ in within) / sum(n for n, _, _ in within)
        tb = np.digitize(H60, terc)
        block[f"L{L}"] = {
            "spearman_H_FVE": round(float(rho), 4), "within_kind_spearman": round(float(wrho), 4),
            "per_kind_spearman": {k: round(float(x), 4) for _, x, k in within},
            "FVE_by_H_tercile": [round(float(np.nanmean(f[tb == t])), 4) for t in range(3)],
            "halluc_rate_by_H_tercile": [round(float((lab[tb == t] == 1).mean()), 4) for t in range(3)],
        }
    prev[SHORT[si]] = block
kl_tab = {}
for k in idx["meta"]["site_kinds"]:
    g = [r for r in recs if r["site_kind"] == k]
    row = {"n": len(g), "mean_H_L60": round(float(np.mean([r["H_L60"] for r in g])), 3)}
    for si in range(3):
        fv = [cell_by[(r["item_id"], r["pos"], L)]["s"][si]["f"] for r in g for L in (20, 36, 44, 52, 60)]
        fv = [x for x in fv if x is not None]
        row[f"mean_FVE_all_layers_{SHORT[si]}"] = round(float(np.mean(fv)), 4)
    kl_tab[k] = row
prev["site_kind_level"] = kl_tab
summary["preview_vs_fve_and_judge"] = prev

with open(f"{OUT_DIR}/site_entropy_summary.json", "w") as f:
    json.dump(summary, f, indent=1, ensure_ascii=False)
log("wrote summary")
print(json.dumps({k: summary[k] for k in ("alignment", "accuracy", "entropy_L60", "entropy_L52",
                                           "L52_vs_L60", "frac_H_L60_below")}, indent=1, ensure_ascii=False))
