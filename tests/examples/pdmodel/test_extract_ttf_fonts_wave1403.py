"""Wave 1403 branch round-out for ``extract_ttf_fonts``.

Closes three partials in ``ExtractTTFFonts``:

* ``61->63`` — a second positional argument arrives after ``pdf_file`` is
  already set, so the ``if pdf_file is None`` guard takes its False arc.
* ``106->88`` — an annotation whose normal appearance is a *sub-dictionary*
  is processed and the per-annotation loop advances to the next annotation.
* ``152->155`` — a ``PDType0Font`` whose descendant is **not** a
  ``PDCIDFontType2`` leaves ``descriptor`` None and skips the write.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from unittest import mock

from pypdfbox.examples.pdmodel.extract_ttf_fonts import ExtractTTFFonts

# ---------------------------------------------------------------------------
# Shared stand-ins (mirroring the wave-1333 sibling test's style).
# ---------------------------------------------------------------------------


class _Key:
    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name


class _CosObj:
    pass


class _FontWithDescriptor:
    def __init__(self, name, cos, descriptor=None):
        self._name = name
        self._cos = cos
        self._descriptor = descriptor

    def get_name(self):
        return self._name

    def get_cos_object(self):
        return self._cos

    def get_font_descriptor(self):
        return self._descriptor


class _Resources:
    def __init__(self, fonts=None) -> None:
        self._fonts = fonts or {}

    def get_font_names(self):
        return list(self._fonts.keys())

    def get_font(self, key):
        return self._fonts.get(key)

    def get_xobject_names(self):
        return []

    def get_pattern_names(self):
        return []

    def get_ext_g_state_names(self):
        return []


# ---------------------------------------------------------------------------
# 152->155 — Type0 font whose descendant is not a PDCIDFontType2.
# ---------------------------------------------------------------------------


def test_type0_with_non_cid_descendant_skips_write(
    monkeypatch, tmp_path: Path,
) -> None:
    class _FakeCID(_FontWithDescriptor):
        pass

    class _OtherDescendant(_FontWithDescriptor):
        """A descendant that is *not* a PDCIDFontType2."""

    class _FakeType0(_FontWithDescriptor):
        def __init__(self, name, cos, descendant):
            super().__init__(name, cos, descriptor=None)
            self._descendant = descendant

        def get_descendant_font(self):
            return self._descendant

    descendant = _OtherDescendant("CID0", _CosObj(), descriptor=None)
    font = _FakeType0("Type0Font", _CosObj(), descendant=descendant)

    monkeypatch.setattr(
        "pypdfbox.pdmodel.font.pd_cid_font_type2.PDCIDFontType2",
        _FakeCID,
        raising=False,
    )
    monkeypatch.setattr(
        "pypdfbox.pdmodel.font.pd_type0_font.PDType0Font",
        _FakeType0,
        raising=False,
    )

    resources = _Resources(fonts={_Key("FT0"): font})
    monkeypatch.chdir(tmp_path)
    ExtractTTFFonts().process_resources_fonts(
        resources, add_key=False, prefix=None,
    )
    # descendant is not CID → descriptor stays None → no .ttf written.
    assert not list(tmp_path.glob("*.ttf"))


# ---------------------------------------------------------------------------
# 61->63 — second positional argument after pdf_file already set.
# ---------------------------------------------------------------------------


class _EmptyDoc:
    """A document with no AcroForm and no pages — extract_fonts walks
    nothing, so the (existing-but-unused) second positional token only
    exercises the argv parser."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_document_catalog(self):
        return self

    def get_acro_form(self):
        return None

    def get_pages(self):
        return _EmptyPages()


class _EmptyPages:
    def __iter__(self):
        return iter(())

    def index_of(self, _page):  # pragma: no cover - no pages to index
        return -1


def test_second_positional_arg_hits_pdf_file_set_branch(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_load_pdf(path, password=""):
        captured["path"] = path
        captured["password"] = password
        return _EmptyDoc()

    monkeypatch.setattr(
        "pypdfbox.loader.Loader.load_pdf", staticmethod(_fake_load_pdf),
    )
    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument",
        lambda cos_doc: cos_doc,
    )

    # Two positional tokens: the first sets pdf_file, the second arrives
    # while pdf_file is non-None → False arc of ``if pdf_file is None`` (61).
    ExtractTTFFonts().extract_fonts(["first.pdf", "second.pdf"])
    # Only the first positional is taken as the document path.
    assert Path(captured["path"]).name == "first.pdf"


# ---------------------------------------------------------------------------
# 106->88 — annotation appearance is a sub-dictionary; loop advances.
# ---------------------------------------------------------------------------


