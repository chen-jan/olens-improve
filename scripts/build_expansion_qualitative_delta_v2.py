"""Wrap the frozen delta builder with exact prior-review identity links."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile

import build_expansion_qualitative_delta as frozen
from expanded_cpu_cached import atomic, sha


def content_identity(unit,pair,kind,context):
    return json.dumps([kind,unit['family'],unit['cell_id'],pair['before']['text'],
        pair['after']['text'],context],sort_keys=True,ensure_ascii=False)


def official_pairs(pair,kind):
    keys=('official_before','official_after') if kind=='capped_N1_pairs' else ('official_parent','official_proposed')
    return [(r[keys[0]],r[keys[1]]) for r in pair['references']]


def main():
    p=argparse.ArgumentParser(add_help=False)
    p.add_argument('--prior-index',type=Path,required=True);p.add_argument('--prior-review',type=Path,action='append',required=True)
    p.add_argument('--output',type=Path,required=True);a,remaining=p.parse_known_args()
    if a.output.exists():raise FileExistsError('Use a new immutable reviewer index')
    old=json.loads(a.prior_index.read_text());old_sha=sha(a.prior_index);reviews={}
    for path in a.prior_review:
        r=json.loads(path.read_text());identity=r.get('source_index') or {'path':r.get('index_path',r.get('source_index_path')),'sha256':r.get('index_sha256',r.get('source_index_sha256'))}
        if identity['sha256']!=old_sha or 'complete' not in r['status']:raise ValueError('Prior review is not complete/bound to prior index')
        partition=r['partition'];expected=len(old['partitions'][partition])
        count=r.get('unit_count',r.get('reviewed_content_units',r.get('coverage',{}).get('units')))
        if count!=expected or partition in reviews:raise ValueError('Prior review partition coverage differs')
        reviews[partition]={'path':str(path),'sha256':sha(path),'partition':partition}
    if set(reviews)!=set(old['partitions']):raise ValueError('All previous delta partitions must be explicitly bound')
    with tempfile.TemporaryDirectory(prefix='expanded-delta-') as tmp:
        previous_argv=sys.argv;sys.argv=[str(Path(frozen.__file__)),*remaining,'--output',str(Path(tmp)/'index.json')]
        try:
            with redirect_stdout(io.StringIO()):frozen.main()
        finally:sys.argv=previous_argv
        current=json.loads((Path(tmp)/'index.json').read_text())
    prior={};prior_count=0
    for partition,units in old['partitions'].items():
        for i,unit in enumerate(units):
            for kind in ('capped_N1_pairs','actual_parent_pairs'):
                for j,pair in enumerate(unit[kind]):
                    identity=content_identity(unit,pair,kind,old['contexts'][unit['context_ref']]);prior_count+=1
                    prior.setdefault(identity,[]).append({'provenance':reviews[partition]|{'prior_unit_index':i,'pair_kind':kind,'prior_pair_index':j},'official_pairs':official_pairs(pair,kind)})
    pending=[];inherited=[];seen_content=0;inherited_refs=0
    for units in current['partitions'].values():
        for unit in units:
            retained=dict(unit)
            for kind in ('capped_N1_pairs','actual_parent_pairs'):
                retained[kind]=[]
                for pair in unit[kind]:
                    matches=prior.get(content_identity(unit,pair,kind,current['contexts'][unit['context_ref']]),[])
                    pair['prior_exact_text_context_review_links']=[m['provenance'] for m in matches]
                    all_known=bool(matches) and all(any(candidate in m['official_pairs'] for m in matches) for candidate in official_pairs(pair,kind))
                    if matches:seen_content+=1
                    if all_known:
                        pair['review_status']='content_and_official_pair_review_inherited; new_condition_grid_metadata_retained'
                        inherited.append({'family':unit['family'],'cell_id':unit['cell_id'],'context_ref':unit['context_ref'],'pair_kind':kind,'pair':pair});inherited_refs+=len(pair['references'])
                    else:
                        pair['review_status']='new_review_required' if not matches else 'content_seen; changed_official_pair_requires_review'
                        retained[kind].append(pair)
            if retained['capped_N1_pairs'] or retained['actual_parent_pairs']:pending.append(retained)
    partitions={name:[] for name in old['partitions']};loads={name:0 for name in partitions}
    for unit in sorted(pending,key=lambda u:(-len(u['capped_N1_pairs'])-len(u['actual_parent_pairs']),u['family'],u['cell_id'],u['proposed_text'])):
        name=min(loads,key=lambda n:(loads[n],n));partitions[name].append(unit);loads[name]+=len(unit['capped_N1_pairs'])+len(unit['actual_parent_pairs'])
    current.update(partitions=partitions,partition_comparison_counts=loads,review_unit_count=len(pending),prior_indexed_comparison_count=prior_count,previous_exact_text_context_pair_count=seen_content,inherited_content_official_pair_count=len(inherited),inherited_case_reference_count=inherited_refs,inherited_comparisons=inherited)
    current['source_sha256'][str(a.prior_index)]=old_sha
    current['source_sha256'].update({r['path']:r['sha256'] for r in reviews.values()});current['implementation_sha256'][str(Path(__file__))]=sha(__file__)
    current['review_instructions'].append('Only exact before/after text, complete source context and official pair equality inherit content notes; new condition-specific whole-grid evidence remains separately retained, not causally inferred.')
    if any(sha(path)!=value for path,value in current['source_sha256'].items()):raise ValueError('Delta inputs changed while indexing')
    atomic(a.output,current)
    print(json.dumps({'output':str(a.output),'sha256':sha(a.output),'new_baseline_refs':current['new_capped_N1_case_references'],'new_parent_refs':current['new_actual_parent_references'],'prior_pairs':prior_count,'inherited_pairs':len(inherited),'pending_pairs':sum(loads.values()),'partition_comparison_counts':loads}))


if __name__=='__main__':main()
