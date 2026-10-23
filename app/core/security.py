import hashlib
import secrets

API_KEY_PREFIX = "sk_"


def generate_api_key() -> str:
    """Return a new random API key. Shown to the user exactly once."""
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def hash_api_key(key: str) -> str:
    """One-way hash. Only this is stored."""
    return hashlib.sha256(key.encode()).hexdigest()
