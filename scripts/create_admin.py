#!/usr/bin/env python3
"""Create or promote an administrator account.

The admin API (/api/v1/admin/...) is protected by the `admin` role, but the
role has to be assigned to somebody first. This script creates a new admin
account or promotes an existing user.

Usage:
    uv run python scripts/create_admin.py --username admin --email admin@example.com
    uv run python scripts/create_admin.py --promote existing_username
    uv run python scripts/create_admin.py --username admin --email admin@example.com --password 'S3cret!'

Without --password the password is read from the terminal without echo.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models.user import User

VALID_ROLES = ("user", "editor", "admin")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create or promote an administrator account")
    parser.add_argument("--username", help="Username of the new account")
    parser.add_argument("--email", help="Email address of the new account")
    parser.add_argument("--password", help="Password (prompted for when omitted)")
    parser.add_argument("--promote", metavar="USERNAME", help="Promote an existing account to admin")
    parser.add_argument("--role", default="admin", choices=VALID_ROLES, help="Role to assign (default: admin)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.promote:
        username = args.promote
    elif args.username and args.email:
        username = args.username
    else:
        print("Error: provide --username and --email, or --promote USERNAME", file=sys.stderr)
        return 2

    password = args.password
    if not args.promote and not password:
        password = getpass.getpass("Password: ")
        if not password:
            print("Error: the password cannot be empty", file=sys.stderr)
            return 2

    db = SessionLocal()
    try:
        result = db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if user is None:
            if not args.username or not args.email:
                print(
                    f"Error: user '{username}' does not exist; pass --username and --email to create it",
                    file=sys.stderr,
                )
                return 1
            user = User(
                username=username,
                email=args.email,
                hashed_password=get_password_hash(password),
                role=args.role,
                is_active=True,
                is_email_verified=True,
            )
            db.add(user)
            action = "created"
        else:
            user.role = args.role
            if password:
                user.hashed_password = get_password_hash(password)
            action = "updated"

        db.commit()
        print(f"Administrator '{username}' {action} with role '{args.role}'")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
