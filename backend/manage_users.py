"""Operator-only account provisioning; passwords are entered without echo."""
import argparse
import getpass
from pathlib import Path

from dotenv import load_dotenv
from pymongo.errors import DuplicateKeyError


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("action", nargs="?", default="create", choices=("create", "reset-password", "disable", "enable"))
    args = parser.parse_args()
    if not Path(args.env).is_file():
        parser.error("the specified environment file does not exist")
    load_dotenv(args.env, override=True)
    from mongo_store import change_user_access, init_mongo, create_user
    from auth_utils import hash_password
    from runtime_config import production, validate_production

    validate_production()
    init_mongo()
    if args.action in {"disable", "enable"}:
        if not change_user_access(args.username, disabled=args.action == "disable"):
            raise SystemExit("Employee account not found")
        print("Account access updated and existing sessions invalidated")
    else:
        password = getpass.getpass("New password: ")
        if password != getpass.getpass("Confirm password: "):
            raise SystemExit("Passwords do not match")
        minimum = 16 if production() else 8
        if not minimum <= len(password) <= 256:
            raise SystemExit(f"Password must contain {minimum} to 256 characters")
        if not 3 <= len(args.username) <= 100 or any(character.isspace() for character in args.username):
            raise SystemExit("Username must contain 3 to 100 characters without whitespace")
        hashed = hash_password(password)
        if args.action == "create":
            try:
                create_user(args.username, hashed, "user")
            except DuplicateKeyError:
                raise SystemExit("Username already exists") from None
            print("User created")
        elif change_user_access(args.username, password_hash=hashed):
            print("Password reset and existing sessions invalidated")
        else:
            raise SystemExit("Account not found")
