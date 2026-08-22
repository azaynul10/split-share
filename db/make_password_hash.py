"""Generate a Django-compatible PBKDF2 password hash.

Usage:
    python db/make_password_hash.py demo1234

The output string can be pasted straight into Users.password_hash.
Django's check_password() reads the algorithm, iteration count and salt
back out of the string, so no Django install is needed to produce one.
"""

import base64
import hashlib
import secrets
import string
import sys

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 600_000
SALT_LENGTH = 16


def make_password(raw_password: str, salt: str | None = None) -> str:
    if salt is None:
        alphabet = string.ascii_lowercase + string.digits
        salt = "".join(secrets.choice(alphabet) for _ in range(SALT_LENGTH))

    digest = hashlib.pbkdf2_hmac(
        "sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), ITERATIONS
    )
    encoded = base64.b64encode(digest).decode("ascii").strip()
    return f"{ALGORITHM}${ITERATIONS}${salt}${encoded}"


def check_password(raw_password: str, encoded: str) -> bool:
    algorithm, iterations, salt, digest = encoded.split("$", 3)
    if algorithm != ALGORITHM:
        return False
    expected = hashlib.pbkdf2_hmac(
        "sha256", raw_password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
    )
    return secrets.compare_digest(base64.b64encode(expected).decode("ascii"), digest)


if __name__ == "__main__":
    password = sys.argv[1] if len(sys.argv) > 1 else "demo1234"
    encoded = make_password(password, salt="sxk29fqp1mz7vbnd")
    print(encoded)
    print("verified:", check_password(password, encoded))
