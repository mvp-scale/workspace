# World engine ontology: topic domains (draft v1, 2026-10-05)

> **Two parts.** Everything from here to the line `PART 2` is the **current** ontology (v1), which the live engine runs. **PART 2 at the end of this file** shows the proposed enhanced version of every element (topics, conditions, person states, decisions, resources) beside what it replaces. Part 2 is a proposal and is not live.


**What this is.** The closed list of topic areas every incoming story is placed in. It answers "what is this about?". It is the first step of reading any input; the state, decision and resource classes in `ontology-draft.md` answer "what does it change?". A topic such as AI, quantum or a fertiliser is never a domain. It is an instance placed in one or more domains.

**Rules.**
1. Closed list of 14 domains plus Other. A new domain needs a written reason and a mapping to a standard.
2. Every story is placed in at least one domain. A story may carry several (a Supreme Court climate case is Government and law, and Environment and climate).
3. Other is for review: a story placed only there is logged, not dropped, and counts against coverage.
4. Backbone: the Comparative Agendas Project (CAP) major policy topics, a coding scheme used to classify government agendas, 21 major topics (names from its master codebook, opened by a reviewer: Macroeconomics, Civil Rights, Health, Agriculture, Labor, Education, Environment, Energy, Immigration, Transportation, Law and Crime, Social Welfare, Housing, Domestic Commerce, Defense, Technology, Foreign Trade, International Affairs, Government Operations, Public Lands, Culture). Our 14 are a regrouping of those 21. Every CAP topic maps to at least one domain. **Business and companies is OUR extension** (CAP is topic-based, not actor-based).

## The domains

| # | Domain | Definition (what is placed here) | CAP topics regrouped | State classes it usually changes | Typical institutional decisions | Resources it draws on |
|---|---|---|---|---|---|---|
| 1 | Economy, finance and housing | Prices, inflation, interest rates, markets, banking, trade, taxes, public budgets, household finances, home prices and rents | Macroeconomics, Housing, Domestic Commerce, Foreign Trade | Income and wealth; Housing; Energy and prices | Regulate or permit; provide or fund | Financial |
| 2 | Work and labour | Employment, wages, unions, strikes, working conditions, job automation, pensions | Labor | Work and job quality; Work-life balance | Mobilise or protest; regulate or permit | Human |
| 3 | Energy, transport and natural resources | Energy and fuel, power grids, transport and supply chains, water, farming, food supply, minerals, land use | Energy, Transportation, Agriculture, Public Lands | Energy and prices; Environmental quality | Provide or fund; invest or adopt | Water; land and food; energy and minerals; produced |
| 4 | Environment and climate | Climate change, pollution, nature, weather disasters, environmental protection | Environment | Environmental quality | Regulate or permit; investigate; demand or condemn | Water; land and food; legitimacy |
| 5 | Health and medicine | Illness, epidemics, medicines, vaccines, health systems, mental health, drugs | Health | Health | Regulate or permit; provide or fund; investigate | Human; financial |
| 6 | Safety and crime | Crime, policing, accidents, personal safety, criminal justice | Law and Crime (crime part) | Safety | Investigate; mobilise or protest | Social; legitimacy |
| 7 | Conflict and security | War, terrorism, armed forces, weapons, alliances, national security | Defense | Conflict | Threaten or posture; use force; withdraw or sanction | Produced; financial; legitimacy |
| 8 | Government, law and courts | Elections, legislation, regulation, courts and rulings, civil rights, public institutions and officials | Government Operations, Civil Rights, Law and Crime (courts part) | Civic engagement and governance | Regulate or permit; investigate; concede or comply; speak or signal | Legitimacy; attention |
| 9 | International relations and migration | Diplomacy, treaties, sanctions, aid, global institutions, immigration, refugees | International Affairs, Immigration | Conflict; Civic engagement and governance | Signal cooperation; provide or fund; withdraw or sanction | Financial; legitimacy; human |
| 10 | Society, community and identity | Community and family life, social welfare, inequality, religion, identity, discrimination, social movements | Social Welfare, Civil Rights | Social connections; Subjective well-being | Mobilise or protest; speak or signal | Social; attention |
| 11 | Culture, sport and leisure | Arts, entertainment, celebrities, sport, tourism, travel, leisure | Culture | Subjective well-being; Work-life balance | Speak or signal | Attention |
| 12 | Technology, science and information | Technology, AI, computing, science, space, research, media, social media, data | Technology | Technology, information and change; Knowledge and skills | Regulate or permit; invest or adopt | Knowledge and information; produced (including compute); attention |
| 13 | Education and knowledge | Schools, universities, training, skills, research funding | Education | Knowledge and skills | Provide or fund; regulate or permit | Human; knowledge and information |
| 14 | Business and companies (EXTENSION) | What a specific company does: products, deals, mergers, leadership, lawsuits, earnings | Domestic Commerce (company level) | depends on the story | Invest, launch or adopt | Financial; produced |
| - | Other | None of the above fits; logged for review | none | none | none | none |

