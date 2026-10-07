#!/usr/bin/env python3
"""Write clef_colab.ipynb. The notebook clones this folder from GitHub. `--embed` instead packs the code into the notebook (a base64 tarball),
for use before the code is published. Edit the files, then rerun this."""
import base64, io, json, sys, tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ["gateway.py", "try_it.py", "models.json", "setup_llama.sh"]


def bundle():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for f in FILES:
            t.add(HERE / f, arcname=f)
        t.add(HERE / "vendor", arcname="vendor", filter=lambda i: None if "__pycache__" in i.name else i)
    return base64.b64encode(buf.getvalue()).decode()


def md(s): return {"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(True)}
def code(s): return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip("\n").splitlines(True)}


CLONE = '''# clones just this folder from GitHub (a sparse clone: the repo holds more than the notebook needs)
REPO = "https://github.com/mvp-scale/workspace"  #@param {type:"string"}
BRANCH = "main"  #@param {type:"string"}
SUBDIR = "colab"  #@param {type:"string"}  # leave empty if the repo root is this folder
import os, subprocess
def sh(c): subprocess.run(c, shell=True, check=True)
sh("rm -rf /content/src")
sh(f"git clone -q --depth 1 --branch {BRANCH} " + (f"--filter=blob:none --sparse {REPO} /content/src && git -C /content/src sparse-checkout set {SUBDIR}" if SUBDIR else f"{REPO} /content/src"))
os.chdir(f"/content/src/{SUBDIR}")
print(os.getcwd(), sorted(os.listdir()))'''
if "--embed" in sys.argv:
    CLONE = f'''# the code travels inside this notebook (built with --embed)
import base64, io, os, tarfile
BUNDLE = "{bundle()}"
tarfile.open(fileobj=io.BytesIO(base64.b64decode(BUNDLE)), mode="r:gz").extractall("/content/clef")
os.chdir("/content/clef")
print(os.getcwd(), sorted(os.listdir()))'''

ids = [m["id"] for m in json.loads((HERE / "models.json").read_text())["models"] if m.get("kind") in ("llama", "proc")]
cells = [
    md("""# Try the Jev-class models on a Colab GPU
One model on the GPU at a time. Load it, call it with text, an image and a video, see the response times, switch to another.
Everything runs and is called **from this notebook**. Run the cells top to bottom.

**Terms.** Colab's FAQ disallows "web service offerings not related to interactive compute", so this notebook does not open a public URL or keep the session alive. See the README."""),
    md("## 1. Get the code"),
    code(CLONE),
    md("## 2. Which GPU, and which models fit it"),
    code('''import json, subprocess
print(subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"], capture_output=True, text=True).stdout or "NO GPU: Runtime > Change runtime type > GPU")
import gateway
gpu, mib = gateway.gpu_info()
g = gateway.Gateway.__new__(gateway.Gateway); g.gpu, g.gpu_mib = gpu, mib
for m in json.load(open("models.json"))["models"]:
    if m.get("kind") in ("llama", "proc"):
        print(("fits   " if g.fits(m) else "NO FIT ") + f"{m['id']:<17} {m['vram_gib']:>5} GiB  {m['name']}")'''),
    md("""## 3. Install the llama.cpp server (Clef Flash Q4 and Q2 use it)
A T4 has no ready-made code in the official build, so the first start compiles it (slow once). For speed, host the prebuilt `llama-b11430-t4.tar.gz` and put its URL below; see the README."""),
    code('''LLAMA_T4_URL = ""  #@param {type:"string"}
import os
os.environ["LLAMA_T4_URL"] = LLAMA_T4_URL
LLAMA = !LLAMA_DIR=$PWD/llama ./setup_llama.sh
LLAMA_BIN = LLAMA[-1]
print(LLAMA_BIN)'''),
    md("## 4. Start the gateway and load a model\nThe first load of a model installs its packages and downloads its weights (minutes). Later loads are fast."),
    code(f'''MODEL = "clef-flash-q4km"  #@param {json.dumps(ids)}
import subprocess, sys, time, urllib.request, json, secrets
KEY = secrets.token_urlsafe(12)
URL = "http://127.0.0.1:8000"
gw = subprocess.Popen([sys.executable, "gateway.py", "--port", "8000", "--key", KEY, "--llama-bin", LLAMA_BIN, "--root", os.path.abspath("vendor"), "--work", os.path.abspath("work")])
time.sleep(2)
import try_it
t = time.time(); status = try_it.select(URL, KEY, MODEL)
print("loaded:", status.get("loaded"), "in", round(time.time() - t), "s", status.get("error") or "")'''),
    md("## 5. Test it: text, image, video\nFive timed calls each after one warm-up. Video goes in as sampled frames. Set `IMAGE` / `VIDEO` to your own files (use the Files panel to upload)."),
    code('''IMAGE = ""  #@param {type:"string"}
VIDEO = ""  #@param {type:"string"}
import json
rows = try_it.demo(URL, KEY, IMAGE or None, VIDEO or None, frames=6, n=5)
for r in rows:
    print(r["test"], "->", json.dumps(r["answers"])[:200])'''),
    md("## 6. Switch to another model\nThe current model is unloaded first. A model that does not fit this GPU is refused with the reason."),
    code('''MODEL = "laya"  #@param ''' + json.dumps(ids) + '''
t = time.time(); status = try_it.select(URL, KEY, MODEL)
print("loaded:", status.get("loaded"), "in", round(time.time() - t), "s", status.get("error") or "")
rows = try_it.demo(URL, KEY, IMAGE or None, VIDEO or None, frames=6, n=5)'''),
    md("## 7. Stop\nFrees the GPU."),
    code("gw.terminate()"),
]
nb = {"cells": cells, "metadata": {"accelerator": "GPU", "colab": {"provenance": []}, "kernelspec": {"display_name": "Python 3", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
(HERE / "clef_colab.ipynb").write_text(json.dumps(nb, indent=1))
print("wrote clef_colab.ipynb:", round((HERE / "clef_colab.ipynb").stat().st_size / 1024), "KB,", len(cells), "cells")
