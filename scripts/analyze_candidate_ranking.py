"""Evaluation-only within-cell availability/FVE ranking; never an inference selector."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.evaluation import paired_group_interval


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def pair_rank(rows, good, bad):
    positives = [r['fve'] for r in rows if good(r)]
    negatives = [r['fve'] for r in rows if bad(r)]
    wins = sum((p > n) + .5 * (p == n) for p in positives for n in negatives)
    return wins, len(positives) * len(negatives)


def interval(rows, key, reference):
    """Each cell retains its contribution; resample whole related source groups."""
    return paired_group_interval({r['cell_id']: r[reference] for r in rows},
        {r['cell_id']: r[key] for r in rows}, {r['cell_id']: r['group_id'] for r in rows})


def analyze(args):
    manifest = load(args.manifest)
    cells = {r['cell_id']: r for r in manifest['cells']}
    if any(r['split'] != 'development' for r in cells.values()):
        raise ValueError('Only development diagnostic is authorized')
    by_site = {(r['family'], r['item_id'], r['layer'], r['position']): cid for cid, r in cells.items()}
    scores = lines(args.scores)
    if len(scores) != len(cells) * 32:
        raise ValueError('Expected complete shared N32 score export')
    score_map = {}
    for row in scores:
        key = (row['cell_id'], row['source_sample_index'])
        if key in score_map or row['cell_id'] not in cells:
            raise ValueError('Duplicate or unexpected score cell')
        if row['text_sha256'] != hashlib.sha256(row['text'].encode()).hexdigest():
            raise ValueError('Scored text hash mismatch')
        score_map[key] = row
    if set(score_map) != {(cid, i) for cid in cells for i in range(32)}:
        raise ValueError('Incomplete candidate indices')
    labels = {}
    provenance = []
    for index in range(32):
        root = args.judgments / f'candidate_index_{index:02d}-n32'
        identity = load(root / 'condition.json')
        if identity['manifest_sha256'] != sha(args.manifest):
            raise ValueError('Judged manifest differs')
        for family in sorted(manifest['families']):
            contract = load(root / family / 'project_contract.json')
            results_path = root / family / 'results.json'
            results = load(results_path)
            readouts = lines(root / f'{family}.readouts.jsonl')
            for row in readouts:
                cid = by_site[(family, row['id'], row['layer'], row['pos'])]
                if row['samples'] != [score_map[(cid, index)]['text']]:
                    raise ValueError('Judged text differs from exact FVE text')
            if family == 'hallucination':
                coverage = contract['hallucination_stage2']
                if coverage['stage1_api_or_missing_readouts'] or coverage['stage2_api_or_missing_readouts']:
                    raise ValueError('Incomplete hallucination stages cannot establish all-bad pools')
                for row in results['rows']:
                    cid = by_site[(family, row['id'], row['layer'], row['pos'])]
                    if len(row['verdict']) != 1:
                        raise ValueError('Expected one verdict per readout')
                    v = row['verdict'][0]
                    labels[(cid, index)] = {'class': v['class'], 'kind': v['kind'], 'claims': v['claims']}
            else:
                coverage = contract['cell_diagnostic']
                if coverage['api_or_missing_unjudged_cells']:
                    raise ValueError('Incomplete recovery pool')
                for row in coverage['rows']:
                    cid = by_site[(family, row['item_id'], row['layer'], row['position'])]
                    labels[(cid, index)] = {'pass': row['pass']}
            provenance.append({'condition': index, 'family': family, 'results_sha256': sha(results_path),
                'project_contract_sha256': sha(root / family / 'project_contract.json')})
    if labels.keys() != score_map.keys():
        raise ValueError('Labels do not cover all candidates')
    original = {r['cell_id']: next(s for s in r['selections'] if s['method'] == 'best_n_exact' and s['n'] == 32)
                for r in lines(args.a32_selections)}
    diagnostics = []
    for cid, cell in sorted(cells.items()):
        candidates = []
        for i in range(32):
            score = score_map[(cid, i)]
            candidates.append({'sample_index': i, 'fve': score['fits']['exact']['fve'],
                'a_eligible': score['a_eligible'], 'parser_flags': score['parser_flags'],
                'token_count': score['token_count'], 'bullet_count': score['bullet_count'],
                'has_unscored_suffix': any(a['truncated'] for a in score['atoms']),
                'effective_ar_key_multiset': sorted(a['cache_key'] for a in score['atoms']),
                **labels[(cid, i)]})
        eligible = [r for r in candidates if r['a_eligible']]
        if not eligible:
            raise ValueError('A32 fallback requires explicit separate handling')
        selected = max(eligible, key=lambda r: (r['fve'], -r['sample_index']))
        if score_map[(cid, selected['sample_index'])]['text'] != original[cid]['text']:
            raise ValueError('Exact ranking does not reproduce original A32 emitted text')
        common = {'cell_id': cid, 'family': cell['family'], 'item_id': cell['item_id'], 'group_id': cell['group_id'],
            'layer': cell['layer'], 'position': cell['position'], 'eligible_count': len(eligible),
            'disqualified_count': 32 - len(eligible), 'selected_index': selected['sample_index'],
            'selected_token_count': selected['token_count'], 'candidates': candidates}
        input_groups = defaultdict(list)
        for candidate in eligible:
            input_groups[tuple(candidate['effective_ar_key_multiset'])].append(candidate)
        collisions = []
        for key, group in input_groups.items():
            if len(group) < 2:
                continue
            texts = {score_map[(cid, r['sample_index'])]['text'] for r in group}
            if len(texts) < 2:
                continue
            changed = len({r.get('class', r.get('pass')) for r in group}) > 1
            collisions.append({'indices': [r['sample_index'] for r in group],
                'distinct_full_texts': len(texts), 'different_quality_labels': changed,
                'fve_range': max(r['fve'] for r in group) - min(r['fve'] for r in group),
                'effective_ar_key_multiset': list(key),
                'texts_and_labels': [{'sample_index': r['sample_index'],
                    'text': score_map[(cid, r['sample_index'])]['text'],
                    'class': r.get('class'), 'pass': r.get('pass'), 'has_unscored_suffix': r['has_unscored_suffix']}
                    for r in group]})
        common['same_effective_inputs_different_text_groups'] = collisions
        disagreements = Counter()
        comparisons = Counter()
        def good(row):
            return row['class'] == 'consistent' if cell['family'] == 'hallucination' else row['pass']
        def bad(row):
            return row['class'] == 'hallucinated' if cell['family'] == 'hallucination' else not row['pass']
        for left in eligible:
            if not good(left):
                continue
            for right in eligible:
                if not bad(right):
                    continue
                category = ('both' if left['has_unscored_suffix'] and right['has_unscored_suffix'] else
                    'only_good' if left['has_unscored_suffix'] else 'only_bad' if right['has_unscored_suffix'] else 'neither')
                comparisons[category] += 1
                disagreements[category] += left['fve'] < right['fve']
        common['good_vs_bad_rank_pairs_by_suffix'] = dict(comparisons)
        common['strict_fve_disagreements_by_suffix'] = dict(disagreements)
        if cell['family'] != 'hallucination':
            good = [r for r in eligible if r['pass']]
            rank = pair_rank(eligible, lambda r: r['pass'], lambda r: not r['pass'])
            common.update({'selected': [int(selected['pass']), 1], 'random_expected': [len(good) / len(eligible), 1],
                'available': [int(bool(good)), 1], 'rank_pairs': list(rank),
                'rank_half': [.5 * rank[1], rank[1]], 'all_good': len(good) == len(eligible),
                'all_bad': len(good) == 0, 'missed_available': bool(good) and not selected['pass']})
        else:
            asserting = [r for r in eligible if r['class'] in ('hallucinated', 'consistent', 'off_topic')]
            counts = Counter(r['class'] for r in eligible)
            sclass = selected['class']
            rank = pair_rank(asserting, lambda r: r['class'] != 'hallucinated', lambda r: r['class'] == 'hallucinated')
            semantic_rank = pair_rank(asserting, lambda r: r['class'] == 'consistent', lambda r: r['class'] == 'hallucinated')
            common.update({'selected': [int(sclass == 'hallucinated'), int(sclass in ('hallucinated', 'consistent', 'off_topic'))],
                'random_expected': [counts['hallucinated'] / len(eligible), len(asserting) / len(eligible)],
                'consistent_available': bool(counts['consistent']), 'nonwrong_asserting_available': bool(counts['consistent'] + counts['off_topic']),
                'selected_class': sclass, 'eligible_class_counts': dict(counts), 'rank_pairs': list(rank),
                'rank_half': [.5 * rank[1], rank[1]], 'consistent_vs_wrong_rank_pairs': list(semantic_rank),
                'asserting_candidate_count': len(asserting), 'no_asserting_candidates': not asserting,
                'all_wrong_asserting': bool(asserting) and counts['hallucinated'] == len(asserting),
                'selected_claims': selected['claims']})
        diagnostics.append(common)
    summary = {}
    for family in sorted(manifest['families']):
        rows = [r for r in diagnostics if r['family'] == family]
        def total(k):
            num = sum(r[k][0] for r in rows); den = sum(r[k][1] for r in rows)
            return {'numerator': num, 'denominator': den, 'rate': num / den if den else None}
        ranks = [r['rank_pairs'][0] / r['rank_pairs'][1] for r in rows if r['rank_pairs'][1]]
        result = {'cells': len(rows), 'items': len({r['item_id'] for r in rows}), 'independent_groups': len({r['group_id'] for r in rows}),
            'eligible_candidates': sum(r['eligible_count'] for r in rows), 'disqualified_candidates': sum(r['disqualified_count'] for r in rows),
            'selected': total('selected'), 'random_expected': total('random_expected'),
            'selected_minus_random_group_interval': interval(rows, 'selected', 'random_expected'),
            'within_cell_rank_pooled_pairs': total('rank_pairs'), 'within_cell_rank_equal_cell_mean': statistics.mean(ranks) if ranks else None,
            'rank_mixed_cells': len(ranks), 'rank_undefined_cells': len(rows) - len(ranks),
            'rank_minus_half_group_interval': interval(rows, 'rank_pairs', 'rank_half'),
            'selected_mean_tokens': statistics.mean(r['selected_token_count'] for r in rows)}
        collisions = [c for r in rows for c in r['same_effective_inputs_different_text_groups']]
        result['scorer_suffix_diagnostic'] = {
            'eligible_candidates_with_unscored_suffix': sum(c['has_unscored_suffix'] for r in rows for c in r['candidates'] if c['a_eligible']),
            'same_effective_inputs_different_text_groups': len(collisions),
            'same_effective_inputs_different_quality_groups': sum(c['different_quality_labels'] for c in collisions),
            'strict_disagreements_by_suffix': {k: sum(r['strict_fve_disagreements_by_suffix'].get(k, 0) for r in rows)
                for k in ('both', 'only_good', 'only_bad', 'neither')},
            'compared_pairs_by_suffix': {k: sum(r['good_vs_bad_rank_pairs_by_suffix'].get(k, 0) for r in rows)
                for k in ('both', 'only_good', 'only_bad', 'neither')},
            'note': 'Exact effective token/cache-key multiset, preserving duplicate multiplicity. Different labels can reflect unscored content or judge variation; inspect text before interpreting.'}
        if family != 'hallucination':
            result.update({'available': total('available'), 'missed_available_cells': sum(r['missed_available'] for r in rows),
                'all_good_cells': sum(r['all_good'] for r in rows), 'all_bad_cells': sum(r['all_bad'] for r in rows)})
        else:
            result.update({'consistent_available_cells': sum(r['consistent_available'] for r in rows),
                'nonwrong_asserting_available_cells': sum(r['nonwrong_asserting_available'] for r in rows),
                'selected_classes': dict(Counter(r['selected_class'] for r in rows)),
                'no_asserting_candidate_cells': sum(r['no_asserting_candidates'] for r in rows),
                'all_wrong_asserting_cells': sum(r['all_wrong_asserting'] for r in rows),
                'consistent_vs_wrong_pair_counts': {'wins': sum(r['consistent_vs_wrong_rank_pairs'][0] for r in rows),
                    'pairs': sum(r['consistent_vs_wrong_rank_pairs'][1] for r in rows)}})
        summary[family] = result
    artifact = {'analysis_status': 'complete_development_partial_grid', 'manifest_sha256': sha(args.manifest),
        'scores_sha256': sha(args.scores), 'a32_selection_sha256': sha(args.a32_selections),
        'judged_conditions': 32, 'judged_candidates': len(labels), 'missing_candidates': 0,
        'bootstrap_seed': 20261010, 'bootstrap_replicates': 2000,
        'random_note': 'Uniform sampling among originally A-eligible candidates, retaining sample multiplicity. Hall ratio of expected count contributions, not expectation of a random realized ratio.',
        'limitations': ['Development partial grids; few independent groups.', 'Official recovery is not precision for additional emitted facts.',
            'Judge-derived available pools are noisy optimistic evaluation-only ceilings.', 'Shared cached verdicts are not independent judge repeats.',
            'Raw FVE is compared within cells only; equality ties count half.'],
        'families': summary, 'cells': diagnostics, 'judgment_provenance': provenance}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--scores', type=Path, required=True)
    p.add_argument('--judgments', type=Path, required=True)
    p.add_argument('--a32-selections', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    analyze(p.parse_args())
