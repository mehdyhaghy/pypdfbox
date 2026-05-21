from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

_LOG = logging.getLogger(__name__)


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

    def get_glyph_id(self, index: int) -> int:
        """Return the GID stored at ``index`` in coverage.

        Mirrors upstream ``CoverageTable.getGlyphId(int)`` — the abstract
        format-1 / format-2 split in Java is collapsed in the Python port
        because the parser already materialises both formats into a flat
        ``glyph_array``. Returns ``-1`` for out-of-range indices to match
        the defensive contract upstream concrete subclasses follow.
        """
        if index < 0 or index >= len(self.glyph_array):
            return -1
        return self.glyph_array[index]


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

    def get_coverage_table(self) -> CoverageTable:
        """Return the :class:`CoverageTable` wrapper (upstream-shaped).

        Mirrors ``LookupSubTable.getCoverageTable()`` upstream which
        returns the ``CoverageTable`` reference held on the abstract
        base. Concrete subclasses in this port override this accessor
        and return their flat ``tuple[int, ...]`` Coverage instead, so
        this base implementation only handles the abstract-base contract
        used by callers holding a generic :class:`LookupSubTable`.
        """
        return self._coverage_object

    @abstractmethod
    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        """Apply this subtable's substitution to ``original_glyph_id``.

        ``coverage_index`` is the position of ``original_glyph_id`` in
        the subtable's Coverage table, or ``-1`` if the glyph is not
        covered. Implementations return the substituted GID or
        ``original_glyph_id`` itself when ``coverage_index < 0``.
        Mirrors ``LookupSubTable.doSubstitution`` upstream — declared
        ``@abstractmethod`` here; concrete subclasses (type-1 single
        substitution being the only one with a meaningful single-GID
        return) own the substitution semantics.
        """


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

    def to_string(self) -> str:
        """Mirror upstream ``LookupTypeSingleSubstFormat1.toString()``.

        Upstream format:
        ``LookupTypeSingleSubstFormat1[substFormat=<F>,deltaGlyphID=<D>]``.
        """
        return (
            "LookupTypeSingleSubstFormat1["
            f"substFormat={self.substitute_format},"
            f"deltaGlyphID={self.delta_glyph_id}]"
        )

    def __str__(self) -> str:
        return self.to_string()


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

    def get_substitute_glyph_i_ds(self) -> tuple[int, ...]:
        """Snake-case mechanical translation of upstream ``getSubstituteGlyphIDs``.

        Java keeps the trailing ``IDs`` capitalised as an acronym; the
        deterministic camelCase-to-snake_case translation splits the
        boundary between ``I`` and ``D`` and yields ``i_ds``. Kept as a
        thin alias so tooling that mirrors upstream method names verbatim
        still resolves.
        """
        return self.substitute_glyph_ids

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        if coverage_index < 0:
            return original_glyph_id
        if coverage_index >= len(self.substitute_glyph_ids):
            return original_glyph_id
        return int(self.substitute_glyph_ids[coverage_index])

    def to_string(self) -> str:
        """Mirror upstream ``LookupTypeSingleSubstFormat2.toString()``.

        Upstream format (uses ``Arrays.toString(int[])`` for the GID
        array, which renders as ``[a, b, c]`` with a space after each
        comma):
        ``LookupTypeSingleSubstFormat2[substFormat=<F>,substituteGlyphIDs=[<...>]]``.
        """
        gids = "[" + ", ".join(str(g) for g in self.substitute_glyph_ids) + "]"
        return (
            "LookupTypeSingleSubstFormat2["
            f"substFormat={self.substitute_format},"
            f"substituteGlyphIDs={gids}]"
        )

    def __str__(self) -> str:
        return self.to_string()


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

    def get_substitute_glyph_i_ds(self) -> tuple[int, ...]:
        """Snake-case mechanical translation of upstream ``getSubstituteGlyphIDs``.

        Mirrors the same ``IDs`` acronym split rule as
        :meth:`LigatureTable.get_component_glyph_i_ds`.
        """
        return self.substitute_glyph_ids

    def to_string(self) -> str:
        """Mirror upstream ``SequenceTable.toString()``.

        Upstream format:
        ``SequenceTable{glyphCount=<N>, substituteGlyphIDs=[<...>]}``.
        """
        gids = "[" + ", ".join(str(g) for g in self.substitute_glyph_ids) + "]"
        return (
            "SequenceTable{"
            f"glyphCount={self.glyph_count}, "
            f"substituteGlyphIDs={gids}"
            "}"
        )

    def __str__(self) -> str:
        return self.to_string()


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
        # Upstream throws UnsupportedOperationException("not applicable")
        # — the single-glyph signature can't express a glyph sequence.
        # Python's nearest equivalent for "operation not supported on
        # this object" is ``TypeError`` (cf. tuple.__setitem__).
        raise TypeError(
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

    def get_alternate_glyph_i_ds(self) -> tuple[int, ...]:
        """Snake-case mechanical translation of upstream ``getAlternateGlyphIDs``.

        Mirrors the same ``IDs`` acronym split rule as
        :meth:`LigatureTable.get_component_glyph_i_ds`.
        """
        return self.alternate_glyph_ids

    def to_string(self) -> str:
        """Mirror upstream ``AlternateSetTable.toString()``.

        Upstream format:
        ``AlternateSetTable{glyphCount=<N>, alternateGlyphIDs=[<...>]}``.
        """
        gids = "[" + ", ".join(str(g) for g in self.alternate_glyph_ids) + "]"
        return (
            "AlternateSetTable{"
            f"glyphCount={self.glyph_count}, "
            f"alternateGlyphIDs={gids}"
            "}"
        )

    def __str__(self) -> str:
        return self.to_string()


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
        # Upstream throws UnsupportedOperationException; alternates need
        # a layout-engine pick, not a single-glyph result. Python's
        # nearest equivalent is ``TypeError``.
        raise TypeError(
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
        # Upstream throws UnsupportedOperationException here. Python's
        # nearest equivalent is ``TypeError``.
        raise TypeError(
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

    def to_string(self) -> str:
        """Mirror upstream ``LookupTypeLigatureSubstitutionSubstFormat1.toString()``.

        Upstream format (uses ``getClass().getSimpleName()`` for the
        prefix, which resolves to the class name):
        ``LookupTypeLigatureSubstitutionSubstFormat1[substFormat=<F>]``.
        """
        return (
            "LookupTypeLigatureSubstitutionSubstFormat1["
            f"substFormat={self.substitute_format}]"
        )

    def __str__(self) -> str:
        return self.to_string()


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

    def get_component_glyph_i_ds(self) -> tuple[int, ...]:
        """Snake-case mechanical translation of upstream ``getComponentGlyphIDs``.

        Java keeps the trailing ``IDs`` capitalised as an acronym; the
        deterministic camelCase-to-snake_case translation drops the
        boundary between ``I`` and ``D`` and yields ``i_ds``. Kept as a
        thin alias so tooling that mirrors upstream method names verbatim
        still resolves.
        """
        return self.component_glyph_ids

    def get_component_count(self) -> int:
        return self.component_count

    def to_string(self) -> str:
        """Mirror upstream ``LigatureTable.toString()``.

        Upstream format: ``LigatureTable[ligatureGlyph=<N>, componentCount=<M>]``.
        Keep verbatim so log-scraping parity holds.
        """
        return (
            f"LigatureTable[ligatureGlyph={self.ligature_glyph}, "
            f"componentCount={self.component_count}]"
        )

    def __str__(self) -> str:
        return self.to_string()


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

    def to_string(self) -> str:
        """Mirror upstream ``LigatureSetTable.toString()``.

        Upstream format (uses ``getClass().getSimpleName()`` for the
        prefix): ``LigatureSetTable[ligatureCount=<N>]``.
        """
        return f"LigatureSetTable[ligatureCount={self.ligature_count}]"

    def __str__(self) -> str:
        return self.to_string()


@dataclass
class SubstitutionLookupRecord:
    """A single nested-lookup pointer used by Type 5 and Type 6 rules.

    Mirrors the OpenType ``SubstLookupRecord`` (GSUB spec §5
    "Lookup-record format"). The pair (``sequence_index``,
    ``lookup_list_index``) means: when the parent rule has matched
    against an input sequence, locate the LookupTable at
    ``lookup_list_index`` in the LookupList and apply it to the input
    glyph at offset ``sequence_index`` (zero-based, counting from the
    first input glyph). Upstream PDFBox 3.0 does not yet ship Types 5 /
    6 (see ``GlyphSubstitutionTable.readLookupSubtable`` upstream which
    points to Apache FOP for guidance); the data classes ported here
    follow the fontTools ``otTables.SubstLookupRecord`` shape and the
    OpenType spec verbatim.
    """

    sequence_index: int = 0
    lookup_list_index: int = 0

    def get_sequence_index(self) -> int:
        return self.sequence_index

    def get_lookup_list_index(self) -> int:
        return self.lookup_list_index

    def to_string(self) -> str:
        return (
            "SubstitutionLookupRecord["
            f"sequenceIndex={self.sequence_index},"
            f"lookupListIndex={self.lookup_list_index}]"
        )

    def __str__(self) -> str:
        return self.to_string()


@dataclass
class SequenceRule:
    """One context rule inside a :class:`SequenceRuleSet`.

    Mirrors fontTools ``SubRule`` (OpenType "SubRule" table in GSUB
    Lookup Type 5, Format 1). The *first* input glyph is the one
    indexed by the parent subtable's Coverage; ``input_sequence`` holds
    the *trailing* input GIDs (i.e. starting with the second glyph),
    matching the spec's "Array of input GlyphIDs - start with second
    glyph" wording. ``glyph_count`` records the total input length
    (including the implicit first glyph), so ``len(input_sequence) ==
    glyph_count - 1``.
    """

    input_sequence: tuple[int, ...] = field(default_factory=tuple)
    substitution_lookup_records: tuple[SubstitutionLookupRecord, ...] = field(
        default_factory=tuple
    )
    glyph_count: int = 0

    def __post_init__(self) -> None:
        if self.glyph_count == 0:
            self.glyph_count = len(self.input_sequence) + 1

    def get_input_sequence(self) -> tuple[int, ...]:
        return self.input_sequence

    def get_substitution_lookup_records(
        self,
    ) -> tuple[SubstitutionLookupRecord, ...]:
        return self.substitution_lookup_records

    def get_glyph_count(self) -> int:
        return self.glyph_count

    def matches(self, glyph_ids: list[int], start_index: int) -> bool:
        """Return ``True`` if ``input_sequence`` matches at ``start_index + 1``.

        The first input glyph is matched against ``glyph_ids[start_index]``
        by the parent subtable's Coverage check; this helper only
        validates the *trailing* glyphs against the rule's
        ``input_sequence``.
        """
        # Guard against negative offsets (defensive — callers should
        # have already established a non-negative start_index via the
        # parent Coverage check, but matches() is a public surface).
        if start_index < 0:
            return False
        end = start_index + 1 + len(self.input_sequence)
        if end > len(glyph_ids):
            return False
        return all(
            glyph_ids[start_index + 1 + i] == gid
            for i, gid in enumerate(self.input_sequence)
        )


@dataclass
class SequenceRuleSet:
    """Ordered set of :class:`SequenceRule` candidates for one Coverage index.

    Mirrors fontTools ``SubRuleSet``. Sits at one Coverage index of a
    :class:`LookupTypeContextualSubstitutionFormat1`. The rules are
    ordered by preference — the first match wins, matching the spec's
    "ordered by preference" wording on the SubRuleSet table.
    """

    sequence_rules: tuple[SequenceRule, ...] = field(default_factory=tuple)

    def get_sequence_rules(self) -> tuple[SequenceRule, ...]:
        return self.sequence_rules

    def get_sequence_rule_count(self) -> int:
        return len(self.sequence_rules)


@dataclass
class LookupTypeContextualSubstitutionFormat1(LookupSubTable):
    """Type-5, Format-1 contextual substitution (simple glyph context).

    Mirrors the OpenType "Context Substitution Format 1: Simple Glyph
    Contexts" subtable (GSUB §5.1). For each covered first glyph, the
    subtable holds an ordered :class:`SequenceRuleSet` of candidate
    rules; each rule names a trailing input sequence plus a list of
    nested-lookup pointers to apply when the input matches.

    Like Types 2 / 3 / 4 the single-glyph ``do_substitution`` signature
    can't express the contextual fan-out — callers obtain the matched
    rule via :meth:`match_rule` and apply each
    :class:`SubstitutionLookupRecord` against the LookupList themselves.
    """

    coverage_table: tuple[int, ...] = field(default_factory=tuple)
    sequence_rule_sets: tuple[SequenceRuleSet | None, ...] = field(
        default_factory=tuple
    )
    substitute_format: int = 1

    def __post_init__(self) -> None:
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=tuple(self.coverage_table)),
        )

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def get_sequence_rule_sets(self) -> tuple[SequenceRuleSet | None, ...]:
        return self.sequence_rule_sets

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        # Contextual lookups fan out to nested lookups against a glyph
        # *run*; the single-glyph signature can't express the result.
        # Mirrors the ``UnsupportedOperationException`` pattern Types
        # 2 / 3 / 4 already use upstream.
        raise TypeError(
            "Contextual substitution requires a glyph sequence and access "
            "to the LookupList; use match_rule + apply via the parent "
            "extractor instead."
        )

    def match_rule(
        self, glyph_ids: list[int], start_index: int
    ) -> SequenceRule | None:
        """Return the first matching :class:`SequenceRule`, or ``None``.

        Walks the parent's Coverage for the glyph at ``start_index``;
        if covered, scans the corresponding :class:`SequenceRuleSet`'s
        rules in order and returns the first whose ``input_sequence``
        matches the trailing glyphs.
        """
        if start_index < 0 or start_index >= len(glyph_ids):
            return None
        gid = glyph_ids[start_index]
        cov_idx = -1
        for c_i, c_gid in enumerate(self.coverage_table):
            if c_gid == gid:
                cov_idx = c_i
                break
        if cov_idx < 0 or cov_idx >= len(self.sequence_rule_sets):
            return None
        rule_set = self.sequence_rule_sets[cov_idx]
        if rule_set is None:
            return None
        for rule in rule_set.sequence_rules:
            if rule.matches(glyph_ids, start_index):
                return rule
        return None


@dataclass
class ClassRule:
    """One class-based context rule inside a :class:`ClassRuleSet`.

    Mirrors fontTools ``SubClassRule`` (GSUB Lookup Type 5, Format 2).
    Like :class:`SequenceRule` but the input is expressed as *class*
    indices (looked up against the parent subtable's
    :class:`ClassDefinitionTable`) rather than glyph IDs. The first
    input class is the class of the Coverage glyph; ``input_classes``
    holds the trailing class indices.
    """

    input_classes: tuple[int, ...] = field(default_factory=tuple)
    substitution_lookup_records: tuple[SubstitutionLookupRecord, ...] = field(
        default_factory=tuple
    )
    glyph_count: int = 0

    def __post_init__(self) -> None:
        if self.glyph_count == 0:
            self.glyph_count = len(self.input_classes) + 1

    def get_input_classes(self) -> tuple[int, ...]:
        return self.input_classes

    def get_substitution_lookup_records(
        self,
    ) -> tuple[SubstitutionLookupRecord, ...]:
        return self.substitution_lookup_records

    def get_glyph_count(self) -> int:
        return self.glyph_count


@dataclass
class ClassRuleSet:
    """Ordered set of :class:`ClassRule` candidates for one class index."""

    class_rules: tuple[ClassRule, ...] = field(default_factory=tuple)

    def get_class_rules(self) -> tuple[ClassRule, ...]:
        return self.class_rules


@dataclass
class ClassDefinitionTable:
    """Mapping from glyph ID to integer class.

    Mirrors the OpenType "Class Definition Table" used by Type 5
    Format 2 and Type 6 Format 2 (GSUB §5.2 / §6.2). Glyphs not present
    in the mapping default to class 0.
    """

    glyph_to_class: tuple[tuple[int, int], ...] = field(default_factory=tuple)

    def get_class(self, glyph_id: int) -> int:
        for gid, cls in self.glyph_to_class:
            if gid == glyph_id:
                return cls
        return 0


@dataclass
class LookupTypeContextualSubstitutionFormat2(LookupSubTable):
    """Type-5, Format-2 contextual substitution (class-based contexts).

    Mirrors the OpenType "Context Substitution Format 2: Class-based
    Glyph Contexts" subtable (GSUB §5.2). Glyphs are partitioned into
    classes via :class:`ClassDefinitionTable`; the rule sets are
    indexed by the *first* glyph's class.
    """

    coverage_table: tuple[int, ...] = field(default_factory=tuple)
    class_definition: ClassDefinitionTable = field(default_factory=ClassDefinitionTable)
    class_rule_sets: tuple[ClassRuleSet | None, ...] = field(default_factory=tuple)
    substitute_format: int = 2

    def __post_init__(self) -> None:
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=tuple(self.coverage_table)),
        )

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def get_class_definition(self) -> ClassDefinitionTable:
        return self.class_definition

    def get_class_rule_sets(self) -> tuple[ClassRuleSet | None, ...]:
        return self.class_rule_sets

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        raise TypeError(
            "Contextual substitution requires a glyph sequence and access "
            "to the LookupList; use match_rule + apply via the parent "
            "extractor instead."
        )

    def match_rule(
        self, glyph_ids: list[int], start_index: int
    ) -> ClassRule | None:
        if start_index < 0 or start_index >= len(glyph_ids):
            return None
        gid = glyph_ids[start_index]
        # Coverage check first — the first input glyph must be covered.
        if gid not in self.coverage_table:
            return None
        first_class = self.class_definition.get_class(gid)
        if first_class < 0 or first_class >= len(self.class_rule_sets):
            return None
        rule_set = self.class_rule_sets[first_class]
        if rule_set is None:
            return None
        for rule in rule_set.class_rules:
            end = start_index + 1 + len(rule.input_classes)
            if end > len(glyph_ids):
                continue
            if all(
                self.class_definition.get_class(glyph_ids[start_index + 1 + i])
                == cls
                for i, cls in enumerate(rule.input_classes)
            ):
                return rule
        return None


