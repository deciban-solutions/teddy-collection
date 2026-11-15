# Teddy Baldassarre Collection plug-in: design

Date: 2026-11-14 · Owner: Deciban Solutions LLC · Status: draft for review

## 1. Intent

Teddy Baldassarre's YouTube channel is a large, well-made body of watch-collecting knowledge, and his videos feature a beautiful range of watches. This plug-in turns one of his videos, or a small set of related ones, into a private, shareable collection of web pages that does two things at once:

- **Showcases the watches** as a photo gallery, with each watch identified to its reference number and linked to a checked source.
- **Formalizes the knowledge.** It states the criteria and concepts behind the video's judgments systematically and grounds them in evidence, under an explicit buyer's stance.

The model is the two-watch-challenge collection built on 2026-11-14 (the owner's private artifact): an overview, a lineup gallery, a sourced collection taxonomy, a criteria inference that reproduced the judges' ranking, the pickers' own watches, and a viewer-comment analysis.

**Why.** The users want to:
- pick better watches;
- understand the watch market;
- be knowledgeable when shopping for new and pre-owned watches;
- have an informed view of history and context when discussing specific watches and brands.

Teddy's videos are the learning resource. The plug-in builds on the foundation he has laid by making his criteria explicit and measurable, and by placing each video in the wider watch world and in time.

**Who uses it.** The owner and friends, each installing the plug-in from GitHub and building their own collections.

## 2. Goals

1. One run turns one video, or a small set of related videos the user names, into a **child set**: its own published artifact of several pages, chosen by video type.
2. Each child set is added to the user's **parent collection**, a separate artifact titled "Teddy Baldassarre". The parent links to every child set and holds what spans videos: timeline, watch index, taxonomy library, meta-analyses.
3. Every watch shown is identified (brand, model, reference where possible, with a stated confidence) and carries a photo and a source link. Every link is checked by a script before publishing.
4. The criteria behind each video are formalized under the **buyer's stance**, and Teddy's own stated criteria are shown beside the formalized taxonomy.
5. Time is part of the record:
   - pages are dated;
   - watches carry a status history;
   - superseded content is linked;
   - taxonomies are versioned;
   - published child sets stay frozen.
6. A structured dataset behind the pages supports meta-analyses over the whole collection, with every count computed by a script.
7. Friends can install it from GitHub, run a setup check, and use it with no knowledge of the owner's machine.

## 3. Non-goals

- **No back-catalogue crawling.** The plug-in never processes the channel wholesale; the user picks each video or small set.
- **No fact-checking or full Bayesian analysis unless the user asks explicitly.** It may offer a hand-off to the owner's `/fact-check` or `/analyze` (BFIH), but never runs one by default.
- **Not for other channels.** It is specific to Teddy Baldassarre's video formats. Generalizing to other channels is out of scope.
- **No buying advice for an individual's money.** It informs choices; it does not recommend a purchase to a specific person.

## 4. Anti-goals (failures even if it technically works)

- **Unverified facts.** A watch or link shown with a confidence it hasn't earned: a reference stated as certain when it was inferred, or a link that 404s or leads to the wrong watch.
- **Model-made numbers.** Counts, trends or percentages produced by the model rather than by a script over the dataset.
- **Silent rewriting.** Pages that change after publishing without a dated note, so the historical record is lost.
- **Inherited bias.** Adopting Teddy's views uncritically, or leaving out the commercial context: he states in his videos that his store is an authorized dealer for over 35 brands.
- **Impersonation.** Pages that use the channel's branding or could be mistaken for official Teddy Baldassarre material.
- **Taste presented as fact,** or a provisional taxonomy presented as validated.

## 5. Constraints

- Runs in Claude Code. Publishing uses claude.ai Artifacts where available. Where they aren't, the plug-in writes the same pages as a self-contained folder of HTML files (the fact-check plug-in's fallback).
- Inputs come from YouTube: the transcript (youtube-transcript-api), metadata, comments and video frames (yt-dlp, ffmpeg). YouTube sometimes blocks downloads, so the plug-in must degrade gracefully: a transcript without frames still yields pages, with gallery photos taken from sources rather than the video.
- Some brand sites block automated visits (IWC and Breguet did on 2026-11-14). Link checking needs fallbacks: brand press releases, authorized-dealer listings, then reference databases. It records which kind of source each link is.
- WebFetch returns summaries, not verbatim text. Exact checks (titles, reference numbers) use a script that fetches the raw page.
- The session's web-search allowance is shared by all agents in a session, so a run must budget its searches.
- Photos are frames from the creator's video, used to identify watches. Child sets publish privately by default; sharing is the user's choice.
- Nothing from the owner's environment is built in: no paths, no browser choice, no private-repository dependencies.

