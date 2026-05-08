from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class CoverageTable:
    """Lightweight Coverage table wrapper.

    Mirrors ``org.apache.fontbox.ttf.table.common.CoverageTable``. Upstream
    is an abstract base with format-1 / format-2 concrete subclasses; for
    the GSUB lookup-subtable surface the only operation callers exercise
    is "is this GID covered, and at what index?". The Python port keeps a
    flat sequence of GIDs (already collapsed from format-2 ranges by the
    parser) and exposes the index lookup via :meth:`get_coverage_index`.
    """

    glyph_array: tuple[int, ...] = field(default_factory=tuple)
    coverage_format: int = 1

    def get_coverage_format(self) -> int:
        return self.coverage_format

    def get_glyph_array(self) -> tuple[int, ...]:
        return self.glyph_array

    def get_size(self) -> int:
        return len(self.glyph_array)

    def get_coverage_index(self, glyph_id: int) -> int:
        """Return the position of ``glyph_id`` in coverage, or ``-1``.

        Mirrors upstream ``CoverageTable.getCoverageIndex(int)``. Linear
        scan is fine for the small per-subtable arrays we see in real
        fonts; upstream itself does the same.
        """
        for idx, gid in enumerate(self.glyph_array):
            if gid == glyph_id:
                return idx
        return -1


class LookupSubTable(ABC):
    """Abstract base for OpenType GSUB lookup subtables.

    Mirrors ``org.apache.fontbox.ttf.table.common.LookupSubTable``. Each
    concrete subclass corresponds to one of the GSUB lookup *types* and
    one of the *formats* within that type (e.g. type-1 single substitution
    has formats 1 and 2). The single common operation is
    :meth:`do_substitution`, which takes an input GID and the matching
    coverage index and returns the substituted GID, or the original GID
    if the subtable does not cover the input.

    ``substitute_format`` records the OpenType subtable format. Upstream
    stores it on the abstract base together with the :class:`CoverageTable`
    so callers can branch without ``isinstance`` checks.
    """

    def __init__(
        self,
        substitute_format: int = 0,
        coverage_table: CoverageTable | None = None,
    ) -> None:
        self.substitute_format: int = substitute_format
        # Stored under a distinct name so dataclass subclasses that keep
        # ``coverage_table`` as a flat ``tuple[int, ...]`` (their public
        # field) aren't shadowed by the wrapper. Access via
        # :meth:`get_coverage_object` for the upstream-shaped object.
        self._coverage_object: CoverageTable = coverage_table or CoverageTable()

    def get_substitute_format(self) -> int:
        return self.substitute_format

    # Upstream alias — Java method is ``getSubstFormat``.
    def get_subst_format(self) -> int:
        return self.substitute_format

    def get_coverage_object(self) -> CoverageTable:
        """Return the :class:`CoverageTable` wrapper.

        Net-new accessor — upstream's ``getCoverageTable`` returns the
        wrapper directly, but pypdfbox subclasses ported earlier expose
        ``get_coverage_table`` as a flat ``tuple[int, ...]`` for
        backward compatibility. This accessor exposes the structured
        wrapper without breaking those callers.
        """
        return self._coverage_object

    @abstractmethod
    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        """Apply this subtable's substitution to ``original_glyph_id``.

        ``coverage_index`` is the position of ``original_glyph_id`` in
        the subtable's Coverage table, or ``-1`` if the glyph is not
        covered. Implementations return the substituted GID or
        ``original_glyph_id`` itself when ``coverage_index < 0``.
        Mirrors ``LookupSubTable.doSubstitution`` upstream.
        """
        raise NotImplementedError


@dataclass
class LookupTypeSingleSubstFormat1(LookupSubTable):
    """Type-1, Format-1 single substitution (Coverage + DeltaGlyphID).

    Mirrors
    ``org.apache.fontbox.ttf.table.gsub.LookupTypeSingleSubstFormat1``.
    A format-1 subtable substitutes any covered glyph by adding a
    constant ``delta_glyph_id`` to its GID; the result is taken modulo
    65536 per the spec.

    ``coverage_table`` is the ordered list of covered GIDs (the parser
    already collapses Coverage Format 1 ranges into a flat list, matching
    upstream).
    """

    delta_glyph_id: int = 0
    coverage_table: tuple[int, ...] = field(default_factory=tuple)
    substitute_format: int = 1

    def __post_init__(self) -> None:
        # ``dataclass`` skips ``LookupSubTable.__init__`` so initialise the
        # base attribute by hand. Keeps both surfaces (dataclass field +
        # base attribute) in sync.
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=tuple(self.coverage_table)),
        )

    def get_delta_glyph_id(self) -> int:
        return self.delta_glyph_id

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        if coverage_index < 0:
            return original_glyph_id
        # Per spec: substituted GID is computed mod 65536.
        return (original_glyph_id + self.delta_glyph_id) & 0xFFFF


