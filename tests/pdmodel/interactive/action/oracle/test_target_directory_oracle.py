"""Live PDFBox differential parity for ``PDTargetDirectory`` (the ``/T`` target
chain of an embedded-GoTo / ``GoToE`` action).

The class had no dedicated oracle probe. This module pins what upstream Apache
PDFBox 3.0.7 actually does, and surfaces the typed-return divergences pypdfbox
deliberately adopted.

AT PARITY (asserted) — the typed-return divergences were CLOSED in wave 1494
(see CHANGES.md): the accessors now mirror upstream verbatim:
* the no-arg constructor produces an EMPTY dictionary — no default ``/R`` is
  stamped (this was a pypdfbox bug, fixed wave 1493: the constructor previously
  wrote ``/R = C``);
* ``getFilename`` / ``getAnnotationName`` string round-trips;
* the chained ``/T`` target wrapper;
* the saved wire form (``A,N,P,R``) after a full integer-form set pass;
* ``getPageNumber()`` / ``getAnnotationIndex()`` are ``getInt(..., -1)``-backed
  and return ``-1`` for an absent / string-form ``/P`` / ``/A``;
* ``getNamedDestination()`` returns a :class:`PDNamedDestination` wrapper
  (probe prints its class identity);
* ``getRelationship()`` returns a :class:`COSName`.

Java side: ``oracle/probes/TargetDirectoryProbe.java``.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.action.pd_target_directory import (
    PDTargetDirectory,
)
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDNamedDestination,
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
    # getInt(-1)-backed integer getters: absent /P /A -> -1 (NOT None).
    assert str(e.get_page_number()) == java["empty.pageNumber"]
    assert str(e.get_annotation_index()) == java["empty.annotationIndex"]
    # getNamedDestination -> None when /P absent.
    assert e.get_named_destination() is None

    # Integer-form set pass and wire shape.
    p = PDTargetDirectory()
    p.set_relationship(COSName.get_pdf_name("P"))
    p.set_filename("inner.pdf")
    p.set_page_number(3)
    p.set_annotation_index(2)
    assert p.get_filename() == java["int.filename"]
    assert str(p.get_page_number()) == java["int.pageNumber"]
    assert str(p.get_annotation_index()) == java["int.annotationIndex"]
    # getRelationship returns a COSName; the Java probe prints COSName.toString()
    # ("COSName{P}"). Compare the resolved name against the dumped form.
    rel = p.get_relationship()
    assert rel is not None
    assert java["int.relationship"] == f"COSName{{{rel.get_name()}}}"

    keys = sorted(k.get_name() for k in p.get_cos_object().key_set())
    assert ",".join(keys) == java["wire.keys"]

    # String forms: /P named destination, /A annotation name.
    s = PDTargetDirectory()
    s.get_cos_object().set_string(COSName.get_pdf_name("P"), "MyDest")
    s.get_cos_object().set_string(COSName.get_pdf_name("A"), "AnnotNM")
    assert s.get_annotation_name() == java["str.annotationName"]
    # getInt(-1) over a string-form /P /A -> -1.
    assert str(s.get_page_number()) == java["str.pageNumber"]
    assert str(s.get_annotation_index()) == java["str.annotationIndex"]
    # getNamedDestination returns a PDNamedDestination wrapper. The Java probe
    # prints the class identity (PDNamedDestination@<hash>) — assert the Python
    # side is the same wrapper type carrying the same name string.
    named = s.get_named_destination()
    assert isinstance(named, PDNamedDestination)
    assert named.get_named_destination() == "MyDest"
    assert "PDNamedDestination@" in java["str.namedDestination"]

    # Chained target.
    parent = PDTargetDirectory()
    child = PDTargetDirectory()
    child.set_filename("deep.pdf")
    parent.set_target_directory(child)
    assert (
        "present" if parent.get_target_directory() is not None else "NULL"
    ) == java["chain.target"]
    assert parent.get_target_directory().get_filename() == java["chain.target.filename"]
