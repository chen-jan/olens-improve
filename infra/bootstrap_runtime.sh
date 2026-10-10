#!/usr/bin/env bash
set -euo pipefail
project_root=${OLENS_REPO_ROOT}
runtime_root=${OLENS_COMPUTE_ROOT}
existing_env=${OLENS_SCRATCH}/workspace/venvs/lens
export UV_CACHE_DIR="$runtime_root/cache/uv"
export PIP_CACHE_DIR="$runtime_root/cache/pip"
export HF_HOME="$runtime_root/cache/huggingface"
export TORCH_HOME="$runtime_root/cache/torch"
mkdir -p "$UV_CACHE_DIR"
if [[ ! -x "$runtime_root/envs/runtime/bin/python" ]]; then
  ${HOME}/.local/bin/uv venv --python "$existing_env/bin/python" "$runtime_root/envs/runtime"
fi
runtime_python="$runtime_root/envs/runtime/bin/python"
"$runtime_python" - "$existing_env" <<'PY'
import pathlib, site, sys
source = pathlib.Path(sys.argv[1]) / 'lib/python3.12/site-packages'
destination = pathlib.Path(site.getsitepackages()[0]) / 'readonly_lens_dependencies.pth'
destination.write_text(str(source) + '\n')
PY
${HOME}/.local/bin/uv pip install --python "$runtime_python" --no-deps peft==0.21.2 scipy==1.18.1
${HOME}/.local/bin/uv pip install --python "$runtime_python" --no-deps --no-build-isolation -e "$project_root"
"$runtime_python" - <<'PY'
from importlib.metadata import version, PackageNotFoundError
import json
packages = ['torch', 'transformers', 'peft', 'safetensors', 'accelerate', 'huggingface_hub', 'numpy', 'scipy', 'openai', 'pydra', 'setuptools', 'olens-improve']
versions = {}
for package in packages:
    try:
        versions[package] = version(package)
    except PackageNotFoundError:
        versions[package] = None
print(json.dumps(versions, indent=2))
import torch, transformers, peft, scipy, numpy, olens_improve
print('Runtime imports verified; weights not loaded.')
PY
