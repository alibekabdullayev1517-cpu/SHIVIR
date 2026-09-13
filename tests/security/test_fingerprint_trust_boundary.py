"""Regression test for a CRITICAL finding in the production launch audit:
client_fingerprint() was trusting the FIRST hop in X-Forwarded-For, which is
entirely attacker-controlled (a plain request header), instead of the LAST
hop appended by our own trusted Nginx layer. That let any sender forge a
fresh fingerprint per request, fully defeating rate limiting and blocks.
"""

from starlette.requests import Request

from core.config import get_settings
from web.routes.sender import client_fingerprint

settings = get_settings()


def _fake_request(headers: dict) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("203.0.113.9", 12345),  # the actual TCP peer (our Nginx, in prod)
    }
    return Request(scope)


def test_fingerprint_uses_last_hop_not_attacker_supplied_first_hop():
    # Attacker sends a forged X-Forwarded-For; Nginx appends the real IP after it.
    forged = _fake_request(
        {"x-forwarded-for": "9.9.9.9", "user-agent": "test-agent"}
    )
    # Simulate what Nginx actually produces: it appends via $proxy_add_x_forwarded_for,
    # so by the time the app sees it there are two entries — attacker's fake one
    # first, the real one (as Nginx saw it) last.
    forged.scope["headers"] = [
        (b"x-forwarded-for", b"9.9.9.9, 203.0.113.9"),
        (b"user-agent", b"test-agent"),
    ]

    fp = client_fingerprint(forged, settings)

    # It must NOT match a fingerprint computed from the attacker-forged value.
    spoofed_only = _fake_request({"x-forwarded-for": "9.9.9.9", "user-agent": "test-agent"})
    fp_if_spoofed_trusted = client_fingerprint(spoofed_only, settings)
    assert fp != fp_if_spoofed_trusted

    # It MUST match a request carrying only the real (last-hop) IP.
    real_only = _fake_request({"x-forwarded-for": "203.0.113.9", "user-agent": "test-agent"})
    fp_real = client_fingerprint(real_only, settings)
    assert fp == fp_real


def test_fingerprint_varying_forged_first_hop_does_not_change_result():
    """The actual attack this closes: spamming with a different forged
    X-Forwarded-For on every request must NOT yield a different fingerprint
    each time (which would bypass per-fingerprint rate limiting entirely)."""
    fingerprints = set()
    for fake_ip in ("1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"):
        req = _fake_request({})
        req.scope["headers"] = [
            (b"x-forwarded-for", f"{fake_ip}, 203.0.113.9".encode()),
            (b"user-agent", b"same-agent"),
        ]
        fingerprints.add(client_fingerprint(req, settings))

    assert len(fingerprints) == 1  # same real client -> same fingerprint, every time