@dataclass
class LookupTypeSingleSubstFormat2(LookupSubTable):
    """Type-1, Format-2 single substitution (Coverage + Substitute array).

    Mirrors
    ``org.apache.fontbox.ttf.table.gsub.LookupTypeSingleSubstFormat2``.
    Each covered GID is replaced by the GID at the same index in
    ``substitute_glyph_ids``. The two arrays MUST have the same length;
    upstream's parser guarantees this.
    """

    substitute_glyph_ids: tuple[int, ...] = field(default_factory=tuple)
    coverage_table: tuple[int, ...] = field(default_factory=tuple)
    substitute_format: int = 2

    def __post_init__(self) -> None:
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=tuple(self.coverage_table)),
        )

    def get_substitute_glyph_ids(self) -> tuple[int, ...]:
        return self.substitute_glyph_ids

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        if coverage_index < 0:
            return original_glyph_id
        if coverage_index >= len(self.substitute_glyph_ids):
            return original_glyph_id
        return int(self.substitute_glyph_ids[coverage_index])


@dataclass
class SequenceTable:
    """One Type-2 multiple-substitution sequence (one input, many outputs).

    Mirrors ``org.apache.fontbox.ttf.table.gsub.SequenceTable``. Each
    Sequence sits at one Coverage index of a
    :class:`LookupTypeMultipleSubstitutionFormat1`; ``substitute_glyph_ids``
    is the ordered list of output GIDs (which may be longer than 1, equal
    to 1, or zero per the spec — though zero is rare in real fonts).
    """

    glyph_count: int = 0
    substitute_glyph_ids: tuple[int, ...] = field(default_factory=tuple)

    def get_glyph_count(self) -> int:
        return self.glyph_count

    def get_substitute_glyph_ids(self) -> tuple[int, ...]:
        return self.substitute_glyph_ids


@dataclass
class LookupTypeMultipleSubstitutionFormat1(LookupSubTable):
    """Type-2, Format-1 multiple substitution (one glyph -> many).

    Mirrors
    ``org.apache.fontbox.ttf.table.gsub.LookupTypeMultipleSubstitutionFormat1``.
    A multiple-substitution lookup expands a single covered glyph into
    a sequence of GIDs (e.g. decomposing a precomposed digit-zero into
    a slashed-zero variant glyph plus a combining mark).

    The single-glyph :meth:`do_substitution` signature inherited from the
    base class can't express many-output shaping, so upstream raises
    ``UnsupportedOperationException`` from it. We mirror that with
    :class:`NotImplementedError`. Use :meth:`do_substitution_multiple`
    to obtain the GID list for the matched coverage index.
    """

    coverage_table: tuple[int, ...] = field(default_factory=tuple)
    sequence_tables: tuple[SequenceTable, ...] = field(default_factory=tuple)
    substitute_format: int = 1

    def __post_init__(self) -> None:
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=tuple(self.coverage_table)),
        )

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def get_sequence_tables(self) -> tuple[SequenceTable, ...]:
        return self.sequence_tables

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        # Upstream throws UnsupportedOperationException("not applicable").
        raise NotImplementedError(
            "Multiple substitution produces a glyph sequence; "
            "use do_substitution_multiple instead."
        )

    def do_substitution_multiple(
        self, original_glyph_id: int, coverage_index: int
    ) -> list[int]:
        """Expand ``original_glyph_id`` to its substitute sequence.

        Returns ``[original_glyph_id]`` when ``coverage_index < 0`` or
        when the coverage index is out of range — defensive behavior for
        malformed fonts, matching the type-1 / type-3 passthrough rule.
        """
        if coverage_index < 0:
            return [original_glyph_id]
        if coverage_index >= len(self.sequence_tables):
            return [original_glyph_id]
        return list(self.sequence_tables[coverage_index].substitute_glyph_ids)


