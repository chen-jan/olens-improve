# Descriptive maps of the original read sites

Status: DEV/VAL computation and five focused tests complete; root reviewed the scientific logic and verified summed slot counts against the complete family endpoints. Figures-only v2 is ready for final presentation review. These maps describe already measured outputs. They neither choose layers nor change the frozen methods, read sites or TEST menu. No TEST outcomes were accessed.

## Question and comparison

How do the existing endpoint rates and output coverage vary across the original layers and positions? Development compares capped N1, best reconstruction N16 and N32 on all 5,236 cells. Validation adds mean matched-control selection N32 on all 3,485 cells. The exact cohorts and condition sources are frozen in [descriptive_grid_sources_v1.json](../../configs/descriptive_grid_sources_v1.json), SHA `6645578caed5b546e5b4a1235b880f4eb71fb6024d0633e3818c39020d1a977d`.

The horizontal coordinate is the rank of a selected token position within its item, not an aligned absolute token or semantic location across items. Later ranks can contain fewer items. Multi-hop and chains each have one selected position; hallucination has up to eight and role binding nineteen. All original layers remain visible. Outside-grid or undefined rates are masked rather than plotted as zero.

## Measures and evidence

Each slot retains expected/accounted cell counts, item and related-group counts, absolute-position range, endpoint numerator/denominator, empty share and a 95% related-group bootstrap interval. Hallucination uses wrong / (wrong + off-topic + consistent), with assertion and off-topic shares separately retained. Other families use their original recovery endpoint over intended cells. Both hallucination stages and required result coverage must be complete before a condition is plotted. A numerical or name hit still need not be a correct explanation.

The bootstrap resamples whole related groups, preserves all member cells, and uses 2,000 draws with seed 20261010. These per-slot intervals are exploratory and unadjusted for inspecting many sites. Chains have only seven related groups in each split; role maps have fifteen in DEV and ten in VAL. Rates can therefore look detailed while having little independent evidence.

The immutable artifact is `${OLENS_DATA_ROOT}/analysis/descriptive-grid-dev-val-v1/grid-audit.json`, SHA `a4ff4c0d0e8fb04c34b419527485be49a34b6169b580ab8bd1b188ded4fa5c6c`. It records every source and all sixteen figure hashes. The same directory contains PNG and PDF figures for each split/family; files are read-only. Source hashes were checked before and after outcome loading. The validation authority and reviewed signed report are verified before accessing its outcomes.

As one descriptive example, validation chain recovery at layer 36 is 4/20 for N16 and 1/20 for N32; at layer 44 it is 2/20 versus 4/20. More samples do not improve every site. This observation provides no basis for choosing a TEST layer, and its uncertainty is retained in the artifact.

## Reproduction and limits

[descriptive_grid_audit.py](../../scripts/descriptive_grid_audit.py) has SHA `19204ae54594964ba17af0eb59727224d08ce21df834242a91435e5af8a2a0a2`. Run it on allocated CPU with `--sources`, `--expected-sha256` and a fresh `--output` directory. [The tests](../../tests/test_descriptive_grid_audit.py), SHA `f1c1f63b41d8fbe1473306874f1fa5bb7691342a052fb3e91ccb701fc9d80e57`, check missing-versus-zero handling, whole-group resampling, deterministic weighted ratios, undefined denominators and TEST rejection before data access. All five passed.

This analysis used two allocated CPU cores, no GPU work, API calls or ledger access. DEV and VAL maps describe different item banks and are not paired cross-split comparisons. TEST is unsupported by this utility until a separate complete, reviewed source is authorized. Publish these as an appendix with their count/uncertainty caveats; no site or operating-point selection follows from them.

## Clearer figure labels, version 2

[render_descriptive_grid.py](../../scripts/render_descriptive_grid.py) reads only the immutable v1 grid artifact. It preserves every metric, interval and original figure, without loading bank outputs or recomputing scores. The new panels use plain method names. Where space permits, each slot shows its percentage and actual endpoint numerator/denominator: for example, `43%` and `12/28`, rather than the intended number of sites. This matters for hallucination because generic and empty outputs are excluded from its official contradiction denominator. Role maps retain all nineteen position ranks; exact counts remain in the source JSON.

Sixteen new PNG/PDF files are in `${OLENS_DATA_ROOT}/analysis/descriptive-grid-dev-val-v2/`. Their immutable `figure-provenance.json`, SHA `a9b3728db917c6e31fcff4dcdbd296c5d245833f76f59153f8797cf0baa7c94a`, binds all figure hashes, the renderer and unchanged v1 source SHA. Three offline tests passed for correct denominator labels, undefined rates remaining masked, and TEST rejection before rendering. The validation hallucination and role figures were visually checked at original resolution. Their labels and footers are readable, and position ranks remain explicitly unaligned across items.

Root reviewed the scientific aggregation and figure labels; [descriptive_grid_review_v1.json](../../configs/descriptive_grid_review_v1.json) binds the immutable sources and figure hashes. These are approved descriptive appendix artifacts, with no TEST read or change to selected sites.
