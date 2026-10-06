# So what: golden cases (draft, 2026-10-06)

These are the unit tests for the so-what composer. Each case is a real engine response (`sowhat-fixtures/<n>.json`, rules_v2 test engine on :8135, captured 2026-10-06) plus the two classifier answers measured on Winnow-12B during design. The expected output for two foci per story was produced by applying the rules in `so-what-ontology.md` exactly. The machine-readable version, with every beat and its trace, is `sowhat-golden.json`; a composer passes when it reproduces `headline`, `line2`, `template` and `lead` for all 44 cases.

How to read the tables: **Old** is what the page prints today for the same input (the `paintCard` logic, re-run on the fixture). **New** is the headline in bold followed by line 2. The template id says which frame and which lead beat were used: SQ squeeze, RL relief, SC scare, BL blow, SH shake-up, SU surge, FR freeze, RF rift, BO boost, RP ripple, NO quiet; -T trigger lead, -W who lead, -S scale lead, -C certainty lead.

Coverage: the world-focus cases use 8 of the 10 frames plus the plain family (14, an unresolved place). Three cases are quiet: counted but too small (06), opinion (21), no impact (22). **Blow and ripple have no golden case**, so their templates are covered only by the review stories (`sowhat-review.md`). All 4 lead beats appear; the certainty lead appears once (20, an opinion). Ten stories enter at a country, and nine of them are local (world move under 0.25), so the world focus tests the local WHO lead 9 times. Case 14 is the one story whose place is unresolved ('the Gulf': ask_country named a part of the world and no country in it).

Changes on 2026-10-06 (the review fixes; every other case is unchanged): see "What changed on 2026-10-06" at the end of this file.

## Side by side

