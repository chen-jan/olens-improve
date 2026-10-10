"""One-shot allocation/resource snapshots; never submit or cancel jobs."""

import argparse
import copy
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sqlite3
import sys
import time
from zoneinfo import ZoneInfo

BUDGET_READ_QUERY_SECONDS = 2.0


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
    per_root = {str(root): {"logical_bytes": 0, "allocated_bytes": 0, "files": 0, "complete": False}
                for root in roots}
    for root in roots:
        root_counts = per_root[str(root)]
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
                root_counts["logical_bytes"] += stat.st_size
                root_counts["allocated_bytes"] += stat.st_blocks * 512
                root_counts["files"] += 1
                if files >= maximum_files:
                    return {"logical_bytes": logical, "allocated_bytes": allocated,
                            "files": files, "complete": False, "limit": maximum_files, "per_root": per_root}
        root_counts["complete"] = True
    return {"logical_bytes": logical, "allocated_bytes": allocated, "files": files,
            "complete": True, "per_root": per_root}


def budget_snapshot(path):
    if not path.exists():
        return {"status": "not_initialized", "path": str(path)}
    expired = False
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=2,
                                    isolation_level=None)) as database:
            deadline = time.monotonic() + BUDGET_READ_QUERY_SECONDS

            def query_deadline():
                nonlocal expired
                expired = time.monotonic() >= deadline
                return int(expired)

            # busy_timeout limits lock waiting, not query execution. SQLite's
            # cooperative VM callback also bounds work in this read snapshot.
            database.set_progress_handler(query_deadline, 1000)
            try:
                database.execute("BEGIN")
                with closing(database.execute("SELECT status,COUNT(*),COALESCE(SUM(reserved),0),COALESCE(SUM(actual),0) FROM attempts GROUP BY status")) as cursor:
                    rows = cursor.fetchall()
                with closing(database.execute("SELECT key,value FROM config")) as cursor:
                    config = dict(cursor)
            finally:
                # Cleanup must remain executable after the deadline has passed.
                database.set_progress_handler(None, 0)
                # This is a read snapshot: end it before resource probes/output.
                if database.in_transaction:
                    database.execute("ROLLBACK")
        statuses = {row[0]: {"count": row[1], "reserved_usd": row[2] / 1e9, "actual_usd": row[3] / 1e9} for row in rows}
        actual = statuses.get("settled", {}).get("actual_usd", 0)
        reserved = sum(statuses.get(key, {}).get("reserved_usd", 0) for key in ("reserved", "unknown"))
        return {"status": "observed_read_only", "actual_usd": actual, "reserved_usd": reserved,
                "unknown_usd": statuses.get("unknown", {}).get("reserved_usd", 0),
                "committed_usd": actual + reserved, "hard_usd": config["hard"] / 1e9,
                "target_usd": config["target"] / 1e9, "attempt_counts": {key: value["count"] for key, value in statuses.items()}}
    except sqlite3.Error as error:
        return {"status": "temporarily_unavailable",
                "error": "Budget read exceeded query deadline" if expired else str(error),
                "query_deadline_seconds": BUDGET_READ_QUERY_SECONDS,
                "query_deadline_exceeded": expired}


def cpu_memory_alerts(job_id, counters):
    usage, limit = counters.get("memory.usage_in_bytes"), counters.get("memory.limit_in_bytes")
    if usage is None or not limit:
        return [f"CPU allocation {job_id} memory headroom is unavailable"]
    alerts = []
    if usage >= .9 * limit:
        alerts.append(f"CPU allocation {job_id} memory charge exceeds 90% of its cgroup limit")
    if counters.get("memory.failcnt"):
        alerts.append(f"CPU allocation {job_id} has recorded memory-limit allocation failures")
    return alerts


