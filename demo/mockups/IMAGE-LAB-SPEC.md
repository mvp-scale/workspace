# Image lab (mock-up spec)

Mock-up: `image-lab.html` (static; scripted answers; `python3 -m http.server -b 127.0.0.1 -d demo 8110`, then `/mockups/image-lab.html`).

## What it is
A page where an image goes in, a typed question goes in, and the model returns one probability per option. Only WINN12 (Winnow-12B with `--mmproj`) accepts images. Every run is stored against its image so it can be reopened and asked again with a different question.

## Screens
- **Try an image**: library rail by business case (with per-case accuracy), thumbnails, large image with source and licence, ask panel (suggested questions per case, free question, Yes/no or Pick-one, optional "your label"), answer bars, runs on this image with "Ask again".
- **Library scorecard**: accuracy, run count and median latency per business case, from labelled runs only.
- **All recorded runs**: every run, newest first; reopening loads the image and question.

## Library
About 50 images across: invoices and receipts, forms and signatures, IDs and licences (specimens only), damage and claims, retail shelves, site safety, screenshots and errors. Each has a business case, a source URL, a licence, and optional known answers per preset question. Images live in git-ignored `data/image-lab/images/`; `data/image-lab/library.json` holds the metadata. Only openly licensed, specimen or self-made images. No real person's ID, no third-party files committed.

## Backend needed (not built)
- `GET /api/image-lab/library`, `GET /api/image-lab/image/<id>` (read-only).
- `POST /api/image-lab/ask` `{image_id | uploaded bytes, question:{type,instructions,criteria}}` -> Winnow `POST /v1/systemone` with `winnow.images: [data URL]`; returns probabilities, tokens, latency.
- `POST /api/image-lab/runs` appends to `data/image-lab/runs.jsonl`; `GET` lists them.
- Uploads: PNG/JPEG/WebP, 24 MB per image (Winnow's limit), size and type checked server-side, stored under a content hash, shown as "uploaded".
- `winnow` added to `BACKENDS` already (`:8091`); the page shows whether vision is on.

## Open points
- Who can upload and record on a shared demo (the server binds to 127.0.0.1 by default).
- Whether typed answers are compared with the chat route's free-text description for the same image.
