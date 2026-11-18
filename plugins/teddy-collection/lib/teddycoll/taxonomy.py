"""Versioned taxonomy library: shipped (read-only) and user-branched criteria sets.

Version ids: `shipped:<category>@<n>` and `user:<category>@<n>.<m>`. Shipped files live
in SHIPPED_DIR (inside the plug-in, never written); user branches live in
`<data home>/taxonomies/user/` (override USER_DIR in tests).
"""
import ast
import copy
import json
import re
from datetime import date
from pathlib import Path

from . import paths

SHIPPED_DIR = Path(__file__).resolve().parents[2] / "taxonomies" / "shipped"
USER_DIR = None  # None -> paths.data_home()/taxonomies/user

LABELS = ("compiled", "provisional")
KINDS = ("must", "more_is_better", "evidence_settled")
EVIDENCE_CLASSES = ("deductive", "research", "practitioner", "contested")
CHECK_TYPES = ("deterministic", "judged")
REQUIRED = ("id", "category", "version", "label", "paradigm", "created", "change_log", "layers")
CRITERION_KEYS = ("key", "statement", "kind", "evidence_class", "check", "sources")
RATIFIER_ROLES = ("the builder", "an independent expert", "independent experts")
FR_ENFORCEMENT = ("machine_gate", "judged_review")
_SLUG = re.compile(r"^[a-z0-9_-]+$")
_ID = re.compile(r"^(shipped|user):([a-z0-9_-]+)@(\d+)(?:\.(\d+))?$")


def _user_dir() -> Path:
    d = Path(USER_DIR) if USER_DIR else paths.data_home() / "taxonomies" / "user"
    d.mkdir(parents=True, exist_ok=True)
    return d


def parse_id(version_id: str):
    """-> (kind, category, major, minor|None); ValueError if malformed."""
    m = _ID.match(version_id)
    if not m:
        raise ValueError(f"bad version id: {version_id!r}")
    kind, cat, n, minor = m.groups()
    if (kind == "shipped") != (minor is None):
        raise ValueError(f"bad version id: {version_id!r} (shipped is @<n>, user is @<n>.<m>)")
    return kind, cat, int(n), None if minor is None else int(minor)


def _file(version_id: str) -> Path:
    kind, cat, n, minor = parse_id(version_id)
    if kind == "shipped":
        return Path(SHIPPED_DIR) / f"{cat}@{n}.json"
    return _user_dir() / f"{cat}@{n}.{minor}.json"


# ---------- validation ----------

def validate(t) -> list:
    """Plain-python check of the format documented in taxonomies/schema.json."""
    errs = []
    if not isinstance(t, dict):
        return ["taxonomy is not an object"]
    for k in REQUIRED:
        if k not in t:
            errs.append(f"missing required key: {k}")
    if "category" in t and not (isinstance(t["category"], str) and _SLUG.match(t["category"])):
        errs.append("category must match ^[a-z0-9_-]+$")
    if "label" in t and t["label"] not in LABELS:
        errs.append(f"label must be one of {LABELS}, got {t['label']!r}")
    if isinstance(t.get("id"), str):
        try:
            kind, cat, n, minor = parse_id(t["id"])
            ver = str(n) if minor is None else f"{n}.{minor}"
            if t.get("category") != cat:
                errs.append(f"id category {cat!r} != category {t.get('category')!r}")
            if str(t.get("version")) != ver:
                errs.append(f"id version {ver!r} != version {t.get('version')!r}")
        except ValueError as e:
            errs.append(str(e))
    if "change_log" in t and not isinstance(t["change_log"], list):
        errs.append("change_log must be a list")
    layers = t.get("layers")
    if isinstance(layers, dict):
        for name in ("wearer", "watch"):
            if name not in layers:
                errs.append(f"layers missing {name}")
        for name, crits in layers.items():
            if name not in ("wearer", "watch", "pair"):
                errs.append(f"unknown layer: {name}")
            elif not isinstance(crits, list):
                errs.append(f"layers.{name} must be a list")
            else:
                for i, c in enumerate(crits):
                    errs.extend(_validate_criterion(c, f"layers.{name}[{i}]"))
    elif "layers" in t:
        errs.append("layers must be an object")
    if "coherence" in t and not isinstance(t["coherence"], list):
        errs.append("coherence must be a list")
    fields = t.get("spec_fields") if isinstance(t.get("spec_fields"), dict) else {}
    if "spec_fields" in t and not isinstance(t["spec_fields"], dict):
        errs.append("spec_fields must be an object")
    for layer, crits in (layers or {}).items() if isinstance(layers, dict) else ():
        for c in crits if isinstance(crits, list) else ():
            chk = c.get("check") if isinstance(c, dict) else None
            if isinstance(chk, dict) and chk.get("type") == "deterministic":
                for name in sorted(_rule_fields(chk.get("rule")) - set(fields)):
                    errs.append(f"layers.{layer}.{c.get('key')}: rule reads {name!r}, "
                                "which is not listed in spec_fields")
    if "warrant" in t:
        errs.extend(_warrant_errors(t["warrant"], t.get("label")))
    for i, p in enumerate(t.get("teddy_principles", []) or []):
        for k in ("quote", "video", "timestamp"):
            if not isinstance(p, dict) or k not in p:
                errs.append(f"teddy_principles[{i}] missing {k}")
    return errs


