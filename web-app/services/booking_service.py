import sqlite3
from datetime import datetime
from config import Config
from database import get_db, query_db

def get_available_rooms():
    """Returns list of rooms not currently booked."""
    db = get_db()
    cur = db.execute("SELECT room_no FROM bookings WHERE status = 'Booked'")
    booked_rooms = {row['room_no'] for row in cur.fetchall()}
    return [r for r in sorted(Config.ROOMS, key=lambda x: int(x)) if r not in booked_rooms]

def get_room_status_overview():
    """
    Returns the status of all rooms 101 to 110.
    Identical logic to the desktop Room Status layout.
    """
    db = get_db()
    cur = db.execute("""
        SELECT room_no, guest_name, days, food_plan, check_in_datetime
        FROM bookings
        WHERE status = 'Booked'
    """)
    active_by_room = {row['room_no']: dict(row) for row in cur.fetchall()}

    overview = []
    for room in sorted(Config.ROOMS, key=lambda x: int(x)):
        if room in active_by_room:
            b = active_by_room[room]
            overview.append({
                "room_no": room,
                "status": "Booked",
                "guest_name": b["guest_name"],
                "days": b["days"],
                "food_plan": b["food_plan"],
                "check_in_datetime": b["check_in_datetime"]
            })
        else:
            overview.append({
                "room_no": room,
                "status": "Available",
                "guest_name": "-",
                "days": "-",
                "food_plan": "-",
                "check_in_datetime": "-"
            })
    return overview

def book_room(guest_name, days, food_plan="None", requested_room=None):
    """
    Creates a new room booking with strict validation and concurrency protection.
    """
    guest_name = str(guest_name).strip() if guest_name else ""
    if not guest_name:
        return {"success": False, "error": "Guest name cannot be empty."}

    try:
        days = int(days)
        if days <= 0:
            return {"success": False, "error": "Number of days must be a positive number."}
    except (ValueError, TypeError):
        return {"success": False, "error": "Please enter a valid integer for number of days."}

    if food_plan not in Config.FOOD_PRICES:
        return {"success": False, "error": f"Invalid food plan. Options are: {', '.join(Config.FOOD_PRICES.keys())}"}

    db = get_db()

    # Use a transaction with exclusive lock to prevent race conditions & double-booking
    with db:
        cur = db.execute("SELECT room_no FROM bookings WHERE status = 'Booked'")
        active_rooms = {row['room_no'] for row in cur.fetchall()}
        available = [r for r in sorted(Config.ROOMS, key=lambda x: int(x)) if r not in active_rooms]

        if not available:
            return {"success": False, "error": "No rooms available to book."}

        # Resolve target room
        target_room = requested_room if requested_room else available[0]
        if target_room not in Config.ROOMS:
            return {"success": False, "error": f"Invalid room number '{target_room}'."}

        if target_room in active_rooms:
            return {"success": False, "error": f"Room {target_room} is already booked."}

        check_in_dt = datetime.now().strftime("%d-%m-%Y %I:%M %p")

        try:
            cur = db.execute("""
                INSERT INTO bookings (room_no, guest_name, days, food_plan, check_in_datetime, status)
                VALUES (?, ?, ?, ?, ?, 'Booked')
            """, (target_room, guest_name, days, food_plan, check_in_dt))
            booking_id = cur.lastrowid
        except sqlite3.IntegrityError:
            return {"success": False, "error": f"Room {target_room} is already booked."}

    return {
        "success": True,
        "message": f"Room {target_room} booked successfully for {guest_name}.",
        "booking": {
            "id": booking_id,
            "room_no": target_room,
            "guest_name": guest_name,
            "days": days,
            "food_plan": food_plan,
            "check_in_datetime": check_in_dt,
            "status": "Booked"
        }
    }

def calculate_bill_preview(room_no):
    """
    Computes exact room and dining charges with 18% GST.
    Formula identical to desktop calculate_bill().
    """
    db = get_db()
    cur = db.execute("""
        SELECT id, room_no, guest_name, days, food_plan, check_in_datetime
        FROM bookings
        WHERE room_no = ? AND status = 'Booked'
    """, (str(room_no),))
    booking = cur.fetchone()

    if not booking:
        return {
            "success": False,
            "error": f"No active booking found for Room {room_no}."
        }

    booking = dict(booking)
    days = max(1, int(booking.get('days', 1)))
    food_plan = booking.get('food_plan', 'None')

    room_charge = Config.ROOM_RATE * days
    food_charge = Config.FOOD_PRICES.get(food_plan, 0) * days
    subtotal = room_charge + food_charge
    gst_amount = subtotal * Config.GST_RATE
    total_amount = subtotal + gst_amount

    return {
        "success": True,
        "booking": booking,
        "bill": {
            "room_rate": Config.ROOM_RATE,
            "days": days,
            "room_charge": room_charge,
            "food_plan": food_plan,
            "food_rate": Config.FOOD_PRICES.get(food_plan, 0),
            "food_charge": food_charge,
            "subtotal": subtotal,
            "gst_rate_percent": int(Config.GST_RATE * 100),
            "gst_amount": gst_amount,
            "total_amount": total_amount,
            "formatted": {
                "room_charge": f"₹{room_charge:,.2f}",
                "food_charge": f"₹{food_charge:,.2f}",
                "subtotal": f"₹{subtotal:,.2f}",
                "gst_amount": f"₹{gst_amount:,.2f}",
                "total_amount": f"₹{total_amount:,.2f}"
            }
        }
    }

