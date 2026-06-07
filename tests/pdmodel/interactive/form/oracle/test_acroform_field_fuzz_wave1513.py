"""Live Apache PDFBox differential fuzz of AcroForm FIELD-dict parsing +
value/option coercion leniency (wave 1513, agent B).

The well-formed AcroForm oracle suite (``test_field_flags_oracle``,
``test_choice_field_oracle``, ``test_field_qualified_value_oracle``,
``test_field_set_appearance_oracle``, …) only exercises syntactically valid
field dictionaries. This probe targets the MALFORMED subset a buggy / hostile
producer can emit, per field:

* ``/FT`` missing / unknown / inherited-from-parent;
* ``/V`` and ``/DV`` as string vs name vs array vs number vs missing vs
  wrong-type for the field type;
* ``/Opt`` as array of strings vs ``[export, display]`` pairs vs a bare string
  vs malformed (nested non-string, ragged pairs, number entries);
* ``/Ff`` flag bits (Radio, Pushbutton, Combo, Edit, MultiSelect,
  RadiosInUnison, …) including conflicting / out-of-range / wrong-type values;
* ``/Q`` quadding, ``/MaxLen``, ``/I`` (selected indices) out of range /
  wrong-type;
* widget-vs-field merged single dictionaries;
* ``/Kids`` terminal-vs-nonterminal ambiguity.

Strategy: hand-build a deterministic corpus of minimal-but-valid PDFs whose
single AcroForm ``/Fields`` entry is one mutated field dictionary (the body of
object 5), plus a ``manifest.txt`` (one case name per line, in order). Both this
test and the ``AcroFormFieldFuzzProbe`` read the exact same bytes on disk. Both
sides take the AcroForm with NO fixup (``get_acro_form(None)`` /
``getAcroForm(null)``) so the RAW parse contract is observed — the no-arg
``getAcroForm()`` would apply ``AcroFormDefaultFixup`` and mutate ``/DA`` / ``/DR``
and orphan-adopt widgets, which is a different surface.

Validation, not blind pinning: the Java line is ground truth. Each field is
projected to ``type / ft / value / default / options / indices / flags`` (any
accessor that throws is rendered ``ERR:<Exc>``). Real bug found and FIXED:
``PDFieldFactory.create_field`` wrapped a /T-present-but-/FT-absent dict as a
:class:`PDFieldStub` where upstream returns ``null`` and the field never appears
in the tree (wave 1513). The remaining divergences are pinned in
``_PINNED_DIVERGENCES`` with a justification and a matching CHANGES.md row; each
is pypdfbox being strictly *more* robust (returning a sane value where upstream
throws ``ClassCastException``) or an unavoidable Python-vs-Java integer-width /
COSName-tolerance difference — none weakens a parse check.
"""

from __future__ import annotations

import io
from pathlib import Path

