"""
backtracker.py  --  Stage 4: Backtracking & "Best Effort"

This is my last resort. If earlier stages couldn't place some classes,
I use recursive backtracking to try different combinations.
It's like trying to solve a puzzle by trial and error, but with smart pruning.
"""

from common import (DAYS, TIME_SLOTS, get_class_blocks, can_class_use_room,
                    is_professor_free, convert_slot_to_time, does_class_fit_in_day,
                    convert_time_to_slot)

# Safety limit so the program doesn't run forever
MAX_ATTEMPTS = 200_000


def build_room_occupancy(schedule):
    """Builds sets of occupied rooms and professors from an existing schedule."""
    occupied_rooms = set()
    occupied_professors = set()
    
    for entry in schedule:
        start_slot = TIME_SLOTS.index(entry["start_time"])
        for block in get_class_blocks(start_slot, entry["duration_hours"]):
            occupied_rooms.add((entry["day"], entry["room_id"], block))
            occupied_professors.add((entry["day"], entry["professor"], block))
    
    return occupied_rooms, occupied_professors


def build_group_membership(student_groups):
    """
    Creates a mapping from class_id to the groups it belongs to.
    This helps me quickly check if two classes share students.
    """
    membership = {}
    for group_name, class_ids in student_groups.items():
        for class_id in class_ids:
            membership.setdefault(class_id, set()).add(group_name)
    return membership


def find_all_possible_spots(class_info, all_rooms, professor_lookup):
    """
    Finds all possible (day, start, room) combos for a single class.
    I check professor availability and room constraints.
    """
    professor_info = professor_lookup.get(class_info["professor"], {})
    duration = class_info["duration"]
    possible = []
    
    for day in DAYS:
        for start_slot in range(len(TIME_SLOTS)):
            if not is_professor_free(professor_info, day, start_slot, duration):
                continue
            for room in all_rooms:
                if can_class_use_room(room, class_info, day, start_slot, duration):
                    possible.append((day, start_slot, room["room_id"]))
    
    return possible


def debug_why_impossible(class_id, class_info, all_rooms, professor_lookup):
    """Helper to figure out WHY a class can't be placed."""
    professor_info = professor_lookup.get(class_info["professor"], {})
    duration = class_info["duration"]
    
    print(f"\n  🔍 DEBUGGING {class_id}:")
    print(f"     Students: {class_info['students']}, Duration: {duration}h, Program: {class_info['program']}")
    print(f"     Professor: {class_info['professor']}")
    
    available = professor_info.get("availability", [])
    if not available:
        print(f"     ⚠️  Professor {class_info['professor']} has NO availability defined")
    else:
        print(f"     Professor availability windows:")
        for window in available:
            print(f"       - {window['day']}: {window['start']} - {window['end']}")
    
    # Check professor availability
    print(f"\n     Checking professor availability:")
    free_slots = []
    for day in DAYS:
        for start_slot in range(len(TIME_SLOTS)):
            if is_professor_free(professor_info, day, start_slot, duration):
                free_slots.append((day, start_slot))
    
    if not free_slots:
        print(f"     ❌ Professor is NOT available for {duration} hours on ANY day!")
        for day in DAYS:
            for window in available:
                if window["day"] == day:
                    window_start = convert_time_to_slot(window["start"])
                    window_end = convert_time_to_slot(window["end"])
                    available_hours = window_end - window_start
                    print(f"       - {day}: {window['start']} - {window['end']} ({available_hours}h available, need {duration}h)")
    else:
        print(f"     ✅ Professor available at {len(free_slots)} time slots")
    
    # Check rooms
    print(f"\n     Checking room feasibility:")
    total_possible = 0
    for day, start_slot in free_slots:
        for room in all_rooms:
            if can_class_use_room(room, class_info, day, start_slot, duration):
                total_possible += 1
                if total_possible <= 3:
                    print(f"       ✅ {day} {TIME_SLOTS[start_slot]} - {room['room_id']} (cap: {room['capacity']})")
            else:
                if total_possible <= 3:
                    if room["campus"] == "Potsdam" and class_info["program"] == "Bachelor":
                        print(f"       ❌ {day} {TIME_SLOTS[start_slot]} - {room['room_id']} (wrong campus)")
                    elif room["campus"] == "Berlin" and class_info["program"] == "Master":
                        print(f"       ❌ {day} {TIME_SLOTS[start_slot]} - {room['room_id']} (wrong campus)")
                    elif room.get("ue_blocked", {}).get(day) == "all":
                        print(f"       ❌ {day} {TIME_SLOTS[start_slot]} - {room['room_id']} (UE blocked)")
                    elif room["capacity"] < class_info["students"]:
                        print(f"       ❌ {day} {TIME_SLOTS[start_slot]} - {room['room_id']} (capacity {room['capacity']} < {class_info['students']})")
    
    if total_possible == 0:
        print(f"\n     ❌ NO possible spots found for {class_id}!")
    else:
        print(f"\n     ✅ Found {total_possible} possible spots")
    
    return total_possible


