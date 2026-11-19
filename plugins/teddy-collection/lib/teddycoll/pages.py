"""Page assembly: child sets and the parent collection, built from the dataset.

Each page is a template under templates/pages/ (its own CSS plus a skeleton). Pages
built from data (gallery, overview facts, sources table, what changed, timeline, watch
index, taxonomy library, child list) are rendered by `render`; model-written analysis
arrives as HTML fragments in `<run>/fragments/<page>.html`. Every view is merged into
templates/shell.html with its CSS scoped to `#v-<page>` (ported from the 2026-11-14
two-watch hub build) and a hash router that also follows in-page anchors.

Numbers: a fragment writes every number as `<span data-num="dotted.key">…</span>` and
`fill_numbers` fills it from numbers.json. `check_bare_numbers` fails the build on a
typed τ, κ or percentage outside those spans (blockquote, code and `data-spec` cells
are exempt).
"""
import json
import os
import re
import shutil
from datetime import date
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from . import coding, dataset, frames, paths, publish, render, sanitize, specs, taxonomy
from .sanitize import safe_url, scope_css, split_style

PLUGIN = Path(__file__).resolve().parents[2]
TEMPLATES = PLUGIN / "templates"
SIZE_BUDGET = 16 * 1024 * 1024
LONG_EDGE, SMALL_EDGE = 900, 700
COMMERCIAL_NOTE = ('<p class="commercial"><b>Commercial context.</b> Teddy\'s videos state that '
                   "his store is an authorized dealer for over 35 brands. Keep that in mind when "
                   "reading the criteria he states or the watches he favours.</p>")

# page key -> (nav title, nav subtitle)
PAGE_META = {
    "overview": ("Overview", "The video and the short answer"),
    "gallery": ("Gallery", "Every watch shown, with photo and source"),
    "criteria-inference": ("Criteria inference", "Which criteria reproduce the ranking"),
    "taxonomy": ("Buyer's checklist", "What to check in this category, and why"),
    "wearers": ("Wearer profiles", "What each person wore, and why they picked"),
    "landscape": ("Landscape", "Where the watches sit among alternatives"),
    "scorecard": ("Scorecard", "The watch measured against the checklist"),
    "list-criteria": ("Implied criteria", "What the list actually rewards"),
    "left-out": ("Left out", "Strong candidates the list omits"),
    "viewers": ("Viewer pulse", "What the comments said, coded twice"),
    "teddy-criteria": ("Teddy's criteria", "What he states, with quotes and timestamps"),
    "what-changed": ("What changed", "Watches added and dropped, price moves"),
    "sources": ("Sources and method", "Where every fact came from"),
    "parent-overview": ("Overview", "The collection and its sample"),
    "timeline": ("Timeline", "Videos by upload date, with watch-world events"),
    "watch-index": ("Watch index", "Every watch once, with status and where it appears"),
    "taxonomy-library": ("Checklist library", "Every buyer's checklist, its versions and how far each is checked"),
    "child-list": ("Video analyses", "Every analysis, by video type and date"),
}
TYPE_PAGES = {"contest": ["criteria-inference", "taxonomy", "wearers"],
              "review": ["landscape", "taxonomy", "scorecard"],
              "list": ["landscape", "list-criteria", "left-out"]}
GENERATED = ("gallery",)                    # no fragment expected
PARTLY_GENERATED = ("overview", "sources", "what-changed")
PARENT_PAGES = ["parent-overview", "timeline", "watch-index", "taxonomy-library", "child-list"]
_COMMERCIAL = ("teddy-criteria", "criteria-inference", "scorecard", "list-criteria", "left-out",
               "taxonomy", "wearers")


class BareNumberError(ValueError):
    """A number on a page was typed instead of read from numbers.json."""


def page_set(vtype: str, related: bool) -> list:
    if vtype not in TYPE_PAGES:
        raise ValueError(f"unknown video type {vtype!r}; version 1 builds {sorted(TYPE_PAGES)}")
    return (["overview", "gallery"] + TYPE_PAGES[vtype] + ["viewers", "teddy-criteria"]
            + (["what-changed"] if related else []) + ["sources"])


