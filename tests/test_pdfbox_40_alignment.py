"""Regression pins for the Apache PDFBox 4.0 migration-guide items.

Source of truth: https://pdfbox.apache.org/4.0/migration.html (4.0 is
still ``4.0.0-SNAPSHOT``; the guide is explicitly a work in progress).
CLAUDE.md "PDFBox 4.0 Alignment Notes" records which of those items
pypdfbox adopted ahead of the upstream release.

Every item the guide lists is pinned here, so an adopted behaviour
cannot silently regress.

As of pypdfbox **2.0.0** no deferred rows remain. The four
source-breaking removals 1.x carried — the ``PDIndexed`` no-arg
constructor, ``PDIndexed.setBaseColorSpace``,
``PDIndexed.setHighValue`` and
``PDVisibleSigBuilder.appendRawCommands`` — are all adopted, and the
overlay transform now uses upstream's exact formula. The pins below
assert the **4.0 shape**: each 3.x name is asserted *absent*.

Guide items and where they land:

===========================================  ==========================
Java 11.0.23 / 17.0.11 minimum               not applicable (Python)
Dependency bumps (BC, Log4j, picocli, …)     not applicable (Python)
Preflight subproject removed                 pinned: never ported
commons-logging -> Log4j 2                   pinned: stdlib ``logging``
ICOSVisitor needs ``visitFromObject``        pinned: ADOPTED
Overlay uses the real lower left             pinned: ADOPTED — 2.0.0
                                             dropped the extra
                                             overlay-corner term for
                                             byte-exact upstream parity
``writeRawCommands(PDStream, String)``       pinned: ADOPTED — 2.0.0
                                             removed
                                             ``appendRawCommands``
PDIndexed: no-arg ctor + 2 methods removed   pinned: ADOPTED in 2.0.0
===========================================  ==========================
"""

import annotationlib
import inspect
import logging
from pathlib import Path
from typing import Any

import pytest

import pypdfbox
from pypdfbox.cos import COSNull, COSObject, ICOSVisitor
from pypdfbox.multipdf.overlay import Overlay
from pypdfbox.pdfwriter.cos_writer import COSWriter
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sig_builder import (
    PDVisibleSigBuilder,
)
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

# ---------------------------------------------------------------------------
# "Preflight was removed"
# ---------------------------------------------------------------------------


def test_no_preflight_module_is_shipped() -> None:
    """4.0 dropped the Preflight subproject; pypdfbox never ported it."""
    with pytest.raises(ImportError):
        __import__("pypdfbox.preflight")
    package_root = Path(pypdfbox.__file__).parent
    assert not (package_root / "preflight").exists()


# ---------------------------------------------------------------------------
# "Switch to Apache Log4j"
# ---------------------------------------------------------------------------


def test_logging_is_stdlib_not_log4j() -> None:
    """4.0 swapped commons-logging for Log4j 2. Not applicable: pypdfbox
    logs through the Python stdlib, so neither Java framework leaks in."""
    from pypdfbox.multipdf import overlay as overlay_module

    assert isinstance(overlay_module._LOG, logging.Logger)
    assert overlay_module._LOG.name.startswith("pypdfbox")


# ---------------------------------------------------------------------------
# "ICOSVisitor derived classes"
#
# 4.0: ``visitFromObject`` is no longer a default method on the interface —
# implementations must supply it, and the old default body moved to
# ``COSWriter``.
# ---------------------------------------------------------------------------


def test_i_cos_visitor_requires_visit_from_object() -> None:
    assert "visit_from_object" in ICOSVisitor.__abstractmethods__
    # ...and it really is abstract: no inherited default body.
    assert getattr(ICOSVisitor.visit_from_object, "__isabstractmethod__", False)


