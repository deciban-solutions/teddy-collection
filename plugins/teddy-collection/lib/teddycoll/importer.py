"""Import a shipped example collection into the user's dataset and registry.

An example lives in `<plug-in>/examples/<name>/` as `records.json` (videos, appearances,
watches in the same format as a run's records), the published `index.html` and `img/`.
Importing copies the folder into `<data home>/examples/<name>/` (the plug-in folder is never
written), merges the records into the dataset and registers the example as a child set.
Importing again changes nothing.
"""
import json
import re
import shutil
from pathlib import Path

from . import dataset, paths, publish
from .sanitize import safe_url

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# What each example's child set is filed under in the taxonomy library.
TAXONOMY = {"two-watch-challenge": {"category": "two-watch", "version_id": "shipped:two-watch@1",
                                    "label": "provisional"}}


def list_examples() -> list:
    if not EXAMPLES_DIR.is_dir():
        return []
    return sorted(d.name for d in EXAMPLES_DIR.iterdir() if (d / "records.json").is_file())


def import_example(name: str, url: str = None) -> dict:
    """Load the example's records and register it as a child set; returns counts.

    `url` is where the user published the example's page. Without it the child is
    registered with no link (the parent shows its title as text); a rerun without `url`
    keeps a link registered earlier. Raises ValueError for an unknown name, a URL that is
    not http(s), or records that fail dataset validation (nothing is written then).
    """
    if not _NAME.match(name or "") or name not in list_examples():
        raise ValueError(f"unknown example {name!r}; available: {', '.join(list_examples()) or 'none'}")
    if url is not None and not safe_url(url):
        raise ValueError(f"--url must be an http or https link, not {url!r}")
    src = EXAMPLES_DIR / name
    records = json.loads((src / "records.json").read_text(encoding="utf-8"))
    rel = f"examples/{name}"
    for w in records.get("watches", []):
        for p in w.get("photos", []):
            if p.get("path") and not Path(p["path"]).is_absolute():
                p["path"] = f"{rel}/{p['path']}"  # relative to the data home
    ds = dataset.load()
    for v in records.get("videos", []):
        dataset.add_video(ds, v)
    for w in records.get("watches", []):
        dataset.upsert_watch(ds, w)
    for a in records.get("appearances", []):
        dataset.add_appearance(ds, a)
    errors = dataset.validate(ds)
    if errors:
        raise ValueError("example records failed validation: " + "; ".join(errors[:5]))
    taxonomy_info = TAXONOMY.get(name)
    video_ids = [v["id"] for v in records.get("videos", [])]
    existing = publish.registry_find(video_ids[0]) if video_ids else None
    dest = paths.data_home() / rel
    own = bool(existing) and Path(existing.get("build") or "").resolve() == dest.resolve()
    shutil.copytree(src, dest, dirs_exist_ok=True)
    dataset.save(ds)
    notice = None
    if existing and not own:
        # The user already has their own child set for this video; never repoint or unfreeze it.
        notice = (f"a video analysis of video {video_ids[0]} is already registered "
                  f"({existing.get('url') or 'no link'}); it was left untouched, "
                  "and the example's records were merged into your dataset")
        url = existing.get("url")
    elif own:
        # Our own earlier import: keep its hashes and published date; only a given url changes.
        url = url or existing.get("url")
        if url != existing.get("url"):
            reg = publish.load_registry()
            for c in reg["children"]:
                if set(c.get("video_ids", [])) == set(video_ids):
                    c["url"] = url
            publish._save_registry(reg)
    else:
        publish.registry_add("child", video_ids, url, dest, {}, type=records["videos"][0].get("type"),
                             taxonomy=taxonomy_info)
    return {"example": name, "videos": len(records.get("videos", [])),
            "watches": len(records.get("watches", [])),
            "appearances": len(records.get("appearances", [])), "url": url, "build": str(dest),
            "registered_own": not (existing and not own), "notice": notice}
