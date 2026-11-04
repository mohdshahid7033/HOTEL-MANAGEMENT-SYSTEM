import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime, timedelta
import json
import os
import hashlib
import hmac
import time
from math import ceil

# --- Security and Password Hashing ---

PBKDF2_ITERATIONS = 100000

def hash_password(password, salt=None):
    """
    Hashes a password using PBKDF2-HMAC-SHA256 with a unique random salt per account.
    Returns (salt_hex, hash_hex).
    """
    if salt is None:
        salt = os.urandom(16).hex()
    salt_bytes = bytes.fromhex(salt)
    pw_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt_bytes,
        PBKDF2_ITERATIONS
    ).hex()
    return salt, pw_hash

def verify_password(provided_password, stored_password, salt=None):
    """
    Verifies a provided password against the stored password and optional salt.
    Preserves backward compatibility with:
      1. PBKDF2-HMAC-SHA256 with separate salt ('password_salt' or 'salt').
      2. PBKDF2-HMAC-SHA256 with embedded salt ('salt$hash').
      3. Legacy SHA-256 hexadecimal digests (64 hex characters, unsalted).
    Uses hmac.compare_digest for constant-time comparison.
    """
    if not stored_password or not provided_password:
        return False

    # 1. PBKDF2-HMAC-SHA256 with salt parameter
    if salt:
        try:
            salt_bytes = bytes.fromhex(salt)
            computed_hash = hashlib.pbkdf2_hmac(
                'sha256',
                provided_password.encode('utf-8'),
                salt_bytes,
                PBKDF2_ITERATIONS
            ).hex()
            if hmac.compare_digest(computed_hash, stored_password):
                return True
        except Exception:
            pass

    # 2. Check if salt is embedded as 'salt$hash'
    if '$' in stored_password:
        parts = stored_password.split('$')
        if len(parts) == 2:
            s_hex, h_hex = parts
            try:
                computed_hash = hashlib.pbkdf2_hmac(
                    'sha256',
                    provided_password.encode('utf-8'),
                    bytes.fromhex(s_hex),
                    PBKDF2_ITERATIONS
                ).hex()
                if hmac.compare_digest(computed_hash, h_hex):
                    return True
            except Exception:
                pass

    # 3. Legacy SHA-256 fallback (for existing staff records)
    legacy_hash = hashlib.sha256(provided_password.encode('utf-8')).hexdigest()
    if hmac.compare_digest(legacy_hash, stored_password):
        return True

    return False

def generate_next_staff_id(staff_list):
    """Generates the next sequential staff ID (e.g. 'S001', 'S002')."""
    max_num = 0
    for s in staff_list:
        sid = str(s.get('staff_id', '')).strip()
        if sid.startswith('S') and sid[1:].isdigit():
            max_num = max(max_num, int(sid[1:]))
    return f"S{max_num + 1:03d}"

# --- Configuration and Data Persistence ---

DATA_DIR = "hotel_data"
BOOKINGS_FILE = os.path.join(DATA_DIR, "bookings.json")
STAFF_FILE = os.path.join(DATA_DIR, "staff.json")
HOUSEKEEPING_FILE = os.path.join(DATA_DIR, "housekeeping.json")
ROOMS = [str(i) for i in range(101, 111)] # Rooms 101 to 110

# Pricing Constants
ROOM_RATE = 15000
FOOD_PRICES = {"None": 0, "Normal": 500, "VIP": 1000}
GST_RATE = 0.18

