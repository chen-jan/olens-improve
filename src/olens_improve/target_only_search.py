"""Bounded verbatim search for ONE target and its fixed candidate dictionary.

Only the injected per-target subset score is visible here. There is no family,
answer, control activation, editor, encoder, or cross-target state in this API.
Fit budgets count unique canonical subsets, including parent and validation
fits. Each method must receive a fresh scorer for measured CPU comparisons.
"""
from dataclasses import dataclass
import math
from typing import Callable, Iterable

from .selection import Admissible, Bullet, Selection


METHODS = ("repeat_swap", "repeat_swap_then_prune_005", "bounded_prune_refill_005")


@dataclass(frozen=True)
class SearchConfig:
    method: str
    subset_fit_budget: int = 2048
    max_swap_steps: int = 8
    max_rounds: int = 2
    threshold: float = .005
    tolerance: float = 1e-8
    max_bullets: int = 4

    def __post_init__(self):
        if self.method not in METHODS:
            raise ValueError("Unknown target-only search method")
        for name in ("subset_fit_budget", "max_swap_steps", "max_rounds", "max_bullets"):
            if type(getattr(self, name)) is not int:
                raise ValueError(f"{name} must be an integer")
        if self.subset_fit_budget < 16:
            raise ValueError("Reserve at least 16 subset fits for parent pruning validation")
        if self.max_swap_steps < 0 or not 1 <= self.max_rounds <= 2 or not 0 <= self.max_bullets <= 4:
            raise ValueError("Invalid search bounds")
        if not math.isfinite(self.threshold) or self.threshold < 0 or not math.isfinite(self.tolerance) or self.tolerance < 0:
            raise ValueError("Threshold and tolerance must be finite and nonnegative")
        if self.method != "repeat_swap" and self.threshold != .005:
            raise ValueError("The named pruning methods freeze threshold at .005")


class _BudgetStop(Exception):
    pass


class SubsetFitMeter:
    """Canonical unordered subsets prevent duplicate NNLS fits and permutations.

    Lexical phrase-ID order is used only for the mathematical fit. Output bullets
    retain parent slot order; replacements occupy the removed bullet's slot.
    """
    def __init__(self, score: Callable[[tuple[str, ...]], float], limit: int):
        self.score = score
        self.limit = limit
        self.values: dict[tuple[str, ...], float] = {}
        self.requests = 0
        self.cache_hits = 0

    def fit(self, ids: Iterable[str], *, phase_limit: int | None = None) -> float:
        ids = tuple(ids)
        if len(set(ids)) != len(ids) or len(ids) > 4:
            raise ValueError("Fit requires a distinct subset of at most four bullets")
        key = tuple(sorted(ids))
        self.requests += 1
        if key in self.values:
            self.cache_hits += 1
            return self.values[key]
        if len(self.values) >= min(self.limit, self.limit if phase_limit is None else phase_limit):
            raise _BudgetStop
        value = float(self.score(key))
        if not math.isfinite(value):
            raise ValueError("Target subset objective must be finite")
        self.values[key] = value
        return value

    def summary(self):
        return {"subset_fit_budget": self.limit, "subset_fits": len(self.values),
                "score_requests": self.requests, "cache_hits": self.cache_hits,
                "accounting": "unique_canonical_subsets_including_parent_and_validation",
                "initial_parent_construction_fits": 0,
                "initial_parent_construction": "shared_cached_plain_pool_parent"}


@dataclass(frozen=True)
class SearchResult:
    selection: Selection
    budget: dict
    stop_flags: tuple[str, ...]
    leave_one_out: dict[str, float] | None
    parent_phrase_ids: tuple[str, ...]
    refined_phrase_ids: tuple[str, ...] | None = None