def _pid(key: str) -> str:
    return "overview" if key == "parent-overview" else key


# ---------- registry ----------

def _load_registry() -> dict:
    """data_home()/registry.json (shared with publish). Missing file = empty."""
    return publish.load_registry()


# ---------- numbers ----------

def _lookup(numbers, key):
    cur = numbers
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            raise KeyError(f"numbers.json has no key {key!r}")
    return cur


def _fmt(v, key) -> str:
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return f"{v:.2f}"
    if isinstance(v, str):
        return escape(v)
    raise TypeError(f"numbers.json key {key!r} holds a {type(v).__name__}, not a number or string")


_SPAN = re.compile(r'(<span\b[^>]*\bdata-num="([^"]+)"[^>]*>)(.*?)(</span>)', re.S)


def fill_numbers(html: str, numbers: dict) -> str:
    """Fill every `<span data-num="key">` from numbers; a missing key raises KeyError."""
    return _SPAN.sub(lambda m: m.group(1) + _fmt(_lookup(numbers, m.group(2)), m.group(2))
                     + m.group(4), html)


_BARE = [re.compile(p) for p in (r"τ\s*[=≈]\s*[-−+]?\.?\d", r"κ\s*[=≈]?\s*[-−+]?\.?\d", r"\d\s*%")]
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta",
         "source", "track", "wbr"}


class _Visible(HTMLParser):
    """Visible text with exempt regions (data-num spans, blockquote, code, data-spec,
    script, style) replaced by a NUL so a number inside one never pairs with text outside."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.skip, self.parts = [], 0, []

    def handle_starttag(self, tag, attrs):
        if tag in _VOID:
            return
        a = dict(attrs)
        exempt = (tag in ("blockquote", "code", "script", "style") or "data-spec" in a
                  or (tag == "span" and "data-num" in a))
        self.stack.append((tag, exempt))
        if exempt:
            if not self.skip:
                self.parts.append("\0")
            self.skip += 1

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for _, ex in self.stack[i:]:
                    self.skip -= ex
                del self.stack[i:]
                return

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def check_bare_numbers(html: str) -> list:
    """Snippets of typed τ, κ or percentage values in visible text; [] when clean."""
    p = _Visible()
    p.feed(html)
    p.close()
    text = "".join(p.parts)
    hits = []
    for rx in _BARE:
        for m in rx.finditer(text):
            hits.append(text[max(0, m.start() - 30):m.end() + 10].replace("\0", "").strip())
    return hits


# ---------- fragments ----------

def _prepare_fragment(pid, html, run, images):
    """-> body. Refuses <script>/<style> (fragments carry no CSS), passes the fragment
    through the allow-list (sanitize.clean_fragment), namespaces its ids (so ref-1 on two
    pages never ties), and copies its img/ images into the build."""
    body = sanitize.clean_fragment(pid, sanitize.fragment_body(pid, html))
    ids = set(re.findall(r'(?<![\w-])id="([^"]+)"', body))
    body = re.sub(r'(?<![\w-])id="([^"]+)"', lambda m: f'id="{pid}-{m.group(1)}"', body)
    body = re.sub(r'(?<![\w-])href="#([^"]+)"', lambda m: f'href="#{pid}-{m.group(1)}"'
                  if m.group(1) in ids else m.group(0), body)

    def local(name):
        """Copy run/img/<name> into the build; the name must be one plain path component."""
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or name in (".", ".."):
            raise ValueError(f"fragment {pid}: image img/{name} must be a single file name in img/")
        src = Path(run) / "img" / name
        if not src.is_file():
            raise ValueError(f"fragment {pid}: image img/{name} not found in {Path(run) / 'img'}")
        return images.add(src, "frag-" + Path(name).stem)
    return re.sub(r'(?<![\w-])src="img/([^"]+)"', lambda m: f'src="{local(m.group(1))}"', body)


# ---------- images and size ----------

class _Images:
    def __init__(self):
        self.items, self.missing = {}, []

    def add(self, src: Path, stem: str) -> str:
        name = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-") + ".jpg"
        if self.items.get(name, src) != src:
            raise ValueError(f"two images would share the name img/{name}")
        self.items[name] = src
        return f"img/{name}"

    def photo(self, w, base_dirs):
        """The watch's primary photo (a frame if any) -> (img path or None, photo dict)."""
        photos = w.get("photos") or []
        ph = next((p for p in photos if p.get("kind") == "frame"), photos[0] if photos else None)
        if not ph:
            return None, None
        p = Path(ph.get("path", ""))
        cands = [p] if p.is_absolute() else [Path(b) / p for b in base_dirs]
        src = next((c for c in cands if c.is_file()), None)
        if src is None:
            self.missing.append(f"{w.get('id')}: {ph.get('path')}")
            return None, ph
        return self.add(src, "watch-" + str(w.get("id"))), ph

    def place(self, build: Path, edge: int):
        d = build / "img"
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        for name, src in self.items.items():
            dest = d / name
            if src.suffix.lower() in (".jpg", ".jpeg"):
                shutil.copyfile(src, dest)
                frames.resize(dest, edge, 82)
            else:
                tmp = d / (dest.stem + src.suffix.lower())
                shutil.copyfile(src, tmp)
                out = frames.resize(tmp, edge, 82)
                tmp.unlink()
                if out != dest:
                    os.replace(out, dest)


