# Knowledge breakdown flow

Date 2026-11-24. Terms: `terminology.md`. Status: **exists** = built and used; **partial** = built but weak or incomplete; **missing** = not built.

## Goals (stated first)
Reader goals (what every rendering must let the reader do):
- **G1 Changed:** know what changed since the last look.
- **G2 Means:** know what it means for their goals.
- **G3 Trust:** know how sure it is and who disputes it.
- **G4 Connects:** see how it connects to what they follow.
- **G5 Next:** know what to watch next.
- **G6 Keep:** carry the state in memory until next time.

System goals:
- **S1** Works for any source type, not only news.
- **S2** Works for any reader, without an interview first.
- **S3** Works at scale (10k items a day).
- **S4** Every line traces to its evidence.

## The breakdown (each level consumes the one before)

| # | Level | Unit produced | News today | Other sources |
|---|---|---|---|---|
| 0 | Intake | source item (text, time, source, read depth) | exists | **missing** (no adapters for filings, PDFs, reports, transcripts) |
| 1 | Fragments | sentences and spans | exists | missing (needs adapter) |
| 2 | Assertions | who did what to whom, when, attributed, polarity, with evidence | partial (did-text often broken) | source-agnostic from here down |
| 3 | Entities | people, organisations, places with identity | partial (wrong types, e.g. Fiona = person) | |
| 4 | Corroboration | the same assertion across sources; independent owners; contradictions | partial (join F1 0.51; contradictions only with named speakers) | |
| 5 | Developments | event threads that group assertions (plus phases) | partial (v0; ids not stable across windows) | |
| 6 | Change over time | what moved since a point in time; certainty changes; forward statements resolved | partial (one window, fixed cut; no stored history) | |
| 7 | Meaning (L2) | why it matters for a reader goal; stated causes | **missing** (no grounded synthesis; causes weak) | |
| 8 | Projection (L3) | what comes next; what would change the judgment | partial (quoted forward statements only; no projection) | |
| 9 | Relevance and rank | which developments matter to this reader | **missing** (no Macro Pulse, no reader profile) | |
| 10 | Reader state | last look, what they already know, recall | **missing** | |
| 11 | Render | requirement -> visual encoding -> view | partial (rules written; generator hardcoded per requirement) | |

Levels 2-11 do not depend on the source type. Adding a new source type means building levels 0-1 only.

## Which levels serve which goal

| Goal | Needs levels | Blocked by |
|---|---|---|
| G1 Changed | 5, 6 | stable development ids; stored history (6) |
| G2 Means | 7 | grounded synthesis (7) |
| G3 Trust | 4 | contradiction coverage (4) |
| G4 Connects | 3, 5 | entity quality (3) |
| G5 Next | 8 | projection (8) |
| G6 Keep | 7, 10 | meaning (7); reader state (10) |
| S1 Any source | 0, 1 | adapters (0-1) |
| S2 Any reader | 9 | relevance and rank (9) |
| S3 Scale | 5, 9 | ranking (9) |
| S4 Traceable | 2, 4 | exists |

## States a rendering must handle
- **Reader state:** first look / since last look / deep dive.
- **Knowledge state:** new / moving / settled / disputed / gap (not enough data).
- **Scale:** one development / one area / all areas (portfolio).

A view is one combination of these states, filled from levels 5-10. No view invents a level that is missing; it shows the gap instead.

## What is missing, in build order
1. Stable development ids plus stored history (level 6). Unblocks G1.
2. Grounded synthesis for meaning, cited and checked against evidence (level 7). Unblocks G2 and G6. Needs the owner's yes.
3. Relevance and rank: reader profile plus Macro Pulse (level 9). Unblocks S2 and S3.
4. Executable requirements and render rules (level 11), replacing hardcoded pages.
5. Reader state (level 10).
6. Source adapters for one non-news type (levels 0-1). Proves S1.