def load_data(filepath, default_data):
    """Loads data from a JSON file, or returns default data if the file doesn't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r') as f:
                # IMPORTANT: Use a check for empty file
                content = f.read()
                if not content:
                    return default_data
                return json.loads(content)
        except json.JSONDecodeError:
            # print(f"Warning: Failed to decode {filepath}. Using default data.")
            return default_data
        except Exception:
             # print(f"Error reading {filepath}. Using default data.")
             return default_data
    return default_data

def save_data(filepath, data):
    """Saves data to a JSON file."""
    os.makedirs(DATA_DIR, exist_ok=True) # Ensure directory exists before saving
    try:
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        # print(f"Successfully saved data to {filepath}.")
    except IOError as e:
        # Instead of a messagebox, we'll rely on the status bar in the main app
        # messagebox.showerror("Save Error", f"Error saving data to {filepath}: {e}")
        pass

# Initial Data Setup (No hardcoded credentials)
INITIAL_STAFF = []
INITIAL_BOOKINGS = []
INITIAL_HOUSEKEEPING = {room: {"status": "Clean", "last_cleaned_by": "System"} for room in ROOMS}

# --- Tkinter Style Configuration ---
def configure_styles(master):
    """Configures the unified dark theme using ttk.Style, including clickable button effect."""
    style = ttk.Style(master)
    style.theme_use('clam')

    BASE_FONT = ('Verdana', 11)
    ACCENT_COLOR = '#FFD700' # Gold
    BG_COLOR = '#1A1A1A' # Dark Gray Background
    FRAME_COLOR = '#2C2C2C' # Slightly lighter frame
    TEXT_COLOR = '#FFFFFF'
    BUTTON_BG = ACCENT_COLOR

    # General Frame/Label Style
    style.configure('TFrame', background=BG_COLOR)
    style.configure('TLabel', background=BG_COLOR, foreground=TEXT_COLOR, font=BASE_FONT)

    # Entry and Combobox
    style.configure('TEntry', fieldbackground=FRAME_COLOR, foreground=TEXT_COLOR, bordercolor='#555555')
    style.configure('TCombobox', fieldbackground=FRAME_COLOR, foreground=TEXT_COLOR, selectbackground=ACCENT_COLOR, selectforeground='#000000')

    # Button Style (Gold Accent)
    style.configure('TButton',
                    background=BUTTON_BG,
                    foreground='#000000',
                    font=('Verdana', 12, 'bold'),
                    borderwidth=0,
                    relief="flat",
                    padding=[15, 10])

    # --- New Clickable Button Look ---
    style.map('TButton',
              background=[('active', '#FFC107'), ('pressed', '#FFC107')], # Slightly lighter on hover/click
              foreground=[('active', '#000000'), ('pressed', '#000000')],
              relief=[('pressed', 'sunken'), ('!disabled', 'raised')]) # Change relief on click for depth

    # Dashboard Button Style (larger padding)
    style.configure('Dashboard.TButton', padding=[25, 20], font=('Verdana', 13, 'bold'))
    # Apply clickable mapping to dashboard buttons as well
    style.map('Dashboard.TButton',
              background=[('active', '#FFC107'), ('pressed', '#FFC107')],
              foreground=[('active', '#000000'), ('pressed', '#000000')],
              relief=[('pressed', 'sunken'), ('!disabled', 'raised')])
    # ---------------------------------

    # Treeview Style
    style.configure("Treeview",
                    background=FRAME_COLOR,
                    foreground=TEXT_COLOR,
                    fieldbackground=FRAME_COLOR,
                    bordercolor=ACCENT_COLOR,
                    font=('Verdana', 11))
    style.configure("Treeview.Heading",
                    font=('Verdana', 12, 'bold'),
                    background="#404040",
                    foreground=ACCENT_COLOR)
    style.map('Treeview',
              background=[('selected', ACCENT_COLOR)],
              foreground=[('selected', '#000000')])

    # Notebook/Tab Style
    style.configure('TNotebook', background=BG_COLOR, borderwidth=0)
    style.configure('TNotebook.Tab', background=FRAME_COLOR, foreground=TEXT_COLOR, font=BASE_FONT, padding=[10, 5])
    style.map('TNotebook.Tab', background=[('selected', ACCENT_COLOR)], foreground=[('selected', '#000000')])


class HotelApp:
    def __init__(self, master):
        self.master = master

        master.title("👑 Taj Banjara Hotel")

        # Window size and centering
        screen_width = master.winfo_screenwidth()
        screen_height = master.winfo_screenheight()
        self.window_width = 950
        self.window_height = 750
        center_x = int(screen_width / 2 - self.window_width / 2)
        center_y = int(screen_height / 2 - self.window_height / 2)
        master.geometry(f'{self.window_width}x{self.window_height}+{center_x}+{center_y}')
        master.configure(bg="#1A1A1A") # Dark Background

        # Apply custom ttk styles
        configure_styles(master)

        # Fonts and Colors for non-ttk widgets (like tk.Label, tk.Entry, etc.)
        self.ACCENT_COLOR = '#FFD700' # Gold
        self.BG_COLOR = '#1A1A1A' # Dark Gray Background
        self.FRAME_COLOR = '#2C2C2C' # Slightly lighter frame
        self.TEXT_COLOR = '#FFFFFF'
        self.BASE_FONT = ('Verdana', 11)
        self.TITLE_FONT = ('Times New Roman', 28, 'bold')
        self.SUBTITLE_FONT = ('Georgia', 20, 'bold')
        self.SUCCESS_COLOR = '#00FF00'
        self.ERROR_COLOR = 'red'

        # Data Loading - ENSURE CORRECT LOADING
        self.bookings = load_data(BOOKINGS_FILE, INITIAL_BOOKINGS)
        self.staff = load_data(STAFF_FILE, INITIAL_STAFF)
        self.housekeeping = load_data(HOUSEKEEPING_FILE, INITIAL_HOUSEKEEPING)

        # Status Bar
        self.status_bar = tk.Label(master, text="System Ready.", bd=1, relief=tk.SUNKEN, anchor=tk.W,
                                   bg="#333333", fg="#FFFFFF", font=('Arial', 10))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.current_frame = None
        self.current_user = None
        self.show_welcome_screen()

    def save_all_data(self):
        """Saves all current data to their respective JSON files."""
        save_data(BOOKINGS_FILE, self.bookings)
        save_data(STAFF_FILE, self.staff)
        save_data(HOUSEKEEPING_FILE, self.housekeeping)
        self.show_status("Data saved successfully.")

    def change_screen(self, new_screen_func, anchor_pos='center'):
        """Destroys the current frame and loads a new one, packed onto the master window."""
        if self.current_frame:
            self.current_frame.destroy()

        # Use ttk.Frame for the main content area
        self.current_frame = ttk.Frame(self.master, style='TFrame')

        # Positioning logic
        self.current_frame.pack(expand=True, fill='both', padx=50, pady=50)

        new_screen_func()

    def show_status(self, message, is_error=False):
        """Updates the internal status bar."""
        color = self.ERROR_COLOR if is_error else self.SUCCESS_COLOR
        self.status_bar.config(text=f"[{datetime.now().strftime('%H:%M:%S')}] {message}", fg=color)

    # --- Helper: Contextual Feedback Label (New) ---
    def _create_feedback_label(self, parent_frame):
        """Creates and returns a label for screen-specific feedback."""
        label = tk.Label(parent_frame, text="",
                         bg=self.BG_COLOR, fg=self.SUCCESS_COLOR,
                         font=('Verdana', 10, 'italic'))
        return label

    # --- Screen 1: Welcome Screen ---
    def show_welcome_screen(self):
        self.change_screen(self._welcome_layout)

    def _welcome_layout(self):
        title = tk.Label(self.current_frame, text="👑 Welcome to Taj Banjara Hotel 👑",
                         bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=("Georgia", 40, 'bold'))
        title.pack(pady=(150, 50))

        def handle_enter():
            if not self.staff:
                self.show_first_time_setup_screen()
            else:
                self.show_login_screen()

        enter_button = tk.Button(self.current_frame, text="Enter",
                                  command=handle_enter,
                                  relief=tk.RAISED,
                                  borderwidth=5,
                                  bg='#fff200',
                                  fg='black',
                                  font=("Georgia", 16, "bold"))
        enter_button.pack(pady=30, ipadx=50, ipady=10)
        developer_label = tk.Label(
            self.current_frame,
            text="Maintained by: Mohd Shahid Moinuddin",
            bg=self.BG_COLOR,
            fg=self.TEXT_COLOR,
            font=("Georgia", 12, "italic"),
            justify=tk.CENTER
        )
        developer_label.pack(pady=20)

    # --- Screen 1B: First-Time Administrator Setup ---
    def show_first_time_setup_screen(self):
        self.change_screen(self._first_time_setup_layout, anchor_pos='top')

    def _first_time_setup_layout(self):
        setup_box_frame = tk.Frame(
            self.current_frame,
            bg=self.FRAME_COLOR,
            padx=35,
            pady=25,
            relief=tk.FLAT,
            bd=2,
            borderwidth=2,
            highlightbackground=self.ACCENT_COLOR,
            highlightthickness=2
        )
        setup_box_frame.pack(pady=30)

        tk.Label(
            setup_box_frame,
            text="👑 Initial Administrator Setup",
            bg=self.FRAME_COLOR,
            fg=self.ACCENT_COLOR,
            font=('Arial', 20, 'bold')
        ).grid(row=0, column=0, columnspan=2, pady=(15, 5))

        tk.Label(
            setup_box_frame,
            text="No staff accounts found. Please configure the primary administrator.",
            bg=self.FRAME_COLOR,
            fg=self.TEXT_COLOR,
            font=('Verdana', 10, 'italic')
        ).grid(row=1, column=0, columnspan=2, pady=(0, 20))

        # Fields: Administrator Name, Contact Information, Username, Password, Confirm Password
        fields = [
            ("Administrator Name:", "name", False),
            ("Contact Information:", "contact", False),
            ("Username:", "username", False),
            ("Password:", "password", True),
            ("Confirm Password:", "confirm_password", True)
        ]

        setup_entries = {}
        for row_idx, (label_text, field_key, is_secret) in enumerate(fields, start=2):
            tk.Label(
                setup_box_frame,
                text=label_text,
                bg=self.FRAME_COLOR,
                fg=self.TEXT_COLOR,
                font=self.BASE_FONT
            ).grid(row=row_idx, column=0, padx=15, pady=8, sticky='w')

            entry = tk.Entry(
                setup_box_frame,
                show="*" if is_secret else "",
                bg=self.FRAME_COLOR,
                fg=self.TEXT_COLOR,
                insertbackground=self.TEXT_COLOR,
                font=self.BASE_FONT,
                width=26
            )
            entry.grid(row=row_idx, column=1, padx=15, pady=8, sticky='w')
            setup_entries[field_key] = entry

        # Setup Feedback Label
        setup_feedback_label = self._create_feedback_label(setup_box_frame)
        setup_feedback_label.grid(row=len(fields) + 2, column=0, columnspan=2, pady=(8, 10))

        def create_admin():
            setup_feedback_label.config(text="")
            name = setup_entries["name"].get().strip()
            contact = setup_entries["contact"].get().strip()
            username = setup_entries["username"].get().strip()
            password = setup_entries["password"].get()
            confirm_password = setup_entries["confirm_password"].get()

            # Empty fields validation
            if not name or not contact or not username or not password or not confirm_password:
                setup_feedback_label.config(text="Input Error: All fields are required.", fg=self.ERROR_COLOR)
                self.show_status("Setup Error: All fields must be filled.", is_error=True)
                return

            if not password.strip():
                setup_feedback_label.config(text="Input Error: Password cannot be blank.", fg=self.ERROR_COLOR)
                self.show_status("Setup Error: Password cannot be blank.", is_error=True)
                return

            # Password confirmation validation
            if password != confirm_password:
                setup_feedback_label.config(text="Input Error: Passwords do not match.", fg=self.ERROR_COLOR)
                self.show_status("Setup Error: Passwords do not match.", is_error=True)
                return

            # Secure password hashing with PBKDF2-HMAC-SHA256 and unique random salt
            salt, pw_hash = hash_password(password)

            admin_account = {
                "staff_id": "S001",
                "name": name,
                "designation": "Manager",
                "contact": contact,
                "login_username": username,
                "password_salt": salt,
                "login_password": pw_hash
            }

            self.staff.append(admin_account)
            self.save_all_data()

            success_msg = f"Administrator '{username}' created successfully! Please log in."
            self.show_status(success_msg, is_error=False)
            self.show_login_screen(initial_feedback=success_msg, is_error=False)

        submit_btn = tk.Button(
            setup_box_frame,
            text="Create Administrator Account",
            command=create_admin,
            relief=tk.RAISED,
            borderwidth=6,
            bg='#fff200',
            fg='black',
            font=("Arial", 14, "bold")
        )
        submit_btn.grid(row=len(fields) + 3, column=0, columnspan=2, pady=(10, 5), ipadx=20, ipady=5)

        back_btn = tk.Button(
            setup_box_frame,
            text="← Back",
            command=self.show_welcome_screen,
            relief=tk.RAISED,
            borderwidth=6,
            bg='#fff200',
            fg='black',
            font=("Arial", 14, "bold")
        )
        back_btn.grid(row=len(fields) + 4, column=0, columnspan=2, pady=(5, 10), ipadx=25, ipady=3)

    # --- Screen 2: Staff Login ---
    def show_login_screen(self, initial_feedback="", is_error=False):
        if not self.staff:
            self.show_first_time_setup_screen()
            return
        self.change_screen(lambda: self._login_layout(initial_feedback, is_error), anchor_pos='top')

    def _login_layout(self, initial_feedback="", is_error=False):
        # Use tk.Frame for the login box (easier to style border)
        login_box_frame = tk.Frame(self.current_frame,
                                    bg=self.FRAME_COLOR, padx=30, pady=30,
                                    relief=tk.FLAT, bd=2, borderwidth=2, highlightbackground=self.ACCENT_COLOR, highlightthickness=2)
        login_box_frame.pack(pady=50)

        tk.Label(login_box_frame, text="🔑 Staff Login",
                 bg=self.FRAME_COLOR, fg=self.ACCENT_COLOR, font=('Arial', 20, 'bold')).grid(row=0, column=0, columnspan=2, pady=(20, 35))

        # Username
        tk.Label(login_box_frame, text="Username:", bg=self.FRAME_COLOR, fg=self.TEXT_COLOR, font=self.BASE_FONT).grid(row=1, column=0, padx=15, pady=15, sticky='w')
        self.username_entry = tk.Entry(login_box_frame,
                                            bg=self.FRAME_COLOR, fg=self.TEXT_COLOR, insertbackground=self.TEXT_COLOR,
                                            font=self.BASE_FONT, width=25)
        self.username_entry.grid(row=1, column=1, padx=15, pady=15, sticky='w')

        # Password
        tk.Label(login_box_frame, text="Password:", bg=self.FRAME_COLOR, fg=self.TEXT_COLOR, font=self.BASE_FONT).grid(row=2, column=0, padx=15, pady=15, sticky='w')
        self.password_entry = tk.Entry(login_box_frame, show="*",
                                            bg=self.FRAME_COLOR, fg=self.TEXT_COLOR, insertbackground=self.TEXT_COLOR,
                                            font=self.BASE_FONT, width=25)
        self.password_entry.grid(row=2, column=1, padx=15, pady=15, sticky='w')

        # Login Feedback Label
        self.login_feedback_label = self._create_feedback_label(login_box_frame)
        self.login_feedback_label.grid(row=3, column=0, columnspan=2, pady=(5, 10))
        if initial_feedback:
            feedback_color = self.ERROR_COLOR if is_error else self.SUCCESS_COLOR
            self.login_feedback_label.config(text=initial_feedback, fg=feedback_color)

        # Login Button
        login_button = tk.Button(login_box_frame, text="Login",
                                  relief=tk.RAISED,
                                  borderwidth=6,
                                  bg='#fff200',
                                  fg='black',
                                  font=("Arial", 16, "bold"))
        login_button.bind('<ButtonRelease-1>', lambda event: self._authenticate())
        login_button.grid(row=4, column=0, columnspan=2, pady=(10, 10), ipadx=40, ipady=5)

        back_button = tk.Button(login_box_frame, text="← Back", command=self.show_welcome_screen, relief=tk.RAISED,
                                  borderwidth=6,
                                  bg='#fff200',
                                  fg='black',
                                  font=("Arial", 16, "bold"))
        back_button.grid(row=5, column=0, columnspan=2, pady=(10, 10), ipadx=30, ipady=4)

    def _authenticate(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self.login_feedback_label.config(text="Please enter both username and password.", fg=self.ERROR_COLOR)
            self.show_status("Authentication Failed: Missing credentials.", is_error=True)
            return

        # Find staff member by username
        user = next((s for s in self.staff if s.get('login_username') == username), None)

        if user and verify_password(password, user.get('login_password', ''), user.get('password_salt') or user.get('salt')):
            # Transparently upgrade legacy SHA-256 password to PBKDF2 with salt upon successful login
            if not user.get('password_salt') and not user.get('salt'):
                salt, new_hash = hash_password(password)
                user['password_salt'] = salt
                user['login_password'] = new_hash
                self.save_all_data()

            self.current_user = user.get('name', username)
            self.show_status(f"Authentication Successful. Welcome, {self.current_user}.", is_error=False)
            self.change_screen(self.show_dashboard)
        else:
            # Replaced messagebox with contextual label and status bar
            self.login_feedback_label.config(text="Invalid username or password.", fg=self.ERROR_COLOR)
            self.show_status("Authentication Failed.", is_error=True)

    # --- Screen 3: Admin Dashboard ---
    def show_dashboard(self):
        self.change_screen(self._dashboard_layout)

    def _dashboard_layout(self):
        # Header
        tk.Label(self.current_frame, text="👑 Taj Banjara Hotel - Dashboard 👑",
                 bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.TITLE_FONT).pack(pady=20)

        current_time = datetime.now().strftime("%d-%m-%Y %I:%M %p")
        tk.Label(self.current_frame, text=current_time,
                 bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.BASE_FONT).pack()
        tk.Label(self.current_frame, text=f"Logged in as: {self.current_user}",
                 bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.BASE_FONT).pack(pady=5)
 # Buttons Grid
        button_data = [
            ("🏨 Book Room", self.show_room_booking_screen),
            ("💵 Checkout", self.show_checkout_screen),
            ("🔍 Search Guest", self.show_search_guest_screen),
            ("🛏️ Room Status", self.show_room_status_screen),

            ("👨‍💼 Staff Management", self.show_staff_management_screen),
            ("📜 Booking History", self.show_booking_history_screen),
            ("🔄 Update Booking", self.show_update_booking_screen),
            ("🧹 Housekeeping Status", self.show_housekeeping_screen),
            ("📈 Revenue Report", self.show_revenue_report_screen),
            ("🚪 Exit", self.master.quit)
        ]


        # Arrange buttons in a grid for better layout
        button_frame = ttk.Frame(self.current_frame, style='TFrame')
        button_frame.pack(pady=30)

        for i, (text, command) in enumerate(button_data):
            row = i // 3 # 3 buttons per row
            col = i % 3
            ttk.Button(button_frame, text=text, command=command, style='Dashboard.TButton', width=20).grid(row=row, column=col, padx=15, pady=15, sticky='nsew')

    # --- Feature: Room Booking (Simplified) ---
    def show_room_booking_screen(self):
        self.change_screen(self._room_booking_layout)

    def _room_booking_layout(self):
        tk.Label(self.current_frame, text="★ Room Booking",
                 bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.SUBTITLE_FONT).pack(pady=20)

        # Room No (Auto-select first available)
        active_room_nos = {b['room_no'] for b in self.bookings if b.get('status') == 'Booked'}
        available_rooms = [r for r in ROOMS if r not in active_room_nos]

        self.booking_feedback_label = self._create_feedback_label(self.current_frame)
        self.booking_feedback_label.pack(pady=5)

        if not available_rooms:
            self.booking_feedback_label.config(text="No Rooms Available!", fg=self.ERROR_COLOR)
            ttk.Button(self.current_frame, text="← Back", command=self.show_dashboard, style='TButton').pack(pady=20)
            return

        booking_container = tk.Frame(self.current_frame, bg=self.FRAME_COLOR, padx=20, pady=20, borderwidth=1, relief=tk.SOLID)
        booking_container.pack(pady=20, padx=100, fill='x')

        # --- Input Fields ---

        tk.Label(booking_container, text=f"Room No (Auto-Assigned): {available_rooms[0]}",
                 bg=self.FRAME_COLOR, fg=self.SUCCESS_COLOR, font=self.BASE_FONT).grid(row=0, column=0, columnspan=2, pady=(15, 20), padx=20, sticky='n')

        tk.Label(booking_container, text="Guest Name:", bg=self.FRAME_COLOR, fg=self.TEXT_COLOR, font=self.BASE_FONT).grid(row=1, column=0, padx=20, pady=10, sticky='w')
        guest_name_entry = ttk.Entry(booking_container, style='TEntry', width=40)
        guest_name_entry.grid(row=1, column=1, padx=20, pady=10, sticky='n')

        tk.Label(booking_container, text="Number of Days:", bg=self.FRAME_COLOR, fg=self.TEXT_COLOR, font=self.BASE_FONT).grid(row=2, column=0, padx=20, pady=10, sticky='w')
        days_entry = ttk.Entry(booking_container, style='TEntry', width=40)
        days_entry.grid(row=2, column=1, padx=20, pady=10, sticky='w')

        # Food Options Radio Buttons
        food_options = [
            ("None (₹0/day)", "None"),
            ("Normal (₹500/day)", "Normal"),
            ("VIP (₹1000/day)", "VIP")
        ]
        food_var = tk.StringVar(value="None")

        tk.Label(booking_container, text="Food Option:", bg=self.FRAME_COLOR, fg=self.TEXT_COLOR, font=self.BASE_FONT).grid(row=3, column=0, padx=20, pady=10, sticky='nw')

        radio_frame = tk.Frame(booking_container, bg=self.FRAME_COLOR)
        radio_frame.grid(row=3, column=1, padx=20, pady=10, sticky='w')

        for i, (text, value) in enumerate(food_options):
            tk.Radiobutton(radio_frame, text=text, variable=food_var, value=value,
                           bg=self.FRAME_COLOR, fg=self.TEXT_COLOR, selectcolor=self.FRAME_COLOR,
                           activebackground=self.FRAME_COLOR, activeforeground=self.ACCENT_COLOR,
                           font=self.BASE_FONT, indicatoron=0, bd=1, relief=tk.RAISED).pack(anchor='w', pady=3)

        def book_room():
            self.booking_feedback_label.config(text="") # Clear previous message

            if not available_rooms:
                self.booking_feedback_label.config(text="Booking Error: No rooms available to book.", fg=self.ERROR_COLOR)
                return

            room_no = available_rooms[0]
            name = guest_name_entry.get().strip()
            days = days_entry.get().strip()
            food = food_var.get()

            if not name or not days.isdigit() or int(days) <= 0:
                self.booking_feedback_label.config(text="Input Error: Please enter a valid guest name and a positive number of days.", fg=self.ERROR_COLOR)
                return

            self.bookings.append({
                "room_no": room_no,
                "guest_name": name,
                "days": int(days),
                "food_plan": food,
                "check_in_datetime": datetime.now().strftime("%d-%m-%Y %I:%M %p"),
                "status": "Booked"
            })
            self.save_all_data()
            success_message = f"Room {room_no} booked successfully for {name}."
            self.show_status(success_message, is_error=False)
            self.booking_feedback_label.config(text=success_message, fg=self.SUCCESS_COLOR) # Display success message

            # Simulate the "Room 104 booked successfully!" message from your image
            # Note: The screen needs to be refreshed to update the available rooms, so we jump back to the dashboard
            self.master.after(500, self.show_dashboard) # Wait half a second before changing screen

        ttk.Button(self.current_frame, text="Book Room", command=book_room, style='TButton').pack(pady=20, ipadx=40, ipady=5)
        ttk.Button(self.current_frame, text="← Back", command=self.show_dashboard, style='TButton').pack(pady=5, ipadx=40, ipady=5)

    # --- Feature: Checkout (Simplified) ---
    def show_checkout_screen(self):
        self.change_screen(self._checkout_layout)

    def _checkout_layout(self):
        tk.Label(self.current_frame, text="🧾 Checkout", bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.SUBTITLE_FONT).pack(pady=20)

        input_frame = tk.Frame(self.current_frame, bg=self.BG_COLOR)
        input_frame.pack(pady=10)

        ttk.Label(input_frame, text="Enter Room Number:").grid(row=0, column=0, padx=10, pady=10)
        room_entry = ttk.Entry(input_frame, style='TEntry', width=20)
        room_entry.grid(row=0, column=1, padx=10, pady=10)

        bill_display = tk.Text(self.current_frame, height=12, width=60,
                               bg=self.FRAME_COLOR, fg=self.TEXT_COLOR,
                               relief=tk.FLAT, font=('Courier New', 12))
        bill_display.pack(pady=10)

        # Checkout Feedback Label (replaces the checkout complete popup)
        self.checkout_feedback_label = self._create_feedback_label(self.current_frame)
        self.checkout_feedback_label.config(font=('Verdana', 12, 'bold'))
        self.checkout_feedback_label.pack(pady=5)

        checkout_final_btn = ttk.Button(self.current_frame, text="Checkout & Confirm Payment", state=tk.DISABLED, style='TButton')

        def calculate_bill():
            self.checkout_feedback_label.config(text="")
            room_no = room_entry.get().strip()
            booking = next((b for b in self.bookings if b.get('room_no') == room_no and b.get('status') == 'Booked'), None)

            bill_display.delete('1.0', tk.END)

            if not booking:
                bill_display.insert(tk.END, "Error: No active booking found for this room.")
                self.checkout_feedback_label.config(text=f"Room {room_no} is not currently booked.", fg=self.ERROR_COLOR)
                checkout_final_btn.config(state=tk.DISABLED)
                self.show_status(f"Error: Room {room_no} is not currently booked.", is_error=True)
                return

            # REFINEMENT: Ensure days is read as integer
            try:
                days = int(booking['days'])
            except:
                days = 1 # Default to 1 if data is corrupted
            food_plan = booking['food_plan']

            room_charge = ROOM_RATE * days
            food_charge = FOOD_PRICES.get(food_plan, 0) * days
            subtotal = room_charge + food_charge
            gst = subtotal * GST_RATE
            total = subtotal + gst

            bill_text = f"--- Taj Banjara Hotel - Final Bill ---\n"
            bill_text += f"Guest: {booking['guest_name']}\n"
            bill_text += f"Days Booked: {days}\n"
            bill_text += f"Check-in Date: {booking['check_in_datetime']}\n"
            bill_text += f"\n"
            bill_text += f"{'Room Charges:':<25} ₹{room_charge:>15,.2f}\n"
            bill_text += f"{f'Food Charges ({food_plan}):':<25} ₹{food_charge:>15,.2f}\n"
            bill_text += f"{'Subtotal:':<25} ₹{subtotal:>15,.2f}\n"
            bill_text += f"{f'GST ({int(GST_RATE*100)}%):':<25} ₹{gst:>15,.2f}\n"
            bill_text += f"---------------------------------------------------\n"
            bill_text += f"{'TOTAL AMOUNT DUE:':<25} ₹{total:>15,.2f}"

            bill_display.insert(tk.END, bill_text)
            self.show_status(f"Bill calculated for Room {room_no}. Total: ₹{total:,.2f}")
            checkout_final_btn.config(state=tk.NORMAL, command=lambda: self._complete_checkout(room_no))

        def trigger_calc():
            checkout_final_btn.config(state=tk.DISABLED)
            calculate_bill()

        ttk.Button(input_frame, text="Calculate Bill", command=trigger_calc, style='TButton').grid(row=0, column=2, padx=10, pady=10)

        checkout_final_btn.pack(pady=10, ipadx=40, ipady=5)

        ttk.Button(self.current_frame, text="← Back", command=self.show_dashboard, style='TButton').pack(pady=5, ipadx=40, ipady=5)

    def _complete_checkout(self, room_no):
        """Finalizes the checkout process."""
        for booking in self.bookings:
            if booking.get('room_no') == room_no and booking.get('status') == 'Booked':
                booking['status'] = 'Checked Out'
                booking['checkout_datetime'] = datetime.now().strftime("%d-%m-%Y %I:%M %p")

                if room_no in self.housekeeping:
                    self.housekeeping[room_no]["status"] = "Needs Cleaning"
                    self.housekeeping[room_no]["last_cleaned_by"] = None

                self.save_all_data()
                success_message = f"Checkout successful for Room {room_no}. Room marked for cleaning."
                self.show_status(success_message, is_error=False)

                # Update contextual label (mimics the popup in your image)
                self.checkout_feedback_label.config(text=success_message, fg=self.SUCCESS_COLOR)

                # Use a short delay before returning to dashboard
                self.master.after(1000, self.show_dashboard)
                return
        # Fallback error message (shouldn't happen after calculate_bill)
        self.checkout_feedback_label.config(text="Error: Could not finalize checkout.", fg=self.ERROR_COLOR)


    # --- Feature: Search Guest (NEW IMPLEMENTATION) ---
    def show_search_guest_screen(self):
        self.change_screen(self._search_guest_layout)

    def _search_guest_layout(self):
        tk.Label(self.current_frame, text="🔍 Search Guest", bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.SUBTITLE_FONT).pack(pady=20)

        search_frame = tk.Frame(self.current_frame, bg=self.BG_COLOR)
        search_frame.pack(pady=10)

        ttk.Label(search_frame, text="Guest Name (or part of name):").pack(side=tk.LEFT, padx=5)
        name_entry = ttk.Entry(search_frame, style='TEntry', width=30)
        name_entry.pack(side=tk.LEFT, padx=5)

        # Treeview Table for Results
        columns = ("Room No", "Guest Name", "Check-in", "Days", "Status")
        self.search_tree = ttk.Treeview(self.current_frame, columns=columns, show='headings', height=10, style='Treeview')

        for col in columns:
            self.search_tree.heading(col, text=col)
            self.search_tree.column(col, anchor=tk.CENTER, width=120)

        self.search_tree.pack(padx=20, pady=10, fill='x', expand=False)

        self.search_feedback_label = self._create_feedback_label(self.current_frame)
        self.search_feedback_label.pack(pady=5)

        def search_guests():
            search_term = name_entry.get().strip().lower()
            self.search_feedback_label.config(text="")

            # Clear previous results
            for item in self.search_tree.get_children():
                self.search_tree.delete(item)

            if not search_term:
                self.search_feedback_label.config(text="Please enter a name to search.", fg=self.ERROR_COLOR)
                self.show_status("Please enter a name to search.", is_error=True)
                return

            found_count = 0
            for booking in self.bookings:
                guest_name = booking.get('guest_name', '').lower()
                status = booking.get('status', 'Unknown')

                if search_term in guest_name:
                    found_count += 1
                    tag = 'booked' if status == 'Booked' else 'checked_out'

                    self.search_tree.insert("", tk.END, values=(
                        booking['room_no'],
                        booking['guest_name'],
                        booking['check_in_datetime'],
                        booking['days'],
                        status
                    ), tags=(tag,))

            if found_count > 0:
                self.search_feedback_label.config(text=f"Found {found_count} booking(s) matching '{search_term}'.", fg=self.SUCCESS_COLOR)
                self.show_status(f"Found {found_count} booking(s) matching '{search_term}'.")
            else:
                self.search_feedback_label.config(text=f"No bookings found matching '{search_term}'.", fg=self.ERROR_COLOR)
                self.show_status(f"No bookings found matching '{search_term}'.", is_error=True)

        self.search_tree.tag_configure('booked', foreground=self.ACCENT_COLOR)
        self.search_tree.tag_configure('checked_out', foreground='#888888')

        ttk.Button(search_frame, text="Search", command=search_guests, style='TButton').pack(side=tk.LEFT, padx=10, ipady=0, ipadx=10)

        ttk.Button(self.current_frame, text="← Back", command=self.show_dashboard, style='TButton').pack(pady=20, ipadx=40, ipady=5)

    # --- Feature: Room Status ---
    def show_room_status_screen(self):
        self.change_screen(self._room_status_layout)

    def _room_status_layout(self):
        tk.Label(self.current_frame, text="🛏️ Room Status", bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.SUBTITLE_FONT).pack(pady=20)

        # Create Treeview Table
        columns = ("Room No", "Status", "Guest", "Days", "Food")
        tree = ttk.Treeview(self.current_frame, columns=columns, show='headings', height=10, style='Treeview')

        for col in columns:
            tree.heading(col, text=col)

        # Adjust column widths for better fit
        tree.column("Room No", anchor=tk.CENTER, width=100)
        tree.column("Status", anchor=tk.CENTER, width=120)
        tree.column("Guest", anchor=tk.W, width=150)
        tree.column("Days", anchor=tk.CENTER, width=80)
        tree.column("Food", anchor=tk.CENTER, width=120)

        # Populate data
        active_bookings = {b['room_no']: b for b in self.bookings if b.get('status') == 'Booked'}

        for room in sorted(ROOMS, key=lambda r: int(r)):
            if room in active_bookings:
                b = active_bookings[room]
                tree.insert("", tk.END, values=(
                    room,
                    "Booked",
                    b['guest_name'],
                    b['days'],
                    b['food_plan']
                ), tags=('booked',))
            else:
                tree.insert("", tk.END, values=(room, "Available", "-", "-", "-"), tags=('available',))

        # Add tags for visual distinction
        tree.tag_configure('booked', foreground=self.ACCENT_COLOR)
        tree.tag_configure('available', foreground=self.SUCCESS_COLOR)

        tree.pack(padx=20, pady=10, fill='x', expand=False)

        ttk.Button(self.current_frame, text="← Back", command=self.show_dashboard, style='TButton').pack(pady=20, ipadx=40, ipady=5)

    # --- Feature: Staff Management ---
    def show_staff_management_screen(self):
        self.change_screen(self._staff_management_layout)

    def _staff_management_layout(self):
        tk.Label(self.current_frame, text="👨‍💼 Staff Management", bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.SUBTITLE_FONT).pack(pady=20)

        notebook = ttk.Notebook(self.current_frame, style='TNotebook')
        notebook.pack(pady=10, padx=20, expand=True, fill="both")

        # --- Tab 1: View/Edit Staff ---
        view_frame = ttk.Frame(notebook, style='TFrame')
        notebook.add(view_frame, text="View/Edit Staff")
        self.staff_tree = self._create_staff_view_tab(view_frame)

        # --- Tab 2: Add Staff ---
        add_frame = ttk.Frame(notebook, style='TFrame')
        notebook.add(add_frame, text="Add New Staff")
        self._create_staff_add_tab(add_frame)

        # Feedback label for staff management actions
        self.staff_feedback_label = self._create_feedback_label(self.current_frame)
        self.staff_feedback_label.pack(pady=5)

        ttk.Button(self.current_frame, text="← Back to Dashboard", command=self.show_dashboard, style='TButton').pack(pady=10, ipadx=40, ipady=5)

    def _create_staff_view_tab(self, frame):
        # Treeview Table
        columns = ("ID", "Name", "Designation", "Contact", "Username")
        tree = ttk.Treeview(frame, columns=columns, show='headings', height=10, style='Treeview')
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor=tk.CENTER, width=120)

        self.refresh_staff_tree(tree)

        tree.pack(padx=10, pady=10, expand=True, fill="both")

        # Functionality to Edit
        def handle_edit():
            selected_item = tree.focus()
            if not selected_item:
                self.staff_feedback_label.config(text="Please select a staff member to edit.", fg=self.ERROR_COLOR)
                self.show_status("Warning: No staff member selected for edit.", is_error=True)
                return

            self.staff_feedback_label.config(text="")
            staff_id = tree.item(selected_item, 'values')[0]
            self._edit_staff_window(staff_id)

        ttk.Button(frame, text="Edit Selected Staff", command=handle_edit, style='TButton').pack(pady=10, ipadx=40, ipady=5)
        return tree

    def refresh_staff_tree(self, tree):
        # Clear existing data
        for item in tree.get_children():
            tree.delete(item)

        # Populate data
        for staff in self.staff:
            tree.insert("", tk.END, values=(
                staff['staff_id'],
                staff['name'],
                staff['designation'],
                staff['contact'],
                staff['login_username']
            ))

    def _edit_staff_window(self, staff_id):
        staff_data = next(s for s in self.staff if s['staff_id'] == staff_id)

        # Create a new Toplevel window for editing
        edit_win = tk.Toplevel(self.master, bg=self.FRAME_COLOR)
        edit_win.title(f"Edit Staff: {staff_data['name']}")
        edit_win.geometry("400x300")

        # Center the Toplevel window
        edit_win.update_idletasks()
        width = edit_win.winfo_width()
        height = edit_win.winfo_height()
        x = (edit_win.winfo_screenwidth() // 2) - (width // 2)
        y = (edit_win.winfo_screenheight() // 2) - (height // 2)
        edit_win.geometry(f'{width}x{height}+{x}+{y}')

        edit_frame = ttk.Frame(edit_win, style='TFrame', padding="20 20 20 20")
        edit_frame.pack(expand=True, fill="both")

        edit_frame.config(style='TFrame') # Ensure the background is applied

        tk.Label(edit_frame, text=f"Editing Staff ID: {staff_id}", font=('Verdana', 14, 'bold'),
                 bg=self.BG_COLOR, fg=self.ACCENT_COLOR).grid(row=0, column=0, columnspan=2, pady=10)

        # Feedback label for Toplevel window
        toplevel_feedback = self._create_feedback_label(edit_frame)
        toplevel_feedback.grid(row=5, column=0, columnspan=2, pady=5)


        # Input fields
        fields = ["Name", "Designation", "Contact"]
        entries = {}

        for i, field in enumerate(fields):
            ttk.Label(edit_frame, text=f"{field}:").grid(row=i+1, column=0, padx=5, pady=5, sticky='w')
            entry = ttk.Entry(edit_frame, style='TEntry', width=25)
            entry.grid(row=i+1, column=1, padx=5, pady=5, sticky='w')
            entry.insert(0, staff_data[field.lower()])
            entries[field] = entry

        def save_changes():
            toplevel_feedback.config(text="")
            new_name = entries["Name"].get().strip()
            new_designation = entries["Designation"].get().strip()
            new_contact = entries["Contact"].get().strip()

            if not all([new_name, new_designation, new_contact]):
                toplevel_feedback.config(text="Error: All fields must be filled.", fg=self.ERROR_COLOR)
                return

            staff_data['name'] = new_name
            staff_data['designation'] = new_designation
            staff_data['contact'] = new_contact

            self.save_all_data()
            success_message = f"Staff ID {staff_id} updated successfully."
            self.staff_feedback_label.config(text=success_message, fg=self.SUCCESS_COLOR) # Main window feedback
            self.show_status(success_message)
            self.refresh_staff_tree(self.staff_tree) # Refresh the main view
            edit_win.destroy()

        ttk.Button(edit_frame, text="Save Changes", command=save_changes, style='TButton').grid(row=len(fields)+2, column=0, columnspan=2, pady=15, ipadx=10)


    def _create_staff_add_tab(self, frame):
        # Input fields for new staff
        add_frame = tk.Frame(frame, bg=self.BG_COLOR)
        add_frame.pack(padx=20, pady=20)

        fields = ["Staff Name", "Designation", "Contact", "Username", "Password"]
        entries = {}

        for i, field in enumerate(fields):
            tk.Label(add_frame, text=f"{field}:", bg=self.BG_COLOR, fg=self.TEXT_COLOR, font=self.BASE_FONT).grid(row=i, column=0, padx=10, pady=10, sticky='w')
            entry = ttk.Entry(add_frame, style='TEntry', width=30, show='*' if field == 'Password' else '')
            entry.grid(row=i, column=1, padx=10, pady=10, sticky='w')
            entries[field] = entry

        def add_new_staff():
            self.staff_feedback_label.config(text="")
            name = entries["Staff Name"].get().strip()
            designation = entries["Designation"].get().strip()
            contact = entries["Contact"].get().strip()
            username = entries["Username"].get().strip()
            password = entries["Password"].get().strip()

            if not all([name, designation, contact, username, password]):
                self.staff_feedback_label.config(text="Input Error: All fields must be filled.", fg=self.ERROR_COLOR)
                return

            # Check for unique username
            if any(s['login_username'] == username for s in self.staff):
                self.staff_feedback_label.config(text=f"Input Error: Username '{username}' already exists.", fg=self.ERROR_COLOR)
                return

            # Generate sequential staff ID
            new_id = generate_next_staff_id(self.staff)
            salt, pw_hash = hash_password(password)

            self.staff.append({
                "staff_id": new_id,
                "name": name,
                "designation": designation,
                "contact": contact,
                "login_username": username,
                "password_salt": salt,
                "login_password": pw_hash
            })
            self.save_all_data()
            success_message = f"New staff '{name}' added with ID: {new_id}."
            self.staff_feedback_label.config(text=success_message, fg=self.SUCCESS_COLOR)
            self.show_status(success_message)

            # Clear entries and refresh view
            for entry in entries.values():
                entry.delete(0, tk.END)
            self.refresh_staff_tree(self.staff_tree)

        ttk.Button(add_frame, text="Add Staff", command=add_new_staff, style='TButton').grid(row=len(fields), column=0, columnspan=2, pady=25, ipadx=40, ipady=5)


    # --- Feature: Booking History ---
    def show_booking_history_screen(self):
        self.change_screen(self._booking_history_layout)

    def _booking_history_layout(self):
        tk.Label(self.current_frame, text="📜 Booking History", bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.SUBTITLE_FONT).pack(pady=20)

        # Sort bookings by check-in date/time (most recent first)
        def sort_key(booking):
            try:
                # Use a specific format for sorting attempts
                return datetime.strptime(booking['check_in_datetime'], '%d-%m-%Y %I:%M %p')
            except:
                # Fallback to a minimum date for bookings with corrupted/missing check-in time
                return datetime.min

        sorted_history = sorted(self.bookings, key=sort_key, reverse=True)

        # Create Treeview Table
        columns = ("Room No", "Guest", "Check-in Date/Time", "Days", "Food Plan", "Status")
        tree = ttk.Treeview(self.current_frame, columns=columns, show='headings', height=15, style='Treeview')

        for col in columns:
            tree.heading(col, text=col)

        tree.column("Room No", anchor=tk.CENTER, width=80)
        tree.column("Check-in Date/Time", anchor=tk.CENTER, width=150)
        tree.column("Days", anchor=tk.CENTER, width=50)
        tree.column("Food Plan", anchor=tk.CENTER, width=100)
        tree.column("Status", anchor=tk.CENTER, width=100)

        # Populate data
        for booking in sorted_history:
            status = booking.get('status', 'Unknown')
            tag = 'checked_out' if status == 'Checked Out' else 'booked'

            tree.insert("", tk.END, values=(
                booking['room_no'],
                booking['guest_name'],
                booking['check_in_datetime'],
                booking['days'],
                booking['food_plan'],
                status
            ), tags=(tag,))

        tree.tag_configure('checked_out', foreground='#888888') # Grayed out
        tree.tag_configure('booked', foreground=self.ACCENT_COLOR)

        tree.pack(padx=20, pady=10, expand=True, fill="both")

        ttk.Button(self.current_frame, text="← Back", command=self.show_dashboard, style='TButton').pack(pady=20, ipadx=40, ipady=5)

    # --- Feature: Update Booking ---
    def show_update_booking_screen(self):
        self.change_screen(self._update_booking_layout)

    def _update_booking_layout(self):
        tk.Label(self.current_frame, text="🔄 Update Booking", bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.SUBTITLE_FONT).pack(pady=20)

        # Search Frame
        search_frame = tk.Frame(self.current_frame, bg=self.BG_COLOR)
        search_frame.pack(pady=10)

        ttk.Label(search_frame, text="Search by Room No:").pack(side=tk.LEFT, padx=5)
        room_entry = ttk.Entry(search_frame, style='TEntry', width=15)
        room_entry.pack(side=tk.LEFT, padx=5)

        # Update Frame (Initially Hidden)
        update_frame = tk.Frame(self.current_frame, bg=self.FRAME_COLOR, padx=20, pady=20, borderwidth=1, relief=tk.SOLID)

        current_info = tk.Label(update_frame, text="Current Booking Details:", bg=self.FRAME_COLOR, fg="#00FF00", justify=tk.LEFT, font=self.BASE_FONT)
        current_info.pack(pady=10, padx=20, fill='x')

        update_fields_frame = tk.Frame(update_frame, bg=self.FRAME_COLOR)
        update_fields_frame.pack()

        tk.Label(update_fields_frame, text="New Days:", bg=self.FRAME_COLOR, fg=self.TEXT_COLOR, font=self.BASE_FONT).grid(row=0, column=0, padx=10, pady=5, sticky='w')
        new_days_entry = ttk.Entry(update_fields_frame, style='TEntry', width=25)
        new_days_entry.grid(row=0, column=1, padx=10, pady=5, sticky='w')

        tk.Label(update_fields_frame, text="New Food Plan:", bg=self.FRAME_COLOR, fg=self.TEXT_COLOR, font=self.BASE_FONT).grid(row=1, column=0, padx=10, pady=5, sticky='w')
        food_plan_var = tk.StringVar(value="")
        food_plan_dropdown = ttk.Combobox(update_fields_frame, textvariable=food_plan_var, values=["None", "Normal", "VIP"], state="readonly", style='TCombobox', width=23)
        food_plan_dropdown.grid(row=1, column=1, padx=10, pady=5, sticky='w')

        # Feedback label for update actions
        self.update_feedback_label = self._create_feedback_label(self.current_frame)
        self.update_feedback_label.pack(pady=5)

        def search_booking():
            room_no = room_entry.get().strip()
            booking = next((b for b in self.bookings if b.get('room_no') == room_no and b.get('status') == 'Booked'), None)

            self.update_feedback_label.config(text="") # Clear previous message

            if booking:
                current_info.config(text=f"Current Details for Room {room_no}:\nGuest: {booking['guest_name']}, Days: {booking['days']}, Food: {booking['food_plan']}", fg=self.SUCCESS_COLOR)
                new_days_entry.delete(0, tk.END)
                new_days_entry.insert(0, str(booking['days']))
                food_plan_var.set(booking['food_plan'])
                update_frame.pack(pady=20)
                update_btn.config(state=tk.NORMAL)
                self.show_status(f"Active booking found for Room {room_no}.")
            else:
                current_info.config(text="No active booking found for this room.", fg=self.ERROR_COLOR)
                self.update_feedback_label.config(text=f"Error: No active booking found for Room {room_no}.", fg=self.ERROR_COLOR)
                update_frame.pack_forget()
                update_btn.config(state=tk.DISABLED)
                self.show_status(f"Error: No active booking found for Room {room_no}.", is_error=True)

        def perform_update():
            room_no = room_entry.get().strip()
            new_days = new_days_entry.get().strip()
            new_food = food_plan_var.get()

            self.update_feedback_label.config(text="")

            if not new_days.isdigit() or int(new_days) <= 0:
                self.update_feedback_label.config(text="Input Error: Please enter a valid number of days.", fg=self.ERROR_COLOR)
                return

            for booking in self.bookings:
                if booking.get('room_no') == room_no and booking.get('status') == 'Booked':
                    booking['days'] = int(new_days)
                    booking['food_plan'] = new_food
                    self.save_all_data()
                    success_message = f"Booking for Room {room_no} updated successfully."
                    self.update_feedback_label.config(text=success_message, fg=self.SUCCESS_COLOR)
                    self.show_status(success_message, is_error=False)
                    self.master.after(1000, self.show_dashboard)
                    return

            # Should not happen if search was successful
            self.update_feedback_label.config(text="Internal Error: Active booking not found.", fg=self.ERROR_COLOR)

        ttk.Button(search_frame, text="Search", command=search_booking, style='TButton').pack(side=tk.LEFT, padx=10, ipady=0, ipadx=10)

        update_btn = ttk.Button(update_frame, text="Apply Update", command=perform_update, style='TButton', state=tk.DISABLED)
        update_btn.pack(pady=10, ipadx=40, ipady=5)

        ttk.Button(self.current_frame, text="← Back", command=self.show_dashboard, style='TButton').pack(pady=20, ipadx=40, ipady=5)

    # --- Feature: Housekeeping Status ---
    def show_housekeeping_screen(self):
        self.change_screen(self._housekeeping_layout)

    def _housekeeping_layout(self):
        tk.Label(self.current_frame, text="🧹 Housekeeping Status", bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.SUBTITLE_FONT).pack(pady=20)

        # Treeview Table
        columns = ("Room No", "Status", "Last Cleaned By")
        tree = ttk.Treeview(self.current_frame, columns=columns, show='headings', height=10, style='Treeview')

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, anchor=tk.CENTER, width=150)

        tree.column("Room No", width=80)

        self.housekeeping_feedback_label = self._create_feedback_label(self.current_frame)
        self.housekeeping_feedback_label.pack(pady=5)

        def refresh_table():
            # Clear existing data
            for item in tree.get_children():
                tree.delete(item)

            for room in sorted(ROOMS, key=lambda r: int(r)):
                # Ensure every room has an entry in housekeeping data
                if room not in self.housekeeping:
                     self.housekeeping[room] = {"status": "Clean", "last_cleaned_by": "System"}

                status_data = self.housekeeping.get(room, {"status": "Unknown", "last_cleaned_by": None})
                status = status_data['status']

                # Tagging for color coding
                tag = 'clean'
                if status == 'Needs Cleaning': tag = 'dirty'
                elif status == 'In Progress': tag = 'progress'

                # Insert row with status
                tree.insert("", tk.END, values=(
                    room,
                    status,
                    status_data.get('last_cleaned_by', '-') if status_data.get('last_cleaned_by') else '-'
                ), tags=(tag, room,))

            # Define colors for tags
            tree.tag_configure('clean', foreground=self.SUCCESS_COLOR)
            tree.tag_configure('dirty', foreground='red')
            tree.tag_configure('progress', foreground=self.ACCENT_COLOR)

        def handle_action_button():
            selected_item = tree.focus()
            self.housekeeping_feedback_label.config(text="")

            if not selected_item:
                self.housekeeping_feedback_label.config(text="Please select a room to update its status.", fg=self.ERROR_COLOR)
                self.show_status("Warning: No room selected for housekeeping update.", is_error=True)
                return

            room_no = tree.item(selected_item, 'values')[0]
            current_status = self.housekeeping.get(room_no, {}).get("status")

            new_status = ""
            action_message = ""

            if current_status == 'Clean':
                new_status = 'Needs Cleaning'
                action_message = "Room marked as 'Needs Cleaning'."
            elif current_status == 'Needs Cleaning':
                new_status = 'In Progress'
                action_message = "Cleaning started."
            elif current_status == 'In Progress':
                new_status = 'Clean'
                action_message = "Room marked as 'Clean'."
            else:
                new_status = 'Needs Cleaning'
                action_message = "Room status reset to 'Needs Cleaning'."

            # Update the in-memory data
            self.housekeeping[room_no]["status"] = new_status
            self.housekeeping[room_no]["last_cleaned_by"] = self.current_user if new_status == 'Clean' else None

            self.save_all_data()
            success_message = f"Room {room_no} status changed to '{new_status}'. {action_message}"
            self.show_status(success_message, is_error=False)
            self.housekeeping_feedback_label.config(text=success_message, fg=self.SUCCESS_COLOR)
            refresh_table() # Refresh the view to show changes

        tree.pack(padx=20, pady=10)

        ttk.Button(self.current_frame, text="Update Selected Room Status", command=handle_action_button, style='TButton').pack(pady=10, ipadx=40, ipady=5)

        refresh_table()

        ttk.Button(self.current_frame, text="← Back", command=self.show_dashboard, style='TButton').pack(pady=20, ipadx=40, ipady=5)

    # --- Feature: Revenue Report ---

    def calculate_revenue(self, report_type):
        """Calculates total revenue for a given period."""
        now = datetime.now()
        start_date = now

        if report_type == 'Daily':
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif report_type == 'Weekly':
            # Calculate start of current week (Monday)
            start_of_week = now - timedelta(days=now.weekday())
            start_date = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
        elif report_type == 'Monthly':
            start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Note: 'All Time' is handled by using a very old start_date implicitly for the rest of the loop

        total_revenue = 0

        for booking in self.bookings:
            try:
                # Calculate revenue only for checked-out rooms since start_date
                if booking.get('status') == 'Checked Out':
                    checkout_dt_str = booking.get('checkout_datetime')
                    if not checkout_dt_str: continue

                    checkout_dt = datetime.strptime(checkout_dt_str, "%d-%m-%Y %I:%M %p")

                    if report_type == 'All Time' or checkout_dt >= start_date:
                        days = int(booking.get('days', 1)) # Default to 1 day for safety
                        food_plan = booking.get('food_plan', 'None')

                        room_charge = ROOM_RATE * days
                        food_charge = FOOD_PRICES.get(food_plan, 0) * days
                        subtotal = room_charge + food_charge
                        total_revenue += subtotal * (1 + GST_RATE) # Include GST in total revenue

            except Exception as e:
                # print(f"Skipping bad booking data in revenue calculation: {e}")
                pass

        return total_revenue

    def show_revenue_report_screen(self):
        self.change_screen(self._revenue_report_layout)

    def _revenue_report_layout(self):
        tk.Label(self.current_frame, text="📈 Revenue Report", bg=self.BG_COLOR, fg=self.ACCENT_COLOR, font=self.SUBTITLE_FONT).pack(pady=20)

        # Display Area
        report_display = tk.Text(self.current_frame, height=15, width=70,
                               bg=self.FRAME_COLOR, fg=self.TEXT_COLOR,
                               relief=tk.FLAT, font=('Courier New', 14))
        report_display.pack(pady=10)

        # Feedback label for report status
        self.report_feedback_label = self._create_feedback_label(self.current_frame)
        self.report_feedback_label.pack(pady=5)

        def display_report(report_type):

            # Recalculate all for the comparison
            daily_rev = self.calculate_revenue('Daily')
            weekly_rev = self.calculate_revenue('Weekly')
            monthly_rev = self.calculate_revenue('Monthly')
            all_time_rev = self.calculate_revenue('All Time')

            revenue = self.calculate_revenue(report_type)

            report_display.delete('1.0', tk.END)

            report_text = f"              --- Hotel Revenue Report ---\n\n"
            report_text += f"{'      Total Revenue (Daily):':<30} ₹{daily_rev:>18,.2f}\n"
            report_text += f"{'      Total Revenue (Weekly):':<30} ₹{weekly_rev:>18,.2f}\n"
            report_text += f"{'      Total Revenue (Monthly):':<30} ₹{monthly_rev:>18,.2f}\n"
            report_text += f"{'      Total Revenue (All Time):':<30} ₹{all_time_rev:>18,.2f}\n"
            report_text += "\n"
            report_text += f"      --------------------------------------------------\n"
            report_text += f"{f'      SELECTED REPORT ({report_type.upper()}):':<30} ₹{revenue:>18,.2f}\n"

            report_display.insert(tk.END, report_text)
            self.show_status(f"Generated {report_type} Revenue Report.")
            self.report_feedback_label.config(text=f"Report generated for {report_type}.", fg=self.SUCCESS_COLOR)

        # Report Buttons
        button_frame = tk.Frame(self.current_frame, bg=self.BG_COLOR)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Daily Report", command=lambda: display_report('Daily'), style='TButton').pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Weekly Report", command=lambda: display_report('Weekly'), style='TButton').pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Monthly Report", command=lambda: display_report('Monthly'), style='TButton').pack(side=tk.LEFT, padx=10)

        # Initial display (Monthly by default)
        display_report('Monthly')

        ttk.Button(self.current_frame, text="← Back", command=self.show_dashboard, style='TButton').pack(pady=20, ipadx=40, ipady=5)

if __name__ == '__main__':
    root = tk.Tk()
    app = HotelApp(root)

    # Save data on window close
    def on_closing():
        app.save_all_data()
        # Destroy Toplevel windows before root to prevent crashes
        for widget in root.winfo_children():
            if isinstance(widget, tk.Toplevel):
                widget.destroy()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()
