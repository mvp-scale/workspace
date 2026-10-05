# World engine ontology: draft v0 (2026-10-05)

Rule: closed lists. A topic (AI, quantum, a fertiliser) is an instance, never a class. An instance is mapped to classes by the yes/no test on each entry. A new class needs a written reason and a standard it maps to. One backbone per list. Everything marked EXTENSION is our own addition and must stay labelled.

Evidence tags: **[opened]** a page was read, **[snippet]** a search snippet only (the OECD, SEEA and World Bank pages blocked the reader), **[memory]** unverified. Nothing here is validated against data; it is a naming and grouping exercise.

## 1. State classes (what is true now)

Backbone: OECD *How's Life?* current well-being dimensions (11) [snippet] plus labelled extensions. No single published framework covered our 15 dials; four had no home.

| # | Class | Test: does this change... | Our dials | Source |
|---|---|---|---|---|
| 1 | Income and wealth | incomes, wealth, financial conditions | financial conditions, prices (partial) | OECD |
| 2 | Work and job quality | jobs, job security, conditions | job security | OECD |
| 3 | Housing | housing cost or access | housing cost | OECD |
| 4 | Health | health or health risk | health risk | OECD |
| 5 | Knowledge and skills | education, skills, know-how | (tech pace, weak fit) | OECD |
| 6 | Environmental quality | pollution, climate, nature | none | OECD |
| 7 | Work-life balance | time and strain | none | OECD |
| 8 | Social connections | trust between people, cohesion; **division is the negative pole** | community, social division | OECD; division mapping is OUR judgement |
| 9 | Civic engagement and governance | trust in institutions, participation | trust in institutions | OECD |
| 10 | Safety | personal safety, crime | crime | OECD |
| 11 | Subjective well-being | outlook, life satisfaction | optimism | OECD |
| 12 | Energy and prices | fuel, energy, cost of living, inflation | energy and fuel, prices | EXTENSION |
| 13 | Conflict | war, terror, organised violence | war and terror | EXTENSION |
| 14 | Technology, information and change | pace of change, disruption, information flow | tech pace, disruption, news overload | EXTENSION |

Fourteen, not ten. Option: merge 1+2 and 6+7 and 11 into neighbours to reach ten, at the cost of departing from the backbone. Your call.

**Values list (separate, attitudes people hold):** Schwartz's 10 basic values in four groups [opened: Wikipedia]. Openness to change: self-direction, stimulation. Self-enhancement: hedonism, achievement, power. Conservation: security, conformity, tradition. Self-transcendence: benevolence, universalism. Built as a circle with conflicts, which suits a numeric engine. It does not state risk tolerance directly; infer it from the stimulation-versus-security axis.

## 2. Decision classes (what actors choose)

**Institutions** (world leaders, governments, regulators, companies). Backbone: CAMEO's 20 root event codes [opened: 16 of 20 in GDELT Cloud docs; 14, 18, 19, 20 from memory], regrouped by us into 10. Keep the CAMEO code as a sub-label so GDELT can feed it. Polarity from the Goldstein scale (-10 to +10) [opened].

| # | Class (CAMEO roots) | Test |
|---|---|---|
| 1 | Speak or signal (01, 02) | states a position or appeal without committing resources |
| 2 | Signal cooperation (03, 04, 05) | offers talks, consults, formal diplomacy |
| 3 | Provide or fund (06, 07) | gives money, goods, aid, joint activity |
| 4 | Concede or comply (08) | yields, relaxes, accepts a demand |
| 5 | Investigate (09) | opens an inquiry |
| 6 | Demand or condemn (10, 11, 12) | demands, accuses, refuses |
| 7 | Threaten or posture (13, 15) | threatens or shows force |
| 8 | Withdraw or sanction (16, 17) | cuts ties, sanctions, restricts, withholds |
| 9 | Use force (18, 19, 20) | uses physical violence |
| 10 | Mobilise or protest (14, ACLED protests and riots) | a group acts publicly against an authority |
| 11 | Regulate or permit | sets or relaxes rules (EXTENSION: CAMEO has no domestic rule-making; the Altman case needs it) |
| 12 | Invest, launch or adopt | an organisation commits capital or adopts something (EXTENSION) |

**People.** No standard taxonomy of what people decide exists. Ours: spend, buy something new, subscribe or commit, travel, change work, move home, switch provider, share or engage publicly (loosely aligned with the American Time Use Survey categories [opened]) plus two additions: back or oppose (trust or distrust), comply or resist. Not covered: health, saving and borrowing, voting, volunteering, donating. All person-level classes are OUR scheme.

## 3. Resource classes (what decisions draw on or build)

Backbone: the Forum for the Future five capitals (natural, human, social, manufactured, financial) [opened], with natural split by UN SEEA-style classes [snippet; SEEA classes from memory], plus three EXTENSIONS that no framework covers.

| # | Class | Test: does this draw on or change... | Source |
|---|---|---|---|
| 1 | Water | water supply, access, quality | SEEA |
| 2 | Land and food | farmland, soil, food, forests, fish | SEEA |
| 3 | Energy and minerals | fuels, power, metals (a flow more than a stock) | SEEA |
| 4 | Produced (infrastructure and compute) | machines, buildings, networks, data centres, compute | Forum "manufactured"; compute folded in by us |
| 5 | Financial | money, credit, asset prices | Forum |
| 6 | Human | health, skills, labour, motivation | Forum |
| 7 | Social | trust between people, networks, institutions | Forum, OECD |
| 8 | Knowledge and information | shared facts, know-how, data | EXTENSION |
| 9 | Attention | limited audience time and focus (Simon 1971 argument [snippet]) | EXTENSION |
| 10 | Legitimacy | acceptance of an authority's right to act (nearest measure: World Bank governance indicators [snippet]) | EXTENSION |

Caveats: social trust (7) and legitimacy (10) overlap and need separate tests; attention and knowledge are not ordinary rival goods (information can be copied).

## 4. The grids (cells are guesses until fed)

State x state, decision x state (with pair terms), resource x resource, decision x resource. Sourced couplings found: water, energy and food affect each other [snippet: SEI nexus]; information consumes attention [snippet]. Everything else is unsourced and must be labelled so.

## 5. Methods since 1966 (what to borrow)

Adopt: (1) sensitivity analysis and history matching on our own matrices, treating every cell as a range (SALib; Morris screening first) [snippet]; (2) system dynamics conventions for stocks, delays and loops, with PySD as a reference to test against [opened: docs], and a loop-gain check where gain of 1 or more fails the build; (3) cross-impact balance as a static consistency check on signs and strengths [opened: Stuttgart CIB-Lab], and LLM extraction of edges only as a drafting aid, every edge human-approved and keeping its quote (reviews call LLMs "imperfect expert systems" [opened: survey]).
Do not adopt: a neural simulator as the engine (hurts explanation, needs a trusted simulator to learn from); GDELT forecasting as the model (use GDELT as a feed and validation source).
Skip for now: Bayesian networks, structural causal models (do not fit delayed loops with thresholds); revisit at person level.
Not verified: licences for SALib and ScenarioWizard, release dates for PySD, pgmpy and DoWhy.

## 6. Open decisions

1. State list: 14 with extensions, or merged to 10?
2. Institutional decisions: accept 12 (10 regrouped from CAMEO plus 2 extensions)?
3. Resources: accept the three extensions (knowledge, attention, legitimacy)?
4. Values: Schwartz's 10 as the attitude lens?
5. Grid size follows the lists; the "10 by 10" becomes 14x14, 12x14, 10x10 and 12x10.