def _warrant_errors(w, label) -> list:
    if not isinstance(w, dict) or not isinstance(w.get("ratified"), bool):
        return ["warrant must be an object with a boolean ratified"]
    errs = []
    if label != "compiled":
        errs.append("only a compiled taxonomy carries a warrant")
    for k in ("freeze_commit", "prereg"):
        if not (isinstance(w.get(k), str) and w[k].strip()):
            errs.append(f"warrant.{k} must be a non-empty string")
    if w["ratified"]:
        if w.get("ratified_by") not in RATIFIER_ROLES:
            errs.append(f"warrant.ratified_by must be one of {RATIFIER_ROLES}")
        cp = w.get("catch_power")
        if isinstance(cp, bool) or not isinstance(cp, (int, float)) or not 0 < cp <= 1:
            errs.append("warrant.catch_power must be a number in (0, 1] when ratified")
    for k in ("not_enforced_here", "not_validated_in_compile"):
        v = w.get(k, [])
        if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
            errs.append(f"warrant.{k} must be a list of strings")
    ne = w.get("not_exported", [])
    if not isinstance(ne, list) or not all(
            isinstance(x, dict) and isinstance(x.get("key"), str) and isinstance(x.get("reason"), str)
            and x.get("kind") in KINDS for x in ne):
        errs.append("warrant.not_exported must be a list of {key, kind, reason}")
    return errs


def _rule_fields(rule) -> set:
    """Field names a rule reads; empty for a rule that does not parse (reported elsewhere)."""
    try:
        return {n.id for n in ast.walk(ast.parse(rule, mode="eval")) if isinstance(n, ast.Name)}
    except (SyntaxError, TypeError, ValueError):
        return set()


def _validate_criterion(c, where) -> list:
    errs = []
    if not isinstance(c, dict):
        return [f"{where} is not an object"]
    for k in CRITERION_KEYS:
        if k not in c:
            errs.append(f"{where} missing {k}")
    if "kind" in c and c["kind"] not in KINDS:
        errs.append(f"{where}.kind must be one of {KINDS}")
    if "evidence_class" in c and c["evidence_class"] not in EVIDENCE_CLASSES:
        errs.append(f"{where}.evidence_class must be one of {EVIDENCE_CLASSES}")
    chk = c.get("check")
    if "check" in c:
        if not isinstance(chk, dict) or chk.get("type") not in CHECK_TYPES:
            errs.append(f"{where}.check.type must be one of {CHECK_TYPES}")
        elif chk["type"] == "deterministic":
            if not isinstance(chk.get("rule"), str) or not chk["rule"].strip():
                errs.append(f"{where}.check.rule required for deterministic checks")
            else:
                errs.extend(f"{where}.check: {e}" for e in rule_syntax_errors(chk["rule"]))
            pl = chk.get("planted")
            if not isinstance(pl, dict) or not isinstance(pl.get("pass"), list) \
                    or not isinstance(pl.get("fail"), list) or not pl["pass"] or not pl["fail"]:
                errs.append(f"{where}.check.planted needs at least one pass case and one fail case")
            if "checks_only" in chk and not (isinstance(chk["checks_only"], str)
                                             and chk["checks_only"].strip()):
                errs.append(f"{where}.check.checks_only must be a non-empty string: what part "
                            "of the statement the rule tests")
    if "sources" in c and not isinstance(c["sources"], list):
        errs.append(f"{where}.sources must be a list")
    return errs


# ---------- storage ----------

def get(version_id: str) -> dict:
    f = _file(version_id)
    if not f.exists():
        raise KeyError(f"no such taxonomy version: {version_id}")
    return json.loads(f.read_text(encoding="utf-8"))


