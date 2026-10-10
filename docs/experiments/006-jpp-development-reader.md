# Experiment 006: independent J++ development reader

Status: source fixture and eight-cell lexical diagnostic completed. This does
not establish a method improvement, semantic accuracy, or clean held-out result.

Pinned source revision is `93f02cd6c27db765abb127f20eff656bb5d27340`; the
`koayon/jpp-lenses` revision is `6c96867a91c43c14cec17cf0f6d157b933c5fee5`.
The downloaded `qwen3.6-27b/lens.pt` has 6,606,048,507 bytes and SHA256
`adc103d4e724d04e721b019ecafa1388ff376541db3ecb78f693e60ed1d8609d`.
Actual checkpoint contents provide maps for zero-based block-output layers
0–62, width 5120, final-layer transport, and a fitting stamp with 64 prompts,
maximum sequence length 128, `lrp_mode=rlens`, and creation time
`2026-09-07_23-46-18`. The exact fitting groups remain unresolved; J++ stays
excluded from clean held-out headlines and final composites.

The minimal reader loads only requested FP32 matrices and the frozen base's
final Qwen RMS norm plus unembedding, directly from existing safetensors shards.
It instantiates no complete 27B model and generates no additional readouts.
The operation matches the pinned source: residual @ map.T, then BF16 casting
before the original Qwen norm (including its 1+weight rule) and BF16 LM head.
CPU and H200 fixtures compared layers 20, 44, and 60 against actual pinned
`BaseLens.transport` and `HFLensModel.unembed`: exact transport tensors,
zero maximum vocabulary-logit difference, and identical top-10 tokens.
Fixtures: fast `logs/jpp_source_fixture{,_cuda}.json`.

Eight existing development instrument cells then used their unchanged first
eight persisted sample strings. Frozen target hashes were checked against the
fresh FP32 index and candidate pool. The diagnostic records ranks/log
probabilities for number and capitalized source spans, each tokenized both
standalone and with one leading space, plus unfiltered top vocabulary tokens.
This bounded span heuristic includes some sentence-initial grammar words; it
is not named-entity recognition. Multi-token entity/number component ranks do
not provide a joint sequence probability or verify the exact value. Token
presence does not prove a relation, and absence does not imply falsehood.

Durable output: `independent/jpp-instrument8-v1/{run,status}.json` and
`diagnostics.jsonl`, SHA256
`2a4f2c034e4a13bb80dd376d29a523ace53fccb05f039ad6da7a46b3c08f2d13`.
The eight complete cell records are individually flushed/fsynced; an
interrupted run resumes existing complete rows and logs uncommitted crash-tail
loss. It rejects validation/test cells while fitting overlap is unresolved.
No gold answers, judge verdicts, paid APIs, or cross-cell candidate summaries
were used. Diagnostic H200 job 25459615 was released to the model worker
after completion; its allocation remains available for useful F/AR work.
