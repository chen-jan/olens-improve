# Upstream source and artifact attribution

The readout carrier, read plans, evaluation contracts, and related inference code follow [Camila Blank's WorkspaceBench](https://github.com/camilablank/workspace-bench), pinned to `92d763e722377f5bfae045e829a308ab5919a820`. Its source is MIT licensed, copyright (c) 2026 Camila Blank.

Whitening, the released finite-iteration nonnegative fit, and reconstructor conventions follow [Agam Bhatia's Oracle Lens research source](https://github.com/agu18dec/olens_draft), pinned to `a32590085a6070d75f950155d3c2b3db3eec97ef`. Its first-party source is MIT licensed, copyright (c) 2026 Agam Bhatia. We do not redistribute its separate vendored training dependencies. Source comparisons and any numerical deviations are recorded with experiment artifacts.

The MIT license text below applies to the upstream-derived portions under their respective notices above:

> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

Model weights, adapters, whitening statistics, and benchmark data remain external artifacts under their original terms. Their identities and revisions are recorded in `configs/project.json` and run manifests. No weights or gated research archive are included in this Git repository.

The development-only J++ reader follows [Kola Ayonrinde's J++ Lens](https://github.com/koayon/jpp_lens), pinned to `93f02cd6c27db765abb127f20eff656bb5d27340`. Its actual pinned LICENSE is Apache-2.0, and its NOTICE credits copyright 2026 Kola Ayonrinde, Anthropic's Jacobian lens, and Camila Blank and Agam Bhatia's R-Lens. Exact upstream notices are preserved in [third_party/jpp_lens/LICENSE](third_party/jpp_lens/LICENSE) and [third_party/jpp_lens/NOTICE](third_party/jpp_lens/NOTICE). Our reader replaces the full model loader with selected frozen transport maps and the base final norm/unembedding, and adds source-span diagnostics and provenance checks; numerical equivalence is verified against the pinned upstream transport/unembedding fixture. No upstream fitting implementation or evaluation data is redistributed here.

The external `koayon/jpp-lenses` Qwen checkpoint is pinned to `6c96867a91c43c14cec17cf0f6d157b933c5fee5`; its artifact hash and fitting-overlap limitation are recorded in experiment 006. Source licensing does not resolve fitting-group provenance or authorize a clean held-out claim.
