"""frames: contact sheets, stills, crops and resizes via the ffmpeg binary (stdlib only)."""
import math
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


class FfmpegError(RuntimeError):
    pass


def _run(args):
    try:
        r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args],
                           capture_output=True, text=True)
    except FileNotFoundError:
        raise FfmpegError("ffmpeg is not installed or not on PATH") from None
    if r.returncode != 0:
        raise FfmpegError(r.stderr.strip() or f"ffmpeg exited {r.returncode}")


def _seconds(ts):
    """'90', '1:30' or '0:01:30.5' -> seconds as a float."""
    total = 0.0
    for part in str(ts).split(":"):
        total = total * 60 + float(part)
    return total


def ts_seconds(t):
    """A video timestamp ('90', 90, '1:30', '0:01:30.5') -> seconds, or None when it is not a
    finite, non-negative time. The one tolerant parser for recorded timestamps (sorting,
    labels, links and dataset validation all use it)."""
    if isinstance(t, bool) or t is None:
        return None
    try:
        s = _seconds(t)
    except (TypeError, ValueError):
        return None
    return s if math.isfinite(s) and s >= 0 else None


def _num(x):
    return f"{x:g}"


def _label(t):
    """Seconds -> the `--at` form: 'm:ss' (or 'h:mm:ss'), with a decimal only when needed."""
    t = round(float(t), 2)
    whole = int(t)
    frac = round(t - whole, 2)
    h, rem = divmod(whole, 3600)
    m, sec = divmod(rem, 60)
    s = f"{sec:02d}" + (f"{frac:.2f}".lstrip("0").rstrip("0").rstrip(".") if frac > 1e-6 else "")
    return f"{h}:{m:02d}:{s}" if h else f"{m}:{s}"


def _sheets(out):
    """The sheets `<out>_<n>.jpg` (any number of digits) beside `out`, in sheet order."""
    rx = re.compile(re.escape(out.name) + r"_(\d+)\.jpg")
    found = [(int(m.group(1)), p) for p in out.parent.glob(out.name + "_*.jpg")
             if (m := rx.fullmatch(p.name))]
    return [p for _, p in sorted(found)]


def sheet_times(start, end, every_s):
    """The tile times (seconds) of a sheet run: start, start+every, ... while below end."""
    start_s, end_s, step = _seconds(start), _seconds(end), float(every_s)
    if step <= 0:
        raise ValueError("--every must be positive")
    n = int((end_s - start_s) / step + 1e-9)
    times = [round(start_s + k * step, 3) for k in range(n + 1)]
    return [t for t in times if t < end_s] or [start_s]


def contact_sheet(video, start, end, every_s, out):
    """Write 4x3 tiled sheets of one frame per `every_s` seconds from start to end.

    Each tile is extracted on its own with the same seek `still` uses (`-ss <t>`), so the
    tile labelled t shows the frame `frames still --at t` returns. The label (m:ss, video
    time) is burned in top left. Files are `<out>_01.jpg`, `<out>_02.jpg`, ...,
    `<out>_100.jpg`, ... (12 tiles per sheet); returns them in sheet order. If ffmpeg's drawtext fails (usually no font
    available), the sheets are made without labels, a note goes to stderr, and the return
    value is unchanged.
    """
    video, out = Path(video), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    for old in _sheets(out):
        old.unlink()
    times = sheet_times(start, end, every_s)
    labels = [True]

    def grab(t, vf, dest):
        """Extract the frame at t; False (nothing written) when t is past the video's end."""
        try:
            _run(["-ss", _num(t), "-i", str(video), "-frames:v", "1", "-vf", vf,
                  "-q:v", "3", str(dest)])
        except FfmpegError as e:
            if "Nothing was written" in str(e) and not dest.is_file():
                return False
            raise
        return True

    def tile(t, dest):
        if labels[0]:
            text = _label(t).replace(":", "\\:")
            try:
                return grab(t, f"scale=480:-1,drawtext=text='{text}':x=5:y=5:fontsize=20:"
                            "fontcolor=yellow:box=1:boxcolor=black", dest)
            except FfmpegError as e:
                if "ffmpeg is not installed" in str(e):
                    raise
                ok = grab(t, "scale=480:-1", dest)  # raises if drawtext was not the cause
                print(f"frames: drawtext failed ({e}); sheet made without timestamps "
                      "(timestamps_burned: false)", file=sys.stderr)
                labels[0] = False
                return ok
        return grab(t, "scale=480:-1", dest)

    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        tmp = Path(tmp)
        n_sheet = 0
        for i in range(0, len(times), 12):
            d = tmp / f"s{i // 12:03d}"
            d.mkdir()
            k = 0
            past_end = False
            for t in times[i:i + 12]:
                if not tile(t, d / f"f_{k:02d}.jpg"):
                    past_end = True
                    break
                k += 1
            if k:
                n_sheet += 1
                _run(["-i", str(d / "f_%02d.jpg"), "-vf", "tile=4x3", "-frames:v", "1",
                      "-q:v", "3", f"{out}_{n_sheet:02d}.jpg"])
            if past_end:
                break
    return _sheets(out)


