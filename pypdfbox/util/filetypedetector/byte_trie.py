"""Prefix tree for byte signatures.

Mirrors ``org.apache.pdfbox.util.filetypedetector.ByteTrie`` (PDFBox 3.0,
``pdfbox/src/main/java/org/apache/pdfbox/util/filetypedetector/ByteTrie.java``).
"""

from __future__ import annotations

from collections.abc import Iterable


class ByteTrieNode[T]:
    """Single node in the trie."""

    __slots__ = ("children", "_value")

    def __init__(self) -> None:
        self.children: dict[int, ByteTrieNode[T]] = {}
        self._value: T | None = None

    def set_value(self, value: T) -> None:
        if self._value is not None:
            raise RuntimeError("Value already set for this trie node")
        self._value = value

    def get_value(self) -> T | None:
        return self._value


class ByteTrie[T]:
    """Retrieval trie that stores values keyed by byte sequences."""

    def __init__(self) -> None:
        self._root: ByteTrieNode[T] = ByteTrieNode()
        self._max_depth: int = 0

    def find(self, data: bytes | bytearray | Iterable[int]) -> T | None:
        """Return the most specific value matching ``data`` from the root."""
        node = self._root
        val = node.get_value()
        for b in data:
            child = node.children.get(b & 0xFF)
            if child is None:
                break
            node = child
            if node.get_value() is not None:
                val = node.get_value()
        return val

    def add_path(self, value: T, *parts: bytes | bytearray) -> None:
        """Insert ``value`` at the concatenation of ``parts``."""
        depth = 0
        node = self._root
        for part in parts:
            for b in part:
                key = b & 0xFF
                child = node.children.get(key)
                if child is None:
                    child = ByteTrieNode()
                    node.children[key] = child
                node = child
                depth += 1
        node.set_value(value)
        if depth > self._max_depth:
            self._max_depth = depth

    def set_default_value(self, default_value: T) -> None:
        self._root.set_value(default_value)

    def get_max_depth(self) -> int:
        return self._max_depth


__all__ = ["ByteTrie", "ByteTrieNode"]