@dataclass
class AlternateSetTable:
    """One Type-3 alternate set (one input, many alternate outputs).

    Mirrors ``org.apache.fontbox.ttf.table.gsub.AlternateSetTable``. Each
    AlternateSet sits at one Coverage index of a
    :class:`LookupTypeAlternateSubstitutionFormat1`; ``alternate_glyph_ids``
    is the ordered list of available alternate GIDs (e.g. stylistic or
    swash variants). Selection among alternates is the layout engine's
    responsibility — the lookup itself just exposes the candidates.
    """

    glyph_count: int = 0
    alternate_glyph_ids: tuple[int, ...] = field(default_factory=tuple)

    def get_glyph_count(self) -> int:
        return self.glyph_count

    def get_alternate_glyph_ids(self) -> tuple[int, ...]:
        return self.alternate_glyph_ids


@dataclass
class LookupTypeAlternateSubstitutionFormat1(LookupSubTable):
    """Type-3, Format-1 alternate substitution (one glyph -> N alternates).

    Mirrors
    ``org.apache.fontbox.ttf.table.gsub.LookupTypeAlternateSubstitutionFormat1``.

    Alternate-substitution lookups don't pick a winner — they *expose*
    the alternate set for a given glyph; the active feature (e.g.
    `salt`, `aalt`) and the layout engine choose. So the single-glyph
    :meth:`do_substitution` signature is unsupported (matches upstream
    ``UnsupportedOperationException``); use
    :meth:`get_alternate_glyph_ids_for` to obtain the candidate list.
    """

    coverage_table: tuple[int, ...] = field(default_factory=tuple)
    alternate_set_tables: tuple[AlternateSetTable, ...] = field(default_factory=tuple)
    substitute_format: int = 1

    def __post_init__(self) -> None:
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=tuple(self.coverage_table)),
        )

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def get_alternate_set_tables(self) -> tuple[AlternateSetTable, ...]:
        return self.alternate_set_tables

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        raise NotImplementedError(
            "Alternate substitution exposes a candidate set; "
            "use get_alternate_glyph_ids_for instead."
        )

    def get_alternate_glyph_ids_for(
        self, original_glyph_id: int, coverage_index: int
    ) -> tuple[int, ...]:
        """Return the alternate GIDs for ``original_glyph_id``.

        Returns an empty tuple when the glyph isn't covered or the
        coverage index falls outside ``alternate_set_tables``. Net-new
        helper (no upstream counterpart) — upstream expects callers to
        index ``alternate_set_tables`` directly with the coverage index;
        we centralise the bounds check here.
        """
        if coverage_index < 0:
            return ()
        if coverage_index >= len(self.alternate_set_tables):
            return ()
        return self.alternate_set_tables[coverage_index].alternate_glyph_ids


