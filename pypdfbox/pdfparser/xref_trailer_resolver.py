from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pypdfbox.cos import COSDictionary, COSObjectKey


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

    # ---------- entry / trailer setters (operate on current section) ----------

    def set_entry(self, key: COSObjectKey, entry: XrefEntry) -> None:
        if self._current is None:
            raise RuntimeError("set_entry called before begin_section")
        # Within a single section, a later entry for the same key wins
        # — matches PDFBox behavior where the parser may overwrite an
        # earlier subsection entry if the file is malformed.
        self._current.entries[key] = entry

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
