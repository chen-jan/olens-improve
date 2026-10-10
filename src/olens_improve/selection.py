"""Verbatim selectors with an injected, fully refitted subset objective.

The scorer must accept an ordered tuple of phrase IDs and return a finite scalar
where larger is better. This module neither whitens vectors nor implements NNLS.
An output-token policy must be frozen after the length pilot and passed as
``admissible``; the universal structural limit is four bullets.
"""

from collections import defaultdict
from dataclasses import dataclass
import math
import re
from typing import Callable, Iterable


Score = Callable[[tuple[str, ...]], float]
Admissible = Callable[[tuple["Bullet", ...]], bool]
_MARKER = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+(?P<text>\S.*?)(?:\r?\n)?$")
PARSER_POLICY = "source_contiguous_dash_blocks_v1"
_DASH_BLOCK = re.compile(r"^[ \t]*-[ \t]+", re.MULTILINE)


@dataclass(frozen=True)
class Bullet:
    phrase_id: str
    text: str
    sample_id: str
    position: int
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True)
class Sample:
    sample_id: str
    index: int
    bullets: tuple[Bullet, ...]
    flags: tuple[str, ...] = ()
    parser_policy: str = PARSER_POLICY

    @property
    def parsing_uncertain(self):
        return any(flag in self.flags for flag in ("unmarked_text", "empty", "empty_bullet", "preamble_before_first_bullet"))


@dataclass(frozen=True)
class Selection:
    method: str
    bullets: tuple[Bullet, ...]
    score: float | None
    trace: tuple[dict, ...] = ()
    reason: str = "selected"

    @property
    def phrase_ids(self):
        return tuple(bullet.phrase_id for bullet in self.bullets)

    @property
    def text(self):
        return render_bullets(self.bullets)


def render_bullets(bullets):
    """Retain each block verbatim, adding a separator only where necessary."""
    output = ""
    for bullet in bullets:
        if output and not output.endswith("\n"):
            output += "\n"
        output += "- " + bullet.text
    return output


def output_admissible(token_count, max_output_tokens=256):
    """Frozen Qwen-token policy; counting must use the frozen target tokenizer."""
    if max_output_tokens < 1:
        raise ValueError("Output token budget must be positive")
    return lambda bullets: len(bullets) <= 4 and token_count(render_bullets(bullets)) <= max_output_tokens


def cap_sample(sample, token_count, max_output_tokens=256):
    """Drop complete trailing bullets until the shared token budget fits."""
    admissible = output_admissible(token_count, max_output_tokens)
    bullets = sample.bullets
    flags = list(sample.flags)
    while bullets and not admissible(bullets):
        bullets = bullets[:-1]
        if "output_token_capped" not in flags:
            flags.append("output_token_capped")
    return Sample(sample.sample_id, sample.index, bullets, tuple(flags), sample.parser_policy)


def parse_bullets(text: str, sample_id: str, index: int, max_bullets: int = 4,
                  *, token_count=None, max_output_tokens=256) -> Sample:
    """Primary dash blocks preserve all continuation bytes through the next marker.

    Preamble before the first marker is explicit uncertainty. Without token_count
    this is structural parsing only; production must apply cap_sample/the same
    output_admissible callback to every comparator and final selection.
    """
    _cap(max_bullets)
    markers = list(_DASH_BLOCK.finditer(text))
    flags, bullets = [], []
    if not markers:
        flags.append("empty")
        if text.strip():
            flags.append("preamble_before_first_bullet")
    elif text[:markers[0].start()].strip():
        flags.append("preamble_before_first_bullet")
    for position, marker in enumerate(markers):
        start = marker.end()
        end = markers[position + 1].start() if position + 1 < len(markers) else len(text)
        content = text[start:end]
        if not content.strip():
            flags.append("empty_bullet")
        bullets.append(Bullet(f"{sample_id}:{position}", content, sample_id, position, start, end))
    if len(bullets) > max_bullets:
        flags.append("deterministically_capped")
    sample = Sample(sample_id, index, tuple(bullets[:max_bullets]), tuple(dict.fromkeys(flags)))
    return cap_sample(sample, token_count, max_output_tokens) if token_count is not None else sample


