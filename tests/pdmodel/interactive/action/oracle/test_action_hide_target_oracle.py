"""Live PDFBox differential parity for ``PDActionHide`` — the Hide action's
``/H`` default and the polymorphic ``/T`` target accessor.

``PDActionHide`` had no dedicated oracle probe (only the multi-subtype
``ActionProbe`` exercised the common ``/S`` dispatch). This pins the
behaviourally-load-bearing corners:

* ``getH()`` defaults to ``true`` on an empty action (PDF 32000-1 Table 200 —
  the spec default is "hide"), so a malformed/absent ``/H`` must NOT read as
  ``false``;
* ``getT()`` is passed through verbatim as the stored ``COSBase`` — a single
  ``COSString`` field name, an annotation dictionary, or a ``COSArray`` of
  either — without coercion;
* the constructor stamps ``/Type Action`` and ``/S Hide`` so the saved wire
  form is ``H,S,T,Type``.

Java side: ``oracle/probes/ActionHideTargetProbe.java``.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide
from tests.oracle.harness import requires_oracle, run_probe_text


@requires_oracle
def test_action_hide_target_matches_pdfbox() -> None:
    java = run_probe_text("ActionHideTargetProbe").splitlines()

    e = PDActionHide()
    lines: list[str] = [
        f"empty.subtype={e.get_sub_type()}",
        f"empty.h={str(e.get_h()).lower()}",
        f"empty.t={'NULL' if e.get_t() is None else type(e.get_t()).__name__}",
    ]

    a = PDActionHide()
    a.set_h(False)
    lines.append(f"setFalse.h={str(a.get_h()).lower()}")

    st = PDActionHide()
    st.set_t(COSString("field1"))
    lines += [
        f"setStringT.t.class={type(st.get_t()).__name__}",
        f"setStringT.t.value={st.get_t().get_string()}",
    ]

    at = PDActionHide()
    arr = COSArray()
    arr.add(COSString("f1"))
    arr.add(COSString("f2"))
    at.set_t(arr)
    lines += [
        f"setArrayT.t.class={type(at.get_t()).__name__}",
        f"setArrayT.t.size={at.get_t().size()}",
    ]

    w = PDActionHide()
    w.set_h(True)
    w.set_t(COSString("widget"))
    cos = w.get_cos_object()
    keys = sorted(k.get_name() for k in cos.key_set())
    lines.append("wire.keys=" + ",".join(keys))
    lines.append(
        "wire.subtype=" + cos.get_name_as_string(COSName.get_pdf_name("S"))
    )

    assert lines == java
