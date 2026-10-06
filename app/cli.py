"""StreamBridge admin CLI.

Usage:
    python manage.py admin bootstrap          # create the first Admin (one-time)
    python manage.py admin reset-password     # reset an existing user's password
    python manage.py admin list               # list admin accounts

Passwords are read from a no-echo prompt. They are never accepted as command-line
arguments and never logged.
"""
import argparse
import getpass
import sys

from app.models.user import User, normalize_username, valid_username
from app.utils.db import SessionLocal, init_db
from app.utils.passwords import password_error


def _prompt_new_password() -> str | None:
    pw1 = getpass.getpass("New password: ")
    err = password_error(pw1)
    if err:
        print(f"error: {err}", file=sys.stderr)
        return None
    pw2 = getpass.getpass("Confirm password: ")
    if pw1 != pw2:
        print("error: passwords do not match", file=sys.stderr)
        return None
    return pw1


def cmd_bootstrap(_args: argparse.Namespace) -> int:
    init_db()
    with SessionLocal() as db:
        existing = db.query(User).filter(User.is_admin.is_(True), User.active.is_(True)).first()
        if existing:
            print(
                f"error: an active admin already exists ('{existing.username}'). "
                "Use 'admin reset-password' instead.",
                file=sys.stderr,
            )
            return 1

        raw_name = input("Admin username (email): ").strip()
        if not valid_username(raw_name):
            print("error: username must be 3-128 chars (letters, numbers, . _ @ + -)", file=sys.stderr)
            return 1
        username = normalize_username(raw_name)
        if db.query(User).filter(User.username == username).first():
            print(f"error: user '{username}' already exists", file=sys.stderr)
            return 1

        password = _prompt_new_password()
        if password is None:
            return 1

        user = User(username=username, active=True, is_admin=True, must_change_password=False)
        user.set_password(password)
        db.add(user)
        db.commit()
        print(f"Created admin '{username}'.")
        return 0


def cmd_reset_password(args: argparse.Namespace) -> int:
    init_db()
    username = normalize_username(args.username)
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"error: user '{username}' not found", file=sys.stderr)
            return 1
        password = _prompt_new_password()
        if password is None:
            return 1
        user.set_password(password)
        user.active = True
        user.must_change_password = False
        db.commit()
        print(f"Password reset for '{username}'.")
        return 0


def cmd_list(_args: argparse.Namespace) -> int:
    init_db()
    with SessionLocal() as db:
        admins = db.query(User).filter(User.is_admin.is_(True)).order_by(User.username).all()
        if not admins:
            print("No admin accounts.")
            return 0
        for u in admins:
            state = "active" if u.active else "disabled"
            print(f"{u.username}\t{state}")
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="manage.py")
    sub = parser.add_subparsers(dest="group", required=True)

    admin = sub.add_parser("admin", help="account administration")
    admin_sub = admin.add_subparsers(dest="action", required=True)

    admin_sub.add_parser("bootstrap", help="create the first admin (one-time)").set_defaults(func=cmd_bootstrap)

    reset = admin_sub.add_parser("reset-password", help="reset a user's password")
    reset.add_argument("--username", required=True)
    reset.set_defaults(func=cmd_reset_password)

    admin_sub.add_parser("list", help="list admin accounts").set_defaults(func=cmd_list)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
