"""Candidate-only Luna labels. Primary output text always comes from the pool.

Model-visible IDs are opaque local IDs, not benchmark IDs (which can themselves
reveal answers). Semantics, support and mutual consistency are separate. An
equivalence cluster is a verified clique, never a single-link component.
"""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
import sqlite3
import re
import copy
from typing import Any

from .budget import BudgetExceeded
from .data import canonical
from .evaluation import JUDGE_MODEL, request_cache_key
from .selection import Bullet, Sample, Selection, render_bullets, parse_bullets

PROPOSAL_VERSION = 'candidate-pair-proposal-local-ids-v2'
MATCH_VERSION = 'whole-bullet-equivalence-compatibility-v5-local-ids-v1'
VETO_VERSION = 'restatement-temporal-merge-veto-v1'
PROPOSAL_SYSTEM = """You shortlist pairs of text assertions that might express the SAME proposition.
You see only noisy source bullets with opaque IDs. Propose likely paraphrases, including
translations, for later verification. Do not rewrite, summarize or repair the bullets.
Shared topic is insufficient. Preserve entities, numbers, dates, units, negation, relation
direction, conditional clauses, modality and all claims in compound bullets. A short bullet
and a longer bullet with an extra claim need not be equivalent. Do not infer missing facts.
Return unique source-ID pairs only, up to the requested limit. An empty list is valid."""
MATCH_SYSTEM = """Compare each supplied pair of WHOLE source bullets. You see no original task,
activation, transcript, correct answer or judge verdict. Use only the two texts.
Return one result per pair. Labels:
- equivalent: each ENTIRE bullet entails the other, with all assertions preserved;
- one-way entails: exactly one entire bullet entails the other;
- contradicts: at least one explicit assertion cannot hold together with the other;
- related: some connection, but neither whole bullet entails the other, without an explicit contradiction;
- uncertain: text, missing referents or incomplete fragments prevent a confident decision.
Assess a_entails_b and b_entails_a separately. Equivalence needs both true, never topic overlap.
Numbers, entities, negation, agent/patient order, quantifiers, conditionals and modality matter.
Do not merge a compound bullet with one of its clauses: its additional claims still matter.
Every explanatory phrase, parenthetical, comment, temporal ordering, stated outcome,
summary constraint and qualification counts as content. A shared leading number, name or
event never licenses discarding the rest. A bare result does not entail its explanation;
"summarize" does not entail "summarize in one sentence". Match ALL additional clauses
bidirectionally or keep the bullets separate. An incomplete extra clause is not harmless:
return uncertain when its missing content prevents whole-bullet comparison.
Check entailment directions against the entire texts, including any self-correction.
Separately assess compatible: can the two ENTIRE bullets simultaneously hold under their
stated referents? Different propositions may be compatible. True means supported compatibility,
false means a contradiction, null means uncertainty. Compatibility is NOT equivalence or truth.
Do not silently assume different unnamed referents are the same, or vice versa.
If simultaneous truth requires differently named people/entities to be identical,
return uncertain/null unless the texts explicitly establish that identity. Do not infer aliases.
Return the supplied pair_id exactly. Do not emit quotes or character offsets: the caller
stores the complete original pair locally. Explain in at most 400 characters per pair.
Return uncertain/null when in doubt; never fill gaps with benchmark or world-knowledge guesses."""


def _schema(name: str, properties: dict, required: list[str]) -> dict:
    return {'type': 'json_schema', 'json_schema': {'name': name, 'strict': True,
        'schema': {'type': 'object', 'properties': properties, 'required': required,
                   'additionalProperties': False}}}


PROPOSAL_SCHEMA = _schema('candidate_pairs', {'pairs': {'type': 'array', 'items': {
    'type': 'object', 'additionalProperties': False, 'required': ['a','b'],
    'properties': {'a': {'type': 'string'}, 'b': {'type': 'string'}}}}}, ['pairs'])
