"""
Admin account provisioning — there is no self-signup.

Usage (from backend/):
    python scripts/create_user.py <username>              # prompts for password
    python scripts/create_user.py <username> --password P  # non-interactive
    python scripts/create_user.py <username> --deactivate  # disable an account
    python scripts/create_user.py --list                   # list accounts

Creating an existing username resets its password (with a confirmation prompt).
Needs the same DB_* env as the app (loaded from backend/.env or the environment).
"""
import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Same dummy-env fallback as export_openapi.py so Settings() can construct even
# when only DB_* matters; real values come from the environment / .env.
for _k, _v in (("DB_PORT", "5432"), ("DB_USER", "postgres"),
               ("DB_PASSWORD", "postgres"), ("DB_NAME", "postgres")):
    os.environ.setdefault(_k, _v)

from app.auth import hash_password  # noqa: E402
from app.db import User, get_session  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Create or manage SEMS app accounts.")
    ap.add_argument("username", nargs="?", help="account username")
    ap.add_argument("--password", help="password (omit to be prompted)")
    ap.add_argument("--deactivate", action="store_true", help="deactivate the account")
    ap.add_argument("--activate", action="store_true", help="re-activate the account")
    ap.add_argument("--list", action="store_true", help="list all accounts and exit")
    args = ap.parse_args()

    with get_session() as session:
        if args.list:
            users = session.query(User).order_by(User.username).all()
            if not users:
                print("(no accounts)")
            for u in users:
                print(f"{'ACTIVE ' if u.active else 'disabled'}  {u.username}")
            return 0

        if not args.username:
            ap.error("username is required (or use --list)")

        existing = session.query(User).filter(User.username == args.username).first()

        if args.deactivate or args.activate:
            if existing is None:
                print(f"No such account: {args.username}", file=sys.stderr)
                return 1
            existing.active = bool(args.activate)
            session.commit()
            print(f"{'Activated' if args.activate else 'Deactivated'} {args.username}")
            return 0

        password = args.password
        if not password:
            password = getpass.getpass("Password: ")
            if password != getpass.getpass("Confirm password: "):
                print("Passwords do not match.", file=sys.stderr)
                return 1
        if len(password) < 8:
            print("Password must be at least 8 characters.", file=sys.stderr)
            return 1

        if existing is not None:
            if input(f"{args.username} exists — reset its password? [y/N] ").strip().lower() != "y":
                print("Aborted.")
                return 1
            existing.password_hash = hash_password(password)
            existing.active = True
            session.commit()
            print(f"Password reset for {args.username}")
        else:
            session.add(User(username=args.username, password_hash=hash_password(password), active=True))
            session.commit()
            print(f"Created account {args.username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
