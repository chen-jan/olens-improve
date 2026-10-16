"""Smoke-test manifests (CPU): 2 items per family x 2 layers, cut from the production manifests.

Run with NT_DATA=<newtasks/data/smoke> and NT_STAGES (shard count 1 per stage), e.g.
  NT_DATA=.../data/smoke NT_STAGES='{"p0":["user_modeling",4,1],"ca":["conjunctive_association",32,1],
  "umA":["user_modeling",32,1],"umB":["user_modeling",32,1]}' python -B code/smoke_setup.py

Writes NT_DATA/manifests/{capture.json, gen_p0.json, gen_ca.json, gen_umA.json, gen_umB.json, smoke.json}
and NT_DATA/control/stages.json. The capture manifest also holds HALL_CELLS: core-v1 hallucination cells
with their exact core-v1 capture_spec (checked against the core-v1 audit's capture_spec_sha256), so
the smoke capture can be compared with the core-v1 activation rows (validates the capture path).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ntcommon as C  # noqa: E402

UM_ITEMS = ('um-sd-country-10', 'um-ss-continent-02')  # both are P0 items (selfdescribe, synthsys)
CA_ITEMS = ('q01_a', 'q01_b')                           # one contrast cluster (child / spouse)
LAYERS = (36, 52)                                        # = the P0 layers
CORE = Path('${OLENS_COMPUTE_ROOT}/activations/core-v1')
HALL_CELLS = ('hallucination|chat-dailydialog-0002|L36|p00020', 'hallucination|chat-dailydialog-0002|L52|p00020')


def main():
    root = C.DATA
    if root.resolve() == (C.NT / 'data').resolve() or not os.environ.get('NT_STAGES'):
        raise SystemExit('set NT_DATA to the smoke root and NT_STAGES')
    real = C.NT / 'data/manifests'
    out = root / 'manifests'
    out.mkdir(parents=True, exist_ok=True)
    keep_items = set(UM_ITEMS) | set(CA_ITEMS)
    cap = json.loads((real / 'capture.json').read_text())
    cells = [c for c in cap['cells'] if c['item_id'] in keep_items and c['layer'] in LAYERS]
    # core-v1 hallucination cells, exact spec
    fresh = json.loads((CORE / 'fresh_manifest_v2.json').read_text())
    audit = {r['cell_id']: r for r in json.loads((CORE / 'capture_audit.json').read_text())['cells']}
    by_id = {c['cell_id']: c for c in fresh['cells']}
    hall_ref = {}
    for cid in HALL_CELLS:
        c = by_id[cid]
        spec = c['capture_spec']
        key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()
        a = audit[cid]
        if key != a['capture_spec_sha256']:
            raise SystemExit(f'{cid}: capture_spec differs from the one core-v1 captured')
        cells.append({'cell_id': cid, 'family': c['family'], 'item_id': c['item_id'], 'layer': c['layer'],
                      'position': c['position'], 'token': c['token'], 'capture_spec': spec,
                      'smoke_reference': 'core-v1'})
        hall_ref[cid] = {'core_activation_row': a['activation_row'], 'core_activation_sha256': a['activation_sha256'],
                         'core_tensor': str(CORE / 'activations.safetensors'), 'capture_spec_sha256': key}
    capture = dict(cap, cells=cells, note=cap.get('note', '') + ' | SMOKE subset + core-v1 reference cells')
    C.atomic_text(out / 'capture.json', json.dumps(capture, indent=1, ensure_ascii=False) + '\n')
    cap_sha = C.file_sha(out / 'capture.json')
    counts = {}
    for stage, (fam, n, shards) in C.STAGES.items():
        man = json.loads((real / f'gen_{stage}.json').read_text())
        g = [c for c in man['cells'] if c['item_id'] in keep_items and c['layer'] in LAYERS]
        payload = dict(man, n=n, shard_count=shards, capture_manifest_sha256=cap_sha, cells=g)
        C.atomic_text(out / f'gen_{stage}.json', json.dumps(payload, indent=1, ensure_ascii=False) + '\n')
        counts[stage] = {'cells': len(g), 'n': n, 'readouts': len(g) * n, 'shards': shards}
    C.atomic_json(root / 'control/stages.json', {'enabled': list(C.STAGES), 'note': 'smoke'})
    info = {'um_items': UM_ITEMS, 'ca_items': CA_ITEMS, 'layers': LAYERS, 'capture_cells': len(cells),
            'capture_sha256': cap_sha, 'stages': counts, 'hall_reference': hall_ref}
    C.atomic_json(out / 'smoke.json', info)
    print(json.dumps(info, indent=1))


if __name__ == '__main__':
    main()
