"""Wave 1396 branch-coverage tests for ``PDSeedValueCertificate``.

Closes the False-branch arrows for the remove_* helpers when the entry
is absent, the iteration filters when an array contains heterogeneous
items, and the byte-array decoder when entries are not strings:

* 139->exit — ``remove_subject`` no-op when /Subject is absent
* 150->149 — ``get_subject_dn`` skips non-dict items
* 177->176 — ``get_key_usage`` skips non-string items
* 226->exit — ``remove_key_usage`` no-op when /KeyUsage is absent
* 248->exit — ``remove_issuer`` no-op when /Issuer is absent
* 270->exit — ``remove_oid`` no-op when /OID is absent
* 481->480 — ``_byte_arrays_from_cos_array`` skips non-string entries
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSString
from pypdfbox.pdmodel.interactive.digitalsignature.pd_seed_value_certificate import (
    PDSeedValueCertificate,
    _byte_arrays_from_cos_array,
)


def test_remove_subject_when_subject_array_absent() -> None:
    """``remove_subject`` is a no-op when /Subject hasn't been set.

    Closes False arm at line 139.
    """
    cert = PDSeedValueCertificate()
    cert.remove_subject(b"unused")  # must not raise


def test_get_subject_dn_skips_non_dictionary_entries() -> None:
    """``get_subject_dn`` skips array entries that aren't dictionaries.

    Closes False arm of ``isinstance(item, COSDictionary)`` at line 150.
    """
    cert = PDSeedValueCertificate()
    array = COSArray()
    # Add a non-dict entry first, then a real one.
    array.add(COSInteger.get(99))
    real = COSDictionary()
    real.set_item("CN", COSString("Alice"))
    array.add(real)
    cert.get_cos_object().set_item("SubjectDN", array)
    dn = cert.get_subject_dn()
    assert dn is not None
    assert len(dn) == 1
    assert dn[0] == {"CN": "Alice"}


def test_get_key_usage_skips_non_string_entries() -> None:
    """``get_key_usage`` skips array entries that aren't strings.

    Closes False arm of ``isinstance(item, COSString)`` at line 177.
    """
    cert = PDSeedValueCertificate()
    array = COSArray()
    array.add(COSInteger.get(99))  # non-string — skipped
    array.add(COSString("100110000"))
    cert.get_cos_object().set_item("KeyUsage", array)
    ku = cert.get_key_usage()
    assert ku == ["100110000"]


def test_remove_key_usage_when_key_usage_array_absent() -> None:
    """``remove_key_usage`` is a no-op when /KeyUsage is absent.

    Closes False arm at line 226.
    """
    cert = PDSeedValueCertificate()
    cert.remove_key_usage("100110000")  # must not raise


def test_remove_issuer_when_issuer_array_absent() -> None:
    """``remove_issuer`` is a no-op when /Issuer is absent.

    Closes False arm at line 248.
    """
    cert = PDSeedValueCertificate()
    cert.remove_issuer(b"ignored")  # must not raise


def test_remove_oid_when_oid_array_absent() -> None:
    """``remove_oid`` is a no-op when /OID is absent.

    Closes False arm at line 270.
    """
    cert = PDSeedValueCertificate()
    cert.remove_oid(b"ignored")  # must not raise


def test_byte_arrays_from_cos_array_skips_non_string_entries() -> None:
    """``_byte_arrays_from_cos_array`` skips entries that aren't strings.

    Closes False arm of ``isinstance(item, COSString)`` at line 481.
    """
    arr = COSArray()
    arr.add(COSInteger.get(99))  # non-string — skipped
    arr.add(COSString(b"\x00\x01\x02"))
    decoded = _byte_arrays_from_cos_array(arr)
    assert decoded == [b"\x00\x01\x02"]
