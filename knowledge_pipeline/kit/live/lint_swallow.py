"""Finds a trailing comment that swallowed code: a line whose '#' comment contains '; <something that parses as a Python statement>' (a ';' chain that was cut by an added comment). Three times on 2026-11-10 an added comment hid the rest of a ';'-joined line (T93 h2 and inv, T98 makedirs, T97 CAP and numpy import); a smoke test did not always show it.
    python3 lint_swallow.py file.py [file.py ...]   exit 0 = clean, 1 = findings printed"""
import ast, io, sys, tokenize
bad = 0
for f in sys.argv[1:]:
    try: src = open(f).read()
    except Exception: continue
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type != tokenize.COMMENT or ";" not in tok.string: continue
        for seg in tok.string.lstrip("# ").split(";")[1:]:
            seg = seg.strip()
            if len(seg) < 4: continue
            try: ast.parse(seg)
            except SyntaxError: continue
            if "=" in seg or "(" in seg or seg.startswith(("import ", "from ")): print(f"{f}:{tok.start[0]}: comment hides code: ; {seg[:70]}"); bad = 1; break
sys.exit(bad)