@dataclass
class LookupTypeContextualSubstitutionFormat3(LookupSubTable):
    """Type-5, Format-3 contextual substitution (per-position Coverage).

    Mirrors the OpenType "Context Substitution Format 3: Coverage-based
    Glyph Contexts" subtable (GSUB §5.3). Every position in the input
    sequence has its own Coverage table; a position matches iff its
    input glyph appears in the corresponding Coverage. The single
    :attr:`coverage_table` on the base class points at the *first*
    Coverage so the existing Type-1 / Type-4 contract (cheap "is this
    glyph eligible?" check) still works.
    """

    input_coverages: tuple[tuple[int, ...], ...] = field(default_factory=tuple)
    substitution_lookup_records: tuple[SubstitutionLookupRecord, ...] = field(
        default_factory=tuple
    )
    substitute_format: int = 3

    def __post_init__(self) -> None:
        first_coverage = (
            tuple(self.input_coverages[0]) if self.input_coverages else ()
        )
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=first_coverage),
        )

    def get_input_coverages(self) -> tuple[tuple[int, ...], ...]:
        return self.input_coverages

    def get_substitution_lookup_records(
        self,
    ) -> tuple[SubstitutionLookupRecord, ...]:
        return self.substitution_lookup_records

    def get_coverage_table(self) -> tuple[int, ...]:
        # Match the upstream contract: the base "coverage_table" is the
        # first input position's Coverage (used for the Coverage-eligible
        # short-circuit).
        return self.input_coverages[0] if self.input_coverages else ()

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        raise TypeError(
            "Contextual substitution requires a glyph sequence and access "
            "to the LookupList; use matches + apply via the parent "
            "extractor instead."
        )

    def matches(self, glyph_ids: list[int], start_index: int) -> bool:
        """Return ``True`` if the full input Coverage chain matches at
        ``start_index``.

        Every position ``k`` in ``input_coverages`` is checked against
        ``glyph_ids[start_index + k]``; the position matches iff the
        glyph appears in that position's Coverage.
        """
        if start_index < 0:
            return False
        if start_index + len(self.input_coverages) > len(glyph_ids):
            return False
        return all(
            glyph_ids[start_index + k] in cov
            for k, cov in enumerate(self.input_coverages)
        )


