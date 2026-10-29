"""Labelling task spec for the teacher kit (stage S3; D4-D6, R5). Stdlib only (PyYAML only for .yaml specs).

A spec (JSON, or YAML when PyYAML is installed) holds everything that defines a teacher request:
  name, prompt_version          provenance (D6); the spec sha256 is also recorded per label
  model, max_tokens, cap_usd    teacher model id, reply ceiling, hard $ cap for one run (R5)
  layers                        layer names the teacher labels, e.g. ["ENTITY", "EVENT"]
  guideline                     text (string or list of lines); goes into the cached system prefix
  examples                      few-shot [{"input": {"text", "candidates"?}, "output": {...}}]; SYNTHETIC text only
  output_schema                 JSON schema of the final label row (objects need additionalProperties: false)
  reply_schema                  generate mode, optional: reply schema when it differs from output_schema (e.g. spans
                                without offsets; candidates.locate_spans adds them)
  mode                          "generate" (reply = reply_schema or output_schema) or "verify" (reply = decisions on CPU candidate
                                ids, candidates.verify_schema; assembled into output_schema)
  verify                        verify mode: {"labels": {layer: [codes]}, "reject": [codes], "max_add": int}
  candidates                    candidate proposers for candidates.py ([{"type": "regex"|"dictionary"|"spacy", ...}])
  input_template                user turn; fields {id} {text} {candidates}
  effort, thinking              optional, passed through to the Messages API when set

    python task_spec.py SPEC          # validate; prints name, version, layers, prefix size estimate
"""
import hashlib
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

REQUIRED = ("name", "prompt_version", "model", "max_tokens", "cap_usd", "layers", "guideline", "output_schema")
DEFAULT_TEMPLATE = "ITEM {id}\n<text>\n{text}\n</text>\n{candidates}"
CHARS_PER_TOKEN_LO = 3.0  # conservative (worst-case) chars per token for estimates without count_tokens
CHARS_PER_TOKEN = 4.0     # typical English prose
MIN_CACHE_TOKENS = 512    # 5.x models: shorter prefixes silently don't cache (README Console section)


class SpecError(ValueError):
    pass


# ----------------------------------------------------------------------------- schema
_TYPES = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}


