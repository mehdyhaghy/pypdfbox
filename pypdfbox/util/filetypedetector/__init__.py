"""File-type sniffing helpers ported from
``org.apache.pdfbox.util.filetypedetector``.
"""

from __future__ import annotations

from pypdfbox.util.filetypedetector.byte_trie import ByteTrie, ByteTrieNode
from pypdfbox.util.filetypedetector.file_type import FileType
from pypdfbox.util.filetypedetector.file_type_detector import FileTypeDetector

__all__ = ["ByteTrie", "ByteTrieNode", "FileType", "FileTypeDetector"]