@dataclass
class ChainedSequenceRule:
    """One chained-context rule inside a :class:`ChainedSequenceRuleSet`.

    Mirrors fontTools ``ChainSubRule`` (GSUB Lookup Type 6, Format 1).
    Extends :class:`SequenceRule` with explicit *backtrack* and
    *lookahead* glyph sequences. Per the spec, the backtrack list is
    stored in **reverse glyph order** — that is, ``backtrack_sequence[0]``
    is the glyph *immediately preceding* the first input glyph,
    ``backtrack_sequence[1]`` is the one before *that*, and so on.
    Lookahead is stored in natural order.
    """

    backtrack_sequence: tuple[int, ...] = field(default_factory=tuple)
    input_sequence: tuple[int, ...] = field(default_factory=tuple)
    lookahead_sequence: tuple[int, ...] = field(default_factory=tuple)
    substitution_lookup_records: tuple[SubstitutionLookupRecord, ...] = field(
        default_factory=tuple
    )

    def get_backtrack_sequence(self) -> tuple[int, ...]:
        return self.backtrack_sequence

    def get_input_sequence(self) -> tuple[int, ...]:
        return self.input_sequence

    def get_lookahead_sequence(self) -> tuple[int, ...]:
        return self.lookahead_sequence

    def get_substitution_lookup_records(
        self,
    ) -> tuple[SubstitutionLookupRecord, ...]:
        return self.substitution_lookup_records

    def matches(self, glyph_ids: list[int], start_index: int) -> bool:
        """Return ``True`` if backtrack + input + lookahead all match.

        ``start_index`` points at the first *input* glyph (covered by
        the parent subtable's Coverage). Backtrack is checked against
        the preceding glyphs in reverse order; lookahead is checked
        forward of the input tail.
        """
        if start_index < 0:
            return False
        # Backtrack must not run off the start of the run.
        if start_index < len(self.backtrack_sequence):
            return False
        for i, gid in enumerate(self.backtrack_sequence):
            if glyph_ids[start_index - 1 - i] != gid:
                return False
        # Input (trailing): the first input glyph is the Coverage-matched
        # glyph at start_index, so check trailing entries.
        input_end = start_index + 1 + len(self.input_sequence)
        if input_end > len(glyph_ids):
            return False
        for i, gid in enumerate(self.input_sequence):
            if glyph_ids[start_index + 1 + i] != gid:
                return False
        # Lookahead: positions input_end .. input_end + len(lookahead)-1.
        if input_end + len(self.lookahead_sequence) > len(glyph_ids):
            return False
        return all(
            glyph_ids[input_end + i] == gid
            for i, gid in enumerate(self.lookahead_sequence)
        )