def _size(build: Path) -> int:
    return sum(f.stat().st_size for f in build.rglob("*") if f.is_file())


# ---------- assembly ----------

def _template(name):
    return (TEMPLATES / "pages" / f"{name}.html").read_text(encoding="utf-8")


def _view(key, set_label, content, footer, h1="", lede="", home=False):
    pid = _pid(key)
    t = _template(key)
    _no_bare(f"template {key}", split_style(t)[1])
    for k, v in (("{{SET}}", escape(set_label)), ("{{H1}}", escape(h1)), ("{{LEDE}}", escape(lede)),
                 ("<!--COMMERCIAL-->", COMMERCIAL_NOTE if key in _COMMERCIAL else ""),
                 ("<!--FOOTER-->", footer)):
        t = t.replace(k, v)
    css, body = split_style(t.replace("<!--CONTENT-->", content))
    title = PAGE_META[key][0]
    hidden = "" if home else " hidden"
    section = (f'<section class="view" id="v-{pid}" data-title="{escape(title)}"{hidden}>\n'
               f"<div data-banner></div>\n<div data-today></div>\n{body.strip()}\n</section>")
    return scope_css(css, pid), section


def _assemble(title, kicker, keys, styles, views, sidefoot, backlink=""):
    shell = (TEMPLATES / "shell.html").read_text(encoding="utf-8")
    home = _pid(keys[0])
    nav = "\n".join(f'<li><a href="#{_pid(k)}" data-view="{_pid(k)}"><span class="nt">'
                    f'{escape(PAGE_META[k][0])}</span><span class="ns">{escape(PAGE_META[k][1])}'
                    "</span></a></li>" for k in keys)
    brand = (f'<a class="brand" href="#{home}" data-view="{home}"><span class="k">{escape(kicker)}'
             f'</span><span class="n">{escape(title)}</span></a>')
    for k, v in (("{{TITLE_JS}}", sanitize.js_string(title)), ("{{TITLE}}", escape(title)),
                 ("{{HOME}}", home), ("<!--BRAND-->", brand), ("<!--BACKLINK-->", backlink),
                 ("<!--NAV-->", nav), ("<!--SIDEFOOT-->", sidefoot),
                 ("/*PAGE_STYLES*/", "\n".join(styles))):
        shell = shell.replace(k, v)
    return shell.replace("<!--VIEWS-->", "\n".join(views))


