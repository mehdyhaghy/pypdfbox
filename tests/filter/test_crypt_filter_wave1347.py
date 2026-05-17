"""Wave 1347 coverage boost for ``pypdfbox.filter.crypt_filter``.

Targets the residual ``_resolve_name`` fallback branches not exercised
by ``test_crypt_filter_wave1280``:

- ``parameters is None`` early return (line 74)
- ``get_dictionary_object`` fallback returning a ``COSName`` (line 83)
- ``get_dictionary_object`` fallback returning a plain ``str`` (line 85)
- ``get_cos_name`` returning a non-``COSName`` value: ``str(value)``
  fall-through (line 89)

Pre-wave the module sat at 89.7 % (4 missing); this set takes it to
100 %.
"""

from __future__ import annotations

import io

from pypdfbox.cos import COSName
from pypdfbox.filter import CryptFilter


# ---------------------------------------------------------------------------
# ``_resolve_name`` direct unit tests
# ---------------------------------------------------------------------------
def test_resolve_name_parameters_none_returns_none() -> None:
    """Line 74: ``parameters is None`` short-circuit."""
    assert CryptFilter._resolve_name(None) is None


class _ParamsNoCosName:
    """COSDictionary-shaped object lacking ``get_cos_name`` so the
    fallback path through ``get_dictionary_object`` engages."""

    def __init__(self, value: object) -> None:
        self._value = value

    def get_dictionary_object(self, key: str) -> object:
        return self._value if key == "Name" else None


def test_resolve_name_fallback_returns_cos_name() -> None:
    """Line 83: ``get_dictionary_object`` yields a ``COSName``."""
    params = _ParamsNoCosName(COSName.get_pdf_name("Identity"))
    assert CryptFilter._resolve_name(params) == "Identity"


def test_resolve_name_fallback_returns_plain_str() -> None:
    """Line 85: ``get_dictionary_object`` yields a plain ``str``."""
    params = _ParamsNoCosName("StdCF")
    assert CryptFilter._resolve_name(params) == "StdCF"


def test_resolve_name_fallback_returns_none_for_unknown_type() -> None:
    """``get_dictionary_object`` yields something that's neither
    ``COSName`` nor ``str`` — should fall through to ``return None``."""
    params = _ParamsNoCosName(42)
    assert CryptFilter._resolve_name(params) is None


class _ParamsCosNameReturnsObject:
    """``get_cos_name`` returns a non-``COSName`` value so ``_resolve_name``
    falls through to ``str(value)`` on line 89."""

    def get_cos_name(self, key: str) -> object:
        return 12345  # not a COSName, not None — forces str(value) path

    def get_dictionary_object(self, key: str) -> object:
        return None


def test_resolve_name_str_fallthrough() -> None:
    """Line 89: ``get_cos_name`` returns a non-``COSName`` truthy value."""
    params = _ParamsCosNameReturnsObject()
    assert CryptFilter._resolve_name(params) == "12345"


# ---------------------------------------------------------------------------
# End-to-end through ``decode``/``encode`` to confirm fallback rejection works
# ---------------------------------------------------------------------------
def test_decode_with_fallback_str_unknown_raises() -> None:
    cf = CryptFilter()
    params = _ParamsNoCosName("StdCF")
    try:
        cf.decode(io.BytesIO(b"x"), io.BytesIO(), params, 0)
    except OSError as exc:
        assert "StdCF" in str(exc)
    else:
        raise AssertionError("expected OSError")


def test_encode_with_fallback_str_unknown_raises() -> None:
    cf = CryptFilter()
    params = _ParamsNoCosName("StdCF")
    try:
        cf.encode(io.BytesIO(b"x"), io.BytesIO(), params)
    except OSError as exc:
        assert "StdCF" in str(exc)
    else:
        raise AssertionError("expected OSError")
