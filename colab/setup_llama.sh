#!/bin/bash
# Put a llama-server that supports Clef (build b11430 or newer) at $LLAMA_DIR/llama-server and print its path.
#
#   T4 (sm_75):  LLAMA_T4_URL=<url of llama-b11430-t4.tar.gz> ./setup_llama.sh    prebuilt with real sm_75 code
#   L4 / RTX 30-50 series:                    ./setup_llama.sh                    the official release already has native code for sm_86/89/120
#   anything else (A100 etc.) uses the official release, whose PTX the driver compiles on first start (slow once, needs a recent driver)
#   BUILD=1 ./setup_llama.sh                                                       build from source for this GPU: about 6 min on 20 cores, so about an hour on Colab's 2
set -euo pipefail
TAG=${TAG:-b11430}; LLAMA_DIR=${LLAMA_DIR:-$PWD/llama}; mkdir -p "$LLAMA_DIR"; cd "$LLAMA_DIR"
cc=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader 2>/dev/null | head -1 | tr -d . || true)
if [ -x "$LLAMA_DIR/bin/llama-server" ]; then echo "$LLAMA_DIR/bin/llama-server"; exit 0; fi
mkdir -p bin
if [ "${BUILD:-0}" = 1 ]; then
  export PATH=/usr/local/cuda/bin:$PATH CUDACXX=/usr/local/cuda/bin/nvcc
  [ -d src ] || git clone -q --depth 1 --branch "$TAG" https://github.com/ggml-org/llama.cpp src
  cmake -S src -B bld -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="${cc:-75}" -DGGML_NATIVE=OFF -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release >/dev/null
  cmake --build bld --target llama-server -j"$(nproc)" >/dev/null
  cp bld/bin/llama-server bld/bin/*.so* bin/
elif [ "$cc" = 75 ] && [ -n "${LLAMA_T4_URL:-}" ]; then
  curl -fsSL "$LLAMA_T4_URL" | tar xz -C bin
else
  [ "$cc" = 75 ] && echo "note: T4 with no LLAMA_T4_URL: using the official release, whose T4 code is PTX the driver compiles on first start (slow once, needs a recent driver). Set LLAMA_T4_URL or BUILD=1." >&2
  curl -fsSL "https://github.com/ggml-org/llama.cpp/releases/download/$TAG/llama-$TAG-bin-ubuntu-cuda-12.8-x64.tar.gz" | tar xz
  mv "llama-$TAG"/* bin/ && rmdir "llama-$TAG"
fi
echo "$LLAMA_DIR/bin/llama-server"