def resolve_with_backtracking(existing_schedule, leftover_ids, all_classes, all_rooms, 
                              all_professors, student_groups, verbose=True):
    """
    Main backtracking function.
    Tries to place leftover classes by recursively trying different combinations.
    Returns: (final_schedule, unscheduled_ids)
    """
    # Setup lookup tables
    class_lookup = {c["class_id"]: c for c in all_classes}
    professor_lookup = {p["prof_id"]: p for p in all_professors}
    room_lookup = {r["room_id"]: r for r in all_rooms}
    group_membership = build_group_membership(student_groups)

    # Build occupancy from existing schedule
    occupied_rooms, occupied_professors = build_room_occupancy(existing_schedule)

    # Track occupied student groups
    occupied_groups = {}
    for entry in existing_schedule:
        start_slot = TIME_SLOTS.index(entry["start_time"])
        for block in get_class_blocks(start_slot, entry["duration_hours"]):
            for group in group_membership.get(entry["class_id"], ()):
                occupied_groups.setdefault((entry["day"], block), set()).add(group)

    # Pre-compute possible spots for each leftover class
    possible_spots = {}
    for class_id in leftover_ids:
        class_info = class_lookup[class_id]
        spots = find_all_possible_spots(class_info, all_rooms, professor_lookup)
        possible_spots[class_id] = spots
        
        if verbose and not spots:
            debug_why_impossible(class_id, class_info, all_rooms, professor_lookup)
    
    # Order by most constrained first (fewest spots)
    search_order = sorted(leftover_ids, 
                          key=lambda c: len(possible_spots[c]))

    # Sort spots for each class: smallest room first
    for class_id in search_order:
        possible_spots[class_id].sort(
            key=lambda spot: room_lookup[spot[2]]["capacity"]
        )

    current_placements = []
    best_result = [len(search_order), [], list(search_order)]
    node_count = [0]
    all_skipped = []

    def is_spot_free(class_id, day, start_slot, room_id):
        """Check if a spot conflicts with existing schedule."""
        class_info = class_lookup[class_id]
        class_blocks = get_class_blocks(start_slot, class_info["duration"])
        
        for block in class_blocks:
            # Room taken?
            if (day, room_id, block) in occupied_rooms:
                return False
            # Professor busy?
            if (day, class_info["professor"], block) in occupied_professors:
                return False
            # Student group busy?
            busy = occupied_groups.get((day, block))
            if busy:
                if busy & group_membership.get(class_id, set()):
                    return False
        return True

    def occupy_spot(class_id, day, start_slot, room_id, is_placing):
        """Add or remove resources for a class."""
        class_info = class_lookup[class_id]
        for block in get_class_blocks(start_slot, class_info["duration"]):
            room_cell = (day, room_id, block)
            professor_cell = (day, class_info["professor"], block)
            
            if is_placing:
                occupied_rooms.add(room_cell)
                occupied_professors.add(professor_cell)
                for group in group_membership.get(class_id, ()):
                    occupied_groups.setdefault((day, block), set()).add(group)
            else:
                occupied_rooms.discard(room_cell)
                occupied_professors.discard(professor_cell)
                for group in group_membership.get(class_id, ()):
                    group_cell = occupied_groups.get((day, block))
                    if group_cell:
                        group_cell.discard(group)

    def update_best_solution(unscheduled):
        """Keep track of the best solution found so far."""
        if len(unscheduled) < best_result[0]:
            best_result[0] = len(unscheduled)
            best_result[1] = list(current_placements)
            best_result[2] = list(unscheduled)
            if verbose:
                print(f"  New best: {len(unscheduled)} unscheduled: {unscheduled}")

    def backtrack_search(current_idx, skipped):
        """
        The recursive backtracking function.
        Returns True if all classes can be placed from this point.
        """
        node_count[0] += 1
        if node_count[0] > MAX_ATTEMPTS:
            if verbose:
                print(f"  Budget exhausted at node {node_count[0]}")
            update_best_solution(skipped)
            return False
        
        # If we've processed all classes, we're done
        if current_idx == len(search_order):
            if verbose:
                print(f"  Leaf: skipped {len(skipped)} classes: {skipped if skipped else 'NONE'}")
            update_best_solution(skipped)
            if skipped:
                all_skipped.extend(skipped)
            return len(skipped) == 0

        class_id = search_order[current_idx]
        class_info = class_lookup[class_id]
        
        if verbose and len(skipped) == 0:
            print(f"  Trying to place {class_id} (possible: {len(possible_spots[class_id])} spots)")

        # Try each possible spot
        for attempt, (day, start_slot, room_id) in enumerate(possible_spots[class_id]):
            if not is_spot_free(class_id, day, start_slot, room_id):
                continue
            
            # Place the class
            occupy_spot(class_id, day, start_slot, room_id, is_placing=True)
            chosen_room = room_lookup[room_id]
            current_placements.append({
                "class_id": class_id, 
                "professor": class_info["professor"], 
                "day": day,
                "start_time": convert_slot_to_time(start_slot), 
                "duration_hours": class_info["duration"],
                "room_id": room_id, 
                "wasted_capacity": chosen_room["capacity"] - class_info["students"],
            })
            
            if verbose and len(skipped) == 0:
                print(f"    Placing {class_id} at {day} {convert_slot_to_time(start_slot)}")
            
            # Recursively try to place the rest
            if backtrack_search(current_idx + 1, skipped):
                return True
            
            # Backtrack - remove the class
            current_placements.pop()
            occupy_spot(class_id, day, start_slot, room_id, is_placing=False)
            
            if verbose and len(skipped) == 0:
                print(f"    Backtracking from {class_id} at {day} {convert_slot_to_time(start_slot)}")

        # Can't place this class - skip it
        if verbose:
            print(f"  Skipping {class_id} (no feasible spot found)")
        
        update_best_solution(skipped + [class_id])
        return backtrack_search(current_idx + 1, skipped + [class_id])

    # Run the backtracking
    if search_order:
        if verbose:
            print(f"\nBacktracking (Stage 4)")
            print(f"  Trying to place {len(search_order)} leftover classes")
            print(f"  Search order (most constrained first): {search_order}")
        
        backtrack_search(0, [])
        
        if verbose:
            print(f"  search nodes expanded: {node_count[0]}")
            if current_placements:
                print(f"  recovered {len(current_placements)} leftover class(es)")
            if best_result[2]:
                print(f"  minimum-conflict unscheduled set: {', '.join(best_result[2])}")
            else:
                print("  all classes scheduled")
    else:
        best_result = [0, [], []]
        if verbose:
            print("\nBacktracking (Stage 4)")
            print("  No leftover classes to place")

    final_schedule = existing_schedule + best_result[1]
    unscheduled = best_result[2]

    # Show all classes that were skipped
    if verbose and all_skipped:
        unique_skipped = list(set(all_skipped))
        print(f"\n  ALL classes that were skipped (from leaf nodes): {', '.join(unique_skipped)}")

    # Detailed analysis for unscheduled classes
    if verbose and unscheduled:
        print(f"\n  📋 DETAILED ANALYSIS FOR UNPLACED CLASSES:")
        for class_id in unscheduled:
            class_info = class_lookup[class_id]
            spots = possible_spots.get(class_id, [])
            print(f"\n    Class {class_id}:")
            print(f"      - {class_info['students']} students, {class_info['duration']} hours")
            print(f"      - Professor: {class_info['professor']}")
            print(f"      - Program: {class_info['program']}")
            print(f"      - Possible spots: {len(spots)}")
            
            if not spots:
                professor_info = professor_lookup.get(class_info["professor"], {})
                available = professor_info.get("availability", [])
                
                if available:
                    print(f"      - Professor availability:")
                    max_hours = 0
                    for window in available:
                        start_h = int(window["start"].split(":")[0])
                        end_h = int(window["end"].split(":")[0])
                        hours = end_h - start_h
                        max_hours = max(max_hours, hours)
                        if window["day"] in DAYS:
                            print(f"        * {window['day']}: {window['start']} - {window['end']} ({hours}h)")
                    
                    if max_hours < class_info["duration"]:
                        print(f"      - ❌ Maximum available hours ({max_hours}) < required duration ({class_info['duration']})")
                
                # Check room constraints
                if class_info["program"] == "Bachelor":
                    berlin_rooms = [r for r in all_rooms if r["campus"] == "Berlin"]
                    print(f"      - Berlin rooms available: {len(berlin_rooms)}")
                else:
                    potsdam_rooms = [r for r in all_rooms if r["campus"] == "Potsdam"]
                    print(f"      - Potsdam rooms available: {len(potsdam_rooms)}")

    return final_schedule, unscheduled