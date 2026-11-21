import os
import sqlite3
from flask import g, current_app
from config import Config
from auth import hash_password

def verify_storage_path(db_path, require_persistence=False):
    """
    Validates the database path and ensures the storage directory is accessible and writable.
    Fails safely with a RuntimeError if persistent storage is unavailable rather than silently
    falling back to an unexpected, ephemeral, or insecure location.
    """
    if not db_path:
        raise RuntimeError("FATAL: DATABASE_PATH configuration is empty or undefined.")

    abs_path = os.path.abspath(db_path)
    db_dir = os.path.dirname(abs_path)

    if require_persistence:
        if not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir, exist_ok=True)
            except Exception as e:
                raise RuntimeError(
                    f"FATAL DATABASE ERROR: Persistent storage directory '{db_dir}' is unavailable or cannot be created: {e}. "
                    f"The application refuses to start with an ephemeral fallback in production. "
                    f"Ensure the Render persistent disk is mounted at '{db_dir}'."
                ) from e

        # Validate write permissions on persistent mount
        test_file = os.path.join(db_dir, '.storage_write_test')
        try:
            with open(test_file, 'w') as f:
                f.write('persistence_ok')
            os.remove(test_file)
        except Exception as e:
            raise RuntimeError(
                f"FATAL DATABASE ERROR: Persistent storage directory '{db_dir}' is not writable: {e}. "
                f"Check persistent disk mount permissions."
            ) from e
    else:
        # Development / local testing: ensure directory exists
        try:
            os.makedirs(db_dir, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"FATAL DATABASE ERROR: Could not create database directory '{db_dir}': {e}") from e

    return abs_path

def get_db():
    """Returns a thread-safe connection to the SQLite database."""
    if 'db' not in g:
        db_path = current_app.config.get('DATABASE_PATH', Config.DATABASE_PATH)
        require_persistence = current_app.config.get('REQUIRE_PERSISTENT_STORAGE', Config.REQUIRE_PERSISTENT_STORAGE)
        verified_path = verify_storage_path(db_path, require_persistence)
        g.db = sqlite3.connect(
            verified_path,
            timeout=30.0  # Generous timeout for concurrent write safety
        )
        g.db.row_factory = sqlite3.Row
        # Enable Write-Ahead Logging (WAL) for superior concurrency and read/write throughput
        g.db.execute("PRAGMA journal_mode=WAL;")
        g.db.execute("PRAGMA foreign_keys=ON;")
    return g.db

