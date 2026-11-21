"""
Taj Banjara Hotel Management System — Comprehensive Backend Test Suite
Project Owner & Sole Developer: Mohd Shahid Moin Uddin
"""

import os
import sys
import unittest
import tempfile
import sqlite3
import json

# Add web-app root to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from config import Config
from database import (
    init_db,
    seed_safe_demo_data,
    verify_storage_path,
    DEV_ADMIN_PASSWORD_FALLBACK,
    resolve_initial_admin_password,
    safe_migrate_or_recover_admin
)
from auth import hash_password, verify_password

class TestHotelBackend(unittest.TestCase):
    def setUp(self):
        # Create a temporary database file in an isolated temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, 'test_hotel.db')

        class TestConfig(Config):
            TESTING = True
            DATABASE_PATH = self.db_path
            SECRET_KEY = 'test-secret-key-32-characters-long!!'
            DEMO_MODE = True
            WTF_CSRF_ENABLED = False

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        # Capture CSRF token
        with self.client:
            resp = self.client.get('/api/csrf-token')
            self.csrf_token = resp.get_json()['csrf_token']
            self.headers = {
                'X-CSRF-Token': self.csrf_token,
                'Content-Type': 'application/json'
            }

    def tearDown(self):
        self.temp_dir.cleanup()

    def get_csrf(self, client=None):
        c = client or self.client
        resp = c.get('/api/csrf-token')
        return resp.get_json()['csrf_token']

    def login_admin(self, client=None):
        """Authenticates with private administrator credentials (not exposed to demo visitors)."""
        c = client or self.client
        csrf = self.get_csrf(c)
        return c.post('/api/auth/login', json={
            'username': 'admin',
            'password': DEV_ADMIN_PASSWORD_FALLBACK
        }, headers={'X-CSRF-Token': csrf, 'Content-Type': 'application/json'})

    def login_demo_receptionist(self, client=None):
        """Public portfolio demo login: strictly restricted to Receptionist role."""
        c = client or self.client
        csrf = self.get_csrf(c)
        return c.post('/api/auth/demo-login', json={
            'role': 'receptionist'
        }, headers={'X-CSRF-Token': csrf, 'Content-Type': 'application/json'})

    # --- 1. Password Hashing & Legacy Compatibility ---
    def test_pbkdf2_hashing_and_uniqueness(self):
        s1, h1 = hash_password('AdminPass123')
        s2, h2 = hash_password('AdminPass123')
        self.assertNotEqual(s1, s2, "Salts must be unique per password hash")
        self.assertNotEqual(h1, h2, "Hashes must differ due to unique salts")
        self.assertEqual(len(s1), 32, "Salt must be 16 bytes (32 hex characters)")
        self.assertEqual(len(h1), 64, "PBKDF2-SHA256 hex digest must be 64 characters")
        self.assertTrue(verify_password('AdminPass123', h1, s1))
        self.assertFalse(verify_password('WrongPass', h1, s1))

    def test_legacy_sha256_compatibility(self):
        # Legacy unsalted SHA-256 hash for 'admin123'
        legacy_hash = '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9'
        self.assertTrue(verify_password('admin123', legacy_hash, None))
        self.assertFalse(verify_password('wrongpass', legacy_hash, None))

    # --- 2. CSRF Protection ---
    def test_csrf_protection_rejects_missing_token(self):
        # POST request without X-CSRF-Token should return 403
        resp = self.client.post('/api/auth/demo-login', json={'role': 'receptionist'})
        self.assertEqual(resp.status_code, 403)
        self.assertIn("CSRF", resp.get_json()['error'])

    def test_csrf_protection_accepts_valid_token(self):
        # POST with X-CSRF-Token should pass CSRF middleware
        resp = self.client.post('/api/auth/demo-login', json={'role': 'receptionist'}, headers=self.headers)
        self.assertEqual(resp.status_code, 200)

    # --- 3. Authentication & Role-Based Access ---
    def test_demo_login_admin_and_staff(self):
        # Public demo login MUST reject administrator requests
        admin_demo_resp = self.client.post('/api/auth/demo-login', json={'role': 'admin'}, headers=self.headers)
        self.assertEqual(admin_demo_resp.status_code, 403)
        self.assertIn("Administrator demo login is disabled", admin_demo_resp.get_json()['error'])

        # Public demo login provides Receptionist access
        staff_demo_resp = self.client.post('/api/auth/demo-login', json={'role': 'receptionist'}, headers=self.headers)
        self.assertEqual(staff_demo_resp.status_code, 200)
        staff_data = staff_demo_resp.get_json()
        self.assertEqual(staff_data['user']['designation'], 'Receptionist')
        self.assertFalse(staff_data['user']['is_admin'])

        # Check me
        me_resp = self.client.get('/api/auth/me')
        self.assertTrue(me_resp.get_json()['authenticated'])

        # Administrator can log in with private authenticated credentials
        admin_login_resp = self.login_admin()
        self.assertEqual(admin_login_resp.status_code, 200)
        self.assertTrue(admin_login_resp.get_json()['user']['is_admin'])

    def test_unauthenticated_guard(self):
        # Direct access to protected endpoint without logging in should return 401
        resp = self.client.get('/api/dashboard/stats')
        self.assertEqual(resp.status_code, 401)

    def test_admin_only_guard(self):
        # Log in as Receptionist (non-admin)
        self.login_demo_receptionist()
        # Attempt to access Staff Management (admin only)
        resp = self.client.get('/api/staff')
        self.assertEqual(resp.status_code, 403)

        # Log in as Administrator
        self.login_admin()
        resp2 = self.client.get('/api/staff')
        self.assertEqual(resp2.status_code, 200)

    # --- 4. Room Booking, Auto-assignment & Duplicate Prevention ---
    def test_room_booking_and_auto_assignment(self):
        self.login_admin()

        # Get initial available rooms
        avail_resp = self.client.get('/api/rooms/available')
        initial_avail = avail_resp.get_json()['available_rooms']
        self.assertIn('102', initial_avail)

        # Book a room
        book_resp = self.client.post('/api/bookings', json={
            'guest_name': 'Kavita Nair',
            'days': 4,
            'food_plan': 'VIP'
        }, headers=self.headers)
        self.assertEqual(book_resp.status_code, 200)
        b_data = book_resp.get_json()
        self.assertTrue(b_data['success'])
        assigned_room = b_data['booking']['room_no']
        self.assertEqual(assigned_room, initial_avail[0])

        # Verify assigned room is no longer in available list
        avail_resp2 = self.client.get('/api/rooms/available')
        self.assertNotIn(assigned_room, avail_resp2.get_json()['available_rooms'])

    def test_duplicate_room_booking_rejection(self):
        self.login_admin()

        # Book room 105 specifically
        resp1 = self.client.post('/api/bookings', json={
            'guest_name': 'First Guest',
            'days': 3,
            'food_plan': 'Normal',
            'room_no': '105'
        }, headers=self.headers)
        self.assertEqual(resp1.status_code, 200)

        # Attempt to book room 105 again while still active
        resp2 = self.client.post('/api/bookings', json={
            'guest_name': 'Second Guest',
            'days': 2,
            'food_plan': 'None',
            'room_no': '105'
        }, headers=self.headers)
        self.assertEqual(resp2.status_code, 400)
        self.assertIn("already booked", resp2.get_json()['error'])

    def test_booking_validation(self):
        self.login_admin()

        # Empty name
        r1 = self.client.post('/api/bookings', json={'guest_name': '', 'days': 3}, headers=self.headers)
        self.assertEqual(r1.status_code, 400)

        # Negative days
        r2 = self.client.post('/api/bookings', json={'guest_name': 'Valid Name', 'days': -1}, headers=self.headers)
        self.assertEqual(r2.status_code, 400)

        # Invalid food plan
        r3 = self.client.post('/api/bookings', json={'guest_name': 'Valid Name', 'days': 2, 'food_plan': 'Buffet'}, headers=self.headers)
        self.assertEqual(r3.status_code, 400)

    # --- 5. Billing Calculation & Checkout Workflow ---
    def test_billing_calculation_and_checkout(self):
        self.login_admin()

        # Book room 106 for 3 days with VIP food (₹1,000/day)
        # Room: 15,000 * 3 = 45,000
        # Food: 1,000 * 3 = 3,000
        # Subtotal: 48,000
        # GST (18%): 8,640
        # Total: 56,640
        book_resp = self.client.post('/api/bookings', json={
            'guest_name': 'Siddharth Rao',
            'days': 3,
            'food_plan': 'VIP',
            'room_no': '106'
        }, headers=self.headers)
        self.assertEqual(book_resp.status_code, 200)

        # Get bill preview
        preview_resp = self.client.get('/api/checkout/preview/106')
        self.assertEqual(preview_resp.status_code, 200)
        bill = preview_resp.get_json()['bill']

        self.assertEqual(bill['room_charge'], 45000.0)
        self.assertEqual(bill['food_charge'], 3000.0)
        self.assertEqual(bill['subtotal'], 48000.0)
        self.assertEqual(bill['gst_amount'], 8640.0)
        self.assertEqual(bill['total_amount'], 56640.0)
        self.assertEqual(bill['formatted']['total_amount'], '₹56,640.00')

        # Complete checkout
        checkout_resp = self.client.post('/api/checkout/106', headers=self.headers)
        self.assertEqual(checkout_resp.status_code, 200)
        c_data = checkout_resp.get_json()
        self.assertTrue(c_data['success'])
        self.assertIn("marked for cleaning", c_data['message'])

        # Verify room 106 is now in Housekeeping as 'Needs Cleaning'
        hk_resp = self.client.get('/api/housekeeping')
        hk_map = {item['room_no']: item for item in hk_resp.get_json()['housekeeping']}
        self.assertEqual(hk_map['106']['status'], 'Needs Cleaning')
        self.assertEqual(hk_map['106']['last_cleaned_by'], '-')

        # Verify checkout cannot be run again on vacant room
        co_fail = self.client.post('/api/checkout/106', headers=self.headers)
        self.assertEqual(co_fail.status_code, 400)

    # --- 6. Housekeeping Lifecycle ---
    def test_housekeeping_state_transitions(self):
        self.login_admin()

        # Room 107 starts Clean
        # 1. Clean -> Needs Cleaning
        r1 = self.client.post('/api/housekeeping/107/cycle', headers=self.headers)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.get_json()['status'], 'Needs Cleaning')

        # 2. Needs Cleaning -> In Progress
        r2 = self.client.post('/api/housekeeping/107/cycle', headers=self.headers)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.get_json()['status'], 'In Progress')

        # 3. In Progress -> Clean (recorded by current user)
        r3 = self.client.post('/api/housekeeping/107/cycle', headers=self.headers)
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.get_json()['status'], 'Clean')
        self.assertEqual(r3.get_json()['last_cleaned_by'], 'System Administrator')

    # --- 7. Guest Search & Booking Updates ---
    def test_guest_search_and_update(self):
        self.login_admin()

        # Search for synthetic guest 'Vikram'
        s_resp = self.client.get('/api/guests/search?q=vikram')
        self.assertEqual(s_resp.status_code, 200)
        results = s_resp.get_json()['results']
        self.assertGreaterEqual(len(results), 1)
        self.assertIn("Vikram", results[0]['guest_name'])

        # Update active booking for Room 101 (Vikram's room)
        up_resp = self.client.put('/api/bookings/active/101', json={
            'days': 7,
            'food_plan': 'Normal'
        }, headers=self.headers)
        self.assertEqual(up_resp.status_code, 200)
        self.assertEqual(up_resp.get_json()['days'], 7)
        self.assertEqual(up_resp.get_json()['food_plan'], 'Normal')

    # --- 8. Staff Management ---
    def test_staff_management_crud(self):
        self.login_admin()

        # Add new staff member
        add_resp = self.client.post('/api/staff', json={
            'name': 'Rahul Sen',
            'designation': 'Supervisor',
            'contact': '9900000099',
            'username': 'rahul_sen',
            'password': 'SecurePass@123'
        }, headers=self.headers)
        self.assertEqual(add_resp.status_code, 200)
        new_staff = add_resp.get_json()['staff']
        self.assertTrue(new_staff['staff_id'].startswith('S'))

        # Verify staff appears in roster
        list_resp = self.client.get('/api/staff')
        usernames = [s['login_username'] for s in list_resp.get_json()['staff']]
        self.assertIn('rahul_sen', usernames)

        # Edit staff
        edit_resp = self.client.put(f"/api/staff/{new_staff['staff_id']}", json={
            'name': 'Rahul Sen Updated',
            'designation': 'Senior Supervisor',
            'contact': '9900000098'
        }, headers=self.headers)
        self.assertEqual(edit_resp.status_code, 200)
        self.assertEqual(edit_resp.get_json()['designation'], 'Senior Supervisor')

    # --- 9. Database Persistence After App Restart ---
    def test_persistence_across_app_restart(self):
        # 1. Start App 1, book Room 108
        self.login_admin()
        self.client.post('/api/bookings', json={
            'guest_name': 'Persistent Guest',
            'days': 5,
            'food_plan': 'VIP',
            'room_no': '108'
        }, headers=self.headers)

        # 2. Simulate complete application shutdown & restart with identical DB file
        class RestartConfig(Config):
            TESTING = True
            DATABASE_PATH = self.db_path
            SECRET_KEY = 'test-secret-key-32-characters-long!!'
            DEMO_MODE = False  # Ensure no auto-reseed happens

        new_app = create_app(RestartConfig)
        new_client = new_app.test_client()

        # Get fresh CSRF token from new instance
        new_csrf = new_client.get('/api/csrf-token').get_json()['csrf_token']
        new_headers = {'X-CSRF-Token': new_csrf, 'Content-Type': 'application/json'}

        # Log into new instance with admin credentials
        login_resp = new_client.post('/api/auth/login', json={
            'username': 'admin',
            'password': DEV_ADMIN_PASSWORD_FALLBACK
        }, headers=new_headers)
        self.assertEqual(login_resp.status_code, 200)

        # Verify Room 108 is STILL booked in new instance
        status_resp = new_client.get('/api/rooms/status')
        self.assertEqual(status_resp.status_code, 200)
        status_map = {r['room_no']: r for r in status_resp.get_json()['rooms']}
        self.assertEqual(status_map['108']['status'], 'Booked')
        self.assertEqual(status_map['108']['guest_name'], 'Persistent Guest')

    # --- 10. Concurrency & Race Condition Test ---
    def test_concurrent_booking_race_condition(self):
        """Simulate two concurrent threads attempting to book the exact same room."""
        import threading

        self.login_admin()
        results = []

        def attempt_book(guest_name):
            th_client = self.app.test_client()
            th_csrf = th_client.get('/api/csrf-token').get_json()['csrf_token']
            th_headers = {'X-CSRF-Token': th_csrf, 'Content-Type': 'application/json'}
            th_client.post('/api/auth/login', json={
                'username': 'admin',
                'password': DEV_ADMIN_PASSWORD_FALLBACK
            }, headers=th_headers)

            resp = th_client.post('/api/bookings', json={
                'guest_name': guest_name,
                'days': 2,
                'food_plan': 'None',
                'room_no': '110'
            }, headers=th_headers)
            results.append((guest_name, resp.status_code, resp.get_json()))

        t1 = threading.Thread(target=attempt_book, args=('Concurrent Guest 1',))
        t2 = threading.Thread(target=attempt_book, args=('Concurrent Guest 2',))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly ONE thread must succeed (200), and the other must be rejected (400)
        status_codes = [r[1] for r in results]
        self.assertIn(200, status_codes)
        self.assertIn(400, status_codes)
        self.assertEqual(status_codes.count(200), 1, "Only one booking must succeed for Room 110")
        self.assertEqual(status_codes.count(400), 1, "Conflicting booking must be rejected")

    # --- 11. Targeted Public Demo Security Tests ---
    def test_public_demo_account_cannot_access_admin_functions(self):
        """Proves that portfolio visitors (receptionist demo) cannot access administrator operations."""
        self.login_demo_receptionist()

        # 1. Cannot list staff
        r1 = self.client.get('/api/staff')
        self.assertEqual(r1.status_code, 403)
        self.assertIn("Access denied", r1.get_json()['error'])

        # 2. Cannot add staff
        r2 = self.client.post('/api/staff', json={
            'name': 'Intruder', 'designation': 'Manager', 'contact': '9999999999',
            'username': 'intruder', 'password': 'Password123!'
        }, headers=self.headers)
        self.assertEqual(r2.status_code, 403)

        # 3. Cannot edit existing staff
        r3 = self.client.put('/api/staff/S001', json={
            'name': 'Hacked Admin', 'designation': 'Hacked', 'contact': '0000000000'
        }, headers=self.headers)
        self.assertEqual(r3.status_code, 403)

        # 4. Cannot reset demo data
        r4 = self.client.post('/api/demo/reset', headers=self.headers)
        self.assertEqual(r4.status_code, 403)

    def test_public_users_cannot_create_or_modify_admin_accounts(self):
        """Proves public users cannot tamper with admin setup or modify admin records."""
        # Setup route is locked once staff accounts exist
        r1 = self.client.post('/api/auth/setup', json={
            'name': 'Malicious User', 'contact': '1234567890',
            'username': 'new_admin', 'password': 'Pass123', 'confirm_password': 'Pass123'
        }, headers=self.headers)
        self.assertEqual(r1.status_code, 403)
        self.assertIn("already been completed", r1.get_json()['error'])

        r2 = self.client.post('/api/setup/admin', json={
            'name': 'Malicious User', 'contact': '1234567890',
            'username': 'new_admin', 'password': 'Pass123', 'confirm_password': 'Pass123'
        }, headers=self.headers)
        self.assertEqual(r2.status_code, 403)

        # Unauthenticated users cannot modify staff
        r3 = self.client.put('/api/staff/S001', json={
            'name': 'Compromised Name', 'designation': 'Manager', 'contact': '9900000001'
        }, headers=self.headers)
        self.assertEqual(r3.status_code, 401)

    # --- 12. Fail-Safe Storage & Configuration Tests ---
    def test_database_fails_safely_when_persistent_path_unavailable(self):
        """Proves that verify_storage_path raises RuntimeError if persistent storage is unmounted."""
        # Non-existent and uncreatable directory on Windows
        invalid_path = r"Z:\non_existent_drive_mount_path_12345\hotel.db"
        with self.assertRaises(RuntimeError) as ctx:
            verify_storage_path(invalid_path, require_persistence=True)
        self.assertIn("Persistent storage directory", str(ctx.exception))

    # --- 13. Production Administrator Password Hardening Tests ---
    def test_production_initialization_fails_if_initial_admin_password_missing(self):
        """Proves that production database initialization strictly fails if INITIAL_ADMIN_PASSWORD is missing."""
        temp_fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(temp_fd)

        class ProdConfig(Config):
            TESTING = True
            IS_PRODUCTION = True
            DATABASE_PATH = temp_db
            SECRET_KEY = 'valid-production-secret-key-32chars!'
            DEMO_MODE = True

        env_backup = os.environ.pop('INITIAL_ADMIN_PASSWORD', None)
        try:
            with self.assertRaises(RuntimeError) as ctx:
                create_app(ProdConfig)
            self.assertIn("INITIAL_ADMIN_PASSWORD must be set", str(ctx.exception))
        finally:
            if env_backup is not None:
                os.environ['INITIAL_ADMIN_PASSWORD'] = env_backup
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except OSError:
                    pass

    def test_production_initialization_fails_if_insecure_default_supplied(self):
        """Proves that production initialization rejects known defaults and insecure passwords."""
        insecure_candidates = ['AdminSecure@2026', 'DevAdmin@LocalOnly#2026', 'admin', 'password', '123456', 'short']

        env_backup = os.environ.get('INITIAL_ADMIN_PASSWORD')
        try:
            for bad_pw in insecure_candidates:
                temp_fd, temp_db = tempfile.mkstemp(suffix='.db')
                os.close(temp_fd)

                class ProdConfig(Config):
                    TESTING = True
                    IS_PRODUCTION = True
                    DATABASE_PATH = temp_db
                    SECRET_KEY = 'valid-production-secret-key-32chars!'
                    DEMO_MODE = True

                os.environ['INITIAL_ADMIN_PASSWORD'] = bad_pw
                try:
                    with self.assertRaises(RuntimeError) as ctx:
                        create_app(ProdConfig)
                    self.assertIn("known default, weak, or trivial password", str(ctx.exception))
                finally:
                    if os.path.exists(temp_db):
                        try:
                            os.remove(temp_db)
                        except OSError:
                            pass
        finally:
            if env_backup is not None:
                os.environ['INITIAL_ADMIN_PASSWORD'] = env_backup
            else:
                os.environ.pop('INITIAL_ADMIN_PASSWORD', None)

    def test_production_initialization_succeeds_with_valid_environment_provided_password(self):
        """Proves that production initialization succeeds when a strong, unique password is provided via environment."""
        temp_fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(temp_fd)

        class ProdConfig(Config):
            TESTING = True
            IS_PRODUCTION = True
            DATABASE_PATH = temp_db
            SECRET_KEY = 'valid-production-secret-key-32chars!'
            DEMO_MODE = True
            WTF_CSRF_ENABLED = False

        strong_pw = 'ProdAdmin#Taj2026!Strong'
        env_backup = os.environ.get('INITIAL_ADMIN_PASSWORD')
        os.environ['INITIAL_ADMIN_PASSWORD'] = strong_pw

        try:
            prod_app = create_app(ProdConfig)
            with prod_app.app_context():
                db = sqlite3.connect(temp_db)
                db.row_factory = sqlite3.Row
                admin_row = db.execute("SELECT * FROM staff WHERE login_username = 'admin'").fetchone()
                db.close()

                self.assertIsNotNone(admin_row)
                self.assertEqual(admin_row['designation'], 'Manager')
                self.assertTrue(verify_password(strong_pw, admin_row['login_password'], admin_row['password_salt']))
        finally:
            if env_backup is not None:
                os.environ['INITIAL_ADMIN_PASSWORD'] = env_backup
            else:
                os.environ.pop('INITIAL_ADMIN_PASSWORD', None)
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except OSError:
                    pass

    def test_no_production_administrator_created_with_hardcoded_fallback_password(self):
        """Confirms no production administrator account can be created with the old hardcoded fallback password."""
        temp_fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(temp_fd)

        class ProdConfig(Config):
            TESTING = True
            IS_PRODUCTION = True
            DATABASE_PATH = temp_db
            SECRET_KEY = 'valid-production-secret-key-32chars!'
            DEMO_MODE = True

        env_backup = os.environ.get('INITIAL_ADMIN_PASSWORD')
        valid_custom_pw = 'CustomSecretKey!2026#Unshared'
        os.environ['INITIAL_ADMIN_PASSWORD'] = valid_custom_pw

        try:
            prod_app = create_app(ProdConfig)
            with prod_app.app_context():
                db = sqlite3.connect(temp_db)
                db.row_factory = sqlite3.Row
                admin_row = db.execute("SELECT * FROM staff WHERE login_username = 'admin'").fetchone()
                db.close()

                self.assertIsNotNone(admin_row)
                # Confirm neither legacy fallback nor dev fallback matches
                self.assertFalse(verify_password('AdminSecure@2026', admin_row['login_password'], admin_row['password_salt']))
                self.assertFalse(verify_password(DEV_ADMIN_PASSWORD_FALLBACK, admin_row['login_password'], admin_row['password_salt']))
                # Confirm only the environment-provided password matches
                self.assertTrue(verify_password(valid_custom_pw, admin_row['login_password'], admin_row['password_salt']))
        finally:
            if env_backup is not None:
                os.environ['INITIAL_ADMIN_PASSWORD'] = env_backup
            else:
                os.environ.pop('INITIAL_ADMIN_PASSWORD', None)
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except OSError:
                    pass

    # --- 14. Local Development Administrator Login & Migration Tests ---
    def test_local_admin_login_with_development_credentials_and_incorrect_rejected(self):
        """Proves local administrator login works with configured dev credentials and rejects invalid passwords."""
        # 1. Correct credentials succeed
        login_resp = self.login_admin()
        self.assertEqual(login_resp.status_code, 200)
        data = login_resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['username'], 'admin')
        self.assertTrue(data['user']['is_admin'])

        # 2. Incorrect password rejected
        csrf = self.get_csrf()
        bad_pw_resp = self.client.post('/api/auth/login', json={
            'username': 'admin',
            'password': 'WrongPassword#123'
        }, headers={'X-CSRF-Token': csrf, 'Content-Type': 'application/json'})
        self.assertEqual(bad_pw_resp.status_code, 401)
        self.assertIn("Invalid username or password", bad_pw_resp.get_json()['error'])

        # 3. Non-existent username rejected
        csrf = self.get_csrf()
        bad_user_resp = self.client.post('/api/auth/login', json={
            'username': 'non_existent_user',
            'password': DEV_ADMIN_PASSWORD_FALLBACK
        }, headers={'X-CSRF-Token': csrf, 'Content-Type': 'application/json'})
        self.assertEqual(bad_user_resp.status_code, 401)
        self.assertIn("Invalid username or password", bad_user_resp.get_json()['error'])

        # 4. Receptionist demo login continues to work
        demo_resp = self.login_demo_receptionist()
        self.assertEqual(demo_resp.status_code, 200)
        self.assertEqual(demo_resp.get_json()['user']['designation'], 'Receptionist')

    def test_legacy_demo_admin_migration_and_data_preservation(self):
        """Proves that a legacy database with demo_admin and existing bookings is safely migrated without data loss."""
        temp_fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(temp_fd)

        try:
            # Seed legacy database manually with existing bookings, housekeeping, and legacy demo_admin
            conn = sqlite3.connect(temp_db)
            conn.execute("""
                CREATE TABLE staff (
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
            """)
            conn.execute("""
                CREATE TABLE bookings (
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
            """)
            conn.execute("""
                CREATE TABLE housekeeping (
                    room_no TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'Clean',
                    last_cleaned_by TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Insert a real booking record (like the user's booking)
            conn.execute("""
                INSERT INTO bookings (id, room_no, guest_name, days, food_plan, check_in_datetime, status)
                VALUES (7, '102', 'Mohd Shahid', 3, 'VIP', '10-11-2026 10:00 AM', 'Booked')
            """)
            # Insert housekeeping room
            conn.execute("""
                INSERT INTO housekeeping (room_no, status, last_cleaned_by)
                VALUES ('102', 'Clean', 'Housekeeper')
            """)
            # Insert legacy demo_admin (S001) with older demo hash
            legacy_salt, legacy_hash = hash_password('TajDemo@2026')
            conn.execute("""
                INSERT INTO staff (staff_id, name, designation, contact, login_username, login_password, password_salt, is_demo)
                VALUES ('S001', 'Demo Administrator', 'Manager', '9900000001', 'demo_admin', ?, ?, 1)
            """, (legacy_hash, legacy_salt))
            # Insert receptionist (S002)
            staff_salt, staff_hash = hash_password('StaffPass@2026')
            conn.execute("""
                INSERT INTO staff (staff_id, name, designation, contact, login_username, login_password, password_salt, is_demo)
                VALUES ('S002', 'Demo Receptionist', 'Receptionist', '9900000002', 'demo_staff', ?, ?, 1)
            """, (staff_hash, staff_salt))
            conn.commit()
            conn.close()

            # Now start app with this legacy database
            class LegacyTestConfig(Config):
                TESTING = True
                IS_PRODUCTION = False
                DATABASE_PATH = temp_db
                SECRET_KEY = 'test-secret-key-32-characters-long!!'
                DEMO_MODE = True
                WTF_CSRF_ENABLED = False

            legacy_app = create_app(LegacyTestConfig)
            legacy_client = legacy_app.test_client()

            # Verify that bookings are 100% preserved
            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row
            booking_row = conn.execute("SELECT * FROM bookings WHERE id = 7").fetchone()
            self.assertIsNotNone(booking_row)
            self.assertEqual(booking_row['guest_name'], 'Mohd Shahid')
            self.assertEqual(booking_row['room_no'], '102')

            # Verify that housekeeping is 100% preserved
            hk_row = conn.execute("SELECT * FROM housekeeping WHERE room_no = '102'").fetchone()
            self.assertIsNotNone(hk_row)
            self.assertEqual(hk_row['status'], 'Clean')

            # Verify that S001 is now migrated to 'admin' with is_demo = 0
            admin_row = conn.execute("SELECT * FROM staff WHERE staff_id = 'S001'").fetchone()
            self.assertEqual(admin_row['login_username'], 'admin')
            self.assertEqual(admin_row['designation'], 'Manager')
            self.assertEqual(admin_row['is_demo'], 0)
            conn.close()

            # Verify that admin can log in with development credentials
            csrf_resp = legacy_client.get('/api/csrf-token')
            csrf = csrf_resp.get_json()['csrf_token']
            login_resp = legacy_client.post('/api/auth/login', json={
                'username': 'admin',
                'password': DEV_ADMIN_PASSWORD_FALLBACK
            }, headers={'X-CSRF-Token': csrf, 'Content-Type': 'application/json'})
            self.assertEqual(login_resp.status_code, 200)
            self.assertTrue(login_resp.get_json()['user']['is_admin'])

            # Verify that receptionist demo still logs in
            rec_resp = legacy_client.post('/api/auth/demo-login', json={'role': 'receptionist'},
                                          headers={'X-CSRF-Token': csrf, 'Content-Type': 'application/json'})
            self.assertEqual(rec_resp.status_code, 200)
            self.assertEqual(rec_resp.get_json()['user']['designation'], 'Receptionist')
        finally:
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except OSError:
                    pass

    # --- 15. Dashboard, Reporting Periods, and CLI Recovery Tests ---
    def test_dashboard_stats_and_revenue_reporting_periods(self):
        """Verifies dashboard metrics, revenue breakdowns across Daily/Weekly/Monthly/All-Time, and booking history."""
        self.login_demo_receptionist()

        # 1. Dashboard stats
        dash_res = self.client.get('/api/dashboard/stats')
        self.assertEqual(dash_res.status_code, 200)
        d_data = dash_res.get_json()
        self.assertEqual(d_data['total_rooms'], 10)
        self.assertIn('available_count', d_data)
        self.assertIn('occupied_count', d_data)
        self.assertIn('needs_cleaning_count', d_data)
        self.assertIn('revenue', d_data)
        self.assertIn('server_time', d_data)

        # 2. Revenue reports for all 4 periods
        for period in ('Daily', 'Weekly', 'Monthly', 'All Time'):
            rev_res = self.client.get(f'/api/revenue/report?period={period}')
            self.assertEqual(rev_res.status_code, 200)
            r_data = rev_res.get_json()
            self.assertTrue(r_data['success'])
            self.assertEqual(r_data['period'], period)
            self.assertIn('total_revenue', r_data)
            self.assertIn('summary', r_data)
            self.assertIn('report_text', r_data)
            self.assertIn('formatted', r_data)
            self.assertIn('Hotel Revenue Report', r_data['report_text'])

        # 3. Booking history
        hist_res = self.client.get('/api/bookings/history')
        self.assertEqual(hist_res.status_code, 200)
        h_data = hist_res.get_json()
        self.assertIn('history', h_data)
        self.assertIsInstance(h_data['history'], list)

    def test_manage_admin_cli_recovery_utility(self):
        """Proves manage_admin CLI utility can inspect status and recover administrator credentials safely."""
        from manage_admin import show_status, recover_admin

        temp_fd, temp_db = tempfile.mkstemp(suffix='.db')
        os.close(temp_fd)

        try:
            # Initialize empty database
            conn = sqlite3.connect(temp_db)
            conn.execute("""
                CREATE TABLE staff (
                    staff_id TEXT PRIMARY KEY, name TEXT NOT NULL, designation TEXT NOT NULL,
                    contact TEXT NOT NULL, login_username TEXT UNIQUE NOT NULL, login_password TEXT NOT NULL,
                    password_salt TEXT, is_demo INTEGER DEFAULT 0, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE bookings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, room_no TEXT NOT NULL, guest_name TEXT NOT NULL,
                    days INTEGER NOT NULL, food_plan TEXT NOT NULL, check_in_datetime TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Booked', checkout_datetime TEXT, room_charge REAL,
                    food_charge REAL, subtotal REAL, gst_amount REAL, total_amount REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE housekeeping (
                    room_no TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'Clean',
                    last_cleaned_by TEXT, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Add existing booking to verify preservation
            conn.execute("INSERT INTO bookings (room_no, guest_name, days, food_plan, check_in_datetime) VALUES ('101', 'Test Guest', 2, 'VIP', '10-11-2026')")
            conn.commit()
            conn.close()

            # Run recover_admin on isolated db
            recover_admin(db_path=temp_db, explicit_password='AdminSafePassword#2026')

            # Verify admin was created and booking was preserved
            conn = sqlite3.connect(temp_db)
            conn.row_factory = sqlite3.Row
            admin = conn.execute("SELECT * FROM staff WHERE login_username = 'admin'").fetchone()
            self.assertIsNotNone(admin)
            self.assertEqual(admin['designation'], 'Manager')
            self.assertTrue(verify_password('AdminSafePassword#2026', admin['login_password'], admin['password_salt']))

            b_count = conn.execute("SELECT COUNT(*) AS c FROM bookings").fetchone()['c']
            self.assertEqual(b_count, 1)
            conn.close()
        finally:
            if os.path.exists(temp_db):
                try:
                    os.remove(temp_db)
                except OSError:
                    pass

    def test_demo_login_missing_account_does_not_reseed_or_overwrite_admin(self):
        """Proves missing demo_staff does not trigger reseeding or modify administrator and bookings."""
        # Record baseline admin credentials and booking state
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        orig_admin = conn.execute("SELECT * FROM staff WHERE login_username = 'admin'").fetchone()
        self.assertIsNotNone(orig_admin)
        orig_bookings = conn.execute("SELECT id, room_no, guest_name FROM bookings ORDER BY id").fetchall()

        # Delete demo_staff
        conn.execute("DELETE FROM staff WHERE login_username = 'demo_staff'")
        conn.commit()
        conn.close()

        # Attempt demo login
        csrf = self.get_csrf()
        resp = self.client.post('/api/auth/demo-login', json={'role': 'receptionist'}, headers={
            'X-CSRF-Token': csrf,
            'Content-Type': 'application/json'
        })
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertFalse(data['success'])
        self.assertIn("Demo receptionist account is unavailable", data['error'])

        # Verify database was NOT mutated
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        demo_staff = conn.execute("SELECT * FROM staff WHERE login_username = 'demo_staff'").fetchone()
        self.assertIsNone(demo_staff, "demo_staff must NOT be automatically reseeded on failed demo login")

        curr_admin = conn.execute("SELECT * FROM staff WHERE login_username = 'admin'").fetchone()
        self.assertEqual(curr_admin['login_password'], orig_admin['login_password'], "Admin password must not change")
        self.assertEqual(curr_admin['password_salt'], orig_admin['password_salt'], "Admin salt must not change")

        curr_bookings = conn.execute("SELECT id, room_no, guest_name FROM bookings ORDER BY id").fetchall()
        self.assertEqual(len(curr_bookings), len(orig_bookings), "Bookings must not be deleted or modified")
        for b_orig, b_curr in zip(orig_bookings, curr_bookings):
            self.assertEqual(b_orig['id'], b_curr['id'])
            self.assertEqual(b_orig['room_no'], b_curr['room_no'])
            self.assertEqual(b_orig['guest_name'], b_curr['guest_name'])
        conn.close()

    def test_setup_token_enforcement(self):
        """Proves SETUP_TOKEN is strictly enforced via constant-time verification for admin setup."""
        temp_dir = tempfile.TemporaryDirectory()
        try:
            token_db = os.path.join(temp_dir.name, 'token_test.db')
            test_token = "secure-render-setup-token-998877"

            class TokenConfig(Config):
                TESTING = True
                DATABASE_PATH = token_db
                SECRET_KEY = "test-token-secret-key-32-chars-long"
                SETUP_TOKEN = test_token
                DEMO_MODE = True
                WTF_CSRF_ENABLED = False

            token_app = create_app(TokenConfig)

            # Clear staff table so first-time setup is active (0 staff)
            conn = sqlite3.connect(token_db)
            conn.execute("DELETE FROM staff")
            conn.commit()
            conn.close()

            client = token_app.test_client()
            csrf = self.get_csrf(client)
            base_headers = {'X-CSRF-Token': csrf, 'Content-Type': 'application/json'}

            setup_payload = {
                "name": "Token Admin",
                "contact": "9876543210",
                "username": "tokenadmin",
                "password": "TokenPassword@2026",
                "confirm_password": "TokenPassword@2026"
            }

            # 1. Missing token -> 403
            resp = client.post('/api/auth/setup', json=setup_payload, headers=base_headers)
            self.assertEqual(resp.status_code, 403)
            self.assertIn("Invalid setup token", resp.get_json()['error'])

            # 2. Invalid token in header -> 403
            h_invalid = dict(base_headers, **{'X-Setup-Token': 'wrong-token'})
            resp = client.post('/api/auth/setup', json=setup_payload, headers=h_invalid)
            self.assertEqual(resp.status_code, 403)
            self.assertIn("Invalid setup token", resp.get_json()['error'])

            # 3. Invalid token in JSON body -> 403
            invalid_body = dict(setup_payload, setup_token='wrong-token-body')
            resp = client.post('/api/auth/setup', json=invalid_body, headers=base_headers)
            self.assertEqual(resp.status_code, 403)
            self.assertIn("Invalid setup token", resp.get_json()['error'])

            # 4. Valid token in header -> 200
            h_valid = dict(base_headers, **{'X-Setup-Token': test_token})
            resp = client.post('/api/auth/setup', json=setup_payload, headers=h_valid)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.get_json()['success'])

            # 5. Subsequent attempt after staff exists -> 403 (already completed)
            resp = client.post('/api/auth/setup', json=setup_payload, headers=h_valid)
            self.assertEqual(resp.status_code, 403)
            self.assertIn("Setup has already been completed", resp.get_json()['error'])

            # 6. Valid token via JSON body on a fresh database
            token_db2 = os.path.join(temp_dir.name, 'token_test2.db')
            class TokenConfig2(Config):
                TESTING = True
                DATABASE_PATH = token_db2
                SECRET_KEY = "test-token-secret-key-32-chars-long"
                SETUP_TOKEN = test_token
                DEMO_MODE = True
                WTF_CSRF_ENABLED = False

            token_app2 = create_app(TokenConfig2)
            conn2 = sqlite3.connect(token_db2)
            conn2.execute("DELETE FROM staff")
            conn2.commit()
            conn2.close()

            client2 = token_app2.test_client()
            csrf2 = self.get_csrf(client2)
            body_valid = dict(setup_payload, setup_token=test_token)
            resp2 = client2.post('/api/auth/setup', json=body_valid, headers={'X-CSRF-Token': csrf2, 'Content-Type': 'application/json'})
            self.assertEqual(resp2.status_code, 200)
            self.assertTrue(resp2.get_json()['success'])
        finally:
            temp_dir.cleanup()

    def test_ephemeral_database_fresh_startup_and_recovery(self):
        """Proves ephemeral database initializes cleanly on fresh container startup or restart."""
        temp_dir = tempfile.TemporaryDirectory()
        try:
            ephemeral_db = os.path.join(temp_dir.name, 'fresh_ephemeral.db')
            self.assertFalse(os.path.exists(ephemeral_db), "Database file must not exist before initialization")

            class EphemeralConfig(Config):
                TESTING = True
                DATABASE_PATH = ephemeral_db
                SECRET_KEY = "ephemeral-test-secret-key-32-chars"
                DEMO_MODE = True
                WTF_CSRF_ENABLED = False

            app = create_app(EphemeralConfig)
            self.assertTrue(os.path.exists(ephemeral_db), "Database file must be automatically created")

            # Verify tables and seed data
            conn = sqlite3.connect(ephemeral_db)
            conn.row_factory = sqlite3.Row
            tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            self.assertIn('staff', tables)
            self.assertIn('bookings', tables)
            self.assertIn('housekeeping', tables)

            admin = conn.execute("SELECT * FROM staff WHERE login_username = 'admin'").fetchone()
            self.assertIsNotNone(admin)
            demo_user = conn.execute("SELECT * FROM staff WHERE login_username = 'demo_staff'").fetchone()
            self.assertIsNotNone(demo_user)
            conn.close()

            # Verify /health endpoint returns healthy
            client = app.test_client()
            resp = client.get('/health')
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_json()['status'], 'healthy')
        finally:
            temp_dir.cleanup()

    def test_first_time_admin_setup_password_validation_and_rejection(self):
        """Proves first-time setup enforces minimum 10 chars, rejects whitespace/weak passwords, and accepts valid credentials."""
        temp_dir = tempfile.TemporaryDirectory()
        try:
            setup_db = os.path.join(temp_dir.name, 'setup_val_test.db')

            class SetupConfig(Config):
                TESTING = True
                DATABASE_PATH = setup_db
                SECRET_KEY = "setup-val-test-secret-key-32chars"
                DEMO_MODE = False
                WTF_CSRF_ENABLED = False

            setup_app = create_app(SetupConfig)

            # Ensure staff table is empty so setup is genuinely available
            conn = sqlite3.connect(setup_db)
            conn.execute("DELETE FROM staff")
            conn.commit()
            conn.close()

            client = setup_app.test_client()
            csrf = self.get_csrf(client)
            headers = {'X-CSRF-Token': csrf, 'Content-Type': 'application/json'}

            # 1. Short password (< 10 characters) is rejected
            short_payload = {
                "name": "Setup Admin",
                "contact": "9876543210",
                "username": "setupadmin",
                "password": "Short#1",
                "confirm_password": "Short#1"
            }
            resp = client.post('/api/auth/setup', json=short_payload, headers=headers)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("at least 10 characters", resp.get_json()['error'])

            # Also verify via /api/setup/admin route
            resp = client.post('/api/setup/admin', json=short_payload, headers=headers)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("at least 10 characters", resp.get_json()['error'])

            # 2. Whitespace-only password is rejected
            ws_payload = {
                "name": "Setup Admin",
                "contact": "9876543210",
                "username": "setupadmin",
                "password": "          ",
                "confirm_password": "          "
            }
            resp = client.post('/api/auth/setup', json=ws_payload, headers=headers)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("blank or whitespace", resp.get_json()['error'])

            # 3. Known weak / default passwords are rejected
            weak_passwords = [
                'AdminSecure@2026',
                'DevAdmin@LocalOnly#2026',
                'administrator',
                'password',
                'admin123',
                '12345678'
            ]
            for weak_pw in weak_passwords:
                weak_payload = {
                    "name": "Setup Admin",
                    "contact": "9876543210",
                    "username": "setupadmin",
                    "password": weak_pw,
                    "confirm_password": weak_pw
                }
                resp = client.post('/api/auth/setup', json=weak_payload, headers=headers)
                self.assertEqual(resp.status_code, 400)
                self.assertIn("too weak or commonly used", resp.get_json()['error'])

            # 4. Mismatched confirmation is rejected
            mismatch_payload = {
                "name": "Setup Admin",
                "contact": "9876543210",
                "username": "setupadmin",
                "password": "ValidStrongPass#2026",
                "confirm_password": "DifferentPass#2026"
            }
            resp = client.post('/api/auth/setup', json=mismatch_payload, headers=headers)
            self.assertEqual(resp.status_code, 400)
            self.assertIn("do not match", resp.get_json()['error'])

            # 5. Valid strong password is accepted when setup is available
            valid_payload = {
                "name": "Setup Admin",
                "contact": "9876543210",
                "username": "setupadmin",
                "password": "ValidStrongPass#2026",
                "confirm_password": "ValidStrongPass#2026"
            }
            resp = client.post('/api/auth/setup', json=valid_payload, headers=headers)
            self.assertEqual(resp.status_code, 200)
            self.assertTrue(resp.get_json()['success'])
            self.assertIn("created successfully", resp.get_json()['message'])

            # Verify in database: secure hash and unique salt created, plaintext not stored
            conn = sqlite3.connect(setup_db)
            conn.row_factory = sqlite3.Row
            admin = conn.execute("SELECT * FROM staff WHERE login_username = 'setupadmin'").fetchone()
            self.assertIsNotNone(admin)
            self.assertEqual(admin['designation'], 'Manager')
            self.assertEqual(len(admin['password_salt']), 32)
            self.assertEqual(len(admin['login_password']), 64)
            self.assertNotEqual(admin['login_password'], "ValidStrongPass#2026")
            self.assertTrue(verify_password("ValidStrongPass#2026", admin['login_password'], admin['password_salt']))
            conn.close()

            # 6. Subsequent setup attempts remain rejected once staff exists
            resp = client.post('/api/auth/setup', json=valid_payload, headers=headers)
            self.assertEqual(resp.status_code, 403)
            self.assertIn("Setup has already been completed", resp.get_json()['error'])
        finally:
            temp_dir.cleanup()

    def test_rejected_setup_attempts_preserve_existing_records(self):
        """Proves rejected setup attempts do not alter existing administrator, staff, or bookings."""
        temp_dir = tempfile.TemporaryDirectory()
        try:
            preserve_db = os.path.join(temp_dir.name, 'preserve_test.db')

            class PreserveConfig(Config):
                TESTING = True
                DATABASE_PATH = preserve_db
                SECRET_KEY = "preserve-test-secret-key-32chars"
                DEMO_MODE = True
                WTF_CSRF_ENABLED = False

            app = create_app(PreserveConfig)

            # Record initial snapshot of database
            conn = sqlite3.connect(preserve_db)
            conn.row_factory = sqlite3.Row
            initial_staff = [dict(row) for row in conn.execute("SELECT staff_id, name, designation, login_username, login_password, password_salt FROM staff ORDER BY staff_id").fetchall()]
            initial_bookings = [dict(row) for row in conn.execute("SELECT id, room_no, guest_name, days, status FROM bookings ORDER BY id").fetchall()]
            initial_housekeeping = [dict(row) for row in conn.execute("SELECT room_no, status FROM housekeeping ORDER BY room_no").fetchall()]
            conn.close()

            self.assertGreater(len(initial_staff), 0)
            self.assertGreater(len(initial_bookings), 0)

            client = app.test_client()
            csrf = self.get_csrf(client)
            headers = {'X-CSRF-Token': csrf, 'Content-Type': 'application/json'}

            # Attempt rejected setup calls
            rejected_payloads = [
                {"name": "Attacker", "contact": "0000000000", "username": "admin", "password": "Short#1", "confirm_password": "Short#1"},
                {"name": "Attacker", "contact": "0000000000", "username": "admin", "password": "password", "confirm_password": "password"},
                {"name": "Attacker", "contact": "0000000000", "username": "admin", "password": "          ", "confirm_password": "          "},
                {"name": "Attacker", "contact": "0000000000", "username": "admin", "password": "ValidPass#2026", "confirm_password": "Mismatch#2026"},
                {"name": "Attacker", "contact": "0000000000", "username": "newadmin", "password": "ValidStrongPass#2026", "confirm_password": "ValidStrongPass#2026"}
            ]

            for payload in rejected_payloads:
                r1 = client.post('/api/auth/setup', json=payload, headers=headers)
                self.assertIn(r1.status_code, (400, 403))
                r2 = client.post('/api/setup/admin', json=payload, headers=headers)
                self.assertIn(r2.status_code, (400, 403))

            # Verify snapshot is 100% identical
            conn = sqlite3.connect(preserve_db)
            conn.row_factory = sqlite3.Row
            current_staff = [dict(row) for row in conn.execute("SELECT staff_id, name, designation, login_username, login_password, password_salt FROM staff ORDER BY staff_id").fetchall()]
            current_bookings = [dict(row) for row in conn.execute("SELECT id, room_no, guest_name, days, status FROM bookings ORDER BY id").fetchall()]
            current_housekeeping = [dict(row) for row in conn.execute("SELECT room_no, status FROM housekeeping ORDER BY room_no").fetchall()]
            conn.close()

            self.assertEqual(initial_staff, current_staff, "Staff records must remain strictly unchanged")
            self.assertEqual(initial_bookings, current_bookings, "Bookings must remain strictly unchanged")
            self.assertEqual(initial_housekeeping, current_housekeeping, "Housekeeping records must remain strictly unchanged")
        finally:
            temp_dir.cleanup()

if __name__ == '__main__':
    unittest.main()
