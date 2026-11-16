"""HTML for the pages generated from data (gallery, overview, sources, what changed, and
the parent's timeline, watch index, taxonomy library and child list).

Pure functions: records in, HTML strings out. Counts are never typed here; they are
written as `<span data-num="key">` and filled from numbers.json by `pages.fill_numbers`.
"""
from html import escape
from urllib.parse import urlparse

from .frames import ts_seconds
from .sanitize import safe_url

CONF_LABEL = {
    "labelled_on_screen": "Labelled on screen",
    "legible_on_dial": "Legible on dial",
    "matched_to_specs": "Matched to specs",
    "inferred": "Inferred",
    "unknown": "Unknown",
}
FIRM = ("labelled_on_screen", "legible_on_dial")
TYPE_LABEL = {"contest": "Contest or tournament", "review": "Single-watch review",
              "list": "List or tier guide"}


def esc(s) -> str:
    return escape("" if s is None else str(s), quote=True)


def link(url, text_html, attrs="") -> str:
    """An <a> to url when it is http(s); otherwise just the text (no link)."""
    u = safe_url(url)
    return f'<a href="{esc(u)}"{attrs}>{text_html}</a>' if u else text_html


def num(key) -> str:
    return f'<span data-num="{esc(key)}">…</span>'


def type_label(t) -> str:
    return TYPE_LABEL.get(t, str(t or "Unclassified").replace("_", " ").capitalize())


def watch_name(w) -> str:
    return " ".join(x for x in (w.get("brand"), w.get("model")) if x) or w.get("id", "")


def ref_text(w) -> str:
    if w.get("reference"):
        return str(w["reference"])
    return "model family; no single reference" if w.get("family") else "reference unknown"


def conf_badge(w) -> str:
    c = w.get("confidence")
    cls = "conf firm" if c in FIRM else "conf"
    return f'<span class="{cls}">{esc(CONF_LABEL.get(c, c))}</span>'


def ts_label(t) -> str:
    """m:ss or h:mm:ss; an unparseable timestamp is shown as its raw text."""
    v = ts_seconds(t)
    if v is None:
        return str(t)
    s = int(v)
    h, m, sec = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def ts_link(url, t) -> str:
    """A link to the video at t; the raw text with no link when t is not a time."""
    v = ts_seconds(t)
    if not safe_url(url) or v is None:
        return esc(ts_label(t))
    sep = "&" if "?" in url else "?"
    return link(f"{url}{sep}t={int(v)}", esc(ts_label(t)))


def _host(url) -> str:
    return (urlparse(url or "").hostname or "").removeprefix("www.")


def not_produced(what="This page") -> str:
    return (f'<div class="not-produced"><b>Not produced in this run.</b> {esc(what)} was '
            "not produced in this run, so it is shown empty rather than left out.</div>")


def status_now(w):
    hist = w.get("status_history") or []
    return hist[-1] if hist else None


def status_text(st, names) -> str:
    if not st:
        return "Status not recorded"
    out = str(st.get("status", "")).replace("_", " ")
    if st.get("successor_id"):
        out += f", replaced by {names.get(st['successor_id'], st['successor_id'])}"
    return f"{out} (as of {st.get('date', 'undated')})"


def photo_block(img, w) -> str:
    """Click-to-enlarge photo, with a visible credit and source link for non-frame photos."""
    alt = f"{watch_name(w)} {w.get('reference') or ''}".strip()
    if not img:
        return '<div class="nophoto">No usable photo</div>'
    return (f'<button type="button" class="zoomable" data-zoom="{esc(img)}" data-alt="{esc(alt)}" '
           f'aria-label="Enlarge photo of {esc(alt)}"><img src="{esc(img)}" alt="{esc(alt)}" '
           'loading="lazy"></button>')


def credit_line(photo) -> str:
    if not photo or photo.get("kind") != "credited":
        return ""
    src = photo.get("source_url")
    tail = f" · {link(src, 'source')}" if safe_url(src) else ""
    return f'<p class="credit">Photo: {esc(photo.get("credit") or "credited source")}{tail}</p>'