## 6. Approaches considered

**A. Skill instructions plus scripts (chosen).** A plug-in in its own GitHub repository, laid out like `deciban-solutions/fact-check-plugin`. Scripts do the mechanical work: ingest, frames, link checks, the comment-agreement check, the dataset, metrics, and page building from templates. The model does the judgment work: identifying watches, coding remarks, analysis and prose. Starter taxonomies are compiled offline with the owner's formalized-reasoner and shipped as validated data. Chosen because it keeps the evidence-based promise where it matters (taxonomies, counts, links) without heavy machinery elsewhere.

**B. Emit it from formalized-reasoner as a compiled slice.** This would carry the full honesty architecture, including refusal to deliver until every check passes. Rejected because:
- the emitter is built for one kind of deliverable per slice, and this needs six video types, a growing collection with state, and video ingestion;
- friends couldn't compile new taxonomies, because the compiler lives in a private repository.

**C. Instructions only, no scripts.** Quickest to build. Rejected because counts, link checks and the dataset would depend on the model getting them right every time, which undermines the meta-analyses.

## 7. The design as decided

### 7.1 Collections

- **Parent collection** (one per user): an artifact titled "Teddy Baldassarre", with these pages:
  - Overview
  - Timeline
  - Watch index
  - Taxonomy library
  - Meta-analyses
  - Child-sets list (by video type, then date)

  It is republished whenever a child set is added or a refresh runs.
- **Child set** (one per run): its own artifact, with a side panel like the two-watch collection's and a link back to the parent. Children are separate artifacts so one video's analysis can be shared on its own. Moving between parent and child opens a new tab, which is accepted.

### 7.2 Commands

| Command | Does |
|---|---|
| `/teddy-setup` | Checks Python, yt-dlp, youtube-transcript-api and ffmpeg; creates the user's data folder; reports what is missing and how to install it |
| `/teddy <url> [<url> …]` | Builds one child set from one video or a small related set, adds it to the dataset, republishes the parent |
| `/teddy-refresh` | Rechecks links, production status and prices across the collection; updates banners and "today" panels; never edits a frozen child page's body |
| `/teddy-meta [analysis]` | Runs the meta-analyses over the dataset and republishes the parent's meta pages |

### 7.3 Video types and page templates

The types are drawn from the channel's 1,012 uploads (title survey, 2026-11-14):

