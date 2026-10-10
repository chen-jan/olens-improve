# Artifact storage and retention plan

Observed 2026-10-10 09:07:42 UTC. This is an inventory and proposed retention policy; nothing has been deleted. Values below use decimal GB. The persistent watcher counted only the two project-owned trees, excluded symlinks, and deduplicated hardlinks by device/inode. Its existing traversal was extended to report each root separately, without an additional scan.

| Project-owned location | Logical bytes | GB | File-block bytes | Files |
|---|---:|---:|---:|---:|
| Fast: `${OLENS_COMPUTE_ROOT}` | 35,685,824,681 | 35.69 | 35,699,388,416 | 5,613 |
| Durable: `${OLENS_DATA_ROOT}` | 12,069,825,936 | 12.07 | 2,861,761,536 | 4,038 |
| Combined | 47,755,650,617 | **47.76** | 38,561,149,952 | 9,651 |

The file-block count is `stat.st_blocks * 512`, not an authoritative lab quota reading. Logical and allocated sizes differ markedly on the durable filesystem; this inventory does not establish why or equate the difference with reclaimable quota. Group quota access remains unresolved because the quota client encounters an unrelated stale NFS mount. The 500 GB aggregate authorization is a spending limit for storage, not proof of available group capacity. Neither location is a backup.

Provenance: the 09:07:42 entry in `fast/watcher/history.jsonl`, produced by `infra/watch_resources.py`; both root counters are complete. The snapshot reported zero alerts and the persistent loop completed successfully at 09:07:45. Live generation and judging can increase these figures.

## Files inside that total

These are selected direct-file inventories of known paths, not an exhaustive independent total. Do not add them again to the combined footprint.

| Artifact | Location | Observed logical size | Retention |
|---|---|---:|---|
| DEV raw reconstructor vectors | `fast/vectors/shared-global-v1/a451cf49d28ac7447722/raw_*.safetensors` | 13.15 GB, 158 shards | Keep canonical shards, indices, contracts and usage provenance |
| VAL raw reconstructor vectors | `fast/vectors/validation-partitions-v1/worker-{0..3}/a451cf49d28ac7447722/raw_*.safetensors` | 8.64 GB, 104 shards | Keep all worker shards; the catalog depends on them |
| Combined VAL/DEV catalog | `fast/vectors/validation-catalog-v1` | 1.00 GB of indices/provenance | Keep; it references vectors rather than copying their tensors |
| Fresh core activations | `fast/activations/core-v1/activations.safetensors` | 0.398 GB | Keep exact FP32 activations and capture/render provenance |
| Matched whitening files | `fast/cache/huggingface/hub/datasets--agu18dec--local-workspace/blobs` | 1.154 GB | Keep pinned files needed to reproduce scoring |
| Oracle Lens / reconstructor artifacts | `fast/cache/huggingface/hub/models--agu18dec--olens_and_ar/blobs` | 1.039 GB | Keep pinned adapters/configuration |
| Independent J++ artifact | `fast/cache/huggingface/hub/models--koayon--jpp-lenses/blobs` | 6.606 GB | Retain for documented DEV diagnostics; optional later removal after preserving revision/fixture evidence |
| Live stochastic journals | `durable/readouts/shared-global-v1/shard-*.jsonl` | 0.527 GB at the direct-file check | Always retain final complete records and order; grows during TEST |
| Authoritative financial ledger | `durable/budget/ledger.sqlite3` | 0.774 GB at the direct-file check | Always retain, including unknown holds, responses and correction history |

The three project-owned Hugging Face blob groups total 8.799 GB and are already included in fast storage. Their snapshot symlinks must not be counted as additional copies. The raw-vector indices and per-run usage mappings are necessary to map cached columns back to source phrases; saving a catalog alone is insufficient.

## Reused external material

The base model is outside this project at the read-only historical cache referenced by `configs/runtime.json` under `paths.base_snapshot`. Its pinned `model.safetensors.index.json` reports **55,562,855,904 bytes across 15 weight shards**. Those 55.56 GB were not downloaded again and are excluded from project-owned totals. The reused historical site-packages directory is also external; this inventory does not scan or size it. The project-owned environment/overlay and any newly installed packages are included in fast storage. External weights, environments and old project data remain untouched.

## Retain after the report

Keep the expensive stochastic evidence: original shared journals, immutable DEV/VAL/TEST snapshots, exact samples and seeds, chunk order, activation hashes, source revisions, gates, and complete terminal status records. Keep paid helper and judge responses, exact-cache origins, budget attempts and unknown holds. Retain the final exact-text evaluation exports and source manifests, reviewed selections, paired analysis artifacts, failure examples, and report/dashboard sources.

Keep canonical vector shards and their indices while any catalog or reproducibility claim depends on them. Before removing fast artifacts, either archive their required canonical files to the durable project location or explicitly document that later replay needs re-encoding. A zero-copy catalog does not make its source shards durable. Future replay may reproduce stochastic samples from retained strings but not reliably regenerate the same samples by drawing again; numerical batching sensitivity also limits claims of identical re-encoding.

## Optional cleanup only after final review

Candidates are disposable synthetic SQLite load-test copies, temporary browser profiles, package-build intermediates, isolated throughput/fixture vector caches, and superseded expanded traces that have an approved complete canonical replacement. Preserve compact reports, hashes, accounting snapshots, numerical fixtures and incident evidence before considering their associated temporary copies. Failed selector v2/v3 journals and their initial costs remain forensic evidence; do not discard them merely because v4 succeeded.

Capture shards duplicate the merged activation tensor and might be removable only after the merged tensor, cell mapping and hashes are verified and the capture audit is retained. Expanded selector journals may be archived or compressed after a lossless source-bound export, but final texts and provenance must remain byte-exact. Do not clean active sample journals, live caches, financial state, source shards referenced by a catalog, or any historical external cache. No cleanup is needed to keep the current 47.76 GB within the authorized 500 GB.

## Remaining storage estimate

TEST has 10,714 cells. At the maximum 32 samples and four unique scored bullets per sample, FP32 width-5120 vectors require `10,714 * 32 * 4 * 5,120 * 4 = 28,085,780,480` bytes, about **28.09 GB**, before indices and provenance. Deduplication, parsing exclusions and shorter bullet lists can reduce this. The bound concerns primary candidate vectors, not an unlimited set of extra diagnostic encodings.

Adding that maximum to the observed footprint gives 75.84 GB before future indices, outputs, judgments and archival copies. A working estimate of **80–100 GB** is reasonable for the current stage design; retaining many duplicate expanded traces or extra archives can raise it. This is an estimate, not a reservation or guarantee. Preserve the 500 GB aggregate limit and ask before exceeding it. No new base-model copy is required.
