# Completed expanded Oracle Lens study

The [public dashboard](https://olens-improve-research.jan618.chatgpt.site) now shows all **70 settings on all four complete benchmark banks**: 469 questions and 19,435 fixed activation sites. Version 18 preserves the original study separately; the [original delivery record](ORIGINAL_DELIVERY.md) is retained.

- [Final report](https://olens-improve-research.jan618.chatgpt.site/downloads/expanded-report.md)
- [Slides — PDF](https://olens-improve-research.jan618.chatgpt.site/downloads/expanded-slides.pdf)
- [Slides — PowerPoint](https://olens-improve-research.jan618.chatgpt.site/downloads/expanded-slides.pptx)
- [Detailed slide notes](https://olens-improve-research.jan618.chatgpt.site/downloads/expanded-speaker-notes.md)
- [Full benchmark results](https://olens-improve-research.jan618.chatgpt.site/downloads/expanded-native-results.json)
- [Full reconstruction results](https://olens-improve-research.jan618.chatgpt.site/downloads/expanded-reconstruction.json)
- [Final resource accounting](https://olens-improve-research.jan618.chatgpt.site/downloads/expanded-resource-supplement.json)

The revised deck has 27 main slides and 67 detail/appendix slides. Plain method explanations and a guide to sample counts, thresholds and editing rounds precede the results. Every task result explicitly references the original released lens; the four-bullet original remains a separate comparator. Every approach has a visual explanation and four-task results; appendices retain every setting, recorded comparison and reconstruction result. Each method also has task-specific interpretation and a source-bound qualitative example. The dashboard includes sampling curves, paired comparisons, uncertainty, costs and 2,206 audited case entries, including preserved earlier entries.

## Clearer charts and original-reference comparisons

The [sample curves](https://olens-improve-research.jan618.chatgpt.site/#sample-trends) show all six sample counts. The [intervention view](https://olens-improve-research.jan618.chatgpt.site/#intervention-effects) shows one approach at a time, with paired changes versus the original Oracle Lens, uncertainty bars, hover previews and enlarged plots. Other approaches are hidden when one is selected. All methods and variants remain available below.

Task names match the WorkspaceBench registry: **Hallucination (chat)**, **Multihop (multi-token)**, **Chained intermediates**, and **Role-bound association**. The [original-reference supplement](https://olens-improve-research.jan618.chatgpt.site/downloads/original-reference-comparisons.json) adds 28 direct paired comparisons for the seven fixed representatives. These are post-hoc exploratory pointwise intervals, separate from the original simultaneous analysis. Frozen sources and judgments are unchanged. See [experiment 063](experiments/063-clear-graphs-and-original-reference.md).

## Findings

Higher reconstruction fit does not consistently improve useful recovery. Best-of-32 improves explained activation variance by 3.7–6.7 percentage points relative to one capped sample. Pooling adds another 2.0–2.5 points beyond best-of-32, while intermediate-number recovery decreases from 61/120 to 53/120 questions. This last comparison is descriptive; its directly paired quality interval is not recorded.

Pruning reduces transcript contradictions with small fit losses, but can remove important names. Strict consensus removes errors and much useful information. Two editing rounds add only 0.002–0.096 fit points beyond pooling, with unchanged recovery totals on the three recovery tasks. Selected edits change 445 of 19,435 final cell texts; examples that retain a pooled parent are not evidence that editing made the parent's gains.

All expanded results are exploratory because the questions were previously inspected. The finite comparison menu contains 496 contrasts; 451 have nondegenerate simultaneous intervals. Undefined and zero-variation intervals are not proof of certainty or equivalence. A recovered name, ranked integer or relation can coexist with false surrounding prose. Independent readers remain postponed, and this is not the full 25-family WorkspaceBench suite.

## Resources and verification

Recorded provider-usage estimates total **$142.73**, including **$106.22** for the expansion. Another **$5.07** remains reserved or uncertain; these holds were preserved. Figures are not invoice-reconciled charges.

The expansion used **5.825 allocated H200-hours** and **225.662 allocated host CPU core-hours**, including host CPUs in the GPU allocation. The original study recorded 70.220 project-held H200-hours through its documented handoff; combined nonoverlapping GPU allocation time is approximately 76.045 hours. These are allocation measures, not measured kernel activity. Dollar prices for cluster compute are unavailable.

The final scoped project snapshot records approximately **123.07 GB logical storage**, **94.18 GB allocated blocks**, and 18,583 files across the compute and durable project roots. Shared external model weights are excluded. All owned expansion allocations have been released; user-owned jobs were untouched.

Strict coverage checks, exact source bindings, independent quantitative and qualitative reviews, and the original delivery checks passed. The clearer presentation additionally passed actual 22-view dashboard browser checks and 94-page slide layout/PDF checks. Selected public assets were downloaded and compared with local hashes. The PDF uses the same-content HTML slide geometry; native PowerPoint rendering has not been independently validated.

Research changes are committed locally; the research GitHub repository was not pushed. The separate authorized Sites repository was published through the Sites workflow.
