from __future__ import annotations

import tests.tools.test_pdfdebugger_wave383 as wave383


def test_wave949_unknown_cos_accept_and_full_context_read_are_callable() -> None:
    assert wave383._UnknownCOS().accept(object()) is None

    context = wave383._BytesContext(b"debugger-preview")

    assert context.read() == b"debugger-preview"
