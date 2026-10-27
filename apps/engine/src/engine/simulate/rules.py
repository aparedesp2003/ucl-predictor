"""2026/27 UEFA Champions League competition rules used by the simulator.

Sources (official UEFA):

- Regulations of the UEFA Champions League 2026/27 (in force 29 July 2026),
  https://documents.uefa.com/r/Regulations-of-the-UEFA-Champions-League-2026/27-Online
  - Art. 18.01 (equality of points, league phase): (1) goal difference, (2) goals scored,
    (3) away goals scored, (4) wins, (5) away wins, (6) points obtained collectively by league
    phase opponents, (7) their collective goal difference, (8) their collective goals scored,
    (9) disciplinary points, (10) club coefficient.
  - Art. 19.01-19.03: positions 1-8 enter the round of 16; positions 9-24 play the knockout phase
    play-offs, with seeded pairs 9/10, 11/12, 13/14, 15/16 drawn against unseeded pairs 23/24,
    21/22, 19/20, 17/18 respectively; seeded pairs 1/2, 3/4, 5/6, 7/8 are each drawn into one of
    two round-of-16 positions. Seeded clubs play the return leg at home.
  - Art. 19.04: teams ranked 1-4 host the quarter-final return leg and teams ranked 1-2 the
    semi-final return leg; a team that eliminates a seeded team takes over its bracket position;
    rankings are not recalculated after each round.
  - Art. 20.01/20.03: knockout ties (except the final) over two legs, decided on aggregate goals.
  - Art. 21.01-21.03: level on aggregate -> two 15-minute periods of extra time at the end of the
    second leg, then a penalty shoot-out. There is no away-goals rule.
  - Art. 22.01: the final is one match at a neutral, predetermined stadium, with extra time and
    penalties if needed.
- Bracket: Annex B of the 2026/27 regulations publishes it only as an image. The layout below is
  taken from UEFA's "Draw procedure - Knockout phase play-offs" for 2025/26 (30 January 2026,
  https://editorial.uefa.com/resources/02a1-1fcdca3890d3-4e303c87e501-1000/ucl_ko_po_draw_procedure.pdf),
  whose quoted Art. 19.02 text matches the 2026/27 edition. It is carried over as the 2026/27
  bracket (decision recorded in the week 3 plan).

Approximations:

- Tiebreakers (9) disciplinary points and (10) club coefficient are replaced by a uniform random
  order (no card or coefficient data). Criteria (1)-(8) are computed exactly from the simulated
  results; UEFA applies them as one lexicographic order to all tied teams (no head-to-head).
- Extra time is played at the second-leg venue at 1/3 of the 90-minute scoring rates, with
  independent Poisson goals; shoot-outs are 50/50.
- Ratings are frozen for the whole run (no updates between simulated rounds).
"""

N_TEAMS = 36
N_TOP = 8  # direct to the round of 16
N_PLAYOFF = 24  # positions 9..24 play the knockout phase play-offs

# One side of the bracket (the "silver" side; the "blue" side is the mirror image). Each entry is
# (seeded play-off pair, unseeded play-off pair, round-of-16 seeded pair), as 1-based positions.
# Round-of-16 ties 0+1 meet in one quarter-final and 2+3 in the other; the two quarter-final
# winners meet in that side's semi-final, and the two sides meet in the final.
BRACKET_SIDE = (
    ((11, 12), (21, 22), (5, 6)),
    ((13, 14), (19, 20), (3, 4)),
    ((9, 10), (23, 24), (7, 8)),
    ((15, 16), (17, 18), (1, 2)),
)
# Quarter-finals as (first-leg host tie, second-leg host tie), indices into BRACKET_SIDE:
# the winners from the 3/4 and 1/2 slots host the return leg.
QUARTER_FINALS = ((0, 1), (2, 3))
# Semi-final on each side: winner of QUARTER_FINALS[0] hosts the first leg, QUARTER_FINALS[1]
# (the 1/2 slot) the return.

PAIRS = tuple((p, p + 1) for p in range(1, N_PLAYOFF + 1, 2))  # (1, 2), (3, 4), ..., (23, 24)

EXTRA_TIME_FRACTION = 1 / 3
