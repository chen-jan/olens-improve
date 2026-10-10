"""Read-only aggregation of frozen cell diagnostics; never invokes a judge."""
from collections import defaultdict
from hashlib import sha256
import json
from datetime import datetime, timezone
from pathlib import Path
from .evaluation import paired_group_interval, BENCH_ROOT

FAMILIES = ('hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association')
SELECTION_SHA = '055c5ea0e0d85fd5aa83af58f2cd1c2f2ea5a95940f1ecd6af4669c9a1f288c5'
BENCHMARK_COMMIT = '92d763e722377f5bfae045e829a308ab5919a820'

def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()

def key(row):
    return (str(row['id']), int(row['layer']), int(row['pos']))

def unique(rows, key_fn):
    out = {}
    for row in rows:
        k = key_fn(row)
        if k in out:
            raise ValueError(f'Duplicate result/readout: {k}')
        out[k] = row
    return out

def original_grid_contract(frozen):
    """Bind a complete DEV grid to the frozen all-core inference manifest.

    A partial pilot cannot acquire item-score status by changing one flag.
    """
    if frozen.get('partial_grid', True):
        return None
    if frozen.get('complete_original_family_grids') is not True or frozen.get('benchmark_commit') != BENCHMARK_COMMIT:
        raise ValueError('Original-grid reporting requires the pinned full-grid contract')
    parent_path=Path(frozen['parent_manifest_path'])
    if digest(parent_path)!=frozen['parent_manifest_sha256']:
        raise ValueError('Full-grid parent manifest hash mismatch')
    parent=json.loads(parent_path.read_text())
    expected=[c for c in parent['cells'] if c['split']=='development']
    def signature(c):return (c['cell_id'],c['family'],str(c['item_id']),int(c['layer']),int(c['position']),c['group_id'])
    actual=unique(frozen['cells'],lambda c:c['cell_id'])
    intended=unique(expected,lambda c:c['cell_id'])
    if {signature(c) for c in actual.values()}!={signature(c) for c in intended.values()}:
        raise ValueError('Original DEV grids differ from the frozen core manifest')
    return {'parent_manifest_path':str(parent_path),'parent_manifest_sha256':digest(parent_path),
            'scope':'complete original development grids; not held-out benchmark accuracy'}

def original_grid_pairs(family, cell_metrics, result):
    """Pinned item ANY rule; hallucination retains its readout-level ratio.

    MT/chain item flags are independently checked against cell outcomes. Role
    needs all three MC answers at one site, then ANY passing site over the grid.
    """
    numbers=result['numbers']
    if family=='hallucination':
        pairs=cell_metrics['contradiction_rate']
        num=sum(p[0] for p in pairs.values());den=sum(p[1] for p in pairs.values())
        value=num/den if den else None
        if numbers.get('metric')!='hallucination_rate' or numbers.get('value')!=value:
            raise ValueError('Pinned hallucination headline differs from verified counts')
        return {'original_grid_contradiction_rate':pairs}
    pairs={item:(int(num>0),1) for item,(num,den) in cell_metrics['cell_recovery'].items()}
    if family!='role_bound_association':
        rows=unique(result['rows'],lambda row:str(row['id']))
        if set(rows)!=set(pairs) or any(not isinstance(rows[item].get('pass'),bool) or rows[item]['pass']!=bool(pair[0]) for item,pair in pairs.items()):
            raise ValueError('Pinned item pass disagrees with complete cell outcomes')
    value=sum(p[0] for p in pairs.values())/len(pairs) if pairs else None
    if numbers.get('metric')!='pass_rate' or numbers.get('value')!=value:
        raise ValueError('Pinned item headline differs from verified counts')
    return {'original_grid_item_pass_rate':pairs}

