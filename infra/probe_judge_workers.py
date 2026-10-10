"""Bounded proc/cgroup observation; no API calls, signals or tracing."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time


def process(pid):
    base = Path("/proc") / str(pid)
    try:
        stat = (base / "stat").read_text().split(") ", 1)[1].split()
        fields = dict(line.split(":", 1) for line in (base / "status").read_text().splitlines() if ":" in line)
        io = {k: int(v) for k, v in (line.split(":", 1) for line in (base / "io").read_text().splitlines())}
        return {"pid": pid, "state": stat[0], "wchan": (base / "wchan").read_text().strip(),
                "cpu_ticks": int(stat[11]) + int(stat[12]), "rss_kib": int(fields["VmRSS"].split()[0]),
                "threads": int(fields["Threads"]), "allowed_cpus": sorted(os.sched_getaffinity(pid)), "io": io}
    except (FileNotFoundError, ProcessLookupError):
        return {"pid": pid, "state": "absent"}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pids", nargs="+", type=int, required=True)
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    before = {pid: process(pid) for pid in args.pids}
    start = time.monotonic()
    time.sleep(2)
    elapsed = time.monotonic() - start
    after = [process(pid) for pid in args.pids]
    for row in after:
        old = before[row["pid"]]
        if "cpu_ticks" in old and "cpu_ticks" in row:
            row["process_cpu_percent_over_interval"] = 100 * (row["cpu_ticks"] - old["cpu_ticks"]) / os.sysconf("SC_CLK_TCK") / elapsed
            row["io_delta"] = {k: row["io"][k] - old["io"][k] for k in row["io"]}
    job = os.environ["SLURM_JOB_ID"]
    cg = Path("/sys/fs/cgroup/memory/slurm") / f"uid_{os.getuid()}" / f"job_{job}"
    memory = {k: int((cg / k).read_text()) for k in ("memory.usage_in_bytes", "memory.limit_in_bytes", "memory.failcnt", "memory.kmem.usage_in_bytes")}
    result = {"checked_utc": datetime.now(timezone.utc).isoformat(), "job_id": int(job),
              "node": os.uname().nodename, "interval_seconds": elapsed, "workers": after, "memory": memory,
              "limits": "One bounded observation; wchan is instantaneous. CPU percentage is process time over wall time, not node utilization or an attribution of API stalls."}
    if args.output:
        with args.output.open("x") as out:
            out.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
