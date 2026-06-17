"""Live Apache PDFBox differential fuzz of the PUBLIC-KEY (certificate /
``Adobe.PubSec``) encryption surface (wave 1550, agent C).

Driven by ``oracle/probes/PublicKeyHandlerFuzzProbe.java``. Distinct from the
adjacent encryption fuzz waves, which target the STANDARD handler:

* wave 1545 (``EncryptDictAccessorFuzzProbe`` / ``AccessPermissionFuzzProbe``)
  fuzzes the ``/V /R /Length /P`` decode + ``AccessPermission`` factory surface
  of the *standard* handler.
* wave 1524 fuzzes ``StandardSecurityHandler``.

This wave fuzzes the public-key cluster the others skip:

* ``PublicKeyProtectionPolicy`` — empty / single / multi-recipient bookkeeping,
  ``getNumberOfRecipients``, ``addRecipient`` + ``removeRecipient`` (present /
  absent / from-empty), iterator ordering, the decryption-cert slot and the
  inherited key-length / preferAES knobs.
* ``PublicKeyRecipient`` — default (null) construction + the x509 / permission
  accessor round-trip (identity preserved).
* ``AccessPermission.getPermissionBytesForPublicKey()`` — the bit re-encoding
  (bit 1 ON, bits 7/8 OFF, bits 13..32 cleared) each recipient's permission
  undergoes before it is packed into a ``/Recipients`` envelope.
* ``PDEncryption`` — the ``Adobe.PubSec`` encryption-DICTIONARY shape:
  ``/Filter``, ``/SubFilter`` variations (``adbe.pkcs7.s3/s4/s5``), ``/V`` +
  ``/R`` combos, and a MALFORMED ``/Recipients`` (missing / empty / wrong-type).

Why no real cert crypto: driving an X.509 cert + RSA key + CMS envelope through
a deterministic in-process oracle is impractical (key gen, provider availability,
non-reproducible envelope bytes). Per the wave brief we fuzz the
policy / recipient / permission-bit accessor surface + the encryption-dict shape
rather than a full encrypt/decrypt round-trip. ``PublicKeyRecipient`` holds a
null x509 here; none of the projected fields read the certificate.

Findings pinned BOTH-SIDES (Java == Python) unless noted:

* ``getPermissionBytesForPublicKey`` re-encodes IDENTICALLY on both runtimes —
  e.g. ``-1 -> 3903``, ``-44 -> 3861``, ``0 -> 1`` (bit 1 forced on), bits 7/8
  cleared (``0xC0 -> 1``), high bits 13.. cleared (``0x00FFF000 -> 1``); and the
  call MUTATES the receiver in place (``afterBytes`` equals ``forPublicKey``).
* ``removeRecipient`` uses object IDENTITY on BOTH sides: ``PublicKeyRecipient``
  has no ``equals`` override (Java) / no ``__eq__`` (Python), so removing an
  equal-but-distinct recipient returns ``false`` and removing from an empty
  policy returns ``false``.
* recipient iterator preserves insertion order; ``getNumberOfRecipients``
  tracks add/remove on both sides.

HONEST DIVERGENCE (pinned, Python side only — the upstream behaviour is also
asserted via the probe output so the gap is explicit):

* ``getRecipientsLength`` on a MALFORMED ``/Recipients``: upstream THROWS — a
  ``NullPointerException`` when the key is absent and a ``ClassCastException``
  when it is present but not an array (unchecked ``(COSArray)`` cast). pypdfbox's
  ``get_recipients_length`` instead returns ``0`` for both (its tolerant
  null-safe contract, pinned by ``test_pd_encryption``). The probe emits
  ``recipientsLen=ERR:<class>`` for these cases; the test asserts the Java side
  threw AND that the Python side returns 0, so the divergence is documented, not
  hidden.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.encryption.access_permission import AccessPermission
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption
from pypdfbox.pdmodel.encryption.public_key_protection_policy import (
    PublicKeyProtectionPolicy,
)
from pypdfbox.pdmodel.encryption.public_key_recipient import PublicKeyRecipient
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "PublicKeyHandlerFuzzProbe"


def _b(v: bool) -> str:
    return "true" if v else "false"


def _recip(perm: int) -> PublicKeyRecipient:
    return PublicKeyRecipient(permissions=AccessPermission(perm))


# --------------------------------------------------------------------- POLICY


def _py_policy(name: str) -> list[str]:
    lines: list[str] = []
    if name == "empty":
        p = PublicKeyProtectionPolicy()
        lines.append(f"count={p.get_number_of_recipients()}")
        lines.append(f"hasNext={_b(next(p.get_recipients_iterator(), None) is not None)}")
        lines.append(f"decryptCertNull={_b(p.get_decryption_certificate() is None)}")
        lines.append(f"keyLength={p.get_encryption_key_length()}")
        lines.append(f"preferAES={_b(p.is_prefer_aes())}")
    elif name == "single":
        p = PublicKeyProtectionPolicy()
        p.add_recipient(_recip(-44))
        lines.append(f"count={p.get_number_of_recipients()}")
        lines.append(f"hasNext={_b(next(p.get_recipients_iterator(), None) is not None)}")
    elif name == "three_order":
        p = PublicKeyProtectionPolicy()
        p.add_recipient(_recip(4))
        p.add_recipient(_recip(8))
        p.add_recipient(_recip(-1))
        lines.append(f"count={p.get_number_of_recipients()}")
        for i, r in enumerate(p.get_recipients_iterator()):
            lines.append(f"perm{i}={r.get_permission().get_permission_bytes()}")
    elif name == "remove_present":
        p = PublicKeyProtectionPolicy()
        a = _recip(4)
        b2 = _recip(8)
        p.add_recipient(a)
        p.add_recipient(b2)
        lines.append(f"removed={_b(p.remove_recipient(a))}")
        lines.append(f"count={p.get_number_of_recipients()}")
        first = next(p.get_recipients_iterator())
        lines.append(f"firstPerm={first.get_permission().get_permission_bytes()}")
    elif name == "remove_absent":
        p = PublicKeyProtectionPolicy()
        p.add_recipient(_recip(4))
        lines.append(f"removed={_b(p.remove_recipient(_recip(4)))}")
        lines.append(f"count={p.get_number_of_recipients()}")
    elif name == "remove_from_empty":
        p = PublicKeyProtectionPolicy()
        lines.append(f"removed={_b(p.remove_recipient(_recip(4)))}")
        lines.append(f"count={p.get_number_of_recipients()}")
    elif name == "key_length_default":
        p = PublicKeyProtectionPolicy()
        lines.append(f"keyLength={p.get_encryption_key_length()}")
        lines.append(f"preferAES={_b(p.is_prefer_aes())}")
    elif name == "key_length_set128":
        p = PublicKeyProtectionPolicy()
        p.set_encryption_key_length(128)
        p.set_prefer_aes(True)
        lines.append(f"keyLength={p.get_encryption_key_length()}")
        lines.append(f"preferAES={_b(p.is_prefer_aes())}")
    elif name == "key_length_set256":
        p = PublicKeyProtectionPolicy()
        p.set_encryption_key_length(256)
        lines.append(f"keyLength={p.get_encryption_key_length()}")
    elif name == "recipient_default_ctor":
        r = PublicKeyRecipient()
        lines.append(f"x509Null={_b(r.get_x509() is None)}")
        lines.append(f"permNull={_b(r.get_permission() is None)}")
    elif name == "recipient_set_permission":
        r = PublicKeyRecipient()
        ap = AccessPermission(-44)
        r.set_permission(ap)
        lines.append(f"permNull={_b(r.get_permission() is None)}")
        lines.append(f"bytes={r.get_permission().get_permission_bytes()}")
        lines.append(f"same={_b(r.get_permission() is ap)}")
    else:  # pragma: no cover - guard
        raise AssertionError(name)
    return lines


POLICY_CASES = [
    "empty",
    "single",
    "three_order",
    "remove_present",
    "remove_absent",
    "remove_from_empty",
    "key_length_default",
    "key_length_set128",
    "key_length_set256",
    "recipient_default_ctor",
    "recipient_set_permission",
]


@requires_oracle
@pytest.mark.parametrize("name", POLICY_CASES)
def test_policy_matches_oracle(name: str) -> None:
    java = run_probe_text(_PROBE, "POLICY", name).strip().splitlines()
    py = _py_policy(name)
    assert py == java


# ----------------------------------------------------------------------- PERM


def _py_perm(value: int) -> list[str]:
    ap = AccessPermission(value)
    for_pk = ap.get_permission_bytes_for_public_key()
    return [
        f"in={value}",
        f"forPublicKey={for_pk}",
        f"afterBytes={ap.get_permission_bytes()}",
    ]


# (case name -> the int the probe feeds AccessPermission(int))
PERM_CASES = {
    "all_set": -1,
    "default_minus4": -4,
    "default_minus44": -44,
    "all_clear": 0,
    "only_print": 4,
    "only_modify": 8,
    "bit7_8_set": 0xC0,
    "high_bits_set": 0x00FFF000,
    "only_bit1": 1,
    "max_positive": 2147483647,
}


@requires_oracle
@pytest.mark.parametrize("name", list(PERM_CASES))
def test_perm_matches_oracle(name: str) -> None:
    java = run_probe_text(_PROBE, "PERM", name).strip().splitlines()
    py = _py_perm(PERM_CASES[name])
    assert py == java


# ----------------------------------------------------------------------- DICT


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _str_array(*blobs: bytes) -> COSArray:
    a = COSArray()
    for blob in blobs:
        a.add(COSString(blob))
    return a


def _build_dict(name: str) -> COSDictionary:
    d = COSDictionary()
    if name == "well_formed_s5_v4":
        d.set_item(_name("Filter"), _name("Adobe.PubSec"))
        d.set_item(_name("SubFilter"), _name("adbe.pkcs7.s5"))
        d.set_item(_name("V"), COSInteger.get(4))
        d.set_item(_name("R"), COSInteger.get(4))
        d.set_item(_name("Length"), COSInteger.get(128))
        d.set_item(_name("Recipients"), _str_array(b"\x01\x02\x03", b"\x04\x05"))
    elif name == "subfilter_s3":
        d.set_item(_name("Filter"), _name("Adobe.PubSec"))
        d.set_item(_name("SubFilter"), _name("adbe.pkcs7.s3"))
    elif name == "subfilter_s4":
        d.set_item(_name("Filter"), _name("Adobe.PubSec"))
        d.set_item(_name("SubFilter"), _name("adbe.pkcs7.s4"))
        d.set_item(_name("V"), COSInteger.get(2))
        d.set_item(_name("R"), COSInteger.get(3))
    elif name == "recipients_missing":
        d.set_item(_name("Filter"), _name("Adobe.PubSec"))
        d.set_item(_name("SubFilter"), _name("adbe.pkcs7.s5"))
    elif name == "recipients_empty":
        d.set_item(_name("Filter"), _name("Adobe.PubSec"))
        d.set_item(_name("Recipients"), COSArray())
    elif name == "recipients_wrongtype":
        d.set_item(_name("Filter"), _name("Adobe.PubSec"))
        d.set_item(_name("Recipients"), COSInteger.get(7))
    elif name == "recipients_bool":
        d.set_item(_name("Recipients"), COSBoolean.TRUE)
    elif name == "v5_r6_256":
        d.set_item(_name("Filter"), _name("Adobe.PubSec"))
        d.set_item(_name("SubFilter"), _name("adbe.pkcs7.s5"))
        d.set_item(_name("V"), COSInteger.get(5))
        d.set_item(_name("R"), COSInteger.get(6))
        d.set_item(_name("Length"), COSInteger.get(256))
    elif name == "no_filter":
        d.set_item(_name("SubFilter"), _name("adbe.pkcs7.s5"))
    else:  # pragma: no cover - guard
        raise AssertionError(name)
    return d


def _emit_dict(d: COSDictionary) -> list[str]:
    e = PDEncryption(d)
    f = e.get_filter()
    sf = e.get_sub_filter()
    lines = [
        f"filter={'null' if f is None else f}",
        f"subFilter={'null' if sf is None else sf}",
        f"V={e.get_version()}",
        f"R={e.get_revision()}",
        f"Length={e.get_length()}",
    ]
    # Honest divergence: pypdfbox returns 0 for missing/wrong-type /Recipients
    # where upstream throws. Map that 0 back to the probe's ERR sentinel only
    # when the Java side threw (the test branches on this), but here we simply
    # surface the value pypdfbox produces.
    lines.append(f"recipientsLen={e.get_recipients_length()}")
    return lines


# Cases where Java's getRecipientsLength succeeds (BOTH-SIDES identical).
DICT_OK_CASES = ["well_formed_s5_v4", "recipients_empty"]

# Cases where Java's getRecipientsLength THROWS while pypdfbox returns 0
# (honest divergence). value = the int pypdfbox returns.
DICT_THROW_CASES = [
    "subfilter_s3",
    "subfilter_s4",
    "recipients_missing",
    "recipients_wrongtype",
    "recipients_bool",
    "v5_r6_256",
    "no_filter",
]


@requires_oracle
@pytest.mark.parametrize("name", DICT_OK_CASES)
def test_dict_recipients_ok_matches_oracle(name: str) -> None:
    java = run_probe_text(_PROBE, "DICT", name).strip().splitlines()
    py = _emit_dict(_build_dict(name))
    assert py == java


@requires_oracle
@pytest.mark.parametrize("name", DICT_THROW_CASES)
def test_dict_recipients_malformed_divergence(name: str) -> None:
    """Java throws on getRecipientsLength; pypdfbox returns 0. Pin BOTH: the
    non-recipient lines (filter/subFilter/V/R/Length) match identically, and
    the recipientsLen line differs by design (Java ``ERR:<class>`` vs Python
    ``0``)."""
    java = run_probe_text(_PROBE, "DICT", name).strip().splitlines()
    py = _emit_dict(_build_dict(name))
    # Every line except the final recipientsLen= line must match exactly.
    assert py[:-1] == java[:-1]
    # Java threw; pypdfbox tolerated.
    assert java[-1].startswith("recipientsLen=ERR:")
    assert py[-1] == "recipientsLen=0"


@requires_oracle
def test_dict_three_recipients_matches_oracle() -> None:
    d = COSDictionary()
    d.set_item(_name("Filter"), _name("Adobe.PubSec"))
    d.set_item(_name("Recipients"), _str_array(b"\x01", b"\x02", b"\x03"))
    e = PDEncryption(d)
    lines = [f"recipientsLen={e.get_recipients_length()}"]
    for i in range(e.get_recipients_length()):
        s = e.get_recipient_string_at(i)
        assert s is not None
        lines.append(f"blob{i}={len(s.get_bytes())}")
    java = run_probe_text(_PROBE, "DICT", "three_recipients").strip().splitlines()
    assert lines == java


# A pure-Python (non-oracle) smoke test so the surface stays pinned even on a
# machine without the live jar.
def test_permission_bytes_for_public_key_reencoding_offline() -> None:
    assert AccessPermission(-1).get_permission_bytes_for_public_key() == 3903
    assert AccessPermission(0).get_permission_bytes_for_public_key() == 1
    assert AccessPermission(0xC0).get_permission_bytes_for_public_key() == 1
    assert AccessPermission(0x00FFF000).get_permission_bytes_for_public_key() == 1


def test_remove_recipient_identity_offline() -> None:
    p = PublicKeyProtectionPolicy()
    a = _recip(4)
    p.add_recipient(a)
    assert p.remove_recipient(_recip(4)) is False  # distinct object
    assert p.remove_recipient(a) is True  # same object
    assert p.get_number_of_recipients() == 0
    assert p.remove_recipient(a) is False  # already gone
