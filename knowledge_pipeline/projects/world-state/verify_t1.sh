#!/bin/bash
# Re-checks task T1 (P0 Freeze the spec, cards and targets) from the files, not from the ledger. Run:  bash verify_t1.sh
cd "$(dirname "$0")"; fail=0
echo "STEP 1  Done means: the files that must not change have a recorded fingerprint (sha256), and today's file still matches it."
chk() { got=$(sha256sum "$2" | cut -c1-16); if [ "$got" = "$3" ]; then echo "   PASS  $1  $got"; else echo "   FAIL  $1  expected $3 got $got"; fail=1; fi; }
chk "spec v1                " specs/world_state_v1.json                      6016f11f3326b3bc
chk "frozen test (pilot300)  " data/pilot300.jsonl                           5005e4a0634f85e5
chk "Clef test labels        " /workspace/data/clef-labels/test_fast300.jsonl 670ee731164c3678
chk "frozen guideline Haiku  " specs/world_state_v2_frozen_haiku.json         92a30b489b0ef637
chk "frozen guideline Sonnet " specs/world_state_v2_frozen_sonnet.json        9817a2ef2da22e8a
chk "gold answer key (prov.) " gold/q50_key_provisional.jsonl                 98f9d7aff3697186
echo "STEP 2  Done means: every card T01..T11 passes the kit's card checker, which requires a spend cap, a GPU-hour cap and a stop rule."
for i in 01 02 03 04 05 06 07 08 09 10 11; do
  out=$(node ../../agentic/scripts/check_card.mjs cards/T$i.json 2>&1 | tail -1); stop=$(python3 -c "import json;d=json.load(open('cards/T$i.json'));print('stop' in d and bool(d['stop']))")
  if echo "$out" | grep -q "^PASS" && [ "$stop" = "True" ]; then echo "   PASS  T$i  ($(echo $out | cut -c1-60))"; else echo "   FAIL  T$i  $out stop-rule=$stop"; fail=1; fi
done
echo "STEP 3  Done means: the owner has written 'signed' (or changes) against these targets: under 50 ms per item on one CPU thread; \$61.50 planned of \$190; pass line = 0.8 x agreement; card caps as listed."
if (cd ../../.ledger && node cp.mjs brief T1 2>&1 | grep -q "3\. Owner signs targets  done"); then echo "   PASS  signed"; else echo "   WAITING  owner sign-off not recorded"; fi
[ $fail = 0 ] && echo "RESULT  steps 1 and 2 verified from the files" || echo "RESULT  FAILED, see FAIL lines"
