"""Build data/trainset/kt-wiki.jsonl from the fetched Wikipedia leads (weak topic labels, D-0023). Run: python3 -I known_topic_build.py"""
import json, glob, sys
SRC = sys.argv[1] if len(sys.argv) > 1 else "/workspace/data/suite/known_topic/wiki"; DST = sys.argv[2] if len(sys.argv) > 2 else "/workspace/data/trainset/kt-wiki.jsonl"
rows = []
for f in sorted(glob.glob(SRC + "/family*.jsonl" if "family" in SRC else SRC + "/*.jsonl")):
    for l in open(f):
        r = json.loads(l); rows.append({"id": r["id"], "input": r["input"], "topic": r["topic"], "country": "other", "target_keys": [], "P": {}, "source": "wiki-weak"})
open(DST, "w").write("".join(json.dumps(r) + "\n" for r in rows)); print(len(rows))
