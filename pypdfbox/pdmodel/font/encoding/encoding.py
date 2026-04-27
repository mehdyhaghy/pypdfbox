from __future__ import annotations

from typing import Optional, Union, overload

from pypdfbox.cos import COSBase, COSName


class Encoding:
    """A PostScript Encoding vector — maps a character code (0..255) to a
    PostScript glyph name and back.

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.Encoding``. The pdmodel
    surface is the abstract base; the predefined singletons (Standard, WinAnsi,
    MacRoman, MacExpert, Symbol, ZapfDingbats) are concrete subclasses, and
    ``DictionaryEncoding`` wraps a ``/Type /Encoding`` PDF dictionary.

    Subclasses populate the two maps in ``__init__`` via :meth:`add` /
    :meth:`overwrite`. After construction the maps are treated as immutable;
    the public accessors return snapshot copies.
    """

    # Java upstream uses these as named array indices into the Object[][]
    # encoding tables. Python ports use plain tuples so the constants are
    # unused at runtime, but keep them for parity.
    CHAR_CODE: int = 0
    CHAR_NAME: int = 1

    def __init__(self) -> None:
        self._code_to_name: dict[int, str] = {}
        self._name_to_code: dict[str, int] = {}

    # -- COS surface -------------------------------------------------------

    def get_cos_object(self) -> COSBase | None:
        """Return the COS object representing this encoding.

        Predefined encodings return their ``COSName`` (e.g. ``/WinAnsiEncoding``).
        ``DictionaryEncoding`` overrides to return its underlying ``COSDictionary``.
        Subclasses with no PDF representation return ``None``.
        """
        name = self.get_encoding_name()
        if name is None:
            return None
        return COSName.get_pdf_name(name)

    # -- construction helpers (called from subclass __init__) --------------

    def add(self, code: int, name: str) -> None:
        """Add a (code, name) pair. The reverse mapping is preserved when an
        existing name is already mapped to a different code (matches Java
        ``Map.putIfAbsent`` semantics)."""
        self._code_to_name[code] = name
        if name not in self._name_to_code:
            self._name_to_code[name] = code

    def overwrite(self, code: int, name: str) -> None:
        """Add a (code, name) pair, replacing any existing reverse mapping."""
        old_name = self._code_to_name.get(code)
        if old_name is not None:
            old_code = self._name_to_code.get(old_name)
            if old_code is not None and old_code == code:
                self._name_to_code.pop(old_name, None)
        self._name_to_code[name] = code
        self._code_to_name[code] = name

    # -- public read API ---------------------------------------------------

    @overload
    def get_name(self) -> str | None: ...
    @overload
    def get_name(self, code: int) -> str: ...
    def get_name(self, code: Optional[int] = None) -> str | None:
        """Polymorphic ``getName``.

        With no argument, returns the encoding name (e.g.
        ``"StandardEncoding"``). Equivalent to :meth:`get_encoding_name`;
        kept as ``get_name()`` so call sites mirror upstream patterns where
        the no-arg form is intuitive.

        With an ``int`` argument, returns the PostScript glyph name for
        ``code`` or ``".notdef"`` when unmapped (matches upstream
        ``getName(int)``).
        """
        if code is None:
            return self.get_encoding_name()
        return self._code_to_name.get(code, ".notdef")

    def get_code(self, name: str) -> int | None:
        """Return the character code for ``name``, or ``None`` if unmapped.

        Backed by the reverse map populated during construction, so each
        lookup is already O(1); no extra cache layer is needed.
        """
        return self._name_to_code.get(name)

    def to_glyph_name(self, code: int) -> str:
        """Return the glyph name for ``code`` with the ``".notdef"`` fallback.

        Equivalent to ``get_name(code)``; provided as a self-documenting
        alias for sites that consume glyph names directly.
        """
        return self._code_to_name.get(code, ".notdef")

    def contains_name(self, name: str) -> bool:
        """``True`` if ``name`` has a mapping. Mirrors ``contains(String)``."""
        return name in self._name_to_code

    def contains_code(self, code: int) -> bool:
        """``True`` if ``code`` has a mapping. Mirrors ``contains(int)``."""
        return code in self._code_to_name

    def contains(self, value: Union[int, str]) -> bool:
        """Polymorphic membership — ``True`` if ``value`` is a known code or name."""
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return value in self._code_to_name
        if isinstance(value, str):
            return value in self._name_to_code
        return False

    def __contains__(self, value: object) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return value in self._code_to_name
        if isinstance(value, str):
            return value in self._name_to_code
        return False

    def get_codes(self) -> dict[int, str]:
        """Return a fresh snapshot of the code -> name mapping."""
        return dict(self._code_to_name)

    def get_code_to_name_map(self) -> dict[int, str]:
        """Snapshot of the code -> name mapping."""
        return dict(self._code_to_name)

    def get_name_to_code_map(self) -> dict[str, int]:
        """Snapshot of the name -> code mapping. More than one name may map
        to the same code; this map keeps the first one added."""
        return dict(self._name_to_code)

    def get_encoding_name(self) -> str | None:
        """Return a stable encoding identifier. The predefined singletons
        return the PDF spec name (``"WinAnsiEncoding"`` etc.); custom
        ``DictionaryEncoding`` instances may return ``None``.
        """
        return None

    # -- factory -----------------------------------------------------------

    @staticmethod
    def get_instance(name: COSName | str | None) -> "Encoding | None":
        """Return the predefined ``Encoding`` for the given ``/Encoding`` name,
        or ``None`` if unknown. Mirrors upstream ``Encoding.getInstance``.
        """
        if name is None:
            return None
        if isinstance(name, COSName):
            key = name.name
        else:
            key = name
        # Local imports to avoid circular import on package initialization.
        from .mac_expert_encoding import MacExpertEncoding
        from .mac_roman_encoding import MacRomanEncoding
        from .standard_encoding import StandardEncoding
        from .symbol_encoding import SymbolEncoding
        from .win_ansi_encoding import WinAnsiEncoding
        from .zapf_dingbats_encoding import ZapfDingbatsEncoding

        table: dict[str, Encoding] = {
            "StandardEncoding": StandardEncoding.INSTANCE,
            "WinAnsiEncoding": WinAnsiEncoding.INSTANCE,
            "MacRomanEncoding": MacRomanEncoding.INSTANCE,
            "MacExpertEncoding": MacExpertEncoding.INSTANCE,
            "SymbolEncoding": SymbolEncoding.INSTANCE,
            "ZapfDingbatsEncoding": ZapfDingbatsEncoding.INSTANCE,
        }
        return table.get(key)


__all__ = ["Encoding"]
