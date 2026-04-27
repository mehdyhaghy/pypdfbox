from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class LookupSubTable(ABC):
    """Abstract base for OpenType GSUB lookup subtables.

    Mirrors ``org.apache.fontbox.ttf.gsub.LookupSubTable``. Each concrete
    subclass corresponds to one of the GSUB lookup *types* and one of the
    *formats* within that type (e.g. type-1 single substitution has
    formats 1 and 2). The single common operation is :meth:`do_substitution`,
    which takes an input GID (or GID sequence, for ligature lookups) and
    returns the substituted GID, or the original GID if the subtable does
    not cover the input.

    ``substitute_format`` records the OpenType subtable format (1 or 2 for
    type-1 single substitution; 1 for type-4 ligature substitution).
    Upstream stores it on the abstract base too so callers can branch
    without ``isinstance`` checks.
    """

    def __init__(self, substitute_format: int = 0) -> None:
        self.substitute_format: int = substitute_format

    def get_substitute_format(self) -> int:
        return self.substitute_format

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

    Mirrors ``org.apache.fontbox.ttf.gsub.LookupTypeSingleSubstFormat1``.
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
        LookupSubTable.__init__(self, self.substitute_format)

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

    Mirrors ``org.apache.fontbox.ttf.gsub.LookupTypeSingleSubstFormat2``.
    Each covered GID is replaced by the GID at the same index in
    ``substitute_glyph_ids``. The two arrays MUST have the same length;
    upstream's parser guarantees this.
    """

    substitute_glyph_ids: tuple[int, ...] = field(default_factory=tuple)
    coverage_table: tuple[int, ...] = field(default_factory=tuple)
    substitute_format: int = 2

    def __post_init__(self) -> None:
        LookupSubTable.__init__(self, self.substitute_format)

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
class LookupTypeLigatureSubstitutionSubstFormat1(LookupSubTable):
    """Type-4, Format-1 ligature substitution.

    Mirrors
    ``org.apache.fontbox.ttf.gsub.LookupTypeLigatureSubstitutionSubstFormat1``.
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
    ligature_set_tables: tuple["LigatureSetTable", ...] = field(default_factory=tuple)
    substitute_format: int = 1

    def __post_init__(self) -> None:
        LookupSubTable.__init__(self, self.substitute_format)

    def get_coverage_table(self) -> tuple[int, ...]:
        return self.coverage_table

    def get_ligature_set_tables(self) -> tuple["LigatureSetTable", ...]:
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
                end = i + 1 + len(comps)
                if end > n:
                    continue
                if all(glyph_ids[i + 1 + k] == comps[k] for k in range(len(comps))):
                    if len(comps) >= best_len:
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

    Mirrors ``org.apache.fontbox.ttf.gsub.LigatureTable``. ``ligature_glyph``
    is the GID emitted on a successful match; ``component_glyph_ids`` are
    the *trailing* component GIDs (the first component is the one indexed
    by Coverage on the parent subtable, so it is implicit and not stored
    here — matching the OpenType spec).
    """

    ligature_glyph: int = 0
    component_glyph_ids: tuple[int, ...] = field(default_factory=tuple)

    def get_ligature_glyph(self) -> int:
        return self.ligature_glyph

    def get_component_glyph_ids(self) -> tuple[int, ...]:
        return self.component_glyph_ids


@dataclass
class LigatureSetTable:
    """Bundle of ligature candidates that share a first component.

    Mirrors ``org.apache.fontbox.ttf.gsub.LigatureSetTable``. Each
    LigatureSet sits at one Coverage index; its ``ligature_tables`` are
    ordered by descending priority per the spec.
    """

    ligature_tables: tuple[LigatureTable, ...] = field(default_factory=tuple)

    def get_ligature_tables(self) -> tuple[LigatureTable, ...]:
        return self.ligature_tables


__all__ = [
    "LigatureSetTable",
    "LigatureTable",
    "LookupSubTable",
    "LookupTypeLigatureSubstitutionSubstFormat1",
    "LookupTypeSingleSubstFormat1",
    "LookupTypeSingleSubstFormat2",
]
