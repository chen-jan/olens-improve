"""Frozen selector cohort inputs; historical pools are provenance, not observations."""
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
from .ar_cache import input_records
from .stage_io import validate_export_stage
from .models import BASE_REVISION, PAIR_REVISION


def terminal_source(path, cohort_sha):
    path = Path(path); body = path.read_bytes(); digest = sha256(body).hexdigest()
    if body and not body.endswith(b'\n'):
        raise ValueError('Terminal selector source contains an uncommitted tail')
    status_path = path.with_suffix('.status.json')
    flat_path = path.with_suffix('.manifest.json')
    if status_path.exists():
        status = json.loads(status_path.read_text())
        if status.get('status') != 'complete' or status.get('journal_sha256') != digest:
            raise ValueError('Journal is not the committed terminal snapshot')
        parents = None
    elif flat_path.exists():
        status = json.loads(flat_path.read_text())
        if status.get('flat_sha256') != digest or status.get('cohort_manifest_sha256') != cohort_sha:
            raise ValueError('Flat selector snapshot does not bind this exact cohort')
        parents = status.get('parent_journal_sha256')
        if not parents: raise ValueError('Flat snapshot lacks immutable source parents')
        for name, expected in parents.items():
            parent = Path(name); actual = sha256(parent.read_bytes()).hexdigest()
            terminal = json.loads(parent.with_suffix('.status.json').read_text())
            if actual != expected or terminal.get('status') != 'complete' or terminal.get('journal_sha256') != expected:
                raise ValueError('Flat snapshot parent is not immutable/terminal')
    else:
        raise ValueError('Require terminal journal or exact source-bound flat snapshot')
    return body, {'path': str(path), 'sha256': digest, 'terminal_status': status,
                  'parent_journal_sha256': parents}


def load_selector_inputs(paths, cohort_body, fresh_body, gate_body=None):
    stage, cohort, captures = validate_export_stage(cohort_body, fresh_body, gate_body)
    for cid, cell in cohort.items():
        if cell['group_id'] != captures[cid]['group_id'] or captures[cid].get('adapter_disabled') is not True:
            raise ValueError('Frozen cohort group/adapters differ from verified fresh capture')
    cohort_sha = sha256(cohort_body).hexdigest()
    records = defaultdict(dict); seen = set(); sources = []; excluded = 0; global_pool_id = None
    for path in paths:
        body, source = terminal_source(path, cohort_sha); sources.append(source)
        for row in input_records(body):
            cid, index = row['cell_id'], row['sample_index']
            if row.get('base_revision') != BASE_REVISION or row.get('adapter_revision') != PAIR_REVISION:
                raise ValueError('Source verbalizer revisions differ from the frozen model/pair')
            pool_id = row.get('global_pool_id')
            if not isinstance(pool_id, str) or not pool_id:
                raise ValueError('Missing explicit global pool identity')
            if global_pool_id is None: global_pool_id = pool_id
            elif pool_id != global_pool_id: raise ValueError('Mixed global pool identities')
            if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < 32:
                raise ValueError('Invalid source sample index')
            if (cid, index) in seen: raise ValueError('Duplicate cell/sample record, including history')
            seen.add((cid, index))
            if cid not in captures: raise ValueError('Source cell absent from frozen fresh capture')
            capture = captures[cid]
            if any(row[k] != capture[k] for k in ('family', 'item_id', 'layer', 'position')):
                raise ValueError('Source identity differs from verified capture')
            if row['activation_sha256'] != capture['activation_sha256']:
                raise ValueError('Source activation differs from verified capture')
            if row.get('split', capture['split']) != capture['split']:
                raise ValueError('Source stage differs from verified capture')
            if cid not in cohort:
                excluded += 1; continue
            records[cid][index] = row
    if set(records) != set(cohort) or any(set(rows) != set(range(32)) for rows in records.values()):
        raise ValueError('Frozen target cohort requires complete distinct N32 samples')
    return stage, cohort, captures, dict(records), sources, excluded


def validate_controls(controls, target_ids, cohort, captures):
    """No donor selection: consume the caller's frozen DEV-only matched bank."""
    bank = {}
    for cid in target_ids:
        own = cohort[cid]
        control_ids = controls['control_cell_ids_by_target'][cid]
        if not control_ids: raise ValueError('Scheduled E comparison requires nonempty frozen matched controls for every target')
        if len(set(control_ids)) != len(control_ids): raise ValueError('Duplicate frozen control ID')
        own_meta = controls.get('target_metadata', {}).get(cid, controls['control_bank'].get(cid, own))
        if any(own_meta[k] != own[k] for k in ('family', 'item_id', 'group_id', 'layer', 'position', 'split')):
            raise ValueError('Frozen target control metadata differs from target cohort')
        kind = own_meta.get('read_position_kind', own.get('read_position_kind'))
        if control_ids and kind is None: raise ValueError('Frozen target read-position kind required')
        for donor in control_ids:
            if donor not in captures: raise ValueError('Frozen donor has no verified fresh capture')
            other = captures[donor]; ref = controls['control_bank'][donor]
            if other['split'] != 'development' or other['group_id'] == own['group_id'] or other.get('adapter_disabled') is not True:
                raise ValueError('Control must be DEV and outside the target related group')
            if any(ref[k] != other[k] for k in ('family', 'item_id', 'group_id', 'layer', 'position', 'split')):
                raise ValueError('Control metadata differs from verified capture')
            if ref['family'] != own['family'] or ref['layer'] != own['layer'] or ref.get('read_position_kind') != kind:
                raise ValueError('Control has unmatched family/layer/read-position kind')
        bank[cid] = control_ids
    return bank
