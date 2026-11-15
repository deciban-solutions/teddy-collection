# Teddy Baldassarre Collection plug-in, version 1: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Claude Code plug-in, installable from GitHub, whose `/teddy <url…>` command turns one Teddy Baldassarre video, or a small related set, into a published child-set artifact. Each child set is added to the user's parent "Teddy Baldassarre" collection. `/teddy-setup` checks the required tools.

**Architecture:**
- **Scripts:** one Python command-line tool (`scripts/teddy.py`) over a small library package does every mechanical, checkable step: ingest, frames, link checks, dataset, taxonomy versions, metrics, page assembly, freeze hashes, publish manifests.
- **Skills:** two skill files (`/teddy-setup`, `/teddy`) give the model the judgment steps (identification, coding, analysis prose) and tell it which script call follows each one.
- **Pages:** built from fixed templates. Numbers on pages come only from script output.

**Tech stack:**
- Python 3.9+, standard library only inside the plug-in.
- External tools: `yt-dlp`, `youtube-transcript-api`, `ffmpeg`, all checked by setup.
- Tests: standard-library `unittest`, offline.
- Publishing: claude.ai Artifacts, with a local-folder fallback.

**Spec:** `docs/specs/2026-11-14-teddy-collection-plugin-design.md` (approved 2026-11-14). Version 1 scope is spec §7.10.

**Reference implementation** (from the 2026-11-14 two-watch run, copied into the repository): `docs/reference/2026-11-14-two-watch/`. It holds:
- `hub/build.py` and `hub/shell.html`: the collection shell with side panel and hash routing;
- `analysis/analysis.py`: the rule search, Kendall τ and the null baseline;
- `comments/BRIEF.md`: the comment-coding brief;
- `scoring/RUBRIC.md`: the blind-scoring rubric;
- the four page HTML files;
- `specs_master.json`;
- `channel_videos.tsv`: the channel title survey.

Port from these; don't reinvent.

## Global Constraints

