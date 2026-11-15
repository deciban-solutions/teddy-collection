---
name: teddy-setup
description: Use when the user asks to set up, install or check the teddy-collection plug-in, or when a /teddy run fails because yt-dlp, youtube-transcript-api or ffmpeg is missing. Checks the dependencies and shows what to install.
---

# /teddy-setup

Check that everything the teddy-collection plug-in needs is installed, and say how to fix what is not.

## Steps

1. Run the check. It also creates the data folder if it does not exist:

   ```bash
   python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/teddy.py" setup-check
   ```

   It prints a JSON list of `{name, ok, version, fix}` and exits 0 when every requirement is met, 1 when any is missing.

2. Show the result as a table with the columns Requirement, Status (ok or MISSING), Version or location, and Fix. The "data folder" row shows where your data lives (`$TEDDY_COLLECTION_HOME`, default `~/.teddy-collection`); the check writes and deletes a test file there, so it is MISSING when the folder cannot be written.

3. For every missing row, give the install command:

   - Python packages (`yt-dlp`, `youtube_transcript_api`): `python3 -m pip install yt-dlp youtube-transcript-api`. Install them for the same Python that ran the check; the check names that interpreter. A `yt-dlp` installed only as a Python module is enough: with no `yt-dlp` command on PATH, ingest runs it as `python3 -m yt_dlp`.
   - `ffmpeg`: use the platform's package manager: macOS `brew install ffmpeg`; Debian or Ubuntu `sudo apt install ffmpeg`; Windows `winget install Gyan.FFmpeg`.
   - Python older than 3.9: install a current Python 3.

4. After the user installs anything, run the check again and show the new table. Do not claim setup is complete until the check exits 0.

## Artifact publishing

Publishing a collection as an Artifact needs a claude.ai account with Artifacts available. This check cannot test that. Without it, the `export-local` command (`teddy.py export-local <build> <dest>`) writes the collection to a local folder that opens in any browser.
