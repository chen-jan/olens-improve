# Execution status

Updated: 2026-10-10, approximately 20:18 UTC.
Started: 2026-10-10 01:25:36 UTC (October 9, 21:25:36 EDT).
Target finish: 2026-10-10 21:25:36 UTC. Execution remains active and authorized.

## Latest operational checkpoint

At 20:17 UTC, **41 of 48 held-out comparisons are complete**. Hallucination finished pooled selection with 16 samples, stopped cleanly, and restarted with connection reuse enabled as PID 42548/session 53016. Both active workers now use the reviewed optimization and 256 concurrent requests / 4,000 RPM. Five hallucination comparisons and two role comparisons remain; eleven DEV comparisons follow on each family after its TEST work finishes. No speed improvement has yet been established. The 20:11 terminal check retained all uncertain charges; the next combined measurement is scheduled for 20:22.

At 20:03 UTC, **40 of 48 held-out family/method comparisons are complete**: all twelve multi-hop and chain comparisons, ten role comparisons, and six hallucination comparisons. Eleven development comparisons also remain. These counts do not represent the percentage of runtime left; hallucination comparisons involve two judging stages.

The role worker stopped cleanly after its tenth comparison at 19:59. Root verified exit code zero, a free cache-owner lock, unchanged uncertain charges and the reviewed source, then restarted it at 20:02:54 with the database connection optimization enabled. It uses 256 concurrent requests and a 4,000 requests/minute cap on the existing CPU allocation. Hallucination is finishing its current comparison before the same switch. No current API calls were cancelled. The first five-minute observation will measure actual throughput.

**The speed gain remains unproven.** Connection reuse passed 92 focused tests and independent review, but two short offline benchmarks disagreed. The earlier 3.37x database-only gain was not reproduced by the actual-code repeat. We are measuring a live trial rather than promising that gain. The latest planning range remains roughly four to six hours from the 19:34–19:48 checkpoint, including final analysis and delivery; a faster estimate requires observed progress.

The 20:01:58 terminal check recorded 82,841 settled TEST requests and $12.52272038 estimated TEST usage. All twelve uncertain TEST charges ($0.059636875) and the separate old reservation ($0.00538675) remain held. These are operational/accounting observations, not benchmark scores or a reconciled provider invoice. No TEST quality has been inspected. See [049](experiments/049-higher-concurrency.md).

The exact DEV twelve-method reporting export is complete: 5,236 cells, 37,259,110 bytes, SHA `a638c102a2e762543d0d81f28575fa2a46dd64ea7d12641b071622736a89c91e`. It is a byte-preserving text/count projection, with no inference or new judgments; eleven DEV family/condition measurements still remain.

Public dashboard version 9 was published at 18:59:45.199753 UTC. It updates operational recovery and retained API charges only. Scientific objects and all 33 figure/example assets are unchanged; no TEST quality was read or published. Prior browser QA was not repeated for this metadata update.

At the 18:58 UTC checkpoint, both workers were healthy: hallucination PID 3783545 and role PID 3802604, each at sixteen concurrent requests / 400 RPM. TEST had 58,789 settled attempts and $8.64896518 estimated usage. The interval added 3,305 settlements over 611.55 seconds, approximately 324/minute across staggered worker starts. All twelve unknown TEST holds ($0.059636875) remained unchanged. The 25 reserved attempts held $0.12956375, including the old terminal hall reservation. These are operational counts and ledger estimates, not quality results or invoice reconciliation. Receipt: `durable/diagnostics/test12-operational-v1/storage-recovery-v9-operational-1858-v1.json`, SHA `6f1116147dd65c2b9a4a90f4f7c2a8c2c7afbc58fa1881d95c896e8165044a77`.

The 18:58 GPU reuse check found all four H200s at 0% utilization and 0 MiB. Their allocations remained RUNNING, with roughly 3.5 hours remaining on three and 21.5 hours on the fourth. They remain handed back to the user; this project schedules no GPU work.

