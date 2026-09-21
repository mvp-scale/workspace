#!/bin/bash
# Ground-zero build script. Run ONCE, by hand, inside the container after
# `docker compose up -d`:
#
#   docker compose exec -it dev bash
#   apt update && apt install -y git   # only thing needed before you can even fetch this repo/script
#   bash /workspace/setup.sh
#
# Nothing here is wired into container startup — that's deliberate. Re-run individual
# sections later if you need to (each is idempotent-ish: checks before re-cloning/re-downloading).
set -euo pipefail

TORCH_CUDA_TAG="${TORCH_CUDA_TAG:-cu124}"
TS_HOSTNAME="${TS_HOSTNAME:-dev-full-ubuntu}"
JEFF_API_KEYS="${JEFF_API_KEYS:-devkey}"

echo "=== base packages ==="
apt update && apt install -y --no-install-recommends \
  python3 python3-pip python3-venv \
  git build-essential curl wget vim nano tmux htop jq \
  ripgrep fd-find socat ca-certificates gnupg lsb-release

echo "=== uv (Python) ==="
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.local/bin:$PATH"

echo "=== Node + Claude Code CLI ==="
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt install -y nodejs
npm i -g @anthropic-ai/claude-code

echo "=== GitHub CLI ==="
curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" > /etc/apt/sources.list.d/github-cli.list
apt update && apt install -y gh

echo "=== Jupyter ==="
pip install --break-system-packages jupyterlab

echo "=== Tailscale — apt install so systemd owns it properly (this is what fixes the SSH bug) ==="
curl -fsSL https://tailscale.com/install.sh | sh
systemctl enable --now tailscaled
echo "  -> run manually once: tailscale up --hostname=${TS_HOSTNAME} --ssh"

echo "=== workspace layout ==="
mkdir -p /workspace/data/kev/runs /workspace/data/kev/hf-cache
mkdir -p /workspace/data/jeff/models /workspace/data/jeff/hf-cache
mkdir -p /workspace/logs

echo "=== kev ==="
if [ ! -d /workspace/kev ]; then
    git clone https://github.com/jaredpalmer/kev.git /workspace/kev
fi
if [ ! -d /workspace/kev/.venv ]; then
    (cd /workspace/kev && uv sync --extra serve)
    echo "  -> forcing CUDA torch build (${TORCH_CUDA_TAG}) — kev's own README calls CUDA untested"
    (cd /workspace/kev && uv pip install --python .venv/bin/python \
        torch --index-url "https://download.pytorch.org/whl/${TORCH_CUDA_TAG}")
fi
if [ ! -d /workspace/data/kev/runs/kev ]; then
    curl -fL https://github.com/jaredpalmer/kev/releases/download/v0.1.0/kev-0.5b.tar.gz \
        | tar xz -C /workspace/data/kev/runs
    mv /workspace/data/kev/runs/kev-0.5b /workspace/data/kev/runs/kev
fi

echo "=== jeff ==="
if [ ! -d /workspace/jeff ]; then
    git clone https://github.com/logan-markewich/jeff.git /workspace/jeff
fi
if [ ! -d /workspace/jeff/.venv ]; then
    (cd /workspace/jeff && uv sync --extra dev)
fi
if [ ! -d /workspace/data/jeff/models/gliformer-large-v1 ]; then
    (cd /workspace/jeff && uv run hf download knowledgator/gliformer-large-v1 \
        --local-dir /workspace/data/jeff/models/gliformer-large-v1)
fi

echo "=== jevbench ==="
if [ ! -d /workspace/jevbench ]; then
    git clone https://github.com/fstandhartinger/jevbench.git /workspace/jevbench
fi

echo "=== real systemd units for kev / kev-proxy / jeff — administered like real services ==="

cat > /etc/systemd/system/kev.service <<EOF
[Unit]
Description=kev — open-source Jev-class typed-decision model server
After=network.target

[Service]
WorkingDirectory=/workspace/kev
Environment=HF_HOME=/workspace/data/kev/hf-cache
ExecStart=/workspace/kev/.venv/bin/python -m kev.serve --run /workspace/data/kev/runs/kev --port 8008
Restart=on-failure
RestartSec=3
StandardOutput=append:/workspace/logs/kev.log
StandardError=append:/workspace/logs/kev.err.log

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/kev-proxy.service <<EOF
[Unit]
Description=socat proxy — published 8009 to kev's loopback-only 8008 (kev hardcodes 127.0.0.1)
After=kev.service
Requires=kev.service

[Service]
ExecStart=/usr/bin/socat TCP-LISTEN:8009,fork,reuseaddr,bind=0.0.0.0 TCP:127.0.0.1:8008
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/jeff.service <<EOF
[Unit]
Description=jeff — open-source Jev-class typed-decision model server
After=network.target

[Service]
WorkingDirectory=/workspace/jeff
Environment=JEFF_HOST=0.0.0.0
Environment=JEFF_PORT=8000
Environment=JEFF_API_KEYS=${JEFF_API_KEYS}
Environment=JEFF_MODEL=/workspace/data/jeff/models/gliformer-large-v1
Environment=JEFF_DEVICE=cuda
Environment=HF_HOME=/workspace/data/jeff/hf-cache
ExecStart=/workspace/jeff/.venv/bin/jeff
Restart=on-failure
RestartSec=3
StandardOutput=append:/workspace/logs/jeff.log
StandardError=append:/workspace/logs/jeff.err.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now kev.service kev-proxy.service jeff.service

echo
echo "=== GPU check ==="
nvidia-smi || echo "  -> nvidia-smi failed — check the Unraid Nvidia-Driver plugin and 'gpus: all' in compose"

echo
echo "=== done ==="
systemctl status ssh tailscaled kev kev-proxy jeff --no-pager || true
echo
echo "Still needed by hand, once:"
echo "  tailscale up --hostname=${TS_HOSTNAME} --ssh"
echo "  passwd root   (or drop a pubkey into /root/.ssh/authorized_keys)"
