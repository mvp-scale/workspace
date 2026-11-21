# Reference sources: how much data is in each

Written 2026-11-18 for the pipeline simulation work. Each number is tagged:
**(measured)** counted on our disk today, **(reported)** read from a source page, **(unconfirmed)** I could not verify it.

## Bottom line

- We hold three sources today: IPTC, WordNet and a small Wikidata slice. Together they are **37.5 MB uncompressed** (19 MB on this disk, because the filesystem compresses them). (measured)
- Everything in the integration plan fits in **about 40 MB**. No gigabytes.
- The things that would be gigabytes, and that we are not taking: the full Wikidata dump, FrameNet (855 MB) and GDELT's event database.
- **Correction:** earlier I said WordNet was 18 MB. That was the compressed size on disk. It is **36.4 MB** uncompressed, and the whole pack is about 38 MB, not 20 MB.

## The table

| Source | What it gives us | What we hold today | Size we hold | If we took all of it | Licence |
|---|---|---|---|---|---|
| **IPTC Media Topics** | The news topic tree: 17 top-level topics, then four more levels below. | 1,394 topics: 17 top, 131 second level, 567 third, 583 fourth, 88 fifth, 8 sixth. 1,307 carry a Wikidata id. (measured) | 0.97 MB (measured) | Same. It is already the whole thing. | CC BY 4.0, stated inside the file (measured) |
| **WordNet 3.0** (Princeton) | Word meanings, synonyms, parents and verb classes. | 82,115 noun meanings (117,798 noun words), 13,767 verb meanings (11,529 words), 18,156 adjective and 3,621 adverb meanings. (measured) | 36.4 MB unzipped, 10.8 MB zipped (measured) | Same. | Princeton licence, text is in the folder |
| **Wikidata** | Real-world things: names, aliases, what kind of thing each is. | A slice for the 1,269 topics IPTC already links to: all labelled, 3,337 aliases, 912 with a class. (measured) | 0.16 MB stored; 0.85 MB downloaded (measured) | Tens of GB. Your figure is about 130 GB. For scale: the 2017 compressed JSON dump alone was 19.3 GB and an RDF dump in 2020 was about 81 GB. The current size is (unconfirmed). | CC0 (reported, Wikidata licensing page) |
| **CAMEO** | Event types for political news: who cooperated with or fought whom, how. | Nothing yet. | The code list is one small text file: 311 codes in 20 groups. Its exact size is (unconfirmed), tiny. | The code list is all we need. GDELT's event database built on it is huge and we do not want it. | GDELT terms: unlimited use with a citation (reported) |
| **SKOS** | A vocabulary for concept labels and links: preferred label, alternative label, hidden label, broader, narrower, related, exact match. | No data. It is a W3C standard, and the IPTC file already uses it. | 0 | 0 | W3C specification (licence not checked) |
| **RDFS** | A vocabulary for classes and subclasses ("a minister is a politician"). | No data. A standard. | 0 | 0 | W3C specification (licence not checked) |
| **FrameNet 1.7** (I read "PrankNet" as FrameNet) | Event frames and their roles, for example who meets whom. | Nothing. | n/a | 855 MB unzipped (reported, arXiv 1703.07438). About 1,200 frames. | (unconfirmed). Release 1.5 was CC BY 3.0, a mirror lists CC BY 2.0, and the official page did not load for me. |

## Others you asked about

| Source | Size and licence | Verdict |
|---|---|---|
| Open English WordNet (the newer WordNet) | About 15 to 17 MB compressed for the older releases (reported, en-word.net). CC BY 4.0. | Optional upgrade to WordNet 3.0. Not needed yet. |
| VerbNet | Custom University of Colorado licence, commercial use allowed but it advises legal review. Size not found. | Skip for now. |
| PropBank | Distributed through LDC, not freely downloadable. | Skip. |
| MAVEN | 168 event types built from FrameNet; 4,480 documents and 118,732 event mentions. Licence (unconfirmed). | A scoring set, so it needs your yes. |
| GeoNames, YAGO 4.5, ConceptNet, DBpedia | Not researched. | Only if a plan phase shows a gap. |

## What the plan adds, and what it costs

| Plan step | Adds | Size |
|---|---|---|
| R3: look up the 150 most frequent names on Wikidata | About 150 small requests | Under 1 MB |
| R4: the CAMEO code list | One text file, 311 codes | Tens of KB (unconfirmed) |
| Everything else | Uses data we already hold | 0 |
| **Total after the plan** | | **About 40 MB** |

## What would blow the size up

1. The full Wikidata dump: tens of GB.
2. FrameNet: 855 MB.
3. GDELT's event data: very large, and not needed.

## Sources

- IPTC file and Wikidata slice: measured in `/workspace/data/ontology_src/`.
- Wikidata licence: https://www.wikidata.org/wiki/Wikidata:Licensing
- Earlier Wikidata dump sizes: Zenodo archives of the 2017 and 2020 dumps.
- CAMEO file and terms: https://www.gdeltproject.org/data/lookups/CAMEO.eventcodes.txt and https://www.gdeltproject.org/about.html
- FrameNet release: https://framenet.icsi.berkeley.edu/framenet_data and https://arxiv.org/pdf/1703.07438
- Open English WordNet: https://en-word.net/downloads
- MAVEN: https://arxiv.org/abs/2004.13590
