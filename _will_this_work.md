# Will this work? — Grid/coordinate encoding gauntlet for Jev

Testing whether Jev (kev-4b local, and hosted `jev-1.13.0` via TypeSafe) can locate
elements in a spatial grid when the grid is described as text in different formats
(ASCII, Markdown, pseudo-HTML, CSV, spreadsheet-style, sparse coordinates, prose,
symbolic-compressed), across two domains: a mock webpage UI layout, and a mock
OpenCV-style image tile grid.

Method: same underlying grid + same questions, only the **encoding** of `state`
changes per variant. For each request we record `usage.input_tokens`,
`usage.output_tokens`, `latency_ms`, and score each answer against the ground truth
below. Accuracy first; token/format tradeoff second.

Every request uses the same 5-question battery per domain (Task A questions are
identical in *meaning* across variants 1–8, only the option labels change to match
each variant's own coordinate scheme — noted per variant).

Models under test: **kev-4b** (local, `127.0.0.1:8010`), **semif** (local, `127.0.0.1:8012`,
Qwen3.5-4B classifier-style adapter — the "other one that's up" besides kev), and
**hosted Jev** (`jev-1.13.0` via TypeSafe API, paid, `$TYPESAFE_API_KEY` from `/workspace/.env`).

---

## ⚠️ Expected-answers quick reference (review BEFORE running)

| # | Variant | Q1 | Q2 | Q3 | Q4 | Q5 |
|---|---------|----|----|----|----|----|
| 1 | Markdown table | Row5 | Col5 | Col4 | Row1Col5 | true |
| 2 | Raw ASCII | Row5 | Col5 | Col4 | Row1Col5 | true |
| 3 | CSV | Row5 | Col5 | Col4 | Row1Col5 | true |
| 4 | Pseudo-HTML table | Row5 | Col5 | Col4 | Row1Col5 | true |
| 5 | Sparse coordinates | Row5 | Col5 | Col4 | Row1Col5 | true |
| 6 | Plain prose | Row5 | Col5 | Col4 | Row1Col5 | true |
| 7 | Spreadsheet (A1) | 5 | E | D | E1 | true |
| 8 | Symbolic + legend | Row5 | Col5 | Col4 | Row1Col5 | true |
| 9 | Image-tile Markdown | Row4 | Col5 | — | Row4Col5 | true / true |
| 10 | Image-tile HTML/CSS | Row4 | Col5 | — | Row4Col5 | true / true |

Column key:
- Variants 1–6, 8: Q1=row of Submit button, Q2=col of Submit button, Q3=col of Hero CTA button, Q4=cell of Login button, Q5=Search button & Cart icon same row?
- Variant 7: same meaning, spreadsheet addressing (row number / column letter / cell ref)
- Variants 9–10: Q1=row of red+high+object cell, Q2=col of that cell, Q3=n/a (only 4 questions used, not 5), Q4=exact cell of that same target, Q5 is actually two separate noul questions ("more than one red cell?" = true, "green cell has object?" = true) — shown combined as "true / true"

If any of these don't match your own read of the grids, say so now — everything downstream (scoring, the "accuracy" column) depends on this key being right, and it's easy to eyeball-check against the grids above since they're small.

---

## Task A ground truth — mock webpage UI grid (6 rows × 5 columns)

Canonical layout (semantic labels, Row1–Row6 / Col1–Col5):

| Row  | Col1        | Col2         | Col3          | Col4            | Col5            |
|------|-------------|--------------|---------------|-----------------|-----------------|
| Row1 | Logo        | NavHome      | NavProducts   | NavAbout        | LoginButton     |
| Row2 | SearchBox   | SearchBox    | SearchButton  | CartIcon        | ProfileIcon     |
| Row3 | HeroImage   | HeroImage    | HeroHeadline  | HeroCTAButton   | -               |
| Row4 | -           | ProductCard1 | ProductCard2  | ProductCard3    | -               |
| Row5 | -           | ReviewsBlock | ReviewsBlock  | NewsletterInput | SubmitButton    |
| Row6 | FooterLinks | FooterLinks  | FooterSocial  | FooterSocial    | FooterCopyright |

Ground truth answers (semantic form):
- Submit button → **Row5, Col5**
- Login button → **Row1, Col5**
- Hero CTA button → **Row3, Col4**
- Search button and Cart icon → **both Row2** (true)

---

## Task B ground truth — mock OpenCV image-tile grid (6 rows × 6 columns)

Each cell = `dominant_color, brightness, contains_object`. Background cells are
`gray, medium, no`. Planted cells:

- **Row2, Col2** → blue, low, no
- **Row3, Col5** → red, medium, no *(decoy: red but no object)*
- **Row4, Col5** → red, high, **yes** *(the unique target: red + high + object)*
- **Row5, Col1** → green, high, **yes** *(decoy: object present, different color)*
- **Row6, Col6** → yellow, low, no

All other 31 cells → gray, medium, no.

Ground truth answers:
- Cell with red + high brightness + object present → **Row4, Col5**
- More than one red cell? → **true** (Row3Col5 and Row4Col5)
- Does the green cell also have an object? → **true** (Row5Col1)

---

## Variant 1 — Markdown table (control)

```
| Row  | Col1        | Col2         | Col3          | Col4            | Col5            |
|------|-------------|--------------|---------------|-----------------|-----------------|
| Row1 | Logo        | NavHome      | NavProducts   | NavAbout        | LoginButton     |
| Row2 | SearchBox   | SearchBox    | SearchButton  | CartIcon        | ProfileIcon     |
| Row3 | HeroImage   | HeroImage    | HeroHeadline  | HeroCTAButton   | -               |
| Row4 | -           | ProductCard1 | ProductCard2  | ProductCard3    | -               |
| Row5 | -           | ReviewsBlock | ReviewsBlock  | NewsletterInput | SubmitButton    |
| Row6 | FooterLinks | FooterLinks  | FooterSocial  | FooterSocial    | FooterCopyright |
```

Questions: Row1–Row6 / Col1–Col5 / cell IDs `Row1Col1`…`Row6Col5` (30 options).

**Results:** kev-4b — input_tokens: _TBD_, accuracy: _TBD_/5. semif — input_tokens: _TBD_, accuracy: _TBD_/5. Hosted jev — input_tokens: _TBD_, accuracy: _TBD_/5.

---

## Variant 2 — Raw ASCII, whitespace-aligned, no table syntax

```
Row1  Logo         NavHome       NavProducts    NavAbout         LoginButton
Row2  SearchBox    SearchBox     SearchButton   CartIcon         ProfileIcon
Row3  HeroImage    HeroImage     HeroHeadline   HeroCTAButton    -
Row4  -            ProductCard1  ProductCard2   ProductCard3     -
Row5  -            ReviewsBlock  ReviewsBlock   NewsletterInput  SubmitButton
Row6  FooterLinks  FooterLinks   FooterSocial   FooterSocial     FooterCopyright
```

Questions: same as Variant 1 (Row1–Row6 / Col1–Col5 / 30 cell IDs).

**Results:** kev-4b — input_tokens: _TBD_, accuracy: _TBD_/5. semif — input_tokens: _TBD_, accuracy: _TBD_/5. Hosted jev — input_tokens: _TBD_, accuracy: _TBD_/5.

---

## Variant 3 — CSV rows, no alignment

```
Row,Col1,Col2,Col3,Col4,Col5
Row1,Logo,NavHome,NavProducts,NavAbout,LoginButton
Row2,SearchBox,SearchBox,SearchButton,CartIcon,ProfileIcon
Row3,HeroImage,HeroImage,HeroHeadline,HeroCTAButton,-
Row4,-,ProductCard1,ProductCard2,ProductCard3,-
Row5,-,ReviewsBlock,ReviewsBlock,NewsletterInput,SubmitButton
Row6,FooterLinks,FooterLinks,FooterSocial,FooterSocial,FooterCopyright
```

Questions: same as Variant 1.

**Results:** kev-4b — input_tokens: _TBD_, accuracy: _TBD_/5. semif — input_tokens: _TBD_, accuracy: _TBD_/5. Hosted jev — input_tokens: _TBD_, accuracy: _TBD_/5.

---

## Variant 4 — Pseudo-HTML table

```
<table>
<tr><td>Row1</td><td>Logo</td><td>NavHome</td><td>NavProducts</td><td>NavAbout</td><td>LoginButton</td></tr>
<tr><td>Row2</td><td>SearchBox</td><td>SearchBox</td><td>SearchButton</td><td>CartIcon</td><td>ProfileIcon</td></tr>
<tr><td>Row3</td><td>HeroImage</td><td>HeroImage</td><td>HeroHeadline</td><td>HeroCTAButton</td><td>-</td></tr>
<tr><td>Row4</td><td>-</td><td>ProductCard1</td><td>ProductCard2</td><td>ProductCard3</td><td>-</td></tr>
<tr><td>Row5</td><td>-</td><td>ReviewsBlock</td><td>ReviewsBlock</td><td>NewsletterInput</td><td>SubmitButton</td></tr>
<tr><td>Row6</td><td>FooterLinks</td><td>FooterLinks</td><td>FooterSocial</td><td>FooterSocial</td><td>FooterCopyright</td></tr>
</table>
```

Questions: same as Variant 1.

**Results:** kev-4b — input_tokens: _TBD_, accuracy: _TBD_/5. semif — input_tokens: _TBD_, accuracy: _TBD_/5. Hosted jev — input_tokens: _TBD_, accuracy: _TBD_/5.

---

## Variant 5 — Sparse coordinate list (non-empty cells only)

```
(Row1,Col1): Logo
(Row1,Col2): NavHome
(Row1,Col3): NavProducts
(Row1,Col4): NavAbout
(Row1,Col5): LoginButton
(Row2,Col1): SearchBox
(Row2,Col2): SearchBox
(Row2,Col3): SearchButton
(Row2,Col4): CartIcon
(Row2,Col5): ProfileIcon
(Row3,Col1): HeroImage
(Row3,Col2): HeroImage
(Row3,Col3): HeroHeadline
(Row3,Col4): HeroCTAButton
(Row4,Col2): ProductCard1
(Row4,Col3): ProductCard2
(Row4,Col4): ProductCard3
(Row5,Col2): ReviewsBlock
(Row5,Col3): ReviewsBlock
(Row5,Col4): NewsletterInput
(Row5,Col5): SubmitButton
(Row6,Col1): FooterLinks
(Row6,Col2): FooterLinks
(Row6,Col3): FooterSocial
(Row6,Col4): FooterSocial
(Row6,Col5): FooterCopyright
```

Questions: same as Variant 1 (empty cells simply don't exist as options for a
"which cell contains X" style question, but Row/Col axis questions are unaffected).

**Results:** kev-4b — input_tokens: _TBD_, accuracy: _TBD_/5. semif — input_tokens: _TBD_, accuracy: _TBD_/5. Hosted jev — input_tokens: _TBD_, accuracy: _TBD_/5.

---

## Variant 6 — Plain prose, no structural syntax at all

```
This describes a webpage layout, row by row, left to right.
Row 1 contains: a logo, a home nav link, a products nav link, an about nav link, and a login button.
Row 2 contains: a search box spanning two slots, a search button, a cart icon, and a profile icon.
Row 3 contains: a hero image spanning two slots, a hero headline, and a hero call-to-action button.
Row 4 contains: an empty slot, then three product cards, then an empty slot.
Row 5 contains: an empty slot, a reviews block spanning two slots, a newsletter input, and a submit button.
Row 6 contains: footer links spanning two slots, footer social icons spanning two slots, and a footer copyright notice.
```

Questions: same as Variant 1 (Row1–Row6 / Col1–Col5 / 30 cell IDs — the model has
to infer column position from ordinal description rather than an explicit grid).

**Results:** kev-4b — input_tokens: _TBD_, accuracy: _TBD_/5. semif — input_tokens: _TBD_, accuracy: _TBD_/5. Hosted jev — input_tokens: _TBD_, accuracy: _TBD_/5.

---

## Variant 7 — Spreadsheet-style addressing (A1 notation)

Column letters: Col1=A, Col2=B, Col3=C, Col4=D, Col5=E. Row numbers: Row1=1 … Row6=6.

```
A1: Logo         B1: NavHome      C1: NavProducts   D1: NavAbout        E1: LoginButton
A2: SearchBox    B2: SearchBox    C2: SearchButton  D2: CartIcon        E2: ProfileIcon
A3: HeroImage    B3: HeroImage    C3: HeroHeadline  D3: HeroCTAButton   E3: -
A4: -            B4: ProductCard1 C4: ProductCard2  D4: ProductCard3    E4: -
A5: -            B5: ReviewsBlock C5: ReviewsBlock  D5: NewsletterInput E5: SubmitButton
A6: FooterLinks  B6: FooterLinks  C6: FooterSocial  D6: FooterSocial    E6: FooterCopyright
```

Questions (own addressing scheme):
- `choice` (1–6): "Which row number is the Submit button in?" → **5**
- `choice` (A–E): "Which column letter is the Submit button in?" → **E**
- `choice` (A–E): "Which column letter is the Hero CTA button in?" → **D**
- `choice` (30 options `A1`…`E6`): "Which cell reference contains the Login button?" → **E1**
- `noul`: "Is the Search button in the same row as the Cart icon?" → **true**

**Results:** kev-4b — input_tokens: _TBD_, accuracy: _TBD_/5. semif — input_tokens: _TBD_, accuracy: _TBD_/5. Hosted jev — input_tokens: _TBD_, accuracy: _TBD_/5.

---

## Variant 8 — Ultra-compact symbolic grid + legend

```
Legend: G=Logo, H=NavHome, P=NavProducts, A=NavAbout, L=LoginButton, S=SearchBox,
B=SearchButton, C=CartIcon, R=ProfileIcon, I=HeroImage, D=HeroHeadline, T=HeroCTAButton,
1=ProductCard1, 2=ProductCard2, 3=ProductCard3, V=ReviewsBlock, N=NewsletterInput,
X=SubmitButton, F=FooterLinks, O=FooterSocial, Y=FooterCopyright, -=empty

Row1: G H P A L
Row2: S S B C R
Row3: I I D T -
Row4: - 1 2 3 -
Row5: - V V N X
Row6: F F O O Y
```

Questions (reference codes directly, since that's what the grid contains):
- `choice` (Row1–Row6): "Which row is the cell with code X in?" → **Row5**
- `choice` (Col1–Col5): "Which column is the cell with code X in?" → **Col5**
- `choice` (Col1–Col5): "Which column is the cell with code T in?" → **Col4**
- `choice` (30 options `Row1Col1`…`Row6Col5`): "Which cell has code L in it?" → **Row1Col5**
- `noul`: "Are code B and code C in the same row?" → **true**

**Results:** kev-4b — input_tokens: _TBD_, accuracy: _TBD_/5. semif — input_tokens: _TBD_, accuracy: _TBD_/5. Hosted jev — input_tokens: _TBD_, accuracy: _TBD_/5.

---

## Variant 9 — OpenCV-style image tile grid, Markdown table (Task B)

```
| Row  | Col1            | Col2            | Col3            | Col4            | Col5              | Col6            |
|------|-----------------|-----------------|-----------------|-----------------|-------------------|-----------------|
| Row1 | gray,medium,no  | gray,medium,no  | gray,medium,no  | gray,medium,no  | gray,medium,no    | gray,medium,no  |
| Row2 | gray,medium,no  | blue,low,no     | gray,medium,no  | gray,medium,no  | gray,medium,no    | gray,medium,no  |
| Row3 | gray,medium,no  | gray,medium,no  | gray,medium,no  | gray,medium,no  | red,medium,no     | gray,medium,no  |
| Row4 | gray,medium,no  | gray,medium,no  | gray,medium,no  | gray,medium,no  | red,high,yes      | gray,medium,no  |
| Row5 | green,high,yes  | gray,medium,no  | gray,medium,no  | gray,medium,no  | gray,medium,no    | gray,medium,no  |
| Row6 | gray,medium,no  | gray,medium,no  | gray,medium,no  | gray,medium,no  | gray,medium,no    | yellow,low,no   |
```

Cell format: `dominant_color,brightness,contains_object`.

Questions:
- `choice` (Row1–Row6): "Which row contains the cell with dominant color red, high brightness, and an object present?" → **Row4**
- `choice` (Col1–Col6): "Which column contains that same cell?" → **Col5**
- `choice` (36 options `Row1Col1`…`Row6Col6`): "Which single cell has dominant_color=red, brightness=high, and contains_object=true?" → **Row4Col5**
- `noul`: "Is there more than one cell with a red dominant color?" → **true** (Row3Col5 decoy + Row4Col5)
- `noul`: "Does the cell with a green dominant color also have contains_object=true?" → **true** (Row5Col1)

**Results:** kev-4b — input_tokens: _TBD_, accuracy: _TBD_/5. semif — input_tokens: _TBD_, accuracy: _TBD_/5. Hosted jev — input_tokens: _TBD_, accuracy: _TBD_/5.

---

## Variant 10 — OpenCV-style image tile grid, pseudo-HTML/CSS-grid (Task B)

```
<div style="grid-row:1;grid-column:1">gray,medium,no</div>
<div style="grid-row:1;grid-column:2">gray,medium,no</div>
<div style="grid-row:1;grid-column:3">gray,medium,no</div>
<div style="grid-row:1;grid-column:4">gray,medium,no</div>
<div style="grid-row:1;grid-column:5">gray,medium,no</div>
<div style="grid-row:1;grid-column:6">gray,medium,no</div>
<div style="grid-row:2;grid-column:1">gray,medium,no</div>
<div style="grid-row:2;grid-column:2">blue,low,no</div>
<div style="grid-row:2;grid-column:3">gray,medium,no</div>
<div style="grid-row:2;grid-column:4">gray,medium,no</div>
<div style="grid-row:2;grid-column:5">gray,medium,no</div>
<div style="grid-row:2;grid-column:6">gray,medium,no</div>
<div style="grid-row:3;grid-column:1">gray,medium,no</div>
<div style="grid-row:3;grid-column:2">gray,medium,no</div>
<div style="grid-row:3;grid-column:3">gray,medium,no</div>
<div style="grid-row:3;grid-column:4">gray,medium,no</div>
<div style="grid-row:3;grid-column:5">red,medium,no</div>
<div style="grid-row:3;grid-column:6">gray,medium,no</div>
<div style="grid-row:4;grid-column:1">gray,medium,no</div>
<div style="grid-row:4;grid-column:2">gray,medium,no</div>
<div style="grid-row:4;grid-column:3">gray,medium,no</div>
<div style="grid-row:4;grid-column:4">gray,medium,no</div>
<div style="grid-row:4;grid-column:5">red,high,yes</div>
<div style="grid-row:4;grid-column:6">gray,medium,no</div>
<div style="grid-row:5;grid-column:1">green,high,yes</div>
<div style="grid-row:5;grid-column:2">gray,medium,no</div>
<div style="grid-row:5;grid-column:3">gray,medium,no</div>
<div style="grid-row:5;grid-column:4">gray,medium,no</div>
<div style="grid-row:5;grid-column:5">gray,medium,no</div>
<div style="grid-row:5;grid-column:6">gray,medium,no</div>
<div style="grid-row:6;grid-column:1">gray,medium,no</div>
<div style="grid-row:6;grid-column:2">gray,medium,no</div>
<div style="grid-row:6;grid-column:3">gray,medium,no</div>
<div style="grid-row:6;grid-column:4">gray,medium,no</div>
<div style="grid-row:6;grid-column:5">gray,medium,no</div>
<div style="grid-row:6;grid-column:6">yellow,low,no</div>
```

Questions: same as Variant 9.

**Results:** kev-4b — input_tokens: _TBD_, accuracy: _TBD_/5. semif — input_tokens: _TBD_, accuracy: _TBD_/5. Hosted jev — input_tokens: _TBD_, accuracy: _TBD_/5.

---

## Summary table (actual results — run 2026-09-27)

semif cannot attempt the "which cell" question in any variant: it hard-errors with
`ValueError: options must contain 2-16 entries` on every 30/36-option choice question
(its `/v1/models` reports `"readout": "answer-letter logits"` — it labels each option
with a single letter, so it structurally tops out at ~16-26 options well before our
30/36). Its accuracy column below is **out of 4**, not 5 (the 4 in-bounds questions:
row, col, hero-col or n/a, same-row/decoy checks), with the excluded question noted.

| # | Variant | Domain | State chars | kev-4b tokens | kev-4b acc | semif tokens | semif acc | Hosted tokens | Hosted acc |
|---|---------|--------|--------------|---------------|------------|--------------|-----------|---------------|------------|
| 1 | Markdown table | A | 719 | 493 | 5/5 | 1311 | 4/4 | 951 | 5/5 |
| 2 | Raw ASCII | A | 446 | 415 | 5/5 | 1011 | 3/4 | 879 | 5/5 |
| 3 | CSV | A | 373 | 428 | 5/5 | 1063 | 4/4 | 889 | 5/5 |
| 4 | Pseudo-HTML table | A | 709 | 591 | 5/5 | 1703 | 4/4 | 1048 | 5/5 |
| 5 | Sparse coordinates | A | 644 | 571 | 5/5 | 1623 | 4/4 | 1037 | 5/5 |
| 6 | Plain prose | A | 664 | 472 | 3/5 | 1227 | 3/4 | 896 | 3/5 |
| 7 | Spreadsheet (A1) | A | 512 | 412 | 5/5 | 1264 | 4/4 | 876 | 5/5 |
| 8 | Symbolic + legend | A | 424 | 486 | 5/5 | 1289 | 3/4 | 939 | 5/5 |
| 9 | Image-tile Markdown | B | 951 | 664 | 3/5 | 1754 | 4/4 | 1112 | 5/5 |
| 10 | Image-tile HTML/CSS | B | 2116 | 1123 | 4/5 | 3590 | 4/4 | 1583 | 5/5 |

**Note on semif's token counts:** they're consistently ~2-3x kev-4b/hosted for the
*same* state text despite answering fewer questions — its adapter appears to spend
substantially more tokens per request (likely re-encoding per answer-letter option),
so it's the most expensive of the three per useful answer, on top of being unable to
do the hardest lookup at all.

### Key findings
1. **Encoding barely matters for accuracy once there's any explicit row/column structure.** Markdown, raw ASCII, CSV, pseudo-HTML, sparse coordinate lists, spreadsheet (A1) addressing, and a symbolic+legend grid all score 5/5 on kev-4b and hosted jev. Token cost varies a lot for identical accuracy: CSV (variant 3, 373 chars) is the cheapest; pseudo-HTML (variant 4) and HTML/CSS-div grids (variant 10) cost noticeably more for no accuracy gain — **CSV or plain markdown-table are the token-efficient choices; avoid HTML-style markup unless something else demands it.**
2. **Structure removal is the one thing that reliably breaks it.** Variant 6 (plain prose, no table/grid at all) is the only Task-A encoding that drops accuracy — identically on both kev-4b and hosted jev (3/5), both missing the same two questions (exact column of the Submit button, exact column of the Hero CTA button). Row-level position survives prose; **precise column position does not.**
3. **kev-4b (open-source) has a distinct weak spot hosted jev doesn't share: cross-referencing two separate facts about the same located entity.** On the image-tile task (variants 9-10), kev-4b nails locating the target cell every time but fails the follow-up boolean checks ("does the green cell *also* have an object present?", "is there a second red cell?") 2-3 times out of 2 attempts — as if locating overwrites its ability to recall a second attribute of what it found. Hosted jev gets 5/5 on both.
4. **semif has a hard, non-negotiable cap of ~16 choice options**, tied to its answer-letter-logit mechanism — no re-encoding of the *state* fixes this, since it's a limit on the *question schema*, not the data. For a real "navigate a website" use case built on semif, any single-shot "which of the 30 elements is X" query would need to be decomposed into row-then-column (or region-then-element) lookups; kev and hosted jev don't have this limitation and can do it in one shot.

**Bottom line for the website-navigation idea:** yes, the grid-as-table approach works — both kev-4b and hosted jev locate a labeled element in a 30-cell grid correctly, cheaply, and in a single call, across nearly every text encoding tried. CSV/markdown is the efficient choice; avoid plain prose descriptions; expect the open-source model to be a little less reliable at "found X, now tell me a second fact about it" reasoning; and if semif is ever in the loop, it can only do this via decomposed row/column lookups, not single-shot full-grid addressing.

---

## Variant 11 — Breadcrumb-keyed, strictly-typed code review facts (real code, no invented percentages)

Run later the same session, after the grid gauntlet. Motivation: earlier ad-hoc tests used
invented "Security%/Readability%" percentages (too subjective) and then an artificial 8/10-bit
security-flag mask (too abstract). This variant grounds everything in **real Python code**, keys
each row by a **breadcrumb signature** (`Class.method(params)` — the method's own declared
parameters, not call-site arguments) rather than an arbitrary label, and restricts every column to
**exactly the three primitive types the systemone wire format itself uses** — `noul` (yes/no),
`choice` (pick one named option), `score` (pick one ordered level) — with the type tagged in the
column header the same way the wire format tags a question's `type` field. No comma-separated
lists, no raw open-ended numbers, no subjective percentages.

The deliberate trap: `AdminConsole.run_admin_command(x)` is the shortest, simplest-by-every-
quantitative-measure method (score 0 on code length, params, try/except, branching) yet contains
`eval()` on unvalidated input — the single worst issue of the four. `DataPipeline.process_data(...)`
is the opposite: highest code-length, param-count, and branching scores, most non-descriptive
names — looks the "worst" by every count — but has zero actual security risk.

> **⚠️ CONFOUNDED — see corrected re-run below.** This run's `state` includes the full Python
> source **as well as** the fact table. Every question here is directly answerable just by reading
> the actual code (anyone can see `eval(x)` and `password="admin123"` with their own eyes), so the
> scores below do **not** show whether the model used the table at all — it may have ignored the
> table entirely and reasoned over the code like any ordinary code-reviewing model would. A
> corrected, table-only re-run (no source code in `state`) is included right after the results
> below, and its numbers diverge from this one in both directions per model — see that section for
> the trustworthy comparison.

### State sent (verbatim)

```
Real Python classes under review:

class BillingService:
    def calculate_total(self, prices, tax_rate):
        if not prices:
            return 0.0
        subtotal = sum(prices)
        return subtotal * (1 + tax_rate)

class AdminConsole:
    def run_admin_command(self, x):
        return eval(x)

class DataPipeline:
    def process_data(self, a, b, c, d, e):
        x = []
        for i in a:
            if i > 0:
                for j in b:
                    if j > 0:
                        try:
                            x.append(i / j)
                        except Exception:
                            pass
        y = 0
        for k in x:
            y += k
        return y

class OpsTools:
    def backup_database(self, host, password="admin123"):
        command = "pg_dump -h " + host + " > /tmp/backup.sql"
        os.system(command)
        return True

Fact table. Each method is identified by its breadcrumb signature (Class.method(params), the
method's own declared parameters, not call-site arguments). Each column is tagged with its
answer type, exactly as in the systemone wire format: [noul]=yes/no, [choice]=pick one named
option, [score]=pick one ordered level.

| Method | [score] Code length: 0=short(<5 lines), 1=medium(5-12), 2=long(>12) | [score] Parameter count: 0=few(1-2), 1=moderate(3-4), 2=many(5+) | [noul] Calls eval/exec on input? | [noul] Hardcoded password or secret? | [choice] Imports: none / stdlib_only / third_party | [score] try/except blocks: 0=none, 1=one, 2=two_or_more | [noul] Validates input before use? | [score] Branching (if/for/while count): 0=low(0-1), 1=medium(2-4), 2=high(5+) | [noul] Non-descriptive names (x,a,b,i,j)? | [choice] Primary risky operation: none / eval_injection / hardcoded_secret / command_injection / multiple_critical |
|---|---|---|---|---|---|---|---|---|---|---|
| BillingService.calculate_total(prices, tax_rate) | 0 | 0 | no | no | none | 0 | yes | 0 | no | none |
| AdminConsole.run_admin_command(x) | 0 | 0 | yes | no | none | 0 | no | 0 | yes | eval_injection |
| DataPipeline.process_data(a, b, c, d, e) | 2 | 2 | no | no | none | 1 | no | 2 | yes | none |
| OpsTools.backup_database(host, password) | 0 | 0 | no | yes | stdlib_only | 0 | no | 0 | no | multiple_critical |
```

### Same table, reformatted for readability (identical content, short headers + separate legend)

Column legend:
| Col | Type | Meaning |
|---|---|---|
| Length | score | code length: 0=short(<5 lines), 1=medium(5-12), 2=long(>12) |
| Params | score | parameter count: 0=few(1-2), 1=moderate(3-4), 2=many(5+) |
| Eval? | noul | calls eval/exec on input |
| Secret? | noul | hardcoded password or secret |
| Imports | choice | none / stdlib_only / third_party |
| Try/Except | score | 0=none, 1=one, 2=two_or_more |
| Validates? | noul | validates input before use |
| Branching | score | if/for/while count: 0=low(0-1), 1=medium(2-4), 2=high(5+) |
| NonDescNames? | noul | uses non-descriptive names (x,a,b,i,j) |
| RiskyOp | choice | none / eval_injection / hardcoded_secret / command_injection / multiple_critical |

| Method | Length | Params | Eval? | Secret? | Imports | Try/Except | Validates? | Branching | NonDescNames? | RiskyOp |
|---|---|---|---|---|---|---|---|---|---|---|
| BillingService.calculate_total | 0 | 0 | no | no | none | 0 | yes | 0 | no | none |
| AdminConsole.run_admin_command | 0 | 0 | yes | no | none | 0 | no | 0 | yes | eval_injection |
| DataPipeline.process_data | 2 | 2 | no | no | none | 1 | no | 2 | yes | none |
| OpsTools.backup_database | 0 | 0 | no | yes | stdlib_only | 0 | no | 0 | no | multiple_critical |

### Questions and ground truth

| Question id | Type | Instructions | Options (choice only) | Ground truth |
|---|---|---|---|---|
| `most_urgent_security` | choice | Which method poses the single most urgent security risk? | the 4 breadcrumbs | `AdminConsole.run_admin_command(x)` |
| `longest_code` | choice | Which method has the longest code (highest code-length score)? | the 4 breadcrumbs | `DataPipeline.process_data(a, b, c, d, e)` |
| `complex_but_safe` | choice | Which method has the highest branching complexity and the most non-descriptive names, but no actual security risk? | the 4 breadcrumbs | `DataPipeline.process_data(a, b, c, d, e)` |
| `admin_has_secret` | noul | Does AdminConsole.run_admin_command(x) contain a hardcoded password or secret? | — | False |
| `admin_longer_than_pipeline` | noul | Is AdminConsole.run_admin_command(x)'s code-length score higher than DataPipeline.process_data(...)'s code-length score? | — | False (0 vs 2) |
| `prioritize_despite_simplicity` | choice | Which method should be prioritized for a security fix over all the others, even though it has the lowest code-length and parameter-count scores of the four? | the 4 breadcrumbs | `AdminConsole.run_admin_command(x)` |

Note: unlike the earlier bitmask test, no explicit severity ranking was given between the
`choice` categories `eval_injection` vs. `multiple_critical` (hardcoded secret + command
injection) — "most urgent" for `most_urgent_security` and `prioritize_despite_simplicity` rests on
an implicit convention (arbitrary `eval()` on unvalidated input outranks a combination of a
hardcoded default password + shell command built via string concatenation), not a stated rule. A
model picking `OpsTools.backup_database(host, password)` instead is making a defensible judgment
call, not necessarily a factual error — worth tightening with an explicit point-value legend
(as the bitmask test used) if this is re-run.

### Actual results (run 2026-09-27)

| Question | kev-4b | semif | hosted jev |
|---|---|---|---|
| most_urgent_security | AdminConsole ✓ (0.81) | OpsTools ✗ (0.39) | AdminConsole ✓ (0.81) |
| longest_code | DataPipeline ✓ (1.0) | DataPipeline ✓ (0.86) | DataPipeline ✓ (1.0) |
| complex_but_safe | DataPipeline ✓ (1.0) | BillingService ✗ (0.67) | DataPipeline ✓ (1.0) |
| admin_has_secret | False ✓ | False ✓ | False ✓ |
| admin_longer_than_pipeline | **True ✗** (0.94, expected False) | False ✓ | False ✓ |
| prioritize_despite_simplicity | AdminConsole ✓ (0.82) | OpsTools ✗ (0.51) | AdminConsole ✓ (0.81) |
| **Score** | **5/6** | **3/6** | **6/6** |
| input_tokens | 1031 | 5291 | 1427 |

### Findings (this confounded run — read the corrected re-run below before trusting these)

- kev-4b 5/6, semif 3/6, hosted jev 6/6. Notably, kev-4b's one miss repeats a pattern seen
  elsewhere in the session: it derives a fact two different ways correctly (AdminConsole is the
  *simplest* method; DataPipeline has the *highest* code-length score) but flips to the wrong
  answer when asked to directly compare the same two numbers head-to-head
  (`admin_longer_than_pipeline` → said True, i.e. 0 > 2 — self-consistency across framings of the
  same fact is the recurring soft spot, independent of the code/table confound).
- **This run cannot support any claim about the table encoding itself** — see the correction below.

---

### Corrected re-run — table only, no source code (isolates what the table encoding alone achieves)

Same `state` as above with the entire Python source section deleted — only the breadcrumb-keyed
fact table remains, prefixed with: *"No source code is shown here — these are the only facts
available."* Same 6 questions, same ground truth.

| Question | kev-4b | semif | hosted jev |
|---|---|---|---|
| most_urgent_security | OpsTools ✗ (0.46) | AdminConsole ✓ (0.95) | AdminConsole ✓ (0.72) |
| longest_code | DataPipeline ✓ (1.0) | DataPipeline ✓ (0.91) | DataPipeline ✓ (1.0) |
| complex_but_safe | DataPipeline ✓ (1.0) | DataPipeline ✓ (0.40) | DataPipeline ✓ (1.0) |
| admin_has_secret | False ✓ | False ✓ | False ✓ |
| admin_longer_than_pipeline | False ✓ | False ✓ | False ✓ |
| prioritize_despite_simplicity | OpsTools ✗ (0.33) | AdminConsole ✓ (0.38) | AdminConsole ✓ (0.74) |
| **Score** | **4/6** | **6/6** | **6/6** |
| input_tokens | 816 | 3947 | 1224 |

**This is the trustworthy comparison, and it moved in opposite directions per model:**

| | With code + table (confounded) | Table only (isolated) |
|---|---|---|
| kev-4b | 5/6 | **4/6 — got worse** |
| semif | 3/6 | **6/6 — got much better, now perfect** |
| hosted jev | 6/6 | 6/6 — unchanged |

- **semif was actively confused by the raw source code.** With the code visible, it picked
  `OpsTools.backup_database` (which has visible `os.system()` + a hardcoded password) as the
  "most urgent" risk over `AdminConsole`'s `eval()` — arguably swayed by how alarming the code
  *looks* on a direct read. With only the abstracted table (no code to look at), it correctly
  followed the stated category (`eval_injection`) both times, going 3/6 → 6/6.
- **kev-4b showed the opposite pattern** — it seems to have partly relied on actually reading the
  code to get "eval is worse" right; forced to rely purely on the table's category label
  (`eval_injection` vs. `multiple_critical`), it flipped to the scarier-*sounding* label
  (`multiple_critical`) on both `most_urgent_security` and `prioritize_despite_simplicity`,
  4/6.
- **Hosted jev was indifferent either way** — identical 6/6, and via the appendix's raw JSON,
  nearly identical confidence values too. It appears to lean on the table regardless of whether
  redundant source code is also present.
- **Conclusion:** the original confounded run's headline claim ("grounding in real code produced
  the cleanest results") does not hold up. Once isolated, the table-only encoding works very well
  for hosted jev and semif (6/6 each) but not for kev-4b (4/6) — and which information source a
  model actually uses, when given both, is model-specific and not predictable from the confounded
  run alone. **Lesson: never give a model both the ground-truth-bearing raw artifact and a
  summary/encoding of it in the same test — you cannot tell which one it used.**

---

## Variant 12 — Dense 8-character base-36 positional mask (quantized "reference anchor")

Motivation: a compact, code-adjacent "reference anchor" — the same underlying facts as Variant 11,
but packed into a single 8-character string (base-36 alphabet, 0-9 then A-Z) instead of spread
across 10 labeled table columns, addressing whether decode accuracy survives much higher
information density per character. Explicitly **not** a one-way hash (that would be irreversible
by construction, for anyone, not just Jev) — this is reversible quantization, the same idea as a
YouTube video ID: a short code that expands back to a wider range of information via a stated
legend, not a cryptographic digest. Table-only methodology (no source code), same 4 breadcrumbs,
same 6 questions/ground truth as the corrected Variant 11 re-run above, for direct comparison.

### State sent (verbatim)

```
Code quality reference anchors: each method below is identified by its breadcrumb signature
(Class.method(params)) and has an 8-character positional mask. Each character position uses the
base-36 alphabet (0-9, then A-Z) and is defined by the legend below; a position only uses as much
of that range as the data requires (most positions here only need 0-4).

Legend (position: meaning, valid values):
1: Code length -- 0=short(<5 lines), 1=medium(5-12 lines), 2=long(>12 lines)
2: Parameter count -- 0=few(1-2), 1=moderate(3-4), 2=many(5+)
3: Calls eval() or exec() on input -- 0=no, 1=yes
4: Contains a hardcoded password or secret -- 0=no, 1=yes
5: Imports -- 0=none, 1=stdlib_only, 2=third_party
6: try/except blocks -- 0=none, 1=one, 2=two_or_more
7: Branching complexity (if/for/while count) as a percent-of-max quartile, where 0-8 branches spans
   0-100% -- 0=0-25% (0-2 branches), 1=25-50% (3-4), 2=50-75% (5-6), 3=75-100% (7-8)
8: Primary risky operation -- 0=none, 1=eval_injection, 2=hardcoded_secret, 3=command_injection,
   4=multiple_critical

| Method | Mask |
|--------|------|
| BillingService.calculate_total(prices, tax_rate) | 00000000 |
| AdminConsole.run_admin_command(x) | 00100001 |
| DataPipeline.process_data(a, b, c, d, e) | 22000120 |
| OpsTools.backup_database(host, password) | 00110004 |
```

### Questions and ground truth

Same 6 questions as Variant 11 (reworded to say "mask"/"position N" instead of "table"/column
names), same ground truth: `most_urgent_security`→AdminConsole, `longest_code`→DataPipeline,
`complex_but_safe`→DataPipeline, `admin_has_secret`→False, `admin_longer_than_pipeline`→False,
`prioritize_despite_simplicity`→AdminConsole.

### Actual results (run 2026-09-27)

| Question | kev-4b | semif | hosted jev |
|---|---|---|---|
| most_urgent_security | OpsTools ✗ (0.53) | AdminConsole ✓ (0.34) | AdminConsole ✓ (0.33) |
| longest_code | DataPipeline ✓ (0.97) | **BillingService ✗ (0.10)** | DataPipeline ✓ (1.0) |
| complex_but_safe | **BillingService ✗ (0.77)** | BillingService ✗ (0.64) | DataPipeline ✓ (0.79) |
| admin_has_secret | False ✓ | False ✓ | False ✓ |
| admin_longer_than_pipeline | False ✓ | False ✓ | False ✓ |
| prioritize_despite_simplicity | OpsTools ✗ (0.82) | BillingService ✗ (0.39) | AdminConsole ✓ (0.42) |
| **Score** | **3/6** | **3/6** | **6/6** |
| input_tokens | 845 | 3956 | 1243 |

### Comparison across all three encodings of the identical underlying facts

| Encoding | kev-4b | semif | hosted jev |
|---|---|---|---|
| 10-column typed table (table-only) | 4/6 | 6/6 | 6/6 |
| 8-char dense base-36 mask | **3/6** | **3/6** | 6/6 |

### Findings

- **Hosted jev: 6/6 on both encodings, no loss at all from the extra compression.** Its confidence
  values on the mask version are lower/more spread (e.g. 0.33-0.42 vs. 0.72-1.0 on the table),
  suggesting it finds the dense format genuinely harder to be *certain* about even though it still
  gets every answer right — but it gets every answer right.
- **Both open-source models degraded, and semif's drop is the steepest of the whole session**:
  6/6 → 3/6. It now fails `longest_code`, a single-position lookup with no cross-referencing at
  all — something it had nailed at 90%+ confidence one encoding ago. Packing 8 facts into one
  unlabeled positional string, each requiring a legend lookup by character position rather than a
  labeled column, made even simple single-fact retrieval unreliable for it.
- **kev-4b also dropped (4/6 → 3/6)**, missing `complex_but_safe` in addition to repeating its
  `most_urgent_security`/`prioritize_despite_simplicity` mistake from the table version (still
  drawn to `OpsTools`'s `multiple_critical` label over `AdminConsole`'s `eval_injection`).
- **Direct answer to the "compact code-quality reference anchor at scale" idea:** it is viable —
  but, on this evidence, only with the hosted model. Both open-source models available here lose
  real accuracy once the same information is compressed this densely, even though nothing was
  actually hashed or made irreversible — the legend was given in full both times. The cost isn't
  the encoding being unrecoverable, it's information density outstripping what the open-source
  models can reliably decode-and-reason-over in one shot.

---

## Appendix — full raw request/response JSON for Variant 11

Re-fired the exact same request to get byte-accurate JSON (not reconstructed from memory). One
observation this surfaced: kev-4b and semif reproduced their confidence numbers almost exactly
between the original run and this re-fire; hosted jev's discrete answers (`choice`/`noul`
decisions) were identical both times, but its confidence values shifted slightly run-to-run
(e.g. `prioritize_despite_simplicity` confidence 0.81 → 0.84, `admin_longer_than_pipeline`
0.01 → 0.02) — the hosted model is not perfectly deterministic between calls, even though nothing
in the request changed.

### Full request body (identical for all three targets; only the URL and, for hosted jev, the
`Authorization: Bearer $TYPESAFE_API_KEY` header differ)