def list_versions(category: str = None) -> list:
    """All version ids (shipped then user), each group sorted numerically."""
    out = []
    for kind, d in (("shipped", Path(SHIPPED_DIR)), ("user", _user_dir())):
        found = []
        if d.is_dir():
            for f in d.glob("*.json"):
                m = re.match(r"^(.+)@(\d+)(?:\.(\d+))?$", f.stem)
                if not m:
                    continue
                cat, n, minor = m.group(1), int(m.group(2)), m.group(3)
                if (kind == "shipped") != (minor is None) or (category and cat != category):
                    continue
                found.append((cat, n, int(minor or 0), f"{kind}:{f.stem}"))
        out.extend(v for *_, v in sorted(found))
    return out


def resolve(category: str) -> dict:
    """The user's newest branch of the newest shipped version, else that shipped version.

    A branch of an older shipped version (user:gmt@1.1 once shipped:gmt@2 exists) no longer
    wins: a plug-in update that ships a newer, better-checked version takes effect. The old
    branch stays in the library and can still be named by id."""
    ids = list_versions(category)
    shipped = [v for v in ids if v.startswith("shipped:")]
    user = [v for v in ids if v.startswith("user:")]
    if shipped:
        newest = parse_id(shipped[-1])[2]
        current = [v for v in user if parse_id(v)[2] >= newest]
        return get(current[-1] if current else shipped[-1])
    if user:
        return get(user[-1])
    raise KeyError(f"no taxonomy for category: {category}")


def branch(version_id: str, additions: dict, reason: str) -> str:
    """Write a new provisional user version derived from version_id; return its id."""
    base = get(version_id)
    kind, cat, n, minor = parse_id(version_id)
    t = copy.deepcopy(base)
    for k, v in additions.items():
        if k == "layers":
            for layer, crits in v.items():
                cur = t["layers"].setdefault(layer, [])
                for c in crits:
                    for i, old in enumerate(cur):
                        if old.get("key") == c.get("key"):
                            cur[i] = c
                            break
                    else:
                        cur.append(c)
        elif k in ("coherence", "teddy_principles"):
            t.setdefault(k, []).extend(v)
        elif k == "paradigm":
            t["paradigm"] = v
        elif k == "spec_fields":
            if not isinstance(v, dict):
                raise ValueError("spec_fields addition must be an object {field: meaning and type}")
            t.setdefault("spec_fields", {}).update(v)
        else:
            raise ValueError(f"unsupported addition key: {k}")
    used = [int(i.rsplit(".", 1)[1]) for i in list_versions(cat)
            if i.startswith("user:") and parse_id(i)[2] == n]
    new_minor = max(used, default=0) + 1
    new_id = f"user:{cat}@{n}.{new_minor}"
    t.update(id=new_id, version=f"{n}.{new_minor}", label="provisional",
             created=date.today().isoformat())
    t.pop("warrant", None)  # a branch is provisional; the base's warrant does not cover its additions
    entry = {"date": date.today().isoformat(), "reason": reason, "additions": additions,
             "derived_from": version_id}
    if base.get("label") == "compiled":
        entry["base_ratified"] = bool((base.get("warrant") or {}).get("ratified"))
    t["change_log"] = list(base.get("change_log", [])) + [entry]
    errs = validate(t)
    if errs:
        raise ValueError("branch would be invalid: " + "; ".join(errs))
    _file(new_id).write_text(json.dumps(t, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return new_id


# ---------- safe expression language ----------

_CMP = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b,
        ast.Lt: lambda a, b: a < b, ast.LtE: lambda a, b: a <= b,
        ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b,
        ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b}


def _const(node):
    if isinstance(node, ast.Constant) and (node.value is None or
                                           isinstance(node.value, (int, float, str, bool))):
        return node.value
    raise ValueError(f"disallowed constant: {ast.dump(node)}")


def _ev(node, spec):
    if isinstance(node, ast.Expression):
        return _ev(node.body, spec)
    if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        is_and = isinstance(node.op, ast.And)
        for v in node.values:
            if bool(_ev(v, spec)) != is_and:
                return not is_and
        return is_and
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _ev(node.operand, spec)
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, (int, float))
            and not isinstance(node.operand.value, bool)):
        return -node.operand.value
    if isinstance(node, ast.Compare):
        left = _ev(node.left, spec)
        for op, right_node in zip(node.ops, node.comparators):
            if type(op) not in _CMP:
                raise ValueError(f"disallowed operator: {type(op).__name__}")
            right = _ev(right_node, spec)
            try:
                ok = _CMP[type(op)](left, right)
            except TypeError as e:
                raise ValueError(f"type error in comparison: {e}")
            if not ok:
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        if node.id not in spec:
            raise ValueError(f"unknown field: {node.id}")
        return spec[node.id]
    if isinstance(node, ast.Constant):
        return _const(node)
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_const(e) for e in node.elts]
    raise ValueError(f"disallowed expression element: {type(node).__name__}")


