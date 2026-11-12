"""The topic map (specs/topic_to_iptc_v1.json) uses MN-DS category names; the IPTC Media Topics top level uses two different labels. AL turns a map category into the IPTC label so the reader constraint can match it. NO_ALIAS=1 gives the pre-2026-11-10 behaviour (ledger T93) to reproduce old results."""
import os
AL = {} if os.environ.get("NO_ALIAS") else {"politics": "politics and government", "religion and belief": "religion"}
