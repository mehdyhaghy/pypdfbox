from __future__ import annotations


class Encoding:
    """A PostScript Encoding vector — maps a character code (0..255) to a
    PostScript glyph name and back.

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.Encoding`` (folded
    together with the abstract ``org.apache.fontbox.encoding.Encoding`` per
    pypdfbox layout — the upstream pdmodel base is the richer one and it is
    what every concrete encoding here extends).

    Subclasses populate the two maps in ``__init__`` via :meth:`add` /
    :meth:`overwrite`. After construction the maps are treated as immutable
    by callers; the public ``get_codes()`` accessor returns a snapshot copy.
    """

    # Java upstream uses these as named array indices into the Object[][]
    # encoding tables. Python ports use plain tuples so the constants are
    # unused at runtime, but keep them for parity.
    CHAR_CODE: int = 0
    CHAR_NAME: int = 1

    def __init__(self) -> None:
        self._code_to_name: dict[int, str] = {}
        self._name_to_code: dict[str, int] = {}

    # -- construction helpers (called from subclass __init__) --------------

    def add(self, code: int, name: str) -> None:
        """Add a (code, name) pair. The reverse mapping is preserved when an
        existing name is already mapped to a different code (matches Java
        ``Map.putIfAbsent`` semantics)."""
        self._code_to_name[code] = name
        if name not in self._name_to_code:
            self._name_to_code[name] = code

    def add_character_encoding(self, code: int, name: str) -> None:
        """Snake_case alias of :meth:`add` matching the upstream fontbox base
        class ``Encoding.addCharacterEncoding`` (which is ``protected`` in
        Java; in Python the mapping is exposed at the same name for
        clarity in subclasses translated from upstream)."""
        self.add(code, name)

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

    def get_name(self, code: object) -> str:
        """Return the glyph name for ``code``, or ``".notdef"`` if unmapped.
        Never returns ``None`` (matches upstream ``getName(int)``)."""
        if not isinstance(code, int) or isinstance(code, bool):
            return ".notdef"
        return self._code_to_name.get(code, ".notdef")

    def get_code(self, name: object) -> int | None:
        """Return the character code for ``name``, or ``None`` if unmapped."""
        if not isinstance(name, str):
            return None
        return self._name_to_code.get(name)

    def get_codes(self) -> dict[int, str]:
        """Return a fresh snapshot of the code -> name mapping."""
        return dict(self._code_to_name)

    def get_code_to_name_map(self) -> dict[int, str]:
        """Alias of :meth:`get_codes` for camelCase->snake_case parity with
        upstream ``getCodeToNameMap()``."""
        return dict(self._code_to_name)

    def get_name_to_code_map(self) -> dict[str, int]:
        """Snapshot of the name -> code mapping. More than one name may map
        to the same code; this map keeps the first one added."""
        return dict(self._name_to_code)

    def contains(self, value: int | str) -> bool:
        """``True`` if ``value`` is a known code (int) or name (str)."""
        if isinstance(value, int) and not isinstance(value, bool):
            return value in self._code_to_name
        if isinstance(value, str):
            return value in self._name_to_code
        return False

    def __contains__(self, value: object) -> bool:
        if isinstance(value, int) and not isinstance(value, bool):
            return value in self._code_to_name
        if isinstance(value, str):
            return value in self._name_to_code
        return False

    def get_encoding_name(self) -> str:
        """Return a stable identifier for this encoding.

        Mirrors upstream ``getEncodingName()`` on
        ``org.apache.pdfbox.pdmodel.font.encoding.Encoding`` (line 176).
        Upstream declares the method abstract; concrete subclasses
        (``WinAnsiEncoding`` -> ``"WinAnsi"``, ``MacRomanEncoding`` ->
        ``"MacRoman"``, ...) hand-roll the literal name.

        The base implementation here derives the same identifier from
        the class name — strip a trailing ``Encoding`` suffix and return
        the rest. Subclasses are still free to override for a different
        spelling (e.g. ``StandardEncoding`` upstream returns
        ``"StandardEncoding"`` rather than ``"Standard"``).
        """
        name = type(self).__name__
        if name.endswith("Encoding") and len(name) > len("Encoding"):
            return name[: -len("Encoding")]
        return name

    def get_cos_object(self) -> object | None:
        """Return the COS representation of this encoding for embedding
        in a PDF.

        Mirrors upstream ``getCOSObject()`` on
        ``org.apache.pdfbox.pdmodel.font.encoding.Encoding``. Concrete
        subclasses override this:

        * The named predefined encodings (``WinAnsiEncoding``,
          ``MacRomanEncoding``, ``MacExpertEncoding``,
          ``StandardEncoding``, ``SymbolEncoding``,
          ``ZapfDingbatsEncoding``) return the matching ``COSName``.
        * ``DictionaryEncoding`` returns the underlying ``COSDictionary``.
        * ``BuiltInEncoding`` raises — upstream throws
          ``UnsupportedOperationException`` because a font's built-in
          encoding cannot be serialized.

        The base default is ``None``, which lets callers (e.g.
        ``_build_simple_ttf_font``) treat "no COS representation" as
        "skip the /Encoding entry" rather than crash on subclasses that
        forgot to override. Matches upstream behaviour where
        ``BuiltInEncoding`` callers explicitly catch the
        ``UnsupportedOperationException``.
        """
        return None
