import os

class Config:
    """Application configuration for Taj Banjara Hotel Management System Web App."""

    # Base directory of the web application
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    # Production environment detection
    IS_PRODUCTION = os.environ.get('RENDER') is not None or os.environ.get('FLASK_ENV') == 'production'

    # Secret key for session management and CSRF tokens.
    # In production, SECRET_KEY MUST be provided via environment variable; source code never stores production secrets.
    _DEV_SECRET = 'taj-banjara-dev-secret-key-change-in-production-2026'
    _env_secret = os.environ.get('SECRET_KEY')

    if IS_PRODUCTION and (not _env_secret or _env_secret == _DEV_SECRET):
        raise RuntimeError(
            "FATAL SECURITY ERROR: In production environments, SECRET_KEY must be set to a secure, "
            "random environment variable. Never run production instances with default or empty keys."
        )

    SECRET_KEY = _env_secret or _DEV_SECRET

    # Initial administrator password for database initialization.
    # In production environments, INITIAL_ADMIN_PASSWORD must be provided via environment variable.
    INITIAL_ADMIN_PASSWORD = os.environ.get('INITIAL_ADMIN_PASSWORD')

    # Database path:
    # Defaults to local web-app/data/hotel_web.db.
    # On Render, set DATABASE_PATH to persistent disk location (e.g. /var/data/hotel_web.db)
    DATABASE_PATH = os.environ.get(
        'DATABASE_PATH',
        os.path.join(BASE_DIR, 'data', 'hotel_web.db')
    )

    # Persistence verification:
    # When deployed on Render or when explicitly enabled, persistent storage is strictly required.
    REQUIRE_PERSISTENT_STORAGE = (
        os.environ.get('REQUIRE_PERSISTENT_STORAGE', 'false').lower() in ('true', '1', 'yes')
        or (IS_PRODUCTION and DATABASE_PATH.startswith('/var/data'))
    )

    # Pricing & Business Constants (Identical to original desktop application)
    ROOMS = [str(i) for i in range(101, 111)]  # Rooms 101 to 110
    ROOM_RATE = 15000  # ₹15,000 per day
    FOOD_PRICES = {
        "None": 0,
        "Normal": 500,
        "VIP": 1000
    }
    GST_RATE = 0.18  # 18% Goods and Services Tax

    # Security & Session Settings
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # When deployed on Render or running with HTTPS, require Secure cookie flag
    SESSION_COOKIE_SECURE = IS_PRODUCTION
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds

    # Public Demo Protection
    # Enable safe demo access (receptionist demo login with synthetic data only)
    DEMO_MODE = os.environ.get('DEMO_MODE', 'true').lower() in ('true', '1', 'yes')

    # Optional setup token to protect the first-time administrator setup in public deployments
    SETUP_TOKEN = os.environ.get('SETUP_TOKEN', '')