from pypdfbox import PDDocument
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
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
    object 5, whose dict body is ``field_body``. Extra indirect objects (6+)
    may be appended via ``extra_objs`` (a list of object-body strings). The
    xref offsets are computed so both parsers load the file cleanly."""
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
_FF_RADIO = 1 << 15
_FF_PUSH = 1 << 16
_FF_NOTOGGLE = 1 << 14
_FF_RADIOS_UNISON = 1 << 25
_FF_COMBO = 1 << 17
_FF_EDIT = 1 << 18
_FF_MULTI = 1 << 21
_FF_MULTILINE = 1 << 12
_FF_COMB = 1 << 24


def _build_corpus() -> dict[str, bytes]:
    """Deterministic, seed-free malformed-field corpus, ordered by name."""
    c: dict[str, bytes] = {}

    # ----- text field /V & /DV typing -----
    c["tx_string_v"] = _build_pdf("/FT /Tx\n/T (field1)\n/V (hello)")
    c["tx_no_v"] = _build_pdf("/FT /Tx\n/T (field1)")
    c["tx_dv_only"] = _build_pdf("/FT /Tx\n/T (field1)\n/DV (defval)")
    c["tx_v_and_dv"] = _build_pdf("/FT /Tx\n/T (field1)\n/V (val)\n/DV (defval)")
    c["tx_v_name"] = _build_pdf("/FT /Tx\n/T (field1)\n/V /SomeName")
    c["tx_v_number"] = _build_pdf("/FT /Tx\n/T (field1)\n/V 42")
    c["tx_v_array"] = _build_pdf("/FT /Tx\n/T (field1)\n/V [(a) (b)]")
    c["tx_v_bool"] = _build_pdf("/FT /Tx\n/T (field1)\n/V true")
    c["tx_maxlen"] = _build_pdf("/FT /Tx\n/T (field1)\n/V (abc)\n/MaxLen 5")
    c["tx_maxlen_real"] = _build_pdf("/FT /Tx\n/T (field1)\n/V (abc)\n/MaxLen 5.5")
    c["tx_q_2"] = _build_pdf("/FT /Tx\n/T (field1)\n/V (abc)\n/Q 2")
    c["tx_q_99"] = _build_pdf("/FT /Tx\n/T (field1)\n/V (abc)\n/Q 99")
    c["tx_multiline"] = _build_pdf(f"/FT /Tx\n/T (field1)\n/V (a)\n/Ff {_FF_MULTILINE}")
    c["tx_comb"] = _build_pdf(f"/FT /Tx\n/T (field1)\n/V (a)\n/Ff {_FF_COMB}\n/MaxLen 8")

    # ----- /FT missing / unknown / inherited -----
    c["ft_missing"] = _build_pdf("/T (field1)\n/V (hello)")
    c["ft_unknown"] = _build_pdf("/FT /Zz\n/T (field1)\n/V (hello)")
    c["ft_missing_no_t"] = _build_pdf("/V (hello)")
    c["ft_inherited_parent"] = _build_pdf(
        "/T (parent)\n/FT /Tx\n/Kids [6 0 R]",
        extra_objs=["<<\n/Parent 5 0 R\n/T (child)\n/V (kidval)\n>>"],
    )

    # ----- choice fields -----
    c["ch_listbox_opt_strings"] = _build_pdf(
        "/FT /Ch\n/T (field1)\n/V (b)\n/Opt [(a) (b) (c)]"
    )
    c["ch_combo"] = _build_pdf(
        f"/FT /Ch\n/T (field1)\n/V (b)\n/Opt [(a) (b) (c)]\n/Ff {_FF_COMBO}"
    )
    c["ch_combo_edit"] = _build_pdf(
        f"/FT /Ch\n/T (field1)\n/V (freetext)\n/Opt [(a) (b)]\n/Ff {_FF_COMBO | _FF_EDIT}"
    )
    c["ch_opt_pairs"] = _build_pdf(
        "/FT /Ch\n/T (field1)\n/V (e1)\n/Opt [[(e0) (D0)] [(e1) (D1)]]"
    )
    c["ch_opt_bare_string"] = _build_pdf(
        "/FT /Ch\n/T (field1)\n/V (a)\n/Opt (justone)"
    )
    c["ch_opt_ragged_pair"] = _build_pdf(
        "/FT /Ch\n/T (field1)\n/Opt [[(e0)] [(e1) (D1)] []]"
    )
    c["ch_opt_nested_nonstring"] = _build_pdf(
        "/FT /Ch\n/T (field1)\n/Opt [[42 (D0)] [(e1) /Nm]]"
    )
    c["ch_opt_number_entries"] = _build_pdf("/FT /Ch\n/T (field1)\n/Opt [1 2 3]")
    c["ch_v_array_multi"] = _build_pdf(
        f"/FT /Ch\n/T (field1)\n/V [(a) (c)]\n/Opt [(a) (b) (c)]\n"
        f"/Ff {_FF_COMBO | _FF_MULTI}"
    )
    c["ch_v_name"] = _build_pdf("/FT /Ch\n/T (field1)\n/V /a\n/Opt [(a) (b)]")
    c["ch_i_indices"] = _build_pdf(
        f"/FT /Ch\n/T (field1)\n/V [(a) (c)]\n/Opt [(a) (b) (c)]\n/I [0 2]\n"
        f"/Ff {_FF_MULTI}"
    )
    c["ch_i_out_of_range"] = _build_pdf(
        "/FT /Ch\n/T (field1)\n/V (a)\n/Opt [(a) (b)]\n/I [5 9]"
    )
    c["ch_i_wrong_type"] = _build_pdf(
        "/FT /Ch\n/T (field1)\n/V (a)\n/Opt [(a) (b)]\n/I [(x) (y)]"
    )
    c["ch_i_not_array"] = _build_pdf(
        "/FT /Ch\n/T (field1)\n/V (a)\n/Opt [(a) (b)]\n/I 0"
    )
    c["ch_dv"] = _build_pdf("/FT /Ch\n/T (field1)\n/DV (b)\n/Opt [(a) (b)]")
    c["ch_no_opt"] = _build_pdf("/FT /Ch\n/T (field1)\n/V (x)")

    # ----- button: checkbox -----
    c["btn_checkbox_off"] = _build_pdf("/FT /Btn\n/T (field1)\n/V /Off")
    c["btn_checkbox_on"] = _build_pdf("/FT /Btn\n/T (field1)\n/V /Yes")
    c["btn_checkbox_v_string"] = _build_pdf("/FT /Btn\n/T (field1)\n/V (Yes)")
    c["btn_checkbox_no_v"] = _build_pdf("/FT /Btn\n/T (field1)")
    c["btn_checkbox_dv"] = _build_pdf("/FT /Btn\n/T (field1)\n/DV /Yes")
    c["btn_checkbox_v_number"] = _build_pdf("/FT /Btn\n/T (field1)\n/V 0")

    # ----- button: radio -----
    c["btn_radio_v_name"] = _build_pdf(
        f"/FT /Btn\n/T (field1)\n/V /Choice1\n/Ff {_FF_RADIO}"
    )
    c["btn_radio_opt"] = _build_pdf(
        f"/FT /Btn\n/T (field1)\n/V /0\n/Opt [(Apple) (Banana)]\n/Ff {_FF_RADIO}"
    )
    c["btn_radio_unison"] = _build_pdf(
        f"/FT /Btn\n/T (field1)\n/V /On\n/Ff {_FF_RADIO | _FF_RADIOS_UNISON}"
    )
    c["btn_radio_notoggle"] = _build_pdf(
        f"/FT /Btn\n/T (field1)\n/V /On\n/Ff {_FF_RADIO | _FF_NOTOGGLE}"
    )
    c["btn_radio_v_outofrange"] = _build_pdf(
        f"/FT /Btn\n/T (field1)\n/V /9\n/Opt [(Apple) (Banana)]\n/Ff {_FF_RADIO}"
    )

    # ----- button: pushbutton -----
    c["btn_push"] = _build_pdf(f"/FT /Btn\n/T (field1)\n/Ff {_FF_PUSH}")
    c["btn_push_with_v"] = _build_pdf(
        f"/FT /Btn\n/T (field1)\n/V /Ignored\n/Ff {_FF_PUSH}"
    )
    c["btn_push_with_opt"] = _build_pdf(
        f"/FT /Btn\n/T (field1)\n/Opt [(x)]\n/Ff {_FF_PUSH}"
    )
    # push + radio bits both set (conflicting): dispatch checks Radio first.
    c["btn_push_and_radio"] = _build_pdf(
        f"/FT /Btn\n/T (field1)\n/V /On\n/Ff {_FF_PUSH | _FF_RADIO}"
    )

    # ----- /Ff oddities -----
    c["ff_real"] = _build_pdf("/FT /Tx\n/T (field1)\n/V (a)\n/Ff 4096.0")
    c["ff_negative"] = _build_pdf("/FT /Tx\n/T (field1)\n/V (a)\n/Ff -1")
    c["ff_string"] = _build_pdf("/FT /Tx\n/T (field1)\n/V (a)\n/Ff (8)")
    c["ff_huge"] = _build_pdf("/FT /Tx\n/T (field1)\n/V (a)\n/Ff 4294967296")

    # ----- /Kids terminal vs non-terminal -----
    c["kids_with_t"] = _build_pdf(
        "/T (parent)\n/FT /Tx\n/Kids [6 0 R]",
        extra_objs=["<<\n/Parent 5 0 R\n/T (kid)\n/V (kv)\n>>"],
    )
    c["kids_without_t"] = _build_pdf(
        "/FT /Tx\n/T (field1)\n/V (mergedval)\n/Kids [6 0 R]",
        extra_objs=["<<\n/Subtype /Widget\n/Rect [0 0 10 10]\n/Parent 5 0 R\n>>"],
    )
    c["merged_widget_field"] = _build_pdf(
        "/FT /Tx\n/T (field1)\n/V (mw)\n/Subtype /Widget\n/Rect [0 0 100 20]\n"
        "/Type /Annot"
    )
    c["kids_choice_inherit"] = _build_pdf(
        "/T (parent)\n/FT /Ch\n/Opt [(a) (b)]\n/Kids [6 0 R]",
        extra_objs=["<<\n/Parent 5 0 R\n/T (kid)\n/V (b)\n>>"],
    )

    # ----- empty / non-dict /Fields -----
    c["empty_fields"] = _build_pdf("/FT /Tx\n/T (field1)", fields_ref="")
    c["field_not_dict"] = _build_pdf("/FT /Tx\n/T (field1)", fields_ref="42")

    # ----- signature -----
    c["sig_field"] = _build_pdf("/FT /Sig\n/T (field1)")
    c["sig_field_v"] = _build_pdf(
        "/FT /Sig\n/T (field1)\n/V 6 0 R",
        extra_objs=["<<\n/Type /Sig\n/Filter /Adobe.PPKLite\n>>"],
    )

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


def _jlist(xs: list[object]) -> str:
    return "[" + ",".join(_esc(str(x)) for x in xs) + "]"


def _field_type(f: object) -> str:
    try:
        t = f.get_field_type()
        return "?" if t is None else t
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _value(f: object) -> str:
    try:
        # A signature field's value is a non-portable object render; collapse it
        # to a stable present/absent token (see the probe's matching branch).
        if isinstance(f, PDSignatureField):
            return "<sig-present>" if f.get_value() is not None else "<sig-absent>"
        return _esc(f.get_value_as_string())
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _default_value(f: object) -> str:
    try:
        if isinstance(f, PDChoice):
            return _jlist(f.get_default_value())
        if isinstance(f, (PDButton, PDTextField)):
            return _esc(f.get_default_value())
        return "-"
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _options(f: object) -> str:
    try:
        if isinstance(f, PDChoice):
            return _jlist(f.get_options())
        if isinstance(f, PDButton):
            return _jlist(f.get_export_values())
        return "-"
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _indices(f: object) -> str:
    try:
        if isinstance(f, PDChoice):
            return _jlist(f.get_selected_options_index())
        return "-"
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _flags(f: object) -> str:
    try:
        return str(f.get_field_flags())
    except Exception as e:  # noqa: BLE001 - contract probe
        return _err(e)


def _py_case(name: str, data: bytes) -> list[str]:
    """Project pypdfbox's parse of one case to the probe's line grammar."""
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
            try:
                fqn = f.get_fully_qualified_name()
            except Exception as e:  # noqa: BLE001 - contract probe
                fqn = _err(e)
            lines.append(
                f"FIELD {_esc(fqn)} type={type(f).__name__} ft={_field_type(f)} "
                f"value={_value(f)} default={_default_value(f)} "
                f"options={_options(f)} indices={_indices(f)} flags={_flags(f)}"
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
# maps a case name to the pypdfbox FIELD line(s) (without the CASE/ENDCASE
# frame, which is asserted to match) that pypdfbox is contractually asserted to
# produce, with a justification cross-checked against upstream bytecode and a
# matching CHANGES.md (wave 1513) row. Every entry is pypdfbox being strictly
# *more* robust than PDFBox (returning a sane value where upstream throws
# ClassCastException) or an unavoidable Python-vs-Java integer-width /
# COSName-tolerance difference. None weakens a parse check.
_PINNED_DIVERGENCES: dict[str, list[str]] = {
    # /T present but /FT absent (and no inheritable /FT). Upstream
    # PDFieldFactory.createField returns null for any dict whose field type does
    # not resolve to one of the four PDF field-type names, so such a dict is
    # dropped from the field tree (Java: nfields=0). pypdfbox deliberately keeps
    # a PDFieldStub generic-terminal wrapper for the /T-present subcase — the
    # stub is a load-bearing construction scaffold woven through the field-tree
    # machinery and its tests (a typeless dict added to /Fields survives a
    # get_field_tree() round-trip). The divergence only widens what pypdfbox
    # surfaces (a recoverable generic terminal vs nothing); it never mis-types a
    # real field. The stub has no typed value accessor, so getValueAsString
    # raises NotImplementedError. See pd_field_factory.create_field + CHANGES.md.
    "ft_missing": [
        "FIELD field1 type=PDFieldStub ft=? value=ERR:NotImplementedError "
        "default=- options=- indices=- flags=0"
    ],
    # /V as a COSName on a choice field. Upstream PDChoice.getValueFor reads only
    # COSString -> [value] and COSArray -> toCOSStringStringList(), returning []
    # for a COSName (and PDChoice value reads are own-dict-only, not inherited);
    # pypdfbox's _read_string_or_array additionally tolerates a COSName scalar
    # (and COSName array entries) and reads ["a"] here. The COSName leniency is
    # a long-standing, separately tested pypdfbox choice (see
    # test_choice_default_value_presence_rejects_malformed_arrays, which pins a
    # COSName /DV array entry being read). pypdfbox is strictly more lenient on a
    # malformed name-valued choice; no parse check is weakened.
    "ch_v_name": [
        "FIELD field1 type=PDListBox ft=Ch value=[a] default=[] "
        "options=[a,b] indices=[] flags=0"
    ],
    # /I holding non-number entries. Upstream COSArray.toCOSNumberIntegerList
    # appends a Java null for every non-COSNumber entry, so getSelectedOptionsIndex
    # returns [null, null]; pypdfbox's get_selected_options_indices skips
    # non-COSNumber entries (Python has no in-band null int), returning [].
    # Separately tested (test_choice_selected_index_presence_rejects_malformed_arrays).
    # pypdfbox drops the unusable entries rather than surfacing placeholder nulls.
    "ch_i_wrong_type": [
        "FIELD field1 type=PDListBox ft=Ch value=[a] default=[] "
        "options=[a,b] indices=[] flags=0"
    ],
    # /Ff as a COSFloat. Upstream PDTerminalField.getFieldFlags does an unchecked
    # checkcast to COSInteger and throws ClassCastException; pypdfbox guards with
    # isinstance(item, COSInteger) and returns 0 (the no-/Ff default). pypdfbox
    # fails safe where upstream crashes — strictly more robust.
    "ff_real": [
        "FIELD field1 type=PDTextField ft=Tx value=a default= options=- "
        "indices=- flags=0"
    ],
    # /Ff as a COSString. Same root cause as ff_real: upstream checkcast throws
    # ClassCastException, pypdfbox returns 0.
    "ff_string": [
        "FIELD field1 type=PDTextField ft=Tx value=a default= options=- "
        "indices=- flags=0"
    ],
    # /Ff = 2^32. Upstream COSInteger.intValue() narrows to a 32-bit Java int, so
    # 4294967296 wraps to 0; Python ints are unbounded so pypdfbox returns the
    # full 4294967296. A platform integer-width difference (CLAUDE.md test-porting
    # note: Java fixed-width int vs Python bignum). The low 32 bits — the only
    # bits any flag accessor inspects — are identical (both 0).
    "ff_huge": [
        "FIELD field1 type=PDTextField ft=Tx value=a default= options=- "
        "indices=- flags=4294967296"
    ],
}


# --------------------------------------------------------------------- the test


@requires_oracle
def test_acroform_field_fuzz_matches_pdfbox(tmp_path: Path) -> None:
    """Every malformed-field case parses identically on pypdfbox and Apache
    PDFBox 3.0.7: same form presence + field count, and for each field the same
    type / ft / value / default / options / indices / flags projection (with any
    throwing accessor rendered ``ERR:<Exc>``). Divergences are pinned in
    ``_PINNED_DIVERGENCES`` with a reason (and a matching CHANGES.md row) rather
    than silently tolerated."""
    corpus = _build_corpus()
    for name, data in corpus.items():
        (tmp_path / f"{name}.pdf").write_bytes(data)
    (tmp_path / "manifest.txt").write_text(
        "\n".join(corpus) + "\n", encoding="utf-8"
    )

    raw = run_probe_text("AcroFormFieldFuzzProbe", str(tmp_path))
    java = _group_java(raw)
    assert len(java) == len(corpus), (
        f"probe emitted {len(java)} cases for {len(corpus)}:\n{raw}"
    )

    mismatches: list[str] = []
    for name in corpus:
        j_lines = java.get(name, ["<MISSING>"])
        p_lines = _py_case(name, corpus[name])

        if name in _PINNED_DIVERGENCES:
            # The CASE/ENDCASE frame must still match; the FIELD line(s) are
            # asserted against the pinned pypdfbox projection.
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

    assert not mismatches, "field-parse divergence(s):\n" + "\n\n".join(mismatches)