def source_links(w) -> str:
    srcs = w.get("sources") or []
    matched = [s for s in srcs if s.get("match")]
    shown = matched or srcs
    if not shown:
        return "none recorded"
    parts = []
    for s in shown:
        label = " · ".join(x for x in (_host(s.get("url")), s.get("kind")) if x)
        tail = {"partial": " (partial match)", "unreadable": " (blocked, unread)"}.get(
            s.get("result"), "" if s.get("match") else " (not matched)")
        parts.append(link(s.get("url"), esc(label or s.get("url"))) + tail)
    return " · ".join(parts)


def source_result(s) -> str:
    """One source's outcome in words."""
    r = s.get("result")
    if r == "unreadable":
        return f"blocked ({s.get('status')}), unread"
    if r == "partial":
        return ("model words matched in order" if s.get("match_level") == "tokens"
                else "core reference number matched")
    if r == "match" or (r is None and s.get("match")):
        return "title or reference matched"
    return "not matched"


def _specs(w) -> str:
    sp = w.get("specs") or {}
    def show(v):
        return ", ".join(str(x) for x in v) if isinstance(v, (list, tuple)) else v
    return "; ".join(f"{str(k).replace('_', ' ')}: {show(v)}" for k, v in sp.items()
                     if v not in (None, "", []))


def footer_child(videos, checked, built) -> str:
    srcs = "; ".join(f'{link(v.get("url"), esc(v.get("title")))}, uploaded '
                     f'{esc(v.get("upload_date") or "date unknown")}' for v in videos)
    return ('<footer class="page-foot">'
            f"<span>Source: {srcs} (Teddy Baldassarre, YouTube). These pages are an independent "
            "analysis of the video.</span>"
            "<span>Photos are frames from the video unless a credit says otherwise.</span>"
            f"<span>Facts checked {esc(checked)} · built <span data-built>{esc(built)}</span>.</span></footer>")


def footer_parent(built) -> str:
    return ('<footer class="page-foot">'
            "<span>Source: the Teddy Baldassarre YouTube videos listed on the Timeline and Video "
            "analyses pages. This collection is an independent analysis of them.</span>"
            "<span>Photos are frames from the videos unless a credit says otherwise.</span>"
            f"<span>Built <span data-built>{esc(built)}</span>.</span></footer>")


# ---------- child pages ----------

def _how_checked(label, warrant, tax=None) -> str:
    """One plain sentence on how far this checklist version has been checked."""
    tax = tax or {}
    if label != "compiled":
        if tax.get("base_label") == "compiled" and tax.get("derived_from"):
            return (f"It is a <b>provisional</b> branch of the compiled {esc(tax['derived_from'])}: "
                    "what it adds has not been compiled or ratified.")
        return ("It is <b>provisional</b>: this plug-in drafted it from published sources, and it "
                "has not been compiled or ratified.")
    if not isinstance(warrant, dict):
        return "It is <b>compiled</b>, but this version records no warrant saying how it was checked."
    s = "It is <b>compiled</b>: built offline with formalized-reasoner"
    if warrant.get("freeze_commit"):
        s += " from a frozen pre-registration"
    if warrant.get("ratified"):
        cp = warrant.get("catch_power")
        caught = "every planted flaw" if cp == 1 else "some of the planted flaws"
        when = f" on {esc(warrant['ratified_on'])}" if warrant.get("ratified_on") else ""
        s += (f", and ratified by {esc(warrant.get('ratified_by') or 'an unnamed grader')}{when}, "
              f"who caught {caught} in its test pages.")
    else:
        s += ", and not yet ratified by a grader."
    def _names(k):
        v = warrant.get(k)
        return [str(n).replace("_", " ") for n in v] if isinstance(v, list) else []
    if _names("not_enforced_here"):
        s += (" Validated in the compile but judged here rather than tested by a script: "
              + esc(", ".join(_names("not_enforced_here"))) + ".")
    if _names("not_validated_in_compile"):
        s += (" Judged in the compile too, with no validated test: "
              + esc(", ".join(_names("not_validated_in_compile"))) + ".")
    return s


