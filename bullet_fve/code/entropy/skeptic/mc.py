import json, numpy as np, re, ast
from scipy import stats
R=json.load(open('analysis_results.json'))
tests=[]
def walk(o,path):
    if isinstance(o,dict):
        if 'b' in o and 'ci' in o and isinstance(o['ci'],list) and o['b'] is not None and o['ci'][0] is not None:
            tests.append(('/'.join(path),o['b'],o['ci']))
        for k,v in o.items():
            if k in ('b','ci'): continue
            walk(v,path+[str(k)])
        # quintile contrasts
        for k in o:
            if k.endswith('_ci') and k[:-3] in o and isinstance(o[k],list) and len(o[k])==2 and o[k][0] is not None and isinstance(o[k[:-3]],(int,float)):
                tests.append(('/'.join(path+[k[:-3]]),o[k[:-3]],o[k]))
    elif isinstance(o,list):
        for i,v in enumerate(o): walk(v,path+[str(i)])
walk({k:v for k,v in R.items() if k not in ('examples','meta')},[])
tests=[t for t in tests if t[2][1]>t[2][0]]
b=np.array([t[1] for t in tests]); lo=np.array([t[2][0] for t in tests]); hi=np.array([t[2][1] for t in tests])
se=(hi-lo)/3.92; p=2*stats.norm.sf(np.abs(b)/se)
m=len(p); o=np.argsort(p)
bh=np.empty(m); prev=1
for r,i in enumerate(o[::-1]):
    prev=min(prev,p[i]*m/(m-r)); bh[i]=prev
holm=np.empty(m); run=0
for r,i in enumerate(o):
    run=max(run,min(1,p[i]*(m-r))); holm[i]=run
excl=((lo>0)|(hi<0))
print("tests with CI in analysis_results.json:", m, " CI excludes 0:", int(excl.sum()), " BH q<.05:", int((bh<.05).sum()), " Holm<.05:", int((holm<.05).sum()))
# claims in ENTROPY.md
claims={
 "L36 FVE slope Original": "fve_vs_H/Original/36/H/full",
 "L20 FVE slope Best of 32": "fve_vs_H/Best of 32/20/H/full",
 "L60-L20 Best of 32": "fve_vs_H/Best of 32/L60_minus_L20_H_full",
 "L60-L20 Combine 32": "fve_vs_H/Combine 32/L60_minus_L20_H_full",
 "L60-L20 Original": "fve_vs_H/Original/L60_minus_L20_H_full",
 "near-det all Original": "robustness/Original/all/H_ge_0.1",
 "near-det L52 Original": "robustness/Original/52/H_ge_0.1",
 "near-det L60 Original": "robustness/Original/60/H_ge_0.1",
 "decile D1 Original": None,
 "NEXT pooled Original": "cont_vs_H/NEXT/Original/all/H/pooled",
 "NONE pooled Original": "cont_vs_H/NONE/Original/all/H/pooled",
 "NEXT L60-L20 Original": "cont_vs_H/NEXT/Original/L60_minus_L20_H_full",
 "offtopic pooled Original": "halluc_vs_H/offtopic/Original/all/H/pooled",
 "true_share pooled Original": "halluc_vs_H/true_share/Original/all/H/pooled",
 "novel_name Best of 32": "halluc_vs_H/novel_name/Best of 32/all/H/pooled",
 "surprisal FVE Original": "surprisal/fve/Original/all/surprisal/pooled",
 "surprisal halluc Best of 32": "surprisal/halluc/Best of 32/all/surprisal/pooled",
 "per-kind sentence slope": "robustness/Original/per_kind_full_slope/sentence/all",
 "per-kind markup L60": "robustness/Original/per_kind_full_slope/markup/60",
 "logH L36": "fve_vs_H/Original/36/logH/full",
 "words_after>=40 L36": "robustness/Original/36/H_rank_words_after_ge40",
 "mediation shift Original": "mediation/Original/all/NEXT/direct_minus_total",
 "H_L52 exposure L52 Original": "fve_vs_H/Original/52/H_L52/full",
 "joint NEXT H Original": "joint_H_surprisal/Original/NEXT/all/H",
}
idx={t[0]:i for i,t in enumerate(tests)}
out={}
for nm,key in claims.items():
    if key is None or key not in idx: print(f"  {nm:32s} not found ({key})"); continue
    i=idx[key]; print(f"  {nm:32s} b={b[i]:+.3f} [{lo[i]:+.3f},{hi[i]:+.3f}] p~{p[i]:.4f} BH q={bh[i]:.3f} Holm={holm[i]:.3f}")
    out[nm]={"b":float(b[i]),"ci":[float(lo[i]),float(hi[i])],"p_approx":float(p[i]),"q_BH":float(bh[i]),"p_Holm":float(holm[i])}
json.dump({"n_tests":m,"n_ci_excl_0":int(excl.sum()),"n_BH":int((bh<.05).sum()),"n_Holm":int((holm<.05).sum()),"claims":out},open('skeptic/mc_results.json','w'),indent=1)
