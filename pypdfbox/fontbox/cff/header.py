from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Header:
    """CFF font header (Adobe Technote #5176, Table 1).

    Mirrors the package-private inner class
    ``org.apache.fontbox.cff.CFFParser.Header`` (upstream
    ``CFFParser.java`` lines 1280-1303).

    The four fields exactly correspond to the CFF header layout:
      * ``major``    — Card8, format major version (currently 1)
      * ``minor``    — Card8, format minor version (currently 0)
      * ``hdr_size`` — Card8, header size in bytes
      * ``off_size`` — OffSize (Card8 1..4), absolute-offset width used
        elsewhere in the font

    Upstream this class is ``private static`` and exposed only for
    parsing; we surface it as a public dataclass so synthetic-byte tests
    and any caller poking at a parsed header can construct / inspect
    one without reflection.
    """

    major: int
    minor: int
    hdr_size: int
    off_size: int

    def to_string(self) -> str:
        """PDFBox: ``Header.toString()`` (upstream ``CFFParser.java``
        line 1298). Java-style fully-qualified-name string used for
        debug output."""
        return (
            f"{type(self).__name__}[major={self.major},"
            f" minor={self.minor},"
            f" hdrSize={self.hdr_size},"
            f" offSize={self.off_size}]"
        )

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["Header"]