_MATCH_FIELDS = {
    'pair_id': {'type': 'string'},
    'label': {'type': 'string', 'enum': ['equivalent','one-way entails','contradicts','related','uncertain']},
    'a_entails_b': {'type': ['boolean','null']}, 'b_entails_a': {'type': ['boolean','null']},
    'compatible': {'type': ['boolean','null']},
    'reason': {'type': 'string'},
}
MATCH_SCHEMA = _schema('pair_relations', {'results': {'type': 'array', 'items': {
    'type': 'object', 'additionalProperties': False, 'required': list(_MATCH_FIELDS),
    'properties': _MATCH_FIELDS}}}, ['results'])

EDIT_VERSION='candidate-only-local-editor-v2'
EDIT_SYSTEM="""You propose limited edits to noisy source bullet lists. You receive only
candidate prose and opaque parent IDs, with no task, activation, context, correct answer or verdict.
Produce at most FOUR proposals TOTAL across all supplied parents, not four per parent.
Each proposal must identify one supplied parent using its exact s0/s1 ID.
The caller assigns proposal IDs locally; do not invent or swap parent labels.
Improve coherence and remove repetition. You may delete a whole assertion or simplify wording,
but preserve numbers, names, negation, relation direction, conditions and qualifications of any
retained assertion. Do not add specific entities, numbers, relations or factual claims absent
from that parent. You cannot determine truth from these bullets: do not pretend to verify facts.
Output each proposed readout as at most four dash-prefixed bullets; use at most256 text tokens.
An empty readout or fewer proposals is allowed. Never emit an explanatory preamble.
Give a short change_summary of at most400 characters. Do not include hidden reasoning.
Return only the requested JSON. Unchanged parents remain available to the local selector."""
EDIT_SCHEMA=_schema('candidate_edits',{'proposals':{'type':'array','items':{
    'type':'object','additionalProperties':False,'required':['parent_id','text','change_summary'],
    'properties':{'parent_id':{'type':'string','enum':['s0','s1']},
        'text':{'type':'string'},'change_summary':{'type':'string'}}}}},['proposals'])


def canonicalize_edit_proposals(result: dict, parents: dict[str,str], *, token_count) -> tuple[list, list]:
    """Opaque proposal IDs are bookkeeping; source parent identity is essential."""
    if set(result)!={'proposals'} or not isinstance(result['proposals'],list) or len(result['proposals'])>4:
        raise HelperValidationError('Editor envelope exceeds aggregate proposal contract')
    accepted=[];rejected=[]
    for i,provider in enumerate(result['proposals']):
        row={**provider,'id':f'p{i}','provider_proposal_id':provider.get('id')}
        if provider.get('parent_id') not in parents:
            rejected.append({'proposal':provider,'reason':'unresolved_parent_reference'});continue
        sample=parse_bullets(provider['text'],'editor-output',0)
        if token_count(provider['text'])>256 or (provider['text'].strip() and sample.parsing_uncertain) or 'deterministically_capped' in sample.flags:
            rejected.append({'proposal':provider,'reason':'violates_full_readout_parser_or_token_cap'});continue
        accepted.append(row)
    return accepted,rejected


