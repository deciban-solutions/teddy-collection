"""Script-checked source links: fetch each URL and test it against the watch.

A source matches when a normalised reference/model string appears in the page
<title>, og:title or the first 200 KB of visible text.

Each source gets a `result`:
- `match`: the full reference (or, with no reference, the full model name) is on the page.
- `partial`: only a weaker form is. For a reference: a reference-shaped token on the page
  (letters, digits and the delimiters - . /, see `_REF_TOKEN`) that, after upper-casing
  and removing spaces, equals the record's reference with only a 1-2 letter brand prefix
  removed and/or one trailing delimited segment removed, or the other way round (see
  `partial_forms`). Brands print one reference that way (Rolex `M53505-0002` on its site,
  `53505` or `53505-0002` in the press). Nothing else counts: a digit run inside a longer
  token (`WGSA0030` is not `WSSA0030`, `5711/1R` is not `5711/1A-010`), or a number in a
  price (`1,53505`, `$53505`) or phone-number context (`555 0030`), never matches.
  For a model name with no reference, its words appear in order with at most GAP
  characters between them.
  A partial match counts as a match; `match_level` (`partial` or `tokens`) says which.
- `no_match`: the page was read (or answered 404) and no form is on it.
- `unreadable`: no page was read: HTTP 401, 403, 429, 5xx, a timeout or no response.
  An unreadable source is not a pass, and it is not evidence against the watch either.
  In one `verify-links` run, a host that answered 403 or 429 is not fetched again: its
  later sources are `unreadable` with that status and a `skipped` note.

A reference of digits only, or of at most SHORT characters, is matched at the full level
on the page's raw text with the same price and phone-number guards as the partial level.
"""
import copy
import html
import http.client
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse

KINDS = ("brand", "press", "dealer", "auction", "database", "other")
KIND_HOSTS = {
    "brand": ["grand-seiko.com", "omegawatches.com", "iwc.com", "breitling.com", "gallet.com",
              "glashuette-original.com", "doxawatches.com", "breguet.com", "felipe-pikullik.odoo.com"],
    "press": ["press.iwc.com"],
    "dealer": ["bobswatches.com", "righttime.com", "europeanwatch.com", "teddybaldassarre.com",
               "watchesofswitzerland.com", "wempe.com"],
    "auction": ["loupethis.com"],
    "database": ["watchbase.com"],
}
USER_AGENT = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/124.0 Safari/537.36")
TIMEOUT = 20
MAX_BYTES = 200 * 1024

_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_OG = re.compile(r"<meta\s[^>]*?property\s*=\s*[\"']og:title[\"'][^>]*>", re.I)
_CONTENT = re.compile(r"content\s*=\s*([\"'])(.*?)\1", re.I | re.S)
_DROP = re.compile(r"<(script|style)\b.*?</\1\s*>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")


UNREADABLE = (0, 401, 403, 429)  # plus every 5xx
GAP = 30


def norm(s: str) -> str:
    """Lowercase, drop `.`, `-` and the signs ® ™ ©, collapse whitespace; other punctuation
    stays as a boundary."""
    return " ".join(re.sub(r"[.\-®™©]", "", s or "").lower().split())


_REF_TOKEN = re.compile(r"[A-Z0-9](?:[A-Z0-9./-]*[A-Z0-9])?")


def partial_forms(ref) -> set:
    """The weaker forms of a reference: upper-cased, spaces removed, with a 1-2 letter
    brand prefix (letters directly before a digit) removed, one trailing delimited
    segment (after the last - . or /) removed, or both. Each form keeps a digit and at
    least four characters. 'M53505-0002' -> {'53505-0002', 'M53505', '53505'};
    '5711/1A-010' -> {'5711/1A'}; 'WSSA0030' and '126610LN' -> set()."""
    r = re.sub(r"\s+", "", ref or "").upper()
    m = re.match(r"[A-Z]{1,2}(?=\d)", r)
    pre = r[m.end():] if m else None

    def unsuffixed(x):
        m2 = re.fullmatch(r"(.+)[-./][A-Z0-9]+", x or "")
        return m2.group(1) if m2 else None
    forms = {pre, unsuffixed(r), unsuffixed(pre)}
    return {f for f in forms if f and f != r and len(f) >= 4 and re.search(r"\d", f)}