def close_db(e=None):
    """Closes the current database connection if open."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def query_db(query, args=(), one=False):
    """Helper to execute SELECT queries and return dictionaries."""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    if one:
        return dict(rv[0]) if rv else None
    return [dict(row) for row in rv]

def execute_db(query, args=(), commit=True):
    """Helper to execute INSERT/UPDATE/DELETE queries."""
    db = get_db()
    cur = db.execute(query, args)
    if commit:
        db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id

def init_db(app, force_reseed=False):
    """
    Creates tables if they do not exist and initializes room inventory and safe demo data.
    Ensures zero interaction with or alteration of desktop hotel_data/.
    """
    with app.app_context():
        db = get_db()

        # Create Schema
        db.executescript("""
        CREATE TABLE IF NOT EXISTS staff (
            staff_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            designation TEXT NOT NULL,
            contact TEXT NOT NULL,
            login_username TEXT UNIQUE NOT NULL,
            login_password TEXT NOT NULL,
            password_salt TEXT,
            is_demo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_no TEXT NOT NULL,
            guest_name TEXT NOT NULL,
            days INTEGER NOT NULL,
            food_plan TEXT NOT NULL,
            check_in_datetime TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Booked',
            checkout_datetime TEXT,
            room_charge REAL,
            food_charge REAL,
            subtotal REAL,
            gst_amount REAL,
            total_amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS housekeeping (
            room_no TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'Clean',
            last_cleaned_by TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS system_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_active_room ON bookings(room_no) WHERE status = 'Booked';
        """)
        db.commit()

        # Initialize Room Inventory (101 to 110) in Housekeeping
        for room in Config.ROOMS:
            cur = db.execute("SELECT room_no FROM housekeeping WHERE room_no = ?", (room,))
            if not cur.fetchone():
                db.execute(
                    "INSERT INTO housekeeping (room_no, status, last_cleaned_by) VALUES (?, 'Clean', 'System')",
                    (room,)
                )
        db.commit()

        # Check if staff accounts exist
        cur = db.execute("SELECT COUNT(*) AS count FROM staff")
        staff_count = cur.fetchone()['count']

        if staff_count == 0 and (Config.DEMO_MODE or force_reseed):
            seed_safe_demo_data(db, app)
        elif Config.DEMO_MODE:
            # If in demo/development mode and legacy demo_admin is present with no 'admin',
            # migrate legacy demo_admin to 'admin' without touching any bookings or other staff
            legacy_admin = db.execute(
                "SELECT staff_id FROM staff WHERE login_username = 'demo_admin' AND is_demo = 1"
            ).fetchone()
            has_admin = db.execute(
                "SELECT staff_id FROM staff WHERE login_username = 'admin'"
            ).fetchone()
            if legacy_admin and not has_admin:
                safe_migrate_or_recover_admin(db, app)

DEV_ADMIN_PASSWORD_FALLBACK = 'DevAdmin@LocalOnly#2026'

DISALLOWED_ADMIN_PASSWORDS = {
    'adminsecure@2026',
    'devadmin@localonly#2026',
    'admin',
    'administrator',
    'password',
    '123456',
    '12345678',
    'admin123',
    'secret',
    'root',
    'toor',
    'guest'
}

def resolve_initial_admin_password(app=None):
    """
    Resolves and validates the initial administrator password for database initialization.

    In production environments:
      - INITIAL_ADMIN_PASSWORD must be provided via environment variable.
      - Default, hardcoded, trivial, or insecure passwords are strictly rejected with a RuntimeError.
      - Passwords are never printed or logged.
    In local development / testing:
      - Uses INITIAL_ADMIN_PASSWORD from the environment if present.
      - Otherwise allows the clearly isolated DEV_ADMIN_PASSWORD_FALLBACK.
    """
    is_prod = False
    if app is not None:
        is_prod = app.config.get('IS_PRODUCTION', False)
    else:
        try:
            is_prod = current_app.config.get('IS_PRODUCTION', False)
        except RuntimeError:
            is_prod = Config.IS_PRODUCTION

    if not is_prod:
        is_prod = (
            os.environ.get('RENDER') is not None
            or os.environ.get('FLASK_ENV') == 'production'
            or Config.IS_PRODUCTION
        )

    env_pw = os.environ.get('INITIAL_ADMIN_PASSWORD')

    if is_prod:
        if not env_pw or not env_pw.strip():
            raise RuntimeError(
                "FATAL SECURITY ERROR: In production environments, INITIAL_ADMIN_PASSWORD must be set "
                "via environment variable to initialize the administrator account. "
                "Production databases must never be created with a default, missing, or hardcoded password."
            )

        cleaned = env_pw.strip()
        if len(cleaned) < 10 or cleaned.lower() in DISALLOWED_ADMIN_PASSWORDS:
            raise RuntimeError(
                "FATAL SECURITY ERROR: In production environments, INITIAL_ADMIN_PASSWORD cannot be a "
                "known default, weak, or trivial password. Provide a strong password of at least 10 characters."
            )
        return cleaned

    # Non-production (local development / testing)
    if env_pw and env_pw.strip():
        return env_pw.strip()

    return DEV_ADMIN_PASSWORD_FALLBACK

def safe_migrate_or_recover_admin(db, app=None, explicit_password=None):
    """
    Safely recovers or migrates the administrator account without modifying, deleting,
    or resetting existing bookings, housekeeping, or other staff records.

    1. Checks if an administrator ('admin') already exists.
    2. If a legacy demo administrator ('demo_admin', is_demo=1) exists, migrates it to 'admin'.
    3. If neither exists, creates 'admin' (S001).
    4. Applies the resolved password (explicit, env-var, or development fallback) with fresh PBKDF2 salt.
    5. Leaves all bookings, housekeeping, and other staff records completely untouched.
    """
    # 1. Resolve password
    if explicit_password:
        is_prod = False
        if app is not None:
            is_prod = app.config.get('IS_PRODUCTION', False)
        else:
            try:
                is_prod = current_app.config.get('IS_PRODUCTION', False)
            except RuntimeError:
                is_prod = Config.IS_PRODUCTION

        if is_prod:
            cleaned = explicit_password.strip()
            if len(cleaned) < 10 or cleaned.lower() in DISALLOWED_ADMIN_PASSWORDS:
                raise RuntimeError(
                    "FATAL SECURITY ERROR: In production environments, administrator password cannot be a "
                    "known default, weak, or trivial password. Provide a strong password of at least 10 characters."
                )
            admin_password = cleaned
        else:
            admin_password = explicit_password.strip()
    else:
        admin_password = resolve_initial_admin_password(app)

    new_salt, new_hash = hash_password(admin_password)

    # 2. Check existing staff records
    cur = db.execute("SELECT staff_id, name, designation, login_username, is_demo FROM staff WHERE login_username = 'admin'")
    admin_row = cur.fetchone()

    if admin_row:
        # Admin already exists: update credentials securely
        db.execute("""
            UPDATE staff
            SET login_password = ?, password_salt = ?, is_demo = 0
            WHERE login_username = 'admin'
        """, (new_hash, new_salt))
        db.commit()
        return {
            "action": "updated",
            "username": "admin",
            "staff_id": admin_row['staff_id'],
            "message": "Existing administrator account credentials safely updated."
        }

    # 3. Check for legacy 'demo_admin' account
    cur = db.execute("SELECT staff_id, name, designation, login_username, is_demo FROM staff WHERE login_username = 'demo_admin'")
    legacy_row = cur.fetchone()

    if legacy_row:
        # Migrate legacy demo_admin to modern admin
        db.execute("""
            UPDATE staff
            SET login_username = 'admin', name = 'System Administrator',
                designation = 'Manager', contact = '9900000001',
                login_password = ?, password_salt = ?, is_demo = 0
            WHERE staff_id = ?
        """, (new_hash, new_salt, legacy_row['staff_id']))
        db.commit()
        return {
            "action": "migrated",
            "username": "admin",
            "staff_id": legacy_row['staff_id'],
            "message": "Legacy demo administrator account migrated to 'admin' with updated credentials."
        }

    # 4. If neither exists, insert S001 as admin
    db.execute("""
        INSERT INTO staff (staff_id, name, designation, contact, login_username, login_password, password_salt, is_demo)
        VALUES ('S001', 'System Administrator', 'Manager', '9900000001', 'admin', ?, ?, 0)
    """, (new_hash, new_salt))
    db.commit()
    return {
        "action": "created",
        "username": "admin",
        "staff_id": "S001",
        "message": "New administrator account 'admin' created successfully."
    }

def seed_safe_demo_data(db, app=None):
    """
    Seeds safe synthetic demo data for portfolio exploration.
    Uses purely fictional names, numbers, and sample bookings.
    """
    # 1. Administrator Account (Protected - Not accessible via public demo login)
    admin_password = resolve_initial_admin_password(app)
    admin_salt, admin_hash = hash_password(admin_password)
    db.execute("""
        INSERT OR REPLACE INTO staff (staff_id, name, designation, contact, login_username, login_password, password_salt, is_demo)
        VALUES ('S001', 'System Administrator', 'Manager', '9900000001', 'admin', ?, ?, 0)
    """, (admin_hash, admin_salt))

    # 2. Public Demo Receptionist (Restricted portfolio demo access)
    # Fictional credentials for portfolio demonstration only
    staff_salt, staff_hash = hash_password('StaffPass@2026')
    db.execute("""
        INSERT OR REPLACE INTO staff (staff_id, name, designation, contact, login_username, login_password, password_salt, is_demo)
        VALUES ('S002', 'Demo Receptionist', 'Receptionist', '9900000002', 'demo_staff', ?, ?, 1)
    """, (staff_hash, staff_salt))

    # 3. Synthetic Demo Bookings (Realistic historical and active stays)
    # Clear existing demo bookings if re-seeding
    db.execute("DELETE FROM bookings WHERE id <= 10")

    demo_bookings = [
        # Past Completed Bookings (Checked Out)
        ("101", "Aarav Sharma", 4, "Normal", "01-11-2026 10:00 AM", "Checked Out", "05-11-2026 11:30 AM", 60000.0, 2000.0, 62000.0, 11160.0, 73160.0),
        ("102", "Priya Verma", 3, "VIP", "02-11-2026 02:15 PM", "Checked Out", "05-11-2026 12:00 PM", 45000.0, 3000.0, 48000.0, 8640.0, 56640.0),
        ("104", "Rohan Mehta", 2, "None", "04-11-2026 04:00 PM", "Checked Out", "06-11-2026 10:45 AM", 30000.0, 0.0, 30000.0, 5400.0, 35400.0),
        ("105", "Neha Patel", 5, "Normal", "03-11-2026 01:30 PM", "Checked Out", "08-11-2026 11:00 AM", 75000.0, 2500.0, 77500.0, 13950.0, 91450.0),
        # Current Active Bookings (Booked)
        ("101", "Vikram Malhotra", 5, "VIP", "09-11-2026 03:00 PM", "Booked", None, None, None, None, None, None),
        ("103", "Ananya Reddy", 3, "Normal", "09-11-2026 06:30 PM", "Booked", None, None, None, None, None, None),
    ]

    for b in demo_bookings:
        db.execute("""
            INSERT INTO bookings (room_no, guest_name, days, food_plan, check_in_datetime, status, checkout_datetime,
                                  room_charge, food_charge, subtotal, gst_amount, total_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, b)

    # 4. Set Housekeeping States
    # Room 102 was recently checked out -> Needs Cleaning
    db.execute("UPDATE housekeeping SET status = 'Needs Cleaning', last_cleaned_by = NULL WHERE room_no = '102'")
    # Room 104 is in cleaning progress
    db.execute("UPDATE housekeeping SET status = 'In Progress', last_cleaned_by = NULL WHERE room_no = '104'")
    # All other rooms are Clean
    db.execute("UPDATE housekeeping SET status = 'Clean', last_cleaned_by = 'System' WHERE room_no NOT IN ('102', '104')")

    db.commit()

def reset_to_clean_demo(app):
    """Wipes and re-initializes safe demo state."""
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM bookings;")
        db.execute("DELETE FROM staff;")
        seed_safe_demo_data(db, app)
        db.commit()
