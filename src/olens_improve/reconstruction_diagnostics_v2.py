"""Descriptive paired site-weighted FVE change with whole-group resampling."""
import hashlib
import numpy as np


def grouped_fit_summary(fit, group_of, *, replicates=10000, seed=20261011, stream=''):
    """Absolute mean on valid sites, resampling whole related-question groups."""
    valid = {k: v for k, v in fit.items() if v is not None}
    if not valid:
        return {'mean_fve_ci95': None, 'independent_scored_groups': 0,
                'defined_mean_bootstrap_draws': 0,
                'mean_fve_warnings': ['No valid reconstruction sites; mean interval is undefined']}
    paired = paired_fit_change(valid, {k: 0. for k in valid}, group_of,
                              replicates=replicates, seed=seed, stream=stream)
    warnings = []
    if paired['warning']:
        warnings.append(paired['warning'])
    values = np.array(list(valid.values()), dtype=float)
    if np.max(np.abs(values)) <= 1e-12 or np.max(np.abs(values-1.)) <= 1e-12:
        warnings.append('All observed fits lie at zero or one; the boundary interval does not establish population certainty')
    return {'mean_fve_ci95': paired['ci95_delta'],
            'independent_scored_groups': paired['independent_groups'],
            'defined_mean_bootstrap_draws': paired['defined_bootstrap_draws'],
            'mean_fve_bootstrap_replicates': replicates,
            'mean_fve_weighting': paired['weighting'], 'mean_fve_warnings': warnings}


def paired_fit_change(proposed, reference, group_of, *, replicates=10000, seed=20261011, stream='', equivalence_tolerance=1e-5):
    if equivalence_tolerance < 0 or not np.isfinite(equivalence_tolerance):
        raise ValueError('Invalid site-change numerical tolerance')
    ids = sorted(k for k in proposed.keys() & reference.keys()
                 if proposed[k] is not None and reference[k] is not None)
    if not ids:
        return {'paired_sites':0,'independent_groups':0,'mean_delta':None,'ci95_delta':None,
                'warning':'No common valid reconstruction sites'}
    before = np.array([reference[k] for k in ids], dtype=float)
    after = np.array([proposed[k] for k in ids], dtype=float)
    if not np.isfinite(before).all() or not np.isfinite(after).all():
        raise ValueError('Nonfinite paired FVE')
    delta = after-before; groups = sorted({group_of[k] for k in ids})
    totals = np.array([sum(float(d) for k,d in zip(ids,delta) if group_of[k]==g) for g in groups])
    counts = np.array([sum(group_of[k]==g for k in ids) for g in groups],dtype=float)
    offset = int.from_bytes(hashlib.sha256(stream.encode()).digest()[:8], 'big')
    rng = np.random.default_rng((seed+offset) % (2**64))
    draws = rng.integers(0,len(groups),size=(replicates,len(groups)))
    samples = totals[draws].sum(axis=1)/counts[draws].sum(axis=1)
    interval = np.quantile(samples,[.025,.975]).tolist()
    return {'paired_sites':len(ids),'independent_groups':len(groups),
            'reference_mean_same_mask':float(before.mean()),'proposed_mean_same_mask':float(after.mean()),
            'mean_delta':float(delta.mean()),'median_delta':float(np.median(delta)),
            'ci95_delta':interval,'bootstrap_replicates':replicates,'defined_bootstrap_draws':replicates,
            'improved_sites':int((delta>equivalence_tolerance).sum()),
            'worsened_sites':int((delta < -equivalence_tolerance).sum()),
            'unchanged_or_within_numerical_tolerance':int((np.abs(delta)<=equivalence_tolerance).sum()),
            'site_change_equivalence_tolerance':equivalence_tolerance,
            'warning':'Zero bootstrap variation; descriptive interval does not establish certainty or significance' if float(np.std(samples)) <= 1e-15 else None,
            'weighting':'equal activation sites within resampled whole related-question groups',
            'interpretation':'post-hoc secondary diagnostic; pointwise interval; outside 496 headline contrasts'}
