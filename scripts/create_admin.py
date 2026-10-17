"""Provision the single admin on a new deployment; prompts without echoing."""
from getpass import getpass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.admin_auth import create_admin


if __name__ == "__main__":
    created = create_admin(ROOT / "results.db", getpass("Admin password: "))
    print("Admin account created." if created else "Admin account already exists; password unchanged.")
