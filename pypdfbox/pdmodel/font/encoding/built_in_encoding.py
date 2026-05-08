from __future__ import annotations

from collections.abc import Mapping

from pypdfbox.cos import COSBase

from .encoding import Encoding


class BuiltInEncoding(Encoding):
    """A font's built-in encoding.

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.BuiltInEncoding``. Used
    when a PDF font has no ``/Encoding`` entry and the encoding is taken from
    the font program itself (Type 1 ``Encoding`` array, Type 3 differences,
    TrueType ``cmap``).

    The instance is constructed from a ``code -> glyph name`` mapping; built-in
    encodings have no PDF representation, so :meth:`get_cos_object` raises.
    """

    def __init__(self, code_to_name: Mapping[int, str]) -> None:
        super().__init__()
        # Upstream uses ``codeToName.forEach(this::add)``; ``add`` keeps the
        # first reverse-mapping for a given glyph name, matching Java's
        # ``Map.putIfAbsent`` semantics. Accept any ``Mapping`` (parity with
        # Java's ``Map<Integer, String>`` interface) — callers may pass an
        # ``OrderedDict``, ``MappingProxyType``, or a plain ``dict``.
        for code, name in code_to_name.items():
            self.add(code, name)

    def get_cos_object(self) -> COSBase | None:
        # Upstream throws ``UnsupportedOperationException``; the closest Python
        # analogue is ``NotImplementedError`` with the same message.
        raise NotImplementedError("Built-in encodings cannot be serialized")

    def get_encoding_name(self) -> str:
        return "built-in (TTF)"


__all__ = ["BuiltInEncoding"]
