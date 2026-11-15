# Page specs: list or tier guide

A list's type pages are `landscape`, `list-criteria` and `left-out`, after the shared pages in `shared.md`.

Dataset fields this type uses: each listed watch's appearance has `role` `listed` or `ranked`, `rank` when the list is ordered, and `group` for its tier or price band (so the gallery shows the list's own grouping). `price_quoted` holds the price the video gives. **Prices:** a long list leaves about one search per watch, so the video's quoted price is the primary figure. Read at most one price source per brand (a brand page or one open dealer), record what it gives in `price_history` with its date and source type, and when a price comes only from a search-result snippet, say so in the entry and on the landscape page ("read prices are search snippets, dated"). A read price that differs from the video's is shown beside it, not instead of it. The video's optional `criteria` lists the selection criteria the video states. Every watch the video names without listing it (a stated exclusion, a comparison) is always recorded, never only described: a `mentioned` appearance in `records.json` with its own watch record and a photo (a frame if the video shows it, else a credited photo), so it reaches the dataset, the gallery and the parent's watch index.

## `landscape` (Landscape)

As in `review.md`, with the listed watches as the subject: one `tbl wide` table of every listed watch by tier or rank (price with date and source type, size, water resistance, movement, brand tier, source link), and a sentence on the spread the list covers. The left-out candidates belong on `left-out`, not here.

## `list-criteria` (Implied selection criteria)

The template adds the commercial-context note.

- **Inputs:**
  - The video's stated criteria, quoted with timestamps.
  - When the list is ranked: build `<run>/criteria.json` (`{criterion: {watch id: value}}`, higher is better) from the verified specs of the listed watches only, with spec features in both directions (`F:x` and `F:-x`) and any stated criterion that reduces to a spec. Save the short standard-library script that builds it as `<run>/build_criteria.py`. Write `<run>/ranking.json` as the list order, best first, and run `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/teddy.py" infer <run>/criteria.json <run>/ranking.json --run <run>`. Log in `<run>/criteria_log.md` which criteria you defined after seeing the order.
  - When the list is not ranked: no `infer`. Compare the listed watches with the left-out candidates criterion by criterion, in a table.
- **Sections:**
  1. *The answer:* a `<div class="answer">`: what the list actually rewards, and how that compares with what it says it rewards.
  2. *Stated criteria:* quotes with timestamps, and whether the listed watches meet each (`y`, `p`, `n`).
  3. *Implied criteria:* for a ranked list, the top single criteria by τ (`infer.top_single.<i>.tau` and `.key`) and any exact rules (`infer.rules.<n>.count` and the minimal rules in words). With many items exact rules are rare and the null rates near zero; say so, and lean on the τ values. For an unranked list, the comparison table.
  4. *Method and limits.*
- **Required numbers:** for a ranked list, `infer.n_items`, `infer.n_criteria`, `infer.top_single.<i>.tau`, `infer.rules.<n>.count`; when citing a baseline, `infer.null_rates.<n>`, described as the chance an exact fit exists among `infer.null_n_criteria` random criteria (as many as the run's own set).
- **Required caveats:** a list's order may reflect presentation (a countdown, a price ladder) rather than preference; say which this one is. Spec features miss finish, comfort and presence. Criteria defined after seeing the order are hypothesis-generating.

## `left-out` (Strong candidates left out)

The template adds the commercial-context note.

- **Finding candidates:** search for watches that meet the list's own criteria (stated and implied) within its theme and price band, and that were available when the video was uploaded. Write them to `<run>/peers.json` in the watch format and run `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/teddy.py" verify-links <run>/peers.json`; drop any with no matching source. Keep the queries you ran.
- **Sections:**
  1. *The strongest omissions:* one `card` per candidate (three to eight): name and reference, price with date and source type, the criteria it meets that listed watches do not (or meets as well), and the plausible reasons it was left off (price just outside the band, discontinued or not yet released at upload, already covered in another video, a stated exclusion).
  2. *Search scope:* the queries, the sites searched and the date, stated plainly: "candidates found by these searches", never "the list ignores every…".
- **Required numbers:** none.
- **Required caveats:** absence claims are bounded by the search; a candidate left out is not evidence of a motive. The store's dealer relationships are context (the note above), and an overlap between listed brands and brands a store sells is an observation, not a cause. Do not say a candidate was left out because the store does not sell it unless a source says which brands the store carries, and even then say it is an overlap, not a reason.
