"""The decider: the one Python source of the rules in lean/Decide.lean. Codes are the Lean codes. check_against_lean() replays Lean's own cases."""
from enum import IntEnum
class Marker(IntEnum): NOT_ADMISSIBLE = 0; TOO_FEW_ITEMS = 1; BELOW_BAR = 2; MEETS = 3
class Source(IntEnum): STATED_FACT = 0; TRAINED_HEAD = 1
class Outcome(IntEnum): ABSTAIN_NOT_ADMITTED = 0; ABSTAIN_TOO_FEW = 1; ABSTAIN_NOT_VALIDATED = 2; ABSTAIN_LOW_CONFIDENCE = 3; ABSTAIN_GATES_DISAGREE = 4; ANSWER_PROVISIONAL = 5; ANSWER = 6
class Harvest(IntEnum): DISCARD = 0; LABEL_QUEUE = 1; TRAINING_LABEL = 2; NEEDS_JUDGE = 3; NEEDS_MORE_ITEMS = 4
def decide(marker, source, validated, conf_permille, thr_permille, gates_agree):
    if marker == Marker.NOT_ADMISSIBLE: return Outcome.ABSTAIN_NOT_ADMITTED
    if marker == Marker.TOO_FEW_ITEMS: return Outcome.ABSTAIN_TOO_FEW
    if source == Source.STATED_FACT and not validated: return Outcome.ABSTAIN_NOT_VALIDATED
    if source == Source.TRAINED_HEAD and conf_permille < thr_permille: return Outcome.ABSTAIN_LOW_CONFIDENCE
    if source == Source.TRAINED_HEAD and not gates_agree: return Outcome.ABSTAIN_GATES_DISAGREE
    return Outcome.ANSWER_PROVISIONAL if marker == Marker.BELOW_BAR else Outcome.ANSWER
def harvest(outcome, source):
    if outcome == Outcome.ABSTAIN_NOT_ADMITTED: return Harvest.NEEDS_JUDGE
    if outcome == Outcome.ABSTAIN_TOO_FEW: return Harvest.NEEDS_MORE_ITEMS
    if outcome in (Outcome.ABSTAIN_NOT_VALIDATED, Outcome.ABSTAIN_LOW_CONFIDENCE, Outcome.ABSTAIN_GATES_DISAGREE): return Harvest.LABEL_QUEUE
    if outcome == Outcome.ANSWER_PROVISIONAL: return Harvest.DISCARD
    return Harvest.TRAINING_LABEL if source == Source.STATED_FACT else Harvest.DISCARD
def check_against_lean(path="rust_decider/vectors.txt"):
    n = 0
    for l in open(path):
        m, s, v, c, a, t, o, h = map(int, l.split()); d = decide(m, s, bool(v), c, t, bool(a)); assert d == o and harvest(d, s) == h, l; n += 1
    return n
