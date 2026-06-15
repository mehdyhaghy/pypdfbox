"""Wave 1511 — document-navigation parsing-leniency differential fuzz vs
Apache PDFBox 3.0.7 (agent E).

Drives the malformed-input leniency edges of three document-navigation parsing
surfaces against the live ``DocNavFuzzProbe`` Java oracle:

* ``PDDestination.create`` dispatch for unusual COS shapes (named string /
  name, COSNull / integer / dict page slots, wrong arity, type-name case +
  whitespace variants, non-name type element, nested arrays);
* ``PDOutlineItem.get_destination`` contract for a malformed ``/Dest`` and the
  ``/Dest`` + ``/A`` precedence question;
* ``PDPageLabels`` construction over malformed ``/Nums`` number trees (odd
  size, non-integer key, non-dictionary value, negative key, unknown ``/S``
  style, ``/St`` 0 / negative, missing / empty ``/Nums``, ranges beyond the
  page count, duplicate start, ``/Kids`` non-dictionary child with a sibling
  ``/Nums``).

Intentional robustness divergence where pypdfbox is the more-lenient
superset (it recovers where upstream drops):

   * ``PDPageLabels`` recovers a same-node sibling ``/Nums`` when ``/Kids``
     carries only junk (non-dictionary) children, where upstream's ``/Kids``
     else-if branch drops the ``/Nums`` entirely (HISTORY wave 310; CHANGES
     Wave 1511).

   This row is pinned both-sides: the test asserts pypdfbox's tolerant
   token AND records the upstream token, so a future "match upstream exactly"
   change is a conscious, test-visible decision.

Wave 1526 note: ``PDOutlineItem.get_destination`` over a malformed ``/Dest``
NO LONGER diverges — wave 1519 made ``PDDestination.create`` propagate the
conversion ``OSError``, so the ``outline:dest_bad_*`` cases now CONVERGE with
upstream (both raise ``IOException``). They are compared directly, not pinned.
"""

from __future__ import annotations

import contextlib

