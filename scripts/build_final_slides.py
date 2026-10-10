"""Editable DEV/VAL draft or explicitly reviewed held-out result deck.

No inference or judging. The source JSON is editable; changing a measured row
requires a new reviewed report. Existing four-slide style proofs are preserved.
"""
import argparse
from copy import deepcopy
from datetime import datetime
import json
import math
from pathlib import Path
import subprocess

from build_slides import (BLUE, H, INK, LINE, MUTED, PAPER, TEAL, W, digest,
                         line, rect, text, write_html, write_pptx)
from build_public_dashboard import public_data
from dashboard_method_sections import headline, label, normalized_signed
from dashboard_qualitative import validated

FAMILIES = {'hallucination': 'Transcript contradictions', 'multihop_mt': 'Multi-hop facts',
            'chain_intermediates': 'Arithmetic steps', 'role_bound_association': 'Who did what'}
METHODS = {'sample_selection': 'Choose a complete sample', 'consensus': 'Count agreement',
           'pruning': 'Remove bullets', 'pooling': 'Combine bullets',
           'contrastive_checks': 'Compare other activations', 'editing': 'Edit a readout',
           'independent_checks': 'Check with another reader', 'combinations': 'Combine approaches'}
DEFAULTS = {'sample_selection': 'best_n_exact-n32', 'consensus': 'consensus_exact_support0.125-n16',
            'pruning': 'prune_loo_a32_0.005-n32', 'pooling': 'pooled_greedy_swap-n32',
            'contrastive_checks': 'best_n_specificity_mean-n32', 'editing': 'editing_round2-n32',
            'combinations': 'best_n_specificity_mean_then_prune_0.005-n32'}
KEY = ['raw_n1-n1', 'best_n_exact-n16', 'best_n_exact-n32', 'best_n_specificity_mean-n32']


