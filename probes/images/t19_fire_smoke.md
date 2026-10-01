# t19_fire_smoke

Status: BLOCKED

## Recon

`fireviewer/fire-smoke-detection-corpus-v2` is about 28 GB with no licence stated. It was not downloaded.

`Simuletic/CCTV-Smoke-Fire-Emergency-Detection-Dataset` is CC-BY-NC-4.0, about 0.34 GB. File names are `fire_detected_*` (239) and `smoke_detected_*` (240). `data.yaml` says:

```
nc: 1
names:
  0: fire
  1: smoke
```

There is no class for a frame with neither. Images were not downloaded.

## Why blocked

"Is there fire or smoke visible?" needs real negatives. Both classes in this set are positives.
