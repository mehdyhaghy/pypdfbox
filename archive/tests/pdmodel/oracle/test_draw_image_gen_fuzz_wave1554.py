"""Live PDFBox differential FUZZING for PDPageContentStream IMAGE + FORM drawing.

Sibling to ``test_content_gen_oracle.py`` (fixed drawing script) and the
text/path/colour generation fuzz of wave 1549. Here we drive a battery of
~30 ``draw_image`` / ``draw_form`` edge cases and assert the EXACT emitted
content-stream bytes plus the page ``/XObject`` resource keys match Apache
PDFBox 3.0.7 line-for-line.

The Java side is ``oracle/probes/DrawImageGenFuzzProbe.java``. Each line is::

    <case-name>\tOK\t<base64-of-stream-bytes>\t<xobject-keys-csv>
    <case-name>\tEXC\t<exception-class>\t<message>

This pins BOTH SIDES:

- emitted ``q`` / ``cm`` / ``/Name Do`` / ``Q`` bytes, including the float
  formatter on zero / negative / fractional / huge / tiny w/h and the
  singular / extreme / negative / rotate / shear matrices;
- the resource-key allocation (``Im1``, ``Im1``/``Im2``, ``Form1``/``Form2``)
  and reuse when the same XObject is drawn twice;
- the NaN / +Inf / -Inf operand guard (raise) and the text-block guard.

A number-format or resource-naming difference is a REAL divergence. The
expected values below are the literal PDFBox-3.0.7 oracle output (captured
2026-06) so the test is self-contained when the live jar is absent; when the
jar IS present the ``requires_oracle`` test re-derives them live and the two
must agree.

Notable parity point pinned here: upstream ``drawForm(PDFormXObject)`` emits a
BARE ``/<key> Do`` with no surrounding ``q`` / ``cm`` / ``Q`` (the caller owns
the graphics state). pypdfbox previously wrapped the origin case in ``q``/``Q``;
fixed in wave 1554 to match.
"""

from __future__ import annotations

import base64

import pytest

from pypdfbox.cos import COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from tests.oracle.harness import oracle_available, requires_oracle, run_probe_text

_INF = float("inf")
_NAN = float("nan")


def _image(doc: PDDocument) -> PDImageXObject:
    """A 4x3 Image XObject — same intrinsic size as the probe's LosslessFactory
    image (the only image property the writer reads is /Width and /Height)."""
    stream = COSStream()
    stream.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Image"))
    stream.set_int(COSName.get_pdf_name("Width"), 4)
    stream.set_int(COSName.get_pdf_name("Height"), 3)
    return PDImageXObject(stream)


def _form(doc: PDDocument) -> PDFormXObject:
    return PDFormXObject(COSStream())


def _project(case: str, script) -> tuple[str, str, str]:
    """Run one drawing script with pypdfbox; project the canonical line fields.

    Returns ``(kind, field3, field4)`` where ``kind`` is ``"OK"`` / ``"EXC"``.
    """
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        try:
            cs = PDPageContentStream(doc, page)
            try:
                script(doc, page, cs)
            finally:
                cs.close()
        except Exception as exc:  # noqa: BLE001 - project the exception like the probe
            return ("EXC", type(exc).__name__, str(exc))
        body = _stream_bytes(page)
        keys = ",".join(
            n.get_name() for n in page.get_resources().get_x_object_names()
        )
        return ("OK", base64.b64encode(body).decode("ascii"), keys)
    finally:
        doc.close()


def _stream_bytes(page: PDPage) -> bytes:
    stream = page.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Contents"))
    return bytes(stream.to_byte_array())


# ----------------------------------------------------------------------------
# The drawing scripts — IDENTICAL sequences to DrawImageGenFuzzProbe.main.
# ----------------------------------------------------------------------------

