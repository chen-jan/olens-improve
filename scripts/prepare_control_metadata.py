"""Augment frozen control assignments with read-plan metadata, never redraw donors."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from olens_improve.ar_cache import digest

FIELDS=('family','item_id','group_id','layer','position','split','read_position_kind')


def augment(controls,read_plan,fresh,provenance):
    cells={c['cell_id']:c for c in read_plan['cells']};captures={c['cell_id']:c for c in fresh['cells']}
    if len(cells)!=len(read_plan['cells']) or len(captures)!=len(fresh['cells']):raise ValueError('Duplicate source cell')
    if set(controls['control_cell_ids_by_target'])!=set(cells) or set(cells)!=set(captures):
        raise ValueError('Control target/read-plan/fresh cell sets differ')
    metadata={}
    for cid,c in cells.items():
        if not c.get('read_position_kind'):raise ValueError('Original read plan lacks explicit site kind')
        if any(c[k]!=captures[cid][k] for k in FIELDS if k!='read_position_kind'):
            raise ValueError('Original read-plan identity differs from frozen fresh metadata')
        metadata[cid]={k:c[k] for k in FIELDS}
    for cid,ids in controls['control_cell_ids_by_target'].items():
        own=metadata[cid]
        for donor in ids:
            ref=controls['control_bank'][donor]
            if any(ref[k]!=metadata[donor][k] for k in FIELDS):raise ValueError('Frozen donor metadata differs from original read plan')
            if ref['split']!='development' or ref['group_id']==own['group_id']:
                raise ValueError('Existing assignment violates DEV/group boundary')
            if any(ref[k]!=own[k] for k in ('family','layer','read_position_kind')):
                raise ValueError('Existing assignment violates matched site kind')
    result=dict(controls)
    result.update(target_metadata=metadata,target_metadata_provenance=provenance)
    result['content_sha256']=digest({k:v for k,v in result.items() if k!='content_sha256'})
    assert result['control_bank']==controls['control_bank']
    assert result['control_cell_ids_by_target']==controls['control_cell_ids_by_target']
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('controls','read-plan','fresh-manifest','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args()
    paths={'controls':a.controls,'read_plan':a.read_plan,'fresh_manifest':a.fresh_manifest}
    bodies={k:p.read_bytes() for k,p in paths.items()}
    provenance={'source_sha256':{str(paths[k]):sha256(b).hexdigest() for k,b in bodies.items()},
                'code_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
                'boundary':'Metadata only, derived from original capture_manifest/read_position_kinds; no outputs, labels or donor redraw.'}
    result=augment(json.loads(bodies['controls']),json.loads(bodies['read_plan']),json.loads(bodies['fresh_manifest']),provenance)
    payload=(json.dumps(result,indent=2)+'\n').encode()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('xb') as f:f.write(payload)
    a.output.chmod(0o444)
    print(json.dumps({'output':str(a.output),'sha256':sha256(payload).hexdigest(),'target_metadata':len(result['target_metadata']),
                      'assignments_changed':0,'empty_targets':sum(not ids for ids in result['control_cell_ids_by_target'].values())}))


if __name__=='__main__':main()
