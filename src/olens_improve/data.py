"""Frozen WorkspaceBench groups and inference-safe cell manifests (stdlib only).

Gold fields are read only to construct opaque grouping keys. Neither gold nor
historical lens outputs enter the generated inference manifest.
"""
from __future__ import annotations

from collections import defaultdict
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import struct
from typing import Any

SOURCE_ROOT = Path('${OLENS_SOURCE_ROOT}')
BENCH_COMMIT = '92d763e722377f5bfae045e829a308ab5919a820'
SPLIT_SEED = 20261010
FAMILIES = ('hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association')
LAYERS = {
    'hallucination': [20, 36, 44, 52, 60],
    'multihop_mt': list(range(20, 61, 4)),
    'chain_intermediates': list(range(20, 61, 4)),
    'role_bound_association': [20, 28, 36, 44, 52, 60],
}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def item_id(item: dict) -> str:
    return re.sub(r'[^A-Za-z0-9._-]', '_', str(item.get('id') or item['name']))


def paths(family: str, root: Path = SOURCE_ROOT) -> dict[str, Path]:
    if family not in FAMILIES:
        raise ValueError(f'Unsupported core family: {family}')
    return {
        'bank': root / 'scratch/repos/workspace-bench-v2/evals' / family / 'items.json',
        'plan': root / 'outputs/wsbench/plan' / f'{family}.jsonl',
        'index': root / 'scratch/wsbench/cells' / f'{family}.index.jsonl',
        'tensor': root / 'scratch/wsbench/cells' / f'{family}.safetensors',
        'meta': root / 'scratch/wsbench/cells' / f'{family}.meta.json',
    }


def load_bank(family: str, root: Path = SOURCE_ROOT) -> list[dict]:
    bank = json.loads(paths(family, root)['bank'].read_text())
    rows = bank if isinstance(bank, list) else bank['items']
    ids = [item_id(x) for x in rows]
    if len(set(ids)) != len(ids):
        raise ValueError(f'Duplicate sanitized IDs in {family}')
    return rows


def _normal(text: str) -> str:
    return ' '.join(text.casefold().split())


def group_items(family: str, rows: list[dict], *, bridge_aliases: bool = False) -> dict[str, list[str]]:
    """Conservative source/template siblings; opaque keys do not reveal gold."""
    groups: dict[str, list[str]] = defaultdict(list)
    if family == 'multihop_mt':
        # Shared bridge labels can make nominally different facts near-duplicates.
        parent = list(range(len(rows)))
        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        seen: dict[str, int] = {}
        for i, row in enumerate(rows):
            labels = [_normal(str(v)) for v in row.get('intermediates', [])]
            if bridge_aliases:
                for bridge in row.get('bridges', []):
                    labels.extend(str(v) for v in bridge.get('answers', []))
                for unit in row.get('units', []):
                    if unit.get('role') != 'target':
                        labels.extend(str(v) for forms in unit.get('forms', {}).values() for v in forms)
                        labels.extend(str(v) for v in unit.get('match', []))
                # Alias lists are bank-authorized equivalences. Removing spaces
                # and punctuation conservatively groups capitalization/format variants.
                labels = ['alias:' + ''.join(c for c in _normal(v) if c.isalnum()) for v in labels]
                labels = [v for v in labels if v != 'alias:']
            labels.append('prompt:' + _normal(row['prompt']))
            for label in labels:
                if label in seen:
                    parent[find(i)] = find(seen[label])
                seen[label] = i
        components: dict[int, list[str]] = defaultdict(list)
        for i, row in enumerate(rows):
            components[find(i)].append(item_id(row))
        for ids in components.values():
            groups[f'{family}:bridge-component:{digest(sorted(ids))[:16]}'] = sorted(ids)
        return dict(groups)
    for row in rows:
        if family == 'role_bound_association':
            key = ('pair', row['pair_id'])
        elif family == 'chain_intermediates':
            key = ('operation-template', row['depth'], row['cond'], row['kinds'])
        else:
            key = ('source-and-exact-prompt', row['source'], _normal(row['prompt']))
        groups[f'{family}:{digest(key)[:16]}'].append(item_id(row))
    return {k: sorted(v) for k, v in groups.items()}


