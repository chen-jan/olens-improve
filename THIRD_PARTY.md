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
