import base64
import hashlib
import hmac
import secrets

HASH_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 260_000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    derived_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    key_b64 = base64.urlsafe_b64encode(derived_key).decode("ascii")
    return f"{HASH_ALGORITHM}${PBKDF2_ITERATIONS}${salt_b64}${key_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_raw, salt_b64, expected_key_b64 = password_hash.split("$", 3)
        iterations = int(iterations_raw)
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        expected_key = base64.urlsafe_b64decode(expected_key_b64.encode("ascii"))
    except (ValueError, TypeError):
        return False

    if algorithm != HASH_ALGORITHM or iterations < 1:
        return False

    derived_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(derived_key, expected_key)
