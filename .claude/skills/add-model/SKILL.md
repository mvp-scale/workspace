---
name: add-model
description: Onboard a new Jev-class decision model (a Hugging Face repo, GitHub repo or hosted API that answers typed noul/choice/score questions) into this workspace end to end — install, adapter, service, fact sheet, GPU measurement, leaderboard, published probe sets, demo pages. Use when the user says "add X to our stack", "deploy this model", "onboard", or pastes a model link.
---

# Add a model

Adding a model touches about a dozen files in five places. Do them in this order, from a checklist, and verify each step. Do not improvise file by file: that is how Clef Flash first shipped with a `family` value that crashed `/models`, a unit that waited forever for another service, and a benchmark that ran out of GPU memory against its own server.

## 0. Read the primary source first

Fetch the model card / README. Write down, from the card only: base model, parameter count, licence, **the code the card gives for loading and calling it**, dependency pins (torch, transformers), dtype, and whether it takes images. **Use the author's own loader and entry point. Do not reimplement model code.** The adapter you write is thin glue between a jevbench task and the author's call. Fields the card does not state stay `null` in `models.json`; never fill them from memory. Cite the card URL and the date read in the adapter docstring.

## 1. Classify the serving pattern

| Pattern | Examples | Install | Serve | Adapter |
|---|---|---|---|---|
| **Own server** (speaks `/v1/systemone`) | kev-4b, jeff | clone + venv in the repo | its own entrypoint, via `service.yaml` | `typesafe` (existing) |
| **In-process Python** (author's package or loader) | semif, so1, laya, verdict, clef-flash | `dev-bench-setup.sh` `setup_<name>()` | `demo/serve_inproc.py --model <id>` | new `jevbench/jevbench/adapters/<name>_local.py` |
| **llama.cpp / vLLM** | winnow, cygnet | build/download, `service.yaml` `proc` entry | its server | `typesafe` or the shim |
| **Hosted API** | jev | none | none | `typesafe` + key |

If it is an own-server or hosted model, skip step 3 and the adapter. If it is in-process, do everything.

### Quantized or third-party variants of a model we already have

Search the Hub for children of the parent: `https://huggingface.co/api/models?filter=base_model:quantized:<owner>/<repo>` (also `finetune`, `adapter`). Then **read each README and the file's declared architecture; do not rule one out from its file list**. Custom-head models (Clef) are only usable if the quantized copy keeps the head: it may be a separate file (`joint_head.safetensors`) or embedded in the GGUF (Clef's GGUFs carry it at Q8_0 and `llama-server` serves `/v1/systemone` natively, which a file-list check misses). Prefer, in order: a copy served by a mainstream runtime with native support for the decision head, then one with a documented adapter for our existing pattern, then one that needs a bespoke runtime pinned to a specific vLLM/CUDA. Quantized copies are unofficial: say so in `models.json`, cite the quantizer, and record what the card says was preserved (head precision, imatrix). Give the variant its own id (`clef-flash-q4km`) and a six-character code that differs from its parent (`CLF9Q4`). Its probe results are compared with the parent's: the point is to find the floor, so measure per-item agreement and accuracy against the full-precision runs.

## 2. Pick the id, code and family

- `id`: lowercase, hyphenated, stable (`clef-flash`). It becomes directory names (`data/bench/<id>-<tier>`, `data/probe-runs-v2/<id>-<set>`), so **never rename it later**. The leaderboard splits the directory name on the last `-`, so tier and set names must not collide with the id's suffix.
- `code`: at most six characters, family letters + size (B = billions, H = hundreds of millions): `CLEF9B`.
- `family` is a **key into `FAM` in `demo/models.html`**. Existing keys: `hosted`, `logits`, `pointer`, `encoder`, `joint`. An unknown value makes `FAM[m.family]` throw and breaks the whole page. If the mechanism is genuinely new, add a `FAM` entry (name, short, flow) in the same change, using only facts from the card.

## 3. Install (in-process models)

