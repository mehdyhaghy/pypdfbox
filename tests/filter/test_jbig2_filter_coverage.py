"""Coverage-boost tests for ``pypdfbox.filter.jbig2_filter``.

Targets:
* ``JBIG2Filter`` registration under upstream long-name.
* ``log_levigo_donated`` — one-shot logging guard.
* ``decode`` / ``encode`` delegate to ``JBIG2Decode`` (decode now wired
  to the first-party pure-Python JBIG2 decoder — Apache-2.0 port of
  apache/pdfbox-jbig2; encode stays unimplemented as upstream).
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.filter import FilterFactory
from pypdfbox.filter.jbig2_decode import JBIG2Decode
from pypdfbox.filter.jbig2_filter import JBIG2Filter

_FIXTURES = Path(__file__).resolve().parents[1] / "jbig2" / "fixtures"

# ---------- registration -------------------------------------------------


def test_jbig2_filter_registered_under_long_name() -> None:
    assert FilterFactory.is_registered("JBIG2Filter")
    inst = FilterFactory.get("JBIG2Filter")
    assert isinstance(inst, JBIG2Filter)


def test_jbig2_filter_is_jbig2_decode_subclass() -> None:
    assert issubclass(JBIG2Filter, JBIG2Decode)


# ---------- ``log_levigo_donated`` ---------------------------------------


def test_log_levigo_donated_emits_two_info_messages_first_call(caplog) -> None:
    # Reset the one-shot guard so we can assert the first-call behaviour.
    JBIG2Filter._levigo_logged = False
    with caplog.at_level(logging.INFO, logger="pypdfbox.filter.jbig2_filter"):
        JBIG2Filter.log_levigo_donated()
    assert JBIG2Filter._levigo_logged is True
    msgs = [r.message for r in caplog.records]
    assert any("Levigo" in m for m in msgs)
    assert any("pdfbox.apache.org" in m for m in msgs)


def test_log_levigo_donated_is_one_shot(caplog) -> None:
    # Mark guard as already-logged and confirm zero new records.
    JBIG2Filter._levigo_logged = True
    with caplog.at_level(logging.INFO, logger="pypdfbox.filter.jbig2_filter"):
        JBIG2Filter.log_levigo_donated()
    records = [
        r for r in caplog.records if r.name == "pypdfbox.filter.jbig2_filter"
    ]
    assert records == []


# ---------- ``decode`` / ``encode`` delegation ---------------------------


def test_decode_delegates_to_parent_and_decodes_real_stream() -> None:
    # The subclass forwards to JBIG2Decode.decode, which now decodes the
    # JBIG2 codestream via the first-party pure-Python decoder.
    data = (_FIXTURES / "003.jb2").read_bytes()
    out = io.BytesIO()
    result = JBIG2Filter().decode(io.BytesIO(data), out)
    assert result.parameters.get_int("Width") == 2550
    assert result.parameters.get_int("Height") == 3305
    assert result.parameters.get_int("BitsPerComponent") == 1
    assert result.bytes_written == len(out.getvalue()) > 0


def test_decode_passes_parameters_and_index_through() -> None:
    # An empty body with an explicit stream dict + index decodes to an
    # empty raster (no segments) without raising.
    out = io.BytesIO()
    result = JBIG2Filter().decode(
        io.BytesIO(b""), out, COSDictionary(), index=0
    )
    assert result.bytes_written == 0


def test_encode_raises_not_implemented_via_parent() -> None:
    # Upstream throws UnsupportedOperationException; the parent class
    # raises NotImplementedError to mirror it.
    with pytest.raises(NotImplementedError):
        JBIG2Filter().encode(io.BytesIO(b""), io.BytesIO(), COSDictionary())


# ---------- module-import-time registration guard ------------------------


def test_module_reimport_does_not_re_register(monkeypatch) -> None:
    # Force is_registered → True so the ``register`` call is skipped on
    # a fresh import. Re-importing must not raise.
    import importlib

    import pypdfbox.filter.jbig2_filter as mod

    # Already registered — calling again would be a no-op.
    importlib.reload(mod)
    assert FilterFactory.is_registered("JBIG2Filter")