def taxonomy_used(tax, warrant=None) -> str:
    """The run's checklist version, what the checklist is for, and how far it has been checked;
    or a visible note that the version was not recorded."""
    if not tax:
        return ('<p class="note taxver"><b>Checklist version not recorded for this run.</b> '
                "The criteria pages cannot say which version of the buyer's checklist they used.</p>")
    label = tax["label"]
    if warrant is None:
        warrant = tax.get("warrant")
    return (f'<p class="taxver">Checklist used: {esc(tax.get("category"))} '
            f'<span class="ref">{esc(tax["version_id"])}</span> '
            f'<span class="badge {esc(label)}">{esc(label)}</span></p>'
            '<p class="note">This is the checklist the analysis measures the watches against. '
            f"{_how_checked(label, warrant, tax)}</p>")


def overview_child(videos, vtype, confs, nav, strip, fragment, no_transcript, tax=None) -> str:
    vl = []
    for v in videos:
        note = (' <span class="note">· No captions were available for this video; the analysis '
                "rests on its metadata, comments and frames.</span>") if v["id"] in no_transcript else ""
        vl.append(f'<div>{link(v.get("url"), esc(v.get("title")), " class=\"vt\"")} '
                  f'<span class="note">uploaded {esc(v.get("upload_date") or "date unknown")}</span>{note}</div>')
    conf = "; ".join(f"{esc(CONF_LABEL[c])} {num('data.by_confidence.' + c)}" for c in confs)
    strip_html = ""
    if strip:
        imgs = "".join(f'<img src="{esc(src)}" alt="{esc(alt)}">' for src, alt in strip)
        strip_html = f'<div class="strip" aria-label="Some of the watches">{imgs}</div>'
    cards = "".join(
        f'<a class="card" href="#{esc(pid)}"><span class="k">{esc(title)}</span>'
        f'<p>{esc(sub)}</p></a>' for pid, title, sub in nav if pid != "overview")
    return (f'<section class="vlist">{"".join(vl)}</section>'
            '<div class="facts">'
            f'<div><b>Video type: {esc(type_label(vtype))}</b><span>This run classified the video '
            "from its title and transcript. You can override it: if the type is wrong, rebuild the "
            "set with the right one.</span></div>"
            f"<div><b>Watches</b><span>{num('data.watches')} watches identified across "
            f"{num('data.appearances')} appearances.</span></div>"
            f"<div><b>How sure the identifications are</b><span>{conf or 'No watches recorded.'}</span></div>"
            "</div>"
            f"{taxonomy_used(tax)}{strip_html}"
            f'<section><h2>The short answer</h2>{fragment or not_produced("The written summary")}</section>'
            f'<section><h2>The pages</h2><div class="cards">{cards}</div></section>')


def gallery_card(w, a, img, photo, video) -> str:
    place = []
    if a.get("rank") is not None:
        place.append(f"No. {a['rank']}")
    if a.get("role"):
        place.append(str(a["role"]))
    rows = []
    specs = _specs(w)
    if specs:
        rows.append(f"<dt>Specs</dt><dd>{esc(specs)}</dd>")
    rows.append(f"<dt>Source</dt><dd>{source_links(w)}</dd>")
    ts = a.get("timestamps") or []
    if ts:
        rows.append("<dt>In video</dt><dd>" + " · ".join(ts_link(video.get("url"), t) for t in ts) + "</dd>")
    pq = a.get("price_quoted") or {}
    if pq.get("amount") is not None:
        rows.append(f"<dt>Price quoted</dt><dd>{esc(pq['amount'])} {esc(pq.get('currency', ''))}</dd>")
    verdict = (a.get("verdict") or {}).get("quote")
    vq = f"<blockquote>{esc(verdict)}</blockquote>" if verdict else ""
    return (f'<article class="gcard">{photo_block(img, w)}<div class="body">'
            f'<span class="place">{esc(" · ".join(place))}</span>'
            f"<h3>{esc(watch_name(w))}</h3><div class=\"ref\">{esc(ref_text(w))}</div>"
            f"<dl>{''.join(rows)}</dl>{conf_badge(w)}"
            f'<p class="basis">{esc(w.get("basis"))}</p>{credit_line(photo)}{vq}</div></article>')


