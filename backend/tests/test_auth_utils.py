from auth_utils import hash_password, verify_password


def test_hash_and_verify_password() -> None:
    plain = "debugiq-secret"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong-password", hashed) is False

