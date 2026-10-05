"""World model v1: dials -> attributes -> yes/no questions, and the 10 x 10 grid (persona element x dial). All strengths are OUR GUESSES."""
import math
# dial -> {"def": ..., "up": [(attribute, definition, [q1, q2])] x3, "down": [...] x3}   'up' = more of what the dial name says
def A(name, definition, q1, q2): return (name, definition, [q1, q2])
DIALS = {
 "prices": {"def": "How expensive everyday life is for ordinary households.",
  "up": [A("consumer price rise", "everyday goods or services cost more than before", "This story reports that everyday goods or services cost more than before.", "This story reports a price increase paid by ordinary households."),
         A("inflation pressure", "inflation or a rising cost of living is the subject", "This story reports inflation or a rising cost of living.", "This story reports households struggling with rising costs."),
         A("key cost shock", "fuel, energy, food or housing costs rise", "This story reports a rise in fuel, energy, food or housing costs.", "This story reports a supply or tax change that raises costs for consumers.")],
  "down": [A("consumer price fall", "everyday goods or services cost less than before", "This story reports that everyday goods or services cost less than before.", "This story reports a price cut that benefits ordinary households."),
           A("inflation easing", "inflation or cost-of-living pressure falls", "This story reports inflation easing or the cost of living falling.", "This story reports households getting relief from costs."),
           A("key cost relief", "fuel, energy, food or housing costs fall", "This story reports a fall in fuel, energy, food or housing costs.", "This story reports a subsidy, cap or tax cut that lowers consumer costs.")]},
 "job_security": {"def": "How secure people's work and income are.",
  "up": [A("hiring", "employers are creating jobs", "This story reports hiring or job creation.", "This story reports a company expanding its workforce."),
         A("strong labour market", "unemployment low or falling, job growth strong", "This story reports unemployment falling or at a low level.", "This story reports strong job growth."),
         A("pay and openings rise", "wages or job openings rising", "This story reports wages rising.", "This story reports more job openings.")],
  "down": [A("layoffs and closures", "workers lose jobs", "This story reports layoffs or job losses.", "This story reports a company closing or cutting staff."),
           A("weak labour market", "unemployment rising or job growth weak", "This story reports unemployment rising.", "This story reports weak or slowing job growth."),
           A("worker insecurity", "workers fear for their jobs or lose hours or benefits", "This story reports workers worried about losing their jobs.", "This story reports cuts to workers' hours, pay or benefits.")]},
 "safety_fear": {"def": "How threatened people feel in daily life (crime, violence, conflict).",
  "up": [A("violent incident", "a violent crime or attack occurs", "This story reports a violent crime or attack.", "This story reports people being killed or injured by violence."),
         A("rising insecurity", "crime or unrest is rising", "This story reports crime or unrest rising.", "This story reports that people feel unsafe."),
         A("public threat", "war, terror or armed conflict threatens people", "This story reports a war, terror or armed conflict affecting civilians.", "This story reports a threat to public safety.")],
  "down": [A("crime falling", "crime or violence goes down", "This story reports crime falling.", "This story reports a reduction in violence.") ,
           A("threat resolved", "a danger ends or someone responsible is caught", "This story reports a public safety threat ending or being resolved.", "This story reports the arrest of someone responsible for violence."),
           A("safety working", "safety measures are shown to work", "This story reports a safety measure that is reducing harm.", "This story reports neighbourhoods becoming safer.")]},
 "health_risk": {"def": "How exposed people are to illness and how strained care is.",
  "up": [A("outbreak", "a disease spreads", "This story reports a disease outbreak or spread.", "This story reports rising illness or infections."),
         A("care strain", "hospitals or clinics are strained", "This story reports hospitals or clinics under strain.", "This story reports shortages of medical staff or supplies."),
         A("health warning", "a warning or recall about health", "This story reports a health warning to the public.", "This story reports a product or practice being recalled for health reasons.")],
  "down": [A("outbreak ending", "a disease recedes", "This story reports an outbreak ending or declining.", "This story reports illness rates falling."),
           A("treatment success", "a vaccine or treatment works", "This story reports a successful vaccine or treatment rollout.", "This story reports a medical advance that improves outcomes."),
           A("care recovering", "health services recover", "This story reports hospitals returning to normal capacity.", "This story reports better access to care.")]},
 "trust_institutions": {"def": "How far people believe governments, companies and media act honestly and competently.",
  "up": [A("credible conduct", "an institution acts honestly or competently", "This story reports an institution acting credibly or honestly.", "This story reports an institution being open and transparent."),
         A("accountability", "reform or fair accountability", "This story reports a successful reform or accountability measure.", "This story reports wrongdoing being fairly investigated and punished."),
         A("approval rising", "public approval rises", "This story reports public approval of an institution rising.", "This story reports public trust in an institution improving.")],
  "down": [A("scandal", "corruption or misconduct", "This story reports a scandal or corruption involving an institution.", "This story reports an official resigning or being charged over misconduct."),
           A("concealment", "an institution hides or misleads", "This story reports an institution misleading or hiding information from the public.", "This story reports a failure by an institution to protect the public."),
           A("trust falling", "public trust falls", "This story reports public trust in an institution falling.", "This story reports the public losing confidence in an institution.")]},
 "community": {"def": "How connected and mutually supportive local communities are.",
  "up": [A("mutual aid", "neighbours or volunteers help each other", "This story reports neighbours or volunteers helping each other.", "This story reports a surge in volunteering or donations."),
         A("gathering", "people come together in shared spaces or events", "This story reports a community event or space bringing people together.", "This story reports a community coming together."),
         A("solidarity", "people act together for a shared cause", "This story reports people organising together for a shared cause.", "This story reports a show of solidarity.")],
  "down": [A("division", "conflict or division in a community", "This story reports a community divided or in conflict.", "This story reports neighbours or groups in dispute."),
           A("loss of spaces", "gathering places or services close", "This story reports community services or gathering places closing.", "This story reports cuts to local community programmes."),
           A("isolation", "loneliness or withdrawal", "This story reports rising loneliness or social isolation.", "This story reports people withdrawing from community life.")]},
 "tech_pace": {"def": "How fast new technology is changing how people live and work.",
  "up": [A("breakthrough", "a major new technology or capability", "This story reports a major new technology launch or breakthrough.", "This story reports a company releasing a much more capable product."),
         A("fast adoption", "people adopt technology quickly", "This story reports rapid adoption of a new technology.", "This story reports sales or use of a new technology growing quickly."),
         A("changing life or work", "technology changes daily life or jobs", "This story reports a new technology changing how people work or live.", "This story reports technology replacing a human task.")],
  "down": [A("delay or cancel", "a rollout is delayed or cancelled", "This story reports a technology rollout being delayed or cancelled.", "This story reports a technology project being shut down."),
           A("restriction", "regulation restricts technology", "This story reports a regulation restricting a technology.", "This story reports a ban or limit on a technology."),
           A("failure", "a technology fails or is withdrawn", "This story reports a technology failing or being withdrawn.", "This story reports adoption of a technology slowing.")]},
 "disruption": {"def": "How much everyday routines (travel, power, services, school, work) are interrupted.",
  "up": [A("service interruption", "services or travel stop", "This story reports services or travel being interrupted.", "This story reports closures of schools, offices or transport."),
         A("severe event", "weather or disaster affects daily life", "This story reports severe weather or a disaster affecting daily life.", "This story reports people forced to leave their homes or change plans."),
         A("strike or outage", "strike, outage or shutdown", "This story reports a strike, outage or shutdown.", "This story reports people unable to follow their usual routines.")],
  "down": [A("restoration", "services come back", "This story reports services being restored.", "This story reports power or transport back to normal."),
           A("normal resumes", "routines return", "This story reports normal operations resuming after an interruption.", "This story reports schools or workplaces reopening."),
           A("disruption ends", "a strike or crisis ends", "This story reports an end to a strike or outage.", "This story reports a crisis that has been resolved.")]},
 "optimism": {"def": "How hopeful people feel about the future.",
  "up": [A("rising confidence", "confidence about the future rises", "This story reports rising confidence about the future.", "This story reports people or businesses feeling more hopeful."),
         A("positive sentiment", "surveys show better sentiment", "This story reports surveys showing improved sentiment.", "This story reports expectations of improvement."),
         A("lifting news", "news that people say lifts their mood", "This story reports good news that people say lifts their mood.", "This story reports a hopeful turning point.")],
  "down": [A("falling confidence", "confidence about the future falls", "This story reports falling confidence about the future.", "This story reports people or businesses feeling more worried."),
           A("negative sentiment", "surveys show worse sentiment", "This story reports surveys showing worsening sentiment.", "This story reports expectations of decline."),
           A("weighing news", "news that weighs on mood", "This story reports bad news that people say weighs on their mood.", "This story reports a discouraging turning point.")]},
}
NEWS_OVERLOAD = "news_overload"   # dial 10: from report volume in the ledger, never from the content of one story
DIAL_ORDER = list(DIALS) + [NEWS_OVERLOAD]
GENRE = {"happened": "This story reports something that has already happened.", "announced": "This story reports a decision, announcement or plan that has been made public.",
         "opinion": "This story is mainly an opinion or commentary.", "forecast": "This story is mainly a forecast or prediction about the future."}
