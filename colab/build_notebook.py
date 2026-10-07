#!/usr/bin/env python3
"""Write jevgw_colab.ipynb: ONE self-contained notebook. Upload it to Colab and run it; nothing else is needed.

The gateway's source files are written out by `%%writefile` cells, so the notebook needs no clone and no repository; its only
downloads are llama.cpp and the model files. The files come from this folder, so edit them here and rerun this script.
The model list is cut to the models that run on stock llama.cpp, since the others need our adapter code.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = "/content/gw"  # where the notebook writes the gateway
SOURCES = sorted(p.name for p in (HERE / "jevgw").glob("*.py"))  # every module, so the notebook can never lack one


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


def writefile(path: str, text: str) -> dict:
    """A cell that writes `text` to `path`, so the notebook carries the source as plain, readable text."""
    return code(f"%%writefile {path}\n{text.rstrip()}\n")


def standalone_catalog() -> dict:
    data = json.loads((HERE / "models.json").read_text())
    data["models"] = [m for m in data["models"] if m["kind"] == "llama"]
    data["note"] = (
        "Models that run on stock llama.cpp. vram_gib is the measured peak GPU memory (our RTX 5090, -ub 16384, with the vision projector)."
    )
    return data


KEEP_ALIVE = """# a silent audio loop: some people report it keeps the tab counted as active. Google does not document this, it can stop working,
# and it does not lift the 12 hour limit. Keep this tab open and in the foreground.
import base64, io, wave
from IPython.display import HTML, display
buf = io.BytesIO()
with wave.open(buf, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(b"\\x00\\x00" * 8000)
display(HTML('<audio autoplay loop controls style="width:100%"><source src="data:audio/wav;base64,' + base64.b64encode(buf.getvalue()).decode() + '"></audio>'))"""


def build() -> list[dict]:
    catalog = standalone_catalog()
    ids = [m["id"] for m in catalog["models"]]
    files = [writefile(f"{APP}/jevgw/{name}", (HERE / "jevgw" / name).read_text()) for name in SOURCES]
    files.append(writefile(f"{APP}/jevgw/ui/index.html", (HERE / "jevgw" / "ui" / "index.html").read_text()))
    return [
        md("""# Jev gateway on a Colab GPU
Try a typed-decision classifier on a free GPU: load a model, ask it questions with text, an image or video frames, and see how fast it answers.

**How to use: Runtime > Change runtime type > T4 GPU, then Runtime > Run all.** That is the whole setup. It installs what it needs, downloads
the model (a few minutes the first time, with progress shown) and opens a control panel.

**Every cell is safe to run again.** Stuck or something looks wrong? Run the cell again; it picks up where it is. If that does not help,
run the **Reset** cell at the bottom, then Run all.

* **Disk is budgeted.** Colab's disk is small, so only the last two models used stay downloaded; loading a third deletes the oldest first.
* **Interactive by default.** The public URL and the keep-alive audio (step 6) are opt-in; read the note there first."""),
        md(
            "## 1. Set up\nThese cells write the gateway's source files into the Colab machine. You do not need to read or change them. To add a model, add one entry to `models.json`."
        ),
        code(f"!mkdir -p {APP}/jevgw/ui /content/work"),
        *files,
        writefile(f"{APP}/models.json", json.dumps(catalog, indent=1)),
        writefile(f"{APP}/setup_llama.sh", (HERE / "setup_llama.sh").read_text()),
        md("## 2. Check the GPU"),
        code(f"""import os, subprocess, sys
sys.path.insert(0, "{APP}")
for name in [n for n in sys.modules if n == "jevgw" or n.startswith("jevgw.")]:
    del sys.modules[name]  # pick up the files written above, even if this notebook ran an older copy before
from jevgw import catalog

gpu_line = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], capture_output=True, text=True).stdout
if not gpu_line:
    raise SystemExit("No GPU. Runtime > Change runtime type > T4 GPU, then run this cell again.")
print(gpu_line)
gpu, mib = catalog.gpu_info()
for m in catalog.load("{APP}/models.json").values():
    print(("fits   " if catalog.fits(m, mib) else "NO FIT ") + f"{{m['id']:<17}} {{m['vram_gib']:>5}} GiB GPU, {{m['file_gib'] + m.get('mmproj_gib', 0):.1f}} GiB download  {{m['name']}}")
