# websec probe set (OWASP Benchmark Java v1.2)

- Source: OWASP Benchmark Project, Java v1.2, https://github.com/OWASP-Benchmark/BenchmarkJava (commit 20cbf3d11123347e47ed89541e6942836def53f7, cloned to /workspace/data/sources/owasp/BenchmarkJava). Labels from `expectedresults-1.2.csv`; code from `src/main/java/org/owasp/benchmark/testcode/`.
- Licence: GPL-2.0 (repo LICENSE). Test code is redistributed here in cleaned excerpts for research; keep the GPL notice in mind when reusing.
- Retrieved: 2026-09-21. Citation: OWASP Foundation, "OWASP Benchmark Project" (Dave Wichers et al.), v1.2, https://owasp.org/www-project-benchmark/
- Builder: `build_websec.py` (seed 20260921), output `websec.jsonl`, 80 rows, noul (labels no/yes; yes = real vulnerability).

## Counts (16 per category, 8 yes / 8 no each)
sqli (CWE-89) 8/8, cmdi (CWE-78) 8/8, pathtraver (CWE-22) 8/8, xss (CWE-79) 8/8, securecookie (CWE-614) 8/8. Total 40 yes, 40 no. Each category has its own audit question (same text within a category), recorded in `family` and `provenance.notes`.

## Cleaning (mechanical)
Licence header, imports, annotations and all comments removed (string-aware stripper); only `doPost` kept (the `doGet` form only used if doPost merely delegates); if doPost calls `doSomething(...)`, that helper method is appended (the label depends on it). Wrapped in `class Handler extends HttpServlet`. `BenchmarkTest#####` and `BenchmarkTest` -> `Handler`; `org.owasp.benchmark.helpers.` -> `helpers.`; blank lines removed, statements re-joined/re-indented. String literals `"SafeXxx"` -> `"Xxx"`, `"safe!"` -> `"ok!"` were not needed for the final categories but the rule exists in the script. Rows containing "benchmark", "vuln" or "safe" (any case) after cleaning are dropped; rows over 1500 chars are dropped (no truncation). For securecookie only, pure console/response-output statements (`response.getWriter().println`, `System.out.println`) are dropped to fit the length limit (the script applies this to the TRIM categories, which include securecookie). Class/servlet path strings and test numbers do not appear. Some rows contain random numeric identifiers (e.g. map12345) that are Benchmark's own and unrelated to test numbers.

## Caveats
- The "no" cases are designed false positives built with tricks (dead branches such as `(7*42)-num > 200 ? ... : param`, constant propagation through maps/lists, sanitisers, parameterised queries), so they are deliberately hard; "yes" cases are often straightforward.
- Selection bias: only files that fit in 1500 chars after cleaning and contain no "safe"/"benchmark" strings qualify; many source files were excluded on that basis.
- hash, crypto (algorithm chosen through a hidden benchmark.properties key: hashAlg1=MD5, hashAlg2=SHA-256, cryptoAlg1=DES, cryptoAlg2=AES/CCM), weakrand (almost all files too long or containing "Safe*" names/strings), ldapi and xpathi (too long, <5 usable per class) were excluded. Hash/crypto labels are not decidable from the text alone.
- securecookie "yes" = cookie without `setSecure(true)`; the rows are otherwise cookie-echo servlets.
- Contamination: OWASP Benchmark is public on GitHub and widely used for SAST evaluation and likely in code-model pretraining.
- Benchmark labels are by construction, not audited by humans; a few known CWE-mapping oddities exist.
