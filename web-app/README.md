# 👑 Taj Banjara Hotel — Management System (Web Application)

**A professional, full-stack browser-based conversion of the Taj Banjara Hotel Management System.**

### Project Credits
- **Project Owner & Sole Developer**: Mohd Shahid Moin Uddin

---

## 1. Project Overview & Architecture

This web application is a faithful, production-ready desktop-to-web conversion of the Python Tkinter Hotel Management System. It preserves all 10 core operational workflows, business rules, pricing models, and the signature **dark and gold luxury visual identity** of Taj Banjara Hotel.

### Technical Stack
- **Backend**: Python 3 (Flask) RESTful API with structured service-layer architecture.
- **Frontend**: Clean Vanilla HTML5, CSS3, and modern JavaScript (Single Page Application architecture, no external heavyweight frameworks or build step required).
- **Database**: SQLite3 with Write-Ahead Logging (WAL) enabled, thread-safe connections, and parameterized SQL queries to prevent injection attacks.
- **WSGI Production Server**: Gunicorn.
- **Security**: PBKDF2-HMAC-SHA256 password hashing with unique per-user salts, CSRF token validation on state-changing requests, and secure HTTP-only session cookies.

---

## 2. Visual Identity & Design System

The application strictly adopts the Taj Banjara Hotel dark luxury theme:
- **Primary Background**: `#1A1A1A`
- **Surface & Cards**: `#2C2C2C`
- **Primary Accent / Gold**: `#FFD700`
- **Hover & Highlight**: `#FFF200`
- **Text & Foreground**: `#FFFFFF`
- **Status Accents**: `#00FF00` (Success/Clean/Available), `#FF4D4D` (Occupied/Error), `#FFB800` (In Progress)
- **Brand Typography & Details**: Gold crown branding (`👑`), monospace ASCII receipt cards, and a real-time status bar at the bottom.

---

## 3. Feature Parity Breakdown

| Desktop Module (Tkinter) | Web Application Implementation | Route / Endpoint |
| :--- | :--- | :--- |
| **Welcome Screen** | Responsive hero panel with developer credits and quick system enter button | `GET /` |
| **First-Time Setup** | Setup wizard when 0 staff exist; strictly locked once any account exists | `POST /api/auth/setup` |
| **Staff Login** | Credential validation with one-click demo access pills for portfolio reviewers | `POST /api/auth/login` |
| **Dashboard** | Real-time KPI summary (Available, Occupied, Cleaning, Revenue) + 10-module action grid | `GET /api/rooms`, `GET /api/revenue/report` |
| **Book Room** | Auto-room assignment (Rooms 101–110), validation, concurrency locks | `POST /api/bookings` |
| **Checkout & Billing** | Dropdown of occupied rooms, bill breakdown preview, payment confirmation, transition to 'Needs Cleaning' | `GET /api/checkout/preview/<room>`, `POST /api/checkout/<room>` |
| **Search Guest** | Debounced real-time guest lookup across active and historical records | `GET /api/bookings/search?q=<query>` |
| **Room Status** | 10 interactive visual room cards + detailed status table | `GET /api/rooms` |
| **Staff Management** | Tabbed roster management with sequential ID generation (`S001`...) and edit modal (Admin only) | `GET /api/staff`, `POST /api/staff`, `PUT /api/staff/<id>` |
| **Booking History** | Complete historical ledger sorted newest first with total revenue billed | `GET /api/bookings/history` |
| **Update Booking** | Query active booking by room number and adjust guest days or meal options | `GET /api/bookings/active/<room>`, `PUT /api/bookings/active/<room>` |
| **Housekeeping** | Three-state cycle: `Clean` $\rightarrow$ `Needs Cleaning` $\rightarrow$ `In Progress` $\rightarrow$ `Clean` | `GET /api/housekeeping`, `POST /api/housekeeping/cycle/<room>` |
| **Revenue Report** | Daily, Weekly, Monthly, and All Time ASCII-formatted receipts with 18% GST breakdown | `GET /api/revenue/report?period=<period>` |

---

## 4. Business Logic & Calculation Formulas

All financial calculations strictly replicate the original application formulas:

1. **Room Tariff**: ₹15,000 per room per day (`ROOM_RATE = 15000`).
2. **Food Options**:
   - `None`: ₹0 per day
   - `Normal`: ₹500 per day
   - `VIP`: ₹1,000 per day
3. **Subtotal Calculation**:
   $$\text{Subtotal} = (\text{Days} \times 15,000) + (\text{Days} \times \text{Food Rate})$$
4. **Goods & Services Tax (GST)**:
   $$\text{GST} = \text{Subtotal} \times 0.18$$
5. **Grand Total**:
   $$\text{Total Cost} = \text{Subtotal} + \text{GST} = \text{Subtotal} \times 1.18$$

---

## 5. Security & Safe Public Demo Safeguards

1. **Restricted Public Demo Access**:
   - Portfolio visitors are provided with a dedicated, restricted **Demo Receptionist** account (`demo_staff` / `StaffPass@2026`).
   - Public visitors have access to operational workflows (room booking, room status, guest checkout, housekeeping, and revenue reports) using synthetic demo data.
   - **Public Administrator Demo Access is Completely Disabled**: Administrative functions, staff management, and first-time setup are strictly blocked and protected by `@admin_required` decorators (`403 Forbidden`).
   - Production secrets are never stored in source code. `SECRET_KEY` is enforced as an environment variable in production.
   - Real guest information or original desktop data (`hotel_data/`) is never touched, imported, or exposed.