SCOPE = {"national": "This story affects people across the whole country.", "local": "This story affects a single city, institution or small group.", "new": "This story reports a development that is new today."}

ELEMENTS = ["tech_comfort", "price_attention", "privacy_stance", "social_ease", "time_pressure", "novelty_seeking", "financial_stress", "optimism", "safety_concern", "institutional_trust"]
GRID = {  # (element, dial): (strength, why)    effective element = base x product over dials of perceived_dial ^ strength
 ("price_attention", "prices"): (.8, "higher prices make people watch costs"), ("price_attention", "job_security"): (-.3, "insecure people watch costs more (secure dial down -> attention up)"),
 ("financial_stress", "prices"): (.6, "higher prices strain budgets"), ("financial_stress", "job_security"): (-.8, "more job security eases stress"), ("financial_stress", "health_risk"): (.3, "illness brings costs"),
 ("optimism", "optimism"): (1.0, "same thing"), ("optimism", "prices"): (-.4, "cost pressure dampens hope"), ("optimism", "job_security"): (.5, "secure work lifts hope"), ("optimism", "safety_fear"): (-.3, "fear dampens hope"),
 ("safety_concern", "safety_fear"): (.9, "more threat, more concern"), ("safety_concern", "health_risk"): (.3, "health threats raise caution"), ("safety_concern", "disruption"): (.2, "disruption raises caution"), ("safety_concern", "trust_institutions"): (-.2, "trusted institutions reassure"),
 ("institutional_trust", "trust_institutions"): (.9, "same thing"), ("institutional_trust", "news_overload"): (-.2, "overload wears trust down"),
 ("social_ease", "community"): (.5, "stronger community, easier with others"), ("social_ease", "safety_fear"): (-.3, "fear reduces openness to strangers"), ("social_ease", "health_risk"): (-.3, "illness keeps people apart"),
 ("time_pressure", "disruption"): (.6, "disruption eats time"), ("time_pressure", "news_overload"): (.2, "overload eats attention"),
 ("tech_comfort", "tech_pace"): (.1, "small: fast change slightly raises comfort in the exposed"),
 ("novelty_seeking", "optimism"): (.5, "hopeful people try new things"), ("novelty_seeking", "safety_fear"): (-.3, "fear narrows exploration"), ("novelty_seeking", "tech_pace"): (.2, "fast tech change invites trying"),
 ("privacy_stance", "trust_institutions"): (-.5, "more trust, less reluctance to share (sign debated)"), ("privacy_stance", "safety_fear"): (-.2, "fear can raise acceptance of surveillance (sign contested)"),
}
def grid_matrix():
    return [[GRID.get((e, d), (0, ""))[0] for d in DIAL_ORDER] for e in ELEMENTS]
