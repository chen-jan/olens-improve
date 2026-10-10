"""Pure cache-key and committed-journal parsing helpers."""
import hashlib
import json


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def vector_key(contract_sha256, tag_ids, token_ids):
    return digest({"contract_sha256": contract_sha256, "tag_ids": tag_ids, "token_ids": token_ids})


def input_records(body):
    """Read standalone rows or atomic generation envelopes; reject malformed rows.

    A trailing uncommitted line is not a completed record; omit it during streaming.
    Its bytes remain in the input snapshot hash, and the next pass will reconsider it.
    """
    lines = body.decode().splitlines(keepends=True)
    for line_number, line in enumerate(lines):
        if not line.strip():
            continue
        if line_number == len(lines)-1 and not line.endswith("\n"):
            continue
        row = json.loads(line)
        records = row.get("records", [row])
        if not isinstance(records, list):
            raise ValueError("Journal records must be a list")
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Candidate record must be an object")
            yield record


def committed_prefix(body):
    """Return the complete-line byte boundary of one append-only journal read."""
    end = body.rfind(b'\n') + 1
    return body[:end]


def complete_cells(records, allowed, completed=(), n=32):
    """Freeze whole contiguous sample pools; reject duplicates/conflicting targets."""
    from collections import defaultdict
    cells=defaultdict(dict)
    for row in records:
        cell_id=row['cell_id'];index=row['sample_index']
        if cell_id not in allowed or not isinstance(index,int) or isinstance(index,bool) or not 0<=index<n:
            raise ValueError('Off-manifest or invalid streaming sample')
        if index in cells[cell_id]:
            raise ValueError('Duplicate streaming sample')
        cells[cell_id][index]=row
    result=[]
    for cell_id in sorted(cells):
        values=cells[cell_id]
        if set(values)!=set(range(len(values))):raise ValueError('Noncontiguous streaming pool')
        if cell_id in completed or len(values)!=n:continue
        hashes={r['activation_sha256'] for r in values.values()}
        if len(hashes)!=1:raise ValueError('Streaming activation provenance changed')
        result.extend(values[index] for index in range(n))
    return result
