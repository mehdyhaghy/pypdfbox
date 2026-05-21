"""Wave 1380 tests for the ``TTFSubsetter.no_subset_tables`` integration.

The PD font subclasses embed a TTF by routing through
:class:`pypdfbox.pdmodel.font.true_type_embedder.TrueTypeEmbedder.subset`.
That code path now honours a ``_no_subset_tables`` policy attribute
which is wired into fontTools' ``Options.no_subset_tables`` (mirrors
upstream PDFBox's ``TTFSubsetter.setNoSubsetTables(Set<String>)``).

Tests:

* The fontbox :class:`TTFSubsetter` exposes a
  :meth:`set_no_subset_tables` / :meth:`get_no_subset_tables` pair.
* The PD-font embedder base class (:class:`TrueTypeEmbedder`) defaults
  to the conservative ``_DEFAULT_NO_SUBSET_TABLES`` list.
* :class:`PDCIDFontType2Embedder` widens that list to include the
  PostScript hinting tables (cvt/fpgm/prep) and the ``cmap``, matching
  the CJK-embedding policy from upstream PDFBox.
* :class:`PDTrueTypeFontEmbedder` inherits the conservative default
  (no subsetting happens at this layer — subsetting routes through
  PDType0Font — but the policy attribute is still exposed for
  consistency).
* The policy is mutable per-instance via :meth:`set_no_subset_tables`.
* The policy survives subsetter ``populate`` + flush round-trips
  without raising, and the resulting bytes are a valid font that
  fontTools can re-parse.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import pytest

from pypdfbox.fontbox.ttf.ttf_parser import TTFParser
from pypdfbox.fontbox.ttf.ttf_subsetter import TTFSubsetter
from pypdfbox.pdmodel.font.true_type_embedder import (
    _CID_NO_SUBSET_TABLES,
    _DEFAULT_NO_SUBSET_TABLES,
)

_FIXTURE_TTF = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


# ---------- fontbox TTFSubsetter API ------------------------------------


@pytest.fixture(scope="module")
def liberation_sans() -> Any:
    font = TTFParser().parse(os.fspath(_FIXTURE_TTF))
    yield font
    font.close()


def test_subsetter_default_no_subset_tables_is_empty(
    liberation_sans: Any,
) -> None:
    subsetter = TTFSubsetter(liberation_sans)
    assert subsetter.get_no_subset_tables() == ()


def test_subsetter_set_no_subset_tables_stores_tuple(
    liberation_sans: Any,
) -> None:
    subsetter = TTFSubsetter(liberation_sans)
    subsetter.set_no_subset_tables(["head", "hhea", "name", "OS/2"])
    assert subsetter.get_no_subset_tables() == ("head", "hhea", "name", "OS/2")


def test_subsetter_set_no_subset_tables_accepts_tuple(
    liberation_sans: Any,
) -> None:
    subsetter = TTFSubsetter(liberation_sans)
    subsetter.set_no_subset_tables(("head", "hhea"))
    assert subsetter.get_no_subset_tables() == ("head", "hhea")


def test_subsetter_set_no_subset_tables_empty_clears_policy(
    liberation_sans: Any,
) -> None:
    subsetter = TTFSubsetter(liberation_sans)
    subsetter.set_no_subset_tables(("head",))
    subsetter.set_no_subset_tables(())
    assert subsetter.get_no_subset_tables() == ()


def test_subsetter_with_no_subset_tables_produces_valid_ttf(
    liberation_sans: Any,
) -> None:
    """When a no-subset-tables policy is set, the resulting font must
    still be a valid TTF that fontTools can re-parse without error.
    Sanity check that we haven't broken the subsetting pipeline."""
    subsetter = TTFSubsetter(liberation_sans)
    subsetter.add(ord("A"))
    subsetter.add(ord("B"))
    subsetter.add(ord("C"))
    subsetter.set_no_subset_tables(_DEFAULT_NO_SUBSET_TABLES)
    out = io.BytesIO()
    subsetter.write_to_stream(out)
    out.seek(0)
    # Re-parse the output via fontTools to confirm validity.
    import fontTools.ttLib as ttLib  # noqa: PLC0415

    reparsed = ttLib.TTFont(out)
    # The descriptor metadata tables must still be present after
    # subsetting (they are explicitly in no_subset_tables).
    for tag in ("head", "hhea", "maxp", "name", "OS/2", "post"):
        assert tag in reparsed, f"expected {tag!r} to be preserved"


