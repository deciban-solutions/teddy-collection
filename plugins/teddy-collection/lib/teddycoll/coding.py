"""Viewer-comment coding support: prepare chunks, inter-rater agreement, aggregation.

A subject is whatever the video ranks or features (a picker, a watch, a brand). The coding
itself is done by the model against references/coding-brief.md; this module does only the
deterministic parts.
"""
import json
import random
import re
import unicodedata
from collections import Counter
from pathlib import Path

BRIEF = Path(__file__).resolve().parents[2] / "skills" / "teddy" / "references" / "coding-brief.md"
KAPPA_FIELDS = ("relevant", "judge_stance", "verdict_stance", "selection_stance", "best", "worst")
MIN_NONEMPTY = 5  # a kappa needs at least this many non-empty codings on each side
TYPES = ("contest", "review", "list")
TYPE_FIELDS = {"contest": '"judge_stance": str|null',
               "review": '"verdict_stance": str|null, "sentiment": {subject: "like"|"dislike"|"mixed"}',
               "list": '"selection_stance": str|null, "missing": [{"brand": str, "model": str|null}]'}
SENTIMENTS = ("like", "dislike", "mixed")
_TYPE_BLOCK = re.compile(r"<!-- type:(\w+) -->\n(.*?)<!-- /type -->\n", re.S)
_CODE = re.compile(r"[a-z0-9_]+")
# Brand key -> the name forms that start a `missing` entry for that brand (folded to ASCII
# lower case words, see _words). A brand not listed keys on its first word.
BRANDS = {
    "a-lange-sohne": ("a lange sohne", "a lange und sohne", "a lange", "lange sohne", "lange"),
    "audemars-piguet": ("audemars piguet", "audemars", "ap"),
    "baume-mercier": ("baume mercier", "baume et mercier"),
    "bell-ross": ("bell ross",),
    "carl-f-bucherer": ("carl f bucherer", "bucherer"),
    "christopher-ward": ("christopher ward",),
    "frederique-constant": ("frederique constant",),
    "girard-perregaux": ("girard perregaux",),
    "glashutte-original": ("glashutte original",),
    "grand-seiko": ("grand seiko",),
    "h-moser-cie": ("h moser cie", "h moser", "moser"),
    "jaeger-lecoultre": ("jaeger lecoultre", "jlc"),
    "maurice-lacroix": ("maurice lacroix",),
    "parmigiani-fleurier": ("parmigiani fleurier", "parmigiani"),
    "patek-philippe": ("patek philippe", "patek"),
    "raymond-weil": ("raymond weil",),
    "richard-mille": ("richard mille",),
    "tag-heuer": ("tag heuer",),
    "ulysse-nardin": ("ulysse nardin",),
    "vacheron-constantin": ("vacheron constantin", "vacheron"),
    "van-cleef-arpels": ("van cleef arpels", "van cleef"),
}


def _words(s):
    """ASCII-folded lower-case words: 'A. Lange & Söhne' -> 'a lange sohne'."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode("ascii")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())


def brand_key(entry):
    """The `missing` key of one entry ({brand, model} or a string): the brand field (else the
    name) matched against BRANDS by its leading words, else the first word, slugged."""
    if isinstance(entry, dict):
        name = _words(entry.get("brand")) or _words(entry.get("model"))
    else:
        name = _words(entry)
    padded = f"{name} "
    best = max(((len(f), k) for k, forms in BRANDS.items() for f in forms
                if padded.startswith(f + " ")), default=None)
    if best:
        return best[1]
    if isinstance(entry, dict) and entry.get("brand"):
        return re.sub(r" +", "-", name)
    return name.split(" ")[0] if name else ""


def normalize_subjects(subjects):
    """{key: [aliases]}, accepting a bare string as a one-alias list and null as none."""
    out = {}
    for k, v in (subjects or {}).items():
        if v is None:
            out[k] = []
        elif isinstance(v, str):
            out[k] = [v]
        else:
            out[k] = [str(a) for a in v]
    return out


def _read_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def _write_jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                          encoding="utf-8")


def _verdict_text(verdicts):
    if not verdicts:
        return ("not recorded in the dataset. Code `verdict_stance` only when the comment itself "
                "says what view of the presenter's it shares or rejects; otherwise null.")
    lines = [f'- {v.get("watch")}: stance **{v.get("stance") or "not recorded"}**; in his words: '
             f'"{v.get("quote") or "no quote recorded"}"' for v in verdicts]
    return "\n" + "\n".join(lines)


def render_brief(subjects, vtype="contest", verdicts=None):
    """The coders' brief for this video type: the type's own stance fields only. For a review,
    `verdicts` ([{watch, stance, quote}]) states the presenter's verdict coders compare with."""
    if vtype not in TYPES:
        raise ValueError(f"unknown video type {vtype!r}; one of {TYPES}")
    subjects = normalize_subjects(subjects)
    table = "| subject key | aliases |\n|---|---|\n" + "".join(
        f"| {k} | {', '.join(v)} |\n" for k, v in subjects.items())
    keys = ", ".join(f'"{k}"' for k in subjects)
    text = _TYPE_BLOCK.sub(lambda m: m.group(2) if m.group(1) == vtype else "",
                           BRIEF.read_text(encoding="utf-8"))
    return (text.replace("{{SUBJECTS}}", table.rstrip("\n")).replace("{{SUBJECT_KEYS}}", keys)
            .replace("{{TYPE_FIELDS}}", TYPE_FIELDS[vtype])
            .replace("{{VERDICT}}", _verdict_text(verdicts)))


