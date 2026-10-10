"""Coordinator capabilities; blind sampling never authorizes outcome analysis."""


def require_gate_capability(gate, capability="analysis"):
    if capability not in {"generation", "analysis"}:
        raise ValueError("Unknown required stage capability")
    scope = gate.get("authorization_scope")
    # Previously issued DEV/fixture gates authorized both operations.
    if scope not in {None, "analysis", "blind_generation_only"}:
        raise ValueError("Unknown coordinator authorization scope")
    if scope == "blind_generation_only" and capability != "generation":
        raise ValueError("Blind-generation-only gate does not authorize analysis, export or AR")


def require_record_analysis(row, cells=None, captures=None):
    """Consume unchanged blind records only under a separately verified analysis gate."""
    scope = row.get("generation_authorization_scope")
    if scope not in {None, "analysis", "blind_generation_only"}:
        raise ValueError("Unknown source generation authorization scope")
    if scope != "blind_generation_only":
        return
    cid = row["cell_id"]
    if cells is None or captures is None or cid not in cells:
        raise ValueError("Blind-generated records require a separately verified analysis gate")
    if any(row[k] != cells[cid][k] for k in ("family", "item_id", "layer", "position")):
        raise ValueError("Blind record identity differs from analysis cohort")
    if row["activation_sha256"] != captures[cid]["activation_sha256"]:
        raise ValueError("Blind record activation differs from analysis gate")