@dataclass
class LookupTypeLigatureSubstitutionSubstFormat1(LookupSubTable):
    """Type-4, Format-1 ligature substitution.

    Mirrors
    ``org.apache.fontbox.ttf.table.gsub.LookupTypeLigatureSubstitutionSubstFormat1``.
    A ligature subtable holds, for each covered first-glyph position,
    a list of :class:`LigatureTable` candidates. Each candidate names
    the trailing component GIDs and the resulting ligature GID.

    The single-glyph :meth:`do_substitution` signature inherited from the
    base class doesn't fit ligature shaping (which is many-to-one), so
    upstream raises ``UnsupportedOperationException`` from it. We mirror
    that with :class:`NotImplementedError`. Use
    :meth:`do_substitution_glyphs` (added in upstream PDFBox 3.0.x via
    PDFBOX-5780) for the full shape lookup, and accept the GID list it
    returns.
    """

    coverage_table: tuple[int, ...] = field(default_factory=tuple)
    ligature_set_tables: tuple[LigatureSetTable, ...] = field(default_factory=tuple)
    substitute_format: int = 1

    def __post_init__(self) -> None:
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=tuple(self.coverage_table)),
        )

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def get_ligature_set_tables(self) -> tuple[LigatureSetTable, ...]:
        return self.ligature_set_tables

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        # Ligature lookups consume multiple glyphs and produce one — the
        # single-glyph signature can't express the shaping result.
        # Upstream throws UnsupportedOperationException here.
        raise NotImplementedError(
            "Ligature substitution requires a glyph sequence; "
            "use do_substitution_glyphs instead."
        )

    def do_substitution_glyphs(self, glyph_ids: list[int]) -> list[int]:
        """Apply ligature substitution to a glyph run.

        Walks ``glyph_ids`` left-to-right. At each position, if the glyph
        is covered and a :class:`LigatureTable` candidate's component
        GIDs match the following glyphs, those glyphs are collapsed into
        the candidate's ``ligature_glyph`` (longest-match wins, matching
        the spec's "search the array of Ligatures in order" rule).
        Returns a new list — the input is not mutated.
        """
        if not glyph_ids:
            return []
        out: list[int] = []
        i = 0
        n = len(glyph_ids)
        while i < n:
            gid = glyph_ids[i]
            cov_idx = -1
            for c_i, c_gid in enumerate(self.coverage_table):
                if c_gid == gid:
                    cov_idx = c_i
                    break
            if cov_idx < 0 or cov_idx >= len(self.ligature_set_tables):
                out.append(gid)
                i += 1
                continue
            best: LigatureTable | None = None
            best_len = 0
            for lig in self.ligature_set_tables[cov_idx].ligature_tables:
                comps = lig.component_glyph_ids
                if not comps:
                    continue
                end = i + 1 + len(comps)
                if end > n:
                    continue
                if all(
                    glyph_ids[i + 1 + k] == comps[k] for k in range(len(comps))
                ) and len(comps) >= best_len:
                    best = lig
                    best_len = len(comps)
            if best is None:
                out.append(gid)
                i += 1
            else:
                out.append(best.ligature_glyph)
                i += 1 + best_len
        return out


@dataclass
class LigatureTable:
    """One ligature candidate inside a :class:`LigatureSetTable`.

    Mirrors ``org.apache.fontbox.ttf.table.gsub.LigatureTable``.
    ``ligature_glyph`` is the GID emitted on a successful match;
    ``component_glyph_ids`` are the *trailing* component GIDs (the first
    component is the one indexed by Coverage on the parent subtable, so
    it is implicit and not stored here — matching the OpenType spec).
    ``component_count`` mirrors upstream's redundant explicit-count field
    (one larger than the trailing-component array — it counts the
    implicit first component too).
    """

    ligature_glyph: int = 0
    component_glyph_ids: tuple[int, ...] = field(default_factory=tuple)
    component_count: int = 0

    def __post_init__(self) -> None:
        # Upstream stores the component count explicitly; default to the
        # canonical "trailing components + 1 implicit first" so callers
        # that don't pass it still see the right value.
        if self.component_count == 0 and self.component_glyph_ids:
            self.component_count = len(self.component_glyph_ids) + 1

    def get_ligature_glyph(self) -> int:
        return self.ligature_glyph

    def get_component_glyph_ids(self) -> tuple[int, ...]:
        return self.component_glyph_ids

    def get_component_count(self) -> int:
        return self.component_count


@dataclass
class LigatureSetTable:
    """Bundle of ligature candidates that share a first component.

    Mirrors ``org.apache.fontbox.ttf.table.gsub.LigatureSetTable``. Each
    LigatureSet sits at one Coverage index; its ``ligature_tables`` are
    ordered by descending priority per the spec. ``ligature_count``
    mirrors upstream's redundant explicit-count field.
    """

    ligature_tables: tuple[LigatureTable, ...] = field(default_factory=tuple)
    ligature_count: int = 0

    def __post_init__(self) -> None:
        if self.ligature_count == 0 and self.ligature_tables:
            self.ligature_count = len(self.ligature_tables)

    def get_ligature_tables(self) -> tuple[LigatureTable, ...]:
        return self.ligature_tables

    def get_ligature_count(self) -> int:
        return self.ligature_count


__all__ = [
    "AlternateSetTable",
    "CoverageTable",
    "LigatureSetTable",
    "LigatureTable",
    "LookupSubTable",
    "LookupTypeAlternateSubstitutionFormat1",
    "LookupTypeLigatureSubstitutionSubstFormat1",
    "LookupTypeMultipleSubstitutionFormat1",
    "LookupTypeSingleSubstFormat1",
    "LookupTypeSingleSubstFormat2",
    "SequenceTable",
]
