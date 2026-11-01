"""Reusable RSA test keys.

RSA key generation dominates the signing / public-key-encryption tests
(~25 ms per 2048-bit key, a few hundred keys per run). Most tests only need
"some RSA key", so :func:`pooled_rsa_key` hands out keys from a pool that is
reused across tests while keeping the semantics tests rely on:

* **Within one test, every call returns a different key**, exactly like
  repeated ``rsa.generate_private_key`` calls. The i-th call in a test gets
  pool slot i, so tests that build two identities (a signer and an
  "other" key, a root CA and a leaf, ...) still get distinct keys.
* **Keys made outside a single test's scope are never shared.** A key built
  at import time, or inside a class-, module-, package- or session-scoped
  fixture, outlives the test that triggered it, so it gets a dedicated slot
  that later tests never receive. A test therefore can never accidentally
  receive the same key as a longer-lived fixture it compares against.

The per-test counter and the fixture-scope tracking are driven by hooks in
``tests/conftest.py``. Tests that verify key generation itself should keep
calling ``rsa.generate_private_key`` directly.
"""

from cryptography.hazmat.primitives.asymmetric import rsa

_pools: dict[tuple[int, int], list[rsa.RSAPrivateKey]] = {}
_reserved: dict[tuple[int, int], set[int]] = {}

# State maintained by the hooks in tests/conftest.py.
_in_test = False
_test_counters: dict[tuple[int, int], int] = {}
_wide_scope_depth = 0


def _generate(public_exponent: int, key_size: int) -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=public_exponent, key_size=key_size)


def _slot(spec: tuple[int, int], index: int) -> rsa.RSAPrivateKey:
    pool = _pools.setdefault(spec, [])
    while len(pool) <= index:
        pool.append(_generate(*spec))
    return pool[index]


def pooled_rsa_key(key_size: int = 2048, public_exponent: int = 65537) -> rsa.RSAPrivateKey:
    """Drop-in for ``rsa.generate_private_key(public_exponent=..., key_size=...)``."""
    spec = (public_exponent, key_size)
    reserved = _reserved.setdefault(spec, set())
    if not _in_test or _wide_scope_depth:
        # Long-lived key: take a fresh slot no test will ever be handed.
        pool = _pools.setdefault(spec, [])
        index = len(pool)
        pool.append(_generate(*spec))
        reserved.add(index)
        return pool[index]
    index = _test_counters.get(spec, 0)
    while index in reserved:
        index += 1
    _test_counters[spec] = index + 1
    return _slot(spec, index)


def begin_test() -> None:
    global _in_test
    _in_test = True
    _test_counters.clear()


def end_test() -> None:
    global _in_test
    _in_test = False
    _test_counters.clear()


def enter_fixture(scope: str) -> bool:
    """Record entry into a fixture's setup. Returns whether it was wide."""
    global _wide_scope_depth
    if scope != "function":
        _wide_scope_depth += 1
        return True
    return False


def exit_fixture(wide: bool) -> None:
    global _wide_scope_depth
    if wide:
        _wide_scope_depth -= 1
