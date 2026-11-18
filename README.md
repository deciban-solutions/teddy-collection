# Teddy Collection

A Claude Code plug-in that turns watch-review videos from Teddy Baldassarre's YouTube channel into a private, sourced collection. Give it a video link. It identifies the watches the video shows, checks each against the maker's or a dealer's page, reads the viewer comments, drafts a taxonomy of the criteria the presenter uses, and builds a set of pages you can read, keep or share. Each video becomes a video analysis, and a collection page lists every video analysis and every watch you have collected.

## What makes it different

- **Every watch carries its evidence.** Each record has a confidence level (labelled on screen, legible on the dial, matched to specs, inferred, or unknown) and a one-line basis that says why. A reference number is never filled in from memory, and a script checks that each watch's source pages actually mention its reference or model.
- **Taxonomies you can branch.** The criteria a presenter applies are written down as a versioned taxonomy of wearer, watch and pair criteria, each with a check and a source. Six provisional starting versions ship with the plug-in. You branch a new version instead of editing an old one, so earlier pages stay true to the version they used.
- **Numbers come from scripts.** Every count, percentage, Kendall rank correlation (tau) and Cohen's kappa on a page is computed by a script and read from a file. The model never types one. Where no script produces a number, the page shows the rows instead.
- **Comments are coded, not skimmed.** Viewer comments are coded by two independent coders plus an audit coder, and the agreement between them is reported, so a reader can see how much weight the viewer summary can bear.
- **Frozen pages.** Once a video analysis is published, its page hashes are recorded, so a later change to a published page is detected instead of slipping in unnoticed.

## Install

In Claude Code:

```
/plugin marketplace add deciban-solutions/teddy-collection
/plugin install teddy-collection@teddy-collection
```

Or from your shell:

```bash
claude plugin marketplace add deciban-solutions/teddy-collection
claude plugin install teddy-collection@teddy-collection
```

## Use

First check that everything the plug-in needs is installed:

```
/teddy-setup
```

It prints a table of requirements and the command that fixes each missing one. Then give it a video:

```
/teddy https://www.youtube.com/watch?v=<video id>
```

You can also paste a link and ask in your own words, for example "add this video to my Teddy collection". A run takes a while and uses a few dozen web searches and a handful of helper agents; a run is limited to 60 web searches by default, and the skill asks you before it goes over.

Your data stays on your machine, in `~/.teddy-collection/` (or the folder named by the `TEDDY_COLLECTION_HOME` environment variable). Nothing you create is written inside the plug-in folder.

### What it builds today

Version 1 builds three kinds of video:

- **Contests and tournaments**, where people pick or build something and it is judged, such as the two-watch challenge.
- **Single-watch reviews**: a new release, a long-term ownership report or a novelty buy, such as "Grand Seiko Ushio 300 Diver" or "5 Years Owning a Sinn 556".
- **Lists and tier guides**, where several watches are chosen or ranked against a theme or budget, such as "Best Quiet Luxury Watches" or "What $2,000 Buys You".

Planned for version 2: brand and model-family guides ("The Tiers of Citizen"), collection building ("Building a Collection with $10,000") and people and their watches ("The Watches of a Teacher", "Watch Shopping with …"). Explainer, history and question-and-answer videos come later.

Give it another kind and it says so after reading only the title and transcript, offers the nearest kind it does build with what that would lose, and stops if you ask, deleting what it downloaded.

### Sharing and privacy

Every artifact the plug-in publishes is **private by default**. The plug-in never changes who can see a page. If you want to share one, you decide that yourself in Claude. Where Artifacts are not available, the plug-in writes a self-contained folder that opens in any browser.

### Commercial context

Teddy's videos state that his store is an authorized dealer for over 35 brands. Keep that in mind when reading the criteria he states or the watches he favours. Every page that presents his criteria carries this note.

### What the pages are not

The `/teddy` skill reports what a video shows and says. It does not check whether the video's claims are true. The pages never use the channel's logo or branding, and always name the video as their source.

## Examples

The plug-in ships one worked example: the two-watch challenge from the video "Watch Shopping with Watch Content Creators in Our Store" (uploaded 14 November 2026). Six enthusiasts each picked the two watches they would keep, and three store staff ranked the pairs without knowing who picked them. The example holds the 12 picked watches, the 6 watches the pickers wore, the published collection page and its photos.

Load it into your own collection:

```bash
python3 -I "<plug-in folder>/scripts/teddy.py" import-example two-watch-challenge
```

If you have published the example's page as an artifact of your own and want the parent page to link to it, add its address:

```bash
python3 -I "<plug-in folder>/scripts/teddy.py" import-example two-watch-challenge --url https://claude.ai/artifact/<your artifact id>
```

