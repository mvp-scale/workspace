# Demo audio clips

Four two-minute clips in `data/audio/` (git-ignored: audio and transcripts of third-party recordings never go in the repo).
They appear in Conversation flow under **Live audio, Library file**. All 18 detectors are on by default.
Sources are kept in `data/audio-src/` (git-ignored) and can be re-cut with `ffmpeg -ss START -t LENGTH -i SRC -vn -c:a aac -b:a 96k OUT.m4a`.

| Clip (file in `data/audio/`) | What it is | Source | Cut | Licence |
|---|---|---|---|---|
| `apollo13-houston-weve-had-a-problem.m4a` | Real crisis conversation: the crew reports the problem, Houston answers | YouTube `VC7bnkMJ-T0` (NASA air-to-ground recording, 34:52) | 18:10, 2:00 | NASA, public domain |
| `jfk-we-choose-to-go-to-the-moon.m4a` | Famous single-voice speech, persuasion | YouTube `WZyRbnpGyzQ` (NASA Video, Rice University 1962) | 8:40, 2:00 | US government work, public domain |
| `reagan-challenger-address.m4a` | Famous single-voice address, grief and empathy | YouTube `DqilE4AAa-M` (US National Archives, 1986) | 0:00, 2:00 | US government work, public domain |
| `a-few-good-men-you-cant-handle-the-truth.m4a` | A conversation with an obvious liar: cross-examination, anger, threat, deflection | YouTube `9FnO3igOkOk` (Movieclips, 1992 film) | 0:03, 2:05 | Copyrighted film: local internal demo only, do not redistribute |

Tried and rejected: the 1972 Nixon "smoking gun" tape (public domain, but the recording is too poor for the speech model: 41 words in 6 minutes).

## What lights up (SemIf, local, all 18 detectors, alert level 80%; one run each, a rough guide, not accuracy)

| Clip | Words | Voices | Detectors flagged | Strongest |
|---|---|---|---|---|
| Apollo 13 | 93 | 2 | 6 | Uncertainty, Fear, Deflection, Commitment |
| JFK Moon | 253 | 1 | 5 | Question, Commitment, Agreement, Persuasive move, Fear |
| Reagan Challenger | 307 | 1 | 3 | Empathy, Agreement, Politeness |
| A Few Good Men | 332 | 4 | 13 | Anger, Disagreement, Threat, Manipulation, Sarcasm |

Notes: NASA radio audio is noisy and transcribes thinly (93 words in two minutes), so Apollo has the fewest opportunities. Other models will score differently.
