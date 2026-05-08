from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSObject,
    COSStream,
)
from pypdfbox.io import copy as io_copy

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument


_LOG = logging.getLogger(__name__)


class PDFCloneUtility:
    """
    Utility class used to clone PDF objects from a source ``PDDocument``
    into a destination ``PDDocument`` while preserving the indirect-
    reference graph. Mirrors
    ``org.apache.pdfbox.multipdf.PDFCloneUtility``.

    The cloner keeps two side tables:

    - ``_cloned_version`` maps a source ``COSBase`` to its already-built
      destination clone, so cyclic / shared subgraphs collapse to a
      single clone in the destination.
    - ``_cloned_values`` is the set of *destination* clones; if the user
      hands one back to :meth:`clone_for_new_document` the cloner
      recognises it and returns it verbatim ("don't clone a clone").
    """

    def __init__(self, dest: PDDocument) -> None:
        self._destination = dest
        self._cloned_version: dict[int, COSBase] = {}
        self._cloned_values: set[int] = set()

    def get_destination(self) -> PDDocument:
        """Return the destination ``PDDocument`` this cloner targets."""
        return self._destination

    def clone_for_new_document(self, base: COSBase | None) -> COSBase | None:
        """Deep-clone ``base`` for inclusion in :attr:`destination`.

        Already-cloned source objects short-circuit to their existing
        clone. If the caller passes back an already-produced clone, it
        is returned unchanged ("don't clone a clone")."""
        if base is None:
            return None
        # Identity-based lookup: COSDictionary defines __eq__ via the
        # default object identity, but to mirror Java's IdentityHashMap-
        # like semantics safely we key by id(). Two equal-but-distinct
        # COSDictionary instances must not collapse during cloning.
        existing = self._cloned_version.get(id(base))
        if existing is not None:
            return existing
        if id(base) in self._cloned_values:
            # Don't clone a clone.
            return base
        retval = self._clone_cos_base_for_new_document(base)
        if retval is None:
            return None
        self._cloned_version[id(base)] = retval
        self._cloned_values.add(id(retval))
        return retval

    def _clone_cos_base_for_new_document(self, base: COSBase) -> COSBase | None:
        if isinstance(base, COSObject):
            return self.clone_for_new_document(base.get_object())
        if isinstance(base, COSArray):
            return self._clone_cos_array(base)
        if isinstance(base, COSStream):
            return self._clone_cos_stream(base)
        if isinstance(base, COSDictionary):
            return self._clone_cos_dictionary(base)
        return base

    def _clone_cos_array(self, array: COSArray) -> COSArray:
        new_array = COSArray()
        # Register the clone before iterating so a self-referential
        # entry can resolve back to ``new_array`` via the ``hasSelfReference``
        # check or via the ``_cloned_version`` table during recursion.
        self._cloned_version[id(array)] = new_array
        for i in range(array.size()):
            value = array.get(i)
            if self._has_self_reference(array, value):
                new_array.add(new_array)
            else:
                cloned = self.clone_for_new_document(value)
                if cloned is not None:
                    new_array.add(cloned)
        return new_array

    def _clone_cos_stream(self, stream: COSStream) -> COSStream:
        # Use the destination document's scratch file for the new stream
        # so its body bytes spill alongside the rest of the dest doc.
        cos_doc = self._destination.get_document()
        new_stream = COSStream(cos_doc.scratch_file)
        # Copy raw (still-encoded) body bytes verbatim — /Filter / /Length
        # come along via the dictionary copy below. Empty source streams
        # (no body set) skip the copy: ``create_raw_input_stream`` raises
        # ``OSError`` on an empty body, which would otherwise abort the
        # clone for a perfectly valid (header-only) stream object.
        if stream.has_data():
            with (
                stream.create_raw_input_stream() as src,
                new_stream.create_raw_output_stream() as dst,
            ):
                io_copy(src, dst)
        self._cloned_version[id(stream)] = new_stream
        for key, value in list(stream.entry_set()):
            if self._has_self_reference(stream, value):
                new_stream.set_item(key, new_stream)
            else:
                cloned = self.clone_for_new_document(value)
                if cloned is not None:
                    new_stream.set_item(key, cloned)
        return new_stream

    def _clone_cos_dictionary(self, dictionary: COSDictionary) -> COSDictionary:
        new_dictionary = COSDictionary()
        # Register the clone before iterating so cyclic references
        # encountered during recursion resolve to ``new_dictionary``.
        self._cloned_version[id(dictionary)] = new_dictionary
        for key, value in list(dictionary.entry_set()):
            if self._has_self_reference(dictionary, value):
                new_dictionary.set_item(key, new_dictionary)
            else:
                cloned = self.clone_for_new_document(value)
                if cloned is not None:
                    new_dictionary.set_item(key, cloned)
        return new_dictionary

    # ---------- merge ----------

    def clone_merge(self, base: object, target: object) -> None:
        """Merge two ``COSObjectable``-like values by deep-cloning members.

        ``base`` and ``target`` must expose ``get_cos_object()`` returning
        a ``COSBase``. ``None``-or-identical pairs are skipped."""
        if base is None or base is target:
            return
        source_cos = base.get_cos_object()  # type: ignore[attr-defined]
        target_cos = target.get_cos_object()  # type: ignore[attr-defined]
        self._clone_merge_cos_base(source_cos, target_cos, set())

    def _clone_merge_cos_base(
        self,
        source: COSBase,
        target: COSBase,
        seen_pairs: set[tuple[int, int]],
    ) -> None:
        source_base: COSBase | None = (
            source.get_object() if isinstance(source, COSObject) else source
        )
        target_base: COSBase | None = (
            target.get_object() if isinstance(target, COSObject) else target
        )
        if source_base is None or target_base is None:
            return
        pair = (id(source_base), id(target_base))
        if pair in seen_pairs:
            return
        seen_pairs.add(pair)
        if isinstance(source_base, COSArray) and isinstance(target_base, COSArray):
            for i in range(source_base.size()):
                cloned = self.clone_for_new_document(source_base.get(i))
                if cloned is not None:
                    target_base.add(cloned)
        elif isinstance(source_base, COSDictionary) and isinstance(
            target_base, COSDictionary
        ):
            for key, value in list(source_base.entry_set()):
                existing = target_base.get_item(key)
                if existing is not None:
                    # Both sides present — recurse into the pair so nested
                    # dictionaries/arrays are merged element-wise.
                    self._clone_merge_cos_base(value, existing, seen_pairs)
                else:
                    cloned = self.clone_for_new_document(value)
                    if cloned is not None:
                        target_base.set_item(key, cloned)

    # ---------- self-reference detection ----------

    @staticmethod
    def _has_self_reference(parent: COSBase, value: COSBase) -> bool:
        """``True`` when ``value`` is an indirect reference whose
        resolved target is ``parent`` itself. Mirrors PDFBox's
        ``hasSelfReference`` — guards the cloners against infinite
        recursion through pathological self-pointing dictionaries
        (PDFBOX-4477 family)."""
        if isinstance(value, COSObject):
            actual = value.get_object()
            if actual is parent:
                _LOG.warning(
                    "%s object has a reference to itself: %s %s R",
                    type(parent).__name__,
                    value.get_object_number(),
                    value.get_generation_number(),
                )
                return True
        return False