2. **PBKDF2 Password Hashing**:
   - Passwords are encrypted with `hashlib.pbkdf2_hmac` using `sha256`, 100,000 iterations, and a cryptographically secure 16-byte random salt per user.
   - Backward compatibility: automatically validates legacy SHA-256 hashes and upgrades them to PBKDF2 upon successful authentication.
3. **CSRF Protection**:
   - Every session generates a secure CSRF token. All state-changing requests (`POST`, `PUT`, `DELETE`) require the `X-CSRF-Token` HTTP header.
4. **Access Control & Privilege Separation**:
   - Administrative endpoints (`/api/staff`, `/api/demo/reset`) are guarded by `@admin_required`, returning HTTP 403 Forbidden to demo receptionists or unprivileged users.
5. **Setup Lockout**:
   - Once the database is initialized, the setup endpoint (`/api/auth/setup` and `/api/setup/admin`) permanently returns HTTP 403 Forbidden to prevent public tampering.
6. **Fail-Safe Storage Verification**:
   - In production, the system verifies persistent disk mounts and write permissions before startup (`verify_storage_path`). If persistent storage is unmounted or unavailable, the application halts startup safely with a `RuntimeError` rather than silently using an unexpected ephemeral location.

---

## 6. Render Persistence & Hosting Economics

### The Ephemeral Filesystem Challenge
On Render's **Free Web Service** tier, the disk filesystem is **ephemeral**. This means:
- Any file written to disk (including SQLite databases) is wiped whenever the instance spins down due to inactivity (after 15 minutes of idle time) or when new code is deployed.
- A free-tier deployment will automatically reseed clean synthetic demo data upon every restart, which is safe for demo purposes but does not retain persistent changes across cold starts.

### True Persistence Configuration (Render Persistent Disk)
To maintain real persistent data across server redeployments and restarts:
1. Attach a **Render Persistent Disk** mounted at `/var/data`.
2. Configure the environment variable:
   ```env
   DATABASE_PATH=/var/data/hotel_web.db
   ```
3. **Hosting Cost Breakdown**:
   - Render Persistent Disks require a paid instance plan (minimum **Starter Plan** at **$7.00 / month**).
   - Persistent Disk storage costs **$0.25 / GB / month** (a 1 GB disk costs $0.25/mo).
   - **Total Estimated Cost for Persistent Hosting**: **$7.25 / month**.
4. Both deployment styles are fully supported by `web-app/render.yaml` and `web-app/config.py`.

---

## 7. Local Development & Testing

### Prerequisites
- Python 3.10+ (tested with Python 3.11, 3.12, 3.14)
- Web browser (Chrome, Firefox, Safari, Edge)

### Step 1: Install Dependencies
```bash
pip install -r web-app/requirements.txt
```

### Step 2: Run Automated Test Suite
Run the 16 unit, integration, and security tests:
```bash
python web-app/tests/test_backend.py
```

### Step 3: Start Local Web Server
```bash
python web-app/app.py
```
Or with Gunicorn:
```bash
gunicorn --chdir web-app --workers 1 --threads 4 app:app --bind 127.0.0.1:5000
```
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 8. Step-by-Step Render Deployment Guide

1. **Repository Setup**:
   Ensure `web-app/` and its configuration files are committed to your GitHub/GitLab repository.
2. **Create New Web Service on Render**:
   - Log in to your [Render Dashboard](https://dashboard.render.com/).
   - Click **New +** $\rightarrow$ **Web Service**.
   - Connect your GitHub repository.
3. **Configure Service Settings**:
   - **Name**: `taj-banjara-hotel-management`
   - **Region**: Choose the closest region (e.g., Singapore, Frankfurt, Oregon).
   - **Branch**: `main`
   - **Root Directory**: Leave blank (or specify `web-app` if deploying the subdirectory directly).
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r web-app/requirements.txt`
   - **Start Command**: `gunicorn --chdir web-app --workers 1 --threads 4 app:app`
4. **Environment Variables**:
   Under **Environment Variables**, add:
   - `SECRET_KEY`: (Click "Generate" or provide a secure random key)
   - `INITIAL_ADMIN_PASSWORD`: (Provide a secure password of at least 10 characters; production rejects default or hardcoded passwords)
   - `DEMO_MODE`: `true`
   - `DATABASE_PATH`: `/var/data/hotel_web.db` (if using Persistent Disk) or `web-app/data/hotel_web.db` (if using ephemeral disk).
5. **(Optional) Add Persistent Disk**:
   - If using the Starter Plan ($7/mo), scroll to **Disks** $\rightarrow$ **Add Disk**.
   - **Name**: `hotel-data-disk`
   - **Mount Path**: `/var/data`
   - **Size**: `1 GB`
6. **Health Check Path**:
   - Set **Health Check Path** to `/health`.
7. **Deploy**:
   - Click **Create Web Service**.
   - Render will build the environment, launch Gunicorn, verify the `/health` check, and publish your live URL.