| # | Story | Focus | Old | New | Template |
|---|---|---|---|---|---|
| 01 | The central bank cut interest rates by half a point today | World | Worldwide, people are likelier to spend more, buy more new things and stay where they live. | **Loans get cheaper: people open their wallets and invest a bit more.** Builds, then eases. A minor shift that reaches nearly everyone. | RL-T |
|  |  | Higher-income, tech-comfortable, big-city | Higher-income, tech-comfortable, big-city people are likelier to put savings into shares, funds or property, spend more and buy more new things. | **Loans get cheaper: big-city high earners invest more and open their wallets.** More than most people. A clear shift here. | RL-T |
| 02 | A new pandemic virus is spreading fast across several countries, and hospitals report a surge in admissions | World | Worldwide, people are likelier to seek care, get tested or change a health habit, travel less and stock up on supplies or buy protection or insurance. | **A major scare: health risks rise, so people protect themselves and travel far less.** A quick jolt that fades. Older, tech-wary people react more than most people. | SC-S |
|  |  | Older, set in their ways, tech-wary | Older, set in their ways, tech-wary people are likelier to seek care, get tested or change a health habit, travel less and stock up on supplies or buy protection or insurance. | **A big scare: health risks rise, so older, tech-wary people protect themselves and travel far less.** A quick jolt that fades. More than most people. | SC-S |
| 03 | Russian forces launched a major new offensive in eastern Ukraine overnight | World | Concentrated in Ukraine: people there are likelier to cut back on spending, travel less and hold off buying new things. | **Only Ukraine feels this scare: armed conflict escalates, and people there cut back and travel less.** Elsewhere, barely a ripple. A quick jolt that fades. | SC-W |
|  |  | Ukraine | People in Ukraine are likelier to cut back on spending, travel less and hold off buying new things. | **Armed conflict escalates, so people in Ukraine cut back and travel less.** Barely felt outside Ukraine. A quick jolt that fades. | SC-T |
| 04 | A record heat wave is hitting India, with temperatures above 48C and power cuts in several cities | World | Worldwide, people are likelier to cut back on spending, travel less and switch brands or providers. | **India feels the scare most: weather hazards get worse, and people there spend far less and travel far less.** A quick jolt that fades. A minor shift that reaches a small minority. | SC-W |
|  |  | India | People in India are likelier to cut back on spending, travel less and switch brands or providers. | **A big scare: weather hazards get worse, so people in India spend far less and travel far less.** Many times as much as most people. A quick jolt that fades. | SC-S |
| 05 | Rail workers across the UK walked out today in a national strike over pay | World | Concentrated in the United Kingdom: people there are likelier to travel less, give less time and money to causes and cut back on spending. | **Only the United Kingdom feels this shake-up: service outages multiply, and people there travel a bit less.** Little changes elsewhere. A small shift there. | SH-W |
|  |  | United Kingdom | People in the United Kingdom are likelier to travel less, give less time and money to causes and cut back on spending. | **Service outages multiply, and people in the United Kingdom adjust: they travel a bit less and give a bit less to causes.** A small shift here. Barely felt outside the United Kingdom. | SH-T |
| 06 | Apple launched a new iPhone with a better camera | World | Worldwide the average person barely moves. | **New digital tools spread, but no decision moves enough to matter.** | NO-Q |
|  |  | United States | Nothing here shifts a decision. | **New digital tools spread, but no decision moves enough to matter for people in the United States.** | NO-Q |
| 07 | The state cut school funding by 12 percent, forcing districts to lay off teachers | World | Worldwide, people are likelier to cut back on spending, ignore official rules and guidance and hold off buying new things. | **Jobs get less secure, and people feel the squeeze: they cut back sharply and brush off official rules.** A notable shift that reaches nearly everyone. Fades slowly. | SQ-T |
|  |  | United States | People in the United States are likelier to cut back on spending, ignore official rules and guidance and hold off buying new things. | **Jobs get less secure, and people in the United States feel the squeeze: they cut back and brush off official rules.** A clear shift here. Fades slowly. | SQ-T |
| 08 | A data breach at a major bank exposed the personal details of 40 million customers | World | Worldwide, people are likelier to ignore official rules and guidance, put off health care and health habits and join protests, boycotts or strikes. | **Digital break-in risks rise, so people brush off official rules and put off health care.** A minor shift that reaches most people. Fades slowly. | SC-T |
|  |  | China | People in China are likelier to ignore official rules and guidance, put off health care and health habits and join protests, boycotts or strikes. | **Digital break-in risks rise, so people in China brush off official rules and put off health care.** A small shift here. Fades slowly. | SC-T |
| 09 | The government raised income tax by two points for middle earners starting next month | World | Worldwide, people are likelier to cut back on spending, hold off buying new things and keep savings in cash. | **Prices will rise, and people will feel the squeeze: they will cut back.** Not in effect yet. A minor shift that reaches nearly everyone. | SQ-T |
|  |  | Higher-income, tech-comfortable, big-city | Higher-income, tech-comfortable, big-city people are likelier to cut back on spending, keep savings in cash and hold off buying new things. | **Prices will rise, and big-city high earners will feel the squeeze: they will cut back and keep savings in cash.** A small shift here. Not in effect yet. | SQ-T |
| 10 | House prices in Canada jumped 9 percent this year as buyers rush back into the market | World | Concentrated in Canada: people there are likelier to cut back on spending, take on new debt and hold off buying new things. | **Canada takes this squeeze almost alone: housing costs rise, so people there spend far less and take on debt.** Little changes elsewhere. A big shift there. | SQ-W |
|  |  | Canada | People in Canada are likelier to cut back on spending, take on new debt and hold off buying new things. | **A big squeeze: housing costs rise, so people in Canada spend far less and take on debt.** Barely felt outside Canada. Fades slowly. | SQ-S |
| 11 | An outsider candidate won a surprise victory in Brazil's presidential election | World | Concentrated in Brazil: people there are likelier to speak out more, join protests, boycotts or strikes and ignore official rules and guidance. | **This rift stays in Brazil: social divides should deepen, and people there push back in public and brush off official rules.** Little changes elsewhere. A small shift there. | RF-W |
|  |  | Brazil | People in Brazil are likelier to speak out more, join protests, boycotts or strikes and ignore official rules and guidance. | **Social divides should deepen, and people in Brazil take sides: they push back in public and brush off official rules.** A small shift here. Barely felt outside Brazil. | RF-T |
| 12 | Ford will close its Michigan assembly plant, cutting 3,000 jobs | World | Concentrated in the United States: people there are likelier to cut back on spending, apply for benefits, aid or entitlements and hold off buying new things. | **Only the United States feels this squeeze: jobs will get less secure, so people there will cut back and apply for aid.** Elsewhere, barely a ripple. Not in effect yet. | SQ-W |
|  |  | United States · rural areas | People in the United States (rural areas) are likelier to cut back on spending, apply for benefits, aid or entitlements and hold off buying new things. | **Jobs will get less secure, and people in the rural United States will feel the squeeze: they will cut back.** Not in effect yet. Many times as much as most people. | SQ-T |
| 13 | Regulators approved a new vaccine that cuts malaria deaths by half | World | Worldwide, people are likelier to put off health care and health habits, travel more and buy only what they need now. | **Health risks should fall, and people ease off on precautions and travel a bit more.** A tiny shift that reaches a large minority. Effects not felt yet. | BO-T |
|  |  | Older, set in their ways, tech-wary | Older, set in their ways, tech-wary people are likelier to put off health care and health habits, travel more and buy only what they need now. | **Health risks should fall, and older, tech-wary people ease off on precautions and travel a bit more.** A small shift here. Effects not felt yet. | BO-T |
| 14 | Oil prices spiked 20 percent after attacks on tankers in the Gulf | World | Worldwide, people are likelier to cut back on spending, switch brands or providers and drop or avoid subscriptions and contracts. | **Fuel and power costs rise, and people spend far less.** A major shift. Builds, then eases. | PL-T |
|  |  | Higher-income, tech-comfortable, big-city | Higher-income, tech-comfortable, big-city people are likelier to cut back on spending, keep savings in cash and drop or avoid subscriptions and contracts. | **Fuel and power costs rise, and big-city high earners spend far less and keep savings in cash.** A big shift here. Builds, then eases. | PL-T |
| 15 | A large tech firm said it will cut 10,000 jobs and replace them with AI tools | World | Worldwide, people are likelier to cut back on spending, hold off buying new things and apply for benefits, aid or entitlements. | **Jobs will get less secure, and people will feel the squeeze: they will cut back and apply for aid.** Not in effect yet. A minor shift that reaches most people. | SQ-T |
|  |  | United States | People in the United States are likelier to cut back on spending, apply for benefits, aid or entitlements and hold off buying new things. | **Jobs will get less secure, and people in the United States will feel the squeeze: they will cut back.** A small shift here. Not in effect yet. | SQ-T |
| 16 | Wildfires forced 50,000 people to evacuate in California | World | Concentrated in the United States: people there are likelier to travel less, seek care, get tested or change a health habit and stock up on supplies or buy protection or insurance. | **Only the United States feels this scare: more people move away, and people there travel less and protect themselves.** Elsewhere, barely a ripple. A small shift there. | SC-W |
|  |  | United States | People in the United States are likelier to travel less, seek care, get tested or change a health habit and stock up on supplies or buy protection or insurance. | **More people move away, so people in the United States travel less and protect themselves.** A small shift here. Barely felt outside the United States. | SC-T |
| 17 | A regional US bank collapsed after a run on deposits, and regulators took control | World | Concentrated in the United States: people there are likelier to cut back on spending, keep savings in cash and hold off buying new things. | **Only the United States feels this freeze: markets swing harder, so people there cut back and keep savings in cash.** Little changes elsewhere. A clear shift there. | FR-W |
|  |  | United States | People in the United States are likelier to cut back on spending, keep savings in cash and hold off buying new things. | **Markets swing harder, and people in the United States wait and see: they cut back and keep savings in cash.** Barely felt outside the United States. A clear shift here. | FR-T |
| 18 | A record number of migrants crossed into Germany this month | World | Concentrated in Germany: people there are likelier to speak out more, join protests, boycotts or strikes and ignore official rules and guidance. | **Only Germany feels this surge: more people move in, and people there push back in public and brush off official rules.** Elsewhere, barely a ripple. A small shift there. | SU-W |
|  |  | Germany | People in Germany are likelier to speak out more, join protests, boycotts or strikes and ignore official rules and guidance. | **More people move in, and people in Germany respond: they push back in public and brush off official rules.** A small shift here. Barely felt outside Germany. | SU-T |
| 19 | A severe drought in Kenya has destroyed crops, leaving millions short of food | World | Concentrated in Kenya: people there are likelier to cut back on spending, hold off buying new things and apply for benefits, aid or entitlements. | **This squeeze stays in Kenya: food shortages spread, so people there cut back sharply and apply for aid.** Elsewhere, barely a ripple. A big shift there. | SQ-W |
|  |  | Kenya | People in Kenya are likelier to cut back on spending, hold off buying new things and apply for benefits, aid or entitlements. | **A big squeeze: food shortages spread, so people in Kenya cut back sharply and apply for aid.** Barely felt outside Kenya. Fades slowly. | SQ-S |
| 20 | Economists warn a recession may be coming next year | World | Worldwide, people are likelier to cut back on spending, hold off buying new things and keep savings in cash. | **If this forecast comes true, jobs would get less secure, and people would cut back a little and keep savings in cash.** A tiny shift that reaches a large minority. Builds, then eases. | SQ-C |
|  |  | Germany | People in Germany are likelier to cut back on spending, keep savings in cash and hold off buying new things. | **If this forecast comes true, jobs would get less secure, and people in Germany would spend a bit less.** A small shift here. Fades slowly. | SQ-C |
| 21 | Opinion: our leaders are failing young people, and it is time we said so | World | Worldwide the average person barely moves. | **An opinion piece: on our numbers no one changes what they do.** | NO-O |
|  |  | United States | Nothing here shifts a decision. | **An opinion piece: on our numbers no one changes what they do.** | NO-O |
| 22 | A local zoo welcomed a baby giraffe named Daisy | World | No material impact expected. | **Nothing to say: this story moves none of the things we track.** | NO-X |
|  |  | India | No material impact expected. | **Nothing to say: this story moves none of the things we track.** | NO-X |

