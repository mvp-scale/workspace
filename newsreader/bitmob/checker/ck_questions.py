"""Question texts for the checker: attribute wordings (classify.QS a|..), the 4 gate questions, and the expected-impact questions (shortened: the fixed 'Suppose ... Answer yes only if' boilerplate is dropped)."""
import os, sys
os.environ.setdefault("WE_RULES", "rules_v2"); os.environ.setdefault("WORLD_GPU", "0")
sys.path[:0] = ["/workspace/probes/world-engine", "/workspace/probes/persona", "/workspace/demo"]
import classify as C
GATE_Q = ["g|happened", "g|announced", "g|opinion", "x|recent"]
def cond_q(d, dr, i, w): return C.QS[f"a|{d}|{dr}|{i}|{w}"]
def gate_q(k): return C.QS[k]
def exp_q(d, u): return f"If the main development in this story plays out as described, is it likely that {C.PHRASES[d][u]}?"