- Plug-in scripts use the Python standard library only, and run as `python3 -I`. A script that imports the library package inserts its own `lib/` path into `sys.path` explicitly.
- No owner-specific values anywhere in the plug-in: no `/home/<user>`, no `/mnt/c`, no `msedge`, no `deciban` paths beyond the manifest `homepage`/`repository` URLs, no BFIH-repository paths.
- User data lives in `$TEDDY_COLLECTION_HOME`, defaulting to `~/.teddy-collection/`. Nothing a user creates is written inside the plug-in folder.
- Child sets publish **privately**. Sharing is the user's choice.
- Pages never use the channel's logo or branding, and always name the video as the source.
- No `/fact-check` or `/analyze` run unless the user explicitly asks for one. The skill may offer one hand-off line.
- Every image is copied into the artifact (artifact pages cannot load other sites' images), resized to at most 900 px on the long edge, JPEG quality 82.
- A non-frame photo carries a visible credit and a link to its source.
- Every watch record carries `confidence` ∈ {`labelled_on_screen`, `legible_on_dial`, `matched_to_specs`, `inferred`, `unknown`} and a one-line `basis`.
- Taxonomy labels: `compiled` or `provisional`. Version ids are `shipped:<category>@<n>` or `user:<category>@<n>.<m>`.
- The "commercial context" note is required on any page that presents Teddy's criteria: his videos state his store is an authorized dealer for over 35 brands.
- Prices only from free sources that need no login or key. Every price is stored with its date and source type (`list`, `dealer`, `auction`).
- Licence MIT. Manifest author "Deciban Solutions LLC". Repository `deciban-solutions/teddy-collection`.
- Every count, percentage, τ or trend on a page is read from a script-produced `numbers.json`. None is typed by the model.

## Review Focus

1. **A video with no on-screen name cards** (wrist shots only): watches must come out `inferred` or `unknown`, never `labelled_on_screen`. The test lives in Task 2.
2. **No captions available** (captions disabled or not in English): ingest records `transcript: unavailable` and continues on metadata, comments and frames, and the Overview says so. The test lives in Task 3.
3. **Re-running `/teddy` on a video already in the collection:** no duplicate child set. The registry reports the existing artifact and the run stops unless `--rebuild` is given. The test lives in Task 10.
4. **The same reference quoted at different prices or currencies in two videos:** both are kept in a dated price history, never overwritten. The test lives in Task 2.
5. **A list video with 20 or more watches:** the child artifact stays under 16 MB including images. The builder downsizes further and reports it. The test lives in Task 9.

---

## File structure

```
.claude-plugin/marketplace.json
plugins/teddy-collection/.claude-plugin/plugin.json
plugins/teddy-collection/scripts/teddy.py            CLI: one subcommand per task below
plugins/teddy-collection/lib/teddycoll/__init__.py
  paths.py        data-folder resolution and run folders
  dataset.py      videos / appearances / watches records, validation, merge
  ingest.py       transcript, metadata, comments, video download (degrading)
  frames.py       contact sheets, stills, crops, resize
  links.py        raw fetch, title/reference match, fallback typing
  coding.py       comment filtering, chunks, audit sample, kappa, aggregation
  taxonomy.py     schema, namespaces, versions, labels, planted-example tests, FR import
  infer.py        Kendall tau, lexicographic and weighted rule search, null baseline
  pages.py        child and parent assembly, gallery/timeline/index from data, numbers.json
  freeze.py       body hashes, banners, today panels
  publish.py      artifact files map, local-folder export, registry
  setupcheck.py   dependency checks
plugins/teddy-collection/templates/shell.html        side-panel shell (child and parent)
plugins/teddy-collection/templates/pages/*.html      per page type skeletons
plugins/teddy-collection/taxonomies/schema.json
plugins/teddy-collection/taxonomies/shipped/*.json   starter taxonomies
plugins/teddy-collection/skills/teddy-setup/SKILL.md
plugins/teddy-collection/skills/teddy/SKILL.md
plugins/teddy-collection/skills/teddy/references/   priming.md, video-types.md, page-specs/*.md,
                                                     coding-brief.md, scoring-rubric.md, taxonomy-drafting.md
tests/                                               one test file per task
examples/two-watch-challenge/                        the 2026-11-14 collection
README.md  LICENSE
```

---

### Task 1: Repository, manifests, data folder

**Files:**
- Create: `.claude-plugin/marketplace.json`, `plugins/teddy-collection/.claude-plugin/plugin.json`, `LICENSE`, `README.md` (stub), `plugins/teddy-collection/scripts/teddy.py`, `lib/teddycoll/__init__.py`, `lib/teddycoll/paths.py`
- Test: `tests/test_paths.py`, `tests/test_no_owner_paths.py`

**Interfaces:**
- Produces:
  - `paths.data_home() -> Path`: `$TEDDY_COLLECTION_HOME` or `~/.teddy-collection`, created on first call, with subfolders `dataset/`, `taxonomies/user/`, `runs/`.
  - `paths.new_run(video_ids: list[str]) -> Path`: returns `runs/<UTC yyyymmddThhmmss>_<first id>/`.
  - CLI: `teddy.py paths` prints both as JSON.

- [ ] **Step 1:** `git init` in `~/projects/teddy-collection`. Write the manifests modelled on `~/projects/fact-check-plugin`, with name `teddy-collection` and version `0.1.0`.
- [ ] **Step 2: Write the failing tests.**
  - `test_data_home_env_override`: with `TEDDY_COLLECTION_HOME` set to a temp dir, `data_home()` equals it and contains `dataset`, `taxonomies/user`, `runs`.
  - `test_new_run_is_unique`: two calls a second apart give different paths.
  - `test_no_owner_paths`: walks `plugins/` and asserts none of `/home/<user>`, `/mnt/c`, `msedge`, `BFIH-Game` appears in any file.
- [ ] **Step 3:** Run `python3 -m unittest discover -s tests -v`. Expected: the new tests FAIL.
- [ ] **Step 4:** Implement `paths.py` and the `teddy.py` dispatcher, which uses argparse subcommands and inserts `Path(__file__).parents[1]/"lib"` into `sys.path`.
- [ ] **Step 5:** Run the tests. Expected: PASS.
- [ ] **Step 6:** Commit: `feat: repository, manifests, data folder`.

### Task 2: Dataset records

**Files:**
- Create: `lib/teddycoll/dataset.py`
- Test: `tests/test_dataset.py`, `tests/test_identification_confidence.py`

**Interfaces:**
- Produces:
  - Record shapes as dicts, per spec §7.5:
    - `Video`: `id, url, title, upload_date, type, duration_s, views, views_fetched_at, guests[], sponsorship{disclosed: bool, quote}`.
    - `Appearance`: `video_id, watch_id, timestamps[], role` (one of `picked`, `reviewed`, `ranked`, `listed`, `mentioned`, `worn`), `rank, price_quoted{amount, currency}, verdict{quote, stance}`.
    - `Watch`: `id` (`brand-model-reference` slug), `brand, model, reference, category, specs{}, confidence, basis, status_history[{date, status, successor_id?, source}], price_history[{date, amount, currency, source_type, url}], sources[{url, kind, checked_at, match}], photos[{path, kind: frame|credited, credit?, source_url?}]`.
  - `dataset.load() -> dict`; `dataset.save(ds)`.
  - `dataset.add_video(ds, v)`, `add_appearance(ds, a)`, `upsert_watch(ds, w)`: these merge status, price and source histories by appending dated entries, never overwriting.
  - `dataset.validate(ds) -> list[str]` (errors).
  - CLI: `teddy.py dataset-add <run>/records.json`, which runs validate and refuses on errors.

- [ ] **Step 1: Write the failing tests.**
  - `test_upsert_keeps_price_history`: two upserts of one reference at USD 7100 (dealer, 2026-11-14) and USD 7400 (list, 2026-12-01) leave both entries, sorted by date.
  - `test_upsert_appends_status`: a later `discontinued` status keeps the earlier `in_production`.
  - `test_confidence_requires_basis`: `validate` flags any watch whose `confidence` is outside the five values or whose `basis` is empty.
  - `test_labelled_needs_frame_evidence`: `labelled_on_screen` without a `photos` entry of kind `frame` is an error.
  - `test_wrist_only_video_cannot_be_labelled`: a records file whose video has `on_screen_cards: false` is refused if any watch claims `labelled_on_screen`. (Review Focus 1.)
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement `dataset.py`. Store one JSON file per record type under `dataset/`, written to a temp file then renamed.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: dataset records with dated histories`.

### Task 3: Ingest

**Files:**
- Create: `lib/teddycoll/ingest.py`
- Test: `tests/test_ingest_degrades.py`

**Interfaces:**
- Consumes: `paths.new_run`.
- Produces: `ingest.run_ingest(url: str, run: Path, *, fetchers=None) -> dict`. It writes:
  - `run/<id>/transcript.txt` (lines `mm:ss text`);
  - `metadata.json` (title, upload_date, duration, views, description, channel);
  - `comments.json`;
  - `video.mp4` (video stream at most 1080p).

  It returns a status dict, `{transcript, metadata, comments, video}`, each `ok` or `unavailable` with a reason. `fetchers` injects callables for tests.
- CLI: `teddy.py ingest <url>… --run <dir>`. It refuses a channel other than Teddy Baldassarre (checked against metadata `channel` / `channel_id`) unless `--any-channel` is given.

- [ ] **Step 1: Write the failing tests** (fake fetchers, no network).
  - `test_blocked_video_still_ingests`: the video fetcher raises, so status `video` is `unavailable` and the other three are `ok`.
  - `test_no_captions`: the transcript fetcher raises `TranscriptsDisabled`, giving status `transcript: unavailable`, and the exit code is still 0. (Review Focus 2.)
  - `test_wrong_channel_refused`: metadata `channel: "Other"` raises `ValueError`.
  - `test_transcript_format`: snippets with start 75.2 and text `"a\nb"` give the line `01:15 a b`.
- [ ] **Step 2:** Run the tests. Expected: FAIL.
- [ ] **Step 3:** Implement. Default fetchers:
  - transcript: `youtube_transcript_api.YouTubeTranscriptApi().fetch(id, languages=['en'])`;
  - metadata and comments: `yt-dlp --skip-download --write-info-json --write-comments`;
  - video: `yt-dlp -f "bv*[height<=1080][ext=mp4]/bv*[height<=1080]"`.

  Port the transcript formatting from `docs/reference/…/transcript.txt` production. Strip the comments list out of `info.json` into `comments.json`.
- [ ] **Step 4:** Run the tests. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: ingest with graceful degradation`.

### Task 4: Frames and photos

**Files:**
- Create: `lib/teddycoll/frames.py`
- Test: `tests/test_frames.py` (skipped when `ffmpeg` is absent)

**Interfaces:**
- Produces:
  - `frames.contact_sheet(video: Path, start: str, end: str, every_s: float, out: Path) -> list[Path]`: 4×3 tiles, timestamp burned in.
  - `frames.still(video, at: str, out: Path) -> Path`.
  - `frames.crop(img: Path, box: tuple[int, int, int, int], out: Path) -> Path`.
  - `frames.resize(img: Path, long_edge: int = 900, quality: int = 82) -> Path`.
  - CLI: `teddy.py frames sheet|still|crop|resize …`.

- [ ] **Step 1: Write the failing tests.** Generate a 5-second test video with `ffmpeg -f lavfi -i testsrc`.
  - `test_sheet_count`: 0–5 s every 1 s gives one sheet.
  - `test_resize_long_edge`: a 1920×1080 still resizes to 900 px on the long edge.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement with `ffmpeg` subprocess calls. Port the drawtext and tile filter strings from this session's commands, recorded in the reference `hub/` notes.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: contact sheets, stills, crops, resize`.

### Task 5: Link verification

**Files:**
- Create: `lib/teddycoll/links.py`
- Test: `tests/test_link_verification.py` (local `http.server` fixtures)

**Interfaces:**
- Produces: `links.verify(url: str, expect: list[str]) -> dict`, returning `{url, status, title, match: bool, matched_terms[], kind, checked_at}`.
  - `expect` holds reference or model strings, compared case-insensitively after stripping `.`, `-` and spaces.
  - `kind` is one of `brand`, `press`, `dealer`, `auction`, `database`, `other`; the caller passes a hint, otherwise it's inferred from the host list in `links.KIND_HOSTS`.
  - `links.verify_watch(w: dict) -> dict` tries `w["sources"]` in order and records each result. A watch passes when at least one source has `match: true`.
- CLI: `teddy.py verify-links <records.json>` writes the results back into the records and exits 1 if any watch has no matching source.

- [ ] **Step 1: Write the failing tests.**
  - `test_title_match`: a page with title `SLGB009 | Grand Seiko` and expect `["SLGB009"]` gives `match` true.
  - `test_reference_normalised`: the body contains `220.10.38.20.01.001` and expect is `22010382001001`, giving a match.
  - `test_wrong_watch`: the page title `SLGB015` against expect `SLGB009` gives no match.
  - `test_blocked_then_fallback`: the first source returns 403 and the second matches, so the watch passes, with the first recorded as `status: 403`.
  - `test_404_fails`: every source returns 404, so the watch fails and the CLI exits 1.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement with `urllib.request`, a browser-like User-Agent, a 20 s timeout and redirects followed. The match looks at `<title>`, `og:title` and the first 200 KB of text.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: script-checked source links with fallbacks`.

### Task 6: Comment coding support

**Files:**
- Create: `lib/teddycoll/coding.py`, `skills/teddy/references/coding-brief.md` (ported from `docs/reference/…/comments/BRIEF.md`, with the picker table replaced by a `{{SUBJECTS}}` placeholder)
- Test: `tests/test_coding.py`

**Interfaces:**
- Produces:
  - `coding.prepare(comments: list[dict], subjects: dict[str, list[str]], keywords: list[str], run: Path, chunk: int = 300, audit_n: int = 90, seed: int) -> dict`: writes `chunk_*.jsonl`, `audit_sample.jsonl` and a rendered `BRIEF.md`.
  - `coding.agreement(primary: list[dict], audit: list[dict]) -> dict`: Cohen's κ for `relevant`, `judge_stance`, `best`, `worst`.
  - `coding.aggregate(coded: list[dict], likes: dict[str, int]) -> dict`: best and worst counts, like-weighted counts, stance counts, Borda, pairwise wins, first and last place, reason counts.
- CLI: `teddy.py coding prepare|agreement|aggregate`. Its outputs merge into `numbers.json`.

- [ ] **Step 1: Write the failing tests.**
  - `test_kappa_known_value`: a 10-item case with 8 of 10 agreement and a 50/50 balance gives κ = 0.6.
  - `test_borda`: the rankings `[a,b,c]` and `[b,a,c]` give Borda a=3, b=3, c=0.
  - `test_audit_sample_deterministic`: the same seed gives the same ids.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement, porting the aggregation and κ code from this session's inline scripts (the reference `analysis/` folder plus the comment-coding brief).
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: comment coding, agreement and aggregation`.

### Task 7: Taxonomy library

**Files:**
- Create: `lib/teddycoll/taxonomy.py`, `taxonomies/schema.json`, `skills/teddy/references/taxonomy-drafting.md`
- Test: `tests/test_taxonomy_labels.py`, `tests/test_taxonomy_versions.py`

**Interfaces:**
- Produces:
  - Taxonomy JSON:
    - `{id, category, version, label: compiled|provisional, paradigm, created, change_log[]}`;
    - `layers{wearer[], watch[], pair[]?}`, each criterion holding `{key, statement, kind: must|more_is_better|evidence_settled, evidence_class: deductive|research|practitioner|contested, check: {type: deterministic|judged, rule?, planted: {pass[], fail[]}}, sources[]}`;
    - `coherence[]` for pair-level factors;
    - `teddy_principles[]` (quote, video, timestamp).
  - `taxonomy.resolve(category) -> dict`: the user's newest branch, else the newest shipped version.
  - `taxonomy.get(version_id) -> dict`: every shipped version stays resolvable.
  - `taxonomy.branch(version_id, additions: dict, reason: str) -> str`: returns the new `user:` id.
  - `taxonomy.run_checks(t) -> list[str]`: every deterministic rule must pass all of its `planted.pass` cases and fail all of its `planted.fail` cases.
  - `taxonomy.import_fr(spec_json: Path) -> dict`: converts a formalized-reasoner `compiled/spec.json` (concepts → criteria; coherence factors → `coherence`) and labels the result `compiled`.
- CLI: `teddy.py taxonomy list|get|resolve|branch|check|import-fr`.

- [ ] **Step 1: Write the failing tests.**
  - `test_label_required`: `schema` validation refuses a taxonomy without `label`.
  - `test_runtime_draft_is_provisional`: `branch()` of a `provisional` base gives `provisional`; `branch()` of a `compiled` base is also `provisional` until re-imported.
  - `test_shipped_readonly`: `branch()` never writes under `taxonomies/shipped/`.
  - `test_old_versions_resolve`: with `shipped:dive@1` and `@2` present, `get("shipped:dive@1")` works and `resolve("dive")` gives `@2`.
  - `test_planted_checks`: the rule `water_resistance_m >= 100` with pass `[{water_resistance_m: 200}]` and fail `[{water_resistance_m: 50}]` gives no errors; swapping the two gives an error.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Deterministic rules are a small safe expression language over spec fields: comparisons, `and`, `or`, `in`, numbers and strings, parsed with `ast` and evaluated only on whitelisted node types. For `import_fr`, read `~/projects/formalized-reasoner/poc/*/compiled/spec.json` on the owner's machine to learn the shape. It is not a runtime dependency, and the test uses a fixture copied from one compiled spec.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: versioned taxonomy library with planted-example checks`.

### Task 8: Rule inference and metrics

**Files:**
- Create: `lib/teddycoll/infer.py`
- Test: `tests/test_infer.py`

**Interfaces:**
- Produces:
  - `infer.kendall_tau_b(x: dict, y: dict) -> float`.
  - `infer.single(criteria: dict[str, dict], target: list[str]) -> list[tuple[float, str]]`.
  - `infer.lexicographic(criteria, target, max_len: int = 3) -> dict[int, list[tuple]]`: minimal exact, tie-free rules.
  - `infer.weighted_share(criteria, keys, target, n: int = 400, seed: int = 7) -> float`: ties count as failures.
  - `infer.null_rate(n_items, n_criteria: int = 40, trials: int = 40, seed) -> dict`.
  - CLI: `teddy.py infer <criteria.json> <ranking.json>` writes `infer.json` and merges it into `numbers.json`.

- [ ] **Step 1: Write the failing tests**, using the 2026-11-14 data as a fixture copied from `docs/reference/…/analysis/`.
  - `test_reproduces_two_watch_rule`: `("F:n_wr100", "F:-max_thick")` is among the length-2 rules for the judges' order `[brit, adrien, teddy, marco, james, andrew]`.
  - `test_ties_fail_weighted`: two criteria that tie brit and adrien give share 0.0.
  - `test_tau_identity`: `kendall_tau_b(x, x) == 1.0`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement by porting `docs/reference/…/analysis/analysis.py`. That file already contains the tie fix.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: criteria inference and rank metrics`.

### Task 9: Page assembly

**Files:**
- Create: `lib/teddycoll/pages.py`, `templates/shell.html`, `templates/pages/{overview,gallery,viewers,teddy-criteria,sources,what-changed,criteria-inference,taxonomy,wearers,landscape,scorecard,list-criteria,left-out,parent-overview,timeline,watch-index,taxonomy-library,child-list}.html`
- Test: `tests/test_pages.py`, `tests/test_metrics_from_dataset.py`

**Interfaces:**
- Consumes: `dataset.load`, `taxonomy.get`, `numbers.json`.
- Produces:
  - `pages.build_child(run: Path, video_ids: list[str], type: str, fragments: dict[str, Path]) -> Path`: writes `run/build/index.html` and `img/`.
    - Gallery, timeline and watch index are generated from data.
    - Model-written analysis pages arrive as HTML fragments in `run/fragments/<page>.html`.
    - Every number in a fragment is written `<span data-num="key">…</span>`, and the builder fills its text from `numbers.json[key]`.
  - `pages.build_parent() -> Path`: parent collection from the dataset and registry. The timeline is ordered by video `upload_date`, not by processing date.
  - `pages.diff_videos(older_id: str, newer_id: str) -> dict`: watches added and dropped, price moves per reference and criteria added. It is written into `numbers.json` under `what_changed.*` for the related-set page.
  - Merge and scoping: port `docs/reference/…/hub/build.py` (CSS scoping per view, hash routing, tie-safe router, citation anchors).
  - The child shell's side panel adds "← Teddy Baldassarre collection", linking to the parent URL from the registry.
  - CLI: `teddy.py build-child <run> --type <type> --videos <ids>…` and `teddy.py build-parent`.

- [ ] **Step 1: Write the failing tests.**
  - `test_num_spans_filled`: the fragment `<span data-num="tau_judges_expert">x</span>` with numbers `{"tau_judges_expert": 0.47}` renders `0.47`.
  - `test_unknown_num_key_fails`: a missing key raises `KeyError`. A typed number with no span is allowed only inside `<blockquote>`, `<code>` or a spec table cell marked `data-spec`. A checker scans for bare `τ =`, `%` and `κ` patterns outside spans and fails on them.
  - `test_page_size_budget`: 24 fake 1920×1080 images give a total build of at most 16 MB, after the builder downsizes to 700 px if needed and records `downsized: true`. (Review Focus 5.)
  - `test_router_anchor`: the built page contains the router script, and every `href="#ref-N"` has a matching `id`.
  - `test_child_links_parent`: the built child contains the parent URL from a fake registry.
  - `test_timeline_by_upload_date`: videos uploaded 2025-03-01 and 2024-06-01, added in that order, appear in the timeline 2024 first.
  - `test_diff_videos`: two fake list videos sharing 3 of 5 references give `added` 2, `dropped` 2, and a price move on a shared reference from 500 to 550 USD.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Page skeletons are ported from the reference HTML: `index.html` gives the gallery, `taxonomy.html` the taxonomy, `inference.html` the criteria inference, `tastes.html` the wearers. The visual tokens come from the reference shell. Spec §7.8: the gallery gets larger images, the video's own grouping, and a click-to-enlarge `<dialog>`.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: child and parent page assembly from data`.

### Task 10: Freeze, publish manifest, registry, local fallback

**Files:**
- Create: `lib/teddycoll/freeze.py`, `lib/teddycoll/publish.py`
- Test: `tests/test_frozen_children.py`, `tests/test_publish.py`

**Interfaces:**
- Consumes: `pages.build_child`, `pages.build_parent`.
- Produces:
  - `freeze.record(build: Path) -> str`: the SHA-256 of each view's body, excluding the `data-banner` and `data-today` slots.
  - `freeze.verify(build, recorded) -> list[str]`.
  - `freeze.set_banner(build, html)` and `freeze.set_today(build, html)`.
  - `publish.files_map(build: Path) -> dict`: `{published_path: absolute_source}` for the Artifact tool's `files`.
  - `publish.export_local(build, dest: Path) -> Path`: a self-contained folder.
  - `publish.registry_add(kind: parent|child, video_ids, url, build, hashes)`, `registry_find(video_id) -> dict | None`.
  - `publish.series_candidates(video: dict) -> list[dict]`: registered videos whose titles match the same pattern with a different year (`What \$[\d,]+ Buys You .* (\d{4})`, `Most Worn Watches .* (\d{4})`, `Top Watches of (\d{4})`). The user confirms each candidate before it is linked.
  - CLI: `teddy.py check-new <ids>… [--rebuild]` exits 3 when any id is already registered, unless `--rebuild` is given. `teddy.py publish-prepare <build>` prints `{file_path, files}` JSON for the skill to pass to Artifact. `teddy.py registry add|find`. `teddy.py export-local <build> <dest>`.

- [ ] **Step 1: Write the failing tests.**
  - `test_banner_does_not_break_freeze`: after `set_banner`, `verify` returns no errors.
  - `test_body_edit_breaks_freeze`: changing one word in a view body makes `verify` report that view.
  - `test_rerun_detected`: after `registry_add(child, ["bDePE9oVcV4"], …)`, `registry_find("bDePE9oVcV4")` returns it, and `teddy.py check-new bDePE9oVcV4` exits 3 without `--rebuild`. (Review Focus 3.)
  - `test_export_local_self_contained`: the exported folder contains `index.html` and every `img/` file it references.
  - `test_files_map_relative_keys`: keys have no leading slash.
  - `test_series_candidates`: a registered "What $500 Buys You in Watches in 2025" is a candidate for "What $500 Buys You in Watches in 2026", and "What $2,000 Buys You in 2026" is not.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. The registry is `data_home()/registry.json`, written atomically.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: frozen children, publish manifests, registry`.

### Task 11: `/teddy-setup`

**Files:**
- Create: `lib/teddycoll/setupcheck.py`, `skills/teddy-setup/SKILL.md`
- Test: `tests/test_setupcheck.py`

**Interfaces:**
- Produces:
  - `setupcheck.check() -> list[dict]`: one entry per requirement, `{name, ok, version?, fix}`.
  - The requirements are Python ≥ 3.9, `yt-dlp` (CLI or module), `youtube_transcript_api` importable by the interpreter that runs it, and `ffmpeg`.
  - It also creates the data folder.
  - CLI: `teddy.py setup-check`.

- [ ] **Step 1: Write the failing test.** `test_missing_tool_reported`: with `PATH` emptied, `ffmpeg` is reported `ok: false` with a non-empty `fix`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Then write the SKILL.md: frontmatter `name: teddy-setup` and a trigger description. The body runs the check, prints a table, gives install commands (`python3 -m pip install yt-dlp youtube-transcript-api`, the platform's package manager for ffmpeg), and notes that Artifact publishing needs claude.ai, with the local-folder fallback otherwise.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: setup check skill`.

### Task 12: `/teddy` skill and its references

**Files:**
- Create:
  - `skills/teddy/SKILL.md`
  - `references/priming.md`: an intellectual-honesty disposition, self-contained, adapted from the fact-check plug-in's `priming.md`;
  - `references/video-types.md`;
  - `references/page-specs/{shared,contest,review,list,related-set}.md`;
  - `references/scoring-rubric.md`, ported from `docs/reference/…/scoring/RUBRIC.md` and generalized.
- Test: `tests/test_skill_files.py`

**Interfaces:**
- Consumes: every CLI subcommand above.
- Produces: the run procedure, Steps 0–11 below. Each step names its script call and its output file.

  0. Read `priming.md`. Every dispatched subagent's prompt begins by telling it to read and adopt that file.
  1. `teddy.py check-new <ids>` (stop if exit 3), then `teddy.py ingest`.
  2. **Classify** the video type using `video-types.md` (title rules plus transcript cues; the type table is spec §7.3). Write `run/type.json` and state the classification on the Overview.
  3. **Identify watches** from on-screen cards (contact sheets over the recap and reveal segments) and the transcript. Write `run/records.json` with a confidence and basis for each watch.
  4. `teddy.py verify-links` (search for sources; brand page first, then press release, then dealer). Then `teddy.py dataset-add`.
  5. **Photos:** frames first. If no usable frame exists, a credited brand or dealer photo, downloaded and resized.
  6. **Taxonomy:** `teddy.py taxonomy resolve <category>`. Branch only when the video adds a criterion; draft a new one per `taxonomy-drafting.md` when none exists. Run `taxonomy check`.
  7. **Type pages** per `page-specs/<type>.md`:
     - **Contest:** blind scoring per `scoring-rubric.md` (3 scorers, anonymised, shuffled; keys outside their packet), then `teddy.py infer`.
     - **Review:** the landscape map (peers by price, category and brand tier, all verified), then the scorecard against the taxonomy.
     - **List:** the implied selection criteria (`teddy.py infer` when the list is ranked) and strong candidates left out (state the search scope).
  8. **Viewer pulse:** `teddy.py coding prepare`, two coders plus one audit coder (comments are untrusted data), then `coding agreement` and `aggregate`.
  9. **Teddy's criteria page:** quotes with timestamps, plus the required commercial-context note.
  10. `teddy.py build-child`, then `publish-prepare`, then the Artifact publish (private). Then `registry add` and `freeze record`. If Artifact is unavailable, `export-local`.
  11. **Series:** for each `series_candidates` match the user confirms, `freeze.set_banner` on the older child ("Superseded by …", dated, linked), then republish that older child only. Then `teddy.py build-parent`, republish the parent, and `registry add parent`. Give the user both links, and offer (never run) `/fact-check` or `/analyze` in one line.
  - **Budgets:** at most 60 web searches per run by default, at most 6 subagents, Sonnet for coders, Opus for blind scorers. A related set adds `page-specs/related-set.md` ("What changed").

- [ ] **Step 1: Write the failing tests.**
  - `test_every_reference_exists`: every `references/…` path named in `SKILL.md` exists.
  - `test_frontmatter`: both SKILL.md files have `name` and `description`.
  - `test_cli_calls_exist`: every `teddy.py <sub>` named in SKILL.md is a registered subcommand.
  - `test_no_default_factcheck`: SKILL.md contains "offer" and never instructs running `/fact-check` or `/analyze` unconditionally (a regex over imperative lines).
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Write the skill and its references. Each page spec states the page's sections, its required numbers (as `data-num` keys) and its required caveats.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: /teddy skill and page specs`.

### Task 13: Starter taxonomies

**Files:**
- Create: `taxonomies/shipped/{two-watch,dive,chronograph,dress,gmt,value}@1.json`
- Test: `tests/test_shipped_taxonomies.py`

**Interfaces:**
- Consumes: the `taxonomy.py` schema and `run_checks`.
- Produces: six `provisional` taxonomies under the buyer's stance (spec §7.4).
  - `two-watch@1` is converted from `docs/reference/…/taxonomy.html`: 6 wearer criteria, 9 watch criteria, 7 pair criteria, 10 sources.
  - The other five are researched by the implementer from published sources. Each holds at least 6 criteria, every one with a source, a kind and an evidence class, and every deterministic one with planted pass and fail cases. `teddy_principles` are seeded from `docs/reference/…/teddy_content_audit.md` where relevant.

- [ ] **Step 1: Write the failing test.** `test_shipped_valid`: every shipped file validates against the schema, passes `run_checks`, has `label: provisional`, has a paradigm whose statement contains "buyer", and lists sources for every criterion.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Write the six files.
- [ ] **Step 4:** Run. Expected: PASS.
- [ ] **Step 5:** Commit: `feat: six provisional starter taxonomies`.

### Task 14: Example collection, import, README

**Files:**
- Create: `examples/two-watch-challenge/` (from `docs/reference/…/hub/index.html` plus `img/`), `lib/teddycoll/importer.py`, the full `README.md`
- Test: `tests/test_example_import.py`

**Interfaces:**
- Consumes: `dataset`, `publish.registry_add`.
- Produces: `teddy.py import-example two-watch-challenge [--url <artifact>]`. It loads the 2026-11-14 records (12 watches from `specs_master.json`, the video, the appearances with roles `picked` and `worn`) into the user's dataset, and registers the child set with its existing URL (the owner's artifact URL for the owner; omitted for others).

