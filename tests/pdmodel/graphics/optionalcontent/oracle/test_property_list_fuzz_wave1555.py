"""Differential fuzz audit for the PDPropertyList.create dispatch + BDC/DP
marked-content property-resolution surface vs Apache PDFBox 3.0.7
(wave 1555, agent E).

Two facets are projected per case, so a divergence pinpoints which path
disagrees:

* DISPATCH — for every ``/Properties`` resource entry, the concrete class
  ``PDResources.get_properties(name)`` returns:
  ``PDOptionalContentGroup`` (``/Type /OCG``),
  ``PDOptionalContentMembershipDictionary`` (``/Type /OCMD``),
  ``PDPropertyList`` (any other ``/Type`` or none), or ``null`` when the
  entry is absent / not a dictionary. This is ``PDPropertyList.create``'s
  dispatch routed through the resource cache.

* MARKS — the recorded ``BDC`` / ``DP`` dispatch sequence from a real
  ``PDFStreamEngine`` whose ``begin_marked_content_sequence`` /
  ``marked_content_point`` overrides record the tag plus the RESOLVED
  property dictionary (inline dict as-is, named ref resolved against
  ``/Properties``, unresolvable name -> early-return / no callback). This
  is the operator-processor resolution path.

This complements the earlier marked-content oracles:

* ``test_marked_point_dispatch_oracle`` drives ONE fixed PDF over MP/DP and
  never fuzzes the ``/Type`` dispatch class.
* ``test_ocmd_fuzz_wave1539`` / ``test_optional_content_fuzz_wave1514``
  project OCG/OCMD MEMBERSHIP, not the create() dispatch + BDC resolution.

Both sides are driven on the SAME bytes: this module writes one PDF per case
(carrying the fuzzed ``/Properties`` frame + a BDC/DP content stream) plus a
``manifest.txt``; the Java probe (``oracle/probes/PropertyListFuzzProbe.java``)
loads each file and projects a framed line; this module reads the exact same
files and projects the identical grammar through pypdfbox, then asserts
line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> dispatch=<k:cls|...> marks=<seq>

``dispatch`` entries are sorted by ``/Properties`` key (``key:class`` or
``key:null``); ``marks`` is the ``"|"``-joined BDC/DP records
``BDC:/<tag>:<props>`` / ``DP:/<tag>:<props>`` where ``<props>`` is ``null``
or a canonical ``{ k=v ; ... }`` dict (keys sorted). A load failure projects
``dispatch=ERR:<name> marks=ERR``.

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/graphics/pd_property_list.py`` (or the marked-content
property helper); a defensible divergence is pinned in ``_PINNED`` with a
matching CHANGES.md row.
"""

from __future__ import annotations

import struct
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator.markedcontent.begin_marked_content_with_props import (  # noqa: E501
    BeginMarkedContentWithProps,
)
from pypdfbox.contentstream.operator.markedcontent.define_marked_content_point_with_props import (  # noqa: E501
    DefineMarkedContentPointWithProps,
)
from pypdfbox.cos import (
    COSArray,
    COSBoolean,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.cos.cos_base import COSBase
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_resources import PDResources
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


# --------------------------------------------------------------- canonical render


def _float32_shortest(value: float) -> str:
    target = struct.unpack("f", struct.pack("f", value))[0]
    for prec in range(1, 18):
        candidate = f"{value:.{prec}g}"
        if struct.unpack("f", struct.pack("f", float(candidate)))[0] == target:
            return candidate
    return repr(value)


def _canon_float(value: float) -> str:
    if value != value:  # NaN
        return "nan"
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    bd = (
        Decimal(_float32_shortest(value))
        .quantize(Decimal("0.00001"), rounding=ROUND_HALF_EVEN)
        .normalize()
    )
    s = format(bd, "f")
    if s == "-0":
        s = "0"
    return s


def _canon_value(b: COSBase | None) -> str:
    if b is None:
        return "NULL"
    if isinstance(b, COSInteger):
        return f"INT:{b.long_value()}"
    if isinstance(b, COSFloat):
        return f"REAL:{_canon_float(b.float_value())}"
    if isinstance(b, COSName):
        return f"NAME:/{b.get_name()}"
    if isinstance(b, COSString):
        return f"STR:{b.get_bytes().hex()}"
    if isinstance(b, COSBoolean):
        return f"BOOL:{'true' if b.get_value() else 'false'}"
    if isinstance(b, COSNull):
        return "NULL"
    if isinstance(b, COSArray):
        return "[" + ",".join(_canon_value(b.get(i)) for i in range(b.size())) + "]"
    if isinstance(b, COSDictionary):
        return _canon_dict(b)
    return f"COS:{type(b).__name__}"


def _canon_dict(d: COSDictionary) -> str:
    items = sorted(
        (key.get_name(), d.get_dictionary_object(key)) for key in d.key_set()
    )
    body = " ; ".join(f"{name}={_canon_value(val)}" for name, val in items)
    return "{ " + body + " }"


# ------------------------------------------------------------------ COS builders


def _ocg(name: str = "Layer") -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("OCG"))
    d.set_string(_N("Name"), name)
    return d