def _no_bare(where, html):
    """Bare-number check for model-written fragments and template prose only; text that
    comes from the dataset (titles, basis lines) is not checked."""
    hits = check_bare_numbers(html)
    if hits:
        raise BareNumberError(f"{where}: typed numbers outside data-num spans: " + " | ".join(hits[:5]))


def _check_page(html):
    ids = re.findall(r'\bid="([^"]+)"', html)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise ValueError(f"duplicate element ids: {dup[:5]}")
    idset = set(ids)
    for h in re.findall(r'href="#([^"]*)"', html):
        if h and h not in idset and f"v-{h}" not in idset:
            raise ValueError(f"in-page link #{h} has no target")
    ext = re.findall(r'<img\b[^>]*\bsrc="((?:https?:)?//[^"]+)"', html)
    if ext:
        raise ValueError(f"external images are not allowed in an artifact: {ext[:3]}")


def _finish(build: Path, html: str, images: _Images, manifest: dict) -> dict:
    """Write index.html and img/, keep the total within SIZE_BUDGET, write manifest.json."""
    if build.exists():
        shutil.rmtree(build)
    build.mkdir(parents=True)
    (build / "index.html").write_text(html, encoding="utf-8")
    images.place(build, LONG_EDGE)
    downsized = False
    if _size(build) > SIZE_BUDGET:
        images.place(build, SMALL_EDGE)
        downsized = True
        if _size(build) > SIZE_BUDGET:
            raise ValueError(f"build is {_size(build)} bytes, over the {SIZE_BUDGET}-byte budget "
                             f"even with images at {SMALL_EDGE} px")
    manifest.update(downsized=downsized, bytes=_size(build), images=len(images.items),
                    missing_photos=images.missing, built=date.today().isoformat())
    (build / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False),
                                         encoding="utf-8")
    return {"build": str(build), **manifest}


def _write_json(f: Path, obj):
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, f)


# ---------- related sets ----------

def diff_videos(older_id: str, newer_id: str) -> dict:
    """Watches added and dropped between two videos, price moves on shared watches (from
    each appearance's price_quoted) and criteria added (from each video's optional
    `criteria` list)."""
    ds = dataset.load()
    videos = {v["id"]: v for v in ds["videos"]}
    for vid in (older_id, newer_id):
        if vid not in videos:
            raise ValueError(f"unknown video id {vid!r}")
    apps = {vid: {a["watch_id"]: a for a in ds["appearances"] if a["video_id"] == vid}
            for vid in (older_id, newer_id)}
    old, new = apps[older_id], apps[newer_id]
    shared = [w for w in old if w in new]
    moves = []
    for w in shared:
        p0, p1 = old[w].get("price_quoted") or {}, new[w].get("price_quoted") or {}
        if p0.get("amount") is None or p1.get("amount") is None:
            continue
        if (p0["amount"], p0.get("currency")) == (p1["amount"], p1.get("currency")):
            continue
        same = p0.get("currency") == p1.get("currency")
        moves.append({"watch_id": w, "from": p0, "to": p1,
                      "currency": p1.get("currency") if same else None,
                      "delta": p1["amount"] - p0["amount"] if same else None})
    c0 = videos[older_id].get("criteria") or []
    crit = [c for c in videos[newer_id].get("criteria") or [] if c not in c0]
    added = [w for w in new if w not in old]
    dropped = [w for w in old if w not in new]
    return {"older": older_id, "newer": newer_id, "added": added, "dropped": dropped,
            "shared": shared, "price_moves": moves, "criteria_added": crit,
            "counts": {"added": len(added), "dropped": len(dropped), "shared": len(shared),
                       "price_moves": len(moves)}}


# ---------- child ----------

def _checked(watches) -> str:
    dates = [s.get("checked_at") for w in watches for s in w.get("sources") or [] if s.get("checked_at")]
    return max(dates) if dates else "not recorded"