def _number_context(raw: str, start: int, end: int, token: str) -> bool:
    """True when the token sits in a price (1,53505 or $53505) or, for an all-digit token,
    beside another number (a phone number such as 800 555 0030)."""
    before, after = raw[max(0, start - 3):start], raw[end:end + 3]
    if re.search(r"\d,$", before) or re.match(r",\d", after) or re.search(r"[$€£¥]\s*$", before):
        return True
    return token.isdigit() and bool(re.search(r"\d[\s().-]{1,2}$", before)
                                    or re.match(r"[\s().-]{1,2}\d", after))


def _partial_ref(ref: str, raw: str):
    """The first page token that is a partial form of ref (or of which ref is one), else None."""
    r = re.sub(r"\s+", "", ref or "").upper()
    mine = partial_forms(r)
    for m in _REF_TOKEN.finditer(raw):
        tok = m.group(0)
        if tok == r or not re.search(r"\d", tok) or _number_context(raw, m.start(), m.end(), tok):
            continue
        if tok in mine or r in partial_forms(tok):
            return tok
    return None


def unreadable_status(status: int) -> bool:
    return status in UNREADABLE or status >= 500


SHORT = 5   # a reference this short (spaces removed), or one of digits only, is guarded
STRICT = 6  # a guarded reference this short must appear on the page exactly as written


def _guarded(term: str) -> bool:
    t = re.sub(r"\s+", "", term or "")
    return bool(re.search(r"\d", t)) and (t.isdigit() or len(t) <= SHORT)


def _full_raw(term: str, raw: str):
    """Full match of a short or all-digit term on the un-normalised page text: the term as a
    whole token, not in a price or phone-number context (`_number_context`). A term of more
    than STRICT characters may have `.` or `-` between its characters, as norm() allows
    (`22010382001001` is Omega's `220.10.38.20.01.001`); a shorter one must appear as written,
    so `5513` is never `55.13` or `5.513`."""
    t = re.sub(r"\s+", "", term).upper()
    sep = r"[.\-]?" if len(t) > STRICT else ""
    body = sep.join(re.escape(c) for c in t)
    for m in re.finditer(r"(?<![A-Z0-9])" + body + r"(?![A-Z0-9])", raw):
        if not _number_context(raw, m.start(), m.end(), t):
            return term
    return None


def _found_level(level: str, term: str, hay: str, raw: str = ""):
    """The matched text (the term, or for `partial` the page token), else None. A short or
    all-digit term is matched at the full level on the raw text with the number guards
    (norm() drops `.` and `-`, so `5513` would otherwise match `$55.13`)."""
    if level == "partial":
        return _partial_ref(term, raw)
    if level == "full" and _guarded(term):
        return _full_raw(term, raw)
    n = norm(term)
    if not n:
        return None
    if level == "tokens":
        words = n.split()
        if len(words) < 2:
            return None
        rx = r"(?<![a-z0-9])" + (r"(?![a-z0-9])[^\n]{0,%d}?(?<![a-z0-9])" % GAP).join(
            re.escape(w) for w in words) + r"(?![a-z0-9])"
        return term if re.search(rx, hay) else None
    return term if _found(n, hay) else None


def _found(term: str, hay: str) -> bool:
    return bool(term) and re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", hay) is not None