def _take_groups(groups: dict[str, list[str]], target: int, rng: random.Random) -> list[str]:
    """Deterministic subset-sum; retain complete groups and disclose adjusted counts."""
    keys = sorted(groups)
    rng.shuffle(keys)
    reachable: dict[int, tuple[str, ...]] = {0: ()}
    for key in keys:
        for total, chosen in list(reachable.items()):
            new = total + len(groups[key])
            if new not in reachable:
                reachable[new] = chosen + (key,)
    total = min(reachable, key=lambda n: (abs(n - target), n > target, n))
    return list(reachable[total])


def build_splits(root: Path = SOURCE_ROOT, seed: int = SPLIT_SEED) -> dict:
    manifest = {
        'schema_version': 1, 'manifest_id': 'grouped-splits-v1', 'seed': seed,
        'benchmark_commit': BENCH_COMMIT,
        'access_boundary': 'Grouping uses bank metadata/gold only; inference manifests exclude gold. No historical readouts inspected.',
        'group_rules': {
            'hallucination': 'same source and normalized exact prompt',
            'multihop_mt': 'connected components sharing exact normalized bridge labels or exact prompt',
            'chain_intermediates': 'same depth, conditional flag and ordered operation kinds (numeric parameters excluded)',
            'role_bound_association': 'explicit pair_id',
        }, 'families': {},
    }
    for family in FAMILIES:
        p = paths(family, root)
        groups = group_items(family, load_bank(family, root))
        rng = random.Random(f'{seed}:{family}')
        dev = _take_groups(groups, 30, rng)
        remaining = {k: v for k, v in groups.items() if k not in dev}
        val = _take_groups(remaining, 20, rng)
        test = sorted(set(remaining) - set(val))
        selected = {'development': dev, 'validation': val, 'test': test}
        manifest['families'][family] = {
            'bank_path': str(p['bank']), 'bank_sha256': file_hash(p['bank']),
            'read_plan_path': str(p['plan']), 'read_plan_sha256': file_hash(p['plan']),
            'groups': groups,
            'splits': {s: {'group_ids': sorted(gs), 'item_ids': sorted(i for g in gs for i in groups[g])}
                       for s, gs in selected.items()},
            'exclusions': [], 'layers': LAYERS[family],
            'position_contract': 'final_token' if family in ('multihop_mt', 'chain_intermediates') else 'all_frozen_read_sites',
        }
    manifest['content_sha256'] = digest(manifest)
    validate_splits(manifest)
    return manifest


def upgrade_alias_splits(previous: dict, root: Path = SOURCE_ROOT) -> dict:
    """Repair v1's canonical-only bridge groups without promoting observed DEV to holdout."""
    validate_splits(previous)
    manifest = copy.deepcopy(previous)
    manifest.pop('content_sha256', None)
    manifest['manifest_id'] = 'grouped-splits-v2'
    manifest['supersedes_sha256'] = previous['content_sha256']
    manifest['created_utc'] = datetime.now(timezone.utc).isoformat()
    manifest['revision_reason'] = 'Canonical-only MT groups missed shared bank-provided bridge aliases. All v1 development items remain development under transitive alias closure.'
    manifest['group_rules']['multihop_mt'] = 'Transitive components sharing canonical bridge labels or bank-provided bridge aliases/forms; case/spacing/punctuation normalized; exact prompts also grouped'
    family = 'multihop_mt'
    groups = group_items(family, load_bank(family, root), bridge_aliases=True)
    old_dev = set(previous['families'][family]['splits']['development']['item_ids'])
    dev = sorted(g for g, ids in groups.items() if old_dev & set(ids))
    remaining = {g: ids for g, ids in groups.items() if g not in dev}
    val = _take_groups(remaining, 20, random.Random(f'{SPLIT_SEED}:{family}:v2-validation'))
    test = sorted(set(remaining) - set(val))
    cfg = manifest['families'][family]
    cfg['groups'] = groups
    cfg['splits'] = {s: {'group_ids': sorted(gs), 'item_ids': sorted(i for g in gs for i in groups[g])}
                     for s, gs in {'development': dev, 'validation': val, 'test': test}.items()}
    cfg['preserved_v1_development_items'] = sorted(old_dev)
    cfg['alias_closure_added_development_items'] = sorted(set(cfg['splits']['development']['item_ids']) - old_dev)
    if not old_dev <= set(cfg['splits']['development']['item_ids']):
        raise ValueError('Observed development item would enter heldout data')
    if len(val) < 5 or len(test) < 5:
        raise ValueError('Alias closure leaves too few independent heldout groups; report to coordinator')
    manifest['content_sha256'] = digest(manifest)
    validate_splits(manifest)
    return manifest