def validate(obj, schema, path="$"):
    """Minimal JSON-schema check (type, enum, const, required, properties, additionalProperties, items, min/maxItems,
    min/maxLength, minimum/maximum, pattern, anyOf). -> list of error strings ([] = valid)."""
    errs = []
    if "anyOf" in schema:
        if not any(not validate(obj, s, path) for s in schema["anyOf"]):
            errs.append(f"{path}: matches no anyOf branch")
        return errs
    t = schema.get("type")
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        ok = False
        for x in ts:
            if x == "integer":
                ok |= isinstance(obj, int) and not isinstance(obj, bool)
            elif x == "number":
                ok |= isinstance(obj, (int, float)) and not isinstance(obj, bool)
            else:
                ok |= isinstance(obj, _TYPES.get(x, object))
        if not ok:
            return [f"{path}: expected {t}, got {type(obj).__name__}"]
    if "enum" in schema and obj not in schema["enum"]:
        errs.append(f"{path}: {obj!r} not in enum")
    if "const" in schema and obj != schema["const"]:
        errs.append(f"{path}: != const")
    if isinstance(obj, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in obj:
                errs.append(f"{path}: missing {k!r}")
        for k, v in obj.items():
            if k in props:
                errs += validate(v, props[k], f"{path}.{k}")
            elif schema.get("additionalProperties") is False:
                errs.append(f"{path}: unexpected key {k!r}")
            elif isinstance(schema.get("additionalProperties"), dict):
                errs += validate(v, schema["additionalProperties"], f"{path}.{k}")
    if isinstance(obj, list):
        if "minItems" in schema and len(obj) < schema["minItems"]:
            errs.append(f"{path}: fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(obj) > schema["maxItems"]:
            errs.append(f"{path}: more than {schema['maxItems']} items")
        if "items" in schema:
            for i, v in enumerate(obj):
                errs += validate(v, schema["items"], f"{path}[{i}]")
    if isinstance(obj, str):
        if "minLength" in schema and len(obj) < schema["minLength"]:
            errs.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(obj) > schema["maxLength"]:
            errs.append(f"{path}: longer than {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], obj):
            errs.append(f"{path}: does not match {schema['pattern']}")
    if isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if "minimum" in schema and obj < schema["minimum"]:
            errs.append(f"{path}: < {schema['minimum']}")
        if "maximum" in schema and obj > schema["maximum"]:
            errs.append(f"{path}: > {schema['maximum']}")
    return errs


def closed(schema, path="$"):
    """Structured outputs need additionalProperties: false on every object. -> list of offending paths."""
    bad = []
    if schema.get("type") == "object" and schema.get("additionalProperties") is not False:
        bad.append(path)
    for k, v in schema.get("properties", {}).items():
        bad += closed(v, f"{path}.{k}")
    if isinstance(schema.get("items"), dict):
        bad += closed(schema["items"], f"{path}[]")
    for i, s in enumerate(schema.get("anyOf", [])):
        bad += closed(s, f"{path}|{i}")
    return bad


# Keywords the API-side constrained decoder may reject; they are enforced locally by validate() instead.
API_DROP = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "minLength", "maxLength",
            "maxItems", "pattern", "format", "$comment"}


def api_schema(schema):
    """Copy of the schema for output_config.format / response_format, without keywords enforced only locally."""
    if isinstance(schema, dict):
        out = {k: api_schema(v) for k, v in schema.items() if k not in API_DROP}
        if "properties" in schema:
            out["properties"] = {k: api_schema(v) for k, v in schema["properties"].items()}
        if isinstance(out.get("minItems"), int) and out["minItems"] > 1:
            out.pop("minItems")
        return out
    if isinstance(schema, list):
        return [api_schema(x) for x in schema]
    return schema


# ----------------------------------------------------------------------------- spec
class TaskSpec:
    def __init__(self, d, path=None):
        self.d, self.path = d, path
        miss = [k for k in REQUIRED if k not in d]
        if miss:
            raise SpecError(f"spec missing {miss}")
        self.name, self.prompt_version, self.model = d["name"], d["prompt_version"], d["model"]
        self.max_tokens, self.cap_usd = int(d["max_tokens"]), float(d["cap_usd"])
        self.layers = list(d["layers"])
        g = d["guideline"]
        self.guideline = "\n".join(g) if isinstance(g, list) else str(g)
        self.output_schema = d["output_schema"]
        self.reply_schema_gen = d.get("reply_schema") or self.output_schema
        self.examples = d.get("examples", [])
        self.mode = d.get("mode", "generate")
        self.verify = d.get("verify") or {}
        self.candidates = d.get("candidates") or []
        self.template = d.get("input_template", DEFAULT_TEMPLATE)
        self.effort, self.thinking = d.get("effort"), d.get("thinking")
        self.sha256 = hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
        self.check()

    def check(self):
        if self.mode not in ("generate", "verify"):
            raise SpecError(f"mode {self.mode!r} must be generate or verify")
        for nm, sc in (("output_schema", self.output_schema), ("reply_schema", self.reply_schema_gen)):
            bad = closed(sc)
            if bad:
                raise SpecError(f"{nm} objects without additionalProperties false: {bad}")
        if self.mode == "verify":
            labs = self.verify.get("labels") or {}
            if set(labs) != set(self.layers):
                raise SpecError(f"verify.labels keys {sorted(labs)} != layers {sorted(self.layers)}")
        for i, ex in enumerate(self.examples):
            e = validate(ex["output"], self.reply_schema(ex["input"].get("candidates")))
            if e:
                raise SpecError(f"example {i} does not match the reply schema: {e[:3]}")

    def reply_schema(self, cands=None):
        """Schema of one model reply: output_schema (generate) or the per-item verify schema (verify)."""
        if self.mode == "generate":
            return self.reply_schema_gen
        import candidates as C  # same folder
        return C.verify_schema(cands or [], self.verify["labels"], self.verify.get("max_add", 10))

    def finalize(self, item, reply, cands=None):
        """Validated reply -> (label, stats, errors). verify: assemble candidates + adds; generate: locate span
        offsets when the reply has spans without them. The label must match output_schema."""
        import candidates as C
        if self.mode == "verify":
            label, stats = C.assemble(item["text"], cands or [], reply, tuple(self.verify.get("reject", ("X", "N"))))
        elif isinstance(reply, dict) and isinstance(reply.get("spans"), list):
            label, stats = C.locate_spans(item["text"], reply)
        else:
            label, stats = reply, {}
        return label, stats, validate(label, self.output_schema)

    def max_tokens_for(self, cands=None):
        if self.mode == "verify" and cands is not None:  # ~11 tokens per decision + adds (teacher_v3 rule)
            return min(self.max_tokens, 12 * len(cands) + 40 * self.verify.get("max_add", 10) + 64)
        return self.max_tokens

    def system_text(self):
        """Guideline + layers + few-shot examples: the shared, cached system prefix."""
        parts = [self.guideline.strip(), "LAYERS: " + ", ".join(self.layers)]
        if self.mode == "verify":
            parts.append("Reply with JSON: {\"d\": {<candidate id>: <code>} for EVERY candidate id, \"add\": "
                         "[{\"layer\", \"text\", \"label\"}] for mentions no candidate covers}. Codes per layer: "
                         + "; ".join(f"{k}: {'/'.join(v)}" for k, v in self.verify["labels"].items()))
        for i, ex in enumerate(self.examples, 1):
            parts.append(f"EXAMPLE {i} (synthetic text, not real news)\n<example_input>\n"
                         + self.user_text(ex["input"]) + "\n</example_input>\n<example_reply>\n"
                         + json.dumps(ex["output"], ensure_ascii=False) + "\n</example_reply>")
        return "\n\n".join(parts)

    def user_text(self, item, cands=None):
        cands = cands if cands is not None else item.get("candidates")
        import candidates as C
        ctext = ("CANDIDATES (id \"text\" (hints)):\n" + C.render(cands)) if cands else ""
        return self.template.format(id=item.get("id", "example"), text=item["text"], candidates=ctext).strip()

    def prefix_tokens_est(self):
        return int(len(self.system_text()) / CHARS_PER_TOKEN)


def load(path):
    p = pathlib.Path(path)
    raw = p.read_text(encoding="utf-8")
    if p.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            raise SpecError("YAML spec needs PyYAML; install it or convert the spec to JSON")
        d = yaml.safe_load(raw)
    else:
        d = json.loads(raw)
    return TaskSpec(d, str(p))


def main(argv=None):
    a = argv if argv is not None else sys.argv[1:]
    if not a:
        print(__doc__)
        return 2
    s = load(a[0])
    pt = s.prefix_tokens_est()
    print(f"{s.name} {s.prompt_version} mode={s.mode} model={s.model} layers={s.layers} examples={len(s.examples)} "
          f"prefix~{pt} tok cap=${s.cap_usd} sha={s.sha256[:12]}")
    if pt < MIN_CACHE_TOKENS:
        print(f"WARN prefix ~{pt} tokens < {MIN_CACHE_TOKENS}: it will not cache on 5.x models")
    return 0


if __name__ == "__main__":
    sys.exit(main())
