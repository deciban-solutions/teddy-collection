"""Safety helpers for page assembly: URL schemes, inline-script strings, the allow-list
pass over model-written fragments, and per-view CSS scoping (ported from the 2026-11-14
two-watch hub build)."""
import json
import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

_IMG = re.compile(r"^img/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*$")


def safe_url(u, allow_img=False):
    """The URL if it is http(s) (or, with allow_img, a relative `img/<name>` with no `..`); else None."""
    if not isinstance(u, str):
        return None
    s = u.strip()
    if not s or any(ord(c) < 32 for c in s):
        return None
    if allow_img:
        if _IMG.match(s) and ".." not in s.split("/"):
            return s
        return None
    p = urlparse(s)
    if p.scheme.lower() in ("http", "https") and p.netloc:
        return s
    return None


def js_string(v) -> str:
    """A JSON string literal safe inside an inline <script>."""
    s = json.dumps(v, ensure_ascii=False)
    for ch, rep in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"),
                    (" ", "\\u2028"), (" ", "\\u2029")):
        s = s.replace(ch, rep)
    return s


# ---------- fragment allow-list ----------

ALLOWED = {"section", "div", "p", "span", "h2", "h3", "h4", "ul", "ol", "li", "table", "thead",
           "tbody", "tr", "th", "td", "blockquote", "figure", "figcaption", "img", "a", "strong",
           "em", "b", "i", "code", "br", "hr", "dl", "dt", "dd", "small", "sup", "sub",
           "details", "summary",
           # harmless text containers the reference pages use
           "header", "article", "cite", "caption", "tfoot", "pre", "abbr", "q", "mark", "time"}
VOID = {"br", "hr", "img"}
# Classes a fragment may use: defined for every view in templates/shell.html (fragments
# carry no CSS of their own). Any other class token is dropped, so a fragment can never
# carry a shell name (view, side, main, brand, zoom, zoomable, shell).
FRAGMENT_CLASSES = ("note", "lede", "callout", "answer", "tbl", "wide", "num", "mono", "ref",
                    "y", "p", "n", "cards", "card", "ranks", "rank", "sub", "plain", "refs",
                    "cite", "findings", "finding", "legend")
_CLASS = re.compile(r"[A-Za-z0-9_ -]+")
# Attributes kept on fragment elements; every other attribute is dropped. The only data-*
# a fragment needs are the two the number check reads (pages.py): data-num (filled from
# numbers.json) and data-spec (a spec cell, exempt from the bare-number check). The shell's
# own data-* (data-zoom, data-view, data-title, ...) are reserved for generated markup.
GLOBAL_ATTRS = {"class", "id", "title", "lang", "dir", "colspan", "rowspan", "scope", "headers",
                "data-num", "data-spec"}
TAG_ATTRS = {"a": {"href"}, "img": {"src", "alt", "width", "height"}, "time": {"datetime"},
             "abbr": {"cite"}, "q": {"cite"}, "blockquote": {"cite"}}


class FragmentError(ValueError):
    pass


class _Clean(HTMLParser):
    def __init__(self, name):
        super().__init__(convert_charrefs=True)
        self.name, self.out, self.stack = name, [], []

    def _refuse(self, what):
        raise FragmentError(f"fragment {self.name}: <{what}> is not allowed")

    def _attrs(self, tag, attrs):
        out = []
        allowed = GLOBAL_ATTRS | TAG_ATTRS.get(tag, set())
        for k, v in attrs:
            k = k.lower()
            v = "" if v is None else v
            if k not in allowed:
                continue
            if k == "class":
                v = " ".join(c for c in v.split() if c in FRAGMENT_CLASSES) if _CLASS.fullmatch(v) else ""
                if not v:
                    continue
            if k == "href":
                if v.startswith("#") and re.match(r"^#[A-Za-z0-9_.:-]*$", v):
                    pass
                elif safe_url(v) is None:
                    continue
            if k == "cite" and safe_url(v) is None:
                continue
            if k == "src":
                if safe_url(v, allow_img=True) is None:
                    raise FragmentError(f"fragment {self.name}: <img src={v!r}> must be a "
                                        "local img/<name> with no '..'")
            out.append(f' {k}="{escape(v, quote=True)}"' if v != "" or k.startswith("data-")
                       else f" {k}")
        if tag == "img" and not any(a.startswith(" src=") for a in out):
            raise FragmentError(f"fragment {self.name}: <img> without a local src")
        return "".join(out)

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED:
            self._refuse(tag)
        self.out.append(f"<{tag}{self._attrs(tag, attrs)}>")
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag not in ALLOWED:
            self._refuse(tag)
        self.out.append(f"<{tag}{self._attrs(tag, attrs)}>")
        if tag not in VOID:
            self.out.append(f"</{tag}>")

    def handle_endtag(self, tag):
        """Close `tag` and any element still open inside it; an end tag with no open
        element of its name is dropped (it would close the view around the fragment)."""
        if tag not in ALLOWED:
            self._refuse(tag)
        if tag in VOID or tag not in self.stack:
            return
        while self.stack:
            t = self.stack.pop()
            self.out.append(f"</{t}>")
            if t == tag:
                break

    def finish(self):
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")

    def handle_data(self, data):
        self.out.append(escape(data, quote=False))

    def handle_decl(self, decl):
        self._refuse(decl.split()[0] if decl.strip() else "!")

    def handle_pi(self, data):
        self._refuse("?" + data[:10])

    def unknown_decl(self, data):
        self._refuse(data[:10])

    def handle_comment(self, data):
        pass


