"""Dataset records: videos, appearances and watches, one JSON file per type.

Histories (status, price, sources, photos) are merged by appending dated entries,
never overwriting. Files are written to a temp file then renamed.
"""
import copy
import json
import os
from pathlib import Path

from . import frames, paths

TYPES = ("videos", "appearances", "watches")
CONFIDENCE = ("labelled_on_screen", "legible_on_dial", "matched_to_specs", "inferred", "unknown")
ROLES = ("picked", "reviewed", "ranked", "listed", "mentioned", "worn")
STANCES = ("positive", "mixed", "negative", "none")
# history field -> sort key (None keeps insertion order)
HISTORIES = {"status_history": "date", "price_history": "date", "sources": None, "photos": None}
# history field -> the field that identifies an entry (a newer entry replaces the older)
IDENT = {"photos": "path"}


def _dir() -> Path:
    return paths.data_home() / "dataset"


def load() -> dict:
    ds = {}
    for t in TYPES:
        f = _dir() / f"{t}.json"
        ds[t] = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else []
    return ds


def save(ds: dict) -> None:
    d = _dir()
    d.mkdir(parents=True, exist_ok=True)
    for t in TYPES:
        tmp = d / f"{t}.json.tmp"
        tmp.write_text(json.dumps(ds.get(t, []), indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, d / f"{t}.json")


def _merge_history(old: list, new: list, key, ident=None) -> list:
    """Append new entries not already present. With `ident` (a field name), an entry
    with the same value of that field replaces the old one in place (newest wins)."""
    out = list(old)
    for entry in new:
        if ident and entry.get(ident):
            same = [i for i, e in enumerate(out) if e.get(ident) == entry[ident]]
            if same:
                out[same[0]] = entry
                for i in reversed(same[1:]):
                    del out[i]
                continue
        if entry not in out:
            out.append(entry)
    if key:
        out.sort(key=lambda e: e.get(key) or "")
    return out


def add_video(ds: dict, v: dict) -> None:
    for i, cur in enumerate(ds["videos"]):
        if cur["id"] == v["id"]:
            ds["videos"][i] = {**cur, **v}
            return
    ds["videos"].append(copy.deepcopy(v))


def _ts_key(t):
    """Sort timestamps by time ('9:05' before '39:30'); anything unparseable goes last."""
    s = frames.ts_seconds(t)
    return (0, s, str(t)) if s is not None else (1, 0.0, str(t))


def add_appearance(ds: dict, a: dict) -> None:
    ident = (a["video_id"], a["watch_id"])
    for i, cur in enumerate(ds["appearances"]):
        if (cur["video_id"], cur["watch_id"]) == ident:
            merged = {**cur, **a}
            merged["timestamps"] = sorted(set(cur.get("timestamps", [])) | set(a.get("timestamps", [])),
                                          key=_ts_key)
            ds["appearances"][i] = merged
            return
    ds["appearances"].append(copy.deepcopy(a))


def upsert_watch(ds: dict, w: dict) -> None:
    for i, cur in enumerate(ds["watches"]):
        if cur["id"] == w["id"]:
            merged = {**cur, **{k: v for k, v in w.items() if k not in HISTORIES}}
            for field, key in HISTORIES.items():
                merged[field] = _merge_history(cur.get(field, []), w.get(field, []), key, IDENT.get(field))
            ds["watches"][i] = merged
            return
    new = copy.deepcopy(w)
    for field, key in HISTORIES.items():
        new[field] = _merge_history([], w.get(field, []), key, IDENT.get(field))
    ds["watches"].append(new)


def validate(ds: dict) -> list:
    errors = []
    videos = {v.get("id"): v for v in ds.get("videos", [])}
    appearances = ds.get("appearances", [])
    watch_ids = {w.get("id") for w in ds.get("watches", [])}
    for a in appearances:
        if a.get("video_id") not in videos:
            errors.append(f"appearance {a.get('video_id')}/{a.get('watch_id')}: unknown video_id")
        if a.get("watch_id") not in watch_ids:
            errors.append(f"appearance {a.get('video_id')}/{a.get('watch_id')}: unknown watch_id")
        if a.get("role") not in ROLES:
            errors.append(f"appearance {a.get('video_id')}/{a.get('watch_id')}: role {a.get('role')!r} not one of {ROLES}")
        for t in a.get("timestamps") or []:
            if frames.ts_seconds(t) is None:
                errors.append(f"appearance {a.get('video_id')}/{a.get('watch_id')}: timestamps entry "
                              f"{str(t)!r} is not a video time (seconds, m:ss or h:mm:ss)")
        verdict = a.get("verdict")
        if verdict is not None and (not isinstance(verdict, dict) or verdict.get("stance") not in STANCES):
            errors.append(f"appearance {a.get('video_id')}/{a.get('watch_id')}: verdict.stance "
                          f"{(verdict or {}).get('stance') if isinstance(verdict, dict) else verdict!r} "
                          f"not one of {STANCES}")
    for w in ds.get("watches", []):
        wid = w.get("id")
        conf = w.get("confidence")
        if conf not in CONFIDENCE:
            errors.append(f"watch {wid}: confidence {conf!r} not one of {CONFIDENCE}")
        if not str(w.get("basis") or "").strip():
            errors.append(f"watch {wid}: basis is empty")
        if "family" in w:
            if not isinstance(w["family"], bool):
                errors.append(f"watch {wid}: family must be true or false")
            elif w["family"] and w.get("reference"):
                errors.append(f"watch {wid}: a family record has no single reference; "
                              "set reference to null or drop family")
        if conf == "labelled_on_screen":
            if not any(p.get("kind") == "frame" for p in w.get("photos", [])):
                errors.append(f"watch {wid}: labelled_on_screen needs a photo of kind frame")
            if not any(a.get("watch_id") == wid for a in appearances):
                errors.append(f"watch {wid}: labelled_on_screen but no appearance links it to a video")
            for a in appearances:
                v = videos.get(a.get("video_id"))
                if a.get("watch_id") == wid and v is not None and not v.get("on_screen_cards"):
                    errors.append(f"watch {wid}: labelled_on_screen but video {v['id']} has on_screen_cards false")
    return errors