**Conditional delivery estimate, 19:00 UTC:** the frozen forecast and 18:58 counts suggest approximately 58,327 remaining TEST judging requests. This is an estimate, not a hard bound, and does not fix future retries or cache reuse. At approximately 324 combined settlements/minute, the aggregate service reference is three hours; allow three to four hours for the TEST tail. The eleven unfinished DEV family/condition comparisons had 22,157 calls in the older cached forecast and require a fresh subset forecast. Role DEV may overlap hall TEST only after the role TEST worker finishes and releases its cache. Working estimates are all judging finished around 23:00 UTC October 10–00:30 UTC October 11, followed by one to two hours of final review, with delivery around 00:00–02:30 UTC October 11. This is conditional, not a promise. Current evidence does not support the original 21:25 UTC target; the four-family scope is unchanged.

### Recovery through 18:53 UTC

The initial higher-concurrency snapshot showed a slowdown, but the longer window recovered. At18:28:55 UTC, TEST had54,378 settled attempts and$7.79799183 estimated usage; all12 uncertain holds ($0.059636875) and the old inactive hall hold ($0.00538675) remained unchanged. The12.4-minute interval since18:16 added4,960 settlements, approximately400/minute combined. Role D16 closed at301 physical responses/minute with16/400; hall A32 closed at142/minute with8/200. These are different conditions and traffic, not a randomized concurrency comparison. Both profiles had zero ledger errors, despite individual waits exceeding100 seconds.

Both workers exited 0 after the requested boundary stops. At 18:29:46 the exact PIDs were absent and their cache-owner locks were free. Hall had completed four of twelve comparisons; role seven; multi-hop and chains all twelve. The independently reviewed byte-preserving ledger move completed. The canonical durable path now resolves to the fast-compute copy; the old inode is a read-only archive. Source/copy SHA, accounting equality and SQLite quick_check passed. Hall alone resumed at 16/400 as PID 3783545/session 3933 at 18:43. The 18:48 health review found 1,106 new hall settlements, unchanged unknown holds and no slow-phase warnings in the checked tail. Role then resumed as PID 3802604/session 65303 at 16/400, ahead of the combined 18:58 check above. The first verification attempt was stopped before copying because its source query stalled; the copy-first retry succeeded. All 73 focused accounting/admission/phase/async/cache/transport/stage tests passed on allocated CPU. A local sandbox notification denial caused the earlier fake-client hang; no production code repair was needed. No TEST quality has been inspected.

The final slide builder has passed synthetic visual checks for66-page complete and58-page TEST-preview layouts: no text overflow or out-of-canvas objects after correcting two paired-chart labels. Root inspected the findings and paired-chart pages. This validates layout fixtures, not real final findings or native PowerPoint rendering. Complete TEST and all469 descriptive inputs, their scientific review, final renders and publication remain required.

### Previous 18:10 checkpoint

At 18:07 UTC, the role worker completed specificity selection and stopped cleanly at the requested comparison boundary. Six of its twelve comparisons are complete; the next is pooled selection with 16 samples. Its cache owner is free. Hallucination has completed three comparisons and is processing best-of-32. Multi-hop and chains have finished all twelve. No TEST quality has been inspected.

A reviewed one-family transport change is prepared: role judging can increase from eight concurrent requests / 200 requests per minute to sixteen / 400, while hallucination retains its current settings. Twenty-five offline tests, root review and independent source review passed. The prepared specification has passed validation without API dispatch. The old worker exited0 and its terminal accounting check retained all charges. Root sealed the specification and launched the faster role worker at approximately18:10 UTC as PID3690209/session80782. A post-launch throughput check is pending. The 18:00 check measured 296 settlements/minute across both workers over 10.3 minutes, with no new uncertain charges. See experiment047.

All required GPU work for the four-family study is complete. The retained pools cover all 469 items and 19,435 cells, with 621,920 samples. Reconstruction vectors, all twelve final TEST outputs, model artifacts and portable-tool checks are retained. The 17:58 live check found all four H200s idle. Remaining judging, analysis and presentation use CPUs and the API. The user reconfirmed that broader WorkspaceBench transfer is a second stage after these results; no additional families are being launched now.

