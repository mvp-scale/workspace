# Persona profile standard (draft 0, 2026-10-02)

Working document for the Persona lab. Purpose: agree what a persona IS before building more. Nothing here is validated against real people. Every element carries a status tag:

- **[ours]** invented by us, no outside standard found
- **[checked]** read in a primary or library source this session (Context7 docs of PyBLP, Mesa, implicit)
- **[agent, partial]** reported by a research agent this session, source seen only in part
- **[memory]** from general knowledge, NOT verified here; check before relying on it
- **[built]** exists in `personas.py` today

## 1. The idea in one paragraph

A persona is not a story. It is a **composite of standard factors**, each a number on a fixed scale, generated in bulk from a seed. Uniqueness comes from the combination, not from a bespoke description. Anything a persona is shown (an article, a product, an ad, a call) is first read by the classifier into a **neutral stimulus profile** on a shared set of dimensions. The persona's response is that profile, filtered through the persona's factors, shifted by a **world state** that nudges many people's numbers at once. The text profile (backstory) is a rendering of the numbers for display and for the model to read; it is not the source of truth.

```
stimulus profile s   (any medium, classified once, neutral)
persona factors  p   (static traits + slow-moving states)
world state      w   (3 to 6 numbers, shared by everyone)

state_i(w)   = states_i + S_i * w            # world moves states, not traits
utility_ij   = s_j . ( B * [traits_i ; state_i(w)] )     # persona acts as a modifier on the neutral profile
response_ij  = softmax / logit(utility_ij)   # try, like, buy, share, ...
```

