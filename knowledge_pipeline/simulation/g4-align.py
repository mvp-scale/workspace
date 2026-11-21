"""G4/G5 v1, unmeasured. Knowledge alignment (playbook sections 1, 2, 8, 18) on top of raw-units: observation -> entity identity -> assertion -> vertical (IPTC) and horizontal links.
Add-only: loaded by raw-units.py via importlib (kebab-case file name); nothing in live_trace / the decider / lean is edited. CPU only, no hosted calls.
One store (Store) holds everything; each edge carries `via` (its relation source) and evidence spans, so the three views on the page (flat table, relation map, hierarchical graph) are derived from the same data.
  Observation: every kept unit stays an observation tied to its span (rec["units"], untouched). Bare numbers and dates are never graph nodes: they attach to assertions as attributes.
  Entity identity: in-article alias clusters (surname, acronym incl. article country, head-noun containment, pronoun-resolved mentions, demonyms and places -> iso:XX), across articles an exact name/alias match in the same type (same name in another type = "unsure" flag).
  Assertion key: (subject identity, predicate lemma, object identity or normalised object head). Evidence is counted per independent publisher; journal copies/republished items do not count.
  Vertical: iptc_path + how in {exact, wordnet, sentence, article-topic}; places also get a geo path country -> region.
  Horizontal via: hierarchy, assertion, attribution, causal cue v0, co-occurrence, temporal, spatial, change, capability, similar v0 (unmeasured), story.
Since T172 (owner yes L2870) the code lives in the importable module projects/world-state/g4_align.py (entity types from Few-NERD, IPTC placement, contradictions, durable store); this kebab-case file stays as a loader so raw-units.py consumers, check-contradictions.py and check-durable.py that load it by path keep working: every name of g4_align.py is re-exported here (Store, align, contradict_edges, contradiction_counts, joins_of, to_node, ...)."""
import importlib.util, pathlib
_sp = importlib.util.spec_from_file_location("g4_align_impl", str(pathlib.Path(__file__).resolve().parent.parent / "projects" / "world-state" / "g4_align.py")); _m = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_m)
globals().update({k: v for k, v in vars(_m).items() if not k.startswith("__")})
