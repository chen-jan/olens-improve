# 008: AR throughput and resumable development encoding

Status: fixed-input batch benchmark completed; one development streaming writer is active on extra H200 job 25460532. This changes encoding throughput, not the 32-sample O-lens cap. No production vector is overwritten, no new samples are generated, and no API calls are involved.

The benchmark froze 512 existing development scorer inputs: all atoms from the previous four deterministic layer-44 N16 diagnostic cells, then additional effective-input keys in hash order. It measured two timed passes at batch sizes 32, 64 and 128 after warm-up, excluding model loading. Tokens per pass include the six layer-tag tokens plus the actual scored span; padded token counts are also recorded. Per-row tag metadata now uses the saved CPU tag IDs, avoiding repeated GPU synchronization without changing the forward computation.

| AR batch size | Vectors/second, two passes | Effective tokens/second | Peak allocated GPU memory |
|---|---|---:|---:|
| 32 | 80.9, 81.7 | approximately 2,330–2,353 | 49.3 GiB |
| 64 | 91.6, 91.7 | approximately 2,639 | 50.4 GiB |
| 128 | 98.8, 98.8 | approximately 2,845 | 52.4 GiB |

Batch 128 was roughly 21% faster than batch 32 on this workload. All four N16 winners remained unchanged at every batch size. Batch-128 FVE differences from immutable original vectors reached .001713; ranking correlations were at least .9941. This small stability audit supports proceeding, not proof of invariant rankings across the bank. The .001 pruning threshold remains sensitive on this numerical scale; the .005 comparison is retained. Detailed timings, texts, input keys, memory, scores, ranks and diagnostic vectors are under `${OLENS_COMPUTE_ROOT}/runs/ar-throughput-v1`.

Root approved **fixed batch 128 for new development vectors**. Existing first-computed batch-32 vectors remain immutable and are shared by every method. New vector index entries record actual batch size, padded width, ordered-batch-key hash and source usage ID. Thus mixed historical/new batches are explicit and common across arms; no candidate receives a favorable recomputed score.

`scripts/stream_ar.py` reads only complete-line prefixes of the append-only generation journals and freezes complete 0–31 sample pools for development cells. Each immutable flat snapshot records its SHA, cell set and each parent journal's committed-byte boundary/hash. It never treats a partially written line or incomplete pool as complete. A locked single writer reuses one loaded frozen AR, stores completed raw-vector shards atomically and updates a resumable completed-cell state. On preemption, completed shards survive; uncommitted work is regenerated and existing vectors are preserved. No permanently duplicated whitened vectors are stored.

The writer consumes `configs/development-full-grid-v2.json`; validation/test cells are excluded. Its snapshots and state are at `${OLENS_DATA_ROOT}/runs/development-ar-stream-v1`, and its log is `${OLENS_COMPUTE_ROOT}/logs/stream_ar_v1.log`. The first snapshot contains 2,079 complete cells and requests 228,818 previously missing vectors. Completion forecasts should use observed streaming throughput, remaining generation counts and the actual cache backlog, not assume the short benchmark applies perfectly.

Editing uses a separate single-writer cache and reads production vectors without modifying them. Its keys obey the same model/head/tokenizer/span contract. This avoids shared-writer races while retaining all proposal lineage and original text. A cache hit is equality of scorer inputs, never semantic equivalence or proof of an edited claim.
