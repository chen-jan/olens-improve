"""Separate candidate-only consensus over verified, exact source claim spans.

Exact substring validation checks provenance, not semantic faithfulness. A second
helper check and a manual audit are required before these spans can receive votes.
"""
from dataclasses import asdict, dataclass
import copy
import re

from .helpers import (HelperValidationError, PairRelation, _schema,
                      clique_clusters, MATCH_SCHEMA, MATCH_SYSTEM, validate_matches)
from .selection import Bullet, Selection

EXTRACT_VERSION = 'exact-source-claim-proposals-v1'
VERIFY_VERSION = 'source-to-exact-claim-qualification-v2-numeric-scope'
CLAIM_MATCH_VERSION = 'exact-source-claim-equivalence-v2-numeric-scope'
EXTRACT_SYSTEM = """Propose at most TWO self-contained claims from each supplied source bullet.
You see only noisy candidate prose and opaque source IDs. Return exact contiguous
quotes copied character-for-character from that bullet, without rewriting, joining
disjoint pieces, resolving pronouns or repairing fragments. Each quote must stand
alone as an assertion, instruction or explicitly qualified proposition. Retain the
entities, numbers, negation, modality, temporal scope, conditions and agent/patient
binding that govern its meaning. Do not turn a hypothetical, quoted, uncertain or
denied assertion into an unqualified assertion. A compound bullet may yield two
independent clauses only when each is self-contained with all governing qualifiers.
Use the whole bullet as ONE fallback only if it is self-contained. Otherwise return
no quotes. Never fill gaps using world knowledge. Do not verify factual truth.
Return each supplied source ID exactly once, with zero, one or two exact quotes."""
VERIFY_SYSTEM = """Assess each proposed exact source quote against its FULL parent bullet.
You see no task, activation, transcript, gold answer or benchmark verdict. Determine
source_entails_claim, self_contained and qualifications_preserved separately.
True source entailment means the parent text supports the entire quoted proposition
under its stated referents and scope; it does not mean the proposition is true.
False or null must be used for lost negation, conditions, modality, time restrictions,
quoting/reporting scope, identity, units or relation direction. An exact substring
can still strengthen or misrepresent its parent. Unresolved pronouns, ellipses and
unfinished fragments are not self-contained. Never infer an alias or missing fact.
Accept only if all three fields are true. Return every check_id exactly once, with
at most 300 characters of explanation. Missing/uncertain support remains unknown."""
VERIFY_SYSTEM += """
A bare unlabeled numeric value is not a self-contained answer or intermediate
proposition. Never invent its referent, unit, role or task scope from its parent.
An explicit label such as 'Answer:15' or an equation such as '2+2=4' can express
a proposition; assess its actual stated scope rather than importing missing context."""
CLAIM_MATCH_SYSTEM = MATCH_SYSTEM + """
These inputs are exact source claim spans, not necessarily complete parent bullets.
Judge ONLY the proposition and qualifiers explicitly expressed by each supplied
span. Matching numeric values do not establish matching answer/intermediate roles.
Never infer an answer label, referent, unit or scope absent from the span: bare '15'
must not become equivalent to 'Answer:15'. Equations can express relations. Preserve
uncertainty when either text lacks a self-contained proposition or shared scope."""

EXTRACT_SCHEMA = _schema('source_claim_quotes', {'sources': {'type': 'array', 'items': {
    'type': 'object', 'additionalProperties': False, 'required': ['source_id', 'quotes'],
    'properties': {'source_id': {'type': 'string'}, 'quotes': {
        'type': 'array', 'maxItems': 2, 'items': {'type': 'string'}}}}}}, ['sources'])
VERIFY_FIELDS = {'check_id': {'type': 'string'}, 'source_entails_claim': {'type': ['boolean', 'null']},
                 'self_contained': {'type': ['boolean', 'null']},
                 'qualifications_preserved': {'type': ['boolean', 'null']}, 'reason': {'type': 'string'}}
VERIFY_SCHEMA = _schema('source_claim_support', {'results': {'type': 'array', 'items': {
    'type': 'object', 'additionalProperties': False, 'required': list(VERIFY_FIELDS),
    'properties': VERIFY_FIELDS}}}, ['results'])


@dataclass(frozen=True)
class ClaimSpan:
    claim_id: str
    source_phrase_id: str
    sample_id: str
    sample_index: int
    bullet_position: int
    text: str
    start: int
    end: int
    readout_start: int | None
    readout_end: int | None
    source_text: str

    def bullet(self):
        return Bullet(self.claim_id, self.text, self.sample_id, self.bullet_position,
                      self.readout_start, self.readout_end)


