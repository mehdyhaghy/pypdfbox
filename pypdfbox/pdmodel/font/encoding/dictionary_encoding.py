from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSNumber,
)

from .encoding import Encoding
from .standard_encoding import StandardEncoding

_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_ENCODING: COSName = COSName.get_pdf_name("Encoding")
_BASE_ENCODING: COSName = COSName.get_pdf_name("BaseEncoding")
_DIFFERENCES: COSName = COSName.get_pdf_name("Differences")


class DictionaryEncoding(Encoding):
    """An ``/Type /Encoding`` dictionary that overlays a base encoding with a
    ``/Differences`` array.

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.DictionaryEncoding``.

    Three construction modes:

    1. ``DictionaryEncoding(base_encoding=COSName, differences=COSArray)`` —
       build a fresh encoding dictionary for embedding (writer side).
    2. ``DictionaryEncoding(font_encoding=COSDictionary)`` — Type 3 font
       reader; no implicit base, the differences are the only mapping.
    3. ``DictionaryEncoding(font_encoding=COSDictionary,
       is_non_symbolic=bool, built_in=Encoding | None)`` — general PDF font
       reader; resolves a base encoding from ``/BaseEncoding`` if present,
       else falls back to ``StandardEncoding`` (non-symbolic) or the font's
       built-in encoding (symbolic).
    """

    def __init__(
        self,
        base_encoding: COSName | None = None,
        differences: COSArray | None = None,
        font_encoding: COSDictionary | None = None,
        is_non_symbolic: bool | None = None,
        built_in: Encoding | None = None,
    ) -> None:
        super().__init__()

        if font_encoding is not None:
            # Reader path.
            self._encoding = font_encoding
            self._base_encoding = self._resolve_base_encoding(
                font_encoding, is_non_symbolic, built_in
            )
        else:
            # Writer / embedding path.
            self._encoding = COSDictionary()
            self._encoding.set_item(_TYPE, _ENCODING)
            if base_encoding is not None:
                self._encoding.set_item(_BASE_ENCODING, base_encoding)
                self._base_encoding = Encoding.get_instance(base_encoding)
            else:
                self._base_encoding = None
            if differences is not None:
                self._encoding.set_item(_DIFFERENCES, differences)

        # Seed code->name from the base, then overlay /Differences.
        if self._base_encoding is not None:
            for code, name in self._base_encoding.get_code_to_name_map().items():
                self.add(code, name)

        self._differences: dict[int, str] = {}
        diffs = self._encoding.get_dictionary_object(_DIFFERENCES)
        if isinstance(diffs, COSArray):
            self._apply_differences(diffs)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _resolve_base_encoding(
        font_encoding: COSDictionary,
        is_non_symbolic: bool | None,
        built_in: Encoding | None,
    ) -> Encoding | None:
        be = font_encoding.get_dictionary_object(_BASE_ENCODING)
        if isinstance(be, COSName):
            resolved = Encoding.get_instance(be)
            if resolved is not None:
                return resolved
        # Type 3 font path: no implicit base.
        if is_non_symbolic is None and built_in is None:
            return None
        if is_non_symbolic:
            return StandardEncoding.INSTANCE
        return built_in

    def _apply_differences(self, diffs: COSArray) -> None:
        code = -1
        for i in range(diffs.size()):
            entry = diffs.get_object(i)
            if isinstance(entry, COSNumber):
                code = int(entry.value)  # type: ignore[arg-type]
            elif isinstance(entry, COSName):
                if code >= 0:
                    self.overwrite(code, entry.name)
                    self._differences[code] = entry.name
                    code += 1

    # -- public API --------------------------------------------------------

    def get_cos_object(self) -> COSDictionary:
        return self._encoding

    def to_cos_object(self) -> COSDictionary:
        """Alias for :meth:`get_cos_object`. Convenience for callers that
        prefer the writer-style ``to_*`` naming."""
        return self._encoding

    def get_base_encoding(self) -> Encoding | None:
        return self._base_encoding

    def set_base_encoding(self, value: Encoding | COSName | str | None) -> None:
        """Replace the ``/BaseEncoding`` entry on the underlying dictionary
        and refresh the cached resolved encoding.

        Accepts a resolved :class:`Encoding`, a ``COSName``, a plain encoding
        name, or ``None`` to remove the entry.
        """
        if value is None:
            self._encoding.remove_item(_BASE_ENCODING)
            self._base_encoding = None
            return
        if isinstance(value, Encoding):
            name = value.get_encoding_name()
            self._base_encoding = value
            if name is not None:
                self._encoding.set_item(_BASE_ENCODING, COSName.get_pdf_name(name))
            else:
                self._encoding.remove_item(_BASE_ENCODING)
            return
        if isinstance(value, COSName):
            self._encoding.set_item(_BASE_ENCODING, value)
            self._base_encoding = Encoding.get_instance(value)
            return
        # Plain string.
        self._encoding.set_item(_BASE_ENCODING, COSName.get_pdf_name(value))
        self._base_encoding = Encoding.get_instance(value)

    def get_differences(self) -> dict[int, str]:
        return dict(self._differences)

    def get_encoding_name(self) -> str | None:
        # Custom dictionary encodings have no canonical PDF name.
        if self._base_encoding is not None:
            base = self._base_encoding.get_encoding_name()
            if base is not None:
                return f"differences with {base}"
            return "differences"
        return "differences"

    def add(self, code: int, name: str) -> None:
        """Add a (code, name) pair. Also recorded in the ``/Differences``
        view; callers building an encoding dictionary should mutate the
        underlying COSArray themselves if they need wire-level control."""
        super().add(code, name)

    # -- helpers for writers ----------------------------------------------

    def set_differences(self, differences: COSArray | dict[int, str]) -> None:
        """Replace the ``/Differences`` entry on the underlying dictionary.

        Accepts either a fully prepared :class:`COSArray` (writer-side wire
        form) or a ``{code: name}`` mapping which is converted to the
        canonical PDF differences array — runs of consecutive codes are
        coalesced under a single leading integer marker, matching the
        spec's compact representation.
        """
        if isinstance(differences, COSArray):
            self._encoding.set_item(_DIFFERENCES, differences)
            self._differences = {}
            self._apply_differences(differences)
            return

        # Build a COSArray from a {code: name} mapping. Sort by code and
        # coalesce consecutive runs.
        arr = COSArray()
        prev_code: int | None = None
        for code in sorted(differences):
            name = differences[code]
            if prev_code is None or code != prev_code + 1:
                arr.add(COSInteger.get(code))
            arr.add(COSName.get_pdf_name(name))
            prev_code = code
        self._encoding.set_item(_DIFFERENCES, arr)
        # Refresh the cached differences view.
        self._differences = {}
        self._apply_differences(arr)


__all__ = ["DictionaryEncoding"]
