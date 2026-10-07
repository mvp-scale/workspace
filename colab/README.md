# Jev models on a Colab GPU

Load any of our decision models that fits the GPU, call it with text, images and video, see the response times, switch to another.
One model at a time. Same `/v1/systemone` shape as the hosted API.

## Try it
1. Open `clef_colab.ipynb` in Google Colab (File > Upload notebook). Runtime > Change runtime type > GPU.
2. Run the cells top to bottom. Pick a model in step 4, test it in step 5, switch in step 6.

The notebook carries its own code, so it needs no repo. Free Colab gives a **T4 (16 GB, about 15 GiB usable)**; paid plans offer larger GPUs (check Colab's current list).

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
POST /v1/systemone   {"state", "questions", "images"?}     Authorization: Bearer <key>
GET  /v1/models      what fits, what is loaded
POST /admin/select   {"model": "<id>"}                     unload the current model, load another
GET  /healthz
```
Responses carry `X-Model` and `X-Latency-Ms`. Video goes in as sampled frames in `images` (the server takes images, not a video file). `try_it.py` does text, image and video and prints round-trip and model time per call.

## Terms: why there is no public URL and no keep-alive
Colab's FAQ (research.google.com/colaboratory/faq.html) lists, for all runtimes: "file hosting, media serving, or other web service offerings not related to interactive compute with Colab" and "connecting to remote proxies"; for free runtimes also "bypassing the notebook UI to interact primarily via a web UI". It also says "Runtimes will time out if you are idle." It does not mention tunnels or keep-alive scripts.

So the notebook calls the model from inside the notebook only. It does not open a tunnel and does not play audio or click to hold the session, which would work around the idle timeout. A public "try it" API for outside developers is a web service offering, so host that elsewhere: `gateway.py --tunnel` works on any GPU host that allows serving (Cloudflare quick tunnels are for testing only, no uptime promise, 200 in-flight requests, no SSE). The gateway requires an API key either way.

## The T4 binary
The official llama.cpp build has ready-made GPU code for RTX 30/40/50 cards (including the L4) but only PTX for a T4, which the driver compiles on first start. `dist/llama-b11430-t4.tar.gz` (145 MB, not in git) is built with real sm_75 code; host it and set `LLAMA_T4_URL` in the notebook. Building on Colab's 2 vCPUs would take about an hour (it took 6 minutes on 20 cores): `BUILD=1 ./setup_llama.sh`.

## What has and has not been tested
Tested on our RTX 5090 box: the gateway (key check, load, switch, refusal of a model that does not fit, cleanup of child processes), llama.cpp Clef Flash Q2 and Q4 with text, image and video-as-frames (CPU only, the GPU was busy), the generic recipe backend with Verdict and Laya, the fit rule for T4, L4 and A100 sizes, and the T4 build's sm_75 code.
**Not tested:** any run on Colab or a real T4, the recipes for semif, so1, kev, jeff and the full-precision Clef Flash through the gateway, and GPU response times. Treat those as written from our own install scripts.

## Layout
`gateway.py` (server) · `try_it.py` (client) · `models.json` (the catalog and recipes) · `setup_llama.sh` · `vendor/` (copies of our install and serve scripts and adapters; `./vendor.sh` refreshes them) · `build_notebook.py` (regenerates the notebook).