def _static(node):
    """Raise ValueError unless every node is one `_ev` accepts, on every branch."""
    if isinstance(node, ast.Expression):
        return _static(node.body)
    if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
        for v in node.values:
            _static(v)
        return
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _static(node.operand)
    if (isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, (int, float))
            and not isinstance(node.operand.value, bool)):
        return
    if isinstance(node, ast.Compare):
        for op in node.ops:
            if type(op) not in _CMP:
                raise ValueError(f"disallowed operator: {type(op).__name__}")
        for n in (node.left, *node.comparators):
            _static(n)
        return
    if isinstance(node, ast.Name):
        return
    if isinstance(node, ast.Constant):
        _const(node)
        return
    if isinstance(node, (ast.List, ast.Tuple)):
        for e in node.elts:
            _const(e)
        return
    raise ValueError(f"disallowed expression element: {type(node).__name__}")


def rule_syntax_errors(rule) -> list:
    """[] when `rule` parses and uses only the safe language on every branch."""
    if not isinstance(rule, str) or not rule.strip():
        return ["rule must be a non-empty string"]
    try:
        _static(ast.parse(rule, mode="eval"))
    except SyntaxError as e:
        return [f"syntax error in rule {rule!r}: {e.msg}"]
    except ValueError as e:
        return [f"rule {rule!r}: {e}"]
    return []


def evaluate(rule: str, spec: dict):
    if not isinstance(rule, str):
        raise ValueError(f"rule must be a string, got {type(rule).__name__}")
    if not isinstance(spec, dict):
        raise ValueError(f"case must be an object, got {type(spec).__name__}")
    try:
        tree = ast.parse(rule, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"syntax error in rule {rule!r}: {e.msg}")
    return _ev(tree, spec)


def run_checks(t: dict) -> list:
    """Errors for every deterministic rule that errors, fails a planted pass, or passes a planted fail."""
    errs = []
    for layer, crits in t.get("layers", {}).items():
        for c in crits:
            chk = c.get("check", {})
            if not isinstance(chk, dict) or chk.get("type") != "deterministic":
                continue
            where = f"{layer}.{c.get('key')}"
            planted = chk.get("planted", {})
            for expect, cases in (("pass", planted.get("pass", [])), ("fail", planted.get("fail", []))):
                for case in cases:
                    try:
                        got = bool(evaluate(chk.get("rule", ""), case))
                    except ValueError as e:
                        errs.append(f"{where}: rule error on planted {expect} case {case}: {e}")
                        continue
                    if got != (expect == "pass"):
                        errs.append(f"{where}: planted {expect} case {case} "
                                    f"{'failed' if expect == 'pass' else 'passed'} rule {chk['rule']!r}")
    return errs


NOT_ASSESSABLE = "not assessable"


def _lower(v):
    if isinstance(v, str):
        return v.lower()
    if isinstance(v, list):
        return [_lower(x) for x in v]
    return v


def _lower_literals(rule: str) -> str:
    tree = ast.parse(rule, mode="eval")
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            node.value = node.value.lower()
    return ast.unparse(tree)


# spec values that mean "not known" (compared stripped and lower-case)
UNKNOWN_VALUES = {"unknown", "n/a", "na", "?", "-", "\u2014", ""}


def _numeric_fields(tax: dict, tree) -> set:
    """Fields a rule treats as numbers: declared `number…` in spec_fields, or compared
    directly with a numeric (non-boolean) constant."""
    out = {f for f, d in (tax.get("spec_fields") or {}).items()
           if isinstance(d, str) and d.strip().lower().startswith("number")}
    num = lambda n: (isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                     and not isinstance(n.value, bool))
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            sides = [node.left, *node.comparators]
            if any(num(x) for x in sides):
                out |= {x.id for x in sides if isinstance(x, ast.Name)}
    return out


def _unknown(v, numeric: bool) -> bool:
    if v is None:
        return True
    if isinstance(v, str) and v.strip().lower() in UNKNOWN_VALUES:
        return True
    return numeric and isinstance(v, bool)