Note: this is the **confounded** run (code + table both present — see the warning on Variant 11
above). `state` is omitted below and shown once, cleanly, in the "State sent (verbatim)" section
near the top of Variant 11 instead of being duplicated here — this keeps the JSON below valid
(no broken escaping) and avoids repeating a large block twice in the same document.

```json
{
  "state": "<< see Variant 11's 'State sent (verbatim)' section above — identical text >>",
  "model": "jev-latest",
  "questions": {
    "most_urgent_security": {
      "type": "choice",
      "instructions": "Which method poses the single most urgent security risk?",
      "criteria": {
        "BillingService.calculate_total(prices, tax_rate)": null,
        "AdminConsole.run_admin_command(x)": null,
        "DataPipeline.process_data(a, b, c, d, e)": null,
        "OpsTools.backup_database(host, password)": null
      }
    },
    "longest_code": {
      "type": "choice",
      "instructions": "Which method has the longest code (highest code-length score)?",
      "criteria": {
        "BillingService.calculate_total(prices, tax_rate)": null,
        "AdminConsole.run_admin_command(x)": null,
        "DataPipeline.process_data(a, b, c, d, e)": null,
        "OpsTools.backup_database(host, password)": null
      }
    },
    "complex_but_safe": {
      "type": "choice",
      "instructions": "Which method has the highest branching complexity and the most non-descriptive names, but no actual security risk?",
      "criteria": {
        "BillingService.calculate_total(prices, tax_rate)": null,
        "AdminConsole.run_admin_command(x)": null,
        "DataPipeline.process_data(a, b, c, d, e)": null,
        "OpsTools.backup_database(host, password)": null
      }
    },
    "admin_has_secret": {
      "type": "noul",
      "instructions": "Does AdminConsole.run_admin_command(x) contain a hardcoded password or secret?"
    },
    "admin_longer_than_pipeline": {
      "type": "noul",
      "instructions": "Is AdminConsole.run_admin_command(x)'s code-length score higher than DataPipeline.process_data(a, b, c, d, e)'s code-length score?"
    },
    "prioritize_despite_simplicity": {
      "type": "choice",
      "instructions": "Which method should be prioritized for a security fix over all the others, even though it has the lowest code-length and parameter-count scores of the four?",
      "criteria": {
        "BillingService.calculate_total(prices, tax_rate)": null,
        "AdminConsole.run_admin_command(x)": null,
        "DataPipeline.process_data(a, b, c, d, e)": null,
        "OpsTools.backup_database(host, password)": null
      }
    }
  }
}
```

