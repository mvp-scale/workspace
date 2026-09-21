# asvs_questions (question library, not a labelled probe set)

- Source: OWASP Application Security Verification Standard 4.0.3, https://github.com/OWASP/ASVS (cloned 2026-09-21; file `4.0/docs_en/OWASP Application Security Verification Standard 4.0.3-en.csv`). Licence CC BY-SA 4.0 (derived files must carry the same licence and attribution to OWASP).
- Build: `build_asvs_questions.py` (deterministic, no sampling) -> `asvs_questions.json`: id, chapter ("V2 Authentication"), section, level1/level2/level3 (booleans from the checkmark columns), cwe (string as in source, may be empty), text verbatim from `req_description` (including embedded markdown links to OWASP Proactive Controls; not stripped).
- Excluded: 8 rows whose text is "[DELETED, ...]" (source placeholders). 286 CSV rows -> 278 requirements.
- Verify-phrased: 277 of 278 start with "Verify"; the one exception (V3 re-authentication) starts "If authenticators permit users to remain logged in, verify that ...". Nearly all are directly testable statements, but many are broad or need process evidence (V1) rather than a text/code snippet.

## Requirements per chapter
V1 Architecture, Design and Threat Modeling 39; V2 Authentication 57; V3 Session Management 20; V4 Access Control 9; V5 Validation, Sanitization and Encoding 30; V6 Stored Cryptography 16; V7 Error Handling and Logging 12; V8 Data Protection 17; V9 Communication 8; V10 Malicious Code 10; V11 Business Logic 8; V12 Files and Resources 15; V13 API and Web Service 13; V14 Configuration 24. Total 278.

## cwe_top25.json
- Source: MITRE 2025 CWE Top 25 Most Dangerous Software Weaknesses, https://cwe.mitre.org/top25/archive/2025/2025_cwe_top25.html (the current list on the site; no 2026 list exists as of retrieval). Names and ranks from that page; descriptions are the `Description` field of the CWE v4.20 catalogue (https://cwe.mitre.org/data/xml/cwec_latest.xml.zip, dated 2026-04-30). MITRE terms: free to use with attribution (c) The MITRE Corporation.
- Fields: rank, id ("CWE-79"), name, description (whitespace-collapsed). MITRE's full description, not a shortened one; the Top 25 page itself carries no per-entry description.

## Caveats
Requirement text is a trusted list of audit questions but is not labelled data; results on documents need separate ground truth. Contamination: ASVS is widely present in training data.
