"""Ingest one YouTube video: transcript, metadata, comments, video file.

Each part degrades independently: a failed part is reported `unavailable` with a
reason and the others still run. Files go to <run>/<video_id>/.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

CHANNEL_NAME = "Teddy Baldassarre"
CHANNEL_ID = "UCLGp7H4XuzA9TLJ0L4PUx8w"
_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


def video_id(url: str) -> str:
    """Extract and validate the 11-character id from a watch, youtu.be or shorts URL."""
    u = urlparse(url)
    host = (u.hostname or "").lower()
    cand = None
    if host == "youtu.be":
        cand = u.path.lstrip("/").split("/")[0]
    elif host.endswith("youtube.com"):
        if u.path == "/watch":
            cand = (parse_qs(u.query).get("v") or [None])[0]
        else:
            m = re.match(r"^/(?:shorts|embed|live)/([^/?]+)", u.path)
            cand = m.group(1) if m else None
    if not cand or not _ID.match(cand):
        raise ValueError(f"not a recognisable YouTube video URL or bad video id: {url!r}")
    return cand


def format_transcript(snippets) -> str:
    lines = []
    for s in snippets:
        secs = int(s.start)
        text = " ".join(s.text.split())
        lines.append(f"{secs // 60:02d}:{secs % 60:02d} {text}")
    return "\n".join(lines) + "\n"


def _fetch_transcript(vid):
    from youtube_transcript_api import YouTubeTranscriptApi  # lazy: optional at import time
    return YouTubeTranscriptApi().fetch(vid, languages=["en"])


def ytdlp_argv():
    """How to run yt-dlp: the `yt-dlp` executable on PATH, else this interpreter's
    `yt_dlp` module (`python -m yt_dlp`), which is what setup-check accepts."""
    exe = shutil.which("yt-dlp")
    return [exe] if exe else [sys.executable, "-m", "yt_dlp"]


def _info_json(vid, extra):
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            [*ytdlp_argv(), "--skip-download", "--write-info-json", *extra,
             "-o", str(Path(tmp) / "info"), f"https://www.youtube.com/watch?v={vid}"],
            check=True, capture_output=True, text=True)
        return json.loads((Path(tmp) / "info.info.json").read_text(encoding="utf-8"))


def _fetch_metadata(vid, run_dir):
    """yt-dlp info.json (no comments) -> metadata dict."""
    info = _info_json(vid, [])
    return {"title": info.get("title"), "upload_date": info.get("upload_date"),
            "duration": info.get("duration"), "views": info.get("view_count"),
            "description": info.get("description"), "channel": info.get("channel"),
            "channel_id": info.get("channel_id")}


def _fetch_comments(vid, run_dir):
    """Separate yt-dlp call so a comments failure never affects metadata."""
    return _info_json(vid, ["--write-comments"]).get("comments") or []


def _fetch_video(vid, run_dir):
    subprocess.run(
        [*ytdlp_argv(), "-f", "bv*[height<=1080][ext=mp4]/bv*[height<=1080]",
         "--merge-output-format", "mp4", "-o", str(Path(run_dir) / "video.%(ext)s"),
         f"https://www.youtube.com/watch?v={vid}"],
        check=True, capture_output=True, text=True)


def default_fetchers():
    return {"transcript": _fetch_transcript, "metadata": _fetch_metadata,
            "comments": _fetch_comments, "video": _fetch_video}


class MetadataUnavailable(Exception):
    """Metadata could not be fetched, so channel, title and date cannot be verified."""


def _reason(e):
    return f"{type(e).__name__}: {e}"


PARTS = ("transcript", "comments", "video")  # metadata is always fetched: it verifies the channel


def run_ingest(url, run, *, fetchers=None, any_channel=False, parts=PARTS) -> dict:
    """Fetch metadata and the requested parts into <run>/<id>/; a part already on disk from an
    earlier pass is left alone. Returns the status of metadata and of each requested part."""
    unknown = set(parts) - set(PARTS)
    if unknown:
        raise ValueError(f"unknown part(s) {sorted(unknown)}; choose from {list(PARTS)}")
    vid = video_id(url)
    f = {**default_fetchers(), **(fetchers or {})}
    out = Path(run) / vid
    status = {}

    meta = None
    try:
        meta = f["metadata"](vid, out)
    except Exception as e:  # noqa: BLE001 - degrade, never abort on a fetch failure
        status["metadata"] = {"status": "unavailable", "reason": _reason(e)}
    if meta is None and not any_channel:
        raise MetadataUnavailable("cannot verify channel, title or upload date: "
                                  f"metadata unavailable ({status['metadata']['reason']})")
    if meta is not None and not any_channel:
        if meta.get("channel_id") != CHANNEL_ID and meta.get("channel") != CHANNEL_NAME:
            raise ValueError(f"channel {meta.get('channel')!r} is not {CHANNEL_NAME}; "
                             "pass --any-channel to ingest it anyway")
    out.mkdir(parents=True, exist_ok=True)
    if meta is not None:
        (out / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        status["metadata"] = {"status": "ok"}
    if "comments" in parts:
        try:
            comments = f["comments"](vid, out)
            (out / "comments.json").write_text(json.dumps(comments, indent=2), encoding="utf-8")
            status["comments"] = {"status": "ok"}
        except Exception as e:  # noqa: BLE001
            status["comments"] = {"status": "unavailable", "reason": _reason(e)}

    if "transcript" in parts:
        try:
            (out / "transcript.txt").write_text(format_transcript(f["transcript"](vid)), encoding="utf-8")
            status["transcript"] = {"status": "ok"}
        except Exception as e:  # noqa: BLE001
            status["transcript"] = {"status": "unavailable", "reason": _reason(e)}

    if "video" in parts:
        try:
            f["video"](vid, out)
            status["video"] = {"status": "ok"}
        except Exception as e:  # noqa: BLE001
            status["video"] = {"status": "unavailable", "reason": _reason(e)}

    return {k: status[k] for k in ("transcript", "metadata", "comments", "video") if k in status}