def test_visitor_missing_visit_from_object_cannot_be_instantiated() -> None:
    """A 3.x-era visitor that relied on the interface default is now
    rejected at construction, exactly as 4.0 rejects it at compile time."""

    class _Incomplete(ICOSVisitor):
        def visit_from_array(self, obj: Any) -> Any: ...
        def visit_from_boolean(self, obj: Any) -> Any: ...
        def visit_from_dictionary(self, obj: Any) -> Any: ...
        def visit_from_document(self, obj: Any) -> Any: ...
        def visit_from_float(self, obj: Any) -> Any: ...
        def visit_from_integer(self, obj: Any) -> Any: ...
        def visit_from_name(self, obj: Any) -> Any: ...
        def visit_from_null(self, obj: Any) -> Any: ...
        def visit_from_stream(self, obj: Any) -> Any: ...
        def visit_from_string(self, obj: Any) -> Any: ...
        # deliberately no visit_from_object

    with pytest.raises(TypeError, match="visit_from_object"):
        _Incomplete()  # type: ignore[abstract]


def test_cos_writer_owns_the_former_default_implementation() -> None:
    """The 3.x default body ("null target -> visitFromNull, else
    accept") lives on COSWriter in 4.0, not on the interface."""
    assert "visit_from_object" in vars(COSWriter)
    assert "visit_from_object" not in vars(ICOSVisitor) or getattr(
        ICOSVisitor.visit_from_object, "__isabstractmethod__", False
    )


def test_cos_object_accept_dispatches_to_visit_from_object() -> None:
    seen: list[Any] = []

    class _Recorder(ICOSVisitor):
        def visit_from_array(self, obj: Any) -> Any: ...
        def visit_from_boolean(self, obj: Any) -> Any: ...
        def visit_from_dictionary(self, obj: Any) -> Any: ...
        def visit_from_document(self, obj: Any) -> Any: ...
        def visit_from_float(self, obj: Any) -> Any: ...
        def visit_from_integer(self, obj: Any) -> Any: ...
        def visit_from_name(self, obj: Any) -> Any: ...
        def visit_from_null(self, obj: Any) -> Any: ...
        def visit_from_stream(self, obj: Any) -> Any: ...
        def visit_from_string(self, obj: Any) -> Any: ...

        def visit_from_object(self, obj: Any) -> Any:
            seen.append(obj)

    obj = COSObject(12, 0, resolved=COSNull.NULL)
    obj.accept(_Recorder())
    assert seen == [obj]


# ---------------------------------------------------------------------------
# "Overlay behavior different" (PDFBOX-6048)
# ---------------------------------------------------------------------------


def _page_with_media_box(*coords: float) -> PDPage:
    page = PDPage()
    page.set_media_box(PDRectangle(*coords))
    return page


def test_overlay_transform_uses_page_lower_left_not_zero_zero() -> None:
    """PDFBOX-6048: 3.0.x centred as if the destination media box started
    at (0,0). 4.0 offsets by the box's real lower-left corner."""
    page = _page_with_media_box(20.0, 30.0, 620.0, 830.0)  # 600 x 800
    overlay_box = PDRectangle(0.0, 0.0, 400.0, 600.0)

    matrix = Overlay().calculate_affine_transform(page, overlay_box)

    assert matrix[:4] == [1.0, 0.0, 0.0, 1.0]
    # 3.0.x would have produced (100, 100); 4.0 adds the (20, 30) corner.
    assert matrix[4] == pytest.approx(20.0 + (600.0 - 400.0) / 2.0)
    assert matrix[5] == pytest.approx(30.0 + (800.0 - 600.0) / 2.0)


def test_overlay_transform_unchanged_for_origin_media_box() -> None:
    """The 6048 correction is a no-op for the overwhelmingly common
    lower-left-at-origin case, so 3.0-era output is untouched."""
    page = _page_with_media_box(0.0, 0.0, 600.0, 800.0)
    overlay_box = PDRectangle(0.0, 0.0, 400.0, 600.0)

    matrix = Overlay().calculate_affine_transform(page, overlay_box)

    assert matrix == [1.0, 0.0, 0.0, 1.0, 100.0, 100.0]


