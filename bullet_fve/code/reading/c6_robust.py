import os, re, math, json, collections
import numpy as np
HERE='${OLENS_SCRATCH}/olens-bullet-fve/reading'
src=open(os.path.join(HERE,'synth_tests.py')).read()
head=src[:src.index('# ============================================================================= Part A')]
partb=src[src.index('# ============================================================================= Part B'):src.index("OB = ['capped_n1-n1'")]
g={'__file__':os.path.join(HERE,'synth_tests.py'),'__name__':'loader'}
exec(compile(head+'\n'+partb,'synth_loader','exec'),g)
by_ro,ratio_ci,per_item,win,SIDS,SHORT,LAB=g['by_ro'],g['ratio_ci'],g['per_item'],g['win'],g['SIDS'],g['SHORT'],g['LAB']
OB=['capped_n1-n1','best_n_exact-n32']
vt=lambda r: r['n_claims']>0 and r['n_true']==r['n_claims']
unv=lambda r: (r['n_unver']>0 or r['n_disp']>0)
noclaim=lambda r: r['n_claims']==0
T=lambda r: True
def pr(sid,score,la,sa,lb,sb,tol=None,lenkey='scored_len'):
    # P(score[b] > score[a]) for a in group A (label la, sel sa), b in group B
    acc=[]
    for (k,s2),bs in by_ro.items():
        if s2!=sid: continue
        A=[x for x in bs if x['label']==la and sa(x)]; B=[x for x in bs if x['label']==lb and sb(x)]
        for a in A:
            for b in B:
                if a is b: continue
                if tol and abs(math.log(max(1,a[lenkey])/max(1,b[lenkey])))>math.log(tol): continue
                acc.append((a['ix'],win(b[score],a[score]),1.))
    r=ratio_ci(*per_item(acc)); return f"{r['est']:.3f} [{r['lo']:.3f},{r['hi']:.3f}] n={r['n']}"
for sid in SIDS:
    sc='solo_pa' if sid in OB else 'solo'
    print('=====',SHORT[sid],sc)
    for tol in (None,1.5,1.25,1.1):
        print(' tol',tol,'| w<c all',pr(sid,sc,'w',T,'c',T,tol),'| w<c vt',pr(sid,sc,'w',T,'c',vt,tol),'| w<c unverif',pr(sid,sc,'w',T,'c',unv,tol), '| unverif<vt (clean only)',pr(sid,sc,'c',unv,'c',vt,tol))
    print(' total len tol1.25 | w<c all',pr(sid,sc,'w',T,'c',T,1.25,'len'),'| w<c vt',pr(sid,sc,'w',T,'c',vt,1.25,'len'))
    print(' token count tol1.25 | w<c all',pr(sid,sc,'w',T,'c',T,1.25,'n_tok_scored'),'| w<c vt',pr(sid,sc,'w',T,'c',vt,1.25,'n_tok_scored'))
    print(' share: | w<c all',pr(sid,'share_pa' if sid in OB else 'share','w',T,'c',T,1.25),'| w<c vt',pr(sid,'share_pa' if sid in OB else 'share','w',T,'c',vt,1.25))
    print(' raw solo (no pos adj): w<c vt tol1.25',pr(sid,'solo','w',T,'c',vt,1.25))
for sid in SIDS:
    print(SHORT[sid],'raw solo len1.25 w<c all',pr(sid,'solo','w',T,'c',T,1.25),'| w<unverif',pr(sid,'solo','w',T,'c',unv,1.25),'| unverif<vt',pr(sid,'solo','c',unv,'c',vt,1.25))
