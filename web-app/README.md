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
6. **Storage Verification**:
   - The application verifies storage availability and write permissions at startup.
   - Persistent storage is required only when `REQUIRE_PERSISTENT_STORAGE` is enabled or the production database path is configured under `/var/data`.
   - The Render Free deployment uses `/tmp/hotel_web.db` on ephemeral storage and does not require a persistent disk. Database changes may be lost when the service restarts, spins down, or is redeployed.

---

## 6. Render Free-Tier Hosting & Ephemeral Architecture

### Free Web Service Plan (Zero Persistent Disks)
This portfolio demonstration is configured for **Render's Free Web Service Tier** ($0/month, zero persistent disks):
- **Free Instance Tier**: Runs on Render's 0.1 CPU, 512 MB RAM free container tier.
- **Zero Paid Subscriptions**: Requires no paid disks ($0.25/GB/mo) and no paid plans ($7/mo Starter).
- **Ephemeral Storage**: SQLite is stored at `/tmp/hotel_web.db`.

### How Ephemeral Storage Operates in the Free Tier
On Render's Free Web Service tier:
1. **Inactivity Sleep**: The instance spins down to conserve resources after 15 minutes of inactivity.
2. **Ephemeral Filesystem**: Because no paid persistent disk is configured, the local filesystem is ephemeral. Bookings, staff changes, and other database modifications must be considered temporary. Data may be lost whenever the service restarts, spins down due to inactivity, or is redeployed.
3. **Demo Initialization**: When a container starts with a fresh or uninitialized filesystem, the application automatically initializes a clean SQLite database and seeds synthetic demo records using the configured initialization process (`seed_safe_demo_data`). This ensures the public portfolio demo remains operational without requiring manual database administration.

### Required Environment Variables
The application configures the following environment variables (defined in `web-app/render.yaml`):

| Variable | Recommended Render Value | Purpose |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.11.8` | Ensures consistent, tested CPython runtime |
| `SECRET_KEY` | *(Generate via Render)* | 32+ character random secret for secure session encryption |
| `INITIAL_ADMIN_PASSWORD` | *(Generate via Render)* | Strong random password for initial administrator provisioning |
| `SETUP_TOKEN` | *(Generate via Render)* | Cryptographic token protecting first-time setup via constant-time verification |
| `DATABASE_PATH` | `/tmp/hotel_web.db` | Standard Linux temporary path for ephemeral SQLite storage |
| `DEMO_MODE` | `true` | Enables safe portfolio demo features (Demo Receptionist login) |

> [!NOTE]
> **Optional Persistent Storage (Paid)**: If permanent data retention across restarts is desired in the future, the application can be seamlessly transitioned to a Render Starter plan ($7/mo) with a 1 GB persistent disk ($0.25/mo) mounted at `/var/data` and `DATABASE_PATH=/var/data/hotel_web.db`. Both modes are fully supported by `config.py`.

---

## 7. Local Development & Testing

### Prerequisites
- Python 3.10+ (tested with Python 3.11, 3.12, 3.14)
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Step 1: Install Dependencies
```bash
pip install -r web-app/requirements.txt
```

### Step 2: Run Full Automated Test Suite
Run the automated unit, integration, security, and end-to-end tests with strict ResourceWarning detection:
```bash
python -W error::ResourceWarning -m unittest discover -v -s web-app/tests
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

## 8. Step-by-Step Render Free-Tier Deployment Guide

### Option A: Blueprint Deployment (Recommended)
1. Push your repository to GitHub: `https://github.com/mohdshahid7033/HOTEL-MANAGEMENT-SYSTEM`.
2. Log in to the [Render Dashboard](https://dashboard.render.com/).
3. Click **New +** $\rightarrow$ **Blueprint**.
4. Connect the `HOTEL-MANAGEMENT-SYSTEM` repository.
5. In the Blueprint configuration, specify or select the nested Blueprint file path `web-app/render.yaml` (since the blueprint file is located in the nested `web-app/` subdirectory rather than the repository root).
6. Render parses `web-app/render.yaml` and provisions:
   - Free Web Service plan ($0.00/mo).
   - Zero persistent disks.
   - Auto-generated secure values for `SECRET_KEY`, `INITIAL_ADMIN_PASSWORD`, and `SETUP_TOKEN`.
   - Ephemeral database storage at `/tmp/hotel_web.db`.
7. Click **Apply**. Render builds the service and outputs your live public HTTPS URL.

### Option B: Manual Web Service Setup
If configuring manually without the Blueprint:
1. In the Render Dashboard, click **New +** $\rightarrow$ **Web Service**.
2. Connect your GitHub repository.
3. Configure the service settings:
   - **Name**: `taj-banjara-hotel-management`
   - **Region**: Choose the closest region (e.g., Singapore, Frankfurt, Oregon).
   - **Branch**: `main`
   - **Root Directory**: *(Leave blank)*
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r web-app/requirements.txt`
   - **Start Command**: `gunicorn --chdir web-app --workers 1 --threads 4 app:app`
   - **Instance Type / Plan**: **Free** ($0.00 / month). Do **NOT** attach any disk.
4. Under **Environment Variables**, add:
   - `PYTHON_VERSION`: `3.11.8`
   - `SECRET_KEY`: Click **Generate** (or enter a random 32+ character string).
   - `INITIAL_ADMIN_PASSWORD`: Click **Generate** (or enter a secure 12+ character password).
   - `SETUP_TOKEN`: Click **Generate** (or enter a secure random token).
   - `DATABASE_PATH`: `/tmp/hotel_web.db`
   - `DEMO_MODE`: `true`
5. Under **Health Check Path**, enter: `/health`.
6. Click **Create Web Service**. Render builds the Python environment, runs the health check, and deploys the live demo.
