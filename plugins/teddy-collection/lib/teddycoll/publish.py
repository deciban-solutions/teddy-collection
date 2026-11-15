"""Publish manifest, registry and local fallback.

The registry is `data_home()/registry.json`:
{"parent": {"url", "updated"} | null,
 "children": [{"video_ids", "url", "type", "published", "build", "hashes", "taxonomy"}]}
written atomically (temp file + rename).
"""
import json
import os
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

from . import dataset, paths

SERIES_PATTERNS = [r"What \$[\d,]+ Buys You .* (\d{4})", r"Most Worn Watches .* (\d{4})",
                   r"Top Watches of (\d{4})"]

STANDALONE_HEAD = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
                   '<meta name="viewport" content="width=device-width, initial-scale=1, '
                   'viewport-fit=cover"></head><body>')


# ---------- registry ----------

def registry_path() -> Path:
    return paths.data_home() / "registry.json"


def load_registry() -> dict:
    """The registry; a missing file is empty."""
    f = registry_path()
    try:
        reg = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"{f} is not valid JSON ({e}); fix or remove it") from e
    if not isinstance(reg, dict) or not isinstance(reg.get("children") or [], list):
        raise ValueError(f"{f} has an unexpected shape: expected an object with a 'children' list")
    if reg.get("parent") is not None and not isinstance(reg["parent"], dict):
        raise ValueError(f"{f} has an unexpected shape: 'parent' must be an object or null; "
                         "fix or remove it")
    bad = [i for i, c in enumerate(reg.get("children") or []) if not isinstance(c, dict)]
    if bad:
        raise ValueError(f"{f} has an unexpected shape: children {bad} are not objects; "
                         "fix or remove them")
    return {"parent": reg.get("parent"), "children": list(reg.get("children") or [])}


def _save_registry(reg: dict) -> None:
    f = registry_path()
    fd, tmp = tempfile.mkstemp(dir=f.parent, prefix=".registry-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(reg, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, f)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def registry_add(kind, video_ids, url, build, hashes, type=None, taxonomy=None) -> dict:
    """Record a published build. `parent` sets the parent entry; `child` replaces the
    entry with the same video_ids set, else appends. Returns the stored entry."""
    if kind not in ("parent", "child"):
        raise ValueError(f"kind must be parent or child, not {kind!r}")
    reg = load_registry()
    today = date.today().isoformat()
    if kind == "parent":
        reg["parent"] = {"url": url, "updated": today}
        _save_registry(reg)
        return reg["parent"]
    entry = {"video_ids": list(video_ids), "url": url, "type": type, "published": today,
             "build": str(Path(build).resolve()), "hashes": dict(hashes or {}), "taxonomy": taxonomy}
    key = set(entry["video_ids"])
    kids = [c for c in reg["children"] if set(c.get("video_ids", [])) != key]
    pos = next((i for i, c in enumerate(reg["children"]) if set(c.get("video_ids", [])) == key), None)
    if pos is None:
        kids.append(entry)
    else:
        kids.insert(pos, entry)
    reg["children"] = kids
    _save_registry(reg)
    return entry


def registry_find(video_id: str):
    """The child entry covering `video_id`, or None."""
    for c in load_registry()["children"]:
        if video_id in c.get("video_ids", []):
            return c
    return None


# ---------- series ----------

def _norm(s: str) -> str:
    s = re.sub(r"[^\w\s$]", "", (s or "").casefold())
    return re.sub(r"\s+", " ", s).strip()


def _series_key(title: str):
    for i, pat in enumerate(SERIES_PATTERNS):
        m = re.search(pat, title or "")
        if m:
            rest = title[:m.start(1)] + title[m.end(1):]
            return i, _norm(rest), m.group(1)
    return None


def series_candidates(video: dict) -> list:
    """Registered videos whose titles match the same pattern and non-year text, with a
    different year. The user confirms each before it is linked."""
    mine = _series_key(video.get("title"))
    if not mine:
        return []
    titles = {v["id"]: v for v in dataset.load()["videos"]}
    out = []
    for c in load_registry()["children"]:
        for vid in c.get("video_ids", []):
            other = titles.get(vid)
            if not other or vid == video.get("id"):
                continue
            k = _series_key(other.get("title"))
            if k and k[0] == mine[0] and k[1] == mine[1] and k[2] != mine[2]:
                out.append({"video_id": vid, "title": other["title"], "year": k[2],
                            "url": c.get("url")})
    return out


# ---------- publish manifest and local fallback ----------

def files_map(build) -> dict:
    """{published path: absolute source} for every file but index.html and manifest.json."""
    build = Path(build)
    out = {}
    for p in sorted(build.rglob("*")):
        if p.is_file():
            rel = p.relative_to(build).as_posix()
            if rel not in ("index.html", "manifest.json"):
                out[rel] = str(p.resolve())
    return out


def export_local(build, dest) -> Path:
    """A standalone folder: index.html wrapped as a full document, plus img/."""
    build, dest = Path(build), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    body = (build / "index.html").read_text(encoding="utf-8")
    (dest / "index.html").write_text(STANDALONE_HEAD + body + "</body></html>", encoding="utf-8")
    if (build / "img").is_dir():
        shutil.copytree(build / "img", dest / "img", dirs_exist_ok=True)
    return dest