Current delivery planning allows roughly six to nine hours from the 17:58 update at the existing rate, including missing DEV judgments and final review. Four to six hours may be feasible if higher concurrency improves measured throughput; it is not yet established. GPU expiry does not prevent completion. The public dashboard remains reviewed DEV/VAL version8, with question-level recovery as its default. A source-reviewed final slide extension is ready; actual final data and visual review remain pending.

CPU job25508300 on node1603 lasts through 05:32 UTC on October11. Hall remains PID2407614/session73504. Old role PID2481603/session68888 is terminal exit0; current role PID3690209/session80782 uses16/400. Preserve the original accounting epoch, $40 TEST run cap, all twelve unknown TEST charges ($0.059636875) and the separate stopped-hall reservation ($0.00538675). The compute agent remains the sole bounded ledger observer. Research commits are local.

## Earlier checkpoints

The public dashboard was updated at 17:04 UTC (Site version 6) with explicit per-activation versus whole-question labels, the unchanged hallucination error endpoint, and the 16:49 API snapshot. Sixteen focused tests, independent review and desktop/mobile checks passed. The later measured timing addendum verifies 621,920 samples and 30.192 GPU task-hours for generation plus main reconstruction; see experiment 044. Both remaining judge sessions were confirmed live at 16:53; no TEST quality has been inspected.

Resource accounting at 16:49 UTC: $18.12687471 estimated API usage plus $4.900247625 retained reservations, total$23.027122335. The16:43 inventory is93.732 GB project files (69.584fast,24.148durable), excluding55.563 GB reused base weights. Resource receiptf9b69d2b… separates64.773 reserved H200-hours from approximately30.17 estimated model task-hours; neither is GPU dollar billing.

At 16:38 UTC, both remaining TEST sessions are active: hallucination v4 (session 88668/PID 3625516) and role v5 (session 63575/PID 3651167). The old role worker stopped on the same lock-acquisition failure; v5 resumed at 16:34 with the reviewed retry patch and saved results. All eleven uncertain TEST holds ($0.05425425) remain reserved. The role log includes a successful 91-second lock wait, so active sessions do not establish healthy sustained throughput. The16:39 bounded checkpoint confirms new settlements in both workers: hall95settled/5active and role94settled/6active in recent100-attempt windows, with no newunknowns. Receipt849be81b… retains all prior holds. Multi-hop and chains have finished judging. TEST quality remains uninspected. Reviewed DEV/VAL read-site maps and an editable presentation draft are ready; the map website update was published at 16:46 UTC as Site version5, and the final deck still awaits final results. The 22:00–00:00 UTC delivery estimate remains conditional on judging progress.

At 16:06 UTC, multi-hop and chains have finished the twelve-condition TEST
judging queue. Role binding remains active and has completed raw/capped N1.
The hallucination continuation stopped again at the ledger's writer-lock
acquisition; its outputs and all uncertain charges are retained. A bounded
acquisition-only retry fix passed 48 offline tests and independent review.
Hallucination resumed at 16:12 UTC in session 88668/PID 3625516 under the sealed
v4 specification, SHA `423a431df4b18b5830681763db0a1a52b2294cc62c449eeff506bb3324932226`.
The fix never replays a transaction body or commit, and the running role worker
remains untouched. The 16:16:55 UTC bounded checkpoint found 94 settled and six
active hall attempts, and 95 settled and five active role attempts, in their
latest 100-attempt windows, with no new unknown charges. All seven prior TEST
holds ($0.03490775) remain. These windows confirm new responses, not a cumulative
throughput guarantee. No TEST quality
has been inspected. Final delivery is currently estimated at 22:00–00:00 UTC
(6–8 pm Eastern), conditional on reliable remaining judging. The public dashboard was subsequently updated at 16:46 UTC with the16:39 operational checkpoint and reviewed DEV/VAL maps.

At approximately **15:00 UTC**, all 12 validation methods/controls are complete
across four families (80 items, 3,485 cells). The prospective final comparison
now includes those same twelve variants: the original six primary comparisons
and six additional secondary comparisons. Settings and the two validation-selected
operating points are unchanged. The expansion was sealed before any TEST
judgment or quality inspection. Small validation samples do not rule methods out.
See experiments 038 and the unchanged original freeze in 032.