_SCRIPTS: dict[str, object] = {
    "xywh_basic": lambda d, p, cs: cs.draw_image(_image(d), 10, 20, 100, 50),
    "xywh_zero_size": lambda d, p, cs: cs.draw_image(_image(d), 5, 5, 0, 0),
    "xywh_negative_size": lambda d, p, cs: cs.draw_image(_image(d), 5, 5, -100, -50),
    "xywh_fractional": lambda d, p, cs: cs.draw_image(_image(d), 1.5, 2.5, 12.345, 6.789),
    "xywh_huge": lambda d, p, cs: cs.draw_image(_image(d), 0, 0, 1.0e9, 1.0e9),
    "xywh_tiny": lambda d, p, cs: cs.draw_image(_image(d), 0.000005, 0, 0.000004, 0.123455),
    "xywh_negative_origin": lambda d, p, cs: cs.draw_image(_image(d), -50, -60, 100, 50),
    "xy_basic": lambda d, p, cs: cs.draw_image(_image(d), 10, 20),
    "xy_origin": lambda d, p, cs: cs.draw_image(_image(d), 0, 0),
    "xy_fractional": lambda d, p, cs: cs.draw_image(_image(d), 7.25, 11.75),
    "matrix_basic": lambda d, p, cs: cs.draw_image(_image(d), (2, 0.5, 0.25, 3, 7, 11)),
    "matrix_identity": lambda d, p, cs: cs.draw_image(_image(d), (1, 0, 0, 1, 0, 0)),
    "matrix_singular": lambda d, p, cs: cs.draw_image(_image(d), (0, 0, 0, 0, 0, 0)),
    "matrix_negative_scale": lambda d, p, cs: cs.draw_image(_image(d), (-100, 0, 0, -50, 50, 60)),
    "matrix_rotate": lambda d, p, cs: cs.draw_image(_image(d), (0, 100, -100, 0, 50, 60)),
    "matrix_extreme": lambda d, p, cs: cs.draw_image(
        _image(d), (1.0e6, 0, 0, 1.0e6, -50000.25, 0.000001)
    ),
    "matrix_shear": lambda d, p, cs: cs.draw_image(_image(d), (1, 0.5, 0.5, 1, 0, 0)),
    "xy_nan_x": lambda d, p, cs: cs.draw_image(_image(d), _NAN, 20),
    "xy_pos_inf_y": lambda d, p, cs: cs.draw_image(_image(d), 10, _INF),
    "xywh_neg_inf_w": lambda d, p, cs: cs.draw_image(_image(d), 0, 0, -_INF, 50),
    "matrix_nan_e": lambda d, p, cs: cs.draw_image(_image(d), (1, 0, 0, 1, _NAN, 0)),
    "draw_form_basic": lambda d, p, cs: cs.draw_form(_form(d)),
    "same_image_twice": lambda d, p, cs: _same_image_twice(d, cs),
    "two_distinct_images": lambda d, p, cs: _two_distinct_images(d, cs),
    "image_then_form": lambda d, p, cs: _image_then_form(d, cs),
    "form_twice_same": lambda d, p, cs: _form_twice_same(d, cs),
    "draw_image_in_text_block": lambda d, p, cs: _draw_image_in_text_block(d, cs),
    "draw_form_in_text_block": lambda d, p, cs: _draw_form_in_text_block(d, cs),
    "save_then_draw_image": lambda d, p, cs: _save_then_draw_image(d, cs),
}


def _same_image_twice(d, cs):
    im = _image(d)
    cs.draw_image(im, 0, 0, 10, 10)
    cs.draw_image(im, 20, 20, 10, 10)


def _two_distinct_images(d, cs):
    cs.draw_image(_image(d), 0, 0, 10, 10)
    cs.draw_image(_image(d), 20, 20, 10, 10)


def _image_then_form(d, cs):
    cs.draw_image(_image(d), 0, 0, 10, 10)
    cs.draw_form(_form(d))


def _form_twice_same(d, cs):
    f = _form(d)
    cs.draw_form(f)
    cs.draw_form(f)


