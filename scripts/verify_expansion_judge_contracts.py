#!/usr/bin/env python3
"""Pure offline validation of expansion terminal artifacts against approved pins.

Only the standard library is imported. No inference, client, benchmark loader,
or network code is loaded. A caller must supply an independently approved
pre-expansion receipt SHA; this module does not confer approval on a receipt.
The verifier checks provenance, not native outcomes or their aggregation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

BENCHMARK_COMMIT = '92d763e722377f5bfae045e829a308ab5919a820'
FAMILIES = ('hallucination', 'multihop_mt', 'chain_intermediates', 'role_bound_association')
OUTER_FIELDS = {'scientific_status', 'inventory_sha256', 'original_splits_preserved'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def valid_sha(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value) is not None


def json_equal(left, right):
    """Compare JSON payloads without Python's True == 1 coercion."""
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def validate_runtime_hashes(hashes):
    require(isinstance(hashes, dict) and bool(hashes), 'Runtime hash pin must be a nonempty dictionary')
    for path, digest in hashes.items():
        require(isinstance(path, str), 'Runtime source path must be text')
        parts = PurePosixPath(path)
        require(not parts.is_absolute() and '..' not in parts.parts and path.startswith('src/wsbench/'),
                'Runtime source path must be relative to the benchmark checkout')
        require(valid_sha(digest), 'Runtime source hash must be a lowercase SHA-256')
    return dict(hashes)


def json_pointer(body, pointer):
    """Resolve an explicit RFC 6901 pointer; never guess a pin from a document."""
    require(isinstance(pointer, str) and (not pointer or pointer.startswith('/')), 'Invalid JSON pointer')
    for part in pointer.split('/')[1:] if pointer else ():
        part = part.replace('~1', '/').replace('~0', '~')
        body = body[int(part)] if isinstance(body, list) else body[part]
    return body


def load_approved_runtime_pin(path, expected_sha256, *, pointer='/runtime_source_hashes'):
    """Bind runtime hashes to exact receipt bytes and an explicit field location."""
    require(valid_sha(expected_sha256), 'An approved receipt SHA-256 is required')
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'Approved runtime receipt bytes changed')
    body = json.loads(raw)
    hashes = validate_runtime_hashes(json_pointer(body, pointer))
    return hashes


