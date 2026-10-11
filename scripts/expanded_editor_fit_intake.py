"""Offline editor FVE authority: canonical event linkage and raw source pins.

Normalization is proved through the approved scorer/dispatch/whitening sources,
not attributed to metadata absent from the editor event.
"""
import hashlib
import json
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
        if '--output' in command and Path(command[command.index('--output') + 1]).resolve() == folder.resolve():
            tasks.append(task)
    if len(tasks) != 1:
        raise ValueError('Editor terminal lacks unique approved dispatch task')
    task = tasks[0]; command = task['command']
    arg = lambda name: command[command.index(name) + 1]
    signature = hashlib.sha256(json.dumps(task, sort_keys=True).encode()).hexdigest()
    if dispatch['completed_tasks'].get(task['id'], {}).get('task_sha256') != signature:
        raise ValueError('Editor dispatch task lacks matching successful service receipt')
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
    for argument, field in (('--proposals', 'proposal_sha256'), ('--cells-manifest', 'cells_manifest_sha256'), ('--fresh-manifest', 'fresh_manifest_sha256'), ('--sealed-manifest', 'sealed_manifest_sha256')):
        pin(arg(argument), contract[field])
    if contract['round'] == 2:
        pin(arg('--history'), contract['history_sha256'])
    elif contract['round'] != 1 or contract['history_sha256'] is not None:
        raise ValueError('Invalid editor round/history authority')
    if contract['beam_width'] != 2 or contract['production_cache_read_only'] is not True or set(contract['candidate_ids']) != set(family_cells):
        raise ValueError('Editor candidate/beam/source policy differs')
    if terminal['cells'] != len(family_cells) or terminal['round'] != contract['round']:
        raise ValueError('Editor terminal coverage differs')
    return {'authority_scope': 'approved_code_dispatch_and_original_whitening; not event metadata',
        'canonical_spec_sha256': canonical_digest(contract), 'round': contract['round'],
        'family': folder.name, 'sites': len(family_cells), 'dispatch_task_id': task['id'],
        'dispatch_task_sha256': signature, 'dispatch_task': task,
        'completed_task_receipt': dispatch['completed_tasks'][task['id']]}
