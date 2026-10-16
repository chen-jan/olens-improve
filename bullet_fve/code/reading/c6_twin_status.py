import os, re, math, json, collections
import numpy as np
HERE='${OLENS_SCRATCH}/olens-bullet-fve/reading'
src=open(os.path.join(HERE,'synth_tests.py')).read()
head=src[:src.index('# ============================================================================= Part A')]
partb=src[src.index('# ============================================================================= Part B'):src.index("OB = ['capped_n1-n1'")]
g={'__file__':os.path.join(HERE,'synth_tests.py'),'__name__':'loader'}
exec(compile(head+'\n'+partb,'synth_loader','exec'),g)
cells,rows,SIDS,SHORT,u16,sl,ITEM_IX,ratio_ci,per_item=g['cells'],g['rows'],g['SIDS'],g['SHORT'],g['u16'],g['sl'],g['ITEM_IX'],g['ratio_ci'],g['per_item']
R={(r['k'],r['sid'],r['j']):r for r in rows}
def norm_b(t): return re.sub(r'\s+',' ',t).strip()
st=collections.Counter(); ex=[]
st_ww=collections.Counter()
for k,(iid,c) in cells.items():
    seen=collections.defaultdict(list)
    for sid in SIDS:
        s=c['settings'][sid]; tb=u16(s['text'] or '')
        for j,b in enumerate(s['bullets']):
            if b['label'] not in ('w','c','o'): continue
            seen[norm_b(sl(tb,b['start'],b['end']))].append((sid,j,b['label']))
    for t,lst in seen.items():
        for x in range(len(lst)):
            for y in range(x+1,len(lst)):
                p,q=lst[x],lst[y]
                if p[0]==q[0] or (c['settings'][p[0]]['text'] or '')==(c['settings'][q[0]]['text'] or ''): continue
                if {p[2],q[2]}=={'c','w'}:
                    cc=p if p[2]=='c' else q
                    r=R[(k,cc[0],cc[1])]
                    if r['n_claims']==0: key='clean copy: no stage-2 claim located'
                    elif r['n_disp']>0: key='clean copy: >=1 disputed claim'
                    elif r['n_unver']>0 and r['n_true']==0: key='clean copy: only unverifiable claims'
                    elif r['n_unver']>0: key='clean copy: mix true+unverifiable'
                    else: key='clean copy: all claims true'
                    st[key]+=1
                    if key=='clean copy: all claims true' and len(ex)<6: ex.append((k,SHORT[cc[0]],t[:120]))
tot=sum(st.values())
for k_,v in st.most_common(): print(f'{k_}: {v} ({v/tot:.1%})')
print(ex)
# base rate: all clean bullets by stage-2 status, for comparison
bs=collections.Counter()
for r in rows:
    if r['label']!='c': continue
    if r['n_claims']==0: key='none'
    elif r['n_disp']>0: key='disp'
    elif r['n_unver']>0 and r['n_true']==0: key='unver only'
    elif r['n_unver']>0: key='mix'
    else: key='all true'
    bs[key]+=1
t2=sum(bs.values()); print({k_:round(v/t2,3) for k_,v in bs.items()})
