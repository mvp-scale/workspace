#!/usr/bin/env python3
"""Build /workspace/probes/v2/websec.jsonl from OWASP Benchmark Java v1.2.
Source: https://github.com/OWASP-Benchmark/BenchmarkJava (expectedresults-1.2.csv,
src/main/java/org/owasp/benchmark/testcode/BenchmarkTest#####.java). Clone (depth 1) to
/workspace/data/sources/owasp/BenchmarkJava (pinned commit recorded in websec.md).
Deterministic: seed 20260921, stratified per category x label.
Cleaning: strip comments, licence header, imports, annotations; keep only doPost (or doGet if
doPost just delegates); wrap in `class Handler`; rename BenchmarkTest##### -> Handler and
org.owasp.benchmark.helpers. -> helpers.; drop blank lines; dedent. Files whose cleaned text
still contains 'benchmark', 'vuln' or 'safe' (case-insens.) or exceeds MAXLEN are excluded.
"""
import csv, json, random, re, os, textwrap
ROOT = "/workspace/data/sources/owasp/BenchmarkJava"
SRC = ROOT + "/src/main/java/org/owasp/benchmark/testcode/"
OUT = "/workspace/probes/v2/websec.jsonl"
SEED, MAXLEN, PER_CLASS = 20260921, 1500, 8
URL = "https://github.com/OWASP-Benchmark/BenchmarkJava/blob/master/src/main/java/org/owasp/benchmark/testcode/%s.java"

Q = {
 "sqli": "Can attacker-controlled input from the request reach a SQL query without being safely parameterised or neutralised?",
 "cmdi": "Can attacker-controlled input from the request reach an operating-system command without being safely neutralised?",
 "pathtraver": "Can attacker-controlled input from the request be used to build a file path that is opened or accessed without being safely validated or neutralised?",
 "xss": "Can attacker-controlled input from the request be written into the HTTP response without being safely encoded or neutralised for HTML?",
 "hash": "Does this code compute a hash using an algorithm that is cryptographically weak or broken for security use?",
 "crypto": "Does this code use a cryptographic cipher algorithm that is weak or broken for protecting data?",
 "weakrand": "Does this code use a predictable (non-cryptographically-secure) random number generator to produce a value that needs to be unpredictable?",
 "securecookie": "Does this code send a cookie over HTTP that is not marked with the Secure flag?",
 "ldapi": "Can attacker-controlled input from the request reach an LDAP query or filter without being safely neutralised?",
 "xpathi": "Can attacker-controlled input from the request reach an XPath query without being safely neutralised?",
}

def strip_comments(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == '"':
            j = i + 1
            while s[j] != '"':
                j += 2 if s[j] == '\\' else 1
            out.append(s[i:j+1]); i = j + 1
        elif c == "'":
            j = i + 1
            while s[j] != "'":
                j += 2 if s[j] == '\\' else 1
            out.append(s[i:j+1]); i = j + 1
        elif s.startswith("//", i):
            while i < n and s[i] != "\n": i += 1
        elif s.startswith("/*", i):
            i = s.index("*/", i) + 2
        else:
            out.append(c); i += 1
    return "".join(out)

def method(s, name, pat=r"public void %s\("):
    m = re.search(pat % name, s)
    if not m: return None
    i = s.index("{", m.start()); d = 0
    for j in range(i, len(s)):
        d += (s[j] == "{") - (s[j] == "}")
        if d == 0: return s[m.start():j+1]

TRIM = {'hash', 'crypto', 'weakrand', 'securecookie', 'ldapi', 'xpathi'}

def clean(fn, cat=None):
    s = strip_comments(open(SRC + fn + ".java").read())
    m = method(s, "doPost")
    if m is None: return None
    if re.search(r"doGet\(request, response\)", m) and len(m) < 300:
        m = method(s, "doGet")
    m = m.replace("org.owasp.benchmark.helpers.", "helpers.")
    m = re.sub(r"BenchmarkTest\d*", "Handler", m)
    m = re.sub(r"@Override\s*", "", m)
    if "doSomething(" in m.replace("doSomething(request", "X", 0):
        h = method(s, "doSomething", r"(?:private static|public) String %s\(")
        if h is None: return None
        m = m + "\n" + h  # helper the servlet method delegates to (needed to decide the label)
    lines = [l.strip() for l in m.split("\n") if l.strip()]
    # whitespace normalisation: join continuation lines of one statement, re-indent by brace depth
    stm, cur = [], ""
    for l in lines:
        cur = (cur + " " + l).strip() if cur else l
        if cur.endswith((";", "{", "}")) or cur.startswith("@"):
            stm.append(cur); cur = ""
    if cur: stm.append(cur)
    if cat in TRIM:  # drop pure console/response output statements (no security relevance)
        stm = [l for l in stm if not re.match(r"(response\.getWriter\(\)\s*\.println|System\.out\.println)\(", l)]
    out, d = ["class Handler extends HttpServlet {"], 1
    for l in stm:
        if l.startswith("}"): d -= 1
        out.append("    " * d + l)
        d += l.count("{") - l.count("}") + (1 if l.startswith("}") else 0)
    out.append("}")
    text = "\n".join(out)
    text = re.sub(r'"Safe(\w+)"', r'"\1"', text)
    text = text.replace('"moresafe"', '"more"').replace('"safe!"', '"ok!"').replace('"safe"', '"ok"')
    text = re.sub(r"\(\s+", "(", text); text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\s+\.", ".", text)
    return text

def main():
    rows = list(csv.reader(l for l in open(ROOT + "/expectedresults-1.2.csv") if not l.startswith("#")))
    rows = [r for r in rows if r and r[0].startswith("Benchmark")]
    cand = {}
    for name, cat, real, cwe in rows:
        if cat not in Q: continue
        t = clean(name, cat)
        if not t or len(t) > MAXLEN or re.search(r"benchmark|vuln|safe", t, re.I): continue
        cand.setdefault((cat, real), []).append((name, cwe, t))
    rng = random.Random(SEED); out = []
    for cat in sorted(Q):
        k = min(PER_CLASS, len(cand.get((cat, "true"), [])), len(cand.get((cat, "false"), [])))
        if k < 5: print("skip", cat, k); continue
        for real in ("true", "false"):
            pool = sorted(cand[(cat, real)]); pick = rng.sample(pool, k)
            for name, cwe, t in pick:
                out.append({"id": "websec-" + name[-5:], "family": cat, "state": t,
                  "question": {"type": "noul", "instructions": Q[cat],
                    "criteria": {"true": "Yes: the code exhibits the weakness described in the question.",
                                 "false": "No: the code does not exhibit the weakness described in the question."}},
                  "labels": ["no", "yes"], "expected": "yes" if real == "true" else "no",
                  "split": "public", "group": None,
                  "provenance": {"exclude_reason": None, "source": "OWASP Benchmark Java v1.2",
                    "url": URL % name, "license": "GPL-2.0", "retrieved": "2026-09-21",
                    "source_id": name, "notes": "category=%s; CWE-%s" % (cat, cwe)}})
    rng.shuffle(out)
    with open(OUT, "w") as f:
        for r in out: f.write(json.dumps(r) + "\n")
    print(len(out))


if __name__ == '__main__':
    main()