def family_counts(family, cells, readouts, result):
    """Return per-item count pairs, checking outcomes independently of flags.

    Empty outputs are explicit abstentions, while absent judgments stay missing.
    Hall false spans and true/unverifiable claims have different segmentation.
    """
    intended = unique(cells, lambda c: (str(c['item_id']), int(c['layer']), int(c['position'])))
    reads = unique(readouts, key)
    if reads.keys() != intended.keys():
        raise ValueError('Readout cohort differs from frozen intended cells')
    if any(len(r.get('samples', [])) != 1 for r in reads.values()):
        raise ValueError('Require exactly one final readout per cell')
    rows = unique(result['rows'], key if family in ('hallucination', 'role_bound_association') else lambda r: str(r['id']))
    expected_rows = intended.keys() if family in ('hallucination', 'role_bound_association') else {k[0] for k in intended}
    if not rows.keys() <= expected_rows:
        raise ValueError('Result contains cells/items outside frozen cohort')
    sums = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    missing1 = missing2 = empty = 0
    for k, cell in intended.items():
        item = k[0]
        blank = not reads[k]['samples'][0].strip()
        empty += blank
        row = rows.get(k if family in ('hallucination', 'role_bound_association') else item)
        if family == 'hallucination':
            verdicts = row.get('verdict') if row else None
            v = verdicts[0] if isinstance(verdicts, list) and len(verdicts) == 1 else None
            if row is not None and row.get('samples') != reads[k]['samples']:
                raise ValueError('Hall result text differs from submitted readout')
            if v is not None and v.get('idx') != 0:
                raise ValueError('Hall verdict index differs from the single final readout')
            judged = v is not None and v.get('class') not in (None, 'unjudged')
            claims = v.get('claims') if judged else None
            tallied = isinstance(claims, dict) and all(isinstance(claims.get(name), int) and not isinstance(claims.get(name), bool) and claims[name] >= 0 for name in ('false', 'true', 'unverifiable'))
            if not blank:
                missing1 += not judged
                missing2 += not tallied
            specific = bool(judged and v.get('class') in ('hallucinated', 'consistent', 'off_topic'))
            wrong = bool(specific and v.get('class') == 'hallucinated')
            off = bool(specific and v.get('class') == 'off_topic')
            for name, num, den in [('contradiction_rate', wrong, specific), ('assertion_share', specific, 1), ('off_topic_rate', off, specific)]:
                sums[name][item][0] += num; sums[name][item][1] += den
            claims = v['claims'] if tallied else {}
            for name, num, den in [('false_span_tally', claims.get('false', 0), 1), ('true_claim_tally', claims.get('true', 0), 1), ('unverifiable_claims_per_output', claims.get('unverifiable', 0), 1)]:
                sums[name][item][0] += num; sums[name][item][1] += den
        else:
            outcome = None
            if blank:
                outcome = False
            elif row is not None:
                if family == 'role_bound_association':
                    outcome = row.get('pass')
                elif family == 'chain_intermediates':
                    kind = row.get('kind_by_layer', {}).get(str(k[1]))
                    if kind not in (None, 'unavailable'):
                        outcome = kind == 'hit'
                else:
                    layer = row.get('layers', {}).get(str(k[1]))
                    if layer is not None:
                        outcome = all(bool(layer.get('hits', {}).get(role)) for role in row['roles'])
            if not isinstance(outcome, bool):
                missing1 += 1
            sums['cell_recovery'][item][0] += outcome is True
            sums['cell_recovery'][item][1] += 1
    return {m: {i: tuple(v) for i, v in items.items()} for m, items in sums.items()}, {'expected_cells':len(cells), 'empty_abstentions':int(empty), 'missing_stage1':int(missing1), 'missing_stage2':int(missing2)}

