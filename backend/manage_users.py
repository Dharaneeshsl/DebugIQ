"""Operator-only account provisioning; passwords are entered without echo."""
import argparse
import getpass
from dotenv import load_dotenv


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", required=True)
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    load_dotenv(args.env, override=True)
    from mongo_store import init_mongo, create_user
    from auth_utils import hash_password
    from main import SignupRequest
    password = getpass.getpass("New user's password: ")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match")
    validated = SignupRequest(username=args.username, password=password)
    init_mongo()
    create_user(validated.username, hash_password(validated.password), "user")
    print("User created")