async def editing_proposals(helper: 'LunaHelper', parents: dict[str,str], *, token_count) -> dict:
    """One physical call/round: malformed proposals never trigger extra proposals."""
    if helper.attempts!=1:
        raise ValueError('Editor requires attempts=1 so retries cannot inflate proposal budget')
    if not 1<=len(parents)<=2 or set(parents)-{'s0','s1'}:
        raise ValueError('One or two opaque parents required')
    def validate(result):
        if not isinstance(result,dict) or set(result)!={'proposals'} or not isinstance(result['proposals'],list):
            raise HelperValidationError('Editor JSON envelope invalid')
        if len(result['proposals'])>4:raise HelperValidationError('More than4 aggregate proposals')
        for row in result['proposals']:
            if set(row)!={'parent_id','text','change_summary'} or any(not isinstance(v,str) for v in row.values()):
                raise HelperValidationError('Editor proposal schema invalid')
            if len(row['change_summary'])>400:raise HelperValidationError('Editor summary exceeds400chars')
    result=await helper.call(EDIT_SYSTEM,{'parents':[{'id':pid,'text':text} for pid,text in parents.items()],
        'total_proposal_limit':4},EDIT_SCHEMA,version=EDIT_VERSION,max_output_tokens=4000,validate=validate)
    accepted,rejected=canonicalize_edit_proposals(result,parents,token_count=token_count) if result is not None else ([],[])
    return {'version':EDIT_VERSION,'proposals':accepted,'rejected':rejected,
        'physical_calls_limit':1,'aggregate_proposal_limit':4,'helper_valid':result is not None,
        'faithfulness_note':'Candidate-only editor cannot verify truth; reencoding and independent judging required.'}


class HelperValidationError(ValueError):
    pass


