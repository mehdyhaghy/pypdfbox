"""Wave 1366 (agent B) — coverage round-out for :class:`TSAClient`.

The base ``test_tsa_client`` suite covers the transport seam and basic
auth header. This file fills:

* the ``_reset`` helper's "no ``.name`` attribute" fallback to
  ``"sha256"`` (the function is private but reachable through the public
  flow when the caller supplies a digest stub),
* the streaming-read loop with a multi-chunk ``content`` source (>8 KiB
  payload, exercises the ``while True`` body more than once),
* nonce monotonic uniqueness across repeated calls (sanity-check on the
  31-bit positive nonce),
* :meth:`get_tsa_response` returning the bytes from the transport
  verbatim (no munging of the response payload),
* the urllib fallback path with a monkeypatched ``urlopen`` so we never
  hit a real network.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from urllib.request import Request

import pytest

from pypdfbox.examples.signature import tsa_client as _tsa_module
from pypdfbox.examples.signature.tsa_client import TSAClient, _reset


class _NameLessDigest:
    """Hashlib-like stub without a ``.name`` attribute."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def update(self, data: bytes) -> None:
        self._buf.extend(data)

    def digest(self) -> bytes:
        return bytes(self._buf[:32]).ljust(32, b"\x00")


def test_reset_falls_back_to_sha256_when_digest_has_no_name() -> None:
    """``_reset`` calls ``getattr(digest, 'name', 'sha256')`` — verify the
    fallback path returns a fresh sha256 hasher when the stub lacks a
    ``name`` attribute."""
    fresh = _reset(_NameLessDigest())
    assert fresh.name == "sha256"
    # Must be a fresh hasher (digest of empty input != fresh.update once).
    empty_digest = fresh.digest()
    assert empty_digest == hashlib.sha256().digest()


def test_get_time_stamp_token_streams_large_payload() -> None:
    """The ``while True / read(8192)`` loop must iterate more than once
    when ``content`` is larger than the read buffer."""
    captured: dict = {}

    def fake_transport(request: bytes, url: str, headers: dict) -> bytes:
        captured["request"] = request
        return b"token-bytes"

    client = TSAClient(
        url="http://tsa.test.invalid",
        username=None,
        password=None,
        digest=hashlib.sha256(),
        transport=fake_transport,
    )
    payload = b"X" * (8192 * 4 + 17)  # 4 chunks + tail
    token = client.get_time_stamp_token(BytesIO(payload))
    assert token == b"token-bytes"
    # The transport saw a request whose hash bytes match sha256(payload).
    expected_hash = hashlib.sha256(payload).digest()
    assert expected_hash in captured["request"]


def test_nonce_changes_across_calls() -> None:
    """Two consecutive ``get_time_stamp_token`` invocations produce
    different nonces (statistical sanity for the 31-bit ``secrets``
    nonce — collisions astronomically unlikely)."""
    seen: list[bytes] = []

    def fake_transport(request: bytes, url: str, headers: dict) -> bytes:
        # The nonce is the trailing decimal field in the ad-hoc request format.
        seen.append(request.rsplit(b"|", 1)[-1])
        return b""

    client = TSAClient(
        url="http://tsa.test.invalid",
        username=None,
        password=None,
        digest=hashlib.sha256(),
        transport=fake_transport,
    )
    client.get_time_stamp_token(BytesIO(b"a"))
    client.get_time_stamp_token(BytesIO(b"b"))
    assert len(seen) == 2
    assert seen[0] != seen[1]


def test_get_tsa_response_returns_transport_bytes_verbatim() -> None:
    """``get_tsa_response`` is a thin wrapper — the response bytes must
    survive the round-trip without modification."""
    payload = bytes(range(32))

    def fake_transport(request: bytes, url: str, headers: dict) -> bytes:
        return payload

    client = TSAClient(
        url="http://tsa.test.invalid",
        username=None,
        password=None,
        digest=hashlib.sha256(),
        transport=fake_transport,
    )
    assert client.get_tsa_response(b"req") == payload