| Type | Examples | Pages beyond the shared ones |
|---|---|---|
| Contest or tournament | Two-watch challenge; subscriber tournaments | Criteria inference; Taxonomy; Wearer profiles |
| Single-watch review (new release, long-term, novelty buy) | "Grand Seiko Ushio 300 Diver"; "5 Years Owning a Sinn 556" | Landscape map; Taxonomy (the watch's category); Scorecard |
| List or tier guide | "Best Quiet Luxury Watches (15)"; "What $2,000 Buys You" | Landscape map; Implied selection criteria; Strong candidates left out |
| Brand or model-family guide | "What You Need to Know Before Buying NOMOS"; "The Tiers of Citizen" | Family map (lineup, tiers, timeline) |
| Collection building | "Building a Collection with $10,000" | Collection taxonomy; Collection scorecards |
| People and their watches | "Watch Shopping with …"; "The Watches of a Teacher"; "Most Worn Watches of the Year" | Wearer profiles |

Explainers, history, industry and Q&A videos use the shared pages plus a dated timeline of the claims and events they cover. They are the lowest priority.

**Shared pages for every child set:** Overview; Gallery (photo, reference, confidence, source link, timestamp for every watch); Viewer pulse (comment coding by two coders plus an audit sample, with agreement reported); Teddy's criteria (what he states, with quotes and timestamps); Sources and method.

**Related set:** when a run covers related videos, add a "What changed" page: watches added and dropped, price moves, criteria shifts.

**The run classifies the video type** and states the classification on the Overview page. The user can override it.

### 7.4 Taxonomy library and the buyer's stance

- **Keyed by category:** dive, chronograph, dress, GMT/travel, field/pilot, integrated-bracelet sports, two-watch and small-collection building, value for money, pre-owned purchase, and so on.
- **The paradigm is the buyer's stance:** an evidence-based, value-aware buyer of new and pre-owned watches who wants an informed view of history and context. Each taxonomy states this stance.
- **Desiderata** are written per category, each with:
  - its kind: must hold, more is better, or settled by evidence;
  - its evidence class: deductive or standard, published research, practitioner consensus, or contested taste.

  Teddy's recurring principles enter as **practitioner consensus**. A content audit of five of his videos (2026-11-14) found real, consistent principles that were not weighted or made measurable.
- **Measurements are tested before use** (formalized-reasoner's validate-first rule): each deterministic check is run against planted pass and fail examples. **Coherence factors** judge combinations, such as the two-watch "both fine, pair redundant" case.
- **Starter taxonomies** are compiled offline by the owner with formalized-reasoner and shipped as versioned data, each with its tests and a "compiled" label. Starter set: the two-watch collection taxonomy (already drafted), dive, chronograph, dress, GMT, and value for money.
- **New taxonomies at runtime:** when a run needs a taxonomy that doesn't exist, the plug-in drafts one with the same schema and built-in checks and labels it "provisional". The owner can later compile and ratify it.
- **Versioning:**
  - A run reuses the matching taxonomy and creates a new version only when the video introduces a criterion the taxonomy lacks.
  - Each child set records the taxonomy version it used.
  - The library shows a change log.
- **Format ownership (builder's call, confirmed by the owner's review):** the plug-in defines the taxonomy format. Owner compiles from formalized-reasoner go through a small exporter into it; the runtime drafter writes the same format.
- **The first starter** is converted from the two-watch taxonomy page of 2026-11-14 (artifact `7yWxiKfWGM7Yq4Uf1qapMU`). Version 1 ships its starters labelled provisional and swaps in compiled versions as the owner finishes them, so the build does not wait on compile work.
- **Shipped and user versions coexist (builder's call):**
  - Shipped versions are read-only and namespaced (for example `shipped:dive@2`).
  - A user's additions branch from a shipped version and are numbered on their own (`user:dive@2.1`).
  - A plug-in update makes its newest shipped version the default for future runs and keeps every earlier shipped version, so frozen child sets still resolve the version they recorded.

### 7.5 Dataset

Stored in the user's data folder as JSON files, one per record type:

- **Video:** id, URL, title, upload date, type, duration, views when fetched, guests, sponsorship disclosed (yes/no, with quote).
- **Appearance:** video id, watch id, timestamp(s), role (picked, reviewed, ranked, listed, mentioned, worn), position or rank if any, price quoted and its currency, Teddy's verdict (quote plus coded stance).
- **Watch (model/reference):**
  - brand, model, reference;
  - category; case size, thickness, material; water resistance; movement; complications;
  - status history (dated: in production, discontinued, replaced by a named successor);
  - price history (dated, with source type: list, dealer, auction);
  - source links with type and date checked.
- **Taxonomy version:** category, version, date, criteria, measurements, tests, compiled or provisional.
- **Artifact registry:** parent and child artifact URLs, the files each was built from, publish dates.

**Price sources (builder's call):**
- Only free sources that need no login or key: brand pages, open dealer listings, public auction results pages. Friends must be able to run the plug-in with no accounts.
- Each price is stored with its date and source type.
- Price data will be patchy, so the price index (§7.7 item 3) and price-based track-record scoring (item 2) stay hidden until the trend thresholds are met.

**Photos (owner's decision, 2026-11-14):**
- Gallery photos are video frames by default, as in the two-watch collection.
- When a usable frame can't be had (download blocked, or the watch isn't shown clearly), the plug-in copies a brand or dealer photo into the artifact, with a visible credit and a link to its source.
- Artifact pages cannot load images from other sites, so every image is copied into the artifact. The page size limit applies, so images are resized.

### 7.6 Time

- Every page shows the video's upload date and the date its facts were checked.
- **Child sets are frozen at publish.** When facts change or a newer related video is added, the child gets a dated banner ("superseded by …" or "facts have changed") and a "today" panel listing what differs. Its body is never rewritten.
- **The parent timeline** orders videos by upload date, not processing date, alongside the watch-world events the collection has recorded (releases, discontinuations, successors).
- **Series detection** links related videos automatically by title pattern and shared subject ("What $X Buys You in YYYY"; "Most Worn Watches of YYYY"). The user confirms each link.
- **Trend pages stay hidden** until the dataset has enough data. The thresholds are left to the builder (§8) and stated on the page.

### 7.7 Meta-analyses (parent collection)

All counts and trends are computed by scripts over the dataset. Every page states its sample (number of videos, date range) and the bias: "this is Teddy's selection of the watch world, not the watch world."

1. **The channel:** format mix and views by format over time; price range of featured watches by year; brand coverage against the brands his store sells (an observed overlap, not a claim about motive); sponsorship disclosure rate.
2. **Track record:** Teddy's calls in reviews and buying guides, scored against later status and prices. Where "wrong" is defined by later popularity, the page says so.
3. **The watch world through his coverage:** release and discontinuation calendar; a price index from the same references quoted at different dates; design trends (size, dial colour, materials, complications).
4. **Brand histories:** models featured over time, the brand's price ladder, Teddy's and viewers' stance by date.
5. **Audience:** viewer reason codes over time; disagreement with rankings and verdicts.

### 7.8 Visual design

The pages reuse the visual system of the 2026-11-14 collection: IBM Plex type, cool steel neutrals, a blue accent, light and dark themes, a side panel that becomes a top bar on phones. The gallery gives the watches more room than the lineup page did: larger images, grouping as the video groups them, and a full-size view on click. The look will be reviewed with mockups before the templates are built.

### 7.9 Packaging

- **Repository:** `deciban-solutions/teddy-collection` (proposed), laid out like the fact-check plug-in:

  ```
  .claude-plugin/marketplace.json
  plugins/teddy-collection/.claude-plugin/plugin.json
  plugins/teddy-collection/skills/<skill>/SKILL.md, scripts/, references/
  taxonomies/            compiled starter taxonomies (versioned data + tests)
  templates/             page templates per page type
  tests/
  examples/              the two-watch collection as a worked example
  ```

- **Install** follows the fact-check pattern: `/plugin marketplace add …` then `/plugin install …`.
- **User data** lives outside the plug-in, in a per-user data folder, so updating the plug-in never touches a user's collection.

### 7.10 Release order (owner's decision, 2026-11-14)

**Version 1:**
- `/teddy-setup`.
- `/teddy` for three video types: contests or tournaments, single-watch reviews, and lists or tier guides. Each child set gets the shared pages plus that type's pages, and a related set gets the "What changed" page.
- The parent collection, with Overview, Timeline, Watch index, Taxonomy library and the child-sets list.
- Starter taxonomies (provisional).
- The 2026-11-14 two-watch collection, imported as the owner's first child set, and also shipped under `examples/`.

**Version 2:**
- `/teddy-refresh`.
- `/teddy-meta` and the meta-analysis pages.
- The brand-guide, collection-building and people video types.

**Later:** explainer, history and Q&A videos.

## 8. Left to the builder

- Script language and file layout within each skill (Python 3.9+ expected, matching the fact-check plug-in).
- Exact JSON schemas, within §7.5.
- How the video type is detected (title rules plus transcript cues), as long as the classification is stated and can be overridden.
- Search and agent budgets per run, within the shared-allowance constraint.
- Thresholds for showing trend pages.
- How many comments are coded per video (the two-watch run coded 600 of 986).

## 9. Open questions

1. **Can friends publish Artifacts from their accounts?** If not, the local-folder fallback becomes the main path for them. To be confirmed on a second account before building the publishing layer.
2. **How much of formalized-reasoner's compile is needed per starter taxonomy?** A full compile with expert ratification, or a lighter compile with tests? This sets how long the starter library takes.
3. **Does a single run fit a reasonable time and cost?** The two-watch collection took several hours with many agents. A target run size for each video type needs measuring on a prototype.
4. **Is title-and-subject series detection reliable enough,** or does every link need the user's confirmation? (The design asks for confirmation.)
5. **Price data quality.** List, dealer and auction prices mix poorly. The price index needs a rule for which source counts. This is a version 2 question, since the price index ships in version 2.

## 10. How this breaks

- **A watch is misidentified,** with the wrong reference shown as certain → `tests/test_identification_confidence.py` (every watch record carries a confidence and a basis).
- **A link points at the wrong watch or is dead** → `tests/test_link_verification.py` (title or reference match required; a blocked site falls back to a typed alternative).
- **A count on a page differs from the dataset** → `tests/test_metrics_from_dataset.py` (pages read numbers only from script output).
- **A frozen child page body changes after publishing** → `tests/test_frozen_children.py` (a body hash recorded at publish; refresh may change only banners and today panels).
- **A provisional taxonomy is shown as compiled** → `tests/test_taxonomy_labels.py`.
- **The plug-in reads from the owner's machine** (paths, browser, private repos) → `tests/test_no_owner_paths.py`.
- **YouTube blocks the download and the run fails outright** instead of degrading → `tests/test_ingest_degrades.py`.
