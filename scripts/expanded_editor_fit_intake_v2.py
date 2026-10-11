"""Offline editor FVE authority: canonical event linkage and raw source pins.

Normalization is proved through the approved scorer/dispatch/whitening sources,
not attributed to metadata absent from the editor event.
"""
import hashlib
import json
import math
from pathlib import Path

NORMALIZATION = {'center_predictions': True, 'whitening_ridge_c': .1,
    'unit_phrase_directions': True, 'phrase_norm_epsilon': 1e-9,
    'target_unit_normalized': False, 'clip_fve': False, 'scored_atom_tokens': 32}


def canonical_digest(value):
    # Exact olens_improve.ar_cache.digest serialization, including ensure_ascii.
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def pinned_editor_spec(spec, pins):
    """A canonical linkage never substitutes for the independent raw-file pin."""
    path = str(spec)
    if path not in pins:
        raise ValueError('Editor spec lacks raw file authority')
    body = Path(spec).read_bytes()
    if hashlib.sha256(body).hexdigest() != pins[path]:
        raise ValueError('Editor spec changed after raw pin')
    contract = json.loads(body)
    return contract, canonical_digest(contract)


def validate_event_linkage(event, contract, linkage):
    if event['spec_sha256'] != linkage or event['round'] != contract['round']:
        raise ValueError('Editor event canonical spec/round linkage differs')


def normalized_pins(pins):
    result = {str(Path(path).resolve()): value for path, value in pins.items()}
    if len(result) != len(pins):
        raise ValueError('Repeated aliases in editor code authority')
    return result


OPTIONS = {'--proposals', '--cells-manifest', '--fresh-manifest', '--checkpoint',
    '--production-cache', '--edit-cache', '--whitener-directory', '--output',
    '--runtime', '--round', '--batch-size', '--sealed-manifest', '--history'}


def unique_dispatch_arguments(command):
    """Reject argv that could differ under producer argparse last-option rules."""
    if len(command) < 2 or len(command[2:]) % 2:
        raise ValueError('Malformed editor command argument pairs')
    arguments = {}
    for option, value in zip(command[2::2], command[3::2]):
        if option not in OPTIONS or option in arguments or not isinstance(value, str) or value.startswith('--'):
            raise ValueError('Duplicate/unknown/malformed editor command option')
        arguments[option] = value
    if not OPTIONS - {'--history'} <= set(arguments):
        raise ValueError('Editor command omits required frozen options')
    return arguments


