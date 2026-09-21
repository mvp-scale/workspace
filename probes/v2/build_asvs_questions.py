#!/usr/bin/env python3
"""Build asvs_questions.json and cwe_top25.json from downloaded published sources (deterministic, no sampling).
Sources: /workspace/data/sources/asvs/repo (OWASP/ASVS 4.0.3 en CSV), top25.html (MITRE CWE Top 25 2025), cwe/cwec_v4.20.xml."""
import csv, json, re, html, collections
import xml.etree.ElementTree as ET
S = '/workspace/data/sources/asvs/'
O = '/workspace/probes/v2/'
rows = list(csv.DictReader(open(S + 'repo/4.0/docs_en/OWASP Application Security Verification Standard 4.0.3-en.csv', encoding='utf-8')))
out, deleted = [], 0
for r in rows:
    t = r['req_description'].strip()
    if t.startswith('[DELETED'):
        deleted += 1; continue
    out.append({"id": r['req_id'], "chapter": f"{r['chapter_id']} {r['chapter_name']}",
                "section": f"{r['section_id']} {r['section_name']}",
                "level1": r['level1'].strip() != '', "level2": r['level2'].strip() != '',
                "level3": r['level3'].strip() != '', "cwe": r['cwe'].strip(), "text": t})
json.dump(out, open(O + 'asvs_questions.json', 'w'), indent=1, ensure_ascii=False)
ch = collections.Counter(x['chapter'] for x in out)
v = sum(x['text'].startswith('Verify') for x in out)
print(len(out), 'deleted skipped', deleted, 'Verify-phrased', v)
for k, n in ch.items(): print(k, n)

# CWE Top 25
h = open(S + 'top25.html', encoding='utf-8').read()
ranks = re.findall(r'<b>(\d+)</b></td>\s*<td[^>]*><a[^>]*>CWE-(\d+)</a></td>\s*<td>(.*?)</td>', h, re.S)
ns = {'c': 'http://cwe.mitre.org/cwe-7'}
root = ET.parse(S + 'cwe/cwec_v4.20.xml').getroot()
desc = {w.get('ID'): ''.join(w.find('c:Description', ns).itertext()).strip() for w in root.iter('{http://cwe.mitre.org/cwe-7}Weakness')}
top = []
for rk, cid, name in ranks:
    top.append({"rank": int(rk), "id": f"CWE-{cid}", "name": html.unescape(name).strip(),
                "description": re.sub(r'\s+', ' ', desc[cid])})
json.dump(top, open(O + 'cwe_top25.json', 'w'), indent=1, ensure_ascii=False)
print(len(top))
