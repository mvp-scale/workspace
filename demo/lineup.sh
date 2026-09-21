#!/bin/bash
# The models the console keeps loaded, as systemd services.
#   demo/lineup.sh install   write and enable the unit files (idempotent), retiring the old kev/jeff services
#   demo/lineup.sh up|down|status
# Order matters: kev-4b needs about 17 GiB for a few seconds while loading, so it starts first; the rest wait for it.
# Memory (measured, see demo/vram.json): kev-4b bf16 9.8, SemIf 8.6, open-alternative-jev 8.6, Laya 3.1, Verdict CPU = about 30 of 31.8 GiB.
set -euo pipefail
U=/etc/systemd/system
LINEUP="kev-4b semif so1 laya verdict"
declare -A PORT=( [kev-4b]=8010 [semif]=8012 [so1]=8013 [laya]=8014 [verdict]=8015 )

unit_kev() { cat <<EOT
[Unit]
Description=kev-4b (bf16): pointer-head decision model on Qwen3.5-4B-Base
After=network.target

[Service]
WorkingDirectory=/workspace/kev
Environment=HF_HOME=/workspace/data/kev/hf-cache
Environment=KEV_DTYPE=bf16
Environment=PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
ExecStart=/workspace/kev/.venv/bin/python /workspace/demo/serve_kev.py --run jaredpalmer/kev-4b --port 8010
Restart=on-failure
RestartSec=5
StandardOutput=append:/workspace/logs/kev-4b.log
StandardError=append:/workspace/logs/kev-4b.err.log

[Install]
WantedBy=multi-user.target
EOT
}
unit_inproc() { cat <<EOT
[Unit]
Description=$1 served through its jevbench adapter (same code as its benchmark numbers)
After=network.target kev-4b.service

[Service]
WorkingDirectory=/workspace/jevbench
Environment=HF_HOME=/workspace/data/models/hf-cache
TimeoutStartSec=900
ExecStartPre=/bin/bash -c 'until curl -sf http://127.0.0.1:8010/v1/models >/dev/null; do sleep 2; done'
ExecStart=/workspace/models/$1/.venv/bin/python /workspace/demo/serve_inproc.py --model $1 --port ${PORT[$1]}
Restart=on-failure
RestartSec=5
StandardOutput=append:/workspace/logs/$1.log
StandardError=append:/workspace/logs/$1.err.log

[Install]
WantedBy=multi-user.target
EOT
}

case "${1:-status}" in
  install)
    unit_kev > $U/kev-4b.service
    for m in semif so1 laya verdict; do unit_inproc $m > $U/$m.service; done
    systemctl daemon-reload
    systemctl disable --now kev-proxy kev jeff 2>/dev/null || true   # retired: kev-0.5b, kev-0.8b and jeff no longer fit next to the top models
    systemctl enable kev-4b semif so1 laya verdict ;;
  up)   systemctl start kev-4b; for m in semif so1 laya verdict; do systemctl start --no-block $m; done ;;
  down) systemctl stop verdict laya so1 semif kev-4b ;;
  status) for m in $LINEUP; do printf "%-9s :%s  %s\n" $m ${PORT[$m]} "$(systemctl is-active $m)"; done; nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader ;;
esac