def validate_splits(manifest: dict) -> None:
    for family, config in manifest['families'].items():
        assigned: set[str] = set()
        for split, data in config['splits'].items():
            expected = {i for g in data['group_ids'] for i in config['groups'][g]}
            if expected != set(data['item_ids']) or assigned & expected:
                raise ValueError(f'Invalid or overlapping groups: {family}/{split}')
            assigned |= expected
        if assigned != {i for group in config['groups'].values() for i in group}:
            raise ValueError(f'Unassigned items: {family}')


def cache_audit(family: str, root: Path = SOURCE_ROOT) -> dict:
    p = paths(family, root)
    meta = json.loads(p['meta'].read_text())
    with p['tensor'].open('rb') as f:
        length = struct.unpack('<Q', f.read(8))[0]
        if length > (1 << 20):
            raise ValueError('Unexpected safetensors header length')
        header = json.loads(f.read(length))
    shape = header['resid']['shape']
    if shape != [meta['n_cells'], 5120] or header['resid']['dtype'] != 'BF16':
        raise ValueError(f'Incompatible cached tensor: {family}')
    if meta['model'] != 'Qwen/Qwen3.6-27B' or not BENCH_COMMIT.startswith(meta['bench_commit']):
        raise ValueError(f'Incompatible cached metadata: {family}')
    return {
        'tensor_path': str(p['tensor']), 'tensor_key': 'resid', 'shape': shape,
        'meta_sha256': file_hash(p['meta']), 'index_sha256': file_hash(p['index']),
        'provenance_status': 'conditional_pending_adapter_off_recapture',
        'missing_provenance': ['full_model_revision', 'tokenizer_revision_and_hash',
                               'per_item_rendered_input_ids_hash', 'explicit_adapter_disabled'],
        'recorded_metadata': meta,
    }


def cells_for_family(family: str, splits: dict, root: Path = SOURCE_ROOT) -> list[dict]:
    config = splits['families'][family]
    if file_hash(paths(family, root)['bank']) != config['bank_sha256']:
        raise ValueError(f'Bank changed after split freeze: {family}')
    if file_hash(paths(family, root)['plan']) != config['read_plan_sha256']:
        raise ValueError(f'Read plan changed after split freeze: {family}')
    assignments = {i: s for s, data in config['splits'].items() for i in data['item_ids']}
    groups = {i: g for g, ids in config['groups'].items() for i in ids}
    p = paths(family, root)
    rows = []
    with p['index'].open() as f:
        for row_index, line in enumerate(f):
            x = json.loads(line)
            if x['id'] not in assignments or x['layer'] not in LAYERS[family]:
                raise ValueError(f'Unexpected cached cell {family}/{x}')
            rows.append({
                'cell_id': f"{family}|{x['id']}|L{x['layer']:02d}|p{x['pos']:05d}",
                'family': family, 'item_id': x['id'], 'layer': x['layer'],
                'position': x['pos'], 'pos': x['pos'], 'token': x['token'],
                'cache_tensor_path': str(p['tensor']), 'cache_tensor_key': 'resid',
                'cache_row': row_index, 'split': assignments[x['id']], 'group_id': groups[x['id']],
                'cache_provenance': 'conditional_pending_adapter_off_recapture',
            })
    if family == 'chain_intermediates':
        final: dict[tuple[str, int], dict] = {}
        for row in rows:
            key = (row['item_id'], row['layer'])
            if key not in final or row['position'] > final[key]['position']:
                final[key] = row
        rows = list(final.values())
    if len({x['cell_id'] for x in rows}) != len(rows):
        raise ValueError(f'Duplicate cell keys: {family}')
    counts = defaultdict(int)
    for x in rows:
        counts[(x['item_id'], x['layer'])] += 1
    for i in assignments:
        for layer in LAYERS[family]:
            count = counts[(i, layer)]
            if count == 0 or (family in ('multihop_mt', 'chain_intermediates') and count != 1):
                raise ValueError(f'Missing/inconsistent cell grid: {family}/{i}/{layer}')
            if family == 'role_bound_association' and count != 19:
                raise ValueError(f'Role position count must be 19, got {count}')
    return sorted(rows, key=lambda x: (x['item_id'], x['layer'], x['position']))


