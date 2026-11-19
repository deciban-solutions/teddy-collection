"""An "unknown" spec value has to be earned by searching, and a known value is never dropped
silently.

Feedback 2026-11-18: a rebuild recorded a peer's `gmt_type` as "unknown" after re-reading
one article that did not state it, though two more searches found it, and it downgraded the
value an earlier run had recorded. Using 3 of 60 allowed searches, it stopped at the first
source.

So each watch (in records.json or peers.json) that records a spec field as unknown carries
`spec_search[field]`:

    {"tried": ["<query or url>", "<query or url>", ...],   # at least MIN_TRIED distinct
     "dropped_because": "<why the earlier value is wrong>"}  # only when an earlier value exists

`tried` lists the searches and pages looked at beyond the watch's listed sources. When the
dataset or another run already holds a known value for that watch and field, the record
keeps that value, or `dropped_because` says what source contradicts it.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import dataset, paths

MIN_TRIED = 2
UNKNOWN_VALUES = {"unknown", "n/a", "na", "?", "-", "—", ""}


def is_unknown(v) -> bool:
    return v is None or (isinstance(v, str) and v.strip().lower() in UNKNOWN_VALUES)


def _known_into(out: dict, watches):
    for w in watches or []:
        if not isinstance(w, dict):
            continue
        for f, v in (w.get("specs") or {}).items():
            if not is_unknown(v):
                out.setdefault(w.get("id"), {}).setdefault(f, v)


def prior_values(exclude_run: Path = None, ds: dict = None) -> dict:
    """{watch id: {field: known value}} from the dataset and every other run's records and
    peers. `exclude_run` (the current run) is skipped."""
    out = {}
    _known_into(out, (ds if ds is not None else dataset.load()).get("watches"))
    runs = paths.data_home() / "runs"
    skip = Path(exclude_run).resolve() if exclude_run else None
    if runs.is_dir():
        for r in sorted(runs.iterdir()):
            if not r.is_dir() or (skip and r.resolve() == skip):
                continue
            for name in ("records.json", "peers.json"):
                f = r / name
                try:
                    _known_into(out, json.loads(f.read_text(encoding="utf-8")).get("watches"))
                except (OSError, ValueError, AttributeError):
                    continue
    return out


def unknown_errors(watches, prior: dict, where: str) -> list:
    """Errors for unknown spec values that lack a search record, or that drop an earlier
    known value without saying why."""
    errs = []
    for w in watches or []:
        if not isinstance(w, dict):
            continue
        wid = w.get("id")
        search = w.get("spec_search") or {}
        if not isinstance(search, dict):
            errs.append(f"{where} watch {wid}: spec_search must be an object keyed by spec field")
            search = {}
        for f, v in (w.get("specs") or {}).items():
            if not is_unknown(v):
                continue
            s = search.get(f)
            tried = s.get("tried") if isinstance(s, dict) else None
            ok = isinstance(tried, list) and len({str(t).strip() for t in tried
                                                  if isinstance(t, str) and t.strip()}) >= MIN_TRIED
            if not ok:
                errs.append(f"{where} watch {wid}: specs.{f} is unknown but spec_search.{f}.tried "
                            f"lists fewer than {MIN_TRIED} searches or pages; search further "
                            "(the brand page, a press release, a dealer listing, a review) before "
                            "recording unknown")
            earlier = prior.get(wid, {}).get(f)
            if earlier is not None:
                why = s.get("dropped_because") if isinstance(s, dict) else None
                if not (isinstance(why, str) and why.strip()):
                    errs.append(f"{where} watch {wid}: specs.{f} was {earlier!r} in an earlier "
                                "record; keep it, or verify it and say in "
                                f"spec_search.{f}.dropped_because what source contradicts it")
    return errs
