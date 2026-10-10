"""Read allocation memory counters without changing caches or processes."""
import json
import os
import argparse
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--detail", action="store_true")
    args = parser.parse_args()
    job = os.environ["SLURM_JOB_ID"]
    base = Path("/sys/fs/cgroup/memory/slurm") / f"uid_{os.getuid()}" / f"job_{job}"
    result = {"job_id": int(job), "node": os.uname().nodename,
              "checked_utc": datetime.now(timezone.utc).isoformat()}
    for name in ("memory.usage_in_bytes", "memory.limit_in_bytes", "memory.failcnt", "memory.kmem.usage_in_bytes"):
        path = base / name
        result[name] = int(path.read_text()) if path.exists() else None
    if args.detail:
        stat = base / "memory.stat"
        result["memory_stat"] = {name: int(value) for name, value in
                                 (line.split() for line in stat.read_text().splitlines())}
        result["steps"] = []
        for step in sorted(base.iterdir()):
            if not step.is_dir() or not step.name.startswith("step_"):
                continue
            row = {"step": step.name}
            for name in ("memory.usage_in_bytes", "memory.kmem.usage_in_bytes"):
                path = step / name
                row[name] = int(path.read_text()) if path.exists() else None
            result["steps"].append(row)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