def instrument_manifest(splits: dict, root: Path = SOURCE_ROOT) -> dict:
    """One/two complete development groups, but one read cell per item: not official scores."""
    cells = []
    audits = {}
    for family in FAMILIES:
        config = splits['families'][family]
        # Prefer a small group; choosing by IDs/group size sees no lens result.
        devgroups = config['splits']['development']['group_ids']
        selected_group = min(devgroups, key=lambda g: (abs(len(config['groups'][g]) - 2), digest([SPLIT_SEED, g])))
        ids = set(config['groups'][selected_group])
        plans = {x['id']: x for x in map(json.loads, paths(family, root)['plan'].read_text().splitlines())}
        for i in sorted(ids):
            candidates = [x for x in cells_for_family(family, splits, root) if x['item_id'] == i and x['layer'] == 44]
            cell = max(candidates, key=lambda x: x['position']).copy()
            cell['capture_spec'] = plans[i]  # rendering/input IDs only, never target labels
            cells.append(cell)
        audits[family] = cache_audit(family, root)
    manifest = {
        'schema_version': 1, 'manifest_id': 'development-instrument-v1',
        'split_sha256': splits['content_sha256'], 'split': 'development',
        'sample_prefixes': [1, 2], 'maximum_shared_samples_per_cell': 32,
        'partial_grid': True, 'report_contract': 'Instrument/cell-level only; never official any-cell item recovery.',
        'cells': cells, 'cache_audit': audits,
    }
    manifest['content_sha256'] = digest(manifest)
    return manifest


def read_position_kinds(family: str, cells: list[dict], root: Path = SOURCE_ROOT) -> dict[str, str]:
    """Site-type matching metadata; never answer correctness or readout content."""
    if family == 'hallucination':
        sites = {(item_id(x), int(site['pos'])): site['kind']
                 for x in load_bank(family, root) for site in x['sites']}
        return {c['cell_id']: f"response-site:{sites[(c['item_id'],c['position'])]}" for c in cells}
    if family == 'role_bound_association':
        positions: dict[str, set[int]] = defaultdict(set)
        for cell in cells:
            positions[cell['item_id']].add(cell['position'])
        offsets = {i: {p: j for j, p in enumerate(sorted(ps))} for i, ps in positions.items()}
        return {c['cell_id']: f"summary-suffix-offset:{offsets[c['item_id']][c['position']]:02d}" for c in cells}
    return {c['cell_id']: 'final-prompt-token' for c in cells}


def capture_manifest(splits: dict, root: Path = SOURCE_ROOT) -> dict:
    """Restricted capture-stage inputs, separate from selector candidate access."""
    cells = []
    for family in FAMILIES:
        family_cells = cells_for_family(family, splits, root)
        kinds = read_position_kinds(family, family_cells, root)
        specs = {x['id']: x for x in map(json.loads, paths(family, root)['plan'].read_text().splitlines())}
        for cell in family_cells:
            cells.append({**cell, 'read_position_kind': kinds[cell['cell_id']],
                          'capture_spec': specs[cell['item_id']]})
    manifest = {
        'schema_version': 1, 'manifest_id': 'core-capture-' + splits['manifest_id'].rsplit('-', 1)[1],
        'split_sha256': splits['content_sha256'], 'benchmark_commit': BENCH_COMMIT,
        'access_boundary': 'Capture process may render original model inputs. Selectors/editors must receive only their cell activation/candidates, never these prompts or labels.',
        'activation_policy': 'Fresh adapter-disabled capture; old tensor rows are references only, not trusted sources.',
        'heldout_policy': 'Capture may run for sealed cells; heldout readout generation/inspection requires final freeze.',
        'cells': cells,
    }
    manifest['content_sha256'] = digest(manifest)
    return manifest


