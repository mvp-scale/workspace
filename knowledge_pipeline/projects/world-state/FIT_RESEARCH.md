# Field fit and label consensus: what the research supports (2026-11-02)

Method: web search, one query per check. Everything below is from search summaries (secondary), not full text.
"Read" column = whether the source itself was opened. None were. Marked VERIFY = open the paper before relying on it.

| Check | Source | What it says | Read |
|---|---|---|---|
| Alpha thresholds | Krippendorff, Content Analysis: An Introduction to Its Methodology, Sage 2004, p.241 | alpha >= 0.800 reliable; 0.667 to 0.800 tentative conclusions only; < 0.667 discard. Others call these guides, not fixed cutoffs. | No (VERIFY p.241) |
| Skewed answers break agreement scores | Feinstein & Cicchetti 1990, J Clin Epidemiol 43:543-549 | High raw agreement can give low kappa when one answer dominates ("prevalence paradox"). | No |
| Fix: agreement per answer | Cicchetti & Feinstein 1990, J Clin Epidemiol 43:551-558 | Report separate positive and negative agreement (p_pos, p_neg, like sensitivity and specificity) beside kappa. | No |
| Sample size for per-answer agreement | Graham & Bull 1998 (CIs for positive/negative agreement) | Asymptotic intervals performed adequately at n >= 200. | No (VERIFY) |
| Pilot then fix the guideline | Pustejovsky & Stubbs, MAMA cycle, via arXiv 1602.05753 | Alternate modelling and pilot annotation, rewrite guidelines before the full corpus. | No |
| Disagreement can be signal | Plank 2022, EMNLP main.731 (arXiv 2211.02570) | Human label variation is not always noise; separate real variation from error. Gives no threshold. | No |
| Label error finding | Northcutt, Jiang, Chuang 2021, JAIR 70:1373-1411 (arXiv 1911.00068) | Finds likely label errors from model probabilities. Not a field-fit test. cleanlab is AGPL-3.0 (L215). | No |
| Labelling-source statistics | Snorkel LFAnalysis docs (coverage, overlap, conflict) | Describes labelling functions, not fields. | No |

NOT FOUND in this search: any published bar for minimum real cases, contested share, same-voter consistency,
cross-family agreement, or a named field-selection ("fit") test. Those bars in fitness_screen.py are ours.

## Consensus side (5 more searches, same method: summaries only, no source opened)

| Topic | Source | What it says | Read |
|---|---|---|---|
| Aggregating labellers beyond majority vote | Dawid & Skene 1979, Applied Statistics 28(1):20-28 | EM estimate of each labeller's error rates and the likeliest true class; weights labellers by reliability. No comparison to majority vote found. | No |
| Same, with item difficulty | Hovy et al. 2013, MACE, NAACL N13-1132 | Item-response model of whom to trust; software README: higher entropy of an item's answers = harder item. | No |
| Use different model families | Verga et al. 2024, Replacing Judges with Juries, arXiv 2404.18796 | Panel of 3 model families (Command R, Haiku, GPT-3.5) beat one large judge, less self-preference bias, 7x cheaper. Max voting. About judging generations, not classification labels. | No |
| Run-to-run stability is not correctness | arXiv 2609.15194 (self-consistency 81 to 89 percent over 3 runs); arXiv 2601.02370 (kappa 0.026 at 58.7 percent raw agreement; use several models, report cross-model reliability) | Consistency and agreement are diagnostics, not truth. | No |
| Dropping contested items vs soft labels | Wu et al. 2023 EMNLP Findings 355; Wright State thesis; HateXplain ICML 2026 paper | Soft labels beat majority vote; training only on unanimous items sits between; aggregation hides real disagreement (about 22 points lower accuracy on disagreement posts). | No |

NOT FOUND: a published bar for the majority threshold (3 of 4), the number of voters needed, or a cross-family agreement bar.
Consequence for us: consensus_rescore.py drops split items, which are the hard ones, so its scores overstate.

## Parallel research 2026-11-03 (5 searches, summaries only, no paper opened)

| Topic | Source | What it says |
|---|---|---|
| Minimum cases per class | arXiv 2402.12819 (EMNLP 2025), 7 models x 8 tasks | Break-even labels depend on the task: up to about 100 for multi-class, up to about 5,000 for binary; accounting for variance raises the need by roughly 100 to 200 percent. Practitioner pieces say 8 to 100 per class. Our F2 bar of 30 is inside the range but not a standard; plot a learning curve per field. |
| Route contested items to more labellers | Baumler et al. 2023, DAAL, Findings of ACL 2023 (658) | Pick examples where model uncertainty and annotator disagreement diverge; uncertainty-only active learning underperforms passive on high-disagreement tasks; DAAL needs at least 24 percent fewer annotations. |
| Keep disagreement as signal | ACTOR (EMNLP 2023) | Annotator-specific heads; matches full training with about 70 percent less annotation. |
| Self-training with LLM pseudo-labels | LLKD, Findings of NAACL 2025 (arXiv 2411.08028); FlexMatch | Keep only samples passing a teacher-confidence and a student-uncertainty threshold; per-class thresholds help rare classes. No classic Noisy Student paper surfaced. |
| Independent alpha implementation | PyPI | `krippendorff` is GPL-3.0-or-later (unverified on PyPI); `krippendorff-aleph-alpha` and `quica` list MIT. Numerical agreement with ours not verified. Installing needs the owner's yes. |
| Kaggle quota | course and blog pages | About 30 GPU hours a week, 12-hour sessions, T4 x2 or P100; figures may be dated. Our own cap (D12) is 3 GPU-hours total and 4 a week. |