def questions():
    q = {}
    for d, spec in DIALS.items():
        for dirn in ("up", "down"):
            for ai, (name, defn, qs) in enumerate(spec[dirn]):
                for qi, text in enumerate(qs): q[f"{d}|{dirn}|{ai}|{qi}"] = text
    q.update({f"genre|{k}": v for k, v in GENRE.items()}); q.update({f"scope|{k}": v for k, v in SCOPE.items()}); return q
def write_md(path):
    L = ["# World model v1: dials, attributes, questions and the 10 x 10 grid", "", "Status: ALL strengths and attribute lists are our drafts. Nothing here is validated against real data.", "",
         "How a story becomes a dial change: story (headline + one-line summary) -> 2 yes/no questions per attribute, 3 attributes per direction -> an attribute is PRESENT if its two questions average >= 0.65 -> a direction is PRESENT if >= 2 of its 3 attributes are present -> a dial moves only if exactly one direction is present and the story is an event or announcement (not opinion, not forecast). Dial 10 (news overload) comes from how many reports arrive, not from any one story.", ""]
    for d, s in DIALS.items():
        L += [f"## Dial: {d}", s["def"], ""]
        for dirn in ("up", "down"):
            L.append(f"**{dirn}**")
            for name, defn, qs in s[dirn]: L.append(f"- *{name}*: {defn}. Questions: {qs[0]} / {qs[1]}")
            L.append("")
    L += ["## Dial: news_overload", "Volume of reports per tick in the ledger. No content questions.", "", "## The 10 x 10 grid (rows = persona elements, columns = dials; a strength of 0.8 means a dial 10% above neutral raises the element by about 8%)", "",
          "| element | " + " | ".join(DIAL_ORDER) + " |", "|---|" + "---|" * len(DIAL_ORDER)]
    for e, row in zip(ELEMENTS, grid_matrix()): L.append(f"| {e} | " + " | ".join(f"{v:+.1f}" if v else "." for v in row) + " |")
    L += ["", "### Why each non-zero cell (guesses)", ""] + [f"- {e} <- {d} ({v:+.1f}): {w}" for (e, d), (v, w) in GRID.items()]
    open(path, "w").write("\n".join(L) + "\n")
if __name__ == "__main__":
    write_md("/workspace/probes/persona/world-model-v1.md"); print(len(questions()), "questions per story;", sum(1 for _ in GRID), "non-zero grid cells of", len(ELEMENTS) * len(DIAL_ORDER))
