"""Prepare the reviewed TEST commands; --launch is for the coordinator only.

Default behavior prints metadata and commands without touching allocations.
Never reads candidate texts, loads models, submits allocations, or imports a pool.
"""

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess


GATE_SHA = "bbd2ef9597cac1f31b438e2faacbe27653382873f73042f4f494bfd073592d40"
PREFLIGHT_SHA = "65444bca622cbbeb4969448da516152b2e3cb396e56ab318a61130a5fcf1d3a8"
MASKS = ["17,19,21,23", "25,27,29,31", "17,19,21,23", "24,26,28,30"]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def prepare():
    runtime = json.loads(Path("configs/runtime.json").read_text())
    if [int(job["job_id"]) for job in runtime["gpu_allocations"]] != [25330001, 25330006, 25330007, 25417596]:
        raise ValueError("GPU job/shard assignment differs from the reviewed four allocations")
    gate_path = Path("configs/gates/test-full-grid-blind-v1.json")
    if digest(gate_path) != GATE_SHA:
        raise ValueError("Reviewed TEST gate changed")
    gate = json.loads(gate_path.read_text())
    if (gate["authorization_scope"] != "blind_generation_only"
            or gate["blind_test_generation_authorized"] is not True
            or gate["frozen_test_authorized"] is not False):
        raise ValueError("Not the reviewed generation-only capability")
    manifest = "configs/test-full-grid-blind-v1.json"
    if digest(manifest) != gate["manifest_sha256"]:
        raise ValueError("TEST manifest changed")
    bindings = dict(gate["source_sha256"])
    bindings.update({gate["prospective_policy_path"]: gate["prospective_policy_sha256"],
                     gate["pool_configuration_path"]: gate["pool_configuration_sha256"],
                     gate["validation_freeze_path"]: gate["validation_freeze_sha256"]})
    fresh = str(Path(runtime["paths"]["fast"]) / "activations/core-v1/fresh_manifest_v2.json")
    bindings[fresh] = gate["fresh_index_sha256"]
    for path, expected in bindings.items():
        if digest(path) != expected:
            raise ValueError("A reviewed source binding changed: " + path)
    durable = Path(runtime["paths"]["durable"])
    preflight_path = durable / "runs/test-blind-preparation-v1/validate-only-v1.json"
    if digest(preflight_path) != PREFLIGHT_SHA:
        raise ValueError("Four-shard preflight record changed")
    preflight = json.loads(preflight_path.read_text())
    # Reuse the exact successful four commands, removing only --validate-only.
    commands = []
    for index, row in enumerate(preflight["results"]):
        if row["exit_code"] != 0:
            raise ValueError("Preflight did not pass")
        if row["result"]["shard_index"] != index or row["result"]["target_n"] != 32:
            raise ValueError("Preflight shard order or sample count differs")
        command = [arg for arg in row["command"] if arg != "--validate-only"]
        commands.append(command)
    if len(commands) != 4:
        raise ValueError("Expected all four preflight commands")
    return runtime, bindings, commands


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--launch", action="store_true", help="Coordinator's explicit launch after handoff")
    args = parser.parse_args()
    runtime, bindings, commands = prepare()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    launches = []
    for index, (job, command) in enumerate(zip(runtime["gpu_allocations"], commands, strict=True)):
        log = Path(runtime["paths"]["logs"]) / f"test-blind-v1-{stamp}-shard-{index:03d}.log"
        full = ["srun", f"--jobid={job['job_id']}", "--overlap", "-N1", "-n1", "-c8",
                "--mem=64G", "--gres=gpu:h200:1", "--cpu-bind=none",
                f"--output={log}", f"--error={log}", "/usr/bin/taskset", "--cpu-list", MASKS[index],
                "/usr/bin/env", "OMP_NUM_THREADS=4", "OPENBLAS_NUM_THREADS=4"] + command
        launches.append({"shard_index": index, "job_id": job["job_id"], "cpu_mask": MASKS[index],
                         "log": str(log), "command": full})
    record = {"prepared_utc": stamp, "gate_sha256": GATE_SHA, "preflight_sha256": PREFLIGHT_SHA,
              "wrapper_sha256": digest(__file__), "source_bindings": bindings,
              "authorization_scope": "blind_generation_only", "launches": launches,
              "launched": False, "submits_allocations": False}
    if not args.launch:
        print(json.dumps(record, indent=2))
        return
    # Exact terminal counters only; no vectors, texts, or outcomes inspected.
    base = Path(runtime["paths"]["fast"]) / "vectors/validation-partitions-v1"
    plan = json.loads((base / "prepared/plan.json").read_text())
    for i in range(4):
        progress = json.loads((base / f"worker-{i}/a451cf49d28ac7447722/progress.json").read_text())
        if progress["status"] != "complete" or progress["new_vectors"] != plan["partitions"][i]["keys"]:
            raise RuntimeError("Validation AR is not terminal")
    for item in launches:
        job_id = item["job_id"]
        status = subprocess.run(["scontrol", "show", "job", str(job_id)], check=True,
                                capture_output=True, text=True).stdout
        if "JobState=RUNNING" not in status or f"UserId=${USER}({runtime['gpu_owner_uid']})" not in status:
            raise RuntimeError("Allocation ownership/state verification failed")
        probe = subprocess.run(["srun", f"--jobid={job_id}", "--overlap", "-N1", "-n1", "-c1",
                                "--mem=512M", "--gres=gpu:h200:1", "nvidia-smi",
                                "--query-compute-apps=pid", "--format=csv,noheader"],
                               check=True, capture_output=True, text=True)
        if probe.stdout.strip():
            raise RuntimeError("An allocation still has an active GPU process")
    for item in launches:
        item["srun_pid"] = subprocess.Popen(item["command"], start_new_session=True).pid
    record["launched"] = True
    destination = Path(runtime["paths"]["durable"]) / f"runs/test-blind-preparation-v1/launch-{stamp}.json"
    with destination.open("x") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
    destination.chmod(0o444)
    print(json.dumps({"launched": True, "record": str(destination), "launches": launches}))


if __name__ == "__main__":
    main()