def _ocmd(*members: COSDictionary) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("OCMD"))
    arr = COSArray()
    for m in members:
        arr.add(m)
    d.set_item(_N("OCGs"), arr)
    return d


def _plain(**entries: COSBase) -> COSDictionary:
    d = COSDictionary()
    for k, v in entries.items():
        d.set_item(_N(k), v)
    return d


# ------------------------------------------------------------------------ corpus

# A case is (properties_entries, content_stream_bytes). properties_entries maps
# a /Properties key (str) -> a COSBase value (dict OR deliberately non-dict).
_Case = tuple[dict[str, COSBase], bytes]


def _corpus() -> dict[str, _Case]:
    cases: dict[str, _Case] = {}

    # ---- dispatch facet: /Type variants resolved through create() ----------
    # /Type /OCG -> PDOptionalContentGroup.
    cases["dispatch_ocg"] = ({"P0": _ocg("OcgLayer")}, b"/Span /P0 BDC EMC\n")

    # /Type /OCMD -> PDOptionalContentMembershipDictionary.
    cases["dispatch_ocmd"] = (
        {"P0": _ocmd(_ocg("M1"))},
        b"/Span /P0 BDC EMC\n",
    )

    # /Type present but unknown name -> bare PDPropertyList.
    d = _plain(Title=COSString("custom"))
    d.set_item(_N("Type"), _N("Bogus"))
    cases["dispatch_unknown_type"] = ({"P0": d}, b"/Span /P0 BDC EMC\n")

    # /Type absent -> bare PDPropertyList.
    cases["dispatch_no_type"] = (
        {"P0": _plain(Title=COSString("plain"), MCID=COSInteger(3))},
        b"/Span /P0 BDC EMC\n",
    )

    # /Type as a non-name value (string "OCG") -> NOT OCG; bare PDPropertyList.
    d = _plain()
    d.set_item(_N("Type"), COSString("OCG"))
    cases["dispatch_type_as_string"] = ({"P0": d}, b"/Span /P0 BDC EMC\n")

    # /Type as an integer -> bare PDPropertyList.
    d = _plain()
    d.set_item(_N("Type"), COSInteger(1))
    cases["dispatch_type_as_int"] = ({"P0": d}, b"/Span /P0 BDC EMC\n")

    # /Type /ocg (lowercase) -> NOT /OCG (name comparison is exact); bare.
    d = _plain()
    d.set_item(_N("Type"), _N("ocg"))
    cases["dispatch_type_lowercase"] = ({"P0": d}, b"/Span /P0 BDC EMC\n")

    # /Properties entry is NOT a dictionary (an array) -> getProperties null.
    arr = COSArray()
    arr.add(COSInteger(1))
    cases["dispatch_entry_array"] = ({"P0": arr}, b"/Span /P0 BDC EMC\n")

    # /Properties entry is a name -> getProperties null.
    cases["dispatch_entry_name"] = ({"P0": _N("X")}, b"/Span /P0 BDC EMC\n")

    # /Properties entry is null -> getProperties null.
    cases["dispatch_entry_null"] = ({"P0": COSNull.NULL}, b"/Span /P0 BDC EMC\n")

    # Empty dict, no /Type -> bare PDPropertyList.
    cases["dispatch_empty_dict"] = ({"P0": _plain()}, b"/Span /P0 BDC EMC\n")

    # Mixed frame: an OCG, an OCMD, a plain dict and a non-dict in one
    # /Properties frame -> per-key dispatch class projected sorted.
    cases["dispatch_mixed_frame"] = (
        {
            "A": _ocg("A"),
            "B": _ocmd(_ocg("Bm")),
            "C": _plain(Foo=COSInteger(9)),
            "D": _N("notdict"),
        },
        b"/Span /A BDC EMC\n",
    )

    # ---- marks facet: BDC resolution paths --------------------------------
    # BDC with a named ref resolving to an OCG dict.
    cases["bdc_named_ocg"] = (
        {"OC0": _ocg("NamedOcg")},
        b"/OC /OC0 BDC EMC\n",
    )

    # BDC with a named ref resolving to a plain (no /Type) dict.
    cases["bdc_named_plain"] = (
        {"MC0": _plain(MCID=COSInteger(5), Title=COSString("hello"))},
        b"/Span /MC0 BDC EMC\n",
    )

    # BDC with a named ref whose /Properties entry is absent -> no callback.
    cases["bdc_named_missing"] = ({}, b"/Span /Missing BDC EMC\n")

    # BDC with a named ref whose /Properties entry is a non-dict -> no
    # callback (resolution fails to a COSDictionary).
    cases["bdc_named_nondict"] = (
        {"Bad": _N("notdict")},
        b"/Span /Bad BDC EMC\n",
    )

    # BDC with an inline property dict (mixed value types).
    cases["bdc_inline_dict"] = (
        {},
        b"/Span << /MCID 1 /Title (inline) /Flag true /K [1 2.5] >> BDC EMC\n",
    )

    # BDC with an inline dict carrying /Type /OCG (still resolved as inline).
    cases["bdc_inline_typed"] = (
        {},
        b"/OC << /Type /OCG /Name (InlineOcg) >> BDC EMC\n",
    )

    # BDC with an empty inline dict.
    cases["bdc_inline_empty"] = ({}, b"/Span << >> BDC EMC\n")

    # BDC with only ONE operand (tag, no props) -> MissingOperandException;
    # engine catches, no callback.
    cases["bdc_one_operand"] = ({}, b"/Span BDC EMC\n")

    # BDC with ZERO operands -> MissingOperandException; no callback.
    cases["bdc_zero_operands"] = ({}, b"BDC EMC\n")

    # BDC where the FIRST operand (tag slot) is not a name -> no callback
    # (operator returns; tag must be a name).
    cases["bdc_tag_not_name"] = (
        {"OC0": _ocg("X")},
        b"(notaname) /OC0 BDC EMC\n",
    )

    # BDC where the props operand is an integer (neither name nor dict) -> no
    # callback (resolution returns null).
    cases["bdc_props_int"] = ({}, b"/Span 42 BDC EMC\n")

    # ---- marks facet: DP (marked point) -----------------------------------
    # DP with a named ref resolving to a dict.
    cases["dp_named"] = (
        {"PT0": _plain(MCID=COSInteger(7), Type=_N("Pagination"))},
        b"/Pt /PT0 DP\n",
    )

    # DP with an inline dict.
    cases["dp_inline"] = (
        {},
        b"/Pt << /MCID 2 /Title (point) >> DP\n",
    )

    # DP with an unresolvable name -> no callback.
    cases["dp_named_missing"] = ({}, b"/Pt /Missing DP\n")

    # ---- combined sequences ------------------------------------------------
    # Several BDC/DP in one stream, exercising both resolution + dispatch.
    cases["combo_sequence"] = (
        {"OC0": _ocg("ComboOcg"), "MC1": _plain(MCID=COSInteger(4))},
        (
            b"/OC /OC0 BDC EMC\n"
            b"/Span /MC1 BDC EMC\n"
            b"/Pt << /MCID 8 >> DP\n"
            b"/Span /Missing BDC EMC\n"
            b"/Art << /Type /Pagination >> BDC EMC\n"
        ),
    )

    return cases


