"""Frozen children: hash each view's body so later edits are detectable.

Every view is `<section class="view" id="v-<page>">` whose first children are the empty
slots `<div data-banner></div>` and `<div data-today></div>`. `record` hashes each view's
HTML with the inner content of those two slots blanked, so a banner or a "today" note can
be added later without breaking the freeze; any edit to the body does.
"""
import hashlib
import re
from pathlib import Path

from . import sanitize

_TOKEN = re.compile(r"<section\b[^>]*>|</section\s*>", re.I)
_ATTR = re.compile(r"""\b([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")


def _view_id(tag: str):
    """The id of a `<section>` tag whose class list has `view`, else None (any attribute order)."""
    attrs = {m.group(1).lower(): m.group(2) if m.group(2) is not None else m.group(3)
             for m in _ATTR.finditer(tag)}
    if "view" in (attrs.get("class") or "").split() and attrs.get("id"):
        return attrs["id"]
    return None
_DIV = re.compile(r"<div\b[^>]*>|</div\s*>", re.I)


def _index(build: Path) -> Path:
    return Path(build) / "index.html"


def _views(html: str) -> list:
    """[(view_id, start, end)] for each top-level `section.view`, nesting-aware."""
    out, depth, cur = [], 0, None
    for m in _TOKEN.finditer(html):
        tag = m.group(0)
        if tag.startswith("</"):
            if depth:
                depth -= 1
                if depth == 0 and cur:
                    out.append((cur[0], cur[1], m.end()))
                    cur = None
        else:
            if depth == 0:
                vid = _view_id(tag)
                cur = (vid, m.start()) if vid else None
            depth += 1
    return out


def _slot(html: str, name: str):
    """(inner_start, inner_end) of the first `<div data-<name>…>…</div>` in html, or None."""
    m = re.search(rf"<div\b[^>]*\bdata-{name}(?=[\s>=/])[^>]*>", html, re.I)
    if not m:
        return None
    depth = 1
    for t in _DIV.finditer(html, m.end()):
        depth += -1 if t.group(0).startswith("</") else 1
        if depth == 0:
            return m.end(), t.start()
    return None


_BUILT = re.compile(r"(<span\b[^>]*\bdata-built\b[^>]*>)[^<]*(</span\s*>)", re.I)


def _blank(view_html: str) -> str:
    """The view with its banner and today slots emptied and every build date
    (`<span data-built>`) blanked, so a rebuild on a later day still verifies."""
    for name in ("banner", "today"):
        s = _slot(view_html, name)
        if s:
            view_html = view_html[:s[0]] + view_html[s[1]:]
    return _BUILT.sub(r"\1\2", view_html)


def record(build) -> dict:
    """{view_id: sha256 of the view's HTML with the banner and today slots emptied and
    the build date blanked}."""
    html = _index(build).read_text(encoding="utf-8")
    views = _views(html)
    if not views:
        raise ValueError(f"{_index(build)} has no <section class=\"view\" id=...> views to freeze")
    return {vid: hashlib.sha256(_blank(html[a:b]).encode("utf-8")).hexdigest()
            for vid, a, b in views}


def verify(build, recorded: dict) -> list:
    """View ids whose body differs from `recorded` (also views added or missing)."""
    now = record(build)
    return sorted(k for k in set(now) | set(recorded) if now.get(k) != recorded.get(k))


def _check(html: str) -> str:
    low = html.lower()
    if "<script" in low or "<style" in low:
        raise ValueError("a banner or today note may not contain <script or <style")
    for tag in ("div", "section"):
        opens = len(re.findall(rf"<{tag}\b", low))
        closes = len(re.findall(rf"</{tag}\s*>", low))
        if opens != closes:
            raise ValueError(f"a banner or today note must have balanced <{tag}> tags "
                             f"({opens} opened, {closes} closed)")
        depth = 0
        for t in re.finditer(rf"<{tag}\b|</{tag}\s*>", low):
            depth += -1 if t.group(0).startswith("</") else 1
            if depth < 0:
                raise ValueError(f"a banner or today note closes a <{tag}> it did not open")
    return sanitize.clean_fragment("banner or today note", html)


def _fill(build, name: str, html: str, only=None) -> int:
    html = _check(html)
    f = _index(build)
    text = f.read_text(encoding="utf-8")
    want = None if only in (None, "all") else {only, f"v-{only}"} if not str(only).startswith("v-") else {only}
    out, last, n = [], 0, 0
    for vid, a, b in _views(text):
        if want is not None and vid not in want:
            continue
        seg = text[a:b]
        s = _slot(seg, name)
        if not s:
            continue
        out.append(text[last:a])
        out.append(seg[:s[0]] + html + seg[s[1]:])
        last, n = b, n + 1
    if not n:
        raise ValueError(f"no view {only if want is not None else 'in this build'!r} has a data-{name} slot")
    out.append(text[last:])
    f.write_text("".join(out), encoding="utf-8")
    return n


def set_banner(build, html: str) -> int:
    """Replace the inner HTML of every view's data-banner slot; returns views changed."""
    return _fill(build, "banner", html)


def set_today(build, html: str, view: str = "all") -> int:
    """Replace the inner HTML of the data-today slot of one view (id with or without `v-`) or all."""
    return _fill(build, "today", html, view)
