"""Adversarial correctness tests for the single-page read cache added to
``ScratchFileBuffer`` (byte-granular ``read()`` no longer re-copies a full
page per byte). The cache must never serve stale bytes after a write, a
cross-page seek, or a ``clear()``.

Every test drives the buffer against a plain ``bytearray`` reference model
and asserts byte-for-byte identity. Multi-page buffers are exercised so the
page-crossing invalidation paths are covered.
"""

from __future__ import annotations

import random

import pytest

from pypdfbox.io import ScratchFile

PAGE = 4096


def _new_buffer():
    sf = ScratchFile()
    return sf, sf.create_buffer()


def _read_all_via_single(buf) -> bytes:
    """Read the whole buffer one byte at a time via ``read()``."""
    buf.seek(0)
    out = bytearray()
    while True:
        b = buf.read()
        if b == buf.EOF:
            break
        out.append(b)
    return bytes(out)


def test_byte_by_byte_read_matches_reference_multi_page() -> None:
    ref = bytes((i * 37 + 11) & 0xFF for i in range(3 * PAGE + 123))
    sf, buf = _new_buffer()
    try:
        buf.write_bytes(ref)
        assert _read_all_via_single(buf) == ref
        # Bulk read must agree with the byte-granular read.
        buf.seek(0)
        bulk = bytearray(len(ref))
        assert buf.read_into(bulk) == len(ref)
        assert bytes(bulk) == ref
    finally:
        sf.close()


def test_read_after_overwrite_is_not_stale() -> None:
    ref = bytearray(b"A" * (2 * PAGE + 500))
    sf, buf = _new_buffer()
    try:
        buf.write_bytes(ref)
        # Read the first byte so the first page is cached in the scratch.
        buf.seek(0)
        assert buf.read() == ref[0]
        # Overwrite a slice that straddles the cached page, then read it back.
        patch = b"ZYXW" * 40  # 160 bytes
        pos = PAGE - 50  # crosses the page-0 / page-1 boundary
        buf.seek(pos)
        buf.write_bytes(patch)
        ref[pos : pos + len(patch)] = patch
        # The cache from the earlier read() must have been invalidated.
        assert _read_all_via_single(buf) == bytes(ref)
    finally:
        sf.close()


def test_overwrite_same_cached_page_then_read() -> None:
    ref = bytearray((i * 13) & 0xFF for i in range(PAGE // 2))
    sf, buf = _new_buffer()
    try:
        buf.write_bytes(ref)
        # Cache page 0 by reading a byte near the middle.
        buf.seek(100)
        assert buf.read() == ref[100]
        # Overwrite a byte in the SAME page; the read cache must not shadow it.
        buf.seek(100)
        buf.write(0xAB)
        ref[100] = 0xAB
        buf.seek(100)
        assert buf.read() == 0xAB
        assert _read_all_via_single(buf) == bytes(ref)
    finally:
        sf.close()


def test_cross_page_seek_reads_correct_page() -> None:
    # Distinct content per page so a wrong-page cache hit would be visible.
    ref = bytes(((i // PAGE) * 7 + (i % PAGE)) & 0xFF for i in range(4 * PAGE))
    sf, buf = _new_buffer()
    try:
        buf.write_bytes(ref)
        # Jump across page boundaries, reading a single byte each time.
        for pos in (0, PAGE, 2 * PAGE, PAGE - 1, 3 * PAGE + 7, 5, 2 * PAGE - 1):
            buf.seek(pos)
            assert buf.read() == ref[pos], f"mismatch at {pos}"
    finally:
        sf.close()


def test_clear_invalidates_cache() -> None:
    sf, buf = _new_buffer()
    try:
        buf.write_bytes(b"hello world" * 1000)
        buf.seek(0)
        assert buf.read() == ord("h")  # caches page 0
        buf.clear()
        assert buf.length() == 0
        buf.write_bytes(b"XYZ")
        buf.seek(0)
        # Must read the freshly written data, never the stale cached page.
        assert _read_all_via_single(buf) == b"XYZ"
    finally:
        sf.close()


@pytest.mark.parametrize("seed", [0, 1, 2, 7, 99])
def test_randomized_interleavings_match_bytesio(seed: int) -> None:
    rng = random.Random(seed)
    size = 3 * PAGE + rng.randint(0, PAGE)
    ref = bytearray(rng.getrandbits(8) for _ in range(size))
    sf, buf = _new_buffer()
    try:
        buf.write_bytes(ref)
        for _ in range(400):
            op = rng.random()
            if op < 0.35:
                # single-byte read at a random position
                pos = rng.randrange(size)
                buf.seek(pos)
                assert buf.read() == ref[pos]
            elif op < 0.6:
                # bulk read of a random span
                pos = rng.randrange(size)
                length = rng.randint(1, min(2 * PAGE, size - pos))
                buf.seek(pos)
                dst = bytearray(length)
                n = buf.read_into(dst)
                assert n == length
                assert bytes(dst) == bytes(ref[pos : pos + length])
            else:
                # overwrite a random span (never grows the buffer here)
                pos = rng.randrange(size)
                length = rng.randint(1, min(2 * PAGE, size - pos))
                patch = bytes(rng.getrandbits(8) for _ in range(length))
                buf.seek(pos)
                buf.write_bytes(patch)
                ref[pos : pos + length] = patch
        # Final full comparison, byte-granular.
        assert _read_all_via_single(buf) == bytes(ref)
    finally:
        sf.close()
