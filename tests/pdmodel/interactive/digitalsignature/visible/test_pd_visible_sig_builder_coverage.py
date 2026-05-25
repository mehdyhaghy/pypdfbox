"""Coverage-boost tests for ``PDVisibleSigBuilder`` (wave 1323).

The builder's many ``try: ... except Exception:`` arms are designed to
degrade gracefully when an upstream pdmodel constructor isn't yet
wired. ``create_page`` / ``create_signature_rectangle`` /
``create_formatter_rectangle`` import ``PDRectangle`` from
``pypdfbox.pdmodel.pd_rectangle`` (wave 1403 corrected these from the
non-existent ``pypdfbox.pdmodel.common.pd_rectangle`` path, which had
silently routed every call into the ``except`` stub). The
``common_pd_rectangle_shim`` fixture below is retained as a harmless
safety net for the legacy import path; the corrected imports succeed
with or without it.

The ``create_signature`` path uses real ``add_page`` plumbing on the
template; ``set_signature_image`` is a parity stub so we only assert it
records ``image`` without raising.
"""

from __future__ import annotations

import io
import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sig_builder import (
    PDVisibleSigBuilder,
)
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sign_designer import (
    PDVisibleSignDesigner,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


@pytest.fixture
def common_pd_rectangle_shim() -> Iterator[None]:
    """Install a ``pypdfbox.pdmodel.common.pd_rectangle`` module that
    re-exports the real ``PDRectangle``. This unblocks the
    ``from pypdfbox.pdmodel.common.pd_rectangle import PDRectangle``
    imports inside several builder methods that otherwise raise
    ``ModuleNotFoundError`` and fall through to the parity stub branch.
    """
    key = "pypdfbox.pdmodel.common.pd_rectangle"
    saved = sys.modules.pop(key, None)
    fake = types.ModuleType(key)
    fake.PDRectangle = PDRectangle  # type: ignore[attr-defined]
    sys.modules[key] = fake
    try:
        yield
    finally:
        if saved is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = saved


# ---------------------------------------------------------------------------
# create_page — try-body now executes thanks to the rectangle shim
# ---------------------------------------------------------------------------


def test_create_page_builds_pd_page_with_media_box(
    common_pd_rectangle_shim: None,
) -> None:
    builder = PDVisibleSigBuilder()
    designer = PDVisibleSignDesigner().page_width(123.0).page_height(456.0)
    builder.create_page(designer)
    page = builder.get_structure().get_page()
    assert page is not None
    # ``PDPage.repr`` includes the media-box coordinates.
    text = repr(page)
    assert "123.0" in text or "123" in text
    assert "456.0" in text or "456" in text


def test_create_page_builds_real_page_without_shim() -> None:
    """With the wave-1403 import fix, ``create_page`` resolves
    ``PDRectangle`` from the real module and builds a page even without
    the legacy-path shim — it no longer falls into the ``except`` stub."""
    builder = PDVisibleSigBuilder()
    designer = PDVisibleSignDesigner()
    builder.create_page(designer)
    assert builder.get_structure().get_page() is not None


# ---------------------------------------------------------------------------
# create_template — exercises line 67 ``adder(page)`` when page != None
# ---------------------------------------------------------------------------


def test_create_template_with_non_none_page_invokes_add_page(
    common_pd_rectangle_shim: None,
) -> None:
    """``create_template(page)`` calls ``template.add_page(page)`` when
    ``page`` is non-``None`` — covers line 67. The branch must run
    without raising even if the local PDPage / PDDocument plumbing
    doesn't increment the page-count visibly."""
    builder = PDVisibleSigBuilder()
    builder.create_page(PDVisibleSignDesigner().page_width(50).page_height(50))
    page = builder.get_structure().get_page()
    assert page is not None  # rectangle shim is active
    builder.create_template(page)
    template = builder.get_structure().get_template()
    assert template is not None


def test_create_template_with_none_page_skips_add_page() -> None:
    builder = PDVisibleSigBuilder()
    builder.create_template(None)
    template = builder.get_structure().get_template()
    assert template is not None


# ---------------------------------------------------------------------------
# create_signature_rectangle — exercises lines 140-152
# ---------------------------------------------------------------------------


class _FakeWidget:
    """Records ``set_rectangle`` calls so the builder's wiring is visible
    from the outside."""

    def __init__(self) -> None:
        self.rect: PDRectangle | None = None

    def set_rectangle(self, rect: PDRectangle) -> None:
        self.rect = rect


class _FakeSignatureField:
    def __init__(self) -> None:
        self._widget = _FakeWidget()

    def get_widgets(self) -> list[_FakeWidget]:
        return [self._widget]


def test_create_signature_rectangle_normalises_dimensions(
    common_pd_rectangle_shim: None,
) -> None:
    """``create_signature_rectangle`` builds a PDRectangle from the
    designer's x/y/width/height/template-height — and stamps it on the
    widget. Covers lines 140-152."""
    designer = (
        PDVisibleSignDesigner()
        .coordinates(10.0, 20.0)
        .width(100.0)
        .height(50.0)
        .page_height(800.0)
    )
    field = _FakeSignatureField()
    builder = PDVisibleSigBuilder()
    builder.create_signature_rectangle(field, designer)
    rect = builder.get_structure().get_signature_rectangle()
    assert rect is not None
    assert isinstance(rect, PDRectangle)
    # Upper-right: x_axis + width = 110; template_height - y_axis = 780.
    assert rect.get_upper_right_x() == 110.0
    assert rect.get_upper_right_y() == 780.0
    # Lower-left: x_axis = 10; template_height - y_axis - height = 730.
    assert rect.get_lower_left_x() == 10.0
    assert rect.get_lower_left_y() == 730.0
    # Widget was stamped with the same instance.
    assert field._widget.rect is rect


def test_create_signature_rectangle_handles_missing_width_height(
    common_pd_rectangle_shim: None,
) -> None:
    """When the designer's width/height are ``None``, the ``(width or 0.0)``
    fallback applies and the math still terminates."""
    designer = PDVisibleSignDesigner().coordinates(5.0, 5.0).page_height(100.0)
    field = _FakeSignatureField()
    builder = PDVisibleSigBuilder()
    builder.create_signature_rectangle(field, designer)
    rect = builder.get_structure().get_signature_rectangle()
    assert rect is not None
    assert rect.get_upper_right_x() == 5.0  # x + 0
    assert rect.get_lower_left_y() == 95.0  # template_height - y - 0


# ---------------------------------------------------------------------------
# create_formatter_rectangle — exercises lines 179-184
# ---------------------------------------------------------------------------


def test_create_formatter_rectangle_normalises_into_pd_rectangle(
    common_pd_rectangle_shim: None,
) -> None:
    """``create_formatter_rectangle`` picks min/max so lower-left and
    upper-right are correctly ordered regardless of input ordering."""
    builder = PDVisibleSigBuilder()
    # Deliberately swap: upper-left then lower-right ordering.
    builder.create_formatter_rectangle([100, 50, 10, 200])
    rect = builder.get_structure().get_formatter_rectangle()
    assert rect is not None
    assert isinstance(rect, PDRectangle)
    assert rect.get_lower_left_x() == 10
    assert rect.get_lower_left_y() == 50
    assert rect.get_upper_right_x() == 100
    assert rect.get_upper_right_y() == 200


# ---------------------------------------------------------------------------
# create_signature — exercises the signer-name branch at line 111-113
# ---------------------------------------------------------------------------


class _FakeAnnotList(list):
    pass


class _FakePage:
    def __init__(self) -> None:
        self._annots = _FakeAnnotList()

    def get_annotations(self) -> _FakeAnnotList:
        return self._annots


class _FakePageWidget:
    def __init__(self) -> None:
        self.page: _FakePage | None = None

    def set_page(self, page: _FakePage) -> None:
        self.page = page


class _FakeFieldWithValue:
    def __init__(self) -> None:
        self._widget = _FakePageWidget()
        self.value: Any = None

    def get_widgets(self) -> list[_FakePageWidget]:
        return [self._widget]

    def set_value(self, value: Any) -> None:
        self.value = value


def test_create_signature_with_signer_name_sets_name() -> None:
    """The signer-name branch (line 111-113) fires when a truthy
    ``signer_name`` is passed."""
    builder = PDVisibleSigBuilder()
    field = _FakeFieldWithValue()
    page = _FakePage()
    builder.create_signature(field, page, "Alice")
    sig = builder.get_structure().get_pd_signature()
    assert sig is not None
    assert sig.get_name() == "Alice"
    assert field._widget.page is page
    assert page.get_annotations() == [field._widget]
    assert field.value is sig


def test_create_signature_with_empty_signer_name_skips_set_name() -> None:
    builder = PDVisibleSigBuilder()
    field = _FakeFieldWithValue()
    builder.create_signature(field, _FakePage(), "")
    sig = builder.get_structure().get_pd_signature()
    assert sig is not None
    assert sig.get_name() is None or sig.get_name() == ""


def test_create_signature_swallows_widget_lookup_error() -> None:
    """If ``signature_field`` has no ``get_widgets``, the except arm runs
    and the structure's pd_signature is set to ``None``."""
    builder = PDVisibleSigBuilder()
    builder.create_signature(object(), _FakePage(), "")
    assert builder.get_structure().get_pd_signature() is None


# ---------------------------------------------------------------------------
# stub branches — record-only methods that need no rectangle shim
# ---------------------------------------------------------------------------


def test_create_signature_image_records_image_passthrough() -> None:
    builder = PDVisibleSigBuilder()
    builder.create_signature_image(template=None, image=b"<png bytes>")
    assert builder.get_structure().get_image() == b"<png bytes>"


def test_append_raw_commands_encodes_iso_8859_1() -> None:
    """``appendRawCommands`` writes the literal bytes using ISO-8859-1
    (matches Java upstream which has no encoding parameter)."""
    builder = PDVisibleSigBuilder()
    buf = io.BytesIO()
    builder.append_raw_commands(buf, "q Q")
    assert buf.getvalue() == b"q Q"


def test_append_raw_commands_writes_nothing_when_stream_has_no_write() -> None:
    """An output target without ``.write`` is silently skipped."""
    builder = PDVisibleSigBuilder()
    builder.append_raw_commands(object(), "BT ET")  # no AttributeError raised
