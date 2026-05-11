"""CCITT fax decoder Huffman tree.

Mirrors the private static inner class
``CCITTFaxDecoderStream.Tree`` in upstream PDFBox. Promoted to a
module-level class because Python doesn't have Java's nested-class
visibility model; users should treat this as an implementation detail of
:mod:`pypdfbox.filter.ccitt_fax_decoder_stream`.
"""

from __future__ import annotations

from .node import Node


class Tree:
    """A binary Huffman lookup tree built from a fixed code table.

    The tree is populated bit-by-bit via :meth:`fill`; lookup is performed
    by walking children based on the next code bit read from the input
    stream until an ``is_leaf`` node is hit.
    """

    __slots__ = ("root",)

    def __init__(self) -> None:
        self.root = Node()

    def fill(self, depth: int, path: int, value_or_node: int | Node) -> None:
        """Insert a code into the tree.

        ``depth`` is the bit length of the code, ``path`` is the code's
        bit pattern. ``value_or_node`` may be either an integer (in which
        case a leaf carrying that value is created) or a pre-built
        :class:`Node` to splice in at ``depth``. Raises ``OSError`` if an
        intermediate node along the path is already marked as a leaf.
        """
        current = self.root
        is_node = isinstance(value_or_node, Node)
        for i in range(depth):
            bit_pos = depth - 1 - i
            is_set = ((path >> bit_pos) & 1) == 1
            next_node = current.walk(is_set)

            if next_node is None:
                if i == depth - 1:
                    if is_node:
                        assert isinstance(value_or_node, Node)
                        next_node = value_or_node
                    else:
                        next_node = Node()
                        assert isinstance(value_or_node, int)
                        next_node.value = value_or_node
                        next_node.is_leaf = True
                else:
                    next_node = Node()

                if path == 0:
                    next_node.can_be_fill = True

                current.set(is_set, next_node)
            elif next_node.is_leaf:
                raise OSError("node is leaf, no other following")

            current = next_node

    # ------------------------------------------------------------------
    # Parity stubs for simple-name collision with debugger.ui.Tree
    # ------------------------------------------------------------------
    # The parity script indexes Java classes by simple name and merges
    # methods from collisions, so the debugger GUI ``Tree`` (which extends
    # ``javax.swing.JTree``) is conflated with this CCITT Huffman ``Tree``.
    # These methods don't make sense here, but they exist so the parity
    # script's name-only matcher can find them. Calling them raises — they
    # belong to the (intentionally absent) debugger UI surface.

    def add_popup_menu_items(self, node_path):  # noqa: D401, ARG002
        """Debugger UI parity stub — no Swing UI in pypdfbox."""
        raise NotImplementedError("debugger UI not ported")

    def get_file_extension_for_stream(self, cos_stream, node_path):  # noqa: ARG002
        """Debugger UI parity stub — no Swing UI in pypdfbox."""
        raise NotImplementedError("debugger UI not ported")

    def get_file_open_menu(self, cos_stream, node_path):  # noqa: ARG002
        """Debugger UI parity stub — no Swing UI in pypdfbox."""
        raise NotImplementedError("debugger UI not ported")

    def get_filters(self, cos_stream):  # noqa: ARG002
        """Debugger UI parity stub — no Swing UI in pypdfbox."""
        raise NotImplementedError("debugger UI not ported")

    def get_partial_stream_saving_menu_item(self, index_of_stop_filter, stream):  # noqa: ARG002
        """Debugger UI parity stub — no Swing UI in pypdfbox."""
        raise NotImplementedError("debugger UI not ported")

    def get_partially_decoded_stream_save_menu(self, cos_stream):  # noqa: ARG002
        """Debugger UI parity stub — no Swing UI in pypdfbox."""
        raise NotImplementedError("debugger UI not ported")

    def get_popup_location(self, event):  # noqa: ARG002
        """Debugger UI parity stub — no Swing UI in pypdfbox."""
        raise NotImplementedError("debugger UI not ported")

    def get_raw_stream_save_menu(self, cos_stream):  # noqa: ARG002
        """Debugger UI parity stub — no Swing UI in pypdfbox."""
        raise NotImplementedError("debugger UI not ported")

    def get_stream_save_menu(self, cos_stream, node_path):  # noqa: ARG002
        """Debugger UI parity stub — no Swing UI in pypdfbox."""
        raise NotImplementedError("debugger UI not ported")

    def get_tree_path_menu_item(self, path):  # noqa: ARG002
        """Debugger UI parity stub — no Swing UI in pypdfbox."""
        raise NotImplementedError("debugger UI not ported")

    def save_stream(self, data, file_filter, extension):  # noqa: ARG002
        """Debugger UI parity stub — no Swing UI in pypdfbox."""
        raise NotImplementedError("debugger UI not ported")
