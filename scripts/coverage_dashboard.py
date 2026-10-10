"""Descriptive frozen-grid coverage, without quality scores or layer selection."""
import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import html
import importlib.util
import json
from pathlib import Path

FAMILIES = ('hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association')


def grouped_grid(cells):
    positions = defaultdict(set)
    seen = set()
    for c in cells:
        cid = c['cell_id']
        if cid in seen or c['family'] not in FAMILIES:
            raise ValueError('Duplicate or foreign frozen-grid cell')
        seen.add(cid)
        positions[c['family'], c['item_id']].add(c['position'])
    ranks = {k:{p:i+1 for i,p in enumerate(sorted(v))} for k,v in positions.items()}
    result = {}
    for family in FAMILIES:
        rows = [c for c in cells if c['family']==family]
        if not rows:
            raise ValueError('Missing frozen-grid family')
        counts = Counter((c['layer'], ranks[family,c['item_id']][c['position']]) for c in rows)
        result[family] = {'cells':len(rows), 'items':len({c['item_id'] for c in rows}),
            'layers':sorted({c['layer'] for c in rows}),
            'position_ranks':sorted({rank for _,rank in counts}),
            'slots':[{'layer':layer,'position_rank':rank,'expected_cells':n}
                     for (layer,rank),n in sorted(counts.items())]}
    return result


def prepare(section, manifest, manifest_sha):
    """Require signed complete/revealed source, then count metadata only."""
    stage = section['stage']
    if stage not in ('validation','test') or manifest.get('split') != stage:
        raise ValueError('Coverage cohort differs from signed stage')
    if stage=='test' and section['review'].get('test_reveal_authorized') is not True:
        raise ValueError('TEST coverage requires completed signed reveal')
    if manifest_sha != section['identities']['manifest_sha256']:
        raise ValueError('Coverage manifest differs from signed source')
    counts = grouped_grid(manifest['cells'])
    for family, grid in counts.items():
        expected = section['family_counts'][family]
        if any(grid[k] != expected[k] for k in ('cells','items')):
            raise ValueError('Coverage grid differs from signed family counts')
        for row in grid['slots']:
            row.update(accounted_cells=row['expected_cells'], missing_required_results=0)
    return {'status':'pending_root_review','stage':stage,
        'artifact_sha256':section['source_sha256'], 'manifest_sha256':manifest_sha,
        'review_metadata_sha256':section['review_metadata_sha256'],
        'condition_ids':section['condition_ids'], 'families':counts,
        'grid_cell_ids_sha256':sha256(json.dumps(sorted(c['cell_id'] for c in manifest['cells']),
            separators=(',',':')).encode()).hexdigest(),
        'missingness_basis':'The completed, reviewed comparison covers every required judging stage for every method. Slots count cells once, not once per method.',
        'position_definition':'Rank1 is the earliest selected token position within each item; ranks refer to its frozen read grid, not absolute token index. Columns can mix different absolute positions across items.',
        'limits':['Counts only; no quality endpoint, new site, or layer/position selected from outcomes.',
                  'Unrequested grid locations are outside the read plan, not missing results.',
                  'Zero missing means verified complete required-stage coverage; unavailable coverage stays unknown.']}


def validate(coverage, section):
    if coverage.get('status')!='root_reviewed' or not coverage.get('reviewed_by'):
        raise ValueError('Coverage metadata requires coordinator review')
    for k in ('stage','condition_ids'):
        if coverage[k] != section[k]: raise ValueError('Foreign coverage stage/menu')
    if (coverage['artifact_sha256']!=section['source_sha256'] or
        coverage['manifest_sha256']!=section['identities']['manifest_sha256'] or
        coverage['review_metadata_sha256']!=section['review_metadata_sha256']):
        raise ValueError('Foreign coverage source identities')
    if section['stage']=='test' and section['review'].get('test_reveal_authorized') is not True:
        raise ValueError('TEST coverage remains sealed')
    if set(coverage['families'])!=set(FAMILIES): raise ValueError('Missing coverage family')
    for family, grid in coverage['families'].items():
        expected = section['family_counts'][family]
        if any(grid[k]!=expected[k] for k in ('cells','items')): raise ValueError('Foreign coverage counts')
        slots=grid['slots'];ids=[(r['layer'],r['position_rank']) for r in slots]
        if len(ids)!=len(set(ids)): raise ValueError('Duplicate coverage slot')
        if sorted({l for l,_ in ids})!=grid['layers'] or sorted({p for _,p in ids})!=grid['position_ranks']:
            raise ValueError('Coverage axes differ from slots')
        for row in slots:
            for key in ('expected_cells','accounted_cells','missing_required_results'):
                n=row[key]
                if n is not None and (isinstance(n,bool) or not isinstance(n,int) or n<0):
                    raise ValueError('Invalid coverage count')
            if row['expected_cells']<1: raise ValueError('Outside-grid locations must not be invented')
            a,b=row['accounted_cells'],row['missing_required_results']
            if (a is None)!=(b is None) or (a is not None and a+b!=row['expected_cells']):
                raise ValueError('Missingness differs from expected grid')
            if b not in (None, 0):
                raise ValueError('Completed comparison coverage must be complete or unknown')
        if sum(r['expected_cells'] for r in slots)!=expected['cells']: raise ValueError('Coverage total differs')