All 342,848 TEST samples passed source identity checks. Reconstruction and all
four selector shards are complete for all 10,714 sites. One selector suffered an
OOM, then resumed its 2,213 saved cells on CPU capacity in another existing
allocation and completed successfully. The merged selection SHA is
`547b953be6fff89d2f850001fd6dcdb3aed606708c8a211b6270369a4aa25df1`.
The prespecified specificity/pruning combinations also completed, SHA
`0e2f4583bd9ee5a9d3b75960801b0dd656b4355ad3fbe3e78ac55d12592170f8`.
Exact twelve-condition export and its cache-aware forecast are complete. Root
launched all four TEST evaluators at 14:58–14:59 UTC, with a shared $40 run
ceiling and expected usage of $19.01. Hallucination has a six-hour ideal service
reference, before I/O/retries and final review. Allow roughly 1–3 hours beyond
the original 20-hour target for final delivery; the user has been informed.
No TEST quality result has been inspected. See experiment 040.

The recovered DEV N=2 role queue completed successfully: 1,556 paid responses
in 505.421 seconds, about 185/minute. A bounded checkpoint found no new uncertain
charges in its latest 100 responses; previous holds remain. The remaining role
N=4/8/16 and hallucination N=8 repair/N=16 queues also completed successfully.
All six DEV prefixes and the complete scaling report are now independently
checked. Source-preserving cell/item figures and grouped intervals are ready.
These late DEV measurements cannot change the fixed TEST methods.

