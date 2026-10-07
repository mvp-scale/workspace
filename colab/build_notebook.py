#!/usr/bin/env python3
"""Write clef_colab.ipynb. The notebook clones this folder from GitHub.

`--embed` packs the code into the notebook instead (a base64 tarball), for use before the code is published.
Edit the files, then rerun this.
"""

from __future__ import annotations

import base64
import io
import json
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EMBED = ["jevgw", "models.json", "setup_llama.sh", "vendor"]
SKIP = ("__pycache__", "work", "dist", ".git")


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)}


def code(text: str) -> dict:
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": text.strip("\n").splitlines(True),
    }


def bundle() -> str:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name in EMBED:
            tar.add(HERE / name, arcname=name, filter=lambda info: None if any(s in info.name.split("/") for s in SKIP) else info)
    return base64.b64encode(buffer.getvalue()).decode()


CLONE = """# clones just this folder from GitHub (a sparse clone: the repo holds more than the notebook needs)
REPO = "https://github.com/mvp-scale/workspace"  #@param {type:"string"}
BRANCH = "main"  #@param {type:"string"}
SUBDIR = "colab"  #@param {type:"string"}  # leave empty if the repo root is this folder
import os, subprocess

def sh(cmd):
    subprocess.run(cmd, shell=True, check=True)

sh("rm -rf /content/src")
if SUBDIR:
    sh(f"git clone -q --depth 1 --branch {BRANCH} --filter=blob:none --sparse {REPO} /content/src && git -C /content/src sparse-checkout set {SUBDIR}")
else:
    sh(f"git clone -q --depth 1 --branch {BRANCH} {REPO} /content/src")
os.chdir(f"/content/src/{SUBDIR}")
print(os.getcwd(), sorted(os.listdir()))"""


def embedded() -> str:
    return f'''# the code travels inside this notebook (built with --embed)
import base64, io, os, tarfile
BUNDLE = "{bundle()}"
tarfile.open(fileobj=io.BytesIO(base64.b64decode(BUNDLE)), mode="r:gz").extractall("/content/clef")
os.chdir("/content/clef")
print(os.getcwd(), sorted(os.listdir()))'''


KEEP_ALIVE = """# a silent audio loop: some people report it keeps the tab counted as active. Google does not document this, it can stop working,
# and it does not lift the 12 hour limit. Keep this tab open and in the foreground.
import base64, io, wave
from IPython.display import HTML, display
buf = io.BytesIO()
with wave.open(buf, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b"\\x00\\x00" * 8000)
display(HTML('<audio autoplay loop controls style="width:100%"><source src="data:audio/wav;base64,' + base64.b64encode(buf.getvalue()).decode() + '"></audio>'))"""