def test_get_tsa_response_uses_urllib_when_no_transport(monkeypatch) -> None:
    """The fallback path constructs a ``Request`` with the configured
    headers and POST method, then reads the response via ``urlopen``."""
    seen: dict = {}

    class _FakeResponse:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, *exc):  # noqa: D401
            return False

        def read(self) -> bytes:
            return self._body

    def _fake_urlopen(req: Request, timeout: int = 30):  # noqa: ARG001
        seen["url"] = req.full_url
        seen["headers"] = dict(req.header_items())
        seen["data"] = req.data
        seen["method"] = req.get_method()
        return _FakeResponse(b"resp-bytes")

    monkeypatch.setattr(_tsa_module, "urlopen", _fake_urlopen)

    client = TSAClient(
        url="http://tsa.example/path",
        username="alice",
        password="secret",
        digest=hashlib.sha256(),
    )
    out = client.get_tsa_response(b"my-request")
    assert out == b"resp-bytes"
    assert seen["url"] == "http://tsa.example/path"
    assert seen["data"] == b"my-request"
    assert seen["method"] == "POST"
    # urllib normalises header keys to Title-Case.
    norm_headers = {k.lower(): v for k, v in seen["headers"].items()}
    assert norm_headers["content-type"] == "application/timestamp-query"
    assert norm_headers["authorization"].startswith("Basic ")


def test_get_tsa_response_omits_auth_when_only_username_set() -> None:
    """Both username and password must be truthy for the basic-auth
    header to be added. With only one set the header is omitted."""
    seen: dict = {}

    def fake_transport(request: bytes, url: str, headers: dict) -> bytes:
        seen["headers"] = dict(headers)
        return b""

    client = TSAClient(
        url="http://tsa.test.invalid",
        username="alice",
        password=None,
        digest=hashlib.sha256(),
        transport=fake_transport,
    )
    client.get_tsa_response(b"req")
    assert "Authorization" not in seen["headers"]


def test_build_request_uses_resetted_digest_name() -> None:
    """The ad-hoc request format embeds the digest algorithm name
    (post-reset). For ``sha256`` we expect a ``b"sha256"`` literal."""

    seen: dict = {}

    def fake_transport(request: bytes, url: str, headers: dict) -> bytes:
        seen["req"] = request
        return b""

    client = TSAClient(
        url="http://tsa.test.invalid",
        username=None,
        password=None,
        digest=hashlib.sha256(),
        transport=fake_transport,
    )
    client.get_time_stamp_token(BytesIO(b"hello"))
    parts = seen["req"].split(b"|")
    # parts == [b"tsp-req", algorithm, digest, nonce]
    assert parts[0] == b"tsp-req"
    assert parts[1] == b"sha256"
    assert parts[2] == hashlib.sha256(b"hello").digest()
    # Nonce parses as a positive integer (31-bit positive nonce).
    assert int(parts[3]) >= 0


def test_build_request_with_sha512_digest_records_algorithm_name() -> None:
    """The digest name is round-tripped from the supplied hasher — not
    pinned to sha256."""
    seen: dict = {}

    def fake_transport(request: bytes, url: str, headers: dict) -> bytes:
        seen["req"] = request
        return b""

    client = TSAClient(
        url="http://tsa.test.invalid",
        username=None,
        password=None,
        digest=hashlib.sha512(),
        transport=fake_transport,
    )
    client.get_time_stamp_token(BytesIO(b"data"))
    # SHA-512 is the algorithm written into the request blob.
    assert b"|sha512|" in seen["req"]


@pytest.mark.parametrize(
    "auth_pair",
    [(None, None), ("", ""), (None, "pass"), ("user", "")],
    ids=["all-none", "all-empty", "only-pass", "only-user-empty-pass"],
)
def test_no_auth_header_when_credentials_missing(auth_pair) -> None:
    """No ``Authorization`` header should appear unless BOTH user and
    password are truthy."""
    user, pw = auth_pair
    seen: dict = {}

    def fake_transport(request: bytes, url: str, headers: dict) -> bytes:
        seen["headers"] = dict(headers)
        return b""

    client = TSAClient(
        url="http://tsa.test.invalid",
        username=user,
        password=pw,
        digest=hashlib.sha256(),
        transport=fake_transport,
    )
    client.get_tsa_response(b"req")
    assert "Authorization" not in seen["headers"]