The expanded [public dashboard](https://olens-improve-research.jan618.chatgpt.site)
was first published at **14:35 UTC**, then updated at **15:49 UTC**. It exposes all eight approach/combination sections,
423 pilot metric rows, sample-count curves with source intervals, exact counts,
paired differences, costs and available examples. Ten focused tests, independent
unit/source review and desktop/mobile checks passed. The scientific snapshot
remains explicitly distinct from the newer operational status.

Following the user's request for systematic qualitative review, eight shared
pilot examples are fixed by an outcome-blind seeded group/item/cell rule.
Three Sol reviewers are assigned A/C/D, E/F/G, and consensus/combinations.
Each uses exact outputs, evaluation context and judge evidence, with at most
two separately labeled method-specific supplements. Review gaps and unrun
methods remain explicit. The richer case cards were published at 15:49 UTC: 688 variant/example records
repeat the same eight examples, with 1,436 exact before/after strings checked
against source. Thirty-eight focused tests, desktop/mobile checks and exact
lazy-loaded quote checks passed. These counts are not independent observations
or an effect estimate. Complete DEV sampling curves and 12 downloadable figure
files are also published.
See `configs/qualitative_shared_panel_v1.json` and QUALITATIVE_REVIEW.md.

The latest verified pre-A2 global receipt at 13:56 records $13.15336 usage cost
plus $4.79472 uncertain charges retained. It is a historical receipt, not the
current invoice total. The $200 target/$300 ceiling and 500-GB storage allowance
remain in force. Research commits remain local; only the dedicated Site source
repository is pushed. Final TEST analysis, report, dashboard and slide deck
remain required; the goal is active.

## Findings so far

No general improvement in explanation faithfulness is established yet. The
**5,236-cell development comparison of best-of-32 against capped N1 is complete**:
contradicted readouts change from 543/1,137 to 523/1,140, a −1.88 percentage-point
change with a paired group interval of [−5.41, +1.76]. Bridge, chain and role
cell recovery increase from 29→43, 26→30 and 151→182, respectively. Item-level
role recovery remains 23/30. The flagged false-span tally rises from 1,305 to
1,324 despite fewer wrong readouts; inspected recovered concepts still occur
inside incorrect explanations. See [the report](REPORT.md) and experiment 019.

The remaining findings below come from the **189-cell development pilot** unless
explicitly labeled otherwise. It contains only 2–8 independent groups per family.
Other complete-grid method comparisons remain partly unfinished.

- Selecting the best reconstruction from a larger nested pool cannot lower the
  score, by construction. Quality moves differently across tasks. Best-of-32 has
  39 contradicted readouts among 71 specific outputs, compared with 46/71 for
  capped N1; a single random draw from N32 has 38/72. Larger measurement is needed.
- Pooling bullets raises reconstruction further. It recovers bridge mentions in
  10/24 cells versus 7/24 for best-of-32, but chain intermediates in only 1/21
  versus 3/21. Inspected names and numbers sometimes appear inside incorrect
  relationships or calculations. Mention recovery is not full correctness.
- Two editing rounds did not improve those recovery counts or reduce the 42
  contradicted pooling outputs. Most accepted edits cleaned formatting; two
  violated preservation instructions. These are risks, not proof that every
  changed detail is false.
- Strict whole-bullet consensus removes most coverage. The repaired pipeline
  completed every requested pair label, but a fresh stratified 40-pair audit
  still found five clear false equivalences. Four affected actual clusters.
  This audit is not a population error estimate; semantic variants remain
  diagnostic. Exact-repeat support plus pooling produced no recovery gain.
- A bounded helper-effort audit rechecked the same 40 semantic pairs with Luna
  reasoning enabled. It rejected all five previously flagged equivalences, but
  also rejected two valid matches. This selected audit is not an accuracy
  estimate. Confirmation on the existing 189-cell pair list is now judged and
  does not establish better selected outputs. Strict filtering still removes
  most coverage. The benchmark judge remains Luna with reasoning disabled.
- Contrastive selection followed by pruning is a promising combination for
  larger measurement, with unchanged bridge recovery and three additional role
  cell passes in the pilot. Inspected role gains are judge-sensitive; the
  retained texts still contain conflicting roles or names. They do not yet
  establish improved relationship faithfulness.
- Contrastive reconstruction is sensitive to layer and wording. The likelihood
  comparison is mixed. J++ token ranks cannot verify reversed relationships and
  have unresolved fitting-data overlap, so remain development diagnostics.
- A repeated Luna audit changed wrongness on 2/10 seeded random A32 readouts
  covering six items. Originals used Flex and repeats used Standard; this does
  not isolate a within-tier effect or establish which label is correct. Primary
  verdicts remain unchanged. See experiment 011 on judge repeatability.
- All32 candidate judgments reveal missed opportunities: bridge mentions appear
  in at least one candidate in 14/24 cells, while reconstruction selection
  recovers them in 7/24. This is an evaluation-only availability ceiling; some
  passing candidates still contain incorrect surrounding claims.
- Matched unrelated donor activations reduce flagged hallucinations from
  543/1,137 to 25/992 specific outputs, but 956/1,145 donor outputs are off-topic
  and only 11 are consistent, versus 446 for the actual activations. An error
  rate without useful coverage would misleadingly reward this control.

Reviewed sources and paired examples are in the experiment records and
[local dashboard](../dashboard/index.html). Local commit `f62adb6` contains the
first source-checked dashboard with grouped intervals. The research GitHub repository has not been pushed. A separate Sites source repository hosts the sanitized public dashboard.

## Current work

| Work | State |
|---|---|
| Model, adapter, matching AR and whitening | Source reproduction passed; exact NNLS is primary |
| Activations and splits | All 19,435 core cells freshly captured; grouped split v2 frozen |
| Shared pilot | 189 cells × 32 samples complete and immutable |
| Full development collection | All 5,236 cells × 32 samples frozen; 167,552 samples |
| Full development reconstruction | Complete: 642,209 unique vectors covering all 5,236 cells |
| Full development selectors | Complete: 5,236 cells and 40 offline conditions; all 2,018 overlapping v3 rows agree exactly; raw/capped baseline identity passed |
| Full development baseline | Raw and capped N1 judged, all stages/cells complete; pinned item aggregation verified |
| Single-method pilots | A/B/C/D/E1/E3/F judged; E2/G diagnostics complete with limits; exact-claim-span v3 stopped after its eight-cell contract audit, without benchmark-quality measurement |
| Combinations | 65 unique pilot conditions judged and source-checked; larger E1-plus-pruning outputs complete and awaiting judging |
| Additional controls | All32 judgments and matched-donor N1 complete; all requested cells/stages covered |
| Held-out evaluation | Validation complete: 12 methods × four families, with systematic trace review. TEST sampling complete: 10,714 cells × 32. Twelve final comparisons sealed; reconstruction and selection complete. Multi-hop evaluation is complete. Multi-hop and chain evaluators completed; hallucination and role workers resumed from saved outputs after a ledger-lock interruption. No TEST quality inspected. |

Combination comparisons retain unchanged parents, component-off outputs, and
random deletion matched on retained bullet count. Fixed support weights are
tested on the same N16 pool without semantic merging. Costs distinguish the
shared research campaign, rerunning a selector from cache, and inference on a
new activation. Quality has priority; extra cost must still be visible.

The larger capped N1 baseline has 543/1,137 contradicted specific readouts;
bridge recovery on 11/31 items, chain recovery on 15/30, and role passes on 23/30.
The corresponding role cell count is only 151/3,420: an item passes when any
inspected site passes, so item recovery must not be read as uniformly faithful
readouts. These are original-grid development scores, not held-out results.

Hall resumed at 15:42 (PID3595134/session12826), and role at 15:47
(PID3598846/session51027), under unchanged specification23163a9e…, run cap,
epoch and holds. The healthy hall checkpoint retained all six uncertain charges
($0.029525125) and found no new unknowns in its latest100 requests. Chain and
multi-hop are terminal exit0. Next: monitor the remaining unchanged menu.
Finish the remaining judgments, paired analysis, independent example review,
report and slides. The fresh-input N32 timing and relocated-cache replay are
complete (035/036). The 14:55 forecast was about six hours of ideal judge
service, before contention, retries and review; it is not a deadline guarantee.

## Earlier operational history

The following notes preserve earlier incidents and partial-development states;
the current checkpoint above supersedes their progress and cost snapshots.

The earlier DEV judging recovery used eight slots/200 RPM per family with fresh operational
profiles and the same $20 run ceiling, exact requests, caches and uncertain
holds. A single unchanged Luna request passed in 1.39 seconds. The copied-ledger
load check completed 384 fake calls without network use or production accounting
changes; sixteen slots were faster than eight in that instrument. Intermittent
local I/O pauses exist, but this did not reproduce the real transport failure.
The cause remains unresolved; there is no automatic concurrency increase.
The DEV queues stopped at clean condition boundaries to prioritize validation.
After all twelve VAL hallucination conditions completed and its worker exited,
DEV hallucination resumed only its fourteen unfinished conditions at 10:58.
Both DEV queues are now held while validation finishes. The resumed hall A4 is
complete; A8 reached its queue boundary with one unresolved readout in both
stages and remains scientifically incomplete. Its successful judgments are cached.
The role DEV queue remains prepared pending its validation handoff. Incomplete DEV comparisons remain
incomplete and cannot change the already frozen validation decision rule.
At 08:38 UTC the new queue had 9,403 settled requests and one isolated
unknown charge of $0.00481825, retained in full. Subsequent latest-100 windows
were healthy; no guard reset or concurrency increase was made.
A read-only monitor was bounded to avoid holding long database read locks;
this is an operational correction, not proof of the previous failure cause.
At the frozen evidence snapshot, 24 multihop, 21 chain, four hallucination and
three role conditions were complete out of 24 per family. Incomplete conditions
remain incomplete, even when partial verdicts are cached.

The merged selection SHA is
`54ee50e61ebc11ac66d8d11c294dda60e17a7f9e06ad8632665e6bbb6505635e`;
all 10,472 raw/capped baseline text-and-token pairs passed identity checks.
E1 pruning used 235.75 seconds on four CPU threads without new model calls.
Repaired consensus and pooling-plus-specificity pilots are judged. The separate
exact-source-span pilot stopped after eight contract audits; its planned
32-cell expansion is incomplete. This does not establish that all claim-level
consensus fails. Small gains with wide intervals can warrant follow-up, while
substantial recovery losses require explicit practical tradeoffs.

The full development audit found 523 bullets empty after AR token cleanup in
103 role cells. Complete-candidate AR methods exclude unscoreable samples;
raw/capped/random controls preserve their text, and N1 pruning leaves such
parents unchanged. Twelve A1 cells abstain where capped N1 retains text (two
parser exclusions and ten unscoreable parents). Report these eligibility
differences separately from selection gains; the fix is not a faithfulness result.

A local vector-first CLI now supports immutable candidate generation and replay.
One existing DEV A16 replay reproduced the exact output and phrase IDs with FVE
drift 1.34e-8, without generation, GPU work or API calls. A separate synthetic
N2 check then completed adapter-disabled capture, generation, eight new phrase
encodings and identical cache-only replay in 156 seconds on one H200. This
validates installed plumbing in the existing environment, not explanation
quality or a complete dependency installation on another machine.

## Resources and limits

- Four main H200 allocations: 25330001, 25330006, 25330007, 25417596.
- Both extra H200 allocations, 25460532 and 25459615, were intentionally
  released after their encoding and diagnostic work completed. Four main
  allocations remain available for the next scientifically authorized stage.
- Scoped CPU allocation 25481193 was released after offline validation work,
  with terminal cancellation confirmed at 09:07:04 UTC. It held sixteen physical
  cores and 80 GiB for 41 minutes 30 seconds; no judge or GPU job was affected.
- Fresh CPU allocation 25474685 provides eight physical cores and 32 GiB for
  judging through 21:25:37 UTC. The old allocation 25299630 reached its memory
  limit, predominantly in its external step; unrelated processes are preserved.
  Its existing lightweight watcher remains active and monitors the new allocation.
  A watcher checks every 600 seconds until 21:25:36 UTC; its process and last
  check are recorded under the fast project's `watcher/` directory. An agent
  stopping does not itself guarantee that this process remains healthy.
- Recorded API usage at 09:07:42 UTC: **$8.54072**, with **$4.63148** reserved,
  including **$4.59653** in unknown-charge holds. The ledger remains
  authoritative as work continues.
  The earlier cache-write pricing correction added $0.30592
  to settled usage and $0.02011 to unknown-request reservations; original events
  and the previous ledger snapshot are preserved. These are usage-based estimates,
  not reconciled invoice charges. Target $200; hard ceiling $300 including reservations.
- Shared O-lens cap: 32 samples/cell across all methods. Editing has its separate
  two-round/eight-proposal cap. No training or new activation sites.
- Project artifacts used 47.76 GB logical at 09:07:42 UTC: 35.69 GB on fast
  storage and 12.07 GB on durable storage. File-block allocation totals 38.56 GB;
  this is not a quota reading. The existing 55.56 GB base cache is reused without
  copying and excluded from those project totals. The projected final project
  footprint is roughly 80–100 GB. Aggregate allowance is 500 GB; lab group quota
  remains unresolved. See [the retention plan](experiments/storage-retention-plan.md).

The full-development judge queue later developed 21 connection failures and
21 cancellations during guard shutdown. All 42 uncertain holds remain reserved;
successful cached verdicts are preserved. The cause is unresolved: observed
CPU cgroup pressure and failure timing do not establish causation. A single
unchanged Luna request on the isolated CPU allocation succeeded in 2.29 seconds.
Recovery was authorized at eight slots and 200 requests/minute per family with a
new documented epoch, the same run cap, and all old holds retained. See experiment
019 and the immutable incident snapshot. No concurrency increase is automatic.

That fresh-CPU recovery settled its first 226 requests without transport errors,
then stalled. Workers were observed waiting on disk, and the chain worker exited
with a database-lock error. All three were gone by 06:49:52 UTC. Ten reservations
belonging to dead workers had no saved response evidence and must remain held as
unknown; no charge is released because a worker exits. A copied-ledger audit found
unindexed request-origin and reservation queries. Five indexes preserve exact
query results and accounting; the slowest measured local-copy lookup fell from
152.05 ms to 0.0116 ms. This does not establish NFS write/locking performance;
a bounded shared-storage check subsequently passed 30 accounting cycles across
three workers without lock errors. Production indexes were applied at 07:00 UTC
after an immutable backup. Accounting remained identical; ten abandoned requests
were separately marked unknown while retaining their full holds. The successful
07:01 health request supports the bounded recovery launched at 07:07, but sustained
throughput remains to be measured. See experiment 023 and the indexed recovery
specification `configs/judging_main_recovery_v2.json`.

Earlier, the donor judge run developed connection failures without provider status codes.
It was stopped, preserving cached successes and uncertain reservations. A
single-request check succeeded; an eight-slot restart with a shared transport
failure guard completed 2,110 physical requests without another transport
failure. The four subsequent diagnostic batches also completed without new
unknown requests. The original cause remains unresolved. No unknown charge was released.
Automatic approval review initially rejected the check/restart for missing
authorization context; root's exact-scope submissions with the existing user
authorization succeeded. This did not expand the model, endpoint, or data scope.

Generation measured roughly 4.2 GPU-seconds/cell at N32. Streaming reconstruction
measured about 98 new phrase vectors/s. These are batched task timings, not
single-request latency or a complete experiment forecast. The earlier overall
forecast was another 10–14 hours from approximately 02:40 UTC; reassess after the
full-grid judge throughput measurement. Standard judging now supports explicit
concurrency/rate limits; a bounded 32-slot/600 logical calls-per-minute pilot
completed without new unknown reservations. This is per family, not a promise
of provider capacity.

Blind preparation of the fixed validation pool can overlap development judging:
3,485 cells at N32 has a measured-component generation reference of about 63
minutes on four GPUs, plus loading and overhead. This is not a complete evaluation
forecast. Only operational counts, hashes, and timing may be inspected before
the development shortlist is frozen. A separate analysis gate is required for
validation export, reconstruction, selection, judging, and example inspection.
Test generation remains gated on the later validation decision.
All four generation workers are active. At 07:02 UTC, 1,167/3,485 cells were
complete. The observed rate of about 56 cells/minute suggests about 42 minutes
of generation remained then, excluding reconstruction, selectors and judging.

## Recovery and artifact map

Read [PLAN.md](PLAN.md), [METHODS.md](METHODS.md), and the latest experiment
records before continuing. Preserve the historical `mats/workspace` checkout.

- Fast models, environment, vectors, activations and watcher:
  `${OLENS_COMPUTE_ROOT}`.
- Durable stochastic text, judgments, analyses and budget ledger:
  `${OLENS_DATA_ROOT}`.
- Pilot: `runs/development-shared-pilot-v2`. Its original 22 authoritative arms
  use `judgments-standard-repair`; E3 uses `judgments`; B uses `judgments-b-v4`;
  editing uses `judgments-editing`; combinations use `judgments-combinations`;
  exact-support pooling uses `judgments-support-pooling`.
  Report exact condition roots and selection hashes, not a directory glob.
- Full development: immutable `runs/development-full-grid-v2`, baseline
  judgments in its `judgments-baselines` directory. Selector comparisons are
  pending. A parallel AR-cache extension preserved all keys and inherited
  vectors in a four-cell real fixture, with no changed best-of-32 winner.
  Its expanded 12-cell batch-size audit exceeded both provisional equivalence
  guards: maximum FVE drift .003524, with 0/12 best-of-32 winners, 2/12 pooled
  texts and 1/12 specificity-selected texts changing. Fixed B128 is accepted as
  a declared implementation, not as numerically equivalent to B32. All method
  arms share the same persisted vectors, batch/partition provenance is retained,
  and near-threshold decisions remain explicitly sensitive. Production is unchanged;
  validation/test access still requires a separate scientific stage gate.
- API ledger: `budget/ledger.sqlite3`. Retain the unknown $2 Claude review
  reservation and 80 unknown Flex attempts unless billing evidence resolves them.
- Runtime/allocation details: `configs/runtime.json`. Verify live state before
  restarting workers. Do not launch a second writer against the same AR cache or
  family judge cache.

Preserve completed samples, responses, manifests and reservations. Do not rerun
paid calls merely because their output exists in a different condition. Make
local reviewed commits; the user handles pushing. Finish the planned research
and report honestly rather than marking an unrun or time-limited method negative.
