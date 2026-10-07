"""python -m jevgw [options]: start the gateway. Prints one JSON line with the local URL and the API key."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import signal
import time
from pathlib import Path

from . import DATA, __version__, catalog
from .backends import install_vendor
from .disk import Disk
from .manager import Gateway
from .server import App, serve
from .tunnel import Tunnel


def parse(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="jevgw", description=__doc__)
    ap.add_argument("--catalog", default=str(DATA / "models.json"), help="the model list and recipes")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1", help="leave as is: the tunnel and the Colab panel reach it locally")
    ap.add_argument(
        "--key", default=os.environ.get("GATEWAY_KEY") or secrets.token_urlsafe(18), help="API key (default: random, printed)"
    )
    ap.add_argument("--model", help="load this model at start")
    ap.add_argument("--only", help="comma-separated ids: every other model starts disabled")
    ap.add_argument(
        "--work",
        default=os.environ.get("JEVGW_WORK", str(Path.home() / ".jevgw")),
        help="logs, downloaded models, installed environments",
    )
    ap.add_argument("--root", help="where model environments and weights are installed (default: <work>/root)")
    ap.add_argument("--keep", type=int, default=2, help="downloaded models kept on disk; the least recently used are deleted")
    ap.add_argument("--disk-margin-gib", type=float, default=5.0, help="free disk space always left alone")
    ap.add_argument("--llama-bin", default=os.environ.get("LLAMA_BIN", "llama-server"))
    ap.add_argument(
        "--tunnel", action="store_true", help="start a Cloudflare quick tunnel at launch (the panel can also start one)"
    )
    ap.add_argument("--no-tunnel-support", action="store_true", help="refuse tunnel requests entirely")
    ap.add_argument(
        "--max-inflight",
        type=int,
        default=0,
        help="concurrent /v1/systemone calls before answering 429 (0: twice the model server's slots)",
    )
    ap.add_argument("--per-minute", type=int, default=600, help="rate limit for /v1/systemone; 0 turns it off")
    return ap.parse_args(argv)


def main(argv=None) -> None:
    args = parse(argv)
    work = Path(args.work)
    root = Path(args.root or work / "root")
    install_vendor(root)
    (work / "weights").mkdir(parents=True, exist_ok=True)
    cfg = {"llama_bin": args.llama_bin, "weights": str(work / "weights"), "work": str(work), "root": str(root),
           "here": str(DATA), "child_port": args.port + 1}  # fmt: skip
    models = catalog.load(args.catalog)
    only = set(args.only.split(",")) if args.only else None
    disk = Disk(cfg["weights"], work / "disk.json", args.keep, args.disk_margin_gib, root=root)
    gateway = Gateway(models, cfg, only, disk)
    tunnel = None if args.no_tunnel_support else Tunnel(args.port, str(work))
    app = App(gateway, args.key, tunnel, str(work), args.max_inflight, args.per_minute)
    server = serve(app, args.port, args.host)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    info = {
        "version": __version__,
        "local": f"http://{args.host}:{args.port}",
        "key": args.key,
        "gpu": gateway.gpu,
        "gpu_gib": round(gateway.gpu_mib / 1024, 1),
    }
    try:
        if args.tunnel and tunnel:
            info["url"] = tunnel.start()["url"]
        print("GATEWAY " + json.dumps(info), flush=True)
        if args.model:
            gateway.select(args.model)
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        if tunnel:
            tunnel.stop()
        server.shutdown()
        gateway.shutdown()


if __name__ == "__main__":
    main()
