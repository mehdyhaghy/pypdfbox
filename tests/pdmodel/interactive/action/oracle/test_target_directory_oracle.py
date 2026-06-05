"""Live PDFBox differential parity for ``PDTargetDirectory`` (the ``/T`` target
chain of an embedded-GoTo / ``GoToE`` action).

The class had no dedicated oracle probe. This module pins what upstream Apache
PDFBox 3.0.7 actually does, and surfaces the typed-return divergences pypdfbox
deliberately adopted.

AT PARITY (asserted):
* the no-arg constructor produces an EMPTY dictionary — no default ``/R`` is
  stamped (this was a pypdfbox bug, fixed this wave: the constructor previously
  wrote ``/R = C``);
* ``getFilename`` / ``getAnnotationName`` string round-trips;
* the chained ``/T`` target wrapper;
* the saved wire form (``A,N,P,R``) after a full integer-form set pass.

DEFERRED divergences (strict-xfail, see DEFERRED.md "PDTargetDirectory typed
returns"):
* upstream ``getPageNumber()`` / ``getAnnotationIndex()`` use ``COSDictionary
  .getInt`` and return ``-1`` for absent / string-form values; pypdfbox returns
  ``None``;
* upstream ``getNamedDestination()`` returns a ``PDNamedDestination`` wrapper;
  pypdfbox returns the raw ``str``;
* upstream ``getRelationship()`` returns a ``COSName``; pypdfbox returns ``str``.

Java side: ``oracle/probes/TargetDirectoryProbe.java``.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
    PDTargetDirectory,
)
from tests.oracle.harness import requires_oracle, run_probe_text


def _probe_map() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in run_probe_text("TargetDirectoryProbe").splitlines():
        key, _, value = line.partition("=")
        out[key] = value
    return out


@requires_oracle
def test_target_directory_at_parity_matches_pdfbox() -> None:
    java = _probe_map()

    # No-arg constructor: empty dictionary, no default /R.
    e = PDTargetDirectory()
    assert e.get_cos_object().size() == 0
    assert (
        "NULL" if e.get_relationship() is None else e.get_relationship()
    ) == java["empty.relationship"]
    assert (
        "NULL" if e.get_filename() is None else e.get_filename()
    ) == java["empty.filename"]
    assert (
        "NULL" if e.get_annotation_name() is None else e.get_annotation_name()
    ) == java["empty.annotationName"]
    assert (
        "present" if e.get_target_directory() is not None else "NULL"
    ) == java["empty.targetDirectory"]

    # Integer-form set pass and wire shape.
    p = PDTargetDirectory()
    p.set_relationship("P")
    p.set_filename("inner.pdf")
    p.set_page_number(3)
    p.set_annotation_index(2)
    assert p.get_filename() == java["int.filename"]
    assert str(p.get_page_number()) == java["int.pageNumber"]
    assert str(p.get_annotation_index()) == java["int.annotationIndex"]

    keys = sorted(k.get_name() for k in p.get_cos_object().key_set())
    assert ",".join(keys) == java["wire.keys"]

    # /A as annotation-name string form.
    s = PDTargetDirectory()
    s.get_cos_object().set_string(COSName.get_pdf_name("A"), "AnnotNM")
    assert s.get_annotation_name() == java["str.annotationName"]

    # Chained target.
    parent = PDTargetDirectory()
    child = PDTargetDirectory()
    child.set_filename("deep.pdf")
    parent.set_target_directory(child)
    assert (
        "present" if parent.get_target_directory() is not None else "NULL"
    ) == java["chain.target"]
    assert parent.get_target_directory().get_filename() == java["chain.target.filename"]


@requires_oracle
@pytest.mark.xfail(
    strict=True,
    reason="DEFERRED: pypdfbox getPageNumber/getAnnotationIndex return None for "
    "absent/string-form /P /A; upstream getInt-backed accessors return -1.",
)
def test_integer_getter_default_matches_pdfbox() -> None:
    java = _probe_map()
    e = PDTargetDirectory()
    # Upstream: -1. pypdfbox: None -> str(None) != "-1", so this xfails.
    assert str(e.get_page_number()) == java["empty.pageNumber"]
    assert str(e.get_annotation_index()) == java["empty.annotationIndex"]


@requires_oracle
@pytest.mark.xfail(
    strict=True,
    reason="DEFERRED: pypdfbox getNamedDestination returns a raw str; upstream "
    "returns a PDNamedDestination wrapper (probe prints its object identity).",
)
def test_named_destination_return_type_matches_pdfbox() -> None:
    java = _probe_map()
    s = PDTargetDirectory()
    s.get_cos_object().set_string(COSName.get_pdf_name("P"), "MyDest")
    # Upstream prints a PDNamedDestination@<hash>; pypdfbox returns "MyDest".
    assert s.get_named_destination() == java["str.namedDestination"]
