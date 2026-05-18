"""Wave 1354 tail-sweep for ``SignaturePane.create_text_view`` error path.

Covers the ``except Exception`` branch (lines 184-185 in
``signature_pane.py``) that turns a ``get_text_string`` crash into the
``"<failed to dump signature: ...>"`` placeholder body instead of
propagating up to the widget hierarchy.
"""

from __future__ import annotations

import tkinter as tk

from pypdfbox.cos import COSString
from pypdfbox.debugger.signaturepane.signature_pane import SignaturePane


def test_create_text_view_falls_back_when_get_text_string_raises(
    tk_root: tk.Tk, monkeypatch
) -> None:
    def _boom(_cos: COSString) -> str:
        raise RuntimeError("synthetic-failure")

    monkeypatch.setattr(SignaturePane, "get_text_string", staticmethod(_boom))
    pane = SignaturePane(tk_root, COSString(b"any"))
    body = pane.asn1_text.get("1.0", "end-1c")
    assert body.startswith("<failed to dump signature:")
    assert "synthetic-failure" in body
