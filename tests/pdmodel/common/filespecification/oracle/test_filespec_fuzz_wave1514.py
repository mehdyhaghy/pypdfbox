"""Differential fuzz audit for file-specification + embedded-file parsing
leniency vs Apache PDFBox 3.0.7 (wave 1514, agent B).

Complements the well-formed file-specification parity suites (round-trip
filename accessors, embedded-file stream + ``/Params`` date round-trips) — none
of which exercise the MALFORMED subset this audit targets:

* ``PDFileSpecification.create_fs`` dispatch: base is a ``COSString`` (simple),
  a ``COSDictionary`` (complex), ``None``, or a wrong type (``COSName`` /
  ``COSInteger`` / ``COSArray`` / ``COSBoolean``) — the last group must raise.
* ``get_filename`` precedence: which of ``/UF`` ``/DOS`` ``/Mac`` ``/Unix``
  ``/F`` wins when several are present, some missing, some wrong-type (a name /
  number where a string is expected falls back to the next slot).
* ``/EF`` embedded-file sub-dictionary: ``/F`` ``/UF`` ``/DOS`` ``/Mac``
  ``/Unix`` as a stream / non-stream / absent; ``/EF`` itself a non-dictionary;
  an empty ``/EF``.
* embedded-file ``/Params``: ``/Size`` ``/CreationDate`` ``/ModDate``
  ``/CheckSum`` ``/Subtype`` present / wrong-type / absent.
* ``/Desc`` description present / wrong-type / absent; ``/Type`` ``/FS``
  variants.

Both sides are driven on the SAME bytes: the corpus builder writes a one-page
PDF per case whose document catalog carries the mutated file-spec base stored
under the custom key ``/FSProbe``, plus a ``manifest.txt`` (one case name per
line, in order) into a tmp dir. The Java probe
(``oracle/probes/FileSpecFuzzProbe.java``) loads each ``<case>.pdf``, reads the
catalog ``/FSProbe`` entry, dispatches it through ``createFS`` and projects a
stable framed line; this module reads the exact same files and projects the
identical grammar through pypdfbox, then asserts line-for-line parity.

Line grammar (one per case, manifest order)::

    CASE <name> class=<simpleName|null|ERR:Exc> file=<F|null>
        filename=<preferred|null> ef=<slots|none> desc=<Desc|null>
        embedded=<params-projection|none>

Java is ground truth: a real divergence is a production fix in
``pypdfbox/pdmodel/common/filespecification/``; a defensible divergence is
pinned in ``_PINNED`` with a matching CHANGES.md row.
"""

from __future__ import annotations