## Beats by story (world focus)

Lead beat first, then the beats in line 2, then the beats computed but not shown. The trace is what the hover shows.

### 01. The central bank cut interest rates by half a point today
- Classifier: frame relief 0.79, boost 0.19, surge 0.02; trigger borrowing_cost 0.98, private_debt 0.01, housing_cost 0.00
- Lead: trigger; line 2: arc, scale
  - **trigger**: loans get cheaper · _trigger choice: borrowing_cost 0.98, runner-up private_debt 0.01; borrowing_cost down: strength 0.996, reported (reported), size notable_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.98, announced 0.98, opinion 0.0, forecast 0.0_
  - **frame**: relief · _frame choice: relief 0.79, runner-up boost 0.19; response sense up (spend+buy_new+subscribe+travel +2.18)_
  - **response**: open their wallets and invest a bit more · _spending: spend +1.30, buy_new +0.88 (peak pts at World); money: invest +0.61 (peak pts at World)_
  - **arc**: Builds, then eases. · _spend at World: now +0.97, next +1.30, later +0.72; peak next; keeps 55%_
  - **scale**: A minor shift that reaches nearly everyone. · _Size 20.4 (Minor); spend reach 99.4% at Next_
  - **who**: Big-city high earners react a bit less than most people. · _spend: Higher-income, tech-comfortable, big-city +0.80 vs world +1.30 (x0.62)_

### 02. A new pandemic virus is spreading fast across several countries, and hospitals report a surge in admissions
- Classifier: frame scare 0.99, surge 0.01, shake_up 0.00; trigger health_risk 0.98, care_strain 0.02, public_service_quality 0.00
- Lead: scale; line 2: arc, who
  - **trigger**: health risks rise · _trigger choice: health_risk 0.98, runner-up care_strain 0.02; health_risk up: strength 0.99, reported (reported), size severe_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.94, announced 0.04, opinion 0.0, forecast 0.01_
  - **frame**: scare · _frame choice: scare 0.99, runner-up surge 0.01; response sense down (spend+buy_new+subscribe+travel -4.71)_
  - **response**: protect themselves and travel far less · _protection: health_action +4.77, stockpile_prepare +2.97 (peak pts at World); travel: travel -4.71 (peak pts at World)_
  - **arc**: A quick jolt that fades. · _health_action at World: now +4.77, next +3.70, later +1.33; peak now; keeps 28%_
  - **scale**: A major shift that reaches nearly everyone. · _Size 53.0 (Major); health_action reach 100.0% at Next_
  - **who**: Older, tech-wary people react more than most people. · _health_action: Older, set in their ways, tech-wary +7.75 vs world +4.77 (x1.62)_

### 03. Russian forces launched a major new offensive in eastern Ukraine overnight
- Classifier: frame scare 0.92, squeeze 0.03, rift 0.02; trigger war_terror 1.00, fiscal_strain 0.00, food_insecurity 0.00
- Lead: who; line 2: who, arc
  - **trigger**: armed conflict escalates · _trigger choice: war_terror 1.00, runner-up fiscal_strain 0.00; war_terror up: strength 0.988, reported (reported), size notable_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.98, announced 0.74, opinion 0.0, forecast 0.0_
  - **frame**: scare · _frame choice: scare 0.92, runner-up squeeze 0.03; response sense down (spend+buy_new+subscribe+travel -3.49)_
  - **response**: cut back and travel less · _spending: spend -1.35, buy_new -0.83, subscribe -0.33 (peak pts at Ukraine); travel: travel -0.98 (peak pts at Ukraine)_
  - **arc**: A quick jolt that fades. · _spend at Ukraine: now -1.35, next -1.08, later -0.43; peak now; keeps 32%_
  - **scale**: A clear shift. · _spend -1.35 pts at Ukraine -> band clear (cuts 0.25/1/3/8)_
  - **who**: Elsewhere, barely a ripple. · _entry COUNTRY:ukr; world largest move 0.01 < 0.25; spend -1.35 at Ukraine_
