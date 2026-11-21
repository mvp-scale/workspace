"""claims v1 (T158, G2): add-only rules on top of spo_chains.extract (nothing in spo_chains.py, facts_lib.py or raw-units.py claims_v0 is changed). One claim = subject, predicate, object plus attributes, with negation, modality and attribution kept.
Rules, each switchable (OPTS) so dev can measure them one at a time:
  parser   the lg parse (en_core_web_lg 3.8.0, MIT, NER excluded: 37 ms for a 680-word article) instead of sm
  expand_o the object is the whole noun phrase subtree (its modifiers and its of/in/over phrases), not just the noun chunk; conjuncts, relative clauses and clauses stay out
  expand_s the same for the subject
  attrs    a prepositional phrase never becomes the object when the verb has a direct object or a measure: it becomes an attribute (time, place, cause or other), 'dropped 10% under Trump' = enrollment | dropped | 10%, cause/other: under Trump
  speaker  a speech verb's speaker is the attribution (said_by), not the subject of the clause's claims; the speech triple keeps the speaker as subject and the clause as object
  passive  a passive with no agent keeps the patient as subject ('the municipality | was renamed | Jones'), not an empty subject
  dedupe   a bare 'X said' with no object is dropped when the same verb has its clause claim
  copula   'X is in/at/from Y' (AUX with a prepositional complement) is a claim
Import: V1.extract(text, nlp) -> [{"s","p","o","attrs","neg","modal","attrib","passive","rule"}].
Since T172 (owner yes L2870) the code lives in the importable module claims_v1.py; this kebab-case file stays as a loader so the scripts that load it by path (claims-round.py, claims-causes.py, direction_v1.py and others) keep working unchanged: every public and private name of claims_v1.py is re-exported here, and OPTS is the same dict object."""
import importlib.util, pathlib
_sp = importlib.util.spec_from_file_location("claims_v1_impl", str(pathlib.Path(__file__).resolve().parent / "claims_v1.py")); _m = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_m)
globals().update({k: v for k, v in vars(_m).items() if not k.startswith("__")})
