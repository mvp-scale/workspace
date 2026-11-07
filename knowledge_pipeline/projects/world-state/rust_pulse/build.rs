// Any mismatch between this decider and Lean's 160 cases fails the build.
include!("src/decider.rs");
fn main() {
    println!("cargo:rerun-if-changed=vectors.txt");
    println!("cargo:rerun-if-changed=src/decider.rs");
    let t = std::fs::read_to_string("vectors.txt").expect("vectors.txt");
    let mut n = 0;
    for l in t.lines().filter(|l| !l.trim().is_empty()) {
        let v: Vec<u32> = l.split_whitespace().map(|x| x.parse().unwrap()).collect();
        assert_eq!(v.len(), 8, "bad line: {l}");
        let i = In { marker: v[0] as u8, source: v[1] as u8, validated: v[2] != 0, conf: v[3] as u16, agrees: v[4] != 0, thr: v[5] as u16 };
        let o = decide(i);
        if o as u32 != v[6] || harvest(o, i.source) as u32 != v[7] { panic!("MISMATCH with Lean on: {l} (got outcome {o})"); }
        n += 1;
    }
    assert_eq!(n, 160, "expected 160 Lean cases");
}