def prepared(report_path, final=False):
    if final:
        return prepared_final(report_path)
    report = json.loads(Path(report_path).read_bytes())
    val = report['signed_comparisons']['validation']
    dev = report['development_scaling']
    if val['review']['status'] != 'root_reviewed' or val['stage'] != 'validation' or dev['reviewed_by'] != 'root':
        raise ValueError('Slides require reviewed DEV/VAL evidence')
    qualitative = validated(report['qualitative_reviews'])
    if public_data(qualitative) != qualitative:
        raise ValueError('Slide examples must not be silently redacted')
    safe = public_data(report)
    val = safe['signed_comparisons']['validation']; dev = safe['development_scaling']
    metrics = normalized_signed(val, set(val['condition_ids']))
    expected={(f,c) for f in FAMILIES for c in val['condition_ids']}
    observed=[(r['family'],r['condition']) for r in metrics]
    if len(observed)!=len(set(observed)) or set(observed)!=expected:
        raise ValueError('Complete four-family reviewed menu is required')
    prefixes=['raw_n1-n1','capped_n1-n1']+[f'best_n_exact-n{n}' for n in [1,2,4,8,16,32]]
    if [c['condition'] for c in dev['measurement']['conditions']]!=prefixes:
        raise ValueError('Keep the complete frozen development sampling prefixes')
    for row in metrics:
        v=row['value'];ci=row.get('ci')
        if v is not None and (not math.isfinite(v) or not 0<=v<=1):raise ValueError('Invalid rate')
        if ci is not None and not (len(ci)==2 and all(math.isfinite(x) for x in ci) and 0<=ci[0]<=ci[1]<=1):raise ValueError('Invalid interval')
    slides = []
    def add(kind, title, **kwargs):
        slides.append({'kind': kind, 'title': title, **kwargs})
    add('message', 'No overall winner is established',
        bullets=['Validation supports two experimental choices: Best of 16 and comparison against other activations.',
                 'Recovering a name or number can still leave the explanation wrong.',
                 'Final held-out quality remains pending; these are development and validation findings.'])
    add('pending', 'The final comparison is fixed; results are pending',
        bullets=['268 held-out items; 10,714 preselected readout sites.',
                 'Six primary choices plus six secondary comparisons were fixed before judging.',
                 'No held-out numbers, verdicts or examples enter this draft.'])
    add('diagram', 'One internal snapshot can yield several descriptions',
        steps=['Frozen model', 'One vector at one layer and position', 'Up to 32 descriptions', 'Chosen readout'],
        note='Each cell is read independently. Batching is a speed optimization, not a joint input.')
    add('options', 'Choosing, combining and deleting are different steps',
        steps=['Choose a complete sample', 'Pool source bullets', 'Remove low-impact bullets', 'Compare matched controls'],
        note='Options and components, not a required sequence. Each cell is read independently; methods reuse its pool. Final outputs have at most four intact bullets and 256 tokens.')
    add('message', 'Settings were chosen before final quality was visible',
        bullets=['Development: 121 items, 5,236 sites; all six sampling prefixes measured.',
                 'Validation: 80 items, 3,485 sites; 12 frozen comparisons.',
                 'Held-out generation was blind; final analysis requires a separate frozen menu and gate.'])
    for family, name in FAMILIES.items():
        add('rates', name + ': reviewed validation', rows=[r for r in metrics if r['family'] == family and r['condition'] in KEY],
            cohort='Validation, complete original grids',
            note='Lower is better.' if family == 'hallucination' else 'Higher is better. Mention or binding recovery is not complete explanation accuracy.')
    add('curves', 'More samples do not give a steady quality gain', measurement=dev['measurement'],
        note='Development only: 121 items, 5,236 sites. Nested saved prefixes; no scaling law. Best of 1 has distinct eligibility checks.')
    add('message', 'Agreement and editing have specific limits',
        bullets=['Whole-bullet consensus was tested; sampled helper audits found false merges.',
                 'Claim extraction failed its eight-cell self-containedness audit; quality expansion was not completed.',
                 'Two editing rounds showed no aggregate recovery gain in the small pilot. Larger editing remains unmeasured.',
                 'Another reader was diagnostic only; token presence does not verify a relation.'])
    pair_menu=[('best_n_exact-n32','prune_loo_a32_0.005-n32'),
               ('best_n_specificity_mean-n32','best_n_specificity_mean_then_prune_0.005-n32'),
               ('prune_loo_a32_0.005-n32','best_n_specificity_mean_then_prune_0.005-n32'),
               ('random_delete_matched_a32_0.005-n32','prune_loo_a32_0.005-n32'),
               ('best_n_specificity_mean_random_delete_matched_0.005-n32','best_n_specificity_mean_then_prune_0.005-n32')]
    pairs = [r for family in FAMILIES for a,b in pair_menu for r in val['paired_rows']
             if r['family']==family and r['scope']=='cell' and r['endpoint'] in ('contradiction_rate','cell_recovery')
             and r['baseline_condition']==a and r['condition']==b]
    add('paired', 'Extra steps must earn their place', rows=pairs,
        note='Validation paired changes. Matched random shortening is a control; absolute error-bar overlap does not establish a paired difference.')
    add('message', 'Activation fit is not factual verification',
        bullets=['Controlled numbers, entities and direction swaps exposed score limitations.',
                 'The reconstruction reader sees only the first 32 cleaned tokens of each bullet.',
                 'Batch-size sensitivity is recorded. Small pruning thresholds are numerically delicate.'])
    add('cost', 'New inputs and cached replay are different workloads', costs=safe['measured_cost_components'],
        engineering=dev['engineering_reference'],
        note='One off-benchmark timing fixture, not a latency distribution. Cold means process initialization; filesystem caches were not flushed.')
    add('diagram', 'Save the work so another comparison can replay it',
        steps=['Explicit input vector', 'Persisted sample pool', 'Saved raw-vector cache', 'Selection replay'],
        note='The portable tool is vector-first. Missing matched controls make specificity unavailable. No runtime benchmark judge is required.')
    add('message', 'Final recommendations await held-out results',
        bullets=['Best of 16 and comparison against other activations are experimental choices, not universal faithfulness guarantees.',
                 'Keep task outcomes, useful-content coverage and costs separate.',
                 'The appendix records every available variant and its limits; omitted variants are not automatically ruled out.'])
    assert len(slides) == 16
    # Keep the entire reviewed menu, rather than only the four display choices.
    for family, name in FAMILIES.items():
        add('rates', name + ': all 12 validation comparisons', rows=[r for r in metrics if r['family'] == family],
            cohort='Validation, complete original grids', note='All preselected conditions; original six primary choices and six secondary comparisons remain identifiable in notes.')
    for method, name in METHODS.items():
        rows = safe['methods'][method]['metrics']
        for family in FAMILIES:
            quality = [r for r in rows if r.get('family') == family and headline(r)]
            for start in range(0, len(quality), 9):
                add('rates', name + ' / ' + FAMILIES[family], rows=quality[start:start+9],
                    cohort=quality[start]['cohort'], note='Development pilot. Partial read grids are descriptive site measurements, not full-grid item accuracy.')
        diagnostics = [r for r in rows if not headline(r)]
        for start in range(0, len(diagnostics), 10):
            add('table', name + ': other measured endpoints', rows=diagnostics[start:start+10],
                note='Exact source units retained. Span and claim tallies have different segmentation; unverifiable is not false.')
        paired=[r for r in safe['methods'][method].get('paired_metrics',[]) if
                headline(dict(r,endpoint=r['endpoint'].removeprefix('Paired delta: '))) and
                r['condition'].split(' vs ')[-1] in ('best_n_exact-n8','best_n_exact-n16','best_n_exact-n32')]
        for family in FAMILIES:
            subset=[r for r in paired if r['family']==family]
            for start in range(0,len(subset),8):
                add('differences',name+': paired '+FAMILIES[family],rows=subset[start:start+8],
                    note='Development pilot, same-pool comparison. Paired grouped intervals copied exactly; zero means unchanged.')
        costs=safe['methods'][method].get('cost_components',[])
        for start in range(0,len(costs),8):
            add('cost_table',name+': known work components',rows=costs[start:start+8],
                note='Component work, initialization and cache replay are different scopes; these rows are not an end-to-end latency sum.')
        add('status', name + ': coverage and limits', method=safe['methods'][method],
            note='Measured variants are not an exhaustive set of combinations. Numerical exports without judgments remain unjudged.')
        q = qualitative['methods'][method]
        if method=='independent_checks':
            add('diagnostic_coverage',name+': diagnostic availability',cases=q['variants'][0]['cases'],
                note='Fixed shared examples only. Available token ranks are not judged prose quality; missing is not failure.')
        v = next((v for v in q['variants'] if v['id'] == DEFAULTS.get(method)), q['variants'][0])
        add('example', name + ': one fixed shared example', case=v['cases'][0], takeaway=q['takeaway'],
            context=qualitative.get('contexts',{}).get(v['cases'][0].get('context_ref')),
            note='First fixed metadata-only shared example, not chosen for its verdict. Illustrative, not an estimated rate. Complete exact text/evidence is in notes.')
    add('message','All 469 items: same-menu summary pending',
        bullets=['The requested target is the same 12 comparisons across all original items.',
                 'Additional development judgments must finish before this slot is filled.',
                 'A combined-cohort summary is descriptive; it does not replace the held-out result.'])
    entries=[{'name':'All 12 validation comparisons','page':18}]
    for name in METHODS.values():
        entries.append({'name':name,'page':next(i+2 for i,s in enumerate(slides) if s['title'].startswith((name+' / ',name+':')))})
    entries.append({'name':'All 469 items, pending','page':len(slides)+1})
    slides.insert(16,{'kind':'contents','title':'Appendix: find the complete evidence','entries':entries,
                     'note':'Every measured row is retained once per source cohort; complete source values and units are in the notes.'})
    return {'schema_version': 2, 'status': 'DRAFT - DEVELOPMENT / VALIDATION ONLY',
            'test_quality_access': False, 'core_slides': 16, 'report_sha256': digest(report_path),
            'source_updated_utc': report['updated_utc'], 'validation_artifact_sha256': val['source_sha256'],
            'development_artifact_sha256': dev['source_sha256'], 'slides': slides}