def infer_kind(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    best, best_len = "other", -1
    for kind, hosts in KIND_HOSTS.items():
        for h in hosts:
            if (host == h or host.endswith("." + h)) and len(h) > best_len:
                best, best_len = kind, len(h)
    return best


def _opener(url: str):
    host = (urlparse(url).hostname or "").lower()
    if host in ("127.0.0.1", "localhost"):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def _fetch(url: str):
    """Return (status, body text); status 0 means no HTTP response."""
    if urlparse(url).scheme not in ("http", "https"):
        return 0, ""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*"})
    try:
        with _opener(url).open(req, timeout=TIMEOUT) as r:
            raw = r.read(MAX_BYTES)
            charset = r.headers.get_content_charset() or "utf-8"
            try:
                return r.status, raw.decode(charset, errors="replace")
            except LookupError:
                return r.status, raw.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        e.close()
        return e.code, ""
    except (urllib.error.URLError, http.client.HTTPException, OSError, ValueError):
        return 0, ""


def _titles(body: str):
    m = _TITLE.search(body)
    title = html.unescape(" ".join(m.group(1).split())) if m else ""
    og = ""
    for tag in _OG.findall(body):
        c = _CONTENT.search(tag)
        if c:
            og = html.unescape(c.group(2).strip())
            break
    return title, og


_RANK = ("full", "partial", "tokens")


def verify(url: str, expect: list, kind: str = None) -> dict:
    """Fetch url and test it. `expect` holds plain terms (full level) or (level, term)
    pairs, level one of `full`, `partial`, `tokens`."""
    status, body = _fetch(url)
    title, og = _titles(body)
    text = html.unescape(_TAGS.sub(" ", _DROP.sub(" ", body)))
    joined = " ".join([title, og, text])
    hay = norm(joined)
    raw = re.sub(r"[®™©]", "", joined).upper()
    levels = {}
    for item in expect:
        level, term = item if isinstance(item, (tuple, list)) else ("full", item)
        got = _found_level(level, term, hay, raw)
        if got:
            levels.setdefault(level, [])
            if got not in levels[level]:
                levels[level].append(got)
    best = next((lv for lv in _RANK if lv in levels), None)
    if best:
        result = "match" if best == "full" else "partial"
    else:
        result = "unreadable" if unreadable_status(status) else "no_match"
    return {"url": url, "status": status, "title": title or og, "match": bool(best),
            "result": result, "match_level": best, "matched_terms": levels.get(best, []),
            "kind": kind if kind in KINDS else infer_kind(url),
            "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def default_expect(w: dict) -> list:
    """(level, term) pairs: the reference, then its partial forms (see `partial_forms`);
    with no reference, the model name, then its words in order."""
    ref, model = w.get("reference"), w.get("model")
    if ref:
        return [("full", ref), ("partial", ref)]
    return [("full", model), ("tokens", model)] if model else []


SKIP_STATUSES = (403, 429)


def verify_watch(w: dict, expect: list = None, skip_hosts: dict = None) -> dict:
    """Return a copy of w with each source's status/title/match/matched_terms/kind/checked_at set.

    Every source is tried in order and recorded. `skip_hosts` ({host: status}), shared across
    the watches of one run, records hosts that answered 403 or 429; a later source on such a
    host is not fetched but marked `unreadable` with that status and a `skipped` note."""
    out = copy.deepcopy(w)
    terms = expect if expect is not None else default_expect(w)
    for i, s in enumerate(out.get("sources", [])):
        host = (urlparse(s["url"]).hostname or "").lower()
        if skip_hosts is not None and host in skip_hosts:
            code = skip_hosts[host]
            out["sources"][i] = {**s, "status": code, "title": "", "match": False,
                                 "result": "unreadable", "match_level": None, "matched_terms": [],
                                 "kind": s.get("kind") if s.get("kind") in KINDS else infer_kind(s["url"]),
                                 "skipped": f"not fetched: {host} answered {code} earlier in this run",
                                 "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            continue
        r = verify(s["url"], terms, kind=s.get("kind"))
        s = {k: v for k, v in s.items() if k != "skipped"}
        out["sources"][i] = {**s, **r}
        if skip_hosts is not None and r["status"] in SKIP_STATUSES and host:
            skip_hosts[host] = r["status"]
    return out


def passes(w: dict) -> bool:
    return any(s.get("match") for s in w.get("sources", []))


def unread(w: dict) -> list:
    """Statuses of the sources that could not be read, when the watch did not pass."""
    if passes(w):
        return []
    return [s.get("status") for s in w.get("sources", []) if s.get("result") == "unreadable"]
