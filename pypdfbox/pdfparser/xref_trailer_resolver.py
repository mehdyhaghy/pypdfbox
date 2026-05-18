from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from pypdfbox.cos import COSDictionary, COSObjectKey

_LOG = logging.getLogger(__name__)


class XrefType(Enum):
    """Origin of an xref entry — kept so the writer can later re-emit
    the same form, and the resolver can decide which entries take
    precedence when sections overlap."""

    TABLE = "table"  # traditional ``xref`` table entry
    STREAM = "stream"  # xref-stream entry (PDF 1.5+)
    COMPRESSED = "compressed"  # entry inside an object stream (PDF 1.5+)


@dataclass
class XrefEntry:
    """One byte-offset entry from an xref section."""

    type: XrefType
    offset: int  # byte offset of the indirect object definition
    # For COMPRESSED entries this is instead the object number of the
    # containing object stream; the index within that stream lives in
    # ``compressed_index``.
    compressed_index: int = 0


@dataclass
class _Section:
    """One xref section: a table fragment plus the trailer that closes it."""

    entries: dict[COSObjectKey, XrefEntry] = field(default_factory=dict)
    trailer: COSDictionary | None = None
    # Byte offset of the ``xref`` keyword (or the xref-stream object) so
    # we can detect cycles when walking ``/Prev``.
    start_offset: int = -1
    # Origin type (TABLE vs STREAM) — mirrors upstream's per-XrefTrailerObj
    # ``xrefType`` field. Defaults to TABLE to match upstream's
    # ``XrefTrailerObj()`` constructor.
    xref_type: XrefType = XrefType.TABLE