@dataclass
class ChainedSequenceRuleSet:
    """Ordered set of :class:`ChainedSequenceRule` candidates."""

    chained_sequence_rules: tuple[ChainedSequenceRule, ...] = field(
        default_factory=tuple
    )

    def get_chained_sequence_rules(self) -> tuple[ChainedSequenceRule, ...]:
        return self.chained_sequence_rules


@dataclass
class LookupTypeChainedContextualSubstitutionFormat1(LookupSubTable):
    """Type-6, Format-1 chained contextual substitution (glyph contexts).

    Mirrors the OpenType "Chained Context Substitution Format 1: Simple
    Glyph Contexts" subtable (GSUB §6.1). Extends Type 5 Format 1 with
    explicit backtrack + lookahead sequences. Most useful for Indic
    cluster shaping and Arabic linking — these are the lookups that
    drive real-world shaping engines.
    """

    coverage_table: tuple[int, ...] = field(default_factory=tuple)
    chained_sequence_rule_sets: tuple[ChainedSequenceRuleSet | None, ...] = field(
        default_factory=tuple
    )
    substitute_format: int = 1

    def __post_init__(self) -> None:
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=tuple(self.coverage_table)),
        )

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def get_chained_sequence_rule_sets(
        self,
    ) -> tuple[ChainedSequenceRuleSet | None, ...]:
        return self.chained_sequence_rule_sets

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        raise TypeError(
            "Chained contextual substitution requires a glyph sequence and "
            "access to the LookupList; use match_rule + apply via the "
            "parent extractor instead."
        )

    def match_rule(
        self, glyph_ids: list[int], start_index: int
    ) -> ChainedSequenceRule | None:
        if start_index < 0 or start_index >= len(glyph_ids):
            return None
        gid = glyph_ids[start_index]
        cov_idx = -1
        for c_i, c_gid in enumerate(self.coverage_table):
            if c_gid == gid:
                cov_idx = c_i
                break
        if cov_idx < 0 or cov_idx >= len(self.chained_sequence_rule_sets):
            return None
        rule_set = self.chained_sequence_rule_sets[cov_idx]
        if rule_set is None:
            return None
        for rule in rule_set.chained_sequence_rules:
            if rule.matches(glyph_ids, start_index):
                return rule
        return None


