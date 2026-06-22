"""
graph_engine.py  --  Stage 2: The Collision Engine

This is where I use graph theory to prevent conflicts. I build a graph where
classes are nodes and edges mean "these two classes can't happen at the same time".
Then I use Welsh-Powell graph coloring to assign time slots.
"""

from collections import defaultdict
from common import (DAYS, TIME_SLOTS, get_class_blocks, is_professor_free,
                    does_class_fit_in_day, convert_slot_to_time)


def build_conflict_graph(all_classes, student_groups):
    """
    Builds the conflict graph.
    Two classes are connected if they share a professor OR share a student group.
    """
    conflict_graph = defaultdict(set)
    
    # Make sure every class is a node (even with no conflicts)
    class_ids = [c["class_id"] for c in all_classes]
    for class_id in class_ids:
        conflict_graph[class_id]  # This creates the node

    professor_for_class = {c["class_id"]: c["professor"] for c in all_classes}

    # Professor conflicts: same professor can't teach two classes at once
    for i in range(len(all_classes)):
        for j in range(i + 1, len(all_classes)):
            class_a = all_classes[i]["class_id"]
            class_b = all_classes[j]["class_id"]
            if professor_for_class[class_a] == professor_for_class[class_b]:
                conflict_graph[class_a].add(class_b)
                conflict_graph[class_b].add(class_a)

    # Student group conflicts: students in same group can't be in two classes at once
    for group in student_groups.values():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                class_a, class_b = group[i], group[j]
                conflict_graph[class_a].add(class_b)
                conflict_graph[class_b].add(class_a)

    return conflict_graph


def do_slots_overlap(start_a, duration_a, start_b, duration_b):
    """
    Checks if two time blocks overlap.
    This is the standard interval overlap check.
    """
    return start_a < start_b + duration_b and start_b < start_a + duration_a


def assign_time_slots(conflict_graph, all_classes, all_professors, verbose=True):
    """
    Assigns time slots using Welsh-Powell graph coloring.
    Classes connected by an edge get different time slots.
    """
    class_lookup = {c["class_id"]: c for c in all_classes}
    professor_lookup = {p["prof_id"]: p for p in all_professors}

    # Welsh-Powell: sort by degree (most conflicts first)
    # This is a common heuristic for graph coloring
    sorted_classes = sorted(conflict_graph.keys(), 
                            key=lambda c: len(conflict_graph[c]), 
                            reverse=True)

    slot_assignment = {}
    unassignable = []

    for class_id in sorted_classes:
        class_info = class_lookup[class_id]
        professor_info = professor_lookup.get(class_info["professor"], {})
        class_duration = class_info["duration"]
        chosen_slot = None

        # Try every day and time slot
        for day in DAYS:
            for start_slot in range(len(TIME_SLOTS)):
                # Check if class fits in the day
                if not does_class_fit_in_day(start_slot, class_duration):
                    continue
                
                # Check professor availability
                if not is_professor_free(professor_info, day, start_slot, class_duration):
                    continue
                
                # Check no conflicts with already scheduled neighbors
                has_conflict = False
                for neighbor in conflict_graph[class_id]:
                    if neighbor in slot_assignment:
                        neighbor_slot = slot_assignment[neighbor]
                        # If same day and overlapping times -> conflict
                        if neighbor_slot["day"] == day and do_slots_overlap(
                                start_slot, class_duration, 
                                neighbor_slot["start_slot"], 
                                class_lookup[neighbor]["duration"]):
                            has_conflict = True
                            break
                
                if has_conflict:
                    continue
                
                # Found a valid slot!
                chosen_slot = {
                    "day": day, 
                    "start_slot": start_slot,
                    "start_time": convert_slot_to_time(start_slot)
                }
                break
            if chosen_slot:
                break

        if chosen_slot:
            slot_assignment[class_id] = chosen_slot
        else:
            unassignable.append(class_id)

    # Print results
    if verbose:
        print("\nTime Slot Assignments (Stage 2)")
        for class_id, slot in slot_assignment.items():
            print(f"  {class_id:10s} -> {slot['day']} {slot['start_time']}")
        if unassignable:
            print("  Could not assign a conflict-free time slot to:",
                  ", ".join(unassignable))

    return slot_assignment, unassignable