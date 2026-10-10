"""Attach the reviewed complete DEV A32/capped-N1 comparison, separate from pilot."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path


FAMILIES = {'hallucination': (1145, 30), 'multihop_mt': (341, 29),
            'chain_intermediates': (330, 7), 'role_bound_association': (3420, 15)}


def comparison(artifact, source_path, source_sha):
    measurement = artifact['measurement']
    if not measurement.get('original_grid_contract'):
        raise ValueError('Require complete original DEV grid contract')
    arms = {a['condition']: a for a in measurement['conditions']}
    if set(arms) != {'capped_n1-n1', 'best_n_exact-n32'}:
        raise ValueError('Only the reviewed two-condition DEV comparison is eligible')
    for arm in arms.values():
        if not arm['measurement_complete'] or arm.get('errors'):
            raise ValueError('Incomplete comparison condition')
        for family, (expected, groups) in FAMILIES.items():
            status = arm['families'][family]
            if status['expected_cells'] != expected or status['missing_stage1'] or status['missing_stage2']:
                raise ValueError('DEV stage coverage incomplete')
            endpoint = 'contradiction_rate' if family == 'hallucination' else 'cell_recovery'
            if status['metrics'][endpoint]['independent_groups'] != groups:
                raise ValueError('Unexpected independent-group contract')
    baseline, proposed = arms['capped_n1-n1'], arms['best_n_exact-n32']
    paired = {(r['family'], r['endpoint']): r for r in measurement['paired_comparisons']
              if r['baseline_condition']=='capped_n1-n1' and r['condition']=='best_n_exact-n32'}
    original = {(r['family'], r['endpoint']): r for r in measurement['original_grid_paired_comparisons']
                if r['baseline_condition']=='capped_n1-n1' and r['condition']=='best_n_exact-n32'}

    def row(family, endpoint, grid=False):
        field = 'original_grid_metrics' if grid else 'metrics'
        a = baseline['families'][family][field][endpoint]
        b = proposed['families'][family][field][endpoint]
        delta = (original if grid else paired)[family, endpoint]
        if abs(delta['baseline']-a['value']) > 1e-12 or abs(delta['proposed']-b['value']) > 1e-12:
            raise ValueError('Paired endpoint differs from source condition')
        return {'family': family, 'endpoint': endpoint, 'baseline': a, 'proposed': b,
                'delta': delta['delta'], 'ci': delta['ci95_delta'], 'groups': delta['independent_groups'],
                'warning': delta['warning']}

    cells = [row(family, 'contradiction_rate' if family=='hallucination' else 'cell_recovery')
             for family in FAMILIES]
    items = [row(family, 'original_grid_item_pass_rate', True) for family in FAMILIES if family!='hallucination']
    hall = {condition: arm['families']['hallucination']['metrics'] for condition, arm in arms.items()}
    return {
        'title': 'Complete development comparison: best of 32 versus capped single-sample baseline',
        'scope': '121 DEV items / 5,236 cells, complete original grids. Separate from the 189-cell pilot; validation judging is underway; test outcomes remain sealed.',
        'reviewed_by': 'root',
        'key_finding': 'Best of 32 recovers more bridge mentions and passes more individual role tasks on development. The contradiction-rate difference remains uncertain, and social-role item coverage stays unchanged. These recovery endpoints do not establish complete truthful explanations.',
        'cell_endpoints': cells, 'original_item_endpoints': items,
        'hallucination_auxiliary_counts': {condition: {k: v for k,v in metrics.items()
                                                    if k in ('assertion_share','off_topic_rate','false_span_tally','true_claim_tally','unverifiable_claims_per_output')}
                                             for condition, metrics in hall.items()},
        'limits': artifact['limits'] + [
            'All other full DEV method comparisons remain incomplete in this panel.',
            'The hallucination interval spans no difference; exploratory grouped intervals are not adjusted for multiple development comparisons.',
            'Role item ANY coverage is unchanged even though more individual cells pass; the seven chain groups limit robustness claims.',
            'For fixed candidate fits, nested best-of-N maximum reconstruction fit is nondecreasing by construction. A pool selector with a best-parent fallback also guarantees this objective floor. Neither property guarantees nondecreasing judged quality.',
        ],
        'manifest_sha256': measurement['manifest_sha256'],
        'selection_source': artifact['selection_source'],
        'selection_source_sha256': artifact['selection_source_sha256'],
        'source_path': str(source_path), 'source_sha256': source_sha,
        'bootstrap_replicates': measurement['bootstrap_replicates'],
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--artifact', type=Path, required=True)
    p.add_argument('--expected-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    args=p.parse_args()
    raw=args.artifact.read_bytes()
    source_sha=sha256(raw).hexdigest()
    if source_sha != args.expected_sha256:
        raise ValueError('Reviewed source hash mismatch')
    report=json.loads(args.report.read_text())
    report['full_development_a32']=comparison(json.loads(raw),args.artifact,source_sha)
    report['updated_utc']=datetime.now(timezone.utc).isoformat()
    report['full_development']['method_comparison_status']='Best-of-32 versus capped N1 is complete on all four DEV families and shown separately above. The remaining full DEV method comparisons are incomplete. Existing pilot quality tables are retained. Validation judging is underway; test outcomes remain sealed.'
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'output':str(args.output),'source_sha256':source_sha,'new_api_calls':0,'new_model_calls':0}))


if __name__=='__main__':
    main()