def checked_hash(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('A complete source SHA-256 is required')
    return value


def checked_metric(metric, counts, item_endpoint=False, family=None):
    """Copy source rates and uncertainty; never derive or fit an interval."""
    value, interval = metric['value'], metric['ci95']
    numerator, denominator = metric['numerator'], metric['denominator']
    if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in (numerator, denominator)) or numerator > denominator:
        raise ValueError('Invalid retained rate counts')
    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                              or not math.isfinite(value) or not 0 <= value <= 1):
        raise ValueError('Invalid retained rate')
    if (value is None) != (denominator == 0) or (denominator and value != numerator / denominator):
        raise ValueError('Retained rate differs from its counts')
    if interval is not None and (len(interval) != 2 or not all(math.isfinite(x) for x in interval)
                                 or not 0 <= interval[0] <= interval[1] <= 1):
        raise ValueError('Invalid retained grouped interval')
    if metric['items'] != counts['items'] or metric['independent_groups'] != counts['groups']:
        raise ValueError('Metric cohort differs from the reviewed item/group counts')
    if item_endpoint and family != 'hallucination' and denominator != counts['items']:
        raise ValueError('Question metric must use the original item denominator')
    if not item_endpoint and family != 'hallucination' and denominator != counts['cells']:
        raise ValueError('Per-activation metric must use all intended cell denominators')
    return deepcopy(metric)


def rate_row(condition, family, endpoint, metric, stage):
    return {'condition': condition, 'family': family, 'endpoint': endpoint, 'value': metric['value'],
            'numerator': metric['numerator'], 'denominator': metric['denominator'], 'ci': metric['ci95'],
            'cohort': stage, 'uncertainty': f"{metric['items']} items / {metric['independent_groups']} related groups; grouped 95% intervals" +
                (' | ' + metric['warning'] if metric.get('warning') else ''), 'source_metric': deepcopy(metric)}


def checked_pairs(rows, metrics, counts, scope):
    seen, result = set(), []
    for row in rows:
        allowed_scopes = ('cell', 'original_grid') if scope == 'original_grid' else ('cell', 'original_item')
        if row.get('scope') not in allowed_scopes:
            raise ValueError('Unknown supplied paired contrast scope')
        if row['scope'] != scope:
            continue
        b, p, f, endpoint = (row[k] for k in ('baseline_condition', 'condition', 'family', 'endpoint'))
        identity = (b, p, f, endpoint)
        if identity in seen or (b, f, endpoint) not in metrics or (p, f, endpoint) not in metrics:
            raise ValueError('Duplicate or foreign paired contrast')
        seen.add(identity)
        left, right = metrics[b, f, endpoint]['value'], metrics[p, f, endpoint]['value']
        delta = right-left if left is not None and right is not None else None
        if row['baseline'] != left or row['proposed'] != right or row['delta'] != delta:
            raise ValueError('Paired contrast differs from retained endpoint values')
        if row['items'] != counts[f]['items'] or row['independent_groups'] != counts[f]['groups']:
            raise ValueError('Paired contrast cohort differs from reviewed counts')
        interval = row['ci95_delta']
        if interval is not None and (len(interval) != 2 or not all(math.isfinite(x) for x in interval)
                                     or not -1 <= interval[0] <= interval[1] <= 1):
            raise ValueError('Invalid paired grouped interval')
        result.append(deepcopy(row))
    return result


def reviewed_test(section):
    """Authorize before iterating any optional held-out result rows."""
    review = section.get('review', {})
    if (section.get('stage') != 'test' or review.get('stage') != 'test'
            or review.get('status') != 'root_reviewed' or not review.get('reviewed_by')
            or not review.get('reviewed_utc') or review.get('test_reveal_authorized') is not True):
        raise ValueError('Final slides require explicit reviewed TEST reveal authority')
    datetime.fromisoformat(review['reviewed_utc'].replace('Z', '+00:00'))
    if checked_hash(section.get('source_sha256')) != review.get('artifact_sha256'):
        raise ValueError('TEST review differs from its source artifact')
    for key in ('manifest_sha256', 'conditions_sha256', 'selection_sha256', 'gate_sha256', 'freeze_sha256'):
        if checked_hash(section.get('identities', {}).get(key)) != review.get(key):
            raise ValueError('TEST review differs from its frozen source identities')
    names, counts = section['condition_ids'], section['family_counts']
    if (len(names) != 12 or len(set(names)) != 12 or names != review.get('condition_ids')
            or not set(KEY) <= set(names) or counts != review.get('expected_family_counts')
            or set(counts) != set(FAMILIES)):
        raise ValueError('Require the exact reviewed twelve-method/four-family TEST menu')
    for count in counts.values():
        if any(isinstance(count[k], bool) or not isinstance(count[k], int) or count[k] < 1
               for k in ('cells', 'items', 'groups')):
            raise ValueError('Invalid reviewed TEST cohort')
    if sum(c['items'] for c in counts.values()) != 268 or sum(c['cells'] for c in counts.values()) != 10714:
        raise ValueError('TEST must retain the frozen 268 items / 10714 sites')
    findings = review.get('findings')
    if not isinstance(findings, list) or not 1 <= len(findings) <= 5 or any(not r.get('claim') or not r.get('evidence') for r in findings):
        raise ValueError('Require root-authored findings and supporting evidence')
    maps, rows = {}, {}
    for scope, field in [('original_item', 'original_item_rows'), ('cell', 'cell_rows')]:
        maps[scope], rows[scope] = {}, []
        for row in section[field]:
            family, name = row['family'], row['condition']
            endpoint = ('original_grid_contradiction_rate' if family == 'hallucination' else 'original_grid_item_pass_rate') if scope == 'original_item' else ('contradiction_rate' if family == 'hallucination' else 'cell_recovery')
            if scope == 'original_item' and row.get('endpoint') != endpoint:
                raise ValueError('Question chart endpoint differs from the official task criterion')
            identity = (name, family, endpoint)
            if family not in counts or name not in names or identity in maps[scope]:
                raise ValueError('Duplicate or foreign TEST metric')
            metric = checked_metric(row['metric'], counts[family], scope == 'original_item', family)
            maps[scope][identity] = metric
            rows[scope].append(rate_row(name, family, endpoint, metric, 'Held-out TEST'))
        if len(maps[scope]) != 12 * 4:
            raise ValueError('Complete four-family TEST menu is required')
    for name in names:
        a, b = maps['cell'][name, 'hallucination', 'contradiction_rate'], maps['original_item'][name, 'hallucination', 'original_grid_contradiction_rate']
        if any(a[k] != b[k] for k in ('value', 'numerator', 'denominator', 'ci95')):
            raise ValueError('Question view must retain native hallucination error counts')
    pairs = {scope: checked_pairs(section.get('paired_rows', []), maps[scope], counts, scope) for scope in maps}
    return rows, pairs