def summarize(manifest, conditions, root, *, selection_sha=SELECTION_SHA):
    manifest, conditions, root = Path(manifest), Path(conditions), Path(root)
    frozen = json.loads(manifest.read_text())
    if any(c['split'] != 'development' for c in frozen['cells']):
        raise ValueError('This report is restricted to development cells')
    manifest_sha = digest(manifest)
    grid_contract=original_grid_contract(frozen)
    families = {f: [c for c in frozen['cells'] if c['family'] == f] for f in FAMILIES}
    groups = {}
    for c in frozen['cells']:
        ident = (c['family'], str(c['item_id']))
        if ident in groups and groups[ident] != c['group_id']:
            raise ValueError('Item belongs to inconsistent related groups')
        groups[ident] = c['group_id']
    report = {'schema_version':1, 'generated_utc':datetime.now(timezone.utc).isoformat(), 'conditions_sha256':digest(conditions), 'condition_root':str(root.resolve()), 'scope':'partial-grid cell diagnostics' if frozen.get('partial_grid') else 'cell diagnostics', 'manifest_sha256':manifest_sha, 'selection_sha256':selection_sha, 'bootstrap_replicates':2000, 'conditions':[], 'paired_comparisons':[], 'caveats':['Whole related groups are resampled after aggregating cells by item.', 'Recovery detects mentions/bindings under the declared judge, not full explanation faithfulness.', 'False spans and true/unverifiable claims have different segmentation.', 'Random selection is one frozen draw.', 'No held-out or official full-grid result is reported.']}
    report['original_grid_contract']=grid_contract
    report['original_grid_paired_comparisons']=[]
    if grid_contract:
        source_names=['src/wsbench/evals/hallucination/score.py','src/wsbench/evals/role_bound_association/score.py','src/wsbench/evals/chain_intermediates/judge.py','src/wsbench/multitoken/family.py','src/wsbench/multitoken/regex.py','src/wsbench/family.py','src/wsbench/results.py']
        report['original_grid_metric_source_sha256']={str(BENCH_ROOT/name):digest(BENCH_ROOT/name) for name in source_names}
    counts_by_arm = {}; grid_counts_by_arm={}
    for arm in json.loads(conditions.read_text()):
        name = f"{arm['method']}-n{arm['n']}"
        arm_root = Path(arm.get('condition_root', root))
        path = arm_root/name
        entry = dict(arm, condition_root=str(arm_root.resolve()), condition=name, measurement_complete=False, families={}, source_sha256={}, errors=[])
        hashes = entry['source_sha256']
        def read(p, lines=False):
            data = p.read_bytes(); hashes[str(p)] = sha256(data).hexdigest()
            return [json.loads(line) for line in data.splitlines() if line.strip()] if lines else json.loads(data)
        try:
            if arm.get('selection_path'):
                selection_path=Path(arm['selection_path']);actual_selection_sha=digest(selection_path)
                hashes[str(selection_path)]=actual_selection_sha
                if actual_selection_sha!=arm.get('selection_sha256',selection_sha):raise ValueError('Selection source bytes differ from the declared SHA')
            identity = read(path/'condition.json')
            if any(identity.get(k) != arm[k] for k in ('method', 'n')) or identity.get('manifest_sha256') != manifest_sha or identity.get('selection_sha256') != arm.get('selection_sha256', selection_sha):
                raise ValueError('Condition provenance/hash mismatch')
            coverage = identity['coverage']
            if coverage.get('expected_cells') != len(frozen['cells']) or coverage.get('produced_cells') != len(frozen['cells']) or coverage.get('missing_cell_ids') or coverage.get('readouts_per_cell') != 1:
                raise ValueError('Condition output coverage mismatch')
            if identity.get('partial_grid') != bool(frozen.get('partial_grid', False)):
                raise ValueError('Condition grid scope mismatch')
            arm_counts = {}; grid_arm_counts={}
            for family, cells in families.items():
                terminal = read(path/f'{family}.summary.json')
                if terminal.get('condition') != identity or family not in terminal.get('families', {}):
                    raise ValueError(f'{family}: terminal summary identity mismatch')
                contract = read(path/family/'project_contract.json')
                if terminal['families'][family].get('project_contract') != contract:
                    raise ValueError(f'{family}: terminal contract differs from result contract')
                if contract.get('manifest_expected_cells') != len(cells) or contract.get('manifest_produced_cells') != len(cells) or contract.get('manifest_missing_cells') != 0 or contract.get('benchmark_commit') != BENCHMARK_COMMIT or contract.get('partial_grid') != identity['partial_grid'] or contract.get('split') != ['development']:
                    raise ValueError(f'{family}: contract/cohort mismatch')
                result = read(path/family/'results.json')
                if result.get('family') != family or result.get('config', {}).get('dry_run'):
                    raise ValueError(f'{family}: dry run or wrong result family')
                readouts = read(path/f'{family}.readouts.jsonl', True)
                metrics, status = family_counts(family, cells, readouts, result)
                entry['families'][family] = status | {'metrics':{}}
                if status['missing_stage1'] or status['missing_stage2']:
                    entry['errors'].append(f'{family}: missing stage1={status["missing_stage1"]}, stage2={status["missing_stage2"]}')
                for metric, pairs in metrics.items():
                    zero = {item:(0, den) for item, (_, den) in pairs.items()}
                    interval = paired_group_interval(zero, pairs, {item:groups[(family,item)] for item in pairs})
                    num = sum(x[0] for x in pairs.values()); den = sum(x[1] for x in pairs.values())
                    entry['families'][family]['metrics'][metric] = {'numerator':num, 'denominator':den, 'value':num/den if den else None, 'ci95':interval['ci95_delta'], 'items':interval['items'], 'independent_groups':interval['independent_groups'], 'defined_draws':interval['defined_draws'], 'warning':interval['warning']}
                arm_counts[family] = metrics
                if grid_contract and not status['missing_stage1'] and not status['missing_stage2']:
                    grid_metrics=original_grid_pairs(family,metrics,result)
                    grid_arm_counts[family]=grid_metrics
                    entry['families'][family]['original_grid_metrics']={}
                    for metric,pairs in grid_metrics.items():
                        zero={item:(0,den) for item,(_,den) in pairs.items()}
                        interval=paired_group_interval(zero,pairs,{item:groups[(family,item)] for item in pairs})
                        num=sum(x[0] for x in pairs.values());den=sum(x[1] for x in pairs.values())
                        entry['families'][family]['original_grid_metrics'][metric]={'numerator':num,'denominator':den,'value':num/den if den else None,'ci95':interval['ci95_delta'],'items':interval['items'],'independent_groups':interval['independent_groups'],'defined_draws':interval['defined_draws'],'warning':interval['warning'],'unit':'specific readouts; ratio of item sums' if family=='hallucination' else 'original-grid item: ANY passing site/layer'}
            for p, sha in hashes.items():
                if digest(p) != sha:
                    raise ValueError('Input changed during aggregation; retry after terminal write')
            entry['measurement_complete'] = not entry['errors']
            if entry['measurement_complete']:
                counts_by_arm[name] = arm_counts
                if grid_contract:grid_counts_by_arm[name]=grid_arm_counts
        except (OSError, ValueError, KeyError, TypeError) as exc:
            entry['errors'].append(str(exc))
        if not entry['measurement_complete']:
            # Never display a partially repaired arm as a finished comparison.
            for family in entry['families'].values():
                family['metrics'] = {}
                family.pop('original_grid_metrics',None)
        report['conditions'].append(entry)
    for name, arm in counts_by_arm.items():
        baselines = ['raw_n1-n1', 'capped_n1-n1']
        n = next(e['n'] for e in report['conditions'] if e['condition']==name)
        if not name.startswith(('best_n_exact-', 'raw_n1-', 'capped_n1-')):
            baselines.append(f'best_n_exact-n{n}')
        for baseline in dict.fromkeys(baselines):
            if baseline not in counts_by_arm or baseline == name:
                continue
            for family, metrics in arm.items():
                for metric in ('cell_recovery', 'contradiction_rate', 'assertion_share', 'off_topic_rate', 'unverifiable_claims_per_output'):
                    if metric not in metrics:
                        continue
                    pairs = metrics[metric]
                    interval = paired_group_interval(counts_by_arm[baseline][family][metric], pairs, {item:groups[(family,item)] for item in pairs})
                    report['paired_comparisons'].append({'baseline_condition':baseline, 'condition':name, 'family':family, 'endpoint':metric, **interval})
            if grid_contract:
                for family,metrics in grid_counts_by_arm[name].items():
                    for metric,pairs in metrics.items():
                        interval=paired_group_interval(grid_counts_by_arm[baseline][family][metric],pairs,{item:groups[(family,item)] for item in pairs})
                        report['original_grid_paired_comparisons'].append({'baseline_condition':baseline,'condition':name,'family':family,'endpoint':metric,**interval})
    if grid_contract:
        if digest(grid_contract['parent_manifest_path'])!=grid_contract['parent_manifest_sha256']:raise ValueError('Full-grid parent changed during reporting')
        if any(digest(path)!=expected for path,expected in report['original_grid_metric_source_sha256'].items()):raise ValueError('Pinned metric source changed during reporting')
        report['scope']='complete original DEV grids: cell diagnostics and pinned item aggregation'
        report['caveats'][-1]='Original item aggregation uses complete DEV grids only; no held-out or whole-bank benchmark accuracy is reported.'
    return report

