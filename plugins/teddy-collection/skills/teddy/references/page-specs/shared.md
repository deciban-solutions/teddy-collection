# Page specs: fragment rules and the shared pages

Every child set has the shared pages below, plus its type's pages (`contest.md`, `review.md`, `list.md`) and, for a related set, `related-set.md`. The build (`build-child`) renders some sections from the dataset; you write the rest as an HTML fragment at `<run>/fragments/<page key>.html`.

## Fragment rules

A fragment is the body of one page, run through an allow-list before it is placed in the page. Break a rule and the build stops with an error naming the fragment.

- **No CSS.** No `<style>` block (a build error) and no `style` attribute (dropped). No `<script>`.
- **Tags** from the allow-list only: `section div p span h2 h3 h4 ul ol li table thead tbody tfoot tr th td caption blockquote figure figcaption img a strong em b i code pre br hr dl dt dd small sup sub details summary header article cite abbr q mark time`. Keep every tag balanced: an end tag with no open element of its name is dropped, and tags still open at the end are closed. Start headings at `h2`; the page header is the `h1`.
- **Attributes** from the allow-list only; every other attribute is dropped: on any tag `class` `id` `title` `lang` `dir` `colspan` `rowspan` `scope` `headers` `data-num` `data-spec`; on `a` `href`; on `img` `src` `alt` `width` `height`; on `time` `datetime`; on `abbr`, `q` and `blockquote` `cite` (an `http` or `https` URL).
- **Classes** only from this list (the shell styles these for every page; any other class name is dropped): `note` `lede` `callout` `answer` `tbl` `wide` `num` `mono` `ref` `y` `p` `n` `cards` `card` `ranks` `rank` `sub` `plain` `refs` `cite` `findings` `finding` `legend`. The shell's own names (`view`, `side`, `main`, `brand`, `zoom`, `zoomable`, `shell`) are never kept.
  - `answer`: the boxed short answer. `callout`: a boxed aside. `note`: small muted text. `lede`: an opening paragraph.
  - `tbl` wraps a `<table>`; add `wide` for a full-width one. `num` on a `td` or `th`: a right-aligned number cell. `mono`: monospaced text; `ref`: a reference number, in the accent colour.
  - `y`, `p`, `n`: yes, partly, no marks in a table cell.
  - `cards` holds `card` boxes (two columns); `ranks` holds `rank` boxes (four columns); `findings` holds `finding` items (a ruled left edge); `sub` is a small muted line.
  - `<ol class="refs">` is the reference list, with `<li id="ref-N">` items; `<a class="cite" href="#ref-N">` is an in-text citation; `<ul class="plain">` is a compact list; `legend` is a key under a table or figure.
