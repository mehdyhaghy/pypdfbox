"""Wave 1333 — coverage uplift for ``extract_ttf_fonts``.

Drives the argv parser, ``process_resources`` short-circuits, the nested
resource walk (``process_nested_resources``), ``process_resources_fonts``
type-dispatch arms, ``write_font`` IO path, ``usage``, and the
``extract_fonts`` Loader.load_pdf entrypoint.

Most tests use lightweight stand-in objects rather than real PDFs to
keep the file fast and to avoid pulling in the font/rendering dep chain.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from pypdfbox.examples.pdmodel.extract_ttf_fonts import ExtractTTFFonts

# ---------------------------------------------------------------------------
# Stand-ins used by multiple tests.
# ---------------------------------------------------------------------------


class _Key:
    """Stand-in for a ``COSName`` with ``get_name``."""

    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name


class _CosObj:
    """Distinct identity object used by ``font_set`` membership checks."""


class _FontDescriptor:
    """Mimic ``PDFontDescriptor`` for ``write_font``."""

    def __init__(self, ff2):
        self._ff2 = ff2

    def get_font_file2(self):
        return self._ff2


class _StreamReader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.closed = False

    def read(self, n: int = -1) -> bytes:
        if n == -1 or n >= len(self.payload):
            data, self.payload = self.payload, b""
            return data
        data, self.payload = self.payload[:n], self.payload[n:]
        return data

    def close(self) -> None:
        self.closed = True


class _FF2:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.last_reader: _StreamReader | None = None

    def create_input_stream(self) -> _StreamReader:
        self.last_reader = _StreamReader(self.payload)
        return self.last_reader


class _FontWithDescriptor:
    """Generic font: returns whatever descriptor the test wires in."""

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
    """Stand-in for ``PDResources``."""

    def __init__(
        self,
        fonts=None,
        xobjects=None,
        patterns=None,
        ext_g_states=None,
    ) -> None:
        self._fonts = fonts or {}
        self._xobjects = xobjects or {}
        self._patterns = patterns or {}
        self._ext_g_states = ext_g_states or {}

    def get_font_names(self):
        return list(self._fonts.keys())

    def get_font(self, key):
        return self._fonts.get(key)

    def get_xobject_names(self):
        return list(self._xobjects.keys())

    def get_xobject(self, name):
        return self._xobjects.get(name)

    def get_pattern_names(self):
        return list(self._patterns.keys())

    def get_pattern(self, name):
        return self._patterns.get(name)

    def get_ext_g_state_names(self):
        return list(self._ext_g_states.keys())

    def get_ext_g_state(self, name):
        return self._ext_g_states.get(name)


# ---------------------------------------------------------------------------
# usage / main / argv parsing
# ---------------------------------------------------------------------------


def test_main_no_argv_prints_usage_and_exits() -> None:
    with pytest.raises(SystemExit) as exc:
        ExtractTTFFonts.main(None)
    assert exc.value.code == 1


def test_main_too_many_args_prints_usage_and_exits() -> None:
    with pytest.raises(SystemExit) as exc:
        ExtractTTFFonts.main(["a", "b", "c", "d", "e"])
    assert exc.value.code == 1


def test_usage_writes_to_stderr_and_exits(capsys) -> None:
    with pytest.raises(SystemExit):
        ExtractTTFFonts.usage()
    err = capsys.readouterr().err
    assert "ExtractTTFFonts" in err
    assert "-password" in err


def test_extract_fonts_password_missing_value_falls_to_usage() -> None:
    # ``-password`` with no following value should hit the usage branch
    # without raising before we get there (extract_fonts returns silently
    # because usage() now raises SystemExit — but with the early-return
    # path, ``len(argv) > 4`` gate triggers the same usage exit when we
    # pad). Pin the trailing -password branch via padded argv that fits
    # the size gate.
    extractor = ExtractTTFFonts()
    with pytest.raises(SystemExit):
        extractor.extract_fonts(["-password"])  # len == 1 → no exit yet, then i+1 OOB → usage


def test_extract_fonts_prefix_missing_value_calls_usage() -> None:
    extractor = ExtractTTFFonts()
    with pytest.raises(SystemExit):
        extractor.extract_fonts(["-prefix"])  # len == 1 then i+1 OOB → usage


def test_extract_fonts_no_pdf_arg_calls_usage() -> None:
    # ``-addkey`` alone: argv length valid, no pdf path → usage
    extractor = ExtractTTFFonts()
    with pytest.raises(SystemExit):
        extractor.extract_fonts(["-addkey"])


# ---------------------------------------------------------------------------
# get_unique_file_name advances counter and avoids existing files
# ---------------------------------------------------------------------------


def test_get_unique_file_name_skips_existing(tmp_path: Path) -> None:
    extractor = ExtractTTFFonts()
    # Seed -1 and -2 as already existing; expect -3 to be picked.
    base = str(tmp_path / "f")
    (tmp_path / "f-1.ttf").write_bytes(b"")
    (tmp_path / "f-2.ttf").write_bytes(b"")
    chosen = extractor.get_unique_file_name(base, "ttf")
    assert chosen.endswith("-3")


# ---------------------------------------------------------------------------
# write_font: real stream → temp file
# ---------------------------------------------------------------------------


def test_write_font_copies_stream_payload(tmp_path: Path) -> None:
    payload = b"\x00\x01OTTO-ish-stub"
    ff2 = _FF2(payload)
    descriptor = _FontDescriptor(ff2)
    name = str(tmp_path / "font")
    ExtractTTFFonts().write_font(descriptor, name)
    out = Path(name + ".ttf")
    assert out.read_bytes() == payload
    assert ff2.last_reader is not None
    assert ff2.last_reader.closed is True


def test_write_font_short_circuits_when_ff2_none(tmp_path: Path) -> None:
    descriptor = _FontDescriptor(None)
    name = str(tmp_path / "skip")
    ExtractTTFFonts().write_font(descriptor, name)
    assert not Path(name + ".ttf").exists()


def test_write_font_handles_reader_without_close(tmp_path: Path) -> None:
    class _NoCloseReader:
        def __init__(self, data: bytes) -> None:
            self._data = data

        def read(self, n: int = -1) -> bytes:
            data, self._data = self._data, b""
            return data

    class _FF2NoClose:
        def create_input_stream(self):
            return _NoCloseReader(b"payload")

    descriptor = _FontDescriptor(_FF2NoClose())
    name = str(tmp_path / "noclose")
    ExtractTTFFonts().write_font(descriptor, name)
    assert Path(name + ".ttf").read_bytes() == b"payload"


# ---------------------------------------------------------------------------
# process_resources / process_resources_fonts paths
# ---------------------------------------------------------------------------


def test_process_resources_fonts_skips_when_font_lookup_returns_none(
    capsys,
) -> None:
    # get_font returns None → continue.
    resources = _Resources(fonts={_Key("F1"): None})
    extractor = ExtractTTFFonts()
    extractor.process_resources_fonts(resources, False, "p")
    # Nothing was written and no exception raised.
    assert capsys.readouterr().out == ""


def test_process_resources_fonts_handles_font_without_name(
    capsys, tmp_path: Path, monkeypatch,
) -> None:
    # Font.get_name raises AttributeError → fallback to "(null)".
    class _NoNameFont:
        def get_cos_object(self):
            return _CosObj()

    font = _NoNameFont()
    # Patch: AttributeError path is via ``try/except`` on ``font.get_name``.
    # _NoNameFont has no ``get_name`` attribute at all → AttributeError.
    resources = _Resources(fonts={_Key("F1"): font})
    monkeypatch.chdir(tmp_path)
    ExtractTTFFonts().process_resources_fonts(resources, False, "p")
    out = capsys.readouterr().out
    assert "(null)" in out


def test_process_resources_fonts_dedup_via_font_set(capsys, tmp_path: Path, monkeypatch) -> None:
    shared_cos = _CosObj()
    font_a = _FontWithDescriptor("FontA", shared_cos, descriptor=None)
    font_b = _FontWithDescriptor("FontB", shared_cos, descriptor=None)
    resources = _Resources(fonts={_Key("F1"): font_a, _Key("F2"): font_b})
    monkeypatch.chdir(tmp_path)
    ExtractTTFFonts().process_resources_fonts(resources, False, "p")
    out = capsys.readouterr().out
    # First font logs; second short-circuits via font_set membership but
    # also prints (the membership check happens AFTER the print).
    assert out.count("on page") == 2


def test_process_resources_fonts_truetype_writes(monkeypatch, tmp_path: Path) -> None:
    """When font is a PDTrueTypeFont with a valid descriptor, write_font is called."""
    from pypdfbox.examples.pdmodel import extract_ttf_fonts as mod

    class _FakeTTF(_FontWithDescriptor):
        pass

    payload = b"TTFDATA"
    ff2 = _FF2(payload)
    descriptor = _FontDescriptor(ff2)
    font = _FakeTTF("Roboto", _CosObj(), descriptor=descriptor)

    monkeypatch.setattr(
        "pypdfbox.pdmodel.font.pd_true_type_font.PDTrueTypeFont",
        _FakeTTF,
        raising=False,
    )

    resources = _Resources(fonts={_Key("FRoboto"): font})
    monkeypatch.chdir(tmp_path)
    extractor = mod.ExtractTTFFonts()
    extractor.process_resources_fonts(resources, add_key=True, prefix="myfont")
    # The chosen prefix is "myfont_FRoboto" (add_key=True path) +
    # "-1.ttf".
    assert (tmp_path / "myfont_FRoboto-1.ttf").read_bytes() == payload


def test_process_resources_fonts_type0_with_cid_font_type2(monkeypatch, tmp_path: Path) -> None:
    class _FakeCID(_FontWithDescriptor):
        pass

    class _FakeType0(_FontWithDescriptor):
        def __init__(self, name, cos, descendant):
            super().__init__(name, cos, descriptor=None)
            self._descendant = descendant

        def get_descendant_font(self):
            return self._descendant

    payload = b"CIDDATA"
    ff2 = _FF2(payload)
    descriptor = _FontDescriptor(ff2)

    descendant = _FakeCID("CID", _CosObj(), descriptor=descriptor)
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
    ExtractTTFFonts().process_resources_fonts(resources, add_key=False, prefix=None)
    # prefix=None and add_key=False → seed is "font" → "font-1.ttf".
    assert (tmp_path / "font-1.ttf").read_bytes() == payload


def test_process_resources_fonts_unknown_class_skips(monkeypatch, tmp_path: Path) -> None:
    # A font that's neither TrueType nor Type0 → descriptor stays None → continue.
    font = _FontWithDescriptor("Other", _CosObj(), descriptor=None)
    resources = _Resources(fonts={_Key("FOther"): font})
    monkeypatch.chdir(tmp_path)
    ExtractTTFFonts().process_resources_fonts(resources, False, "p")
    # No .ttf written.
    assert not list(tmp_path.glob("*.ttf"))


def test_process_resources_fonts_uses_str_key_when_no_get_name(
    monkeypatch, tmp_path: Path,
) -> None:
    class _FakeTTF(_FontWithDescriptor):
        pass

    payload = b"K"
    ff2 = _FF2(payload)
    descriptor = _FontDescriptor(ff2)
    font = _FakeTTF("Roboto", _CosObj(), descriptor=descriptor)
    monkeypatch.setattr(
        "pypdfbox.pdmodel.font.pd_true_type_font.PDTrueTypeFont",
        _FakeTTF,
        raising=False,
    )
    # plain string key, no get_name attribute → goes via ``str(key)``.
    resources = _Resources(fonts={"Plain": font})
    monkeypatch.chdir(tmp_path)
    ExtractTTFFonts().process_resources_fonts(
        resources, add_key=True, prefix="pre",
    )
    assert (tmp_path / "pre_Plain-1.ttf").read_bytes() == payload


# ---------------------------------------------------------------------------
# process_nested_resources: xobject / pattern / ext-g-state arms
# ---------------------------------------------------------------------------


def test_process_nested_resources_recurses_into_form_xobject(monkeypatch) -> None:
    class _FakeForm:
        def __init__(self, inner):
            self._inner = inner

        def get_resources(self):
            return self._inner

    monkeypatch.setattr(
        "pypdfbox.pdmodel.graphics.form.pd_form_x_object.PDFormXObject",
        _FakeForm,
        raising=False,
    )

    inner_resources = _Resources()
    form = _FakeForm(inner_resources)
    outer = _Resources(xobjects={_Key("Im0"): form})

    calls: list[object] = []

    extractor = ExtractTTFFonts()
    real = extractor.process_resources

    def _spy(res, *a, **kw):
        calls.append(res)
        return real(res, *a, **kw)

    extractor.process_resources = _spy  # type: ignore[assignment]
    extractor.process_nested_resources(outer, "p", False)
    assert inner_resources in calls


def test_process_nested_resources_recurses_into_tiling_pattern(monkeypatch) -> None:
    class _FakeTiling:
        def __init__(self, inner):
            self._inner = inner

        def get_resources(self):
            return self._inner

    monkeypatch.setattr(
        "pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern.PDTilingPattern",
        _FakeTiling,
        raising=False,
    )

    inner = _Resources()
    outer = _Resources(patterns={_Key("P0"): _FakeTiling(inner)})

    extractor = ExtractTTFFonts()
    calls: list[object] = []
    real = extractor.process_resources

    def _spy(res, *a, **kw):
        calls.append(res)
        return real(res, *a, **kw)

    extractor.process_resources = _spy  # type: ignore[assignment]
    extractor.process_nested_resources(outer, "p", False)
    assert inner in calls


def test_process_nested_resources_ext_g_state_none_short_circuits() -> None:
    outer = _Resources(ext_g_states={_Key("GS0"): None})
    # Must not raise.
    ExtractTTFFonts().process_nested_resources(outer, "p", False)


def test_process_nested_resources_ext_g_state_no_soft_mask_method() -> None:
    class _NoSoftMask:
        pass

    outer = _Resources(ext_g_states={_Key("GS0"): _NoSoftMask()})
    ExtractTTFFonts().process_nested_resources(outer, "p", False)


def test_process_nested_resources_ext_g_state_soft_mask_none() -> None:
    class _Ext:
        def get_soft_mask_typed(self):
            return None

    outer = _Resources(ext_g_states={_Key("GS0"): _Ext()})
    ExtractTTFFonts().process_nested_resources(outer, "p", False)


def test_process_nested_resources_ext_g_state_recurses_through_group() -> None:
    inner = _Resources()

    class _Group:
        def get_resources(self):
            return inner

    class _SoftMask:
        def get_group(self):
            return _Group()

    class _Ext:
        def get_soft_mask_typed(self):
            return _SoftMask()

    outer = _Resources(ext_g_states={_Key("GS0"): _Ext()})
    extractor = ExtractTTFFonts()
    calls: list[object] = []
    real = extractor.process_resources

    def _spy(res, *a, **kw):
        calls.append(res)
        return real(res, *a, **kw)

    extractor.process_resources = _spy  # type: ignore[assignment]
    extractor.process_nested_resources(outer, "p", False)
    assert inner in calls


def test_process_nested_resources_ext_g_state_group_none() -> None:
    class _SoftMask:
        def get_group(self):
            return None

    class _Ext:
        def get_soft_mask_typed(self):
            return _SoftMask()

    outer = _Resources(ext_g_states={_Key("GS0"): _Ext()})
    ExtractTTFFonts().process_nested_resources(outer, "p", False)


def test_process_nested_resources_non_form_xobject_skipped(monkeypatch) -> None:
    class _FakeForm:
        pass

    monkeypatch.setattr(
        "pypdfbox.pdmodel.graphics.form.pd_form_x_object.PDFormXObject",
        _FakeForm,
        raising=False,
    )
    outer = _Resources(xobjects={_Key("Im0"): object()})
    # Should not raise; non-form xobject simply ignored.
    ExtractTTFFonts().process_nested_resources(outer, "p", False)


def test_process_nested_resources_non_tiling_pattern_skipped(monkeypatch) -> None:
    class _FakeTiling:
        pass

    monkeypatch.setattr(
        "pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern.PDTilingPattern",
        _FakeTiling,
        raising=False,
    )
    outer = _Resources(patterns={_Key("P0"): object()})
    ExtractTTFFonts().process_nested_resources(outer, "p", False)


# ---------------------------------------------------------------------------
# extract_fonts: end-to-end via heavily-mocked Loader & PDDocument
# ---------------------------------------------------------------------------


def test_extract_fonts_walks_pages_and_annotations(monkeypatch, tmp_path: Path) -> None:
    """Full driver test exercising the long ``extract_fonts`` body.

    Mocks Loader.load_pdf so we never hit a real parser, and mocks the
    PDDocument constructor to return a hand-built object exposing the
    minimal surface area the example reads.
    """
    from pypdfbox.examples.pdmodel import extract_ttf_fonts as mod

    # --- build mock acro form + page tree + annotations ----------------
    acro_resources = _Resources()
    acro_form = mock.MagicMock()
    acro_form.get_default_resources.return_value = acro_resources

    catalog = mock.MagicMock()
    catalog.get_acro_form.return_value = acro_form

    page_resources = _Resources()
    annotation_nas_resources = _Resources()

    nas = mock.MagicMock()
    nas.get_resources.return_value = annotation_nas_resources

    appearance_stream_resources = _Resources()
    nas_from_appearance = mock.MagicMock()
    nas_from_appearance.get_resources.return_value = (
        appearance_stream_resources
    )

    normal_appearance_stream = mock.MagicMock()
    normal_appearance_stream.is_stream.return_value = True
    normal_appearance_stream.is_sub_dictionary.return_value = False
    normal_appearance_stream.get_appearance_stream.return_value = (
        nas_from_appearance
    )

    appearance_with_stream = mock.MagicMock()
    appearance_with_stream.get_normal_appearance.return_value = (
        normal_appearance_stream
    )

    sub_dict_resources_a = _Resources()
    sub_dict_resources_b = _Resources()
    sub_dict_stream_a = mock.MagicMock()
    sub_dict_stream_a.get_resources.return_value = sub_dict_resources_a
    sub_dict_stream_b = mock.MagicMock()
    sub_dict_stream_b.get_resources.return_value = sub_dict_resources_b

    normal_appearance_subdict = mock.MagicMock()
    normal_appearance_subdict.is_stream.return_value = False
    normal_appearance_subdict.is_sub_dictionary.return_value = True
    sub_dict = mock.MagicMock()
    sub_dict.values.return_value = [sub_dict_stream_a, sub_dict_stream_b]
    normal_appearance_subdict.get_sub_dictionary.return_value = sub_dict

    appearance_with_subdict = mock.MagicMock()
    appearance_with_subdict.get_normal_appearance.return_value = (
        normal_appearance_subdict
    )

    appearance_none_normal = mock.MagicMock()
    appearance_none_normal.get_normal_appearance.return_value = None

    # Four annotations to exercise all branches:
    #   1) nas exists + appearance is None → continue
    #   2) nas None + appearance None-normal → inner continue
    #   3) nas None + appearance with normal is_stream
    #   4) nas None + appearance with normal is_sub_dictionary
    annot_with_nas = mock.MagicMock()
    annot_with_nas.get_normal_appearance_stream.return_value = nas
    annot_with_nas.get_appearance.return_value = None

    annot_none_normal_app = mock.MagicMock()
    annot_none_normal_app.get_normal_appearance_stream.return_value = None
    annot_none_normal_app.get_appearance.return_value = appearance_none_normal

    annot_with_stream_app = mock.MagicMock()
    annot_with_stream_app.get_normal_appearance_stream.return_value = None
    annot_with_stream_app.get_appearance.return_value = (
        appearance_with_stream
    )

    annot_with_subdict_app = mock.MagicMock()
    annot_with_subdict_app.get_normal_appearance_stream.return_value = None
    annot_with_subdict_app.get_appearance.return_value = (
        appearance_with_subdict
    )

    annot_with_no_appearance = mock.MagicMock()
    annot_with_no_appearance.get_normal_appearance_stream.return_value = None
    annot_with_no_appearance.get_appearance.return_value = None

    # is_stream + get_appearance_stream returns None branch
    nas_none_branch = mock.MagicMock()
    nas_none_branch.is_stream.return_value = True
    nas_none_branch.is_sub_dictionary.return_value = False
    nas_none_branch.get_appearance_stream.return_value = None
    appearance_with_none_stream = mock.MagicMock()
    appearance_with_none_stream.get_normal_appearance.return_value = (
        nas_none_branch
    )
    annot_stream_none = mock.MagicMock()
    annot_stream_none.get_normal_appearance_stream.return_value = None
    annot_stream_none.get_appearance.return_value = (
        appearance_with_none_stream
    )

    page = mock.MagicMock()
    page.get_resources.return_value = page_resources
    page.get_annotations.return_value = [
        annot_with_nas,
        annot_none_normal_app,
        annot_with_stream_app,
        annot_with_subdict_app,
        annot_with_no_appearance,
        annot_stream_none,
    ]

    page_tree = mock.MagicMock()
    page_tree.__iter__ = lambda self: iter([page])
    page_tree.index_of.return_value = 0

    document = mock.MagicMock()
    document.get_document_catalog.return_value = catalog
    document.get_pages.return_value = page_tree

    # PDDocument(cos_doc) → document; patch the constructor used inside
    # the lazy ``from pypdfbox.pdmodel.pd_document import PDDocument``.
    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument",
        lambda *a, **kw: document,
        raising=True,
    )

    # Loader.load_pdf returns a CM whose body yields a stand-in cos doc.
    class _CM:
        def __enter__(self):
            return mock.MagicMock(name="cos_doc")

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        "pypdfbox.loader.Loader.load_pdf",
        lambda *_args, **_kw: _CM(),
        raising=True,
    )

    pdf_path = tmp_path / "in.pdf"
    pdf_path.write_bytes(b"%PDF-stub")

    # Use prefix= via positional ordering and verify add_key plumbing.
    # len(argv) must be <= 4 per the size gate.
    mod.ExtractTTFFonts().extract_fonts(
        ["-prefix", "p", "-addkey", str(pdf_path)],
    )


def test_extract_fonts_no_acro_form(monkeypatch, tmp_path: Path) -> None:
    """The acro_form is None branch."""
    from pypdfbox.examples.pdmodel import extract_ttf_fonts as mod

    catalog = mock.MagicMock()
    catalog.get_acro_form.return_value = None

    page_tree = mock.MagicMock()
    page_tree.__iter__ = lambda self: iter([])

    document = mock.MagicMock()
    document.get_document_catalog.return_value = catalog
    document.get_pages.return_value = page_tree

    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument",
        lambda *a, **kw: document,
        raising=True,
    )

    class _CM:
        def __enter__(self):
            return mock.MagicMock(name="cos_doc")

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        "pypdfbox.loader.Loader.load_pdf",
        lambda *_args, **_kw: _CM(),
        raising=True,
    )

    pdf_path = tmp_path / "no_acro.pdf"
    pdf_path.write_bytes(b"%PDF-stub")
    mod.ExtractTTFFonts().extract_fonts([str(pdf_path)])


def test_extract_fonts_prefix_auto_derived_from_short_pdf_name(
    monkeypatch, tmp_path: Path,
) -> None:
    """Cover the ``len(pdf_file) > 4`` prefix-derivation branch."""
    from pypdfbox.examples.pdmodel import extract_ttf_fonts as mod

    catalog = mock.MagicMock()
    catalog.get_acro_form.return_value = None

    page_tree = mock.MagicMock()
    page_tree.__iter__ = lambda self: iter([])

    document = mock.MagicMock()
    document.get_document_catalog.return_value = catalog
    document.get_pages.return_value = page_tree

    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument",
        lambda *a, **kw: document,
        raising=True,
    )

    class _CM:
        def __enter__(self):
            return mock.MagicMock(name="cos_doc")

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        "pypdfbox.loader.Loader.load_pdf",
        lambda *_args, **_kw: _CM(),
        raising=True,
    )

    # ``len("a.pdf") == 5`` → ``> 4`` so prefix becomes ``"a"``.
    mod.ExtractTTFFonts().extract_fonts(["a.pdf"])


def test_extract_fonts_password_consumed_and_passed_to_loader(
    monkeypatch, tmp_path: Path,
) -> None:
    """Cover the ``-password <value>`` consumption branch."""
    from pypdfbox.examples.pdmodel import extract_ttf_fonts as mod

    catalog = mock.MagicMock()
    catalog.get_acro_form.return_value = None

    page_tree = mock.MagicMock()
    page_tree.__iter__ = lambda self: iter([])

    document = mock.MagicMock()
    document.get_document_catalog.return_value = catalog
    document.get_pages.return_value = page_tree

    monkeypatch.setattr(
        "pypdfbox.pdmodel.pd_document.PDDocument",
        lambda *a, **kw: document,
        raising=True,
    )

    captured: dict[str, object] = {}

    class _CM:
        def __enter__(self):
            return mock.MagicMock(name="cos_doc")

        def __exit__(self, *exc):
            return False

    def _fake_load_pdf(path, password=""):
        captured["path"] = path
        captured["password"] = password
        return _CM()

    monkeypatch.setattr(
        "pypdfbox.loader.Loader.load_pdf", _fake_load_pdf, raising=True,
    )

    pdf_path = tmp_path / "pw.pdf"
    pdf_path.write_bytes(b"%PDF-stub")
    mod.ExtractTTFFonts().extract_fonts(
        ["-password", "topsecret", str(pdf_path)],
    )
    assert captured["password"] == "topsecret"