def _run_taxonomy(run: Path):
    """`<run>/taxonomy.json` ({category, version_id, label}, written by the skill) or None."""
    f = run / "taxonomy.json"
    if not f.is_file():
        return None
    t = json.loads(f.read_text(encoding="utf-8"))
    if not isinstance(t, dict) or not t.get("version_id"):
        raise ValueError(f"{f}: needs a version_id")
    taxonomy.parse_id(t["version_id"])
    if t.get("label") not in taxonomy.LABELS:
        raise ValueError(f"{f}: label must be one of {taxonomy.LABELS}, got {t.get('label')!r}")
    try:
        lib = taxonomy.get(t["version_id"])
    except (OSError, ValueError, KeyError):
        lib = None
    if isinstance(lib, dict):
        if lib.get("label") != t["label"]:
            raise ValueError(f"{f}: label {t['label']!r} disagrees with the library's "
                             f"{lib.get('label')!r} for {t['version_id']}")
        t["warrant"] = lib.get("warrant")
        t.update(render._branch_info(lib))
    elif t["label"] == "compiled":
        t["warrant"] = None
    return t


def _words(s) -> str:
    """Lower-case words separated by single spaces, framed by spaces for whole-word search."""
    return " " + " ".join(re.split(r"[^a-z0-9]+", str(s or "").lower())).strip() + " "


def subject_check(run: Path, video_ids=None) -> list:
    """Keys of `<run>/coding/subjects.json` that name no watch this run recorded; [] if none.

    Candidates are only this run's watches: those with an appearance (in the dataset or
    `<run>/records.json`) whose video is one of `video_ids` (default: the videos in
    `<run>/records.json`), plus every watch in `<run>/peers.json`. A watch another video
    recorded does not count. A key matches a candidate when it equals the candidate's id,
    or when one of the key's alias phrases (its subjects.json values) appears as whole
    words in the candidate's brand, model and reference ('sky-dweller' matches
    "Rolex Sky-Dweller"; 'rose' does not match "Everose"). The key's own words are not
    matched, so a key such as 'gmt' or 'dial' never matches by accident. A watch the
    video names must be recorded (a `mentioned` appearance) or be a peer, so the Viewer
    pulse never codes comments against a watch the pages do not show.
    """
    run = Path(run)
    f = run / "coding" / "subjects.json"
    if not f.is_file():
        return []
    subjects = coding.normalize_subjects(json.loads(f.read_text(encoding="utf-8")))

    def load(name):
        g = run / name
        return json.loads(g.read_text(encoding="utf-8")) if g.is_file() else {}
    records, peers = load("records.json"), load("peers.json")
    vids = set(video_ids if video_ids is not None
               else (v.get("id") for v in records.get("videos") or []))
    ds = dataset.load()
    wmap = {w.get("id"): w for w in ds["watches"]}
    wmap.update({w.get("id"): w for w in records.get("watches") or []})
    mine = {a.get("watch_id") for a in list(ds["appearances"]) + list(records.get("appearances") or [])
            if a.get("video_id") in vids}
    cands = [wmap[i] for i in mine if i in wmap] + list(peers.get("watches") or [])
    ids = {w.get("id") for w in cands}
    texts = [_words(" ".join(str(w.get(k) or "") for k in ("brand", "model", "reference")))
             for w in cands]
    out = []
    for key, aliases in subjects.items():
        if key in ids:
            continue
        phrases = [_words(a).strip() for a in aliases or []]
        if not any(p and f" {p} " in t for p in phrases for t in texts):
            out.append(key)
    return out


