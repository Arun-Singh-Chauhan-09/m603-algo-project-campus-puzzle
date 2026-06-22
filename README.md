# The Campus Puzzle — University Timetable Scheduler

A best-effort semester scheduler that assigns classes to time slots and rooms
across two campuses (Berlin / Potsdam) while respecting professor availability,
room capacity, blocked (UE) rooms, variable class durations, and shared-student
conflicts. When the problem is over-constrained, the system produces a partial
schedule and a **Conflict Report** identifying the classes that need manual
intervention.

## Time model

The week is a grid of `(day, block)`. Days are Mon–Sat; blocks are 1-hour slots
from 08:00 to 19:00 (12 blocks). A class of duration *D* hours occupies *D*
consecutive blocks in one room on one day. Variable durations (3/4/5/6 h) are a
first-class part of the model.

## Inputs (`/data/constraints.json`)

- **rooms** — Berlin (Donnauer) and Potsdam rooms with capacity. Potsdam rooms
  carry a `ue_blocked` map of days that are UE-blocked. Room data is taken
  directly from `Tentative_Schedule_Data.xlsx`.
- **professors** — each with an `availability` list of `{day, start, end}`
  windows, derived from the freelancer/internal availability notes.
- **classes** — id, students, professor, program (Bachelor/Master), duration.
- **student_groups** — which classes each group attends (drives the conflict graph).

> Note: `classes` and `student_groups` are currently realistic **placeholder**
> data so the pipeline runs end-to-end. They are to be replaced with the official
> module list and group mapping when provided. Room and availability data are real.

## The four stages

### Stage 1 — Greedy baseline (`greedy_solver.py`)
We sort classes hardest-first by **number of students**, because larger classes
are the hardest to fit, so placing them first reduces the chance they get
stranded. Each class is dropped into the first `(day, start, room)` that satisfies
every hard constraint and clashes with nothing already placed.
*Complexity:* O(C · D · B · R) per pass — linear in classes × days × blocks ×
rooms — which scales comfortably to a few thousand classes.

### Stage 2 — Graph coloring (`graph_engine.py`)
We build a **conflict graph**: a node per class, an edge whenever two classes
share a professor **or** a student group. We then colour the graph with
**Welsh–Powell** (order nodes by descending degree, assign each the first
non-conflicting time slot), where a "colour" is a concrete `(day, start)` placement
checked for **span overlap** against already-coloured neighbours. Professor
availability restricts the legal slots.
*Why:* Welsh–Powell runs in O(V² ) on the conflict graph and tends to use few
colours on sparse graphs, which is what timetable conflict graphs usually are.
*Greedy vs. coloring:* the greedy baseline can place a class into a slot that
later forces a downstream conflict; coloring reasons about all pairwise conflicts
up front, so it prevents same-time clashes between connected classes by construction.

### Stage 3 — Dynamic Programming room allocation (`optimizer.py`)
With time slots fixed, classes whose spans overlap on the same day compete for
rooms. Within each overlapping group we minimise **total wasted capacity** with a
DP over a bitmask of used rooms.

- **State:** `dp(i, mask)` = minimum extra waste to place classes `i..k-1` given
  that the rooms in `mask` are already used.
- **Recurrence:**
  `dp(i, mask) = min over feasible free room j of [ waste(c_i, r_j) + dp(i+1, mask | 1<<j) ]`,
  with the option `dp(i, mask) = PENALTY + dp(i+1, mask)` when no room fits
  (the class is dropped, at a large penalty). Base case `dp(k, mask) = 0`.
- **Why it avoids brute force:** there are up to `k!` class→room orderings, but
  many share the same `(i, mask)` subproblem. Memoising on `(i, mask)` collapses
  them into at most `k · 2^m` states, each solved once.

### Stage 4 — Backtracking & best effort (`backtracker.py`)
Classes that Stage 2 or 3 could not place are fed to a recursive backtracking
search over `(day, start, room)`. Stage 4 **independently re-checks every hard
constraint** (professor availability and clash, student-group clash, room campus,
UE block, capacity, room clash, end-of-day), so its output does not depend on the
earlier stages being correct.

**Pruning strategy:**
1. *Constraint pruning* — invalid `(day, start, room)` placements are rejected
   before expansion, so dead branches are never explored.
2. *Fail-first ordering* — leftover classes are tried in order of fewest feasible
   placements, hitting dead ends early and keeping the tree small.
3. *Tight-room ordering* — rooms are tried smallest-feasible-first, keeping large
   rooms free for large classes.
4. *Node budget* — a cap on expansions guarantees termination; if hit, the search
   returns the minimum-conflict state found so far (best effort).

## The Conflict Report

`main.py` prints lines in the required format, e.g.:

```
Scheduled CS101  Mon 12:00 BER-D208  Wasted 1 seats
Scheduled WEB210 Mon 14:00 BER-D104  Perfect Fit
Unscheduled NLP630   N/A   N/A
```

In the current run, **NLP630** cannot be scheduled: its professor (Kaveh) is only
available Tue 15:00–18:00 and Wed 14:00–17:00, and both windows collide with its
MSc_AI groupmates (ML502 on Tue, DS601 on Wed). This is a genuine, unavoidable
conflict — the kind the brief asks us to flag rather than hide.

## The Manual Fix Log

For the leftover ~1–6%, a human manager uses the report to resolve conflicts that
software cannot, for example by: asking the affected professor for one extra
availability window; splitting a large student group; moving a groupmate's class
to free a slot; or approving a temporarily over-capacity room. The software's job
is to shrink the manual workload to a tiny, clearly-identified set.

## Running

```bash
cd src
python3 main.py
```

No external libraries are required (Python 3.10+).

## Repository layout

```
data/constraints.json   inputs (rooms + availability real; classes/groups placeholder)
src/common.py           time model + shared constraint checks
src/greedy_solver.py    Stage 1
src/graph_engine.py     Stage 2
src/optimizer.py        Stage 3 (DP)
src/backtracker.py      Stage 4
src/main.py             orchestration + Conflict Report
```
