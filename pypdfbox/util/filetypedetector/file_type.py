"""File type sentinel values used by :class:`FileTypeDetector`.

Mirrors ``org.apache.pdfbox.util.filetypedetector.FileType``.
"""

from enum import Enum, unique


@unique
class FileType(Enum):
    UNKNOWN = "Unknown"
    JPEG = "JPEG"
    TIFF = "TIFF"
    PSD = "PSD"
    PNG = "PNG"
    BMP = "BMP"
    GIF = "GIF"
    ICO = "ICO"
    PCX = "PCX"
    RIFF = "RIFF"
    ARW = "ARW"
    CRW = "CRW"
    CR2 = "CR2"
    NEF = "NEF"
    ORF = "ORF"
    RAF = "RAF"
    RW2 = "RW2"


__all__ = ["FileType"]
