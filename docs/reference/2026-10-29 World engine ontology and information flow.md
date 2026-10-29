# World engine: the ontology and how information flows through it

Self-contained reference. Written 2026-10-29 for a reader who has no other access to this project: everything needed is in this file, including the full lists and tables in the appendices. Nothing here depends on code, files or services you cannot see.

**Scope.** This describes what the engine models, how the parts relate, and how a change in one part spreads and becomes a forecast. It does **not** describe how a raw source item (an article, an email, a message) is read and turned into the inputs described in section 4. That step is a separate problem and is deliberately left out. Section 4 says exactly what the engine needs from it.

**Status of every number.** All strengths, half-lives, weights and thresholds are hand-set guesses unless a row says `rule`. None has been fitted to real outcomes and nothing has been compared with a real outcome yet. Treat the structure as the contribution and the numbers as placeholders.

## 1. What the engine is for

Given something that happened or was said, it answers: **what changes in the world, for whom, and what do people do about it.** "World model" is meant loosely: how the situation, and the perspective of the people in it, shifts. The output is a forecast: the size of change in each decision people might take, in each place and audience, over three horizons, compared with a run in which the event never happened.

## 2. Terms used in this file (and the names in the raw tables)

| Term here | Name in the engine's own tables and code | Meaning |
|---|---|---|
| Condition | `dial` | A measurable state of a place that can move up or down (prices, water stress, civil unrest) |
| Person state | `element` | Something about a person: a fixed trait or a feeling or circumstance that conditions can move |
| Decision | `decision` | An act a person might take |
| Resource | `resource` | A stock a condition draws on |
| Topic | `domain` | What a source item is about |
| Tick | `tick` | One simulation step. The demo treats 1 tick as 1 day; this is an assumption, not a calibrated clock |
| Half-life | `half_life_ticks` | Ticks for a condition's change to fade by half as it drifts back to its normal level |
| Points | | Percentage points of likelihood. +1.3 points means a person's chance of taking an act is 1.3 percentage points higher than in the control run |
| Control run | | An identical copy of the world with no event, run beside the event run. Everything reported is the difference between the two |
| Gate | | A threshold below which a change does not pass along a link or edge |
| Lag | | Ticks a change waits before passing along an edge |
| Gain | | Multiplier applied when a change passes along an edge |

## 3. The layers and links (the ontology)

Five kinds of thing, plus places. A change always travels one way down this list; nothing flows back up except through the explicit condition-to-condition ties.

| Layer | What it is | Count | Appendix |
|---|---|---|---|
| Topic | What an item is about. A closed list; every item gets at least one; `other` collects what fits nowhere and is logged for review. Backbone is the Comparative Agendas Project policy-topic scheme, regrouped | 48 + other | D |
| Condition | See section 2. Each has a half-life (60 to 500 ticks), a real-world data series it is meant to be grounded in, and an `up_means` note saying whether more is good or bad. 38 are real-world conditions; `news_overload` is a media condition driven only by story volume | 39 | B, C |
| Person state | 20 fixed traits (such as risk tolerance, loss aversion), 8 derived values, 19 moving states (such as financial stress, job worry, grievance) | 47 | E |
| Decision | An act a person might take, each with a baseline rate, a bias and a stakes weight | 20 | F |
| Resource | A stock such as freshwater or social trust. Derived from each condition's resource, not hand-linked to topics | 26 | A |

Each condition has **direction attributes**: the specific ways it can rise or fall (for water stress: up through supply shortage, up through contamination, down through supply restored). A change is always: a condition, a direction, a size. See Appendix C.

### Links

Every link is signed and graded weak 0.2, medium 0.5 or strong 0.8, with a written reason. Capped to keep the graph sparse and readable.

| Link | Meaning | Count | Appendix |
|---|---|---|---|
| Topic to condition | An item on this topic may move these conditions. At most 3 per topic, main one first | 101 | D |
| Condition to condition (tie) | A change in one condition passes to another at the same place one tick later (fuel cost to prices). At most 12; one outgoing tie per condition; a change that arrived by a tie may start at most 3 further ties in a row | 12 | G1 |
| Condition to person state | A condition moves the states that feel it (rising prices raise financial stress). At most 4 conditions per state | 53 | G2 |
| Person state to decision | A state raises or lowers the chance of an act. 4 to 6 inputs per decision | 109 | G3 |

The chain in one line: **topic, then condition, then (resource), person state, decision, group, place.**

### Places and people

- **Place tree.** One world node; one node per country (100 countries, Appendix I); under each country three settlement types: metro, town, rural. That is 401 nodes (1 + 100 + 300).
- **Country facts held.** Region, population, median age, income, urban share, and six default trait values (tech comfort, privacy stance, social ease, time pressure, novelty seeking, price attention) taken from public population and income statistics. Country-specific starting levels for the conditions are all zero at present (no data wired), so countries differ only in these facts.
- **People.** A synthetic population of 100,000, drawn from the country table. People are grouped into **audiences**: 8 segments found by clustering on beliefs, habits and life situation together. A person or audience is a lens: it feels the conditions of its place through its own traits.
- **Perspective is chosen by the viewer:** world, a country, a region, or an audience. The same event produces different numbers from each.

## 4. What the engine needs from a source item (the entry contract)

Whatever the source, the engine needs these fields. How they are produced is outside this document.

| Field | Meaning |
|---|---|
| Entry place | World, or one country; where the change begins |
| Topic(s) | What it is about (Appendix D) |
| Condition changes | For each one: which condition, which direction, how large |
| Size level | A multiplier on the base change (table below) |
| Mode | How firmly the change is asserted (table below) |
| Story type | Fact, unclear, forecast or opinion (table below). Hedged types enter at reduced weight, and the engine can also show "what if it were true" by removing the hedge |


**Size levels**

| Level | Multiplier | Meaning |
|---|---|---|
| Minor | 0.4 | A small change that most people would hardly notice |
| Notable | 1.0 | A clear change that many people would notice. This is the size every reading had before levels existed |
| Major | 2.0 | A big change that affects daily life for many people |
| Severe | 4.0 | A very large change that amounts to a crisis |
| Extreme | 7.0 | An unprecedented change that reshapes how society works |


**Mode**

| Mode | Weight | Meaning |
|---|---|---|
| reported | 1.0 | The story reports the change itself (a dial check cleared the 65% bar). Unchanged from before. |
| expected_in_effect | 0.6 | Not reported as a change, but the story gives a real reason to expect one, and the development is already in effect. |
| expected_pending | 0.3 | Not reported as a change, but a change is expected if the story plays out; the development is still pending (a hearing, a plan, a proposal, a possibility). |


**Story type**

| Type | Weight | Meaning |
|---|---|---|
| fact | 1.0 | Reported as happened or announced, and not mainly opinion or a forecast: counts in full. Unchanged from the earlier gate. |
| forecast | 0.3 | Mainly a forecast. Used to be refused; now enters at reduced weight. |
| opinion | 0.3 | Mainly opinion or commentary. Used to be refused; now enters at reduced weight. |
| unclear | 0.5 | Neither reported as happened or announced, nor opinion or forecast (for example an explainer or an interview). Used to be refused. |


## 5. How a change travels (the arithmetic)

Only arithmetic from here on. Every step is logged with the path it took, so any number can be traced back.

1. **Enter.** The condition changes land on the entry node, scaled by size level, mode and story-type weight.
2. **Spread.** Changes pass along edges: world to each country (gain 0.6, lag 1 tick, gate 0.003), country to each of its three settlement types (gain about 1, varying 0.7 to 1.3 by condition, lag 1, gate 0.002). A small seeded random noise (5 percent) is added per edge. Each edge also has a per-condition `slant` for agenda or political skew; it is zero everywhere today, so that element is built but not exercised.
3. **Tie.** Condition-to-condition ties fire at the same node, one tick later, with no extra noise; ties below an absolute size of 0.002 are dropped.
4. **Decay.** Each condition drifts back to its place's normal level with its own half-life.
5. **Feel.** Each person perceives each condition's local change through a personal salience (a random value from 0.3 to 1.0 per person per condition): perceived = 1 + salience x change, floored at 0.2. A person's effective state = base state x the product, over the conditions linked to it, of perceived raised to the link strength (signed). States live on a 1 to 5 scale and are clipped to 0.5 to 5.5.
6. **Decide.** The chance of each decision = logistic(bias + sum over its linked states of weight x (state - 3) / 1.5). A state at the scale midpoint (3) contributes nothing.
7. **Compare.** The event run is set against the control run; reported numbers are differences in points of likelihood.

## 6. How it forecasts

