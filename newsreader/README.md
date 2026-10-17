# News reader

Finds stories in curated feeds, fetches each article once, turns it into Markdown and queues it for the World engine to read. No logins, no cookies, no browser; robots.txt honoured; one request per site at a time with a gap.

```
catalogue.csv ──poll──▶ queue (SQLite) ──fetch + Trafilatura──▶ ready (full or teaser) ──GET /next──▶ World engine (Clef reads) ──POST /ack──▶ done
```

- **Sources:** RSS/Atom (feedparser, with ETag/Last-Modified) and Google-News-style news sitemaps for sites without a feed (`kind=sitemap`). `kind=rsshub` rows go through an RSSHub instance (`NR_RSSHUB`, default `http://127.0.0.1:1200`; in Docker Compose below). Feeds that carry the whole article skip the fetch.
- **Depth:** `full` = the article's own text (≥150 words extracted, or ≥300 in the feed); `teaser` = only the feed's headline and summary, with a reason: `robots` (the site refuses fetching), `paywall_or_blocked` (401/402/403/451), `not_html`, `short_extract` (video, live blog, gallery, consent wall), `http_<code>`, `fetch_error_<type>`.
- **Story id:** `sha256(normalised title | source | day)`, the reuse key from `docs/world-engine-as-a-service.md`; `story` is a title-only hash linking the same wire story across outlets.
- **Retention:** article text is deleted after `NR_KEEP_DAYS` (default 7); metadata stays. The queue lives in `data/newsreader/` (git-ignored).

## Run

```
./service.sh start newsreader          # from /workspace; port 8140, log logs/newsreader.log
newsreader/.venv/bin/python -m unittest discover -s newsreader/tests -v
```

World engine: `POST /api/world-engine/live {"source": "newsreader"}` (or the Sample bank / Live news switch on How it works) makes the live feed read from this queue; `"bank"` goes back to the fixed headline file.

## API (127.0.0.1:8140)

| | |
|---|---|
| `GET /health` | `{"ok": true}` |
| `GET /stats` | counts by state and depth, reasons, rates per second over the last 5 minutes (found, extracted, read), backlog, full-text share, median extraction ms, feed health |
| `GET /next?n=1&lease=180&order=newest` | lease ready stories with their Markdown (`order=fifo` for oldest first) |
| `POST /ack {"ids": [...]}` | mark read |
| `GET /items?limit=50` | recent stories, metadata only |
| `POST /poll` | poll every feed now |

The console relays `/stats`, `/items` and `/health` read-only at `/api/newsreader/*`.

## Env

`NR_PORT` (8140), `NR_DB`, `NR_CATALOGUE`, `NR_WORKERS` (8), `NR_POLL_S` (900), `NR_KEEP_DAYS` (7), `NR_HOST_GAP` (1.5 s), `NR_UA`, `NR_RSSHUB`.

## Docker

`docker compose up -d` here starts the reader and RSSHub (`diygod/rsshub`). Not used inside the dev container (no Docker there); `./service.sh` runs the same code as a process.

## Catalogue

`catalogue.csv`: `id,name,url,kind,country,region,lang,category,notes`. An id starting with `#` is switched off (satire is off for the real-news reader). Measured 2026-10-17 on 14 mainstream feeds: Trafilatura gave ≥300 words on 88% of the pages sites allowed; 6 sites refuse fetching through robots.txt and stay at teaser depth.
