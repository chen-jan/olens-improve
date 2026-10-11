# Method specifications for the frozen Oracle Lens

**Next phase:** [EXPANSION_PLAN.md](EXPANSION_PLAN.md) specifies the broader four-family comparison, pooling length controls and a single preemptable H200. It is planning-only until the user starts it. All other-reader experiments are deferred. The completion and freeze statements below describe the original study; new method versions will be reported separately as exploratory.

Status: scientific judging, statistical reporting and systematic trace reviews are complete for the twelve frozen methods across DEV, VAL and TEST. The six development sampling prefixes, shared 189-cell pilots and bounded helper/independent-reader diagnostics are also complete within their declared scopes. The whole-469-item aggregation is descriptive; the 268-item TEST comparison remains the primary held-out evidence. Final report/dashboard attachments and slides are published; see [delivery](DELIVERY.md). Procedures below include unrun proposed variants as well as completed work; experiment records and [the delivery checklist](DELIVERY_CHECKLIST.md) state which variants were actually measured. [STATUS.md](STATUS.md) records current handoff; [PLAN.md](PLAN.md) preserves the frozen contracts and historical execution target. No method setting is changed after outcome access.

O-lens means Oracle Lens, AR means activation reconstructor, FVE means fraction of variance explained, and NNLS means nonnegative least squares. The released O-lens and matched AR stay frozen. No core method changes the target model, accesses additional target cells, or trains a new representation; the optional separate layer-42 diagnostic below is outside that protocol.

## Shared data flow and scoring

For each approved item/layer/position, reuse or capture the same base-model activation. Start with tiny N=1/2 timing and instrument validation, then expand ordered nested prefixes through N=4,8,16 and at most **32 total O-lens samples per cell, shared across all methods** under the development expansion rules. No fresh pool per method or automatic 64/128 extension: the user must revisit the cap first. Record exact text, seed, batch order, token count, truncation, and runtime. Numerical defaults below are pilot proposals, revisable on development and frozen before validation/test; they do not require a full cross-product.

Candidates, consensus votes, and selected evidence stay within one cell: one item, layer, and position. Independent rows processed in a batch are not joint input. Never feed cross-cell text summaries to selectors. Exact-text vector/helper caches may be global when their keys match, but cached computations do not transfer support votes between cells. Preserve the benchmark's official item-level aggregation after independent cell readouts.

Keep the raw N=1 baseline unchanged. Build the same-cap N=1 comparator using deterministic parsing/truncation fixed after the length pilot, not FVE. Every proposed final readout has at most four bullets and the common output-token/compound-claim limits. If parsing is uncertain, mark it rather than silently inventing text. Score the text actually emitted; distinguish raw, parsed, capped, and rewritten versions.

Primary scoring atoms are raw source bullets; decomposed atomic claims are a separate variant. Retain source sample, original bullet, verbatim span, and transformations. Splitting must preserve qualifiers, referents, negation, modality, and relations; otherwise retain the full bullet. Partial support for one clause never supports its whole compound bullet: require support for all retained claims, or emit only supported minimal atoms and re-encode them. A normalized matching string never replaces the original.

Encode each distinct scoring string once per AR configuration and layer. Preserve exact layer tags and the validated whitening transform. Joint scoring means NNLS fits nonnegative weights for the selected text vectors against the target activation, using the exact validated FVE definition. Record coefficients, reconstruction error, and objective components. Do not substitute raw cosine similarity or treat good reconstruction as semantic truth. AR-dependent pilots wait for the loader/whitener checks; independent sampling and consensus can continue.

**Numerical solver decision, frozen before method development:** use SciPy's NNLS solver (`scipy_exact`) for the main A/C/D selections and primary joint-fit metric. The source uses an 80-step projected-gradient approximation (`released80`); retain it as an explicitly labeled release-compatibility metric and a same-pool selection ablation. The initial 16 real sample scores differed by at most 0.000552, with no winner changes in eight two-candidate comparisons; exact fitting took 0.00525 seconds versus 0.0124 seconds for the approximate solver in this tiny timing. Larger pools may differ and must be checked. Exact fitting better matches the proposed best nonnegative reconstruction and its monotonic set-fit property. Do not silently equate the two numerical conventions or compare exact-fit scores with published values computed using the approximation.