def test_overlay_transform_ignores_the_overlays_own_lower_left() -> None:
    """2.0.0 parity correction. pypdfbox 1.x subtracted the *overlay's*
    lower-left corner as well::

        (pw - ow) / 2 + page_llx - overlay_llx

    Upstream trunk (``Overlay.java`` lines 615-616) computes only::

        pageMediaBox.getLowerLeftX() + (pw - ow) / 2

    and handles a non-origin overlay box through the form XObject's
    retranslated ``/BBox`` instead. The extra term was an invented
    divergence; 2.0.0 drops it for byte-exact upstream parity.
    """
    page = _page_with_media_box(0.0, 0.0, 600.0, 800.0)
    # Overlay MediaBox NOT at the origin: lower-left (50, 70), 400 x 600.
    overlay_box = PDRectangle(50.0, 70.0, 450.0, 670.0)

    matrix = Overlay().calculate_affine_transform(page, overlay_box)

    # Upstream formula: page_llx + (600-400)/2 = 100, page_lly + (800-600)/2 = 100.
    assert matrix[4] == pytest.approx(100.0)
    assert matrix[5] == pytest.approx(100.0)
    # The pre-2.0.0 pypdfbox formula would have yielded (50, 30).
    assert matrix[4] != pytest.approx(50.0)
    assert matrix[5] != pytest.approx(30.0)


def test_overlay_transform_origin_overlay_box_output_is_unmoved() -> None:
    """Dropping the overlay-corner term is a no-op whenever the overlay's
    own MediaBox starts at the origin — the ordinary case — so ordinary
    output does not move."""
    page = _page_with_media_box(20.0, 30.0, 620.0, 830.0)
    origin_overlay = PDRectangle(0.0, 0.0, 400.0, 600.0)

    matrix = Overlay().calculate_affine_transform(page, origin_overlay)

    # Identical to what pypdfbox 1.x produced (overlay_llx/lly were 0).
    assert matrix == [1.0, 0.0, 0.0, 1.0, 120.0, 130.0]


def test_overlay_form_bbox_is_the_retranslated_rectangle() -> None:
    """Upstream's counterpart to the formula above: the form XObject's
    ``/BBox`` is ``overlayMediaBox.createRetranslatedRectangle()``
    (``[0 0 w h]``), which is what clips a non-origin overlay."""
    box = PDRectangle(50.0, 70.0, 450.0, 670.0)
    retranslated = box.create_retranslated_rectangle()

    assert retranslated.get_lower_left_x() == pytest.approx(0.0)
    assert retranslated.get_lower_left_y() == pytest.approx(0.0)
    assert retranslated.get_width() == pytest.approx(400.0)
    assert retranslated.get_height() == pytest.approx(600.0)

    source = inspect.getsource(Overlay._create_overlay_form_x_object)
    assert "create_retranslated_rectangle()" in source


# ---------------------------------------------------------------------------
# "Signing": appendRawCommands -> writeRawCommands(PDStream, String)
# ---------------------------------------------------------------------------


def test_write_raw_commands_is_the_4_0_shape() -> None:
    builder = PDVisibleSigBuilder()
    assert hasattr(builder, "write_raw_commands")
    # FORWARDREF: see note in tests/pdfparser/test_xref_parser_wave1389.py --
    # write_raw_commands is annotated with a TYPE_CHECKING-only PDStream.
    params = list(
        inspect.signature(
            builder.write_raw_commands,
            annotation_format=annotationlib.Format.FORWARDREF,
        ).parameters
    )
    assert params == ["stream", "commands"]


