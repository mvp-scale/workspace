# Knowledge pipeline view v2: a guided story on one screen (2026-11-20)

Page: http://localhost:8100/mockups/knowledge-raw/index.html. v1 (four scrolling acts) was rejected by the owner, ledger L2772 and later.

## What it must show
- **What the pipeline is:** news in, decision-grade knowledge out. It recognises what we already know and grows it with new evidence instead of repeating it.
- **News is the first proving ground.** The same pipeline serves other integrations later: the world model, and organisational knowledge such as email, documents and communications.

## Owner's bar
- **One screen, no scrolling:** everything is visible at once on a laptop.
- **Guided:**
  - the page tells the viewer what to do next;
  - Play walks through the steps by itself;
  - the viewer never has to discover that a dot is clickable.
- **The whole pipeline, not just entities:** every tool we already have appears in its step.
- **The data tells the story.** Our words are limited to step titles and one caption per step that says what the step does, never what the data means.
- **Ends in a decision:** what changed, how sure we are, the evidence behind it, and what we don't know.

## Layout
- **Left, the stepper:** six steps with progress.
  - Each step has a one-line caption, plus Next and Play.
  - After step 6 the button becomes "Read next article", and the cycle repeats on a new article with the knowledge carried forward.
- **Centre, the stage:** the same article throughout, changing per step.
- **Right, "What we know so far":**
  - always visible and updated after each article;
  - articles read, knowledge items, items reinforced, topics, and the consolidation curve;
  - the top reinforced items, by name.

## Steps (each with its existing tool and output)
1. **Read:**
   - publisher, time, the article text;
   - the story check from the journal: new story, copy, or already seen.
2. **Understand:**
   - IPTC domain › topic › node with p;
   - story type, place, time;
   - each shown with its decider call: ANSWER (solid), PROVISIONAL (outlined) or ABSTAIN (grey).
3. **Extract:**
   - names, organisations, places, amounts, dates and claims, highlighted inline;
   - filter v0 kept/dropped count; dropped items are struck through.
4. **Connect:**
   - a named graph with labels on the nodes;
   - this article's items light up;
   - each item marked NEW, or ALREADY KNOWN (n articles, m publishers) with links to the earlier articles.
5. **World state:**
   - which of the 26 resources this article moves (ledger_split), with direction up/down/none and weight;
   - abstain carries weight 0.25 of attention and never sets a direction (recorded ledger rule), shown dashed and grey.
6. **Decision:**
   - a card built only from pipeline fields: what changed, how sure (decider), the evidence (article and sentence), and the open gaps (fields that abstained or were not answered);
   - nothing generated.

## Honesty
- Fields the pipeline does not answer are shown as "not answered", never hidden.
- Merge v0 and filter v0 are labelled as such.
