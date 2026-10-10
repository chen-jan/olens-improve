#!/usr/bin/env python3
"""Freeze grouped bank splits and a tiny inference-safe development instrument."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from olens_improve.data import (SOURCE_ROOT, FAMILIES, build_splits, cells_for_family,
                                instrument_manifest, write_immutable, capture_manifest,
                                build_control_manifest, validate_splits, upgrade_alias_splits,
                                development_pilot_manifest)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-root', type=Path, default=SOURCE_ROOT)
    parser.add_argument('--splits', type=Path, default=Path('configs/splits_v2.json'))
    parser.add_argument('--instrument', type=Path, default=Path('configs/splits_pilot_instrument_v1.json'))
    parser.add_argument('--capture-manifest', type=Path, help='Restricted full capture manifest; keep outside Git')
    parser.add_argument('--controls', type=Path, help='Full frozen control assignments; keep outside Git')
    parser.add_argument('--shared-pilot', type=Path, default=Path('configs/splits_pilot_shared_v2.json'))
    args = parser.parse_args()
    if args.splits.exists():
        splits = json.loads(args.splits.read_text())
        validate_splits(splits)
    elif args.splits.name == 'splits_v2.json':
        previous = json.loads(Path('configs/splits_v1.json').read_text())
        splits = upgrade_alias_splits(previous, args.source_root)
    else:
        splits = build_splits(args.source_root)
    write_immutable(args.splits, splits)
    if args.instrument.exists():
        # The original8-cell smoke artifact remains historically exact; all its
        # observed IDs were explicitly preserved as development in v2.
        instrument = json.loads(args.instrument.read_text())
    else:
        instrument = instrument_manifest(splits, args.source_root)
        write_immutable(args.instrument, instrument)
    write_immutable(args.shared_pilot, development_pilot_manifest(splits, instrument, args.source_root))
    if args.capture_manifest:
        write_immutable(args.capture_manifest, capture_manifest(splits, args.source_root))
    if args.controls:
        write_immutable(args.controls, build_control_manifest(splits, args.source_root))
    summary = {}
    for family in FAMILIES:
        cells = cells_for_family(family, splits, args.source_root)
        summary[family] = {
            'groups': len(splits['families'][family]['groups']),
            'items': {s: len(v['item_ids']) for s, v in splits['families'][family]['splits'].items()},
            'official_cells': len(cells),
            'instrument_cells': sum(x['family'] == family for x in instrument['cells']),
        }
    print(json.dumps({'splits': str(args.splits), 'instrument': str(args.instrument),
                      'families': summary, 'paid_calls': 0}, indent=2))


if __name__ == '__main__':
    main()