def whole_cohort(section, names):
    """A separate optional reviewed descriptive attachment; no pooled estimation."""
    review = section.get('review', {})
    if (section.get('status') != 'root_reviewed' or section.get('reviewed_by') != 'root'
            or review.get('status') != 'root_reviewed' or review.get('test_reveal_authorized') is not True
            or not review.get('reviewed_utc')):
        raise ValueError('Whole-469 evidence needs a separate reviewed reveal and source binding')
    if checked_hash(section.get('source_sha256')) != review.get('artifact_sha256'):
        raise ValueError('Whole-469 review differs from its artifact')
    counts = review['expected_family_counts']
    if set(counts) != set(FAMILIES) or any(any(isinstance(c[k], bool) or not isinstance(c[k], int) or c[k] < 1
            for k in ('cells', 'items', 'groups')) for c in counts.values()):
        raise ValueError('Invalid reviewed whole-469 cohort')
    if (set(counts) != set(FAMILIES) or sum(c['items'] for c in counts.values()) != 469
            or sum(c['cells'] for c in counts.values()) != 19435):
        raise ValueError('Whole-469 descriptive cohort differs from original grids')
    measurement = section['measurement']
    if (measurement['status'] != 'complete_descriptive_whole_cohort'
            or [c['condition'] for c in measurement['conditions']] != names
            or review.get('condition_ids') != names):
        raise ValueError('Whole-469 must retain the same exact reviewed menu')
    metrics, rows = {}, []
    for arm in measurement['conditions']:
        if not arm.get('measurement_complete') or set(arm['families']) != set(FAMILIES):
            raise ValueError('Whole-469 method coverage is incomplete')
        for f in FAMILIES:
            endpoint = 'original_grid_contradiction_rate' if f == 'hallucination' else 'original_grid_item_pass_rate'
            metric = arm['families'][f][endpoint]
            expected_unit = ('contradictory / specific readouts' if f == 'hallucination' else
                             'items with any passing site / intended items')
            if metric.get('scope') != 'original_grid' or metric.get('unit') != expected_unit:
                raise ValueError('Whole-469 chart must preserve original-grid rate units')
            metric = checked_metric(metric, counts[f], True, f)
            metrics[arm['condition'], f, endpoint] = metric
            rows.append(rate_row(arm['condition'], f, endpoint, metric, 'All 469, descriptive DEV + VAL + TEST'))
    pairs = checked_pairs(measurement.get('paired_comparisons', []), metrics, counts, 'original_grid')
    return rows, pairs