def test_subsetter_no_subset_tables_survives_single_glyph_subset(
    liberation_sans: Any,
) -> None:
    """A no-subset-tables policy must not break a single-glyph subset
    flush. The flush should succeed and the named tables should
    survive into the output."""
    subsetter = TTFSubsetter(liberation_sans)
    subsetter.add(ord("A"))
    subsetter.set_no_subset_tables(("head", "hhea", "name", "OS/2", "post"))
    out = io.BytesIO()
    subsetter.write_to_stream(out)
    assert out.tell() > 0


# ---------- PD font embedder defaults ------------------------------------


def test_default_no_subset_tables_constant_shape() -> None:
    """The default policy must include the descriptor metadata tables
    every PDF reader consults (head, hhea, maxp, name, OS/2, post)."""
    assert "head" in _DEFAULT_NO_SUBSET_TABLES
    assert "hhea" in _DEFAULT_NO_SUBSET_TABLES
    assert "maxp" in _DEFAULT_NO_SUBSET_TABLES
    assert "name" in _DEFAULT_NO_SUBSET_TABLES
    assert "OS/2" in _DEFAULT_NO_SUBSET_TABLES
    assert "post" in _DEFAULT_NO_SUBSET_TABLES


def test_cid_no_subset_tables_widens_default_with_hinting() -> None:
    """The CID policy must be a strict superset of the default and
    must include the PostScript hinting bytecode tables that CJK
    fonts rely on for visible-quality rasterisation."""
    for tag in _DEFAULT_NO_SUBSET_TABLES:
        assert tag in _CID_NO_SUBSET_TABLES, (
            f"CID policy must include all default entries; missing {tag!r}"
        )
    # CID-specific additions.
    assert "cvt " in _CID_NO_SUBSET_TABLES  # control value table
    assert "fpgm" in _CID_NO_SUBSET_TABLES  # font program (TT bytecode)
    assert "prep" in _CID_NO_SUBSET_TABLES  # CVT program
    assert "cmap" in _CID_NO_SUBSET_TABLES  # CID embeddings retain cmap


def test_cid_no_subset_tables_does_not_include_glyf_or_loca() -> None:
    """Tables whose bytes depend on the new glyph-index space must NOT
    be in the no-subset list — including them would leave inter-table
    references stale after the subset pass."""
    forbidden = ("glyf", "loca", "hmtx", "vmtx", "CFF ")
    for tag in forbidden:
        assert tag not in _CID_NO_SUBSET_TABLES, (
            f"{tag!r} must NOT be in CID no_subset_tables — its bytes "
            f"depend on the post-subset glyph index space"
        )
        assert tag not in _DEFAULT_NO_SUBSET_TABLES, (
            f"{tag!r} must NOT be in default no_subset_tables — its "
            f"bytes depend on the post-subset glyph index space"
        )


# ---------- PD font embedder integration ---------------------------------