- Weak spot: War moves Ukraine by about 1 point and the rest of the world by nothing; the engine undersizes war, so the so-what is honest but small.

### 04. A record heat wave is hitting India, with temperatures above 48C and power cuts in several cities
- Classifier: frame scare 0.94, shake_up 0.05, blow 0.01; trigger climate_stress 0.97, disruption 0.03, energy_fuel 0.00
- Lead: who; line 2: arc, scale
  - **trigger**: weather hazards get worse · _trigger choice: climate_stress 0.97, runner-up disruption 0.03; climate_stress up: strength 0.993, reported (reported), size major_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.95, announced 0.01, opinion 0.0, forecast 0.0_
  - **frame**: scare · _frame choice: scare 0.94, runner-up shake_up 0.05; response sense down (spend+buy_new+subscribe+travel -3.01)_
  - **response**: spend far less and travel far less · _spending: spend -1.31, subscribe -0.55, buy_new -0.51 (peak pts at World); travel: travel -0.64 (peak pts at World)_
  - **arc**: A quick jolt that fades. · _spend at World: now -1.31, next -1.07, later -0.44; peak now; keeps 34%_
  - **scale**: A minor shift that reaches a small minority. · _Size 12.7 (Minor); spend reach 18.4% at Next_
  - **who**: India reacts many times as much as most people. · _spend: India -7.13 vs world -1.31 (x5.44); share 0.184_

### 05. Rail workers across the UK walked out today in a national strike over pay
- Classifier: frame shake_up 0.98, ripple 0.01, rift 0.01; trigger disruption 0.97, supply_chain_strain 0.02, public_service_quality 0.01
- Lead: who; line 2: who, scale; budget: dropped 2nd response theme
  - **trigger**: service outages multiply · _trigger choice: disruption 0.97, runner-up supply_chain_strain 0.02; disruption up: strength 0.955, reported (reported), size minor_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.91, announced 0.52, opinion 0.0, forecast 0.0_
  - **frame**: shake-up · _frame choice: shake_up 0.98, runner-up ripple 0.01; response sense down (spend+buy_new+subscribe+travel -1.31)_
  - **response**: travel a bit less · _travel: travel -0.68 (peak pts at United Kingdom); support: donate_volunteer -0.48 (peak pts at United Kingdom)_
  - **arc**: A quick jolt that fades. · _travel at United Kingdom: now -0.68, next -0.46, later -0.09; peak now; keeps 13%_
  - **scale**: A small shift. · _travel -0.68 pts at United Kingdom -> band small (cuts 0.25/1/3/8)_
  - **who**: Little changes elsewhere. · _entry COUNTRY:gbr; world largest move 0.01 < 0.25; travel -0.68 at United Kingdom_
- Weak spot: Under 1 point, travel only. The second response (give less to causes) is an engine side effect; the word budget dropped it at world focus.

### 06. Apple launched a new iPhone with a better camera
- Classifier: frame shake_up 0.63, boost 0.36, ripple 0.01; trigger tech_adoption 0.99, industrial_output 0.01
- Lead: quiet; line 2: none
  - **trigger**: new digital tools spread · _trigger choice: tech_adoption 0.99, runner-up industrial_output 0.01; tech_adoption up: strength 0.689, reported (reported), size minor_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.97, announced 0.97, opinion 0.0, forecast 0.01_
  - **frame**: shake_up · _frame choice: shake_up 0.63, runner-up boost 0.36; response sense up (spend+buy_new+subscribe+travel +0.33)_
  - **response**: none · _no decision at World moves 0.25+ pts (largest spend +0.20)_
- Weak spot: Nothing reaches 0.25 points anywhere: the quiet form is the right answer.

### 07. The state cut school funding by 12 percent, forcing districts to lay off teachers
- Classifier: frame squeeze 0.93, blow 0.04, shake_up 0.02; trigger job_security 0.88, public_service_quality 0.11, fiscal_strain 0.01
- Lead: trigger; line 2: scale, arc
  - **trigger**: jobs get less secure · _trigger choice: job_security 0.88, runner-up public_service_quality 0.11; job_security down: strength 0.998, reported (reported), size major_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.97, announced 0.98, opinion 0.0, forecast 0.0_
  - **frame**: squeeze · _frame choice: squeeze 0.93, runner-up blow 0.04; response sense down (spend+buy_new+subscribe+travel -5.30)_
  - **response**: cut back sharply and brush off official rules · _spending: spend -3.23, buy_new -2.07 (peak pts at World); rules: break_rules +2.34 (peak pts at World)_
  - **arc**: Fades slowly. · _spend at World: now -3.23, next -2.76, later -1.48; peak now; keeps 46%_
  - **scale**: A notable shift that reaches nearly everyone. · _Size 39.3 (Notable); spend reach 100.0% at Next_
  - **who**: Big-city high earners react about half as much as most people. · _spend: Higher-income, tech-comfortable, big-city -1.82 vs world -3.23 (x0.56)_
- Weak spot: Rule-breaking (+2.3 pts) comes from guessed decision weights (trust in institutions -> break_rules). The composer must report it; the fix belongs in decision_weights.csv.

