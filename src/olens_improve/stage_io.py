"""Stage identity for frozen artifact exporters; no scientific gate creation."""
from hashlib import sha256
import json

from .ar_partition import validate_stage


def intended_stage(manifest):
    cells = {c['cell_id']: c for c in manifest['cells']}
    stages = {c['split'] for c in cells.values()}
    if len(cells) != len(manifest['cells']) or len(stages) != 1:
        raise ValueError('Require unique cells from exactly one intended stage')
    stage = next(iter(stages))
    if stage not in ('development', 'validation', 'test') or manifest.get('split', stage) != stage:
        raise ValueError('Manifest split differs from its cells')
    return stage, cells


def validate_export_stage(manifest_body, fresh_body=None, gate_body=None):
    manifest = json.loads(manifest_body)
    stage, cells = intended_stage(manifest)
    if stage != 'development' and (fresh_body is None or gate_body is None):
        raise ValueError('Validation/test exporters require exact fresh capture and coordinator gate')
    if gate_body is not None:
        if fresh_body is None:
            raise ValueError('A coordinator gate requires the bound fresh capture manifest')
        return validate_stage(manifest, sha256(manifest_body).hexdigest(), json.loads(fresh_body),
                              sha256(fresh_body).hexdigest(), json.loads(gate_body))
    captures = {}
    if fresh_body is not None:
        fresh = json.loads(fresh_body)
        rows = fresh['cells'] if isinstance(fresh, dict) else fresh
        captures = {c['cell_id']: c for c in rows}
        if len(captures) != len(rows):
            raise ValueError('Duplicate fresh capture cell')
        for cid, cell in cells.items():
            if cid not in captures or any(cell[k] != captures[cid][k]
                                          for k in ('family', 'item_id', 'layer', 'position', 'split')):
                raise ValueError('Frozen cohort differs from fresh capture')
    return stage, cells, captures


def original_prefix_overlap(original, wanted):
    expected = {}
    seen = set()
    for row in original:
        key = row['cell_id'], row['sample_index']
        if key in seen:
            raise ValueError('Duplicate original instrument record')
        seen.add(key)
        if row['cell_id'] in wanted:
            expected[key] = row
    return expected