The state, decision and resource columns are our judgement (status: guess). They name classes from `ontology-draft.md`.

## Coverage test (inputs written by me, answers by the local model)

44 one-line stories on deliberately different topics (AI regulation, quantum, a pandemic, an election, the World Cup, Mars, a crypto collapse, a strike, a hurricane, a failed harvest, a bank run, a data breach, a vaccine, a rate cut, refugees, a church scandal, a celebrity wedding, a museum theft, tuition, a self-driving crash, cartel violence, a nuclear treaty, a port strike, minimum wage, home prices, solar subsidies, an oil spill, a school shooting, doping, pensions, an antitrust suit, tariffs, a heat wave, AI replacing jobs, a deepfake, an airline merger, a plane crash, a tsunami, famine, a protest ban ruling, a phone launch, an interfaith prayer, a viral recipe, a bakery award).

Result: all 44 were placed; none landed in Other; none had a top choice under 50%. Weaker placements: a viral recipe went to Technology (80%) where Culture fits better; a bakery award went to Business (65%); a port strike split between Work (69%) and Energy and transport (24%). This tests the list's reach, not its accuracy; the expected labels were not independently set.

## What this does not cover

- Topics with no policy angle at all (purely personal events) fall to Culture, Society or Other.
- Non-text input, other languages (untested), and the size and direction of an effect (that is the state, decision and resource step).
- The CAP names above came from a reviewer's reading of the codebook; I have not opened it myself, so exact names may differ slightly.

---

# PART 2: Proposed enhancement (v2) — NOT LIVE

**Status.** This part shows what each element of the ontology becomes if the proposal is adopted. The tables above are the **current** (v1) ontology and are what the live engine runs. Nothing in this part is wired into the engine or the page yet. All links and weights below are **guesses** until fitted, and every source in the expansion work is from memory (none opened this session). It was written by three drafting agents, reviewed by a fourth, then merged and machine-checked (`probes/persona/validate_v2.py`, files in `probes/persona/rules_v2/`).

## At a glance