### 08. A data breach at a major bank exposed the personal details of 40 million customers
- Classifier: frame scare 0.92, shake_up 0.03, blow 0.03; trigger cyber_insecurity 0.99, trust_institutions 0.01, borrowing_cost 0.00
- Lead: trigger; line 2: scale, arc
  - **trigger**: digital break-in risks rise · _trigger choice: cyber_insecurity 0.99, runner-up trust_institutions 0.01; cyber_insecurity up: strength 0.966, reported (reported), size major_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.97, announced 0.05, opinion 0.0, forecast 0.0_
  - **frame**: scare · _frame choice: scare 0.92, runner-up shake_up 0.03; response sense down (spend+buy_new+subscribe+travel -0.27)_
  - **response**: brush off official rules and put off health care · _rules: break_rules +0.74 (peak pts at World); protection: health_action -0.41 (peak pts at World)_
  - **arc**: Fades slowly. · _break_rules at World: now +0.74, next +0.66, later +0.42; peak now; keeps 57%_
  - **scale**: A minor shift that reaches most people. · _Size 15.6 (Minor); break_rules reach 69.3% at Next_
- Weak spot: Weakest headline: "brush off official rules and put off health care" is what the numbers say, through the same guessed weights. Do not paper over it in the composer.

### 09. The government raised income tax by two points for middle earners starting next month
- Classifier: frame squeeze 0.99, shake_up 0.00, freeze 0.00; trigger prices 0.59, job_security 0.20, private_debt 0.10
- Lead: trigger; line 2: certainty, scale
  - **trigger**: prices will rise · _trigger choice: prices 0.59, runner-up job_security 0.20; prices up: strength 0.827, reported (reported), size notable_
  - **certainty**: announced · _weight fact 1.0; gate happened 0.21, announced 0.99, opinion 0.0, forecast 0.46_
  - **frame**: squeeze · _frame choice: squeeze 0.99, runner-up shake_up 0.00; response sense down (spend+buy_new+subscribe+travel -3.15)_
  - **response**: cut back · _spending: spend -1.81, buy_new -0.96, subscribe -0.38 (peak pts at World)_
  - **arc**: Fades slowly. · _spend at World: now -1.81, next -1.57, later -0.70; peak now; keeps 39%_
  - **scale**: A minor shift that reaches nearly everyone. · _Size 23.6 (Minor); spend reach 98.9% at Next_
  - **who**: Big-city high earners react about half as much as most people. · _spend: Higher-income, tech-comfortable, big-city -0.82 vs world -1.81 (x0.45)_
- Weak spot: The trigger question picked prices (0.59) over the budget reading (government budgets get breathing room). A tax rise headlined as a price rise is debatable.

### 10. House prices in Canada jumped 9 percent this year as buyers rush back into the market
- Classifier: frame squeeze 0.57, surge 0.43, relief 0.00; trigger housing_cost 0.92, asset_values 0.08, prices 0.00
- Lead: who; line 2: who, scale
  - **trigger**: housing costs rise · _trigger choice: housing_cost 0.92, runner-up asset_values 0.08; housing_cost up: strength 0.994, reported (reported), size major_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.94, announced 0.04, opinion 0.01, forecast 0.01_
  - **frame**: squeeze · _frame choice: squeeze 0.57, runner-up surge 0.43; response sense down (spend+buy_new+subscribe+travel -5.36)_
  - **response**: spend far less and take on debt · _spending: spend -3.17, buy_new -1.53, subscribe -0.66 (peak pts at Canada); money: borrow +1.63, invest -0.28 (peak pts at Canada)_
  - **arc**: Fades slowly. · _spend at Canada: now -3.17, next -2.66, later -1.34; peak now; keeps 42%_
  - **scale**: A big shift. · _spend -3.17 pts at Canada -> band big (cuts 0.25/1/3/8)_
  - **who**: Little changes elsewhere. · _entry COUNTRY:can; world largest move 0.02 < 0.25; spend -3.17 at Canada_
- Weak spot: Frame was close (squeeze 0.57, surge 0.43). The world Size badge says Negligible while Canada moves 1.6+ pts: the badge is world-only.

### 11. An outsider candidate won a surprise victory in Brazil's presidential election
- Classifier: frame rift 0.98, scare 0.01, shake_up 0.00; trigger social_division 0.99, civil_unrest 0.01
- Lead: who; line 2: who, scale
  - **trigger**: social divides should deepen · _trigger choice: social_division 0.99, runner-up civil_unrest 0.01; social_division up: strength 0.855, expected (expected_in_effect), size notable_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.96, announced 0.95, opinion 0.01, forecast 0.01_
  - **frame**: rift · _frame choice: rift 0.98, runner-up scare 0.01; response sense flat (spend+buy_new+subscribe+travel -0.22)_
  - **response**: push back in public and brush off official rules · _voice: share +0.50, protest +0.41, vote +0.33 (peak pts at Brazil); rules: break_rules +0.40 (peak pts at Brazil)_
  - **arc**: Fades slowly. · _share at Brazil: now +0.50, next +0.41, later +0.28; peak now; keeps 56%_
  - **scale**: A small shift. · _share +0.50 pts at Brazil -> band small (cuts 0.25/1/3/8)_
  - **who**: Little changes elsewhere. · _entry COUNTRY:bra; world largest move 0.01 < 0.25; share +0.50 at Brazil_
- Weak spot: Only expected readings (no reported change) and 0.4 pts in Brazil: the hedge "should" carries the weight.

### 12. Ford will close its Michigan assembly plant, cutting 3,000 jobs
- Classifier: frame squeeze 0.63, blow 0.36, shake_up 0.01; trigger job_security 0.99, industrial_output 0.01, pay_growth 0.00
- Lead: who; line 2: who, certainty
  - **trigger**: jobs will get less secure · _trigger choice: job_security 0.99, runner-up industrial_output 0.01; job_security down: strength 0.999, reported (reported), size notable_
  - **certainty**: announced · _weight fact 1.0; gate happened 0.2, announced 0.98, opinion 0.0, forecast 0.05_
  - **frame**: squeeze · _frame choice: squeeze 0.63, runner-up blow 0.36; response sense down (spend+buy_new+subscribe+travel -4.21)_
  - **response**: cut back and apply for aid · _spending: spend -2.57, buy_new -1.64 (peak pts at United States); support: claim_support +1.75 (peak pts at United States)_
  - **arc**: Fades slowly. · _spend at United States: now -2.57, next -2.16, later -1.10; peak now; keeps 43%_
  - **scale**: A clear shift. · _spend -2.57 pts at United States -> band clear (cuts 0.25/1/3/8)_
  - **who**: Elsewhere, barely a ripple. · _entry COUNTRY:usa; world largest move 0.11 < 0.25; spend -2.57 at United States_

