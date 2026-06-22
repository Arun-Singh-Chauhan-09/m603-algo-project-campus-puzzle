# The Campus Puzzle — University Timetable Scheduler
**M603 Advanced Algorithms | Gisma University of Applied Sciences**

A four-stage scheduling pipeline for a real two-campus university (Berlin + Potsdam). It tries hard to fit every class into a valid slot and room — and when it can't, it tells you exactly why.

---

## Repository Layout

```
campus_scheduler/
├── data/
│   └── constraints.json    ← rooms, professors, classes, student groups
├── src/
│   ├── common.py           ← shared time model & constraint checks
│   ├── greedy_solver.py    ← Stage 1
│   ├── graph_engine.py     ← Stage 2
│   ├── optimizer.py        ← Stage 3
│   ├── backtracker.py      ← Stage 4
│   └── main.py             ← runs everything, prints the Conflict Report
└── requirements.txt        ← none (Python 3.10+ standard library only)
```

---

## How to Run

```bash
git clone git@github.com:Arun-Singh-Chauhan-09/m603-algo-project-campus-puzzle.git
cd m603-algo-project-campus-puzzle
python src/main.py
```

No installs needed. The script finds `data/constraints.json` automatically.

---

## The Four Stages

### Stage 1 — Greedy Baseline (`greedy_solver.py`)

Sort classes largest-first (by enrolment), then drop each one into the first valid `(day, time, room)` slot. Bigger classes go first because they're the hardest to place — if you leave them for last, they often don't fit anywhere. This gives us a working schedule fast, but it's short-sighted: placing a class now might block something else later.

**Complexity:** O(C · D · B · R) — scales easily to thousands of classes.

---

### Stage 2 — Graph Coloring (`graph_engine.py`)

Build a conflict graph: one node per class, one edge between any two classes that share a professor or a student group. Then colour it with **Welsh–Powell** (most-connected nodes first), where each "colour" is a concrete `(day, time)` slot checked against professor availability.

This is the key upgrade over Stage 1. Graph colouring reasons about *all* conflicts at once, so two connected classes can never end up in the same slot — by construction, not by luck.

**Complexity:** O(V² + E) on the conflict graph.

| | Stage 1 Greedy | Stage 2 Graph Coloring |
|---|---|---|
| Professor clashes | Possible | Zero |
| Student-group clashes | Possible | Zero |

---

### Stage 3 — Dynamic Programming (`optimizer.py`)

Time slots are now fixed. Within each group of classes running simultaneously, we need to assign rooms while minimising wasted seats. Brute-forcing all room permutations is k! — hopeless for large groups. Instead, we use bitmask DP:

```
dp(i, mask) = min wasted seats to place classes i…k given rooms in `mask` are taken

dp(i, mask) = min { waste(class_i, room_j) + dp(i+1, mask | 1<<j) }   for each free room j
            = PENALTY + dp(i+1, mask)                                   if nothing fits
```

Many room assignments share the same `(i, mask)` sub-problem — memoising collapses the search from k! to at most k·2^m states. Much more manageable.

---

### Stage 4 — Backtracking (`backtracker.py`)

Anything still unplaced goes into a recursive backtracking search. Stage 4 re-checks every hard constraint independently (it doesn't trust earlier stages), so the final output is always correct regardless of what happened upstream.

Pruning keeps it fast:
- Invalid `(day, time, room)` triples are cut *before* recursion, not after
- Hardest-to-place classes go first (fail-fast)
- Smallest viable rooms are tried first, saving big rooms for big classes
- A node budget caps runtime; if hit, the best partial solution so far is returned

---

## Conflict Report

The final output looks like this:

```
Scheduled   B127   Mon 09:00  BER-D208   Perfect Fit
Scheduled   M501   Tue 10:00  BER-D210   Wasted 5 seats
Scheduled   M502   Wed 09:00  BER-D104   Perfect Fit
Unscheduled NLP630 N/A        N/A

Summary: scheduled 9/10, unscheduled 1 (10.0% need manual intervention)
```

**Why is NLP630 unscheduled?** Its professor (Kaveh) is only free Tue 15:00–18:00 and Wed 14:00–17:00. Both windows are already taken by the MSc_AI group's other required classes. There's no valid slot — the system surfaces it clearly rather than hiding it.

---

## Manual Fix Log

For the classes the algorithm can't place, a university manager can typically resolve them by:

- Asking the professor for one extra availability window
- Splitting a student group so fewer classes conflict
- Swapping two rooms to free up a suitable slot
- Requesting a UE-block exception for a Potsdam room

The system's job is to shrink this manual workload to a small, clearly-labelled list.

---

## Complexity Summary

| Stage | Algorithm | Time Complexity |
|---|---|---|
| 1 | Greedy (largest-first) | O(C · D · B · R) |
| 2 | Welsh–Powell Graph Coloring | O(V² + E) |
| 3 | Bitmask DP | O(k · 2^m) per overlapping group |
| 4 | Backtracking with pruning | O(b^d), pruned heavily |

---

## References

- Coffman, E.G., Garey, M.R. and Johnson, D.S. (1984). *Approximation Algorithms for Bin Packing.* PWS Publishing.
- Werra, D. de (1985). An Introduction to Timetabling. *European Journal of Operational Research*, 19(2), pp. 151–162.
- Welsh, D.J.A. and Powell, M.B. (1967). An Upper Bound for the Chromatic Number of a Graph. *The Computer Journal*, 10(1), pp. 85–86.
- Cormen, T.H. et al. (2022). *Introduction to Algorithms.* 4th edn. MIT Press.
