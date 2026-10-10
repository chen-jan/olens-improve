"""Descriptive DEV/VAL outcomes on existing frozen sites; no site selection."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from analyze_consensus_conditions import read_arm
from coverage_dashboard import grouped_grid

FAMILIES = ('hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def grouped_rate(rows, groups, *, replicates=2000, seed=20261010):
    """Resample related groups, retaining every member's numerator/denominator."""
    import numpy as np
    totals = defaultdict(lambda: [0, 0])
    for item, numerator, denominator in rows:
        totals[groups[item]][0] += numerator
        totals[groups[item]][1] += denominator
    numerator = sum(row[0] for row in totals.values())
    denominator = sum(row[1] for row in totals.values())
    value = numerator / denominator if denominator else None
    result = {'numerator':numerator, 'denominator':denominator, 'value':value,
              'independent_groups':len(totals), 'ci95':None, 'defined_draws':0,
              'warning':None}
    if len(totals) < 2:
        result['warning'] = 'Fewer than two related groups; no interval.'
        return result
    a = np.asarray([totals[k] for k in sorted(totals)], dtype=float)
    indexes = np.random.default_rng(seed).integers(0, len(a), (replicates, len(a)))
    draws = a[indexes].sum(axis=1)
    valid = draws[:, 1] > 0
    rates = draws[valid, 0] / draws[valid, 1]
    result['defined_draws'] = int(valid.sum())
    if len(rates):
        result['ci95'] = np.quantile(rates, [.025, .975]).tolist()
    if denominator == 0:
        result['warning'] = 'No eligible denominator; undefined rate, not zero.'
    elif len(a) < 10:
        result['warning'] = 'Fewer than ten related groups; interval is unstable.'
    return result


def audit_family(cells, outcomes, family, *, replicates=2000):
    selected = [c for c in cells if c['family'] == family]
    ids = {c['cell_id'] for c in selected}
    if set(outcomes) != ids:
        raise ValueError('Missing or foreign outcome cells; do not plot them as zero')
    grid = grouped_grid(cells)[family]
    positions = defaultdict(set)
    for c in selected:
        positions[c['item_id']].add(c['position'])
    ranks = {item:{p:i+1 for i,p in enumerate(sorted(ps))} for item,ps in positions.items()}
    groups = {c['item_id']:c['group_id'] for c in selected}
    buckets = defaultdict(list)
    for c in selected:
        buckets[c['layer'], ranks[c['item_id']][c['position']]].append(c)
    slots = []
    for (layer, rank), rows in sorted(buckets.items()):
        pairs, asserted, off_topic, empty = [], [], [], []
        classes = Counter()
        for c in rows:
            o = outcomes[c['cell_id']]
            if family == 'hallucination':
                if o['class'] not in ('hallucinated','consistent','off_topic','generic','empty'):
                    raise ValueError('Unknown hallucination class')
                eligible = int(o['class'] in ('hallucinated','consistent','off_topic'))
                pairs.append((c['item_id'], int(o['class']=='hallucinated'), eligible))
                asserted.append((c['item_id'], eligible, 1))
                off_topic.append((c['item_id'], int(o['class']=='off_topic'), 1))
                classes[o['class']] += 1
            else:
                pairs.append((c['item_id'], int(o['pass']), 1))
            empty.append((c['item_id'], int(o['empty']), 1))
        slots.append({'layer':layer, 'position_rank':rank, 'expected_cells':len(rows),
            'accounted_cells':len(rows), 'missing_required_results':0,
            'items':len({c['item_id'] for c in rows}),
            'independent_groups':len({c['group_id'] for c in rows}),
            'absolute_position_min':min(c['position'] for c in rows),
            'absolute_position_max':max(c['position'] for c in rows),
            'metric':grouped_rate(pairs, groups, replicates=replicates),
            'empty_share':grouped_rate(empty, groups, replicates=replicates),
            'assertion_share':grouped_rate(asserted, groups, replicates=replicates) if asserted else None,
            'off_topic_share':grouped_rate(off_topic, groups, replicates=replicates) if off_topic else None,
            'classes':dict(classes) if classes else None})
    grid['slots'] = slots
    grid['independent_groups'] = len(set(groups.values()))
    grid['endpoint'] = ('Unrevoked wrong / (wrong + off-topic + consistent)' if family=='hallucination'
        else 'Required bridge mentions / intended cells' if family=='multihop_mt'
        else 'Intermediate number recovery / intended cells' if family=='chain_intermediates'
        else 'Directed role-task passes / intended cells')
    return grid