def search_target_only(pool: Iterable[Bullet], parent: Iterable[Bullet],
                       score: Callable[[tuple[str, ...]], float], *,
                       config: SearchConfig, admissible: Admissible | None = None) -> SearchResult:
    """Refine the cached plain pooled parent under an equal per-method fit cap.

    Ties within tolerance keep the first proposal: parent slot index, then pool
    order (which production freezes to earliest sample/position). Pruning removes
    the smallest leave-one-out gain, ties by earliest current slot. Eligibility
    requires every gain STRICTLY > .005 + tolerance, matching the released
    deletion boundary. Eligible FVE ties retain the earlier
    validated state. Accepted states are never revisited.

    Both swap variants validate the same initial fallback and reserve 14 fits
    for complete final pruning (a four-bullet powerset has 16 subsets; empty and
    full are already scored). They therefore have identical refined parents,
    including budget stops; standalone swaps leave the reserve unused. A partial
    scan keeps its best improving neighbor and marks that stop. Prune/refill first
    validates a pruned parent, then searches eligible swap/add neighbors for at
    most two rounds; every neighbor is pruned before comparison. It never fills
    a slot without an eligible FVE improvement and never restores an ineligible
    superset merely because its unpruned FVE is higher.
    """
    pool = tuple(pool)
    parent = tuple(parent)
    by_id = {b.phrase_id: b for b in pool}
    if len(by_id) != len(pool):
        raise ValueError("Candidate pool has repeated phrase IDs")
    if len({b.text for b in pool}) != len(pool):
        raise ValueError("Candidate pool must use exact-text representatives")
    if any(by_id.get(b.phrase_id) != b for b in parent):
        raise ValueError("Parent bullets must be unchanged members of this target's pool")

    def ids(state):
        return tuple(b.phrase_id for b in state)

    def key(state):
        return tuple(sorted(ids(state)))

    def allowed(state):
        return len(state) <= config.max_bullets and (admissible is None or admissible(state))

    if len(set(ids(parent))) != len(parent) or not allowed(parent):
        raise ValueError("Parent violates shared output caps or has duplicate bullets")
    meter = SubsetFitMeter(score, config.subset_fit_budget)
    trace: list[dict] = []
    flags: list[str] = []
    visited = {key(parent)}
    # Always metered, even when the score implementation knows the empty fit.
    meter.fit(())
    meter.fit(ids(parent))
    best_eligible = ()
    best_eligible_score = meter.fit(())
    best_loo: dict[str, float] = {}
    validated_gains: dict[tuple[str, ...], dict[str, float]] = {(): {}}
    swap_steps = 0
    refined_ids = None

    def flag(name):
        if name not in flags:
            flags.append(name)

    def remember(state, gains):
        nonlocal best_eligible, best_eligible_score, best_loo
        value = meter.fit(ids(state))
        validated_gains[key(state)] = gains
        if value > best_eligible_score + config.tolerance:
            best_eligible, best_eligible_score, best_loo = state, value, gains

    def prune(state, *, record=False, scope="neighbor"):
        while state:
            value = meter.fit(ids(state))
            proposals = []
            for index, b in enumerate(state):
                trial = state[:index] + state[index + 1:]
                proposals.append((value - meter.fit(ids(trial)), index, trial, b.phrase_id))
            gains = {pid: loss for loss, _, _, pid in proposals}
            loss, index, trial, pid = min(proposals, key=lambda row: (row[0], row[1]))
            if loss > config.threshold + config.tolerance:
                remember(state, gains)
                return state
            if record:
                trace.append({"action": "prune", "from": ids(state), "removed": pid,
                              "leave_one_out_gain": loss, "threshold": config.threshold,
                              "scope": scope})
            state = trial
        remember((), {})
        return ()

    def swaps(state, *, phase_limit=None, eligible=False):
        nonlocal swap_steps
        while swap_steps < config.max_swap_steps:
            current = meter.fit(ids(state))
            winner, best = None, current
            selected = set(ids(state))
            exhausted = False
            try:
                for index in range(len(state)):
                    for bullet in pool:
                        if bullet.phrase_id in selected:
                            continue
                        trial = state[:index] + (bullet,) + state[index + 1:]
                        if not allowed(trial) or key(trial) in visited:
                            continue
                        value = meter.fit(ids(trial), phase_limit=phase_limit)
                        if eligible:
                            trial = prune(trial)
                            value = meter.fit(ids(trial))
                            if key(trial) in visited:
                                continue
                        if value > best + config.tolerance:
                            winner, best = trial, value
            except _BudgetStop:
                exhausted = True
                flag("subset_fit_budget" if phase_limit is None else "swap_budget_reserved_for_pruning")
            if winner is None:
                if not exhausted:
                    flag("swap_local_optimum")
                return state
            trace.append({"action": "swap", "from": ids(state), "to": ids(winner),
                          "gain": best - current, "neighborhood_complete": not exhausted})
            state = winner
            visited.add(key(state))
            swap_steps += 1
            if exhausted:
                return state
        flag("max_swap_steps")
        return state

    if config.method == "repeat_swap":
        prune(parent, record=True, scope="cached_parent_fallback")
        final = swaps(parent, phase_limit=config.subset_fit_budget - 14)
        refined_ids = ids(final)
        final_loo = None
    elif config.method == "repeat_swap_then_prune_005":
        # Count the validated cached-parent fallback before spending on swaps.
        prune(parent, record=True, scope="cached_parent_fallback")
        refined = swaps(parent, phase_limit=config.subset_fit_budget - 14)
        refined_ids = ids(refined)
        # Reserved powerset allowance guarantees this full validation finishes.
        final = prune(refined, record=True, scope="final_refined_parent")
        final_loo = validated_gains[key(final)]
    else:
        current = prune(parent, record=True, scope="cached_parent_fallback")
        visited.add(key(current))
        for round_index in range(config.max_rounds):
            before = key(current)
            trace.append({"action": "round", "round": round_index + 1, "start": ids(current)})
            current = swaps(current, eligible=True)
            if "subset_fit_budget" in flags:
                break
            for _ in range(config.max_bullets):
                if len(current) >= config.max_bullets:
                    flag("bullet_cap")
                    break
                winner, best = None, meter.fit(ids(current))
                exhausted = False
                try:
                    selected = set(ids(current))
                    for bullet in pool:
                        if bullet.phrase_id in selected:
                            continue
                        trial = current + (bullet,)
                        if not allowed(trial) or key(trial) in visited:
                            continue
                        trial = prune(trial)
                        value = meter.fit(ids(trial))
                        if key(trial) not in visited and value > best + config.tolerance:
                            winner, best = trial, value
                except _BudgetStop:
                    exhausted = True
                    flag("subset_fit_budget")
                if winner is None:
                    if not exhausted:
                        flag("refill_local_optimum")
                    break
                trace.append({"action": "refill", "from": ids(current), "to": ids(winner),
                              "gain": best - meter.fit(ids(current)), "neighborhood_complete": not exhausted})
                current = winner
                visited.add(key(current))
                if exhausted:
                    break
            if "subset_fit_budget" in flags:
                break
            if key(current) == before:
                flag("round_fixed_point")
                break
        else:
            flag("max_rounds")
        final, final_loo = best_eligible, best_loo
    value = meter.fit(ids(final))
    trace.append({"action": "stop", "stop_flags": tuple(flags), "subset_fits": len(meter.values),
                  "selected": ids(final), "eligibility_validated": final_loo is not None})
    budget = meter.summary()
    if config.method != "bounded_prune_refill_005":
        budget.update({"swap_phase_fit_limit": config.subset_fit_budget - 14,
                       "final_pruning_fit_reserve": 14,
                       "standalone_swap_reserve_left_unused": config.method == "repeat_swap"})
    return SearchResult(Selection(config.method, final, value, tuple(trace)), budget,
                        tuple(flags), final_loo, ids(parent), refined_ids)