**Scorer visibility:** the released reward tokenizer scores only the first 32 text tokens of each bullet after its documented cleanup. Preserve and report the full emitted bullet and its original/scored lengths. Details beyond that boundary receive no direct evidence from this score. Output shortening is a separate condition, never an implicit claim that unseen suffixes were verified.

Use compact, shared artifacts rather than a new framework:

| Artifact | Minimum contents |
|---|---|
| Run manifest | Parent experiment, revisions, split/read-plan hashes, parser, scoring and helper-model settings, budgets |
| Candidate/claim records | Cell/sample IDs, exact text/spans, provenance, formatting flags, generation cost |
| Vector cache | Exact text hash, layer, AR/whitener hashes and encoding settings, vector reference |
| Fit/score cache | Target-activation hash, selected candidate IDs/order, vector-cache keys, solver/objective settings, coefficients/scores; E also records control-bank IDs/hash |
| Selection records | Method/configuration, input pool, selected IDs, edits, search trace, final text |
| Judge/results records | Exact request hash, verdict/evidence, coverage, cost, aggregate denominators |

Keep arrays in a few appropriately sized shards. Gram matrices are keyed by the complete ordered vector-cache keys; fit/score caches cannot be reused across different targets or control banks. A cache hit requires all relevant hashes to match. Never reuse a verdict for changed output text or altered judge evidence.

## Which language-model calls cost extra?

The O-lens and AR run locally on allocated GPUs. Helper language models may also run locally, but still consume time/GPU-hours. GPT-6 Luna judging is paid API work, separate from generation and selection. The same model used as a helper is not an independent evaluator simply because its prompt differs.

| Method | Extra helper-LM work beyond the shared pool | Local O-lens / AR work | Paid Luna evaluation |
|---|---|---|---|
| A: best-of-N | None | Shared O-lens pool; AR encode/refit | Final outputs |
| B: consensus | Optional claim extraction/equivalence confirmation | Shared pool; AR unnecessary unless a named hybrid | Final outputs; helper calls separately logged if API-backed |
| C: pruning | None for coefficient/deletion pilots; optional detail proposals | AR subset refits; encode changed text | Final outputs |
| D: pooling | None for fixed-pool selection | AR vectors and repeated small NNLS fits | Final outputs |
| E: contrastives | Optional diagnostic near-miss construction | AR controls or teacher-forced O-lens likelihood | Final outputs; diagnostic/helper calls separately logged |
| F: editing | Usually yes; bounded local model or API | AR re-encodes edits; shared O-lens pool | Final outputs plus any API editor calls |
| G: independent check | A second reader or bounded consistency helper | Depends on available frozen model | Final outputs plus any API helper calls |

Initially use Luna helpers: Standard for calls blocking the next selection/edit step, Flex for independently queued offline/bulk jobs. Luna remains the sole benchmark judge; Qwen is not a planned benchmark judge. Freeze settings; no silent model fallback. Helpers see candidates only, never targets, transcripts, or verdicts; context-aware extensions are separate. Text matching does not verify activation content.

An optional, deferred helper-only comparison against base Qwen3.6 is warranted only if measured Luna latency/cost motivates it; it is not required for the initial pilot. Verify availability/runtime and disable lens adapters and injection hooks. Compare identical candidate-only inputs, semantic traps, errors, latency, retries, and GPU opportunity cost. Reuse base files in an isolated worker or serialized phase; another worker needs extra VRAM. Never share mutable adapters concurrently. A separate instance is not independent evidence; local inference is not automatically faster or more faithful. Disclose shared-lineage bias. Consider a cached smaller helper only if straightforward.

### Helper implementation and cost forecast

Use one task-tagged asynchronous client with bounded concurrency, token limits, retry/backoff, and budget reservations. Batch work into one or a few chunked calls per cell, not one call per pair. Tasks are match confirmation, edit proposals, and the optional claim-extraction ablation; each has a versioned prompt and strict JSON schema. Short outputs contain source IDs and verbatim spans, match-pair IDs plus the five labels specified in B, or edits with parent/source IDs. Validate IDs, span offsets, labels, and output caps locally. Invalid references never become evidence; repair/retry only within the recorded allowance.

