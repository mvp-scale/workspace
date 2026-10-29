# RunPod burst notes

Use RunPod only when the local GPUs are busy or the job needs more VRAM than 32 GB. Cap the spend before you start.

1. **Cost cap first.** Put `budget.usd` and `budget.gpu_h` on the task card. Fund the account with no more than
   the card cap and turn auto-pay off, so an idle pod can't overspend. Write the hourly rate and the planned hours
   in the card (`usd = rate x hours`).
2. **Network volume.** Create a volume in the same data center as the pod. Put private data (gold, publisher text)
   on the volume once, and keep it there. `local_gpu_run.sh` copies code only, unless you set `PRIVATE_TARGET=1`.
   A volume bills while it exists, so delete it when the project ends.
3. **Create the pod.** Use a PyTorch template, choose the GPU, attach the volume at `/workspace`, and add your
   public SSH key in account settings. Set `RUNPOD_API_KEY` in `secrets/vault.env` if you script pods with
   `runpodctl` (the launch hook requires `CARD=` on `runpodctl` commands).
4. **SSH.** Use the pod's "SSH over exposed TCP" address (`root@<ip> -p <port>`), not the proxy one. The proxy
   address doesn't support the stdin piping the script uses. Run:
   `SSH_PORT=<port> CARD=cards/T7.json kit/ops/local_gpu_run.sh root@<ip> /workspace/jobs runs/T7/pod -- python train.py`
   The R4 check works the same way: one job per pod GPU.
5. **Stop when done.** When the script returns, check that the outputs are in `runs/...`, then **stop** the pod. A
   stopped pod still bills for its container disk, so **terminate** it if you won't reuse it. Record the hours and
   cost in a ledger `result` line and in `spend.jsonl` (`{"usd": ...}`) so `preflight.mjs` counts it.
6. **Never** keep secrets in the pod image or on the volume. Use `SEND_KEYS` to pass them to the job process only.
