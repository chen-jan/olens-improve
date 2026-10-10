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

## Expanded paired diagnostic

The frozen E2 manifest was read in isolation: 36 ordered pairs, 72 target entries,
and 45 unique development cells at layers 20, 44 and 60. Existing fresh adapter-free
activations were reused. No samples or API responses were generated. The run on
H200 job 25459615 finished successfully; the GPU was released immediately for the
editing audit. All phrase components, changed source spans, generic controls,
leading-space variants and unfiltered top tokens remain in the external artifact.

Artifact: `${OLENS_DATA_ROOT}/diagnostics/jpp-e2-expanded-v1/results.json`,
SHA256 `9dbcd9bf320223932d28803466acd2a43d32f75c595e5c3ae431c31604a3e416`. Its E2 source manifest SHA256 is
`9f050c9d0f6ef3393f281bffc35b55e03e08d0d27cf869fd047b32e86755958f`. The pinned source fixture and lens hashes are preserved
in the artifact. These pairs overlap across layers and variants; 72 entries are
not 72 independent observations.

The numeric strings decompose into digit tokens, so a rank of a component is not
a prediction of the whole number. At layer 44, the 11-versus-12 pair gives digit 2
a better rank than digit 1 on both targets (98 versus 252 for the 11 target; 79
versus 213 for the 12 target). The 12-versus-10 pair also prefers digit 2 over
digit 0 on both targets. The 5-versus-15 pair shares the same digit 5 and differs
by the extra digit 1. These examples do not establish a usable whole-number
verifier; no composite numeric probability or accuracy is reported.

All 12 abstract role-direction pairs have identical full-phrase token multisets
for their opposing descriptions. An unordered token-support aggregate cannot
distinguish their directions. Named descriptions can change tokenization through
position/capitalization, but component presence still cannot verify who acted on
whom. Fitting-group overlap remains unresolved; this is a development diagnostic
and does not enter clean held-out headlines or candidate/editor feedback.
