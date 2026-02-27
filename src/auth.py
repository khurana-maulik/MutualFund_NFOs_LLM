"""
auth.py — Authentication module for SID Chatbot.

Handles user registration, login, and session management.
Uses SQLite (same DB as fund data) + bcrypt for password hashing.

Tables:
  - users: Stores user credentials and profile info
"""

import sqlite3
import bcrypt
from datetime import datetime
from contextlib import contextmanager
from src.config import DATABASE_PATH


# ── Database Helpers ──────────────────────────────────────────────────

@contextmanager
def _get_conn():
    """Context manager for auth database connections."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_users_table():
    """Create the users table if it doesn't exist."""
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email
            ON users(email)
        """)
        conn.commit()


# ── Registration ──────────────────────────────────────────────────────

def register_user(username: str, email: str, password: str) -> dict:
    """
    Register a new user.

    Args:
        username: Display name
        email: Unique email address
        password: Plain-text password (hashed before storage)

    Returns:
        {"success": True, "user_id": int} on success
        {"success": False, "error": str} on failure
    """
    # Validate inputs
    if not username or not email or not password:
        return {"success": False, "error": "All fields are required."}

    if len(password) < 6:
        return {"success": False, "error": "Password must be at least 6 characters."}

    if "@" not in email or "." not in email:
        return {"success": False, "error": "Please enter a valid email address."}

    # Hash the password
    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    try:
        with _get_conn() as conn:
            cursor = conn.execute(
                """INSERT INTO users (username, email, password_hash)
                   VALUES (?, ?, ?)""",
                (username.strip(), email.strip().lower(), password_hash)
            )
            conn.commit()
            return {"success": True, "user_id": cursor.lastrowid}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "An account with this email already exists."}
    except Exception as e:
        return {"success": False, "error": f"Registration failed: {str(e)}"}


# ── Authentication ────────────────────────────────────────────────────

def authenticate_user(email: str, password: str) -> dict:
    """
    Authenticate a user by email and password.

    Args:
        email: User's email address
        password: Plain-text password to verify

    Returns:
        {"success": True, "user": dict} on success
        {"success": False, "error": str} on failure
    """
    if not email or not password:
        return {"success": False, "error": "Email and password are required."}

    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),)
        ).fetchone()

        if not row:
            return {"success": False, "error": "Invalid email or password."}

        # Verify password against hash
        stored_hash = row["password_hash"].encode("utf-8")
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
            # Update last login timestamp
            conn.execute(
                "UPDATE users SET last_login = ? WHERE id = ?",
                (datetime.now().isoformat(), row["id"])
            )
            conn.commit()

            return {
                "success": True,
                "user": {
                    "id": row["id"],
                    "username": row["username"],
                    "email": row["email"],
                    "created_at": row["created_at"],
                    "last_login": datetime.now().isoformat(),
                }
            }
        else:
            return {"success": False, "error": "Invalid email or password."}


# ── Utilities ─────────────────────────────────────────────────────────

def get_user_by_id(user_id: int) -> dict | None:
    """Get user details by ID (excludes password hash)."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, email, created_at, last_login FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()
        return dict(row) if row else None


def get_user_count() -> int:
    """Get total number of registered users."""
    with _get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()
        return row["cnt"]