@dataclass
class ChainedClassRule:
    """One chained class-based context rule.

    Mirrors fontTools ``ChainSubClassRule`` (GSUB Lookup Type 6,
    Format 2). Backtrack is stored in *reverse* class order (matching
    the spec's "Array of backtracking classes" wording aligned with
    Format 1's backtrack-reverse rule).
    """

    backtrack_classes: tuple[int, ...] = field(default_factory=tuple)
    input_classes: tuple[int, ...] = field(default_factory=tuple)
    lookahead_classes: tuple[int, ...] = field(default_factory=tuple)
    substitution_lookup_records: tuple[SubstitutionLookupRecord, ...] = field(
        default_factory=tuple
    )

    def get_backtrack_classes(self) -> tuple[int, ...]:
        return self.backtrack_classes

    def get_input_classes(self) -> tuple[int, ...]:
        return self.input_classes

    def get_lookahead_classes(self) -> tuple[int, ...]:
        return self.lookahead_classes

    def get_substitution_lookup_records(
        self,
    ) -> tuple[SubstitutionLookupRecord, ...]:
        return self.substitution_lookup_records


@dataclass
class ChainedClassRuleSet:
    """Ordered set of :class:`ChainedClassRule` candidates."""

    chained_class_rules: tuple[ChainedClassRule, ...] = field(default_factory=tuple)

    def get_chained_class_rules(self) -> tuple[ChainedClassRule, ...]:
        return self.chained_class_rules