class HelperCache:
    """Exact validated task-response cache; no votes or truth labels are cached."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS responses (key TEXT PRIMARY KEY, response TEXT NOT NULL)')

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            db.execute('PRAGMA busy_timeout=30000')
            db.execute('PRAGMA journal_mode=DELETE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, key: str) -> dict | None:
        with self._connect() as db:
            row = db.execute('SELECT response FROM responses WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, result: dict) -> None:
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT OR IGNORE INTO responses VALUES (?,?)', (key, canonical(result)))


class LunaHelper:
    """Use the reviewed BudgetedClient, with bounded logical retries and concurrency."""
    def __init__(self, client: Any, cache: HelperCache, *, service_tier: str = 'default',
                 concurrency: int = 4, attempts: int = 2, reasoning_effort: str = 'none'):
        if service_tier not in ('default','flex') or not 1 <= attempts <= 2:
            raise ValueError('Explicit tier and at most two logical attempts required')
        if reasoning_effort not in ('none','medium'):
            raise ValueError('Only none or the explicit medium helper diagnostic is supported')
        self.client, self.cache, self.tier = client, cache, service_tier
        self.reasoning_effort = reasoning_effort
        self.attempts = attempts
        self.semaphore = asyncio.Semaphore(concurrency)
        self.events: list[dict] = []

    async def call(self, system: str, payload: dict, schema: dict, *, version: str,
                   validate, max_output_tokens: int = 6000) -> dict | None:
        # No context, run IDs or provenance headings are inserted in the payload.
        request = {'model': JUDGE_MODEL, 'reasoning_effort': self.reasoning_effort, 'service_tier': self.tier,
            'max_completion_tokens': max_output_tokens, 'timeout': 90,
            'messages': [{'role':'system','content':system}, {'role':'user','content':canonical(payload)}],
            'response_format': schema}
        if self.reasoning_effort == 'none':
            request['temperature'] = 0
        key = hashlib.sha256(canonical({'version':version,'request_key':request_cache_key(request)}).encode()).hexdigest()
        cached = self.cache.get(key)
        if cached is not None:
            validate(cached)
            self.events.append({'version':version,'content_key':key,'cached':True})
            return cached
        for attempt in range(self.attempts):
            response = None
            try:
                async with self.semaphore:
                    response = await self.client.chat.completions.create(**request)
                choice = response.choices[0]
                if choice.finish_reason != 'stop' or getattr(choice.message, 'refusal', None):
                    raise HelperValidationError('Refused/truncated helper output')
                result = json.loads(choice.message.content or '')
                validate(result)
                self.cache.put(key,result)
                self.events.append({'version':version,'content_key':key,'cached':False,'attempt':attempt,
                                    'response_id':response.id,'valid':True})
                return result
            except BudgetExceeded:
                raise
            except Exception as error:
                self.events.append({'version':version,'content_key':key,'cached':False,'attempt':attempt,
                                    'valid':False,'error_type':type(error).__name__,
                                    'response_id':getattr(response,'id',None),
                                    'validation_error':str(error)[:400] if isinstance(error,(HelperValidationError,json.JSONDecodeError)) else None})
                if attempt + 1 < self.attempts:
                    await asyncio.sleep(min(2 ** attempt, 4))
        return None


@dataclass(frozen=True)
class PairRelation:
    a: str
    b: str
    label: str
    a_entails_b: bool | None
    b_entails_a: bool | None
    compatible: bool | None
    reason: str
    evidence: dict

    @property
    def equivalent(self) -> bool:
        return (self.label == 'equivalent' and self.a_entails_b is True
                and self.b_entails_a is True and self.compatible is True)


def _pair(a: str, b: str) -> tuple[str,str]:
    if a == b:
        raise HelperValidationError('Self-pairs are not semantic evidence')
    return tuple(sorted((a,b)))


def validate_proposal(result: dict, texts: dict[str,str], limit: int) -> None:
    if not isinstance(result,dict) or set(result) != {'pairs'} or not isinstance(result['pairs'],list):
        raise HelperValidationError('Invalid proposal schema')
    for row in result['pairs']:
        if not isinstance(row,dict) or set(row) != {'a','b'} or not all(isinstance(row[k],str) for k in ('a','b')):
            raise HelperValidationError('Invalid proposal row structure')


def canonicalize_proposals(result: dict | None, texts: dict[str,str], limit: int) -> tuple[list, list]:
    """Repair bookkeeping locally; skipped proposals are never confident labels."""
    if result is None:
        return [], [{'reason': 'proposal_call_exhausted; candidate pair coverage unknown'}]
    accepted, skipped, seen = [], [], set()
    for index, row in enumerate(result['pairs']):
        reason = None
        if row['a'] not in texts or row['b'] not in texts:
            reason = 'unknown_source_id'
        elif row['a'] == row['b']:
            reason = 'self_pair'
        else:
            key = tuple(sorted((row['a'],row['b'])))
            if key in seen:
                reason = 'duplicate_pair'
            elif len(accepted) >= limit:
                reason = 'beyond_fixed_pair_budget'
            else:
                seen.add(key); accepted.append(key)
        if reason:
            skipped.append({'provider_index': index, 'provider_pair': row, 'reason': reason})
    return accepted, skipped


def validate_matches(result: dict, payload_pairs: list[dict]) -> None:
    expected = {x['pair_id']: x for x in payload_pairs}
    if not isinstance(result,dict) or set(result) != {'results'} or not isinstance(result['results'],list):
        raise HelperValidationError('Invalid match schema')
    seen = set()
    for row in result['results']:
        if not isinstance(row,dict) or set(row) != set(_MATCH_FIELDS):
            raise HelperValidationError('Missing/extra match fields')
        pid = row['pair_id']
        if pid not in expected or pid in seen:
            raise HelperValidationError('Unknown/duplicate pair ID')
        seen.add(pid)
        if row['label'] not in _MATCH_FIELDS['label']['enum']:
            raise HelperValidationError('Unknown relation label')
        for field in ('a_entails_b','b_entails_a','compatible'):
            if row[field] is not None and not isinstance(row[field],bool):
                raise HelperValidationError('Entailment/compatibility must be boolean or null')
        if row['label'] == 'equivalent' and not all(row[k] is True for k in ('a_entails_b','b_entails_a','compatible')):
            raise HelperValidationError('Equivalence must be bidirectional and compatible')
        if row['label'] == 'one-way entails' and (row['a_entails_b'] is None or row['b_entails_a'] is None or row['a_entails_b']==row['b_entails_a']):
            raise HelperValidationError('One-way entailment needs exactly one direction')
        if row['label'] == 'one-way entails' and row['compatible'] is not True:
            raise HelperValidationError('Whole-bullet one-way entailment must be compatible')
        if row['label'] in ('related','contradicts') and (row['a_entails_b'] is not False or row['b_entails_a'] is not False):
            raise HelperValidationError('Related/contradictory whole bullets cannot also entail each other')
        if row['label'] == 'contradicts' and row['compatible'] is not False:
            raise HelperValidationError('Contradiction must be incompatible')
        if row['label'] == 'uncertain' and row['compatible'] is not None:
            raise HelperValidationError('Uncertain compatibility must remain null')
        if not isinstance(row['reason'],str) or len(row['reason']) > 400:
            raise HelperValidationError('Invalid/excessive rationale')
    if seen != set(expected):
        raise HelperValidationError('Missing requested pair results')


async def confirm_pairs(helper: LunaHelper, pairs: list[tuple[str,str]], texts: dict[str,str],
                        *, chunk_size: int = 20, max_output_tokens: int = 6000) -> dict[tuple[str,str],PairRelation]:
    if not 1 <= chunk_size <= 20:
        raise ValueError('Confirmation chunks must contain at most20 pairs')
    relations = {}
    async def chunk_call(chunk):
        payload_pairs = [{'pair_id':f'p{i:02d}','a_text':texts[a],'b_text':texts[b]}
                         for i,(a,b) in enumerate(chunk)]
        schema = copy.deepcopy(MATCH_SCHEMA)
        schema['json_schema']['schema']['properties']['results']['items']['properties']['pair_id']['enum'] = [x['pair_id'] for x in payload_pairs]
        result = await helper.call(MATCH_SYSTEM, {'pairs':payload_pairs}, schema,
            version=MATCH_VERSION, validate=lambda r:validate_matches(r,payload_pairs),
            max_output_tokens=max_output_tokens)
        if result is None:
            return
        for row in result['results']:
            index = int(row['pair_id'][1:])
            a,b = chunk[index]
            evidence = {side:{'start':0,'end':len(texts[uid]),'text':texts[uid],
                              'source':'Complete local source text; not model-extracted evidence or truth verification.'}
                        for side,uid in [('a',a),('b',b)]}
            relations[_pair(a,b)] = PairRelation(a,b,row['label'],row['a_entails_b'],row['b_entails_a'],
                                                 row['compatible'],row['reason'],evidence)
    await asyncio.gather(*(chunk_call(pairs[i:i+chunk_size]) for i in range(0,len(pairs),chunk_size)))
    return relations


def clique_clusters(ids: list[str], relations: dict[tuple[str,str],PairRelation]) -> list[list[str]]:
    """Deterministic greedy complete-link groups; missing comparisons cannot merge."""
    clusters: list[list[str]] = []
    for uid in ids:
        for group in clusters:
            if all(_pair(uid,other) in relations and relations[_pair(uid,other)].equivalent for other in group):
                group.append(uid)
                break
        else:
            clusters.append([uid])
    return clusters


async def semantic_consensus(samples: list[Sample], helper: LunaHelper, *,
                             min_support_fraction: float = .25, max_pairs: int = 40,
                             filter_compatibility: bool = True, admissible=None) -> tuple[Selection,dict]:
    if not 0 <= min_support_fraction <= 1 or not 6 <= max_pairs <= 40:
        raise ValueError('Support in0..1 and bounded6..40 pair budget required')
    ordered = sorted(samples,key=lambda s:s.index)
    if len({s.sample_id for s in ordered}) != len(ordered):
        raise ValueError('Distinct source sample IDs required')
    exact: dict[str,list[Bullet]] = {}
    for sample in ordered:
        if sample.parsing_uncertain:
            continue
        for bullet in sample.bullets:
            exact.setdefault(' '.join(bullet.text.split()),[]).append(bullet)
    groups = list(exact.values())
    # Only opaque local IDs and candidate text cross the helper boundary.
    sources = {f'b{i:03d}':values for i,values in enumerate(groups)}
    texts = {uid:values[0].text for uid,values in sources.items()}
    relation_budget = max_pairs - 6 if filter_compatibility else max_pairs
    proposal = None
    if len(texts) > 1:
        schema = copy.deepcopy(PROPOSAL_SCHEMA)
        for side in ('a','b'):
            schema['json_schema']['schema']['properties']['pairs']['items']['properties'][side]['enum'] = list(texts)
        proposal = await helper.call(PROPOSAL_SYSTEM,
            {'bullets':[{'id':uid,'text':text} for uid,text in texts.items()], 'pair_limit':relation_budget},
            schema,version=PROPOSAL_VERSION,max_output_tokens=1200,
            validate=lambda r:validate_proposal(r,texts,relation_budget))
    proposed_pairs, proposal_skipped = canonicalize_proposals(proposal,texts,relation_budget) if len(texts)>1 else ([],[])
    relations = await confirm_pairs(helper,proposed_pairs,texts)
    clusters = clique_clusters(list(texts),relations)
    # Supporting sample IDs are local bookkeeping; the helper never receives them.
    ranked = []
    for cluster in clusters:
        members = [b for uid in cluster for b in sources[uid]]
        support = len({b.sample_id for b in members})
        representative = members[0]
        if support >= min_support_fraction * len(ordered):
            ranked.append((support,list(texts).index(cluster[0]),representative,cluster))
    ranked.sort(key=lambda x:(-x[0],x[1]))
    # Up to4 tentative representatives; separate compatibility check, never a
    # demand that different output bullets express the same proposition.
    tentative = []
    for row in ranked:
        if len(tentative) == 4:
            break
        if admissible is None or admissible(tuple(x[2] for x in tentative)+ (row[2],)):
            tentative.append(row)
    compatibility_pairs = []
    if filter_compatibility:
        for i,left in enumerate(tentative):
            for right in tentative[i+1:]:
                key = _pair(left[3][0],right[3][0])
                if key not in relations:
                    compatibility_pairs.append(key)
        if len(proposed_pairs)+len(compatibility_pairs) > max_pairs:
            raise ValueError('Total equivalence/compatibility budget exceeded')
        relations.update(await confirm_pairs(helper,compatibility_pairs,texts))
    selected,skipped = [],[]
    for row in tentative:
        if filter_compatibility:
            checks = [relations.get(_pair(row[3][0],prior[3][0])) for prior in selected]
            if any(check is None or check.compatible is not True for check in checks):
                skipped.append({'phrase_id':row[2].phrase_id,'reason':'incompatible_or_unverified_pairwise_compatibility'})
                continue
        selected.append(row)
    bullets = tuple(row[2] for row in selected)
    method = 'semantic_consensus_compatible' if filter_compatibility else 'semantic_consensus_no_compatibility_filter'
    report = {
        'prompt_versions':[PROPOSAL_VERSION,MATCH_VERSION], 'unique_exact_groups':len(groups),
        'semantic_clusters':len(clusters),'proposal_pairs':len(proposed_pairs),
        'proposal_skipped':proposal_skipped, 'equivalence_requested_pairs':[list(k) for k in proposed_pairs],
        'compatibility_pairs':len(compatibility_pairs),'verified_pairs':len(relations),
        'compatibility_requested_pairs':[list(k) for k in compatibility_pairs],
        'requested_but_unverified_pairs':[list(k) for k in proposed_pairs+compatibility_pairs if k not in relations],
        'budget_unverified_policy':'Leave unmatched pairs separate; compatibility-unknown tentative outputs abstain.',
        'clusters':[{'opaque_members':c,'source_phrase_ids':[b.phrase_id for uid in c for b in sources[uid]],
                     'supporting_samples':sorted({b.sample_id for uid in c for b in sources[uid]})} for c in clusters],
        'relations':[asdict(v) for v in relations.values()], 'skipped':skipped,
        'selected_phrase_ids':[b.phrase_id for b in bullets],
        'unfiltered_phrase_ids':[row[2].phrase_id for row in tentative],
        'unfiltered_text':render_bullets(tuple(row[2] for row in tentative)),
        'compatibility_ablation':'Same clusters/ranking/candidate/output budgets; compare unfiltered_text with selected text, reusing labels.',
        'source_mapping':{uid:[b.phrase_id for b in values] for uid,values in sources.items()},
        'no_rewriting':True,'consistency_scope':'Verified pairwise compatibility only; not truth or joint logical satisfiability.',
    }
    selection = Selection(method,bullets,None,tuple(skipped), 'selected' if bullets else 'abstained')
    return selection,report


def semantic_audit_pairs() -> list[dict]:
    """40 prewritten candidate-text traps, separate from benchmark data and tuning."""
    pairs = []
    for i in range(5):
        a,b = f'Person A{i}',f'Person B{i}'
        examples = [
            ('equivalent',f'{a} handed the key to {b}.',f'{b} received the key from {a}.'),
            ('equivalent',f'The computed total is {10+i}.',f'The result of the computation equals {10+i}.'),
            ('contradicts',f'The computed total is exactly {10+i}.',f'The computed total is exactly {11+i}.'),
            ('contradicts',f'{a} owns this unique key.',f'{a} does not own this unique key.'),
            ('not_equivalent',f'{a} chased {b}.',f'{b} chased {a}.'),
            ('one-way entails',f'{a} owns a red car and a bicycle.',f'{a} owns a red car.'),
            ('not_equivalent',f'{a} might deliver the letter.',f'{a} definitely delivered the letter.'),
            ('contradicts',f'{a} is the only owner of this unique key.',f'{b} is the only owner of this unique key.'),
        ]
        for expected,left,right in examples:
            pairs.append({'audit_id':f'trap{len(pairs):02d}','expected':expected,'a':left,'b':right})
    return pairs


def distinct_owner_audit_pairs() -> list[dict]:
    """Additional identity-clarified traps; never replace the original40 results."""
    return [{'audit_id':f'distinct-owner{i}', 'expected':'contradicts',
        'a':f'Person A{i} and Person B{i} are distinct people. Person A{i} is the only owner of this unique key.',
        'b':f'Person A{i} and Person B{i} are distinct people. Person B{i} is the only owner of this unique key.'}
        for i in range(5)]


def reselect_consensus(samples: list[Sample], report: dict, *, fraction: float,
                      filter_compatibility: bool, admissible=None) -> dict:
    """Offline threshold sweep reuses fixed clusters/labels; unknown pairs abstain."""
    if not 0 <= fraction <= 1:
        raise ValueError('Support fraction must be in0..1')
    bullets = {b.phrase_id:b for s in samples for b in s.bullets}
    ranked=[]
    for i,c in enumerate(report['clusters']):
        support=len(c['supporting_samples'])
        if support >= fraction*len(samples):
            ranked.append((support,i,bullets[c['source_phrase_ids'][0]],c['opaque_members'][0]))
    ranked.sort(key=lambda x:(-x[0],x[1]))
    tentative=[]
    for row in ranked:
        if len(tentative)==4:break
        if admissible is None or admissible(tuple(x[2] for x in tentative)+(row[2],)):
            tentative.append(row)
    relations={_pair(r['a'],r['b']):r for r in report['relations']}
    selected=[]
    skipped=[]
    for row in tentative:
        checks=[relations.get(_pair(row[3],prior[3])) for prior in selected]
        if filter_compatibility and any(r is None or r['compatible'] is not True for r in checks):
            skipped.append(row[2].phrase_id)
        else:selected.append(row)
    return {'support_fraction':fraction,'text':render_bullets(tuple(x[2] for x in selected)),
        'phrase_ids':[x[2].phrase_id for x in selected], 'skipped_unverified_or_incompatible':skipped,
        'compatibility_filter':filter_compatibility,'new_calls':0,
        'limitation':'Fixed pair-budget labels; agreement lower bound. Unchecked pairs stay separate.'}


def conservative_merge_veto(left: str, right: str) -> list[str]:
    """A visible conservative lexical veto, not semantic or truth verification."""
    if ' '.join(left.split()) == ' '.join(right.split()):
        return []
    reasons = []
    alternatives = r'\b(?:or more concisely|or rather|alternatively|in other words|here are (?:two|three|several) (?:versions|options)|option\s*\d+)\b'
    if re.search(alternatives,left,re.I) or re.search(alternatives,right,re.I):
        reasons.append('explicit_alternative_or_restatement_requires_preserving_every_version')
    temporal = re.compile(r'\b(?:before|after|then|first|later|until|while|subsequent(?:ly)?|following)\b',re.I)
    if sorted(x.lower() for x in temporal.findall(left)) != sorted(x.lower() for x in temporal.findall(right)):
        reasons.append('unmatched_explicit_temporal_cues')
    return reasons


def report_with_merge_veto(samples: list[Sample], report: dict, *, enabled: bool) -> dict:
    """Split existing clusters using the same evidence; never add a paid comparison."""
    result = copy.deepcopy(report)
    result['merge_veto'] = {'version': VETO_VERSION, 'enabled': enabled,
        'meaning': 'Conservative lexical rejection; may create false splits and is not proof of correct remaining merges.'}
    if not enabled:
        return result
    bullets = {b.phrase_id:b for s in samples for b in s.bullets}
    mapping = report['source_mapping']
    native = {_pair(r['a'],r['b']):PairRelation(**r) for r in report['relations']}
    allowed = {}
    vetoed = []
    for key, relation in native.items():
        a,b = key
        reasons = conservative_merge_veto(bullets[mapping[a][0]].text,bullets[mapping[b][0]].text)
        if relation.equivalent and reasons:
            vetoed.append({'a':a,'b':b,'reasons':reasons})
        else:
            allowed[key] = relation
    clusters = []
    for cluster in report['clusters']:
        for members in clique_clusters(cluster['opaque_members'],allowed):
            ids = [pid for uid in members for pid in mapping[uid]]
            clusters.append({'opaque_members': members, 'source_phrase_ids': ids,
                'supporting_samples': sorted({bullets[pid].sample_id for pid in ids})})
    result['clusters'] = clusters
    result['semantic_clusters'] = len(clusters)
    result['merge_veto']['vetoed_pairs'] = vetoed
    return result


def audit_summary(pairs: list[dict], relations: dict[tuple[str,str],PairRelation]) -> dict:
    rows = []
    for i,pair in enumerate(pairs):
        relation = relations.get(_pair(f'a{i:03d}',f'b{i:03d}'))
        predicted = relation.label if relation else 'unverified'
        equivalent = relation.equivalent if relation else False
        rows.append({'audit_id':pair['audit_id'],'expected':pair['expected'],'predicted':predicted,
                     'false_merge':equivalent and pair['expected']!='equivalent',
                     'false_split':not equivalent and pair['expected']=='equivalent',
                     'unsafe_compatibility':relation is not None and relation.compatible is True and pair['expected']=='contradicts',
                     'label_error':predicted!=pair['expected'] if pair['expected']!='not_equivalent' else equivalent,
                     'unverified':relation is None})
    return {'pairs':len(rows),'verified':sum(not r['unverified'] for r in rows),
            'false_merges':sum(r['false_merge'] for r in rows),'false_splits':sum(r['false_split'] for r in rows),
            'unsafe_compatibility':sum(r['unsafe_compatibility'] for r in rows),
            'label_errors':sum(r['label_error'] for r in rows),
            'rows':rows,'limitation':'Candidate-text pair agreement is not independent benchmark accuracy or activation truth; disclose selection and any repeated templates.'}
