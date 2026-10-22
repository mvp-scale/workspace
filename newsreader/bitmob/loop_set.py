#!/usr/bin/env python3
"""python3 newsreader/bitmob/loop_set.py <round> <phase> [of]  : update data/progress/loop.json (read by tools/loop_status.py and the Trainer page)."""
import json, sys, os
f = "/workspace/data/progress/loop.json"
try: d = json.load(open(f))
except Exception: d = {}
if len(sys.argv) < 3: sys.exit(__doc__)
d["round"] = int(sys.argv[1]); d["phase"] = sys.argv[2]
if len(sys.argv) > 3: d["of"] = int(sys.argv[3])
json.dump(d, open(f + ".tmp", "w")); os.replace(f + ".tmp", f); print(d)
