# How Performance Translates Between Leagues
## A briefing for scouts and soccer operations

### What this is

A rating of league difficulty built from what actually happens to players who
change leagues. When a winger leaves USL Championship for MLS, his production
changes. Measure that change across every player who made a similar move, correct
for age and playing time, and you get a conversion rate between the two leagues.
Do it across nine leagues and 1,871 moves and you get a strength scale.

No opinions, no eye test, no reputation. Just before-and-after numbers from
1,460 players who made real moves between 2018 and 2025.

### The scale (MLS = 1.00, higher = tougher league)

| league | strength | read it as |
|---|---|---|
| Premier League | 1.36 | hardest league measured |
| La Liga | 1.25 | |
| Serie A | 1.15 | |
| Ligue 1 | 1.12 | |
| Bundesliga | 1.11 | |
| MLS | 1.00 | the yardstick |
| USL Championship | 0.71 | |
| USL League One | 0.68 | nearly level with USLC |
| MLS NEXT Pro | 0.58 | biggest gap to MLS |

### How to use it

Divide origin strength by destination strength. That is the share of a player's
attacking production (xG + assists quality per 90) you should expect to survive
the move, all else equal.

- USL Championship starter moving to MLS: expect roughly **71%** of his numbers.
  A 0.40 xG+xA per 90 in USLC projects to about 0.28 in MLS.
- MLS NEXT Pro standout jumping straight to MLS: expect roughly **58%**. Big
  numbers in NEXT Pro shrink a lot; discount accordingly.
- MLS attacker sold to the Premier League: expect roughly **74%**.
- MLS veteran dropping to USL Championship: expect about **1.40x** his MLS rate.

### The number nobody talks about: players who just do not stick

Some moves fail so completely the player barely gets on the pitch. Those failures
never show up in per-90 stats, so we count them separately:

- **54%** of NEXT Pro players who reached MLS never got to 450 minutes there.
- **43%** of USL Championship players moving up to MLS did not stick either.
- Between European top flights the rate is much lower (10-25%).

Translation for scouting: the conversion rates above describe players who got a
real chance. The odds of getting that chance are a separate risk, and for the
American pyramid it is roughly a coin flip.

### Why you can trust it (and how far)

- **Tested on held-out players.** We hid half the movers, projected them using
  only their pre-move numbers, and checked the projections against reality.
  The projections beat random shuffling decisively (372 held-out moves,
  1-in-2000 chance of arising by luck) and cut projection error by 14% versus
  using raw unadjusted stats.
- **Age-corrected.** A 31-year-old declining in MLS is not evidence MLS is hard;
  a 21-year-old improving in Leeds is not evidence England is easy. Every move
  is adjusted for the normal aging curve, built from thousands of season-over-
  season comparisons of players who stayed in the same league.
- **Checked against an outside benchmark.** The ordering matches independent
  club-strength ratings (FiveThirtyEight SPI). Same order, no surprises.

**Where to be careful:** the American-pyramid numbers (MLS, USLC, USL1, NEXT Pro)
rest on 300-550 moves per league and are solid. The Europe-to-MLS numbers rest on
about 130 moves; the ordering is confident, but treat individual conversion rates
there as ranges, not decimals. And these are averages: a pressing league may suit
one player and bury another. This tool sets the baseline expectation; scouting
still decides who beats it.

### One-line takeaways

- USL Championship and League One are nearly the same difficulty. A dominant
  USL1 player is not a project; he is a USLC player without the label.
- The NEXT Pro to MLS jump is the most underestimated gap in the pyramid:
  production drops 42% for those who stick, and half do not stick.
- MLS sits below the Big-5 but the gap to Ligue 1 and the Bundesliga (about 11%)
  is smaller than most boards assume, and the data says it with confidence for
  England and Spain.