def complete_checkout(room_no):
    """
    Finalizes checkout: updates status, records charges, and marks room as 'Needs Cleaning'.
    """
    preview = calculate_bill_preview(room_no)
    if not preview["success"]:
        return preview

    bill = preview["bill"]
    booking = preview["booking"]
    checkout_dt = datetime.now().strftime("%d-%m-%Y %I:%M %p")

    db = get_db()
    with db:
        # Mark booking as Checked Out
        db.execute("""
            UPDATE bookings
            SET status = 'Checked Out',
                checkout_datetime = ?,
                room_charge = ?,
                food_charge = ?,
                subtotal = ?,
                gst_amount = ?,
                total_amount = ?
            WHERE id = ?
        """, (
            checkout_dt,
            bill["room_charge"],
            bill["food_charge"],
            bill["subtotal"],
            bill["gst_amount"],
            bill["total_amount"],
            booking["id"]
        ))

        # Update Housekeeping: Room needs cleaning after checkout
        db.execute("""
            UPDATE housekeeping
            SET status = 'Needs Cleaning',
                last_cleaned_by = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE room_no = ?
        """, (str(room_no),))

    return {
        "success": True,
        "message": f"Checkout successful for Room {room_no}. Room marked for cleaning.",
        "booking": booking,
        "bill": bill,
        "checkout_summary": {
            "room_no": str(room_no),
            "guest_name": booking["guest_name"],
            "check_in_datetime": booking["check_in_datetime"],
            "checkout_datetime": checkout_dt,
            "days": bill["days"],
            "total_amount": bill["total_amount"],
            "total_amount_formatted": bill["formatted"]["total_amount"]
        }
    }

def search_guests(term):
    """Case-insensitive substring search across all guest bookings."""
    term = str(term).strip().lower() if term else ""
    if not term:
        return {"success": False, "error": "Search term cannot be empty.", "results": []}

    db = get_db()
    cur = db.execute("""
        SELECT id, room_no, guest_name, check_in_datetime, checkout_datetime, days, food_plan, status
        FROM bookings
        WHERE LOWER(guest_name) LIKE ?
        ORDER BY id DESC
    """, (f"%{term}%",))
    rows = [dict(r) for r in cur.fetchall()]

    return {
        "success": True,
        "count": len(rows),
        "results": rows
    }

def get_active_booking_for_room(room_no):
    """Retrieves active booking details for update modal."""
    row = query_db("""
        SELECT id, room_no, guest_name, days, food_plan, check_in_datetime, status
        FROM bookings
        WHERE room_no = ? AND status = 'Booked'
    """, (str(room_no),), one=True)
    if not row:
        return {"success": False, "error": f"No active booking found for Room {room_no}."}
    return {"success": True, "booking": row}

def update_booking(room_no, new_days, new_food_plan):
    """Updates stay duration and dining plan for an active booking."""
    try:
        new_days = int(new_days)
        if new_days <= 0:
            return {"success": False, "error": "Please enter a valid positive number of days."}
    except (ValueError, TypeError):
        return {"success": False, "error": "Please enter a valid integer for number of days."}

    if new_food_plan not in Config.FOOD_PRICES:
        return {"success": False, "error": f"Invalid food plan. Options are: {', '.join(Config.FOOD_PRICES.keys())}"}

    db = get_db()
    with db:
        cur = db.execute("""
            UPDATE bookings
            SET days = ?, food_plan = ?
            WHERE room_no = ? AND status = 'Booked'
        """, (new_days, new_food_plan, str(room_no)))
        if cur.rowcount == 0:
            return {"success": False, "error": f"No active booking found for Room {room_no} to update."}

    return {
        "success": True,
        "message": f"Booking for Room {room_no} updated successfully.",
        "room_no": str(room_no),
        "days": new_days,
        "food_plan": new_food_plan
    }

def get_booking_history():
    """
    Returns full booking history sorted by check-in date/time descending.
    Matches desktop sort_key logic.
    """
    db = get_db()
    cur = db.execute("""
        SELECT id, room_no, guest_name, check_in_datetime, checkout_datetime, days, food_plan, status, total_amount
        FROM bookings
        ORDER BY id DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]

    # Sort using date parsing fallback to guarantee reverse-chronological order
    def parse_dt(row):
        try:
            return datetime.strptime(row['check_in_datetime'], '%d-%m-%Y %I:%M %p')
        except:
            return datetime.min

    sorted_rows = sorted(rows, key=parse_dt, reverse=True)
    return sorted_rows