### 13. Regulators approved a new vaccine that cuts malaria deaths by half
- Classifier: frame boost 0.99, relief 0.00, scare 0.00; trigger health_risk 0.98, care_strain 0.02
- Lead: trigger; line 2: scale, certainty
  - **trigger**: health risks should fall · _trigger choice: health_risk 0.98, runner-up care_strain 0.02; health_risk down: strength 0.993, expected (expected_pending), size major_
  - **certainty**: pending · _weight fact 1.0; gate happened 0.98, announced 0.99, opinion 0.0, forecast 0.01_
  - **frame**: boost · _frame choice: boost 0.99, runner-up relief 0.00; response sense up (spend+buy_new+subscribe+travel +0.44)_
  - **response**: ease off on precautions and travel a bit more · _protection: health_action -0.59, stockpile_prepare -0.34 (peak pts at World); travel: travel +0.44 (peak pts at World)_
  - **arc**: A quick jolt that fades. · _health_action at World: now -0.59, next -0.47, later -0.20; peak now; keeps 34%_
  - **scale**: A tiny shift that reaches a large minority. · _Size 10.8 (Negligible); health_action reach 36.3% at Next_
  - **who**: Older, tech-wary people react more than most people. · _health_action: Older, set in their ways, tech-wary -0.97 vs world -0.59 (x1.64)_
- Weak spot: Changed 2026-10-06 (review fix 2): the approval happened (gate happened 0.98), only its effects are pending, so the event is plain present, the reading says 'should' and line 2 says 'Effects not felt yet.' (no modal 'will'). The engine lowers health actions because health risk falls; the vaccine itself is a health action, so the so-what is faithful to the numbers but misses the obvious take-up.

### 14. Oil prices spiked 20 percent after attacks on tankers in the Gulf
- Classifier: frame squeeze 0.99, surge 0.00, freeze 0.00; trigger energy_fuel 0.99, prices 0.01, market_volatility 0.00
- Lead: trigger; line 2: scale, arc
  - **trigger**: fuel and power costs rise · _trigger choice: energy_fuel 0.99, runner-up prices 0.01; energy_fuel up: strength 0.942, reported (reported), size major_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.98, announced 0.03, opinion 0.0, forecast 0.0_
  - **frame**: shift · _frame choice: squeeze 0.99, runner-up surge 0.00; response sense down (spend+buy_new+subscribe+travel -12.10); place not resolved (WORLD:world), plain used_
  - **response**: spend far less · _spending: spend -6.82, buy_new -3.23, subscribe -2.05 (peak pts at World)_
  - **arc**: Builds, then eases. · _spend at World: now -4.26, next -6.82, later -3.03; peak next; keeps 44%_
  - **scale**: A major shift. · _Size 53.8 (Major); spend reach 100.0% at Next_
  - **who**: Big-city high earners react about half as much as most people. · _spend: Higher-income, tech-comfortable, big-city -3.53 vs world -6.82 (x0.52)_
- Weak spot: Changed 2026-10-06 (honesty about place): ask_country answered 'global' with no probability (a part of the world, no country in it: 'the Gulf'), so the place is unresolved. No place, no WHO, no 'major squeeze' frame: the plain template, and line 2 gives the size without a reach claim.

### 15. A large tech firm said it will cut 10,000 jobs and replace them with AI tools
- Classifier: frame squeeze 0.90, shake_up 0.08, freeze 0.01; trigger job_security 0.77, tech_adoption 0.23, pay_growth 0.00
- Lead: trigger; line 2: certainty, scale
  - **trigger**: jobs will get less secure · _trigger choice: job_security 0.77, runner-up tech_adoption 0.23; job_security down: strength 0.999, reported (reported), size major_
  - **certainty**: announced · _weight forecast 0.3; gate happened 0.1, announced 0.99, opinion 0.0, forecast 0.83_
  - **frame**: squeeze · _frame choice: squeeze 0.90, runner-up shake_up 0.08; response sense down (spend+buy_new+subscribe+travel -1.43)_
  - **response**: cut back and apply for aid · _spending: spend -0.85, buy_new -0.56 (peak pts at World); support: claim_support +0.51 (peak pts at World)_
  - **arc**: Fades slowly. · _spend at World: now -0.85, next -0.73, later -0.39; peak now; keeps 46%_
  - **scale**: A minor shift that reaches most people. · _Size 13.5 (Minor); spend reach 78.3% at Next_
  - **who**: Big-city high earners react about half as much as most people. · _spend: Higher-income, tech-comfortable, big-city -0.44 vs world -0.85 (x0.52)_
- Weak spot: Changed 2026-10-06 (certainty rule): happened 0.1 < 0.5 and announced 0.99 > forecast 0.83, so it reads 'announced' ('will', 'Not in effect yet.'), not 'forecast'.

### 16. Wildfires forced 50,000 people to evacuate in California
- Classifier: frame scare 0.54, blow 0.45, shake_up 0.00; trigger migration_flow 0.94, land_degradation 0.04, health_risk 0.01
- Lead: who; line 2: who, scale
  - **trigger**: more people move away · _trigger choice: migration_flow 0.94, runner-up land_degradation 0.04; migration_flow down: strength 0.844, reported (reported), size minor_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.95, announced 0.11, opinion 0.0, forecast 0.0_
  - **frame**: scare · _frame choice: scare 0.54, runner-up blow 0.45; response sense down (spend+buy_new+subscribe+travel -0.90)_
  - **response**: travel less and protect themselves · _travel: travel -0.76 (peak pts at United States); protection: health_action +0.68, stockpile_prepare +0.39 (peak pts at United States)_
  - **arc**: A quick jolt that fades. · _travel at United States: now -0.76, next -0.58, later -0.20; peak now; keeps 26%_
  - **scale**: A small shift. · _travel -0.76 pts at United States -> band small (cuts 0.25/1/3/8)_
  - **who**: Elsewhere, barely a ripple. · _entry COUNTRY:usa; world largest move 0.03 < 0.25; travel -0.76 at United States_