def build_child(run: Path, video_ids: list, type: str, fragments: dict) -> Path:
    """Build `<run>/build/index.html` and `img/` for one child set; returns the build folder.

    `fragments` maps page key -> fragment path; any page not given is looked up at
    `<run>/fragments/<page>.html`. Writes `data.*` (and `what_changed.*` for a related
    set) into `<run>/numbers.json`, keeping every other key. The taxonomy version from
    `<run>/taxonomy.json` is shown on the overview and taxonomy pages (a visible note when
    the file is missing).
    """
    run = Path(run)
    if not video_ids:
        raise ValueError("build_child needs at least one video id")
    ds = dataset.load()
    vmap = {v["id"]: v for v in ds["videos"]}
    unknown = [v for v in video_ids if v not in vmap]
    if unknown:
        raise ValueError(f"videos not in the dataset: {unknown}")
    videos = sorted((vmap[v] for v in dict.fromkeys(video_ids)),
                    key=lambda v: v.get("upload_date") or "")
    related = len(videos) > 1
    keys = page_set(type, related)
    if type != "contest":  # a contest's coding subjects are its contestants, not watches
        unmatched = subject_check(run, [v["id"] for v in videos])
        if unmatched:
            raise ValueError("subjects.json names watches the run did not record: "
                             + ", ".join(unmatched) + ". Add each as a `mentioned` appearance "
                             "(with a photo) or a peer in peers.json, then rebuild")
    pf = run / "peers.json"
    if pf.is_file():
        peer_watches = (json.loads(pf.read_text(encoding="utf-8")) or {}).get("watches")
        errs = specs.unknown_errors(peer_watches, specs.prior_values(exclude_run=run, ds=ds),
                                    "peers.json")
        if errs:
            raise ValueError("; ".join(errs))
    wmap = {w["id"]: w for w in ds["watches"]}
    ids = {v["id"] for v in videos}
    apps = [a for a in ds["appearances"] if a["video_id"] in ids]
    wids = list(dict.fromkeys(a["watch_id"] for a in apps))
    watches = [wmap[w] for w in wids if w in wmap]

    nf = run / "numbers.json"
    numbers = json.loads(nf.read_text(encoding="utf-8")) if nf.is_file() else {}
    by_conf = {c: sum(1 for w in watches if w.get("confidence") == c) for c in dataset.CONFIDENCE}
    numbers["data"] = {"videos": len(videos), "watches": len(watches), "appearances": len(apps),
                       "by_confidence": by_conf,
                       "credited_photos": sum(1 for w in watches for p in w.get("photos") or []
                                              if p.get("kind") == "credited")}
    diff = None
    if related:
        diff = diff_videos(videos[0]["id"], videos[-1]["id"])
        numbers["what_changed"] = diff
    _write_json(nf, numbers)

    tax = _run_taxonomy(run)
    frag_paths = {k: run / "fragments" / f"{k}.html" for k in keys}
    frag_paths.update({k: Path(p) for k, p in (fragments or {}).items()})
    images = _Images()
    base_dirs = [run, paths.data_home()]
    frag_html, missing = {}, []
    for k in keys:
        f = frag_paths.get(k)
        if k in GENERATED:
            continue
        if f and f.is_file():
            frag_html[k] = _prepare_fragment(_pid(k), f.read_text(encoding="utf-8"),
                                                          run, images)
            _no_bare(f"fragment {k}", fill_numbers(frag_html[k], numbers))
        else:
            missing.append(k)

    cards = {}
    for w in watches:
        cards[w["id"]] = images.photo(w, base_dirs)
    unchecked = [wid for wid, (img, ph) in cards.items() if img and not (ph or {}).get("checked")]
    per_video = []
    for v in videos:
        va = sorted((a for a in apps if a["video_id"] == v["id"] and a["watch_id"] in wmap),
                    key=lambda a: (a.get("rank") is None, a.get("rank") or 0,
                                   min((x for x in map(frames.ts_seconds, a.get("timestamps") or [])
                                        if x is not None), default=0)))
        groups = {}
        for a in va:
            img, ph = cards[a["watch_id"]]
            groups.setdefault(a.get("group"), []).append(
                render.gallery_card(wmap[a["watch_id"]], a, img, ph, v))
        per_video.append((v, list(groups.items())))

    checked, built = _checked(watches), date.today().isoformat()
    footer = render.footer_child(videos, checked, built)
    nav = [(_pid(k), *PAGE_META[k]) for k in keys]
    no_tx = {v["id"] for v in videos if not (run / v["id"] / "transcript.txt").is_file()}
    strip = [(cards[w["id"]][0], render.watch_name(w)) for w in watches if cards[w["id"]][0]][:6]
    title = videos[-1].get("title") or videos[-1]["id"] if not related else \
        " / ".join(v.get("title") or v["id"] for v in videos)
    set_label = f"Teddy Baldassarre · {render.type_label(type)}"

    styles, views = [], []
    for k in keys:
        frag = frag_html.get(k)
        h1 = lede = ""
        if k == "overview":
            h1 = title
            lede = ("An analysis of " + ("these related videos" if related else "this video")
                    + ": the watches shown, the criteria stated, and what viewers said.")
            content = render.overview_child(videos, type, [c for c, n in by_conf.items() if n],
                                            nav, strip, frag, no_tx, tax)
        elif k == "gallery":
            content = render.gallery(per_video, related)
        elif k == "sources":
            content = render.sources_table(watches, frag)
        elif k == "what-changed":
            content = render.what_changed(diff, wmap, vmap, frag)
        else:
            content = frag or render.not_produced("This page")
            if k == "taxonomy":
                content = render.taxonomy_used(tax) + content
        css, section = _view(k, set_label, content, footer, h1, lede, home=(k == keys[0]))
        styles.append(f"/* ---- {k} ---- */\n{css}")
        views.append(fill_numbers(section, numbers))

    parent = _load_registry()["parent"]
    backlink = render.link((parent or {}).get("url"), "← The collection",
                           ' class="back" target="_blank" rel="noopener"')
    if not safe_url((parent or {}).get("url")):
        backlink = ""
    sidefoot = ("<span>Source: " + "; ".join(
        render.link(v.get("url"), escape(v.get("title") or v["id"])) for v in videos) + f"</span><span>Built {built}</span>")
    html = _assemble(title, set_label, keys, styles, views, sidefoot, backlink)
    _check_page(html)
    manifest = {"kind": "child", "video_ids": [v["id"] for v in videos], "type": type,
                "pages": keys, "missing_fragments": missing, "unchecked_photos": unchecked}
    result = _finish(run / "build", html, images, manifest)
    return Path(result["build"])


