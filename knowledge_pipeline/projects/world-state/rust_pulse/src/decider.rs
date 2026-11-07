// The decider: the Rust copy of lean/Decide.lean. Codes are the Lean codes.
// build.rs replays vectors.txt (Lean's own cases) against this file; any mismatch fails the build.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct In { pub marker: u8, pub source: u8, pub validated: bool, pub conf: u16, pub thr: u16, pub agrees: bool }

#[inline]
pub fn decide(i: In) -> u8 {
    if i.marker == 0 { 0 }
    else if i.marker == 1 { 1 }
    else if i.source == 0 && !i.validated { 2 }
    else if i.source == 1 && i.conf < i.thr { 3 }
    else if i.source == 1 && !i.agrees { 4 }
    else if i.marker == 2 { 5 } else { 6 }
}

#[inline]
pub fn harvest(outcome: u8, source: u8) -> u8 {
    match outcome {
        0 => 3,
        1 => 4,
        2 | 3 | 4 => 1,
        5 => 0,
        _ => if source == 0 { 2 } else { 0 },
    }
}
