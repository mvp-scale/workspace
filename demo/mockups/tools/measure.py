#!/usr/bin/env python3
"""Fluidity harness for the mock-ups. Usage: measure.py page.html [seconds] [speed]
Needs playwright + chromium (PLAYWRIGHT_BROWSERS_PATH). Prints one JSON object of measured outcomes.
Every wait is bounded. Works on file:// pages; no network."""
import json, sys, time, pathlib
from playwright.sync_api import sync_playwright

INIT = """
window.__m = {reqs: 0, frames: [], cls: 0, long: 0, scroll: [], firstWord: null, t0: null, flags: {}};
(() => { let last = performance.now(), sc = null, prev = 0;
  const pick = () => { let best = null, bh = 0; for (const e of document.querySelectorAll('*')) { const cs = getComputedStyle(e);
      if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') && e.scrollHeight > e.clientHeight + 20 && e.clientHeight > bh) { best = e; bh = e.clientHeight; } } return best; };
  const loop = (t) => { __m.frames.push(t - last); last = t;
    if (__m.t0 !== null) {
      if (window.__glideY) { const y = Object.values(window.__glideY)[0]; if (y !== undefined) { if (__m.gprev !== undefined) __m.scroll.push(y - __m.gprev); __m.gprev = y; } }
      else if (!sc || !sc.isConnected) { sc = pick(); prev = sc ? sc.scrollTop : 0; }
      else { __m.scroll.push(sc.scrollTop - prev); prev = sc.scrollTop; } }
    requestAnimationFrame(loop); };
  requestAnimationFrame(loop);
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) { __m.cls += e.value; (__m.shifts = __m.shifts || []).push([e.value, (e.sources || []).map(s => (s.node ? (s.node.nodeName + '.' + (s.node.className || s.node.id || '')) : '?') + ' ' + Math.round(s.previousRect.y) + '>' + Math.round(s.currentRect.y))]); } }).observe({type: 'layout-shift', buffered: true});
  try { new PerformanceObserver(l => { __m.long += l.getEntries().length; }).observe({type: 'longtask'}); } catch (e) {}
  new MutationObserver(() => { if (__m.t0 !== null && __m.firstWord === null && document.querySelector('.w')) __m.firstWord = performance.now() - __m.t0; })
    .observe(document, {childList: true, subtree: true});
})();
"""

def pct(a, p):
    a = sorted(a); return a[min(len(a) - 1, int(len(a) * p))] if a else None

def main():
    page = pathlib.Path(sys.argv[1]).resolve(); secs = float(sys.argv[2]) if len(sys.argv) > 2 else 20
    speed = sys.argv[3] if len(sys.argv) > 3 else "1"
    with sync_playwright() as p:
        b = p.chromium.launch(); import os; vw, vh = (os.environ.get("VIEW", "1440x900")).split("x"); ctx = b.new_context(viewport={"width": int(vw), "height": int(vh)}); pg = ctx.new_page()
        reqs = []
        pg.on("request", lambda r: reqs.append(r.url) if not (r.url.startswith("file:") or "fonts.g" in r.url) else None)
        pg.add_init_script(INIT); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(page.as_uri(), wait_until="load", timeout=15000); pg.wait_for_timeout(400)
        if speed != "1":
            try: pg.select_option("select[aria-label=Speed]", speed, timeout=2000)
            except Exception: pass
        pg.evaluate("__m.frames.length = 0; __m.cls = 0; __m.long = 0; __m.scroll.length = 0; __m.t0 = performance.now()")
        pg.click(".btn.primary", timeout=3000)
        flag_seen = {}; card_seen = {}; added = None; cls_before = None
        t_end = time.time() + secs; t_add = time.time() + secs * 0.5
        while time.time() < t_end:
            pg.wait_for_timeout(250)
            if pg.evaluate("!!window.__mockClock"):
                for k, v in pg.evaluate("window.__mockFlags ? window.__mockFlags() : {}").items(): flag_seen.setdefault(k, [v, v])[1] = v
                for k, v in pg.evaluate("window.__mockFlags ? window.__mockFlags('.moment') : {}").items(): card_seen.setdefault(k, [v, v])[1] = v
            if added is None and time.time() > t_add and pg.query_selector("#watch-in"):
                cls_before = pg.evaluate("__m.cls"); n0 = pg.evaluate("document.querySelectorAll('.wbar .chip').length")
                if n0 >= 8:
                    pg.click(".wbar .chip .x"); pg.wait_for_timeout(100); n0 = pg.evaluate("document.querySelectorAll('.wbar .chip').length")
                cls_before = pg.evaluate("__m.cls")
                pg.fill("#watch-in", "Anyone mentioning a deadline"); pg.click(".wbar .btn")
                pg.wait_for_timeout(120); added = {"chip_added": pg.evaluate("document.querySelectorAll('.wbar .chip').length") == n0 + 1}
        if added is not None: added["cls_delta"] = round(pg.evaluate("__m.cls") - cls_before, 4)
        sim_end = pg.evaluate("window.__mockClock ? window.__mockClock() : 0")
        overflow = pg.evaluate("document.documentElement.scrollWidth > innerWidth")
        m = pg.evaluate("__m")
        pg.set_viewport_size({"width": 400, "height": 800}); pg.wait_for_timeout(300)
        overflow400 = pg.evaluate("document.documentElement.scrollWidth > innerWidth")
        if len(sys.argv) > 4: pg.screenshot(path=f"{sys.argv[4]}-phone.png")
        pg.set_viewport_size({"width": int(vw), "height": int(vh)})
        for scheme in ("light", "dark"):
            pg.emulate_media(color_scheme=scheme); pg.wait_for_timeout(300)
            if len(sys.argv) > 4: pg.screenshot(path=f"{sys.argv[4]}-{scheme}.png")
        b.close()
    fr = m["frames"][5:]; sc = m["scroll"]
    out = {"page": page.name, "seconds": secs, "speed": speed, "errors": errs,
           "frame_ms_p50": round(pct(fr, .5), 1), "frame_ms_p95": round(pct(fr, .95), 1), "frame_ms_max": round(max(fr), 1),
           "frames_over_33ms_pct": round(100 * sum(f > 33.4 for f in fr) / len(fr), 2),
           "cls": round(m["cls"], 4), "long_tasks": m["long"],
           "first_word_ms": None if m["firstWord"] is None else round(m["firstWord"]),
           "scroll_max_jump_px": round(max([abs(x) for x in sc] or [0]), 1),
           "scroll_frames_over_40px": sum(abs(x) > 40 for x in sc),
           "sim_end_s": round(sim_end, 1), "overflow_1440": overflow, "overflow_400": overflow400, "requests_non_font": len(reqs), "watch_add": added,
           "flags_seen": len(flag_seen), "top_shifts": sorted(m.get("shifts", []), key=lambda x: -x[0])[:4],
           "flag_dwell_min_sim_s": None if not flag_seen else round(min(min(v[1] - v[0], sim_end - v[0]) for v in flag_seen.values() if True), 1),
           "flags_short": sorted(k for k, v in flag_seen.items() if (v[1] - v[0]) < 29.5 and (sim_end - v[0]) >= 30),
           "cards_seen": len(card_seen), "cards_short": sorted(k for k, v in card_seen.items() if (v[1] - v[0]) < 29.5 and (sim_end - v[0]) >= 30)}
    print(json.dumps(out))
main()
