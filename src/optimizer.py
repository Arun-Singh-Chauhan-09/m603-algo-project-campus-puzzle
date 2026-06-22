"""
optimizer.py  --  Stage 3: The Efficiency Engine (Dynamic Programming)

Now that we have time slots fixed, I need to assign rooms optimally.
I use DP with bitmask to minimize wasted seating capacity.
This is better than brute force because it reuses subproblem solutions.
"""

from functools import lru_cache
from common import can_class_use_room, sort_rooms_by_priority, convert_slot_to_time

# If a class can't be placed, this penalty makes the DP avoid it if possible
DROP_PENALTY = 10_000


def find_overlapping_groups(all_classes, slot_assignment):
    """
    Groups classes that overlap in time on the same day.
    Classes in the same group compete for rooms.
    I use union-find to merge overlapping classes transitively.
    """
    class_lookup = {c["class_id"]: c for c in all_classes}
    scheduled_classes = list(slot_assignment.keys())

    # Union-Find data structure
    parent = {c: c for c in scheduled_classes}

    def find_root(class_id):
        # Path compression for efficiency
        while parent[class_id] != class_id:
            parent[class_id] = parent[parent[class_id]]
            class_id = parent[class_id]
        return class_id

    def merge_groups(class_a, class_b):
        parent[find_root(class_a)] = find_root(class_b)

    # Check every pair of classes
    for i in range(len(scheduled_classes)):
        for j in range(i + 1, len(scheduled_classes)):
            class_a = scheduled_classes[i]
            class_b = scheduled_classes[j]
            slot_a = slot_assignment[class_a]
            slot_b = slot_assignment[class_b]
            
            # Only care about classes on the same day
            if slot_a["day"] != slot_b["day"]:
                continue
            
            start_a = slot_a["start_slot"]
            duration_a = class_lookup[class_a]["duration"]
            start_b = slot_b["start_slot"]
            duration_b = class_lookup[class_b]["duration"]
            
            # If they overlap, they're in the same group
            if start_a < start_b + duration_b and start_b < start_a + duration_a:
                merge_groups(class_a, class_b)

    # Group by root
    groups = {}
    for class_id in scheduled_classes:
        root = find_root(class_id)
        groups.setdefault(root, []).append(class_id)
    
    return list(groups.values())


def solve_one_group(class_id_group, all_classes, all_rooms):
    """
    Solves room assignment for one group using DP.
    State: (class_index, used_rooms_mask) where mask is bits of used rooms.
    This is a classic DP over subsets.
    """
    class_lookup = {c["class_id"]: c for c in all_classes}
    group_classes = [class_lookup[c] for c in class_id_group]

    # All classes in the group are on the same day
    target_day = group_classes[0]["_target_day"]

    # Find all rooms that could work for ANY class in this group
    candidate_rooms = []
    for room in sorted(all_rooms, key=sort_rooms_by_priority):
        works_for_any = any(
            can_class_use_room(room, class_info, target_day, 
                               class_info["_target_start_slot"], 
                               class_info["duration"])
            for class_info in group_classes
        )
        if works_for_any:
            candidate_rooms.append(room)

    num_rooms = len(candidate_rooms)
    num_classes = len(group_classes)

    def calculate_waste(class_info, room_info):
        """Calculate wasted seats if this class goes in this room."""
        if can_class_use_room(room_info, class_info, target_day, 
                              class_info["_target_start_slot"], 
                              class_info["duration"]):
            return room_info["capacity"] - class_info["students"]
        return None  # Not feasible

    @lru_cache(maxsize=None)
    def dp_solve(class_index, used_mask):
        """
        DP function.
        Returns: (minimum_waste, placement_choices)
        """
        if class_index == num_classes:
            return (0, ())  # All classes placed
        
        best = None
        current_class = group_classes[class_index]
        
        # Try assigning to each free room
        for room_idx in range(num_rooms):
            if used_mask & (1 << room_idx):
                continue  # Room already taken
            
            waste = calculate_waste(current_class, candidate_rooms[room_idx])
            if waste is None:
                continue  # Room not feasible for this class
            
            sub_cost, sub_choice = dp_solve(class_index + 1, used_mask | (1 << room_idx))
            total_cost = waste + sub_cost
            
            if best is None or total_cost < best[0]:
                best = (total_cost, (("place", room_idx),) + sub_choice)
        
        # Option: leave this class unplaced (if no room works)
        sub_cost, sub_choice = dp_solve(class_index + 1, used_mask)
        total_cost = DROP_PENALTY + sub_cost
        
        if best is None or total_cost < best[0]:
            best = (total_cost, (("drop", -1),) + sub_choice)
        
        return best

    _, placement_choices = dp_solve(0, 0)

    # Build the results
    scheduled = []
    unplaced = []
    
    for class_info, (action, room_idx) in zip(group_classes, placement_choices):
        if action == "place":
            chosen_room = candidate_rooms[room_idx]
            scheduled.append({
                "class_id": class_info["class_id"],
                "professor": class_info["professor"],
                "day": class_info["_target_day"],
                "start_time": convert_slot_to_time(class_info["_target_start_slot"]),
                "duration_hours": class_info["duration"],
                "room_id": chosen_room["room_id"],
                "wasted_capacity": chosen_room["capacity"] - class_info["students"],
            })
        else:
            unplaced.append(class_info["class_id"])

    dp_solve.cache_clear()
    return scheduled, unplaced


def assign_rooms_with_dp(all_classes, all_rooms, slot_assignment, verbose=True):
    """
    Main entry point for Stage 3.
    Assigns rooms to all classes that have time slots.
    """
    class_lookup = {c["class_id"]: c for c in all_classes}

    # Annotate classes with their fixed time slots
    for class_id, slot_info in slot_assignment.items():
        class_lookup[class_id]["_target_day"] = slot_info["day"]
        class_lookup[class_id]["_target_start_slot"] = slot_info["start_slot"]

    # Find overlapping groups
    overlapping_groups = find_overlapping_groups(all_classes, slot_assignment)

    # Solve each group independently
    all_scheduled = []
    all_unplaced = []
    
    for group in overlapping_groups:
        scheduled, unplaced = solve_one_group(group, all_classes, all_rooms)
        all_scheduled.extend(scheduled)
        all_unplaced.extend(unplaced)

    # Print results
    if verbose:
        print("\nOptimized Room Allocation (Stage 3 - DP)")
        for placement in sorted(all_scheduled, key=lambda p: (p["day"], p["start_time"])):
            print(f"  {placement['class_id']:10s} {placement['day']} {placement['start_time']} "
                  f"-> {placement['room_id']:9s} (waste {placement['wasted_capacity']})")
        if all_unplaced:
            print("  No feasible room found for:", ", ".join(all_unplaced))

    return all_scheduled, all_unplaced