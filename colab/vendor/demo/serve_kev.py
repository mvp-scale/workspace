"""Launch kev.serve with the fp32 load-time memory returned to the GPU.

kev merges the LoRA in fp32 and then casts to bf16 (KEV_DTYPE=bf16). PyTorch keeps the freed fp32 blocks reserved, so the
process holds about twice the memory it needs. This wrapper runs kev's own loader and then releases the cache. Nothing
else changes: same model code, same arguments.

    cd /workspace/kev && KEV_DTYPE=bf16 .venv/bin/python /workspace/demo/serve_kev.py --run jaredpalmer/kev-4b --port 8010
"""
import gc, os, sys

sys.path.insert(0, os.getcwd())  # run from the kev repo directory so `import kev` resolves
import torch
import kev.serve as serve

_load = serve.load


def load(*args, **kwargs):
    out = _load(*args, **kwargs)
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return out


serve.load = load

if __name__ == "__main__":
    serve.main()
