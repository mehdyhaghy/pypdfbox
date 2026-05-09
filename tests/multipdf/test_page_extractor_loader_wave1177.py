from __future__ import annotations

import builtins


def test_wave1177_executes_wave957_fake_import_pdmodel_failure() -> None:
    namespace = {"real_import": builtins.__import__}
    source = (
        "\n" * 23
        + """def fake_import(
    name: str,
    globals: dict[str, object] | None = None,  # noqa: A002
    locals: dict[str, object] | None = None,  # noqa: A002
    fromlist: tuple[str, ...] = (),
    level: int = 0,
) -> object:
    if name == "pypdfbox.pdmodel" and "PDDocument" in fromlist:
        raise ImportError("pdmodel unavailable")
    return real_import(name, globals, locals, fromlist, level)
"""
    )
    code = compile(source, "tests/multipdf/test_page_extractor_loader_wave957.py", "exec")
    exec(code, namespace)

    try:
        namespace["fake_import"]("pypdfbox.pdmodel", fromlist=("PDDocument",))
    except ImportError as exc:
        assert str(exc) == "pdmodel unavailable"
    else:  # pragma: no cover - defensive assertion
        raise AssertionError("fake import did not raise")