def _make_embedder(embed_subset: bool) -> Any:
    """Build a minimal PDTrueTypeFontEmbedder for inspection. We avoid
    real document I/O — the embedder constructor only needs a document
    + a COSDictionary + a fontTools TTFont + an Encoding."""
    import fontTools.ttLib as ttLib  # noqa: PLC0415

    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import (
        WinAnsiEncoding,
    )
    from pypdfbox.pdmodel.font.pd_true_type_font_embedder import (
        PDTrueTypeFontEmbedder,
    )
    from pypdfbox.pdmodel.pd_document import PDDocument

    document = PDDocument()
    tt = ttLib.TTFont(os.fspath(_FIXTURE_TTF))
    dict_ = COSDictionary()
    # PDTrueTypeFontEmbedder is hard-coded to embed_subset=False.
    del embed_subset  # accepted for future flexibility
    return PDTrueTypeFontEmbedder(document, dict_, tt, WinAnsiEncoding())


def _make_cid_embedder() -> Any:
    """Build a minimal :class:`PDCIDFontType2Embedder` for inspection."""
    import fontTools.ttLib as ttLib  # noqa: PLC0415

    from pypdfbox.cos import COSDictionary
    from pypdfbox.pdmodel.font.pd_cid_font_type2_embedder import (
        PDCIDFontType2Embedder,
    )
    from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
    from pypdfbox.pdmodel.pd_document import PDDocument

    document = PDDocument()
    tt = ttLib.TTFont(os.fspath(_FIXTURE_TTF))
    dict_ = COSDictionary()
    parent = PDType0Font.__new__(PDType0Font)  # bypass __init__ for unit test
    return PDCIDFontType2Embedder(
        document,
        dict_,
        tt,
        embed_subset=True,
        parent=parent,
        vertical=False,
    )


def test_true_type_font_embedder_has_default_no_subset_policy() -> None:
    """A :class:`PDTrueTypeFontEmbedder` inherits the conservative
    default no-subset list (descriptor metadata)."""
    embedder = _make_embedder(embed_subset=False)
    assert embedder.get_no_subset_tables() == _DEFAULT_NO_SUBSET_TABLES


def test_cid_font_type2_embedder_widens_to_cid_policy() -> None:
    """A :class:`PDCIDFontType2Embedder` widens the default to the CID
    policy in its constructor — verify the policy is set when the
    instance is built."""
    embedder = _make_cid_embedder()
    assert embedder.get_no_subset_tables() == _CID_NO_SUBSET_TABLES


def test_embedder_set_no_subset_tables_overrides_default() -> None:
    embedder = _make_embedder(embed_subset=False)
    embedder.set_no_subset_tables(("head", "name"))
    assert embedder.get_no_subset_tables() == ("head", "name")


def test_embedder_set_no_subset_tables_accepts_list_and_tuple() -> None:
    embedder = _make_embedder(embed_subset=False)
    embedder.set_no_subset_tables(["head", "name"])
    assert embedder.get_no_subset_tables() == ("head", "name")
    embedder.set_no_subset_tables(("hhea", "post"))
    assert embedder.get_no_subset_tables() == ("hhea", "post")


def test_embedder_set_no_subset_tables_empty_clears_policy() -> None:
    embedder = _make_embedder(embed_subset=False)
    embedder.set_no_subset_tables(())
    assert embedder.get_no_subset_tables() == ()


# ---------- PD-font subclass policy validation ---------------------------


@pytest.mark.parametrize(
    "expected_tag",
    ["head", "hhea", "maxp", "name", "OS/2", "post"],
    ids=["head", "hhea", "maxp", "name", "os_2", "post"],
)
def test_default_policy_includes_descriptor_metadata(expected_tag: str) -> None:
    assert expected_tag in _DEFAULT_NO_SUBSET_TABLES


@pytest.mark.parametrize(
    "expected_tag",
    ["head", "hhea", "maxp", "name", "OS/2", "post", "cvt ", "fpgm", "prep", "cmap"],
    ids=[
        "head",
        "hhea",
        "maxp",
        "name",
        "os_2",
        "post",
        "cvt",
        "fpgm",
        "prep",
        "cmap",
    ],
)
def test_cid_policy_includes_required_tag(expected_tag: str) -> None:
    assert expected_tag in _CID_NO_SUBSET_TABLES