def prepare(comments, subjects, keywords, run, chunk=300, audit_n=90, seed=0, vtype="contest",
            verdicts=None):
    """Filter comments to those naming a subject alias or keyword; write chunks, audit sample, brief."""
    subjects = normalize_subjects(subjects)
    run = Path(run)
    run.mkdir(parents=True, exist_ok=True)
    terms = [t.strip() for t in [t for v in subjects.values() for t in v] + list(keywords or [])]
    parts = []
    for t in terms:
        if not t:
            continue
        lead = r"\b" if re.match(r"\w", t[0]) else ""
        trail = r"\b" if re.match(r"\w", t[-1]) else ""
        parts.append(lead + re.escape(t) + trail)
    pattern = re.compile("|".join(parts), re.I) if parts else None
    by_id = {c["id"]: c for c in comments}
    rows = []
    for c in comments:
        text = c.get("text") or ""
        if pattern is None or not pattern.search(text):
            continue
        row = {"id": c["id"], "text": text, "likes": c.get("like_count") or 0}
        parent = by_id.get(c.get("parent"))
        if parent is not None and c.get("parent") != "root":
            row["parent_text"] = (parent.get("text") or "")[:400]
        rows.append(row)
    for old in run.glob("chunk_*.jsonl"):
        old.unlink()
    n_chunks = 0
    for i in range(0, len(rows), chunk):
        n_chunks += 1
        _write_jsonl(run / f"chunk_{n_chunks:02d}.jsonl", rows[i:i + chunk])
    audit = random.Random(seed).sample(rows, min(audit_n, len(rows)))
    _write_jsonl(run / "audit_sample.jsonl", audit)
    (run / "BRIEF.md").write_text(render_brief(subjects, vtype, verdicts), encoding="utf-8")
    return {"n_comments": len(comments), "n_candidates": len(rows), "n_chunks": n_chunks,
            "n_audit": len(audit), "seed": seed, "type": vtype}


def _cat(row, field):
    v = row.get(field)
    if field in ("best", "worst"):
        return tuple(sorted(v or []))
    return v


def _kappa(pairs):
    n = len(pairs)
    if n == 0:
        return 1.0
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in ca) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def agreement(primary, audit):
    """Cohen's kappa per field over the ids both lists code; `n` is the overlap size.

    Fields are those of KAPPA_FIELDS that any row carries (each video type has its own
    stance field). `n_nonempty[field]` counts the overlapping rows coded non-empty (true,
    a non-empty list, a non-null value) on each side; when either count is below
    MIN_NONEMPTY the kappa is None, since agreement on near-empty codings means nothing.
    """
    a = {r["id"]: r for r in primary}
    out = {}
    ids = [r["id"] for r in audit if r["id"] in a]
    b = {r["id"]: r for r in audit}
    fields = [f for f in KAPPA_FIELDS if any(f in r for r in list(a.values()) + list(b.values()))]
    out["audit_ids_missing_from_primary"] = sum(1 for i in b if i not in a)
    if not ids:
        out.update({f: None for f in fields})
        out.update({"n": 0, "no_overlap": True, "n_nonempty": {}})
        return out
    out["n_nonempty"] = {}
    for f in fields:
        ne = {"primary": sum(1 for i in ids if a[i].get(f)), "audit": sum(1 for i in ids if b[i].get(f))}
        out["n_nonempty"][f] = ne
        out[f] = (_kappa([(_cat(a[i], f), _cat(b[i], f)) for i in ids])
                  if min(ne.values()) >= MIN_NONEMPTY else None)
    out["n"] = len(ids)
    out["no_overlap"] = False
    return out