def validate_extraction(result, sources):
    if not isinstance(result, dict) or set(result) != {'sources'} or not isinstance(result['sources'], list):
        raise HelperValidationError('Invalid extraction envelope')
    seen = set()
    for row in result['sources']:
        if not isinstance(row, dict) or set(row) != {'source_id', 'quotes'}:
            raise HelperValidationError('Invalid extraction source fields')
        sid = row['source_id']
        if sid not in sources or sid in seen:
            raise HelperValidationError('Unknown/duplicate extraction source ID')
        seen.add(sid)
        if not isinstance(row['quotes'], list) or len(row['quotes']) > 2 or any(not isinstance(q, str) for q in row['quotes']):
            raise HelperValidationError('At most two string quotes per source required')
    if seen != set(sources):
        raise HelperValidationError('Missing extraction source IDs')


def exact_spans(result, sources):
    """Reject malformed/ambiguous quotes without silently changing their text."""
    validate_extraction(result, sources)
    accepted, rejected = [], []
    for row in result['sources']:
        bullet, index = sources[row['source_id']]
        seen = set()
        for number, quote in enumerate(row['quotes']):
            reason = None
            starts = [i for i in range(len(bullet.text)) if bullet.text.startswith(quote, i)] if quote else []
            if not quote or not quote.strip(): reason = 'empty_quote'
            elif quote in seen: reason = 'duplicate_quote'
            elif len(starts) != 1: reason = 'not_unique_exact_contiguous_source_quote'
            if reason:
                rejected.append({'source_id': row['source_id'], 'source_phrase_id': bullet.phrase_id,
                                 'provider_quote': quote, 'reason': reason})
                continue
            seen.add(quote); start = starts[0]; end = start + len(quote)
            accepted.append(ClaimSpan(f'{bullet.phrase_id}:claim{number}', bullet.phrase_id,
                bullet.sample_id, index, bullet.position, quote, start, end,
                bullet.start + start if bullet.start is not None else None,
                bullet.start + end if bullet.start is not None else None, bullet.text))
    return accepted, rejected


def validate_verification(result, expected):
    if not isinstance(result, dict) or set(result) != {'results'} or not isinstance(result['results'], list):
        raise HelperValidationError('Invalid source-support envelope')
    seen = set()
    for row in result['results']:
        if not isinstance(row, dict) or set(row) != set(VERIFY_FIELDS):
            raise HelperValidationError('Invalid source-support fields')
        if row['check_id'] not in expected or row['check_id'] in seen:
            raise HelperValidationError('Unknown/duplicate source-support check ID')
        seen.add(row['check_id'])
        for field in ('source_entails_claim', 'self_contained', 'qualifications_preserved'):
            if row[field] is not None and not isinstance(row[field], bool):
                raise HelperValidationError('Support fields must be boolean or null')
        if not isinstance(row['reason'], str) or len(row['reason']) > 300:
            raise HelperValidationError('Source-support explanation too long')
    if seen != set(expected): raise HelperValidationError('Missing source-support check IDs')


def bare_numeric_fragment(text):
    """Narrow audit-derived guard, not a general math-expression parser."""
    candidate = text.strip()
    # Only matched outer Markdown delimiters; no operators/labels are removed.
    while True:
        wrapper = next((w for w in ('**', '__', '`', '*', '_')
                        if candidate.startswith(w) and candidate.endswith(w) and len(candidate) > 2*len(w)), None)
        if wrapper is None: break
        candidate = candidate[len(wrapper):-len(wrapper)].strip()
    return re.fullmatch(r'[+\-−]?(?:\d+(?:\.\d*)?|\.\d+)', candidate) is not None


def reused_spans(report, sources):
    """Revalidate every original proposal against the unchanged parsed source."""
    expected_sources = {k: {'source_phrase_id': b.phrase_id, 'sample_index': i,
                           'source_text': b.text} for k, (b, i) in sources.items()}
    if report['sources'] != expected_sources: raise ValueError('Reused proposal source mapping changed')
    lookup = {b.phrase_id: (b, i) for b, i in sources.values()}
    spans = [ClaimSpan(**row) for row in report['proposed_spans']]
    seen, per_source = set(), {}
    for span in spans:
        if span.source_phrase_id not in lookup or span.claim_id in seen:
            raise ValueError('Unknown/duplicate reused claim ID')
        seen.add(span.claim_id); b, i = lookup[span.source_phrase_id]
        per_source[b.phrase_id] = per_source.get(b.phrase_id, 0) + 1
        expected_start = b.start + span.start if b.start is not None else None
        expected_end = b.start + span.end if b.start is not None else None
        if (span.source_text != b.text or span.sample_id != b.sample_id or span.sample_index != i
                or span.bullet_position != b.position or not 0 <= span.start < span.end <= len(b.text)
                or b.text[span.start:span.end] != span.text or not span.text.strip()
                or (span.readout_start, span.readout_end) != (expected_start, expected_end)
                or per_source[b.phrase_id] > 2):
            raise ValueError('Reused exact source span provenance differs')
    return spans