def clean_fragment(name: str, html: str) -> str:
    """Re-emit a fragment through the allow-list (elements, per-tag attributes, classes) with
    its tags balanced: unmatched end tags dropped, open tags closed at the end. Raises
    FragmentError on a refused element."""
    p = _Clean(name)
    p.feed(html)
    p.close()
    p.finish()
    return "".join(p.out)


# ---------- CSS ----------

# A browser ends a style element at `</style` followed by whitespace, `/` or `>`.
_STYLE = re.compile(r"<style\b[^>]*>(.*?)</style(?=[\s/>])[^>]*>", re.S | re.I)


def split_style(html):
    """-> (css of every <style> block, html without them)."""
    return "\n".join(_STYLE.findall(html)), _STYLE.sub("", html)


def fragment_body(name, html):
    """Breakout guards for a model-written fragment, which carries no CSS at all: no
    `<script` and no `<style` (any case, any attributes) anywhere in the raw text."""
    if re.search(r"<\s*script", html, re.I):
        raise FragmentError(f"fragment {name}: <script> is not allowed")
    if re.search(r"<\s*/?\s*style", html, re.I):
        raise FragmentError(f"fragment {name}: <style> is not allowed; fragments carry no CSS "
                            "(use the classes in sanitize.FRAGMENT_CLASSES)")
    return html


# quoted CSS strings, masked during scoping of the shell's and templates' own (trusted) CSS
_STR = re.compile(r"""("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*')""", re.S)


def _split_blocks(css):
    out, i, n = [], 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            break
        sel, depth, k = css[i:j].strip(), 1, j + 1
        while depth and k < n:
            depth += {"{": 1, "}": -1}.get(css[k], 0)
            k += 1
        out.append((sel, css[j + 1:k - 1]))
        i = k
    return out


_NESTED = ("@media", "@supports", "@container", "@layer")


def scope_css(css: str, pid: str) -> str:
    """Prefix every selector with `#v-<pid>`; drop :root/html/body rules (the shell owns them).
    @media/@supports/@container/@layer bodies are scoped too; @keyframes names get a
    `<pid>-` prefix (and so do the animation declarations that use them); @import is refused;
    other block-less at-statements are dropped."""
    strings = []

    def mask(m):
        strings.append(m.group(0))
        return f"\0{len(strings) - 1}\0"
    css = _STR.sub(mask, css)            # strings are opaque to everything below
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    if re.search(r"@import\b", css, re.I):
        raise ValueError(f"page {pid}: @import is not allowed in page CSS")
    if re.search(r"@[\w-]*\\", css):
        raise ValueError(f"page {pid}: escaped at-rule names are not allowed in page CSS")
    css = re.sub(r"@[A-Za-z-]+[^{};]*;", "", css)
    frames = re.findall(r"@(?:-webkit-)?keyframes\s+([A-Za-z0-9_-]+)", css)
    out = _scope(css, pid, frames)
    return re.sub(r"\0(\d+)\0", lambda m: strings[int(m.group(1))], out)


def _rename_anims(body, pid, frames):
    def fix(m):
        val = m.group(2)
        for f in frames:
            val = re.sub(rf"(?<![\w-]){re.escape(f)}(?![\w-])", f"{pid}-{f}", val)
        return m.group(1) + val
    return re.sub(r"(animation(?:-name)?\s*:)([^;}]*)", fix, body)


def _scope(css, pid, frames):
    res = []
    for sel, body in _split_blocks(css):
        low = sel.lower()
        if low.startswith(_NESTED):
            inner = _scope(body, pid, frames)
            if inner.strip():
                res.append(f"{sel} {{\n{inner}\n}}")
            continue
        m = re.match(r"(@(?:-webkit-)?keyframes)\s+([A-Za-z0-9_-]+)", sel)
        if m:
            res.append(f"{m.group(1)} {pid}-{m.group(2)} {{{body}}}")
            continue
        if sel.startswith("@"):
            res.append(f"{sel}{{{body}}}")
            continue
        parts = []
        for s in sel.split(","):
            s = s.strip()
            if s.startswith(":root") or s in ("html", "body"):
                parts = None
                break
            parts.append(f"#v-{pid} {s}")
        if parts:
            res.append(", ".join(parts) + " {" + _rename_anims(body, pid, frames) + "}")
    return "\n".join(res)