def markdown(report):
    explanation='Cell endpoints and pinned original item aggregation are separate below.' if report.get('original_grid_contract') else 'These are not official full-grid item scores.'
    lines = ['# Development results', '', report['scope']+'. Grouped intervals resample whole related groups (2,000 paired draws). '+explanation, '', '| Condition | Complete | Contradictions / specific | Bridge cells | Chain cells | Role cells |', '|---|---|---:|---:|---:|---:|']
    for arm in report['conditions']:
        values=[]
        for family, metric in [('hallucination','contradiction_rate'),('multihop_mt','cell_recovery'),('chain_intermediates','cell_recovery'),('role_bound_association','cell_recovery')]:
            row=arm['families'].get(family,{}).get('metrics',{}).get(metric)
            values.append(f"{row['numerator']}/{row['denominator']}" if row else 'Pending')
        lines.append('| '+ ' | '.join([arm['condition'],str(arm['measurement_complete'])]+values)+' |')
    if report.get('original_grid_contract'):
        lines+=['','Original-grid DEV aggregation uses the pinned item rule (ANY passing site/layer), with whole related groups resampled. Hallucination retains the ratio of readout counts, aggregated by item before resampling. These are development results, not held-out or whole-bank accuracy.','','| Condition | Hall contradictions / specific | Bridge items | Chain items | Role items |','|---|---:|---:|---:|---:|']
        for arm in report['conditions']:
            values=[]
            for family in FAMILIES:
                metrics=arm['families'].get(family,{}).get('original_grid_metrics',{})
                row=next(iter(metrics.values()),None)
                values.append(f"{row['numerator']}/{row['denominator']}" if row else 'Pending')
            lines.append('| '+' | '.join([arm['condition']]+values)+' |')
        lines+=['','| Original-grid condition vs baseline | Family / endpoint | Paired delta | Grouped 95% interval | Groups |','|---|---|---:|---|---:|']
        for row in report['original_grid_paired_comparisons']:
            if row['baseline_condition']!='capped_n1-n1':continue
            lines.append(f"| {row['condition']} vs capped N1 | {row['family']} / {row['endpoint']} | {row['delta']:.4f} | {row['ci95_delta']} | {row['independent_groups']} |" if row['delta'] is not None else f"| {row['condition']} | {row['family']} | Undefined | Undefined | {row['independent_groups']} |")
    lines += ['', '| Condition vs baseline | Family / endpoint | Paired delta | Grouped 95% interval | Groups |', '|---|---|---:|---|---:|']
    for row in report['paired_comparisons']:
        if row['baseline_condition']!='capped_n1-n1' or row['endpoint'] not in ('cell_recovery','contradiction_rate'): continue
        lines.append(f"| {row['condition']} vs capped N1 | {row['family']} / {row['endpoint']} | {row['delta']:.4f} | {row['ci95_delta']} | {row['independent_groups']} |" if row['delta'] is not None else f"| {row['condition']} | {row['family']} | Undefined | Undefined | {row['independent_groups']} |")
    return '\n'.join(lines)+'\n'