## Pre-tagging rare answers: sources and methods (2026-11-03, 3 searches, summaries only)

| Topic | Source | What it says |
|---|---|---|
| Opinion-vs-news labelled data | RTBF-InfOpinion (French, 10,000 articles, on request, licence not seen); Webis-Editorials-16 (300, argument-level); Webis-Editorial-Quality-18 (1,000, licence not seen); NewSoMe (LDC, not free); Proppy (propaganda by outlet); MN-DS (topics only, Creative Commons) | No openly licensed corpus that separates news, opinion, editorial and analysis was found. Check licences on the official pages before any use. |
| Pre-tagged events at scale | GDELT GKG (2,500+ themes, about 2,200 from the World Bank taxonomy) and CAMEO (20 top-level event codes incl. protest, kill, arrest) | Candidate weak labels for conditions (protest, conflict, disaster). Terms of use NOT confirmed in the results; coverage of our pool and the URL join untested. |
| Rare classes with weak supervision | Osprey (Snorkel, imbalanced extraction); ARS2 (arXiv 2210.03092: weak labels can amplify imbalance; class-wise ranking sampling); STENCIL (ICML 2024: weakly labelled rare exemplars then annotated, 17 to 40 percent rare-class F1 gain); Darwin (random sample has few positives, write rules); REGAL (active learning over labelling functions) | Funnel pattern: cheap labelling functions rank candidates, experts confirm. Unbiased recall estimation from such samples was NOT found in the search. |

## Modern open-weight voters from other makers (2026-11-03, read-only agent; live Hugging Face and vLLM pages; I spot-checked Gemma 4 only)

| Pick | Maker, size | Licence (as tagged, LICENSE files NOT read) | Fit and notes |
|---|---|---|---|
| Gemma 4 31B-it (also 26B-A4B MoE) | Google, 30.7B dense | Apache 2.0 on mirrors; one third-party page cites Google's Gemma License for a QAT variant: unresolved | about 17 GB at 4-bit (agent's estimate); vLLM serve; thinking OFF by default, enable_thinking or reasoning_effort turns it on; MMLU-Pro 85.2, GPQA 84.3 |
| Granite 4.2-30b (also 8b, 3b) | IBM, 29B, released 2026-08-25 | Apache 2.0 | fp8 variant about 29 to 30 GB (tight on 32 GB); enable_thinking=False gives direct answers; IFBench 77.17 |
| Ministral-3-14B-Instruct-2512 | Mistral, 13.5B | Apache 2.0 | FP8 on 24 GB per card, 4-bit should fit 16 GB; no thinking mode; vLLM 0.12+ |
| gpt-oss-20b | OpenAI, 21B MoE | Apache 2.0 | MXFP4 within 16 GB per card; reasoning low/medium/high, no off switch stated; T4 kernel support for MXFP4 not verified |
| GLM-4.7-Flash | Zhipu, 30B-A3B MoE | MIT | BF16 about 60 GB so needs a 4-bit quant (unverified); vLLM nightly; no thinking switch on the card |
Excluded: NVIDIA Nemotron-3-Nano-30B-A3B (custom Nemotron Open Model License, outside the free/open rule); Mistral Small 4 (119B) and Large 4 (1T) too big. NOT verified by anyone: classification benchmarks (none found), JSON-schema constrained output per model, actual 4-bit repos, leaderboards.

## Outside anchors and pre-tag sources, checked while the Qwen test ran (2026-11-03, 2 searches, summaries only)

| Source | What it gives | Licence and terms | Caveats |
|---|---|---|---|
| MN-DS (Petukhova and Fachada 2023, MDPI Data 8(5):74, arXiv 2212.12061) | 10,917 news articles (all 2019, from NELA-GT-2019) hand-labelled by the authors with the IPTC Media Topic taxonomy: 17 first-level and 109 second-level categories, about 100 articles per second-level category, one category per article | CC-BY 4.0 per a MaRDI mirror page; original repository licence file not seen | balanced by design, not the natural mix; our 47 topic ids need a mapping to IPTC; full articles, we use headline plus description. A real human-labelled anchor for TOPIC. |
| GDELT (GKG themes, CAMEO events) | machine-tagged events and themes for news, free pre-tags for conditions | official about page: unlimited, unrestricted use incl. commercial, redistribution allowed, citation of GDELT and a link required (via a search summary; GKG and Events not licensed separately; the terms page itself is the authority) | machine labels, not human gold; coverage of our pool and any URL join untested |
