"""Launch stable four-way workers inside existing allocations; never submit jobs."""

import argparse
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime", default="configs/runtime.json")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--gate", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--fresh-index", required=True)
    parser.add_argument("--import-pool", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--capture-version", required=True)
    parser.add_argument("--n", type=int, default=32)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    runtime = json.loads(Path(args.runtime).read_text())
    jobs = runtime["gpu_allocations"]
    if len(jobs) != 4:
        raise ValueError("This runner requires the frozen four existing main allocations")
    common = [runtime["paths"]["python"], "scripts/generate_samples.py", "--runtime", args.runtime,
        "--manifest", args.manifest, "--gate", args.gate, "--adapter", args.adapter,
        "--fresh-index", args.fresh_index, "--import-pool", args.import_pool,
        "--output", args.output, "--capture-version", args.capture_version, "--n", str(args.n),
        "--batch-size", "32", "--cells-per-batch", "4", "--maximum-batch-sequences", "128"]
    for index in range(4):
        subprocess.run(common + ["--shard-index", str(index), "--validate-only"], check=True)
    if args.dry_run:
        return
    # Recheck owned/running allocations immediately before touching them.
    for job in jobs:
        result = subprocess.run(["scontrol", "show", "job", str(job["job_id"])], check=True, capture_output=True, text=True)
        if "JobState=RUNNING" not in result.stdout or f"UserId=${USER}({runtime['gpu_owner_uid']})" not in result.stdout:
            raise RuntimeError("Allocation ownership/state verification failed")
        probe = subprocess.run(["srun", f"--jobid={job['job_id']}", "--overlap", "-N1", "-n1", "-c1",
            "--gres=gpu:h200:1", "nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader"],
            check=True, capture_output=True, text=True)
        if probe.stdout.strip():
            raise RuntimeError(f"GPU job{job['job_id']} still has an active compute process; wait for handoff")
    launches = []
    for index, job in enumerate(jobs):
        log = Path(runtime["paths"]["logs"]) / f"pilot-n{args.n}-shard-{index:03d}.log"
        command = ["srun", f"--jobid={job['job_id']}", "--overlap", "-N1", "-n1", "-c8", "--gres=gpu:h200:1",
            f"--output={log}", f"--error={log}"] + common + ["--shard-index", str(index)]
        process = subprocess.Popen(command, start_new_session=True)
        launches.append({"shard_index": index, "job_id": job["job_id"], "srun_pid": process.pid,
                         "log": str(log), "command": command})
    destination = Path(runtime["paths"]["fast"]) / "watcher/latest_launch.json"
    destination.write_text(json.dumps({"manifest": args.manifest, "gate": args.gate,
        "output": args.output, "launches": launches}, indent=2) + "\n")
    print(json.dumps({"launched": launches, "submission": False}))


if __name__ == "__main__":
    main()
