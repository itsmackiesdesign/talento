"""Small, local-only operational commands.

Usage inside the API container:
    python -m app.cli create-admin --email admin@example.com --name "Platform Admin"
"""

import argparse
import asyncio
import getpass

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import User


async def create_admin(email: str, name: str | None) -> None:
    email = email.lower().strip()
    async with SessionLocal() as db:
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            password = getpass.getpass("New admin password: ")
            if len(password) < 8:
                raise SystemExit("Password must contain at least 8 characters")
            confirmation = getpass.getpass("Confirm password: ")
            if password != confirmation:
                raise SystemExit("Passwords do not match")
            user = User(
                email=email,
                full_name=(name or "Platform Admin").strip(),
                password_hash=hash_password(password),
                is_platform_admin=True,
            )
            db.add(user)
            message = f"Created platform administrator {email}"
        else:
            user.is_platform_admin = True
            if name:
                user.full_name = name.strip()
            message = f"Granted platform administrator access to {email}"
        await db.commit()
        print(message)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-admin", help="create or promote a platform admin")
    create.add_argument("--email", required=True)
    create.add_argument("--name")
    args = parser.parse_args()
    if args.command == "create-admin":
        asyncio.run(create_admin(args.email, args.name))


if __name__ == "__main__":
    main()