def _draw_image_in_text_block(d, cs):
    cs.begin_text()
    cs.draw_image(_image(d), 0, 0)


def _draw_form_in_text_block(d, cs):
    cs.begin_text()
    cs.draw_form(_form(d))


def _save_then_draw_image(d, cs):
    cs.save_graphics_state()
    cs.draw_image(_image(d), 1, 2, 3, 4)
    cs.restore_graphics_state()


# ----------------------------------------------------------------------------
# Frozen PDFBox-3.0.7 oracle output (captured 2026-06). Field layout per case:
#   OK  -> (b64 stream bytes, xobject keys csv)
#   EXC -> ("EXC", exception substring) — pypdfbox raises ValueError where Java
#          raises IllegalArgumentException / IllegalStateException; we match on
#          the OK/EXC classification + that pypdfbox raises, not the Java class.
# ----------------------------------------------------------------------------

_EXPECTED_BYTES: dict[str, bytes] = {
    "xywh_basic": b"q\n100 0 0 50 10 20 cm\n/Im1 Do\nQ\n",
    "xywh_zero_size": b"q\n0 0 0 0 5 5 cm\n/Im1 Do\nQ\n",
    "xywh_negative_size": b"q\n-100 0 0 -50 5 5 cm\n/Im1 Do\nQ\n",
    "xywh_fractional": b"q\n12.345 0 0 6.789 1.5 2.5 cm\n/Im1 Do\nQ\n",
    "xywh_huge": b"q\n1000000000 0 0 1000000000 0 0 cm\n/Im1 Do\nQ\n",
    "xywh_tiny": b"q\n0 0 0 0.12346 0 0 cm\n/Im1 Do\nQ\n",
    "xywh_negative_origin": b"q\n100 0 0 50 -50 -60 cm\n/Im1 Do\nQ\n",
    "xy_basic": b"q\n4 0 0 3 10 20 cm\n/Im1 Do\nQ\n",
    "xy_origin": b"q\n4 0 0 3 0 0 cm\n/Im1 Do\nQ\n",
    "xy_fractional": b"q\n4 0 0 3 7.25 11.75 cm\n/Im1 Do\nQ\n",
    "matrix_basic": b"q\n2 0.5 0.25 3 7 11 cm\n/Im1 Do\nQ\n",
    "matrix_identity": b"q\n1 0 0 1 0 0 cm\n/Im1 Do\nQ\n",
    "matrix_singular": b"q\n0 0 0 0 0 0 cm\n/Im1 Do\nQ\n",
    "matrix_negative_scale": b"q\n-100 0 0 -50 50 60 cm\n/Im1 Do\nQ\n",
    "matrix_rotate": b"q\n0 100 -100 0 50 60 cm\n/Im1 Do\nQ\n",
    "matrix_extreme": b"q\n1000000 0 0 1000000 -50000.25 0 cm\n/Im1 Do\nQ\n",
    "matrix_shear": b"q\n1 0.5 0.5 1 0 0 cm\n/Im1 Do\nQ\n",
    "draw_form_basic": b"/Form1 Do\n",
    "same_image_twice": (
        b"q\n10 0 0 10 0 0 cm\n/Im1 Do\nQ\nq\n10 0 0 10 20 20 cm\n/Im1 Do\nQ\n"
    ),
    "two_distinct_images": (
        b"q\n10 0 0 10 0 0 cm\n/Im1 Do\nQ\nq\n10 0 0 10 20 20 cm\n/Im2 Do\nQ\n"
    ),
    "image_then_form": b"q\n10 0 0 10 0 0 cm\n/Im1 Do\nQ\n/Form2 Do\n",
    "form_twice_same": b"/Form1 Do\n/Form1 Do\n",
    "save_then_draw_image": b"q\nq\n3 0 0 4 1 2 cm\n/Im1 Do\nQ\nQ\n",
}

