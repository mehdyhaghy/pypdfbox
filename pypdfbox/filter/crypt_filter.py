"""Crypt filter — wraps the ``/Identity`` crypt sub-filter.

Mirrors ``org.apache.pdfbox.filter.CryptFilter``. The Java upstream is a
short class that decrypts data encrypted by a security handler, then
reproduces the original. In the absence of a custom crypt filter name —
or when the name is the literal ``/Identity`` — both upstream and this
port delegate to :class:`IdentityFilter` (pass-through). Any other
``/Name`` is rejected with ``OSError``.

Real per-stream PDF encryption is handled at the parser layer, not here
(the encryption sub-system intercepts the encrypted body before it ever
reaches the filter chain). The filter exists in upstream only to keep the
filter pipeline orthogonal when a stream's ``/Filter`` array literally
contains ``/Crypt``.
"""

from __future__ import annotations

from typing import BinaryIO

from pypdfbox.cos import COSDictionary, COSName

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory
from .identity_filter import IdentityFilter

_IDENTITY = COSName.get_pdf_name("Identity")
_NAME = COSName.get_pdf_name("Name")


class CryptFilter(Filter):
    """``/Crypt`` filter (ISO 32000-1 §7.4.10).

    Delegates to :class:`IdentityFilter` when ``/Name`` is missing or
    ``/Identity``. Any other name raises ``OSError`` (we mirror upstream's
    ``IOException("Unsupported crypt filter " + name)``).
    """

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        encryption_name = self._resolve_name(parameters)
        if encryption_name is None or encryption_name == _IDENTITY.get_name():
            identity = IdentityFilter()
            identity.decode(encoded, decoded, parameters, index)
            out_params = parameters if parameters is not None else COSDictionary()
            return DecodeResult(parameters=out_params)
        raise OSError(f"Unsupported crypt filter {encryption_name}")

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        encryption_name = self._resolve_name(parameters)
        if encryption_name is None or encryption_name == _IDENTITY.get_name():
            identity = IdentityFilter()
            identity.encode(raw, encoded, parameters)
            return
        raise OSError(f"Unsupported crypt filter {encryption_name}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_name(parameters: COSDictionary | None) -> str | None:
        if parameters is None:
            return None
        value = parameters.get_cos_name("Name") if hasattr(parameters, "get_cos_name") else None
        if value is None:
            # Some callers store the dictionary under a different key shape;
            # fall back to a plain item lookup.
            item = parameters.get_dictionary_object("Name") if hasattr(
                parameters, "get_dictionary_object"
            ) else None
            if isinstance(item, COSName):
                return item.get_name()
            if isinstance(item, str):
                return item
            return None
        if isinstance(value, COSName):
            return value.get_name()
        return str(value) if value is not None else None


# Register under the canonical ``/Crypt`` name so ``FilterFactory.get("Crypt")``
# resolves. Mirrors upstream ``FilterFactory`` ctor wiring
# (``filters.put(COSName.CRYPT, crypt)``).
FilterFactory.register("Crypt", CryptFilter())