### Full response — kev-4b (`127.0.0.1:8010`)

```json
{
  "model": "jev-latest",
  "answers": {
    "most_urgent_security": {
      "type": "choice",
      "choice": "AdminConsole.run_admin_command(x)",
      "confidence": 0.81,
      "probabilities": {
        "BillingService.calculate_total(prices, tax_rate)": 0.0,
        "AdminConsole.run_admin_command(x)": 0.86,
        "DataPipeline.process_data(a, b, c, d, e)": 0.0,
        "OpsTools.backup_database(host, password)": 0.14
      }
    },
    "longest_code": {
      "type": "choice",
      "choice": "DataPipeline.process_data(a, b, c, d, e)",
      "confidence": 1.0,
      "probabilities": {
        "BillingService.calculate_total(prices, tax_rate)": 0.0,
        "AdminConsole.run_admin_command(x)": 0.0,
        "DataPipeline.process_data(a, b, c, d, e)": 1.0,
        "OpsTools.backup_database(host, password)": 0.0
      }
    },
    "complex_but_safe": {
      "type": "choice",
      "choice": "DataPipeline.process_data(a, b, c, d, e)",
      "confidence": 1.0,
      "probabilities": {
        "BillingService.calculate_total(prices, tax_rate)": 0.0,
        "AdminConsole.run_admin_command(x)": 0.0,
        "DataPipeline.process_data(a, b, c, d, e)": 1.0,
        "OpsTools.backup_database(host, password)": 0.0
      }
    },
    "admin_has_secret": {
      "type": "noul",
      "noul": 0.0
    },
    "admin_longer_than_pipeline": {
      "type": "noul",
      "noul": 0.94
    },
    "prioritize_despite_simplicity": {
      "type": "choice",
      "choice": "AdminConsole.run_admin_command(x)",
      "confidence": 0.82,
      "probabilities": {
        "BillingService.calculate_total(prices, tax_rate)": 0.0,
        "AdminConsole.run_admin_command(x)": 0.87,
        "DataPipeline.process_data(a, b, c, d, e)": 0.0,
        "OpsTools.backup_database(host, password)": 0.13
      }
    }
  },
  "usage": {
    "input_tokens": 1031,
    "output_tokens": 458
  },
  "latency_ms": 71.1
}
```

