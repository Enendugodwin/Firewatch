"""Create or promote an operator account.

    python -m scripts.create_admin --email admin@example.com --password ...
    python -m scripts.create_admin --email admin@example.com --role analyst

The password is Argon2id-hashed. Omit ``--password`` to read it interactively so
it does not appear in shell history.
"""

from __future__ import annotations

import argparse
import getpass

from app.core.logging import configure_logging
from app.db.session import session_scope
from app.services import auth as auth_service


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", default=None)
    parser.add_argument("--display-name", default="")
    parser.add_argument(
        "--role", default="admin", choices=list(auth_service.ROLES)
    )
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password (min 10 chars): ")
    configure_logging()
    with session_scope() as session:
        user = auth_service.create_user(
            session,
            email=args.email,
            password=password,
            display_name=args.display_name or args.email,
            role=args.role,
        )
    print(f"created {user.email} ({user.role})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
