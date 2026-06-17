"""Live Apache PDFBox differential parity for the WIDGET + LINK annotation
appearance & appearance-state machinery (wave 1434).

Surface under test (``pypdfbox/pdmodel/interactive/annotation/``):

  * :class:`PDAnnotationWidget` — ``get_appearance_state`` (``/AS``),
    ``get_appearance`` -> :class:`PDAppearanceDictionary`,
    ``get_appearance_characteristics`` -> ``/MK`` (``/BG`` background,
    ``/BC`` border colour, ``/CA`` caption, ``/R`` rotation).
  * :class:`PDAppearanceDictionary` / :class:`PDAppearanceEntry` — the ``/AP``
    ``/N`` / ``/D`` entries; single appearance stream vs state-keyed
    subdictionary (``is_sub_dictionary`` / ``get_sub_dictionary``), and the
    spec ``/N``-fallback when ``/D`` is absent (``get_down_appearance``).
  * :class:`PDAnnotationLink` — ``get_highlight_mode`` (``/H``),
    ``get_border_style`` (``/BS`` style + width), URI action subtype.

Why this is a NON-colliding surface
------------------------------------
Prior appearance probes targeted the *generated* ``/AP /N`` form-XObject of
MARKUP annotations: ``AnnotApAppearanceProbe`` (wave 1429 — container shape:
``/Type`` ``/Subtype`` ``/FormType`` ``/Matrix`` ``/Resources``) and
``AnnotAppearGenProbe`` / ``AnnotAppear2Probe`` (content-stream operator
sequences). None inspected the WIDGET/LINK *appearance-state machinery*: the
``/AS`` value, the ``/AP`` sub-dictionary STATE KEYS (single-stream vs
state-keyed entry), the ``/MK`` characteristics, the ``/D`` (down) appearance,
or the link ``/H`` + border + action.

The fixture is built ONCE by pypdfbox (no upstream resource carries this exact
shape) and saved to ``tmp_path``; the same file is then read by BOTH
implementations, so the build itself is part of the differential surface. Each
implementation emits canonical facts and the two must be byte-identical.

High-value invariants
---------------------
  * appearance-state RESOLUTION — ``/AS`` selects the matching sub-dictionary
    stream; the on-state ``/BBox`` is the one keyed by ``/AS``;
  * sub-dictionary keying — a state-keyed entry reports ``is_sub_dictionary``
    and the exact (sorted) state-key set ``{Off, On}``;
  * ``/MK`` parsing — ``/BG`` / ``/BC`` colour components (canonical floats),
    ``/CA`` caption, ``/R`` rotation;
  * ``/D`` presence vs ``/N`` fallback — an explicit ``/D`` key is reported as
    present, while a missing ``/D`` resolves to ``/N`` (spec fallback) under
    BOTH implementations;
  * link ``/H`` mode + ``/BS`` style/width + action ``/S`` subtype.

Decorated ``@requires_oracle`` so they skip on machines without Java + jar.
Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.common import PDRectangle
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationLink,
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (  # noqa: E501
    PDAppearanceCharacteristicsDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "WidgetApProbe"

_BBOX = COSName.get_pdf_name("BBox")
_TYPE = COSName.get_pdf_name("Type")
_SUBTYPE = COSName.get_pdf_name("Subtype")
_FORMTYPE = COSName.get_pdf_name("FormType")
_AP = COSName.get_pdf_name("AP")
_D = COSName.get_pdf_name("D")
_A = COSName.get_pdf_name("A")
_S = COSName.get_pdf_name("S")
_ON = COSName.get_pdf_name("On")
_OFF = COSName.get_pdf_name("Off")


# --------------------------------------------------------------------------- #
# canonical float rendering — mirrors WidgetApProbe.canonFloat (Java)
# --------------------------------------------------------------------------- #
def _canon_float(value: float) -> str:
    text = f"{round(float(value), 3):.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        text = "0"
    return text


# --------------------------------------------------------------------------- #
# pypdfbox fixture builder — the build is part of the differential surface
# --------------------------------------------------------------------------- #
def _ap_stream(x1: float, y1: float) -> COSStream:
    """A minimal valid appearance form-XObject stream with a /BBox."""
    s = COSStream()
    s.set_item(_TYPE, COSName.get_pdf_name("XObject"))
    s.set_item(_SUBTYPE, COSName.get_pdf_name("Form"))
    s.set_int(_FORMTYPE, 1)
    s.set_item(_BBOX, COSArray([COSFloat(0), COSFloat(0), COSFloat(x1), COSFloat(y1)]))
    with s.create_output_stream() as out:
        out.write(b"q Q\n")
    return s


def _build_fixture(path: Path) -> None:
    """Build a PDF with (a) a checkbox widget with /MK (BG/BC/CA) + state-keyed
    /AP /N (On/Off) + /AS=On; (b) a widget with state-keyed /N and /D (down)
    sub-dicts + /AS=Off; (c) a link with /H=push + dashed border + URI action.
    """
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)

        # (a) checkbox/pushbutton widget: /MK + state-keyed /AP /N + /AS.
        cb = PDAnnotationWidget()
        cb.set_rectangle(PDRectangle(50, 700, 100, 750))
        cb.set_page(page)
        mk = PDAppearanceCharacteristicsDictionary()
        mk.set_background(COSArray([COSFloat(0.75), COSFloat(0.75), COSFloat(0.75)]))
        mk.set_border_colour(COSArray([COSFloat(0), COSFloat(0), COSFloat(0)]))
        mk.set_normal_caption("4")  # ZapfDingbats check glyph
        mk.set_rotation(0)
        cb.set_appearance_characteristics(mk)
        ap = PDAppearanceDictionary()
        n_sub = COSDictionary()
        n_sub.set_item(_ON, _ap_stream(50, 50))
        n_sub.set_item(_OFF, _ap_stream(50, 50))
        ap.set_normal_appearance(n_sub)
        cb.set_appearance(ap)
        cb.set_appearance_state("On")
        page.add_annotation(cb)

        # (b) widget with state-keyed /N and /D (down) sub-dicts.
        btn = PDAnnotationWidget()
        btn.set_rectangle(PDRectangle(150, 700, 250, 750))
        btn.set_page(page)
        ap2 = PDAppearanceDictionary()
        n2 = COSDictionary()
        n2.set_item(_ON, _ap_stream(100, 50))
        n2.set_item(_OFF, _ap_stream(100, 50))
        ap2.set_normal_appearance(n2)
        d2 = COSDictionary()
        d2.set_item(_ON, _ap_stream(100, 50))
        d2.set_item(_OFF, _ap_stream(100, 50))
        ap2.set_down_appearance(d2)
        btn.set_appearance(ap2)
        btn.set_appearance_state("Off")
        page.add_annotation(btn)

        # (c) link annotation with /H highlight + border style + URI action.
        link = PDAnnotationLink()
        link.set_rectangle(PDRectangle(50, 600, 300, 620))
        link.set_page(page)
        link.set_highlight_mode(PDAnnotationLink.HIGHLIGHT_MODE_PUSH)
        bs = PDBorderStyleDictionary()
        bs.set_width(2)
        bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
        link.set_border_style(bs)
        uri = PDActionURI()
        uri.set_uri("https://example.com/")
        link.set_action(uri)
        page.add_annotation(link)

        doc.save(str(path))
    finally:
        doc.close()


# --------------------------------------------------------------------------- #
# Java probe driver — parse WidgetApProbe read-mode output into records
# --------------------------------------------------------------------------- #
def _parse_java(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        if raw.startswith("ANNOT "):
            current = {"subtype": raw[len("ANNOT ") :]}
        elif raw == "END":
            assert current is not None
            records.append(current)
            current = None
        elif current is not None:
            key, _, value = raw.partition(" ")
            current[key] = value
    return records


def _java_records(path: Path) -> list[dict[str, str]]:
    return _parse_java(run_probe_text(_PROBE, "read", str(path)))


# --------------------------------------------------------------------------- #
# pypdfbox fact extraction — mirrors WidgetApProbe exactly
# --------------------------------------------------------------------------- #
def _sub_keys(entry) -> str:
    if entry is None or not entry.is_sub_dictionary():
        return "-"
    keys = sorted(entry.get_sub_dictionary().keys())
    return " ".join(keys) if keys else "-"


def _kind(entry) -> str:
    if entry is None:
        return "none"
    return "subdict" if entry.is_sub_dictionary() else "stream"


def _color_array(color) -> str:
    if color is None:
        return "none"
    arr = color.to_cos_array()
    comps = [
        _canon_float(arr.get_object(i).value)
        for i in range(arr.size())
        if hasattr(arr.get_object(i), "value")
    ]
    return " ".join(comps) if comps else "none"


def _on_bbox(widget, normal) -> str:
    if normal is None:
        return "none"
    if normal.is_sub_dictionary():
        state = widget.get_appearance_state()
        if state is None:
            return "none"
        stream = normal.get_sub_dictionary().get(state)
    else:
        stream = normal.get_appearance_stream()
    if stream is None:
        return "none"
    bbox = stream.get_bbox()
    if bbox is None:
        return "none"
    return ",".join(
        _canon_float(v)
        for v in (
            bbox.get_lower_left_x(),
            bbox.get_lower_left_y(),
            bbox.get_upper_right_x(),
            bbox.get_upper_right_y(),
        )
    )


def _py_widget_facts(widget: PDAnnotationWidget) -> dict[str, str]:
    state = widget.get_appearance_state()
    ap = widget.get_appearance()
    normal = ap.get_normal_appearance() if ap is not None else None
    down = ap.get_down_appearance() if ap is not None else None

    cos = widget.get_cos_object()
    ap_base = cos.get_dictionary_object(_AP)
    d_present = isinstance(ap_base, COSDictionary) and ap_base.contains_key(_D)

    mk = widget.get_appearance_characteristics()
    caption = mk.get_normal_caption() if mk is not None else None
    return {
        "subtype": "Widget",
        "AS": "none" if state is None else state,
        "NKIND": _kind(normal),
        "NKEYS": _sub_keys(normal),
        "DPRESENT": "1" if d_present else "0",
        "DKIND": _kind(down),
        "DKEYS": _sub_keys(down),
        "MKBG": "none" if mk is None else _color_array(mk.get_background()),
        "MKBC": "none" if mk is None else _color_array(mk.get_border_colour()),
        "MKCA": "none" if (mk is None or caption is None) else caption,
        "MKR": str(0 if mk is None else mk.get_rotation()),
        "ONBBOX": _on_bbox(widget, normal),
    }


def _py_link_facts(link: PDAnnotationLink) -> dict[str, str]:
    bs = link.get_border_style()
    cos = link.get_cos_object()
    action = cos.get_dictionary_object(_A)
    if isinstance(action, COSDictionary):
        s = action.get_dictionary_object(_S)
        asubtype = s.get_name() if isinstance(s, COSName) else "none"
    else:
        asubtype = "none"
    return {
        "subtype": "Link",
        "H": link.get_highlight_mode(),
        "BSSTYLE": "none" if bs is None else bs.get_style(),
        "BSWIDTH": "none" if bs is None else _canon_float(bs.get_width()),
        "ASUBTYPE": asubtype,
    }


def _py_records(path: Path) -> list[dict[str, str]]:
    doc = PDDocument.load(str(path))
    try:
        out: list[dict[str, str]] = []
        for page in doc.get_pages():
            for annot in page.get_annotations():
                if isinstance(annot, PDAnnotationWidget):
                    out.append(_py_widget_facts(annot))
                elif isinstance(annot, PDAnnotationLink):
                    out.append(_py_link_facts(annot))
        return out
    finally:
        doc.close()


def _qpdf_ok(path: Path) -> bool:
    """``qpdf --check`` passes (warnings tolerated, hard errors not)."""
    if shutil.which("qpdf") is None:
        return True
    result = subprocess.run(
        ["qpdf", "--check", str(path)],
        capture_output=True,
        text=True,
    )
    # qpdf exit codes: 0 = clean, 3 = warnings only, 2 = errors.
    return result.returncode in (0, 3)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
@requires_oracle
def test_widget_link_appearance_facts_match_pdfbox(tmp_path: Path) -> None:
    """Every canonical fact pypdfbox reports for the widget + link annotations
    equals what Apache PDFBox reports on the same pypdfbox-built fixture —
    ``/AS``, ``/AP`` sub-dict kind + state keys, ``/MK`` BG/BC/CA/R, ``/D``
    presence + resolution, on-state ``/BBox``, link ``/H`` + border + action."""
    fixture = tmp_path / "widget_ap.pdf"
    _build_fixture(fixture)
    assert _qpdf_ok(fixture)

    java = _java_records(fixture)
    py = _py_records(fixture)

    assert len(java) == 3, f"unexpected probe annotation count: {len(java)}"
    assert len(py) == len(java)
    assert py == java


@requires_oracle
def test_appearance_state_subdict_keying_matches_pdfbox(tmp_path: Path) -> None:
    """The state-keyed ``/AP /N`` entry reports ``is_sub_dictionary`` and the
    exact (sorted) state-key set ``{Off, On}``; ``/AS`` selects the matching
    on-state stream — identical to PDFBox (the single-stream-vs-state-keyed
    high-value case)."""
    fixture = tmp_path / "widget_ap.pdf"
    _build_fixture(fixture)
    java_list = [r for r in _java_records(fixture) if r["subtype"] == "Widget"]
    py = [r for r in _py_records(fixture) if r["subtype"] == "Widget"]

    assert java_list  # at least one widget parsed
    for jr, pr in zip(java_list, py, strict=True):
        assert pr["NKIND"] == jr["NKIND"] == "subdict"
        assert pr["NKEYS"] == jr["NKEYS"] == "Off On"
        assert pr["AS"] == jr["AS"]
        # On-state /BBox is the one keyed by /AS, identical under both.
        assert pr["ONBBOX"] == jr["ONBBOX"]
        assert pr["ONBBOX"] != "none"


@requires_oracle
def test_mk_characteristics_match_pdfbox(tmp_path: Path) -> None:
    """``/MK`` ``/BG`` background + ``/BC`` border colour (canonical float
    components), ``/CA`` caption, ``/R`` rotation parse identically to
    PDFBox."""
    fixture = tmp_path / "widget_ap.pdf"
    _build_fixture(fixture)
    java = [r for r in _java_records(fixture) if r["subtype"] == "Widget"]
    py = [r for r in _py_records(fixture) if r["subtype"] == "Widget"]

    # Widget (a) carries the /MK; widget (b) has none.
    assert py[0]["MKBG"] == java[0]["MKBG"] == "0.75 0.75 0.75"
    assert py[0]["MKBC"] == java[0]["MKBC"] == "0 0 0"
    assert py[0]["MKCA"] == java[0]["MKCA"] == "4"
    assert py[0]["MKR"] == java[0]["MKR"] == "0"
    # No /MK on widget (b) — both report "none"/0.
    assert py[1]["MKBG"] == java[1]["MKBG"] == "none"
    assert py[1]["MKCA"] == java[1]["MKCA"] == "none"


@requires_oracle
def test_down_appearance_presence_and_fallback_match_pdfbox(tmp_path: Path) -> None:
    """An explicit ``/AP /D`` key is reported present; a MISSING ``/D`` resolves
    to ``/N`` (spec fallback) under BOTH implementations — the "/D dropped"
    triage signal. Widget (a) has no /D (DPRESENT 0 but DKIND resolves to /N);
    widget (b) has an explicit /D (DPRESENT 1)."""
    fixture = tmp_path / "widget_ap.pdf"
    _build_fixture(fixture)
    java = [r for r in _java_records(fixture) if r["subtype"] == "Widget"]
    py = [r for r in _py_records(fixture) if r["subtype"] == "Widget"]

    assert py[0]["DPRESENT"] == java[0]["DPRESENT"] == "0"
    # Resolved (fallback to /N) entry still a subdict with the same keys.
    assert py[0]["DKIND"] == java[0]["DKIND"] == "subdict"
    assert py[0]["DKEYS"] == java[0]["DKEYS"] == "Off On"

    assert py[1]["DPRESENT"] == java[1]["DPRESENT"] == "1"
    assert py[1]["DKIND"] == java[1]["DKIND"] == "subdict"
    assert py[1]["DKEYS"] == java[1]["DKEYS"] == "Off On"


@requires_oracle
def test_link_highlight_border_action_match_pdfbox(tmp_path: Path) -> None:
    """Link ``/H`` highlight mode, ``/BS`` style + width, and URI action ``/S``
    subtype parse identically to PDFBox."""
    fixture = tmp_path / "widget_ap.pdf"
    _build_fixture(fixture)
    java = [r for r in _java_records(fixture) if r["subtype"] == "Link"]
    py = [r for r in _py_records(fixture) if r["subtype"] == "Link"]

    assert len(java) == len(py) == 1
    assert py[0]["H"] == java[0]["H"] == "P"
    assert py[0]["BSSTYLE"] == java[0]["BSSTYLE"] == "D"
    assert py[0]["BSWIDTH"] == java[0]["BSWIDTH"] == "2"
    assert py[0]["ASUBTYPE"] == java[0]["ASUBTYPE"] == "URI"