async def extract_verified_spans(samples, proposal_helper, support_helper, *, reused_report=None):
    """At most 2 extraction + 8 verification chunks for an eligible N16 pool."""
    sources = {f'b{i:03d}': (b, s.index) for i, (s, b) in enumerate(
        (s, b) for s in samples if not s.parsing_uncertain for b in s.bullets)}
    if len(sources) > 64: raise ValueError('N16/four-bullet source contract exceeded')
    spans, rejected, missing = [], [], []
    entries = list(sources.items())
    if reused_report is not None:
        spans = reused_spans(reused_report, sources)
        rejected = list(reused_report['local_rejections'])
        missing = list(reused_report['missing_extraction_sources'])
    for offset in ([] if reused_report is not None else range(0, len(entries), 32)):
        chunk = dict(entries[offset:offset + 32]); schema = copy.deepcopy(EXTRACT_SCHEMA)
        schema['json_schema']['schema']['properties']['sources']['items']['properties']['source_id']['enum'] = list(chunk)
        result = await proposal_helper.call(EXTRACT_SYSTEM,
            {'sources': [{'source_id': sid, 'text': value[0].text} for sid, value in chunk.items()]},
            schema, version=EXTRACT_VERSION, max_output_tokens=6000,
            validate=lambda r: validate_extraction(r, chunk))
        if result is None:
            missing.extend(chunk); continue
        found, bad = exact_spans(result, chunk); spans.extend(found); rejected.extend(bad)
    original_spans = list(spans)
    for s in spans:
        if bare_numeric_fragment(s.text):
            rejected.append({'claim_id': s.claim_id, 'source_phrase_id': s.source_phrase_id,
                             'provider_quote': s.text, 'start': s.start, 'end': s.end,
                             'reason': 'bare_numeric_fragment'})
    spans = [s for s in spans if not bare_numeric_fragment(s.text)]
    verified, checks = [], []
    for offset in range(0, len(spans), 16):
        chunk = spans[offset:offset + 16]; expected = {f'p{i:02d}': s for i, s in enumerate(chunk)}
        schema = copy.deepcopy(VERIFY_SCHEMA)
        schema['json_schema']['schema']['properties']['results']['items']['properties']['check_id']['enum'] = list(expected)
        result = await support_helper.call(VERIFY_SYSTEM, {'checks': [
            {'check_id': uid, 'source_text': s.source_text, 'claim_text': s.text}
            for uid, s in expected.items()]}, schema, version=VERIFY_VERSION, max_output_tokens=6000,
            validate=lambda r: validate_verification(r, expected))
        if result is None:
            checks.extend({'claim_id': s.claim_id, 'accepted': False, 'status': 'unknown_missing_helper'} for s in chunk)
            continue
        for row in result['results']:
            span = expected[row['check_id']]
            accepted = all(row[k] is True for k in ('source_entails_claim', 'self_contained', 'qualifications_preserved'))
            checks.append({'claim_id': span.claim_id, 'accepted': accepted, 'status': 'checked', **row})
            if accepted: verified.append(span)
    return verified, {'sources': {k: {'source_phrase_id': b.phrase_id, 'sample_index': i,
                      'source_text': b.text} for k, (b, i) in sources.items()},
        'proposed_spans': [asdict(s) for s in original_spans], 'accepted_spans': [asdict(s) for s in verified],
        'local_rejections': rejected, 'missing_extraction_sources': missing, 'source_checks': checks,
        'extraction_reused': reused_report is not None,
        'semantic_caveat': 'Helper source entailment and qualifications are audit-required labels, not verified truth.'}


def span_groups(spans):
    groups = {}
    for span in sorted(spans, key=lambda s: (s.sample_index, s.bullet_position, s.start, s.claim_id)):
        groups.setdefault(' '.join(span.text.split()), []).append(span)
    return list(groups.values())


def span_pair_shortlist(groups, limit=40):
    """Lexical retrieval only; semantic decisions are made by the frozen matcher."""
    if not 0 <= limit <= 40: raise ValueError('At most forty span-pair confirmations')
    tokens = [set(re.findall(r'\w+', g[0].text.casefold())) for g in groups]
    scored = []
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            if len({s.sample_id for s in groups[i] + groups[j]}) == 1: continue
            overlap = len(tokens[i] & tokens[j]); union = len(tokens[i] | tokens[j])
            if overlap: scored.append((-overlap / max(union, 1), i, j))
    return [(f'c{i:03d}', f'c{j:03d}') for _, i, j in sorted(scored)[:limit]]


