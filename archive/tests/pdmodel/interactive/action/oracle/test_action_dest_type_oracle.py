"""Live Apache PDFBox differential parity for the TYPE CONTRACT of
``PDActionGoTo.get_destination`` across the four ``/D`` shapes a GoTo action's
destination may take (PDF 32000-1 §12.6.4.2):

* ``stringnamed`` — ``/D`` is a ``COSString`` named destination.
* ``namenamed``  — ``/D`` is a ``COSName`` named destination.
* ``array``      — ``/D`` is an explicit page-target ``COSArray``.
* ``dictbad``    — ``/D`` is a malformed ``COSDictionary`` (neither).

Upstream ``PDActionGoTo#getDestination`` is a one-liner delegating to
``PDDestination.create`` (PDActionGoTo.java line 66-69); the dispatch is
entirely ``PDDestination.create``'s. Before wave 1491 the Python port
diverged: a name/string ``/D`` was returned as a bare ``str`` rather than a
``PDNamedDestination``. This test pins the Java *class identity* of the
returned destination so the type contract — not just the resolved page — is
oracle-anchored. The grammar must match ``oracle/probes/ActionDestTypeProbe``::

    <label>\\t<javaSimpleClassName>\\t<payload>

The Python ``type(...).__name__`` matches Java's ``getClass().getSimpleName()``
1:1 for these classes (``PDNamedDestination``, ``PDPageXYZDestination``); the
malformed shape raises ``OSError`` / ``IOException`` in both, emitted as
``EXC:<ExceptionType>`` (the exception *type* differs across languages, so the
malformed line is compared on its ``EXC:`` prefix only).
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_go_to import PDActionGoTo
from pypdfbox.pdmodel.interactive.documentnavigation.destination.pd_named_destination import (
    PDNamedDestination,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_D: COSName = COSName.D  # type: ignore[attr-defined]


def _make_action(d: COSBase) -> PDActionGoTo:
    action = PDActionGoTo()
    action.get_cos_object().set_item(_D, d)
    return action


def _python_line(label: str, d: COSBase) -> str:
    action = _make_action(d)
    payload = ""
    try:
        dest = action.get_destination()
        if dest is None:
            type_name = "null"
        else:
            type_name = type(dest).__name__
            if isinstance(dest, PDNamedDestination):
                payload = dest.get_named_destination() or ""
    except OSError as exc:
        type_name = f"EXC:{type(exc).__name__}"
    return f"{label}\t{type_name}\t{payload}"


def _shapes() -> list[tuple[str, COSBase]]:
    page = COSDictionary()
    page.set_name(COSName.get_pdf_name("Type"), "Page")
    arr = COSArray([page, COSName.get_pdf_name("XYZ")])
    return [
        ("stringnamed", COSString("Chapter1")),
        ("namenamed", COSName.get_pdf_name("Chapter2")),
        ("array", arr),
        ("dictbad", COSDictionary()),
    ]


def test_python_type_contract_self_consistent() -> None:
    """The Python port's class identities are stable regardless of the
    oracle being present (the named forms are ``PDNamedDestination``, the
    array form is the concrete page subclass, the malformed dict raises)."""
    lines = {label: _python_line(label, d) for label, d in _shapes()}
    assert lines["stringnamed"] == "stringnamed\tPDNamedDestination\tChapter1"
    assert lines["namenamed"] == "namenamed\tPDNamedDestination\tChapter2"
    assert lines["array"] == "array\tPDPageXYZDestination\t"
    assert lines["dictbad"].startswith("dictbad\tEXC:")


@requires_oracle
def test_action_dest_type_matches_pdfbox() -> None:
    """Differential: pypdfbox ``get_destination`` class identities match
    Apache PDFBox ``getDestination().getClass().getSimpleName()``."""
    java = run_probe_text("ActionDestTypeProbe").strip().splitlines()
    java_by_label = {ln.split("\t", 1)[0]: ln for ln in java}

    for label, d in _shapes():
        py_line = _python_line(label, d)
        java_line = java_by_label[label]
        if label == "dictbad":
            # Both raise (Java IOException / Python OSError); the exception
            # *type* name legitimately differs across languages, so compare
            # only that both report an EXC:* marker.
            assert py_line.startswith(f"{label}\tEXC:")
            assert java_line.startswith(f"{label}\tEXC:")
        else:
            assert py_line == java_line


@pytest.mark.parametrize(
    ("setter_value", "expected_name"),
    [("named-dest", "named-dest"), ("Chapter1", "Chapter1")],
)
def test_set_destination_string_reads_back_as_named_destination(
    setter_value: str, expected_name: str
) -> None:
    """A ``str`` set via ``set_destination`` reads back as a
    ``PDNamedDestination`` carrying the same name (upstream parity)."""
    action = PDActionGoTo()
    action.set_destination(setter_value)
    dest = action.get_destination()
    assert isinstance(dest, PDNamedDestination)
    assert dest.get_named_destination() == expected_name
