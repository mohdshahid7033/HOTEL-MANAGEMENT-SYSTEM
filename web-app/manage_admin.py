"""
Taj Banjara Hotel Management System — Administrator Account Management & Safe Recovery CLI
Project Owner & Sole Developer: Mohd Shahid Moin Uddin

This utility provides a safe, explicit recovery and administration process for local
and production databases without resetting, reseeding, or deleting existing bookings,
housekeeping records, or staff data.

Usage:
    python web-app/manage_admin.py --status
    python web-app/manage_admin.py --recover
    python web-app/manage_admin.py --set-password <new_password>
"""

import os
import sys
import argparse
import sqlite3

# Ensure web-app directory is on path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from config import Config
from database import (
    get_db,
    verify_storage_path,
    safe_migrate_or_recover_admin,
    resolve_initial_admin_password,
    DEV_ADMIN_PASSWORD_FALLBACK,
    DISALLOWED_ADMIN_PASSWORDS
)
from auth import hash_password, verify_password

def get_connection(db_path=None):
    """Establishes an isolated SQLite connection to the target database."""
    target_path = db_path or Config.DATABASE_PATH
    verified = verify_storage_path(target_path, require_persistence=False)
    conn = sqlite3.connect(verified)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def show_status(db_path=None):
    """Displays the status of staff, bookings, and housekeeping without exposing sensitive hashes."""
    conn = get_connection(db_path)
    try:
        staff_rows = conn.execute("SELECT staff_id, name, designation, contact, login_username, is_demo FROM staff").fetchall()
        booking_count = conn.execute("SELECT COUNT(*) AS c FROM bookings").fetchone()['c']
        hk_count = conn.execute("SELECT COUNT(*) AS c FROM housekeeping").fetchone()['c']

        print("\n=== Taj Banjara Hotel — Database Status ===")
        print(f"Database: {db_path or Config.DATABASE_PATH}")
        print(f"Total Preserved Bookings: {booking_count}")
        print(f"Total Preserved Housekeeping Rooms: {hk_count}")
        print(f"Total Staff Records: {len(staff_rows)}")
        print("\nRegistered Staff Accounts:")
        for s in staff_rows:
            role_tag = "[ADMIN]" if s['designation'] in ('Manager', 'Administrator') else "[STAFF]"
            demo_tag = "(Demo Account)" if s['is_demo'] else "(Standard Account)"
            print(f"  - Staff ID: {s['staff_id']} | Username: '{s['login_username']}' | Role: {s['designation']} {role_tag} {demo_tag}")

        admin_exists = any(s['login_username'] == 'admin' for s in staff_rows)
        legacy_exists = any(s['login_username'] == 'demo_admin' for s in staff_rows)

        print("\nAdministrator Account Health:")
        if admin_exists:
            print("  [OK] Active 'admin' account found.")
        elif legacy_exists:
            print("  [ACTION NEEDED] Legacy 'demo_admin' account found. Run '--recover' to migrate to 'admin'.")
        else:
            print("  [ACTION NEEDED] No 'admin' account found. Run '--recover' to create the administrator.")
        print()
    finally:
        conn.close()

def recover_admin(db_path=None, explicit_password=None):
    """Safely migrates or updates the administrator account without touching any bookings or other data."""
    conn = get_connection(db_path)
    try:
        # Pre-check counts
        b_before = conn.execute("SELECT COUNT(*) AS c FROM bookings").fetchone()['c']
        hk_before = conn.execute("SELECT COUNT(*) AS c FROM housekeeping").fetchone()['c']

        result = safe_migrate_or_recover_admin(conn, explicit_password=explicit_password)

        # Post-check counts
        b_after = conn.execute("SELECT COUNT(*) AS c FROM bookings").fetchone()['c']
        hk_after = conn.execute("SELECT COUNT(*) AS c FROM housekeeping").fetchone()['c']

        assert b_before == b_after, "FATAL INTEGRITY VIOLATION: Bookings count changed during admin recovery!"
        assert hk_before == hk_after, "FATAL INTEGRITY VIOLATION: Housekeeping count changed during admin recovery!"

        print("\n=== Administrator Safe Recovery Completed ===")
        print(f"Action: {result['action'].upper()}")
        print(f"Administrator Username: '{result['username']}' (Staff ID: {result['staff_id']})")
        print(f"Status: {result['message']}")
        print(f"Integrity Verified: All {b_after} existing bookings and {hk_after} housekeeping records preserved intact.")
        print()
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Taj Banjara Hotel — Administrator Account Management & Safe Recovery")
    parser.add_argument('--status', action='store_true', help="Check database status and administrator health")
    parser.add_argument('--recover', action='store_true', help="Safely recover or migrate administrator credentials")
    parser.add_argument('--set-password', type=str, help="Set a specific password for the administrator account")
    parser.add_argument('--db-path', type=str, help="Override database path")

    args = parser.parse_args()

    if args.set_password:
        recover_admin(db_path=args.db_path, explicit_password=args.set_password)
    elif args.recover:
        recover_admin(db_path=args.db_path)
    elif args.status:
        show_status(db_path=args.db_path)
    else:
        # Default behavior when invoked without args: recover if needed, then show status
        recover_admin(db_path=args.db_path)
        show_status(db_path=args.db_path)

if __name__ == '__main__':
    main()