async def span_relations(spans, helper):
    groups = span_groups(spans); texts = {f'c{i:03d}': g[0].text for i, g in enumerate(groups)}
    pairs = span_pair_shortlist(groups)
    relations = {}
    for offset in range(0, len(pairs), 20):
        chunk = pairs[offset:offset+20]
        payload = [{'pair_id': f'p{i:02d}', 'a_text': texts[a], 'b_text': texts[b]}
                   for i, (a, b) in enumerate(chunk)]
        schema = copy.deepcopy(MATCH_SCHEMA)
        schema['json_schema']['schema']['properties']['results']['items']['properties']['pair_id']['enum'] = [r['pair_id'] for r in payload]
        result = await helper.call(CLAIM_MATCH_SYSTEM, {'pairs': payload}, schema,
                                  version=CLAIM_MATCH_VERSION, max_output_tokens=6000,
                                  validate=lambda r: validate_matches(r, payload))
        if result is None: continue
        for row in result['results']:
            a, b = chunk[int(row['pair_id'][1:])]
            evidence = {side: {'start': 0, 'end': len(texts[uid]), 'text': texts[uid],
                              'source': 'Complete exact claim span; not truth verification.'}
                        for side, uid in [('a', a), ('b', b)]}
            relations[tuple(sorted((a, b)))] = PairRelation(a, b, row['label'], row['a_entails_b'],
                 row['b_entails_a'], row['compatible'], row['reason'], evidence)
    clusters = clique_clusters(list(texts), relations)
    return {'groups': [[s.claim_id for s in g] for g in groups], 'texts': texts,
            'requested_pairs': pairs, 'relations': [asdict(r) for r in relations.values()],
            'clusters': clusters, 'missing_pairs': [p for p in pairs if p not in relations],
            'retrieval_caveat': 'Bounded lexical shortlist misses translations and low-overlap paraphrases; unknown pairs never merge.'}


def select_span_support(spans, evidence, fraction, admissible, *, semantic):
    if fraction not in (0., .125): raise ValueError('Only frozen soft/.125 settings')
    groups = span_groups(spans)
    clusters = evidence['clusters'] if semantic else [[f'c{i:03d}'] for i in range(len(groups))]
    rows = []
    for order, cluster in enumerate(clusters):
        members = [s for uid in cluster for s in groups[int(uid[1:])]]
        sample_ids = sorted({s.sample_id for s in members})
        if len(sample_ids) >= fraction * 16:
            representative = min(members, key=lambda s: (s.sample_index, s.bullet_position, s.start, s.claim_id))
            rows.append((-len(sample_ids), order, representative, sample_ids, [s.claim_id for s in members]))
    selected, trace = [], []
    for minus_support, _, span, voters, members in sorted(rows, key=lambda r: (r[0], r[1])):
        if len(selected) == 4: break
        if admissible(tuple(s.bullet() for s in selected) + (span.bullet(),)):
            selected.append(span); trace.append({'claim_id': span.claim_id, 'support': -minus_support,
                'sample_ids': voters, 'source_claim_ids': members})
    return Selection('consensus_over_extracted_claims', tuple(s.bullet() for s in selected), None,
                     tuple(trace), 'selected' if selected else 'abstained')


def extraction_only(spans, source_phrase_ids, admissible):
    """Preserve the whole-bullet A16 parent's ordering; stop at complete-span cap."""
    selected = []
    for source_id in source_phrase_ids:
        for span in sorted((s for s in spans if s.source_phrase_id == source_id), key=lambda s: s.start):
            if len(selected) == 4 or not admissible(tuple(s.bullet() for s in selected) + (span.bullet(),)):
                return Selection('extraction_only_a16', tuple(s.bullet() for s in selected), None)
            selected.append(span)
    return Selection('extraction_only_a16', tuple(s.bullet() for s in selected), None)


def random_matched_spans(spans, count, admissible, rng):
    """Count-matched random pool control, without changing source text."""
    unique = [group[0] for group in span_groups(spans)]; rng.shuffle(unique)
    selected = []
    for span in unique:
        if len(selected) == count: break
        if admissible(tuple(s.bullet() for s in selected) + (span.bullet(),)): selected.append(span)
    return Selection('random_spans_matched_count', tuple(s.bullet() for s in selected), None,
                     reason='matched' if len(selected) == count else 'count_unmatched_cap')