def score(tax: dict, record: dict) -> dict:
    """{"<layer>.<key>": "y" | "n" | "not assessable"} for every deterministic criterion.

    A rule is not assessable when a field it reads is missing or None, holds a not-known string
    (UNKNOWN_VALUES: "unknown", "n/a", "na", "?", "-", "—" or empty), holds a boolean where the
    rule needs a number, or has the wrong type for the comparison. Strings (field values and
    rule literals) compare lower-case.
    """
    specs = (record or {}).get("specs") or {}
    out = {}
    for layer, crits in tax.get("layers", {}).items():
        for c in crits:
            chk = c.get("check", {})
            if not isinstance(chk, dict) or chk.get("type") != "deterministic":
                continue
            cid = f"{layer}.{c.get('key')}"
            rule = _lower_literals(chk["rule"])
            tree = ast.parse(rule, mode="eval")
            fields = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
            numeric = _numeric_fields(tax, tree)
            vals = {f: specs.get(f) for f in fields}
            if any(_unknown(v, f in numeric) for f, v in vals.items()):
                out[cid] = NOT_ASSESSABLE
                continue
            try:
                out[cid] = "y" if evaluate(rule, {f: _lower(v) for f, v in vals.items()}) else "n"
            except ValueError as e:
                if not str(e).startswith("type error"):
                    raise
                out[cid] = NOT_ASSESSABLE
    return out


def partial_rules(tax: dict) -> dict:
    """{"<layer>.<key>": checks_only} for every deterministic criterion whose rule tests only
    part of its statement; a rule mark there settles that part, not the whole criterion."""
    out = {}
    for layer, crits in tax.get("layers", {}).items():
        for c in crits:
            chk = c.get("check", {})
            if isinstance(chk, dict) and chk.get("type") == "deterministic" and chk.get("checks_only"):
                out[f"{layer}.{c.get('key')}"] = chk["checks_only"]
    return out


# ---------- formalized-reasoner import ----------

class ImportRefused(ValueError):
    """A compile the importer cannot carry without guessing; `reasons` lists every problem."""

    def __init__(self, reasons):
        self.reasons = list(reasons)
        super().__init__("import refused: " + "; ".join(self.reasons))


# formalized-reasoner kinds and evidence sources, mapped onto this format's own
_FR_KIND = {"constraining": "must", "adaptive": "evidence_settled", "value": "more_is_better"}
_KIND_STRICTNESS = ("must", "evidence_settled", "more_is_better")      # strictest first
_FR_SOURCE = {"A": "deductive", "B": "deductive", "C": "research", "D": "practitioner",
              "E": "contested"}
_CLASS_STRENGTH = ("deductive", "research", "practitioner", "contested")  # strongest first
_NOT_ENFORCED_NOTE = ("Validated in the compile but not enforced by the plug-in: criteria "
                      "listed here are judged on the pages, and the plug-in does not yet score "
                      "coherence factors, which need facts about the buyer.")


def _load_json(path, what, reasons):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        reasons.append(f"cannot read {what} {path}: {e}")
        return None


def _list(spec, key, reasons, *, dicts=True):
    """spec[key] as a list (of dicts when `dicts`), [] when absent; a reason when malformed."""
    v = spec.get(key)
    if v is None:
        return []
    if not isinstance(v, list) or (dicts and not all(isinstance(x, dict) for x in v)):
        reasons.append(f"{key} must be a list" + (" of objects" if dicts else ""))
        return []
    return v


def _canon_set(spec, key, reasons) -> set:
    """accepted / rejected: a list of canon strings, or an object keyed by canon."""
    v = spec.get(key)
    if v is None:
        return set()
    keys = list(v) if isinstance(v, (list, dict)) else None
    if keys is None or not all(isinstance(k, str) for k in keys):
        reasons.append(f"{key} must be a list of concept canons or an object keyed by them")
        return set()
    return set(keys)


def _name_tokens(ratifier) -> set:
    """Words of the ratifier's name (the parenthesised part when there is one), longer than
    two characters, lower-case; used to refuse a shipped file that would carry the name."""
    if not isinstance(ratifier, str):
        return set()
    m = re.search(r"\(([^)]*)\)", ratifier)
    text = m.group(1) if m else ratifier
    roles = {"author", "builder", "owner", "the", "independent", "expert", "experts", "panel"}
    return {w for w in re.findall(r"[a-z]+", text.lower()) if len(w) > 2 and w not in roles}


