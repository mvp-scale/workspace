"""S7 ship check (M7): a clean venv with only the pinned requirements reproduces the harness output byte for byte.

    # 1. in the evaluation harness env, write the reference once:
    python ship_check.py --model-dir ship/x --fixture fixture.jsonl --write-expected expected.jsonl
    # 2. on the ship target (or a fresh CI box):
    python ship_check.py --model-dir ship/x --fixture fixture.jsonl --expected expected.jsonl [--venv /tmp/kitvenv]

Step 2: refuses unpinned requirements (every line `name==version` or `name @ url`), creates a fresh venv
(venv, falling back to virtualenv), pip installs requirements.txt with --no-cache-dir, copies runtime.py + core.py
into a temp package dir, runs `python -I runtime.py --jsonl fixture --workers 1 --threads 1` in the venv, and
compares stdout bytes with the expected file (sha256 + first differing line). Writes ship_log.json (pip freeze,
shas, rc). Exit 0 only on identical output. Never ship on a failed M7: fix the pins and re-run.
The fixture should be synthetic or licence-clear text (it is copied next to the package).
"""
import argparse
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = pathlib.Path(__file__).resolve().parent
PKG_FILES = ("runtime.py", "core.py", "requirements.txt")
PIN = re.compile(r"^[A-Za-z0-9_.\-\[\]]+(==[^\s;]+|\s*@\s*\S+)(\s*;.*)?$")


def bsha(b):
    return hashlib.sha256(b).hexdigest()


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, **kw)
    return r


def check_pins(req):
    bad = []
    for line in open(req, encoding="utf-8"):
        s = line.split("#", 1)[0].strip()
        if s and not PIN.match(s):
            bad.append(s)
    return bad


def make_venv(path):
    shutil.rmtree(path, ignore_errors=True)
    r = run([sys.executable, "-m", "venv", str(path)])
    py = path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if r.returncode or not py.exists() or run([str(py), "-m", "pip", "--version"]).returncode:
        shutil.rmtree(path, ignore_errors=True)
        run([sys.executable, "-m", "pip", "install", "-q", "virtualenv"])
        run([sys.executable, "-m", "virtualenv", str(path)])
    return py


def runtime_cmd(py, pkg, model_dir, fixture):
    return [str(py), "-I", str(pkg / "runtime.py"), "--model-dir", str(model_dir), "--jsonl", str(fixture),
            "--workers", "1", "--threads", "1"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--fixture", required=True, help="JSONL {id, text}")
    ap.add_argument("--expected", help="harness output JSONL (from --write-expected)")
    ap.add_argument("--write-expected", help="write the harness output with the CURRENT interpreter and stop")
    ap.add_argument("--requirements", default=str(HERE / "requirements.txt"))
    ap.add_argument("--venv", default=os.path.join(tempfile.gettempdir(), "student_kit_ship_venv"))
    ap.add_argument("--log", default="ship_log.json")
    a = ap.parse_args(argv)
    model_dir, fixture = pathlib.Path(a.model_dir).resolve(), pathlib.Path(a.fixture).resolve()

    if a.write_expected:
        r = run(runtime_cmd(sys.executable, HERE, model_dir, fixture))
        if r.returncode:
            sys.stderr.write(r.stderr.decode("utf-8", "replace")[-3000:])
            sys.exit(r.returncode)
        open(a.write_expected, "wb").write(r.stdout)
        print(f"[ship] expected written: {a.write_expected} sha256 {bsha(r.stdout)[:16]} ({len(r.stdout)} bytes)")
        return
    if not a.expected:
        raise SystemExit("--expected or --write-expected required")

    t0 = time.time()
    log = {"task": "student-ship-check", "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "model_dir": str(model_dir), "fixture_sha256": bsha(open(fixture, "rb").read()),
           "expected_sha256": bsha(open(a.expected, "rb").read()), "host_python": sys.version.split()[0]}
    bad = check_pins(a.requirements)
    log["requirements_sha256"] = bsha(open(a.requirements, "rb").read())
    if bad:
        log.update(ok=False, error="unpinned requirements", unpinned=bad)
        json.dump(log, open(a.log, "w"), indent=1)
        raise SystemExit(f"unpinned requirements: {bad}")
    venv = pathlib.Path(a.venv)
    py = make_venv(venv)
    r = run([str(py), "-m", "pip", "install", "-q", "--no-cache-dir", "--disable-pip-version-check", "-r",
             a.requirements])
    log["install_rc"] = r.returncode
    if r.returncode:
        log.update(ok=False, install_err=r.stderr.decode("utf-8", "replace")[-2000:])
        json.dump(log, open(a.log, "w"), indent=1)
        raise SystemExit("pip install failed")
    log["pip_freeze"] = run([str(py), "-m", "pip", "freeze"]).stdout.decode().split()
    pkg = pathlib.Path(tempfile.mkdtemp(prefix="student_kit_pkg_"))
    for f in PKG_FILES:
        shutil.copy(HERE / f, pkg / f)
    log["package_sha256"] = {f: bsha(open(pkg / f, "rb").read()) for f in PKG_FILES}
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "CONDA", "VIRTUAL_ENV"))}
    r = run(runtime_cmd(py, pkg, model_dir, fixture), env=env, cwd=str(pkg))
    log["runtime_rc"] = r.returncode
    if r.returncode:
        log.update(ok=False, runtime_err=r.stderr.decode("utf-8", "replace")[-2000:])
        json.dump(log, open(a.log, "w"), indent=1)
        raise SystemExit("runtime failed in the clean venv")
    got, want = r.stdout, open(a.expected, "rb").read()
    log["output_sha256"] = bsha(got)
    log["identical"] = got == want
    if not log["identical"]:
        gl, wl = got.split(b"\n"), want.split(b"\n")
        k = next((i for i in range(min(len(gl), len(wl))) if gl[i] != wl[i]), min(len(gl), len(wl)))
        log["first_diff_line"] = k
        log["lines"] = {"got": len(gl), "want": len(wl)}
    log["ok"] = log["identical"]
    log["wall_s"] = round(time.time() - t0, 1)
    json.dump(log, open(a.log, "w"), indent=1)
    print(f"[ship] identical={log['identical']} output {log['output_sha256'][:16]} expected {log['expected_sha256'][:16]}")
    sys.exit(0 if log["ok"] else 1)


if __name__ == "__main__":
    main()