def load_stage(section):
    # The current utility cannot inspect TEST, even with a supplied path.
    if section['stage'] not in ('development','validation'):
        raise ValueError('Only DEV/VAL are supported; TEST remains closed in this utility')
    hashes = {}
    signed = None
    if section['stage'] == 'validation':
        from export_signed_figures import load_section
        signed = load_section(section['signed_analysis'], section['review'], section['analysis_sha256'])
        if signed['stage'] != 'validation':
            raise ValueError('Foreign signed stage')
        hashes[section['signed_analysis']] = section['analysis_sha256']
        hashes[section['review']] = digest(section['review'])
    path = Path(section['manifest'])
    before = digest(path)
    if before != section['manifest_sha256']:
        raise ValueError('Foreign frozen cohort')
    manifest = json.loads(path.read_text())
    if manifest['split'] != section['stage'] or {c['split'] for c in manifest['cells']} != {section['stage']}:
        raise ValueError('Foreign cells or stage')
    cells = {c['cell_id']:c for c in manifest['cells']}
    if len(cells) != len(manifest['cells']):
        raise ValueError('Duplicate frozen cell')
    if signed is not None:
        if signed['identities']['manifest_sha256'] != before:
            raise ValueError('Signed cohort differs')
        if not set(section['conditions']) <= set(signed['condition_ids']):
            raise ValueError('Unsigned validation condition')
    hashes[str(path)] = before
    result = {'stage':section['stage'], 'manifest_sha256':before, 'conditions':[],
              'expected_cells':len(cells)}
    for condition in section['conditions']:
        root = Path(section['judgments']) / condition
        sources = [root/'condition.json']
        for family in FAMILIES:
            sources += [root/f'{family}.readouts.jsonl', root/family/'project_contract.json', root/family/'results.json']
        source_hashes = {str(p):digest(p) for p in sources}
        authority = json.loads((root/'condition.json').read_text())
        if authority['manifest_sha256'] != before:
            raise ValueError('Condition belongs to a different cohort')
        families = {f:audit_family(manifest['cells'], read_arm(root,f,cells),f) for f in FAMILIES}
        if any(digest(p) != h for p,h in source_hashes.items()):
            raise ValueError('Outcome source changed during descriptive audit')
        hashes.update(source_hashes)
        result['conditions'].append({'condition':condition, 'families':families})
    if digest(path) != before:
        raise ValueError('Cohort changed during audit')
    return result, hashes