def _ratification(rec, rec_bytes, spec, side, reasons) -> dict:
    """The warrant's ratification fields. A record counts only when it is bound to this
    compile (its slice and freeze_commit match, or the sidecar names its sha256) and its
    fields are well formed. The ratifier's name is never copied: the sidecar states a role."""
    import hashlib
    out = {"ratified": False, "ratified_by": None, "catch_power": None, "ratified_on": None,
           "ratification_sha256": None}
    if rec is None:
        return out
    if not isinstance(rec, dict):
        reasons.append("ratification record must be a JSON object")
        return out
    digest = hashlib.sha256(rec_bytes).hexdigest()
    bound = ((rec.get("slice") == spec.get("slice") and spec.get("slice"))
             and rec.get("freeze_commit") == spec.get("freeze_commit")) \
        or side.get("ratification_sha256") == digest
    if not bound:
        reasons.append("ratification record is not bound to this compile: it must carry this "
                       "compile's slice and freeze_commit, or the sidecar must name its "
                       "ratification_sha256")
        return out
    cp, fp = rec.get("catch_power"), rec.get("false_positive_on_coherent")
    if not isinstance(rec.get("ratified"), bool):
        reasons.append("ratification record: ratified must be true or false")
    if isinstance(cp, bool) or not isinstance(cp, (int, float)) or not 0 <= cp <= 1:
        reasons.append("ratification record: catch_power must be a number from 0 to 1")
        cp = None
    if not isinstance(fp, list):
        reasons.append("ratification record: false_positive_on_coherent must be a list")
    graded = rec.get("graded")
    out.update(catch_power=cp, ratification_sha256=digest,
               ratified_on=graded[:10] if isinstance(graded, str) and graded else None)
    if rec.get("ratified") is True and cp and isinstance(fp, list) and not fp:
        role = side.get("ratifier_role")
        if role not in RATIFIER_ROLES:
            reasons.append(f"ratifier_role must be one of {RATIFIER_ROLES} (a role, never a "
                           f"name), got {role!r}")
        out.update(ratified=True, ratified_by=role if role in RATIFIER_ROLES else None)
    return out