from pathlib import Path

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSBoolean,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.common.filespecification.pd_complex_file_specification import (
    PDComplexFileSpecification,
)
from pypdfbox.pdmodel.common.filespecification.pd_embedded_file import PDEmbeddedFile
from pypdfbox.pdmodel.common.filespecification.pd_file_specification import (
    PDFileSpecification,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------------- helpers

_N = COSName.get_pdf_name
_FS_PROBE = _N("FSProbe")


def _arr(*items: COSBase) -> COSArray:
    a = COSArray()
    for it in items:
        a.add(it)
    return a


def _ef_stream(data: bytes = b"hello") -> COSStream:
    """A minimal embedded-file stream (``/Type /EmbeddedFile``)."""
    s = COSStream()
    s.set_item(_N("Type"), _N("EmbeddedFile"))
    out = s.create_output_stream()
    out.write(data)
    out.close()
    return s


def _ef_stream_with_params(
    *,
    size: int | None = None,
    subtype: str | None = None,
    cksum: bytes | None = None,
    cdate: str | None = None,
    mdate: str | None = None,
    bad_size: COSBase | None = None,
    bad_subtype: COSBase | None = None,
    bad_cksum: COSBase | None = None,
) -> COSStream:
    s = _ef_stream()
    if subtype is not None:
        s.set_name(_N("Subtype"), subtype)
    if bad_subtype is not None:
        s.set_item(_N("Subtype"), bad_subtype)
    params = COSDictionary()
    has_params = False
    if size is not None:
        params.set_int(_N("Size"), size)
        has_params = True
    if bad_size is not None:
        params.set_item(_N("Size"), bad_size)
        has_params = True
    if cksum is not None:
        cs = COSString(cksum)
        cs.set_force_hex_form(True)
        params.set_item(_N("CheckSum"), cs)
        has_params = True
    if bad_cksum is not None:
        params.set_item(_N("CheckSum"), bad_cksum)
        has_params = True
    if cdate is not None:
        params.set_item(_N("CreationDate"), COSString(cdate))
        has_params = True
    if mdate is not None:
        params.set_item(_N("ModDate"), COSString(mdate))
        has_params = True
    if has_params:
        s.set_item(_N("Params"), params)
    return s


# --------------------------------------------------------------------- corpus


def _build_corpus() -> dict[str, COSBase]:
    cases: dict[str, COSBase] = {}

    # ----- createFS dispatch corners ---------------------------------------
    cases["simple_string"] = COSString("simple.txt")
    cases["simple_empty_string"] = COSString("")
    cases["dispatch_name_wrong_type"] = _N("Foo")
    cases["dispatch_int_wrong_type"] = COSInteger(42)
    cases["dispatch_array_wrong_type"] = _arr(COSInteger(1), COSInteger(2))
    cases["dispatch_bool_wrong_type"] = COSBoolean.TRUE

    # ----- complex: empty / type / FS variants -----------------------------
    d = COSDictionary()
    cases["complex_empty_dict"] = d

    d = COSDictionary()
    d.set_item(_N("Type"), _N("Filespec"))
    cases["complex_type_only"] = d

    d = COSDictionary()
    d.set_item(_N("Type"), _N("Filespec"))
    d.set_item(_N("FS"), _N("URL"))
    d.set_string(_N("F"), "http://example.com/x.pdf")
    cases["complex_fs_url"] = d

    # ----- /F /UF /DOS /Mac /Unix presence + precedence --------------------
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    cases["filename_f_only"] = d

    d = COSDictionary()
    d.set_string(_N("UF"), "uf.txt")
    cases["filename_uf_only"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_string(_N("UF"), "uf.txt")
    cases["filename_uf_wins_over_f"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_string(_N("DOS"), "dos.txt")
    d.set_string(_N("Mac"), "mac.txt")
    d.set_string(_N("Unix"), "unix.txt")
    cases["filename_dos_wins_over_mac_unix_f"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_string(_N("Mac"), "mac.txt")
    d.set_string(_N("Unix"), "unix.txt")
    cases["filename_mac_wins_over_unix_f"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_string(_N("Unix"), "unix.txt")
    cases["filename_unix_wins_over_f"] = d

    # /UF present but wrong type (a name) -> falls back to next (DOS), then F
    d = COSDictionary()
    d.set_item(_N("UF"), _N("notastring"))
    d.set_string(_N("DOS"), "dos.txt")
    d.set_string(_N("F"), "f.txt")
    cases["filename_uf_wrong_type_falls_to_dos"] = d

    # /UF and /DOS wrong type -> falls all the way to /F
    d = COSDictionary()
    d.set_item(_N("UF"), COSInteger(1))
    d.set_item(_N("DOS"), _arr(COSInteger(1)))
    d.set_string(_N("F"), "f.txt")
    cases["filename_uf_dos_wrong_type_falls_to_f"] = d

    # /F wrong type and nothing else -> filename null
    d = COSDictionary()
    d.set_item(_N("F"), COSInteger(7))
    cases["filename_f_wrong_type_only"] = d

    # ----- /Desc description ------------------------------------------------
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_string(_N("Desc"), "a description")
    cases["desc_present"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_item(_N("Desc"), _N("nameNotString"))
    cases["desc_wrong_type"] = d

    # ----- /EF embedded-file sub-dictionary --------------------------------
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    ef = COSDictionary()
    ef.set_item(_N("F"), _ef_stream())
    d.set_item(_N("EF"), ef)
    cases["ef_f_stream"] = d

    d = COSDictionary()
    d.set_string(_N("UF"), "uf.txt")
    ef = COSDictionary()
    ef.set_item(_N("UF"), _ef_stream())
    d.set_item(_N("EF"), ef)
    cases["ef_uf_stream"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    ef = COSDictionary()
    ef.set_item(_N("F"), _ef_stream())
    ef.set_item(_N("UF"), _ef_stream())
    ef.set_item(_N("DOS"), _ef_stream())
    ef.set_item(_N("Mac"), _ef_stream())
    ef.set_item(_N("Unix"), _ef_stream())
    d.set_item(_N("EF"), ef)
    cases["ef_all_slots_streams"] = d

    # /EF/F present but NOT a stream (a plain dict) -> not an embedded file
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    ef = COSDictionary()
    ef.set_item(_N("F"), COSDictionary())
    d.set_item(_N("EF"), ef)
    cases["ef_f_non_stream_dict"] = d

    # /EF/F a name (wrong type)
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    ef = COSDictionary()
    ef.set_item(_N("F"), _N("notastream"))
    d.set_item(_N("EF"), ef)
    cases["ef_f_wrong_type_name"] = d

    # /EF itself not a dictionary (an array)
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_item(_N("EF"), _arr(COSInteger(1)))
    cases["ef_not_a_dict"] = d

    # /EF present but empty
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_item(_N("EF"), COSDictionary())
    cases["ef_empty_dict"] = d

    # ----- embedded-file /Params -------------------------------------------
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    ef = COSDictionary()
    ef.set_item(
        _N("F"),
        _ef_stream_with_params(
            size=5,
            subtype="application/pdf",
            cksum=b"\x00\x01\x02\x03\x04\x05\x06\x07"
            b"\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f",
            cdate="D:20240102030405Z",
            mdate="D:20240607080910+02'00'",
        ),
    )
    d.set_item(_N("EF"), ef)
    cases["params_full"] = d

    # /Params/Size wrong type (a string)
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    ef = COSDictionary()
    ef.set_item(
        _N("F"),
        _ef_stream_with_params(bad_size=COSString("notnum")),
    )
    d.set_item(_N("EF"), ef)
    cases["params_size_wrong_type"] = d

    # /Subtype wrong type (a number)
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    ef = COSDictionary()
    ef.set_item(
        _N("F"),
        _ef_stream_with_params(bad_subtype=COSInteger(3)),
    )
    d.set_item(_N("EF"), ef)
    cases["params_subtype_wrong_type"] = d

    # /CheckSum wrong type (a name)
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    ef = COSDictionary()
    ef.set_item(
        _N("F"),
        _ef_stream_with_params(bad_cksum=_N("notchecksum")),
    )
    d.set_item(_N("EF"), ef)
    cases["params_cksum_wrong_type"] = d

    # embedded file with NO /Params at all
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    ef = COSDictionary()
    ef.set_item(_N("F"), _ef_stream())
    d.set_item(_N("EF"), ef)
    cases["params_absent"] = d

    # malformed date strings in /Params
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    ef = COSDictionary()
    ef.set_item(
        _N("F"),
        _ef_stream_with_params(cdate="garbage", mdate="D:99999999"),
    )
    d.set_item(_N("EF"), ef)
    cases["params_bad_dates"] = d

    return cases


def _write_case_pdf(path: Path, base: COSBase) -> None:
    """Build a one-page PDF whose catalog carries ``base`` under ``/FSProbe``."""
    from pypdfbox.pdmodel.pd_page import PDPage

    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.get_document_catalog().get_cos_object().set_item(_FS_PROBE, base)
        doc.save(str(path))
    finally:
        doc.close()


# ----------------------------------------------------- Python-side projection


def _nz(s: str | None) -> str:
    return "null" if s is None else s


def _filename_of(fs: PDFileSpecification) -> str:
    try:
        if isinstance(fs, PDComplexFileSpecification):
            return _nz(fs.get_filename())
        return _nz(fs.get_file())
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


def _ef_slots(fs: PDComplexFileSpecification) -> str:
    parts: list[str] = []
    try:
        if fs.get_embedded_file() is not None:
            parts.append("F")
        if fs.get_embedded_file_unicode() is not None:
            parts.append("UF")
        if fs.get_embedded_file_dos() is not None:
            parts.append("DOS")
        if fs.get_embedded_file_mac() is not None:
            parts.append("Mac")
        if fs.get_embedded_file_unix() is not None:
            parts.append("Unix")
    except Exception as e:
        return f"ERR:{_java_exc(e)}"
    return "+".join(parts) if parts else "none"


def _embedded_projection(fs: PDComplexFileSpecification) -> str:
    try:
        ef: PDEmbeddedFile | None = fs.get_embedded_file()
    except Exception as e:
        return f"ERR:{_java_exc(e)}"
    if ef is None:
        return "none"
    parts: list[str] = []
    try:
        parts.append(f"size={ef.get_size()}")
    except Exception as e:
        parts.append(f"size=ERR:{_java_exc(e)}")
    try:
        parts.append(f"subtype={_nz(ef.get_subtype())}")
    except Exception as e:
        parts.append(f"subtype=ERR:{_java_exc(e)}")
    try:
        parts.append(
            f"cksum={'absent' if ef.get_check_sum() is None else 'present'}"
        )
    except Exception as e:
        parts.append(f"cksum=ERR:{_java_exc(e)}")
    try:
        parts.append(
            f"cdate={'absent' if ef.get_creation_date() is None else 'present'}"
        )
    except Exception as e:
        parts.append(f"cdate=ERR:{_java_exc(e)}")
    try:
        parts.append(
            f"mdate={'absent' if ef.get_mod_date() is None else 'present'}"
        )
    except Exception as e:
        parts.append(f"mdate=ERR:{_java_exc(e)}")
    return ",".join(parts)


def _java_exc(exc: Exception) -> str:
    """Map a pypdfbox exception to the Java exception simple-name the probe
    would report for the same failure (createFS raises IOException upstream →
    OSError here)."""
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        return prefix + (
            f"class=ERR:{_java_exc(e)} file=ERR filename=ERR "
            "ef=ERR desc=ERR embedded=ERR"
        )
    try:
        cat = doc.get_document_catalog()
        base = cat.get_cos_object().get_dictionary_object(_FS_PROBE)
        try:
            fs = PDFileSpecification.create_fs(base)
        except Exception as e:
            return prefix + (
                f"class=ERR:{_java_exc(e)} file=ERR filename=ERR "
                "ef=ERR desc=ERR embedded=ERR"
            )
        if fs is None:
            return prefix + (
                "class=null file=null filename=null ef=none desc=null "
                "embedded=none"
            )
        out = prefix + f"class={type(fs).__name__}"
        try:
            file = _nz(fs.get_file())
        except Exception as e:
            file = f"ERR:{_java_exc(e)}"
        out += f" file={file}"
        out += f" filename={_filename_of(fs)}"
        if isinstance(fs, PDComplexFileSpecification):
            out += f" ef={_ef_slots(fs)}"
            try:
                desc = _nz(fs.get_file_description())
            except Exception as e:
                desc = f"ERR:{_java_exc(e)}"
            out += f" desc={desc}"
            out += f" embedded={_embedded_projection(fs)}"
        else:
            out += " ef=none desc=null embedded=none"
        return out
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
# No divergences pinned in this wave — every case asserts hard parity.
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_filespec_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated file-spec base dispatches + parses identically on
    pypdfbox and Apache PDFBox 3.0.7: same concrete class, same /F, same
    preferred filename precedence, same /EF stream slots, same /Desc, same
    embedded /Params projection. Divergences are pinned in ``_PINNED`` (with a
    matching CHANGES.md row)."""
    corpus = _build_corpus()
    for name, base in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", base)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("FileSpecFuzzProbe", str(tmp_path))
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

    assert not mismatches, "filespec fuzz divergences:\n" + "\n".join(mismatches)
