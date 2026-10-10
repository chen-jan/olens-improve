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
