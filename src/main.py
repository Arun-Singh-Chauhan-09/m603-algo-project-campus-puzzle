"""
main.py  --  Campus Scheduler

This runs the entire scheduling pipeline:
1. Greedy baseline - quick initial schedule
2. Graph coloring - assign time slots
3. Dynamic Programming - optimize room allocation
4. Backtracking - best effort to recover leftovers

ALL data is read from data/constraints.json - no hardcoded classes or groups!
"""

import json
import os
import sys
import re
from datetime import datetime

# Add the current directory to path if needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from greedy_solver import build_greedy_schedule
from graph_engine import build_conflict_graph, assign_time_slots
from optimizer import assign_rooms_with_dp
from backtracker import resolve_with_backtracking


def load_data():
    """Load the constraints file from the data directory."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Try multiple possible locations
    possible_paths = [
        # data/ at the same level as src/
        os.path.join(os.path.dirname(current_dir), "data", "constraints.json"),
        # data/ inside src/
        os.path.join(current_dir, "data", "constraints.json"),
        # data/ two levels up
        os.path.join(os.path.dirname(os.path.dirname(current_dir)), "data", "constraints.json"),
        # Relative to current working directory
        "data/constraints.json",
        "../data/constraints.json",
        "../../data/constraints.json",
    ]
    
    for file_path in possible_paths:
        if os.path.exists(file_path):
            print(f"✅ Found constraints file: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    
    print(f"❌ Error: constraints.json not found!")
    print(f"   Current working directory: {os.getcwd()}")
    print(f"   Script directory: {current_dir}")
    print(f"\n   Tried these paths:")
    for path in possible_paths:
        print(f"     - {os.path.abspath(path)}")
    print("\n   Please create data/constraints.json in one of these locations.")
    print("   Expected structure:")
    print("     campus_scheduler/")
    print("     ├── data/")
    print("     │   └── constraints.json")
    print("     └── src/")
    print("         ├── common.py")
    print("         ├── main.py")
    print("         └── ...")
    exit(1)


def normalize_time(time_str):
    """Convert time to 24-hour format."""
    if not time_str:
        return "09:00"
    
    time_str = str(time_str).strip().lower()
    
    # Handle PM
    if "pm" in time_str:
        time_str = time_str.replace("pm", "").strip()
        if ":" in time_str:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = parts[1] if len(parts) > 1 else "00"
        else:
            hour = int(time_str) if time_str else 12
            minute = "00"
        if hour != 12:
            hour += 12
        if hour >= 24:
            hour = 17
        return f"{hour:02d}:{minute[:2]}"
    
    # Handle AM
    if "am" in time_str:
        time_str = time_str.replace("am", "").strip()
        if ":" in time_str:
            parts = time_str.split(":")
            hour = int(parts[0])
            minute = parts[1] if len(parts) > 1 else "00"
        else:
            hour = int(time_str) if time_str else 9
            minute = "00"
        if hour == 12:
            hour = 0
        if hour >= 24:
            hour = 17
        return f"{hour:02d}:{minute[:2]}"
    
    # Handle simple numbers
    if time_str.isdigit():
        hour = int(time_str)
        if hour < 8:
            hour += 12
        if hour >= 24:
            hour = 17
        return f"{hour:02d}:00"
    
    # Handle HH:MM format
    if ":" in time_str:
        parts = time_str.split(":")
        hour = int(parts[0]) if parts[0].isdigit() else 9
        minute = parts[1] if len(parts) > 1 and parts[1].isdigit() else "00"
        if hour >= 24:
            hour = 17
        return f"{hour:02d}:{minute[:2]}"
    
    return "09:00"


def parse_availability_text(text):
    """Simple parser for availability text."""
    if not text or text == "":
        return []
    
    text = str(text)
    windows = []
    
    # Check for "Full availability"
    if "full" in text.lower():
        for day in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
            windows.append({"day": day, "start": "09:00", "end": "17:00"})
        return windows
    
    # Default times
    start_time = "09:00"
    end_time = "17:00"
    
    # Look for time ranges
    range_pattern = r'(\d{1,2}(?::\d{2})?)\s*(?:-|to|–)\s*(\d{1,2}(?::\d{2})?)'
    range_match = re.search(range_pattern, text)
    if range_match:
        start_time = normalize_time(range_match.group(1))
        end_time = normalize_time(range_match.group(2))
    
    # Check for "after" or "from" patterns
    if not range_match:
        from_pattern = r'(?:from|after)\s*(\d{1,2}(?::\d{2})?)\s*([ap]m)?'
        from_match = re.search(from_pattern, text, re.IGNORECASE)
        if from_match:
            time_str = from_match.group(1)
            ampm = from_match.group(2) or ""
            start_time = normalize_time(time_str + ampm)
    
    # Check for standalone PM times
    pm_match = re.search(r'(\d{1,2})\s*pm', text.lower())
    if pm_match and not range_match and not from_match:
        hour = int(pm_match.group(1))
        if hour != 12:
            hour += 12
        start_time = f"{hour:02d}:00"
    
    # Find days mentioned
    days_found = []
    day_map = {
        "Monday": "Mon", "Mondays": "Mon",
        "Tuesday": "Tue", "Tuesdays": "Tue", "Tues": "Tue",
        "Wednesday": "Wed", "Wednesdays": "Wed", "Weds": "Wed",
        "Thursday": "Thu", "Thursdays": "Thu", "Thurs": "Thu",
        "Friday": "Fri", "Fridays": "Fri",
    }
    
    for key, value in day_map.items():
        if key in text:
            days_found.append(value)
    
    # If no full day names found, check for short forms
    if not days_found:
        if "Mon" in text and "Monday" not in text:
            days_found.append("Mon")
        if "Tue" in text and "Tuesday" not in text:
            days_found.append("Tue")
        if "Wed" in text and "Wednesday" not in text:
            days_found.append("Wed")
        if "Thu" in text and "Thursday" not in text:
            days_found.append("Thu")
        if "Fri" in text and "Friday" not in text:
            days_found.append("Fri")
    
    # If still no days found, assume full week
    if not days_found:
        days_found = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    
    # Add window for each day found
    for day in days_found:
        windows.append({"day": day, "start": start_time, "end": end_time})
    
    return windows


def convert_json_to_standard_format(json_data):
    """
    Convert the JSON format to the format expected by the scheduler.
    ALL data comes from JSON now - nothing hardcoded!
    """
    # Convert freelancers and internal faculty to professors
    professors = []
    
    # Add freelancers (external)
    for freelancer in json_data.get("freelancers_availability", []):
        name = freelancer["freelancer"]
        availability_text = freelancer["availability"]
        
        # Parse availability text into structured format
        avail = parse_availability_text(availability_text)
        
        professors.append({
            "prof_id": name.replace(" ", "_"),
            "type": "external",
            "availability": avail
        })
    
    # Add internal faculty
    for faculty in json_data.get("internal_faculty", []):
        name = faculty["name"]
        notes = faculty.get("notes") or ""
        
        avail = parse_availability_text(notes) if notes else []
        
        # If no specific availability, assume full week
        if not avail:
            for day in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
                avail.append({"day": day, "start": "09:00", "end": "17:00"})
        
        professors.append({
            "prof_id": name.replace(" ", "_"),
            "type": "internal",
            "availability": avail
        })
    
    # Convert Berlin rooms
    rooms = []
    for room in json_data.get("rooms_berlin", {}).get("rooms", []):
        rooms.append({
            "room_id": f"BER-{room['room']}",
            "capacity": room["capacity"],
            "campus": "Berlin",
            "ue_blocked": {}
        })
    
    # Convert Potsdam rooms
    for room in json_data.get("rooms_potsdam", {}).get("rooms", []):
        ue_blocked = {}
        allocation = room.get("allocation", {})
        
        # Map days to check for UE blocking
        day_map = {
            "monday": "Mon",
            "tuesday": "Tue",
            "wednesday": "Wed",
            "thursday": "Thu",
            "friday": "Fri",
            "saturday": "Sat"
        }
        
        for day_key, day_short in day_map.items():
            if day_key in allocation:
                value = allocation[day_key]
                if "UE" in str(value).upper():
                    ue_blocked[day_short] = "all"
        
        rooms.append({
            "room_id": f"POT-{room['room']}",
            "capacity": room["capacity"],
            "campus": "Potsdam",
            "ue_blocked": ue_blocked
        })
    
    # ============================================================
    # READ CLASSES FROM JSON (NO HARDCODING!)
    # ============================================================
    classes = json_data.get("classes", [])
    
    # If no classes in JSON, show error and exit
    if not classes:
        print("❌ ERROR: No 'classes' found in constraints.json!")
        print("   Please add a 'classes' array to your constraints.json file.")
        print("   Example:")
        print('   "classes": [')
        print('     {')
        print('       "class_id": "M501",')
        print('       "students": 30,')
        print('       "professor": "Farid",')
        print('       "program": "Master",')
        print('       "duration": 3')
        print('     }')
        print('   ]')
        exit(1)
    
    # ============================================================
    # READ STUDENT GROUPS FROM JSON (NO HARDCODING!)
    # ============================================================
    student_groups = json_data.get("student_groups", {})
    
    if not student_groups:
        print("⚠️  WARNING: No 'student_groups' found in constraints.json!")
        print("   Using default empty groups. Please add student groups to the JSON file.")
        print("   Example:")
        print('   "student_groups": {')
        print('     "Master_Group_1": ["M501", "M502"],')
        print('     "Bachelor_Group_1": ["B124", "B125"]')
        print('   }')
        # Create default groups based on class prefixes
        master_classes = [c["class_id"] for c in classes if c.get("program") == "Master"]
        bachelor_classes = [c["class_id"] for c in classes if c.get("program") == "Bachelor"]
        if master_classes:
            student_groups["Default_Master_Group"] = master_classes
        if bachelor_classes:
            student_groups["Default_Bachelor_Group"] = bachelor_classes
    
    return {
        "days": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "blocks": ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"],
        "rooms": rooms,
        "professors": professors,
        "classes": classes,
        "student_groups": student_groups
    }


def format_waste(wasted_seats):
    """Format the waste message nicely."""
    if wasted_seats == 0:
        return "Perfect Fit"
    return f"Wasted {wasted_seats} seats"


def main():
    """Main entry point - runs all 4 stages of the scheduler."""
    
    print("=" * 60)
    print("📚 CAMPUS SCHEDULER")
    print("=" * 60)
    print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Load and convert data
    raw_data = load_data()
    data = convert_json_to_standard_format(raw_data)
    
    all_classes = data["classes"]
    all_rooms = data["rooms"]
    all_professors = data["professors"]
    student_groups = data["student_groups"]
    
    print(f"📊 Data loaded:")
    print(f"   - {len(all_professors)} professors")
    print(f"   - {len(all_rooms)} rooms")
    print(f"   - {len(all_classes)} classes")
    print(f"   - {len(student_groups)} student groups\n")
    
    # Stage 1: Greedy Baseline
    print("=" * 60)
    print("STAGE 1: GREEDY BASELINE")
    print("=" * 60)
    
    greedy_schedule, greedy_unscheduled = build_greedy_schedule(
        all_classes, all_rooms, all_professors
    )
    
    for entry in sorted(greedy_schedule, key=lambda x: (x["day"], x["start_time"])):
        print(f"  {entry['class_id']:10s} {entry['day']} {entry['start_time']} "
              f"({entry['duration_hours']}h) -> {entry['room_id']:9s} (waste {entry['wasted_capacity']})")
    
    print(f"  Greedy placed {len(greedy_schedule)}/{len(all_classes)}; "
          f"unplaced: {greedy_unscheduled or 'none'}")
    
    # Stage 2: Graph Coloring
    print("\n" + "=" * 60)
    print("STAGE 2: GRAPH COLORING (time slots)")
    print("=" * 60)
    
    conflict_graph = build_conflict_graph(all_classes, student_groups)
    slot_assignment, uncolorable = assign_time_slots(
        conflict_graph, all_classes, all_professors
    )
    
    # Stage 3: Dynamic Programming
    print("\n" + "=" * 60)
    print("STAGE 3: DYNAMIC PROGRAMMING (room allocation)")
    print("=" * 60)
    
    scheduled_placements, no_room_classes = assign_rooms_with_dp(
        all_classes, all_rooms, slot_assignment
    )
    
    # Find classes that still need placement
    placed_ids = {p["class_id"] for p in scheduled_placements}
    leftover_ids = [
        c["class_id"] for c in all_classes 
        if c["class_id"] not in placed_ids
    ]
    
    # Stage 4: Backtracking
    print("\n" + "=" * 60)
    print("STAGE 4: BACKTRACKING (best effort)")
    print("=" * 60)
    
    final_schedule, final_unscheduled = resolve_with_backtracking(
        scheduled_placements, leftover_ids, all_classes, 
        all_rooms, all_professors, student_groups
    )
    
    # Final Report
    print("\n" + "=" * 60)
    print("FINAL SCHEDULE / CONFLICT REPORT")
    print("=" * 60)
    
    # Show scheduled classes
    if final_schedule:
        for entry in sorted(final_schedule, key=lambda x: (x["day"], x["start_time"])):
            print(f"Scheduled {entry['class_id']:10s} {entry['day']} {entry['start_time']} "
                  f"{entry['room_id']:9s} {format_waste(entry['wasted_capacity'])}")
    else:
        print("  No classes were scheduled")
    
    # Show unscheduled classes
    scheduled_ids = {e["class_id"] for e in final_schedule}
    all_unscheduled = [c["class_id"] for c in all_classes if c["class_id"] not in scheduled_ids]
    
    if all_unscheduled:
        for class_id in all_unscheduled:
            print(f"Unscheduled {class_id:10s} N/A   N/A")
    else:
        print("  ✅ All classes scheduled successfully!")
    
    # Summary
    total = len(all_classes)
    scheduled_count = len(final_schedule)
    unscheduled_count = len(all_unscheduled)
    
    print(f"\n📊 Summary: scheduled {scheduled_count}/{total}, "
          f"unscheduled {unscheduled_count} "
          f"({unscheduled_count/total*100:.1f}% need manual intervention)")


if __name__ == "__main__":
    main()