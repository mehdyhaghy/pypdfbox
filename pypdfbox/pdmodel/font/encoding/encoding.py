from __future__ import annotations

from collections.abc import Iterator
from typing import overload

from pypdfbox.cos import COSBase, COSName

_NO_CODE = object()


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

    #: Names recognized by upstream ``Encoding.getInstance(COSName)`` —
    #: the four PDF-spec ``/Encoding`` values. ``SymbolEncoding`` and
    #: ``ZapfDingbatsEncoding`` are font-program built-ins (not valid
    #: ``/Encoding`` entries), but pypdfbox still resolves them through
    #: :meth:`get_instance` for ergonomic symmetry. Use this constant to
    #: test "is this a PDF-spec predefined encoding name?".
    PREDEFINED_NAMES: frozenset[str] = frozenset({
        "StandardEncoding",
        "WinAnsiEncoding",
        "MacRomanEncoding",
        "MacExpertEncoding",
    })

    #: Encoding names that come from a font program rather than the PDF
    #: ``/Encoding`` spec catalogue. ``SymbolEncoding`` and
    #: ``ZapfDingbatsEncoding`` are font-program built-ins — they cannot
    #: appear as a PDF ``/Encoding`` name entry but pypdfbox still resolves
    #: them through :meth:`get_instance` for ergonomic symmetry. Use this
    #: constant (or :meth:`is_font_specific`) to test "is this encoding
    #: tied to a specific font program?".
    FONT_SPECIFIC_NAMES: frozenset[str] = frozenset({
        "SymbolEncoding",
        "ZapfDingbatsEncoding",
    })

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
    @overload
    def get_name(self, code: object) -> str: ...
    def get_name(self, code: object = _NO_CODE) -> str | None:
        """Polymorphic ``getName``.

        With no argument, returns the encoding name (e.g.
        ``"StandardEncoding"``). Equivalent to :meth:`get_encoding_name`;
        kept as ``get_name()`` so call sites mirror upstream patterns where
        the no-arg form is intuitive.

        With an ``int`` argument, returns the PostScript glyph name for
        ``code`` or ``".notdef"`` when unmapped (matches upstream
        ``getName(int)``).
        """
        if code is _NO_CODE:
            return self.get_encoding_name()
        if not isinstance(code, int) or isinstance(code, bool):
            return ".notdef"
        return self._code_to_name.get(code, ".notdef")

    def get_code(self, name: object) -> int | None:
        """Return the character code for ``name``, or ``None`` if unmapped.

        Backed by the reverse map populated during construction, so each
        lookup is already O(1); no extra cache layer is needed.
        """
        if not isinstance(name, str):
            return None
        return self._name_to_code.get(name)

    def to_glyph_name(self, code: object) -> str:
        """Return the glyph name for ``code`` with the ``".notdef"`` fallback.

        Equivalent to ``get_name(code)``; provided as a self-documenting
        alias for sites that consume glyph names directly.
        """
        if not isinstance(code, int) or isinstance(code, bool):
            return ".notdef"
        return self._code_to_name.get(code, ".notdef")

    def contains_name(self, name: object) -> bool:
        """``True`` if ``name`` has a mapping. Mirrors ``contains(String)``."""
        if not isinstance(name, str):
            return False
        return name in self._name_to_code

    def contains_code(self, code: object) -> bool:
        """``True`` if ``code`` has a mapping. Mirrors ``contains(int)``."""
        if not isinstance(code, int) or isinstance(code, bool):
            return False
        return code in self._code_to_name

    def contains(self, value: int | str) -> bool:
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

    # -- predicates / typed accessors --------------------------------------

    def is_predefined(self) -> bool:
        """``True`` when :meth:`get_encoding_name` returns one of the four
        PDF-spec predefined encoding names (``StandardEncoding``,
        ``WinAnsiEncoding``, ``MacRomanEncoding``, ``MacExpertEncoding``).

        Built-in font encodings, ``DictionaryEncoding``, ``SymbolEncoding``,
        and ``ZapfDingbatsEncoding`` all return ``False`` — the latter two
        are font-program built-ins, not values that may appear as a PDF
        ``/Encoding`` name entry.
        """
        return self.get_encoding_name() in self.PREDEFINED_NAMES

    def is_font_specific(self) -> bool:
        """``True`` when this encoding is a font-program built-in
        (:class:`SymbolEncoding` or :class:`ZapfDingbatsEncoding`).

        Font-specific encodings are tied to a specific font program (the
        Symbol and Zapf Dingbats Adobe fonts respectively) — they cannot
        appear as a PDF ``/Encoding`` name entry, although pypdfbox still
        resolves them through :meth:`get_instance` for ergonomic symmetry.

        Strictly disjoint from :meth:`is_predefined` — every encoding
        satisfies at most one of the two predicates. ``DictionaryEncoding``,
        :class:`BuiltInEncoding`, and :class:`MacOSRomanEncoding` return
        ``False`` for both.
        """
        return self.get_encoding_name() in self.FONT_SPECIFIC_NAMES

    def get_max_code(self) -> int | None:
        """Return the largest mapped character code, or ``None`` for an
        empty encoding.

        Cheap typed accessor over :meth:`get_code_to_name_map` — useful for
        sizing buffers, range checks, and parity tests against the upstream
        256-code-vector convention.
        """
        if not self._code_to_name:
            return None
        return max(self._code_to_name)

    def get_min_code(self) -> int | None:
        """Return the smallest mapped character code, or ``None`` for an
        empty encoding.

        Counterpart to :meth:`get_max_code`; helpful when an encoding's
        explicit table starts at a non-zero code (e.g. Standard's first
        printable code is 0x20).
        """
        if not self._code_to_name:
            return None
        return min(self._code_to_name)

    def iter_codes(self) -> Iterator[int]:
        """Iterate over mapped character codes in ascending order.

        Streaming alternative to ``sorted(self.get_code_to_name_map())``
        that avoids materializing the snapshot dict. Useful for large
        encodings (256 entries each) where the caller only needs to walk
        the codes once.
        """
        return iter(sorted(self._code_to_name))

    def size(self) -> int:
        """Number of (code, name) mappings in this encoding.

        Equivalent to ``len(encoding)``; provided as a method-style
        accessor matching upstream ``Map.size()`` ergonomics.
        """
        return len(self._code_to_name)

    def __len__(self) -> int:
        return len(self._code_to_name)

    def get_codes_for_name(self, name: str | None) -> list[int]:
        """Return all character codes that map to ``name``, sorted ascending.

        Differs from :meth:`get_code` which returns only the first
        reverse-mapped code (matching ``Map.putIfAbsent`` semantics).
        Useful when a single glyph appears at multiple codes — for example
        :class:`WinAnsiEncoding` maps every otherwise-unused code in 0o41+
        to ``bullet``, so ``get_code("bullet")`` returns one code while
        ``get_codes_for_name("bullet")`` returns the full set.

        Returns an empty list when ``name`` is not in the encoding.
        """
        if name is None:
            return []
        return sorted(c for c, n in self._code_to_name.items() if n == name)

    def get_glyph_names(self) -> set[str]:
        """Return the set of distinct glyph names in this encoding.

        Equivalent to ``set(self.get_code_to_name_map().values())`` but
        avoids materializing the snapshot dict. Useful for set-style
        membership checks across multiple encodings (e.g. determining the
        intersection of glyphs supported by a base encoding and a font's
        built-in encoding).
        """
        return set(self._code_to_name.values())

    # -- factory -----------------------------------------------------------

    @staticmethod
    def get_instance(name: COSName | str | None) -> Encoding | None:
        """Return the predefined ``Encoding`` for the given ``/Encoding`` name,
        or ``None`` if unknown. Mirrors upstream ``Encoding.getInstance``.
        """
        if name is None:
            return None
        key = name.name if isinstance(name, COSName) else name
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
