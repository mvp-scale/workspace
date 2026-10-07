#!/bin/bash
# Install the top open Jev-class models for benchmarking, one isolated venv each, the same way every time.
#
#   ./dev-bench-setup.sh [laya|verdict|semif|so1|clef-flash|kev|jeff ...]   # default: laya verdict semif so1
#   JEV_ROOT=/some/dir ./dev-bench-setup.sh ...   # install somewhere other than /workspace
#
# Layout (all ignored by git):
#   $ROOT/models/<name>/.venv      isolated env (Python 3.12, CUDA torch, the model's own package)
#   $ROOT/models/<repo>            author's repo where the package needs one
#   $ROOT/data/models/hf-cache     shared HF cache (SemIf and so1 share Qwen3.5-4B)
# Idempotent: finished steps are skipped. Adapters in jevbench/jevbench/adapters/ import these packages.
set -euo pipefail

ROOT="${JEV_ROOT:-/workspace}"   # where models/ and data/ live; the Colab copy sets JEV_ROOT
export PATH="/root/.local/bin:$PATH"
M=$ROOT/models
export HF_HOME=$ROOT/data/models/hf-cache
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
  hf laya convaiinnovations/laya --local-dir $ROOT/data/models/laya
}
setup_verdict() {    # heman10x openJev Verdict 1.4, ModernBERT-base 151M (author's rlcd engine)
  clone Heman10x-NGU/openJev-verdict-2.0 openJev-verdict-2.0
  venv verdict
  "$(py verdict)" -c "import core.engine_encoder" 2>/dev/null || pip verdict -e "$M/openJev-verdict-2.0"
  hf verdict heman10x/rlcd-modernbert-151m --local-dir $ROOT/data/models/verdict
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

setup_clef_flash() { # Cloudflare Clef Flash, Qwen3.5-9B + joint schema head; card tested torch 2.11 / transformers 5.10.2
  venv clef-flash torch==2.11.0
  "$(py clef-flash)" -c "import transformers" 2>/dev/null || pip clef-flash transformers==5.10.2 huggingface_hub pillow accelerate safetensors torchvision --extra-index-url "https://download.pytorch.org/whl/$TORCH_CUDA_TAG"
  hf clef-flash Cloudflare/clef-flash --local-dir $ROOT/data/models/clef-flash
}

setup_clef_flash_q4km() { # bartowski Q4_K_M GGUF served by the official prebuilt llama.cpp b11430 (CUDA 12.8); needs a build with the clef architecture (PR 29831)
  local L=$M/llama-cpp-b11430; mkdir -p "$L" $ROOT/data/models/clef-flash-q4km
  [ -x "$L/llama-b11430/llama-server" ] || { (cd "$L" && gh release download b11430 --repo ggml-org/llama.cpp --pattern "llama-b11430-bin-ubuntu-cuda-12.8-x64.tar.gz" --pattern "cudart-llama-b11430-bin-ubuntu-cuda-12.8-x64.tar.gz" && for f in *.tar.gz; do tar xzf "$f"; done); }
  ln -sf llama-server "$L/llama-b11430/clef-flash-q4km"   # nvidia-smi shows the launch name: give each server its own
  "$M/clef-flash/.venv/bin/hf" download bartowski/Cloudflare_clef-flash-GGUF Cloudflare_clef-flash-Q4_K_M.gguf --local-dir $ROOT/data/models/clef-flash-q4km >/dev/null
}

setup_clef_flash_q2k() { # bartowski Q2_K GGUF (about 3.7 bits per weight, made without an imatrix); same llama.cpp b11430 as the Q4
  local L=$M/llama-cpp-b11430; mkdir -p "$L" $ROOT/data/models/clef-flash-q2k
  [ -x "$L/llama-b11430/llama-server" ] || setup_clef_flash_q4km
  ln -sf llama-server "$L/llama-b11430/clef-flash-q2k"
  "$M/clef-flash/.venv/bin/hf" download bartowski/Cloudflare_clef-flash-GGUF Cloudflare_clef-flash-Q2_K.gguf --local-dir $ROOT/data/models/clef-flash-q2k >/dev/null
}

setup_kev() {        # kev decision models (Qwen LoRA, pointer head): the repo, CUDA torch, and the 0.5b release; 0.8b and 4b come from the Hub when served
  [ -d "$ROOT/kev" ] || git clone -q --depth 1 https://github.com/jaredpalmer/kev.git "$ROOT/kev"
  [ -x "$ROOT/kev/.venv/bin/python" ] || (cd "$ROOT/kev" && uv sync -q --extra serve)
  "$ROOT/kev/.venv/bin/python" -c "import torch;assert torch.cuda.is_available()" 2>/dev/null ||
    uv pip install -q --python "$ROOT/kev/.venv/bin/python" torch --index-url "https://download.pytorch.org/whl/$TORCH_CUDA_TAG"
  mkdir -p "$ROOT/data/kev/runs" "$ROOT/data/kev/hf-cache"
  [ -d "$ROOT/data/kev/runs/kev" ] || { curl -fsSL https://github.com/jaredpalmer/kev/releases/download/v0.1.0/kev-0.5b.tar.gz | tar xz -C "$ROOT/data/kev/runs" && mv "$ROOT/data/kev/runs/kev-0.5b" "$ROOT/data/kev/runs/kev"; }
}
setup_jeff() {       # jeff: GLiFormer encoder server (Python 3.12 only)
  [ -d "$ROOT/jeff" ] || git clone -q --depth 1 https://github.com/logan-markewich/jeff.git "$ROOT/jeff"
  [ -x "$ROOT/jeff/.venv/bin/python" ] || (cd "$ROOT/jeff" && uv sync -q --extra dev)
  [ -d "$ROOT/data/jeff/models/gliformer-large-v1" ] || (cd "$ROOT/jeff" && uv run hf download knowledgator/gliformer-large-v1 --local-dir "$ROOT/data/jeff/models/gliformer-large-v1" >/dev/null)
}

verify() {  # import check + CUDA visibility for each installed env
  for n in "$@"; do
    local p; p="$(py "$n")"; [ "$n" = kev ] && p="$ROOT/kev/.venv/bin/python"; [ "$n" = jeff ] && p="$ROOT/jeff/.venv/bin/python"
    "$p" -c "import torch;print('$n ok  torch', torch.__version__, 'cuda', torch.cuda.is_available())" 2>&1 | tail -1
  done
}

targets=("$@"); [ ${#targets[@]} -eq 0 ] && targets=(laya verdict semif so1)
for t in "${targets[@]}"; do
  echo "=== $t ==="; "setup_${t//-/_}"
done
verify "${targets[@]}"