@dataclass
class LookupTypeChainedContextualSubstitutionFormat2(LookupSubTable):
    """Type-6, Format-2 chained contextual substitution (class contexts).

    Mirrors the OpenType "Chained Context Substitution Format 2:
    Class-based Glyph Contexts" subtable (GSUB §6.2). Holds three class
    definitions: one each for backtrack, input, and lookahead. The
    parent subtable's Coverage selects the eligible first input glyph;
    the input-class-definition then picks which :class:`ChainedClassRuleSet`
    to consult.
    """

    coverage_table: tuple[int, ...] = field(default_factory=tuple)
    backtrack_class_definition: ClassDefinitionTable = field(
        default_factory=ClassDefinitionTable
    )
    input_class_definition: ClassDefinitionTable = field(
        default_factory=ClassDefinitionTable
    )
    lookahead_class_definition: ClassDefinitionTable = field(
        default_factory=ClassDefinitionTable
    )
    chained_class_rule_sets: tuple[ChainedClassRuleSet | None, ...] = field(
        default_factory=tuple
    )
    substitute_format: int = 2

    def __post_init__(self) -> None:
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=tuple(self.coverage_table)),
        )

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def get_backtrack_class_definition(self) -> ClassDefinitionTable:
        return self.backtrack_class_definition

    def get_input_class_definition(self) -> ClassDefinitionTable:
        return self.input_class_definition

    def get_lookahead_class_definition(self) -> ClassDefinitionTable:
        return self.lookahead_class_definition

    def get_chained_class_rule_sets(
        self,
    ) -> tuple[ChainedClassRuleSet | None, ...]:
        return self.chained_class_rule_sets

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        raise TypeError(
            "Chained contextual substitution requires a glyph sequence and "
            "access to the LookupList; use match_rule + apply via the "
            "parent extractor instead."
        )

    def match_rule(
        self, glyph_ids: list[int], start_index: int
    ) -> ChainedClassRule | None:
        if start_index < 0 or start_index >= len(glyph_ids):
            return None
        gid = glyph_ids[start_index]
        if gid not in self.coverage_table:
            return None
        first_class = self.input_class_definition.get_class(gid)
        if first_class < 0 or first_class >= len(self.chained_class_rule_sets):
            return None
        rule_set = self.chained_class_rule_sets[first_class]
        if rule_set is None:
            return None
        for rule in rule_set.chained_class_rules:
            # Backtrack (reverse).
            if start_index < len(rule.backtrack_classes):
                continue
            backtrack_ok = all(
                self.backtrack_class_definition.get_class(
                    glyph_ids[start_index - 1 - i]
                )
                == cls
                for i, cls in enumerate(rule.backtrack_classes)
            )
            if not backtrack_ok:
                continue
            # Input (trailing).
            input_end = start_index + 1 + len(rule.input_classes)
            if input_end > len(glyph_ids):
                continue
            input_ok = all(
                self.input_class_definition.get_class(
                    glyph_ids[start_index + 1 + i]
                )
                == cls
                for i, cls in enumerate(rule.input_classes)
            )
            if not input_ok:
                continue
            # Lookahead.
            if input_end + len(rule.lookahead_classes) > len(glyph_ids):
                continue
            lookahead_ok = all(
                self.lookahead_class_definition.get_class(
                    glyph_ids[input_end + i]
                )
                == cls
                for i, cls in enumerate(rule.lookahead_classes)
            )
            if not lookahead_ok:
                continue
            return rule
        return None


@dataclass
class LookupTypeChainedContextualSubstitutionFormat3(LookupSubTable):
    """Type-6, Format-3 chained contextual substitution (per-position Coverage).

    Mirrors the OpenType "Chained Context Substitution Format 3:
    Coverage-based Glyph Contexts" subtable (GSUB §6.3). Every position
    in backtrack / input / lookahead has its own Coverage table.
    Backtrack Coverages are stored in *reverse* order (so
    ``backtrack_coverages[0]`` is the Coverage that must match the
    glyph immediately preceding the first input glyph).
    """

    backtrack_coverages: tuple[tuple[int, ...], ...] = field(default_factory=tuple)
    input_coverages: tuple[tuple[int, ...], ...] = field(default_factory=tuple)
    lookahead_coverages: tuple[tuple[int, ...], ...] = field(default_factory=tuple)
    substitution_lookup_records: tuple[SubstitutionLookupRecord, ...] = field(
        default_factory=tuple
    )
    substitute_format: int = 3

    def __post_init__(self) -> None:
        first_coverage = (
            tuple(self.input_coverages[0]) if self.input_coverages else ()
        )
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=first_coverage),
        )

    def get_backtrack_coverages(self) -> tuple[tuple[int, ...], ...]:
        return self.backtrack_coverages

    def get_input_coverages(self) -> tuple[tuple[int, ...], ...]:
        return self.input_coverages

    def get_lookahead_coverages(self) -> tuple[tuple[int, ...], ...]:
        return self.lookahead_coverages

    def get_substitution_lookup_records(
        self,
    ) -> tuple[SubstitutionLookupRecord, ...]:
        return self.substitution_lookup_records

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.input_coverages[0] if self.input_coverages else ()

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        raise TypeError(
            "Chained contextual substitution requires a glyph sequence and "
            "access to the LookupList; use matches + apply via the parent "
            "extractor instead."
        )

    def matches(self, glyph_ids: list[int], start_index: int) -> bool:
        """Return ``True`` if every backtrack / input / lookahead Coverage
        matches at the right offset relative to ``start_index``."""
        if start_index < 0:
            return False
        # Backtrack: positions start_index-1, start_index-2, ...
        if start_index < len(self.backtrack_coverages):
            return False
        for i, cov in enumerate(self.backtrack_coverages):
            if glyph_ids[start_index - 1 - i] not in cov:
                return False
        # Input: positions start_index, start_index+1, ...
        if start_index + len(self.input_coverages) > len(glyph_ids):
            return False
        for k, cov in enumerate(self.input_coverages):
            if glyph_ids[start_index + k] not in cov:
                return False
        # Lookahead.
        input_end = start_index + len(self.input_coverages)
        if input_end + len(self.lookahead_coverages) > len(glyph_ids):
            return False
        for i, cov in enumerate(self.lookahead_coverages):
            if glyph_ids[input_end + i] not in cov:
                return False
        return True


