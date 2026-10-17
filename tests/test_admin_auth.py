import sqlite3

import pytest

from src.admin_auth import authenticate_admin, create_admin


def test_only_one_admin_password_is_hashed_and_cannot_be_reprovisioned(tmp_path):
    path = tmp_path / "results.db"
    password = "test-only-password!"
    assert create_admin(path, password)
    with sqlite3.connect(path) as con:
        row = con.execute("SELECT username, password_hash FROM admin_users").fetchone()
        assert row[0] == "admin"
        assert password not in row[1] and row[1].startswith("pbkdf2_sha256$")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("INSERT INTO admin_users VALUES (2, 'another', 'hash')")
    assert authenticate_admin(path, "admin", password)
    assert not authenticate_admin(path, "admin", "wrong")
    assert not authenticate_admin(path, "' OR 1=1 --", password)
    assert not create_admin(path, "replacement")
    assert authenticate_admin(path, "admin", password)
    assert not authenticate_admin(path, "admin", "replacement")


def test_authentication_does_not_create_database_or_change_results(tmp_path):
    path = tmp_path / "missing.db"
    assert not authenticate_admin(path, "admin", "anything")
    assert not path.exists()
    with sqlite3.connect(path) as con:
        con.execute("CREATE TABLE golden_runs (id INTEGER)")
        con.execute("INSERT INTO golden_runs VALUES (10)")
    create_admin(path, "test-password")
    before = path.read_bytes()
    assert authenticate_admin(path, "admin", "test-password")
    assert not authenticate_admin(path, "admin", "bad-password")
    assert path.read_bytes() == before
    with sqlite3.connect(path) as con:
        assert con.execute("SELECT id FROM golden_runs").fetchone() == (10,)