def parse_strict_bullets(text: str, sample_id: str, index: int, max_bullets: int = 4,
                         *, token_count=None, max_output_tokens=256) -> Sample:
    """Parse marked single-line bullets; record uncertainty rather than rewriting.

    Content is the exact source span, excluding the marker and leading line
    whitespace. Unmarked continuations are flagged, never joined into invented
    text. Deterministic first-bullet capping is explicit in the flags.
    """
    _cap(max_bullets)
    bullets, flags, offset = [], [], 0
    for line in text.splitlines(keepends=True):
        match = _MARKER.match(line)
        if match:
            content = match.group("text")
            # Preserve the exact emitted content, including internal spacing.
            start = offset + match.start("text")
            end = offset + match.end("text")
            bullet = Bullet(f"{sample_id}:{len(bullets)}", content, sample_id, len(bullets), start, end)
            bullets.append(bullet)
        elif line.strip():
            flags.append("unmarked_text")
        offset += len(line)
    if not bullets:
        flags.append("empty")
    if len(bullets) > max_bullets:
        flags.append("deterministically_capped")
    sample = Sample(sample_id, index, tuple(bullets[:max_bullets]), tuple(dict.fromkeys(flags)), "strict_single_line_v1")
    return cap_sample(sample, token_count, max_output_tokens) if token_count is not None else sample


def _cap(limit):
    if not isinstance(limit, int) or not 0 <= limit <= 4:
        raise ValueError("max_bullets must be an integer between zero and four")


def _objective(score, bullets):
    value = float(score(tuple(bullet.phrase_id for bullet in bullets)))
    if not math.isfinite(value):
        raise ValueError("subset objective must be finite")
    return value


def _allowed(bullets, admissible):
    return len(bullets) <= 4 and (admissible is None or admissible(tuple(bullets)))


def _validated_pool(samples, prefix_n=None):
    """Require distinct records and zero-based indexes for a requested prefix."""
    records = list(samples)
    identifiers, indexes = set(), set()
    for sample in records:
        if sample.sample_id in identifiers:
            raise ValueError(f"duplicate sample ID: {sample.sample_id}")
        if not isinstance(sample.index, int) or isinstance(sample.index, bool) or sample.index < 0:
            raise ValueError("sample indexes must be nonnegative zero-based integers")
        if sample.index in indexes:
            raise ValueError(f"duplicate sample index: {sample.index}")
        identifiers.add(sample.sample_id)
        indexes.add(sample.index)
    if prefix_n is not None and not set(range(prefix_n)).issubset(indexes):
        raise ValueError(f"incomplete N={prefix_n} pool: require distinct indexes 0 through {prefix_n - 1}")
    return sorted(records, key=lambda sample: sample.index)


def best_of_n(samples: Iterable[Sample], n: int, score: Score, *, admissible: Admissible | None = None,
              tolerance: float = 0.0) -> Selection:
    """Choose among complete records indexed 0..N-1; earliest score ties win.

    Missing records and duplicate sample IDs/indexes are errors, never a smaller
    pool silently labeled N. Parsing-ineligible records remain explicit skips.
    """
    if not isinstance(n, int) or isinstance(n, bool) or not 1 <= n <= 32 or tolerance < 0:
        raise ValueError("n must be between one and 32 and tolerance nonnegative")
    ordered = _validated_pool(samples, prefix_n=n)
    winner, best, trace = None, -math.inf, []
    for sample in ordered[:n]:
        if sample.parsing_uncertain or not _allowed(sample.bullets, admissible):
            trace.append({"sample_id": sample.sample_id, "skipped": "uncertain_or_inadmissible"})
            continue
        value = _objective(score, sample.bullets)
        trace.append({"sample_id": sample.sample_id, "score": value})
        if winner is None or value > best + tolerance:
            winner, best = sample, value
    if winner is None:
        return Selection("best_of_n", (), None, tuple(trace), "no_eligible_complete_sample")
    return Selection("best_of_n", winner.bullets, best, tuple(trace))


def exact_consensus(samples: Iterable[Sample], *, min_support_fraction: float = 0.0,
                    max_bullets: int = 4, admissible: Admissible | None = None) -> Selection:
    """Count each exact-format-normalized claim at most once per source sample."""
    _cap(max_bullets)
    if not 0 <= min_support_fraction <= 1:
        raise ValueError("support fraction must be in [0, 1]")
    ordered = _validated_pool(samples)
    sample_ids = {sample.sample_id for sample in ordered}
    votes, representative, appearance = defaultdict(set), {}, {}
    for sample in ordered:
        if sample.parsing_uncertain:
            continue
        for bullet in sample.bullets:
            # Only whitespace normalization: preserve case, numbers, negation,
            # direction, and the verbatim output representative.
            key = " ".join(bullet.text.split())
            votes[key].add(sample.sample_id)
            if key not in representative:
                representative[key] = bullet
                appearance[key] = len(appearance)
    threshold = min_support_fraction * len(sample_ids)
    ranked = sorted(votes, key=lambda key: (-len(votes[key]), appearance[key]))
    selected, trace = [], []
    for key in ranked:
        bullet = representative[key]
        accepted = len(votes[key]) >= threshold and len(selected) < max_bullets and _allowed((*selected, bullet), admissible)
        trace.append({"phrase_id": bullet.phrase_id, "support": len(votes[key]),
                      "sample_denominator": len(sample_ids), "accepted": accepted})
        if accepted:
            selected.append(bullet)
    return Selection("exact_consensus", tuple(selected), None, tuple(trace))