def aggregate(coded, likes, subjects=None):
    """Counts, like-weighted counts, stance, Borda, pairwise wins, first/last place, reasons."""
    if subjects is None:
        seen = []
        for r in coded:
            for f in ("full_ranking", "best", "worst", "underrated", "overrated"):
                for s in r.get(f) or []:
                    if s not in seen:
                        seen.append(s)
        subjects = seen
    subjects = list(subjects)
    n = len(subjects)
    zero = lambda: {s: 0 for s in subjects}
    out = {f: zero() for f in ("best", "worst", "best_weighted", "worst_weighted", "underrated",
                               "overrated", "borda", "first_place", "last_place")}
    out.update({"stance": Counter(), "pairwise_wins": Counter(), "reasons": Counter(),
                "verdict_stance": Counter(), "selection_stance": Counter(), "missing": Counter(),
                "n_comments": len(coded), "n_relevant": 0, "n_rankings": 0,
                "unknown_subjects": []})
    out["sentiment"] = {s: {v: 0 for v in SENTIMENTS} for s in subjects}
    other_codes, missing_names = set(), {}
    known = set(subjects)

    def keep(r, f):
        vals = []
        for s in r.get(f) or []:
            if s in known:
                vals.append(s)
            else:
                out["unknown_subjects"].append({"id": r["id"], "key": s, "field": f})
        return vals

    for r in coded:
        w = 1 + (likes.get(r["id"]) or 0)
        if r.get("relevant"):
            out["n_relevant"] += 1
        for f in ("best", "worst", "underrated", "overrated"):
            for s in set(keep(r, f)):
                out[f][s] += 1
                if f in ("best", "worst"):
                    out[f + "_weighted"][s] += w
        if r.get("judge_stance"):
            out["stance"][r["judge_stance"]] += 1
        for f in ("verdict_stance", "selection_stance"):
            if r.get(f):
                out[f][r[f]] += 1
        for s, v in (r.get("sentiment") or {}).items():
            if s not in known:
                out["unknown_subjects"].append({"id": r["id"], "key": s, "field": "sentiment"})
            elif v in SENTIMENTS:
                out["sentiment"][s][v] += 1
        brands = set()
        for m in r.get("missing") or []:
            name = (" ".join(str(x) for x in (m.get("brand"), m.get("model")) if x) if isinstance(m, dict)
                    else str(m)).strip()
            brand = brand_key(m)
            if brand:
                brands.add(brand)
                missing_names.setdefault(brand, set()).add(name)
        for brand in brands:
            out["missing"][brand] += 1
        folded = False
        for code in set(r.get("reasons") or []):
            if _CODE.fullmatch(code):
                out["reasons"][code] += 1
            else:
                other_codes.add(code)
                folded = True
        if folded:
            out["reasons"]["other"] += 1
        rank = keep(r, "full_ranking")
        if rank and len(set(rank)) >= n - 1:
            rank = list(dict.fromkeys(rank))
            rank += [s for s in subjects if s not in rank]  # the one omitted subject is last
            out["n_rankings"] += 1
            for pos, s in enumerate(rank):
                out["borda"][s] += n - 1 - pos
                for later in rank[pos + 1:]:
                    out["pairwise_wins"][f"{s}>{later}"] += 1
            out["first_place"][rank[0]] += 1
            out["last_place"][rank[-1]] += 1
    out["stance"] = dict(out["stance"])
    out["pairwise_wins"] = dict(out["pairwise_wins"])
    out["reasons"] = dict(out["reasons"])
    out["reasons_other"] = sorted(other_codes)
    for f in ("verdict_stance", "selection_stance", "missing"):
        out[f] = dict(out[f])
    out["missing_names"] = {b: sorted(n) for b, n in missing_names.items()}
    return out
