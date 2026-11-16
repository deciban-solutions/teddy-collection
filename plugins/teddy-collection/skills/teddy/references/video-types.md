# Video types

Classify each run's video (or, for a related set, the set) into one type. The type picks the pages (`page-specs/<type>.md`). Version 1 builds three types: `contest`, `review` and `list`. The types come from a survey of the channel's uploads.

## The types

| Type key | What it is | Examples | Pages beyond the shared ones |
|---|---|---|---|
| `contest` | People pick or build something and it is judged or ranked | Two-watch challenge; subscriber tournaments; "Who built the best collection?" | Criteria inference; Taxonomy; Wearer profiles |
| `review` | One watch (or one reference family) examined in depth: a new release, a long-term ownership report, a novelty buy | "Grand Seiko Ushio 300 Diver"; "5 Years Owning a Sinn 556" | Landscape map; Taxonomy (the watch's category); Scorecard |
| `list` | Several watches chosen, grouped or ranked against a theme or budget | "Best Quiet Luxury Watches (15)"; "What $2,000 Buys You"; tier guides | Landscape map; Implied selection criteria; Strong candidates left out |

Not built in version 1: brand or model-family guides ("What You Need to Know Before Buying NOMOS", "The Tiers of Citizen"), collection building ("Building a Collection with $10,000"), people and their watches ("Watch Shopping with …", "Most Worn Watches of the Year"), and explainers, history, industry and question-and-answer videos.

## How to classify

1. **Title rules first.** Match the title, ignoring case:
   - `contest`: "challenge", "tournament", "versus", "vs", "battle", "who wins", "who built", "competition", "bracket".
   - `review`: one named model or reference and no number of watches; "review", "hands-on", "years owning", "months with", "long-term", "why I bought", "first look".
   - `list`: a count ("15 watches", "Top 10", "(12)"), "best", "tier", "tiers of", "what $X buys you", "under $X", "ranking every", "buyer's guide" with several models.
   - Not built: "before buying" plus a brand name alone, "tiers of" plus one brand (brand guide); "building a collection", "collection with $" (collection building); "watch shopping with", "the watches of", "most worn" (people); "history of", "how it's made", "explained", "Q&A" (explainer).
2. **Transcript cues second.** Read the first three minutes and the last five:
   - `contest`: several people introduced as competitors; a brief or rules stated; a reveal, judging or scoring segment; a declared winner or placing.
   - `review`: one watch on the wrist throughout; specs, pros and cons, a verdict on that watch.
   - `list`: repeated "next up", "number N", "moving on"; a price band or tier named per section; a stated theme for the selection.
3. **When the two disagree**, the transcript wins, because titles are written to be clicked. Say so in `basis`.
4. **When the video is a type version 1 does not build**, stop and tell the user: name its type, say version 1 does not build it, and name the nearest built type with what would be lost (for example, a brand guide read as a `list` loses the family map). Continue only if the user picks a built type. If they stop, discard the run as SKILL.md Step 2 says; only the metadata and transcript were fetched, so little was spent.
5. **A related set** takes the type of its videos. If they differ, ask the user which type to build.

## The record

Write `<run>/type.json`:

```json
{"type": "list", "title_rule": "count in title: \"15 watches\"",
 "transcript_cues": ["\"number 15\" at 1:02", "price band named per section"],
 "basis": "Title and transcript agree: a ranked list of fifteen watches.",
 "overridden_by_user": false}
```

The Overview page states the type the build was given and that the user can override it. If the user overrides, set `type` to their choice, keep the original evidence, set `overridden_by_user` to true, and say so in the Overview's short answer.