def merge_runtime_observations(original, observed, latest):
    """Keep concurrent configuration edits; apply only unchanged observation fields."""
    merged = copy.deepcopy(latest)
    fields = ("state", "reason", "node", "last_check_utc", "end_utc", "progress")
    for category in ("gpu_allocations", "preemptable_allocations", "additional_cpu_allocations"):
        before = {job["job_id"]: job for job in original.get(category, [])}
        after = {job["job_id"]: job for job in observed.get(category, [])}
        for job in merged.get(category, []):
            key = job["job_id"]
            if key not in before or key not in after:
                continue
            for field in fields:
                if (field in after[key] and after[key].get(field) != before[key].get(field)
                        and job.get(field) == before[key].get(field)):
                    job[field] = after[key][field]
    merged.setdefault("watcher", {})["last_check_utc"] = observed["watcher"]["last_check_utc"]
    return merged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default="configs/runtime.json")
    args = parser.parse_args()
    runtime = json.loads(Path(args.runtime).read_text())
    original_runtime = copy.deepcopy(runtime)
    now = datetime.now(timezone.utc)
    jobs = runtime["gpu_allocations"] + runtime.get("preemptable_allocations", []) + runtime.get("additional_cpu_allocations", [])
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
        fields = dict(re.findall(r"(?:^|\s)([A-Za-z][A-Za-z0-9_]*)=(\S*)", text))
        detail["state"] = fields.get("JobState")
        detail["reason"] = fields.get("Reason")
        diagnostic = job in runtime.get("preemptable_allocations", [])
        cpu_allocation = job in runtime.get("additional_cpu_allocations", [])
        if cpu_allocation:
            job.update(state=fields.get("JobState"), reason=fields.get("Reason"),
                       node=fields.get("NodeList") or None, last_check_utc=now.isoformat())
            detail["requested_utc"] = job["requested_utc"]
            detail["purpose"] = job.get("purpose")
            if fields.get("JobState") == "PENDING":
                detail["pending_seconds"] = (now-datetime.fromisoformat(job["requested_utc"].replace("Z", "+00:00"))).total_seconds()
        if (diagnostic or cpu_allocation) and job.get('intentionally_released_utc'):
            detail['intentional_release'] = {'utc':job['intentionally_released_utc'], 'reason':job.get('release_reason')}
            if fields.get('JobState') != 'RUNNING':
                detail['released_as_planned'] = True
                job.update(state=fields.get('JobState') or 'RELEASED_RECORD_UNAVAILABLE', last_check_utc=now.isoformat())
                continue
            release_age=(now-datetime.fromisoformat(job['intentionally_released_utc'].replace('Z','+00:00'))).total_seconds()
            if release_age > 120:
                snapshot['alerts'].append(f'Job {key} still RUNNING after planned release; verify cancellation')
        if diagnostic:
            previous_state = job.get("state")
            job.update(state=fields.get("JobState"), reason=fields.get("Reason"),
                       node=fields.get("NodeList") or None, last_check_utc=now.isoformat())
            detail["requested_utc"] = job["requested_utc"]
            if fields.get("JobState") == "PENDING":
                pending = (now-datetime.fromisoformat(job["requested_utc"].replace("Z", "+00:00"))).total_seconds()
                detail["pending_seconds"] = pending
                if pending > job.get("fallback_after_pending_seconds", 720):
                    snapshot["alerts"].append(f"Diagnostic job {key} pending over12 minutes; consider an H100 replacement after memory-fit review")
            elif fields.get("JobState") == "RUNNING" and previous_state != "RUNNING":
                job["progress"] = "Allocated; workload handoff/status must be recorded separately"
            detail["progress"] = job.get("progress")
        if fields.get("JobState") != "RUNNING" and not ((diagnostic or cpu_allocation) and fields.get("JobState") == "PENDING"):
            snapshot["alerts"].append(f"Job {key} is not confirmed RUNNING")
        if f"UserId=${USER}({runtime['gpu_owner_uid']})" not in text:
            snapshot["alerts"].append(f"Job {key} ownership needs verification")
        live_end = fields.get("EndTime")
        if live_end and live_end != "Unknown":
            job["end_utc"] = datetime.fromisoformat(live_end).replace(tzinfo=ZoneInfo("America/New_York")).astimezone(timezone.utc).isoformat()
        if job.get("end_utc"):
            remaining = (datetime.fromisoformat(job["end_utc"].replace("Z", "+00:00")) - now).total_seconds()
            detail["configured_remaining_seconds"] = remaining
            warning_seconds = job.get("warn_when_remaining_seconds", 7200)
            if remaining < warning_seconds:
                snapshot["alerts"].append(f"Job {key} has less than {warning_seconds / 60:g} minutes remaining")
    claims = Path(runtime["paths"]["fast"]) / "claims"
    snapshot["claim_files"] = []
    for path in sorted(claims.glob("*.json"))[:1000]:
        snapshot["claim_files"].append({"name": path.name, "age_seconds": now.timestamp() - path.stat().st_mtime})
    readouts = Path(runtime["paths"]["durable"]) / "readouts/shared-global-v1"
    snapshot["generation_progress"] = []
    for path in sorted(readouts.glob("*.status.json"))[:100]:
        snapshot["generation_progress"].append(json.loads(path.read_text()))
    running = [job for job in jobs if "gpu" in job and snapshot["jobs"][str(job["job_id"])].get("state") == "RUNNING"]
    def gpu_status(job):
        return str(job["job_id"]), command(["srun", f"--jobid={job['job_id']}", "--overlap", "--mem=512M", "--cpu-bind=none", "-N1", "-n1", "-c1",
            f"--gres=gpu:{job['gpu']}:1", "nvidia-smi", "--query-gpu=name,memory.used,utilization.gpu", "--format=csv,noheader"])
    with ThreadPoolExecutor(max_workers=5) as pool:
        snapshot["gpu_status"] = dict(pool.map(gpu_status, running))
    for key, result in snapshot["gpu_status"].items():
        if result.get("returncode") != 0:
            snapshot["alerts"].append(f"GPU observation for job {key} unavailable; see recorded probe error")
    snapshot["additional_cpu_status"] = {}
    for job in runtime.get("additional_cpu_allocations", []):
        key = str(job["job_id"])
        if snapshot["jobs"][key].get("state") != "RUNNING":
            continue
        probe = command(["srun", f"--jobid={key}", "--overlap", "-N1", "-n1", "-c1", "--mem=512M", "--cpu-bind=none",
                         sys.executable, str(Path(__file__).with_name("probe_cpu_cgroup.py"))])
        snapshot["additional_cpu_status"][key] = probe
        if probe.get("returncode") != 0:
            snapshot["alerts"].append(f"CPU cgroup observation for job {key} unavailable")
            continue
        try:
            counters = json.loads(probe["stdout"])
            probe["counters"] = counters
            snapshot["alerts"].extend(cpu_memory_alerts(key, counters))
        except (ValueError, KeyError):
            snapshot["alerts"].append(f"CPU cgroup observation for job {key} could not be parsed")
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
    runtime = merge_runtime_observations(original_runtime, runtime, json.loads(runtime_path.read_text()))
    runtime_temporary = runtime_path.with_suffix(".tmp")
    runtime_temporary.write_text(json.dumps(runtime, indent=2) + "\n")
    runtime_temporary.replace(runtime_path)
    print(json.dumps({"checked_utc": snapshot["checked_utc"], "jobs": list(snapshot["jobs"]),
                      "storage": storage, "alerts": snapshot["alerts"], "snapshot": str(destination / "latest.json")}))


if __name__ == "__main__":
    main()