import pytest

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSNull,
    COSString,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_destination import (
    PDDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_page_destination import (
    PDPageDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_labels import PDPageLabels
from tests.oracle.harness import requires_oracle, run_probe_text

# Rows where pypdfbox is the more-lenient documented superset. The value is the
# UPSTREAM token; the Python token below is asserted to be the tolerant one.
_KNOWN_DIVERGENCES: dict[str, str] = {
    # /Kids junk child with a sibling /Nums: upstream drops /Nums, pypdfbox
    # recovers it.
    "labels:kids_nonchild_with_nums": "[1,2,3,4,5]",
}

_PYTHON_TOLERANT: dict[str, str] = {
    "labels:kids_nonchild_with_nums": "[I,II,III,IV,V]",
}


# --------------------------------------------------------------------------
# COS construction helpers (mirror DocNavFuzzProbe.java exactly).
# --------------------------------------------------------------------------


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for b in items:
        a.add(b)
    return a


def _range(
    style: str | None, prefix: str | None, start: int | None
) -> COSDictionary:
    d = COSDictionary()
    if style is not None:
        d.set_item(_name("S"), _name(style))
    if prefix is not None:
        d.set_item(_name("P"), COSString(prefix))
    if start is not None:
        d.set_item(_name("St"), COSInteger.get(start))
    return d


def _wrap_nums(nums: COSArray) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_name("Nums"), nums)
    return d


def _nums_tree(*entries: tuple[int, COSDictionary]) -> COSDictionary:
    a = COSArray()
    for key, value in entries:
        a.add(COSInteger.get(key))
        a.add(value)
    return _wrap_nums(a)


def _goto_action() -> COSDictionary:
    a = COSDictionary()
    a.set_item(_name("S"), _name("GoTo"))
    a.set_item(_name("D"), COSString("OtherTarget"))
    return a


# --------------------------------------------------------------------------
# Python-side token producers (mirror DocNavFuzzProbe.java's contract).
# --------------------------------------------------------------------------


def _create_token(base: COSBase | None) -> str:
    try:
        d = PDDestination.create(base)
    except OSError:
        return "EXC:IOException"
    if d is None:
        return "null"
    cls = type(d).__name__
    if isinstance(d, PDNamedDestination):
        return cls + ":" + (d.get_named_destination() or "")
    return cls


def _pagenum_token(base: COSBase | None) -> str:
    try:
        d = PDDestination.create(base)
    except OSError:
        return "EXC:IOException"
    if not isinstance(d, PDPageDestination):
        return "notpage"
    return f"page={d.get_page_number()}"


def _outline_token(dest: COSBase | None, action: COSDictionary | None) -> str:
    item = PDOutlineItem()
    if dest is not None:
        item.get_cos_object().set_item(_name("Dest"), dest)
    if action is not None:
        item.get_cos_object().set_item(_name("A"), action)
    try:
        d = item.get_destination()
    except OSError:
        return "EXC:IOException"
    if d is None:
        return "null"
    cls = type(d).__name__
    if isinstance(d, PDNamedDestination):
        return cls + ":" + (d.get_named_destination() or "")
    return cls


def _label_token(tree: COSDictionary) -> str:
    doc = PDDocument()
    try:
        for _ in range(5):
            doc.add_page(PDPage())
        labels = PDPageLabels(doc, tree)
        arr = labels.get_labels_by_page_indices()
        return "[" + ",".join(x if x is not None else "" for x in arr) + "]"
    except OSError:
        return "EXC:IOException"
    finally:
        with contextlib.suppress(Exception):
            doc.close()


def _python_tokens() -> dict[str, str]:
    tokens: dict[str, str] = {}

    # ---- create dispatch ----
    tokens["create:named_string"] = _create_token(COSString("Chapter1"))
    tokens["create:named_name"] = _create_token(_name("Chapter2"))
    tokens["create:null"] = _create_token(None)
    tokens["create:bare_int"] = _create_token(COSInteger.get(7))
    tokens["create:bare_dict"] = _create_token(COSDictionary())
    tokens["create:bare_null_obj"] = _create_token(COSNull.NULL)
    tokens["create:xyz_int_page"] = _create_token(_arr(COSInteger.get(0), _name("XYZ")))
    tokens["create:xyz_null_page"] = _create_token(_arr(COSNull.NULL, _name("XYZ")))
    tokens["create:xyz_dict_page"] = _create_token(_arr(COSDictionary(), _name("XYZ")))
    tokens["create:fit"] = _create_token(_arr(COSInteger.get(0), _name("Fit")))
    tokens["create:fitb"] = _create_token(_arr(COSInteger.get(0), _name("FitB")))
    tokens["create:fith"] = _create_token(_arr(COSInteger.get(0), _name("FitH")))
    tokens["create:fitbh"] = _create_token(_arr(COSInteger.get(0), _name("FitBH")))
    tokens["create:fitv"] = _create_token(_arr(COSInteger.get(0), _name("FitV")))
    tokens["create:fitbv"] = _create_token(_arr(COSInteger.get(0), _name("FitBV")))
    tokens["create:fitr"] = _create_token(_arr(COSInteger.get(0), _name("FitR")))
    tokens["create:xyz_only2"] = _create_token(_arr(COSInteger.get(0), _name("XYZ")))
    tokens["create:xyz_5slot"] = _create_token(
        _arr(
            COSInteger.get(0),
            _name("XYZ"),
            COSInteger.get(1),
            COSInteger.get(2),
            COSFloat(3.5),
        )
    )
    tokens["create:xyz_extra"] = _create_token(
        _arr(
            COSInteger.get(0),
            _name("XYZ"),
            COSInteger.get(1),
            COSInteger.get(2),
            COSInteger.get(3),
            COSInteger.get(99),
        )
    )
    tokens["create:xyz_lower"] = _create_token(_arr(COSInteger.get(0), _name("xyz")))
    tokens["create:xyz_trailspace"] = _create_token(
        _arr(COSInteger.get(0), _name("XYZ "))
    )
    tokens["create:fit_lower"] = _create_token(_arr(COSInteger.get(0), _name("fit")))
    tokens["create:unknown_tag"] = _create_token(_arr(COSInteger.get(0), _name("Foo")))
    tokens["create:empty_array"] = _create_token(COSArray())
    tokens["create:size1_array"] = _create_token(_arr(COSInteger.get(0)))
    tokens["create:nonname_int1"] = _create_token(
        _arr(COSInteger.get(0), COSInteger.get(5))
    )
    tokens["create:nonname_str1"] = _create_token(
        _arr(COSInteger.get(0), COSString("XYZ"))
    )
    tokens["create:nested_array1"] = _create_token(
        _arr(COSInteger.get(0), _arr(_name("XYZ")))
    )
    tokens["create:null_at_1"] = _create_token(_arr(COSInteger.get(0), COSNull.NULL))
    tokens["create:neg_page"] = _pagenum_token(_arr(COSInteger.get(-3), _name("Fit")))
    tokens["create:int_page"] = _pagenum_token(_arr(COSInteger.get(4), _name("Fit")))
    tokens["create:null_page_num"] = _pagenum_token(_arr(COSNull.NULL, _name("Fit")))
    tokens["create:dict_page_num"] = _pagenum_token(
        _arr(COSDictionary(), _name("Fit"))
    )

    # ---- outline get_destination ----
    tokens["outline:dest_string"] = _outline_token(COSString("Bk"), None)
    tokens["outline:dest_name"] = _outline_token(_name("Bk"), None)
    tokens["outline:dest_array"] = _outline_token(
        _arr(COSInteger.get(1), _name("Fit")), None
    )
    tokens["outline:dest_bad_array"] = _outline_token(_arr(COSInteger.get(1)), None)
    tokens["outline:dest_bad_int"] = _outline_token(COSInteger.get(9), None)
    tokens["outline:dest_bad_dict"] = _outline_token(COSDictionary(), None)
    tokens["outline:dest_absent"] = _outline_token(None, None)
    tokens["outline:dest_and_action"] = _outline_token(
        _arr(COSInteger.get(2), _name("Fit")), _goto_action()
    )
    tokens["outline:action_only"] = _outline_token(None, _goto_action())

    # ---- page-labels malformed /Nums ----
    odd = COSArray()
    odd.add(COSInteger.get(0))
    odd.add(_range("D", None, None))
    odd.add(COSInteger.get(2))
    nonint = COSArray()
    nonint.add(COSString("zero"))
    nonint.add(_range("D", None, None))
    nondict = COSArray()
    nondict.add(COSInteger.get(0))
    nondict.add(COSInteger.get(42))
    negkey = COSArray()
    negkey.add(COSInteger.get(-1))
    negkey.add(_range("R", None, None))
    dup = COSArray()
    dup.add(COSInteger.get(0))
    dup.add(_range("D", None, None))
    dup.add(COSInteger.get(0))
    dup.add(_range("R", None, None))
    kids_dict = COSDictionary()
    kids = COSArray()
    kids.add(COSInteger.get(123))
    kids_dict.set_item(_name("Kids"), kids)
    kids_nums = COSArray()
    kids_nums.add(COSInteger.get(0))
    kids_nums.add(_range("R", None, None))
    kids_dict.set_item(_name("Nums"), kids_nums)

    tokens["labels:baseline"] = _label_token(_nums_tree((0, _range("D", None, None))))
    tokens["labels:odd_size"] = _label_token(_wrap_nums(odd))
    tokens["labels:nonint_key"] = _label_token(_wrap_nums(nonint))
    tokens["labels:nondict_value"] = _label_token(_wrap_nums(nondict))
    tokens["labels:negative_key"] = _label_token(_wrap_nums(negkey))
    tokens["labels:unknown_style"] = _label_token(
        _nums_tree((0, _range("Q", None, None)))
    )
    tokens["labels:st_zero"] = _label_token(_nums_tree((0, _range("D", None, 0))))
    tokens["labels:st_negative"] = _label_token(_nums_tree((0, _range("D", None, -2))))
    tokens["labels:missing_nums"] = _label_token(COSDictionary())
    tokens["labels:empty_nums"] = _label_token(_wrap_nums(COSArray()))
    tokens["labels:start_beyond"] = _label_token(
        _nums_tree((0, _range("D", None, None)), (99, _range("R", None, None)))
    )
    tokens["labels:duplicate_start"] = _label_token(_wrap_nums(dup))
    tokens["labels:multi_range"] = _label_token(
        _nums_tree((0, _range("D", None, None)), (2, _range("r", None, 1)))
    )
    tokens["labels:kids_nonchild_with_nums"] = _label_token(kids_dict)
    return tokens


def _parse_probe(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in text.splitlines():
        if not raw:
            continue
        label, _, value = raw.partition("\t")
        out[label] = value
    return out


# --------------------------------------------------------------------------
# Tests.
# --------------------------------------------------------------------------


def test_corpus_size_is_stable() -> None:
    """The fuzz corpus is fixed and seed-free — guard against accidental drift."""
    tokens = _python_tokens()
    assert len(tokens) == 56


@requires_oracle
def test_doc_nav_fuzz_matches_pdfbox() -> None:
    """Every non-divergent fuzz case matches Apache PDFBox 3.0.7 token-for-token;
    the documented robustness divergences are pinned both-sides."""
    java = _parse_probe(run_probe_text("DocNavFuzzProbe"))
    python = _python_tokens()

    assert set(java) == set(python), (
        f"label set mismatch: java-only={set(java) - set(python)}, "
        f"python-only={set(python) - set(java)}"
    )

    mismatches: list[str] = []
    for label in sorted(python):
        py = python[label]
        jv = java[label]
        if label in _KNOWN_DIVERGENCES:
            # Upstream value pinned; pypdfbox's tolerant value pinned.
            assert jv == _KNOWN_DIVERGENCES[label], (
                f"{label}: upstream token drifted to {jv!r} "
                f"(expected pinned {_KNOWN_DIVERGENCES[label]!r})"
            )
            assert py == _PYTHON_TOLERANT[label], (
                f"{label}: pypdfbox token drifted to {py!r} "
                f"(expected tolerant {_PYTHON_TOLERANT[label]!r})"
            )
            continue
        if py != jv:
            mismatches.append(f"{label}: python={py!r} java={jv!r}")

    assert not mismatches, "differential mismatches:\n" + "\n".join(mismatches)


@pytest.mark.parametrize("label", sorted(_KNOWN_DIVERGENCES))
def test_known_divergence_python_side_is_tolerant(label: str) -> None:
    """Independently of the oracle, pin pypdfbox's lenient token for each
    documented robustness divergence so the contract is asserted even when the
    Java oracle isn't available."""
    assert _python_tokens()[label] == _PYTHON_TOLERANT[label]