print(subprocess.run(["df", "-h", "/content"], capture_output=True, text=True).stdout)"""),
        md(
            "## 3. Install the llama.cpp server\nTakes about a minute the first time. Run again if it fails: a broken install is removed and redone."
        ),
        code("""LLAMA_T4_URL = ""  #@param {type:"string"}  # optional: a prebuilt T4 build (faster first start); see the README
from jevgw import notebook
LLAMA_BIN = notebook.ensure_llama(LLAMA_T4_URL)"""),
        md(
            "## 4. Start the gateway and open the control panel\nRun it as often as you like: a running gateway is reused (same key), a stuck one is replaced, a busy port is skipped. The panel loads, unloads, enables, disables and deletes models."
        ),
        code("""KEEP = 2  #@param {type:"integer"}  # models kept on disk
API_KEY = ""  #@param {type:"string"}  # leave empty for a random key (it is printed below); or choose your own
client, info = notebook.start(LLAMA_BIN, KEEP, key=API_KEY)
KEY = info["key"]
notebook.show_panel(info)"""),
        md(
            "## 5. Load a model and test it\nThe first load downloads the model and shows progress. If it fails it retries; run the cell again to try again. Or use the panel above."
        ),
        code(f"""MODEL = "clef-flash-q4km"  #@param {json.dumps(ids)}
notebook.wait_ready(client, MODEL)"""),
        code("""IMAGE = ""  #@param {type:"string"}  # optional: a path to your own image
VIDEO = ""  #@param {type:"string"}  # optional: a path to your own video (upload it in the Files panel)
import json
from jevgw import client as jc
rows = jc.demo(client, IMAGE or None, VIDEO or None, frames=6, n=5)  # five timed calls per test, after one warm-up
for r in rows:
    print(r["test"], "->", json.dumps(r["answers"])[:200])"""),
        md("""## 6. Serve mode (opt-in): a public endpoint
**Read this first.** Colab's FAQ lists, for all runtimes, "web service offerings not related to interactive compute with Colab" and
"connecting to remote proxies", and for free runtimes "bypassing the notebook UI to interact primarily via a web UI". It also says
"Runtimes will time out if you are idle." A public endpoint is the kind of thing those lines describe, and the audio loop is a workaround for the
idle timeout. Google may disconnect the session or restrict your Colab use. It is your account and your call. For anything you want to keep running,
host the gateway on a GPU machine that allows serving (`python -m jevgw --tunnel`).

What this does: opens a free Cloudflare quick tunnel (testing only: no uptime promise, the URL changes if it restarts, 200 requests in flight at most,
no streaming), keeps it alive with a watchdog, and plays a silent audio loop. The URL serves the API only, not the panel, and every call needs the API key."""),
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
print("loaded:", s["loaded"], "| load", s["load_s"], "s | warm-up", s["warm_ms"], "ms | disk free", s["disk"]["free_gib"], "GiB")
for model, v in client.stats().items():
    print(f"{model:<18} {v['requests']:>5} calls, {v['errors']} errors, p50 {v['p50_ms']} ms, p95 {v['p95_ms']} ms")"""),
        md(
            "## 7. Stop or reset\nLeave this on `nothing` for Run all. **stop** frees the GPU and closes the tunnel. **reset** also clears any half-finished state (a stuck download or load); then Run all starts clean. Downloaded models are kept unless you pick the last option."
        ),
        code("""ACTION = "nothing"  #@param ["nothing", "stop", "reset", "reset and delete downloaded models"]
if ACTION == "stop":
    notebook.stop()
    print("stopped. Run step 4 to start again.")
elif ACTION.startswith("reset"):
    notebook.reset(delete_models=ACTION.endswith("models"))
else:
    print("nothing to do")"""),
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
    out = HERE / "jevgw_colab.ipynb"
    out.write_text(json.dumps(notebook, indent=1))
    print(f"wrote {out.name}: {out.stat().st_size / 1024:.0f} KB, {len(notebook['cells'])} cells")
