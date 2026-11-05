#!/bin/bash
# T36 step 4: the hunted trait questions (bundle B13, 1520 tasks). Clef first, then Gemma and Qwen through run_gq.sh (restores voice and Clef on exit).
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
F="t_x005 t_x006 t_x011 t_x012 t_x013 t_x016 t_x018 t_x024 t_x026 t_x027 t_x028 t_x029 t_x031 t_x032 t_x041 t_x042 t_x046 t_x048 t_x050"
python3 $X/run.py --bundle runs/xtest/B13 --variant A --rater $X/raters/clef.json --fields $F --order-seed 0 --workers 8 --cap-usd 1 || echo "FAILED clef"
$X/run_gq.sh runs/xtest/B13 "$F" A 0
