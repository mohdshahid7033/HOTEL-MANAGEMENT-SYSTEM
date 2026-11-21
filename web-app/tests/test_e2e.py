"""
End-to-end user journey and static asset delivery verification tests.
Project Owner & Sole Developer: Mohd Shahid Moin Uddin
"""

import os
import sys
import tempfile
import unittest

# Ensure web-app directory is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from config import Config
from database import reset_to_clean_demo, DEV_ADMIN_PASSWORD_FALLBACK

class E2EUserJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.temp_db_fd)

        class TestConfig(Config):
            TESTING = True
            DATABASE_PATH = self.temp_db_path
            SECRET_KEY = 'e2e-test-secret-key-32-chars-long!!'
            DEMO_MODE = True
            WTF_CSRF_ENABLED = False

        self.app = create_app(TestConfig)
        self.client = self.app.test_client()

        with self.app.app_context():
            reset_to_clean_demo(self.app)

    def tearDown(self):
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except OSError:
                pass

    def get_csrf(self):
        res = self.client.get('/api/csrf-token')
        return res.get_json()['csrf_token']

    def test_01_static_assets_and_html_shell(self):
        """Verifies that the HTML shell and all static CSS/JS assets are properly served with accurate sole-developer credits."""
        # Check root page
        with self.client.get('/') as res:
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn("Taj Banjara Hotel", html)
            self.assertIn("Mohd Shahid Moin Uddin", html, "Exact name 'Mohd Shahid Moin Uddin' must appear in HTML")
            self.assertNotIn("Mohd Shahid Moinuddin", html, "Incorrect spelling 'Mohd Shahid Moinuddin' must not appear in HTML")
            self.assertNotIn("Abaid Khan", html, "Abaid Khan must not be credited as developer")
            self.assertNotIn("Demo Administrator", html, "Public administrator demo button must be removed")
            self.assertIn("Demo Receptionist", html)
            self.assertIn("view-welcome", html)
            self.assertIn("view-dashboard", html)

        # Check CSS with proper context management to ensure file descriptor closure
        with self.client.get('/static/css/style.css') as res_css:
            self.assertEqual(res_css.status_code, 200)
            css = res_css.get_data(as_text=True)
            self.assertIn("#1A1A1A", css)
            self.assertIn("#FFD700", css)

        # Check JS with proper context management
        with self.client.get('/static/js/api.js') as res_api:
            self.assertEqual(res_api.status_code, 200)
            self.assertIn("window.API", res_api.get_data(as_text=True))

        with self.client.get('/static/js/app.js') as res_app:
            self.assertEqual(res_app.status_code, 200)
            self.assertIn("init()", res_app.get_data(as_text=True))

        # Check Health
        with self.client.get('/health') as res_health:
            self.assertEqual(res_health.status_code, 200)
            health_json = res_health.get_json()
            self.assertIn(health_json['status'], ('healthy', 'ok'))

    def test_02_full_receptionist_and_guest_lifecycle(self):
        """
        Simulates complete user journey:
        1. Public demo login as restricted Receptionist (no admin credentials).
        2. Verify Receptionist is strictly blocked from Administrator endpoints.
        3. Receptionist executes guest booking, room status, search, checkout, and housekeeping.
        4. Private administrator logs in via authenticated credentials to manage staff.
        5. Logout and verify unauthenticated guards.
        """
        csrf = self.get_csrf()

        # Step 1: Public demo login as Receptionist
        # Rejects public attempts to obtain admin demo access
        blocked_demo_admin = self.client.post('/api/auth/demo-login', json={
            'role': 'admin'
        }, headers={'X-CSRF-Token': csrf})
        self.assertEqual(blocked_demo_admin.status_code, 403)
        self.assertIn("Administrator demo login is disabled", blocked_demo_admin.get_json()['error'])

        # Successful public receptionist demo login
        login_res = self.client.post('/api/auth/demo-login', json={
            'role': 'receptionist'
        }, headers={'X-CSRF-Token': csrf})
        self.assertEqual(login_res.status_code, 200)
        user_info = login_res.get_json()['user']
        self.assertEqual(user_info['username'], 'demo_staff')
        self.assertFalse(user_info['is_admin'])

        # Step 2: Verify Receptionist is strictly blocked from Admin endpoints
        blocked_staff_get = self.client.get('/api/staff')
        self.assertEqual(blocked_staff_get.status_code, 403)

        blocked_staff_post = self.client.post('/api/staff', json={
            'name': 'Hacker', 'designation': 'Manager', 'contact': '111', 'username': 'hacker', 'password': '123'
        }, headers={'X-CSRF-Token': csrf})
        self.assertEqual(blocked_staff_post.status_code, 403)

        blocked_reset = self.client.post('/api/demo/reset', headers={'X-CSRF-Token': csrf})
        self.assertEqual(blocked_reset.status_code, 403)

        # Step 3: Query next available room as Receptionist
        next_room_res = self.client.get('/api/rooms/next-available')
        self.assertEqual(next_room_res.status_code, 200)
        next_room = next_room_res.get_json()
        self.assertTrue(next_room['available'])
        target_room = next_room['room_no']

        # Step 4: Book room for 3 days with VIP food
        book_res = self.client.post('/api/bookings', json={
            'room_no': target_room,
            'guest_name': 'Mr. Vikram Malhotra',
            'days': 3,
            'food_option': 'VIP'
        }, headers={'X-CSRF-Token': csrf})
        self.assertEqual(book_res.status_code, 200)
        booking_data = book_res.get_json()['booking']
        self.assertEqual(booking_data['room_no'], target_room)
        self.assertEqual(booking_data['guest_name'], 'Mr. Vikram Malhotra')

        # Step 5: Search guest
        search_res = self.client.get('/api/bookings/search?q=Vikram')
        self.assertEqual(search_res.status_code, 200)
        search_results = search_res.get_json()['results']
        self.assertTrue(any(r['guest_name'] == 'Mr. Vikram Malhotra' for r in search_results))

        # Step 6: Check Room Status Overview
        rooms_res = self.client.get('/api/rooms')
        self.assertEqual(rooms_res.status_code, 200)
        rooms = rooms_res.get_json()['rooms']
        booked_card = next(r for r in rooms if r['room_no'] == target_room)
        self.assertIn(booked_card['status'], ('Booked', 'Occupied'))
        self.assertEqual(booked_card['guest_name'], 'Mr. Vikram Malhotra')

        # Step 7: Calculate Bill Preview
        # Subtotal: (3 * 15000) + (3 * 1000) = 48000
        # GST 18%: 48000 * 0.18 = 8640
        # Total: 48000 + 8640 = 56640
        preview_res = self.client.get(f'/api/checkout/preview/{target_room}')
        self.assertEqual(preview_res.status_code, 200)
        bill = preview_res.get_json()['bill']
        self.assertEqual(bill['room_cost'], 45000)
        self.assertEqual(bill['food_cost'], 3000)
        self.assertEqual(bill['subtotal'], 48000)
        self.assertEqual(bill['gst_amount'], 8640)
        self.assertEqual(bill['total_cost'], 56640)

        # Step 8: Complete Checkout
        checkout_res = self.client.post(f'/api/checkout/{target_room}', headers={'X-CSRF-Token': csrf})
        self.assertEqual(checkout_res.status_code, 200)
        checkout_data = checkout_res.get_json()
        self.assertTrue(checkout_data['success'])
        self.assertEqual(checkout_data['bill']['total_cost'], 56640)

        # Step 9: Verify Housekeeping state
        hk_res = self.client.get('/api/housekeeping')
        self.assertEqual(hk_res.status_code, 200)
        hk_rooms = hk_res.get_json()['rooms']
        target_hk = next(r for r in hk_rooms if r['room_no'] == target_room)
        self.assertEqual(target_hk['status'], 'Needs Cleaning')

        # Cycle 1: Needs Cleaning -> In Progress
        cycle1 = self.client.post(f'/api/housekeeping/cycle/{target_room}', headers={'X-CSRF-Token': csrf})
        self.assertEqual(cycle1.status_code, 200)
        self.assertEqual(cycle1.get_json()['new_status'], 'In Progress')

        # Cycle 2: In Progress -> Clean
        cycle2 = self.client.post(f'/api/housekeeping/cycle/{target_room}', headers={'X-CSRF-Token': csrf})
        self.assertEqual(cycle2.status_code, 200)
        self.assertEqual(cycle2.get_json()['new_status'], 'Clean')

        # Step 10: Verify Revenue Report includes the checkout
        rev_res = self.client.get('/api/revenue/report?period=All Time')
        self.assertEqual(rev_res.status_code, 200)
        rev = rev_res.get_json()
        self.assertGreaterEqual(rev['total_revenue'], 56640)
        self.assertIn("56,640", rev['report_text'])

        # Receptionist logs out
        self.client.post('/api/auth/logout', headers={'X-CSRF-Token': csrf})

        # Step 11: Authorized Administrator logs in via standard credentials
        csrf = self.get_csrf()
        admin_login = self.client.post('/api/auth/login', json={
            'username': 'admin',
            'password': DEV_ADMIN_PASSWORD_FALLBACK
        }, headers={'X-CSRF-Token': csrf})
        self.assertEqual(admin_login.status_code, 200)
        self.assertTrue(admin_login.get_json()['user']['is_admin'])

        # Administrator can access Staff Management
        staff_list_res = self.client.get('/api/staff')
        self.assertEqual(staff_list_res.status_code, 200)

        # Administrator adds new staff
        add_staff_res = self.client.post('/api/staff', json={
            'name': 'Ayesha Siddiqui',
            'designation': 'Receptionist',
            'contact': '9876543210',
            'username': 'ayesha_s',
            'password': 'ReceptionPass@2026'
        }, headers={'X-CSRF-Token': csrf})
        self.assertIn(add_staff_res.status_code, (200, 201))
        staff_id = add_staff_res.get_json()['staff_id']

        # Administrator updates staff details
        update_staff_res = self.client.put(f'/api/staff/{staff_id}', json={
            'name': 'Ayesha Siddiqui Khan',
            'designation': 'Senior Receptionist',
            'contact': '9876543211'
        }, headers={'X-CSRF-Token': csrf})
        self.assertEqual(update_staff_res.status_code, 200)

        # Step 12: Logout
        logout_res = self.client.post('/api/auth/logout', headers={'X-CSRF-Token': csrf})
        self.assertEqual(logout_res.status_code, 200)

        # Verify unauthenticated call to staff is blocked with 401
        blocked_res = self.client.get('/api/staff')
        self.assertEqual(blocked_res.status_code, 401)

if __name__ == '__main__':
    unittest.main()