def test_write_raw_commands_writes_into_a_pd_stream_body() -> None:
    from pypdfbox.pdmodel.common.pd_stream import PDStream
    from pypdfbox.pdmodel.pd_document import PDDocument

    builder = PDVisibleSigBuilder()
    with PDDocument() as doc:
        pd_stream = PDStream(doc)
        builder.write_raw_commands(pd_stream, "q 1 0 0 1 0 0 cm /n0 Do Q\n")
        assert pd_stream.to_byte_array() == b"q 1 0 0 1 0 0 cm /n0 Do Q\n"


def test_append_raw_commands_is_removed_in_4_0() -> None:
    """ADOPTED in 2.0.0: the 3.x name is gone, and so is the forwarding
    branch inside ``write_raw_commands`` that existed only to support
    it."""
    builder = PDVisibleSigBuilder()
    assert not hasattr(builder, "append_raw_commands")
    assert not hasattr(PDVisibleSigBuilder, "append_raw_commands")
    # The forwarding branch is gone too: no call site remains.
    source = inspect.getsource(PDVisibleSigBuilder.write_raw_commands)
    assert "self.append_raw_commands(" not in source


def test_write_raw_commands_ignores_a_3_x_shaped_raw_stream() -> None:
    """Without the forwarding branch, a bare writable object (the 3.x
    ``OutputStream`` shape) is no longer accepted: ``write_raw_commands``
    needs a PDStream."""
    import io

    builder = PDVisibleSigBuilder()
    buf = io.BytesIO()
    builder.write_raw_commands(buf, "q Q")
    assert buf.getvalue() == b""


# ---------------------------------------------------------------------------
# "Deprecations": PDIndexed no-arg constructor + two removed methods
#
# ADOPTED in 2.0.0. Upstream 3.0.x marks all three
# ``@Deprecated ... will be removed in 4.0``; trunk deletes the two
# methods outright and makes the no-arg constructor ``private``, moving
# the COSArray construction into the ``create`` factory.
# ---------------------------------------------------------------------------


def test_pd_indexed_no_arg_construction_is_gone() -> None:
    """4.0 made ``PDIndexed()`` private. There is no public no-argument
    construction path — the array is required."""
    with pytest.raises(TypeError, match="array"):
        PDIndexed()  # type: ignore[call-arg]

    params = list(inspect.signature(PDIndexed.__init__).parameters)
    assert params == ["self", "array"]
    assert (
        inspect.signature(PDIndexed.__init__).parameters["array"].default
        is inspect.Parameter.empty
    )


def test_pd_indexed_set_base_color_space_and_set_high_value_are_gone() -> None:
    """Both were deleted on trunk."""
    assert not hasattr(PDIndexed, "set_base_color_space")
    assert not hasattr(PDIndexed, "set_high_value")


def test_pd_indexed_create_factory_is_the_4_0_construction_path() -> None:
    """4.0 moved the COSArray construction into ``create`` (PDFBOX-6192)."""
    from pypdfbox.cos import COSArray
    from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB

    indexed = PDIndexed.create(
        PDDeviceRGB.INSTANCE, 1, b"\xff\x00\x00\x00\xff\x00"
    )
    assert indexed.get_name() == "Indexed"
    assert indexed.get_hival() == 1
    assert indexed.get_base_color_space() is PDDeviceRGB.INSTANCE
    cos = indexed.get_cos_object()
    assert isinstance(cos, COSArray)
    assert cos.size() == 4
    assert cos.get_object(0).get_name() == "Indexed"


def test_pd_indexed_array_constructor_stays_public() -> None:
    """``PDIndexed(COSArray)`` is public in both 3.0 and trunk."""
    from pypdfbox.cos import COSArray, COSInteger, COSName, COSNull
    from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB

    arr = COSArray()
    arr.add(COSName.get_pdf_name("Indexed"))
    arr.add(PDDeviceRGB.INSTANCE.get_cos_object())
    arr.add(COSInteger.get(255))
    arr.add(COSNull.NULL)

    indexed = PDIndexed(arr)
    assert indexed.get_name() == "Indexed"
    assert indexed.get_hival() == 255
