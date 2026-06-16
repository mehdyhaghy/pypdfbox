"""Differential fuzz audit for file-specification platform-filename + volatile
parsing leniency vs Apache PDFBox 3.0.7 (wave 1540, agent E).

Wave 1514 (``test_filespec_fuzz_wave1514.py``) covered ``create_fs`` dispatch,
``get_filename`` precedence, ``/EF`` stream slots, ``/Desc`` and the embedded
``/Params`` projection. This wave drives the SAME shared probe
(``oracle/probes/FileSpecFuzzProbe.java``) — whose grammar wave 1540 extended
with four trailing fields ``dos`` / ``mac`` / ``unix`` / ``vol`` — over a
DISJOINT corpus that targets exactly that newly-exposed surface:

* direct ``get_file_dos`` / ``get_file_mac`` / ``get_file_unix`` accessors when
  the matching ``/DOS`` / ``/Mac`` / ``/Unix`` entry is a string / a name
  (wrong type) / a number (wrong type) / absent — a wrong-type entry must read
  back as ``null`` on both sides (``COSDictionary.get_string`` returns ``null``
  for a non-string), and the ``get_filename`` precedence must still see the
  wrong-typed slot as missing and fall through.
* ``/V`` volatile: explicit ``true`` / explicit ``false`` / a non-boolean
  ``/V`` (name / number / array) / absent — ``is_volatile`` must coerce every
  non-boolean (and absence) to the spec default ``false``.
* simple-spec corner: a ``COSString`` base must project ``dos=null mac=null
  unix=null vol=false`` (the four fields are complex-only) and never raise.
* combined: platform names present alongside a volatile flag and a description,
  to confirm the field ordering and the fall-through interactions hold.

Both sides read the EXACT same bytes: the corpus builder writes a one-page PDF
per case whose catalog carries the mutated file-spec base under ``/FSProbe``
plus a ``manifest.txt``. The Java probe dispatches through ``createFS`` and
prints a framed line; this module reproduces the identical grammar through
pypdfbox and asserts line-for-line parity.

Line grammar (one per case, manifest order; shared with wave 1514)::

    CASE <name> class=<simpleName|null|ERR:Exc> file=<F|null>
        filename=<preferred|null> ef=<slots|none> desc=<Desc|null>
        embedded=<params-projection|none> dos=<DOS|null> mac=<Mac|null>
        unix=<Unix|null> vol=<true|false>

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


# --------------------------------------------------------------------- corpus


def _build_corpus() -> dict[str, COSBase]:
    cases: dict[str, COSBase] = {}

    # ----- direct /DOS /Mac /Unix accessors, well-typed --------------------
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_string(_N("DOS"), "dos.txt")
    cases["dos_string"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_string(_N("Mac"), "mac.txt")
    cases["mac_string"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_string(_N("Unix"), "unix.txt")
    cases["unix_string"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_string(_N("DOS"), "dos.txt")
    d.set_string(_N("Mac"), "mac.txt")
    d.set_string(_N("Unix"), "unix.txt")
    cases["dos_mac_unix_all_strings"] = d

    # ----- /DOS /Mac /Unix wrong type -> get_file_* reads null --------------
    # A name where a string is expected: get_string returns null, so the
    # accessor is null AND get_filename must fall through past this slot.
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_item(_N("DOS"), _N("notastring"))
    cases["dos_name_wrong_type"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_item(_N("Mac"), COSInteger(9))
    cases["mac_int_wrong_type"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_item(_N("Unix"), _arr(COSInteger(1)))
    cases["unix_array_wrong_type"] = d

    # All three platform slots wrong-typed: filename falls all the way to /F.
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_item(_N("DOS"), _N("x"))
    d.set_item(_N("Mac"), COSInteger(2))
    d.set_item(_N("Unix"), COSBoolean.TRUE)
    cases["all_platforms_wrong_type_fall_to_f"] = d

    # ----- /V volatile ------------------------------------------------------
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_boolean(_N("V"), True)
    cases["volatile_true"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_boolean(_N("V"), False)
    cases["volatile_false"] = d

    # /V absent -> spec default false.
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    cases["volatile_absent"] = d

    # /V non-boolean -> coerced to default false on both sides.
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_item(_N("V"), _N("true"))
    cases["volatile_name_wrong_type"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_item(_N("V"), COSInteger(1))
    cases["volatile_int_wrong_type"] = d

    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_item(_N("V"), _arr(COSBoolean.TRUE))
    cases["volatile_array_wrong_type"] = d

    # ----- simple spec: platform/volatile fields are complex-only ----------
    cases["simple_string_no_platform_fields"] = COSString("simple.txt")
    cases["simple_empty_string_no_platform_fields"] = COSString("")

    # ----- combined: platforms + volatile + description --------------------
    d = COSDictionary()
    d.set_string(_N("F"), "f.txt")
    d.set_string(_N("UF"), "uf.txt")
    d.set_string(_N("DOS"), "dos.txt")
    d.set_string(_N("Mac"), "mac.txt")
    d.set_string(_N("Unix"), "unix.txt")
    d.set_boolean(_N("V"), True)
    d.set_string(_N("Desc"), "combined case")
    cases["combined_all_fields"] = d

    # Platform names present but NO /F /UF: get_filename prefers /DOS.
    d = COSDictionary()
    d.set_string(_N("DOS"), "dos.txt")
    d.set_string(_N("Mac"), "mac.txt")
    cases["platforms_only_no_f_uf"] = d

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


def _java_exc(exc: Exception) -> str:
    if isinstance(exc, OSError):
        return "IOException"
    return type(exc).__name__


def _safe(fn) -> str:
    try:
        return _nz(fn())
    except Exception as e:
        return f"ERR:{_java_exc(e)}"


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
        parts.append(f"cksum={'absent' if ef.get_check_sum() is None else 'present'}")
    except Exception as e:
        parts.append(f"cksum=ERR:{_java_exc(e)}")
    try:
        parts.append(
            f"cdate={'absent' if ef.get_creation_date() is None else 'present'}"
        )
    except Exception as e:
        parts.append(f"cdate=ERR:{_java_exc(e)}")
    try:
        parts.append(f"mdate={'absent' if ef.get_mod_date() is None else 'present'}")
    except Exception as e:
        parts.append(f"mdate=ERR:{_java_exc(e)}")
    return ",".join(parts)


def _python_line(case_dir: Path, name: str) -> str:
    pdf = case_dir / f"{name}.pdf"
    prefix = f"CASE {name} "
    err_suffix = (
        "file=ERR filename=ERR ef=ERR desc=ERR embedded=ERR "
        "dos=ERR mac=ERR unix=ERR vol=ERR"
    )
    try:
        doc = PDDocument.load(str(pdf))
    except Exception as e:
        return prefix + f"class=ERR:{_java_exc(e)} " + err_suffix
    try:
        cat = doc.get_document_catalog()
        base = cat.get_cos_object().get_dictionary_object(_FS_PROBE)
        try:
            fs = PDFileSpecification.create_fs(base)
        except Exception as e:
            return prefix + f"class=ERR:{_java_exc(e)} " + err_suffix
        if fs is None:
            return prefix + (
                "class=null file=null filename=null ef=none desc=null "
                "embedded=none dos=null mac=null unix=null vol=false"
            )
        out = prefix + f"class={type(fs).__name__}"
        out += f" file={_safe(fs.get_file)}"
        out += f" filename={_filename_of(fs)}"
        if isinstance(fs, PDComplexFileSpecification):
            out += f" ef={_ef_slots(fs)}"
            out += f" desc={_safe(fs.get_file_description)}"
            out += f" embedded={_embedded_projection(fs)}"
            out += f" dos={_safe(fs.get_file_dos)}"
            out += f" mac={_safe(fs.get_file_mac)}"
            out += f" unix={_safe(fs.get_file_unix)}"
            try:
                vol = "true" if fs.is_volatile() else "false"
            except Exception as e:
                vol = f"ERR:{_java_exc(e)}"
            out += f" vol={vol}"
        else:
            out += (
                " ef=none desc=null embedded=none "
                "dos=null mac=null unix=null vol=false"
            )
        return out
    finally:
        doc.close()


# --------------------------------------------------------------------- pins

# name -> (python_line_override, java_line_override, reason).
# No divergences pinned in this wave — every case asserts hard parity.
_PINNED: dict[str, tuple[str, str, str]] = {}


# --------------------------------------------------------------------- test


@requires_oracle
def test_file_spec_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every mutated file spec projects platform-filename + volatile fields
    identically on pypdfbox and Apache PDFBox 3.0.7: same get_file_dos/mac/unix
    (wrong-type entries read null on both sides), same is_volatile coercion of
    non-boolean /V to the spec default false, same simple-spec behaviour.
    Divergences are pinned in ``_PINNED`` with a matching CHANGES.md row."""
    corpus = _build_corpus()
    for name, base in corpus.items():
        _write_case_pdf(tmp_path / f"{name}.pdf", base)
    (tmp_path / "manifest.txt").write_text("\n".join(corpus) + "\n", encoding="utf-8")

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
