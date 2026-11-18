# Page specs: contest

A contest's type pages are `criteria-inference`, `taxonomy` and `wearers`, after the shared pages in `shared.md`. Their inputs are the blind scores and `infer` results from `scoring-rubric.md`.

Dataset fields this type uses: each appearance's `group` holds the entry it belongs to (for example "Brit's pair"), so the gallery shows each entry together; `rank` holds the entry's placing; `role` is `picked` for an entry's watches and `worn` for what a contestant wore on the day. The video's optional `criteria` lists the brief's stated criteria. Every watch the video names outside the entries (a comparison, a watch a contestant mentions) is always recorded, never only described: a `mentioned` appearance in `records.json` with its own watch record and a photo (a frame if the video shows it, else a credited photo), so it reaches the dataset, the gallery and the parent's watch index.

## `criteria-inference` (Criteria inference)

The template adds the commercial-context note. All sections come from your fragment.

- **Sections:**
  1. *The answer:* a `<div class="answer">`: which criterion the exact rules share as their first step, what breaks the remaining ties, and what the evidence cannot tell apart.
  2. *How sure is this?* The number of exact rules of each length (`infer.rules.1.count`, `infer.rules.2.count`, `infer.rules.3.count`) against the null baseline: among as many random criteria as the run's own set (`infer.null_n_criteria`, read from numbers, never typed), an exact one-step, two-step or three-step fit exists in `infer.null_rates.1`, `infer.null_rates.2`, `infer.null_rates.3` of trials. Say whether the rules agree on a first step, which random criteria would not do.
  3. *The judges' own words, coded:* a table of every evaluative remark in the reveal (quote, timestamp link, the entry and placing, the criterion it implies) and whether the scores agree with that reading (`y`, `p`, `n`).
  4. *Method:* fact base, blind scoring (three scorers, anonymised, shuffled, no web access), the criterion library (`infer.n_criteria` candidates over `infer.n_items` entries, by family), the rule search (rank correlation, exact lexicographic rules of up to three criteria, ties count as failures) and the null baseline.
  5. *Which single criteria track the result:* the top single criteria by τ (`infer.top_single.0.tau` with its key `infer.top_single.0.key`, and so on down the list).
  6. *Every rule that reproduces the exact order:* the minimal rules from `infer.json` (`rules.<length>.minimal`), written out in words, one per line.
  7. *Blind scorers and viewers rank differently:* the contest's placing beside the scorers' consensus order (from `S:expert_rank(inv)` in `criteria.json`, shown as an ordered list with no scores typed; cite its τ only if it appears in `infer.top_single`) and the viewers' favourites (`viewers.best.<subject>`).
  8. *Limits.*
- **Required numbers:** `infer.rules.<n>.count`, `infer.null_rates.<n>`, `infer.null_n_criteria`, `infer.n_criteria`, `infer.n_items`, `infer.top_single.<i>.tau`; κ and viewer counts from `shared.md` when cited.
- **Required caveats:**
  - The three blind scorers are instances of the same AI model; their agreement shows consistency, not independent confirmation.
  - A handful of entries can identify one or two criteria at most. The answer is one consistent explanation; the judges may have deliberated in ways no rule captures.
  - Criteria defined after seeing the ranking (from `criteria_log.md`) are hypothesis-generating, not confirmatory. Name them.
  - The judges saw the physical watches; the scorers saw only specs. Size on the wrist, finishing and presence may have mattered.
  - Prices are list or dealer figures with their dates, and only rough.

## `taxonomy` (Taxonomy)

The build adds, above your fragment, the checklist version, one sentence on what the checklist is for, and how far that version has been checked. Readers see this page as the **Buyer's checklist**: write "checklist" in its prose, not "taxonomy", and avoid the format's own terms (kind, evidence class, layer, paradigm, deterministic).

- **Sections:**
  1. *What this page is for:* one or two plain sentences: this is the checklist the analysis measures the watches against, and where the result is (the Scorecard for a review, the Criteria inference page for a contest).
  2. *The buyer it serves:* the checklist's stance in a sentence, said as one reasonable buyer's view, not the only one.
  3. *The checklist:* what to know about the wearer (facts about the buyer, not properties of any watch), what to check on each watch, and, where there is one, what to check across the pair or collection. One table for each, with these columns:
     - **Criterion**;
     - **What it means**, in a sentence;
     - **How strict**: must hold, more is better, or depends on evidence;
     - **Based on**: a rule or standard, published research, what practitioners agree on, or a matter of taste;
     - **Tested by**: a script, from the specs (name the rule in words), or judgement. When the criterion's check has `checks_only`, write "partly by a script: <what it checks>; the rest by judgement", never just "a script".
  4. *The occasion matrix* the scorers used, when the contest is about covering a life.
  5. *Combinations judged together:* where two things are fine alone but not together, such as two fine watches that make a redundant pair.
  6. *Teddy's principles:* his recurring principles, as what practitioners agree on, quoted with video and timestamp. The template adds the commercial-context note.
  7. *Where the items pull against each other.*
  8. *How this was built, and its limits:* compiled or provisional; whether this run branched it or drafted it, and why; the sources and what kind each is.
- **Required numbers:** none.
- **Required caveats:** a provisional taxonomy has not been compiled or ratified; sources that sell watches are named as such; a taxonomy written after seeing the result is not blind.

## `wearers` (Wearer profiles)

- **Sections:** one `card` per contestant: name, what they wore on the day (a frame photo from `img/`, its reference and confidence), what they said about it, and their stated criteria for their picks, quoted with timestamp links. Then *The contestants as wearer profiles:* a short table of what each one's criteria imply about the wearer they had in mind.
- **Required numbers:** none.
- **Required caveats:** the commercial-context note (the template adds it); a worn watch identified below `matched_to_specs` says so in its card.