def prepared_final(report_path):
    report = json.loads(Path(report_path).read_bytes())
    test = report.get('signed_comparisons', {}).get('test', {})
    rows, pairs = reviewed_test(test)  # authorize before constructing any result slides
    whole = report.get('descriptive_whole_cohort')
    whole_rows, whole_pairs = whole_cohort(whole, test['condition_ids']) if whole is not None else (None, None)
    source = prepared(report_path)
    if set(test['condition_ids']) != set(report['signed_comparisons']['validation']['condition_ids']):
        raise ValueError('TEST must retain the frozen twelve validation method identities')
    slides = source['slides']
    findings = deepcopy(test['review']['findings'])
    slides[0] = {'kind': 'message', 'title': 'What the held-out comparison establishes',
                 'bullets': [r['claim'] for r in findings[:3]], 'reviewed_findings': findings}
    slides[1] = {'kind': 'message', 'title': '268 held-out questions, with the original task rules',
                 'bullets': ['Twelve preselected comparisons; 10,714 original readout sites. Each question uses its complete frozen read grid.',
                             'Each question uses its original task-specific aggregation rule.',
                             'Transcript contradictions remain errors per specific readout; they are not question accuracy.'],
                 'criteria': {'multihop_mt': 'All required connecting names in the same layer.',
                              'role_bound_association': 'All three checks correct at the same site.',
                              'chain_intermediates': 'Top-named computed value is an intermediate at any layer in the frozen grid.'}}
    for index, family in enumerate(FAMILIES, 5):
        slides[index] = {'kind': 'rates', 'title': FAMILIES[family] + ': held-out TEST',
                         'rows': [r for r in rows['original_item'] if r['family'] == family and r['condition'] in KEY],
                         'cohort': 'Held-out TEST / ' + ('contradictions per specific readout' if family == 'hallucination' else 'questions meeting the complete task criterion'),
                         'note': ('Lower is better. Native readout error rate; not accuracy.' if family == 'hallucination' else
                                  'Higher is better. Each question uses its original task-specific aggregation rule; a pass does not guarantee a completely correct explanation.')}
    chosen_pairs = {('best_n_exact-n16', 'best_n_exact-n32'),
                    ('best_n_exact-n32', 'best_n_specificity_mean-n32'),
                    ('best_n_specificity_mean-n32', 'best_n_specificity_mean_then_prune_0.005-n32'),
                    ('prune_loo_a32_0.005-n32', 'best_n_specificity_mean_then_prune_0.005-n32'),
                    ('best_n_specificity_mean_random_delete_matched_0.005-n32', 'best_n_specificity_mean_then_prune_0.005-n32')}
    slides[11] = {'kind': 'paired', 'title': 'Do extra steps help on held-out questions?',
                  'rows': [r for r in pairs['original_item'] if (r['baseline_condition'], r['condition']) in chosen_pairs],
                  'note': 'Held-out TEST, paired grouped 95% intervals. Recovery uses questions; contradictions retain native readout errors. Matched random deletion is the control.'}
    slides[15] = {'kind': 'message', 'title': 'Use the evidence within its limits',
                  'bullets': [r['claim'] for r in findings[:3]], 'reviewed_findings': findings}
    # Remove only the draft contents and whole-cohort placeholder; retain DEV/VAL evidence.
    slides = [s for s in slides if s['kind'] != 'contents' and s['title'] != 'All 469 items: same-menu summary pending']
    first_test = len(slides) + 2
    for scope, label_text in [('original_item', 'questions / native transcript errors'), ('cell', 'per-activation diagnostics')]:
        for family in FAMILIES:
            family_rows = [r for r in rows[scope] if r['family'] == family]
            for start in range(0, len(family_rows), 6):
                slides.append({'kind': 'rates', 'title': FAMILIES[family] + ': all 12 TEST comparisons',
                    'rows': family_rows[start:start+6], 'cohort': 'Held-out TEST / ' + label_text,
                    'note': 'Exact source counts and grouped 95% intervals. Native transcript error is lower better; recovery is higher better.'})
        pair_names = list(dict.fromkeys((r['baseline_condition'], r['condition']) for r in pairs[scope]))
        for start in range(0, len(pair_names), 5):
            subset = set(pair_names[start:start+5])
            slides.append({'kind': 'paired', 'title': 'Held-out TEST: paired component and budget changes',
                'rows': [r for r in pairs[scope] if (r['baseline_condition'], r['condition']) in subset],
                'note': 'Held-out TEST / ' + label_text + '; only supplied prespecified contrasts, no new estimation.'})
    whole_page = len(slides) + 2
    if whole_rows is None:
        slides.append({'kind': 'message', 'title': 'All 469: descriptive comparison still pending',
            'bullets': ['This is a reviewed TEST preview, not the completed whole-project delivery.',
                        'The separate same-menu DEV + VAL + TEST summary is not yet attached.',
                        'No combined-cohort rates or intervals are inferred from stage averages.']})
    else:
        for family in FAMILIES:
            family_rows = [r for r in whole_rows if r['family'] == family]
            for start in range(0, len(family_rows), 6):
                slides.append({'kind': 'rates', 'title': FAMILIES[family] + ': all 469, descriptive',
                    'rows': family_rows[start:start+6], 'cohort': 'Descriptive DEV + VAL + TEST / original task rules',
                    'note': '469 combined items are not 469 held-out items. Preserve separate TEST results; copied source ratios and grouped intervals.'})
        names = list(dict.fromkeys((r['baseline_condition'], r['condition']) for r in whole_pairs))
        for start in range(0, len(names), 5):
            subset = set(names[start:start+5])
            slides.append({'kind': 'paired', 'title': 'All 469: descriptive paired changes',
                'rows': [r for r in whole_pairs if (r['baseline_condition'], r['condition']) in subset],
                'note': 'Descriptive DEV + VAL + TEST / original task rules; not an independent held-out confirmation.'})
    entries = [{'name': 'All 12 validation comparisons', 'page': 18}]
    for name in METHODS.values():
        entries.append({'name': name, 'page': next(i+2 for i, s in enumerate(slides) if s['title'].startswith((name+' / ', name+':')))})
    entries += [{'name': 'Held-out TEST: complete menu and pairs', 'page': first_test},
                {'name': 'All 469, descriptive' + (' (pending)' if whole_rows is None else ''), 'page': whole_page}]
    slides.insert(16, {'kind': 'contents', 'title': 'Appendix: separate cohorts and complete evidence',
        'entries': entries, 'note': 'DEV, VAL, held-out TEST and the descriptive combined cohort remain separate.'})
    source.update(schema_version=3, mode='reviewed_test', status=('REVIEWED TEST PREVIEW / WHOLE-469 PENDING' if whole is None else 'REVIEWED TEST + DESCRIPTIVE WHOLE-469'),
                  test_quality_access=True, whole_cohort_complete=whole is not None, slides=slides,
                  test_artifact_sha256=test['source_sha256'], test_source_identities=deepcopy(test['identities']),
                  test_review=deepcopy(test['review']), whole_cohort_artifact_sha256=None if whole is None else whole['source_sha256'],
                  whole_cohort_review=None if whole is None else deepcopy(whole['review']),
                  whole_cohort_measurement=None if whole is None else deepcopy(whole['measurement']),
                  implementation_sha256={name: digest(Path(__file__).with_name(name)) for name in
                                          ('build_final_slides.py', 'build_slides.py', 'render_slides.mjs')})
    return source


def base(title, number, count, source):
    if source.get('mode') == 'reviewed_test':
        footer = 'Held-out TEST ' + source['test_artifact_sha256'][:12] + ' | ' + ('All 469: descriptive' if source['whole_cohort_complete'] else 'Whole-469 pending; TEST preview only')
        return [rect(0, 0, W, H, PAPER), text(60, 28, 1480, 35, 'ORACLE LENS / REVIEWED TEST', 20, MUTED),
                text(60, 83, 1480, 103, title, 45, serif=True), line(60, 851, 1540, 851),
                text(60, 865, 1370, 25, footer, 17, MUTED), text(1430, 865, 110, 25, str(number)+' / '+str(count), 18, MUTED)]
    return [rect(0, 0, W, H, PAPER), text(60, 28, 1480, 35, 'ORACLE LENS / DRAFT / DEVELOPMENT + VALIDATION', 20, MUTED),
            text(60, 83, 1480, 103, title, 45, serif=True), line(60, 851, 1540, 851),
            text(60, 865, 1370, 25, 'Reviewed sources: DEV ' + source['development_artifact_sha256'][:12] + ' / VAL ' + source['validation_artifact_sha256'][:12] + ' | TEST quality pending', 17, MUTED),
            text(1430, 865, 110, 25, str(number)+' / '+str(count), 18, MUTED)]


def rate_items(rows, y=250, step=44):
    """Editable points/intervals; exact counts and unknown intervals stay visible."""
    upper=max([.05]+[(r.get('ci') or [r['value']])[-1] for r in rows if r['value'] is not None])
    maximum=min(1, max(.05, math.ceil(upper/.05)*.05))
    at=lambda v: 810+450*v/maximum
    items=[]
    for i,r in enumerate(rows):
        yy=y+i*step; color=TEAL if 'specificity' in r['condition'] else BLUE
        name=label(r['condition']);font=18 if len(name)>70 else 22
        items.append(text(70,yy-17,715,42,name,font,color))
        if r['value'] is None:
            items.append(text(820,yy-17,620,35,'Not measured',22,MUTED)); continue
        items.append(line(810,yy,1260,yy))
        ci=r.get('ci')
        if ci:
            lo,hi=ci;items += [line(at(lo),yy,at(hi),yy,color,3),line(at(lo),yy-6,at(lo),yy+6,color),line(at(hi),yy-6,at(hi),yy+6,color)]
        items += [dict(kind='ellipse',x=at(r['value'])-5,y=yy-5,w=10,h=10,color=color),
                  text(1300,yy-17,220,32,f"{r['value']*100:.2f}%",24,color,True),
                  text(1300,yy+10,220,25,f"{r.get('numerator','?')}/{r.get('denominator','?')}"+(' | CI unavailable' if not ci else ''),15,MUTED)]
    axis=y+len(rows)*step
    for t in [0,.5,1]:items.append(text(at(maximum*t)-40,axis,100,30,f'{maximum*t*100:g}%',20,MUTED))
    return items


