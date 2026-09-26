# Detector packs

Files in this folder are the **Presets** dropdown beside the + in Conversation flow's detector bar (JSON or YAML; see
`format-example.yaml`), grouped by each file's `group`. Choosing one replaces the current detectors. The Detectors tab lists every
detector from the other presets that is not in the current one, so you can add them one at a time. Import, download and
"Save as a preset" are in the header ⋯ menu. The lab allows 20 detectors at a time.

Library detectors (`library: anger`) have measured accuracy on published sets. Everything else is our own wording:
unvalidated, drawn with a dashed outline, and best read as a hint. A detector reused across packs has identical wording
everywhere, so combining packs never duplicates it.

| Pack | File | For | Count |
|---|---|---|---|
| General · Core 16 | `core16.json` | The default set for any conversation | 16 |
| Governance & meetings · Team meeting | `meeting.json` | Team and project meetings | 14 |
| Coaching & interviewing · Teaching observation | `observation.json` | Observing a teacher, trainer or facilitator | 12 |
| Coaching & interviewing · Job interview | `interview.json` | How a candidate's answers are phrased (language only, not a hiring decision) | 12 |
| Scams · Scam caller | `scam-call.json` | The caller in phone and tech-support scams | 12 |
| Scams · Scam victim | `scam-victim.json` | The person being scammed; pair with the caller pack | 8 |
| Coaching & interviewing · Coaching 1:1 | `coaching.json` | Manager 1:1s and mentoring | 13 |
| Governance & meetings · Board and committee | `board.json` | Board and committee meetings | 14 |
| Sales & service · Sales call | `sales.json` | Sales conversations | 12 |
| Sales & service · Customer service | `customer-service.json` | Support calls | 13 |
| Sales & service · Negotiation | `negotiation.json` | Negotiations | 14 |
| Conflict & debate · De-escalation | `conflict.json` | Heated conversations | 14 |
| Operations · Emergency and control room | `operations.json` | Cockpit, control-room and dispatch traffic | 10 |
| Conflict & debate · Public debate | `debate.json` | Interviews and debates | 11 |
| YouTube personalities · The Spiffing Brit | `spiffing-brit.json` | An exploit-hunting gaming channel's humour: exploits, "perfectly balanced", devs jabs, tea | 12 |
| YouTube personalities · Randa Rosa | `randa-rosa.json` | A beauty, nails and comedy creator: makeup, long-nail struggles, reveals, plus reported catchphrases (unverified) | 17 |

Good detectors describe one observable behaviour in the words, phrased "the speaker ...", that a stranger could answer yes or
no from 20 to 40 words. They cannot read tone of voice, intent or truth. Add your own by copying an entry.
