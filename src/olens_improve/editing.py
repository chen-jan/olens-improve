"""Candidate-only editing provenance checks; no target evidence or model calls."""
from .selection import parse_bullets


def validate_lineage(row, history, round_number):
    if len(row['parents'])>2:
        raise ValueError('Editing beam exceeds two parents')
    history_ids=[item['candidate_id'] for item in history]
    if len(history_ids)!=len(set(history_ids)):
        raise ValueError('Duplicate history candidate ID')
    parent_ids=[item['candidate_id'] for item in row['parents']]
    if len(parent_ids)!=len(set(parent_ids)):
        raise ValueError('Duplicate parent candidate ID')
    known={item['candidate_id']:item['text'] for item in history}
    for parent in row['parents']:
        key=parent['candidate_id']
        if round_number==2 and key not in known:
            raise ValueError('Round-two parent absent from complete round-one history')
        if key in known and known[key]!=parent['text']:
            raise ValueError('Parent text changed under an existing ID')
    if len(row['editing']['proposals'])>4:
        raise ValueError('More than four aggregate proposals per round')
    seen=set(history_ids)|set(parent_ids)
    for proposal in row['editing']['proposals']:
        if proposal['candidate_id'] in seen:
            raise ValueError('Proposal reused a candidate ID')
        if proposal['parent_candidate_id'] not in parent_ids:
            raise ValueError('Proposal points outside its supplied candidate-only parents')
        seen.add(proposal['candidate_id'])


def validated_sample(text, candidate_id, token_count):
    sample=parse_bullets(text,candidate_id,0,token_count=token_count,max_output_tokens=256)
    # Explicit abstention is valid. Nonempty unmarked prose is not an empty edit.
    if not text.strip():
        return sample
    if token_count(text)>256 or sample.parsing_uncertain or any(flag in sample.flags for flag in
            ('deterministically_capped','output_token_capped','empty_bullet')):
        raise ValueError('Editing candidate violates frozen source/cap policy')
    return sample