- Weak spot: The trigger chose "more people move away" (0.95) over land damage; true to the story but not what most readers would lead with.

### 17. A regional US bank collapsed after a run on deposits, and regulators took control
- Classifier: frame freeze 0.35, squeeze 0.33, blow 0.14; trigger market_volatility 0.52, asset_values 0.44, borrowing_cost 0.03
- Lead: who; line 2: who, scale; budget: dropped 2nd trigger
  - **trigger**: markets swing harder · _trigger choice: market_volatility 0.52, runner-up asset_values 0.44; market_volatility up: strength 0.961, reported (reported), size minor; asset_values down: strength 0.982, expected (expected_in_effect), size minor_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.98, announced 0.85, opinion 0.0, forecast 0.0_
  - **frame**: freeze · _frame choice: freeze 0.35, runner-up squeeze 0.33; response sense down (spend+buy_new+subscribe+travel -2.09)_
  - **response**: cut back and keep savings in cash · _spending: spend -1.27, buy_new -0.82 (peak pts at United States); money: invest -1.15 (peak pts at United States)_
  - **arc**: Fades slowly. · _spend at United States: now -1.27, next -1.09, later -0.57; peak now; keeps 45%_
  - **scale**: A clear shift. · _spend -1.27 pts at United States -> band clear (cuts 0.25/1/3/8)_
  - **who**: Little changes elsewhere. · _entry COUNTRY:usa; world largest move 0.06 < 0.25; spend -1.27 at United States_
- Weak spot: Frame margin is thin (freeze 0.35, squeeze 0.33) and the trigger margin too (0.52 vs 0.44): two readings were picked and the word budget dropped the second.

### 18. A record number of migrants crossed into Germany this month
- Classifier: frame surge 0.85, rift 0.14, ripple 0.01; trigger migration_flow 1.00, social_division 0.00
- Lead: who; line 2: who, scale
  - **trigger**: more people move in · _trigger choice: migration_flow 1.00, runner-up social_division 0.00; migration_flow up: strength 0.942, reported (reported), size notable_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.92, announced 0.01, opinion 0.0, forecast 0.0_
  - **frame**: surge · _frame choice: surge 0.85, runner-up rift 0.14; response sense flat (spend+buy_new+subscribe+travel +0.00)_
  - **response**: push back in public and brush off official rules · _voice: share +0.74, protest +0.60, vote +0.50 (peak pts at Germany); rules: break_rules +0.56 (peak pts at Germany)_
  - **arc**: Fades slowly. · _share at Germany: now +0.74, next +0.62, later +0.42; peak now; keeps 57%_
  - **scale**: A small shift. · _share +0.74 pts at Germany -> band small (cuts 0.25/1/3/8)_
  - **who**: Elsewhere, barely a ripple. · _entry COUNTRY:deu; world largest move 0.01 < 0.25; share +0.74 at Germany_

### 19. A severe drought in Kenya has destroyed crops, leaving millions short of food
- Classifier: frame squeeze 0.53, scare 0.34, blow 0.12; trigger food_insecurity 0.99, land_degradation 0.01, health_risk 0.00
- Lead: who; line 2: who, scale
  - **trigger**: food shortages spread · _trigger choice: food_insecurity 0.99, runner-up land_degradation 0.01; food_insecurity up: strength 0.993, reported (reported), size notable_
  - **certainty**: happened · _weight fact 1.0; gate happened 0.96, announced 0.01, opinion 0.0, forecast 0.01_
  - **frame**: squeeze · _frame choice: squeeze 0.53, runner-up scare 0.34; response sense down (spend+buy_new+subscribe+travel -7.49)_
  - **response**: cut back sharply and apply for aid · _spending: spend -3.85, buy_new -2.29, subscribe -0.65 (peak pts at Kenya); support: claim_support +1.59 (peak pts at Kenya)_
  - **arc**: Fades slowly. · _spend at Kenya: now -3.85, next -3.32, later -1.55; peak now; keeps 40%_
  - **scale**: A big shift. · _spend -3.85 pts at Kenya -> band big (cuts 0.25/1/3/8)_
  - **who**: Elsewhere, barely a ripple. · _entry COUNTRY:ken; world largest move 0.03 < 0.25; spend -3.85 at Kenya_

### 20. Economists warn a recession may be coming next year
- Classifier: frame squeeze 0.97, freeze 0.02, scare 0.00; trigger job_security 0.68, asset_values 0.25, industrial_output 0.06
- Lead: certainty; line 2: scale, arc
  - **trigger**: jobs would get less secure · _trigger choice: job_security 0.68, runner-up asset_values 0.25; job_security down: strength 0.996, expected (expected_pending), size major_
  - **certainty**: forecast · _weight forecast 0.3; gate happened 0.02, announced 0.12, opinion 0.71, forecast 0.99_
  - **frame**: squeeze · _frame choice: squeeze 0.97, runner-up freeze 0.02; response sense down (spend+buy_new+subscribe+travel -0.76)_
  - **response**: cut back a little and keep savings in cash · _spending: spend -0.45, buy_new -0.31 (peak pts at World); money: invest -0.26 (peak pts at World)_
  - **arc**: Builds, then eases. · _spend at World: now -0.36, next -0.45, later -0.24; peak next; keeps 53%_
  - **scale**: A tiny shift that reaches a large minority. · _Size 7.3 (Negligible); spend reach 35.7% at Next_
  - **who**: Big-city high earners react a bit less than most people. · _spend: Higher-income, tech-comfortable, big-city -0.30 vs world -0.45 (x0.67)_
