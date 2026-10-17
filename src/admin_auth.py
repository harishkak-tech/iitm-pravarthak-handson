"""One database-backed administrator, with no plaintext password storage."""
from contextlib import closing
import hashlib
import hmac
from pathlib import Path
import secrets
import sqlite3


ITERATIONS = 600_000
SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    username TEXT NOT NULL UNIQUE CHECK (username = 'admin'),
    password_hash TEXT NOT NULL
);
"""


def create_admin(db_path: str | Path, password: str) -> bool:
    """Provision the only account once; never replace an existing password."""
    if not password:
        raise ValueError("An administrator password is required")
    salt = secrets.token_hex(32)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    encoded = f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"
    with closing(sqlite3.connect(db_path)) as con, con:
        con.executescript(SCHEMA)
        result = con.execute(
            "INSERT OR IGNORE INTO admin_users (id, username, password_hash) VALUES (1, 'admin', ?)",
            (encoded,),
        )
        return result.rowcount == 1


def authenticate_admin(db_path: str | Path, username: str, password: str) -> bool:
    """Verify credentials without creating or modifying the database."""
    path = Path(db_path).resolve()
    try:
        with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as con:
            row = con.execute("SELECT password_hash FROM admin_users WHERE id = 1 AND username = ?",
                              (username,)).fetchone()
        if not row:
            return False
        algorithm, iterations, salt, expected = row[0].split("$")
        if algorithm != "pbkdf2_sha256" or int(iterations) != ITERATIONS:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations)).hex()
        return hmac.compare_digest(actual, expected)
    except (sqlite3.Error, ValueError, TypeError, OSError):
        return False
