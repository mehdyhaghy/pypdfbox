"""Live Apache PDFBox differential fuzz of the AcroForm /XFA entry + top-level
AcroForm dict accessors (wave 1560, agent E).

The well-formed AcroForm oracle suite (``test_acro_form_accessor_oracle``,
``test_field_flags_oracle``, …) only exercises syntactically valid forms.
``test_acroform_field_fuzz_wave1513`` fuzzes the per-field dict subset. This
probe targets the FORM-level surface a buggy / hostile producer can emit:

* ``/XFA`` as a single ``COSStream`` vs a packet array
  ``[name stream name stream …]`` — well-formed pairs, odd-length arrays,
  non-stream entries, name labels as ``COSName`` vs ``COSString``;
* ``/XFA`` absent / wrong-type (dict / number / bool);
* ``/DA`` missing / string / name / number; ``/DR`` missing / dict / non-dict;
* ``/NeedAppearances`` bool / non-bool; ``/SigFlags`` int / non-int;
* ``/CO`` calc-order array malformed / non-array;
* ``/Fields`` non-array / containing non-dict.

Strategy mirrors ``test_acroform_field_fuzz_wave1513``: hand-build a
deterministic corpus of minimal PDFs (some carrying real stream objects for the
XFA payload) into ``tmp_path`` plus a ``manifest.txt`` (one case name per line,
in order). Both this test and ``XfaAcroFormFuzzProbe`` read the exact same bytes
on disk. Both sides take the AcroForm with NO fixup (``get_acro_form(None)`` /
``getAcroForm(null)``) so the RAW parse contract is observed.

Validation, not blind pinning: the Java line is ground truth. Each form is
projected to ``hasxfa / xfa-present / xfalen / da / dr / needapp / sigflags /
co / nfields`` (any accessor that throws is rendered ``ERR:<Exc>``).
Divergences are pinned in ``_PINNED_DIVERGENCES`` with a justification.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox import PDDocument
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------- corpus builder


def _obj_body(o: str | bytes) -> bytes:
    """Render one indirect-object body.

    A ``str`` is a plain COS object (dict / array / scalar). A ``bytes`` payload
    of the form ``b"STREAM:" + dict_part + b"\\x00BODY\\x00" + body`` is rendered
    as a stream object with a computed ``/Length``. We use the ``\\x00``
    separators because the XFA stream body is arbitrary XML text.
    """
    if isinstance(o, str):
        return o.encode("latin-1")
    assert o.startswith(b"STREAM:")
    rest = o[len(b"STREAM:") :]
    dict_part, body = rest.split(b"\x00BODY\x00", 1)
    out = bytearray()
    out += b"<<\n"
    out += dict_part
    out += f"\n/Length {len(body)}\n>>\nstream\n".encode("latin-1")
    out += body
    out += b"\nendstream"
    return bytes(out)


def _stream(dict_part: str, body: bytes) -> bytes:
    """Construct a stream-object spec for :func:`_obj_body`."""
    return b"STREAM:" + dict_part.encode("latin-1") + b"\x00BODY\x00" + body


def _build_pdf(
    acroform_body: str,
    extra_objs: list[str | bytes] | None = None,
) -> bytes:
    """Assemble a minimal valid PDF whose ``/AcroForm`` dict (object 3) body is
    ``acroform_body``. Extra indirect objects (5+) may be appended via
    ``extra_objs`` (dict/array/scalar strings or stream specs). The xref offsets
    are computed so both parsers load the file cleanly.
    """
    objs: list[str | bytes] = [
        "<<\n/Type /Catalog\n/Pages 2 0 R\n/AcroForm 3 0 R\n>>",
        "<<\n/Type /Pages\n/Kids [4 0 R]\n/Count 1\n>>",
        "<<\n" + acroform_body + "\n>>",
        "<<\n/Type /Page\n/MediaBox [0 0 612 792]\n/Parent 2 0 R\n>>",
    ]
    if extra_objs:
        objs.extend(extra_objs)
    body = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n".encode("latin-1") + _obj_body(o) + b"\nendobj\n"
    xref_pos = len(body)
    n = len(objs) + 1
    body += f"xref\n0 {n}\n".encode("latin-1")
    body += b"0000000000 65535 f \n"
    for off in offsets:
        body += f"{off:010d} 00000 n \n".encode("latin-1")
    body += b"trailer\n" + f"<<\n/Root 1 0 R\n/Size {n}\n>>\n".encode("latin-1")
    body += f"startxref\n{xref_pos}\n%%EOF".encode("latin-1")
    return bytes(body)


# A minimal text field dict body usable inside /Fields.
_FIELD = "<<\n/FT /Tx\n/T (f1)\n>>"

# XFA packet bodies (kept tiny; only the byte length matters for parity).
_DS = b"<xfa:datasets><xfa:data/></xfa:datasets>"  # 40 bytes
_TMPL = b"<template/>"  # 11 bytes
_CONFIG = b"<config/>"  # 9 bytes


def _build_corpus() -> dict[str, bytes]:
    """Deterministic, seed-free malformed-form corpus, ordered by name."""
    c: dict[str, bytes] = {}

    # ----- baseline -----
    c["bare_form"] = _build_pdf("/Fields []")

    # ----- /XFA as a single stream -----
    c["xfa_single_stream"] = _build_pdf(
        "/Fields []\n/XFA 5 0 R",
        extra_objs=[_stream("", _DS)],
    )
    c["xfa_single_stream_empty"] = _build_pdf(
        "/Fields []\n/XFA 5 0 R",
        extra_objs=[_stream("", b"")],
    )

    # ----- /XFA as a packet array (name stream pairs) -----
    c["xfa_array_one_pair"] = _build_pdf(
        "/Fields []\n/XFA [(datasets) 5 0 R]",
        extra_objs=[_stream("", _DS)],
    )
    c["xfa_array_two_pairs"] = _build_pdf(
        "/Fields []\n/XFA [(template) 5 0 R (datasets) 6 0 R]",
        extra_objs=[_stream("", _TMPL), _stream("", _DS)],
    )
    c["xfa_array_name_labels"] = _build_pdf(
        "/Fields []\n/XFA [/template 5 0 R /datasets 6 0 R]",
        extra_objs=[_stream("", _TMPL), _stream("", _DS)],
    )
    # Odd-length array: trailing label with no following stream.
    c["xfa_array_odd_len"] = _build_pdf(
        "/Fields []\n/XFA [(template) 5 0 R (datasets)]",
        extra_objs=[_stream("", _TMPL)],
    )
    # Pair whose "stream" half is a non-stream (a string).
    c["xfa_array_nonstream_entry"] = _build_pdf(
        "/Fields []\n/XFA [(template) 5 0 R (datasets) (notastream)]",
        extra_objs=[_stream("", _TMPL)],
    )
    # Pair whose "stream" half is a number.
    c["xfa_array_number_entry"] = _build_pdf(
        "/Fields []\n/XFA [(template) 5 0 R (config) 42]",
        extra_objs=[_stream("", _TMPL)],
    )
    # Three streams, but only odd indices are concatenated (index 0,2,4 skipped).
    c["xfa_array_three_pairs"] = _build_pdf(
        "/Fields []\n/XFA [(t) 5 0 R (c) 6 0 R (d) 7 0 R]",
        extra_objs=[_stream("", _TMPL), _stream("", _CONFIG), _stream("", _DS)],
    )
    # Empty array.
    c["xfa_array_empty"] = _build_pdf("/Fields []\n/XFA []")
    # Array of just streams with no labels (degenerate): odd indices only.
    c["xfa_array_streams_only"] = _build_pdf(
        "/Fields []\n/XFA [5 0 R 6 0 R]",
        extra_objs=[_stream("", _TMPL), _stream("", _DS)],
    )

    # ----- /XFA wrong-type -----
    c["xfa_dict"] = _build_pdf("/Fields []\n/XFA 5 0 R", extra_objs=["<<\n/A 1\n>>"])
    c["xfa_number"] = _build_pdf("/Fields []\n/XFA 42")
    c["xfa_bool"] = _build_pdf("/Fields []\n/XFA true")
    c["xfa_name"] = _build_pdf("/Fields []\n/XFA /SomeName")
    c["xfa_absent"] = _build_pdf("/Fields []")

    # ----- /DA typing -----
    c["da_string"] = _build_pdf("/Fields []\n/DA (/Helv 12 Tf 0 g)")
    c["da_name"] = _build_pdf("/Fields []\n/DA /Helv")
    c["da_number"] = _build_pdf("/Fields []\n/DA 12")
    c["da_absent"] = _build_pdf("/Fields []")

    # ----- /DR typing -----
    c["dr_dict"] = _build_pdf(
        "/Fields []\n/DR 5 0 R", extra_objs=["<<\n/Font <<>>\n>>"]
    )
    c["dr_number"] = _build_pdf("/Fields []\n/DR 99")
    c["dr_array"] = _build_pdf("/Fields []\n/DR [1 2 3]")
    c["dr_absent"] = _build_pdf("/Fields []")

    # ----- /NeedAppearances typing -----
    c["needapp_true"] = _build_pdf("/Fields []\n/NeedAppearances true")
    c["needapp_false"] = _build_pdf("/Fields []\n/NeedAppearances false")
    c["needapp_number"] = _build_pdf("/Fields []\n/NeedAppearances 1")
    c["needapp_string"] = _build_pdf("/Fields []\n/NeedAppearances (true)")
    c["needapp_absent"] = _build_pdf("/Fields []")

    # ----- /SigFlags typing -----
    c["sigflags_int"] = _build_pdf("/Fields []\n/SigFlags 3")
    c["sigflags_real"] = _build_pdf("/Fields []\n/SigFlags 3.0")
    c["sigflags_string"] = _build_pdf("/Fields []\n/SigFlags (3)")
    c["sigflags_absent"] = _build_pdf("/Fields []")

    # ----- /CO calc-order typing -----
    c["co_array_dicts"] = _build_pdf(
        "/Fields [5 0 R]\n/CO [5 0 R]",
        extra_objs=["<<\n/FT /Tx\n/T (f1)\n>>"],
    )
    c["co_array_nondict"] = _build_pdf("/Fields []\n/CO [1 2 3]")
    c["co_not_array"] = _build_pdf("/Fields []\n/CO 5")
    c["co_empty"] = _build_pdf("/Fields []\n/CO []")
    c["co_absent"] = _build_pdf("/Fields []")

    # ----- /Fields typing -----
    c["fields_nonarray"] = _build_pdf("/Fields 42")
    c["fields_nondict_entries"] = _build_pdf("/Fields [1 2 (x)]")
    c["fields_one_dict"] = _build_pdf(
        "/Fields [5 0 R]", extra_objs=[_FIELD]
    )
    c["fields_missing"] = _build_pdf("/DA (/Helv 0 Tf 0 g)")

    return c


# --------------------------------------------------------------- projection


def _esc(s: str | None) -> str:
    if s is None:
        return "null"
    return (
        s.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
        .replace(" ", "\\s")
    )


def _err(e: BaseException) -> str:
    return "ERR:" + type(e).__name__


def _has_xfa(form: object) -> str:
    try:
        return str(form.has_xfa()).lower()
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _xfa_present(form: object) -> str:
    try:
        return "present" if form.get_xfa() is not None else "absent"
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _xfa_len(form: object) -> str:
    try:
        xfa = form.get_xfa()
        if xfa is None:
            return "-"
        b = xfa.get_bytes()
        return "null" if b is None else str(len(b))
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _da(form: object) -> str:
    try:
        return _esc(form.get_default_appearance())
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _dr(form: object) -> str:
    try:
        return "present" if form.get_default_resources() is not None else "absent"
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _need_app(form: object) -> str:
    try:
        return str(form.get_need_appearances()).lower()
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _sig_flags(form: object) -> str:
    try:
        return str(form.get_signature_flags())
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _co(form: object) -> str:
    try:
        return str(len(form.get_calc_order()))
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _nfields(form: object) -> str:
    try:
        return str(len(form.get_fields()))
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _py_case(name: str, data: bytes) -> str:
    """Project pypdfbox's parse of one case to the probe's single-line grammar."""
    try:
        doc = PDDocument.load(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001 - contract probe
        return f"CASE {name} form=ERR:{type(e).__name__}"
    try:
        cat = doc.get_document_catalog()
        try:
            form = cat.get_acro_form(None)
        except Exception as e:  # noqa: BLE001 - contract probe
            return f"CASE {name} form={_err(e)}"
        if form is None:
            return f"CASE {name} form=absent"
        return (
            f"CASE {name} form=present hasxfa={_has_xfa(form)} "
            f"xfa={_xfa_present(form)} xfalen={_xfa_len(form)} da={_da(form)} "
            f"dr={_dr(form)} needapp={_need_app(form)} "
            f"sigflags={_sig_flags(form)} co={_co(form)} nfields={_nfields(form)}"
        )
    finally:
        doc.close()


def _group_java(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in raw.splitlines():
        if line.startswith("CASE "):
            out[line.split()[1]] = line
    return out


# Pinned, intentional divergences from the Java per-form projection. Each entry
# maps a case name to the pypdfbox CASE line. Cross-checked against upstream
# behaviour with a matching CHANGES.md (wave 1560) row.
_PINNED_DIVERGENCES: dict[str, str] = {}


# --------------------------------------------------------------------- the test


@requires_oracle
def test_xfa_acro_form_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed-form case parses identically on pypdfbox and Apache
    PDFBox 3.0.7: same form presence and the same ``hasxfa / xfa-present /
    xfalen / da / dr / needapp / sigflags / co / nfields`` projection (with any
    throwing accessor rendered ``ERR:<Exc>``). Divergences are pinned in
    ``_PINNED_DIVERGENCES`` with a reason."""
    corpus = _build_corpus()
    for name, data in corpus.items():
        (tmp_path / f"{name}.pdf").write_bytes(data)
    (tmp_path / "manifest.txt").write_text("\n".join(corpus) + "\n", encoding="utf-8")

    raw = run_probe_text("XfaAcroFormFuzzProbe", str(tmp_path))
    java = _group_java(raw)
    assert len(java) == len(corpus), (
        f"probe emitted {len(java)} cases for {len(corpus)}:\n{raw}"
    )

    mismatches: list[str] = []
    for name in corpus:
        j_line = java.get(name, "<MISSING>")
        p_line = _py_case(name, corpus[name])
        expected = _PINNED_DIVERGENCES.get(name, j_line)
        if p_line != expected:
            mismatches.append(f"{name}:\n  JAVA: {j_line}\n  PY:   {p_line}")

    assert not mismatches, "form-parse divergence(s):\n" + "\n\n".join(mismatches)