| Layer | Now (v1) | Proposed (v2) | Kept as is | New | Renamed, split or merged |
|---|---|---|---|---|---|
| Topics (this document's domains) | 14 | 48 | 4 | 0 | 45 |
| Conditions (world levels) | 16 | 38 | 12 | 18 | 8 |
| Person states | 15 | 47 | 15 | 32 | 0 |
| Decisions | 8 | 20 | 8 | 12 | 0 |
| Resources (the building blocks) | 10 | 26 | 4 | 1 | 21 |

Links between layers: topic→condition 99, condition→condition 12 (a new step), condition→person state 52, person state→decision 109, **272 in total** (v1 has about 183, and v1 topics had no links to conditions at all). Cap 375. Resources are not linked by hand: each condition names the one resource it is a level of, and a topic reaches resources through its conditions.

## What each layer is (the test every item had to pass)

| Layer | What it is | What it is not |
|---|---|---|
| Resource | A stock that can be held, used up, built or damaged (a noun). The shared building blocks: every other layer points at them. | An event, a feeling, a price, a policy. |
| Condition | A measurable level of one resource or system, with a clear meaning for up and down. | A one-off event, an opinion, one named statistic. |
| Topic | What a story is about. A label for routing; it holds no number. | A state. |
| Person state | A quantity about one person that helps predict what they do: a fixed trait, a state that moves, or something set by their circumstances. | Anything that cannot affect a decision, or just copies a condition. |
| Decision | A class of action a person may take (a verb phrase). | A product, a brand, a one-off act. |

Rule applied throughout: a named thing (a brand, a country, one event) belongs below this ontology, not in it; a node must be reachable from the layer above or able to change the layer below.

## 1. Resources: 10 → 26

**Why.** The old ten were too coarse to point conditions at, and they fed nothing downstream. Now every condition names exactly one resource, and every resource has at least one condition. Only Water, Knowledge, Attention and Legitimacy keep their ids.

Current (v1): Water; Land and food; Energy and minerals; Produced; Financial; Human; Social; Knowledge and information; Attention; Legitimacy.

| Id | Name | What it is | Change from v1 |
|---|---|---|---|
| water | Freshwater | Usable fresh water in rivers, lakes, aquifers and supply systems. | kept |
| land_soil | Land and soil | Farmland, grazing land, forest and the soil quality that supports them. | split from land_food |
| biodiversity | Ecosystems and wildlife | Living nature: species, habitats, oceans and fish stocks. | split from land_food |
| atmosphere_climate | Air and climate | The air we breathe and the stability of the climate system. | **new** |
| primary_energy | Energy sources (fuels, sun, wind, water) | Fuels and renewable energy sources that can be used to make power and heat. | split from energy_minerals |
| minerals_materials | Minerals and materials | Metals, industrial minerals, sand and other raw materials in the ground or stockpiled. | split from energy_minerals |
| food_stock | Food supply | Harvested crops, livestock products, catch and stored food available to eat. | split from land_food |
| built_infrastructure | Built infrastructure | Roads, rail, ports, power grids, pipes, and public buildings. | split from produced |
| housing_stock | Housing stock | Homes available to live in. | split from produced |
| productive_capital | Productive capital | Factories, machines, vehicles, farms equipment and business inventories. | split from produced |
| computing_capacity | Computing and networks | Computers, data centres, communication networks and software systems. | split from produced |
| supply_networks | Trade and supply links | Working shipping, logistics and trading relationships that move goods between makers and users. | split from produced |
| monetary_credit | Money and credit | The money and lending capacity of the financial system. | split from financial |
| asset_wealth | Wealth and assets | Savings, property and shares that households and firms hold, net of the debts they owe. | split from financial |
| public_finances | Public finances | Government revenue, borrowing capacity and reserves. | split from financial |
| population | Population | The number, age mix and movement of people living in a place. | split from human |
| population_health | Population health | Physical and mental health of the people in a place. | split from human |
| care_capacity | Care capacity | Hospitals, clinics, health workers and medicines available to treat people. | split from human |
| skills | Skills and education | Learned abilities of the population. | split from human |
| labour_force | Labour | People able and available to work, and the work they hold. | split from human |
| social_trust | Social trust and cohesion | Trust between people and groups. | split from social |
| community_ties | Community ties | Local networks, clubs, volunteering and everyday help between people. | split from social |
| legitimacy | Legitimacy | The public's acceptance of an authority's right to act. | kept |
| state_capacity | State capacity and public safety | Ability of government, police, courts and armed forces to deliver services, enforce rules, keep people safe and protect rights. | split from legitimacy |
| knowledge | Knowledge and information | Recorded knowledge: research, data, records and published information. What people carry in their heads is skills. | kept |
| attention | Time and attention | The limited daily time and focus people have, including the free time left after work and care. One budget, so free time is not a separate stock. | kept |

Of the ten current resources, Water, Knowledge, Attention and Legitimacy keep their ids; the rest are split into finer ones (see the change column). Added: Population (needed for migration stories). During review, Public order was folded into State capacity (it is a level, not a stock) and Free time into Attention; neither was ever in the current list.

## 2. Conditions: 16 → 38

**Why.** Sixteen could not tell apart, for example, a food shortage from a fuel shortage from a supply-chain jam, which push people to different choices. Each is still an abstract level, not an event or an indicator name. `optimism` stops being a condition: it is a feeling, so it lives only as a person state, and the engine keeps a computed readout called `outlook`.

Current (v1): Prices and cost of living; Housing cost; Energy and fuel; Financial conditions; Job and income security; Crime and personal safety; War and terror; Health risk; Trust in institutions; Community and belonging; Social division; Technology pace; Disruption of routines; Outlook (computed); News overload; Environmental harm and climate risk.

| Id | Name | Level of (resource) | Up means | Change from v1 |
|---|---|---|---|---|
| water_stress | Water stress | water | more shortage or contamination (bad) | **new** |
| land_degradation | Land degradation | land_soil | more land lost or degraded (bad) | split from environment |
| biodiversity_loss | Biodiversity loss | biodiversity | more decline (bad) | split from environment |
| climate_stress | Climate stress | atmosphere_climate | more hazard (bad) | split from environment |
| air_pollution | Air pollution | atmosphere_climate | dirtier air (bad) | split from environment |
| energy_fuel | Energy cost and supply | primary_energy | costlier or scarcer (bad) | kept |
| mineral_scarcity | Mineral and material scarcity | minerals_materials | scarcer or costlier (bad) | **new** |
| food_insecurity | Food insecurity | food_stock | more people short of food (bad) | **new** |
| housing_cost | Housing cost | housing_stock | costlier (bad) | kept |
| infrastructure_condition | Infrastructure condition | built_infrastructure | better repair (good) | **new** |
| disruption | Disruption of services | built_infrastructure | more interruptions (bad) | kept |
| industrial_output | Industrial output | productive_capital | more output (good) | **new** |
| supply_chain_strain | Supply chain strain | supply_networks | more strain (bad) | **new** |
| tech_adoption | Technology adoption | computing_capacity | more adoption (neutral) | renamed from tech_pace |
| cyber_insecurity | Cyber insecurity | computing_capacity | more breaches (bad) | **new** |
| prices | Prices | monetary_credit | higher prices (bad) | kept |
| borrowing_cost | Borrowing cost and credit access | monetary_credit | costlier or tighter credit (bad) | split from financial_conditions |
| asset_values | Asset values | asset_wealth | higher values (good for holders) | split from financial_conditions |
| market_volatility | Market volatility | asset_wealth | more volatility (bad) | split from financial_conditions |
| private_debt | Private debt | asset_wealth | heavier burden (bad) | **new** |
| inequality | Economic inequality | asset_wealth | wider gap (bad) | **new** |
| fiscal_strain | Fiscal strain | public_finances | more strain (bad) | **new** |
| health_risk | Health risk | population_health | more risk (bad) | kept |
| mental_distress | Mental distress | population_health | more distress (bad) | **new** |
| care_strain | Care strain | care_capacity | more strain (bad) | **new** |
| job_security | Job security | labour_force | more secure (good) | kept |
| pay_growth | Pay growth | labour_force | faster pay growth (good) | **new** |
| social_division | Social division | social_trust | more division (bad) | kept |
| community | Community strength | community_ties | stronger (good) | kept |
| trust_institutions | Trust in institutions | legitimacy | more trust (good) | kept |
| public_service_quality | Public service quality | state_capacity | better (good) | **new** |
| civil_liberties | Civil liberties | legitimacy | more freedom (good) | **new** |
| crime | Crime | state_capacity | more crime (bad) | kept |
| war_terror | War and terror | state_capacity | more conflict (bad) | kept |
| civil_unrest | Civil unrest | state_capacity | more unrest (bad) | **new** |
| information_reliability | Information reliability | knowledge | more reliable (good) | **new** |
| news_overload | News overload | attention | more news competing (bad) | kept |
| migration_flow | Migration flow | population | more net arrivals (neutral) | **new** |

Retired: `optimism`. One condition, News overload, has no topic that moves it (it moves with story volume), by design.

### New step: condition → condition ties (12)

v1 has no step where one condition moves another. Without it, ten of the new conditions (water, land, minerals, supply chains and so on) would be dead ends. Each tie is one hop with a written reason:

| From | To | Strength | Reason |
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

## 3. Topics (the domains above): 14 → 48, plus Other

**Why.** Fourteen broad areas cannot say what a story moves. Each topic now routes to at most three conditions (the first is the main one), which v1 did not have. Other is still the review bucket and does not count. The 450 cached headlines must be reclassified, not relabelled, because most v1 ids were split.

Current (v1): Economy, finance and housing; Work and labour; Energy, transport and natural resources; Environment and climate; Health and medicine; Safety and crime; Conflict and security; Government, law and courts; International relations and migration; Society, community and identity; Culture, sport and leisure; Technology, science and information; Education and knowledge; Business and companies.

| Id | Topic | What is placed here | Moves (main first) | Change from v1 |
|---|---|---|---|---|
| macro_growth_recession | Growth and recession | The overall size and health of an economy: output, recession, recovery, national income, business cycle | Job security; Industrial output | split from economy_housing |
| inflation_prices | Inflation and living costs | Prices of everyday goods and services rising or falling, cost of living, price controls | Prices | split from economy_housing |
| interest_credit_banking | Interest rates, credit and banks | Central bank decisions, loan and mortgage rates, bank health, lending, household and business debt | Borrowing cost and credit access; Private debt; Housing cost | split from economy_housing |
| markets_investment | Markets and investing | Stock, bond, currency, commodity and crypto prices, investor behaviour, savings products | Asset values; Market volatility | split from economy_housing |
| public_budget_tax | Taxes and public budgets | Taxation, government spending, deficits and debt, subsidies, public-sector pay | Fiscal strain; Public service quality; Economic inequality | split from economy_housing |
| trade_tariffs | Trade and supply chains | Imports, exports, tariffs, trade deals, shipping and supply disruptions of goods | Supply chain strain; Mineral and material scarcity; Industrial output | split from economy_housing |
| housing_rents | Housing and rents | Home prices, rents, construction of homes, evictions, homelessness, housing policy | Housing cost; Asset values | split from economy_housing |
| work_labour | Jobs and wages | Employment, unemployment, hiring, layoffs, pay, working hours and conditions | Job security; Pay growth | kept |
| labour_disputes | Unions and strikes | Trade unions, strikes, collective bargaining, labour law disputes | Pay growth; Disruption of services; Civil unrest | split from work_labour |
| ai_automation | AI and automation | Artificial intelligence, robots and software replacing or changing tasks and jobs, AI safety and rules | Technology adoption; Job security; Information reliability | split from technology_science |
| retirement_pensions | Retirement and pensions | Pension systems, retirement age, ageing populations' income, elder care funding | Fiscal strain | split from work_labour |
| social_welfare_poverty | Welfare, poverty and inequality | Benefits, poverty, hunger programmes, income inequality, social safety nets | Economic inequality; Food insecurity; Private debt | split from society_identity |
| energy_power | Energy and fuel | Oil, gas, coal, electricity, power grids, fuel prices, renewable build-out | Energy cost and supply; Prices; Air pollution | split from energy_resources |
| transport_infrastructure | Transport and infrastructure | Roads, rail, aviation, ports, public transport, bridges, grid and network build and failure | Infrastructure condition; Disruption of services; Supply chain strain | split from energy_resources |
| food_agriculture | Food and farming | Crops, livestock, fisheries, food supply and safety, famine, food prices | Food insecurity; Prices; Land degradation | split from energy_resources |
| water_utilities | Water and utilities | Drinking water, sanitation, droughts and floods affecting supply, utility services | Water stress | split from energy_resources |
| climate_change | Climate change | Global warming, emissions, climate policy and targets, adaptation | Climate stress; Water stress; Biodiversity loss | split from environment_climate |
| pollution_nature | Pollution and nature | Air and water pollution, waste, wildlife, forests, conservation, land use | Air pollution; Biodiversity loss; Land degradation | split from environment_climate |
| natural_disasters | Disasters and extreme weather | Storms, floods, heatwaves, wildfires, earthquakes and the response | Climate stress; Disruption of services; Infrastructure condition | split from environment_climate |
| public_health | Disease and public health | Epidemics, vaccination, outbreaks, health warnings, food and drug safety | Health risk; Care strain | split from health |
| health_care_system | Health care services | Hospitals, doctors, insurance, waiting times, health costs and funding | Care strain; Public service quality | split from health |
| medicines_science | Medicines and treatments | New drugs, trials, approvals, medical devices and medical research | Health risk; Care strain | split from health |
| mental_health_substances | Mental health and substance use | Mental illness, wellbeing, addiction, drugs, alcohol, tobacco policy | Mental distress | split from health |
| crime_policing | Crime and policing | Violent and property crime, policing, gangs, organised crime, prisons | Crime | split from safety_crime |
| courts_rulings | Courts and legal rulings | Court cases, judgments, legal rights decisions, investigations and trials of public interest | Trust in institutions; Civil liberties | split from government_law |
| accidents_incidents | Accidents and incidents | Transport crashes, industrial accidents, fires, product failures, rescues | Health risk; Disruption of services | split from safety_crime |
| cyber_privacy | Cyber security and privacy | Hacks, data breaches, surveillance, online fraud, privacy law | Cyber insecurity; Civil liberties; Disruption of services | split from technology_science |
| war_conflict | War and armed conflict | Wars, invasions, ceasefires, attacks on civilians, conflict casualties | War and terror; Energy cost and supply; Food insecurity | split from conflict_security |
| terrorism_violence | Terrorism and political violence | Terror attacks, extremism, assassination attempts and other premeditated political violence | War and terror | split from conflict_security |
| defence_weapons | Defence and weapons | Military budgets, arms, alliances, conscription, nuclear and weapons programmes | War and terror; Fiscal strain | split from conflict_security |
| diplomacy_treaties | Diplomacy and treaties | Summits, treaties, alliances, global institutions, relations between states | War and terror | split from international_migration |
| sanctions_aid | Sanctions and aid | Sanctions, embargoes, foreign aid, humanitarian relief, development finance | Supply chain strain; Energy cost and supply; Mineral and material scarcity | split from international_migration |
| migration_refugees | Migration and refugees | Immigration rules, border control, asylum, refugee flows, integration | Migration flow; Social division | split from international_migration |
| elections_politics | Elections and political parties | Elections, campaigns, polls, party politics, leaders' standing, coalitions | Trust in institutions; Social division; Civil unrest | split from government_law |
| legislation_regulation | Laws and regulation | New laws, rules, bans, licensing, regulation of industries | Civil liberties | split from government_law |
| governance_corruption | Government performance and corruption | Scandals, corruption, public services failing and institutional failure | Trust in institutions; Public service quality | split from government_law |
| civil_rights_discrimination | Civil rights and discrimination | Equality, minority and gender rights, freedom of speech, discrimination | Civil liberties; Social division | split from society_identity |
| protest_movements | Protests and social movements | Demonstrations, activism, petitions, boycotts, riots and civil unrest | Civil unrest | split from society_identity |
| family_demographics | Family and demographics | Births, marriage, childcare, ageing, population change, family policy | Migration flow; Community strength | split from society_identity |
| religion_identity | Religion and identity | Religion, culture clashes, nationalism, community identity, social values | Social division; Community strength | split from society_identity |
| education_schools | Schools and universities | Schools, universities, fees, exams, teachers, training and skills programmes | Public service quality | renamed from education |
| research_space | Science and space | Scientific discoveries, research funding, space missions, physics, biology (non-medical) | Information reliability; Technology adoption | split from technology_science |
| technology_consumer | Digital technology and consumer tech | Gadgets, internet services, software, telecoms, platforms' products and rules | Technology adoption | split from technology_science |
| media_information | Media and information | News media, misinformation, censorship, social media content, press freedom | Information reliability | split from technology_science |
| consumer_retail | Consumer goods and retail | Shops, product launches, recalls, consumer protection, brand fortunes at household level | Prices; Health risk | split from business_corporate |
| business_corporate | Business and companies | What one company does: deals, mergers, leadership, lawsuits, earnings | Industrial output; Cyber insecurity | kept |
| mining_materials | Minerals and materials | Metals, rare earths, mining and industrial raw materials | Mineral and material scarcity; Supply chain strain | split from energy_resources |
| culture_leisure | Culture, sport and leisure | Film, music, art, celebrities, books, games, sport, tournaments, mass events, holidays, hospitality and the leisure industry | Community strength | kept |

## 4. Person states: 15 → 47

**Why.** This is the layer that decides what a person does, so it grows most. Three kinds: **trait** (fixed, news does not change it), **state** (moves when conditions move), **derived** (set by where and how the person lives). Only states have incoming links from conditions; traits and derived states act through the decision weights. A state may sit close to a condition (a person's job worry vs the job market) on purpose, but is never a copy of it.

Current (v1): Tech comfort; Price attention; Privacy stance; Social ease; Time pressure; Novelty seeking; Financial stress; Optimism; Safety concern; Institutional trust; Liquidity; Habit and inertia; Loss aversion; Tenure (rent or own); Life stage and household.

| Id | Name | Kind | Moved by (condition, sign) | Feeds decisions | Change from v1 |
|---|---|---|---|---|---|
| tech_comfort | Tech comfort | trait | — | subscribe; switch_brand | kept |
| price_attention | Price attention | state | +Prices; +Energy cost and supply | spend; subscribe; switch_brand | kept |
| privacy_stance | Privacy stance | trait | — | subscribe; share | kept |
| social_ease | Social ease | trait | — | share; protest; donate_volunteer | kept |
| novelty_seeking | Novelty seeking | trait | — | buy_new; change_work; switch_brand; start_business | kept |
| habit_inertia | Habit and inertia | trait | — | subscribe; move; switch_brand | kept |
| loss_aversion | Loss aversion | trait | — | invest; borrow; stockpile_prepare | kept |
| conscientiousness | Conscientiousness and planning | trait | — | health_action; study_train; break_rules | **new** |
| emotional_reactivity | Emotional reactivity | trait | — | share; protest; stockpile_prepare | **new** |
| risk_tolerance | Risk tolerance | trait | — | change_work; invest; start_business | **new** |
| patience | Patience | trait | — | spend; invest; borrow; study_train | **new** |
| fairness_concern | Fairness concern | trait | — | protest | **new** |
| status_concern | Status concern | trait | — | spend; buy_new; borrow | **new** |
| conformity | Social influence susceptibility | trait | — | share | **new** |
| econ_orientation | Economic orientation | trait | — | vote | **new** |
| cultural_orientation | Cultural orientation | trait | — | break_rules | **new** |
| group_identity | Group identity strength | trait | — | vote | **new** |
| religiosity | Religiosity | trait | — | family_change; donate_volunteer | **new** |
| prosociality | Prosociality (willingness to help others) | trait | — | donate_volunteer | **new** |
| environmental_values | Environmental values | trait | — | travel | **new** |
| health_orientation | Health orientation | trait | — | health_action | **new** |
| financial_literacy | Financial literacy | derived | — | invest | **new** |
| financial_stress | Financial stress | state | +Prices; −Pay growth; −Job security; +Housing cost | spend; buy_new; borrow; claim_support | kept |
| liquidity | Liquidity | state | −Prices; +Pay growth; +Job security; +Asset values | spend; invest; start_business; claim_support | kept |
| debt_burden | Debt burden | state | +Borrowing cost and credit access; +Private debt | borrow | **new** |
| job_worry | Job insecurity worry | state | −Job security; +Technology adoption; −Industrial output | change_work; study_train; start_business; claim_support | **new** |
| time_pressure | Time pressure | state | +Disruption of services; +Care strain | travel; study_train; donate_volunteer | kept |
| optimism | Optimism | state | +Job security; −Prices; +Asset values; −War and terror | spend; buy_new; invest; family_change | kept |
| safety_concern | Safety concern | state | +Crime; +War and terror; +Civil unrest; +Climate stress | travel; move; stockpile_prepare | kept |
| wellbeing | Well-being | state | −Mental distress; −Disruption of services; +Community strength | travel; family_change | **new** |
| loneliness | Loneliness | state | −Community strength; +Health risk | donate_volunteer | **new** |
| job_satisfaction | Job satisfaction and autonomy | state | +Pay growth; +Job security | change_work | **new** |
| perceived_health_threat | Perceived health threat | state | +Health risk; +Care strain; +Air pollution | travel; health_action; stockpile_prepare | **new** |
| health_status | Health status | derived | — | health_action; claim_support | **new** |
| institutional_trust | Institutional trust | state | +Trust in institutions; +Public service quality; −Social division | protest; health_action; claim_support; break_rules | kept |
| interpersonal_trust | Trust in other people | state | −Social division; −Crime; +Community strength | donate_volunteer | **new** |
| media_trust | Trust in news media | state | +Information reliability | health_action; break_rules | **new** |
| political_efficacy | Political efficacy | state | +Civil liberties; +Trust in institutions | vote; protest | **new** |
| grievance | Felt grievance | state | +Economic inequality; +Social division; −Public service quality; +Migration flow | share; vote; protest; break_rules | **new** |
| news_attention | News attention | state | +News overload; +War and terror | share; vote | **new** |
| tenure | Tenure (rent or own) | derived | — | move | kept |
| housing_burden | Housing burden | state | +Housing cost; +Borrowing cost and credit access | move; borrow; family_change | **new** |
| life_stage | Life stage and household | derived | — | change_work; move; study_train; family_change | kept |
| education_skills | Education and skills | derived | — | study_train; start_business | **new** |
| digital_access | Digital access | derived | — | subscribe; claim_support | **new** |
| hazard_exposure | Local hazard exposure | derived | — | move; stockpile_prepare | **new** |
| car_dependence | Car dependence | derived | — | buy_new | **new** |

During review (these were never in the current list): Burnout was folded into Well-being, Cooperativeness into Prosociality, Spending confidence into Optimism. In v1, 6 traits were moved by 15 of the 42 condition links; v2 retires those, and Price attention and Liquidity become moving states.

## 5. Decisions: 8 → 20

**Why.** Eight could not express saving, borrowing, voting, protest or health action, and states had nothing to feed. Still abstract action classes. The eight originals are unchanged.

Current (v1): Spend (vs save); Buy something new; Subscribe or commit; Travel; Change work; Move home; Switch brand or provider; Share or engage publicly.

| Id | Name | Question the classifier is asked | Change from v1 |
|---|---|---|---|
| spend | Spend (vs save) | Will this person spend more freely rather than hold money back? | kept |
| buy_new | Buy something new | Will this person buy a major new item (not a routine purchase)? | kept |
| subscribe | Subscribe or commit | Will this person sign up to a recurring or long contract? | kept |
| travel | Travel | Will this person take a trip? | kept |
| change_work | Change work | Will this person change job, hours or employer? | kept |
| move | Move home | Will this person move home (within or between places)? | kept |
| switch_brand | Switch brand or provider | Will this person switch to a different brand or provider? | kept |
| share | Share or engage publicly | Will this person post, share or speak publicly about it? | kept |
| vote | Vote or take party action | Will this person vote, join a party or contact an official? | **new** |
| protest | Protest or strike | Will this person join a protest, boycott or strike? | **new** |
| health_action | Take a health action | Will this person seek care, test, vaccinate or change a health habit? | **new** |
| study_train | Study or retrain | Will this person enrol in study or training? | **new** |
| family_change | Change family situation | Will this person marry, separate, have a child or take on care duties? | **new** |
| stockpile_prepare | Stockpile or prepare | Will this person stock up on supplies or buy protection or insurance? | **new** |
| start_business | Start or expand a business | Will this person start or expand a business? | **new** |
| donate_volunteer | Give, volunteer or join a group | Will this person give money or time to a cause, or join a group? | **new** |
| claim_support | Claim support | Will this person apply for benefits, aid or an entitlement? | **new** |
| borrow | Borrow (take on new debt) | Will this person take on new debt? | **new** |
| invest | Invest | Will this person put savings into shares, funds or property? | **new** |
| break_rules | Ignore official rules or guidance | Will this person ignore official rules or guidance? | **new** |

During review the draft names were changed to avoid bundling opposite acts: borrow (was borrow or repay), invest (was save or invest), break rules (was comply with rules). A draft decision, adopt a technology, was cut (a channel, not an act).

## What changes if this is adopted (impact)

| Area | Change | Work needed |
|---|---|---|
| Engine | Loads the v2 rule files; gains the condition→condition step; joins topics to resources by id instead of by name (the by-name join breaks silently if a resource is renamed). | Code, behind a switch; v1 stays the default. |
| Classifier | About 150 new questions and phrases for the new conditions and decisions; reworded questions for the narrowed disruption, health risk and social division. | Write and test on labelled items. This is where accuracy comes from. |
| Data | 450 cached headlines reclassified against 48 topics; each of the 100 countries needs starting values for the new conditions. | Needs GPU run and real sources; where none exists, start at neutral and label it so. |
| Page | The How it works graph shows the larger layers; each node tagged fitted, guessed or neutral by default. | After the engine runs v2. |
| Stored results | Renamed ids (id_map.csv lists all 83) break old keys. | Freeze the v1 ledger with the map before switching. |

Not yet done: checking the source claims (the first two worth checking are the Michigan consumer-sentiment components and the housing-burden threshold, OECD about 40% vs the US 30% rule); writing the classifier questions; fitting any weight.

