"""Differential fuzz audit for the per-subclass leaf value-wrapping of the
typed ``PDNameTreeNode`` subclasses vs Apache PDFBox 3.0.7 (wave 1532, agent A).

The generic name/number-tree probes (``NameTreeSetterProbe`` /
``NameNumberTreeFuzzProbe``) isolate the *base-class* traversal. This audit's
angle is the *per-subclass* ``convert_cos_to_value`` / ``convert_value_to_cos``
(upstream ``convertCOSToPD`` / ``convertObjectToCOS``): each typed subclass wraps
a ``/Names`` leaf COS value into a different typed object, and each tolerates a
different set of malformed leaf shapes.

Only two of pypdfbox's typed subclasses have an upstream counterpart in the
PDFBox 3.0.7 jar:

* ``PDJavascriptNameTreeNode`` → upstream ``PDActionJavaScript``
* ``PDEmbeddedFilesNameTreeNode`` → upstream ``PDComplexFileSpecification``

(``PDDestinationNameTreeNode`` / ``PDStructureElementNameTreeNode`` also exist
upstream but have no pypdfbox sibling in this agent's zone.) The live probe
``oracle/probes/TypedNameTreeNodeFuzzProbe.java`` drives upstream
``convertCOSToPD`` over a battery of leaf shapes and prints the wrapped object's
simple class name (or ``ERR:<Exc>`` / ``null``). This module replays the same
leaf shapes through pypdfbox.

Two parity stances:

* **EmbeddedFiles** — pypdfbox is byte-for-byte aligned with upstream
  (Python ``None`` leaf → wrapper, ``COSNull``/non-dict → error, dict → wrapper),
  so we assert pypdfbox matches the probe's projection directly.
* **JavaScript** — pypdfbox deliberately diverges (documented in ``CHANGES.md``):
  the leaf value type is the Python ``str`` JS *body* read from ``/JS``, not the
  ``PDActionJavaScript`` wrapper upstream returns via ``PDActionFactory``. The
  divergence cascades through every dict-shaped leaf. We pin BOTH sides: the
  probe's upstream projection is asserted against a recorded table, and the
  pypdfbox str-body behaviour is asserted independently.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.pd_alternate_presentations_name_tree_node import (
    PDAlternatePresentationsNameTreeNode,
)
from pypdfbox.pdmodel.pd_embedded_files_name_tree_node import (
    PDEmbeddedFilesNameTreeNode,
)
from pypdfbox.pdmodel.pd_ids_name_tree_node import PDIDSNameTreeNode
from pypdfbox.pdmodel.pd_javascript_name_tree_node import PDJavascriptNameTreeNode
from pypdfbox.pdmodel.pd_pages_name_tree_node import PDPagesNameTreeNode
from pypdfbox.pdmodel.pd_renditions_name_tree_node import PDRenditionsNameTreeNode
from pypdfbox.pdmodel.pd_templates_name_tree_node import PDTemplatesNameTreeNode
from pypdfbox.pdmodel.pd_urls_name_tree_node import PDURLSNameTreeNode
from tests.oracle.harness import requires_oracle, run_probe_text

_PROBE = "TypedNameTreeNodeFuzzProbe"

_S = COSName.get_pdf_name("S")
_JS = COSName.get_pdf_name("JS")
_TYPE = COSName.get_pdf_name("Type")
_JAVA_SCRIPT = COSName.get_pdf_name("JavaScript")


def _run_probe_cases() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in run_probe_text(_PROBE).splitlines():
        line = line.strip()
        if not line.startswith("CASE "):
            continue
        # grammar: CASE <node> <leaf> -> <result>
        head, _, result = line.partition(" -> ")
        _, node, leaf = head.split(" ", 2)
        out[f"{node}:{leaf}"] = result
    return out


# ---------------------------------------------------------------------------
# Recorded upstream projection (PDFBox 3.0.7, captured from the live probe).
# This is the "pin BOTH sides" anchor for the JavaScript divergence and the
# byte-exact target for EmbeddedFiles.
# ---------------------------------------------------------------------------

_UPSTREAM = {
    # JavaScript: upstream wraps via PDActionFactory + cast to PDActionJavaScript.
    "js:null": "ERR:IOException",
    "js:cosstring": "ERR:IOException",
    "js:cosname": "ERR:IOException",
    "js:cosint": "ERR:IOException",
    "js:cosnull": "ERR:IOException",
    "js:cosarray": "ERR:IOException",
    "js:dict_js_action": "PDActionJavaScript",
    "js:dict_wrong_S": "ERR:ClassCastException",
    "js:dict_no_S": "null",
    "js:dict_no_JS": "PDActionJavaScript",
    "js:dict_empty": "null",
    "js:dict_js_stream": "PDActionJavaScript",
    # EmbeddedFiles: pypdfbox matches these exactly.
    "ef:null": "PDComplexFileSpecification",
    "ef:cosnull": "ERR:IOException",
    "ef:empty_dict": "PDComplexFileSpecification",
    "ef:cosstring": "ERR:IOException",
    "ef:cosname": "ERR:IOException",
    "ef:cosint": "ERR:IOException",
    "ef:cosarray": "ERR:IOException",
    "ef:filespec_dict": "PDComplexFileSpecification",
}


@requires_oracle
def test_probe_matches_recorded_upstream():
    """The live probe still emits exactly the upstream projection we pinned.

    Guards against an oracle-jar swap silently changing the upstream contract
    under the both-sides pin.
    """
    assert _run_probe_cases() == _UPSTREAM


# ---------------------------------------------------------------------------
# EmbeddedFiles — pypdfbox is aligned with upstream.
# ---------------------------------------------------------------------------


def _ef_project(leaf):
    node = PDEmbeddedFilesNameTreeNode()
    try:
        value = node.convert_cos_to_value(leaf)
    except OSError:
        return "ERR:IOException"
    if value is None:
        return "null"
    return type(value).__name__


_EF_LEAVES = {
    "null": None,
    "cosnull": COSNull.NULL,
    "empty_dict": COSDictionary(),
    "cosstring": COSString("x"),
    "cosname": COSName.get_pdf_name("Foo"),
    "cosint": COSInteger.get(1),
    "cosarray": COSArray(),
}


@pytest.mark.parametrize("case", sorted(_EF_LEAVES), ids=sorted(_EF_LEAVES))
def test_embedded_files_matches_upstream(case):
    got = _ef_project(_EF_LEAVES[case])
    assert got == _UPSTREAM[f"ef:{case}"]


def test_embedded_files_filespec_dict_matches_upstream():
    fs = COSDictionary()
    fs.set_item(_TYPE, COSName.get_pdf_name("Filespec"))
    fs.set_string(COSName.get_pdf_name("F"), "test.txt")
    assert _ef_project(fs) == _UPSTREAM["ef:filespec_dict"]


def test_embedded_files_null_leaf_round_trip():
    """``[String, null]`` → wrapper around a fresh dict (testNullEmbeddedFile)."""
    node = PDEmbeddedFilesNameTreeNode()
    spec = node.convert_cos_to_value(None)
    cos = node.convert_value_to_cos(spec)
    assert isinstance(cos, COSDictionary)


def test_embedded_files_dict_round_trip_is_identity():
    node = PDEmbeddedFilesNameTreeNode()
    fs = COSDictionary()
    fs.set_string(COSName.get_pdf_name("F"), "a.txt")
    spec = node.convert_cos_to_value(fs)
    assert node.convert_value_to_cos(spec) is fs


# ---------------------------------------------------------------------------
# JavaScript — pinned BOTH sides (documented divergence: str body vs wrapper).
# ---------------------------------------------------------------------------


def _js_node():
    return PDJavascriptNameTreeNode()


def test_javascript_non_dict_leaves_raise_like_upstream():
    """Non-dict leaves raise on BOTH sides (upstream IOException → OSError)."""
    node = _js_node()
    for leaf in (
        None,
        COSString("app.alert(1)"),
        COSName.get_pdf_name("Foo"),
        COSInteger.get(3),
        COSNull.NULL,
        COSArray(),
    ):
        with pytest.raises(OSError):
            node.convert_cos_to_value(leaf)


def _js_dict(body: str | None, subtype: COSName | None) -> COSDictionary:
    d = COSDictionary()
    d.set_item(_TYPE, COSName.get_pdf_name("Action"))
    if subtype is not None:
        d.set_item(_S, subtype)
    if body is not None:
        d.set_string(_JS, body)
    return d


def test_javascript_well_formed_returns_str_body_not_wrapper():
    """DIVERGENCE: upstream returns PDActionJavaScript; pypdfbox returns the
    raw ``str`` JS body. Upstream-side pinned in _UPSTREAM."""
    node = _js_node()
    assert _UPSTREAM["js:dict_js_action"] == "PDActionJavaScript"
    assert node.convert_cos_to_value(_js_dict("app.alert(1)", _JAVA_SCRIPT)) == "app.alert(1)"


def test_javascript_wrong_subtype_returns_body_not_classcast():
    """DIVERGENCE: upstream casts to PDActionJavaScript → ClassCastException
    when /S is not /JavaScript; pypdfbox ignores /S and returns the /JS body."""
    node = _js_node()
    assert _UPSTREAM["js:dict_wrong_S"] == "ERR:ClassCastException"
    body = node.convert_cos_to_value(_js_dict("app.alert(1)", COSName.get_pdf_name("URI")))
    assert body == "app.alert(1)"


def test_javascript_missing_js_body_raises_where_upstream_wraps():
    """DIVERGENCE: a dict with /S=/JavaScript but no /JS body wraps fine
    upstream (PDActionJavaScript, empty body); pypdfbox needs the /JS body and
    raises OSError."""
    node = _js_node()
    assert _UPSTREAM["js:dict_no_JS"] == "PDActionJavaScript"
    with pytest.raises(OSError):
        node.convert_cos_to_value(_js_dict(None, _JAVA_SCRIPT))


def test_javascript_empty_dict_raises_where_upstream_returns_null():
    """DIVERGENCE: empty dict → null upstream (createAction returns null with
    no /S, the cast of null succeeds); pypdfbox raises OSError (no /JS body)."""
    node = _js_node()
    assert _UPSTREAM["js:dict_empty"] == "null"
    with pytest.raises(OSError):
        node.convert_cos_to_value(COSDictionary())


def test_javascript_js_stream_body_decoded_to_str():
    """A /JS stream is decoded to its str body (upstream wraps as
    PDActionJavaScript; pypdfbox returns the decoded source)."""
    node = _js_node()
    assert _UPSTREAM["js:dict_js_stream"] == "PDActionJavaScript"
    d = COSDictionary()
    d.set_item(_S, _JAVA_SCRIPT)
    stream = COSStream()
    with stream.create_output_stream() as os_:
        os_.write(b"app.print()")
    d.set_item(_JS, stream)
    assert node.convert_cos_to_value(d) == "app.print()"


def test_javascript_round_trip_str_to_action_dict():
    """convert_value_to_cos(str) builds an /S=/JavaScript /JS=body action dict
    that round-trips back to the same body."""
    node = _js_node()
    cos = node.convert_value_to_cos("console.log(1)")
    assert isinstance(cos, COSDictionary)
    assert cos.get_dictionary_object(_S) is _JAVA_SCRIPT
    assert node.convert_cos_to_value(cos) == "console.log(1)"


# ---------------------------------------------------------------------------
# pypdfbox-only subclasses (no upstream counterpart in the 3.0.7 jar):
# URLS / IDS / Pages / Templates / Renditions / AlternatePresentations.
# Hand-tested for internal consistency of the convert pair.
# ---------------------------------------------------------------------------

_DICT_ONLY_SUBCLASSES = [
    PDURLSNameTreeNode,
    PDPagesNameTreeNode,
    PDTemplatesNameTreeNode,
    PDRenditionsNameTreeNode,
    PDAlternatePresentationsNameTreeNode,
]
_DICT_ONLY_IDS = [c.__name__ for c in _DICT_ONLY_SUBCLASSES]


@pytest.mark.parametrize("cls", _DICT_ONLY_SUBCLASSES, ids=_DICT_ONLY_IDS)
def test_dict_only_subclass_dict_is_identity_round_trip(cls):
    node = cls()
    d = COSDictionary()
    d.set_string(COSName.get_pdf_name("X"), "y")
    value = node.convert_cos_to_value(d)
    assert value is d
    assert node.convert_value_to_cos(value) is d


@pytest.mark.parametrize("cls", _DICT_ONLY_SUBCLASSES, ids=_DICT_ONLY_IDS)
@pytest.mark.parametrize(
    "leaf",
    [COSString("s"), COSInteger.get(1), COSName.get_pdf_name("N"), COSArray(), None],
    ids=["cosstring", "cosint", "cosname", "cosarray", "none"],
)
def test_dict_only_subclass_wrong_type_raises(cls, leaf):
    node = cls()
    with pytest.raises(OSError):
        node.convert_cos_to_value(leaf)


def test_ids_string_to_bytes_round_trip():
    node = PDIDSNameTreeNode()
    raw = b"\x01\x02ABC"
    value = node.convert_cos_to_value(COSString(raw))
    assert value == raw
    cos = node.convert_value_to_cos(value)
    assert isinstance(cos, COSString)
    assert cos.get_bytes() == raw


@pytest.mark.parametrize(
    "leaf",
    [COSDictionary(), COSInteger.get(1), COSName.get_pdf_name("N"), COSArray(), None],
    ids=["cosdict", "cosint", "cosname", "cosarray", "none"],
)
def test_ids_wrong_type_raises(leaf):
    node = PDIDSNameTreeNode()
    with pytest.raises(OSError):
        node.convert_cos_to_value(leaf)