- **Links**: `http` or `https` only, or `#anchor` within the page. Timestamp links are the video URL plus `&t=<seconds>`.
- **Images**: `<img src="img/<name>.jpg" alt="…">` only, naming a file in `<run>/img/`; the build copies it in.
- **Numbers**: every count, percentage, τ (Kendall rank correlation) or κ (Cohen's kappa) is `<span data-num="dotted.key"></span>`, filled from `<run>/numbers.json`. A typed τ, κ or percentage outside such a span stops the build; typed counts are not caught, so check them yourself. A key missing from `numbers.json` stops the build. Rates are fractions shown with two decimals: write "in <span data-num="…"></span> of trials", never a `%` after a fraction. Keys containing `>` (the `pairwise_wins` pairs) cannot be used; describe those in words or leave them out. A number no script produces is not stated: show the rows and let the reader count.
- **Quotes** go in `<blockquote>` (exempt from the number check), each with its speaker and a timestamp link.
- **Commercial context.** The page template adds the note to every page that presents Teddy's criteria: `teddy-criteria`, `criteria-inference`, `taxonomy`, `wearers`, `scorecard`, `list-criteria` and `left-out`. Fragments never write it; a second copy would repeat it.
- **Source.** Name the video as the source wherever the page draws on it. Never use the channel's logo or branding.

## Numbers every run has

`build-child` writes these into `numbers.json` before placing fragments:

- `data.videos`, `data.watches`, `data.appearances`, `data.credited_photos`
- `data.by_confidence.labelled_on_screen`, `.legible_on_dial`, `.matched_to_specs`, `.inferred`, `.unknown`

## `overview`

- **From data:** the video title, link and upload date; the video type with the override note; the watch and appearance counts; how sure the identifications are; the taxonomy version and label; a strip of photos; the page cards.
- **Fragment ("The short answer"):** a `<div class="answer">` of three to six sentences: what the video does, what it rewards (the main finding of the type pages), what viewers made of it, and how sure the run is. Then one sentence giving the basis of the type classification from `type.json`, and, if the user overrode the type, that they did.
- **Required numbers:** none beyond the data block; use `data.watches` if the answer counts watches.
- **Required caveats:** this is one video's selection, not the watch world; anything the run could not do (no transcript, no comments, no frames).

## `gallery`

Built entirely from the dataset; no fragment. It shows, per watch, the photo (full size on click), reference, confidence badge and basis, source links, timestamp links, quoted price and Teddy's verdict quote. It groups watches by the appearance's optional `group` field (a contestant's pair, a tier, a price band) and orders them by `rank`, then first timestamp. A credited photo shows its credit and source link. To change the gallery, change `records.json` and rerun `dataset-add`.

## `viewers` (Viewer pulse)

- **Sections:**
  1. *The sample:* how many comments were downloaded (`coding_prepare.n_comments`), how many matched a subject or keyword (`coding_prepare.n_candidates`), how many were coded (`viewers.n_comments`) and found relevant (`viewers.n_relevant`). Say what the filter matched on.
  2. *Agreement:* two coders split the comments; a third recoded a random sample (`coding_agreement.n`). Report κ for each field the type codes: `coding_agreement.best`, `.worst`, `.relevant` and the type's stance field (`.judge_stance` for a contest, `.verdict_stance` for a review, `.selection_stance` for a list). Say in words what the values mean (above 0.8 strong, 0.6 to 0.8 substantial, below 0.6 weak). A κ is empty when fewer than five audited comments were coded non-empty on that field by either side (`coding_agreement.n_nonempty.<field>.primary` and `.audit`): say the field was too few to measure, cite those counts instead, and cite no κ for it. When `coding_agreement.no_overlap` is true, or no comment matched (`coding_prepare.n_candidates` is 0), the κ values are empty and citing one stops the build: say plainly that agreement could not be measured, and cite no κ. With no matched comments, sections 3 to 5 are replaced by that one statement.
  3. *What viewers favoured:* a table of subjects with `viewers.best.<subject>`, `viewers.worst.<subject>`, `viewers.underrated.<subject>` and the like-weighted `viewers.best_weighted.<subject>`. When `viewers.n_rankings` is at least 10, add the Borda scores (`viewers.borda.<subject>`) and first and last places.
  4. *Their stance,* by type (only the keys present):
     - contest, on the result: `viewers.stance.agree`, `.disagree`, `.mixed`;
     - review, on the presenter's verdict: `viewers.verdict_stance.agrees`, `.disagrees`, `.mixed`, and a table of each subject's `viewers.sentiment.<subject>.like`, `.dislike`, `.mixed`;
     - list, on the selection: `viewers.selection_stance.agrees`, `.disputes`, `.mixed`, and what commenters said was left out, by brand (`viewers.missing.<brand>`; `viewers.missing_names` lists the names they used). Compare those brands with the `left-out` candidates.
  5. *Their reasons:* the commonest reason codes (`viewers.reasons.<code>`), each with one representative quote in a `<blockquote>`. Free-text codes are folded into one count, `viewers.reasons.other`; `viewers.reasons_other` lists them, to describe in words.
- **Required caveats:** commenters are not all viewers, and not buyers; comments were filtered to those naming a subject or keyword; the coders are AI models working from one brief, so agreement shows consistency, not independent confirmation; like weighting favours early comments.

## `teddy-criteria` (Teddy's criteria)

- **Sections:**
  1. *What he says he looks for:* a table with the quote (in his words, in a `<blockquote>` or a quote cell), the timestamp link, the criterion it states, and whether he gives a reason (`y`, `p` or `n`).
  2. *Superlatives and claims stated as fact:* quotes that assert rather than measure ("the king of this category"), kept apart from the criteria.
  3. *How the criteria map to the taxonomy:* which match a taxonomy criterion (practitioner consensus) and which are new.
- **Required numbers:** none; if you count quotes, there is no producer, so list them instead.
- **Required caveats:** the commercial-context note (the template adds it); who is speaking, since some channel videos are in a guest's voice, not Teddy's (check the intro and sign-off); transcripts are auto-captions, so brand names can be garbled; say where you corrected one.

## `sources` (Sources and method)

- **From data:** a table of every watch with its confidence, basis, sources (kind, date checked, whether the reference or model matched) and photo kind.
- **Fragment ("Method"):** the steps this run took, in order, each with its guard against bias: ingest (which parts were available); type classification; identification; link checks; photos; taxonomy (version and whether it was branched or drafted); the type pages' method; comment coding. Then the budgets used (searches and subagents, in words), what was not done, and why.
- **Required caveats:** prices are dated and typed (list, dealer, auction) and only from free sources; peers and candidates were chosen by this run, not by the video.
