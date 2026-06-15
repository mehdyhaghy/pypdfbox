"""Live PDFBox differential parity for the model-layer XObject factory and
``PDFormXObject`` / ``PDTransparencyGroupAttributes`` accessors.

``oracle/probes/FormXObjectModelProbe.java`` exercises the same surface in
authoritative Apache PDFBox 3.0.7 and emits ``key=value`` lines:

* ``PDXObject.createXObject`` dispatch — ``/Subtype /Form`` →
  ``PDFormXObject``, ``/Form`` + ``/Group /S /Transparency`` →
  ``PDTransparencyGroup``, ``/Group`` with a non-Transparency ``/S`` →
  plain ``PDFormXObject``, unknown subtype / missing subtype / non-stream
  base → exception, ``null`` base → ``null``.
* ``PDFormXObject`` fresh-construction dict shape (``/Type /XObject``,
  ``/Subtype /Form``, ``/FormType`` default 1, ``getBBox`` / ``getResources``
  default null, ``getStructParents`` default -1).
* ``getMatrix`` graceful-degradation to identity (absent, size<6,
  non-numeric entry).
* ``getResources`` PDFBOX-4372 broken-non-dict → empty ``PDResources``.
* ``getBBox`` non-array → null.
* ``PDTransparencyGroupAttributes`` defaults (``/S /Transparency`` from the
  no-arg ctor, ``isIsolated`` / ``isKnockout`` false, ``getColorSpace``
  null; empty-dict ctor → no ``/S``, colour space null).

pypdfbox reads/builds the SAME shapes and must reproduce identical values.
Two Java/Python idiom differences are accepted and asserted explicitly:
``null`` ↔ ``None`` in the "Invalid XObject Subtype: …" message, and the
Java fully-qualified class name vs Python short name in the
"Unexpected object type: …" message.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (
    PDTransparencyGroup,
)
from pypdfbox.pdmodel.graphics.form.pd_transparency_group_attributes import (
    PDTransparencyGroupAttributes,
)
from pypdfbox.pdmodel.graphics.pd_x_object import PDXObject
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]
_GROUP = COSName.get_pdf_name("Group")
_S = COSName.get_pdf_name("S")
_MATRIX = COSName.get_pdf_name("Matrix")
_BBOX = COSName.get_pdf_name("BBox")
_RESOURCES = COSName.RESOURCES  # type: ignore[attr-defined]


def _form_stream() -> COSStream:
    stream = COSStream()
    stream.set_name(_SUBTYPE, "Form")  # type: ignore[attr-defined]
    return stream


def _oracle() -> dict[str, str]:
    text = run_probe_text("FormXObjectModelProbe")
    out: dict[str, str] = {}
    for line in text.splitlines():
        if not line:
            continue
        key, _, value = line.partition("=")
        out[key] = value
    return out


@requires_oracle
def test_form_xobject_model_matches_pdfbox() -> None:
    oracle = _oracle()

    # --- fresh construction dict shape ---
    doc = PDDocument()
    fresh = PDFormXObject(doc)
    fd = fresh.get_cos_object()
    assert fd.get_name(COSName.TYPE) == oracle["fresh.Type"] == "XObject"
    assert fd.get_name(_SUBTYPE) == oracle["fresh.Subtype"] == "Form"
    assert str(fresh.get_form_type()) == oracle["fresh.FormType"] == "1"
    assert oracle["fresh.BBox"] == "null"
    assert fresh.get_b_box() is None
    assert oracle["fresh.Resources"] == "null"
    assert fresh.get_resources() is None
    assert (
        str(fresh.get_struct_parents()) == oracle["fresh.StructParents"] == "-1"
    )

    # --- factory dispatch ---
    assert (
        type(PDXObject.create_x_object(_form_stream())).__name__
        == oracle["dispatch.form.class"]
        == "PDFormXObject"
    )

    s2 = _form_stream()
    grp = COSDictionary()
    grp.set_name(_S, "Transparency")
    s2.set_item(_GROUP, grp)
    obj2 = PDXObject.create_x_object(s2)
    assert isinstance(obj2, PDTransparencyGroup)
    assert type(obj2).__name__ == oracle["dispatch.tgroup.class"]

    s3 = _form_stream()
    grp3 = COSDictionary()
    grp3.set_name(_S, "Foo")
    s3.set_item(_GROUP, grp3)
    assert (
        type(PDXObject.create_x_object(s3)).__name__
        == oracle["dispatch.groupNonTransparency.class"]
        == "PDFormXObject"
    )

    # unknown subtype: Java "Invalid XObject Subtype: Bogus"
    s4 = COSStream()
    s4.set_name(_SUBTYPE, "Bogus")  # type: ignore[attr-defined]
    with pytest.raises(OSError) as ei4:
        PDXObject.create_x_object(s4)
    assert str(ei4.value) == oracle["dispatch.unknown.msg"]
    assert oracle["dispatch.unknown.msg"] == "Invalid XObject Subtype: Bogus"

    # missing subtype: Java concatenates the absent name as "null"; wave 1532
    # aligned pypdfbox to emit the same literal (plain string formatting, not a
    # Java FQN, so exactly alignable). Message now identical.
    s5 = COSStream()
    with pytest.raises(OSError) as ei5:
        PDXObject.create_x_object(s5)
    assert oracle["dispatch.missing.msg"] == "Invalid XObject Subtype: null"
    assert str(ei5.value) == "Invalid XObject Subtype: null"

    # non-stream base: Java uses the FQN, Python the short class name —
    # accepted idiom difference; the prefix is identical.
    with pytest.raises(OSError) as ei6:
        PDXObject.create_x_object(COSDictionary())
    assert (
        oracle["dispatch.nonstream.msg"]
        == "Unexpected object type: org.apache.pdfbox.cos.COSDictionary"
    )
    assert str(ei6.value) == "Unexpected object type: COSDictionary"

    # null base
    assert oracle["dispatch.null"] == "null"
    assert PDXObject.create_x_object(None) is None

    # --- getMatrix graceful degradation ---
    identity = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert oracle["matrix.default"] == "[1.0,0.0,0.0,1.0,0.0,0.0]"
    assert PDFormXObject(_form_stream()).get_matrix() == identity

    sm = _form_stream()
    sm.set_item(_MATRIX, COSArray([COSFloat(2.0)] * 4))
    assert oracle["matrix.short4"] == "[1.0,0.0,0.0,1.0,0.0,0.0]"
    assert PDFormXObject(sm).get_matrix() == identity

    sm2 = _form_stream()
    sm2.set_item(
        _MATRIX, COSArray([COSFloat(1.0)] * 5 + [COSName.get_pdf_name("X")])
    )
    assert oracle["matrix.nonNumeric"] == "[1.0,0.0,0.0,1.0,0.0,0.0]"
    assert PDFormXObject(sm2).get_matrix() == identity

    # --- getResources PDFBOX-4372: broken non-dict → empty PDResources ---
    sr = _form_stream()
    sr.set_item(_RESOURCES, COSInteger.get(5))
    assert oracle["resources.brokenNotDict"] == "PDResources"
    assert type(PDFormXObject(sr).get_resources()).__name__ == "PDResources"

    # --- getBBox non-array → null ---
    sb = _form_stream()
    sb.set_item(_BBOX, COSInteger.get(7))
    assert oracle["bbox.nonArray"] == "null"
    assert PDFormXObject(sb).get_b_box() is None

    # --- transparency-group attributes defaults ---
    tga = PDTransparencyGroupAttributes()
    assert tga.get_subtype() == oracle["tga.default.S"] == "Transparency"
    assert oracle["tga.default.isolated"] == "false"
    assert tga.is_isolated() is False
    assert oracle["tga.default.knockout"] == "false"
    assert tga.is_knockout() is False
    assert oracle["tga.default.colorSpace"] == "null"
    assert tga.get_color_space() is None

    tga2 = PDTransparencyGroupAttributes(COSDictionary())
    assert oracle["tga.empty.colorSpace"] == "null"
    assert tga2.get_color_space() is None
    assert oracle["tga.empty.isolated"] == "false"
    assert tga2.is_isolated() is False

    # --- typed getGroup with no /Group → null ---
    assert oracle["form.getGroup.noGroup"] == "null"
    assert PDFormXObject(_form_stream()).get_group_attributes() is None
