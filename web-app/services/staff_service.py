from database import get_db
from auth import hash_password

def generate_next_staff_id():
    """Generates the next sequential staff ID (e.g. 'S001', 'S002')."""
    db = get_db()
    cur = db.execute("SELECT staff_id FROM staff")
    rows = cur.fetchall()

    max_num = 0
    for r in rows:
        sid = str(r['staff_id']).strip()
        if sid.startswith('S') and sid[1:].isdigit():
            max_num = max(max_num, int(sid[1:]))
    return f"S{max_num + 1:03d}"

def get_all_staff():
    """Returns safe staff list (no passwords or salts)."""
    db = get_db()
    cur = db.execute("""
        SELECT staff_id, name, designation, contact, login_username, is_demo
        FROM staff
        ORDER BY staff_id ASC
    """)
    return [dict(r) for r in cur.fetchall()]

def add_staff_member(name, designation, contact, username, password):
    """Adds a new staff member with PBKDF2 salt and hash."""
    name = str(name).strip() if name else ""
    designation = str(designation).strip() if designation else ""
    contact = str(contact).strip() if contact else ""
    username = str(username).strip() if username else ""
    password = str(password) if password else ""

    if not all([name, designation, contact, username, password]):
        return {"success": False, "error": "All fields are required."}

    if not password.strip():
        return {"success": False, "error": "Password cannot be blank."}

    db = get_db()
    cur = db.execute("SELECT staff_id FROM staff WHERE login_username = ?", (username,))
    if cur.fetchone():
        return {"success": False, "error": f"Username '{username}' already exists."}

    staff_id = generate_next_staff_id()
    salt, pw_hash = hash_password(password)

    with db:
        db.execute("""
            INSERT INTO staff (staff_id, name, designation, contact, login_username, login_password, password_salt, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0)
        """, (staff_id, name, designation, contact, username, pw_hash, salt))

    return {
        "success": True,
        "message": f"New staff '{name}' added with ID: {staff_id}.",
        "staff_id": staff_id,
        "staff": {
            "staff_id": staff_id,
            "name": name,
            "designation": designation,
            "contact": contact,
            "login_username": username
        }
    }

def update_staff_member(staff_id, name, designation, contact):
    """Updates name, designation, and contact for an existing staff member."""
    name = str(name).strip() if name else ""
    designation = str(designation).strip() if designation else ""
    contact = str(contact).strip() if contact else ""

    if not all([name, designation, contact]):
        return {"success": False, "error": "All fields must be filled."}

    db = get_db()
    with db:
        cur = db.execute("""
            UPDATE staff
            SET name = ?, designation = ?, contact = ?
            WHERE staff_id = ?
        """, (name, designation, contact, str(staff_id)))
        if cur.rowcount == 0:
            return {"success": False, "error": f"Staff member '{staff_id}' not found."}

    return {
        "success": True,
        "message": f"Staff ID {staff_id} updated successfully.",
        "staff_id": staff_id,
        "name": name,
        "designation": designation,
        "contact": contact
    }
