# Detector packs

Files in this folder appear in the Conversation flow's **Detectors → Or start from a set** list (JSON or YAML; see
`format-example.yaml`). Pick one and choose **Use this set** (replace) or **Add it to mine**. The lab allows 20 detectors at a time.

Library detectors (`library: anger`) have measured accuracy on published sets. Everything else is our own wording:
unvalidated, drawn with a dashed outline, and best read as a hint. A detector reused across packs has identical wording
everywhere, so combining packs never duplicates it.

| Pack | File | For | Count |
|---|---|---|---|
| Core 16 | `core16.json` | The default set for any conversation | 16 |
| Meeting · Decisions and follow-through | `meeting.json` | Team and project meetings | 14 |
| Observation · Teaching and training | `observation.json` | Observing a teacher, trainer or facilitator | 12 |
| Interview · Answer quality | `interview.json` | How a candidate's answers are phrased (language only, not a hiring decision) | 12 |
| Scam call · Pressure and payment | `scam-call.json` | The caller in phone and tech-support scams | 12 |
| Scam call · Victim signals | `scam-victim.json` | The person being scammed; pair with the caller pack | 8 |
| Coaching · Feedback conversations | `coaching.json` | Manager 1:1s and mentoring | 13 |
| Board · Governance and oversight | `board.json` | Board and committee meetings | 14 |
| Sales call · Discovery to close | `sales.json` | Sales conversations | 12 |
| Customer service · Frustration to resolution | `customer-service.json` | Support calls | 13 |
| Negotiation · Offers and leverage | `negotiation.json` | Negotiations | 14 |
| Conflict · De-escalation | `conflict.json` | Heated conversations | 14 |
| Operations · Emergency and control room | `operations.json` | Cockpit, control-room and dispatch traffic | 10 |
| Public debate · Claims and dodges | `debate.json` | Interviews and debates | 11 |

Good detectors describe one observable behaviour in the words, phrased "the speaker ...", that a stranger could answer yes or
no from 20 to 40 words. They cannot read tone of voice, intent or truth. Add your own by copying an entry.