In `/workspace/dev-bench-setup.sh` add `setup_<name_with_underscores>()` using the existing helpers: `venv <id> torch==<pin>`, `pip`, `clone`, `hf`. Use the card's pins. Torch must be a CUDA wheel (`TORCH_CUDA_TAG`, default cu128 for the RTX 5090). Weights go to `/workspace/data/models/<id>`. Run `./dev-bench-setup.sh <id>`. The loop turns `-` into `_` when it calls the function.

## 4. Adapter and registration

Copy the closest adapter (`laya_local.py` for encoders, `clef_local.py` for a decoder with a `systemone()` call). Required: `load()`, `build_request()`, `run()` returning a `DecisionResult` with `probs` over the exact labels (`noul` -> `{"yes": p, "no": 1-p}`), no retries and no fallbacks, `reserve_estimate()` returning 0 for local models. Then register in four places:

1. `jevbench/jevbench/adapters/__init__.py` import
2. `jevbench/jevbench/cli.py`: import, the `kinds` dict, the `revision` tuple, and the `--adapter` `choices` list
3. `demo/serve_inproc.py`: a branch in `make()` and the `--model` `choices`
4. `demo/bench-batch.sh`: `ADAPTER`, `ENDPOINT` (and `COST` if it is not CPU)

## 5. Service

Add the systemd unit in `demo/lineup.sh` (`unit_inproc`) **and** an entry in `service.yaml` (`kind: systemd`, `port`, `match: serve_inproc`, `health: /healthz`, `heavy: true`, tags). Run `./service.sh check`.

- llama.cpp servers: `kind: proc` like winnow, binary from the official prebuilt release that includes the architecture (check the PR is merged and the build number is at or after it; do not reuse another model's pinned build). Decision-mode **inputs must fit one physical batch**: pass `-b 16384 -ub 16384` (the card's max input) and `-np` slots with `-c` = slots x 16384, or inputs over 512 tokens fail with HTTP 500 "input is too large to process" and show up as failed items. Memory then is the weights plus compute buffers: Clef Flash Q4_K_M was 6.0 GiB at default batch and 9.7 GiB at `-ub 16384`. Measure with `demo/vram.py` (add a `measure_served` job; it measures the text-only config, so re-measure if you add `--mmproj`: Clef Flash Q4 was about 10.8 GiB with the projector).
- Next free port after 8018 (taken: 8008-8018, 8091, 8100, 8110, 8112, 8200).
- Only models that share `kev-4b`'s start-up memory spike should wait on it. A standalone model must not have the `ExecStartPre` wait, or it sits in "activating" forever when kev-4b is down.
- **GPU budget before anything else**: `nvidia-smi` and `./service.sh` status. A 9B bf16 model needs about 19 GiB; Winnow takes about 15 GiB. If it will not fit beside the `models` profile, tag it `solo`, leave it out of `profiles.models` and out of `LINEUP`, and say so in the desc.

**Name the process.** `nvidia-smi` names a process by how it was launched (its `argv[0]`, cut from the left), so five Python services all read `.../bin/python` and every llama.cpp server reads `.../llama-server`. Launch each model through a link named for it: `ln -sf python <venv>/bin/<id>` for in-process models (the venv still works, because Python finds `pyvenv.cfg` next to the link) and `ln -sf llama-server <dir>/<id>` for llama.cpp (needs only `LD_LIBRARY_PATH`). Use that path as `ExecStart`/`cmd`, and keep `service.yaml` `match:` on something present in both the old and new command lines (`--alias <id>`), never a prefix shared with another model: a loose `match` makes `./service.sh stop <a>` hit model `<b>`. Verified on a CUDA process: `nvidia-smi` showed `.../.venv/bin/clef-flash-bf16`.

## 6. Fact sheet

Append to `demo/models.json`: `id, name, code, vendor, kind, open, licence, params, price, base, architecture, family, interface, repo, verify, served_as, sauce, how[], public_rank, public_score`. Facts only, `null` when unknown.

Also add the id to `BACKENDS` in `demo/server.py` and to `LOCAL` in `demo/index.html`. Do **not** put model counts in page text ("Nine models"); they go stale on every add.

## 7. Measure (one model on the GPU at a time)

