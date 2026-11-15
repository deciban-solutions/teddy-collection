# Blind scoring for contests

A contest ranks entries: a pair or small collection each person built, or a single watch each person picked. Blind scoring asks three scorers to rate every entry without knowing who built it or how it was placed. Their scores become candidate criteria for `teddy.py infer`, which asks which criteria reproduce the contest's ranking.

This file has two parts: how to prepare the packets (for you, the orchestrator), and the rubric itself (copied into each packet).

## Part A: preparing the packets (orchestrator only)

1. **Fact base.** For every watch in every entry, write the specs from the verified sources in `records.json`: case diameter and thickness, lug-to-lug if known, water resistance, crown type, band, movement (type, calibre, power reserve), complications and list price with its date. Never from memory; write "unknown" for a missing field.
2. **The brief.** Copy the contest's brief from the transcript, word for word, with its timestamp.
3. **Judge-derived criteria.** List every evaluative remark the judges make in the reveal, with its timestamp. Phrase each as a neutral criterion ("the two watches make sense together as one collection"). Do not say which entry prompted which remark.
4. **Anonymise.** Give the entries labels ENTRY-U, ENTRY-V, ENTRY-W and so on, and the watches within an entry -1, -2. Remove every person's name, the placings, the judges' words tied to an entry, and anything else that identifies an entry (a nickname, a watch someone is known for wearing).
5. **Shuffle per scorer.** Each scorer gets the entries in a different order with different labels, and the watches within each entry in a different order. Use a seeded shuffle (seeds 1, 2, 3) so the packets can be rebuilt.
6. **Keys outside the packets.** Write the label-to-entry and label-to-watch maps to `<run>/scoring_keys.json`, outside `<run>/scoring/`. Each scorer's folder `<run>/scoring/scorer<N>/` holds only `RUBRIC.md` (Part B below, filled in) and `entries.md` (the anonymised fact base). Scorers write `scores.json` there.
7. **Dispatch three scorers** (model: Opus), in parallel, each told to read only its two files, with no web access and no other files.

## Part B: the rubric (copied into each packet, with the bracketed parts filled)

### The task you are scoring against

