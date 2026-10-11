"""Paired whole-group uncertainty for the frozen exploratory contrast menu."""
from collections import defaultdict
import numpy as np


def grouped_draws(conditions, group_of, *, replicates=10000, seed=20261011):
    """Return shared bootstrap rates; each value is an item numerator/denominator."""
    if not conditions or not group_of or replicates < 100:
        raise ValueError('Require nonempty counts/groups and at least100 draws')
    item_ids = set(group_of)
    names = sorted(conditions)
    groups = sorted(set(group_of.values()))
    index = {group: i for i, group in enumerate(groups)}
    counts = np.zeros((len(names), len(groups), 2), dtype=float)
    for arm, name in enumerate(names):
        if set(conditions[name]) != item_ids:
            raise ValueError('Every condition must have the identical complete item cohort')
        for item, pair in conditions[name].items():
            value = np.asarray(pair, dtype=float)
            if value.shape != (2,) or not np.isfinite(value).all() or (value < 0).any() or value[0] > value[1]:
                raise ValueError('Invalid numerator/denominator')
            counts[arm, index[group_of[item]]] += value
    rng = np.random.default_rng(seed)
    weights = rng.multinomial(len(groups), np.full(len(groups), 1 / len(groups)), size=replicates)
    numerators = weights @ counts[:, :, 0].T
    denominators = weights @ counts[:, :, 1].T
    rates = np.full_like(numerators, np.nan)
    np.divide(numerators, denominators, out=rates, where=denominators > 0)
    totals = counts.sum(axis=1)
    point = np.full(len(names), np.nan)
    np.divide(totals[:, 0], totals[:, 1], out=point, where=totals[:, 1] > 0)
    return {'names': names, 'rates': rates, 'point': point, 'totals': totals,
            'items': len(item_ids), 'groups': len(groups), 'seed': seed}


def analyze(families, comparisons, *, replicates=10000, seed=20261011,
            require_complete=True):
    """Each family supplies conditions and group_of; comparisons name two arms.

    Resample each family independently, retaining shared draws within it. The
    joint maximum uses all declared contrasts across the different endpoints.
    These bootstrap intervals are approximate, not finite-sample guarantees.
    """
    expected = [(family, pair['reference'], pair['condition'])
                for family in sorted(families) for pair in comparisons]
    if len(set(expected)) != len(expected):
        raise ValueError('Duplicate declared contrast')
    results, missing, centered, nondegenerate = [], [], [], []
    absolute = defaultdict(dict)
    for family_index, family in enumerate(sorted(families)):
        source = families[family]
        draws = grouped_draws(source['conditions'], source['group_of'],
                              replicates=replicates, seed=seed + family_index)
        positions = {name: i for i, name in enumerate(draws['names'])}
        for name, arm in positions.items():
            samples = draws['rates'][:, arm]
            finite = samples[np.isfinite(samples)]
            warnings = []
            if not np.isfinite(draws['point'][arm]):
                warnings.append('Undefined rate: zero total denominator')
            if len(finite) != replicates:
                warnings.append('Some ratio draws are undefined; pointwise interval uses only defined draws')
            if len(finite) > 1 and np.std(finite, ddof=1) <= 1e-14:
                warnings.append('Zero bootstrap variation; the displayed interval does not establish certainty')
            absolute[family][name] = {
                'value': float(draws['point'][arm]) if np.isfinite(draws['point'][arm]) else None,
                'numerator': float(draws['totals'][arm, 0]), 'denominator': float(draws['totals'][arm, 1]),
                'ci95': np.quantile(finite, [.025, .975]).tolist() if len(finite) else None,
                'defined_draws': len(finite), 'bootstrap_replicates': replicates,
                'warnings': warnings,
                'items': draws['items'], 'independent_groups': draws['groups']}
        for pair in comparisons:
            reference, condition = pair['reference'], pair['condition']
            if reference not in positions or condition not in positions:
                missing.append({'family': family, **pair})
                continue
            left, right = positions[reference], positions[condition]
            difference = draws['rates'][:, right] - draws['rates'][:, left]
            estimate = draws['point'][right] - draws['point'][left]
            valid = np.isfinite(difference)
            values = difference[valid]
            std = float(np.std(values, ddof=1)) if len(values) > 1 else None
            row = {'family': family, **pair,
                   'delta': float(estimate) if np.isfinite(estimate) else None,
                   'ci95_delta': np.quantile(values, [.025, .975]).tolist() if len(values) else None,
                   'bootstrap_standard_error': std, 'defined_draws': int(valid.sum()),
                   'bootstrap_replicates': replicates,
                   'items': draws['items'], 'independent_groups': draws['groups'],
                   'simultaneous_ci95_delta': None}
            results.append(row)
            if len(values) != replicates or not np.isfinite(estimate):
                row['warning'] = 'Some ratio draws are undefined; no simultaneous interval for this contrast'
            elif std is None or std <= 1e-14:
                row['warning'] = 'Zero bootstrap variation; no robust zero-uncertainty or significance claim'
            else:
                centered.append(np.abs((difference - estimate) / std))
                nondegenerate.append(row)
    complete = not missing
    if require_complete and not complete:
        critical = None
    elif centered:
        maximum = np.max(np.stack(centered), axis=0)
        critical = float(np.quantile(maximum, .95, method='higher'))
        for row in nondegenerate:
            width = critical * row['bootstrap_standard_error']
            # Keep the pointwise interval visible and inside the reported wider
            # interval even when a skewed bootstrap shifts its endpoints.
            low, high = row['ci95_delta']
            row['simultaneous_ci95_delta'] = [max(-1., min(row['delta'] - width, low)),
                                             min(1., max(row['delta'] + width, high))]
    else:
        critical = None
    return {'conditions': dict(absolute), 'comparisons': results, 'missing_comparisons': missing,
            'comparison_family_complete': complete, 'declared_contrasts': len(expected),
            'effective_non_degenerate_contrasts': len(nondegenerate),
            'joint_interval_contrasts': len(nondegenerate) if critical is not None else 0,
            'joint_critical_value': critical, 'bootstrap_replicates': replicates, 'seed': seed,
            'method': 'Paired whole-group bootstrap; centered standardized joint maximum',
            'limits': ['Exploratory: adjustment does not remove adaptive method history.',
                       'Bootstrap coverage is approximate; zero variation is not robust certainty.',
                       'The four native endpoints measure different things; do not average them.']}