@dataclass
class LookupTypeExtensionSubstitutionFormat1(LookupSubTable):
    """Type-7, Format-1 extension substitution (offset indirection).

    Mirrors the OpenType ``ExtensionSubstFormat1`` subtable. The whole
    purpose of a Type-7 subtable is to break the 16-bit subtable-offset
    ceiling: it carries a 32-bit ``extension_offset`` to the real
    subtable, plus the inner ``extension_lookup_type`` (which must be
    one of 1..6 — a Type-7 wrapping another Type-7 is forbidden by the
    spec to prevent infinite recursion).

    Upstream PDFBox 3.0 unwraps Type-7 transparently during parsing
    (``GlyphSubstitutionTable.readLookupTable`` promotes the inner
    ``extensionLookupType`` to the outer ``lookupType``), so the
    extension subtable never reaches :class:`GlyphSubstitutionDataExtractor`
    in the parsed graph. This class is provided for callers that want
    to *materialise* an extension subtable directly (e.g. tooling that
    inspects raw GSUB structure or roundtrips an unmodified subset);
    :meth:`do_substitution` dispatches to the wrapped inner subtable.
    """

    extension_lookup_type: int = 0
    extension_offset: int = 0
    inner_subtable: LookupSubTable | None = None
    substitute_format: int = 1

    def __post_init__(self) -> None:
        # Spec: ExtensionLookupType must not equal 7 itself (no
        # extension-wrapping-extension). Mirror upstream's defensive
        # log + still hold the wrapped reference so the caller can
        # decide how to recover.
        if self.extension_lookup_type == 7:
            _LOG.error(
                "ExtensionLookupType 7 wraps itself at offset %d "
                "— forbidden by the OpenType spec",
                self.extension_offset,
            )
        # Coverage lives on the *wrapped* subtable; the extension
        # subtable itself doesn't carry a Coverage. Surface the inner
        # subtable's coverage through the base attribute so callers
        # walking ``get_coverage_object`` still see the right glyph set.
        coverage = (
            self.inner_subtable.get_coverage_object()
            if self.inner_subtable is not None
            else CoverageTable()
        )
        LookupSubTable.__init__(self, self.substitute_format, coverage)

    def get_extension_lookup_type(self) -> int:
        return self.extension_lookup_type

    def get_extension_offset(self) -> int:
        return self.extension_offset

    def get_inner_subtable(self) -> LookupSubTable | None:
        return self.inner_subtable

    def get_coverage_table(self) -> CoverageTable:
        """Return the wrapped subtable's :class:`CoverageTable`.

        Mirrors upstream's transparent unwrap: callers querying
        Coverage on a Type-7 subtable see whatever the inner subtable
        exposes. Returns an empty :class:`CoverageTable` when the
        inner subtable is unset (malformed font).
        """
        if self.inner_subtable is None:
            return CoverageTable()
        return self.inner_subtable.get_coverage_object()

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        """Delegate to the wrapped inner subtable.

        Returns ``original_glyph_id`` unchanged when the inner subtable
        is unset or doesn't implement the single-glyph signature (e.g.
        ligature or multiple-substitution inner subtables which raise
        :class:`TypeError` from their own ``do_substitution``).
        """
        if self.inner_subtable is None:
            return original_glyph_id
        try:
            return self.inner_subtable.do_substitution(
                original_glyph_id, coverage_index
            )
        except TypeError:
            # Inner subtable doesn't support the single-glyph path
            # (e.g. Type 2 / 3 / 4). Mirror the type-1/3 passthrough
            # contract so a generic walk doesn't crash.
            return original_glyph_id

    def to_string(self) -> str:
        """Mirror upstream ``LookupTypeExtensionSubstitutionFormat1.toString()``.

        Format:
        ``LookupTypeExtensionSubstitutionFormat1[substFormat=<F>,extensionLookupType=<T>,extensionOffset=<O>]``.
        """
        return (
            "LookupTypeExtensionSubstitutionFormat1["
            f"substFormat={self.substitute_format},"
            f"extensionLookupType={self.extension_lookup_type},"
            f"extensionOffset={self.extension_offset}]"
        )

    def __str__(self) -> str:
        return self.to_string()


