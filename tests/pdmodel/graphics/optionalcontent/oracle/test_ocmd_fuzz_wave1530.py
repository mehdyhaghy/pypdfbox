"""Differential fuzz audit for the optional-content membership dictionary
(OCMD) vs Apache PDFBox 3.0.7 (wave 1530, agent E).

Goes deeper than the wave-1514 optional-content fuzz on the OCMD-specific
surface:

* ``/OCGs`` membership list shape: absent, single OCG dict, single non-OCG
  dict (nested OCMD / arbitrary dict), array of OCG dicts, array with
  non-dict members (skipped by upstream), ``/OCGs`` as a non-dict/non-array
  scalar (yields an empty list).
* ``/P`` visibility policy: absent (default ``AnyOn``), each of the four
  spec names, an unknown name (returned verbatim — PDFBox 3.0.7
  ``getVisibilityPolicy`` is ``getCOSName(P, ANY_ON)`` with no ``valueOf``
  enum lookup, so it never throws), and a non-name value (falls back to the
  ``AnyOn`` default).
* ``/VE`` visibility expression: absent, well-formed ``[/And ...]`` /
  ``[/Or ...]`` / ``[/Not ...]`` (possibly nested), an unknown operator name
  (still reported as the operator — the wrapper does not validate), an empty
  array, a non-array scalar.
* ``/Type`` not ``/OCMD``: routes through ``PDPropertyList.create`` so the
  divergence is the wrapper class, never an OCMD.

Both sides are driven on the SAME bytes: the corpus builder writes one PDF
per case, carrying the fuzzed OCMD as the first page's resource
``/Properties /MC1``. The Java probe (``oracle/probes/OcmdFuzzProbe.java``)
loads each file and projects a stable framed line; this module reads the
exact same files and projects the identical grammar through pypdfbox, then
asserts line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> cls=<simpleClass|null> ocgs=<count|n/a> names=<|-joined|n/a>
        policy=<name|n/a> ve=<op|absent|scalar|empty|noop|n/a>

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/graphics/optionalcontent/``; a defensible divergence is
pinned in ``_PINNED`` with a matching CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.graphics.optionalcontent.pd_optional_content_membership_dictionary import (  # noqa: E501
    PDOptionalContentMembershipDictionary,
)
from pypdfbox.pdmodel.graphics.pd_property_list import PDPropertyList
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from tests.oracle.harness import requires_oracle, run_probe_text

_N = COSName.get_pdf_name


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _ocg(name: str | None = None, **extra: COSBase) -> COSDictionary:
    """A minimal ``/Type /OCG`` dictionary, optionally with a ``/Name``."""
    d = COSDictionary()
    d.set_item(_N("Type"), _N("OCG"))
    if name is not None:
        d.set_string(_N("Name"), name)
    for k, v in extra.items():
        d.set_item(_N(k), v)
    return d


def _ocmd(**entries: COSBase) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_N("Type"), _N("OCMD"))
    for k, v in entries.items():
        d.set_item(_N(k), v)
    return d


# --------------------------------------------------------------------- corpus


def _corpus() -> dict[str, COSDictionary]:
    cases: dict[str, COSDictionary] = {}

    def add(name: str, d: COSDictionary) -> None:
        cases[name] = d

    # --- /OCGs shape corners ----------------------------------------------
    add("ocgs_absent", _ocmd())
    add("ocgs_single_ocg", _ocmd(OCGs=_ocg("Solo")))
    # Single dict that is NOT an OCG (a nested OCMD) — upstream still wraps it
    # and returns a singleton list (count 1).
    add("ocgs_single_nested_ocmd", _ocmd(OCGs=_ocmd(OCGs=_ocg("Inner"))))
    # Single dict with no /Type at all — wraps to a plain PDPropertyList,
    # still counted as 1.
    add("ocgs_single_plain_dict", _ocmd(OCGs=COSDictionary()))
    add("ocgs_array_two", _ocmd(OCGs=_arr(_ocg("Alpha"), _ocg("Beta"))))
    add("ocgs_array_empty", _ocmd(OCGs=COSArray()))
    # Array members that are not dictionaries are skipped.
    add(
        "ocgs_array_mixed",
        _ocmd(OCGs=_arr(_ocg("Keep"), COSInteger(7), COSString("x"))),
    )
    add(
        "ocgs_array_all_non_dict",
        _ocmd(OCGs=_arr(COSInteger(1), COSString("y"), _N("z"))),
    )
    # Array members that are non-OCG dicts (nested OCMD / plain) are wrapped
    # too — they appear by their wrapper class name.
    add(
        "ocgs_array_non_ocg_dicts",
        _ocmd(OCGs=_arr(_ocg("Real"), _ocmd(), COSDictionary())),
    )
    # /OCGs as a non-dict / non-array scalar -> empty list.
    add("ocgs_scalar_string", _ocmd(OCGs=COSString("not-an-array")))
    add("ocgs_scalar_int", _ocmd(OCGs=COSInteger(42)))
    add("ocgs_scalar_name", _ocmd(OCGs=_N("Nope")))

    # --- /P visibility policy corners -------------------------------------
    add("p_absent", _ocmd(OCGs=_arr(_ocg("A"))))
    add("p_any_on", _ocmd(OCGs=_arr(_ocg("A")), P=_N("AnyOn")))
    add("p_all_on", _ocmd(OCGs=_arr(_ocg("A")), P=_N("AllOn")))
    add("p_any_off", _ocmd(OCGs=_arr(_ocg("A")), P=_N("AnyOff")))
    add("p_all_off", _ocmd(OCGs=_arr(_ocg("A")), P=_N("AllOff")))
    # Unknown policy name: returned verbatim (no valueOf, no throw).
    add("p_unknown_name", _ocmd(OCGs=_arr(_ocg("A")), P=_N("Bogus")))
    add("p_empty_name", _ocmd(OCGs=_arr(_ocg("A")), P=_N("")))
    # Non-name /P value: falls back to default AnyOn.
    add("p_non_name_string", _ocmd(OCGs=_arr(_ocg("A")), P=COSString("AllOn")))
    add("p_non_name_int", _ocmd(OCGs=_arr(_ocg("A")), P=COSInteger(3)))
    add("p_non_name_array", _ocmd(OCGs=_arr(_ocg("A")), P=_arr(_N("AllOn"))))

    # --- /VE visibility expression corners --------------------------------
    add("ve_absent", _ocmd(OCGs=_arr(_ocg("A"))))
    add("ve_and", _ocmd(VE=_arr(_N("And"), _ocg("A"), _ocg("B"))))
    add("ve_or", _ocmd(VE=_arr(_N("Or"), _ocg("A"), _ocg("B"))))
    add("ve_not", _ocmd(VE=_arr(_N("Not"), _ocg("A"))))
    add(
        "ve_nested",
        _ocmd(
            VE=_arr(
                _N("And"),
                _ocg("A"),
                _arr(_N("Or"), _ocg("B"), _ocg("C")),
            )
        ),
    )
    # Unknown operator name — the wrapper reports it verbatim, no validation.
    add("ve_unknown_op", _ocmd(VE=_arr(_N("Xor"), _ocg("A"))))
    # Empty /VE array.
    add("ve_empty_array", _ocmd(VE=COSArray()))
    # /VE whose first element is not a name.
    add("ve_head_not_name", _ocmd(VE=_arr(_ocg("A"), _ocg("B"))))
    # /VE as a non-array scalar.
    add("ve_scalar_string", _ocmd(VE=COSString("nope")))
    add("ve_scalar_int", _ocmd(VE=COSInteger(9)))
    add("ve_scalar_name", _ocmd(VE=_N("And")))
    # /VE present alongside /OCGs + /P (VE does not displace the others).
    add(
        "ve_with_ocgs_and_p",
        _ocmd(
            OCGs=_arr(_ocg("A")),
            P=_N("AllOff"),
            VE=_arr(_N("Not"), _ocg("A")),
        ),
    )

    # --- /Type corners ----------------------------------------------------
    # /Type not OCMD -> create() returns a plain PDPropertyList, not an OCMD.
    no_type = COSDictionary()
    no_type.set_item(_N("OCGs"), _arr(_ocg("A")))
    no_type.set_item(_N("P"), _N("AllOn"))
    add("type_absent", no_type)

    wrong_type = COSDictionary()
    wrong_type.set_item(_N("Type"), _N("Bogus"))
    wrong_type.set_item(_N("OCGs"), _arr(_ocg("A")))
    add("type_wrong", wrong_type)

    # /Type /OCG on the property itself -> wraps as PDOptionalContentGroup.
    add("type_is_ocg", _ocg("AmIAGroup"))

    return cases


def _write_case_pdf(path: Path, entry: COSDictionary) -> None:
    """Build a one-page PDF carrying ``entry`` as the first page's resource
    ``/Properties /MC1``."""
    doc = PDDocument()
    try:
        page = PDPage()
        doc.add_page(page)
        resources = COSDictionary()
        props = COSDictionary()
        props.set_item(_N("MC1"), entry)
        resources.set_item(_N("Properties"), props)
        page.set_resources(resources)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _java_exc(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    if isinstance(exc, ValueError):
        return "IllegalArgumentException"
    return type(exc).__name__


def _java_class_name(prop: PDPropertyList) -> str:
    """Simple class name the Java probe would report for ``prop``."""
    from pypdfbox.pdmodel.graphics.optionalcontent import (
        PDOptionalContentGroup,
    )

    if isinstance(prop, PDOptionalContentMembershipDictionary):
        return "PDOptionalContentMembershipDictionary"
    if isinstance(prop, PDOptionalContentGroup):
        return "PDOptionalContentGroup"
    return "PDPropertyList"


def _ocg_entry(g: PDPropertyList) -> str:
    """Mirror the Java probe's ``ocgEntry``: an OCG's name (``""`` when
    null), else the wrapper's simple class name."""
    from pypdfbox.pdmodel.graphics.optionalcontent import (
        PDOptionalContentGroup,
    )

    try:
        if isinstance(g, PDOptionalContentGroup):
            n = g.get_name()
            return "" if n is None else n
        return _java_class_name(g)
    except Exception as e:  # pragma: no cover - defensive
        return f"ERR:{_java_exc(e)}"


