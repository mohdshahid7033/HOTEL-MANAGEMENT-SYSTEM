import os
import hmac
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, g

from config import Config
from database import get_db, close_db, init_db, reset_to_clean_demo, DISALLOWED_ADMIN_PASSWORDS
from auth import (
    hash_password,
    verify_password,
    get_or_create_csrf_token,
    verify_csrf,
    is_admin,
    login_required,
    admin_required
)
from services.booking_service import (
    get_available_rooms,
    get_room_status_overview,
    book_room,
    calculate_bill_preview,
    complete_checkout,
    search_guests,
    get_active_booking_for_room,
    update_booking,
    get_booking_history
)
from services.housekeeping_service import (
    get_housekeeping_status,
    cycle_room_status
)
from services.report_service import get_complete_revenue_report
from services.staff_service import (
    get_all_staff,
    add_staff_member,
    update_staff_member
)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Teardown database connections
    app.teardown_appcontext(close_db)

    # Auto-initialize database schema on startup
    with app.app_context():
        init_db(app)

    # --- CSRF and Session Security Middleware ---
    @app.before_request
    def handle_csrf_and_security():
        # Exempt safe methods and static/health routes from CSRF token validation
        if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
            # Allow health or specific routes if needed
            if request.path in ('/health',):
                return None
            if not verify_csrf():
                return jsonify({
                    "success": False,
                    "error": "Invalid or missing CSRF token. Please refresh and try again."
                }), 403

    @app.after_request
    def set_security_headers(response):
        # Set anti-clickjacking and browser defense headers
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # Provide CSRF token in header for API clients
        token = get_or_create_csrf_token()
        response.headers['X-CSRF-Token'] = token
        return response

    # --- System & Health Endpoints ---
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health-check endpoint for Render, load balancers, and monitoring."""
        return jsonify({
            "status": "healthy",
            "service": "taj-banjara-hotel-management",
            "timestamp": datetime.now().isoformat(),
            "demo_mode": app.config.get('DEMO_MODE', True)
        }), 200

    @app.route('/api/csrf-token', methods=['GET'])
    def get_csrf():
        """Returns the CSRF token for the session."""
        token = get_or_create_csrf_token()
        return jsonify({"csrf_token": token})

    @app.route('/api/system/info', methods=['GET'])
    @app.route('/api/auth/status', methods=['GET'])
    def system_info():
        """Returns hotel parameters and current user state."""
        db = get_db()
        cur = db.execute("SELECT COUNT(*) AS count FROM staff")
        staff_count = cur.fetchone()['count']

        user_info = None
        if session.get('user_id'):
            user_info = {
                "user_id": session.get('user_id'),
                "name": session.get('user_name'),
                "designation": session.get('user_designation'),
                "username": session.get('user_username'),
                "is_admin": is_admin(session.get('user_designation'))
            }

        return jsonify({
            "hotel_name": "👑 Taj Banjara Hotel",
            "developer": "Mohd Shahid Moin Uddin",
            "sole_developer": True,
            "room_rate": app.config['ROOM_RATE'],
            "food_prices": app.config['FOOD_PRICES'],
            "gst_rate": app.config['GST_RATE'],
            "total_rooms": len(app.config['ROOMS']),
            "needs_setup": (staff_count == 0),
            "demo_mode": app.config.get('DEMO_MODE', True),
            "current_user": user_info,
            "logged_in": bool(session.get('user_id')),
            "user": user_info,
            "csrf_token": get_or_create_csrf_token()
        })

    # --- Authentication & First-Time Setup ---
    @app.route('/api/setup/admin', methods=['POST'])
    @app.route('/api/auth/setup', methods=['POST'])
    def setup_initial_admin():
        """
        Creates the first administrator account if no staff exists.
        Protected against public abuse once any account is created.
        """
        db = get_db()
        cur = db.execute("SELECT COUNT(*) AS count FROM staff")
        if cur.fetchone()['count'] > 0:
            return jsonify({
                "success": False,
                "error": "Setup has already been completed. Please log in with existing credentials."
            }), 403

        # If a setup token was configured, enforce it
        expected_token = app.config.get('SETUP_TOKEN')
        if expected_token:
            provided_token = request.headers.get('X-Setup-Token') or (request.json or {}).get('setup_token')
            if not provided_token or not hmac.compare_digest(str(provided_token), str(expected_token)):
                return jsonify({
                    "success": False,
                    "error": "Invalid setup token. Administrative setup is protected."
                }), 403

        data = request.get_json() or {}
        name = str(data.get('name', '')).strip()
        contact = str(data.get('contact', '')).strip()
        username = str(data.get('username', '')).strip()
        password = str(data.get('password', ''))
        confirm_password = str(data.get('confirm_password', ''))

        if not name or not contact or not username or not password or not confirm_password:
            return jsonify({"success": False, "error": "All fields are required."}), 400

        if not password.strip():
            return jsonify({"success": False, "error": "Password cannot be blank or whitespace-only."}), 400

        if password != confirm_password:
            return jsonify({"success": False, "error": "Passwords do not match."}), 400

        cleaned_password = password.strip()
        if cleaned_password.lower() in DISALLOWED_ADMIN_PASSWORDS:
            return jsonify({
                "success": False,
                "error": "Password is too weak or commonly used. Please choose a stronger password."
            }), 400

        if len(cleaned_password) < 10:
            return jsonify({
                "success": False,
                "error": "Password must be at least 10 characters long."
            }), 400

        salt, pw_hash = hash_password(cleaned_password)

        with db:
            db.execute("""
                INSERT INTO staff (staff_id, name, designation, contact, login_username, login_password, password_salt, is_demo)
                VALUES ('S001', ?, 'Manager', ?, ?, ?, ?, 0)
            """, (name, contact, username, pw_hash, salt))

        return jsonify({
            "success": True,
            "message": f"Administrator '{username}' created successfully! Please log in."
        })

    @app.route('/api/auth/login', methods=['POST'])
    def login():
        """Authenticates user, verifies PBKDF2 salt/hash, and creates session."""
        data = request.get_json() or {}
        username = str(data.get('username', '')).strip()
        password = str(data.get('password', '')).strip()

        if not username or not password:
            return jsonify({
                "success": False,
                "error": "Please enter both username and password."
            }), 400

        db = get_db()
        cur = db.execute("""
            SELECT staff_id, name, designation, contact, login_username, login_password, password_salt
            FROM staff
            WHERE login_username = ?
        """, (username,))
        user = cur.fetchone()

        if not user:
            return jsonify({
                "success": False,
                "error": "Invalid username or password."
            }), 401

        user = dict(user)
        is_valid = verify_password(password, user['login_password'], user.get('password_salt'))

        if not is_valid:
            return jsonify({
                "success": False,
                "error": "Invalid username or password."
            }), 401

        # Transparent upgrade to modern PBKDF2 if salt was missing
        if not user.get('password_salt'):
            new_salt, new_hash = hash_password(password)
            with db:
                db.execute("""
                    UPDATE staff
                    SET login_password = ?, password_salt = ?
                    WHERE staff_id = ?
                """, (new_hash, new_salt, user['staff_id']))

        # Set session
        session['user_id'] = user['staff_id']
        session['user_name'] = user['name']
        session['user_designation'] = user['designation']
        session['user_username'] = user['login_username']

        return jsonify({
            "success": True,
            "message": f"Authentication Successful. Welcome, {user['name']}.",
            "user": {
                "staff_id": user['staff_id'],
                "name": user['name'],
                "designation": user['designation'],
                "username": user['login_username'],
                "is_admin": is_admin(user['designation'])
            }
        })

    @app.route('/api/auth/demo-login', methods=['POST'])
    def demo_login():
        """
        Instant demo login for public portfolio demonstration.
        Strictly restricted to the Receptionist role. Administrator demo access is disabled.
        """
        if not app.config.get('DEMO_MODE', True):
            return jsonify({"success": False, "error": "Demo login is disabled in this environment."}), 403

        data = request.get_json() or {}
        role = str(data.get('role', 'receptionist')).lower()

        if role in ('admin', 'administrator', 'manager'):
            return jsonify({
                "success": False,
                "error": "Access Denied: Administrator demo login is disabled. Portfolio visitors are granted restricted receptionist access only."
            }), 403

        target_username = 'demo_staff'

        db = get_db()
        cur = db.execute("""
            SELECT staff_id, name, designation, contact, login_username
            FROM staff
            WHERE login_username = ?
        """, (target_username,))
        user = cur.fetchone()

        if not user:
            return jsonify({
                "success": False,
                "error": "Demo receptionist account is unavailable. Please log in with valid credentials."
            }), 404

        user = dict(user)
        session['user_id'] = user['staff_id']
        session['user_name'] = user['name']
        session['user_designation'] = user['designation']
        session['user_username'] = user['login_username']

        user_resp = {
            "staff_id": user['staff_id'],
            "name": user['name'],
            "designation": user['designation'],
            "username": user['login_username'],
            "is_admin": False
        }

        return jsonify({
            "success": True,
            "message": f"Logged in as Demo Receptionist ({user['name']}). Portfolio access is restricted.",
            "user": user_resp
        })

    @app.route('/api/auth/logout', methods=['POST'])
    def logout():
        """Clears user session."""
        session.clear()
        return jsonify({"success": True, "message": "Logged out successfully."})

    @app.route('/api/auth/me', methods=['GET'])
    def current_user():
        """Returns the currently logged in user, or 401 if unauthenticated."""
        if not session.get('user_id'):
            return jsonify({"authenticated": False, "user": None})
        return jsonify({
            "authenticated": True,
            "user": {
                "staff_id": session.get('user_id'),
                "name": session.get('user_name'),
                "designation": session.get('user_designation'),
                "username": session.get('user_username'),
                "is_admin": is_admin(session.get('user_designation'))
            }
        })

    # --- Dashboard Overview ---
    @app.route('/api/dashboard/stats', methods=['GET'])
    @login_required
    def dashboard_stats():
        """Returns aggregated hotel metrics for the dashboard view."""
        available_rooms = get_available_rooms()
        occupied_count = len(Config.ROOMS) - len(available_rooms)

        hk_status = get_housekeeping_status()
        needs_cleaning_count = sum(1 for h in hk_status if h['status'] == 'Needs Cleaning')

        rev_report = get_complete_revenue_report('Monthly')

        return jsonify({
            "total_rooms": len(Config.ROOMS),
            "available_count": len(available_rooms),
            "occupied_count": occupied_count,
            "needs_cleaning_count": needs_cleaning_count,
            "revenue": rev_report["summary"],
            "revenue_formatted": rev_report["formatted"],
            "server_time": datetime.now().strftime("%d-%m-%Y %I:%M %p")
        })

    # --- Room Booking & Status Endpoints ---
    @app.route('/api/rooms/available', methods=['GET'])
    @app.route('/api/rooms/next-available', methods=['GET'])
    @login_required
    def available_rooms_endpoint():
        """Returns rooms ready to be booked."""
        avail = get_available_rooms()
        next_room = avail[0] if avail else None
        return jsonify({
            "available_rooms": avail,
            "available": bool(avail),
            "room_no": next_room
        })

    @app.route('/api/rooms', methods=['GET'])
    @app.route('/api/rooms/status', methods=['GET'])
    @login_required
    def room_status_endpoint():
        """Returns all 10 rooms with current occupancy and guest details."""
        rooms = get_room_status_overview()
        available = get_available_rooms()
        return jsonify({
            "rooms": rooms,
            "available_rooms": available,
            "available_count": len(available),
            "occupied_count": len(Config.ROOMS) - len(available)
        })

    @app.route('/api/bookings', methods=['POST'])
    @login_required
    def create_booking_endpoint():
        """Creates a new room booking."""
        data = request.get_json() or {}
        food_plan = data.get('food_plan') or data.get('food_option', 'None')
        result = book_room(
            guest_name=data.get('guest_name'),
            days=data.get('days'),
            food_plan=food_plan,
            requested_room=data.get('room_no')
        )
        status_code = 200 if result["success"] else 400
        return jsonify(result), status_code

    @app.route('/api/bookings/history', methods=['GET'])
    @login_required
    def booking_history_endpoint():
        """Returns reverse-chronological list of all bookings."""
        history = get_booking_history()
        return jsonify({
            "history": history,
            "bookings": history
        })

    @app.route('/api/guests/search', methods=['GET'])
    @app.route('/api/bookings/search', methods=['GET'])
    @login_required
    def search_guests_endpoint():
        """Searches guests by name."""
        term = request.args.get('q', '')
        result = search_guests(term)
        res_list = result.get('results', [])
        return jsonify({
            "success": True,
            "results": res_list,
            "guests": res_list
        })

    @app.route('/api/bookings/active/<room_no>', methods=['GET'])
    @login_required
    def get_active_booking_endpoint(room_no):
        """Looks up an active stay for modification."""
        result = get_active_booking_for_room(room_no)
        status_code = 200 if result["success"] else 404
        return jsonify(result), status_code

    @app.route('/api/bookings/active/<room_no>', methods=['PUT'])
    @login_required
    def update_booking_endpoint(room_no):
        """Updates stay duration and dining choice for active reservation."""
        data = request.get_json() or {}
        new_food = data.get('food_plan') or data.get('food_option', 'None')
        result = update_booking(
            room_no=room_no,
            new_days=data.get('days'),
            new_food_plan=new_food
        )
        status_code = 200 if result["success"] else 400
        return jsonify(result), status_code

    # --- Checkout & Billing Endpoints ---
    @app.route('/api/checkout/preview/<room_no>', methods=['GET'])
    @login_required
    def checkout_preview_endpoint(room_no):
        """Generates itemized bill breakdown for a room."""
        result = calculate_bill_preview(room_no)
        status_code = 200 if result["success"] else 404
        if result.get("success"):
            bill = result["bill"]
            bill["total_cost"] = bill["total_amount"]
            bill["room_cost"] = bill["room_charge"]
            bill["food_cost"] = bill["food_charge"]
            booking = result["booking"]
            receipt_text = (
                f"=====================================================\n"
                f"            👑 TAJ BANJARA HOTEL 👑                  \n"
                f"                CHECKOUT RECEIPT                     \n"
                f"=====================================================\n"
                f" Room Number      : {booking.get('room_no')}\n"
                f" Guest Name       : {booking.get('guest_name')}\n"
                f" Stay Duration    : {bill.get('days')} Day(s)\n"
                f" Food Plan        : {bill.get('food_plan')}\n"
                f"-----------------------------------------------------\n"
                f" Room Charges     : ₹{bill['room_charge']:,.2f}\n"
                f" Dining Charges   : ₹{bill['food_charge']:,.2f}\n"
                f" Subtotal         : ₹{bill['subtotal']:,.2f}\n"
                f" GST (18%)        : ₹{bill['gst_amount']:,.2f}\n"
                f"-----------------------------------------------------\n"
                f" TOTAL AMOUNT     : ₹{bill['total_amount']:,.2f}\n"
                f"=====================================================\n"
                f"         Thank you for choosing Taj Banjara!         \n"
                f"====================================================="
            )
            result["receipt_text"] = receipt_text
        return jsonify(result), status_code

    @app.route('/api/checkout/<room_no>', methods=['POST'])
    @login_required
    def complete_checkout_endpoint(room_no):
        """Finalizes checkout and marks room for cleaning."""
        result = complete_checkout(room_no)
        status_code = 200 if result["success"] else 400
        if result.get("success") and "bill" in result:
            bill = result["bill"]
            bill["total_cost"] = bill["total_amount"]
            bill["room_cost"] = bill["room_charge"]
            bill["food_cost"] = bill["food_charge"]
            booking = result.get("booking", {})
            receipt_text = (
                f"=====================================================\n"
                f"            👑 TAJ BANJARA HOTEL 👑                  \n"
                f"                PAYMENT CONFIRMED                    \n"
                f"=====================================================\n"
                f" Room Number      : {booking.get('room_no')}\n"
                f" Guest Name       : {booking.get('guest_name')}\n"
                f" Stay Duration    : {bill.get('days')} Day(s)\n"
                f" Food Plan        : {bill.get('food_plan')}\n"
                f"-----------------------------------------------------\n"
                f" Room Charges     : ₹{bill['room_charge']:,.2f}\n"
                f" Dining Charges   : ₹{bill['food_charge']:,.2f}\n"
                f" Subtotal         : ₹{bill['subtotal']:,.2f}\n"
                f" GST (18%)        : ₹{bill['gst_amount']:,.2f}\n"
                f"-----------------------------------------------------\n"
                f" PAID IN FULL     : ₹{bill['total_amount']:,.2f}\n"
                f"=====================================================\n"
                f"         Thank you for choosing Taj Banjara!         \n"
                f"====================================================="
            )
            result["receipt_text"] = receipt_text
        return jsonify(result), status_code

    # --- Housekeeping Endpoints ---
    @app.route('/api/housekeeping', methods=['GET'])
    @login_required
    def housekeeping_list_endpoint():
        """Returns housekeeping status for all rooms."""
        hk = get_housekeeping_status()
        return jsonify({
            "housekeeping": hk,
            "rooms": hk
        })

    @app.route('/api/housekeeping/<room_no>/cycle', methods=['POST'])
    @app.route('/api/housekeeping/cycle/<room_no>', methods=['POST'])
    @login_required
    def housekeeping_cycle_endpoint(room_no):
        """Cycles room through Clean -> Needs Cleaning -> In Progress -> Clean."""
        current_staff = session.get('user_name', 'Staff')
        result = cycle_room_status(room_no, current_staff)
        status_code = 200 if result["success"] else 400
        return jsonify(result), status_code

    # --- Revenue Report Endpoints ---
    @app.route('/api/reports/revenue', methods=['GET'])
    @app.route('/api/revenue/report', methods=['GET'])
    @login_required
    def revenue_report_endpoint():
        """Returns hotel revenue breakdown (Daily, Weekly, Monthly, All Time)."""
        period = request.args.get('period', 'Monthly')
        result = get_complete_revenue_report(period)
        return jsonify({
            "success": True,
            "period": period,
            "summary": result["summary"],
            "formatted": result["formatted"],
            "report_text": result["report_text"],
            "total_revenue": result["total_revenue"]
        })

    # --- Staff Management Endpoints (Admin Only) ---
    @app.route('/api/staff', methods=['GET'])
    @admin_required
    def staff_list_endpoint():
        """Lists staff roster (Manager/Administrator only)."""
        return jsonify({"staff": get_all_staff()})

    @app.route('/api/staff', methods=['POST'])
    @admin_required
    def add_staff_endpoint():
        """Registers a new staff member with PBKDF2 hashing and unique salt."""
        data = request.get_json() or {}
        result = add_staff_member(
            name=data.get('name'),
            designation=data.get('designation'),
            contact=data.get('contact'),
            username=data.get('username'),
            password=data.get('password')
        )
        status_code = 200 if result["success"] else 400
        return jsonify(result), status_code

    @app.route('/api/staff/<staff_id>', methods=['PUT'])
    @admin_required
    def update_staff_endpoint(staff_id):
        """Edits name, designation, or contact for existing staff."""
        data = request.get_json() or {}
        result = update_staff_member(
            staff_id=staff_id,
            name=data.get('name'),
            designation=data.get('designation'),
            contact=data.get('contact')
        )
        status_code = 200 if result["success"] else 400
        return jsonify(result), status_code

    # --- Demo Reset Endpoint ---
    @app.route('/api/demo/reset', methods=['POST'])
    @admin_required
    def reset_demo_endpoint():
        """Resets the web demo database back to clean synthetic data (Admin only)."""
        if not app.config.get('DEMO_MODE', True):
            return jsonify({"success": False, "error": "Reset is disabled in this mode."}), 403
        reset_to_clean_demo(app)
        return jsonify({"success": True, "message": "Demo data has been reset to clean initial state."})

    # --- Root HTML Shell ---
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def index(path):
        """Serves the single-page application shell."""
        return render_template('index.html')

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