Stop the model's own service first; in-process runs load a second copy and will OOM beside it. HTTP-served models (kev, llama.cpp) keep their service up and use `demo/bench.sh` (`MODELS=<id>`, endpoint in its `EP` map, `CONC[<id>]` for concurrency, private ledger per run) instead of `bench-batch.sh`. Every step below needs an idle GPU for that model; other services may stay up only if the sum fits.

```bash
systemctl stop <id>
python3 demo/vram.py <id>                       # merges into demo/vram.json; add a job in demo/vram.py first
demo/bench-batch.sh <id>                        # leaderboard tiers -> data/bench/<id>-{original,easy,hard}
SETS=$(ls probes/v2/*.jsonl | xargs -n1 basename | sed 's/\.jsonl$//' | tr '\n' ' ')
TASKS_DIR=/workspace/probes/v2 BENCH_OUT=/workspace/data/probe-runs-v2 TIERS="$SETS" demo/bench-batch.sh <id>
systemctl start <id>
```

**Speed: build a batching pipeline, do not run copies of the model.** The GPU is saturated by keeping many requests in flight and running them as padded batches through one loaded model, not by serial calls and not by loading the model twice. The pattern is in the repo:

- `jevbench/jevbench/batching.py` — `MicroBatcher`: callers `submit(item, size)` and wait on a future; one worker gathers waiting items, size-sorts them, cuts batches under `max_batch` items and `max_tokens` padded tokens, runs one forward per batch and returns each caller its own result; a failing batch is split so one bad item or an OOM fails only that item.
- `clef_local.py` — the adapter reference: `thread_safe = True`, tokenise in the caller thread, forward through the batcher using the author's own collate/encode/answer functions. Tune with `CLEF_MAX_BATCH` and `CLEF_MAX_BATCH_TOKENS` and watch peak memory and `nvidia-smi` utilisation.
- `jevbench.cli run --concurrency N` keeps N tasks in flight, writes records in task order, applies the same stop rules. `demo/bench-batch.sh` sets `CONC[<id>]` per model and uses it for the probe sets only. **Leaderboard tiers (`original|easy|hard`) stay serial**: per-item latency under concurrency includes queue time and is not comparable.
- `demo/serve_inproc.py` skips its global lock for `thread_safe` adapters, so the live demo gets the same batching.

Every new in-process model should ship a batching path if its author's code can batch (check for a collate/batch function in the card). If it cannot, leave `thread_safe` unset and run serial.

**Proof before use (required).** Pick a set that already has serial results, run it with `--concurrency 64` into a scratch dir and compare item by item: predicted labels, max |delta p|, accuracy, wall time and peak memory. Clef Flash on `mmlu_anatomy` (135 items): 135/135 same predictions, max |dp| 0.030 (bf16 padding noise), accuracy 0.8667 both ways, 228 s originally / 26 s serial with a private ledger / 3.7 s batched, peak 22.4 GiB. Record the comparison in the report; if predictions differ, stop and investigate before publishing.

**Private ledger.** `bench-batch.sh` gives every run its own `$out/ledger.jsonl`. Do not point local-model runs at the shared `data/probe-runs-v2/ledger.jsonl` (180k+ lines): each reserve/settle re-reads the whole file, 1.5 s per item against 0.17 s of model time (measured). Local models cost $0, so the shared guard adds nothing. Paid APIs keep the shared ledger and `demo/bench.sh`.

**Load once.** Each set is a new process that reloads the model (about 8 s each). Acceptable at 72 sets; a single process that loops over sets is the next improvement.

**Gate every run on a healthy server and a free GPU.** Before measuring or benchmarking, check `curl :<port>/health` (or `/healthz`) answers and `nvidia-smi` shows room for the model: `demo/vram.py` refuses unless the GPU is idle, and a llama.cpp server with `-ub 16384` needs about 9 GiB beyond its weights. A chain that does not check this runs the whole benchmark against nothing: every item fails (the runner stops after 3 straight errors, so each set holds only a few rows) and it leaves result directories that make a rerun skip. After any failed run, delete that model's `data/bench/<id>-*` and `data/probe-runs-v2/<id>-*` before rerunning, and read the `done: N/M attempted, F failed` lines, not just whether the chain finished. Another service may have been started meanwhile; look at `nvidia-smi` first.