def gallery(per_video, multi) -> str:
    """per_video: [(video, [(group or None, [card_html, ...]), ...]), ...]"""
    out = []
    for video, groups in per_video:
        if multi:
            out.append(f'<h2>{esc(video.get("title"))} <span class="note">'
                       f'uploaded {esc(video.get("upload_date"))}</span></h2>')
        if not groups:
            out.append('<p class="note">No watches recorded for this video.</p>')
        for g, cards in groups:
            head = f'<div class="group-head"><h2>{esc(g)}</h2></div>' if g else ""
            out.append(f'<section class="group">{head}<div class="grid">{"".join(cards)}</div></section>')
    return "".join(out)


def sources_table(watches, fragment) -> str:
    rows = []
    for w in watches:
        srcs = "<br>".join(
            f'{link(s.get("url"), esc(_host(s.get("url")) or s.get("url")))} '
            f'<span class="src">{esc(s.get("kind"))} · checked {esc(s.get("checked_at"))} · '
            f'{esc(source_result(s))}</span>'
            for s in w.get("sources") or []) or "none recorded"
        photos = "; ".join("video frame" if p.get("kind") == "frame" else
                           f"credited: {esc(p.get('credit'))}" for p in w.get("photos") or []) or "none"
        rows.append(f"<tr><td>{esc(watch_name(w))}<div class=\"ref\">{esc(w.get('reference'))}</div></td>"
                    f"<td>{conf_badge(w)}<div class=\"note\">{esc(w.get('basis'))}</div></td>"
                    f"<td>{srcs}</td><td>{photos}</td></tr>")
    table = ('<section><h2>Every watch and its sources</h2><div class="tbl wide"><table><thead><tr>'
             "<th>Watch</th><th>Identified by</th><th>Sources</th><th>Photo</th></tr></thead>"
             f"<tbody>{''.join(rows)}</tbody></table></div></section>")
    return (f'<section><h2>Method</h2>{fragment or not_produced("The method write-up")}</section>' + table)


def _delta(d) -> str:
    return "" if d is None else esc(format(d, "+g"))


def what_changed(diff, wmap, videos, fragment) -> str:
    def names(ids):
        if not ids:
            return "<li>none</li>"
        return "".join(f"<li>{esc(watch_name(wmap.get(i, {'id': i})))} "
                       f"<span class=\"ref\">{esc(wmap.get(i, {}).get('reference'))}</span></li>" for i in ids)
    older, newer = videos[diff["older"]], videos[diff["newer"]]
    moves = "".join(
        f"<tr><td>{esc(watch_name(wmap.get(m['watch_id'], {'id': m['watch_id']})))}</td>"
        f"<td>{esc(m['from']['amount'])} {esc(m['from'].get('currency'))}</td>"
        f"<td>{esc(m['to']['amount'])} {esc(m['to'].get('currency'))}</td>"
        f"<td>{_delta(m.get('delta'))}</td></tr>"
        for m in diff["price_moves"])
    moves_html = ('<div class="tbl"><table><thead><tr><th>Watch</th><th>Earlier</th><th>Later</th>'
                  f'<th>Change</th></tr></thead><tbody>{moves}</tbody></table></div>' if moves
                  else '<p class="note">No reference was quoted at a different price in both videos.</p>')
    crit = "".join(f"<li>{esc(c)}</li>" for c in diff["criteria_added"]) or "<li>none recorded</li>"
    return (f'<p>From {link(older.get("url"), esc(older.get("title")))} '
            f'({esc(older.get("upload_date"))}) to {link(newer.get("url"), esc(newer.get("title")))} '
            f'({esc(newer.get("upload_date"))}).</p>'
            '<div class="cols">'
            f"<div class=\"col\"><h3>Added ({num('what_changed.counts.added')})</h3><ul>{names(diff['added'])}</ul></div>"
            f"<div class=\"col\"><h3>Dropped ({num('what_changed.counts.dropped')})</h3><ul>{names(diff['dropped'])}</ul></div>"
            "</div>"
            f"<section><h2>Price moves</h2>{moves_html}</section>"
            f"<section><h2>Criteria added</h2><ul>{crit}</ul></section>"
            f'<section><h2>What it means</h2>{fragment or not_produced("The written comparison")}</section>')


# ---------- parent pages ----------