def prune_leave_one_out(bullets: Iterable[Bullet], score: Score, *, maximum_loss: float,
                       min_bullets: int = 0, tolerance: float = 1e-8) -> Selection:
    """Remove the earliest least-contributing bullet, refitting after each deletion."""
    selected = tuple(bullets)
    _cap(len(selected))
    if maximum_loss < 0 or tolerance < 0 or not 0 <= min_bullets <= len(selected):
        raise ValueError("invalid pruning limits")
    current, trace = _objective(score, selected), []
    while len(selected) > min_bullets:
        candidates = []
        for index, bullet in enumerate(selected):
            trial = selected[:index] + selected[index + 1:]
            trial_score = _objective(score, trial)
            candidates.append((current - trial_score, index, trial_score, trial))
        loss, index, trial_score, trial = min(candidates, key=lambda row: (row[0], row[1]))
        accepted = loss <= maximum_loss + tolerance
        trace.append({"removed_id": selected[index].phrase_id, "loss": loss, "accepted": accepted})
        if not accepted:
            break
        selected, current = trial, trial_score
    return Selection("prune_leave_one_out", selected, current, tuple(trace))


def greedy_pool(bullets: Iterable[Bullet], score: Score, *, max_bullets: int = 4,
                minimum_gain: float = 0.0, swap_passes: int = 0, tolerance: float = 1e-8,
                eligible_ids: set[str] | None = None, admissible: Admissible | None = None,
                complete_samples: Iterable[Sample] = ()) -> Selection:
    """Fully refit every proposed addition/swap; fallback respects all constraints."""
    _cap(max_bullets)
    if minimum_gain < 0 or swap_passes < 0 or tolerance < 0:
        raise ValueError("gain, swap passes, and tolerance must be nonnegative")
    pool, seen = [], set()
    for bullet in bullets:
        if bullet.phrase_id in seen:
            continue
        seen.add(bullet.phrase_id)
        if eligible_ids is None or bullet.phrase_id in eligible_ids:
            pool.append(bullet)
    selected, trace = (), []
    current = _objective(score, selected)
    for _ in range(max_bullets):
        winner, best = None, -math.inf
        selected_ids = {bullet.phrase_id for bullet in selected}
        for bullet in pool:
            if bullet.phrase_id in selected_ids or not _allowed((*selected, bullet), admissible):
                continue
            trial = selected + (bullet,)
            value = _objective(score, trial)
            if winner is None or value > best + tolerance:
                winner, best = trial, value
        if winner is None or best - current <= minimum_gain + tolerance:
            trace.append({"action": "stop", "best_gain": None if winner is None else best - current})
            break
        trace.append({"action": "add", "phrase_id": winner[-1].phrase_id, "gain": best - current})
        selected, current = winner, best
    for _ in range(swap_passes):
        winner, best = None, current
        selected_ids = {bullet.phrase_id for bullet in selected}
        for index in range(len(selected)):
            for bullet in pool:
                if bullet.phrase_id in selected_ids:
                    continue
                trial = selected[:index] + (bullet,) + selected[index + 1:]
                if not _allowed(trial, admissible):
                    continue
                value = _objective(score, trial)
                if value > best + tolerance:
                    winner, best = trial, value
        if winner is None:
            break
        trace.append({"action": "swap", "from": tuple(b.phrase_id for b in selected),
                      "to": tuple(b.phrase_id for b in winner), "gain": best - current})
        selected, current = winner, best
    allowed_ids = {bullet.phrase_id for bullet in pool}
    for sample in sorted(complete_samples, key=lambda sample: sample.index):
        if sample.parsing_uncertain or len(sample.bullets) > max_bullets:
            continue
        if not all(bullet.phrase_id in allowed_ids for bullet in sample.bullets) or not _allowed(sample.bullets, admissible):
            continue
        value = _objective(score, sample.bullets)
        if value > current + tolerance:
            trace.append({"action": "complete_sample_fallback", "sample_id": sample.sample_id, "gain": value - current})
            selected, current = sample.bullets, value
    return Selection("greedy_pool", selected, current, tuple(trace))
