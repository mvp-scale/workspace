# Model card: <name> <version>

| Field | Value |
|---|---|
| Task / heads | e.g. BIO spans: ENTITY, EVENT_VERB, EVENT_NOUN, TIME, QUANTITY |
| Architecture | e.g. 4-layer, hidden 384 encoder (MiniLM-L12 init), 19.2M params |
| Format | ONNX int8 (dynamic / static, bias-corrected?), file size, sha |
| Runtime | onnxruntime version; fused ops used (com.microsoft); browser support |
| Input | tokenizer (file + sha), window length, stride, special tokens |
| Output | logits shape and decoding rule |
| Training data | teacher(s), label pool size, gold excluded? publisher/time split |
| Scores | link to gate report |
| Speed | link to gate report |
| Known failure modes | e.g. tags digits inside numbers as entities; no entity types |
| Licence / release | private / internal / public; trained on copyrighted text? release approved by whom |
