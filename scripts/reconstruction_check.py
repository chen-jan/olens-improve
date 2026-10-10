"""Compare the local math with exact functions extracted from pinned upstream source."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

import torch
from olens_improve.reconstruction import JointNNLS, whitening_matrix


def source_functions(path, names):
    tree = ast.parse(path.read_text())
    functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    for f in functions:
        f.returns = None
        for arg in f.args.posonlyargs + f.args.args + f.args.kwonlyargs:
            arg.annotation = None
    namespace = {"torch": torch}
    module = ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    return namespace


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    root = Path(args.source) / "src/oracle_lens/core"
    whitening_source = source_functions(root / "whitening.py", {"whitening_matrix"})
    fit_source = source_functions(root / "nnomp.py", {"_nnls_batched", "nnls_refit"})
    torch.manual_seed(71)
    torch.set_num_threads(2)
    cases, max_w_error, max_fve_error, largest_exact_gap = 0, 0.0, 0.0, 0.0
    for dimensions in (3, 7, 12):
        for rank_deficient in (False, True):
            a = torch.randn(dimensions, 2 if rank_deficient else dimensions)
            cov = a @ a.T
            ours = whitening_matrix(cov)
            original = whitening_source["whitening_matrix"](cov, ridge_c=.1)
            max_w_error = max(max_w_error, float((ours-original).abs().max()))
            assert torch.allclose(ours, original, atol=1e-6, rtol=1e-6)
            for k in (1, 2, 4):
                x = torch.randn(dimensions)
                vectors = torch.nn.functional.normalize(torch.randn(k, dimensions), dim=1)
                original_c, original_f = fit_source["nnls_refit"](
                    vectors[None], x[None], torch.ones((1,k), dtype=torch.bool))
                ids = tuple(map(str, range(k)))
                dictionary = dict(zip(ids, vectors))
                ours_fit = JointNNLS(x, dictionary, solver="released80").fit(ids)
                max_fve_error = max(max_fve_error, abs(ours_fit.fve-float(original_f[0])))
                assert abs(ours_fit.fve-float(original_f[0])) < 2e-6
                assert torch.allclose(torch.tensor(ours_fit.coefficients), original_c[0], atol=2e-6)
                exact = JointNNLS(x, dictionary, solver="scipy_exact").fit(ids)
                gap = exact.fve-ours_fit.fve
                assert gap > -2e-6
                largest_exact_gap = max(largest_exact_gap, gap)
                cases += 1
    result = {"status": "source-math-fixture-passed-not-artifact-validated", "cases": cases,
              "source_revision": "a32590085a6070d75f950155d3c2b3db3eec97ef",
              "max_whitening_error": max_w_error, "max_fve_error": max_fve_error,
              "largest_exact_solver_gain": largest_exact_gap,
              "source_file_sha256": {f:hashlib.sha256((root/f).read_bytes()).hexdigest()
                                     for f in ("whitening.py", "nnomp.py")},
              "scope": "Mathematical source fixture; actual artifact/AR fixtures are separate"}
    Path(args.output).write_text(json.dumps(result, indent=2)+"\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