def build() -> list[dict]:
    models = json.loads((HERE / "models.json").read_text())["models"]
    ids = [m["id"] for m in models if m.get("kind") in ("llama", "proc")]
    return [
        md("""# Try the Jev-class models on a Colab GPU
One model at a time on the GPU. Load it, call it with text, an image and a video, see the response times, switch to another.
A control panel shows every model, what fits this GPU, and Load / Unload / Enable / Disable buttons.

**Two modes.** *Interactive* (default) runs and is called from this notebook. *Serve* (opt-in, step 5) also opens a public
Cloudflare URL and plays an audio loop to keep the session up. Read the note in step 5 before turning it on."""),
        md("## 1. Get the code"),
        code(embedded() if "--embed" in sys.argv else CLONE),
        md("## 2. Which GPU, and which models fit it"),
        code("""import subprocess
from jevgw import catalog

print(subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
                     capture_output=True, text=True).stdout or "NO GPU: Runtime > Change runtime type > GPU")
gpu, mib = catalog.gpu_info()
for m in catalog.load("models.json").values():
    if catalog.runnable(m):
        print(("fits   " if catalog.fits(m, mib) else "NO FIT ") + f"{m['id']:<17} {m['vram_gib']:>5} GiB  {m['name']}")"""),
        md(
            "## 3. Install the llama.cpp server (Clef Flash Q4 and Q2 use it)\n"
            "A T4 has no ready-made code in the official build, so its first start compiles it (slow once). For speed, host the prebuilt "
            "`llama-b11430-t4.tar.gz` and put its URL below; see the README."
        ),
        code("""LLAMA_T4_URL = ""  #@param {type:"string"}
import os
os.environ["LLAMA_T4_URL"] = LLAMA_T4_URL
LLAMA = !LLAMA_DIR=$PWD/llama ./setup_llama.sh
LLAMA_BIN = LLAMA[-1]
print(LLAMA_BIN)"""),
        md(
            "## 4. Start the gateway and open the control panel\nThe panel loads and unloads models. The first load of a model installs its packages and downloads its weights (minutes)."
        ),
        code(f"""MODEL = "clef-flash-q4km"  #@param {json.dumps(ids)}
import json, secrets, subprocess, sys, time, urllib.error, urllib.request
from jevgw.client import Client

KEY = secrets.token_urlsafe(12)
URL = "http://127.0.0.1:8000"
gw = subprocess.Popen([sys.executable, "-m", "jevgw", "--port", "8000", "--key", KEY, "--llama-bin", LLAMA_BIN,
                       "--root", os.path.abspath("vendor"), "--work", os.path.abspath("work")])
for _ in range(60):
    try:
        urllib.request.urlopen(URL + "/healthz", timeout=2)
    except urllib.error.HTTPError:
        break  # a 503 is fine: it is up, just no model yet
    except OSError:
        time.sleep(1)
client = Client(URL, KEY)
from google.colab import output
output.serve_kernel_port_as_iframe(8000, path=f"/#key={{KEY}}", height="900")  # the panel, inside this notebook"""),
        code("""t = time.time()
client.select(MODEL)
print("loaded", MODEL, "in", round(time.time() - t), "s")"""),
        md(
            "### Test it\nFive timed calls per test after one warm-up. Video goes in as sampled frames. Set `IMAGE` / `VIDEO` to your own files (upload them in the Files panel)."
        ),
        code("""IMAGE = ""  #@param {type:"string"}
VIDEO = ""  #@param {type:"string"}
from jevgw import client as jc
rows = jc.demo(client, IMAGE or None, VIDEO or None, frames=6, n=5)
for r in rows:
    print(r["test"], "->", json.dumps(r["answers"])[:200])"""),
        md(
            "### Switch to another model\nThe current one is unloaded first. A model that does not fit this GPU is refused with the reason."
        ),
        code(f"""MODEL = "laya"  #@param {json.dumps(ids)}
client.select(MODEL)
rows = jc.demo(client, IMAGE or None, VIDEO or None, frames=6, n=5)"""),
        md("""## 5. Serve mode (opt-in): a public endpoint
**Read this first.** Colab's FAQ lists, for all runtimes, "web service offerings not related to interactive compute with Colab" and
"connecting to remote proxies", and for free runtimes "bypassing the notebook UI to interact primarily via a web UI". It also says
"Runtimes will time out if you are idle." A public endpoint is the kind of thing those lines describe, and the audio loop is a workaround for the
idle timeout. Google may disconnect the session or restrict your Colab use. It is your account and your call. For anything you want to keep running,
host the gateway on a GPU machine that allows serving (`python -m jevgw --tunnel`).

What this does: opens a free Cloudflare quick tunnel (testing only: no uptime promise, the URL changes if it restarts, 200 requests in flight at most,
no streaming), keeps it alive with a watchdog, and plays a silent audio loop. Every call needs the API key."""),
        code(
            """SERVE = False  #@param {type:"boolean"}
if SERVE:
    tunnel = client.tunnel("start")
    sample = {"state": "Our checkout is returning errors.", "questions": {"outage": {"type": "noul", "instructions": "Is a service down?"}}}
    print("endpoint:", tunnel["url"])
    print("key     :", KEY)
    print(f"curl {tunnel['url']}/v1/systemone -H 'Authorization: Bearer {KEY}' -H 'Content-Type: application/json' -d '{json.dumps(sample)}'")
else:
    print("Serve mode is off.")"""
        ),
        code(KEEP_ALIVE),
        code("""# status: run again any time. The URL changes if the tunnel restarted.
print("tunnel:", client.tunnel())
s = client.models()
print("loaded:", s["loaded"], "| load", s["load_s"], "s | warm-up", s["warm_ms"], "ms")
for model, v in client.stats().items():
    print(f"{model:<18} {v['requests']:>5} calls, {v['errors']} errors, p50 {v['p50_ms']} ms, p95 {v['p95_ms']} ms")"""),
        md("## 6. Stop\nFrees the GPU and closes the tunnel."),
        code("gw.terminate()"),
    ]


if __name__ == "__main__":
    notebook = {
        "cells": build(),
        "metadata": {
            "accelerator": "GPU",
            "colab": {"provenance": []},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    out = HERE / "clef_colab.ipynb"
    out.write_text(json.dumps(notebook, indent=1))
    print(f"wrote {out.name}: {out.stat().st_size / 1024:.0f} KB, {len(notebook['cells'])} cells")