def _via_temp(out, args):
    """Run ffmpeg `args` (input options first) writing a temp file beside `out` with the same
    suffix, then rename it onto `out`: ffmpeg refuses an output that is also its input."""
    fd, tmp = tempfile.mkstemp(suffix=out.suffix, dir=out.parent)
    os.close(fd)
    try:
        _run([*args, tmp])
        os.replace(tmp, out)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return out


def still(video, at, out):
    """Extract one frame at time `at` (seconds or h:mm:ss) as a JPEG; returns `out`.

    Written directly, not through a temp file: the input is the video, so ffmpeg's own
    "same as input" refusal is what keeps `--out <video>` from destroying it."""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    _run(["-ss", str(at), "-i", str(video), "-frames:v", "1", "-q:v", "2", str(out)])
    return out


def crop(img, box, out):
    """Crop `img` to `box` = (x, y, w, h): top-left corner, then width and height, in pixels.

    (ffmpeg's own filter takes w:h:x:y; this function reorders.) `out` may be `img`
    itself: the crop goes to a temp file that is then renamed. Returns `out`.
    """
    x, y, w, h = box
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    return _via_temp(out, ["-i", str(img), "-vf", f"crop={w}:{h}:{x}:{y}", "-frames:v", "1",
                           "-q:v", "2"])


def _qv(quality):
    # JPEG quality (higher is better) -> ffmpeg -q:v (2 best .. 31 worst); 82 -> 3.
    return max(2, min(31, round((100 - quality) / 6)))


def resize(img, long_edge=900, quality=82):
    """Shrink `img` so its long edge is at most `long_edge`; never upscales.

    A .jpg/.jpeg input is replaced in place and its path returned. Any other suffix
    (png, webp, ...) is left untouched and a JPEG is written beside it as `<stem>.jpg`;
    that new path is returned.

    Aspect ratio is kept. Quality maps to `-q:v` as round((100 - quality) / 6),
    clamped to 2..31, so the default 82 is `-q:v 3`.
    """
    img = Path(img)
    dest = img if img.suffix.lower() in (".jpg", ".jpeg") else img.with_suffix(".jpg")
    vf = (f"scale='if(gt(iw,ih),min({int(long_edge)},iw),-2)':"
          f"'if(gt(iw,ih),-2,min({int(long_edge)},ih))'")
    fd, tmp = tempfile.mkstemp(suffix=".jpg", dir=img.parent)
    os.close(fd)
    try:
        _run(["-i", str(img), "-vf", vf, "-frames:v", "1", "-q:v", str(_qv(quality)), tmp])
        os.replace(tmp, dest)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return dest
