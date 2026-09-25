import time, torch
from nemo.collections.asr.models import ASRModel

t0 = time.time()
model = ASRModel.from_pretrained("nvidia/parakeet-tdt-0.6b-v3")
model = model.to("cuda").eval()
print(f"loaded in {time.time()-t0:.1f}s")
print("gpu mb", torch.cuda.memory_allocated()/1e6, "reserved", torch.cuda.memory_reserved()/1e6)
