"""Upstream-parity tests for ``Encoding.getCOSObject``.

Source: ``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/font/encoding/``
(PDFBox 3.0.x). Upstream's ``Encoding.java`` and each concrete
predefined-encoding subclass override ``getCOSObject()`` to return a
``COSName`` (or, for ``DictionaryEncoding``, the underlying
``COSDictionary``). The pypdfbox port was missing the override on six
of the concrete encodings up through wave 1363 — every call site
guarded by ``encoding.get_cos_object()`` (``_build_simple_ttf_font``
on the writer side) threw ``AttributeError`` when the caller passed
``WinAnsiEncoding.INSTANCE``. Fixed in wave 1364.

This file pins the contract per concrete subclass so the regression
can't slip back in.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos.cos_name import COSName
from pypdfbox.fontbox.encoding.encoding import Encoding
from pypdfbox.fontbox.encoding.mac_expert_encoding import MacExpertEncoding
from pypdfbox.fontbox.encoding.mac_roman_encoding import MacRomanEncoding
from pypdfbox.fontbox.encoding.standard_encoding import StandardEncoding
from pypdfbox.fontbox.encoding.symbol_encoding import SymbolEncoding
from pypdfbox.fontbox.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.fontbox.encoding.zapf_dingbats_encoding import ZapfDingbatsEncoding


def test_win_ansi_encoding_cos_object() -> None:
    """Mirrors upstream ``WinAnsiEncoding.getCOSObject`` (returns
    ``COSName.WIN_ANSI_ENCODING``).
    """
    assert WinAnsiEncoding.INSTANCE.get_cos_object() is COSName.WIN_ANSI_ENCODING


def test_mac_roman_encoding_cos_object() -> None:
    """Mirrors upstream ``MacRomanEncoding.getCOSObject``."""
    assert MacRomanEncoding.INSTANCE.get_cos_object() is COSName.MAC_ROMAN_ENCODING


def test_mac_expert_encoding_cos_object() -> None:
    """Mirrors upstream ``MacExpertEncoding.getCOSObject``."""
    assert MacExpertEncoding.INSTANCE.get_cos_object() is COSName.MAC_EXPERT_ENCODING


def test_standard_encoding_cos_object() -> None:
    """Mirrors upstream ``StandardEncoding.getCOSObject``."""
    assert StandardEncoding.INSTANCE.get_cos_object() is COSName.STANDARD_ENCODING


def test_symbol_encoding_cos_object() -> None:
    """Mirrors upstream ``SymbolEncoding.getCOSObject`` which returns
    ``COSName.getPDFName("SymbolEncoding")`` rather than a static
    ``COSName.SYMBOL_ENCODING`` constant (there is no such constant
    upstream).
    """
    out = SymbolEncoding.INSTANCE.get_cos_object()
    assert out is not None
    assert out == COSName.get_pdf_name("SymbolEncoding")


def test_zapf_dingbats_encoding_cos_object() -> None:
    """Mirrors upstream ``ZapfDingbatsEncoding.getCOSObject``."""
    out = ZapfDingbatsEncoding.INSTANCE.get_cos_object()
    assert out is not None
    assert out == COSName.get_pdf_name("ZapfDingbatsEncoding")


def test_base_encoding_default_returns_none() -> None:
    """The pypdfbox-specific default for ``Encoding.get_cos_object`` is
    ``None``. Upstream declares the method abstract; the Python port
    keeps a safe default so callers (e.g. ``_build_simple_ttf_font``)
    can short-circuit on ``None`` rather than crash on
    ``AttributeError``. Verified via a bare ``Encoding`` instance.
    """
    bare = Encoding()
    assert bare.get_cos_object() is None


def test_built_in_encoding_raises_on_cos_object() -> None:
    """Mirrors upstream ``BuiltInEncoding.getCOSObject`` which throws
    ``UnsupportedOperationException``. The Python port raises the
    closest analogue, ``NotImplementedError``, with the same message.
    """
    from pypdfbox.pdmodel.font.encoding.built_in_encoding import BuiltInEncoding

    built_in = BuiltInEncoding({0: ".notdef"})
    with pytest.raises(NotImplementedError, match="cannot be serialized"):
        built_in.get_cos_object()