_EXPECTED_KEYS: dict[str, str] = {
    "xywh_basic": "Im1",
    "xywh_zero_size": "Im1",
    "xywh_negative_size": "Im1",
    "xywh_fractional": "Im1",
    "xywh_huge": "Im1",
    "xywh_tiny": "Im1",
    "xywh_negative_origin": "Im1",
    "xy_basic": "Im1",
    "xy_origin": "Im1",
    "xy_fractional": "Im1",
    "matrix_basic": "Im1",
    "matrix_identity": "Im1",
    "matrix_singular": "Im1",
    "matrix_negative_scale": "Im1",
    "matrix_rotate": "Im1",
    "matrix_extreme": "Im1",
    "matrix_shear": "Im1",
    "draw_form_basic": "Form1",
    "same_image_twice": "Im1",
    "two_distinct_images": "Im1,Im2",
    "image_then_form": "Im1,Form2",
    "form_twice_same": "Form1",
    "save_then_draw_image": "Im1",
}

_EXPECTED_EXC = {
    "xy_nan_x",
    "xy_pos_inf_y",
    "xywh_neg_inf_w",
    "matrix_nan_e",
    "draw_image_in_text_block",
    "draw_form_in_text_block",
}


@pytest.mark.parametrize("case", sorted(_EXPECTED_BYTES))
def test_draw_image_bytes_match_frozen_oracle(case: str) -> None:
    kind, field3, keys = _project(case, _SCRIPTS[case])
    assert kind == "OK", f"{case}: expected OK, got {kind} {field3}"
    body = base64.b64decode(field3)
    assert body == _EXPECTED_BYTES[case], (
        f"{case}: bytes {body!r} != oracle {_EXPECTED_BYTES[case]!r}"
    )
    assert keys == _EXPECTED_KEYS[case], (
        f"{case}: keys {keys!r} != oracle {_EXPECTED_KEYS[case]!r}"
    )


@pytest.mark.parametrize("case", sorted(_EXPECTED_EXC))
def test_draw_image_guards_raise(case: str) -> None:
    kind, cls, msg = _project(case, _SCRIPTS[case])
    assert kind == "EXC", f"{case}: expected raise, got {kind}"


@requires_oracle
def test_draw_image_matches_live_oracle() -> None:
    """When the live jar is present, re-derive every frozen value and assert the
    frozen expectations still match upstream PDFBox 3.0.7 exactly."""
    raw = run_probe_text("DrawImageGenFuzzProbe")
    live: dict[str, tuple[str, ...]] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        live[parts[0]] = tuple(parts[1:])

    for case, expected in _EXPECTED_BYTES.items():
        kind, b64, keys = live[case]
        assert kind == "OK", f"{case}: live oracle {kind} (frozen expected OK)"
        assert base64.b64decode(b64) == expected, f"{case}: live bytes drift"
        assert keys == _EXPECTED_KEYS[case], f"{case}: live keys drift"

    for case in _EXPECTED_EXC:
        assert live[case][0] == "EXC", f"{case}: live oracle did not raise"


@pytest.mark.skipif(not oracle_available(), reason="oracle jar absent")
def test_pypdfbox_matches_live_oracle_line_for_line() -> None:
    """Strongest check: drive pypdfbox over every case and compare its
    projection to the live PDFBox projection line-for-line."""
    raw = run_probe_text("DrawImageGenFuzzProbe")
    live: dict[str, tuple[str, ...]] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        live[parts[0]] = tuple(parts[1:])

    for case, script in _SCRIPTS.items():
        kind, field3, keys = _project(case, script)
        if kind == "OK":
            assert live[case][0] == "OK", f"{case}: pypdfbox OK, java {live[case][0]}"
            assert base64.b64decode(field3) == base64.b64decode(live[case][1]), (
                f"{case}: stream-byte divergence"
            )
            assert keys == live[case][2], f"{case}: resource-key divergence"
        else:
            assert live[case][0] == "EXC", (
                f"{case}: pypdfbox raised but java returned {live[case][0]}"
            )
