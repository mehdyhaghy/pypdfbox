"""Wave 1403 branch round-out for ``ASCII85OutputStream.flush``.

Closes the two defensive sentinel-stripping arcs:

* 90->92 — encoded body does *not* start with ``<~`` (the leading-sentinel
  strip is skipped).
* 92->97 — encoded body does *not* end with ``~>`` (the trailing-sentinel
  strip is skipped).

``base64.a85encode(..., adobe=True)`` *always* wraps its output with
``<~ ... ~>``, so neither False arm is reachable with real codec output.
We monkeypatch the module-local ``base64.a85encode`` to return
non-conforming bytes — exercising the real guard branches without touching
production behaviour.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.filter import ascii85_output_stream as mod
from pypdfbox.filter.ascii85_output_stream import ASCII85OutputStream


def test_flush_when_encoded_has_no_leading_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes 90->92: a fake encoder returns a body without the ``<~``
    prefix, so the leading-sentinel strip is skipped (the body still ends
    with ``~>`` so line 92's strip runs)."""
    fake = type(mod.base64)("base64")
    fake.a85encode = lambda data, adobe=True: b"5l~>"  # no leading <~
    monkeypatch.setattr(mod, "base64", fake)

    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    stream.write(b"A")
    stream.flush()
    # Body without <~ prefix; trailing ~> stripped, terminator appended.
    assert sink.getvalue().startswith(b"5l")


def test_flush_when_encoded_has_no_trailing_sentinel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes 92->97: a fake encoder returns a body with the ``<~`` prefix
    (stripped at line 91) but without the ``~>`` suffix, so line 92's
    trailing strip is skipped and control jumps to the line-folding block."""
    fake = type(mod.base64)("base64")
    fake.a85encode = lambda data, adobe=True: b"<~5l"  # leading <~, no ~>
    monkeypatch.setattr(mod, "base64", fake)

    sink = io.BytesIO()
    stream = ASCII85OutputStream(sink)
    stream.write(b"A")
    stream.flush()
    # <~ stripped, no ~> to strip; body retained verbatim before terminator.
    assert sink.getvalue().startswith(b"5l")
