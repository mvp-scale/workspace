import time, torch
from nemo.collections.asr.models import SortformerEncLabelModel

t0 = time.time()
model = SortformerEncLabelModel.from_pretrained("nvidia/Nemotron-3-Diarization")
model = model.to("cuda").eval()
print(f"loaded in {time.time()-t0:.1f}s")
print("gpu mb", torch.cuda.memory_allocated()/1e6, "reserved", torch.cuda.memory_reserved()/1e6)
