#!/usr/bin/env python3
"""Descriptive emitted-output behavior on the complete, pinned target-only cohort.

No fitting, inference, judging, confidence intervals, or trace-based pruning claims.
Run real input scans inside an allocated Slurm CPU step.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import statistics
import tempfile

from merge_target_only_search import IDENTITY, Sources

SEAL = '181fcc259ed81213a7b26ea18142b6cd35648e89b83100a5cf07590ed75b2c47'
PARENTS = {'repeat_swap-n32': 'pooled_greedy_swap-n32',
    'repeat_swap_then_prune_005-n32': 'repeat_swap-n32',
    'bounded_prune_refill_005-n32': 'pooled_greedy_swap_then_prune_0.005-n32',
    'repeated_swaps_random_delete_match_005-n32': 'repeat_swap-n32'}
TITLES = {'hallucination': 'Hallucination (chat)', 'multihop_mt': 'Multihop (multi-token)',
    'chain_intermediates': 'Chained intermediates', 'role_bound_association': 'Role-bound association'}


def lines(path):
    with Path(path).open() as stream:
        for line in stream:
            if line.strip():
                yield json.loads(line)


def condition(s):
    return f"{s['method']}-n{s['n']}"


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def exact_fve(s):
    if s.get('fits_scope') not in (None, 'emitted_bullets'):
        raise ValueError('Exact FVE does not describe emitted bullets')
    value = s.get('fits', {}).get('exact', {}).get('fve')
    if not number(value):
        raise ValueError('Emitted selection lacks finite exact FVE')
    return value


def reduce_parent(s, require_fve=True):
    if not isinstance(s.get('text'), str) or any(type(s.get(k)) is not int or s[k] < 0
            for k in ('token_count', 'bullet_count')):
        raise ValueError('Invalid parent output')
    result = {k: s[k] for k in ('text', 'token_count', 'bullet_count')}
    if require_fve:
        result['fve'] = exact_fve(s)
    return result


def describe(values):
    return {'count': len(values), 'mean': statistics.mean(values), 'median': statistics.median(values),
            'minimum': min(values), 'maximum': max(values), 'sum': sum(values)} if values else {'count': 0}


class Behavior:
    def __init__(self):
        self.values = defaultdict(list)
        self.counts = Counter()
        self.k = Counter()
        self.flags = Counter()

    def add(self, selected, parent, atoms):
        new = reduce_parent(selected)
        ids = selected['phrase_ids']
        if len(ids) != new['bullet_count'] or len(set(ids)) != len(ids):
            raise ValueError('Selected phrase/count mismatch')
        truncated = 0
        for pid in ids:
            atom = atoms[pid]
            n = atom['original_token_count']
            if type(n) is not int or n < 0 or atom.get('truncated') is not (n > 32):
                raise ValueError('Invalid selected AR truncation metadata')
            if len(atom['scored_token_ids']) != min(n, 32):
                raise ValueError('Selected atom scored-token length differs')
            truncated += n > 32
        changed = new['text'] != parent['text']
        delta = new['bullet_count'] - parent['bullet_count']
        self.counts.update({'outputs': 1, 'text_changed': int(changed),
            'same_bullet_count_different_text': int(changed and delta == 0),
            'fewer_bullets': int(delta < 0), 'same_bullets': int(delta == 0), 'more_bullets': int(delta > 0),
            'selected_bullets': len(ids), 'selected_truncated_ar_bullets': truncated,
            'outputs_with_selected_truncated_ar_bullet': int(truncated > 0)})
        self.k[new['bullet_count']] += 1
        for name, value in {'new_bullet_count': new['bullet_count'], 'parent_bullet_count': parent['bullet_count'],
                'bullet_count_delta': delta, 'new_token_count': new['token_count'],
                'parent_token_count': parent['token_count'], 'token_count_delta': new['token_count']-parent['token_count'],
                'new_exact_fve': new['fve'], 'parent_exact_fve': parent['fve'],
                'paired_exact_fve_delta': new['fve']-parent['fve']}.items():
            self.values[name].append(value)
        # Only terminal flags and saved budget fields: exploratory trace moves
        # (especially cached_parent_fallback) never establish output behavior.
        self.flags.update(set(selected.get('stop_flags', [])))
        for key, value in selected.get('budget', {}).items():
            if number(value):
                self.values['budget.'+key].append(value)

    def result(self):
        n = self.counts['outputs']
        bullets = self.counts['selected_bullets']
        return {'counts': dict(self.counts), 'output_proportions': {k: self.counts[k]/n for k in
            ('text_changed', 'same_bullet_count_different_text', 'fewer_bullets', 'same_bullets', 'more_bullets',
             'outputs_with_selected_truncated_ar_bullet')},
            'selected_truncated_ar_bullet_proportion': self.counts['selected_truncated_ar_bullets']/bullets if bullets else None,
            'final_output_k_counts': {str(k): v for k, v in sorted(self.k.items())},
            'saved_numeric_fields': {k: describe(v) for k, v in sorted(self.values.items())},
            'stop_flag_output_counts': dict(sorted(self.flags.items()))}


def descriptors(directory, wanted, seal, sources, cells):
    index = {}
    for path in sorted(Path(directory).glob('**/*.ready.json')):
        d = json.loads(path.read_text())
        own = {condition(s) for s in d.get('conditions', [])} & wanted
        if not own:
            continue
        d = sources.load(path)
        if d.get('ready') is not True or d.get('partial_grid') or d.get('inventory_sha256') != seal:
            raise ValueError('Require sealed complete ready descriptors')
        family = d['family']
        manifest = sources.load(d['manifest'], d['manifest_sha256'])
        sources.pin(d['selections'], d['selection_sha256'])
        expected = {cid: c for cid, c in cells.items() if c['family'] == family}
        actual = {c['cell_id']: c for c in manifest['cells']}
        if (manifest.get('inventory_sha256') != seal or manifest.get('partial_grid') or
                len(actual) != len(manifest['cells']) or actual.keys() != expected.keys()):
            raise ValueError('Descriptor manifest has partial/foreign cohort')
        if any(any(c.get(k) != expected[cid][k] for k in IDENTITY if k != 'group_id') for cid, c in actual.items()):
            raise ValueError('Original cohort identity differs')
        if d.get('cells') != len(expected) or d.get('items') != len({c['item_id'] for c in expected.values()}):
            raise ValueError('Descriptor declared cohort counts differ')
        for key in own:
            if (key, family) in index:
                raise ValueError('Duplicate ready descriptor')
            index[key, family] = d
    if set(index) != {(key, family) for key in wanted for family in {c['family'] for c in cells.values()}}:
        raise ValueError('Missing complete method/family descriptors')
    return index


def checked_rows(d, wanted, cells, seal, new=False):
    expected = {cid for cid, c in cells.items() if c['family'] == d['family']}
    seen = set()
    for row in lines(d['selections']):
        cid = row['cell_id']
        identity = IDENTITY if new else tuple(k for k in IDENTITY if k != 'group_id')
        if cid in seen or cid not in expected or any(row.get(k) != cells[cid][k] for k in identity):
            raise ValueError('Selection identity/duplicate differs')
        if new and (row.get('inventory_sha256') != seal or row.get('search_spec_sha256') !=
                d.get('search_spec_sha256_by_cell', {}).get(cid, d.get('search_spec_sha256'))):
            raise ValueError('Selection source authority differs')
        seen.add(cid)
        selected = {key: [s for s in row['selections'] if condition(s) == key] for key in wanted}
        if any(len(v) != 1 for v in selected.values()):
            raise ValueError('Missing/duplicate required selection')
        yield cid, row, {k: v[0] for k, v in selected.items()}
    if seen != expected:
        raise ValueError('Incomplete full-family selection rows')


def fitted_parents(index, wanted, sources, cells):
    """Recover FVE stripped from old display exports from their pinned journals."""
    paths = {}
    for d in index.values():
        for pin in d['source_parents']:
            if pin['path'] in paths and paths[pin['path']] != pin['sha256']:
                raise ValueError('Conflicting source parent pins')
            paths[pin['path']] = pin['sha256']
    output = {}
    for path, seal in sorted(paths.items()):
        sources.pin(path, seal)
        for row in lines(path):
            cid = row['cell_id']
            if cid not in cells or any(row.get(k) != cells[cid][k] for k in IDENTITY if k != 'group_id'):
                raise ValueError('Fitted old source parent identity differs')
            for s in row['selections']:
                key = condition(s)
                if key not in wanted:
                    continue
                reduced = reduce_parent(s)
                pair = cid, key
                if pair in output:
                    raise ValueError('Duplicate fitted old parent record')
                output[pair] = reduced
    if set(output) != {(cid, key) for cid in cells for key in wanted}:
        raise ValueError('Incomplete fitted old parent cohort')
    return output


def summarize(args):
    if not os.environ.get('SLURM_JOB_ID') or not os.environ.get('SLURM_STEP_ID'):
        raise ValueError('Real source scanning requires an allocated Slurm CPU step')
    sources = Sources()
    inventory = sources.load(args.inventory, args.inventory_sha256)
    config = sources.load(args.api_config)
    if inventory.get('status') != 'sealed' or {c['condition_id']: c['actual_parent'] for c in inventory['conditions']} != PARENTS:
        raise ValueError('Sealed method/actual-parent contract differs')
    old_seal = config['baseline_inventory_sha256']
    old_inventory = sources.load(config['baseline_inventory'], old_seal)
    if old_inventory['fresh_manifest'] != inventory['fresh_manifest']:
        raise ValueError('Actual parents use a different original capture')
    fresh = sources.load(inventory['fresh_manifest']['path'], inventory['fresh_manifest']['sha256'])
    cells = {c['cell_id']: c for c in fresh['cells']}
    items = {(c['family'], c['item_id']) for c in cells.values()}
    if (len(cells) != len(fresh['cells']) or len(cells) != 19435 or len(items) != 469 or
            inventory['expected']['cells'] != len(cells) or inventory['expected']['items'] != len(items) or
            set(inventory['families']) != set(TITLES) or {c['family'] for c in cells.values()} != set(TITLES)):
        raise ValueError('Require exact full19435site/469question cohort')
    new_index = descriptors(args.ready_directory, set(PARENTS), args.inventory_sha256, sources, cells)
    old_wanted = set(PARENTS.values()) - set(PARENTS)
    old_index = descriptors(config['baseline_descriptor_snapshot'], old_wanted, old_seal, sources, cells)
    fitted = fitted_parents(old_index, old_wanted, sources, cells)
    summaries = {}
    for family in inventory['families']:
        old = {}
        paths = defaultdict(set)
        for key in old_wanted:
            paths[old_index[key, family]['selections']].add(key)
        for path, wanted in paths.items():
            d = next(old_index[k, family] for k in wanted)
            for cid, _, selected in checked_rows(d, wanted, cells, old_seal):
                for key, s in selected.items():
                    parent = fitted[cid, key]
                    if reduce_parent(s, require_fve=False) != {k: parent[k] for k in ('text', 'token_count', 'bullet_count')}:
                        raise ValueError('Fitted parent differs from complete sealed old selection')
                    old.setdefault(cid, {})[key] = parent
        own = {k: Behavior() for k in PARENTS}
        # Merged new family rows must carry the whole four-method menu.
        if len({new_index[k, family]['selections'] for k in PARENTS}) != 1:
            raise ValueError('Require a single merged complete new family source')
        d = new_index[next(iter(PARENTS)), family]
        for cid, row, selected in checked_rows(d, set(PARENTS), cells, args.inventory_sha256, new=True):
            raw_atoms = row['atoms']
            atoms = {a['phrase_id']: a for a in raw_atoms} if isinstance(raw_atoms, list) else raw_atoms
            if len(atoms) != len(raw_atoms):
                raise ValueError('Duplicate source atoms')
            for key, s in selected.items():
                if s['bullet_count'] > 4 or s['token_count'] > 256:
                    raise ValueError('Emitted output cap differs')
                if key != 'repeated_swaps_random_delete_match_005-n32':
                    budget = s.get('budget', {})
                    if (budget.get('subset_fit_budget') != inventory['search']['subset_fit_budget'] or
                            type(budget.get('subset_fits')) is not int or
                            not 0 <= budget['subset_fits'] <= inventory['search']['subset_fit_budget']):
                        raise ValueError('Saved distinct subset fit budget differs')
                parent_key = PARENTS[key]
                parent = reduce_parent(selected[parent_key]) if parent_key in selected else old[cid][parent_key]
                own[key].add(s, parent, atoms)
                summaries.setdefault(key, {'overall': Behavior(), 'families': {}})['overall'].add(s, parent, atoms)
        for key, behavior in own.items():
            summaries[key]['families'][family] = {'display_name': TITLES[family], **behavior.result()}
    sources.verify()
    return {'schema_version': 'target-only-emitted-behavior-v1', 'status': 'complete',
        'created_utc': datetime.now(timezone.utc).isoformat(), 'cells': len(cells), 'questions': len(items),
        'scope': 'Descriptive paired activation-site summaries on all four previously inspected banks; no CIs or significance.',
        'original_released_oracle_lens_reference': {'condition': 'raw_n1-n1', 'exact_fve': None,
            'status': 'unavailable_in_this_supplement; original raw FVE is not substituted by capped/four-bullet FVE'},
        'interpretation': 'Changes compare final emitted text with the declared actual parent. More/fewer/same bullet counts describe final refills relative to old plain-pool pruning. Trace actions, including cached_parent_fallback, are ignored. Saved unique subset fits are per-selector counts; summing reused budgets does not establish physical effort.',
        'methods': {k: {'actual_parent': PARENTS[k], 'overall': v['overall'].result(), 'families': v['families']}
                    for k, v in summaries.items()},
        'source_sha256': {str(p): pin[0] for p, pin in sorted(sources.pins.items())}}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inventory', type=Path, default=Path('configs/target_only_inventory_v2.json'))
    p.add_argument('--inventory-sha256', default=SEAL)
    p.add_argument('--api-config', type=Path, default=Path('configs/target_only_api_v1.json'))
    p.add_argument('--ready-directory', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = summarize(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=args.output.parent, delete=False) as stream:
        json.dump(result, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
        temp = Path(stream.name)
    temp.replace(args.output)
    print(json.dumps({'status': result['status'], 'cells': result['cells'], 'questions': result['questions'], 'output': str(args.output)}))


if __name__ == '__main__':
    main()
