# The Campus Puzzle — University Timetable Scheduler
**M603 Advanced Algorithms | Gisma University of Applied Sciences**

A four-stage scheduling pipeline for a real two-campus university (Berlin + Potsdam). It fits every class into a valid slot and room — and when it can't, it tells you exactly why.

**GitHub:** `git@github.com:Arun-Singh-Chauhan-09/m603-algo-project-campus-puzzle.git`

---

## Repository Layout

```
campus_scheduler/
├── data/
│   └── constraints.json    ← all inputs: rooms, professors, classes, student groups
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

## Customising the Data (No Code Required)

Everything lives in `data/constraints.json`. You can test different scenarios just by editing that file — no Python knowledge needed.

### Adding a class

```json
{
  "class_id": "M212",
  "students": 28,
  "professor": "Alexander",
  "program": "Master",
  "duration": 3
}
```

- `program`: `"Master"` → Potsdam rooms, `"Bachelor"` → Berlin rooms
- `professor`: must match a name in `freelancers_availability` or `internal_faculty`
- `duration`: hours (3, 4, 5, or 6)

### Adding or updating a professor

```json
{ "freelancer": "Dr. Smith", "availability": "Mondays 9:00-12:00, Wednesdays 14:00-17:00" }
```

| Availability text | Parsed as |
|---|---|
| `"Full availability"` | Mon–Fri 09:00–17:00 |
| `"Mondays 9:00-12:00"` | Mon: 09:00–12:00 |
| `"Tuesdays, Thursdays 14:00-17:00"` | Tue + Thu: 14:00–17:00 |

### Blocking a Potsdam room (UE)

```json
{
  "room": "11", "capacity": 30,
  "allocation": { "monday": "UE", "tuesday": "UE", "friday": "Gisma" }
}
```

Any day set to `"UE"` is blocked. `"Gisma"` means available.

### Managing student groups

```json
{
  "Master_Group_1": ["M501", "M502", "M503"],
  "Bachelor_Group_1": ["B124", "B125", "B126"]
}
```

Classes in the same group cannot overlap — students can't be in two places at once.

---

## The Four Stages

### Stage 1 — Greedy Baseline (`greedy_solver.py`)

Sort classes largest-first by enrolment, then drop each into the first valid `(day, time, room)` slot. Bigger classes go first because they're the hardest to fit — leaving them to last usually means they don't fit anywhere. Fast and decent, but short-sighted: placing a class now might block something better later.

**Complexity:** O(C · D · B · R)

---

### Stage 2 — Graph Coloring (`graph_engine.py`)

Build a conflict graph: one node per class, one edge between any two classes sharing a professor or student group. Apply **Welsh–Powell** coloring (most-conflicted nodes first) to assign time slots.

This is the key upgrade over Stage 1 — graph coloring reasons about *all* conflicts at once, so two connected classes can never land in the same slot by construction, not by luck.

**Complexity:** O(V² + E)

| | Stage 1 Greedy | Stage 2 Graph Coloring |
|---|---|---|
| Professor clashes | Possible | Zero |
| Student-group clashes | Possible | Zero |

---

### Stage 3 — Dynamic Programming (`optimizer.py`)

Time slots are fixed. Now assign rooms while minimising wasted seats. Brute-forcing all permutations is k! — hopeless even for small groups. Bitmask DP solves it by memoising on `(class_index, rooms_used_mask)`:

```
dp(i, mask) = min { waste(class_i, room_j) + dp(i+1, mask | 1<<j) }   for each free room j
            = PENALTY + dp(i+1, mask)                                   if nothing fits
```

Collapses k! orderings into at most k · 2^m states — much more manageable.

**Complexity:** O(k · 2^m) per overlapping group

---

### Stage 4 — Backtracking (`backtracker.py`)

Anything still unplaced goes into a recursive backtracking search. Stage 4 re-checks every hard constraint independently — it doesn't trust earlier stages — so the final output is always correct.

Pruning keeps it fast:
- Invalid triples cut *before* recursion, not after
- Hardest-to-place classes tried first (fail-fast)
- Smallest viable rooms tried first, saving large rooms for large classes
- Node budget of 200,000 caps runtime; returns the best partial solution if hit

---

## Conflict Report

```
Scheduled   B127   Mon 09:00  BER-D208   Perfect Fit
Scheduled   M501   Tue 10:00  POT-R201   Wasted 5 seats
Scheduled   M502   Wed 09:00  POT-R105   Perfect Fit
Unscheduled NLP630 N/A        N/A

Summary: scheduled 9/10, unscheduled 1 (10.0% need manual intervention)
```

**Why NLP630?** Professor Kaveh is only free Tue 15:00–18:00 and Wed 14:00–17:00. Both windows are already occupied by the MSc_AI group's other required classes. There's no valid slot — the system surfaces it rather than hiding it.

---

## Manual Fix Log

When a class can't be placed automatically, a manager can usually resolve it with one of these:

| Problem | Fix |
|---|---|
| Professor availability too narrow | Ask for one extra time window |
| Student group clashes in every slot | Split the group into two sub-groups for one module |
| All suitable rooms taken | Move a lower-priority class to free up the slot |
| Room slightly too small | Approve a temporary capacity override |
| Potsdam UE-block on all available days | Request an exception, or deliver remotely |

---

## Complexity Summary

| Stage | Algorithm | Time Complexity |
|---|---|---|
| 1 | Greedy — largest first | O(C · D · B · R) |
| 2 | Welsh–Powell Graph Coloring | O(V² + E) |
| 3 | Bitmask DP | O(k · 2^m) per overlapping group |
| 4 | Backtracking with pruning | O(b^d), heavily pruned |

C = classes, D = days, B = blocks/day, R = rooms · V = conflict-graph nodes, E = edges · k = classes per group, m = rooms available · b = branching factor, d = depth

---

## References

- Coffman, E.G., Garey, M.R. and Johnson, D.S. (1984). *Approximation Algorithms for Bin Packing.* PWS Publishing.
- Welsh, D.J.A. and Powell, M.B. (1967). An upper bound for the chromatic number of a graph. *The Computer Journal*, 10(1), pp. 85–86.
- Werra, D. de (1985). An introduction to timetabling. *European Journal of Operational Research*, 19(2), pp. 151–162.
- Cormen, T.H. et al. (2022). *Introduction to Algorithms.* 4th edn. MIT Press.
