"""Static export of the read-only parts of the demo, for Cloudflare Pages (or any static host).

    python3 demo/build_static.py

Regenerates `dist/` from scratch out of whatever's currently in data/bench/, data/probe-runs-v2/
and probes/v2/ -- run again any time that data changes; dist/ itself is never hand-edited (it's
gitignored, like data/). Every JSON file below is produced by calling the exact same functions
demo/server.py's live GET routes call -- nothing here is reimplemented or recomputed differently.

Ships the four pages that have no live model calls anywhere in them -- Leaderboard, Scenario lab,
How they work, Report -- as plain static files: no key, no GPU, no server process needed to view
them. Baseline compare is deliberately not included; it's a genuinely live page (a free-typed
question to every backend) with no static equivalent. Conversation flow ships as a *recorded*
summary (flow_recordings.html) built from whatever real exports sit in data/flow-recordings/ --
see demo/flow.html's own "Export" button for how those are produced; nothing here calls a model.
"""
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import server  # noqa: E402 -- reuses server.py's own functions; never reimplement the same logic twice

DIST = HERE.parent / "dist"
PAGES = ["index.html", "scenarios.html", "models.html", "report.html", "flow-recordings.html"]
RECORDINGS_DIR = HERE.parent / "data" / "flow-recordings"


def write_json(rel_path, data):
    full = DIST / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(json.dumps(data))


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    for page in PAGES:
        html = (HERE / page).read_text()
        if page == "index.html":
            # Same clean-URL-vs-real-filename issue as app.js's NAV: the Leaderboard's per-model
            # links point at /models#<id>, which only resolves on a host that maps clean URLs to
            # .html files (Cloudflare Pages does; a plain static server doesn't).
            old_link = "href: `/models#${r.id}`"
            new_link = "href: `/models.html#${r.id}`"
            assert old_link in html, "model-card link in index.html has changed -- update build_static.py's substitution"
            html = html.replace(old_link, new_link)
        (DIST / page).write_text(html)
    static_out = DIST / "static"
    static_out.mkdir()
    for f in (HERE / "static").iterdir():
        if not f.is_file():
            continue
        if f.name == "app.js":
            # The shared nav is clean-URL (/scenarios, no extension), which Cloudflare Pages
            # resolves to scenarios.html automatically -- but a plain static file server (or
            # file://) can't. Point the copy shipped in dist/ at the real filenames instead, and
            # drop the two pages that only exist live (Baseline compare, Conversation flow) so
            # there are no dead links in a build that's meant to stand alone.
            js = f.read_text()
            old_nav = '  const NAV = [["/", "Leaderboard"], ["/compare", "Baseline compare"], ["/scenarios", "Scenario lab"], ["/flow", "Conversation flow"], ["/models", "How they work"], ["/report", "Report"]];'
            new_nav = '  const NAV = [["/index.html", "Leaderboard"], ["/scenarios.html", "Scenario lab"], ["/flow-recordings.html", "Conversation flow"], ["/models.html", "How they work"], ["/report.html", "Report"]];'
            assert old_nav in js, "NAV literal in app.js has changed -- update build_static.py's substitution"
            js = js.replace(old_nav, new_nav).replace('href: "/" }, "Jev Bench "', 'href: "/index.html" }, "Jev Bench "')
            (static_out / "app.js").write_text(js)
        else:
            shutil.copy2(f, static_out / f.name)

    # Shared + Leaderboard + How they work + Report
    write_json("api/models", json.loads((HERE / "models.json").read_text()))
    write_json("api/leaderboard", server.leaderboard())
    write_json("api/agreement", server.probe_agreement())
    write_json("api/probe-macro", server.probe_macro())
    write_json("api/vram", server.vram())

    # Scenario lab
    sets = server.probe_sets()
    write_json("api/probes", sets)
    for s in sets:
        write_json(f"api/probe/{s['id']}.json", server.probe_detail(s["id"]))
    write_json("api/batch-perf", server.batch_perf())
    write_json("api/decompose-tree", server.decompose_tree())
    write_json("api/monte-carlo", server.monte_carlo_schedule())
    write_json("api/decompose-examples", server.decompose_examples())
    write_json("api/hierarchy", server.hierarchy_study())
    write_json("api/time-study", server.time_study())
    write_json("api/window-study", server.window_study())
    if server.lcd is not None:
        write_json("api/decompose-library", server.lcd.skeleton(server.lcd.load_library()))
    else:
        print(f"note: skipped api/decompose-library -- {server._LCD_ERROR}")

    # Conversation flow -- recorded, not live. Whatever real exports exist in data/flow-recordings/
    # (see demo/flow.html's own "Export" button) get shipped verbatim; nothing is generated here.
    if RECORDINGS_DIR.is_dir():
        names = sorted(f.name for f in RECORDINGS_DIR.glob("*.json"))
        for name in names:
            write_json(f"api/flow-recordings/{name}", json.loads((RECORDINGS_DIR / name).read_text()))
        write_json("api/flow-recordings/index.json", [{"file": n} for n in names])
        print(f"included {len(names)} conversation-flow recording(s)")
    else:
        write_json("api/flow-recordings/index.json", [])
        print("note: no data/flow-recordings/ directory -- Conversation flow page will show empty")

    n = sum(1 for _ in DIST.rglob("*") if _.is_file())
    size_mb = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file()) / 1e6
    print(f"Wrote {n} files ({size_mb:.1f} MB) to {DIST}")


if __name__ == "__main__":
    main()
