"""Tests for ``SHA1DigestCalculator``."""

from __future__ import annotations

import hashlib

from pypdfbox.examples.signature.cert.sha1_digest_calculator import (
    SHA1DigestCalculator,
)


def test_algorithm_oid_matches_sha1():
    calc = SHA1DigestCalculator()
    assert calc.get_algorithm_identifier() == "1.3.14.3.2.26"


def test_output_stream_feeds_hasher():
    calc = SHA1DigestCalculator()
    stream = calc.get_output_stream()
    stream.write(b"abc")
    stream.write(b"def")
    expected = hashlib.sha1(b"abcdef", usedforsecurity=False).digest()
    assert calc.get_digest() == expected


def test_empty_digest_matches_sha1_of_empty():
    calc = SHA1DigestCalculator()
    expected = hashlib.sha1(b"", usedforsecurity=False).digest()
    assert calc.get_digest() == expected