def build_control_manifest(splits: dict, root: Path = SOURCE_ROOT, count: int = 8) -> dict:
    """Freeze target->control IDs, drawing exclusively from development groups.

Controls match family, layer and read-position kind. No fallback to validation,
test, same/related groups, or gold-based selection is permitted.
"""
    if count <= 0:
        raise ValueError('Positive number of controls required')
    assignments = {}
    bank = {}
    shortages = {}
    for family in FAMILIES:
        cells = cells_for_family(family, splits, root)
        kinds = read_position_kinds(family, cells, root)
        strata: dict[tuple[int, str], list[dict]] = defaultdict(list)
        for cell in cells:
            if cell['split'] == 'development':
                strata[(cell['layer'], kinds[cell['cell_id']])].append(cell)
                bank[cell['cell_id']] = {k: cell[k] for k in ('family','item_id','group_id','layer','position','split')}
                bank[cell['cell_id']]['read_position_kind'] = kinds[cell['cell_id']]
        missing = 0
        for cell in cells:
            candidates = [c for c in strata[(cell['layer'], kinds[cell['cell_id']])]
                          if c['group_id'] != cell['group_id']]
            candidates.sort(key=lambda c: digest([SPLIT_SEED, cell['cell_id'], c['cell_id']]))
            selected = [c['cell_id'] for c in candidates[:count]]
            assignments[cell['cell_id']] = selected
            missing += len(selected) < count
        shortages[family] = {'target_cells_below_requested_count': missing, 'requested_count': count}
    manifest = {
        'schema_version': 1, 'manifest_id': 'development-matched-controls-' + splits['manifest_id'].rsplit('-', 1)[1],
        'split_sha256': splits['content_sha256'], 'seed': SPLIT_SEED,
        'rule': 'Exact family/layer/read-position-kind; development only; exclude target same/related group; sort SHA256(seed,targetID,controlID). No gold-correctness filtering.',
        'requested_controls_per_cell': count, 'control_bank': bank,
        'control_cell_ids_by_target': assignments, 'shortages': shortages,
        'access_boundary': 'Calibration metadata and cell IDs only; no answers, targets, transcripts or verdicts for selectors.',
        'activation_policy': 'Resolve frozen IDs against fresh capture manifest before scoring; never silently use old cached vectors.',
    }
    manifest['content_sha256'] = digest(manifest)
    return manifest


def development_pilot_manifest(splits: dict, instrument: dict, root: Path = SOURCE_ROOT,
                               target_items_per_family: int = 8) -> dict:
    """Shared ~200-cell partial-grid pilot; preserve all existing instrument cells."""
    all_cells = []
    selection = {}
    for family in FAMILIES:
        config = splits['families'][family]
        required = {x['item_id'] for x in instrument['cells'] if x['family'] == family}
        dev_groups = config['splits']['development']['group_ids']
        chosen = [g for g in dev_groups if required & set(config['groups'][g])]
        remainder = {g: config['groups'][g] for g in dev_groups if g not in chosen}
        current = sum(len(config['groups'][g]) for g in chosen)
        chosen += _take_groups(remainder, max(0, target_items_per_family - current),
                               random.Random(f'{SPLIT_SEED}:{family}:shared-pilot'))
        ids = sorted(i for g in chosen for i in config['groups'][g])
        family_cells = cells_for_family(family, splits, root)
        for i in ids:
            positions = sorted({c['position'] for c in family_cells if c['item_id'] == i})
            selected_positions = {positions[0], positions[len(positions)//2], positions[-1]}
            all_cells.extend(c for c in family_cells if c['item_id'] == i
                             and c['layer'] in (20, 44, 60) and c['position'] in selected_positions)
        selection[family] = {'group_ids': sorted(chosen), 'item_ids': ids,
                             'cell_count': sum(x['family'] == family for x in all_cells)}
    if not {c['cell_id'] for c in instrument['cells']} <= {c['cell_id'] for c in all_cells}:
        raise ValueError('Shared pilot must include existing stochastic instrument cells')
    manifest = {
        'schema_version': 1, 'manifest_id': 'development-shared-pilot-v2',
        'split_sha256': splits['content_sha256'], 'seed': SPLIT_SEED,
        'instrument_parent_sha256': instrument['content_sha256'],
        'selection_rule': 'Keep instrument groups; deterministic whole-group subset sum towards8items/family. Layers20/44/60, first/middle/last frozen sites; MT/chain finaltoken only. No readout/judge/gold-based selection.',
        'partial_grid': True, 'report_contract': 'Paired cell-level diagnostics only; not official any-cell or any-layer item recovery.',
        'maximum_shared_samples_per_cell': 32, 'prefixes': [1,2,4,8,16,32],
        'families': selection, 'cells': sorted(all_cells, key=lambda x: x['cell_id']),
    }
    manifest['content_sha256'] = digest(manifest)
    return manifest


def write_immutable(path: Path, value: dict) -> None:
    """A rerun may confirm an identical freeze, never silently replace one."""
    rendered = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text() != rendered:
            raise FileExistsError(f'Frozen manifest differs: {path}; create a new explicit version')
        return
    with path.open('x') as f:
        f.write(rendered)