def overview_parent(nav) -> str:
    cards = "".join(
        f'<a class="card" href="#{esc(pid)}"><span class="k">{esc(title)}</span>'
        f'<p>{esc(sub)}</p></a>' for pid, title, sub in nav if pid != "overview")
    return ('<div class="facts">'
            f"<div><b>Sample</b><span>{num('parent.videos')} videos uploaded from "
            f"{num('parent.first_upload')} to {num('parent.last_upload')}.</span></div>"
            f"<div><b>Watches</b><span>{num('parent.watches')} distinct watches across "
            f"{num('parent.appearances')} appearances.</span></div>"
            f"<div><b>Video analyses</b><span>{num('parent.child_sets')} published.</span></div>"
            "</div>"
            "<p class=\"note\">Every count here is computed from the collection's dataset. "
            "This is Teddy's selection of the watch world, not the watch world.</p>"
            f'<section><h2>The pages</h2><div class="cards">{cards}</div></section>')


def timeline(years) -> str:
    """years: [(year, [(date, kind, html), ...]), ...] already in order."""
    if not years:
        return '<p class="note">No videos in the collection yet.</p>'
    out = []
    for y, items in years:
        lis = "".join(f'<li><span class="d">{esc(d)}</span><span><span class="kind">{esc(k)}</span>'
                      f"{h}</span></li>" for d, k, h in items)
        out.append(f'<section class="year"><h2>{esc(y)}</h2><ul class="items">{lis}</ul></section>')
    return "".join(out)


def watch_card(w, img, photo, status, kids) -> str:
    sets = " · ".join(kids) or "not yet in a published video analysis"
    return (f'<article class="wcard">{photo_block(img, w)}<div class="body">'
            f"<h3>{esc(watch_name(w))}</h3><div class=\"ref\">{esc(ref_text(w))}</div>"
            f"{conf_badge(w)}<p class=\"basis\">{esc(w.get('basis'))}</p>"
            f"<dl><dt>Status</dt><dd>{esc(status)}</dd><dt>Appears in</dt><dd>{sets}</dd></dl>"
            f"{credit_line(photo)}</div></article>")


def watch_index(cards) -> str:
    if not cards:
        return '<p class="note">No watches in the collection yet.</p>'
    return f'<div class="grid">{"".join(cards)}</div>'


def _branch_info(t) -> dict:
    """{derived_from, base_label} for a user branch, from its last change-log entry."""
    log = [e for e in t.get("change_log") or [] if isinstance(e, dict) and e.get("derived_from")]
    if not log:
        return {}
    e = log[-1]
    return {"derived_from": e["derived_from"],
            "base_label": "compiled" if "base_ratified" in e else None}


def taxonomy_library(taxes) -> str:
    """taxes: [(index, taxonomy dict), ...]"""
    if not taxes:
        return '<p class="note">No checklists installed yet.</p>'
    out = []
    for i, t in taxes:
        label = t.get("label", "provisional")
        log = "".join(f"<li>{esc(e.get('date'))}: {esc(e.get('reason'))}</li>"
                      for e in t.get("change_log") or []) or "<li>no changes recorded</li>"
        out.append(f'<article class="tax"><div class="tax-head"><h3>{esc(t.get("category"))}</h3>'
                   f'<span class="ref">{esc(t.get("id"))}</span>'
                   f'<span class="badge {esc(label)}">{esc(label)}</span></div>'
                   f'<p class="note">Created {esc(t.get("created"))} · '
                   f"{num(f'taxonomies.{i}.criteria')} criteria</p>"
                   f'<p class="note">{_how_checked(label, t.get("warrant"), _branch_info(t))}</p>'
                   f"<p>{esc(t.get('paradigm'))}</p><h3>Change log</h3><ul class=\"log\">{log}</ul></article>")
    return "".join(out)


def child_list(groups) -> str:
    """groups: [(type, [(date, html), ...]), ...]"""
    if not groups:
        return '<p class="note">No video analyses published yet.</p>'
    out = []
    for t, items in groups:
        lis = "".join(f'<li><span class="d">{esc(d)}</span><span>{h}</span></li>' for d, h in items)
        out.append(f'<section class="kind-group"><h2>{esc(type_label(t))}</h2><ul class="kids">{lis}</ul></section>')
    return "".join(out)