- [ ] **Step 1: Write the failing test.** `test_import_then_parent_builds`: in a temp `TEDDY_COLLECTION_HOME`, import, then run `build_parent()`. The parent contains "Watch Shopping with Watch Content Creators in Our Store" and 12 index entries plus 6 worn watches.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3:** Implement. Write the README in the fact-check README's shape: what it does, what makes it different, install, use, examples, requirements, layout. State the private-by-default rule and the commercial-context note.
- [ ] **Step 4:** Run the whole suite: `python3 -m unittest discover -s tests -v`. Expected: all PASS (ffmpeg tests may be skipped).
- [ ] **Step 5:** Commit: `feat: example collection, importer, README`.

### Task 15: Live trial on two new videos

**Files:**
- Modify: page specs or scripts as the trial shows
- Create: `docs/trials/2026-11-trial.md`

- [ ] **Step 1:** Install the plug-in locally (`/plugin marketplace add ~/projects/teddy-collection`, then `/plugin install teddy-collection@deciban-solutions`), run `/teddy-setup`, then import the example.
- [ ] **Step 2:** Run `/teddy` on one single-watch review (for example `https://www.youtube.com/watch?v=8dXA9BIObQQ`, "Hands-On with the Newest Rolex - The Perpetual Padellone"). Record wall time, subagent count, searches used and the output links. This answers spec open question 3.
- [ ] **Step 3:** Run `/teddy` on one list video (for example `pZ62fpeW760`, "What $500 Buys You in Watches in 2026"). Record the same figures.
- [ ] **Step 4:** Ask the owner to have one friend install the plug-in and run `/teddy-setup` plus one `/teddy` on their own account. Record whether Artifact publishing works there. This answers spec open question 1 and needs the owner.
- [ ] **Step 5:** Fix what the trial exposes, with a test for each fix. Then commit: `fix: trial findings` and `docs: trial record`.