class XrefTrailerResolver:
    """
    Holds every parsed xref section + trailer fragment and merges them
    into a single ``(COSObjectKey → XrefEntry)`` map and a single
    consolidated trailer.

    Mirrors `org.apache.pdfbox.pdfparser.XrefTrailerResolver`.

    Resolution rule (matches PDFBox + PDF spec): the **most recent**
    section wins for any overlapping key. "Most recent" = the section
    parsed last when walking ``/Prev`` from the latest xref backwards
    *in reverse insertion order* — i.e., the section we first read from
    disk is the newest one. Free entries from older sections are still
    visible if no newer section supersedes them, since they may indicate
    a deletion at that revision.
    """

    def __init__(self) -> None:
        self._sections: list[_Section] = []
        self._current: _Section | None = None
        # Cycle detection for /Prev walking — populated by the parser.
        self._visited_offsets: set[int] = set()
        # Resolved view (only populated by ``set_startxref``). Mirrors
        # upstream's ``resolvedXrefTrailer`` — separate from the per-section
        # storage so it can be re-built when the parser calls
        # ``set_startxref`` after all sections are collected.
        self._resolved_trailer: COSDictionary | None = None
        self._resolved_xref_table: dict[COSObjectKey, XrefEntry] | None = None
        self._resolved_xref_type: XrefType | None = None

    # ---------- section lifecycle ----------

    def begin_section(self, start_offset: int) -> None:
        """Start a new section. ``start_offset`` is the byte offset at
        which the section begins (the ``xref`` keyword or the xref-stream
        object header)."""
        section = _Section(start_offset=start_offset)
        self._sections.append(section)
        self._current = section
        if start_offset >= 0:
            self._visited_offsets.add(start_offset)

    def has_visited(self, offset: int) -> bool:
        return offset in self._visited_offsets

    def next_xref_obj(self, start_byte_pos: int, type_: XrefType) -> None:
        """Signal that a new xref object (table or stream) starts at the
        given byte position with the given type. Upstream-name parity
        wrapper around :meth:`begin_section` — mirrors PDFBox
        ``XrefTrailerResolver.nextXrefObj(long, XRefType)`` (Java line 152).
        Records ``type_`` on the section so ``get_xref_type()`` can read it
        back from the resolved trailer."""
        self.begin_section(start_byte_pos)
        # The section we just started is now ``self._current``.
        if self._current is not None:
            self._current.xref_type = type_

    # ---------- entry / trailer setters (operate on current section) ----------

    def set_entry(self, key: COSObjectKey, entry: XrefEntry) -> None:
        if self._current is None:
            raise RuntimeError("set_entry called before begin_section")
        # Within a single section, a later entry for the same key wins
        # — matches PDFBox behavior where the parser may overwrite an
        # earlier subsection entry if the file is malformed.
        self._current.entries[key] = entry

    def set_x_ref(self, obj_key: COSObjectKey, offset: int) -> None:
        """Add a single xref entry for the current section. Upstream-name
        parity wrapper around :meth:`set_entry` — mirrors PDFBox
        ``XrefTrailerResolver.setXRef(COSObjectKey, long)`` (Java line 175).

        Behavior matches upstream PDFBOX-3506: if an entry already exists
        for ``obj_key`` in the current section it is **not** overwritten —
        this protects table entries from being clobbered by obsolete
        ``/XRefStm`` entries in hybrid files. Logs a warning and silently
        returns if no section has been started (upstream also warns and
        returns rather than raising)."""
        if self._current is None:
            # Upstream logs and returns instead of raising.
            _LOG.warning(
                "Cannot add XRef entry for '%s' because XRef start was not signalled.",
                obj_key.object_number,
            )
            return
        if obj_key in self._current.entries:
            return
        # Default-type entry — upstream stores raw byte offsets without a
        # type tag because the section's xref_type already qualifies them.
        self._current.entries[obj_key] = XrefEntry(
            type=self._current.xref_type, offset=offset
        )

    def set_trailer(self, trailer: COSDictionary) -> None:
        if self._current is None:
            raise RuntimeError("set_trailer called before begin_section")
        self._current.trailer = trailer

    # ---------- merged views ----------

    def get_xref_table(self) -> dict[COSObjectKey, XrefEntry]:
        """Return the consolidated xref. Sections parsed earlier (i.e.
        newer in ``/Prev`` walking order) take precedence."""
        merged: dict[COSObjectKey, XrefEntry] = {}
        # Walk OLDEST → NEWEST so newer entries overwrite older ones.
        for section in reversed(self._sections):
            merged.update(section.entries)
        return merged

    def get_trailer(self) -> COSDictionary | None:
        """Return the consolidated trailer. The newest section's trailer
        wins; older sections' keys fill in anything the newest omits.
        Returns ``None`` if no section had a trailer."""
        merged: COSDictionary | None = None
        for section in reversed(self._sections):
            if section.trailer is None:
                continue
            if merged is None:
                merged = COSDictionary()
            for key, value in section.trailer.entry_set():
                merged.set_item(key, value)
        return merged

    # ---------- diagnostics ----------

    def section_count(self) -> int:
        return len(self._sections)

    def visited_offsets(self) -> set[int]:
        return set(self._visited_offsets)

    # ---------- per-section accessors (upstream parity) ----------

    def get_trailer_count(self) -> int:
        """Return the number of registered xref sections (each with a
        trailer slot). Mirrors PDFBox's ``getTrailerCount()`` — note that
        upstream counts byte-position keys, which equals one per section
        because every section is registered at a unique start offset."""
        return len(self._sections)

    def get_current_trailer(self) -> COSDictionary | None:
        """Return the trailer of the most recently begun section, or
        ``None`` if the current section has no trailer set yet (or no
        section has been started). Mirrors PDFBox's
        ``getCurrentTrailer()``."""
        if self._current is None:
            return None
        return self._current.trailer

    def get_first_trailer(self) -> COSDictionary | None:
        """Return the trailer of the section with the smallest start
        offset, or ``None`` if no sections exist. Sections registered
        with a negative start offset (synthetic / unknown position) are
        ignored — matches upstream which keys ``bytePosToXrefMap`` by
        the actual start byte position. Mirrors
        ``XrefTrailerResolver.getFirstTrailer()``."""
        ranked = [s for s in self._sections if s.start_offset >= 0]
        if not ranked:
            return None
        ranked.sort(key=lambda s: s.start_offset)
        return ranked[0].trailer

    def get_last_trailer(self) -> COSDictionary | None:
        """Return the trailer of the section with the largest start
        offset, or ``None`` if no sections exist. Mirrors
        ``XrefTrailerResolver.getLastTrailer()``."""
        ranked = [s for s in self._sections if s.start_offset >= 0]
        if not ranked:
            return None
        ranked.sort(key=lambda s: s.start_offset)
        return ranked[-1].trailer

    # ---------- resolved view (set_startxref + getters) ----------

    def set_startxref(self, startxref_byte_pos_value: int) -> None:
        """Set the byte position of the latest startxref so the resolver
        can build the chain of active xref/trailer objects. Mirrors PDFBox
        ``XrefTrailerResolver.setStartxref(long)`` (Java line 232).

        The resolved trailer/xref are exposed through
        :meth:`get_xref_type` and :meth:`get_contained_object_numbers`.
        Walks ``/Prev`` from the section at ``startxref_byte_pos_value``
        backwards. If no section is registered at that offset, falls back
        to merging every section in byte-position order (upstream's
        recovery behavior). Pass ``-1`` to opt into this fallback for
        documents with a missing startxref."""
        if self._resolved_trailer is not None:
            _LOG.warning(
                "Method must be called only ones with last startxref value."
            )
            return

        # Build a byte-pos → section map. Upstream uses ``HashMap<Long,
        # XrefTrailerObj>`` keyed by start offset; we walk our list
        # because sections were appended in arrival order.
        byte_pos_map: dict[int, _Section] = {
            s.start_offset: s for s in self._sections if s.start_offset >= 0
        }

        resolved_trailer = COSDictionary()
        resolved_table: dict[COSObjectKey, XrefEntry] = {}
        resolved_type: XrefType = XrefType.TABLE

        cur_obj = byte_pos_map.get(startxref_byte_pos_value)
        xref_seq_byte_pos: list[int] = []

        if cur_obj is None:
            _LOG.warning(
                "Did not found XRef object at specified startxref position %s",
                startxref_byte_pos_value,
            )
            # Use all objects in byte position order — last entries
            # overwrite previous ones (upstream lines 252-253).
            xref_seq_byte_pos = sorted(byte_pos_map.keys())
        else:
            resolved_type = cur_obj.xref_type
            xref_seq_byte_pos.append(startxref_byte_pos_value)
            while cur_obj.trailer is not None:
                prev_byte_pos = cur_obj.trailer.get_long("Prev", -1)
                if prev_byte_pos == -1:
                    break
                next_obj = byte_pos_map.get(prev_byte_pos)
                if next_obj is None:  # pragma: no cover - malformed /Prev chain recovery
                    _LOG.warning(
                        "Did not found XRef object pointed to by 'Prev' "
                        "key at position %s",
                        prev_byte_pos,
                    )
                    break
                cur_obj = next_obj
                xref_seq_byte_pos.append(prev_byte_pos)
                # Prevent infinite loops (upstream lines 278-282).
                if len(xref_seq_byte_pos) >= len(byte_pos_map):
                    break
            # Reverse so newer entries overwrite older ones.
            xref_seq_byte_pos.reverse()

        # Merge in the resolved order.
        for b_pos in xref_seq_byte_pos:
            section = byte_pos_map.get(b_pos)
            if section is None:  # pragma: no cover -- b_pos always sourced from byte_pos_map
                continue
            if section.trailer is not None:
                # COSDictionary.add_all merges keys without overwriting
                # existing ones in upstream PDFBox; replicate by only
                # setting keys not already present so newer trailer wins.
                # Actually upstream uses ``addAll`` which DOES overwrite —
                # see COSDictionary.addAll. We follow that behavior.
                for key, value in section.trailer.entry_set():
                    resolved_trailer.set_item(key, value)
            resolved_table.update(section.entries)

        self._resolved_trailer = resolved_trailer
        self._resolved_xref_table = resolved_table
        self._resolved_xref_type = resolved_type

    def get_xref_type(self) -> XrefType | None:
        """Return the resolved trailer's xref type, or ``None`` if
        :meth:`set_startxref` has not been called. Mirrors PDFBox
        ``XrefTrailerResolver.getXrefType()`` (Java line 164)."""
        return self._resolved_xref_type

    def get_contained_object_numbers(self, objstm_obj_nr: int) -> set[int] | None:
        """Return the object numbers contained within the object stream
        whose object number is ``objstm_obj_nr``. Mirrors PDFBox
        ``XrefTrailerResolver.getContainedObjectNumbers(int)`` (Java line
        336).

        In upstream's encoding, compressed-object xref entries store the
        object stream's number negated as the offset value. We use a
        typed encoding instead — :class:`XrefEntry` with
        ``type=XrefType.COMPRESSED`` and ``offset=objstm_obj_nr`` — so
        the comparison is on (type, offset) rather than a sign trick.

        Returns ``None`` (not an empty set) if :meth:`set_startxref` has
        not yet been called, matching upstream which returns ``null``
        when ``resolvedXrefTrailer`` is ``null``."""
        if self._resolved_xref_table is None:
            return None
        result: set[int] = set()
        for key, entry in self._resolved_xref_table.items():
            if entry.type is XrefType.COMPRESSED and entry.offset == objstm_obj_nr:
                result.add(key.object_number)
        return result

    def reset(self) -> None:
        """Clear every section's entry map and forget the current
        section so the resolver can be re-driven by a recovery pass.
        Trailers and start offsets are preserved on each section,
        matching upstream's ``reset()`` (which clears the per-object
        ``xrefTable`` map but keeps the ``XrefTrailerObj`` envelope and
        its trailer). Visited offsets are parser-walk state, so they are
        cleared with the entries."""
        for section in self._sections:
            section.entries.clear()
        self._current = None
        self._visited_offsets.clear()
        # Also drop any resolved view — set_startxref must be called
        # again after a reparse pass.
        self._resolved_trailer = None
        self._resolved_xref_table = None
        self._resolved_xref_type = None
