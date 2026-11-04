# Third-family voter: Ministral-3-14B-Instruct-2512 AWQ 4-bit (cyankiwi build, Apache-2.0) via vLLM labels the Pulse items with the frozen spec ws-v2-frozen.
# Private dataset in, labels.jsonl out. No trust_remote_code, no hosted calls.
N_ITEMS = 400        # first 5 are the smoke test; the run aborts if they do not parse
import glob, hashlib, json, os, subprocess, sys, time
sys.path.insert(0, next(os.path.dirname(p) for p in glob.glob("/kaggle/input/**/guard.py", recursive=True)))
from guard import guard, beat
guard(max_min=50, idle_min=15)
import threading
def _bg():
    while True:
        time.sleep(30); beat()
threading.Thread(target=_bg, daemon=True).start()   # keeps the guard fed during long loads
IN = os.path.dirname(next(iter(glob.glob("/kaggle/input/**/spec.json", recursive=True))))
spec = json.load(open(f"{IN}/spec.json"))
items = [json.loads(l) for l in open(f"{IN}/items.jsonl")][:N_ITEMS]
wheels = sorted(glob.glob("/kaggle/input/**/wheels", recursive=True))
beat(f"inputs: {len(items)} items, wheels {wheels}")
out = {"n_items": len(items)}
t0 = time.time()
if wheels:
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-index", "--find-links", wheels[0], "vllm"], capture_output=True, text=True)
    out["install_mode"] = "offline-wheels"; out["install_rc"] = r.returncode
else:
    r = None
if r is None or r.returncode != 0:
    if r is not None: out["offline_tail"] = (r.stdout + r.stderr)[-400:]
    r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "vllm"], capture_output=True, text=True)
    out["install_mode"] = "online"; out["install_rc"] = r.returncode
subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "-q", "torchaudio"], capture_output=True)
out["install_s"] = round(time.time() - t0); beat(f"vllm installed {out['install_mode']} rc={out['install_rc']}")

# prompt exactly as kit/teacher/task_spec.py builds it (system = guideline + layers + examples; user = template)
g = spec["guideline"]; g = "\n".join(g) if isinstance(g, list) else str(g)
tpl = spec.get("input_template")
user_text = lambda it: tpl.format(id=it.get("id", "example"), text=it["text"], candidates="").strip()
parts = [g.strip(), "LAYERS: " + ", ".join(spec["layers"])]
for i, ex in enumerate(spec.get("examples", []), 1):
    parts.append(f"EXAMPLE {i} (synthetic text, not real news)\n<example_input>\n" + user_text(ex["input"]) + "\n</example_input>\n<example_reply>\n" + json.dumps(ex["output"], ensure_ascii=False) + "\n</example_reply>")
system = "\n\n".join(parts) + "\n\nReply with the JSON object only."
spec_sha = hashlib.sha256(json.dumps(spec, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
schema = spec["output_schema"]
out["spec_sha256"] = spec_sha

t0 = time.time()
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub"], capture_output=True)
from huggingface_hub import snapshot_download
mdir = snapshot_download("cyankiwi/Ministral-3-14B-Instruct-2512-AWQ-4bit", local_dir="/tmp/ministral_model", ignore_patterns=["consolidated.safetensors"])
out["download_s"] = round(time.time() - t0); beat("weights on local disk")
from vllm import LLM, SamplingParams
import importlib.metadata as md; out["vllm"] = md.version("vllm")
t0 = time.time()
llm = LLM(model=mdir, tokenizer_mode="hf", config_format="hf", load_format="safetensors", tensor_parallel_size=2, dtype="half", max_model_len=12288, gpu_memory_utilization=0.90, trust_remote_code=False, enable_prefix_caching=True)
out["load_s"] = round(time.time() - t0); beat("model loaded")
sp = dict(temperature=0.0, max_tokens=1200)
try:
    from vllm.sampling_params import StructuredOutputsParams
    sp_obj = SamplingParams(structured_outputs=StructuredOutputsParams(json=schema), **sp); out["constrained"] = "structured_outputs"
except Exception as e:
    out["constrained_err"] = repr(e)[:200]
    try:
        from vllm.sampling_params import GuidedDecodingParams
        sp_obj = SamplingParams(guided_decoding=GuidedDecodingParams(json=schema), **sp); out["constrained"] = "guided_decoding"
    except Exception as e2:
        out["constrained_err2"] = repr(e2)[:200]; sp_obj = SamplingParams(**sp); out["constrained"] = "none"
def run(chunk):
    msgs = [[{"role": "system", "content": system}, {"role": "user", "content": user_text(it)}] for it in chunk]
    return list(zip(chunk, llm.chat(msgs, sp_obj, chat_template_kwargs={"enable_thinking": False})))
def ok(r):
    try:
        lab = json.loads(r.outputs[0].text.strip().removeprefix("```json").removesuffix("```").strip()); return set(lab) == {"topic", "story_type", "claim", "conditions"}
    except Exception: return False
res_all = run(items[:5]); beat("smoke 5 labelled")
out["smoke_ok"] = sum(ok(r) for _, r in res_all); print("SMOKE", out["smoke_ok"], "/5", flush=True)
if out["smoke_ok"] < 5: out["aborted"] = "smoke parse failure"; items = items[:5]
B = 50
for s0 in range(5, len(items), B):
    res_all += run(items[s0:s0 + B]); beat(f"labelled {len(res_all)}/{len(items)}")
date = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); fails = 0
with open("/kaggle/working/labels.jsonl", "w") as f, open("/kaggle/working/raw.jsonl", "w") as fr:
    for it, r in res_all:
        txt = r.outputs[0].text; fr.write(json.dumps({"item_id": it["id"], "raw": txt, "finish": r.outputs[0].finish_reason}) + "\n")
        try:
            lab = json.loads(txt.strip().removeprefix("```json").removesuffix("```").strip())
            assert set(lab) == {"topic", "story_type", "claim", "conditions"}
        except Exception:
            fails += 1; continue
        f.write(json.dumps({"item_id": it["id"], "label": lab, "stats": {}, "provenance": {"teacher": "ministral", "model": "cyankiwi/Ministral-3-14B-Instruct-2512-AWQ-4bit", "prompt_version": spec["prompt_version"], "spec_name": spec["name"], "spec_sha256": spec_sha, "date": date, "text_sha256": hashlib.sha256(it["text"].encode("utf-8")).hexdigest(), "mode": "kaggle-vllm"}}, ensure_ascii=False) + "\n")
out["truncated"] = sum(r.outputs[0].finish_reason == "length" for _, r in res_all); out["parse_fail"] = fails; out["labelled"] = len(res_all) - fails
json.dump(out, open("/kaggle/working/run_info.json", "w"), indent=1); print(json.dumps(out, indent=1)); beat("done"); sys.stdout.flush(); os._exit(0)   # exit at once so the GPU is released; no keep-alive after the work