Without `--url`, the example's video analysis is listed by title only, with no link. Importing again never duplicates a watch, an appearance or a registry entry, and a rerun without `--url` keeps a link you registered earlier. The `/teddy` skill offers this import the first time it sees an empty collection.

## Requirements

- Claude Code with web search and web fetch available.
- Python 3.9 or later on your `PATH` as `python3`. The plug-in's own scripts use only the standard library.
- Two Python packages for fetching video data: `python3 -m pip install yt-dlp youtube-transcript-api`.
- `ffmpeg`, for frames and image resizing. macOS: `brew install ffmpeg`. Debian or Ubuntu: `sudo apt install ffmpeg`. Windows: `winget install Gyan.FFmpeg`.
- To publish as an Artifact, a claude.ai account with Artifacts available. Without one, the plug-in exports a local folder.

`/teddy-setup` checks all of these.

## Repository layout

```
.claude-plugin/marketplace.json            marketplace listing for this repository
plugins/teddy-collection/
  .claude-plugin/plugin.json               plug-in manifest
  skills/teddy/                            the /teddy procedure, priming, page specs, scoring rubric
  skills/teddy-setup/                      the /teddy-setup dependency check
  scripts/teddy.py                         one command-line entry point for every script step
  lib/teddycoll/                           dataset, ingest, frames, links, coding, taxonomy,
                                           infer, pages, publish, freeze, importer
  taxonomies/shipped/                      six provisional starting taxonomies
  taxonomies/schema.json                   the taxonomy format
  templates/                               page shell and per-page templates
  examples/two-watch-challenge/            the example: records.json, index.html, img/
tests/                                     offline unit tests
```

## Development

```bash
python3 -m unittest discover -s tests -v
claude plugin validate .
claude plugin validate ./plugins/teddy-collection
```

Tests that build pages need `ffmpeg` and are skipped without it. To try local changes without installing: `claude --plugin-dir ./plugins/teddy-collection`.

### Shipping a compiled checklist

Pages call a taxonomy a **buyer's checklist**. A compiled one is built offline with formalized-reasoner and converted with:

```bash
python3 -I plugins/teddy-collection/scripts/teddy.py taxonomy import-fr <compile>/spec.json \
  --checks <compile>/teddy-checks.json [--ratification <ratification record>.json] \
  --category gmt --version 2 --out plugins/teddy-collection/taxonomies/shipped/gmt@2.json
```

`teddy-checks.json` is written during the compile, for this plug-in. It holds three things:

- `spec_fields`: every field a rule reads, as in a shipped taxonomy;
- `ratifier_role`: who ratified, by role ("the builder", "an independent expert"), never by name;
- `criteria`: an entry for each concept the compile keeps, keyed by its `canon`. Each entry gives its `layer` (`wearer`, `watch` or `pair`) and optional `sources`. A script-tested criterion adds a `rule` in the plug-in's safe expression language, with `planted` pass and fail cases.
- Every criterion with a `rule` declares how much of its statement the rule tests: `rule_covers_statement: true` when the rule is the whole statement, or `checks_only` with the part it tests, in words, when the rest needs facts the record lacks (such as the buyer's use). The checklist page names that part under "Tested by", and the scorecard marks the criterion "partly" unless judgement settles the rest.
- `not_exported` (optional): concepts the compile keeps but the plug-in can't score, because they judge the whole recommendation page rather than a watch, a wearer or a pair. Each entry is `{canon, reason}`. Every kept concept must appear either in `criteria` or here, and the pages list the ones left out, with their reasons.

The import guesses nothing:

- a criterion's strictness comes from the strictest owner desideratum it serves;
- its evidence class comes from the weakest source among them;
- every rule must pass its planted cases.

A compile with no paradigm, no frozen pre-registration, an unvalidated coherence factor or a concept missing from the sidecar is refused, with every reason listed. The result carries a `warrant`, and the pages show it next to the version: whether the checklist was ratified, by whom (as a role), how many planted flaws the grader caught, and what the plug-in judges instead of testing. That last list includes every coherence factor for now, since scoring them needs facts about the buyer.

## License

Copyright 2026 Deciban Solutions LLC.

- **Code** is under the MIT License (`LICENSE`): everything under `plugins/` (the library, scripts, skills, templates and taxonomies, that is, what the plug-in installs) and everything under `tests/`.
- **Documentation** is under the Creative Commons Attribution 4.0 International License (CC BY 4.0, `LICENSE-docs`): this README and everything under `docs/`.
- **Third-party material is not covered by either license.** Video frames, quotations from Teddy Baldassarre's videos, viewer comments, brand and dealer photos, and trademarks belong to their owners and are included for commentary and reference, credited where they appear.