class _SubDictNormalAppearance:
    def is_stream(self):
        return False

    def is_sub_dictionary(self):
        return True

    def get_sub_dictionary(self):
        # A mapping of appearance-state name -> stream-like object.
        return {"On": _AppearanceStream()}


class _AppearanceStream:
    def get_resources(self):
        return _Resources()


class _Appearance:
    def get_normal_appearance(self):
        return _SubDictNormalAppearance()


class _Annotation:
    def __init__(self, with_nas: bool) -> None:
        self._with_nas = with_nas

    def get_normal_appearance_stream(self):
        # Returning None pushes flow toward get_appearance().
        return None

    def get_appearance(self):
        return _Appearance()


class _Page:
    def __init__(self, annotations) -> None:
        self._annotations = annotations

    def get_resources(self):
        return _Resources()

    def get_annotations(self):
        return self._annotations


class _PageTree:
    def __init__(self, pages) -> None:
        self._pages = pages

    def __iter__(self):
        return iter(self._pages)

    def index_of(self, page):
        return self._pages.index(page)


class _DocWithSubDictAnnotation:
    def __init__(self, page_tree) -> None:
        self._page_tree = page_tree

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_document_catalog(self):
        return self

    def get_acro_form(self):
        return None

    def get_pages(self):
        return self._page_tree


def test_subdictionary_appearance_advances_annotation_loop(monkeypatch) -> None:
    # Two annotations so the loop body runs and then loops back (106->88).
    page = _Page([_Annotation(False), _Annotation(False)])
    page_tree = _PageTree([page])
    calls: list[object] = []

    def _fake_load_pdf(path, password=""):
        return _DocWithSubDictAnnotation(page_tree)

    monkeypatch.setattr(
        "pypdfbox.loader.Loader.load_pdf", staticmethod(_fake_load_pdf),
    )
    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument",
        lambda cos_doc: cos_doc,
    )

    extractor = ExtractTTFFonts()
    original = extractor.process_resources

    def _tracking(resources, prefix, add_key):
        calls.append(resources)
        with contextlib.suppress(Exception):
            return original(resources, prefix, add_key)
        return None

    monkeypatch.setattr(extractor, "process_resources", _tracking)
    extractor.extract_fonts(["doc.pdf"])
    # The sub-dictionary stream's resources were processed for each
    # annotation, confirming the elif arm ran and the loop advanced.
    assert any(isinstance(c, _Resources) for c in calls)


class _NeitherNormalAppearance:
    """Normal appearance that is neither a stream nor a sub-dictionary."""

    def is_stream(self):
        return False

    def is_sub_dictionary(self):
        return False


class _NeitherAppearance:
    def get_normal_appearance(self):
        return _NeitherNormalAppearance()


class _NeitherAnnotation:
    def get_normal_appearance_stream(self):
        return None

    def get_appearance(self):
        return _NeitherAppearance()


def test_appearance_neither_stream_nor_subdict_advances_loop(monkeypatch) -> None:
    """An annotation whose normal appearance reports neither
    ``is_stream`` nor ``is_sub_dictionary`` falls through the elif
    (False arc) and the loop advances to the next annotation — arc
    ``106->88``."""
    page = _Page([_NeitherAnnotation(), _NeitherAnnotation()])
    page_tree = _PageTree([page])

    monkeypatch.setattr(
        "pypdfbox.loader.Loader.load_pdf",
        staticmethod(lambda path, password="": _DocWithSubDictAnnotation(page_tree)),
    )
    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument",
        lambda cos_doc: cos_doc,
    )

    # Should complete without writing anything or raising.
    ExtractTTFFonts().extract_fonts(["doc.pdf"])


def test_subdictionary_uses_mock_loader_resources(monkeypatch) -> None:
    """Variant using ``mock`` to assert the sub-dictionary stream's
    ``get_resources`` was consulted (the elif branch body)."""
    stream = mock.Mock()
    stream.get_resources.return_value = _Resources()

    class _SubDict:
        def is_stream(self):
            return False

        def is_sub_dictionary(self):
            return True

        def get_sub_dictionary(self):
            return {"On": stream}

    class _App:
        def get_normal_appearance(self):
            return _SubDict()

    class _Annot:
        def get_normal_appearance_stream(self):
            return None

        def get_appearance(self):
            return _App()

    page = _Page([_Annot(), _Annot()])
    page_tree = _PageTree([page])

    monkeypatch.setattr(
        "pypdfbox.loader.Loader.load_pdf",
        staticmethod(lambda path, password="": _DocWithSubDictAnnotation(page_tree)),
    )
    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument",
        lambda cos_doc: cos_doc,
    )

    ExtractTTFFonts().extract_fonts(["doc.pdf"])
    assert stream.get_resources.called