def figures(stage, output):
    os.environ.setdefault('MPLCONFIGDIR', '/tmp/olens-improve-grid-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    created = []
    for family in FAMILIES:
        methods = stage['conditions']
        fig, axes = plt.subplots(1, len(methods), figsize=(5.2*len(methods), 6.5), squeeze=False,
                                 layout='constrained')
        for ax, method in zip(axes.flat, methods):
            grid = method['families'][family]
            layers, ranks = grid['layers'], grid['position_ranks']
            values = np.full((len(layers),len(ranks)),np.nan)
            lookup = {(r['layer'],r['position_rank']):r for r in grid['slots']}
            for j,l in enumerate(layers):
                for i,p in enumerate(ranks):
                    row = lookup.get((l,p))
                    if row and row['metric']['value'] is not None:
                        values[j,i] = 100*row['metric']['value']
            image = ax.imshow(values, vmin=0, vmax=100, aspect='auto',
                              cmap='YlOrRd' if family=='hallucination' else 'YlGnBu')
            ax.set_xticks(range(len(ranks)),ranks,fontsize=8)
            ax.set_yticks(range(len(layers)),layers,fontsize=9)
            ax.set_xlabel('Within-item selected position rank')
            ax.set_ylabel('Decoder layer')
            ax.set_title(method['condition'].replace('-n',' N'),fontsize=10)
            if len(ranks) <= 8:
                for (l,p),row in lookup.items():
                    v=row['metric']['value']
                    if v is not None:
                        ax.text(ranks.index(p),layers.index(l),f'{100*v:.0f}\n(n={row["expected_cells"]})',
                                ha='center',va='center',fontsize=7,color='black')
            fig.colorbar(image, ax=ax, shrink=.6,label='Endpoint rate (%)')
        fig.suptitle(stage['stage'].upper()+' — '+family.replace('_',' ')+'\n'+
            methods[0]['families'][family]['endpoint']+'; original frozen sites only',fontsize=12)
        fig.supxlabel('Position ranks mix different token indices across items. No best site is selected.\n'
            'Missing/outside-grid values are masked, not zero. Counts, grouped 95% intervals, assertion/empty shares are in the JSON.\n'
            'Intervals are exploratory and unadjusted across slots; colors do not establish reliable site differences.',fontsize=9)
        for extension in ('png','pdf'):
            path = output/(stage['stage']+'-'+family+'.'+extension)
            fig.savefig(path,dpi=160,bbox_inches='tight',facecolor='white')
            created.append({'path':str(path),'sha256':digest(path)})
        plt.close(fig)
    return created


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources',type=Path,required=True)
    p.add_argument('--expected-sha256',required=True)
    p.add_argument('--output',type=Path,required=True)
    args = p.parse_args()
    if digest(args.sources) != args.expected_sha256:
        raise ValueError('Source spec changed')
    spec = json.loads(args.sources.read_text())
    # Reject any unsupported stage before reading a manifest or outcomes.
    if not spec['stages'] or any(s['stage'] not in ('development','validation') for s in spec['stages']):
        raise ValueError('Only DEV/VAL sources are authorized here')
    if args.output.exists():
        raise ValueError('Preserve previous artifacts; use a fresh output directory')
    args.output.mkdir(parents=True)
    stages, hashes = [], {str(args.sources):args.expected_sha256,
                         str(Path(__file__).resolve()):digest(Path(__file__).resolve())}
    for source in spec['stages']:
        result, source_hashes = load_stage(source)
        stages.append(result); hashes.update(source_hashes)
    exported = [file for stage in stages for file in figures(stage,args.output)]
    artifact = {'status':'complete_descriptive_dev_val_pending_review',
        'created_utc':datetime.now(timezone.utc).isoformat(), 'stages':stages,
        'bootstrap_replicates':2000,'bootstrap_seed':20261010,'source_sha256':hashes,
        'figures':exported,'new_API_calls':0,'test_outcomes_accessed':False,
        'position_definition':'Rank is ordered selected token position within each item. It is not an aligned semantic location across items. Later ranks can change the item cohort.',
        'limits':['Frozen methods and sites are unchanged; these are post-freeze descriptions, not tuning.',
            'Unadjusted per-slot related-group percentile bootstrap intervals; not a simultaneous test of layer/position differences.',
            'Ranks can have small and different item/group counts. No rate is inferred for an outside-grid site.',
            'Hallucination uses the official unrevoked contradiction rate conditional on specific output; assertion/off-topic/empty shares remain separate.',
            'Required mention/number/role recovery does not establish whole-output factual truth.',
            'DEV and VAL use different fixed item cohorts; their maps are not paired cross-split comparisons.',
            'TEST is intentionally unsupported until a separate completed, reviewed source is authorized.']}
    path = args.output/'grid-audit.json'
    path.write_text(json.dumps(artifact,indent=2,allow_nan=False)+'\n')
    for file in args.output.iterdir(): file.chmod(0o444)
    print(json.dumps({'path':str(path),'sha256':digest(path),'figures':len(exported),
        'stages':[{ 'stage':s['stage'],'methods':len(s['conditions']),'cells_per_method':s['expected_cells']} for s in stages]}))


if __name__ == '__main__':
    main()