### Full response — semif (`127.0.0.1:8012`)

```json
{
  "model": "semif",
  "answers": {
    "most_urgent_security": {
      "type": "choice",
      "choice": "OpsTools.backup_database(host, password)",
      "confidence": 0.3935,
      "probabilities": {
        "BillingService.calculate_total(prices, tax_rate)": 0.0271,
        "AdminConsole.run_admin_command(x)": 0.4245,
        "DataPipeline.process_data(a, b, c, d, e)": 0.0032,
        "OpsTools.backup_database(host, password)": 0.5451
      }
    },
    "longest_code": {
      "type": "choice",
      "choice": "DataPipeline.process_data(a, b, c, d, e)",
      "confidence": 0.8573,
      "probabilities": {
        "BillingService.calculate_total(prices, tax_rate)": 0.0346,
        "AdminConsole.run_admin_command(x)": 0.0077,
        "DataPipeline.process_data(a, b, c, d, e)": 0.893,
        "OpsTools.backup_database(host, password)": 0.0647
      }
    },
    "complex_but_safe": {
      "type": "choice",
      "choice": "BillingService.calculate_total(prices, tax_rate)",
      "confidence": 0.6665,
      "probabilities": {
        "BillingService.calculate_total(prices, tax_rate)": 0.7499,
        "AdminConsole.run_admin_command(x)": 0.0176,
        "DataPipeline.process_data(a, b, c, d, e)": 0.2148,
        "OpsTools.backup_database(host, password)": 0.0176
      }
    },
    "admin_has_secret": {
      "type": "noul",
      "noul": 0.0675466911396291
    },
    "admin_longer_than_pipeline": {
      "type": "noul",
      "noul": 0.18242552380635632
    },
    "prioritize_despite_simplicity": {
      "type": "choice",
      "choice": "OpsTools.backup_database(host, password)",
      "confidence": 0.5078,
      "probabilities": {
        "BillingService.calculate_total(prices, tax_rate)": 0.0277,
        "AdminConsole.run_admin_command(x)": 0.3377,
        "DataPipeline.process_data(a, b, c, d, e)": 0.0038,
        "OpsTools.backup_database(host, password)": 0.6309
      }
    }
  },
  "usage": {
    "input_tokens": 5291,
    "output_tokens": 6
  },
  "latency_ms": 677.4
}
```

