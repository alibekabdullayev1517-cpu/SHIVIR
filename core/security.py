"""Fingerprint hashing and CSRF token handling.

Privacy note: raw IP addresses are never persisted anywhere. They are used only
transiently, within a single request, to derive a one-way HMAC hash. That hash
(not the IP) is what gets stored, and only for the purpose of abuse prevention
(rate limiting, blocking repeat senders). Because it's a keyed one-way hash, it
cannot be reversed back to an IP/device even by us.
"""

import hashlib
import hmac
import time


def compute_fingerprint(secret_key: str, ip: str, user_agent: str) -> str:
    """Stable, irreversible per-sender fingerprint.

    Stable (not time-bucketed) on purpose: a recipient's block must keep working
    against the same sender indefinitely, not just within the day it was created.
    """
    message = f"{ip}|{user_agent}".encode()
    digest = hmac.new(secret_key.encode(), message, hashlib.sha256).hexdigest()
    return digest[:32]


def generate_csrf_token(secret_key: str, context: str, ttl_seconds: int = 3600) -> str:
    issued_at = int(time.time())
    payload = f"{context}|{issued_at}"
    signature = hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{issued_at}.{signature}"


def verify_csrf_token(secret_key: str, token: str, context: str, ttl_seconds: int = 3600) -> bool:
    try:
        issued_at_str, signature = token.split(".", 1)
        issued_at = int(issued_at_str)
    except (ValueError, AttributeError):
        return False

    if time.time() - issued_at > ttl_seconds:
        return False

    payload = f"{context}|{issued_at}"
    expected = hmac.new(secret_key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
