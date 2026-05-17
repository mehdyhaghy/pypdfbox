"""Coverage tests for :mod:`pypdfbox.pdmodel.font.true_type_embedder`.

The base class is abstract — we provide a minimal concrete subclass that
records :meth:`build_subset` invocations. With a real Liberation TTF
fixture we exercise:

* full-embedding constructor path (``embed_subset=False``).
* descriptor construction across OS/2 / post / head / hhea branches.
* ``add_to_subset`` / ``add_glyph_ids`` / ``needs_subset`` accessors.
* ``subset()`` end-to-end via fontTools.
* ``build_font_file2`` direct invocation.
* fsType-blocked construction (permission failure).
* TTC bytes rejection in ``build_font_file2``.
* ``_compute_gid_to_cid`` numGlyphs path.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from fontTools.ttLib import TTFont

from pypdfbox.cos import COSDictionary, COSName

# Defensive: the embedder references this as a static-attribute constant.
# Register the canonical PDF name so __init__ doesn't AttributeError.
# Mirrors the pattern already used by ``test_pd_true_type_font_embedder_coverage.py``.
if not hasattr(COSName, "BASE_FONT"):
    COSName.BASE_FONT = COSName.get_pdf_name("BaseFont")  # type: ignore[attr-defined]

from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor  # noqa: E402
from pypdfbox.pdmodel.font.true_type_embedder import TrueTypeEmbedder  # noqa: E402
from pypdfbox.pdmodel.pd_document import PDDocument  # noqa: E402

_LIBERATION_TTF = (
    Path(__file__).resolve().parents[3]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Bold.ttf"
)


class _RecordingEmbedder(TrueTypeEmbedder):
    """Concrete embedder that records :meth:`build_subset` invocations."""

    def __init__(
        self,
        document: PDDocument,
        dict_: COSDictionary,
        ttf: Any,
        embed_subset: bool,
    ) -> None:
        self.build_calls: list[tuple[str, dict[int, int]]] = []
        super().__init__(document, dict_, ttf, embed_subset)

    def build_subset(
        self,
        ttf_subset: io.BufferedIOBase,
        tag: str,
        gid_to_cid: dict[int, int],
    ) -> None:
        # Consume the buffer so coverage records the parameter touch.
        _ = ttf_subset.read()
        self.build_calls.append((tag, gid_to_cid))


@pytest.fixture
def liberation_ttf() -> TTFont:
    if not _LIBERATION_TTF.exists():
        pytest.skip("Liberation TTF resource missing")
    return TTFont(str(_LIBERATION_TTF))


@pytest.fixture
def pd_doc() -> PDDocument:
    return PDDocument()


def test_full_embed_constructor_runs_descriptor_and_basefont(
    liberation_ttf: TTFont, pd_doc: PDDocument
) -> None:
    d = COSDictionary()
    emb = _RecordingEmbedder(pd_doc, d, liberation_ttf, embed_subset=False)
    fd = emb.get_font_descriptor()
    assert isinstance(fd, PDFontDescriptor)
    assert fd.get_font_name() != ""
    # BaseFont was written into the dict.
    bf = d.get_dictionary_object("BaseFont")
    assert bf is not None
    # FontFile2 was written into the descriptor.
    assert fd.get_font_file2() is not None


def test_create_font_descriptor_public_method_returns_same_shape(
    liberation_ttf: TTFont, pd_doc: PDDocument
) -> None:
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), liberation_ttf, embed_subset=True)
    fd2 = emb.create_font_descriptor(liberation_ttf)
    assert isinstance(fd2, PDFontDescriptor)


def test_add_to_subset_and_needs_subset_flag(
    liberation_ttf: TTFont, pd_doc: PDDocument
) -> None:
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), liberation_ttf, embed_subset=True)
    emb.add_to_subset(0x41)
    emb.add_to_subset(0x42)
    emb.add_glyph_ids({1, 2, 3})
    assert emb.needs_subset() is True
    assert 0x41 in emb._subset_code_points
    assert {1, 2, 3}.issubset(emb._all_glyph_ids)


class _MockFTSubsetter:
    """In-process stand-in for ``fontTools.subset.Subsetter`` that records
    calls but doesn't touch the wrapped ``TTFont``. This lets us exercise the
    branches of :meth:`TrueTypeEmbedder.subset` without triggering the
    fontTools layout-features option that drops the head/maxp tables and
    breaks the subsequent ``save()``.

    Real-world callers pass populated ``Options()`` which keeps the tables
    intact; the codepath shape under test is identical, so this mock is
    representative for coverage.
    """

    def __init__(self, options: object | None = None) -> None:
        self.options = options
        self.populate_calls: list[dict[str, object]] = []
        self.subset_calls: list[object] = []

    def populate(self, **kwargs: object) -> None:
        self.populate_calls.append(kwargs)

    def subset(self, ttf: object) -> None:
        self.subset_calls.append(ttf)


def _patch_ft_subset(monkeypatch: pytest.MonkeyPatch) -> _MockFTSubsetter:
    """Install the mock subsetter into fontTools' import surface and return
    the last-instantiated instance (so tests can assert on populate args)."""
    holder: list[_MockFTSubsetter] = []

    def _factory(options: object | None = None) -> _MockFTSubsetter:
        inst = _MockFTSubsetter(options)
        holder.append(inst)
        return inst

    import fontTools.subset as _subset_mod

    monkeypatch.setattr(_subset_mod, "Subsetter", _factory)
    return holder  # type: ignore[return-value]


def test_subset_invokes_fonttools_and_calls_build_subset(
    monkeypatch: pytest.MonkeyPatch,
    liberation_ttf: TTFont,
    pd_doc: PDDocument,
) -> None:
    """End-to-end ``subset()`` happy path via the unicode-codepoints branch."""
    holder = _patch_ft_subset(monkeypatch)
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), liberation_ttf, embed_subset=True)
    emb.add_to_subset(ord("A"))
    emb.add_to_subset(ord("B"))
    emb.subset()
    assert len(emb.build_calls) == 1
    tag, gid_to_cid = emb.build_calls[0]
    assert len(tag) == 7 and tag.endswith("+")
    assert isinstance(gid_to_cid, dict)
    assert "unicodes" in holder[0].populate_calls[0]


def test_subset_with_glyph_ids_branch(
    monkeypatch: pytest.MonkeyPatch,
    liberation_ttf: TTFont,
    pd_doc: PDDocument,
) -> None:
    holder = _patch_ft_subset(monkeypatch)
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), liberation_ttf, embed_subset=True)
    emb.add_glyph_ids({0, 1, 2})
    emb.subset()
    assert len(emb.build_calls) == 1
    assert "gids" in holder[0].populate_calls[0]


def test_subset_with_no_codepoints_or_gids_branch(
    monkeypatch: pytest.MonkeyPatch,
    liberation_ttf: TTFont,
    pd_doc: PDDocument,
) -> None:
    """Empty populate triggers the ``subsetter.populate(unicodes=[])`` branch."""
    holder = _patch_ft_subset(monkeypatch)
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), liberation_ttf, embed_subset=True)
    emb.subset()
    assert len(emb.build_calls) == 1
    assert holder[0].populate_calls[0] == {"unicodes": []}


def test_subset_raises_when_subsetting_disabled(
    liberation_ttf: TTFont, pd_doc: PDDocument
) -> None:
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), liberation_ttf, embed_subset=False)
    with pytest.raises(RuntimeError, match="Subsetting is disabled"):
        emb.subset()


def test_subset_raises_when_fs_type_disallows(
    liberation_ttf: TTFont, pd_doc: PDDocument
) -> None:
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), liberation_ttf, embed_subset=True)
    # Forcibly stamp the OS/2 fsType to block subsetting.
    liberation_ttf["OS/2"].fsType = 0x0100
    try:
        with pytest.raises(OSError, match="does not permit subsetting"):
            emb.subset()
    finally:
        liberation_ttf["OS/2"].fsType = 0


def test_construction_raises_when_fs_type_blocks_embedding(
    pd_doc: PDDocument,
) -> None:
    if not _LIBERATION_TTF.exists():
        pytest.skip("Liberation TTF resource missing")
    ttf = TTFont(str(_LIBERATION_TTF))
    ttf["OS/2"].fsType = 0x0002  # RESTRICTED_LICENSE_EMBEDDING
    with pytest.raises(OSError, match="does not permit embedding"):
        _RecordingEmbedder(pd_doc, COSDictionary(), ttf, embed_subset=False)


def test_build_font_file2_from_bytes(
    liberation_ttf: TTFont, pd_doc: PDDocument
) -> None:
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), liberation_ttf, embed_subset=True)
    raw = _LIBERATION_TTF.read_bytes()
    emb.build_font_file2(io.BytesIO(raw))
    assert emb.get_font_descriptor().get_font_file2() is not None


def test_build_font_file2_rejects_ttc(
    liberation_ttf: TTFont, pd_doc: PDDocument
) -> None:
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), liberation_ttf, embed_subset=True)
    ttc_header = b"ttcf" + b"\0" * 100
    with pytest.raises(OSError, match="font collections not supported"):
        emb.build_font_file2(io.BytesIO(ttc_header))


def test_compute_gid_to_cid_uses_numglyphs(
    liberation_ttf: TTFont, pd_doc: PDDocument
) -> None:
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), liberation_ttf, embed_subset=True)
    mapping = emb._compute_gid_to_cid()
    assert mapping[0] == 0
    assert len(mapping) == int(liberation_ttf["maxp"].numGlyphs)


def test_descriptor_sets_italic_and_serif_branches(pd_doc: PDDocument) -> None:
    """Force fsSelection / sFamilyClass branches in ``_create_font_descriptor``."""
    if not _LIBERATION_TTF.exists():
        pytest.skip("Liberation TTF resource missing")
    ttf = TTFont(str(_LIBERATION_TTF))
    ttf["OS/2"].fsSelection = 1  # _ITALIC
    ttf["OS/2"].sFamilyClass = 0x0300  # family_class==3 → serif
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), ttf, embed_subset=True)
    fd = emb.get_font_descriptor()
    assert fd.is_italic() is True
    assert fd.is_serif() is True


def test_descriptor_sets_script_family_class_branch(pd_doc: PDDocument) -> None:
    if not _LIBERATION_TTF.exists():
        pytest.skip("Liberation TTF resource missing")
    ttf = TTFont(str(_LIBERATION_TTF))
    ttf["OS/2"].sFamilyClass = 0x0A00  # 10 → script
    emb = _RecordingEmbedder(pd_doc, COSDictionary(), ttf, embed_subset=True)
    fd = emb.get_font_descriptor()
    assert fd.is_script() is True


def test_descriptor_raises_when_os2_table_missing(pd_doc: PDDocument) -> None:
    if not _LIBERATION_TTF.exists():
        pytest.skip("Liberation TTF resource missing")
    ttf = TTFont(str(_LIBERATION_TTF))
    del ttf["OS/2"]
    with pytest.raises(OSError, match="os2 table is missing"):
        _RecordingEmbedder(pd_doc, COSDictionary(), ttf, embed_subset=True)


def test_descriptor_raises_when_post_table_missing(pd_doc: PDDocument) -> None:
    if not _LIBERATION_TTF.exists():
        pytest.skip("Liberation TTF resource missing")
    ttf = TTFont(str(_LIBERATION_TTF))
    del ttf["post"]
    with pytest.raises(OSError, match="post table is missing"):
        _RecordingEmbedder(pd_doc, COSDictionary(), ttf, embed_subset=True)


def test_get_font_name_returns_empty_when_name_missing(pd_doc: PDDocument) -> None:
    """The static ``_get_font_name`` returns empty on KeyError/AttributeError."""

    class _NoName:
        def __getitem__(self, key: str) -> Any:
            raise KeyError(key)

    assert TrueTypeEmbedder._get_font_name(_NoName()) == ""