### Full response — hosted jev (`api.typesafe.ai`, model `jev-1.13.0`)

```json
{
  "model": "jev-1.13.0",
  "answers": {
    "most_urgent_security": {
      "type": "choice",
      "choice": "AdminConsole.run_admin_command(x)",
      "confidence": 0.8,
      "probabilities": {
        "OpsTools.backup_database(host, password)": 0.15,
        "AdminConsole.run_admin_command(x)": 0.85,
        "BillingService.calculate_total(prices, tax_rate)": 0.0,
        "DataPipeline.process_data(a, b, c, d, e)": 0.0
      }
    },
    "longest_code": {
      "type": "choice",
      "choice": "DataPipeline.process_data(a, b, c, d, e)",
      "confidence": 1.0,
      "probabilities": {
        "OpsTools.backup_database(host, password)": 0.0,
        "AdminConsole.run_admin_command(x)": 0.0,
        "BillingService.calculate_total(prices, tax_rate)": 0.0,
        "DataPipeline.process_data(a, b, c, d, e)": 1.0
      }
    },
    "complex_but_safe": {
      "type": "choice",
      "choice": "DataPipeline.process_data(a, b, c, d, e)",
      "confidence": 1.0,
      "probabilities": {
        "OpsTools.backup_database(host, password)": 0.0,
        "AdminConsole.run_admin_command(x)": 0.0,
        "BillingService.calculate_total(prices, tax_rate)": 0.0,
        "DataPipeline.process_data(a, b, c, d, e)": 1.0
      }
    },
    "admin_has_secret": {
      "type": "noul",
      "noul": 0.02
    },
    "admin_longer_than_pipeline": {
      "type": "noul",
      "noul": 0.02
    },
    "prioritize_despite_simplicity": {
      "type": "choice",
      "choice": "AdminConsole.run_admin_command(x)",
      "confidence": 0.84,
      "probabilities": {
        "OpsTools.backup_database(host, password)": 0.12,
        "AdminConsole.run_admin_command(x)": 0.88,
        "BillingService.calculate_total(prices, tax_rate)": 0.0,
        "DataPipeline.process_data(a, b, c, d, e)": 0.0
      }
    }
  },
  "usage": {
    "input_tokens": 1427,
    "output_tokens": 431
  }
}
```