- Weak spot: Forecast at 0.3 weight: under half a point. Same opener as 15 would have had (same frame, certainty and trigger) before the gate fix; the feed rule in the ontology flips the variant when two stories in a row share it. Certainty: happened 0.02 < 0.5 and forecast 0.99 > announced 0.12, so forecast (the 2026-10-06 certainty rule; opinion 0.71 is under the 0.9 cut).

### 21. Opinion: our leaders are failing young people, and it is time we said so
- Classifier: frame rift 0.92, ripple 0.07, shake_up 0.00; trigger not asked (fewer than 2 readings)
- Lead: quiet; line 2: none
  - **trigger**: trust in institutions could fall · _only reading: trust_institutions down; trust_institutions down: strength 0.56, expected (expected_pending), size minor_
  - **certainty**: opinion · _weight opinion 0.3; gate happened 0.09, announced 0.01, opinion 1.0, forecast 0.02_
  - **frame**: rift · _frame choice: rift 0.92, runner-up ripple 0.07; response sense flat (spend+buy_new+subscribe+travel +0.00)_
  - **response**: none · _no decision at World moves 0.25+ pts (largest share +0.04)_
- Weak spot: Opinion with one tiny expected reading: the honest form is "nothing to say".

### 22. A local zoo welcomed a baby giraffe named Daisy
- Classifier: frame ripple 1.00, boost 0.00, squeeze 0.00; trigger not asked (fewer than 2 readings)
- Lead: quiet; line 2: none
  - **certainty**: no_impact · _identify.counted false; status no_impact_expected; closest miss light news flow 0.563_
- Weak spot: No reading cleared the bar: nothing to say.

## What the side by side shows

- **Old lines are one shape.** Every event line is `Worldwide, people are likelier to ...` or `Concentrated in X: people there are likelier to ...` (`People in X are likelier to ...` for a focus), with three phrases, and some of those phrases are 8 or more words long ("stock up on supplies or buy protection or insurance").
- **Old lines carry no size and no focus.** For local stories the old line is right about the country (Ukraine: spend -1.35, travel -0.98, buy_new -0.83 points), but it lists three acts as if they were equal and never says that the rest of the world does not move. The new line says where the effect is ("Only Ukraine feels this scare", "Elsewhere, barely a ripple."), gives the size in words, and keeps at most two responses. In 09 and 14 it keeps only one, because the second is under 0.4 times the first.
- **The new line says why.** Every new headline except the quiet ones names the change that drives it (the trigger), which the old line never did.
- **Hedges match the story.** The kind comes from the gate (happened < 0.5: forecast or announced, whichever is larger; opinion only at 0.9 or more). The tax rise (announced, not yet in effect) and the AI job cuts (a company said it will; announced 0.99 beats forecast 0.83) read "will", the recession warning (happened 0.02, forecast 0.99 above announced 0.12) reads "would", the vaccine approval (happened, effects pending) reads "should fall" with "Effects not felt yet.", and the opinion piece says nothing happens. The old line treated all of them as fact.
- **Where the new line is weak**, it is because the numbers are weak or odd: 07 and 08 (rule-breaking from guessed weights), 13 (vaccine lowers health actions), 03, 05 and 11 (under 1 point). See the weak spots above and in the ontology, section 7.

## What changed on 2026-10-06 (review fixes 1-6 and the place rule)

Golden cases may change only where a stated rule change requires it. All 44 cases were re-composed; these outputs changed (19 after the certainty rule below put 20 back) (the other 23 are identical), and all others, including every headline not listed, are unchanged.

| Case / focus | What changed | Rule that requires it |
|---|---|---|
| 05 World, 11 World, 10 World, 17 World | line 2 starts "Little changes elsewhere." instead of "Elsewhere, barely a ripple." (10, 17, 05, 11); in 05 and 11 the arc is replaced by "A small shift there." | fix 5 (second 'elsewhere' variant, chosen by a hash of the headline); fix 4 (a small band always shows its size) |
| 05 gbr, 11 bra, 16 usa, 18 deu (country focus) | line 2 is now "A small shift here. Barely felt outside X." (arc dropped) | fix 4: small band always shows its size, ahead of the arc |
| 16 World, 18 World | "A small shift there." replaces the arc | fix 4 |
| 08 chn | line 2 order: "A small shift here. Fades slowly." | fix 4 (scale first) |
| 09 AUDIENCE:4 | "A small shift here. Not in effect yet." replaces the "about half as much as most people" fragment | fix 4 |
| 08 World | the computed (not shown) WHO beat is gone: Canada at 0.53 vs world 0.74 is a country comparison on a story whose entry is the world | rule A (WHO only for a real country entry) |
| 13 World, 13 AUDIENCE:6 | "Health risks should fall, and people ease off on precautions ..." (was "will fall ... will ease off"); line 2 "Effects not felt yet." (was "Not in effect yet.") plus the size word | fix 2 (pending); fix 4 |
| 14 World, 14 AUDIENCE:4 | PL-T plain template, no "major squeeze", no WHO; line 2 "A major shift. Builds, then eases." | rule A (unresolved place) |
| 15 World, 15 usa | now SQ-T: "Jobs will get less secure, and people will feel the squeeze: they will cut back ..."; line 2 "Not in effect yet." (was a forecast with "would") | certainty rule (happened 0.1 < 0.5, announced 0.99 > forecast 0.83 gives announced) |
| 20 World, 20 deu | unchanged from the original golden (forecast, SQ-C, "If this forecast comes true ... would"); it was briefly an opinion under the first gate order; the second headline change in 20 World is the same as the original | final certainty rule (opinion >= 0.9 only; happened < 0.5 and forecast 0.99 > announced 0.12 gives forecast) |