# ---------- parent ----------

def _successor(st, names) -> str:
    sid = st.get("successor_id")
    return f", replaced by {names.get(sid, sid)}" if sid else ""


def build_parent() -> Path:
    """Build the parent collection into `<data home>/parent/build/`; returns that folder."""
    home = paths.data_home()
    ds = dataset.load()
    reg = _load_registry()
    vmap = {v["id"]: v for v in ds["videos"]}
    wmap = {w["id"]: w for w in ds["watches"]}
    names = {w["id"]: render.watch_name(w) for w in ds["watches"]}
    kids = reg["children"]
    child_of = {}
    for c in kids:
        for vid in c.get("video_ids") or []:
            child_of.setdefault(vid, c)

    tax_ids = taxonomy.list_versions()
    taxes = []
    for i, tid in enumerate(tax_ids):
        taxes.append((i, taxonomy.get(tid)))
    uploads = sorted(v["upload_date"] for v in ds["videos"] if v.get("upload_date"))
    numbers = {"parent": {"videos": len(ds["videos"]), "watches": len(ds["watches"]),
                          "appearances": len(ds["appearances"]), "child_sets": len(kids),
                          "first_upload": uploads[0] if uploads else "no date",
                          "last_upload": uploads[-1] if uploads else "no date"},
               "taxonomies": [{"id": t["id"], "criteria": sum(len(c) for c in (t.get("layers") or {}).values())}
                              for _, t in taxes]}
    pdir = home / "parent"
    pdir.mkdir(exist_ok=True)
    _write_json(pdir / "numbers.json", numbers)

    def vlink(v):
        c = child_of.get(v["id"])
        url = c["url"] if c else v.get("url")
        if not safe_url(url):
            url = v.get("url")
        return render.link(url, escape(v.get("title") or v["id"]))

    items = [(v.get("upload_date") or "", "video",
              f'{vlink(v)} <span class="ev">· {escape(render.type_label(v.get("type")))}</span>')
             for v in ds["videos"]]
    for w in ds["watches"]:
        for st in w.get("status_history") or []:
            if st.get("date"):
                items.append((st["date"], str(st.get("status", "")).replace("_", " "),
                              f'<span class="ev">{escape(names[w["id"]])} '
                              f'{escape(w.get("reference") or "")}{escape(_successor(st, names))}</span>'))
    items.sort(key=lambda x: (x[0] or "9999", x[1] != "video"))
    years = {}
    for d, kind, h in items:
        years.setdefault(d[:4] if d else "Undated", []).append((d or "undated", kind, h))

    images = _Images()
    # relative photo paths resolve against the data home, then each registered child's run,
    # then every other run folder, newest first (a run's watches reach the dataset at
    # Step 4, before its child is registered)
    base_dirs = [home] + [Path(c["build"]).parent for c in kids if c.get("build")]
    runs = home / "runs"
    if runs.is_dir():
        base_dirs += [r for r in sorted(runs.iterdir(), reverse=True) if r.is_dir() and r not in base_dirs]
    cards = []
    for w in sorted(ds["watches"], key=lambda w: (w.get("brand") or "", w.get("model") or "", w["id"])):
        img, ph = images.photo(w, base_dirs)
        vids = list(dict.fromkeys(a["video_id"] for a in ds["appearances"] if a["watch_id"] == w["id"]))
        sets, seen = [], set()
        for vid in vids:
            c = child_of.get(vid)
            if c and c["url"] not in seen:
                seen.add(c["url"])
                first = vmap.get((c.get("video_ids") or [vid])[0], {"id": vid})
                sets.append(render.link(c["url"], escape(first.get("title") or first["id"]),
                                        ' target="_blank" rel="noopener"'))
        cards.append(render.watch_card(w, img, ph, render.status_text(render.status_now(w), names), sets))

    order = list(render.TYPE_LABEL)
    groups = {}
    for c in kids:
        vs = [vmap.get(v, {"id": v}) for v in c.get("video_ids") or []]
        d = min((v.get("upload_date") or "" for v in vs), default="")
        link = (render.link(c.get("url"), escape(" / ".join(v.get("title") or v["id"] for v in vs)),
                            ' target="_blank" rel="noopener"')
                + f' <span class="note">published {escape(c.get("published") or "")}</span>')
        groups.setdefault(c.get("type"), []).append((d or "undated", link))
    child_groups = [(t, sorted(groups[t])) for t in sorted(
        groups, key=lambda t: (order.index(t) if t in order else len(order), str(t)))]

    built = date.today().isoformat()
    footer = render.footer_parent(built)
    nav = [(_pid(k), *PAGE_META[k]) for k in PARENT_PAGES]
    content = {"parent-overview": render.overview_parent(nav),
               "timeline": render.timeline(list(years.items())),
               "watch-index": render.watch_index(cards),
               "taxonomy-library": render.taxonomy_library(taxes),
               "child-list": render.child_list(child_groups)}
    styles, views = [], []
    for k in PARENT_PAGES:
        css, section = _view(k, "Collection", content[k], footer,
                             home=(k == PARENT_PAGES[0]))
        styles.append(f"/* ---- {k} ---- */\n{css}")
        views.append(fill_numbers(section, numbers))
    html = _assemble("Watch videos, analysed", "A collection", PARENT_PAGES, styles, views,
                     f"<span>Built {built}</span>")
    _check_page(html)
    result = _finish(pdir / "build", html, images, {"kind": "parent", "pages": PARENT_PAGES})
    return Path(result["build"])