- **Three horizons.** *Now* is 3 ticks. *Later* is the median condition half-life rounded to a multiple of 5 ticks. *Next* is about one fifth of Later, at least 5 ticks. Every horizon is computed for every event.
- **Per-decision score (0 to 100)** from four parts, each scaled 0 to 1: **size** (weight 0.45; 1 minus exp(minus points / 4), so a 4-point move at world level counts about 0.63), **reach** (0.15; share of people moved by at least 0.5 points at Next), **persistence** (0.15; how much of the peak is left at Later) and **stakes** (0.25; the act's stakes weight divided by 5, Appendix F). The result is multiplied by the square root of size so a tiny change cannot rank high on stakes alone.
- **Event significance** = 0.7 x the top decision score + 0.3 x the mean of the top three. Bands: Negligible below 12, Minor below 30, Notable below 50, Major below 70, Historic above.
- **Resources** get a net pressure (built, strained, mixed or none) summed from the conditions, states and decisions that touch them.
- **Outputs.** A ranked list of decisions; a table of points by place (or audience) by decision at Now, Next and Later; the resource view; a trace chain (topic, condition, resource, state, decision, group, place) with strengths; and a plain sentence ("so what") composed only from numbers the engine produced.
- **Scoring forecasts.** Today forecasts are scored only against the engine's own later state. Scoring against real-world evidence needs a real clock and outside data series; conditions are tied to named real series so this is possible, but it is not done.

## 7. Using this with feeds that are not news

The layers, links and arithmetic do not depend on the source. Only the entry contract (section 4) does, and parts of it assume news:

- **Story type and recency** are news ideas. Other feeds need an equivalent: an email might be a request, an update or a commitment; a message might be a status or a mood. What survives is a *weight for how firmly the item asserts a change*.
- **Topics** are news-shaped. Topics only route to conditions, so a new feed can add topics, or skip them and name conditions directly.
- **Entry place** may not exist for non-geographic content. World is the default.
- **New conditions or decisions** may be needed (a company-internal feed would want conditions about its own operations). The ontology is designed to grow by adding rows, each with a written reason, a link and a status, without changing the arithmetic.
- **Time.** A feed needs a real clock, with dated items, before ticks mean anything.

## 8. Known limits

- Every weight is a guess; none is fitted. Country and settlement parameters are illustrative.
- No comparison with any real outcome.
- Events spill between countries only through the world node.
- The channel slant is zero, so the political-agenda element is unexercised.
- The person-to-decision model was first fitted on US-style generated people and is extrapolated to other countries.
- The topic-to-condition routing is our judgement, not derived from data.

---

# Appendices (the full ontology)


## A. Resources (26)

| id | name | group | meaning |
|---|---|---|---|
| water | Freshwater | natural | Usable fresh water in rivers, lakes, aquifers and supply systems. |
| land_soil | Land and soil | natural | Farmland, grazing land, forest and the soil quality that supports them. |
| biodiversity | Ecosystems and wildlife | natural | Living nature: species, habitats, oceans and fish stocks. |
| atmosphere_climate | Air and climate | natural | The air we breathe and the stability of the climate system. |
| primary_energy | Energy sources (fuels, sun, wind, water) | natural | Fuels and renewable energy sources that can be used to make power and heat. |
| minerals_materials | Minerals and materials | natural | Metals, industrial minerals, sand and other raw materials in the ground or stockpiled. |
| food_stock | Food supply | natural | Harvested crops, livestock products, catch and stored food available to eat. |
| built_infrastructure | Built infrastructure | produced | Roads, rail, ports, power grids, pipes, and public buildings. |
| housing_stock | Housing stock | produced | Homes available to live in. |
| productive_capital | Productive capital | produced | Factories, machines, vehicles, farms equipment and business inventories. |
| computing_capacity | Computing and networks | produced | Computers, data centres, communication networks and software systems. |
| supply_networks | Trade and supply links | produced | Working shipping, logistics and trading relationships that move goods between makers and users. |
| monetary_credit | Money and credit | financial | The money and lending capacity of the financial system. |
| asset_wealth | Wealth and assets | financial | Savings, property and shares that households and firms hold, net of the debts they owe. |
| public_finances | Public finances | financial | Government revenue, borrowing capacity and reserves. |
| population | Population | human | The number, age mix and movement of people living in a place. |
| population_health | Population health | human | Physical and mental health of the people in a place. |
| care_capacity | Care capacity | human | Hospitals, clinics, health workers and medicines available to treat people. |
| skills | Skills and education | human | Learned abilities of the population. |
| labour_force | Labour | human | People able and available to work, and the work they hold. |
| social_trust | Social trust and cohesion | social | Trust between people and groups. |
| community_ties | Community ties | social | Local networks, clubs, volunteering and everyday help between people. |
| legitimacy | Legitimacy | institutional | The public's acceptance of an authority's right to act. |
| state_capacity | State capacity and public safety | institutional | Ability of government, police, courts and armed forces to deliver services, enforce rules, keep people safe and protect rights. |
| knowledge | Knowledge and information | knowledge | Recorded knowledge: research, data, records and published information. What people carry in their heads is skills. |
| attention | Time and attention | knowledge | The limited daily time and focus people have, including the free time left after work and care. One budget, so free time is not a separate stock. |


## B. Conditions (39)

Columns: half-life in ticks; what up means; what a rise and a fall look like; the resource it draws on.

| id | name | kind | half-life | meaning | up means | a rise is | a fall is | resource |
|---|---|---|---|---|---|---|---|---|
| water_stress | Water stress | condition | 200 | How short or unsafe water supply is for a place. | more shortage or contamination (bad) | water supply gets shorter or less safe | water supply gets more plentiful or safer | Freshwater |
| land_degradation | Land degradation | condition | 400 | Loss of usable farmland, forest and soil through erosion, fire, flooding or sprawl. | more land lost or degraded (bad) | farmland, forest or soil is lost or damaged | farmland, forest or soil is restored or protected | Land and soil |
| biodiversity_loss | Biodiversity loss | condition | 500 | Decline of species, habitats and fish stocks. | more decline (bad) | wildlife, habitats or fish stocks decline | wildlife, habitats or fish stocks recover | Ecosystems and wildlife |
| climate_stress | Climate stress | condition | 300 | How severe heat, drought, flood and storm hazard is compared with normal. | more hazard (bad) | heat, drought, flood or storm hazard gets worse | heat, drought, flood or storm hazard eases | Air and climate |
| air_pollution | Air pollution | condition | 150 | Concentration of harmful particles and gases in the air. | dirtier air (bad) | the air gets dirtier | the air gets cleaner | Air and climate |
| energy_fuel | Energy cost and supply | condition | 100 | How expensive and how available fuel, electricity and heating are. | costlier or scarcer (bad) | fuel, electricity or heating costs rise or supply gets tighter | fuel, electricity or heating costs fall or supply improves | Energy sources (fuels, sun, wind, water) |
| mineral_scarcity | Mineral and material scarcity | condition | 250 | How hard it is to obtain metals and raw materials. | scarcer or costlier (bad) | metals and raw materials get scarcer or costlier | metals and raw materials get easier to obtain or cheaper | Minerals and materials |
| food_insecurity | Food insecurity | condition | 150 | Share of people who cannot reliably get enough affordable food. | more people short of food (bad) | more people struggle to get enough affordable food | fewer people struggle to get enough affordable food | Food supply |
| housing_cost | Housing cost | condition | 300 | Rent, house prices and mortgage cost relative to income. | costlier (bad) | rents, house prices or mortgage payments rise | rents, house prices or mortgage payments fall | Housing stock |
| infrastructure_condition | Infrastructure condition | condition | 500 | How well roads, grids, pipes and public buildings are maintained. | better repair (good) | roads, grids, pipes and public buildings get better maintained | roads, grids, pipes and public buildings fall into disrepair | Built infrastructure |
| disruption | Disruption of services | condition | 80 | Interruptions to travel, power, water and public services. | more interruptions (bad) | travel, power, water or public services are interrupted more often | travel, power, water or public services are interrupted less often | Built infrastructure |
| industrial_output | Industrial output | condition | 150 | How much goods production is running relative to capacity. | more output (good) | factories produce more | factories produce less | Productive capital |
| supply_chain_strain | Supply chain strain | condition | 100 | Delays, shortages and trade barriers in moving goods. | more strain (bad) | goods get harder or slower to move and trade | goods get easier and faster to move and trade | Trade and supply links |
| tech_adoption | Technology adoption | condition | 300 | Share of daily life and work done with newer digital tools. | more adoption (neutral) | more daily life and work moves onto newer digital tools | less daily life and work moves onto newer digital tools | Computing and networks |
| cyber_insecurity | Cyber insecurity | condition | 100 | How exposed digital systems are to breaches and outages. | more breaches (bad) | digital systems become more exposed to breaches and outages | digital systems become less exposed to breaches and outages | Computing and networks |
| prices | Prices | condition | 150 | How expensive everyday goods and services are, i.e. how little a unit of money buys. | higher prices (bad) | everyday prices and the cost of living rise | everyday prices and the cost of living fall | Money and credit |
| borrowing_cost | Borrowing cost and credit access | condition | 150 | How costly and available loans are. | costlier or tighter credit (bad) | loans get costlier or harder to get | loans get cheaper or easier to get | Money and credit |
| asset_values | Asset values | condition | 200 | Level of share, property and savings values. | higher values (good for holders) | share, property and savings values rise | share, property and savings values fall | Wealth and assets |
| market_volatility | Market volatility | condition | 60 | How violently asset prices are swinging. | more volatility (bad) | financial markets swing more wildly | financial markets become calmer | Wealth and assets |
| private_debt | Private debt | condition | 300 | Share of income that households and firms owe in repayments. | heavier burden (bad) | repayments take a bigger share of household or firm income | repayments take a smaller share of household or firm income | Wealth and assets |
| inequality | Economic inequality | condition | 500 | Gap between richest and poorest in income and wealth (the Gini coefficient is the usual single number for it). | wider gap (bad) | the gap between the richest and poorest widens | the gap between the richest and poorest narrows | Wealth and assets |
| fiscal_strain | Fiscal strain | condition | 300 | Pressure on government budgets from deficits, debt and spending needs. | more strain (bad) | pressure on government budgets increases | pressure on government budgets eases | Public finances |
| health_risk | Health risk | condition | 150 | Exposure to illness, injury and disease outbreak. | more risk (bad) | exposure to illness, injury or outbreak increases | exposure to illness, injury or outbreak decreases | Population health |
| mental_distress | Mental distress | condition | 250 | Share of people with anxiety, depression or stress. | more distress (bad) | more people suffer anxiety, depression or stress | fewer people suffer anxiety, depression or stress | Population health |
| care_strain | Care strain | condition | 100 | Pressure on hospitals, clinics, staff and medicine supply. | more strain (bad) | hospitals, clinics, staff or medicine supply come under more strain | hospitals, clinics, staff or medicine supply come under less strain | Care capacity |
| job_security | Job security | condition | 200 | How secure people's jobs and work availability are. | more secure (good) | work and incomes become more secure | jobs and incomes become less secure | Labour |
| pay_growth | Pay growth | condition | 250 | How fast pay is rising, before any price rises are taken off. | faster pay growth (good) | pay rises faster | pay rises more slowly or falls | Labour |
| social_division | Social division | condition | 400 | Polarisation and unfairness between groups. | more division (bad) | society becomes more polarised or unfair | society becomes less polarised or unfair | Social trust and cohesion |
| community | Community strength | condition | 300 | How connected and supportive local communities are. | stronger (good) | local communities become more connected and supportive | local communities become less connected and supportive | Community ties |
| trust_institutions | Trust in institutions | condition | 300 | How credibly government, business and media are seen to act. | more trust (good) | government, business or media come to be seen as more credible and trustworthy | government, business or media come to be seen as less credible and trustworthy | Legitimacy |
| public_service_quality | Public service quality | condition | 300 | How well government delivers schools, courts, permits and benefits. | better (good) | schools, courts, permits and benefits are delivered better | schools, courts, permits and benefits are delivered worse | State capacity and public safety |
| civil_liberties | Civil liberties | condition | 400 | How freely people can speak, vote, assemble and get fair legal treatment. | more freedom (good) | people become freer to speak, vote, assemble and get fair legal treatment | people become less free to speak, vote, assemble and get fair legal treatment | Legitimacy |
| crime | Crime | condition | 100 | Crime and violence around people's daily life. | more crime (bad) | street crime and violence by individuals in people's daily lives increase | street crime and violence by individuals in people's daily lives decrease | State capacity and public safety |
| war_terror | War and terror | condition | 150 | Armed conflict and terrorism affecting the audience's country or region. | more conflict (bad) | armed conflict or terrorism affecting the country or region increases | armed conflict or terrorism affecting the country or region decreases | State capacity and public safety |
| civil_unrest | Civil unrest | condition | 60 | Level of riots, mass protest and disorder. | more unrest (bad) | riots, mass protest and disorder increase | riots, mass protest and disorder decrease | State capacity and public safety |
| information_reliability | Information reliability | condition | 300 | How accurate and trustworthy public information is. | more reliable (good) | public information becomes more accurate and trustworthy | public information becomes less accurate and trustworthy | Knowledge and information |
| news_overload | News overload | media | 20 | Share of audience attention taken up by news volume. | more news competing (bad) | there is more news competing for people's attention | there is less news competing for people's attention | Time and attention |
| migration_flow | Migration flow | condition | 300 | How many people are arriving in or leaving a place, relative to its population. | more net arrivals (neutral) | more people arrive in a place than leave it | more people leave a place than arrive in it | Population |
| skills_level | Skills and education level | condition | 225 | How far the people of a place have the education and skills they need for work and life. | more people with the skills they need (good) | more people gain the skills and education they need | fewer people have the skills and education they need | Skills and education |


## C. Direction attributes (the specific ways each condition moves)

| condition | direction | attribute | what it means |
|---|---|---|---|
| Water stress | up | supply shortage | water supply runs short |
| Water stress | up | contamination | water becomes unsafe to drink |
| Water stress | down | supply restored | water supply recovers or is secured |
| Water stress | down | water made safe | water quality is cleaned up |
| Land degradation | up | land loss | farmland, forest or soil is lost |
| Land degradation | up | fire or flood damage | fire or flood destroys land |
| Land degradation | down | land restored | land or forest is restored |
| Land degradation | down | land protected | land is protected from loss |
| Biodiversity loss | up | species decline | wildlife numbers fall |
| Biodiversity loss | up | habitat or fish stock loss | habitats or fish stocks shrink |
| Biodiversity loss | down | wildlife recovery | wildlife numbers recover |
| Biodiversity loss | down | habitat protection | habitats or fish stocks are protected |
| Climate stress | up | extreme heat or drought | unusual heat or drought hits |
| Climate stress | up | flood or storm | severe flood or storm hits |
| Climate stress | down | milder weather | weather hazard eases |
| Climate stress | down | hazard preparedness | defences against weather hazards improve |
| Air pollution | up | smog or smoke | air quality worsens |
| Air pollution | up | emissions rise | harmful emissions increase |
| Air pollution | down | cleaner air | air quality improves |
| Air pollution | down | emissions cut | harmful emissions fall |
| Energy cost and supply | up | energy price rise | fuel, power or heating costs more |
| Energy cost and supply | up | supply squeeze | energy supply gets tight |
| Energy cost and supply | down | energy price fall | fuel, power or heating costs less |
| Energy cost and supply | down | supply secured | energy supply improves |
| Mineral and material scarcity | up | raw material shortage | metals or materials are hard to get |
| Mineral and material scarcity | up | material price spike | raw material prices jump |
| Mineral and material scarcity | down | materials plentiful | metals or materials are easier to get |
| Mineral and material scarcity | down | material prices fall | raw material prices fall |
| Food insecurity | up | hunger | more people cannot get enough food |
| Food insecurity | up | food price rise | food costs more |
| Food insecurity | down | food relief | people get enough food |
| Food insecurity | down | food price fall | food costs less |
| Housing cost | up | rent or price rise | rents or house prices rise |
| Housing cost | up | mortgage cost up | loan payments on homes rise |
| Housing cost | down | rent or price fall | rents or house prices fall |
| Housing cost | down | housing relief | housing cost pressure eases |
| Infrastructure condition | up | repair and upgrade | roads, grids or pipes are repaired or built |
| Infrastructure condition | up | network completed | a new link or system opens |
| Infrastructure condition | down | neglect and decay | infrastructure falls into disrepair |
| Infrastructure condition | down | collapse or failure | a structure or network fails |
| Disruption of services | up | outage or cancellation | power, travel or services stop |
| Disruption of services | up | strike or breakdown | work stoppage or breakdown halts services |
| Disruption of services | down | services restored | services come back |
| Disruption of services | down | disruption ends | a stoppage is resolved |
| Industrial output | up | production up | factories produce more |
| Industrial output | up | new plant or orders | new capacity or orders arrive |
| Industrial output | down | production cut | factories produce less |
| Industrial output | down | plant closure | factories close or idle |
| Supply chain strain | up | shipping delays | goods take longer to arrive |
| Supply chain strain | up | trade barriers | new limits on trade appear |
| Supply chain strain | down | delivery recovery | goods flow faster |
| Supply chain strain | down | trade barriers lifted | limits on trade are removed |
| Technology adoption | up | new tool spreads | a new digital tool is widely taken up |
| Technology adoption | up | automation of work | machines or software take on tasks |
| Technology adoption | down | rollout halted | a technology is delayed or blocked |
| Technology adoption | down | rejection | people turn away from a technology |
| Cyber insecurity | up | data breach | private data is stolen or exposed |
| Cyber insecurity | up | attack or outage | a cyber attack knocks systems out |
| Cyber insecurity | down | security improved | digital defences get stronger |
| Cyber insecurity | down | attackers caught | a cyber threat is stopped |
| Prices | up | consumer price rise | everyday goods cost more |
| Prices | up | inflation pressure | inflation or a rising cost of living is the subject |
| Prices | down | consumer price fall | everyday goods cost less |
| Prices | down | inflation easing | inflation cools |
| Borrowing cost and credit access | up | rates rise | loans cost more |
| Borrowing cost and credit access | up | credit tightens | loans are harder to get |
| Borrowing cost and credit access | down | rates fall | loans cost less |
| Borrowing cost and credit access | down | credit eases | loans are easier to get |
| Asset values | up | share or property gains | shares or property gain value |
| Asset values | up | record highs | markets reach new highs |
| Asset values | down | share or property losses | shares or property lose value |
| Asset values | down | market slump | markets drop sharply |
| Market volatility | up | market swings | prices swing wildly |
| Market volatility | up | financial stress | credit or banks come under stress |
| Market volatility | down | markets calm | prices settle |
| Market volatility | down | confidence returns | fear in markets fades |
| Private debt | up | debt burden rise | households or firms owe more relative to income |
| Private debt | up | arrears and defaults | more people fall behind on repayments |
| Private debt | down | debt reduced | debts are paid down or cleared |
| Private debt | down | debt relief | debts are forgiven or restructured |
| Economic inequality | up | widening gap | the gap between rich and poor grows |
| Economic inequality | up | concentrated wealth | wealth concentrates among few |
| Economic inequality | down | narrowing gap | the gap between rich and poor shrinks |
| Economic inequality | down | redistribution | taxes or transfers share income more evenly |
| Fiscal strain | up | deficit or debt rise | government borrowing grows |
| Fiscal strain | up | budget cuts or tax rises | government raises money or cuts to cope |
| Fiscal strain | up | new spending commitments | government takes on large new costs |
| Fiscal strain | down | surplus or paydown | government finances improve |
| Fiscal strain | down | revenue boost | government income rises |
| Health risk | up | outbreak | an illness spreads |
| Health risk | up | rising illness or injury | more people fall ill or are hurt |
| Health risk | down | outbreak ending | an outbreak fades |
| Health risk | down | treatment or prevention success | a treatment or vaccine works |
| Mental distress | up | rising anxiety or depression | more people report anxiety or low mood |
| Mental distress | up | stress and burnout | stress and exhaustion rise |
| Mental distress | down | mood improving | fewer people report distress |
| Mental distress | down | support expanded | mental health help grows |
| Care strain | up | long waits | people wait longer for care |
| Care strain | up | staff or medicine shortage | care lacks staff or medicines |
| Care strain | down | waits shorten | people are seen faster |
| Care strain | down | capacity added | care capacity grows |
| Job security | up | hiring | employers hire more |
| Job security | up | low unemployment | fewer people are out of work |
| Job security | down | layoffs | employers cut jobs |
| Job security | down | closures | firms close or freeze hiring |
| Pay growth | up | pay rise | wages go up |
| Pay growth | up | wage deal | a pay deal is agreed |
| Pay growth | down | pay cut or freeze | wages fall or stall |
| Pay growth | down | earnings slowdown | earnings growth slows |
| Social division | up | polarisation | groups drift further apart |
| Social division | up | discrimination | some groups are treated unfairly |
| Social division | down | reconciliation | groups come closer |
| Social division | down | fairer treatment | unfair treatment is reduced |
| Community strength | up | mutual aid | neighbours help each other |
| Community strength | up | local gatherings | local events draw people |
| Community strength | down | loss of local spaces | shared local places close |
| Community strength | down | isolation | people become more cut off |
| Trust in institutions | up | credible conduct | institutions act openly and honestly |
| Trust in institutions | up | accountability | wrongdoing is held to account |
| Trust in institutions | down | scandal | an institution is caught out |
| Trust in institutions | down | concealment | an institution hides the truth |
| Public service quality | up | services improve | schools, courts or offices work better |
| Public service quality | up | faster delivery | permits or benefits arrive faster |
| Public service quality | down | services decline | public services work worse |
| Public service quality | down | backlogs | requests pile up unanswered |
| Civil liberties | up | rights expanded | people gain freedoms |
| Civil liberties | up | fair legal process | courts and elections become fairer |
| Civil liberties | down | rights curtailed | people lose freedoms |
| Civil liberties | down | repression | authorities crack down |
| Crime | up | violent incident | violence happens nearby |
| Crime | up | rising crime | crime rates climb |
| Crime | down | crime falling | crime rates fall |
| Crime | down | offenders caught | criminals are stopped |
| War and terror | up | armed attack | an attack or battle occurs |
| War and terror | up | conflict escalation | conflict spreads or worsens |
| War and terror | down | ceasefire or peace | fighting stops |
| War and terror | down | threat removed | an attack plot is stopped |
| Civil unrest | up | riots | disorder breaks out |
| Civil unrest | up | mass protest | large protests gather |
| Civil unrest | down | order restored | disorder ends |
| Civil unrest | down | grievances answered | protest causes are addressed |
| Information reliability | up | claims verified | a claim is checked and confirmed accurate |
| Information reliability | up | falsehood corrected | a false claim is debunked or corrected |
| Information reliability | down | false claims spread | false stories circulate |
| Information reliability | down | facts faked or withheld | figures or evidence are faked or withheld |
| News overload | up | flood of coverage | news volume swamps attention |
| News overload | up | nonstop alerts | constant alerts demand attention |
| News overload | down | light news flow | few stories compete for attention |
| News overload | down | news avoidance | people deliberately tune out of news |
| Migration flow | up | net arrivals | more people arrive than leave |
| Migration flow | up | refugee or worker inflow | people arrive seeking refuge or work |
| Migration flow | down | net departures | more people leave than arrive |
| Migration flow | down | entry limits | arrivals are restricted |
| Skills and education level | up | schools and training expand | more schooling, training or reading support reaches people |
| Skills and education level | up | skills match jobs | workers hold the skills employers need |
| Skills and education level | down | schools and training cut | schooling or training loses funding or places |
| Skills and education level | down | skills gap | people lack skills that work needs |


## D. Topics (48 + other) and the conditions each routes to

| id | name | meaning | moves these conditions (main first) |
|---|---|---|---|
| macro_growth_recession | Growth and recession | The overall size and health of an economy: output, recession, recovery, national income, business cycle | Job security; Industrial output |
| inflation_prices | Inflation and living costs | Prices of everyday goods and services rising or falling, cost of living, price controls | Prices |
| interest_credit_banking | Interest rates, credit and banks | Central bank decisions, loan and mortgage rates, bank health, lending, household and business debt | Borrowing cost and credit access; Private debt; Housing cost |
| markets_investment | Markets and investing | Stock, bond, currency, commodity and crypto prices, investor behaviour, savings products | Asset values; Market volatility |
| public_budget_tax | Taxes and public budgets | Taxation, government spending, deficits and debt, subsidies, public-sector pay | Fiscal strain; Public service quality; Economic inequality |
| trade_tariffs | Trade and supply chains | Imports, exports, tariffs, trade deals, shipping and supply disruptions of goods | Supply chain strain; Mineral and material scarcity; Industrial output |
| housing_rents | Housing and rents | Home prices, rents, construction of homes, evictions, homelessness, housing policy | Housing cost; Asset values |
| work_labour | Jobs and wages | Employment, unemployment, hiring, layoffs, pay, working hours and conditions | Job security; Pay growth; Skills and education level |
| labour_disputes | Unions and strikes | Trade unions, strikes, collective bargaining, labour law disputes | Pay growth; Disruption of services; Civil unrest |
| ai_automation | AI and automation | Artificial intelligence, robots and software replacing or changing tasks and jobs, AI safety and rules | Technology adoption; Job security; Information reliability |
| retirement_pensions | Retirement and pensions | Pension systems, retirement age, ageing populations' income, elder care funding | Fiscal strain |
| social_welfare_poverty | Welfare, poverty and inequality | Benefits, poverty, hunger programmes, income inequality, social safety nets | Economic inequality; Food insecurity; Private debt |
| energy_power | Energy and fuel | Oil, gas, coal, electricity, power grids, fuel prices, renewable build-out | Energy cost and supply; Prices; Air pollution |
| transport_infrastructure | Transport and infrastructure | Roads, rail, aviation, ports, public transport, bridges, grid and network build and failure | Infrastructure condition; Disruption of services; Supply chain strain |
| food_agriculture | Food and farming | Crops, livestock, fisheries, food supply and safety, famine, food prices | Food insecurity; Prices; Land degradation |
| water_utilities | Water and utilities | Drinking water, sanitation, droughts and floods affecting supply, utility services | Water stress |
| climate_change | Climate change | Global warming, emissions, climate policy and targets, adaptation | Climate stress; Water stress; Health risk |
| pollution_nature | Pollution and nature | Air and water pollution, waste, wildlife, forests, conservation, land use | Air pollution; Biodiversity loss; Land degradation |
| natural_disasters | Disasters and extreme weather | Storms, floods, heatwaves, wildfires, earthquakes and the response | Climate stress; Disruption of services; Infrastructure condition |
| public_health | Disease and public health | Epidemics, vaccination, outbreaks, health warnings, food and drug safety | Health risk; Care strain |
| health_care_system | Health care services | Hospitals, doctors, insurance, waiting times, health costs and funding | Care strain; Public service quality |
| medicines_science | Medicines and treatments | New drugs, trials, approvals, medical devices and medical research | Health risk; Care strain |
| mental_health_substances | Mental health and substance use | Mental illness, wellbeing, addiction, drugs, alcohol, tobacco policy | Mental distress |
| crime_policing | Crime and policing | Violent and property crime, policing, gangs, organised crime, prisons | Crime |
| courts_rulings | Courts and legal rulings | Court cases, judgments, legal rights decisions, investigations and trials of public interest | Trust in institutions; Civil liberties |
| accidents_incidents | Accidents and incidents | Transport crashes, industrial accidents, fires, product failures, rescues | Health risk; Disruption of services |
| cyber_privacy | Cyber security and privacy | Hacks, data breaches, surveillance, online fraud, privacy law | Cyber insecurity; Civil liberties; Disruption of services |
| war_conflict | War and armed conflict | Wars, invasions, ceasefires, attacks on civilians, conflict casualties | War and terror; Energy cost and supply; Food insecurity |
| terrorism_violence | Terrorism and political violence | Terror attacks, extremism, assassination attempts and other premeditated political violence | War and terror |
| defence_weapons | Defence and weapons | Military budgets, arms, alliances, conscription, nuclear and weapons programmes | War and terror; Fiscal strain |
| diplomacy_treaties | Diplomacy and treaties | Summits, treaties, alliances, global institutions, relations between states | War and terror |
| sanctions_aid | Sanctions and aid | Sanctions, embargoes, foreign aid, humanitarian relief, development finance | Supply chain strain; Energy cost and supply; Mineral and material scarcity |
| migration_refugees | Migration and refugees | Immigration rules, border control, asylum, refugee flows, integration | Migration flow; Social division |
| elections_politics | Elections and political parties | Elections, campaigns, polls, party politics, leaders' standing, coalitions | Trust in institutions; Social division; Civil unrest |
| legislation_regulation | Laws and regulation | New laws, rules, bans, licensing, regulation of industries | Civil liberties |
| governance_corruption | Government performance and corruption | Scandals, corruption, public services failing and institutional failure | Trust in institutions; Public service quality |
| civil_rights_discrimination | Civil rights and discrimination | Equality, minority and gender rights, freedom of speech, discrimination | Civil liberties; Social division |
| protest_movements | Protests and social movements | Demonstrations, activism, petitions, boycotts, riots and civil unrest | Civil unrest |
| family_demographics | Family and demographics | Births, marriage, childcare, ageing, population change, family policy | Migration flow; Community strength |
| religion_identity | Religion and identity | Religion, culture clashes, nationalism, community identity, social values | Social division; Community strength |
| education_schools | Schools and universities | Schools, universities, fees, exams, teachers, training and skills programmes | Public service quality; Skills and education level |
| research_space | Science and space | Scientific discoveries, research funding, space missions, physics, biology (non-medical) | Information reliability; Technology adoption |
| technology_consumer | Digital technology and consumer tech | Gadgets, internet services, software, telecoms, platforms' products and rules | Technology adoption |
| media_information | Media and information | News media, misinformation, censorship, social media content, press freedom | Information reliability |
| consumer_retail | Consumer goods and retail | Shops, product launches, recalls, consumer protection, brand fortunes at household level | Prices; Health risk |
| business_corporate | Business and companies | What one company does: deals, mergers, leadership, lawsuits, earnings | Industrial output; Cyber insecurity |
| mining_materials | Minerals and materials | Metals, rare earths, mining and industrial raw materials | Mineral and material scarcity; Supply chain strain |
| culture_leisure | Culture, sport and leisure | Film, music, art, celebrities, books, games, sport, tournaments, mass events, holidays, hospitality and the leisure industry | Community strength |
| other | Other | None of the above fits at all (review bucket, never counted) |  |


## E. Person states (47)

Kinds: `trait` (fixed), `derived` (computed from others), `state` (moved by conditions).

| id | name | kind | meaning |
|---|---|---|---|
| tech_comfort | Tech comfort | trait | Ease learning and using new apps and devices. |
| price_attention | Price attention | state | How closely the person watches costs and small fees. |
| privacy_stance | Privacy stance | trait | Reluctance to hand personal data to companies. |
| social_ease | Social ease | trait | Comfort dealing with people they do not know. |
| novelty_seeking | Novelty seeking | trait | Readiness to try new things early. |
| habit_inertia | Habit and inertia | trait | Tendency to stay with existing choices. |
| loss_aversion | Loss aversion | trait | How much losses weigh against gains. |
| conscientiousness | Conscientiousness and planning | trait | Tendency to plan ahead, follow through and control impulses. |
| emotional_reactivity | Emotional reactivity | trait | How strongly and how easily the person feels worry, fear or upset. |
| risk_tolerance | Risk tolerance | trait | Willingness to accept uncertain outcomes for a chance of gain. |
| patience | Patience | trait | How much the person values later rewards over sooner ones. |
| fairness_concern | Fairness concern | trait | How strongly the person reacts to unequal or unfair treatment of themselves or others. |
| status_concern | Status concern | trait | How much the person cares how their possessions and position compare with others'. |
| conformity | Social influence susceptibility | trait | How much the person follows what peers and crowds do or say. |
| econ_orientation | Economic orientation | trait | Position on how far government should manage the economy and redistribute (left to right). |
| cultural_orientation | Cultural orientation | trait | Position on tradition, authority and social change (traditional to liberal). |
| group_identity | Group identity strength | trait | How strongly the person identifies with a nation, community or group. |
| religiosity | Religiosity | trait | How central religious belief and practice are to the person's life. |
| prosociality | Prosociality (willingness to help others) | trait | Readiness to help others at a cost to oneself and to give them the benefit of the doubt. |
| environmental_values | Environmental values | trait | How much the person cares about nature and climate in everyday choices. |
| health_orientation | Health orientation | trait | How much the person believes their own actions protect their health and acts on it. |
| financial_literacy | Financial literacy | derived | How well the person understands interest, inflation and risk. |
| financial_stress | Financial stress | state | Felt strain on the household budget. |
| liquidity | Liquidity | state | Cash buffer and steadiness of income: can the person absorb a shock? |
| debt_burden | Debt burden | state | Share of income going to repaying debt. |
| job_worry | Job insecurity worry | state | How likely the person thinks it is that they lose work or income soon. |
| time_pressure | Time pressure | state | How little spare time the person has. |
| optimism | Optimism | state | How hopeful the person feels about their own money and life over the next year, including whether now feels a good time for big purchases. |
| safety_concern | Safety concern | state | How threatened the person feels in daily life. |
| wellbeing | Well-being | state | Day-to-day mood and energy, including feeling rested rather than worn out. |
| loneliness | Loneliness | state | Felt lack of company and support. |
| job_satisfaction | Job satisfaction and autonomy | state | How fulfilling, fairly paid and self-directed the person finds their work. |
| perceived_health_threat | Perceived health threat | state | How likely and how serious the person thinks illness is for themselves. |
| health_status | Health status | derived | The person's own current health and any long-term condition. |
| institutional_trust | Institutional trust | state | How much the person believes institutions act honestly. |
| interpersonal_trust | Trust in other people | state | Belief that most people can be trusted. |
| media_trust | Trust in news media | state | How much the person believes the news they see is accurate. |
| political_efficacy | Political efficacy | state | Belief that one's own action can change what authorities do. |
| grievance | Felt grievance | state | Current sense of being treated unfairly or left behind. |
| news_attention | News attention | state | How much of the person's time and focus is spent following news. |
| tenure | Tenure (rent or own) | derived | Rents (0) or owns (1) the home. Read from demographics, not asked. |
| housing_burden | Housing burden | state | Share of income spent on rent or mortgage. |
| life_stage | Life stage and household | derived | Age band, children and caring duties; higher means older with more caring duties. Read from demographics, not asked. |
| education_skills | Education and skills | derived | Highest education and how in-demand the person's skills are. |
| digital_access | Digital access | derived | Quality of the person's connection and devices. |
| hazard_exposure | Local hazard exposure | derived | How exposed the person's home and work are to floods, fires, storms or quakes. |
| car_dependence | Car dependence | derived | How much the person relies on a car for daily life (more likely in rural or spread-out places). |


## F. Decisions (20)

Baseline rate = how often the opportunity arises; bias = starting lean; stakes 1 to 5 = how big one act is (1 small and easy to reverse, 5 life-changing).

| id | name | baseline rate | bias | stakes | plain question |
|---|---|---|---|---|---|
| spend | Spend (vs save) | 0.2 | 0.0 | 1 | Will this person spend more freely rather than hold money back? |
| buy_new | Buy something new | 0.05 | -0.5 | 2 | Will this person buy a major new item (not a routine purchase)? |
| subscribe | Subscribe or commit | 0.02 | -0.8 | 2 | Will this person sign up to a recurring or long contract? |
| travel | Travel | 0.01 | -0.3 | 3 | Will this person take a trip? |
| change_work | Change work | 0.002 | -1.5 | 4 | Will this person change job, hours or employer? |
| move | Move home | 0.001 | -2.2 | 5 | Will this person move home (within or between places)? |
| switch_brand | Switch brand or provider | 0.01 | -1.0 | 2 | Will this person switch to a different brand or provider? |
| share | Share or engage publicly | 0.1 | -0.5 | 2 | Will this person post, share or speak publicly about it? |
| vote | Vote or take party action | 0.003 | -1.5 | 2 | Will this person vote, join a party or contact an official? |
| protest | Protest or strike | 0.002 | -2.0 | 3 | Will this person join a protest, boycott or strike? |
| health_action | Take a health action | 0.03 | -0.8 | 3 | Will this person seek care, test, vaccinate or change a health habit? |
| study_train | Study or retrain | 0.005 | -1.5 | 4 | Will this person enrol in study or training? |
| family_change | Change family situation | 0.001 | -2.5 | 5 | Will this person marry, separate, have a child or take on care duties? |
| stockpile_prepare | Stockpile or prepare | 0.02 | -1.0 | 2 | Will this person stock up on supplies or buy protection or insurance? |
| start_business | Start or expand a business | 0.001 | -2.5 | 5 | Will this person start or expand a business? |
| donate_volunteer | Give, volunteer or join a group | 0.03 | -1.0 | 2 | Will this person give money or time to a cause, or join a group? |
| claim_support | Claim support | 0.005 | -1.5 | 3 | Will this person apply for benefits, aid or an entitlement? |
| borrow | Borrow (take on new debt) | 0.01 | -1.0 | 4 | Will this person take on new debt? |
| invest | Invest | 0.05 | -0.5 | 3 | Will this person put savings into shares, funds or property? |
| break_rules | Ignore official rules or guidance | 0.02 | -1.5 | 3 | Will this person ignore official rules or guidance? |


## G1. Condition to condition ties (12)

| from | to | strength | why |
|---|---|---|---|
| Energy cost and supply | Prices | 0.5 | fuel and power costs pass into everyday prices |
| Supply chain strain | Prices | 0.5 | shortages and delays raise shelf prices |
| Mineral and material scarcity | Supply chain strain | 0.5 | scarce raw materials strain supply |
| Land degradation | Food insecurity | 0.2 | less usable land means less food |
| Biodiversity loss | Food insecurity | 0.2 | lost fish stocks and pollinators cut food |
| Food insecurity | Prices | 0.2 | food shortage lifts food prices |
| Water stress | Health risk | 0.2 | unsafe water raises illness |
| Infrastructure condition | Disruption of services | -0.5 | better repair means fewer outages and delays |
| Industrial output | Job security | 0.5 | more production means steadier jobs |
| Fiscal strain | Public service quality | -0.5 | budget pressure cuts services |
| Market volatility | Asset values | -0.5 | wild swings tend to drag values down |
| Cyber insecurity | Disruption of services | 0.5 | breaches and outages interrupt services |


## G2. Condition to person state (53)

Positive strength means the state rises when the condition rises.

| person state | condition | strength | why | moderated by |
|---|---|---|---|---|
| Financial stress | Prices | 0.5 | prices rise faster than the budget |  |
| Financial stress | Pay growth | -0.5 | faster pay eases the budget |  |
| Financial stress | Job security | -0.5 | secure work eases the budget |  |
| Financial stress | Housing cost | 0.5 | rent or mortgage is the largest bill (crosses housing into money) | tenure |
| Liquidity | Prices | -0.5 | higher prices eat savings |  |
| Liquidity | Pay growth | 0.5 |  |  |
| Liquidity | Job security | 0.5 |  |  |
| Liquidity | Asset values | 0.5 | owners hold savings in assets | tenure |
| Debt burden | Borrowing cost and credit access | 0.5 | costlier loans raise repayments |  |
| Debt burden | Private debt | 0.8 | identity-like: the person-level version of the place debt level |  |
| Housing burden | Housing cost | 0.8 | identity-like: rent or price rise is this person's burden (renters most) | tenure |
| Housing burden | Borrowing cost and credit access | 0.5 | mortgage payments follow loan costs (mortgagors) | tenure |
| Price attention | Prices | 0.5 |  |  |
| Price attention | Energy cost and supply | 0.5 | fuel and bills are watched closely |  |
| Job insecurity worry | Job security | -0.8 | identity-like: secure jobs mean less worry |  |
| Job insecurity worry | Technology adoption | 0.2 | automation fear (crosses tech into work) |  |
| Job insecurity worry | Industrial output | -0.2 | more output means less layoff fear |  |
| Optimism | Job security | 0.5 |  |  |
| Optimism | Prices | -0.5 | rising prices dampen hope |  |
| Optimism | Asset values | 0.5 |  |  |
| Optimism | War and terror | -0.5 | conflict dims outlook (crosses security into mood) |  |
| Time pressure | Disruption of services | 0.5 | delays and outages eat spare time |  |
| Time pressure | Care strain | 0.5 | waiting for care costs time (crosses health into time) | life_stage |
| Safety concern | Crime | 0.8 | identity-like: crime nearby raises felt threat |  |
| Safety concern | War and terror | 0.5 |  |  |
| Safety concern | Civil unrest | 0.5 |  |  |
| Safety concern | Climate stress | 0.2 | storm and heat hazard raises felt threat (crosses climate into safety) |  |
| Well-being | Mental distress | -0.8 | identity-like: more distress means lower mood |  |
| Well-being | Disruption of services | -0.2 | upheaval wears people down |  |
| Well-being | Community strength | 0.2 |  |  |
| Loneliness | Community strength | -0.5 | stronger community means less loneliness |  |
| Loneliness | Health risk | 0.2 | illness risk keeps people home (crosses health into social) |  |
| Job satisfaction and autonomy | Pay growth | 0.2 |  |  |
| Job satisfaction and autonomy | Job security | 0.2 |  |  |
| Perceived health threat | Health risk | 0.8 | identity-like: outbreak risk raises felt threat |  |
| Perceived health threat | Care strain | 0.2 | strained care raises worry |  |
| Perceived health threat | Air pollution | 0.2 | dirty air raises health worry (crosses environment into health) |  |
| Institutional trust | Trust in institutions | 0.8 | identity-like: personal version of the place trust level |  |
| Institutional trust | Public service quality | 0.5 |  |  |
| Institutional trust | Social division | -0.2 | division erodes trust in shared institutions |  |
| Trust in other people | Social division | -0.5 | division lowers trust in others |  |
| Trust in other people | Crime | -0.2 | crime lowers trust in strangers |  |
| Trust in other people | Community strength | 0.5 |  |  |
| Trust in news media | Information reliability | 0.8 | identity-like: reliable news earns trust |  |
| Political efficacy | Civil liberties | 0.5 |  |  |
| Political efficacy | Trust in institutions | 0.2 |  |  |
| Felt grievance | Economic inequality | 0.5 | a wider gap breeds felt unfairness |  |
| Felt grievance | Social division | 0.5 |  |  |
| Felt grievance | Public service quality | -0.5 | better services reduce feeling left behind |  |
| Felt grievance | Migration flow | 0.2 | contested: politically disputed link, depends on the person's views | cultural_orientation |
| News attention | News overload | 0.5 |  |  |
| News attention | War and terror | 0.5 | crisis draws attention (crosses security into media habits) |  |
| Job insecurity worry | Skills and education level | -0.5 | better skills mean more employable people and less job worry |  |


## G3. Person state to decision (109)

Positive weight raises the chance of the act when the state is higher.

| decision | person state | weight | why |
|---|---|---|---|
| Spend (vs save) | Financial stress | -0.8 | money strain forces cutbacks |
| Spend (vs save) | Optimism | 0.5 |  |
| Spend (vs save) | Liquidity | 0.5 |  |
| Spend (vs save) | Price attention | -0.5 | price watchers hold back |
| Spend (vs save) | Patience | -0.2 | patient people spend less now |
| Spend (vs save) | Status concern | 0.2 |  |
| Buy something new | Optimism | 0.5 |  |
| Buy something new | Financial stress | -0.5 | money strain delays big buys |
| Buy something new | Novelty seeking | 0.5 |  |
| Buy something new | Car dependence | 0.2 | cars are the big new purchase |
| Buy something new | Status concern | 0.2 |  |
| Subscribe or commit | Price attention | -0.5 | fee watchers avoid commitments |
| Subscribe or commit | Habit and inertia | 0.5 |  |
| Subscribe or commit | Tech comfort | 0.5 |  |
| Subscribe or commit | Privacy stance | -0.5 | data-wary people avoid sign-ups |
| Subscribe or commit | Digital access | 0.5 |  |
| Travel | Safety concern | -0.8 | felt danger stops trips |
| Travel | Perceived health threat | -0.5 | illness worry stops trips |
| Travel | Time pressure | -0.5 | no spare time |
| Travel | Environmental values | -0.2 | cares about flying and driving emissions |
| Travel | Well-being | 0.2 |  |
| Change work | Job satisfaction and autonomy | -0.8 | unhappy workers leave |
| Change work | Risk tolerance | 0.5 |  |
| Change work | Life stage and household | -0.5 | older with more duties means fewer job moves |
| Change work | Novelty seeking | 0.5 |  |
| Change work | Job insecurity worry | 0.2 | insecure workers look elsewhere |
| Move home | Housing burden | 0.5 |  |
| Move home | Tenure (rent or own) | -0.5 | owners move less than renters |
| Move home | Life stage and household | -0.5 | older with more duties means fewer moves |
| Move home | Safety concern | 0.5 |  |
| Move home | Local hazard exposure | 0.5 |  |
| Move home | Habit and inertia | -0.5 | settled habits keep people put |
| Switch brand or provider | Price attention | 0.5 |  |
| Switch brand or provider | Habit and inertia | -0.8 | inertia blocks switching |
| Switch brand or provider | Novelty seeking | 0.5 |  |
| Switch brand or provider | Tech comfort | 0.5 |  |
| Share or engage publicly | News attention | 0.5 |  |
| Share or engage publicly | Social ease | 0.5 |  |
| Share or engage publicly | Felt grievance | 0.5 |  |
| Share or engage publicly | Emotional reactivity | 0.5 |  |
| Share or engage publicly | Social influence susceptibility | 0.2 |  |
| Share or engage publicly | Privacy stance | -0.5 | private people share less |
| Invest | Liquidity | 0.8 | needs spare money to invest |
| Invest | Optimism | 0.5 |  |
| Invest | Risk tolerance | 0.5 |  |
| Invest | Financial literacy | 0.5 |  |
| Invest | Loss aversion | -0.5 | loss-averse people avoid investing |
| Invest | Patience | 0.5 |  |
| Borrow (take on new debt) | Debt burden | -0.5 | heavy debt blocks new borrowing |
| Borrow (take on new debt) | Financial stress | 0.5 |  |
| Borrow (take on new debt) | Patience | -0.2 | impatient people borrow more |
| Borrow (take on new debt) | Housing burden | 0.2 |  |
| Borrow (take on new debt) | Status concern | 0.2 |  |
| Borrow (take on new debt) | Loss aversion | -0.5 | loss-averse people avoid debt |
| Vote or take party action | Political efficacy | 0.8 | people who think it matters vote |
| Vote or take party action | Felt grievance | 0.5 |  |
| Vote or take party action | News attention | 0.5 |  |
| Vote or take party action | Group identity strength | 0.2 | strong group identity raises turnout |
| Vote or take party action | Economic orientation | 0.2 | contested: direction depends on the party mix, weak guess |
| Protest or strike | Felt grievance | 0.8 | felt unfairness drives protest |
| Protest or strike | Political efficacy | 0.5 |  |
| Protest or strike | Institutional trust | -0.5 | distrust pushes people to the streets |
| Protest or strike | Fairness concern | 0.5 |  |
| Protest or strike | Social ease | 0.2 |  |
| Protest or strike | Emotional reactivity | 0.2 |  |
| Take a health action | Perceived health threat | 0.8 | felt threat triggers action |
| Take a health action | Health orientation | 0.8 | people who believe in prevention act |
| Take a health action | Health status | -0.5 | worse health means more care sought |
| Take a health action | Conscientiousness and planning | 0.2 |  |
| Take a health action | Trust in news media | 0.2 |  |
| Take a health action | Institutional trust | 0.2 |  |
| Study or retrain | Job insecurity worry | 0.5 |  |
| Study or retrain | Education and skills | -0.5 | lower skills gain more from training |
| Study or retrain | Patience | 0.5 |  |
| Study or retrain | Conscientiousness and planning | 0.5 |  |
| Study or retrain | Life stage and household | -0.5 | younger people study more |
| Study or retrain | Time pressure | -0.2 | no spare time |
| Change family situation | Optimism | 0.5 |  |
| Change family situation | Life stage and household | 0.2 | guess: mid-life stage most likely to marry or have children |
| Change family situation | Housing burden | -0.5 | housing strain delays family change |
| Change family situation | Religiosity | 0.5 | religious people marry and have children more often |
| Change family situation | Well-being | 0.2 |  |
| Stockpile or prepare | Safety concern | 0.5 |  |
| Stockpile or prepare | Perceived health threat | 0.5 |  |
| Stockpile or prepare | Local hazard exposure | 0.5 |  |
| Stockpile or prepare | Emotional reactivity | 0.5 |  |
| Stockpile or prepare | Loss aversion | 0.5 |  |
| Start or expand a business | Risk tolerance | 0.5 |  |
| Start or expand a business | Liquidity | 0.5 |  |
| Start or expand a business | Education and skills | 0.5 |  |
| Start or expand a business | Novelty seeking | 0.5 |  |
| Start or expand a business | Job insecurity worry | 0.2 |  |
| Give, volunteer or join a group | Prosociality (willingness to help others) | 0.8 | helping others is the trait itself |
| Give, volunteer or join a group | Religiosity | 0.5 | religious communities give and volunteer more |
| Give, volunteer or join a group | Time pressure | -0.5 | no spare time |
| Give, volunteer or join a group | Loneliness | 0.2 | contested: lonely people may seek a group or withdraw |
| Give, volunteer or join a group | Trust in other people | 0.5 |  |
| Give, volunteer or join a group | Social ease | 0.2 |  |
| Claim support | Financial stress | 0.5 |  |
| Claim support | Liquidity | -0.5 | no buffer means asking for help |
| Claim support | Job insecurity worry | 0.2 |  |
| Claim support | Institutional trust | 0.2 |  |
| Claim support | Health status | -0.2 | poor health raises need |
| Claim support | Digital access | 0.2 |  |
| Ignore official rules or guidance | Institutional trust | -0.5 | distrust weakens the duty to comply |
| Ignore official rules or guidance | Trust in news media | -0.5 | distrusted official messaging is ignored |
| Ignore official rules or guidance | Felt grievance | 0.5 |  |
| Ignore official rules or guidance | Cultural orientation | -0.2 | contested: authority-respecting pole of the trait lowers it |
| Ignore official rules or guidance | Conscientiousness and planning | -0.5 | rule-followers comply |


## I. Countries (100)

Starting facts only (population in millions, median age, income index, urban share). Source: UN World Population Prospects 2024 and World Bank indicators.

| id | name | region | population m | median age | income | urban share |
|---|---|---|---|---|---|---|
| ind | India | South Asia | 1450.9 | 28.4 | 7.02 | 0.357 |
| chn | China | East Asia & Pacific | 1419.3 | 39.6 | 17.58 | 0.663 |
| usa | United States | North America | 345.4 | 38.3 | 54.0 | 0.802 |
| idn | Indonesia | East Asia & Pacific | 283.5 | 30.1 | 10.62 | 0.594 |
| pak | Pakistan | Middle East, North Africa, Afghanistan & Pakistan | 251.3 | 20.4 | 3.96 | 0.395 |
| nga | Nigeria | Sub-Saharan Africa | 232.7 | 17.9 | 5.7 | 0.638 |
| bra | Brazil | Latin America & Caribbean | 212.0 | 34.4 | 14.04 | 0.882 |
| bgd | Bangladesh | South Asia | 173.6 | 25.7 | 6.12 | 0.332 |
| rus | Russia | Europe & Central Asia | 144.8 | 39.9 | 29.76 | 0.753 |
| eth | Ethiopia | Sub-Saharan Africa | 132.1 | 18.9 | 2.16 | 0.241 |
| mex | Mexico | Latin America & Caribbean | 130.9 | 29.3 | 15.54 | 0.8 |
| jpn | Japan | East Asia & Pacific | 123.8 | 49.4 | 33.24 | 0.923 |
| egy | Egypt | Middle East, North Africa, Afghanistan & Pakistan | 116.5 | 24.3 | 12.12 | 0.429 |
| phl | Philippines | East Asia & Pacific | 115.8 | 25.7 | 7.56 | 0.558 |
| cod | Democratic Republic of the Congo | Sub-Saharan Africa | 109.3 | 15.8 | 1.14 | 0.451 |
| vnm | Vietnam | East Asia & Pacific | 101.0 | 32.9 | 10.86 | 0.388 |
| irn | Iran | Middle East, North Africa, Afghanistan & Pakistan | 91.6 | 33.4 | 11.82 | 0.774 |
| tur | Türkiye | Europe & Central Asia | 87.5 | 33.0 | 27.18 | 0.895 |
| deu | Germany | Europe & Central Asia | 84.6 | 45.3 | 45.24 | 0.821 |
| tha | Thailand | East Asia & Pacific | 71.7 | 40.1 | 15.78 | 0.628 |
| gbr | United Kingdom | Europe & Central Asia | 69.1 | 40.0 | 38.76 | 0.833 |
| tza | Tanzania | Sub-Saharan Africa | 68.6 | 17.4 | 2.7 | 0.369 |
| fra | France | Europe & Central Asia | 66.5 | 42.1 | 38.4 | 0.788 |
| zaf | South Africa | Sub-Saharan Africa | 64.0 | 28.5 | 9.54 | 0.638 |
| ita | Italy | Europe & Central Asia | 59.3 | 47.8 | 37.68 | 0.697 |
| ken | Kenya | Sub-Saharan Africa | 56.4 | 19.8 | 4.2 | 0.322 |
| mmr | Myanmar | East Asia & Pacific | 54.5 | 29.8 | 3.6 | 0.306 |
| col | Colombia | Latin America & Caribbean | 52.9 | 32.0 | 13.56 | 0.788 |
| kor | South Korea | East Asia & Pacific | 51.7 | 45.0 | 37.86 | 0.812 |
| sdn | Sudan | Sub-Saharan Africa | 50.4 | 18.4 | 1.32 | 0.349 |
| uga | Uganda | Sub-Saharan Africa | 50.0 | 16.7 | 2.1 | 0.319 |
| esp | Spain | Europe & Central Asia | 47.9 | 45.4 | 35.94 | 0.805 |
| dza | Algeria | Middle East, North Africa, Afghanistan & Pakistan | 46.8 | 28.4 | 11.16 | 0.758 |
| irq | Iraq | Middle East, North Africa, Afghanistan & Pakistan | 46.0 | 20.6 | 8.58 | 0.699 |
| arg | Argentina | Latin America & Caribbean | 45.7 | 32.5 | 19.56 | 0.924 |
| afg | Afghanistan | Middle East, North Africa, Afghanistan & Pakistan | 42.6 | 17.1 | 1.32 | 0.259 |
| yem | Yemen | Middle East, North Africa, Afghanistan & Pakistan | 40.6 | 18.3 | 1.92 | 0.37 |
| can | Canada | North America | 39.7 | 40.5 | 40.02 | 0.829 |
| pol | Poland | Europe & Central Asia | 38.5 | 41.8 | 32.58 | 0.601 |
| mar | Morocco | Middle East, North Africa, Afghanistan & Pakistan | 38.1 | 29.5 | 6.66 | 0.631 |
| ago | Angola | Sub-Saharan Africa | 37.9 | 16.5 | 6.18 | 0.715 |
| ukr | Ukraine | Europe & Central Asia | 37.9 | 42.1 | 11.34 | 0.696 |
| uzb | Uzbekistan | Europe & Central Asia | 36.4 | 27.0 | 8.16 | 0.51 |
| mys | Malaysia | East Asia & Pacific | 35.6 | 30.5 | 24.9 | 0.774 |
| moz | Mozambique | Sub-Saharan Africa | 34.6 | 16.4 | 1.02 | 0.372 |
| gha | Ghana | Sub-Saharan Africa | 34.4 | 21.1 | 5.16 | 0.589 |
| per | Peru | Latin America & Caribbean | 34.2 | 29.8 | 11.28 | 0.856 |
| sau | Saudi Arabia | Middle East, North Africa, Afghanistan & Pakistan | 34.0 | 29.6 | 44.28 | 0.846 |
| mdg | Madagascar | Sub-Saharan Africa | 32.0 | 19.0 | 1.2 | 0.329 |
| civ | Ivory Coast | Sub-Saharan Africa | 31.9 | 18.2 | 4.92 | 0.545 |
| npl | Nepal | South Asia | 29.7 | 25.0 | 3.72 | 0.67 |
| cmr | Cameroon | Sub-Saharan Africa | 29.1 | 17.9 | 3.48 | 0.557 |
| ven | Venezuela | Latin America & Caribbean | 28.4 | 29.2 | 12.78 | 0.893 |
| ner | Niger | Sub-Saharan Africa | 27.0 | 15.4 | 1.32 | 0.184 |
| aus | Australia | East Asia & Pacific | 26.7 | 38.0 | 43.14 | 0.877 |
| prk | North Korea | East Asia & Pacific | 26.5 | 36.3 | 9.12 | 0.642 |
| syr | Syria | Middle East, North Africa, Afghanistan & Pakistan | 24.7 | 22.8 | 2.94 | 0.721 |
| mli | Mali | Sub-Saharan Africa | 24.5 | 15.6 | 2.1 | 0.322 |
| bfa | Burkina Faso | Sub-Saharan Africa | 23.5 | 17.5 | 1.86 | 0.289 |
| twn | Taiwan | East Asia & Pacific | 23.2 | 44.2 | 9.12 | 0.628 |
| lka | Sri Lanka | South Asia | 23.1 | 33.1 | 10.26 | 0.205 |
| mwi | Malawi | Sub-Saharan Africa | 21.7 | 17.8 | 1.14 | 0.176 |
| zmb | Zambia | Sub-Saharan Africa | 21.3 | 17.7 | 2.64 | 0.459 |
| kaz | Kazakhstan | Europe & Central Asia | 20.6 | 29.6 | 26.58 | 0.624 |
| tcd | Chad | Sub-Saharan Africa | 20.3 | 15.7 | 1.74 | 0.276 |
| chl | Chile | Latin America & Caribbean | 19.8 | 36.4 | 22.68 | 0.892 |
| rou | Romania | Europe & Central Asia | 19.0 | 42.9 | 30.54 | 0.522 |
| som | Somalia | Sub-Saharan Africa | 19.0 | 15.5 | 0.96 | 0.551 |
| sen | Senegal | Sub-Saharan Africa | 18.5 | 19.4 | 3.3 | 0.558 |
| gtm | Guatemala | Latin America & Caribbean | 18.4 | 23.0 | 9.12 | 0.563 |
| nld | Netherlands | Europe & Central Asia | 18.2 | 41.4 | 52.38 | 0.959 |
| ecu | Ecuador | Latin America & Caribbean | 18.1 | 28.8 | 10.08 | 0.634 |
| khm | Cambodia | East Asia & Pacific | 17.6 | 26.0 | 5.1 | 0.411 |
| zwe | Zimbabwe | Sub-Saharan Africa | 16.6 | 18.0 | 3.9 | 0.405 |
| gin | Guinea | Sub-Saharan Africa | 14.8 | 18.1 | 2.94 | 0.385 |
| ben | Benin | Sub-Saharan Africa | 14.5 | 17.9 | 2.88 | 0.534 |
| rwa | Rwanda | Sub-Saharan Africa | 14.3 | 19.7 | 2.52 | 0.309 |
| bdi | Burundi | Sub-Saharan Africa | 14.0 | 16.1 | 0.72 | 0.257 |
| bol | Bolivia | Latin America & Caribbean | 12.4 | 24.9 | 7.74 | 0.716 |
| tun | Tunisia | Middle East, North Africa, Afghanistan & Pakistan | 12.3 | 32.5 | 9.12 | 0.707 |
| ssd | South Sudan | Sub-Saharan Africa | 11.9 | 18.3 | 0.72 | 0.217 |
| hti | Haiti | Latin America & Caribbean | 11.8 | 23.8 | 1.86 | 0.556 |
| bel | Belgium | Europe & Central Asia | 11.7 | 41.7 | 44.82 | 0.877 |
| jor | Jordan | Middle East, North Africa, Afghanistan & Pakistan | 11.6 | 24.5 | 7.56 | 0.932 |
| dom | Dominican Republic | Latin America & Caribbean | 11.4 | 28.0 | 17.22 | 0.725 |
| are | United Arab Emirates | Middle East, North Africa, Afghanistan & Pakistan | 11.0 | 31.6 | 47.58 | 0.86 |
| cub | Cuba | Latin America & Caribbean | 11.0 | 41.9 | 9.12 | 0.772 |
| hnd | Honduras | Latin America & Caribbean | 10.8 | 23.9 | 4.74 | 0.593 |
| cze | Czechia | Europe & Central Asia | 10.7 | 43.2 | 36.3 | 0.729 |
| swe | Sweden | Europe & Central Asia | 10.6 | 40.1 | 43.5 | 0.891 |
| tjk | Tajikistan | Europe & Central Asia | 10.6 | 22.1 | 3.54 | 0.262 |
| png | Papua New Guinea | East Asia & Pacific | 10.6 | 22.6 | 3.12 | 0.158 |
| prt | Portugal | Europe & Central Asia | 10.4 | 46.6 | 31.86 | 0.615 |
| aze | Azerbaijan | Europe & Central Asia | 10.3 | 33.1 | 15.66 | 0.586 |
| grc | Greece | Europe & Central Asia | 10.0 | 46.3 | 27.18 | 0.792 |
| hun | Hungary | Europe & Central Asia | 9.7 | 43.6 | 29.88 | 0.707 |
| tgo | Togo | Sub-Saharan Africa | 9.5 | 18.9 | 2.46 | 0.444 |
| isr | Israel | Middle East, North Africa, Afghanistan & Pakistan | 9.4 | 29.2 | 35.82 | 0.916 |
| aut | Austria | Europe & Central Asia | 9.1 | 43.4 | 46.08 | 0.697 |
| blr | Belarus | Europe & Central Asia | 9.1 | 40.9 | 20.82 | 0.795 |
