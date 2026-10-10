"""One-shot allocation/resource snapshots; never submit or cancel jobs."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sqlite3


def command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=30)
        return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"error": str(error)}


def project_storage(roots, maximum_files=50000):
    """Bounded inspection of project-owned trees only; never follow symlinks."""
    logical = allocated = files = 0
    seen = set()
    for root in roots:
        for directory, _, names in os.walk(root, followlinks=False):
            for name in names:
                path = Path(directory) / name
                if path.is_symlink():
                    continue
                try:
                    stat = path.stat()
                except FileNotFoundError:
                    continue  # Concurrent cleanup is normal; the next check refreshes it.
                key = (stat.st_dev, stat.st_ino)
                if key in seen:
                    continue
                seen.add(key)
                logical += stat.st_size
                allocated += stat.st_blocks * 512
                files += 1
                if files >= maximum_files:
                    return {"logical_bytes": logical, "allocated_bytes": allocated,
                            "files": files, "complete": False, "limit": maximum_files}
    return {"logical_bytes": logical, "allocated_bytes": allocated, "files": files, "complete": True}


def budget_snapshot(path):
    if not path.exists():
        return {"status": "not_initialized", "path": str(path)}
    try:
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2) as database:
            database.execute("BEGIN")
            rows = database.execute("SELECT status,COUNT(*),COALESCE(SUM(reserved),0),COALESCE(SUM(actual),0) FROM attempts GROUP BY status").fetchall()
            config = dict(database.execute("SELECT key,value FROM config"))
        statuses = {row[0]: {"count": row[1], "reserved_usd": row[2] / 1e9, "actual_usd": row[3] / 1e9} for row in rows}
        actual = statuses.get("settled", {}).get("actual_usd", 0)
        reserved = sum(statuses.get(key, {}).get("reserved_usd", 0) for key in ("reserved", "unknown"))
        return {"status": "observed_read_only", "actual_usd": actual, "reserved_usd": reserved,
                "unknown_usd": statuses.get("unknown", {}).get("reserved_usd", 0),
                "committed_usd": actual + reserved, "hard_usd": config["hard"] / 1e9,
                "target_usd": config["target"] / 1e9, "attempt_counts": {key: value["count"] for key, value in statuses.items()}}
    except sqlite3.Error as error:
        return {"status": "temporarily_unavailable", "error": str(error)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default="configs/runtime.json")
    args = parser.parse_args()
    runtime = json.loads(Path(args.runtime).read_text())
    now = datetime.now(timezone.utc)
    jobs = runtime["gpu_allocations"] + runtime.get("preemptable_allocations", [])
    snapshot = {
        "checked_utc": now.isoformat(),
        "watcher": runtime["watcher"]["agent"],
        "jobs": {},
        "personal_quota": (Path.home() / "orcd/.quota").read_text(),
        "group_quota_status": runtime["storage_group_quota_status"],
        "alerts": [],
    }
    snapshot["project_storage"] = project_storage([runtime["paths"]["fast"], runtime["paths"]["durable"]])
    snapshot["budget"] = budget_snapshot(Path(runtime["paths"]["durable"]) / "budget/ledger.sqlite3")
    budget = snapshot["budget"]
    if budget.get("committed_usd", 0) > budget.get("hard_usd", float("inf")):
        snapshot["alerts"].append("Observed budget exceeds the hard cap; stop paid dispatch and reconcile")
    storage = snapshot["project_storage"]
    if not storage["complete"]:
        snapshot["alerts"].append("Project storage scan reached its file-count bound; byte count is partial")
    if storage["logical_bytes"] >= .9 * runtime["storage_authorized_aggregate_bytes"]:
        snapshot["alerts"].append("Project logical storage reached 90% of aggregate authorization")
    for job in jobs:
        key = str(job["job_id"])
        snapshot["jobs"][key] = command(["scontrol", "show", "job", key])
        detail = snapshot["jobs"][key]
        text = detail.get("stdout", "")
        if "JobState=RUNNING" not in text:
            snapshot["alerts"].append(f"Job {key} is not confirmed RUNNING")
        if f"UserId=${USER}({runtime['gpu_owner_uid']})" not in text:
            snapshot["alerts"].append(f"Job {key} ownership needs verification")
        if job.get("end_utc"):
            remaining = (datetime.fromisoformat(job["end_utc"].replace("Z", "+00:00")) - now).total_seconds()
            detail["configured_remaining_seconds"] = remaining
            if remaining < 7200:
                snapshot["alerts"].append(f"Job {key} has less than two hours remaining")
    claims = Path(runtime["paths"]["fast"]) / "claims"
    snapshot["claim_files"] = []
    for path in sorted(claims.glob("*.json"))[:1000]:
        snapshot["claim_files"].append({"name": path.name, "age_seconds": now.timestamp() - path.stat().st_mtime})
    destination = Path(runtime["paths"]["fast"]) / "watcher"
    destination.mkdir(exist_ok=True)
    payload = json.dumps(snapshot, indent=2) + "\n"
    temporary = destination / "latest.tmp"
    temporary.write_text(payload)
    temporary.replace(destination / "latest.json")
    with (destination / "history.jsonl").open("a") as stream:
        stream.write(json.dumps(snapshot) + "\n")
    runtime["watcher"]["last_check_utc"] = now.isoformat()
    runtime_path = Path(args.runtime)
    runtime_temporary = runtime_path.with_suffix(".tmp")
    runtime_temporary.write_text(json.dumps(runtime, indent=2) + "\n")
    runtime_temporary.replace(runtime_path)
    print(json.dumps({"checked_utc": snapshot["checked_utc"], "jobs": list(snapshot["jobs"]),
                      "storage": storage, "alerts": snapshot["alerts"], "snapshot": str(destination / "latest.json")}))


if __name__ == "__main__":
    main()
