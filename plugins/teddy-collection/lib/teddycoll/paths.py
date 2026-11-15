"""User data locations. Nothing a user creates is written inside the plug-in folder."""
import os
from datetime import datetime, timezone
from pathlib import Path

SUBFOLDERS = ("dataset", "taxonomies/user", "runs")


def data_home(strict: bool = False) -> Path:
    """$TEDDY_COLLECTION_HOME or ~/.teddy-collection, created with its subfolders when it
    can be. A home that cannot be created (a read-only file system) is still returned, so
    reads work; a later write names the problem. With `strict`, that OSError is raised."""
    env = os.environ.get("TEDDY_COLLECTION_HOME")
    home = Path(env).expanduser() if env else Path.home() / ".teddy-collection"
    for sub in SUBFOLDERS:
        try:
            (home / sub).mkdir(parents=True, exist_ok=True)
        except OSError:
            if strict:
                raise
            break
    return home


def new_run(video_ids: list) -> Path:
    """Create and return runs/<UTC yyyymmddThhmmss>_<first id>/."""
    if not video_ids:
        raise ValueError("new_run needs at least one video id")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run = data_home() / "runs" / f"{stamp}_{video_ids[0]}"
    run.mkdir(parents=True, exist_ok=True)
    return run
