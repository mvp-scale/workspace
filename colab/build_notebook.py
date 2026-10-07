#!/usr/bin/env python3
"""Write jevgw_colab.ipynb: a short, readable notebook that installs the `jevgw` package from this public repository at a fixed release tag.

Nothing is bundled in the file: the one install cell names the repository and the exact version, so anyone can read what runs. The other cells
are titled form cells (code hidden until you expand it) that call the package. The model table and the model dropdown are generated from the
package's model list, so the notebook cannot disagree with it. Run this after changing the list, and tag the release (see the README).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jevgw import __version__

HERE = Path(__file__).resolve().parent
REPO = "https://github.com/mvp-scale/workspace"  # public: everything the notebook installs is readable here
SUBDIR = "colab"
REF = f"v{__version__}"  # the exact release the notebook installs, never a branch that moves
T4_GIB = 14.0  # usable memory on Colab's free GPU, in GiB, for the dropdown and the table


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(True)}


def code(text: str, title: str) -> dict:
    """A form cell: Colab shows only `title` and the parameters, with the code one click away."""
    return {
        "cell_type": "code",
        "metadata": {"cellView": "form"},
        "execution_count": None,
        "outputs": [],
        "source": f"#@title {title}\n{text.strip(chr(10))}".splitlines(True),
    }


def t4_models() -> list[dict]:
    models = json.loads((HERE / "jevgw" / "data" / "models.json").read_text())["models"]
    return [m for m in models if m["kind"] in ("llama", "proc") and 0 < m.get("vram_gib", 0) <= T4_GIB]


def table(models: list[dict]) -> str:
    rows = ["| Model | What it takes | GPU memory | Download | Typical first-time total |", "|---|---|---|---|---|"]
    for m in models:
        takes = "text, images, video" if m.get("vision") else "text"
        size = (m.get("file_gib", 0) + m.get("mmproj_gib", 0)) or m.get("install_gib", 0)
        rows.append(
            f"| **{m['name']}** (`{m['id']}`) | {takes} | {m['vram_gib']} GiB | about {size:.0f} GB | {m.get('first_run_min', '?')} min |"
        )
    return "\n".join(rows)


INTRO = """# Try type-safe open-source models on a free Colab GPU
These models answer **typed questions** (yes/no, multiple choice, a score) with probabilities instead of prose. This notebook loads one at a
time on Colab's free **T4 GPU**, opens the **Jev console** in its own browser tab (a control panel with a test box and response times), and shows how fast each answers.

**Quick start:** *Runtime → Change runtime type → T4 GPU*, then *Runtime → Run all*. Every cell is safe to run again.

### What will happen
| Step | What it does | Typical time |
|---|---|---|
| 1 · Install | Checks the GPU, disk, network and tools, installs the gateway, and installs llama.cpp for the Clef models | 1–2 min |
| 2 · Start | Starts the gateway and gives you a link that opens the Jev console in its own tab | seconds |
| 3 · Load a model | Pre-flight check (GPU memory, disk, network), then download or install, then start | **2–9 min the first time** (table below); seconds if it is already on disk |
| 4 · Test | Times five calls with text, and an image and a video for models that take them | under a minute |
| 7 · Console | Shows the link again and explains each part of the console | seconds |

### Good to know
* **You will see it working.** Each step prints what it is doing, a line whenever the phase changes, and the elapsed time and the latest log line
  every 30 seconds. If **no new line appears for 5 minutes**, run that cell again: it is safe and picks up where it was.
* **A Hugging Face token makes downloads faster (recommended).** Add it before you run: the key icon in Colab's left sidebar → *Add new secret* →
  name `HF_TOKEN`, value a [read token](https://huggingface.co/settings/tokens) → turn on *Notebook access*. It works without one, just slower.
* **The first model is the slow one.** Besides downloading, the GPU compiles its code once (about a minute). Later models and reloads are quicker.
* **Speed:** an answer comes back in roughly 0.2–1.2 seconds depending on the model. A single T4 serves about 2–3 requests per second; beyond that
  the endpoint answers `429` with a `Retry-After` header. Plenty for trying a model; it is not a production server.
* **One model at a time** is on the GPU. Colab's disk is small, so only the two most recently used models stay downloaded; older ones are deleted
  automatically before a new download.
* **GPU only.** If the GPU can't be used (no GPU, a driver too old, not enough free GPU memory), the notebook stops before downloading anything and says
  why, instead of running slowly on the CPU."""

TERMS = """### Optional: a public endpoint
Colab's FAQ lists "web service offerings not related to interactive compute" and "connecting to remote proxies" among the things it does not
allow, and says idle runtimes time out. A public URL is the kind of thing those lines describe, so it is **off by default**: use the notebook and
its panel, which is interactive. Turning it on opens a free Cloudflare quick tunnel (testing only: the URL changes if it restarts, and it needs
your API key on every call). Google may disconnect the session or restrict your account; it is your call. The silent-audio keep-alive some people
use is undocumented and may stop working; this notebook does not play it."""


def build() -> list[dict]:
    models = t4_models()
    ids = [m["id"] for m in models]
    return [
        md(INTRO),
        md("### Models that fit a T4\n" + table(models)),
        md(
            "### Where the code comes from\n"
            f"Cell 1 installs the Jev gateway package, version `{REF}`, from the public repository {REPO} (folder `{SUBDIR}`). "
            "Everything it installs is readable there at that tag; nothing is bundled inside this file. The only other downloads are the tools and models listed here."
        ),
        md("## 1 · Install and check the machine"),
        code(
            f"""REPO, REF = "{REPO}", "{REF}"  # the public repository and the exact release this notebook installs
import shutil, subprocess, sys
from importlib.metadata import PackageNotFoundError, version

def stop(message):
    raise SystemExit(message) from None  # one clear message, no chained traceback

if not shutil.which("nvidia-smi"):
    stop("No GPU found. Runtime > Change runtime type > T4 GPU, then run this cell again.")
try:
    have = version("jevgw")
except PackageNotFoundError:
    have = None
if have == REF[1:]:
    print(f"The Jev gateway package {{REF}} is already installed.")
else:
    published = subprocess.run(["git", "ls-remote", "--exit-code", "--tags", REPO, f"refs/tags/{{REF}}"], capture_output=True)
    if published.returncode == 2:  # git's code for "no such tag": say so plainly, before pip's long error
        stop(f"Release {{REF}} is not published at {{REPO}}. Check that you have the latest copy of this notebook.")
    print(f"Installing the Jev gateway package {{REF}} from {{REPO}} (10-20 seconds)...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-q", f"jevgw @ git+{{REPO}}@{{REF}}#subdirectory={SUBDIR}"],
                            capture_output=True, text=True)
    if result.returncode:
        stop(f"Could not install the Jev gateway package from GitHub:\\n{{result.stderr[-800:]}}\\nCheck the connection and run this cell again.")
    for name in [n for n in sys.modules if n == "jevgw" or n.startswith("jevgw.")]:
        del sys.modules[name]  # use the version just installed, not an older one this session already imported
