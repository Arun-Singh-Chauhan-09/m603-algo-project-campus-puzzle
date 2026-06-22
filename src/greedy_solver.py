"""
greedy_solver.py  --  Stage 1: The Greedy Baseline

This is my first attempt at scheduling. I sort classes by how many students they have
(larger first because they're harder to fit) and just place them in the first 
available slot I find. It's simple but gives a decent starting point.
"""

from common import (DAYS, TIME_SLOTS, get_class_blocks, can_class_use_room,
                    is_professor_free, convert_slot_to_time)


def build_greedy_schedule(all_classes, all_rooms, all_professors):
    """
    Creates a schedule using the greedy approach.
    Returns: (schedule, list_of_unscheduled_classes)
    """
    # Create quick lookup dictionaries
    professor_lookup = {prof["prof_id"]: prof for prof in all_professors}

    final_schedule = []
    unscheduled_classes = []

    # Track what's already booked
    # (day, room_id, slot_index) -> room is taken
    booked_rooms = set()
    # (day, professor_id, slot_index) -> professor is busy
    booked_professors = set()

    # Sort by number of students (largest first)
    # I chose this because bigger classes have fewer room options
    sorted_classes = sorted(all_classes, key=lambda c: c["students"], reverse=True)

    for class_info in sorted_classes:
        professor_info = professor_lookup.get(class_info["professor"], {})
        class_duration = class_info["duration"]
        class_placed = False

        # Try every day and time slot
        for day in DAYS:
            for start_slot in range(len(TIME_SLOTS)):
                class_blocks = get_class_blocks(start_slot, class_duration)

                # Check professor availability
                if not is_professor_free(professor_info, day, start_slot, class_duration):
                    continue
                
                # Check professor isn't already teaching then
                if any((day, class_info["professor"], block) in booked_professors for block in class_blocks):
                    continue

                # Try each room
                for room_info in all_rooms:
                    # Check room constraints (campus, UE, capacity, etc.)
                    if not can_class_use_room(room_info, class_info, day, start_slot, class_duration):
                        continue
                    
                    # Check room isn't already taken
                    if any((day, room_info["room_id"], block) in booked_rooms for block in class_blocks):
                        continue

                    # We found a spot! Book it
                    for block in class_blocks:
                        booked_rooms.add((day, room_info["room_id"], block))
                        booked_professors.add((day, class_info["professor"], block))

                    final_schedule.append({
                        "class_id": class_info["class_id"],
                        "professor": class_info["professor"],
                        "day": day,
                        "start_time": convert_slot_to_time(start_slot),
                        "duration_hours": class_duration,
                        "room_id": room_info["room_id"],
                        "wasted_capacity": room_info["capacity"] - class_info["students"],
                    })
                    class_placed = True
                    break  # Found a room, move to next class
                if class_placed:
                    break  # Found a time, move to next class
            if class_placed:
                break  # Found a day, move to next class

        # If we couldn't place the class anywhere, add to unscheduled list
        if not class_placed:
            unscheduled_classes.append(class_info["class_id"])

    return final_schedule, unscheduled_classes