[The contest's brief, word for word.] The entries are anonymised (ENTRY-U, ENTRY-V, …; watches -1, -2). You do not know who built them or how anyone ranked them. Do not try to find out: do not search the web and do not open any file other than this rubric, your `entries.md` and the output you write. Judge only from the specs given and your own knowledge of these watches.

### The default wearer (use for every entry)

Unless the brief names a wearer, use this one: a watch enthusiast with a medium wrist (about 17 cm or 6.75 in), an office job, travelling internationally a few times a year. Days per year by occasion:

| Occasion key | Occasion | Days per year |
|---|---|---|
| black_tie | Black tie or formal evening | 2 |
| suit | Suit, business formal | 20 |
| biz_casual | Business casual office | 150 |
| dinner | Dinner, night out | 40 |
| weekend | Weekend casual | 100 |
| active | Sport, outdoors, yard work | 30 |
| swim | Swimming, beach | 10 |
| scuba | Scuba diving | 0 |
| travel | Travel across time zones | 12 |

If the brief names a wearer or a budget, write that wearer here instead and keep the table's form.

### Part 1: each watch (score all of them)

Integer scores 1 to 5 (5 is best) unless stated.

- `register`: 1 pure tool, 2 sport, 3 the versatile middle, 4 dressy, 5 formal dress (thin, plain, leather or precious metal).
- `robustness`: what it survives. Water resistance against activities (30 m splash; 50 m casual swimming; 100 m snorkelling or surfing; 200 m scuba), screw-down crown, lume, legibility, shock and scratch tolerance. A dress watch that must stay dry scores low.
- `wearability`: all-day comfort on the wearer's wrist: diameter, thickness (does it fit under a cuff?), lug-to-lug, weight, band comfort and adjustability.
- `useful_complications`: how much the complications serve this wearer's life (date, GMT for travel, chronograph for timing). Ornamental or rarely used complications score lower; none at all is a 3.
- `practicality`: daily ownership friction: accuracy, power reserve (does it survive a weekend off the wrist?), automatic or hand-wound, calendar resetting, delicacy, servicing cost. 5 is grab-and-go.
- `horological_merit`: movement design and finishing, in-house engineering, innovation, dial craft.
- `design_integrity`: purposeful design with historical roots, timelessness, and enough neutrality to go anywhere.
- `value`: what the money buys in quality, finishing and engineering per dollar.
- `occasion_fit`: for each occasion key, 2 fits, 1 passable but a compromise, 0 wrong for the setting. Judge this watch on its own band, not the watch type in general.

### Part 2: each entry (score all of them)

Skip this part when every entry is a single watch; then Part 1 plus the holistic rank is the whole rubric.

**Collection criteria from the taxonomy (1 to 5).** [One line per criterion in the resolved taxonomy's `pair` layer, with its key and statement. For the two-watch taxonomy these are:]

- `differentiation`: do the watches differ in register, size, dial colour, complications and band, so there is no redundancy?
- `coherence_expert`: can each watch's place be explained by one collection logic, and do they share values while looking different?
- `anchor_strength`: how well the better daily watch covers the bulk of wear-days alone.
- `tension_point`: is there one deliberate, productive contrast (origin, movement type, era, register)?
- `gap_test`: remove either watch; does a real gap open that the other can't fill? 5 means each is indispensable.
- `wear_balance`: does each watch own a distinct kind of day, so both get worn?

**Criteria from the judges' words (1 to 5).** [One line per judge-derived criterion from Part A step 3, each with a short key. Say who the judges are in general terms (for example "a panel of three boutique staff") so the scorer can read the criterion as they would, but never which entry prompted it.]

### Holistic

- `expert_rank`: rank the entries 1 (best) to N for this brief and this wearer, using your own expert judgment. No ties.
- `rationale`: two to four sentences per entry.

### Output

Write one JSON file to `scores.json` in your folder:

```json
{
  "watches": {"ENTRY-U-1": {"register": 3, "robustness": 4, "wearability": 4, "useful_complications": 3,
                            "practicality": 5, "horological_merit": 4, "design_integrity": 4, "value": 3,
                            "occasion_fit": {"black_tie": 1, "suit": 2, "biz_casual": 2, "dinner": 2,
                                             "weekend": 2, "active": 1, "swim": 1, "scuba": 0, "travel": 1}}},
  "entries": {"ENTRY-U": {"differentiation": 3, "...": 3, "expert_rank": 2, "rationale": "..."}}
}
```

Every watch and every entry must be present, and every score an integer in range. Validate the file with Python (json.load, key and range checks) before you finish. Score Part 1 for all watches before Part 2, and score the criteria before you make the holistic ranking.

## Part C: from scores to criteria (orchestrator only)

1. Check each `scores.json` against the rubric. A scorer that missed a key or went out of range is re-run once; a second failure is reported on the page and that scorer is dropped.
2. Unblind with `<run>/scoring_keys.json`. Save the short standard-library script that does this as `<run>/scoring/build_criteria.py`, so the step can be re-run and checked, and have it write `<run>/criteria.json` as `{criterion: {subject: value}}` with higher meaning better, and `<run>/ranking.json` as the contest's placing, best first. Subjects are the entry keys used in the coding subjects (the person's short name).
3. Criterion families, by prefix:
   - `S:` each entry-level score, averaged over the scorers; `S:expert_rank(inv)` is the scorers' rank inverted so higher is better.
   - `C:` occasion coverage from `occasion_fit` (days-weighted, unweighted, number of occasions fully covered), taking the best watch in the entry for each occasion.
   - `W:` watch-score aggregates per entry (the minimum and the sum of each Part 1 score; register gap, sportiest and dressiest).
   - `F:` objective spec features from the fact base (count of watches at 100 m or more, thickest case, count on bracelets, total complications, list price). Add each in both directions: `F:x` and `F:-x` (negated). `infer` never combines a feature with its own negation.
4. Write `<run>/criteria_log.md`: every criterion, its family, and whether it was defined before or after you saw the ranking. Criteria defined after seeing the ranking are hypothesis-generating, not confirmatory, and the page says so.
5. Run `teddy.py infer <run>/criteria.json <run>/ranking.json --run <run>`. It writes `<run>/infer.json` and the `infer` keys of `<run>/numbers.json`.