from jevgw import notebook
LLAMA_BIN = notebook.setup()""",
            "1 · Install and check the machine (about 1–2 minutes)",
        ),
        md(
            "## 2 · Start the gateway\nThe API key is printed below and used by every call. Leave the field empty for a random one, or choose your own."
        ),
        code(
            """API_KEY = ""  #@param {type:"string"}
client, info = notebook.start(LLAMA_BIN, key=API_KEY)
KEY = info["key"]
notebook.show_panel(info)""",
            "2 · Start the gateway and open the control panel",
        ),
        md(
            "## 3 · Load a model\nPick one and run the cell (or use the panel above). Progress is shown; if a download fails it retries."
        ),
        code(
            f"""MODEL = "clef-flash-q4km"  #@param {json.dumps(ids)}
notebook.wait_ready(client, MODEL)""",
            "3 · Load a model",
        ),
        md(
            "## 4 · Test it\nFive timed calls with text, then an image and a video's frames for models that take them. Your own files are optional."
        ),
        code(
            """IMAGE = ""  #@param {type:"string"}
VIDEO = ""  #@param {type:"string"}
notebook.test(client, IMAGE, VIDEO)""",
            "4 · Test the loaded model",
        ),
        md("## 5 · Optional: a public endpoint\n" + TERMS.split("\n", 1)[1]),
        code(
            """SERVE = False  #@param {type:"boolean"}
if SERVE:
    tunnel = client.tunnel("start")
    print("Jev console (manage the gateway from any browser):", tunnel["url"] + "/#key=" + KEY)
    print("  or open", tunnel["url"], "and enter the API key:", KEY)
    print("API endpoint:", tunnel["url"] + "/v1/systemone", "   (check it first: open", tunnel["url"] + "/healthz)")
    print(f'curl {tunnel["url"]}/v1/systemone -H "Authorization: Bearer {KEY}" -H "Content-Type: application/json" '
          '-d \\'{"state": "Checkout is failing.", "questions": {"outage": {"type": "noul", "instructions": "Is a service down?"}}}\\'')
else:
    print("The public endpoint is off.")""",
            "5 · Public endpoint (off by default)",
        ),
        md(
            "## 6 · Stop or reset\nLeave on *nothing* for Run all. *reset* also clears a stuck download or load; downloaded models are kept unless you pick the last option."
        ),
        code(
            """ACTION = "nothing"  #@param ["nothing", "stop", "reset", "reset and delete downloaded models"]
if ACTION == "stop":
    notebook.stop()
elif ACTION.startswith("reset"):
    notebook.reset(delete_models=ACTION.endswith("models"))""",
            "6 · Stop or reset",
        ),
        md("## 7 · Use the Jev console\nThe last cell reopens the console here and explains what each part does."),
        code("notebook.console(client, info)", "7 · Open the Jev console and how to use it"),
    ]


def with_ids(cells: list[dict]) -> list[dict]:
    """nbformat 4.5 requires an id on every cell. Derive it from the cell, so rebuilding gives the same file."""
    for index, cell in enumerate(cells):
        first = "".join(cell["source"]).splitlines()[0] if cell["source"] else ""
        cell["id"] = hashlib.sha1(f"{index}:{first}".encode()).hexdigest()[:8]
    return cells


if __name__ == "__main__":
    notebook = {
        "cells": with_ids(build()),
        "metadata": {
            "accelerator": "GPU",
            "colab": {"provenance": [], "gpuType": "T4"},
            "kernelspec": {"display_name": "Python 3", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    out = HERE / "jevgw_colab.ipynb"
    out.write_text(json.dumps(notebook, indent=1) + "\n")
    print(f"wrote {out.name}: {out.stat().st_size / 1024:.0f} KB, {len(notebook['cells'])} cells")
