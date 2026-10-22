# Kaggle options for headline + description topic classifier (Haiku research, 2026-10-21)

Scope: datasets with headline/short text plus a topic label; opinion vs report labels; Kaggle free GPU terms. Only pages opened in this session are cited. Kaggle pages render with JavaScript, so their body text was not readable; those cells say so.

## 1. Datasets

| # | Name | URL (opened) | Size | Label set | Licence (exact) | Text fields | Mapping to our ~50 topics |
|---|---|---|---|---|---|---|---|
| 1 | News Category Dataset (Rishabh Misra; HuffPost) | https://www.kaggle.com/datasets/rmisra/news-category-dataset (title only readable) ; HF mirror https://huggingface.co/datasets/heegyu/news-category-dataset | 209,527 rows, 87.3 MB (HF); years 2012-2022 per the arXiv abstract (https://arxiv.org/abs/2209.11429) | 12 categories seen on HF preview: U.S. NEWS, WORLD NEWS, POLITICS, ENTERTAINMENT, SPORTS, CULTURE & ARTS, TECH, ENVIRONMENT, COMEDY, PARENTING, WEIRD NEWS, EDUCATION. Per-category counts not readable. | HF card: `cc-by-4.0`. Kaggle licence not readable; HF card gives no licence text. | link, headline, category, short_description, authors, date | Partial: POLITICS, ENVIRONMENT, EDUCATION, PARENTING, ENTERTAINMENT map; crime, courts, religion, mining, poverty, family_demographics have no label |
| 2 | AG News | https://huggingface.co/datasets/fancyzhx/ag_news | 120,000 train + 7,600 test | World, Sports, Business, Sci/Tech (4) | "unknown" on the HF card ("[More Information Needed]"); original corpus from ComeToMyHead | text (title + description joined), label | Poor: 4 coarse classes, no short-description split |
| 3 | BBC News topic set (Greene & Cunningham) | https://huggingface.co/datasets/SetFit/bbc-news | 2,225 articles (1.23k train / 1k test per viewer) | tech, business, sport, entertainment, politics (5) | No licence stated; card says "All rights, including copyright, in the content of the original articles are owned by the BBC." | text (full article body, not headline + short description), label, label_text | Poor: 5 classes; full-length text |

Not done: a multi-country news topic set. No search was run for one, so this is an open gap.

## 2. Opinion vs news / factuality labels

Not searched in this session. No dataset is listed here. A search is needed before any claim about opinion or factuality labels.

## 3. Kaggle free GPU (official terms)

| Item | Status |
|---|---|
| GPU type, weekly quota, session limit, internet, API token | Not verified. The Kaggle docs page (https://www.kaggle.com/docs/notebooks) opened as a title only. A Kaggle GitHub API page (https://github.com/Kaggle/kaggle-api) gives no quota or token steps. |
| Third-party snippets (unverified, do not rely on) | Search snippets gave about 30 GPU hours/week and a 12-hour session, with accelerator GPU T4/P100. These came from search snippets only, not from an opened Kaggle page. |

Action: open the Kaggle docs in a browser session (the page needs JavaScript) to confirm the quota, session limit and internet rules before planning a GPU run.

## Summary

1. News Category Dataset is the closest match: headline and short_description with a topic-like category. Its Kaggle licence is unconfirmed; the HF mirror says CC BY 4.0.
2. AG News and BBC News are usable only as coarse sanity checks. Their licences are unknown or unstated.
3. A multi-country news topic set and opinion/factuality labels were not found in this session; both remain open.
4. Kaggle GPU quota and session limits are unverified from official pages.
5. Any dataset used for training must have its licence confirmed on its own page before use.
