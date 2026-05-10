"""CFF Expert Encoding singleton (EncodingId 1).

Mirrors ``org.apache.fontbox.cff.CFFExpertEncoding`` from upstream
PDFBox 3.0. Reuses the existing :mod:`pypdfbox.fontbox.cff._expert_encoding`
table (built from the same Java (code, sid) pairs and the fontTools
CFF Standard Strings list) so we don't transcribe 256 entries twice.
"""

from __future__ import annotations

from ._expert_encoding import EXPERT_ENCODING_TABLE
from .cff_encoding import CFFEncoding


class CFFExpertEncoding(CFFEncoding):
    """Singleton for the predefined CFF Expert Encoding."""

    _instance: CFFExpertEncoding | None = None

    def __init__(self) -> None:
        super().__init__()
        # Slots not present in EXPERT_ENCODING_TABLE map to SID 0
        # (".notdef") in the Java original; mirror that by walking the
        # full 0..255 range and back-filling with ".notdef".
        # Write directly to the underlying maps so we don't trip the
        # CFFEncoding.add override (which expects (code, sid[, name])).
        # pylint: disable=protected-access
        for code in range(256):
            name = EXPERT_ENCODING_TABLE.get(code, ".notdef")
            self._code_to_name[code] = name
            if name not in self._name_to_code:
                self._name_to_code[name] = code

    @classmethod
    def get_instance(cls) -> CFFExpertEncoding:
        """Return the shared singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


__all__ = ["CFFExpertEncoding"]