def _write_case_pdf(path: Path, entry: _Case) -> None:
    properties_entries, content = entry
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)

        resources = PDResources()
        if properties_entries:
            props = COSDictionary()
            for key, value in properties_entries.items():
                props.set_item(_N(key), value)
            resources.get_cos_object().set_item(_N("Properties"), props)
        page.set_resources(resources)

        stream = doc.get_document().create_cos_stream()
        out = stream.create_output_stream()
        try:
            out.write(content)
        finally:
            out.close()
        page.set_contents(stream)

        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


class _RecordingEngine(PDFStreamEngine):
    """Engine recording every BDC / DP dispatch with the resolved props,
    rendering the probe's canonical line grammar."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []
        self.add_operator(BeginMarkedContentWithProps())
        self.add_operator(DefineMarkedContentPointWithProps())

    def begin_marked_content_sequence(
        self, tag: COSName | None, properties: COSDictionary | None
    ) -> None:
        tag_str = tag.get_name() if isinstance(tag, COSName) else "<none>"
        props = "null" if properties is None else _canon_dict(properties)
        self.records.append(f"BDC:/{tag_str}:{props}")

    def marked_content_point(
        self, tag: COSName | None, properties: COSDictionary | None
    ) -> None:
        tag_str = tag.get_name() if isinstance(tag, COSName) else "<none>"
        props = "null" if properties is None else _canon_dict(properties)
        self.records.append(f"DP:/{tag_str}:{props}")


def _java_exc_simple(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:  # noqa: BLE001 — mirror probe's catch-all framing
        return prefix + f"dispatch=ERR:{_java_exc_simple(e)} marks=ERR"
    try:
        page = doc.get_page(0)
        resources = page.get_resources()

        # (1) dispatch facet.
        dispatch: dict[str, str] = {}
        if resources is not None:
            for key in resources.get_properties_names():
                try:
                    pl = resources.get_properties(key)
                    cls = "null" if pl is None else type(pl).__name__
                except Exception as e:  # noqa: BLE001
                    cls = f"ERR:{_java_exc_simple(e)}"
                dispatch[key.get_name()] = cls
        dsb = "|".join(f"{k}:{dispatch[k]}" for k in sorted(dispatch))

        # (2) marks facet.
        engine = _RecordingEngine()
        engine.process_page(page)
        marks = "|".join(engine.records)
        return prefix + f"dispatch={dsb} marks={marks}"
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- tests


@requires_oracle
def test_property_list_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every fuzzed /Properties frame + BDC/DP content stream dispatches and
    resolves identically on pypdfbox and Apache PDFBox 3.0.7: same
    PDPropertyList.create class per /Properties key AND same BDC/DP callback
    sequence with the same resolved property dict. Divergences are pinned in
    ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _corpus()
    for name, entry in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", entry)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("PropertyListFuzzProbe", str(tmp_path))
    java_lines = [ln for ln in raw.splitlines() if ln.startswith("CASE ")]
    assert len(java_lines) == len(corpus), (
        f"probe emitted {len(java_lines)} lines for {len(corpus)} cases:\n{raw}"
    )
    java_by_name = {ln.split(" ", 2)[1]: ln for ln in java_lines}

    mismatches: list[str] = []
    for name in corpus:
        java = java_by_name.get(name, "<MISSING>")
        py = _python_line(tmp_path, name)
        if name in _PINNED:
            py_exp, java_exp, _reason = _PINNED[name]
            if py == py_exp and java == java_exp:
                continue
        if py != java:
            mismatches.append(f"  {name}\n    java: {java}\n    py  : {py}")

    assert not mismatches, (
        "property-list fuzz divergences:\n" + "\n".join(mismatches)
    )


def test_create_dispatch_self_contained() -> None:
    """Self-contained pin on ``PDPropertyList.create`` dispatch (no oracle):
    OCG / OCMD / unknown-type / no-type / non-dict map to the exact classes
    PDFBox 3.0.7 produces. Guards the dispatch even on a machine without the
    Java oracle."""
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_group import (  # noqa: E501
        PDOptionalContentGroup,
    )
    from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (  # noqa: E501
        PDOptionalContentMembershipDictionary,
    )
    from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList

    assert type(PDPropertyList.create(_ocg())) is PDOptionalContentGroup
    assert (
        type(PDPropertyList.create(_ocmd(_ocg())))
        is PDOptionalContentMembershipDictionary
    )

    d = _plain()
    d.set_item(_N("Type"), _N("Bogus"))
    assert type(PDPropertyList.create(d)) is PDPropertyList
    assert type(PDPropertyList.create(_plain())) is PDPropertyList

    # /Type as a string is NOT /OCG (exact COSName comparison) -> bare list.
    d = _plain()
    d.set_item(_N("Type"), COSString("OCG"))
    assert type(PDPropertyList.create(d)) is PDPropertyList

    # None passes through to None (pypdfbox is permissive; upstream NPEs).
    assert PDPropertyList.create(None) is None
