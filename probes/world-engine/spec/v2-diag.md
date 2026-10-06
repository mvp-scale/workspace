# v2 diagnosis and data fixes (agent DIAG)

Test engine: `WE_RULES=rules_v2` on :8132 (stopped). Vocabulary: topics, conditions, person states, decisions, resources.

## Findings
1. **School reform moved nothing.** Topic `education_schools` routes to one condition, `public_service_quality`. Its attribute bank only had "services work better / faster delivery / decline / backlogs". A story that says a reform "changes how schools are run" matched none (best mean 0.45 vs bar 0.65), so no reading, status `no_impact_expected`, all zeros. No gate or weight zeroed it. Missing in the bank: schools funded or cut. A story with direction ("more funding, new teachers") already moves; see before/after. Structural gap (not fixed, outside allowed files): no condition points at resource `skills`, and `education_skills` is a fixed trait, so schooling cannot move `study_train`.
2. **War/strike -> travel, population, built_infrastructure.** Not noise in the person-state path: travel falls through `safety_concern` (weight -0.8, "felt danger stops trips"). The noise was upstream: the war story was read as `crime` (bank: "violent crime or attack" matched bombing) and as `social_division` ("hostility between camps" matched two countries), while `war_terror` fell under the bar (q2 "fighting near the audience"). Crime fed `safety_concern` at 0.8, war_terror only 0.5. A data breach also got `crime` (expected) -> travel. Strike: resource `built_infrastructure` comes from `disruption` (dial_resources.csv, `disruption` -> built_infrastructure); a strike halts services, not buildings: data issue in a file outside the allowed list (not changed). `population` for war/wildfire comes from `migration_flow`.
3. **Spend leads.** `prices`, `job_security`, `pay_growth` each feed 3-4 money states (financial_stress, liquidity, optimism, price_attention) and four of spend's six inputs are those states, so any economy, energy or food story moves spend. Meaningful for economic stories (12 of 20), but the same condition is counted through several states. Not changed (no meaning-only grounds found to cut one link).
Code issue: none found.

## Data changes (each reason is about meaning)
| File | Change | Reason |
|---|---|---|
| dial_attributes.csv crime/violent incident q1 | "violent crime or attack" -> "violent crime such as an assault, robbery or murder by individuals" | Wars and military attacks are war_terror, not street crime |
| dial_attributes.csv war_terror/armed attack q2 | "fighting near the audience" -> "soldiers or armed groups fighting" | War anywhere is conflict; "near the audience" excluded the plain case |
| impact_phrases.csv crime | "street crime and violence by individuals in daily lives" | Online theft and war are other conditions |
| dial_attributes.csv social_division q2 | "hostility between groups within one society" | Division is inside a society; a war between states is not it |
| dial_attributes.csv fiscal_strain/surplus q2 | "a government deficit shrinking" (was "money to spare") | "Money to spare" matched new spending, reading strain down |
| dial_attributes.csv fiscal_strain up | new attribute "new spending commitments" | New spending or lost revenue raises deficits; was missing |
| dial_attributes_extra.csv public_service_quality | up "schools better resourced", down "schools cut back" | Education topic had no schooling-specific wording |
| domains.csv climate_change | 3rd condition biodiversity_loss -> health_risk (resources column derived to population_health) | Heat and smoke are direct health effects; biodiversity already routes from pollution_nature |
Caps unchanged (topics <=3, links 272/375). `validate_v2.py`: ALL CHECKS PASSED after each batch.

