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
    for i, p in enumerate(t.get("teddy_principles", []) or []):
        for k in ("quote", "video", "timestamp"):
            if not isinstance(p, dict) or k not in p:
                errs.append(f"teddy_principles[{i}] missing {k}")
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
            pl = chk.get("planted")
            if not isinstance(pl, dict) or not isinstance(pl.get("pass"), list) \
                    or not isinstance(pl.get("fail"), list) or not pl["pass"] or not pl["fail"]:
                errs.append(f"{where}.check.planted needs at least one pass case and one fail case")
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
    """The user's newest branch for the category, else the newest shipped version."""
    for kind in ("user", "shipped"):
        ids = [v for v in list_versions(category) if v.startswith(kind + ":")]
        if ids:
            return get(ids[-1])
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
    t["change_log"] = list(base.get("change_log", [])) + [
        {"date": date.today().isoformat(), "reason": reason, "additions": additions}]
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


# ---------- formalized-reasoner import ----------

def import_fr(spec_json: Path) -> dict:
    """Convert a compiled formalized-reasoner spec.json into a `compiled` taxonomy dict."""
    spec = json.loads(Path(spec_json).read_text(encoding="utf-8"))
    category = re.sub(r"[^a-z0-9_-]+", "-", str(spec.get("slice", "imported")).lower()).strip("-") \
        or "imported"
    unmapped = []
    criteria = []
    for c in spec.get("concepts", []):
        key = c.get("canon") or c.get("name")
        if not key:
            unmapped.append("concept without canon/name")
            continue
        text = c.get("description") or c.get("name") or key
        check = {"type": "judged", "planted": {"pass": [], "fail": []}}
        rule = c.get("rule")
        if isinstance(rule, str) and rule.strip():
            planted = c.get("planted")
            try:
                ast.parse(rule, mode="eval")
                if isinstance(planted, dict) and planted.get("pass") and planted.get("fail"):
                    check = {"type": "deterministic", "rule": rule, "planted": planted}
                else:
                    unmapped.append(f"{key}: rule has no planted pass and fail cases; imported as judged")
            except SyntaxError:
                unmapped.append(f"{key}: rule is not a safe expression; imported as judged")
        criteria.append({"key": key, "statement": text, "kind": "more_is_better",
                         "evidence_class": "contested", "check": check, "sources": []})
    coherence = []
    for ckey in ("coherence", "coherence_factors"):
        for f in spec.get(ckey, []) or []:
            coherence.append(f if isinstance(f, dict) else {"factor": str(f)})
    if not coherence:
        unmapped.append("no coherence factors present in spec")
    if spec.get("edges"):
        unmapped.append(f"{len(spec['edges'])} concept edges not mapped")
    if spec.get("accepted"):
        unmapped.append("accepted measure code not mapped (kept judged unless a rule was present)")
    unmapped.append("kind and evidence_class defaulted to more_is_better / contested")
    today = date.today().isoformat()
    t = {"id": f"shipped:{category}@1", "category": category, "version": "1",
         "label": "compiled", "paradigm": str(spec.get("culture", "")), "created": today,
         "change_log": [{"date": today, "reason": "imported from formalized-reasoner compiled spec",
                         "additions": {"criteria": len(criteria)}, "unmapped": unmapped}],
         "layers": {"wearer": [], "watch": criteria}, "coherence": coherence,
         "teddy_principles": []}
    return t
