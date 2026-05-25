"""Wave 1396 — GsubWorkerForTamil upstream-typo parity alias.

PDFBox upstream spells the private helper ``getbeforeRephGlyphIds`` with
a lowercase ``b`` immediately after ``get`` — a long-standing naming
quirk in the Java source. pypdfbox's port uses the semantically-correct
``get_before_reph_glyph_ids`` as the canonical entry point; wave 1396
adds ``getbefore_reph_glyph_ids`` as a parity alias so the parity matcher
(and ported callers that mirror the upstream name verbatim) can resolve
it. The two are byte-identical in behaviour.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub.gsub_worker_for_tamil import GsubWorkerForTamil


class _StubCmap:
    """Minimal CmapLookup stub: maps each codepoint to itself + 1000."""

    def get_glyph_id(self, codepoint: int) -> int:
        return codepoint + 1000


class _StubGsubData:
    """Empty GSUB data — no substitutions performed."""

    def get_glyph_substitution_map(self) -> dict[object, object]:
        return {}


def _make_worker() -> GsubWorkerForTamil:
    return GsubWorkerForTamil(_StubCmap(), _StubGsubData())


def test_wave1396_typo_alias_returns_same_value_as_canonical_form() -> None:
    """The parity alias produces an identical list to the canonical form."""
    worker = _make_worker()
    canonical = worker.get_before_reph_glyph_ids()
    alias = worker.getbefore_reph_glyph_ids()
    assert canonical == alias
    # And we actually got something back — the stub cmap maps every
    # _BEFORE_REPH_CHARS character to a glyph id.
    assert len(alias) > 0


def test_wave1396_typo_alias_is_present_on_class() -> None:
    """The alias is a real method on the class, not a leftover attribute."""
    assert callable(getattr(GsubWorkerForTamil, "getbefore_reph_glyph_ids", None))
