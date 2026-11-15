"""Dependency check behind /teddy-setup: what is installed, what is missing, how to fix it."""
import importlib
import importlib.metadata
import shutil
import os
import subprocess
import sys
import tempfile

from . import paths

TIMEOUT = 10
MIN_PYTHON = (3, 9)

FIX_PIP = "python3 -m pip install yt-dlp youtube-transcript-api"
FIX_FFMPEG = ("install ffmpeg with your package manager: macOS `brew install ffmpeg`, "
              "Debian/Ubuntu `sudo apt install ffmpeg`, Windows `winget install Gyan.FFmpeg`")


def _run_version(argv):
    """First line of a command's output, or None on failure, timeout or OS error."""
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if r.returncode != 0:
        return None
    lines = (r.stdout or r.stderr).strip().splitlines()
    return lines[0].strip() if lines else ""


def _module_version(mod, dist):
    v = getattr(mod, "__version__", None)
    if v:
        return str(v)
    try:
        return importlib.metadata.version(dist)
    except importlib.metadata.PackageNotFoundError:
        return ""


def _entry(name, ok, version="", fix=""):
    return {"name": name, "ok": ok, "version": version, "fix": "" if ok else fix}


def _check_python():
    v = ".".join(str(x) for x in tuple(sys.version_info)[:3])
    ok = tuple(sys.version_info)[:2] >= MIN_PYTHON
    return _entry("python", ok, f"{v} ({sys.executable})",
                  "install Python 3.9 or newer from python.org or your package manager")


def _check_ytdlp():
    """The executable on PATH, or the module (ingest then runs `python -m yt_dlp`)."""
    exe = shutil.which("yt-dlp")
    if exe:
        v = _run_version([exe, "--version"])
        if v is not None:
            return _entry("yt-dlp", True, v)
    try:
        mod = importlib.import_module("yt_dlp")
        return _entry("yt-dlp", True, _module_version(mod, "yt-dlp"))
    except Exception:  # a broken install is a missing install
        return _entry("yt-dlp", False, fix=FIX_PIP)


def _check_transcript_api():
    try:
        mod = importlib.import_module("youtube_transcript_api")
    except Exception:
        return _entry("youtube_transcript_api", False,
                      fix=f"{FIX_PIP} (it must be installed for {sys.executable})")
    return _entry("youtube_transcript_api", True, _module_version(mod, "youtube-transcript-api"))


def _check_ffmpeg():
    exe = shutil.which("ffmpeg")
    v = _run_version([exe, "-version"]) if exe else None
    if v is None:
        return _entry("ffmpeg", False, fix=FIX_FFMPEG)
    return _entry("ffmpeg", True, v)


def _check_data_folder():
    """Create the data folder (errors not swallowed), then write and delete a temp file in it."""
    try:
        home = paths.data_home(strict=True)
        fd, probe = tempfile.mkstemp(prefix=".write-check-", dir=home)
        os.close(fd)
        os.unlink(probe)
        return _entry("data folder", True, str(home))
    except OSError as e:
        return _entry("data folder", False, fix=f"make the data folder writable or set "
                                                f"TEDDY_COLLECTION_HOME to a writable path ({e})")


def check():
    """One {name, ok, version, fix} entry per requirement; also creates the data folder."""
    return [_check_python(), _check_ytdlp(), _check_transcript_api(), _check_ffmpeg(),
            _check_data_folder()]
