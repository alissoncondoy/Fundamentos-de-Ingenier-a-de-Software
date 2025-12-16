from django.contrib.auth.hashers import check_password, make_password


def is_django_hashed(value: str | None) -> bool:
    if not value:
        return False
    return (
        value.startswith("pbkdf2_")
        or value.startswith("bcrypt_")
        or value.startswith("argon2")
        or value.startswith("scrypt_")
    )


def make_password_if_needed(raw_password: str) -> str:
    # Use Django default hasher (PBKDF2 by default)
    return make_password(raw_password)


def verify_and_upgrade_password(stored_hash: str | None, raw_password: str) -> tuple[bool, str | None]:
    """
    Returns (ok, new_hash_if_upgraded)

    - If stored_hash is a Django hash => check_password()
    - Else treat as plaintext legacy => compare and upgrade to Django hash on success
    """
    if not stored_hash:
        return False, None

    if is_django_hashed(stored_hash):
        return (check_password(raw_password, stored_hash), None)

    # Legacy plaintext fallback
    if stored_hash == raw_password:
        return True, make_password_if_needed(raw_password)
    return False, None
