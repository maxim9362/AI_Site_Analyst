import base64
import hashlib
import hmac
import re
import secrets

HASH_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 260_000
SALT_BYTES = 16
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128
PASSWORD_RESET_TOKEN_BYTES = 32


COMMON_PASSWORDS = {
    "password",
    "password123",
    "qwerty",
    "qwerty123",
    "12345678",
    "123456789",
    "admin123",
    "letmein",
}


def validate_password_strength(password: str, email: str = "") -> list[str]:
    errors: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Пароль должен быть не короче {PASSWORD_MIN_LENGTH} символов.")
    if len(password) > PASSWORD_MAX_LENGTH:
        errors.append(f"Пароль должен быть не длиннее {PASSWORD_MAX_LENGTH} символов.")
    if not re.search(r"[a-z]", password):
        errors.append("Добавьте хотя бы одну строчную латинскую букву.")
    if not re.search(r"[A-Z]", password):
        errors.append("Добавьте хотя бы одну заглавную латинскую букву.")
    if not re.search(r"\d", password):
        errors.append("Добавьте хотя бы одну цифру.")
    if not re.search(r"[^A-Za-z0-9]", password):
        errors.append("Добавьте хотя бы один специальный символ.")

    normalized = password.strip().lower()
    if normalized in COMMON_PASSWORDS:
        errors.append("Этот пароль слишком распространен.")

    local_part = email.split("@", 1)[0].lower() if email and "@" in email else ""
    if local_part and len(local_part) >= 4 and local_part in normalized:
        errors.append("Пароль не должен содержать часть email.")

    if re.search(r"(.)\1{3,}", password):
        errors.append("Не используйте длинные повторы одного символа.")

    return errors


def generate_password_reset_token() -> str:
    return secrets.token_urlsafe(PASSWORD_RESET_TOKEN_BYTES)


def hash_password_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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
