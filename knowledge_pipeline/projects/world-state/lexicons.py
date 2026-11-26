"""lexicons: domain word lists as data (playbook 00.1 round E, owner D3 via D55, ledger L3011). The words live in lexicons.json (class -> words | map | groups | pairs, with provenance); code names a class, never a word.
KP_LEXICONS=off loads every class empty, so the general path (polarity, amount, date, direction) runs alone: simulation/check-lexicons.py and the lexicons-off gate runs use it. An unknown class name raises KeyError in both modes."""
import os, json
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lexicons.json")
OFF = os.environ.get("KP_LEXICONS", "on").strip().lower() == "off"
_D = {}
def _cls(name):
    if not _D: _D.update(json.load(open(PATH))["classes"])
    return _D[name]
def state(): return "off" if OFF else "on"
def words(name):
    """-> set of words (insertion order = file order)"""
    c = _cls(name); return set() if OFF else set(c["words"])
def seq(name):
    """-> list of words in file order (regex alternations)"""
    c = _cls(name); return [] if OFF else list(c["words"])
def table(name):
    """-> {word: value}; list values become tuples"""
    c = _cls(name); return {} if OFF else {k: tuple(v) if isinstance(v, list) else v for k, v in c["map"].items()}
def groups(name):
    """-> [(set, set)] opposite word groups"""
    c = _cls(name); return [] if OFF else [(set(a), set(b)) for a, b in c["groups"]]
def pairs(name):
    """-> {(a, b): kind} for 3-item pairs, else {(a, b)} for 2-item pairs"""
    c = _cls(name)
    if OFF: return {} if any(len(p) == 3 for p in c["pairs"]) else set()
    return {(p[0], p[1]): p[2] for p in c["pairs"]} if any(len(p) == 3 for p in c["pairs"]) else {tuple(p) for p in c["pairs"]}
