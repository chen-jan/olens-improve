"""Separate zero-Q abstention control; preserve original specificity parents."""
import argparse
from hashlib import sha256
import json
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();body=a.input.read_bytes();source=json.loads(a.input.with_name('status.json').read_text())
    if source['status']!='complete' or source['selection_sha256']!=sha256(body).hexdigest():
        raise ValueError('Require exact terminal frozen combination snapshot')
    rows=[];seen=set();abstained=[]
    for line in body.splitlines():
        row=json.loads(line);cid=row['cell_id']
        if cid in seen:raise ValueError('Duplicate source cell')
        seen.add(cid)
        parent=[s for s in row['selections'] if s['method']=='best_n_specificity_mean' and s['n']==32]
        if len(parent)!=1:raise ValueError('Missing complete E1 parent')
        parent=parent[0];q=parent['extra']['score'];selected=dict(parent,method='best_n_specificity_mean_abstain_nonpositive')
        selected['abstention_control']={'threshold':0.,'parent_Q':q,'abstained':q<=0,
                                       'parent_text':parent['text'],'parent_phrase_ids':parent['phrase_ids']}
        if q<=0:
            abstained.append(cid)
            selected.update(text='',phrase_ids=[],token_count=0,bullet_count=0,atoms=[],trace=[],
                reason='nonpositive_complete_mean_Q',fits={'exact':{'coefficients':[],'fve':0.,'atom_ids':[],'solver':'scipy_exact'},
                'released80':{'coefficients':[],'fve':0.,'atom_ids':[],'solver':'released80'}},
                fits_scope='emitted_bullets',scored_text='',extra={'score':0.,'abstention_objective':'empty_Q_zero'})
        rows.append({k:v for k,v in row.items() if k!='selections'}|{'selections':[selected]})
    if len(rows)!=source['cells']:raise ValueError('Frozen cohort count differs')
    payload=''.join(json.dumps(r)+'\n' for r in rows).encode()
    metadata={'status':'complete','cells':len(rows),'threshold':0.,'abstentions':len(abstained),'abstained_cell_ids':abstained,
              'parent_sha256':sha256(body).hexdigest(),'selection_sha256':sha256(payload).hexdigest(),
              'code_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),'new_model_calls':0,'new_api_calls':0,
              'purpose':'Separate matched empty-option control; unchanged original D+E outputs'}
    if a.output.exists():raise ValueError('Refuse changed immutable output')
    a.output.mkdir(parents=True)
    for name,data in [('selections.jsonl',payload),('conditions.json',b'[{"method":"best_n_specificity_mean_abstain_nonpositive","n":32}]\n'),
                      ('export.json',(json.dumps(metadata,indent=2)+'\n').encode())]:
        (a.output/name).write_bytes(data);(a.output/name).chmod(0o444)
    print(json.dumps(metadata),flush=True)


if __name__=='__main__':main()
