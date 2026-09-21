#!/bin/bash
# Install the top open Jev-class models for benchmarking, one isolated venv each, the same way every time.
#
#   ./dev-bench-setup.sh [laya|verdict|semif|so1 ...]   # default: all
#
# Layout (all ignored by git):
#   /workspace/models/<name>/.venv      isolated env (Python 3.12, CUDA torch, the model's own package)
#   /workspace/models/<repo>            author's repo where the package needs one
#   /workspace/data/models/hf-cache     shared HF cache (SemIf and so1 share Qwen3.5-4B)
# Idempotent: finished steps are skipped. Adapters in jevbench/jevbench/adapters/ import these packages.
set -euo pipefail

export PATH="/root/.local/bin:$PATH"
M=/workspace/models
export HF_HOME=/workspace/data/models/hf-cache
TORCH_CUDA_TAG="${TORCH_CUDA_TAG:-cu128}"   # RTX 5090 (Blackwell) needs cu128+
mkdir -p "$M" "$HF_HOME"

# venv <name> [torch-spec]  -> creates $M/<name>/.venv with CUDA torch
venv() {
  local name=$1 torch=${2:-torch}
  mkdir -p "$M/$name"
  [ -x "$M/$name/.venv/bin/python" ] || uv venv -q --python 3.12 "$M/$name/.venv"
  "$M/$name/.venv/bin/python" -c "import torch" 2>/dev/null ||
    uv pip install -q --python "$M/$name/.venv/bin/python" "$torch" --index-url "https://download.pytorch.org/whl/$TORCH_CUDA_TAG"
}
py()  { echo "$M/$1/.venv/bin/python"; }
pip() { local n=$1; shift; uv pip install -q --python "$(py "$n")" "$@"; }
clone() { [ -d "$M/$2" ] || git clone -q --depth 1 "https://github.com/$1.git" "$M/$2"; }
hf() { local n=$1; shift; "$M/$n/.venv/bin/hf" download "$@" >/dev/null; }

setup_laya() {       # Convai Innovations, ModernBERT-large 421M
  venv laya
  "$(py laya)" -c "import laya" 2>/dev/null || pip laya laya
  hf laya convaiinnovations/laya --local-dir /workspace/data/models/laya
}
setup_verdict() {    # heman10x openJev Verdict 1.4, ModernBERT-base 151M (author's rlcd engine)
  clone Heman10x-NGU/openJev-verdict-2.0 openJev-verdict-2.0
  venv verdict
  "$(py verdict)" -c "import core.engine_encoder" 2>/dev/null || pip verdict -e "$M/openJev-verdict-2.0"
  hf verdict heman10x/rlcd-modernbert-151m --local-dir /workspace/data/models/verdict
}
setup_semif() {      # TheoLeeCJ SemIf (formerly OpenJev), Qwen3.5-4B; repo pins torch==2.10.0
  clone TheoLeeCJ/openjev openjev
  venv semif torch==2.10.0
  "$(py semif)" -c "import semif_phase1" 2>/dev/null || pip semif -e "$M/openjev"
  hf semif Qwen/Qwen3.5-4B
}
setup_so1() {        # IkerMoel open-alternative-jev, Qwen3.5-4B
  clone ikermoel/open-alternative-jev open-alternative-jev
  venv so1
  "$(py so1)" -c "import so1" 2>/dev/null || pip so1 -e "$M/open-alternative-jev"
  hf so1 Qwen/Qwen3.5-4B
}

verify() {  # import check + CUDA visibility for each installed env
  for n in "$@"; do
    "$(py "$n")" -c "import torch;print('$n ok  torch', torch.__version__, 'cuda', torch.cuda.is_available())" 2>&1 | tail -1
  done
}

targets=("$@"); [ ${#targets[@]} -eq 0 ] && targets=(laya verdict semif so1)
for t in "${targets[@]}"; do
  echo "=== $t ==="; "setup_$t"
done
verify "${targets[@]}"
