# memsafety probe set

- Source: NIST SARD Juliet Test Suite for C/C++ v1.3 (2017-10-01 release), SARD test suite 112.
- URL: https://samate.nist.gov/SARD/test-suites/112 (zip: https://samate.nist.gov/SARD/downloads/test-suites/2017-10-01-juliet-test-suite-for-c-cplusplus-v1-3.zip)
- Licence: public domain (US Government / NIST work).
- Retrieved: 2026-09-21. Raw files: /workspace/data/sources/juliet/ (git-ignored).
- Citation: Boland, T., Black, P.E. "Juliet 1.1 C/C++ and Java Test Suite", IEEE Computer 45(10), 2012; NIST SARD Juliet Test Suite for C/C++ v1.3.
- Build: `python3 build_memsafety.py` (seed 20260921), output memsafety.jsonl.

## Sampling
Per CWE, up to 8 test cases: single-file testcases, flow variant 01 (variant 02 only to fill up when fewer than 8 distinct 01 bases are usable), seeded shuffle. Each case gives the `_bad` function (yes) and one seeded-random good function (no), sharing a `group` id. Functions >1500 chars or retaining bad/good/CWE/flaw after sanitising are skipped.
Total 154 items = 77 pairs: 77 yes / 77 no (perfectly balanced by construction).

| CWE | pairs |
|---|---|
| 121 stack overflow | 8 |
| 122 heap overflow | 8 |
| 124 buffer underwrite | 8 |
| 126 buffer over-read | 8 |
| 127 buffer under-read | 8 |
| 401 memory leak | 8 |
| 415 double free | 6 (only 6 usable single-file bases in 01/02) |
| 416 use after free | 7 |
| 457 uninitialised variable | 8 |
| 476 NULL dereference | 8 |

Good-variant flavours: goodG2B 46, goodB2G 25, good1 6 (`notes` field records it).

## Sanitising (mechanical)
Comments stripped (all Juliet FLAW/FIX/POTENTIAL FLAW comments); only the target function body kept (main, `_good`/`_bad` wrappers, includes, ifdefs outside the function dropped); function renamed `target_function`; other identifiers/string literals containing bad/good/CWE/flaw renamed `helper_N` / `"text"`; leading `static` removed (good functions are static, bad are not, which would leak the label); lone `;` filler lines removed; blank lines and trailing whitespace collapsed. Logic untouched. Verified: no state matches bad|good|flaw|cwe (case-insensitive); max state length 571 chars.

## Caveats
- Juliet cases are synthetic, small and far simpler than real bugs; models may exploit patterns (e.g. `malloc(10)` vs `malloc(10*sizeof(int))`, presence of a NULL check, a `free` followed by no use).
- Good variants: G2B swaps the bad source for a safe one (sink code identical to bad, which can look "buggy"); B2G keeps the bad source but adds a safe sink; both are labelled safe. Bad and good in a pair often differ by one line.
- Macros/helpers (ALLOCA, printLine, printIntLine, data-source helpers from std_testcase.h) are not defined in the state. Some good functions in CWE-401 are leak-free only by using stack allocation (ALLOCA).
- Contamination: Juliet is public and widely used in vulnerability-detection training data; original identifiers were removed but code shape is recognisable.
- Label quality: labels come from Juliet's bad/good design; no manual verification beyond that (known rare Juliet imperfections, e.g. incidental leaks/undefined behaviour in "good" variants).
