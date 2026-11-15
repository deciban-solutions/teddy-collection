# Page spec: related set ("What changed")

A run over two or more related videos (a series such as "What $2,000 Buys You" year by year, or a video and its follow-up) adds the `what-changed` page after the shared and type pages. The build compares the earliest and the latest video by upload date.

Dataset fields this page uses: each video's optional `criteria` (the criteria it states, as short phrases, written the same way in both videos so a change is a real change), and each appearance's `price_quoted`.

## `what-changed` (What changed)

- **From data:** the two videos with their upload dates; the watches added (`what_changed.counts.added`) and dropped (`what_changed.counts.dropped`), each listed; price moves on references both videos quote, with the change where the currencies match; criteria the later video states that the earlier does not.
- **Fragment ("What it means"):**
  1. A `<div class="answer">`: what the change says about the series in two or three sentences (a shifted price band, a brand rotated out, a new criterion).
  2. *Why watches dropped:* for each dropped watch, what the dataset's `status_history` shows (discontinued, replaced by a named successor) or "no reason recorded".
  3. *Price moves in context:* whether the quoted prices moved with list prices, in words; cite `what_changed.counts.price_moves` for the count.
- **Required numbers:** `what_changed.counts.added`, `.dropped`, `.shared`, `.price_moves` when cited.
- **Required caveats:** quoted prices are the video's figures, not market prices; currencies that differ are not compared; a watch dropped from a list was not necessarily judged worse.