def render(coverage, section, labels):
    validate(coverage,section)
    esc=lambda x:html.escape(str(x),quote=True)
    out=['<details><summary>Coverage by layer and position in the frozen read grid</summary>',
         '<p>'+esc(coverage['position_definition'])+'</p><p>'+esc(coverage['missingness_basis'])+'</p>']
    for family,grid in coverage['families'].items():
        ranks=grid['position_ranks'];layers=grid['layers'];slots={(r['layer'],r['position_rank']):r for r in grid['slots']}
        width=120+48*len(ranks);height=75+35*len(layers);maximum=max(r['expected_cells'] for r in slots.values())
        out+=['<h4>'+esc(labels(family))+'</h4>']
        if family in ('multihop_mt','chain_intermediates'):
            out+=['<p>Single final prompt-token position per item. Absolute token indices vary with input length.</p>']
        out+=['<div class="table-scroll"><svg viewBox="0 0 '+str(width)+' '+str(height)+'" style="min-width:'+str(min(width,800))+'px" role="img" aria-label="'+esc(labels(family)+' frozen-grid cell counts')+'">']
        for i,p in enumerate(ranks):out+=[f'<text x="{125+48*i}" y="20" text-anchor="middle">{p}</text>']
        for j,l in enumerate(layers):
            y=35+35*j;out+=[f'<text x="8" y="{y+21}">Layer {l}</text>']
            for i,p in enumerate(ranks):
                x=103+48*i;r=slots.get((l,p))
                if r is None:
                    out+=[f'<rect x="{x}" y="{y}" width="44" height="30" fill="#eee"><title>Outside frozen read grid</title></rect>']
                    continue
                n=r['expected_cells'];a=r['accounted_cells'];b=r['missing_required_results'];v=round(245-100*n/maximum)
                shown='?' if a is None else str(n)
                title=f'{n} expected; '+('coverage unknown' if a is None else f'{a} accounted; {b} missing required results')
                out+=[f'<rect x="{x}" y="{y}" width="44" height="30" fill="rgb({v},{v+5},{min(v+15,255)})"><title>{esc(title)}</title></rect>',f'<text x="{x+22}" y="{y+21}" text-anchor="middle">{shown}</text>']
        out+=['</svg></div><p>Numbers are expected cells, counted once per layer/position; darker shading means more cells. Gray locations are outside the read grid, not missing.</p>']
        missing=[r['missing_required_results'] for r in slots.values()]
        out+=['<p>Required-result coverage: '+('unknown' if any(v is None for v in missing) else str(sum(missing))+' missing cells for each compared method')+'.</p>']
    out+=['<p>Frozen manifest SHA-256 '+esc(coverage['manifest_sha256'])+'; reviewed analysis '+esc(coverage['artifact_sha256'])+'.</p></details>']
    return ''.join(out)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('analysis','review','manifest','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--expected-sha256',required=True);a=p.parse_args()
    spec=importlib.util.spec_from_file_location('signed_figures',Path(__file__).with_name('export_signed_figures.py'))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    section=mod.load_section(a.analysis,a.review,a.expected_sha256)  # Before frozen manifest access.
    raw=a.manifest.read_bytes();result=prepare(section,json.loads(raw),sha256(raw).hexdigest())
    result['manifest_path']=str(a.manifest);result['implementation_sha256']=sha256(Path(__file__).read_bytes()).hexdigest()
    if a.output.exists():raise ValueError('Preserve prior coverage metadata')
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'output':str(a.output),'status':result['status'],'new_model_calls':0,'new_API_calls':0}))

if __name__=='__main__':main()