This is the random-coefficients choice form: taste = common mean + matrix times person covariates + unobserved variation, beta_i ~ N(beta + Pi * d_i, Sigma Sigma') [checked, PyBLP docs]. We use it without the estimation machinery, which needs real choice data we do not have.

## 2. Persona layers

Traits are fixed per person. States can be moved by the world. Cohorts are not stored (section 3).

| Layer | What | Scale | Dims | Source of the numbers | Status |
|---|---|---|---|---|---|
| L0 Demographics | age, sex, region, area type, income band, household, education, work | categorical / ordinal | ~8 | census-style synthesis: fit a joint distribution to published marginals (iterative proportional fitting), then sample | method [agent, partial] (Beckman et al. 1996 TRANSIMS; SPEW); ours today is hand-weighted lists [built] |
| L1 Personality | Big Five | z-score | 5 | conditional on L0 from public norm data | [memory] instrument details unverified; not built |
| L2 Values | Schwartz basic values (10) or higher-order (4) | z-score | 4 to 10 | published survey norms, conditional on L0 | [agent, partial] PVQ-RR tested in 49 groups; not opened |
| L3 Needs and motivations | what drives a decision: autonomy, competence, relatedness (self-determination), security, status, novelty | 0 to 1 | ~6 | derived from L1/L2/L0 by fixed mapping, then personal noise | taxonomy [memory]; mapping [ours]; not built |
| L4 Wants and goals | what they are trying to get: save money, save time, protect family, stay independent, belong, learn, advance, stay healthy | 0 to 1 weight per goal | ~10 | sampled by life stage and L3 | partly [built] (one aspiration out of 7) |
| L5 Constraints and resources | budget slack, time slack, tech skill, access (area, connectivity), health, caregiving load | 0 to 1 | ~8 | derived from L0 plus noise | partly [built] (price, time, tech as 1 to 5 traits) |
| L6 Habits and channels | early adopter vs follower, price comparing, brand loyalty, media diet, social proof reliance | 0 to 1 | ~8 | sampled conditional on L1/L5 | partly [built] (novelty); rest [ours] |
| L7 Beliefs and trust | trust in institutions, companies, strangers, technology; privacy stance; worldview | -1 to 1 | ~8 | sampled conditional on L2/L0 | partly [built] (privacy, social, worldview) |
| L8 States | financial stress, mood, urgency, attention | 0 to 1 | ~4 | start at neutral, moved by world | [ours]; not built |

About 55 to 65 numbers per persona. 100,000 of them is a 100,000 x ~64 float32 matrix, about 26 MB, and generating random numbers of that size took 0.055 s in the scale agent's run (random data only, not our rules) [agent, measured once].

Rule from the double-counting pitfall [agent, partial]: traits must be **world-neutral**. A trait such as "economic anxiety" belongs in L8 (a state the world moves), not in L1 to L7.

## 3. Cohorts are queries, not stored labels

A cohort is a predicate over factors: "age 18 to 29 AND area = large city", "high privacy stance AND low tech skill", "caregivers with low time slack". Nothing is assigned at generation. This keeps cohorts composable and lets the user define new ones on the 100,000 after the fact. Heat maps are group-bys over any two factors or predicates.

## 4. Wants, needs, motivations: how they differ in the model

| Concept | In the model | Used for |
|---|---|---|
| Need (L3) | stable drive; sets how much a stimulus feature matters | weights in the utility |
| Want / goal (L4) | what the person is trying to get now | does the stimulus serve a goal (fit term) |
| Motivation | need x want x state: why this person would act on this stimulus now | derived, not stored |
| Constraint (L5) | what blocks acting | veto / penalty terms (cost, effort, access) |
| Delight / frustration | positive / negative contributions to utility by feature | the explanation output |

## 5. The stimulus profile (the neutral side)

One classifier pass reads any medium into the same dimensions, so the persona side never changes with the medium. Proposed starting set (about 30 to 40, all [ours], needs a freeze before fitting):

- cost: money now, money recurring, time needed, effort to start, skill needed
- risk and trust: data or ID asked for, stranger contact, claim credibility, reversibility, social visibility
- fit: which goals it serves (same list as L4), who it is aimed at (age, area, income), novelty
- tone (for text or audio): urgency, fear, status signal, belonging, humour, authority
- medium tag: product, article, ad, call, message (a separate input, not a persona factor)

The classifier gives each a probability. Reading is done once per stimulus; edits that map to a known dimension change the vector arithmetically with no model call.

## 6. World model

A small vector w, 3 to 6 numbers (candidates: economy, institutional trust, season or time of year, news mood, prices; the "3 to 6" is the research agent's own judgement, not sourced). Each persona has sensitivities S_i = diag(u_i) * B with B low-rank and shared and u_i a per-person multiplier set by cohort. The world moves L8 states and some L7 beliefs only. Where the numbers in B come from, in order of strength: real survey waves or known before/after shifts (not available); published elasticities (not collected); asking the model to answer the same persona under two world states (a measurement of the model, not of people). Until calibrated, B is a prior and every world result is labelled so.

## 7. Outputs per persona and stimulus

noul (would engage or buy), a choice (first reaction, top delight, top frustration, each with a "none"), and a score where the answer is ordinal. Explanation = split of the cohort's change into persona, world and stimulus parts (exact, because the form is linear before the logit) [agent, measured]. This is a statement about the model, not a causal claim about real people.

## 8. What exists today (for contrast)

`personas.py` generates: age, work, area, region, income, household, caregiver, six domain traits (tech, price, privacy, social, time, novelty on 1 to 5), one aspiration, one worldview, and a rendered text profile. That covers a thin slice of L0, L4, L5, L6, L7. Missing: L1 personality, L2 values, L3 needs, L8 states, the world vector, the stimulus profile, and any link to real distributions. The six domain traits are domain constructs with no published standard [agent: none found].

## 9. Known risks (carry into every result)

- Model-simulated respondents show less variance than people, are sensitive to wording, and tilt toward some groups [agent, partial; sources not read in full]. A small real sample for calibration is the strongest fix reported there.
- Offline, a vector model fitted on hand-coded attributes failed on a new kind of idea (r 0.06 to 0.22). The stimulus dimension list must cover what ideas can be about.
- 100,000 simulated people are not 100,000 independent observations. Uncertainty sits in the fitted matrices, so report it by resampling those, not by counting personas.
- Our own factor lists and mappings are guesses until checked against real data.

## 10. Decisions needed before building more

1. Which media first: product ideas only, or also articles and calls?
2. Layer list: is this the right set, and which of L1, L2, L3 do we include now? Values and personality need external norm data and a licence check.
3. Source for L0: keep hand-weighted lists, or fit to published census marginals (needs a download and a licence check)?
4. Stimulus dimensions: freeze about 30 to 40 before any fitting, so changing them later is a new version, not an edit.
5. Is there any real survey or behaviour data we can use for calibration, even small?

---

# Engine v0: world dials, perception, decision gates (draft 0, 2026-10-02)

Status of everything below: **[ours]** unless stated. The strengths are guesses. Every result is a SCENARIO ("if the world moved like this and people respond like this"), not a forecast.

## World dials (10), all start at 1 (neutral), higher = more of the thing
1 prices and cost of living; 2 job and income security; 3 personal safety and crime fear; 4 health risk; 5 trust in institutions; 6 community and belonging; 7 pace of technology change; 8 disruption to daily routines; 9 optimism about the future; 10 news overload.
An event multiplies one or more dials (prices x1.3). Each dial drifts back toward 1 with its own half-life (in ticks).

## Perception
Each persona perceives a dial through its own filter: perceived = 1 + salience x (dial - 1), salience between 0.3 and 1, fixed per persona and dial (seeded).

## Persona elements the world moves (8)
tech, price, privacy, social, time, novelty (the six traits, level 1 to 5) plus two moving states: financial stress and optimism.
Effective element = base element x product over dials of (perceived dial) ^ strength. Strength is a small table (element x dial, mostly zeros, ~20 entries). Multiplying around 1 means a neutral world changes nothing.

## Decision gates (8) = the main loop
spend (vs save), buy something new, subscribe, travel, change work, move, switch brand, share or engage.
Each persona meets decision d on a tick with a small base probability (an opportunity). If it does, it acts with probability sigmoid(bias + sum of weights x effective elements). Personality flair (Big Five) is not in v0.

## Tick
1 events arrive and dials move, then drift toward 1; 2 each persona perceives; 3 elements are modified; 4 gates are evaluated (expected rate, or sampled with the run seed); 5 the dial values, events and per-cohort rates are logged; any persona's number can be explained by resetting one dial at a time.

## Pre-registered checks for the toy (probes/persona/engine.py)
 E1 same seed -> identical sampled run; different seed -> different run.
 E2 neutral world (no events): no gate rate changes at any tick (drift < 1e-9).
 E3 wiring direction: a prices x1.3 shock lowers 'subscribe' and 'buy new' at the peak, and the relative drop is >= 1.25x larger for high price-attention personas (price >= 4) than low (price <= 2); a shock to 'pace of technology change' (x1.5) moves 'buy new' and 'subscribe' by < 1% relative.
 E4 decay: six half-lives after an event the dial is within 2% of 1 and gate rates within 1% of baseline.
 E5 speed: 100,000 personas x 1,000 ticks in under 120 s.
 E6 explanation: resetting dials one at a time, the single-dial effects add up to within 15% of the total effect, and the prices dial is the largest for 'subscribe' under the prices shock.
 E7 sensitivity (report only): redraw every strength by a random factor 0.5 to 1.5 (20 draws); report the range of the peak effect. If the range is wider than the effect, the result is decided by our guesses, and is labelled so.
 Caveat declared in advance: E3 to E6 test that the wiring does what we wrote, not that people behave this way.
