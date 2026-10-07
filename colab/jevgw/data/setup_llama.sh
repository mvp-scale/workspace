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
# The official build is linked against CUDA 12.8; newer Colab images only have CUDA 13, so its GPU library cannot load and llama.cpp
# silently falls back to the CPU. llama.cpp publishes the three runtime libraries it needs as a separate bundle: put them beside the server.
ensure_cuda_libs() {
  local bin="$1"
  [ -f "$bin/libggml-cuda.so" ] || return 0
  LD_LIBRARY_PATH="$bin:${LD_LIBRARY_PATH:-}" ldd "$bin/libggml-cuda.so" | grep -E "libcudart|libcublas" | grep -q "not found" || return 0
  echo "fetching the CUDA 12.8 runtime libraries llama.cpp needs (about 570 MB)" >&2
  local tmp; tmp=$(mktemp -d "$LLAMA_DIR/.cudart.XXXXXX")
  curl -fsSL --retry 3 "https://github.com/ggml-org/llama.cpp/releases/download/$TAG/cudart-llama-$TAG-bin-ubuntu-cuda-12.8-x64.tar.gz" | tar xz -C "$tmp"
  mv "$tmp"/*/*.so.12 "$bin/"; rm -rf "$tmp"
}
if [ -x "$LLAMA_DIR/bin/llama-server" ]; then ensure_cuda_libs "$LLAMA_DIR/bin"; echo "$LLAMA_DIR/bin/llama-server"; exit 0; fi
rm -rf "$LLAMA_DIR/bin"
# Everything is built in a scratch folder and moved into bin/ only when it is complete, so an interrupted run leaves nothing half-done
# and running this again is always safe.
tmp=$(mktemp -d "$LLAMA_DIR/.tmp.XXXXXX"); trap 'rm -rf "$tmp"' EXIT; mkdir -p "$tmp/bin"
if [ "${BUILD:-0}" = 1 ]; then
  export PATH=/usr/local/cuda/bin:$PATH CUDACXX=/usr/local/cuda/bin/nvcc
  [ -d src ] || git clone -q --depth 1 --branch "$TAG" https://github.com/ggml-org/llama.cpp src
  cmake -S src -B bld -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="${cc:-75}" -DGGML_NATIVE=OFF -DLLAMA_CURL=OFF -DCMAKE_BUILD_TYPE=Release >/dev/null
  cmake --build bld --target llama-server -j"$(nproc)" >/dev/null
  cp bld/bin/llama-server bld/bin/*.so* "$tmp/bin/"
elif [ "$cc" = 75 ] && [ -n "${LLAMA_T4_URL:-}" ]; then
  curl -fsSL --retry 3 "$LLAMA_T4_URL" | tar xz -C "$tmp/bin"
else
  [ "$cc" = 75 ] && echo "note: T4 with no LLAMA_T4_URL: using the official release, whose T4 code is PTX the driver compiles on first start (slow once, needs a recent driver). Set LLAMA_T4_URL or BUILD=1." >&2
  curl -fsSL --retry 3 "https://github.com/ggml-org/llama.cpp/releases/download/$TAG/llama-$TAG-bin-ubuntu-cuda-12.8-x64.tar.gz" | tar xz -C "$tmp"
  mv "$tmp/llama-$TAG"/* "$tmp/bin/"
fi
[ -x "$tmp/bin/llama-server" ] || { echo "llama-server missing after install" >&2; exit 1; }
rm -rf bin; mv "$tmp/bin" bin
ensure_cuda_libs "$LLAMA_DIR/bin"
echo "$LLAMA_DIR/bin/llama-server"
