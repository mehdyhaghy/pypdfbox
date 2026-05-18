"""Coverage-boost tests for
``pypdfbox.pdmodel.encryption.pd_encryption`` (wave 1349).

Pre-wave: 97.4% (268 stmts, 7 missing). Missing lines:

* 115-118: ``get_security_handler`` raises ``OSError`` when no handler
  has been installed (the upstream-parity error message format is
  important — Apache Tika matches against it);
* 127: ``set_security_handler`` stores the supplied handler;
* 136: ``has_security_handler`` returns ``True`` when the handler is
  *missing* (upstream parity — see the docstring);
* 569: ``remove_v45filters`` alias delegates to ``remove_v45_filters``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.encryption.pd_encryption import PDEncryption

# ---- get_security_handler / set_security_handler / has_security_handler ----


def test_get_security_handler_raises_when_none_installed_default_filter() -> None:
    """Default /Filter is ``None``; the error message embeds the literal
    ``None`` token (upstream's ``getFilter()`` returns ``null``, formatted
    by Java as the string ``"null"``; we keep the Python representation
    because Tika's regex anchors on the *prefix*)."""
    enc = PDEncryption()
    with pytest.raises(OSError, match=r"No security handler for filter"):
        enc.get_security_handler()


def test_get_security_handler_raises_with_named_filter_in_message() -> None:
    """When /Filter is set, the message must mention the actual filter
    name. Apache Tika (TIKA-4082) parses the trailing token."""
    enc = PDEncryption()
    enc.set_filter("Standard")
    with pytest.raises(OSError) as info:
        enc.get_security_handler()
    assert "Standard" in str(info.value)


def test_set_security_handler_stores_handler_and_returns_it() -> None:
    enc = PDEncryption()
    sentinel = object()
    enc.set_security_handler(sentinel)
    assert enc.get_security_handler() is sentinel


def test_set_security_handler_can_overwrite_existing_handler() -> None:
    enc = PDEncryption()
    first = object()
    second = object()
    enc.set_security_handler(first)
    enc.set_security_handler(second)
    assert enc.get_security_handler() is second


def test_set_security_handler_does_not_touch_filter() -> None:
    """Upstream parity: ``setSecurityHandler`` carries a TODO that says it
    should also rewrite /Filter, but does not. We replicate the quirk —
    setting a handler must leave /Filter alone."""
    enc = PDEncryption()
    enc.set_filter("Custom")
    enc.set_security_handler(object())
    assert enc.get_filter() == "Custom"


def test_has_security_handler_returns_true_when_handler_is_missing() -> None:
    """Parity quirk: upstream's ``hasSecurityHandler`` returns true when
    the handler is *null* (Java body: ``return securityHandler == null;``).
    We mirror it bit-for-bit, even though the name reads inverted."""
    enc = PDEncryption()
    # Pristine instance — no handler yet.
    assert enc.has_security_handler() is True


def test_has_security_handler_returns_false_when_handler_installed() -> None:
    enc = PDEncryption()
    enc.set_security_handler(object())
    assert enc.has_security_handler() is False


# ---- remove_v45filters alias -----------------------------------------------


def test_remove_v45filters_alias_clears_cf_stmf_strf_eff() -> None:
    """The ``remove_v45filters`` parity alias must clear the same four keys
    as ``remove_v45_filters``."""
    enc = PDEncryption()
    dictionary: COSDictionary = enc.get_cos_object()
    # Populate the four keys upstream strips when downgrading to V<=3.
    cf = COSDictionary()
    dictionary.set_item(COSName.get_pdf_name("CF"), cf)
    dictionary.set_name(COSName.get_pdf_name("StmF"), "StdCF")
    dictionary.set_name(COSName.get_pdf_name("StrF"), "StdCF")
    dictionary.set_name(COSName.get_pdf_name("EFF"), "StdCF")
    assert dictionary.contains_key(COSName.get_pdf_name("CF"))
    assert dictionary.contains_key(COSName.get_pdf_name("StmF"))
    assert dictionary.contains_key(COSName.get_pdf_name("StrF"))
    assert dictionary.contains_key(COSName.get_pdf_name("EFF"))

    enc.remove_v45filters()

    assert not dictionary.contains_key(COSName.get_pdf_name("CF"))
    assert not dictionary.contains_key(COSName.get_pdf_name("StmF"))
    assert not dictionary.contains_key(COSName.get_pdf_name("StrF"))
    assert not dictionary.contains_key(COSName.get_pdf_name("EFF"))


def test_remove_v45filters_alias_is_noop_on_empty_dict() -> None:
    """Calling the alias on a brand-new ``PDEncryption`` with no /CF, /StmF,
    /StrF, /EFF must not raise — ``COSDictionary.remove_item`` is idempotent
    against missing keys."""
    enc = PDEncryption()
    enc.remove_v45filters()  # must not raise
    # Underlying dict still has no encryption-pipeline keys.
    dictionary = enc.get_cos_object()
    assert not dictionary.contains_key(COSName.get_pdf_name("CF"))


def test_remove_v45filters_and_remove_v45_filters_are_equivalent() -> None:
    """The alias and the snake-cased method produce identical state when
    invoked on equivalent starting dictionaries."""
    enc_a = PDEncryption()
    enc_b = PDEncryption()
    for enc in (enc_a, enc_b):
        d = enc.get_cos_object()
        d.set_item(COSName.get_pdf_name("CF"), COSDictionary())
        d.set_name(COSName.get_pdf_name("StmF"), "StdCF")
    enc_a.remove_v45_filters()
    enc_b.remove_v45filters()
    # Both dictionaries are now empty of those keys.
    da = enc_a.get_cos_object()
    db = enc_b.get_cos_object()
    assert not da.contains_key(COSName.get_pdf_name("CF"))
    assert not da.contains_key(COSName.get_pdf_name("StmF"))
    assert not db.contains_key(COSName.get_pdf_name("CF"))
    assert not db.contains_key(COSName.get_pdf_name("StmF"))
