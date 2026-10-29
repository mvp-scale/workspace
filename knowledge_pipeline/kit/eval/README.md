# kit/eval — evaluation toolkit (agent-facing)

Python 3.10+ stdlib only. Project-agnostic. Each tool is a CLI that prints JSON and an importable module.
Gate IDs refer to `knowledge_pipeline/ACCEPTANCE.md`.

## Input shapes

- Spans: `{"items": [{"id": "x1", "spans": [{"start": 0, "end": 4, "label": "PER"}], "ignore": [{"start": 9, "end": 15}]}]}`.
  `ignore` is optional. Any span that overlaps an ignore region is dropped on both sides.
- Labels: `{"items": [{"id": "x1", "labels": ["POS"]}]}`, or `"label": "POS"`.
- Layers: one per label, plus `ALL` (all spans pooled; labels must still match).
  `exact` means the same (start, end, label). `overlap` means the same label and any shared character, matched
  greedily 1:1 by highest Jaccard first (the same algorithm as `pipeline/eval/score.py`).
- CI: 95% percentile bootstrap that resamples items, with `--n 1000 --seed 0` by default. Every layer uses the same
  draws, and so do both systems in `compare.py`.

## Tools

| Tool | Gates | Command | Output |
|---|---|---|---|
| `score_spans.py` | M1 input, R6 | `python score_spans.py CAND REF [--ignore IGN] [--out s.json] [--expect prior.json]` | `layers[L][exact\|overlap] = {p, r, f1, tp, n_cand, n_ref, lo, hi}` + `meta` (scorer_sha, n_items, seed) |
| `agreement.py` | D1, D2 | `python agreement.py spans A B` / `python agreement.py labels A B` | per layer F1 or kappa + CI, `gate` = 0.8 × IAA, `verdict` go ≥ 0.6 / review 0.4–0.6 / fix < 0.4; `D1.ok` = n_items ≥ 30 |
| `consensus.py` | D1/D2 review, silver ruler | `python consensus.py A B [--mode overlap\|exact] [--span intersect\|union\|a\|b] --out merged.json --disagreements dis.json` | merged spans file (disagreement regions become `ignore`, so it can be scored as REF directly) + stats |
| `gate.py` | M1 | `python gate.py s.json gates.json [--meta meta.json] --md report.md` or `python gate.py s.json --agreement iaa.json --mode overlap` | pass/fail per layer on the lower bound, JSON plus a markdown report in the `templates/gate-report.md` layout; exits 1 on any failure |
| `compare.py` | M2, M8 | `python compare.py REF --a base.json [seed2 ...] --b new.json [seed2 ...]` | `diff` = F1(B) − F1(A), paired CI, `verdict` better / worse / no-difference; with ≥ 2 runs per arm also `run_sd` and the M8 rule \|diff\| ≥ 2 × sd; `meta.m8_seeds_ok` = ≥ 3 runs per arm |

`gates.json`: `{"layers": {"PER": {"mode": "overlap", "iaa": 0.82}, "ORG": {"mode": "exact", "gate": 0.5}}}`.

## Notes

- Verdicts in D2 use the point estimate. The lower bound is reported next to it. For span layers there is no chance
  correction, so the same cut points are applied to F1.
- In `score_spans` and in `agreement spans`, the set of items is taken from REF (or B). If an item is missing from
  CAND (or A), it counts as empty. The count shows up in `meta`.
- In `consensus`, a disagreement region that overlaps an agreed span is not added to `ignore`, so agreed spans are
  never hidden.

## Freeze (D3, R6)

1. Run `python score_spans.py --sha` and record the 8-hex value on the task card and in the gate report. Every tool
   also prints its own `--sha`, and its output `meta` includes `scorer_sha`.
2. Do not edit a frozen tool. If a change is needed, ship a new file and a new sha.
3. For R6, re-score the fetched outputs with `--expect <published score.json>`. The command exits 0 only when every
   layer number is exactly the same.

## Tests

`python -m unittest discover -s knowledge_pipeline/kit/eval/tests` (synthetic fixtures only).