def validate_editor_authority(contract, authority, dispatch, folder, family_cells, terminal, pin):
    if authority['solver'] != 'scipy_exact' or authority['objective'] != '1-squared_residual/squared_target' or authority['normalization'] != NORMALIZATION:
        raise ValueError('Unapproved editor scoring normalization')
    if contract['sealed_manifest_sha256'] != authority['manifest_sha256'] or contract['vector_contract']['sha256'] != authority['vector_contract_sha256']:
        raise ValueError('Editor scoring authority differs from sealed cohort')
    if normalized_pins(contract['code_sha256']) != normalized_pins(authority['code_sha256']):
        raise ValueError('Unapproved editor/scorer implementation')
    for path, value in authority['code_sha256'].items():
        pin(path, value)
    original = authority['whitening_authority']; pin(original['path'], original['sha256'])
    policy_source = authority['dispatch_policy']; pin(policy_source['path'], policy_source['sha256'])
    policy = json.loads(Path(policy_source['path']).read_text())
    original_pins = json.loads(Path(original['path']).read_text())['source_sha256']
    for layer in {c['layer'] for c in family_cells.values()}:
        path = str(Path(authority['whitener_directory']) / f'whitening_iolens_pooled_L{layer}.safetensors')
        expected = authority['whitener_sha256'].get(path)
        if expected is None or original_pins.get(path) != expected:
            raise ValueError('Whitening artifact lacks original fit authority')
        pin(path, expected)
    tasks = []
    for task in dispatch['tasks']:
        command = task['command']
        if len(command) < 2 or command[1] != 'scripts/expanded_encode_edits.py':
            continue  # Other sealed tasks include the earlier likelihood producer.
        arguments = unique_dispatch_arguments(command)
        if Path(arguments['--output']).resolve() == folder.resolve():
            tasks.append(task)
    if len(tasks) != 1:
        raise ValueError('Editor terminal lacks unique approved dispatch task')
    task = tasks[0]; command = task['command']
    arguments = unique_dispatch_arguments(command)
    arg = lambda name: arguments[name]
    signature = hashlib.sha256(json.dumps(task, sort_keys=True).encode()).hexdigest()
    completion = dispatch['completed_tasks'].get(task['id'], {})
    if completion.get('task_sha256') != signature:
        raise ValueError('Editor dispatch task lacks matching successful service receipt')
    for field in ('seconds', 'finished_unix'):
        value = completion.get(field)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0 or field == 'finished_unix' and value == 0:
            raise ValueError('Invalid completed editor task timing receipt')
    if not str(completion.get('job_id', '')).isdigit() or int(completion['job_id']) <= 0:
        raise ValueError('Completed editor task lacks valid allocation receipt')
    expected_id = f'editing-round{contract["round"]}-{folder.name}-v1'
    if task['id'] != expected_id or task['sealed_manifest'] != policy['sealed_manifest']:
        raise ValueError('Editor task family/round/seal metadata differs')
    for argument, field in (('--checkpoint', 'checkpoint'), ('--production-cache', 'production_cache'), ('--edit-cache', 'edit_cache'), ('--whitener-directory', 'whitener_directory'), ('--runtime', 'runtime'), ('--sealed-manifest', 'sealed_manifest')):
        if arg(argument) != policy[field]:
            raise ValueError('Editor dispatch differs from immutable approved policy')
    if command[0] != policy['python'] or policy['sealed_manifest_sha256'] != authority['manifest_sha256']:
        raise ValueError('Editor dispatch executable/seal differs')
    if arg('--whitener-directory') != authority['whitener_directory'] or arg('--round') != str(contract['round']) or arg('--batch-size') != str(contract['batch_size']):
        raise ValueError('Editor dispatch scoring arguments differ')
    if command[1] != 'scripts/expanded_encode_edits.py':
        raise ValueError('Editor dispatch uses a different producer')
    task_pins = normalized_pins({p['path']: p['sha256'] for p in task['pins']})
    for path, value in authority['code_sha256'].items():
        if task_pins.get(str(Path(path).resolve())) != value:
            raise ValueError('Editor dispatch omits approved code authority')
    for source in task['pins']:
        pin(source['path'], source['sha256'])
    descriptor_path = Path(policy['descriptors']) / f'round{contract["round"]}-{folder.name}.json'
    descriptor_sha = task_pins.get(str(descriptor_path.resolve()))
    if descriptor_sha is None:
        raise ValueError('Editor task omits immutable family descriptor authority')
    pin(descriptor_path, descriptor_sha)
    descriptor = json.loads(descriptor_path.read_text())
    if descriptor['id'] != expected_id or descriptor['family'] != folder.name or descriptor['round'] != contract['round'] or Path(descriptor['output']).resolve() != folder.resolve():
        raise ValueError('Editor immutable descriptor task metadata differs')
    for argument, field in (('--proposals', 'proposals'), ('--cells-manifest', 'cells_manifest')):
        source = descriptor[field]
        if arg(argument) != source['path'] or task_pins.get(str(Path(source['path']).resolve())) != source['sha256']:
            raise ValueError('Editor descriptor source differs from signed task')
    for argument, field in (('--proposals', 'proposal_sha256'), ('--cells-manifest', 'cells_manifest_sha256'), ('--fresh-manifest', 'fresh_manifest_sha256'), ('--sealed-manifest', 'sealed_manifest_sha256')):
        pin(arg(argument), contract[field])
    if contract['round'] == 2:
        pin(arg('--history'), contract['history_sha256'])
        history = descriptor['history']
        if history['path'] != arg('--history') or history['sha256'] != contract['history_sha256'] or task_pins.get(str(Path(history['path']).resolve())) != history['sha256']:
            raise ValueError('Editor history differs from immutable descriptor/task')
    elif contract['round'] != 1 or contract['history_sha256'] is not None:
        raise ValueError('Invalid editor round/history authority')
    elif '--history' in arguments or descriptor['history'] is not None:
        raise ValueError('Round1 unexpectedly consumes a history source')
    if contract['beam_width'] != 2 or contract['production_cache_read_only'] is not True or set(contract['candidate_ids']) != set(family_cells):
        raise ValueError('Editor candidate/beam/source policy differs')
    if terminal['cells'] != len(family_cells) or terminal['round'] != contract['round']:
        raise ValueError('Editor terminal coverage differs')
    return {'authority_scope': 'approved_code_dispatch_and_original_whitening; not event metadata',
        'canonical_spec_sha256': canonical_digest(contract), 'round': contract['round'],
        'family': folder.name, 'sites': len(family_cells), 'dispatch_task_id': task['id'],
        'dispatch_task_sha256': signature, 'dispatch_task': task,
        'completed_task_receipt': dispatch['completed_tasks'][task['id']]}