Exact matching and optional existing embeddings shortlist comparisons. Provisionally cap non-exact comparisons at 40 pairs per cell/pass, chunking 20 at a time; tune this limit on development. Preserve all-member compatibility within every accepted semantic cluster. When a required comparison exceeds the budget, leave claims unmerged rather than assume equivalence. Cache versioned extraction/matching/edit responses once using exact task inputs, model/settings, and source IDs. Global computational reuse must not transfer votes between cells. Runtime helpers remain separate from research agents reviewing development traces.

The [official GPT-6 Luna model page](https://developers.openai.com/api/docs/models/gpt-6-luna), checked 2026-10-09, gives Standard prices of $0.10 input/$0.50 output per million tokens; Flex is half, $0.05/$0.25. Forecasts below assume requests below 272K context, reasoning `none`, no regional uplift, and no cached-input discount. Each “pass” totals **all helper calls per cell** at an illustrative 10,000 input plus 3,000 output tokens; not every operation is guaranteed to fit.

| Hypothetical workload | Flex helper cost | Standard helper cost |
|---|---:|---:|
| One cell, one aggregate pass | $0.00125 | $0.00250 |
| 1,000 cells, one pass | $1.25 | $2.50 |
| 5,000 cells, one pass | $6.25 | $12.50 |
| 20,000 cells, one pass | $25 | $50 |
| 20,000 cells, two equivalent passes | $50 | $100 |

Cells are item/layer/position combinations, not questions; 20,000 is an approximate planning workload, not a verified exact count. Start with a **$2–5 helper pilot**, then forecast a **$40–60 working allocation inside the existing $200 target**, using the measured Standard/Flex mix, not a new spending cap. The current O-lens limit is N=32. Unrestricted pair comparisons remain prohibited: even 128 eligible bullets yield 8,128 pairs, so shortlist and cap helper work.

These are forecasts, not measurements. Meter actual prompt/output/reasoning tokens, cache usage or writes where reported, retry/repair and alternative-prompt costs, regional charges, and actual tier. Fund the routing policy within existing limits. Some work is local with no API charge; neither tier guarantees speed. Reconcile helper charges in the shared ledger.

## A. Select the best complete sample

Initial algorithm: apply the fixed parser and output cap to each of the first N complete samples; encode its emitted bullets; fit joint NNLS; choose the sample with greatest validated FVE. Break numerical ties by earliest sample index. Do not silently replace whole-sample selection with picking its best fragments.

Compare raw N=1, deterministic capped N=1, uniformly sampled complete candidates, and best-of-N on identical prefixes. Include a parsed-only control if parsing changes source output materially. Plot semantic quality and cost against N, not only FVE. Record how often the winner changes as N grows.

Failure checks: truncation, repeated bullets, generic winners, longer outputs receiving better scores, and candidates exploiting AR weaknesses. A gain in FVE with poorer recovery or more contradictions is not success. The generation pool is the main cost; AR encoding is reusable across every downstream method.

## B. Consensus over meaning

Primary consensus scores and emits **verbatim original bullets**. Compare conservative normalized exact matching with semantic matching over those same bullets; helpers return labels and IDs, not rewritten scoring atoms. Exact matching changes only harmless whitespace/formatting. Extraction/splitting into atomic assertions is a separate ablation. Optional embeddings shortlist comparisons but never establish equivalence.

A frozen helper labels shortlisted pairs `equivalent`, `one-way entails`, `contradicts`, `related`, or `uncertain`, with source spans. Only bidirectional equivalence merges. Audit approximately 40 pairs, including number/negation/direction traps, before trusting it. Preserve entities and modality too. Prevent transitive chains by checking all-member compatibility, not just one representative. Cap comparisons; leave unverified/uncertain pairs unmerged at every pool size. Audit false merges and false splits.

Count distinct supporting samples, not repeats within one sample. Rank by support; break ties by earliest occurrence. Select up to four compatible clusters. Initially use deterministic verbatim representatives with provenance; FVE-selected wording is a separate ablation. Do not average AR vectors across equivalent wording: each string keeps its own encoding. Log excluded contradictions and semantic merges.

Copying text does not guarantee faithful selection: a false merge can lend a rare wrong claim false consensus. Keep compatibility checks and uncertain pairs separate; rewrites/detail deletions remain distinct arms with fresh AR encoding, not proof of truth.

Try support fractions .25/.5/.75 and a consensus-plus-AR tie-break selectively on development. Compare with exact matching. AR similarity never establishes semantic equivalence. Cache comparisons; avoid unrestricted all-pairs helper calls.

## C. Prune an existing readout

Begin with A's winner and, separately, capped N=1. Fit its bullets jointly. Compare:

1. **Coefficient filter:** remove bullets with fitted weight below a development-set threshold, then refit.
2. **Leave-one-out deletion:** omit each bullet in turn, refit all remaining weights, and measure lost FVE. Remove the least-contributing bullet when its loss is below the fixed threshold; repeat with a new fit.
3. **Detail pruning:** propose source-backed deletions of modifiers or subordinate clauses using deterministic spans or a bounded helper. Re-encode every changed string; compare with deleting the whole bullet.

NNLS coefficients can shift between redundant bullets. Small contribution means dispensability for this fit, not falsehood. Without penalties, removing a column cannot improve exact reconstruction; tolerate numerical noise and use semantic outcomes to assess pruning. Protect negation, quantities, modality, and role binding from deletion that changes meaning.

Compare matched random deletion and deterministic shortening at similar token/claim counts. This distinguishes smarter selection from simply saying less. Subset refits are cheap; detail proposals and their fresh AR encodings are separately measured.

## D. Compose from the fixed pool

Collect eligible source bullets from all N samples, preserving provenance. Remove exact duplicates; do not discard semantic near-duplicates merely because their AR vectors are close. Compute each vector once and cache the Gram matrix and target dot products when memory permits. Select no more than four bullets by fully refitted joint NNLS:

```text
selected = []
repeat at most four times:
    for each eligible bullet b outside selected:
        trial[b] = fit_all_nonnegative_weights(selected + [b])
    choose b with best joint objective, using fixed tie-breaking
    stop if its marginal gain fails the development-fixed rule
    selected = selected + [b]
    keep the fully refitted coefficients
```

Recompute marginal gains after every addition; do not rank isolated bullet FVE once. This is fully refitted nonnegative greedy selection, not classical orthogonal matching pursuit's correlation rule; compare the [OMP/orthogonal-least-squares distinction](https://arxiv.org/html/1111.0522). Import no recovery guarantees. Validate tiny cases against exhaustive search; measure NNLS speed rather than assuming Gram caching makes it cheap.

Optional swaps replace one bullet and accept improvement under fixed rules; cap passes and log swaps. Compare with A/B on the same pool. A best-complete-candidate fallback ensures no-worse reconstruction only with identical allowed atoms, cap, penalties, and development-set numerical tolerance. Reliability-filtered D cannot fall back to excluded claims. FVE alone does not prevent incompatible assertions.

**Four selection rounds are not new sampling rounds.** Residual O-lens resampling is deferred under the current 32-sample cap; it cannot silently add generations beyond the shared pool. Numerical greedy rounds and NNLS refits use existing candidates and do not consume new O-lens samples. A later residual experiment would require revisiting scope and retaining the coordinate, near-zero norm, original-target scoring, and equal-budget safeguards.

## E. Ask whether a readout is specific to this activation

**E1: matched controls.** Provisionally use eight controls per cell from the fixed development/calibration bank, excluding related groups and all test examples. Match layer and context/position characteristics. Start with true score minus mean control score; separately test a control-percentile variant. Reuse AR vectors; record control identities/distributions. Generic text should not win by matching everything.

Freeze each cell's control IDs and selection seed and reuse them across method comparisons; all controls come from the same frozen calibration bank.

**E2: semantic near misses.** First cross two controlled activations with two descriptions; score all pairings and generic omission to test directional discrimination. For inference, construct 1–3 plausible single-change alternatives from the candidate claim alone, changing a number, negation, or relation without answers. Encode each and compute the original's score minus its highest-scoring alternative. Use this margin only after the diagnostic and development comparison support it; it is not proof of truth. Known answers remain diagnostic-only and never enter deployment generation/selection.

**E3: conditional likelihood.** Teacher-force the identical candidate under the frozen O-lens carrier with the true activation and matched controls. Compare log likelihood differences with a prespecified token-length treatment, recording both totals and lengths. Keep the candidate fixed across conditions. This costs local O-lens forward passes; batch them and cache exact conditions. It may reward fluent, expected phrasing rather than accurate content, so compare with AR selection and semantic evaluation.

## F. Edit with explicit limits

**F1: pool-constrained editing** allows deletion and substitutions drawn from source claims already in the shared pool. Preserve a map from every output clause to its sources. This tests recombination before introducing unconstrained language.

**F2: free language-model editing** initially uses Standard Luna on selected candidate claims only, instructed to improve clarity/consistency without adding facts. Record the prompt/model and retain the original. New assertions are marked as introduced, not source-supported merely because the editor wrote them.

**F3: bounded beam search** uses two sequential calls, each returning four proposals total across at most two retained states, not four per state: eight proposals overall. Configure aggregate input/output limits, counting accumulated context each round. Re-encode, rescore, and log every state/parent/rejection/cost. The 32 O-lens sample cap does not cap external-editor calls; these eight proposals and their tokens are separately bounded.

Illustrative two-round Standard Luna costs at $0.10/$0.50 per million input/output tokens:

| Input/output per round | Per cell | 1,000 cells | 20,000 cells |
|---|---:|---:|---:|
| 2,000 / 800 tokens | $0.0012 | $1.20 | $24 |
| 8,000 / 2,000 tokens | $0.0036 | $3.60 | $72 |

These two illustrations price ordinary input. If all input incurred the verified
cache-write rate of $0.125 per million tokens, their two-round costs would be
$0.0013 and $0.0040 per cell. The corrected ledger reserves that higher input
rate; measured campaign figures include reported writes and remain separate
from invoice reconciliation. See experiment 022 for the accounting correction.

These are forecasts without assumed cache discounts or retries. Three variants over 20,000 cells would cost $72–216 just for editing; the $40–60 helper allocation is not a guarantee. Pilot 100–300 representative development cells, shortlist 1–2 variants, then use actual planned cell counts; running all variants on 20,000 cells is not required. Freeze one cell manifest shared with raw/capped N=1 and A controls. Report partial-grid pilots as cell-level metrics, not official full-grid item accuracy; final comparisons use the original complete family grids and official item aggregation.

Every rewrite needs fresh AR encoding. Accept by local AR objective initially; separately test a development-fixed validated score combination. Luna never judges each proposal or supplies feedback to the editor. Judge final outputs for each condition; sampled intermediate audits occur only after selection, without feedback. Compare editing/encoding cost against A with a larger shared prefix up to 32 or measured compute; equal pools do not equalize cost. Check deleted true details and added unsupported ones.

## G. Use an independent frozen check

A second compatible pretrained AR would provide a distinct score, but access/compatibility remain unresolved. Verify coordinates and lineage; agreement between correlated readers is not ground truth. Calibrate ranks or scales on development before combining scores; never average incompatible raw FVE. Mark unavailable variants rather than substitute incompatible models.

Prioritize J++ within G after compatibility checks: cache candidate entity/number token ranks/support on existing cells and test incremental quality. The reader itself needs no API calls. Token absence does not imply falsehood, and word presence does not verify relations. An activation-blind LM consistency check is separate, not a second activation reader; disclose shared-model bias if Luna also evaluates it.

The [J++ card](https://huggingface.co/koayon/jpp-lenses) advertises layers 0–62; its [quickstart](https://github.com/safety-research/jpp_lens)'s seven layers are examples. Artifact contents, coordinates, normalization and CPU/H200 source fixtures have now been checked in [the J++ development diagnostic](experiments/006-jpp-development-reader.md); no quality improvement or clean held-out result follows from those engineering checks. Its expert weights use labeled readout items: audit fitting-data overlap with our WorkspaceBench groups and disclose it. Until this audit establishes disjoint fitting and evaluation groups, keep J++ as a development diagnostic, excluded from clean held-out headlines and the final composite. Paper-level held-out results do not establish that the released map excluded our items; do not claim clean held-out improvement without checking. The [NLA card](https://huggingface.co/ceselder/qwen3.6-27b-nla-rl) specifies source layer 42, reader injection layer 1, and its own `av_base`/metadata. Consider feasibility of a small, separately labeled layer-42 development diagnostic, outside the core grids. Never feed layer 44 as 42 or mix this probe into core headlines. Its reconstructor is not a drop-in AR or raw-score average; validate its own coordinates/preprocessing. Core completion does not depend on this optional study.

## Combining methods and measuring their added value

After the individual pilots and failure audits, run a bounded combination
search on the same development cohort. Start with the strongest useful simple
method, add one component addressing an observed weakness, then remove each
component from a promising combination to check its contribution. Test a few
ordering changes where they have a concrete rationale, such as filtering before
pooling versus filtering its selected output. This is an adaptive forward and
backward search, not an exhaustive cross-product of all methods and thresholds.

Initial candidates, subject to the single-method evidence, include consensus
filtering followed by pooling; pooling followed by pruning; and matched-control
selection followed by pruning. Editing is an optional final component only if
its pilot produces useful improvements. A combination may help even when a
component alone has mixed results, but it needs a specific hypothesis and a
paired comparison. Do not require a significance threshold for exploration.

Keep the comparison constraints explicit:

- Compare components alone, the combination, and the combination with each
  component removed. Compare against raw/capped N1 and best-of-N at the same
  candidate budget. Report the best *tested* configuration, not a global optimum.
- Match signal availability. For example, consensus measured over the first
  16 samples can support a clean N16 pooling comparison; do not silently label
  unexamined N17–32 claims unreliable or call that equivalent to N32 consensus.
- Respect each score's unit. Complete-readout likelihood and joint
  reconstruction cannot be treated as interchangeable bullet-level evidence.
  Any new objective, weight, threshold or ordering must be development-set
  specified and frozen before held-out testing.
- Reliability-filtered pooling may only fall back to outputs satisfying its
  filter. An ablation should remove the named component while preserving other
  constraints. If it changes which expensive calls occur, report that change.
- Retain the shared maximum of 32 O-lens samples per cell and the bounded editor
  proposal budget. Reuse saved proposals and their lineage for offline ablations;
  disclose when an ablation is conditional on the shared search rather than a
  fresh independent editing run. Do not silently buy another editor search for
  every combination.
- Narrow the shortlist using validation, then freeze the tested combinations,
  component removals and decision rules before opening test results.

Quality is the priority. Each result must also report its cost on a **new
activation**: O-lens samples and generated tokens, local AR encodings/forward
passes and fitting work, helper calls and tokens, measured GPU-seconds, API
dollars, and elapsed latency with batching/concurrency disclosed. If GPU dollar
pricing is unavailable, report GPU time rather than invent a conversion. Show
the simpler alternatives and the quality–cost frontier, with uncertainty and
family-specific tradeoffs. A costlier method earns its place through useful
quality gains, not merely a higher reconstruction score.

Distinguish actual campaign spend, incremental cost of rerunning a selector on
the cached research pool, and end-to-end inference cost. Shared caches can save
money during development without making N32 generation free at deployment.
Exclude benchmark judging from the deployment method's inference cost, but
report evaluation costs separately. Include genuine recurring runtime helper
and editor calls in the method cost.

## Iteration, decisions, and coordination

Follow a repeated loop: specify comparison → tiny representative development run → Luna judge → GPT-6.1 Sol inspects wins, regressions, and random unchanged cases → coordinator chooses revision → update the record/specification. Research agents reviewing traces are not runtime helpers and cannot inspect held-out results during selection. Targeted diagnostics supplement the representative sample.

No statistical-significance gate: consider practical effects, paired examples, failure mechanisms, consistency, regressions, uncertainty, and incremental cost. A single-family gain can justify another iteration. Describe promising evidence honestly; selected examples are not proof.

Routine iterations within authorization do not require new user approval. Ask the user about changed research direction, budget expansion, or a genuine external block requiring their input. Keep them informed of consequential decisions and time forecasts. Preserve time for all seven bounded pilots, final frozen comparisons, component ablations, and the report; do not overengineer infrastructure. Configurations, helper prompts, control banks, and decision rules freeze before test. Execution status belongs in the experiment records; a specified procedure is not itself evidence that it ran or worked.
