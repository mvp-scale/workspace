mod decider;
use decider::*;
use std::time::Instant;
fn main() {
    let n = 50_000_000u32; let mut acc = 0u64; let t = Instant::now();
    for k in 0..n {
        let i = In { marker: (k & 3) as u8, source: ((k >> 2) & 1) as u8, validated: (k >> 3) & 1 == 1, conf: (k % 1000) as u16, thr: 700, agrees: (k >> 4) & 1 == 1 };
        let o = decide(std::hint::black_box(i)); acc += (o + harvest(o, i.source)) as u64;
    }
    let ns = t.elapsed().as_nanos() as f64 / n as f64;
    println!("decide+harvest: {ns:.2} ns per call ({acc})");
}