Probe runs go to `data/probe-runs-v2/`, never `data/bench/` (the leaderboard averages everything in `data/bench/`). After each run check `results.jsonl` for failed items; a failure is an error, not 0% accuracy. Existing complete runs are skipped, so a failed run's directory must be removed before a rerun.

## 7b. Vision, if the model takes images

Check the card for `images`/`videos` and test it; do not assume text-only from a PR title or a README table. Text probe sets say nothing about vision. Requests use `images`: an array of data URLs (`data:image/...;base64,...`), the field both the card and llama-server's `/v1/systemone` use (Winnow is the exception: `winnow: {images}`). Run the Image Lab tasks with `probes/images/run_winnow.py --images-field top --out-name <id> --endpoint http://127.0.0.1:<port> --model <id>`; the Image Lab lists every `data/image-lab/runs/<id>/` as a model. For llama.cpp pass `--mmproj <projector>.gguf` (about 0.9 GB for Clef Flash; the server answers 501 \"start it with `--mmproj`\" without it) and re-check memory. llama.cpp warns that Qwen-VL models may want `--image-min-tokens 1024` for grounding tasks; untuned, so say image numbers may be understated. For an in-process adapter, expose an `answer_request(body)` that decodes the data URLs and is used by `serve_inproc.py` (Clef Flash decides all questions of a request jointly, as the model is built to). Video is separate and unverified unless you run it. Clef Flash on the 44 image tasks (1,100 items): bf16 74.2%, Q4_K_M 73.4%, Winnow 73.4%; Q4 gave the same answer as bf16 on 95.2% (26 right-to-wrong, 17 wrong-to-right).

## 8. Show it in the demo

The Scenario lab and Image lab share their heat map, model strip and colour scale (`table.heat`, `.strip`/`.mrow`, `.scale` in `static/app.css`; `Jev.heat` in `static/app.js`). Keep the two labs' structure aligned: an overview heat map (rows grouped, a column per model in one fixed order, an Average row, the chance-centred scale), and a per-item "Model comparison" strip with the 95% interval bar. A new model must show in those views without clicking into a task; check the overview, a domain and a task page after onboarding. The Image Lab discovers models from `data/image-lab/runs/<id>/` and reads fact sheets from `/api/models`.

The Leaderboard, Scenario lab and Baseline compare discover models from `data/` directories and `BACKENDS`, so they pick the model up once the data and the `server.py` entry exist. The **demo server must be restarted** (`./service.sh restart demo`) to load `BACKENDS`; check first that no window study is running (`probes/window_study.py`). Optional hand-typed reference maps in `demo/scenarios.html` (p50 latency, WEAK accuracy) are not required.

## 8b. Offer it on Colab

If the model's peak GPU memory is under about 14 GiB (a free T4), add it to `colab/jevgw/data/models.json`: `kind: llama` with a GGUF plus `file_gib` and `mmproj_gib`, or `kind: proc` with the same setup and launch recipe the main repo uses plus `install_gib` and `paths` (the folders under the install root it owns, for the disk budget). `vram_gib` is the measured peak; say in `verified` what was actually run through the gateway on a T4. Pin every repository the setup clones to the commit you validated (`clone <owner/repo> <dir> <sha>` in `dev-bench-setup.sh`). Run `colab/vendor.sh` if its server wrapper or setup function changed, `python colab/build_notebook.py` (the notebook's table and dropdown are generated from the list), and `python -m unittest discover -s colab/tests -t colab`. Load it on a real T4 before saying it works: a model that only ran on this box can fail on Colab (an unpinned clone did).

## 9. Verify, then report

- `./service.sh check`, `python3 -c "import json; json.load(open('demo/models.json'))"`, `bash -n` on every edited script.
- `curl :<port>/healthz` and one real `/v1/systemone` call with a `noul`, a `choice` and a `score` question.
- Load `/api/leaderboard`, `/api/status`, `/api/vram`, `/models` and `/scenarios` and confirm the id appears and nothing throws.
- Report measured numbers with what they are measured against. Quote vendor numbers as the vendor's. Say what was not run.
- Do not commit unless asked. Changes span `/workspace` (`demo/`, `service.yaml`, `dev-bench-setup.sh`) and the separate `jevbench` repo.