def import_fr(spec_json, checks_json, *, category: str, version: str,
              ratification_json=None) -> dict:
    """Convert a formalized-reasoner compile into a `compiled` shipped taxonomy.

    - `spec_json`: the compile's spec.json (paradigm, owner_desiderata, concepts with `canon`
      and `serves`, accepted/rejected, edges, coherence_factors, debt, freeze_commit, prereg).
    - `checks_json`: the sidecar the compile writes for this plug-in: `spec_fields`,
      `ratifier_role`, optional `ratification_sha256` and `sources`, and `criteria` keyed by
      concept canon, each with its `layer`, optional `sources` and, for a script-tested
      criterion, a `rule` in this format's safe language with `planted` pass and fail cases.
    - `ratification_json`: the coherence-ratification record, when there is one.

    Nothing is defaulted: a kind comes from the strictest desideratum the concept serves,
    an evidence class from the weakest source among them, a layer from the sidecar. Concepts
    the compile kept as judged (neither accepted nor rejected) are carried and disclosed.
    Every problem is collected and raised together as ImportRefused.
    """
    reasons = []
    if not (isinstance(category, str) and _SLUG.match(category)):
        reasons.append(f"category must match ^[a-z0-9_-]+$, got {category!r}")
    if not (isinstance(version, str) and version.isdigit()):
        reasons.append(f"version must be a whole number for a shipped taxonomy, got {version!r}")
    spec = _load_json(spec_json, "spec", reasons)
    side = _load_json(checks_json, "sidecar", reasons)
    rec = rec_bytes = None
    if ratification_json is not None:
        rec = _load_json(ratification_json, "ratification record", reasons)
        try:
            rec_bytes = Path(ratification_json).read_bytes()
        except OSError:
            rec_bytes = b""
    for obj, what in ((spec, "spec"), (side, "sidecar")):
        if obj is not None and not isinstance(obj, dict):
            reasons.append(f"{what} is not a JSON object")
    if not isinstance(spec, dict) or not isinstance(side, dict):
        raise ImportRefused(reasons)

    par = spec.get("paradigm")
    stance = par.get("culture") if isinstance(par, dict) else None
    if not (isinstance(stance, str) and stance.strip()):
        reasons.append("paradigm missing: the compile has no paradigm with a stance sentence "
                       "(culture)")
    for k in ("freeze_commit", "prereg"):
        if not (isinstance(spec.get(k), str) and spec[k].strip()):
            reasons.append(f"{k} missing: a compiled taxonomy must name its frozen "
                           "pre-registration")
    desid = {}
    for d in _list(spec, "owner_desiderata", reasons):
        did = d.get("id")
        if not isinstance(did, str) or not did:
            reasons.append("a desideratum has no string id")
        elif did in desid:
            reasons.append(f"desideratum {did} is listed twice")
        else:
            desid[did] = d
            if d.get("kind") not in _FR_KIND:
                reasons.append(f"desideratum {did}: unknown kind {d.get('kind')!r}")
            if d.get("source") not in _FR_SOURCE:
                reasons.append(f"desideratum {did}: unknown evidence source {d.get('source')!r}")
    if not desid:
        reasons.append("owner_desiderata missing: the compile records no owner desiderata")

    fields = side.get("spec_fields") or {}
    if not isinstance(fields, dict) or not all(isinstance(v, str) for v in fields.values()):
        reasons.append("sidecar spec_fields must be an object of field: meaning-and-type strings")
        fields = fields if isinstance(fields, dict) else {}
    entries = side.get("criteria")
    if not isinstance(entries, dict):
        reasons.append("sidecar criteria must be an object keyed by concept canon")
        entries = {}
    registry = side.get("sources")
    if registry is not None:
        need = ("url", "title", "publisher", "date", "checked")
        if not isinstance(registry, list) or not all(
                isinstance(r, dict) and all(isinstance(r.get(k), str) for k in need) for r in registry):
            reasons.append(f"sidecar sources must be a list of objects with {need}")
    accepted = _canon_set(spec, "accepted", reasons)
    rejected = _canon_set(spec, "rejected", reasons)
    left_out = {}
    raw = side.get("not_exported", [])
    if not isinstance(raw, list):
        reasons.append("sidecar not_exported must be a list of {canon, reason} objects")
        raw = []
    for e in raw:
        if not (isinstance(e, dict) and isinstance(e.get("canon"), str)
                and isinstance(e.get("reason"), str) and e["reason"].strip()):
            reasons.append(f"sidecar not_exported entry {e!r} needs a canon and a non-empty reason")
        elif e["canon"] in left_out:
            reasons.append(f"sidecar not_exported lists {e['canon']!r} twice")
        else:
            left_out[e["canon"]] = e["reason"].strip()
    for k in sorted(set(left_out) & set(entries)):
        reasons.append(f"{k}: listed in both criteria and not_exported")

    layers = {"wearer": [], "watch": [], "pair": []}
    not_enforced, not_validated, dropped, seen, canons = [], [], [], set(), set()
    not_exported = []
    for c in _list(spec, "concepts", reasons):
        key = c.get("canon")
        if not (isinstance(key, str) and _SLUG.match(key)):
            reasons.append(f"a concept has no usable canon ({c.get('name')!r}); the sidecar is "
                           "keyed by canon, so none is guessed")
            continue
        if key in canons:
            reasons.append(f"{key}: the concept is listed twice")
            continue
        canons.add(key)
        if key in rejected:
            dropped.append(key)
            continue
        seen.add(key)
        serves = c.get("serves")
        if not isinstance(serves, list) or not serves or not all(isinstance(s, str) for s in serves):
            reasons.append(f"{key}: serves no owner desideratum (a non-empty list of ids is "
                           "needed), so its kind cannot be set")
            continue
        unknown = [s for s in serves if s not in desid]
        if unknown:
            reasons.append(f"{key}: serves unknown desiderata {unknown}")
            continue
        kinds = {_FR_KIND.get(desid[s].get("kind")) for s in serves}
        classes = {_FR_SOURCE.get(desid[s].get("source")) for s in serves}
        if None in kinds or None in classes:
            continue  # reported with the desideratum
        kind = next(k for k in _KIND_STRICTNESS if k in kinds)
        evidence = next(k for k in reversed(_CLASS_STRENGTH) if k in classes)
        if key in left_out:
            if key not in entries:
                not_exported.append({"key": key, "kind": kind, "reason": left_out[key]})
            continue
        entry = entries.get(key)
        if not isinstance(entry, dict):
            reasons.append(f"{key}: no sidecar entry (every kept concept needs its layer, "
                           "and its plug-in rule if it is script-tested)")
            continue
        layer = entry.get("layer")
        if not isinstance(layer, str) or layer not in layers:
            reasons.append(f"{key}: layer must be wearer, watch or pair, got {layer!r}")
            continue
        if "rule" in entry:
            rule = entry["rule"]
            check = {"type": "deterministic", "rule": rule, "planted": entry.get("planted")}
            only, whole = entry.get("checks_only"), entry.get("rule_covers_statement")
            if only is not None and whole is not None:
                reasons.append(f"{key}: give checks_only or rule_covers_statement, not both")
                continue
            if only is not None:
                if not (isinstance(only, str) and only.strip()):
                    reasons.append(f"{key}: checks_only must say, in words, what part of the "
                                   "statement the rule tests")
                    continue
                check["checks_only"] = only.strip()
            elif whole is not True:
                reasons.append(f"{key}: a rule must declare its scope: checks_only (the part of "
                               "the statement it tests) or rule_covers_statement: true")
                continue
            crit_errs = _validate_criterion(
                {"key": key, "statement": "-", "kind": kind, "evidence_class": evidence,
                 "check": check, "sources": []}, key)
            if crit_errs:
                reasons.extend(crit_errs)
                continue
            missing = sorted(_rule_fields(rule) - set(fields))
            if missing:
                reasons.append(f"{key}: rule reads {missing}, not listed in spec_fields")
                continue
            errs = run_checks({"layers": {layer: [{"key": key, "check": check}]}})
            if errs:
                reasons.extend(errs)
                continue
        elif "planted" in entry:
            reasons.append(f"{key}: planted cases given but no rule")
            continue
        else:
            check = {"type": "judged"}
            (not_enforced if key in accepted else not_validated).append(key)
        sources = entry.get("sources", [])
        if not isinstance(sources, list) or not all(isinstance(x, str) for x in sources):
            reasons.append(f"{key}: sources must be a list of URL strings")
            continue
        desc = c.get("description") or c.get("name") or key
        layers[layer].append({"key": key, "statement": str(desc), "kind": kind,
                              "evidence_class": evidence, "check": check,
                              "sources": sources, "serves": list(serves)})
    for extra in sorted(set(entries) - seen - rejected):
        reasons.append(f"sidecar names {extra!r}, which is not a kept concept in the compile")
    for k in sorted(set(left_out) - seen):
        reasons.append(f"not_exported names {k!r}, which is not a kept concept in the compile")
    for ghost in sorted(accepted - canons):
        reasons.append(f"accepted names {ghost!r}, which is not a concept in the compile")

    coherence = []
    for f in _list(spec, "coherence_factors", reasons):
        name = f.get("name")
        if not (isinstance(name, str) and name):
            reasons.append("a coherence factor has no name")
            continue
        if f.get("validated") is not True:
            reasons.append(f"coherence factor {name}: not validated in the compile")
            continue
        if f.get("enforcement") not in FR_ENFORCEMENT:
            reasons.append(f"coherence factor {name}: enforcement must be one of "
                           f"{FR_ENFORCEMENT}, got {f.get('enforcement')!r}")
            continue
        coherence.append({k: f[k] for k in ("name", "scope", "kind", "enforcement", "rationale")
                          if k in f})
        if f["enforcement"] == "machine_gate":
            not_enforced.append(name)

    edges = _list(spec, "edges", reasons)
    debt = _list(spec, "debt", reasons)
    warrant = {"source_slice": spec.get("slice"), "freeze_commit": spec.get("freeze_commit"),
               "prereg": spec.get("prereg"),
               **_ratification(rec, rec_bytes or b"", spec, side, reasons),
               "unresolved_debt": sum(1 for d in debt if not d.get("resolved")),
               "edges": {"total": len(edges),
                         "validated": sum(1 for e in edges if e.get("warrant") == "validated")},
               "not_enforced_here": not_enforced, "not_validated_in_compile": not_validated,
               "not_exported": not_exported,
               "not_enforced_note": _NOT_ENFORCED_NOTE}
    if reasons:
        raise ImportRefused(reasons)

    today = date.today().isoformat()
    t = {"id": f"shipped:{category}@{version}", "category": category, "version": version,
         "label": "compiled", "paradigm": stance.strip(), "created": today,
         "change_log": [{"date": today,
                         "reason": f"imported from formalized-reasoner compile {spec.get('slice')!r} "
                                   f"(freeze {spec.get('freeze_commit')})",
                         "additions": {"criteria": sum(len(v) for v in layers.values())},
                         "dropped_rejected_concepts": dropped}],
         "spec_fields": fields,
         "layers": {k: v for k, v in layers.items() if v or k != "pair"},
         "coherence": coherence, "teddy_principles": [], "warrant": warrant}
    if registry is not None:
        t["sources"] = registry
    names = _name_tokens(rec.get("ratifier")) if isinstance(rec, dict) else set()
    words = set(re.findall(r"[a-z]+", json.dumps(t).lower()))
    if names & words:
        raise ImportRefused([f"the ratifier's name ({len(names & words)} word(s) of it) appears in "
                             "the compile's text; a shipped file must not carry a person's name"])
    errs = validate(t)
    if errs:
        raise ImportRefused(errs)
    return t
