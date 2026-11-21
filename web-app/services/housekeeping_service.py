from config import Config
from database import get_db

def get_housekeeping_status():
    """Returns housekeeping status for all rooms 101 to 110."""
    db = get_db()
    cur = db.execute("SELECT room_no, status, last_cleaned_by, updated_at FROM housekeeping")
    lookup = {row['room_no']: dict(row) for row in cur.fetchall()}

    results = []
    for r in sorted(Config.ROOMS, key=lambda x: int(x)):
        data = lookup.get(r, {"status": "Clean", "last_cleaned_by": "System"})
        results.append({
            "room_no": r,
            "status": data["status"],
            "last_cleaned_by": data["last_cleaned_by"] or "-"
        })
    return results

def cycle_room_status(room_no, staff_name="Staff"):
    """
    Cycles housekeeping status:
      'Clean' -> 'Needs Cleaning'
      'Needs Cleaning' -> 'In Progress'
      'In Progress' -> 'Clean' (recorded with staff_name)
    Exact parity with desktop handle_action_button().
    """
    room_no = str(room_no).strip()
    if room_no not in Config.ROOMS:
        return {"success": False, "error": f"Invalid room number '{room_no}'."}

    db = get_db()
    cur = db.execute("SELECT status FROM housekeeping WHERE room_no = ?", (room_no,))
    row = cur.fetchone()
    current_status = row['status'] if row else 'Clean'

    if current_status == 'Clean':
        new_status = 'Needs Cleaning'
        cleaned_by = None
        action_msg = "Room marked as 'Needs Cleaning'."
    elif current_status == 'Needs Cleaning':
        new_status = 'In Progress'
        cleaned_by = None
        action_msg = "Cleaning started."
    elif current_status == 'In Progress':
        new_status = 'Clean'
        cleaned_by = staff_name
        action_msg = "Room marked as 'Clean'."
    else:
        new_status = 'Needs Cleaning'
        cleaned_by = None
        action_msg = "Room status reset to 'Needs Cleaning'."

    with db:
        db.execute("""
            INSERT INTO housekeeping (room_no, status, last_cleaned_by, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(room_no) DO UPDATE SET
                status = excluded.status,
                last_cleaned_by = excluded.last_cleaned_by,
                updated_at = CURRENT_TIMESTAMP
        """, (room_no, new_status, cleaned_by))

    return {
        "success": True,
        "message": f"Room {room_no} status changed to '{new_status}'. {action_msg}",
        "room_no": room_no,
        "status": new_status,
        "new_status": new_status,
        "last_cleaned_by": cleaned_by or "-"
    }
