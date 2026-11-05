#!/bin/bash
# T36 natural confirmation: Gemma and Qwen on bundle B14 (11 traits x 800 natural items). run_gq.sh restores voice and Clef on exit.
cd /workspace/knowledge_pipeline/projects/world-state; X=/workspace/knowledge_pipeline/xtest
F="t_x025 t_x034 t_x012 t_x013 t_x016 t_x018 t_x024 t_x026 t_x027 t_x028 t_x031"
$X/run_gq.sh runs/xtest/B14 "$F" A 0
