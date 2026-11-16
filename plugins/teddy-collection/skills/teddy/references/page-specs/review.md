# Page specs: single-watch review

A review's type pages are `landscape`, `taxonomy` and `scorecard`, after the shared pages in `shared.md`. The taxonomy is the reviewed watch's category (for example `dive` for a diver).

Dataset fields this type uses: the reviewed watch's appearance has `role` `reviewed` and Teddy's `verdict` (`{"quote", "stance"}`, stance one of `positive`, `mixed`, `negative`, `none`). Every other watch the video names is always recorded, never only described: a `mentioned` appearance in `records.json` with its own watch record and a photo (a frame if the video shows it, else a credited photo), so it reaches the dataset, the gallery and the parent's watch index. The video's optional `criteria` lists what he says he judged it on.

## `landscape` (Landscape)

- **Peers:** five to ten nearest alternatives a buyer would cross-shop, chosen by price (within about a third either way of the reviewed watch's price), category and brand tier. A peer the video names is always in the landscape, whatever its price: the price band applies only to the peers this run adds. A named peer is a watch the video sets against the reviewed watch, as a comparison or an alternative. A watch named only as history (or for its technology) is recorded as `mentioned` and shown in the gallery, but is not a landscape peer. Write them to `<run>/peers.json` as `{"watches": [...]}` in the watch format of `records.json` (brand, model, reference, specs, `price_history` with date and source type, `sources`), with `confidence` `matched_to_specs` and a basis naming the page. Run `python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/teddy.py" verify-links <run>/peers.json`; drop an added peer with no matching source. A named peer with no matching source stays, with "no source matched" or "source blocked, unread" in its basis. Peers are never added to the dataset; a named peer is also a `mentioned` watch in `records.json` (above), so it is in both.
- **Prices you cannot read:** a peer with a matching source but no readable price stays, with "not read" in the price cell. A price in another currency is shown unconverted, with the currency named; never convert it.
- **Sections:**
  1. *Where it sits:* a `<div class="answer">`: the reviewed watch's position among the peers on price, size and specification, in two or three sentences.
  2. *The map:* one `tbl wide` table, reviewed watch first, then peers by price: brand and model, reference, price (amount, date, source type), case diameter and thickness, water resistance, movement and power reserve, brand tier, source link.
  3. *How the peers were chosen:* the search scope (queries, sites, date) and the price band, and which named watches it left out, and why (named only as history or technology, not set against the reviewed watch).
- **Required numbers:** none; prices and specs are facts with sources, not computed numbers.
- **Required caveats:** the peers were chosen by this run, not by the video; prices are dated and typed, and list, dealer and auction prices are not comparable; the peer list is bounded by the searches made, so absence from it means not found, not not existing.

## `taxonomy` (Taxonomy)

As in `contest.md`, for the watch's category, without the pair layer or occasion matrix unless the taxonomy has them.

## `scorecard` (Scorecard)

The template adds the commercial-context note, since the scorecard sets Teddy's verdict beside the taxonomy.

- **Sections:**
  1. *The verdict, then the evidence:* a `<div class="answer">`: Teddy's verdict in his words (timestamp link), then where the taxonomy agrees or disagrees with it.
  2. *Criterion by criterion:* one row per taxonomy criterion: the criterion and how strict it is (must hold, more is better, depends on evidence), the mark (`y` meets, `p` partly, `n` does not, or `not assessable`), the evidence (the spec value and its source, or the judgement and its reason) and whether Teddy addressed it (quote and timestamp, or "not mentioned").
     - For a deterministic criterion, take the mark from the library, never by eye. It prints `{"taxonomy", "watch", "marks"}`, with `marks` keyed `<layer>.<key>` and each mark `y`, `n` or `not assessable`:

       ```bash
       python3 -I "${CLAUDE_PLUGIN_ROOT}/scripts/teddy.py" taxonomy score <version id> <run>/records.json <watch id>
       ```

     - A `not assessable` mark (a field the rule reads is missing, null, `unknown` or the wrong type) is shown as "not assessable" with the missing field named. It is never turned into `n`, guessed or judged by eye.
     - A judged criterion says it is judged and gives the reason.
  3. *What the review leaves out:* criteria the taxonomy weighs that the review does not discuss.
- **Required numbers:** none. Do not total the marks; there is no producer for a total.
- **Required caveats:** the commercial-context note (the template adds it); a provisional taxonomy is not ratified; the scorecard reads one taxonomy, a buyer's stance, not the only reasonable one.