## 20 stories: top 3 decisions, top 2 resources, Size tier
Before / after (after = final run). Unchanged rows shown once.
| Story | Decisions | Resources | Tier |
|---|---|---|---|
| rate cut | spend, buy_new, claim_support | housing_stock, asset_wealth | Minor |
| pandemic | travel, health_action, stockpile_prepare | care_capacity, population_health | Notable |
| war | before travel, share, protest; after spend, travel, buy_new | state_capacity, social_trust -> primary_energy, state_capacity | Notable -> Minor |
| heat wave | before spend, travel, buy_new; after spend, travel, health_action | atmosphere_climate, primary_energy | Minor |
| strike | spend, travel, buy_new | built_infrastructure, supply_networks | Minor |
| phone launch | buy_new, invest, spend (all ~0) | computing_capacity, productive_capital | Negligible |
| school reform | all 0 (no reading) | none | Negligible |
| data breach | before travel, break_rules, health_action; after break_rules, health_action, protest | computing_capacity, legitimacy | Minor |
| tax rise | spend, buy_new, claim_support | asset_wealth, public_finances | Notable |
| housing boom | spend, borrow, buy_new | housing_stock, monetary_credit | Notable |
| election upset | break_rules, protest, share | social_trust, legitimacy | Minor |
| factory closure | spend, claim_support, buy_new | labour_force, productive_capital | Minor |
| new vaccine | travel, health_action, stockpile_prepare | population_health, care_capacity | Minor |
| oil price spike | spend, buy_new, invest | asset_wealth, primary_energy | Major |
| AI job cuts | spend, claim_support, buy_new | labour_force, computing_capacity | Notable |
| wildfire | health_action, travel, stockpile_prepare | built_infrastructure, population | Minor |
| bank failure | spend, invest, buy_new | asset_wealth, labour_force | Notable |
| immigration surge | share, protest, break_rules | population, social_trust | Minor |
| drought | before spend, buy_new, invest; after spend, travel, buy_new | food_stock, water | Notable |
| big sports final | donate_volunteer, travel, family_change | community_ties, attention | Negligible |

Summary (top-1 decision, stories with a non-zero move = 19): before 6 distinct, spend 10 of 20 (50%); after 6 distinct, spend 11 of 20 (55%). Worse: spend share rose by one (war and drought now lead with spend through energy, food and price rises); the war Size fell from Notable to Minor once the false crime reading went. Better: war reads war_terror, data breach no longer reads street crime, heat wave reads health_risk.
Direct checks: "schools given much more funding" now reads public_service_quality up and fiscal_strain up (before: fiscal_strain down, wrong way); "school budget cuts, 200 closures" reads public_service_quality down. The neutral school reform sentence still moves nothing (no direction stated).

## Open items (not data-fixable within the allowed files)
- A condition for education/skills (resource `skills` has no condition).
- `disruption` -> `built_infrastructure` resource link (dial_resources.csv).
- Money double counting through four states (grid.csv / decision_weights.csv design call).

## Added condition: skills_level (agent SKILLS)
Closes the first open item. `skills_level` ("Skills and education level", resource `skills`, up = more people with the skills they need, good). Half-life 225 ticks, a guess: the median of the six human-resource conditions (health_risk 150, mental_distress 250, care_strain 100, job_security 200, pay_growth 250, migration_flow 300). Grounding series: educational attainment and adult skills survey results. Status guess.
Wiring (all guesses, additive): topics education_schools (public_service_quality; skills_level) and work_labour (job_security; pay_growth; skills_level), both within the 3-condition cap, nothing dropped; ai_automation left alone (already 3, and an automation story moves skills only indirectly). Banks: 2 up and 2 down attributes (4 statements), impact phrase, dial_resources row (level_of, build). Grid: one link, job_worry <- skills_level -0.5 ("better skills mean more employable people and less job worry"); job_worry now has 4 links (cap met). The derived state `education_skills` stays fixed: derived states have no incoming links. Totals: 39 conditions, 101 topic links, 53 grid links, 275 links in all (cap 375). validate_v2.py passes (expected condition count 39, id_map action `new` allowed).

Test (own engine :8134, WE_RULES=rules_v2, event mode, reset between stories; skills_level delta from the skills resource chain):
| Story | skills_level | Top decision | Top resource |
|---|---|---|---|
| school funding increase | up +0.44 | break_rules (-) | public_finances (strained) |
| graduates lack job skills | down -0.87 | spend (-) | labour_force (strained) |
| school and training budgets cut | down -0.92 | protest (+) | skills (strained) |
| new primary reading programme | up +0.59 | study_train (-, Negligible) | skills (built) |
| factories closed, retraining needed | up +0.50 | spend (-) | labour_force (strained) |
| central bank rate cut (control) | no move | spend (+) | housing_stock |
Reading: the control stays clean, and the first four move the right way. Weak spot: the retraining story reads skills up, but the story is about lost jobs plus a need for skills, so "down or unchanged" arguably fits better; the classifier read the retraining answer as a build. The reading-programme story gives study_train slightly negative because lower-skill people gain more from training (existing study_train weight on education_skills, not changed here). No weights were tuned to the outputs.
