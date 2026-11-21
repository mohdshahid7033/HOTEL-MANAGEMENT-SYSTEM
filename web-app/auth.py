import os
import hashlib
import hmac
import secrets
from functools import wraps
from flask import session, request, jsonify, abort

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
      1. PBKDF2-HMAC-SHA256 with separate salt ('password_salt').
      2. PBKDF2-HMAC-SHA256 with embedded salt ('salt$hash').
      3. Legacy SHA-256 hexadecimal digests (64 hex characters, unsalted).
    Uses hmac.compare_digest for constant-time comparison to prevent timing attacks.
    """
    if not stored_password or not provided_password:
        return False

    # 1. PBKDF2-HMAC-SHA256 with separate salt parameter
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

    # 3. Legacy SHA-256 fallback (for compatibility)
    legacy_hash = hashlib.sha256(provided_password.encode('utf-8')).hexdigest()
    if hmac.compare_digest(legacy_hash, stored_password):
        return True

    return False

# --- CSRF Protection ---

def get_or_create_csrf_token():
    """Generates a CSRF token for the current session if not already present."""
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']

def verify_csrf():
    """
    Validates CSRF token on state-changing HTTP requests.
    Reads token from 'X-CSRF-Token' request header or JSON body.
    """
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        # Allow pre-flight / setup route exception if specifically handled
        token = request.headers.get('X-CSRF-Token')
        if not token and request.is_json:
            token = request.json.get('csrf_token') if isinstance(request.json, dict) else None

        session_token = session.get('csrf_token')
        if not token or not session_token or not hmac.compare_digest(token, session_token):
            return False
    return True

# --- Authentication & Authorization Decorators ---

def is_admin(designation):
    """Returns True if the designation corresponds to an administrator."""
    return str(designation or '').lower() in ('manager', 'administrator', 'admin')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({
                "success": False,
                "error": "Authentication required. Please log in."
            }), 401
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user_id'):
            return jsonify({
                "success": False,
                "error": "Authentication required. Please log in."
            }), 401

        designation = str(session.get('user_designation', '')).lower()
        if designation not in ('manager', 'administrator', 'admin'):
            return jsonify({
                "success": False,
                "error": "Access denied. Administrator privileges required."
            }), 403
        return f(*args, **kwargs)
    return decorated_function
