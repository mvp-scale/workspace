# World engine ontology: topic domains (draft v1, 2026-10-05)

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