def excerpt(value,limit=330):
    if len(value)<=limit:return value
    return value[:limit].rsplit(' ',1)[0]+' ... [complete text in notes]'


def pages(source):
    result=[]
    for i,s in enumerate(source['slides'],1):
        items=base(s['title'],i,len(source['slides']),source); kind=s['kind']
        if kind in ('message','pending'):
            if kind=='pending':items.append(text(70,205,1450,70,'HELD-OUT RESULT SLOTS: NOT YET FILLED',36,TEAL,True))
            for j,b in enumerate(s['bullets']):items += [rect(65,300+j*115,9,70,TEAL),text(100,298+j*115,1400,100,b,32)]
        elif kind=='diagram':
            for j,value in enumerate(s['steps']):
                x=65+j*385;items += [rect(x,285,330,190,'FFFFFF'),text(x+20,325,290,130,value,32,TEAL,True)]
                if j<3:items.append(text(x+335,335,50,70,'→',42,MUTED))
            items.append(text(70,575,1450,140,s['note'],31))
        elif kind=='options':
            items += [rect(70,365,520,210,'FFFFFF'),text(100,402,460,120,'One cell\nOne shared sample pool',36,TEAL,True),
                      line(590,470,710,470,MUTED,3),line(710,260,710,680,MUTED,3)]
            for j,value in enumerate(s['steps']):
                yy=210+j*140
                items += [line(710,yy+50,800,yy+50,MUTED,3),text(790,yy+22,50,50,'→',32,MUTED),
                          rect(850,yy,665,100,'FFFFFF'),text(875,yy+27,610,55,value,31,TEAL,True)]
            items.append(text(70,745,1430,40,'Choose an option; combine components only in an explicitly tested method.',26,MUTED))
        elif kind=='contents':
            for j,row in enumerate(s['entries']):
                x=70+(j%2)*770;yy=235+(j//2)*100
                items += [text(x,yy,600,65,row['name'],29),text(x+610,yy,100,45,str(row['page']),29,TEAL,True)]
        elif kind=='rates':
            items += [text(70,194,1460,50,s['cohort'],25,MUTED)] + rate_items(s['rows'])
            meta=[]
            for r in s['rows']:
                if r.get('uncertainty') and r['uncertainty'] not in meta:meta.append(r['uncertainty'])
            items.append(text(70,765,1470,65,' | '.join(meta[:2]) or 'Item/group counts or intervals are not supplied.',18,MUTED))
        elif kind=='curves':
            for j,family in enumerate(FAMILIES):
                x=70+(j%2)*775;y=205+(j//2)*310;items += [text(x,y-25,700,35,FAMILIES[family],27,INK,True)]
                ms=[]
                for c in s['measurement']['conditions']:
                    f=c['families'][family];m=f['metrics']['contradiction_rate' if family=='hallucination' else 'cell_recovery'];ms.append((c['condition'],m))
                maximum=math.ceil(max(m['ci95'][1] if m['ci95'] else m['value'] for _,m in ms)/.05)*.05
                at=lambda v:y+190-155*v/maximum
                items += [line(x+35,y+190,x+680,y+190)]
                for k,n in enumerate([1,2,4,8,16,32]):items.append(text(x+60+k*118,y+211,75,28,str(n),21,MUTED))
                for t in [0,.5,1]:items.append(text(x-10,at(maximum*t)-12,80,28,f'{maximum*t*100:g}%',18,MUTED))
                for (_,m),color in zip(ms[:2],['8495A7','BF7529']):items.append(line(x+80,at(m['value']),x+670,at(m['value']),color,2))
                previous=None
                for k,(_,m) in enumerate(ms[2:]):
                    xx=x+80+k*118
                    if m['ci95']:items.append(line(xx,at(m['ci95'][0]),xx,at(m['ci95'][1]),TEAL,2))
                    if previous:items.append(line(previous[0],previous[1],xx,at(m['value']),BLUE,2))
                    items.append(dict(kind='ellipse',x=xx-5,y=at(m['value'])-5,w=10,h=10,color=BLUE)); previous=(xx,at(m['value']))
                m=ms[0][1];items.append(text(x+35,y+245,690,30,f"Samples / {m['items']} items / {m['independent_groups']} related groups; 95% intervals",18,MUTED))
        elif kind=='paired':
            # Four panels retain meaningful zero; notes contain every exact pair.
            for j,family in enumerate(FAMILIES):
                x=70+(j%2)*775;y=230+(j//2)*300;rows=[r for r in s['rows'] if r['family']==family][:5]
                items.append(text(x,y-60,700,38,FAMILIES[family],27,INK,True))
                direction='Lower is better: left' if family=='hallucination' else 'Higher is better: right'
                counts='' if not rows else f" / {rows[0]['items']} items, {rows[0]['independent_groups']} related groups"
                items.append(text(x,y-23,720,25,direction+counts,17,MUTED))
                span=max([.01]+[abs(v) for r in rows for v in (r['ci95_delta'] or [r['delta']]) if v is not None]);at=lambda v:x+475+125*v/span
                items.append(line(at(0),y+5,at(0),y+160,MUTED))
                for k,r in enumerate(rows):
                    pair_names={
                        ('best_n_exact-n32','prune_loo_a32_0.005-n32'):'Best 32 → remove bullets',
                        ('best_n_specificity_mean-n32','best_n_specificity_mean_then_prune_0.005-n32'):'Other activations → remove bullets',
                        ('prune_loo_a32_0.005-n32','best_n_specificity_mean_then_prune_0.005-n32'):'Removal → add other-activation check',
                        ('random_delete_matched_a32_0.005-n32','prune_loo_a32_0.005-n32'):'Random deletion → guided deletion',
                        ('best_n_specificity_mean_random_delete_matched_0.005-n32','best_n_specificity_mean_then_prune_0.005-n32'):'Other activations: random → guided removal'}
                    if source.get('mode') == 'reviewed_test':
                        pair_names.update({('best_n_exact-n16','best_n_exact-n32'):'Best of 16 → best of 32',
                                           ('best_n_exact-n32','best_n_specificity_mean-n32'):'Best of 32 → compare activations'})
                    fallback = (label(r['baseline_condition'])+' → '+label(r['condition'])) if source.get('mode') == 'reviewed_test' else label(r['condition'])
                    yy=y+15+k*33;items.append(text(x,yy-14,330,33,pair_names.get((r['baseline_condition'],r['condition']),fallback),15,INK))
                    if r['delta'] is None:
                        items.append(text(x+350,yy-13,380,28,'Unavailable; missing denominator',16,MUTED))
                        continue
                    if r['ci95_delta']:items.append(line(at(r['ci95_delta'][0]),yy,at(r['ci95_delta'][1]),yy,TEAL,2))
                    items += [dict(kind='ellipse',x=at(r['delta'])-4,y=yy-4,w=8,h=8,color=TEAL),text(x+635,yy-13,120,28,f"{r['delta']*100:+.2f} pp",18,TEAL)]
                for t in [-1,0,1]:
                    tick='0 pp' if t==0 else f'{span*t*100:+.2f} pp'
                    items.append(text(at(span*t)-53,y+173,120,27,tick,17,MUTED))
                legend_width = 480 if source.get('mode') == 'reviewed_test' else 490
                items.append(text(x+270,y+210,legend_width,25,'Paired change; lines: grouped 95% intervals',16,MUTED))
        elif kind=='differences':
            rows=s['rows'];span=max([.01]+[abs(v) for r in rows for v in (r.get('ci') or [r['value']])]);at=lambda v:1050+200*v/span
            items.append(line(at(0),210,at(0),670,MUTED))
            for j,r in enumerate(rows):
                yy=240+j*53;name=label(r['condition'].split(' vs ')[0])+' vs '+label(r['condition'].split(' vs ')[-1])
                items.append(text(70,yy-17,730,44,name,17))
                if r.get('ci'):items.append(line(at(r['ci'][0]),yy,at(r['ci'][1]),yy,TEAL,3))
                items += [dict(kind='ellipse',x=at(r['value'])-5,y=yy-5,w=10,h=10,color=TEAL),
                          text(1310,yy-17,220,34,f"{r['value']*100:+.2f} pp",23,TEAL,True)]
            for t in [-1,0,1]:items.append(text(at(span*t)-55,690,150,35,f'{span*t*100:+.1f} pp',20,MUTED))
            items.append(text(70,740,1460,45,rows[0].get('uncertainty','Group count or interval not supplied.'),19,MUTED))
        elif kind=='table':
            for j,r in enumerate(s['rows']):
                yy=215+j*53;v=r['value'];endpoint=r['endpoint'].lower()
                count=r.get('value_unit')=='count_per_output' or 'claims per ' in endpoint or 'spans per ' in endpoint or 'per output' in endpoint or 'tally' in endpoint
                rate=not count and 'FVE' not in r['endpoint'] and r.get('numerator') is not None
                value='Unavailable' if v is None else f'{v*100:.2f}%' if rate else f'{v:.5g}'
                items += [text(70,yy,690,43,label(r['condition'])+' / '+FAMILIES.get(r.get('family'),''),19),text(780,yy,500,43,r['endpoint'],18,MUTED),text(1300,yy,220,43,value,21,TEAL)]
        elif kind=='status':
            m=s['method'];items += [text(70,210,1460,60,'Current status: '+str(m['status']),26,TEAL,True)]
            for j,b in enumerate([m.get('hypothesis','Measured component combinations; no exhaustive cross-product was run.'),m['limits'],m['next_action']]):
                value=' '.join(str(x) for x in b) if isinstance(b,list) else str(b)
                items.append(text(70,310+j*150,1460,130,excerpt(value,350),25,INK if j==0 else MUTED))
        elif kind=='cost_table':
            for j,r in enumerate(s['rows']):
                yy=220+j*66;value=r.get('value');shown='Not measured' if value is None else f'{value:.5g}' if isinstance(value,(int,float)) else str(value)
                items += [text(70,yy,730,55,r['component'],23),text(820,yy,270,25,shown,22,TEAL),
                          text(820,yy+28,285,30,r.get('unit',''),15,MUTED),
                          text(1120,yy,400,55,excerpt(str(r.get('scope',''))+' / '+str(r.get('measurement','')),110),15,MUTED)]
        elif kind=='diagnostic_coverage':
            available=sum(c.get('status')=='existing_diagnostic_only' for c in s['cases']);missing=len(s['cases'])-available
            for j,(name,count,color) in enumerate([('Existing token diagnostic',available,TEAL),('Unavailable at this fixed example',missing,'8495A7')]):
                yy=300+j*160;items += [text(70,yy,660,60,name,31),rect(760,yy,600*count/len(s['cases']),55,color),
                                      text(1380,yy,140,60,str(count)+' / '+str(len(s['cases'])),31,color,True)]
            items.append(text(70,660,1460,85,'Coverage counts only. No independent-reader quality curve or deployed selector was measured.',31,MUTED))
        elif kind=='example':
            c=s['case'];items += [text(70,196,1460,50,c['cell_id'],20,MUTED)]
            for j,side in enumerate(['baseline','proposed']):
                x=70+j*770;v=c.get(side)
                items += [rect(x,280,710,370,'FFFFFF'),text(x+20,295,670,60,('Before: ' if j==0 else 'After: ')+(v or {}).get('label','Diagnostic unavailable'),25,TEAL,True)]
                quote=(v or {}).get('text')
                shown='Empty output: recorded abstention.' if quote=='' else excerpt(quote,300) if quote else 'No prose readout was produced for this diagnostic.'
                items.append(text(x+20,375,670,220,shown,24))
            items.append(text(70,690,1460,105,excerpt(c.get('assessment',s['takeaway']),330),25,MUTED))
        elif kind=='cost':
            eng=s['engineering'];items += [text(70,225,1430,90,'One new synthetic N32 input: '+f"{eng['cold_N32_lifecycle_through_first_selection_seconds']:.2f}"+' seconds through first selection',38,TEAL,True),
                text(70,345,1460,100,eng['basis'],27),text(70,470,1460,90,'Raw and shortened baselines need no reconstruction reader. Selected methods pay for generation and encoding on genuinely new inputs.',29),
                text(70,605,1460,120,'Cached replay is a separate workload. GPU dollar pricing and a latency distribution remain unavailable. Campaign judging cost is not a runtime helper cost.',28,MUTED)]
        if s.get('note'):
            note=s['note']
            if kind=='curves':note+=' Blue: best-fit selection; grey: original; amber: shortened original.'
            items.append(text(70,797,1460,45,note,17,MUTED))
        notes=json.dumps(s,ensure_ascii=False,indent=2)+'\n\nSource report SHA: '+source['report_sha256']+'\nAll displayed values and supplied intervals are copied; no inference or re-estimation.'
        result.append({'title':s['title'],'items':items,'notes':notes})
    return result


def build(source_path, report_path, output):
    source=json.loads(Path(source_path).read_bytes());expected=prepared(report_path, final=source.get('mode')=='reviewed_test')
    if source!=expected:raise ValueError('Draft source differs from the exact reviewed data/story source; regenerate prospectively')
    output=Path(output)
    if output.exists():raise ValueError('Use a new immutable output directory')
    rendered=pages(source);output.mkdir(parents=True)
    write_pptx(rendered,output/'draft.pptx');write_html(rendered,output/'draft.html')
    from pptx import Presentation
    deck=Presentation(output/'draft.pptx')
    final=source.get('mode')=='reviewed_test'
    deck.core_properties.title='Oracle Lens - reviewed held-out results' if final else 'Oracle Lens - comprehensive DEV / VAL draft'
    deck.core_properties.subject=source['status'] if final else 'Reviewed development and validation; final TEST slots are empty'
    deck.save(output/'draft.pptx')
    (output/'source.json').write_bytes(Path(source_path).read_bytes())
    (output/'report-source.json').write_bytes(Path(report_path).read_bytes())
    (output/'geometry.json').write_text(json.dumps(rendered,ensure_ascii=False,indent=2)+'\n')
    (output/'speaker-notes.md').write_text('\n\n'.join(f"# {i}. {p['title']}\n\n{p['notes']}" for i,p in enumerate(rendered,1))+'\n')
    if digest(report_path)!=source['report_sha256']:raise ValueError('Source report changed during slide build; output remains unsealed')
    receipt={'status':source['status'],'source_sha256':digest(source_path),'report_sha256':digest(report_path),
             'builder_sha256':digest(__file__),'shared_geometry_builder_sha256':digest(Path(__file__).with_name('build_slides.py')),
             'slides':len(rendered),'core_slides':16,'native_pptx_rendering_validated':False,'test_quality_access':source['test_quality_access'],
             'native_pptx_renderer_limit':'No native PowerPoint/LibreOffice rendering was validated; the PDF is an HTML geometry mirror, not PPTX-to-PDF conversion.',
             'pdf_route':'HTML same-content mirror, not native PPTX rendering',
             'outputs':{p.name:digest(p) for p in output.iterdir()}}
    if final:
        receipt.update(mode=source['mode'],whole_cohort_complete=source['whole_cohort_complete'],
            test_artifact_sha256=source['test_artifact_sha256'],whole_cohort_artifact_sha256=source['whole_cohort_artifact_sha256'],
            implementation_sha256=source['implementation_sha256'])
    (output/'build.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt


def render(output,chrome,node):
    output=Path(output).resolve();receipt=json.loads((output/'build.json').read_text())
    if digest(output/'draft.html')!=receipt['outputs']['draft.html']:raise ValueError('Draft HTML changed')
    subprocess.run([str(node),str(Path(__file__).with_name('render_slides.mjs')),str(chrome),str(output/'draft.html'),str(output/'draft.pdf')],check=True,timeout=50)
    import pymupdf
    from PIL import Image
    doc=pymupdf.open(output/'draft.pdf')
    if len(doc)!=receipt['slides']:raise ValueError('PDF page count mismatch')
    sheet=Image.new('RGB',(1280,math.ceil(len(doc)/4)*180),'#D6E1EC')
    expected_header='ORACLE LENS / REVIEWED TEST' if receipt.get('mode')=='reviewed_test' else 'ORACLE LENS / DRAFT'
    expected_footer=('All 469: descriptive' if receipt['whole_cohort_complete'] else 'Whole-469 pending; TEST preview only') if receipt.get('mode')=='reviewed_test' else 'TEST quality pending'
    for i,p in enumerate(doc):
        if expected_header not in p.get_text() or expected_footer not in p.get_text():raise ValueError('Source status header/footer clipped')
        if abs(p.rect.width-960)>1 or abs(p.rect.height-540)>1:raise ValueError('Unexpected slide page size')
        path=output/f'slide-{i+1:03}.png';p.get_pixmap(matrix=pymupdf.Matrix(4/3,4/3)).save(path)
        with Image.open(path) as image:sheet.paste(image.resize((320,180)),((i%4)*320,(i//4)*180))
    sheet.save(output/'contact-sheet.png');doc.close()
    (output/'render.json').write_text(json.dumps({'pages':receipt['slides'],'pdf_sha256':digest(output/'draft.pdf'),
        'native_pptx_rendering_validated':False,'native_pptx_renderer_limit':receipt['native_pptx_renderer_limit'],
        'route':receipt['pdf_route']},indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True);parser.add_argument('--prepare-source',action='store_true')
    parser.add_argument('--final',action='store_true',help='Prepare explicitly reviewed revealed TEST results; legacy draft is the default')
    parser.add_argument('--output',type=Path);parser.add_argument('--chrome',type=Path);parser.add_argument('--node',default='node');args=parser.parse_args()
    if args.prepare_source:
        if args.source.exists():raise ValueError('Do not overwrite a prepared source')
        args.source.parent.mkdir(parents=True,exist_ok=True);args.source.write_text(json.dumps(prepared(args.report,final=args.final),ensure_ascii=False,indent=2)+'\n')
    else:
        if not args.output:parser.error('--output is required for build')
        print(json.dumps(build(args.source,args.report,args.output)))
        if args.chrome:render(args.output,args.chrome,args.node)