def verify_judge_contract(*, family, method, n, expected_cells, inventory_sha256,
                          descriptor, summary, result, contract,
                          approved_runtime_source_hashes):
    """Validate one terminal family; returns a receipt or raises ValueError.

    Normalization permits ONLY the three documented outer metadata updates.
    Upstream complete/pinned flags are intentionally preserved, not required.
    """
    require(family in FAMILIES, 'Unknown family')
    require(isinstance(method, str) and bool(method), 'Expected method is required')
    require(type(n) is int and n > 0, 'Expected N must be a positive integer')
    require(type(expected_cells) is int and expected_cells > 0, 'Expected cell count must be positive')
    require(valid_sha(inventory_sha256), 'Invalid inventory SHA-256')
    approved = validate_runtime_hashes(approved_runtime_source_hashes)
    require(descriptor.get('family') == family and descriptor.get('ready') is True,
            'Wrong or unready family descriptor')
    require(descriptor.get('inventory_sha256') == inventory_sha256, 'Descriptor inventory differs')
    for field in ('manifest_sha256', 'selection_sha256'):
        require(valid_sha(descriptor.get(field)), 'Descriptor has invalid ' + field)
    menu = descriptor.get('conditions')
    require(isinstance(menu, list), 'Descriptor conditions must be an already loaded list')
    require(sum(isinstance(c, dict) and c.get('method') == method and type(c.get('n')) is int and c['n'] == n
                for c in menu) == 1, 'Condition is absent or duplicated in descriptor')

    require(result.get('family') == family, 'Result family differs')
    require(isinstance(result.get('config'), dict) and result['config'].get('dry_run') is False,
            'Result must explicitly be non-dry-run')
    require(contract.get('benchmark_commit') == BENCHMARK_COMMIT, 'Benchmark revision differs')
    for field in ('manifest_expected_cells', 'manifest_produced_cells'):
        require(type(contract.get(field)) is int and contract[field] == expected_cells, 'Wrong ' + field)
    require(type(contract.get('manifest_missing_cells')) is int and contract['manifest_missing_cells'] == 0,
            'Contract has missing cells')
    require(contract.get('partial_grid') is False, 'Contract is not an explicit full grid')
    require(contract.get('project_reasoning_effort') == 'none', 'Judge effort differs')
    require(contract.get('project_judge_model') == ('regex' if family == 'multihop_mt' else 'gpt-6-luna'),
            'Judge model differs')
    require(contract.get('runtime_source_hashes') == approved, 'Runtime hashes differ from approved pre-expansion pin')

    scientific = summary.get('condition')
    require(isinstance(scientific, dict), 'Missing terminal scientific condition')
    require(scientific.get('method') == method and type(scientific.get('n')) is int and scientific['n'] == n,
            'Terminal scientific method/N differs')
    for field, expected in (('inventory_sha256', inventory_sha256),
                            ('manifest_sha256', descriptor['manifest_sha256']),
                            ('selection_sha256', descriptor['selection_sha256'])):
        require(scientific.get(field) == expected, 'Terminal scientific ' + field + ' differs')
    require(scientific.get('partial_grid') is False, 'Scientific condition is not an explicit full grid')
    coverage = scientific.get('coverage')
    require(isinstance(coverage, dict), 'Scientific condition lacks coverage')
    for field in ('expected_cells', 'produced_cells'):
        require(type(coverage.get(field)) is int and coverage[field] == expected_cells, 'Wrong scientific ' + field)
    require(coverage.get('missing_cell_ids') == [] and type(coverage.get('readouts_per_cell')) is int
            and coverage['readouts_per_cell'] == 1, 'Scientific coverage is incomplete or not single-readout')
    families = summary.get('families')
    require(isinstance(families, dict) and set(families) == {family}, 'Terminal summary has wrong family set')
    terminal = families[family]
    require(isinstance(terminal, dict) and json_equal(terminal.get('upstream'), result),
            'Terminal upstream payload differs from result file')
    embedded = terminal.get('project_contract')
    require(isinstance(embedded, dict), 'Terminal summary lacks embedded project contract')
    current = {'scientific_status': 'exploratory-full-bank-comparison',
               'inventory_sha256': inventory_sha256, 'original_splits_preserved': True}
    for field, expected in current.items():
        require(contract.get(field) == expected and type(contract.get(field)) is type(expected),
                'Wrong external contract ' + field)
        if field == 'scientific_status':
            require(embedded.get(field) in ('frozen-grid-comparison', expected), 'Wrong embedded scientific status')
        elif field in embedded:
            require(embedded[field] == expected and type(embedded[field]) is type(expected),
                    'Wrong embedded contract ' + field)
    left = {k: v for k, v in embedded.items() if k not in OUTER_FIELDS}
    right = {k: v for k, v in contract.items() if k not in OUTER_FIELDS}
    require(json_equal(left, right), 'Embedded/external contract differs outside the three documented metadata updates')
    return {'status': 'verified', 'condition': f'{method}-n{n}', 'family': family,
            'expected_cells': expected_cells, 'inventory_sha256': inventory_sha256,
            'benchmark_commit': BENCHMARK_COMMIT,
            'runtime_source_count': len(approved), 'inference_calls': 0,
            'preserved_upstream_complete': result.get('complete'),
            'preserved_upstream_pinned_instrument': result.get('pinned_instrument')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('summary', 'result', 'contract', 'descriptor', 'runtime-receipt'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--runtime-receipt-sha256', required=True)
    parser.add_argument('--runtime-hashes-pointer', default='/runtime_source_hashes')
    parser.add_argument('--family', choices=FAMILIES, required=True)
    parser.add_argument('--method', required=True)
    parser.add_argument('--n', type=int, required=True)
    parser.add_argument('--expected-cells', type=int, required=True)
    parser.add_argument('--inventory-sha256', required=True)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    hashes = {}

    def read(path):
        raw = path.read_bytes()
        hashes[str(path)] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    pin_body = read(args.runtime_receipt)
    require(hashes[str(args.runtime_receipt)] == args.runtime_receipt_sha256,
            'Approved runtime receipt bytes changed')
    pin = validate_runtime_hashes(json_pointer(pin_body, args.runtime_hashes_pointer))
    objects = {name: read(getattr(args, name)) for name in ('summary', 'result', 'contract', 'descriptor')}
    descriptor = objects['descriptor']
    if isinstance(descriptor.get('conditions'), str):
        descriptor['conditions'] = read(Path(descriptor['conditions']))
    receipt = verify_judge_contract(family=args.family, method=args.method, n=args.n,
        expected_cells=args.expected_cells, inventory_sha256=args.inventory_sha256,
        approved_runtime_source_hashes=pin, **objects)
    for path, expected in hashes.items():
        require(hashlib.sha256(Path(path).read_bytes()).hexdigest() == expected, 'Verifier source changed: ' + path)
    receipt.update(source_sha256=hashes, runtime_pin_pointer=args.runtime_hashes_pointer,
                   verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    rendered = json.dumps(receipt, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.output.with_name(args.output.name + '.tmp')
        temporary.write_text(rendered)
        temporary.replace(args.output)
    print(rendered, end='')


if __name__ == '__main__':
    main()
