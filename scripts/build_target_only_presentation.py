"""Additive, source-bound dashboard and compact slide supplement.

No inference, fitting or statistics are performed. Use a new output directory.
Native results enter through --analysis, --inventory and an exact --review pin.
Without reviewed results --pending renders methods with no invented outcomes.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import shutil
import subprocess
import textwrap

from build_slides import text, rect, line, write_html, write_pptx

ROOT = Path(__file__).resolve().parents[1]
RAW = 'raw_n1-n1'
CAP = 'capped_n1-n1'
POOL = 'pooled_greedy_swap-n32'
REPEAT = 'repeat_swap-n32'
TASKS = {
    'hallucination': ('Hallucination (chat)', 'Contradicting readouts; lower is better'),
    'multihop_mt': ('Multihop (multi-token)', 'Required entities; higher is better'),
    'chain_intermediates': ('Chained intermediates', 'Intermediate numbers; higher is better'),
    'role_bound_association': ('Role-bound association', 'Entity-role bindings; higher is better'),
}
MENU = {
    RAW: ('Original released Oracle Lens', None),
    CAP: ('Original, four bullets', RAW),
    'best_n_exact-n32': ('Best complete sample / 32', CAP),
    POOL: ('Plain pooled / 32', 'best_n_exact-n32'),
    'pooled_greedy_swap_then_prune_0.005-n32': ('Plain pool, then prune', POOL),
    'pooled_greedy_swap_random_delete_matched_0.005-n32': ('Plain pool, random deletion', POOL),
    REPEAT: ('Repeat bullet swaps', POOL),
    'repeat_swap_then_prune_005-n32': ('Repeat swaps, then prune', REPEAT),
    'bounded_prune_refill_005-n32': ('Prune and refill', 'pooled_greedy_swap_then_prune_0.005-n32'),
    'repeated_swaps_random_delete_match_005-n32': ('Repeat swaps, random deletion', REPEAT),
}
INK, MUTED, TEAL, BLUE, ORANGE, LINE = '183449', '526979', '087F83', '286AAD', 'AA701F', 'D8E3EA'


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def pending():
    return {'schema_version': 'target-only-presentation-v1', 'status': 'running',
            'coverage': {'questions': 469, 'cells': 19435, 'all_previously_inspected': True},
            'methods': [{'id': key, 'label': name, 'parent_id': parent, 'is_new': i >= 6,
                         'metrics': {}, 'comparisons': {}, 'examples': []}
                        for i, (key, (name, parent)) in enumerate(MENU.items())],
            'source_hashes': {}, 'root_review': None}


def validate(data):
    if data.get('schema_version') != 'target-only-presentation-v1':
        raise ValueError('Unknown presentation schema')
    if data.get('status') not in {'running', 'validated'}:
        raise ValueError('Unknown presentation status')
    if data.get('coverage', {}).get('questions') != 469 or data['coverage'].get('cells') != 19435:
        raise ValueError('Require the frozen full four-bank cohort')
    ids = [m['id'] for m in data['methods']]
    if len(ids) != len(set(ids)) or set(ids) != set(MENU):
        raise ValueError('Only the ten declared target-only references and methods are eligible')
    for method in data['methods']:
        if method['parent_id'] != MENU[method['id']][1]:
            raise ValueError('Actual parent changed')
        for family, metric in method.get('metrics', {}).items():
            if family not in TASKS:
                raise ValueError('Foreign task')
            value = metric['value']
            if value is not None and (not math.isfinite(value) or not 0 <= value <= 1):
                raise ValueError('Invalid native rate')
            if metric.get('numerator') is None or metric.get('denominator') is None:
                raise ValueError('Native counts must accompany every rate')
            den, num = metric['denominator'], metric['numerator']
            if den < 0 or num < 0 or num > den:
                raise ValueError('Invalid counts')
            if value is not None and (den == 0 or abs(value - num / den) > 1e-9):
                raise ValueError('Native rate/count inconsistency')
            ci = metric.get('ci95')
            if ci is not None and (len(ci) != 2 or not 0 <= ci[0] <= ci[1] <= 1):
                raise ValueError('Invalid rate interval')
        for reference, rows in method.get('comparisons', {}).items():
            if reference not in ids:
                raise ValueError('Ineligible comparison reference')
            for family, comparison in rows.items():
                if family not in TASKS or not math.isfinite(comparison['delta']):
                    raise ValueError('Invalid paired comparison')
                for field in ('ci95', 'simultaneous_ci95'):
                    ci = comparison.get(field)
                    if ci is not None and (len(ci) != 2 or not all(math.isfinite(v) for v in ci) or ci[0] > ci[1]):
                        raise ValueError('Invalid paired interval')
        for example in method.get('examples', []):
            if example.get('family') not in TASKS or example.get('reference_id') not in ids:
                raise ValueError('Foreign example task/reference')
            if (not all(example.get(k) for k in ('cell_id', 'kind', 'finding', 'selection_policy', 'endpoint_evidence'))
                    or not all(isinstance(example.get(k), str) for k in ('before', 'after'))):
                raise ValueError('Examples need exact text, selection policy and endpoint evidence')
    if data['status'] == 'validated':
        if not data.get('source_hashes') or data.get('root_review', {}).get('status') != 'root_reviewed':
            raise ValueError('Validated results require exact source hashes and root review')
        if any(set(m.get('metrics', {})) != set(TASKS) for m in data['methods']):
            raise ValueError('Validated mode requires all ten methods on all four tasks')
    elif any(m.get('metrics') or m.get('comparisons') or m.get('examples') for m in data['methods']) or data.get('findings'):
        raise ValueError('Pending mode cannot display unreviewed evidence or result claims')
    return data


def native_payload(analysis_path, inventory_path, review_path):
    analysis = json.loads(analysis_path.read_bytes())
    inventory = json.loads(inventory_path.read_bytes())
    review = json.loads(review_path.read_bytes())
    if analysis['status'] != 'complete_exploratory':
        raise ValueError('Final presentation requires complete exploratory analysis')
    if (review.get('status') != 'root_reviewed' or review.get('analysis_sha256') != digest(analysis_path)
            or review.get('inventory_sha256') != digest(inventory_path)
            or review.get('source_sha256') != analysis['source_sha256']):
        raise ValueError('Root review must bind the exact analysis, inventory and sources')
    for path, expected in analysis['source_sha256'].items():
        if digest(path) != expected:
            raise ValueError('Analysis source changed: ' + path)
    declared = {r['condition_id'] for r in inventory['conditions']}
    new_ids = set(list(MENU)[6:])
    if declared != new_ids:
        raise ValueError('Inventory must declare exactly the four new eligible methods')
    for condition in inventory['conditions']:
        if condition['actual_parent'] != MENU[condition['condition_id']][1]:
            raise ValueError('Inventory and presentation disagree about the component comparator')
    data = pending()
    data.update(status='validated', coverage=analysis['cohort'],
                source_hashes={'analysis': digest(analysis_path), 'inventory': digest(inventory_path),
                               'review': digest(review_path), **analysis['source_sha256']},
                root_review={'status': 'root_reviewed', 'sha256': digest(review_path)},
                title=review.get('title', 'Inspect gains and regressions across four tasks'),
                findings=review.get('findings', []), resources=review.get('resources', {}))
    methods = {m['id']: m for m in data['methods']}
    for family in TASKS:
        for condition in MENU:
            metric = deepcopy(analysis['headline']['conditions'][family][condition])
            metric['unit'] = 'readouts' if family == 'hallucination' else 'questions'
            methods[condition]['metrics'][family] = metric
    comparisons = analysis['headline']['comparisons'] + analysis.get('supplementary_pointwise_comparisons', [])
    for row in comparisons:
        if row['condition'] not in MENU or row['reference'] not in MENU:
            continue
        target = methods[row['condition']]['comparisons'].setdefault(row['reference'], {})
        # A declared-family interval takes precedence over any supplementary copy.
        if row['family'] in target and target[row['family']].get('simultaneous_ci95'):
            continue
        target[row['family']] = {'delta': row['delta'], 'ci95': row.get('ci95_delta'),
                                'simultaneous_ci95': row.get('simultaneous_ci95_delta'),
                                'warnings': list(dict.fromkeys([*row.get('warnings', []), *([row['warning']] if row.get('warning') else [])]))}
    for condition, method in methods.items():
        method['examples'] = review.get('examples', {}).get(condition, [])
        method['finding'] = review.get('method_findings', {}).get(condition)
        method['lengths'] = analysis.get('lengths', {}).get(condition, {})
        method['secondary'] = analysis.get('secondary', {}).get(condition, {})
    data['resources'].update(lengths=analysis.get('lengths', {}), secondary=analysis.get('secondary', {}), search_diagnostics=analysis.get('search_diagnostics', {}), baseline_reconstruction=analysis.get('baseline_reconstruction', []), paired_lengths=analysis.get('paired_lengths', []))
    return validate(data)


def wrapped(value, width=41):
    return '\n'.join(textwrap.fill(p, width=width) if p else '' for p in str(value).split('\n'))


def percent(value):
    return 'Pending' if value is None else f'{100*value:.2f}%'


def panels(data, chosen):
    by_id = {m['id']: m for m in data['methods']}
    ids = list(dict.fromkeys([RAW, CAP, *chosen]))
    items = []
    for i, (family, (name, endpoint)) in enumerate(TASKS.items()):
        x, y = 550+(i % 2)*505, 215+(i // 2)*292
        items += [rect(x, y, 485, 274, 'F4F8FB'), text(x+15, y+12, 460, 32, name, 23, INK, True),
                  text(x+15, y+48, 460, 25, endpoint, 15, MUTED)]
        for j, condition in enumerate(ids):
            method = by_id[condition]
            yy = y+88+j*32
            metric = method.get('metrics', {}).get(family, {})
            value = metric.get('value')
            color = TEAL if condition == RAW else MUTED if condition == CAP else BLUE
            label = method['label'].replace('Original released Oracle Lens', 'Original released lens')
            items += [text(x+15, yy-13, 240, 37, wrapped(label, 30), 16, color, condition == RAW),
                      line(x+250, yy, x+365, yy, LINE),
                      text(x+378, yy-13, 100, 30, percent(value), 15, color, True)]
            if value is not None:
                ci = metric.get('ci95')
                if ci:
                    items.append(line(x+250+115*ci[0], yy, x+250+115*ci[1], yy, color, 3))
                items.append({'kind': 'ellipse', 'x': x+246+115*value, 'y': yy-4, 'w': 8, 'h': 8, 'color': color})
        for z in (0, .5, 1):
            items.append(text(x+236+115*z, y+248, 45, 22, f'{100*z:g}%', 13, MUTED))
    return items


def pages(data):
    output = []
    def add(title, prose, right, notes):
        number = len(output)+1
        state = 'Reviewed exploratory results' if data['status'] == 'validated' else 'Running; outcomes await review'
        items = [rect(0, 0, 1600, 900, 'FFFFFF'), text(65, 30, 1450, 32, 'Oracle Lens / same-state search follow-up', 20, MUTED),
                 text(65, 84, 1460, 110, title, 45, INK, True), line(65, 848, 1535, 848, LINE),
                 text(65, 865, 1420, 26, state+' | Same 469 questions / 19,435 sites / N=32 | '+str(number), 17, MUTED),
                 text(65, 225, 425, 595, wrapped(prose, 34), 27, INK)] + right
        output.append({'title': title, 'items': items,
                       'notes': notes+'\nStatus: '+state+'\nExact source hashes: '+json.dumps(data['source_hashes'], sort_keys=True)})
    findings = '\n\n'.join(data.get('findings', [])) or 'Results are running.\n\nRead each task separately.\n\nA better reconstruction fit is not established factual improvement.'
    add(data.get('title') or 'Wait for task evidence before choosing a method', findings,
        panels(data, [REPEAT, 'bounded_prune_refill_005-n32']),
        'No invented result values. Only complete native metrics approved against exact source hashes enter this deck. These banks have already been inspected, so the new comparisons are exploratory.')
    add('Test better search using only the current activation',
        'Can we combine the same source bullets more effectively?\n\nEvery valid method sees one activation and its own 32 samples.\n\nThe original released lens remains the reference.',
        panels(data, [POOL]),
        'All model weights, whitening, source samples, reading sites and task endpoints are frozen. Historical control-activation methods are ineligible for this follow-up. The raw original is cap-exempt; capped and new outputs use at most four intact bullets and 256 Qwen tokens.')
    add('Keep the original lens separate from its capped reference',
        'Original: one released raw sample.\n\nFour-bullet original: the same sample, shortened deterministically.\n\nPlain pool: combines bullets from the shared 32 samples.',
        panels(data, ['best_n_exact-n32', POOL]),
        'Counts and grouped rate intervals are copied directly from the native analysis. Hallucination has readout denominators; recovery has question denominators. Never substitute capped reconstruction for unavailable raw reconstruction.')
    steps = [('Start with plain pooled-32', 'Reuse the saved parent, including its complete-response fallback.'),
             ('Try one-bullet replacements', 'Fit the full proposed set jointly against this activation.'),
             ('Repeat within the frozen budget', 'Keep accepted improvements; record fits, cache hits and stop reasons.')]
    diagram = []
    for i, (heading, body) in enumerate(steps):
        yy = 235+i*185
        diagram += [rect(550, yy, 960, 155, 'F4F8FB'), text(575, yy+15, 900, 42, heading, 29, TEAL, True),
                    text(575, yy+68, 890, 65, wrapped(body, 67), 24, INK)]
    add('Repeat local swaps to improve the combined description',
        'Replace one bullet at a time.\n\nReuse intact source text.\n\nMeasure the added benefit against the plain pooled parent.', diagram,
        'Repeated swaps use only the current activation, original source pool and frozen matched reconstructor. Exact search tolerance and unique-subset budgets come from the sealed configuration, not these explanatory diagrams.')
    add('Judge repeated swaps against the plain pooled parent',
        next((m.get('finding') for m in data['methods'] if m['id'] == REPEAT), None) or
        'Task outcomes await review.\n\nThe parent is plain pooled-32.\n\nAlso compare with the original released lens.',
        panels(data, [POOL, REPEAT]),
        'Rate bars are grouped pointwise intervals, not intervals for paired differences. Paired original and parent comparisons, including simultaneous intervals where declared, are provided in the dashboard and source payload.')
    prune = [rect(550, 225, 960, 245, 'F4F8FB'), text(575, 245, 900, 45, 'Guided deletion', 32, TEAL, True),
             text(575, 315, 900, 120, wrapped('Remove a bullet when its refitted contribution is at most 0.005. Refit after every deletion.', 60), 28),
             rect(550, 505, 960, 245, 'F4F8FB'), text(575, 525, 900, 45, 'Matched random deletion', 32, BLUE, True),
             text(575, 595, 900, 120, wrapped('Remove exactly as many bullets from the same repeated-swaps parent, using frozen random seeds.', 60), 28)]
    add('Separate guided pruning from simply making output shorter',
        'Start from the repeated-swaps result.\n\nBoth deletion methods shorten by the same bullet count on each activation.\n\nCheck lost recovery as well as fewer contradictions.', prune,
        'The matched random deletion baseline controls output shortening at the bullet-count level; exact token lengths can still differ. A low reconstruction contribution is not a falsehood label. Hallucination assertion share and empty outputs are required diagnostics.')
    add('Check whether pruning removes errors and useful facts together',
        next((m.get('finding') for m in data['methods'] if m['id'] == 'repeat_swap_then_prune_005-n32'), None) or
        'Task outcomes await review.\n\nCompare guided and matched random deletion.\n\nKeep the repeated-swaps parent visible.',
        panels(data, [REPEAT, 'repeat_swap_then_prune_005-n32', 'repeated_swaps_random_delete_match_005-n32']),
        'The declared paired comparison family is frozen before new outcomes. Native paired deltas retain the endpoint direction: negative is better for contradiction rate; positive is better for recovery. Inspect simultaneous uncertainty as well as individual intervals.')
    refill = []
    for i, (heading, body) in enumerate([('Prune weak bullets', 'Begin from plain pooled-32, with the same 0.005 contribution threshold.'),
                                       ('Explore bounded refills', 'Try existing source bullets as additions or replacements; fit each set again.'),
                                       ('Keep a validated constrained set', 'Every retained bullet must contribute more than 0.005. Fewer than four bullets are allowed.')]):
        yy = 225+i*185
        refill += [rect(550, yy, 960, 160, 'F4F8FB'), text(575, yy+15, 900, 42, heading, 29, TEAL, True),
                   text(575, yy+68, 900, 75, wrapped(body, 64), 25)]
    add('Prune and refill while keeping every bullet above the threshold',
        'A constrained search can reject a higher-scoring weak superset.\n\nDo not force four bullets.\n\nCompare with plain pooling and plain pooling plus pruning.', refill,
        'Prune/refill changes the constrained objective and search scaffold. Its comparison does not isolate optimization efficiency alone. The best retained feasible set is checked explicitly; do not restore a weak superset solely for reconstruction score.')
    add('Compare refill with both of its plain-pooling references',
        next((m.get('finding') for m in data['methods'] if m['id'] == 'bounded_prune_refill_005-n32'), None) or
        'Task outcomes await review.\n\nPlain pooling shows the full added scaffold.\n\nPlain pooling plus pruning tests what bounded refill adds.',
        panels(data, [POOL, 'pooled_greedy_swap_then_prune_0.005-n32', 'bounded_prune_refill_005-n32']),
        'The original released lens is shown on every result panel. Parent references are eligible target-only methods, not the historical specificity-based combine-and-prune method. Reconstruction alone is secondary evidence.')
    examples = [(m, e) for m in data['methods'] for e in m.get('examples', [])]
    right = []
    if examples:
        m, e = examples[0]
        right += [text(550, 220, 960, 45, m['label']+': '+e['kind'], 28, TEAL, True),
                  text(550, 280, 960, 75, wrapped(e['finding'], 76), 22),
                  text(550, 385, 460, 45, 'Before / '+MENU[e['reference_id']][0], 22, MUTED, True),
                  text(1040, 385, 475, 45, 'After', 22, BLUE, True),
                  text(550, 440, 460, 300, wrapped(textwrap.shorten(e['before'], width=420, placeholder=' [...]'), 39), 20),
                  text(1040, 440, 475, 300, wrapped(textwrap.shorten(e['after'], width=420, placeholder=' [...]'), 39), 20),
                  text(550, 785, 960, 32, 'Source excerpts; full readouts, cell ID and endpoint evidence are in the notes and dashboard.', 17, MUTED)]
    else:
        right += [text(565, 250, 915, 400, wrapped('Exact before/after examples await qualitative review.\n\nInspect recovered facts, contradictions, relation reversals and lost details.\n\nExamples will be labeled as gains, regressions or randomly sampled unchanged cases.', 60), 30, MUTED)]
    add('Inspect the exact text behind a gain or regression',
        'A required name can be recovered inside incorrect prose.\n\nA weak bullet can carry a useful fact.\n\nExamples explain possible failure mechanisms; they do not prove causality.', right,
        'Selected qualitative cases must preserve source cell IDs, exact before/after text, selection policy and endpoint evidence. Outcome-selected cases are not representative prevalence estimates. All reviewed examples remain expandable in the dashboard.'+
        ('\nDisplayed case (slide contains explicitly labeled excerpts): '+json.dumps(examples[0][1], ensure_ascii=False) if examples else ''))
    effort_summary = data.get('resources', {}).get('slide_summary') or 'Reuse frozen generation and phrase encodings. Report numerical fits, search stops, CPU effort, judged changes and usage estimates.'
    right = [rect(550, 225, 960, 250, 'F4F8FB'), text(575, 245, 900, 45, 'Compare the same grouped questions', 32, TEAL, True),
             text(575, 315, 900, 130, wrapped('Paired intervals ask about the difference. Simultaneous intervals account for the declared comparison menu. Missing intervals remain unavailable.', 62), 27),
             rect(550, 510, 960, 240, 'F4F8FB'), text(575, 530, 900, 45, 'Account for the computation', 32, BLUE, True),
             text(575, 600, 900, 130, wrapped(effort_summary, 62), 27)]
    add('Keep uncertainty, output coverage and effort visible',
        'Four task endpoints, no pooled quality average.\n\nReport lengths, silence and claim coverage.\n\nThese previously inspected banks give exploratory evidence.', right,
        'No new Oracle Lens sampling, GPU inference or model training is part of these upgrades. Search budgets and API costs come from measured accounting, not inferred totals. The historical study remains archived, including out-of-scope control-activation methods. PDF is an HTML geometry mirror, not a native PowerPoint rendering-parity claim.')
    return output


def build(data, output, chrome=None, node='node'):
    validate(data)
    if output.exists():
        raise ValueError('Use a new output directory; historical artifacts are immutable')
    output.mkdir(parents=True)
    downloads = output/'downloads'
    downloads.mkdir()
    serialized = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    (output/'target-only-data.json').write_text(serialized+'\n')
    template = (ROOT/'dashboard/target-only.html').read_text()
    (output/'index.html').write_text(template.replace('__TARGET_ONLY_DATA__', serialized.replace('<', '\\u003c')))
    for filename in ('target-only.css', 'target-only.js'):
        shutil.copyfile(ROOT/'dashboard'/filename, output/filename)
    slides = pages(data)
    write_html(slides, downloads/'target-only-slides.html')
    slidehtml = downloads/'target-only-slides.html'
    slidehtml.write_text(slidehtml.read_text().replace('DRAFT validation style proof', 'Oracle Lens same-state search supplement'))
    write_pptx(slides, downloads/'target-only-slides.pptx')
    from pptx import Presentation
    ppt = Presentation(downloads/'target-only-slides.pptx')
    ppt.core_properties.title = 'Oracle Lens: same-state bullet search'
    ppt.core_properties.subject = 'Exploratory follow-up / '+data['status']
    ppt.save(downloads/'target-only-slides.pptx')
    (downloads/'target-only-speaker-notes.md').write_text('\n\n'.join(f"## {i+1}. {p['title']}\n\n{p['notes']}" for i, p in enumerate(slides))+'\n')
    (output/'geometry.json').write_text(json.dumps(slides, indent=2)+'\n')
    if chrome:
        subprocess.run([node, str(ROOT/'scripts/render_slides.mjs'), str(chrome), str(slidehtml.resolve()),
                        str((downloads/'target-only-slides.pdf').resolve())], check=True)
    receipt = {'status': data['status'], 'slides': len(slides), 'methods': len(data['methods']),
               'source_hashes': data['source_hashes'], 'builder_sha256': digest(__file__),
               'frontend_sha256': {name: digest(ROOT/'dashboard'/name) for name in ('target-only.html', 'target-only.css', 'target-only.js')},
               'inference_calls': 0, 'native_pptx_rendering_validated': False,
               'pdf_route': 'Same-geometry HTML mirror; not a native PPTX conversion',
               'archive_action_required': 'Assembly owner must preserve and clearly banner historical-expanded-study.html before publication',
               'outputs': {str(p.relative_to(output)): digest(p) for p in output.rglob('*') if p.is_file()}}
    (output/'build.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pending', action='store_true')
    parser.add_argument('--analysis', type=Path)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--chrome', type=Path)
    parser.add_argument('--node', default='node')
    args = parser.parse_args()
    if args.pending:
        if any((args.analysis, args.inventory, args.review)):
            parser.error('Pending mode cannot consume result sources')
        data = pending()
    else:
        if not all((args.analysis, args.inventory, args.review)):
            parser.error('Provide analysis, inventory and exact root review, or --pending')
        data = native_payload(args.analysis, args.inventory, args.review)
    receipt = build(data, args.output, args.chrome, args.node)
    print(json.dumps({k: receipt[k] for k in ('status', 'slides', 'methods', 'inference_calls')}))


if __name__ == '__main__':
    main()
