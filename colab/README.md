# jevgw: Jev models on a Colab GPU

Load any of our decision models that fits the GPU, call it with text, images and video, see the response times, switch to another.
One model at a time behind one TypeSafe-compatible `/v1/systemone`, a control panel, and an optional public endpoint.

## Quick start
**Colab.** Upload the one file `jevgw_colab.ipynb` (File > Upload notebook), Runtime > GPU, run the cells top to bottom. Nothing else is needed: no clone, no
repository. Its cells write the gateway's source (readable, in the notebook), install llama.cpp and download model files from Hugging Face. Step 4 opens the
control panel inside the notebook. Free Colab is a **T4 (16 GB, about 15 GiB usable)**; paid plans offer larger GPUs (check Colab's current list).
The notebook carries only the models that run on stock llama.cpp (the Clef Flash GGUFs); the other models need our adapter code and run from the repo (below).

**Anywhere with a CUDA GPU.**
```
python -m jevgw --llama-bin /path/to/llama-server --model clef-flash-q4km --tunnel    # then open http://127.0.0.1:8000
python -m jevgw.client --url http://127.0.0.1:8000 --key <key> -n 5                    # text, image, video: round trip and model time
```
The first load of a model installs its packages and downloads its weights. The key is printed at start (or set `GATEWAY_KEY`).

## Safe to run again
For people who just want to play with a classifier: **Runtime > Run all** is the whole procedure, and every cell can be run again.
- The gateway start reuses a running gateway (same port, same key), replaces a dead one, and skips a busy port.
- The llama.cpp install is built in a scratch folder and moved into place only when complete; a missing or broken install is removed and redone.
- A model load runs in the background (`POST /admin/select` with `"wait": false`). Asking for a model that is loading or loaded does nothing, so
  running the cell again joins the load in flight. The notebook and the panel show progress ("downloading 3.1 of 6.5 GiB", "starting the model
  server"); a dropped download retries three times and resumes from the partial file; a failed load is retried twice, then the error is shown and
  Load (or the cell) can be pressed again. A model that does not fit, a full disk or a disabled model is refused at once with the reason.
- The last cell stops or **resets** (clears gateway state and half-finished loads, optionally the downloaded models) so Run all starts clean.
These helpers are `jevgw/notebook.py`, with unit tests (`tests/test_notebook.py`).

## The control panel
`GET /` (no key needed to see it, but it answers only requests that did not come through the tunnel: the public URL serves the API, never the panel; every
action needs the key). One table of every model: GiB, what it takes (text, images), state
(ready, loaded, disabled, needs 24 GB, no recipe yet) and **Load / Unload / Enable / Disable / Delete files**, and whether its weights are on disk. The header shows free disk. Plus the tunnel (start, stop, URL, curl),
live p50/p95 per model, and a test box for text, an image, or a video (sampled into frames in your browser).

## Disk
A Colab session's disk is small and a GGUF is several GiB, so downloads are budgeted. At most `--keep` models (default 2) stay on disk, a margin of free space
(`--disk-margin-gib`, default 5) is always left, and before a download the least recently used models are deleted until the new one fits. A file two models share
(the Clef quants use one vision projector) is deleted only when nothing else needs it. If a model cannot fit even alone, the load is refused with a 507 and the
numbers. Each catalog entry declares its file sizes (`file_gib`, `mmproj_gib`); the panel's Delete files button frees a model by hand.

## Models
`vram_gib` is peak GPU memory measured on our RTX 5090. The gateway refuses a model that does not fit the GPU it runs on.

| id | GiB | T4 (free) | 24 GB | images |
|---|---|---|---|---|
| clef-flash-q4km | 10.8 | yes | yes | yes |
| clef-flash-q2k | 9.3 | yes | yes | yes |
| clef-flash (bf16) | 18.5 | no | yes | yes |
| laya | 3.1 | yes | yes | no |
| verdict | CPU | yes | yes | no |
| semif, so1 | 8.6 | yes (bf16 is emulated on a T4) | yes | no |
| kev-0.5b, kev-0.8b | 2.7, 4.5 | yes | yes | no |
| kev-4b | 17.8 | no | yes | no |
| jeff | 9.5 | yes | yes | no |
| winnow-12b (recipe not written yet) | 14.7 | tight | yes | yes |
| cygnet (excluded, over 20 GiB) | 28.6 | no | no | no |

## API
```
POST /v1/systemone   {"state", "questions", "images"?}            Authorization: Bearer <key>   (or X-API-Key)
GET  /v1/models      what fits, what is loaded, load and warm-up time
GET  /v1/stats       calls, errors, p50, p95 per model            GET /v1/tunnel   the tunnel's status
POST /admin/select   {"model"}      POST /admin/unload      POST /admin/enable {"model","enabled"}      POST /admin/purge {"model"}      POST /admin/tunnel {"action": "start"|"stop"}
GET  /healthz        200 once a model is loaded, 503 while loading; no key, no secrets
```
Responses carry `X-Request-Id`, `X-Model`, `X-Gateway-Version`; `/v1/systemone` also `X-Latency-Ms` (time inside the model). A model is warmed with one
throwaway call after loading, so the first real call is not the cold one. Video goes in as sampled frames in `images`.

Built in for a test service: API key on everything but `/healthz` and the local panel · rate limit (default 600/min, `--per-minute`) and an in-flight cap
(`--max-inflight`, answers 429 with `Retry-After`) · 503 with `Retry-After` while loading · CORS for browser clients · request ids · a request log with
no bodies (`work/requests.jsonl`) · request bodies capped at 32 MB · children are stopped with the gateway.

## Serve mode and the terms
Colab's FAQ (research.google.com/colaboratory/faq.html) lists, for all runtimes: "file hosting, media serving, or other web service offerings not
related to interactive compute with Colab" and "connecting to remote proxies"; for free runtimes also "bypassing the notebook UI to interact primarily
via a web UI". It also says "Runtimes will time out if you are idle." It does not mention tunnels or keep-alive scripts.

A public endpoint is the kind of thing those lines describe, and the audio loop works around the idle timeout. So the notebook is **interactive by
default**; serve mode (step 6, `SERVE = True`) is opt-in and prints this. Google may disconnect the session or restrict your Colab use. For anything
you want to keep running, host the gateway on a GPU machine that allows serving.

What serve mode does: opens a free Cloudflare quick tunnel and a watchdog, and plays a silent audio loop. What to expect:
- Quick tunnels are for testing: no uptime guarantee, the URL changes whenever the tunnel restarts, 200 requests in flight, no streaming.
- The watchdog reads cloudflared's local `/ready` (live edge connections), not the public hostname, and restarts a dead or disconnected tunnel
  (tested: kill cloudflared, a new URL within about 10 s, no restart loop). A new hostname can take up to a minute to resolve on some resolvers.
- The audio loop is a community trick that Google does not document. Keep the tab open and in the foreground. It does not lift Colab's 12 hour limit
  or stop it reclaiming the GPU. When the session ends the endpoint ends; clients should retry on 503/429/connection errors.

## The T4 binary
The official llama.cpp build has ready-made GPU code for RTX 30/40/50 cards (including the L4) but only PTX for a T4, which the driver compiles on first
start. `dist/llama-b11430-t4.tar.gz` (145 MB, not in git) is built with real sm_75 code: host it and set `LLAMA_T4_URL` in the notebook (step 3). Building on Colab's
2 vCPUs takes about an hour (6 minutes on 20 cores): `BUILD=1 ./setup_llama.sh`.

## Layout
```
jevgw/                  notebook.py (the notebook's idempotent helpers)  catalog.py (models.json, what fits)  backends.py (llama + recipe servers)  manager.py (load, unload, enable, stats)
                        disk.py (disk budget, least-recently-used deletion)
                        tunnel.py (cloudflared + watchdog)   server.py (HTTP API)  client.py (calls and timing)  ui/index.html (panel)  __main__.py
models.json             the catalog and each model's recipe        setup_llama.sh   llama.cpp install        jevgw_colab.ipynb   the standalone notebook, built by build_notebook.py
vendor/                 copies of our install and serve scripts and adapters; ./vendor.sh refreshes them from the main repo
tests/                  python -m unittest discover -s tests -t .        lint: uvx ruff check . && uvx ruff format --check .
```
Adding a model: add its entry to `models.json` (kind `llama` with a GGUF, or `proc` with setup and launch commands), run `./vendor.sh` if its scripts changed,
`python build_notebook.py` (it embeds this folder's files, so the notebook never drifts from the code).

## What has and has not been tested
Tested on our RTX 5090 box: 49 unit tests (including the disk budget, the panel being hidden from the tunnel, background loads, retries and the notebook helpers' idempotency) with a fake model server (auth, CORS, load / switch / unload / enable, refusals, rate limit, in-flight cap, stats,
request log, keep-alive, tunnel restart and stop); the panel in a browser (Load, Unload, Enable, Disable, the test box, the tunnel); a real Cloudflare tunnel
(public calls, the key check, restart after killing cloudflared); llama.cpp Clef Flash Q2 and Q4 with text, image and video-as-frames (CPU only, the GPU was busy);
Verdict and Laya through the recipe backend; the fit rule for T4, L4 and A100 sizes; the T4 build's sm_75 code; the keep-alive audio's format.
The standalone notebook's cells were also run end to end on this box (with the Colab-only calls stubbed and local copies of llama.cpp and the weights).
**Not tested:** any run on Colab or a real T4 (including `serve_kernel_port_as_iframe` and whether the audio loop holds a session), GPU response times, the
image and video tabs of the panel (they need a file picker), and the recipes for semif, so1, kev, jeff and full-precision Clef Flash through the gateway.