@dataclass
class LookupTypeReverseChainedContextualSubstitutionFormat1(LookupSubTable):
    """Type-8, Format-1 reverse chained contextual single substitution.

    Mirrors the OpenType ``ReverseChainSingleSubstFormat1`` subtable.
    Unlike all other GSUB lookup types, Type 8 is applied in *reverse*
    glyph order (right-to-left within the glyph run). The shape is:

    * A Coverage table identifying which glyphs can match the central
      input glyph.
    * A backtrack-Coverage sequence (Coverage tables that must match
      the glyphs *preceding* the input in the run, in spec order:
      index 0 is the glyph immediately before the input).
    * A lookahead-Coverage sequence (Coverage tables that must match
      the glyphs *following* the input, in spec order: index 0 is the
      glyph immediately after the input).
    * A flat ``substitute_glyph_ids`` array parallel to the main
      Coverage: when the chain matches, the input glyph is replaced
      by the GID at the matching Coverage index.

    Used almost exclusively in Arabic + Hebrew shaping for terminal /
    initial cursive forms (the "final form" / "isolated form" pickup
    is a reverse-context lookup because the *next* glyph determines
    which form the *current* glyph should take).
    """

    coverage_table: tuple[int, ...] = field(default_factory=tuple)
    backtrack_coverage: tuple[tuple[int, ...], ...] = field(default_factory=tuple)
    lookahead_coverage: tuple[tuple[int, ...], ...] = field(default_factory=tuple)
    substitute_glyph_ids: tuple[int, ...] = field(default_factory=tuple)
    substitute_format: int = 1

    def __post_init__(self) -> None:
        LookupSubTable.__init__(
            self,
            self.substitute_format,
            CoverageTable(glyph_array=tuple(self.coverage_table)),
        )

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def get_backtrack_coverage(self) -> tuple[tuple[int, ...], ...]:
        return self.backtrack_coverage

    def get_lookahead_coverage(self) -> tuple[tuple[int, ...], ...]:
        return self.lookahead_coverage

    def get_substitute_glyph_ids(self) -> tuple[int, ...]:
        return self.substitute_glyph_ids

    def get_substitute_glyph_i_ds(self) -> tuple[int, ...]:
        """Snake-case mechanical translation of upstream ``getSubstituteGlyphIDs``.

        Mirrors the same ``IDs`` acronym split rule applied throughout
        the GSUB module.
        """
        return self.substitute_glyph_ids

    def do_substitution(self, original_glyph_id: int, coverage_index: int) -> int:
        """Apply the substitution *without* a context check.

        Mirrors the single-glyph contract on the base: when called
        with a valid coverage index, return the substitute GID. The
        chained context check requires the full glyph run and the
        position; use :meth:`do_substitution_at` for context-aware
        shaping.
        """
        if coverage_index < 0:
            return original_glyph_id
        if coverage_index >= len(self.substitute_glyph_ids):
            return original_glyph_id
        return int(self.substitute_glyph_ids[coverage_index])

    def do_substitution_at(
        self,
        glyph_ids: list[int],
        position: int,
    ) -> int:
        """Return the substituted GID for ``glyph_ids[position]`` or the
        original GID if the context doesn't match.

        Walks the OpenType §5.3.6 algorithm: with the input glyph at
        ``position``, check that:

        1. ``glyph_ids[position]`` appears in the main Coverage.
        2. The previous ``len(backtrack_coverage)`` glyphs each appear
           in the corresponding ``backtrack_coverage[i]`` (index 0 is
           the glyph immediately preceding the input — i.e. the
           algorithm walks backward from the input position).
        3. The following ``len(lookahead_coverage)`` glyphs each
           appear in the corresponding ``lookahead_coverage[i]``
           (index 0 is the glyph immediately following the input).

        When the chain matches end-to-end, the substitute GID at the
        same Coverage index as the input is returned. Otherwise
        ``glyph_ids[position]`` is returned unchanged.
        """
        if not glyph_ids:
            return -1
        if position < 0 or position >= len(glyph_ids):
            return glyph_ids[0] if position == 0 else -1
        input_gid = glyph_ids[position]
        # Step 1 — main coverage.
        coverage_index = -1
        for c_i, c_gid in enumerate(self.coverage_table):
            if c_gid == input_gid:
                coverage_index = c_i
                break
        if coverage_index < 0:
            return input_gid
        # Step 2 — backtrack (glyphs preceding the input).
        if position < len(self.backtrack_coverage):
            return input_gid
        for i, cov in enumerate(self.backtrack_coverage):
            preceding_gid = glyph_ids[position - 1 - i]
            if preceding_gid not in cov:
                return input_gid
        # Step 3 — lookahead (glyphs following the input).
        if position + len(self.lookahead_coverage) >= len(glyph_ids):
            return input_gid
        for i, cov in enumerate(self.lookahead_coverage):
            following_gid = glyph_ids[position + 1 + i]
            if following_gid not in cov:
                return input_gid
        # Match — return the substitute GID at this coverage index.
        if coverage_index >= len(self.substitute_glyph_ids):
            return input_gid
        return int(self.substitute_glyph_ids[coverage_index])

    def apply_to_run(self, glyph_ids: list[int]) -> list[int]:
        """Apply the reverse-chained substitution across a glyph run.

        Walks ``glyph_ids`` *right to left* per the spec (this matters
        when the substitute GID could itself satisfy a context match
        on an earlier position — applying left-to-right would cascade
        through the just-substituted glyphs, which is wrong). Returns
        a new list; the input is not mutated.
        """
        result = list(glyph_ids)
        for position in range(len(result) - 1, -1, -1):
            new_gid = self.do_substitution_at(result, position)
            if new_gid >= 0 and new_gid != result[position]:
                result[position] = new_gid
        return result

    def to_string(self) -> str:
        """Mirror upstream ``LookupTypeReverseChainedContextualSubstitutionFormat1.toString()``.

        Format:
        ``LookupTypeReverseChainedContextualSubstitutionFormat1[substFormat=<F>,backtrackGlyphCount=<B>,lookaheadGlyphCount=<L>,glyphCount=<N>]``.
        """
        return (
            "LookupTypeReverseChainedContextualSubstitutionFormat1["
            f"substFormat={self.substitute_format},"
            f"backtrackGlyphCount={len(self.backtrack_coverage)},"
            f"lookaheadGlyphCount={len(self.lookahead_coverage)},"
            f"glyphCount={len(self.substitute_glyph_ids)}]"
        )

    def __str__(self) -> str:
        return self.to_string()


__all__ = [
    "AlternateSetTable",
    "ChainedClassRule",
    "ChainedClassRuleSet",
    "ChainedSequenceRule",
    "ChainedSequenceRuleSet",
    "ClassDefinitionTable",
    "ClassRule",
    "ClassRuleSet",
    "CoverageTable",
    "LigatureSetTable",
    "LigatureTable",
    "LookupSubTable",
    "LookupTypeAlternateSubstitutionFormat1",
    "LookupTypeChainedContextualSubstitutionFormat1",
    "LookupTypeChainedContextualSubstitutionFormat2",
    "LookupTypeChainedContextualSubstitutionFormat3",
    "LookupTypeContextualSubstitutionFormat1",
    "LookupTypeContextualSubstitutionFormat2",
    "LookupTypeContextualSubstitutionFormat3",
    "LookupTypeExtensionSubstitutionFormat1",
    "LookupTypeLigatureSubstitutionSubstFormat1",
    "LookupTypeMultipleSubstitutionFormat1",
    "LookupTypeReverseChainedContextualSubstitutionFormat1",
    "LookupTypeSingleSubstFormat1",
    "LookupTypeSingleSubstFormat2",
    "SequenceRule",
    "SequenceRuleSet",
    "SequenceTable",
    "SubstitutionLookupRecord",
]
