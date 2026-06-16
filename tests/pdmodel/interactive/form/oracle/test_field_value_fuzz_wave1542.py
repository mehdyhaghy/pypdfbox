"""Live Apache PDFBox differential fuzz of the PDField VALUE + FLAG-PREDICATE +
NAME surface (wave 1542, agent A).

The existing AcroForm field oracle suite reads only the raw ``get_field_flags()``
int (``test_field_flags_oracle``, ``test_acroform_field_fuzz_wave1513``) and the
value/default/options projection. None of it calls the TYPED FLAG-PREDICATE
METHODS as predicates, nor stresses fully-qualified-name resolution over
pathological ``/T`` chains. This probe isolates, per field:

* the resolved field-type class chosen by the factory + ``get_field_type()``;
* ``is_terminal()`` (PDTerminalField vs PDNonTerminalField);
* the base flag predicates ``is_read_only / is_required / is_no_export``;
* text predicates ``is_multiline / is_password / is_comb / is_file_select /
  do_not_scroll / do_not_spell_check / is_rich_text``;
* button predicates ``is_push_button / is_radio_button`` plus radio
  ``is_radios_in_unison``;
* choice predicates ``is_combo / is_edit / is_multi_select / is_sort /
  is_do_not_spell_check / is_commit_on_sel_change``;
* ``get_value()`` (the TYPED accessor: str for text/button, list for choice)
  DISTINCT from ``get_value_as_string()``;
* ``get_default_value()`` typed;
* ``get_fully_qualified_name()`` across pathological ``/T`` chains
  (missing-/T parent, dotted /T, empty /T, deep nesting).

Strategy mirrors ``test_acroform_field_fuzz_wave1513``: hand-build a deterministic
corpus of minimal-but-valid PDFs plus a ``manifest.txt``; both this test and the
``FieldValueFuzzProbe`` read the exact same bytes on disk and take the AcroForm
with NO fixup (``get_acro_form(None)`` / ``getAcroForm(null)``) so the RAW parse
contract is observed.

Validation, not blind pinning: the Java line is ground truth. Divergences are
pinned in ``_PINNED_DIVERGENCES`` with a justification rather than silently
tolerated. Each pin is pypdfbox being strictly more robust or an unavoidable
Python-vs-Java rendering difference; none weakens a parse check.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox import PDDocument
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from pypdfbox.pdmodel.interactive.form.pd_terminal_field import PDTerminalField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from tests.oracle.harness import requires_oracle, run_probe_text

# --------------------------------------------------------------- corpus builder


def _build_pdf(
    field_body: str,
    acroform_extra: str = "",
    extra_objs: list[str] | None = None,
    fields_ref: str = "5 0 R",
) -> bytes:
    """Assemble a minimal valid PDF whose single AcroForm ``/Fields`` entry is
    object 5 (body ``field_body``). Extra indirect objects (6+) may be appended
    via ``extra_objs``."""
    objs: list[str] = [
        "<<\n/Type /Catalog\n/Pages 2 0 R\n/AcroForm 3 0 R\n>>",
        "<<\n/Type /Pages\n/Kids [4 0 R]\n/Count 1\n>>",
        "<<\n/Fields [" + fields_ref + "]" + acroform_extra + "\n>>",
        "<<\n/Type /Page\n/MediaBox [0 0 612 792]\n/Parent 2 0 R\n>>",
        "<<\n" + field_body + "\n>>",
    ]
    if extra_objs:
        objs.extend(extra_objs)
    body = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n".encode("latin-1") + o.encode("latin-1") + b"\nendobj\n"
    xref_pos = len(body)
    n = len(objs) + 1
    body += f"xref\n0 {n}\n".encode("latin-1")
    body += b"0000000000 65535 f \n"
    for off in offsets:
        body += f"{off:010d} 00000 n \n".encode("latin-1")
    body += b"trailer\n" + f"<<\n/Root 1 0 R\n/Size {n}\n>>\n".encode("latin-1")
    body += f"startxref\n{xref_pos}\n%%EOF".encode("latin-1")
    return bytes(body)


# Flag bit values (PDF 32000-1 Table 226/227/228/229).
_FF_READ_ONLY = 1 << 0
_FF_REQUIRED = 1 << 1
_FF_NO_EXPORT = 1 << 2
_FF_MULTILINE = 1 << 12
_FF_PASSWORD = 1 << 13
_FF_NOTOGGLE = 1 << 14
_FF_RADIO = 1 << 15
_FF_PUSH = 1 << 16
_FF_COMBO = 1 << 17
_FF_EDIT = 1 << 18
_FF_SORT = 1 << 19
_FF_FILE_SELECT = 1 << 20
_FF_MULTI = 1 << 21
_FF_DO_NOT_SPELL = 1 << 22
_FF_DO_NOT_SCROLL = 1 << 23
_FF_COMB = 1 << 24
_FF_RICH = 1 << 25
_FF_RADIOS_UNISON = 1 << 25
_FF_COMMIT = 1 << 26


def _build_corpus() -> dict[str, bytes]:
    """Deterministic, seed-free corpus, ordered by name."""
    c: dict[str, bytes] = {}

    # ----- text-field flag predicate matrix -----
    c["tx_no_flags"] = _build_pdf("/FT /Tx\n/T (f)\n/V (v)")
    c["tx_multiline"] = _build_pdf(f"/FT /Tx\n/T (f)\n/V (v)\n/Ff {_FF_MULTILINE}")
    c["tx_password"] = _build_pdf(f"/FT /Tx\n/T (f)\n/V (v)\n/Ff {_FF_PASSWORD}")
    c["tx_comb_maxlen"] = _build_pdf(
        f"/FT /Tx\n/T (f)\n/V (v)\n/Ff {_FF_COMB}\n/MaxLen 6"
    )
    c["tx_file_select"] = _build_pdf(f"/FT /Tx\n/T (f)\n/V (v)\n/Ff {_FF_FILE_SELECT}")
    c["tx_do_not_scroll"] = _build_pdf(
        f"/FT /Tx\n/T (f)\n/V (v)\n/Ff {_FF_DO_NOT_SCROLL}"
    )
    c["tx_do_not_spell"] = _build_pdf(
        f"/FT /Tx\n/T (f)\n/V (v)\n/Ff {_FF_DO_NOT_SPELL}"
    )
    c["tx_rich_text"] = _build_pdf(f"/FT /Tx\n/T (f)\n/V (v)\n/Ff {_FF_RICH}")
    c["tx_all_text_flags"] = _build_pdf(
        "/FT /Tx\n/T (f)\n/V (v)\n/Ff "
        + str(
            _FF_MULTILINE | _FF_PASSWORD | _FF_COMB | _FF_FILE_SELECT
            | _FF_DO_NOT_SCROLL | _FF_DO_NOT_SPELL | _FF_RICH
        )
    )
    # base RO/REQ/NOX predicates
    c["tx_read_only"] = _build_pdf(f"/FT /Tx\n/T (f)\n/V (v)\n/Ff {_FF_READ_ONLY}")
    c["tx_required"] = _build_pdf(f"/FT /Tx\n/T (f)\n/V (v)\n/Ff {_FF_REQUIRED}")
    c["tx_no_export"] = _build_pdf(f"/FT /Tx\n/T (f)\n/V (v)\n/Ff {_FF_NO_EXPORT}")
    c["tx_ro_req_nox"] = _build_pdf(
        f"/FT /Tx\n/T (f)\n/V (v)\n/Ff {_FF_READ_ONLY | _FF_REQUIRED | _FF_NO_EXPORT}"
    )
    # typed value vs value-as-string for a text field with /DV
    c["tx_v_and_dv"] = _build_pdf("/FT /Tx\n/T (f)\n/V (theval)\n/DV (thedefault)")
    c["tx_dv_only"] = _build_pdf("/FT /Tx\n/T (f)\n/DV (thedefault)")

    # ----- checkbox -----
    c["cb_off"] = _build_pdf("/FT /Btn\n/T (f)\n/V /Off")
    c["cb_on"] = _build_pdf("/FT /Btn\n/T (f)\n/V /Yes")
    c["cb_no_v"] = _build_pdf("/FT /Btn\n/T (f)")
    c["cb_v_string"] = _build_pdf("/FT /Btn\n/T (f)\n/V (Yes)")
    c["cb_dv"] = _build_pdf("/FT /Btn\n/T (f)\n/DV /Yes")
    c["cb_read_only"] = _build_pdf(f"/FT /Btn\n/T (f)\n/V /Yes\n/Ff {_FF_READ_ONLY}")

    # ----- radio -----
    c["radio_v_name"] = _build_pdf(f"/FT /Btn\n/T (f)\n/V /On\n/Ff {_FF_RADIO}")
    c["radio_unison"] = _build_pdf(
        f"/FT /Btn\n/T (f)\n/V /On\n/Ff {_FF_RADIO | _FF_RADIOS_UNISON}"
    )
    c["radio_notoggle"] = _build_pdf(
        f"/FT /Btn\n/T (f)\n/V /On\n/Ff {_FF_RADIO | _FF_NOTOGGLE}"
    )
    c["radio_opt_index"] = _build_pdf(
        f"/FT /Btn\n/T (f)\n/V /1\n/Opt [(Apple) (Banana)]\n/Ff {_FF_RADIO}"
    )

    # ----- pushbutton -----
    c["push"] = _build_pdf(f"/FT /Btn\n/T (f)\n/Ff {_FF_PUSH}")
    c["push_with_v"] = _build_pdf(f"/FT /Btn\n/T (f)\n/V /Ignored\n/Ff {_FF_PUSH}")
    # conflicting push + radio: factory checks radio first -> PDRadioButton.
    c["push_and_radio"] = _build_pdf(
        f"/FT /Btn\n/T (f)\n/V /On\n/Ff {_FF_PUSH | _FF_RADIO}"
    )

    # ----- listbox -----
    c["list_single"] = _build_pdf("/FT /Ch\n/T (f)\n/V (b)\n/Opt [(a) (b) (c)]")
    c["list_multi"] = _build_pdf(
        f"/FT /Ch\n/T (f)\n/V [(a) (c)]\n/Opt [(a) (b) (c)]\n/Ff {_FF_MULTI}"
    )
    c["list_sort"] = _build_pdf(
        f"/FT /Ch\n/T (f)\n/V (a)\n/Opt [(a) (b)]\n/Ff {_FF_SORT}"
    )
    c["list_dv"] = _build_pdf("/FT /Ch\n/T (f)\n/DV (b)\n/Opt [(a) (b)]")
    c["list_no_v"] = _build_pdf("/FT /Ch\n/T (f)\n/Opt [(a) (b)]")

    # ----- combo -----
    c["combo_plain"] = _build_pdf(
        f"/FT /Ch\n/T (f)\n/V (b)\n/Opt [(a) (b)]\n/Ff {_FF_COMBO}"
    )
    c["combo_edit"] = _build_pdf(
        f"/FT /Ch\n/T (f)\n/V (freetext)\n/Opt [(a) (b)]\n/Ff {_FF_COMBO | _FF_EDIT}"
    )
    c["combo_commit_spell"] = _build_pdf(
        f"/FT /Ch\n/T (f)\n/V (a)\n/Opt [(a)]\n"
        f"/Ff {_FF_COMBO | _FF_COMMIT | _FF_DO_NOT_SPELL}"
    )

    # ----- fully-qualified name pathologies -----
    # parent with /T, child with /T -> dotted fqn.
    c["fqn_dotted"] = _build_pdf(
        "/T (parent)\n/FT /Tx\n/Kids [6 0 R]",
        extra_objs=["<<\n/Parent 5 0 R\n/T (child)\n/V (kv)\n>>"],
    )
    # parent WITHOUT /T (only AcroForm-level grouping), child with /T.
    c["fqn_parent_no_t"] = _build_pdf(
        "/FT /Tx\n/Kids [6 0 R]",
        extra_objs=["<<\n/Parent 5 0 R\n/T (child)\n/V (kv)\n>>"],
    )
    # child WITHOUT /T under a named parent -> fqn collapses to parent name.
    c["fqn_child_no_t"] = _build_pdf(
        "/T (parent)\n/FT /Tx\n/Kids [6 0 R]",
        extra_objs=["<<\n/Parent 5 0 R\n/T (realkid)\n>>"],
    )
    # three-level nesting: gp(/T) -> p(/T) -> kid(/T).
    c["fqn_three_level"] = _build_pdf(
        "/T (gp)\n/FT /Tx\n/Kids [6 0 R]",
        extra_objs=[
            "<<\n/Parent 5 0 R\n/T (p)\n/Kids [7 0 R]\n>>",
            "<<\n/Parent 6 0 R\n/T (k)\n/V (deep)\n>>",
        ],
    )
    # top-level field with empty /T string.
    c["fqn_empty_t"] = _build_pdf("/FT /Tx\n/T ()\n/V (v)")
    # top-level field with NO /T at all but resolvable /FT (terminal text).
    c["fqn_no_t_tx"] = _build_pdf("/FT /Tx\n/V (v)")

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


def _b(v: bool) -> str:
    return "1" if v else "0"


def _list(xs: list[object]) -> str:
    return _esc("[" + ", ".join(str(x) for x in xs) + "]")


def _field_type(f: object) -> str:
    try:
        t = f.get_field_type()
        return "?" if t is None else t
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _fqn(f: object) -> str:
    try:
        n = f.get_fully_qualified_name()
        if n is None:
            return "null"
        return "<empty>" if n == "" else _esc(n)
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _preds(f: object) -> str:
    try:
        if isinstance(f, PDTextField):
            return (
                f"multiline:{_b(f.is_multiline())}"
                f",password:{_b(f.is_password())}"
                f",comb:{_b(f.is_comb())}"
                f",fileSelect:{_b(f.is_file_select())}"
                f",doNotScroll:{_b(f.do_not_scroll())}"
                f",doNotSpellCheck:{_b(f.do_not_spell_check())}"
                f",richText:{_b(f.is_rich_text())}"
            )
        if isinstance(f, PDRadioButton):
            return (
                f"push:{_b(f.is_push_button())}"
                f",radio:{_b(f.is_radio_button())}"
                f",unison:{_b(f.is_radios_in_unison())}"
            )
        if isinstance(f, PDPushButton):
            return f"push:{_b(f.is_push_button())},radio:{_b(f.is_radio_button())}"
        if isinstance(f, PDCheckBox):
            return f"push:{_b(f.is_push_button())},radio:{_b(f.is_radio_button())}"
        if isinstance(f, PDComboBox):
            return (
                f"combo:{_b(f.is_combo())}"
                f",edit:{_b(f.is_edit())}"
                f",multiSelect:{_b(f.is_multi_select())}"
                f",sort:{_b(f.is_sort())}"
                f",doNotSpellCheck:{_b(f.is_do_not_spell_check())}"
                f",commit:{_b(f.is_commit_on_sel_change())}"
            )
        if isinstance(f, PDListBox):
            return (
                f"combo:{_b(f.is_combo())}"
                f",multiSelect:{_b(f.is_multi_select())}"
                f",sort:{_b(f.is_sort())}"
                f",doNotSpellCheck:{_b(f.is_do_not_spell_check())}"
                f",commit:{_b(f.is_commit_on_sel_change())}"
            )
        return "-"
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _typed_value(f: object) -> str:
    try:
        if isinstance(f, PDChoice):
            return _list(f.get_value())
        if isinstance(f, (PDTextField, PDButton)):
            return _esc(f.get_value())
        return "-"
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _value_as_string(f: object) -> str:
    try:
        return _esc(f.get_value_as_string())
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _typed_default(f: object) -> str:
    try:
        if isinstance(f, PDChoice):
            return _list(f.get_default_value())
        if isinstance(f, (PDTextField, PDButton)):
            return _esc(f.get_default_value())
        return "-"
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _py_case(name: str, data: bytes) -> list[str]:
    try:
        doc = PDDocument.load(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001 - contract probe
        return [f"CASE {name} form=ERR:{type(e).__name__} nfields=?", f"ENDCASE {name}"]
    try:
        cat = doc.get_document_catalog()
        try:
            form = cat.get_acro_form(None)
        except Exception as e:  # noqa: BLE001 - contract probe
            return [f"CASE {name} form={_err(e)} nfields=?", f"ENDCASE {name}"]
        if form is None:
            return [f"CASE {name} form=absent nfields=0", f"ENDCASE {name}"]
        try:
            fields = list(form.get_field_tree())
            nfields = str(len(fields))
        except Exception as e:  # noqa: BLE001 - contract probe
            return [
                f"CASE {name} form=present nfields={_err(e)}",
                f"ENDCASE {name}",
            ]
        lines = [f"CASE {name} form=present nfields={nfields}"]
        for f in fields:
            ro = req = nox = "?"
            try:
                ro = _b(f.is_read_only())
                req = _b(f.is_required())
                nox = _b(f.is_no_export())
            except Exception as e:  # noqa: BLE001 - contract probe
                ro = _err(e)
            terminal = _b(isinstance(f, PDTerminalField))
            lines.append(
                f"FIELD {_fqn(f)} type={type(f).__name__} ft={_field_type(f)} "
                f"terminal={terminal} ro={ro} req={req} nox={nox} "
                f"preds={_preds(f)} val={_typed_value(f)} "
                f"vas={_value_as_string(f)} dv={_typed_default(f)}"
            )
        lines.append(f"ENDCASE {name}")
        return lines
    finally:
        doc.close()


def _group_java(raw: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur: str | None = None
    for line in raw.splitlines():
        if line.startswith("CASE "):
            cur = line.split()[1]
            out[cur] = [line]
        elif cur is not None:
            out[cur].append(line)
    return out


# Pinned, intentional divergences from the Java per-field projection. Each entry
# maps a case name to the pypdfbox FIELD line(s) (without the CASE/ENDCASE frame,
# which is asserted to match). Cross-checked against upstream behaviour; each is
# pypdfbox being strictly more robust or an unavoidable rendering difference.
_PINNED_DIVERGENCES: dict[str, list[str]] = {
    # Top-level dict with no /T but resolvable /FT /Tx. Upstream
    # PDFieldFactory.createField returns a real PDTextField (FT resolves) and its
    # getFullyQualifiedName() is the empty string -> rendered "<empty>" on BOTH
    # sides, so this is NOT actually a divergence and is handled by the plain
    # comparison. (Kept out of pins on purpose.)
}


# --------------------------------------------------------------------- the test


@requires_oracle
def test_field_value_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every case projects identically on pypdfbox and Apache PDFBox 3.0.7: same
    form presence + field count, and for each field the same
    fqn / type / ft / terminal / ro/req/nox / typed-predicate-matrix /
    typed-value / value-as-string / typed-default (any throwing accessor rendered
    ``ERR:<Exc>``). Divergences, if any, are pinned in ``_PINNED_DIVERGENCES``
    with a reason rather than silently tolerated."""
    corpus = _build_corpus()
    for name, data in corpus.items():
        (tmp_path / f"{name}.pdf").write_bytes(data)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("FieldValueFuzzProbe", str(tmp_path))
    java = _group_java(raw)
    assert len(java) == len(corpus), (
        f"probe emitted {len(java)} cases for {len(corpus)}:\n{raw}"
    )

    mismatches: list[str] = []
    for name in corpus:
        j_lines = java.get(name, ["<MISSING>"])
        p_lines = _py_case(name, corpus[name])

        if name in _PINNED_DIVERGENCES:
            expected = [
                f"CASE {name} form=present nfields={len(_PINNED_DIVERGENCES[name])}",
                *_PINNED_DIVERGENCES[name],
                f"ENDCASE {name}",
            ]
            if p_lines != expected:
                mismatches.append(
                    f"{name}: PINNED py expected:\n   "
                    + "\n   ".join(expected)
                    + "\n  got:\n   "
                    + "\n   ".join(p_lines)
                )
            continue

        if j_lines != p_lines:
            mismatches.append(
                f"{name}:\n  JAVA:\n   "
                + "\n   ".join(j_lines)
                + "\n  PY:\n   "
                + "\n   ".join(p_lines)
            )

    assert not mismatches, "field-value divergence(s):\n" + "\n\n".join(mismatches)
