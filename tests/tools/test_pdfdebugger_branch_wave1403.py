"""Wave 1403 branch round-out for ``pdfdebugger``.

Closes the False-branch arrows in
``pypdfbox/tools/pdfdebugger.py``:

* 938->941 — ``_format_token`` receives a ``COSBase`` that is neither a
  scalar (``_fmt_simple`` returns None), nor a ``COSArray``, nor a
  ``COSDictionary``, so it falls through to ``return repr(tok)``.
* 1301->1307 — the walker ``cat`` command is given NO depth argument, so
  the ``if args`` arm is False and the default depth is used.
* 1365->1367 — the walker ``cd ..`` command is run at the trailer root
  (``len(stack) == 1``), so the ``if len(stack) > 1`` arm is False and
  the stack is left unchanged.
"""

from __future__ import annotations

import builtins

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSDocument,
    COSInteger,
    COSName,
    COSObjectKey,
    COSStream,
    COSString,
)
from pypdfbox.tools import pdfdebugger


class _FakeDoc:
    def __init__(self, cos_doc: COSDocument) -> None:
        self._cos_doc = cos_doc

    def get_document(self) -> COSDocument:
        return self._cos_doc


def _build_walker_doc() -> tuple[COSDocument, COSStream]:
    cos_doc = COSDocument()
    trailer = COSDictionary()
    catalog = COSDictionary()
    catalog.set_item("Type", COSName.get_pdf_name("Catalog"))
    catalog.set_item("Kids", COSArray([COSInteger.get(1), COSString("two")]))

    stream = COSStream()
    stream.set_data(b"stream data")
    catalog.set_item("Stream", stream)

    key = COSObjectKey(7, 0)
    ref = cos_doc.get_object_from_pool(key)
    ref.set_object(catalog)
    trailer.set_item(COSName.ROOT, ref)
    cos_doc.set_trailer(trailer)
    return cos_doc, stream


# ----------------------------------------------------------------------
# 938->941 — _format_token fall-through to repr(tok)
# ----------------------------------------------------------------------


def test_format_token_falls_back_to_repr_for_other_cos_base() -> None:
    """Closes 938->941: a ``COSDocument`` is a ``COSBase`` but is not a
    scalar / array / dictionary, so ``_format_token`` returns ``repr``."""
    other = COSDocument()
    try:
        result = pdfdebugger._format_token(other)
        # The repr fall-through path: matches the object's repr string.
        assert result == repr(other)
        assert "COSDocument" in result
    finally:
        other.close()


# ----------------------------------------------------------------------
# 1301->1307 — walker `cat` with no depth argument
# ----------------------------------------------------------------------


def test_walker_cat_without_args_uses_default_depth(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Closes 1301->1307: a bare ``cat`` (no depth arg) skips the
    int-parse block and prints the current node at the default depth."""
    cos_doc, stream = _build_walker_doc()
    commands = iter(["cat", "q"])
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(commands))
    try:
        assert pdfdebugger._interactive_walker(_FakeDoc(cos_doc)) == 0  # type: ignore[arg-type]
    finally:
        stream.close()
        cos_doc.close()

    out = capsys.readouterr().out
    # The trailer node was printed (no "depth must be an integer" error).
    assert "cat: depth must be an integer" not in out
    assert "/Root" in out


# ----------------------------------------------------------------------
# 1365->1367 — walker `cd ..` at the trailer root (stack length 1)
# ----------------------------------------------------------------------


def test_walker_cd_up_at_root_is_noop(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Closes 1365->1367: ``cd ..`` while at the trailer root leaves the
    breadcrumb stack untouched (the pop is skipped) and re-prints the
    root location."""
    cos_doc, stream = _build_walker_doc()
    commands = iter(["cd ..", "pwd", "q"])
    monkeypatch.setattr(builtins, "input", lambda _prompt: next(commands))
    try:
        assert pdfdebugger._interactive_walker(_FakeDoc(cos_doc)) == 0  # type: ignore[arg-type]
    finally:
        stream.close()
        cos_doc.close()

    out = capsys.readouterr().out
    # Still at the trailer root after cd .. -> pwd prints "trailer".
    assert "trailer" in out