def _ve_shape(ocmd: PDOptionalContentMembershipDictionary) -> str:
    ve = ocmd.get_cos_object().get_dictionary_object(_N("VE"))
    if ve is None:
        return "absent"
    if not isinstance(ve, COSArray):
        return "scalar"
    if ve.size() == 0:
        return "empty"
    head = ve.get_object(0)
    if isinstance(head, COSName):
        return head.name
    return "noop"


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        return prefix + (
            f"cls=ERR:{_java_exc(e)} ocgs=ERR names=ERR policy=ERR ve=ERR"
        )
    try:
        page = doc.get_page(0)
        res = page.get_resources()
        prop = None if res is None else res.get_properties(_N("MC1"))
        if prop is None:
            return prefix + "cls=null ocgs=n/a names=n/a policy=n/a ve=n/a"
        if not isinstance(prop, PDOptionalContentMembershipDictionary):
            cls = _java_class_name(prop)
            return prefix + f"cls={cls} ocgs=n/a names=n/a policy=n/a ve=n/a"
        try:
            entries = prop.get_ocgs_property_list()
            ocgs = str(len(entries))
            ns = [_ocg_entry(g) for g in entries]
            names = "" if not ns else "|".join(ns)
        except Exception as e:
            ocgs = f"ERR:{_java_exc(e)}"
            names = f"ERR:{_java_exc(e)}"
        try:
            policy = prop.get_visibility_policy_name().name
        except Exception as e:
            policy = f"ERR:{_java_exc(e)}"
        try:
            ve = _ve_shape(prop)
        except Exception as e:
            ve = f"ERR:{_java_exc(e)}"
        cls = _java_class_name(prop)
        return prefix + (
            f"cls={cls} ocgs={ocgs} names={names} policy={policy} ve={ve}"
        )
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_ocmd_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated OCMD dictionary parses (or fails to parse) identically
    on pypdfbox and Apache PDFBox 3.0.7: same wrapper class, same /OCGs
    count + entry names, same /P visibility policy (including unknown names
    returned verbatim), same /VE shape. Divergences are pinned explicitly in
    ``_PINNED`` (with a matching CHANGES.md row)."""
    corpus = _corpus()
    for name, entry in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", entry)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("OcmdFuzzProbe", str(tmp_path))
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

    assert not mismatches, "OCMD fuzz divergences:\n" + "\n".join(mismatches)
