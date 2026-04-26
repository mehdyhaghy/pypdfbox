from __future__ import annotations

from pypdfbox.fontbox.encoding.mac_expert_encoding import _TABLE

from .encoding import Encoding


class MacExpertEncoding(Encoding):
    """The Mac Expert Encoding.

    Mirrors ``org.apache.pdfbox.pdmodel.font.encoding.MacExpertEncoding``.
    """

    INSTANCE: "MacExpertEncoding"

    def __init__(self) -> None:
        super().__init__()
        for code, name in _TABLE:
            self.add(code, name)

    def get_encoding_name(self) -> str:
        return "MacExpertEncoding"


MacExpertEncoding.INSTANCE = MacExpertEncoding()


__all__ = ["MacExpertEncoding"]
