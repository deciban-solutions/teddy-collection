# Blind scoring rubric: six two-watch collections

## The task you are scoring against
Each of six people built a collection of exactly **two watches**. The brief: "Think about a scenario where you could only have two watches in your actual collection. And that has to serve you every single day. There's no price limitations." The pairs are anonymised (PAIR-U … PAIR-Z, watches -1 and -2). You do not know who built them or how anyone ranked them. Do not try to find out: do not search the web, do not open any file other than this rubric, your pairs.md, and the output you write. Judge only from the specs given and your own knowledge of these watches.

## The default wearer (use this for every pair)
A watch enthusiast with a medium wrist (about 17 cm / 6.75 in), an office job, travelling internationally a few times a year. Days per year by occasion:

| Occasion key | Occasion | Days/yr |
|---|---|---|
| black_tie | Black tie / formal evening | 2 |
| suit | Suit, business formal | 20 |
| biz_casual | Business casual office | 150 |
| dinner | Dinner, night out | 40 |
| weekend | Weekend casual | 100 |
| active | Sport, outdoors, yard work | 30 |
| swim | Swimming, beach | 10 |
| scuba | Scuba diving | 0 |
| travel | Travel across time zones | 12 |

## Part 1: each watch (score all 12)
Integer scores 1–5 (5 = best) unless stated.
- `register`: 1 = pure tool, 2 = sport, 3 = versatile sport-dress middle, 4 = dressy, 5 = formal dress (thin, plain, leather/precious metal).
- `robustness`: what it survives: water resistance vs activities (30 m splash; 50 m casual swimming; 100 m snorkelling/surfing; 200 m scuba), screw-down crown, lume, legibility, shock and scratch tolerance. A dress watch that must stay dry scores low.
- `wearability`: all-day comfort for the default wrist: diameter, thickness (fits under a cuff?), lug-to-lug, weight, band comfort and adjustability.
- `useful_complications`: how much the complications serve this wearer's actual life (date, GMT for travel, chronograph for timing). Ornamental or rarely used complications score lower; none at all is a 3.
- `practicality`: daily ownership friction: accuracy, power reserve (survives a weekend off the wrist?), automatic vs hand-wound, need to reset calendars, delicacy, servicing cost. 5 = grab-and-go.
- `horological_merit`: movement design and finishing, in-house engineering, innovation, dial craft: what an enthusiast admires.
- `design_integrity`: purposeful design with historical roots, timelessness, and neutrality enough to go anywhere.
- `value`: what the money buys in quality, finishing and engineering per dollar.
- `occasion_fit`: for each occasion key above, 2 = fits, 1 = passable but draws notice or is a compromise, 0 = wrong for the setting. Judge this specific watch on its own band, not the watch type in general.

## Part 2: each pair (score all 6)
### Expert collection criteria (1–5)
- `differentiation`: do the two differ in register, size, dial colour, complications and band, so there is no redundancy?
- `coherence_expert`: can each watch's place be explained by one collection logic, and do they share values (era, design philosophy, mechanical interest) while looking different?
- `anchor_strength`: how well the better daily watch of the two covers the bulk of wear-days alone.
- `tension_point`: is there one deliberate, productive contrast (origin, movement type, era, register)?
- `gap_test`: remove either watch; does a real gap open that the other can't serve? 5 = each watch is indispensable.
- `wear_balance`: does each watch own a distinct kind of day, so both get worn and the morning choice is easy?

### Store-staff criteria (1–5)
These come from what a panel of three watch-boutique staff (people who serve collectors daily) said about what they valued. Score each pair on each, as such a panel would read them:
- `makes_sense_together`: "the two of them together make sense" as one person's whole collection.
- `beaten_path`: how close the pair is to what typical collectors coming into a boutique would actually assemble as a two-watch collection (5 = squarely conventional; 1 = odd, off the beaten path).
- `daily_driver`: whether the pair contains "a nice daily driver": one watch you can wear every day, everywhere, without thought.
- `sensible_spice`: whether the pair has "a little bit more spice": some energy, fun, colour or sporty character, while staying sensible and wearable (1 = flat or merely dressy; 5 = clear spice that still fits an everyday life).
- `everyday_livability`: how well the pair as a whole lets you "live with these two watches every single day".

### Holistic
- `expert_rank`: rank the six pairs 1 (best) to 6 for this brief and this wearer, using your own expert judgment (no ties).
- `rationale`: 2–4 sentences per pair.

## Output
Write ONE JSON file to the output path you are given:
```json
{
  "watches": {"PAIR-U-1": {"register":3,"robustness":4,"wearability":4,"useful_complications":3,"practicality":5,"horological_merit":4,"design_integrity":4,"value":3,
                           "occasion_fit":{"black_tie":1,"suit":2,"biz_casual":2,"dinner":2,"weekend":2,"active":1,"swim":1,"scuba":0,"travel":1}}, "...": {}},
  "pairs": {"PAIR-U": {"differentiation":3,"coherence_expert":4,"anchor_strength":4,"tension_point":3,"gap_test":3,"wear_balance":3,
                        "makes_sense_together":4,"beaten_path":3,"daily_driver":5,"sensible_spice":2,"everyday_livability":4,
                        "expert_rank":2,"rationale":"..."}, "...": {}}
}
```
All 12 watches and all 6 pairs must be present; every score an integer in range. Validate the file with Python (json.load, key and range checks) before you finish. Score Part 1 for all watches before Part 2. Score the criteria before you make the holistic ranking.
