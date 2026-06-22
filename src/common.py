"""
common.py
Helper functions for the campus scheduler.

This file contains the basic building blocks used across all stages.
I defined the week days and time blocks here so they're consistent everywhere.
"""

# Week days from Monday to Saturday (we don't use Sunday)
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

# Time slots from 9am to 7pm (10 blocks)
# The college runs 9-5 but I allowed some buffer for professors who work later
TIME_SLOTS = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00", "19:00"]


def convert_time_to_slot(time_string):
    """
    Converts a time string like "13:30" to a slot index.
    I floor it to the hour because classes start on the hour.
    Example: "13:30" becomes index 4 (13:00)
    """
    hour, minute = time_string.split(":")
    hour = int(hour)
    minute = int(minute)
    
    # 09:00 is index 0, so we subtract 9
    slot_index = hour - 9
    
    # Safety: make sure we don't go out of bounds
    if slot_index < 0:
        slot_index = 0
    if slot_index >= len(TIME_SLOTS):
        slot_index = len(TIME_SLOTS) - 1
    return slot_index


def convert_slot_to_time(slot_index):
    """Convert a slot index back to a readable time string."""
    if 0 <= slot_index < len(TIME_SLOTS):
        return TIME_SLOTS[slot_index]
    return f"slot{slot_index}"


def get_class_blocks(start_slot, duration):
    """
    Returns all block indices a class will occupy.
    For example: start=0, duration=3 gives [0,1,2] (9am to 12pm)
    """
    end = start_slot + duration
    if end > len(TIME_SLOTS):
        end = len(TIME_SLOTS)
    return list(range(start_slot, end))


def does_class_fit_in_day(start_slot, duration):
    """Check if a class finishes before 7pm."""
    return start_slot + duration <= len(TIME_SLOTS)


def is_professor_free(professor_info, day, start_slot, duration):
    """
    Checks if a professor can teach a class at a given time.
    I check that their availability window covers the ENTIRE class duration.
    If a professor has no availability listed, I assume they're free all day
    (this was a design choice to keep things simple).
    """
    available_windows = professor_info.get("availability")
    
    # If no availability defined, professor is fully available
    if not available_windows:
        return True
    
    class_start = start_slot
    class_end = start_slot + duration
    
    for window in available_windows:
        # Skip days that don't match
        if window["day"] != day:
            continue
        
        window_start = convert_time_to_slot(window["start"])
        window_end = convert_time_to_slot(window["end"])
        
        # The class must fit completely inside the professor's availability
        if window_start <= class_start and class_end <= window_end:
            return True
    
    return False


def is_room_right_for_program(room_info, class_info):
    """
    Rule: Bachelor classes go to Berlin, Master classes go to Potsdam.
    This is a university rule so I had to implement it.
    """
    if class_info["program"] == "Bachelor":
        return room_info["campus"] == "Berlin"
    if class_info["program"] == "Master":
        return room_info["campus"] == "Potsdam"
    return True


def is_room_blocked_by_ue(room_info, day):
    """
    Some rooms are blocked by UE (Unternehmerisch) activities.
    If a room says "all" for a day, we can't use it.
    """
    blocked_days = room_info.get("ue_blocked", {})
    return blocked_days.get(day) == "all"


def can_class_use_room(room_info, class_info, day, start_slot, duration):
    """
    Checks if a room can host a specific class.
    I check: campus match, UE blocking, capacity, and if the class fits in the day.
    """
    # Program must match campus
    if not is_room_right_for_program(room_info, class_info):
        return False
    
    # Can't use room if UE blocked
    if is_room_blocked_by_ue(room_info, day):
        return False
    
    # Room must have enough seats
    if room_info["capacity"] < class_info["students"]:
        return False
    
    # Class must fit before 7pm
    if not does_class_fit_in_day(start_slot, duration):
        return False
    
    return True


def sort_rooms_by_priority(room_info):
    """
    Sorts rooms: Berlin rooms first (external campus), then by capacity.
    I put Berlin first because it's the smaller campus and harder to find rooms.
    """
    # Berlin rooms are external, Potsdam is internal
    is_internal = room_info["campus"] != "Berlin"
    return (is_internal, room_info["capacity"])