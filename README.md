# Improving the released Oracle Lens at inference time

The project tests whether inference-time selection and composition can improve the frozen released Oracle Lens. Maximum quality is the priority: measure recovery/error tradeoffs, explore sampling saturation, and explain any combined method with controlled comparisons.

The execution target is approximately 20 hours from the actual start, subject to prerequisite checks and measured throughput. A dashboard begins after the first validated pilot and updates after scored experiments and trace reviews: key findings first, then charts and method tabs. Final delivery includes the report, per-family results, uncertainty, costs, and inspectable examples.

Read [the execution plan](docs/PLAN.md) and [detailed method specifications](docs/METHODS.md) before continuing. Record each experiment using [the experiment template](docs/experiments/TEMPLATE.md), and follow [AGENTS.md](AGENTS.md) for cluster and storage rules.

Current state: autonomous execution started on 2026-10-10 at 01:25:36 UTC. Prerequisite checks and implementation are in progress. See [the current status](docs/STATUS.md) for measured results, spending, active jobs, and recovery instructions. Local commits only; the user handles pushing.
