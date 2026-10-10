"""Attach compact, source-verified evaluation diagnostics; never expose gold to selectors."""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(path, expected):
    if digest(path) != expected:
        raise ValueError(f'Source hash differs: {path}')


def candidate_summary(artifact, expected_manifest):
    if (artifact['manifest_sha256'] != expected_manifest or
            artifact['analysis_status'] != 'complete_development_partial_grid' or
            artifact.get('analysis_revision') != 'v2-source-item-bootstrap-metadata' or
            artifact['missing_candidates'] != 0 or artifact['judged_candidates'] != 6048):
        raise ValueError('Require complete corrected pilot candidate analysis')
    families = deepcopy(artifact['families'])
    for family, row in families.items():
        interval = row['rank_minus_half_group_interval']
        if interval['items'] != row['items']:
            raise ValueError('Bootstrap unit differs from source item count')
        row['rank_ci95'] = [v + .5 for v in interval['ci95_delta']]
        row['rank_definition'] = ('Consistent or off-topic versus hallucinated assertions'
                                  if family == 'hallucination' else 'Passing versus failing readouts')
    return {'title': 'Does reconstruction rank the available matches?',
            'scope': 'Evaluation-only diagnostic on the 189-cell partial-grid DEV pilot',
            'families': families, 'candidate_count': artifact['judged_candidates'],
            'limits': artifact['limitations'] + [
                'Available means at least one judged match among the existing 32 samples. Gold judgments never guide the selector.',
                'The arithmetic-chain interval uses only two related groups; its apparent width cannot establish robustness.',
                'The hallucination rank includes off-topic assertions on its nonwrong side; it does not measure factual precision.'],
            'random_note': artifact['random_note']}


def attach(report, artifact_path, donor_path, durable):
    report = deepcopy(report)
    artifact = json.loads(artifact_path.read_text())
    summary = candidate_summary(artifact, report['provenance']['cohort_manifest_sha256'])
    check(durable/'diagnostics/all-candidate-scores-v1/scores.jsonl', artifact['scores_sha256'])
    check(durable/'selections/pilot189-selectors-v1/selections.jsonl', artifact['a32_selection_sha256'])
    judgments = durable/'runs/development-shared-pilot-v2/judgments-all-candidates'
    if len(artifact['judgment_provenance']) != 128:
        raise ValueError('Expected 32 conditions across four families')
    for parent in artifact['judgment_provenance']:
        root = judgments/f"candidate_index_{parent['condition']:02d}-n32"/parent['family']
        check(root/'results.json', parent['results_sha256'])
        check(root/'project_contract.json', parent['project_contract_sha256'])
    summary['source'] = {'path': str(artifact_path), 'sha256': digest(artifact_path),
                         'manifest_sha256': artifact['manifest_sha256'],
                         'scores_sha256': artifact['scores_sha256'],
                         'a32_selection_sha256': artifact['a32_selection_sha256']}
    report['candidate_diagnostic'] = summary
    donor = json.loads(donor_path.read_text())
    section = report['full_development']
    if (donor['status'] != 'complete_project_development_grid' or
            donor['manifest_sha256'] != section['measurement_manifest_sha256']):
        raise ValueError('Require matched complete DEV donor analysis')
    base = durable/'runs/development-full-grid-v2/judgments-baselines/capped_n1-n1'
    other = donor_path.parent/'matched_donor_capped_n1-n1'
    check(base/'condition.json', donor['baseline_condition_sha256'])
    check(other/'condition.json', donor['donor_condition_sha256'])
    for family, row in donor['families'].items():
        for arm, root in [('target', base), ('donor', other)]:
            coverage = row['coverage_and_classes'][arm]
            if coverage['missing_cells'] or coverage['produced_cells'] != coverage['expected_cells']:
                raise ValueError('Donor coverage is incomplete')
            check(root/family/'results.json', coverage['results_sha256'])
            check(root/family/'project_contract.json', coverage['project_contract_sha256'])
    section['donor'] = donor | {'source': {'path': str(donor_path), 'sha256': digest(donor_path)}}
    report['updated_utc'] = datetime.now(timezone.utc).isoformat()
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report', type=Path, default=Path('dashboard/report.json'))
    p.add_argument('--durable', type=Path, default=Path('${OLENS_DATA_ROOT}'))
    p.add_argument('--output', type=Path, default=Path('dashboard/report.json'))
    args = p.parse_args()
    updated = attach(json.loads(args.report.read_text()),
        args.durable/'diagnostics/all-candidate-scores-v1/quality-analysis-v2.json',
        args.durable/'runs/development-full-grid-v2/judgments-donor/paired-analysis-v1.json', args.durable)
    args.output.write_text(json.dumps(updated, indent=2) + '\n')
