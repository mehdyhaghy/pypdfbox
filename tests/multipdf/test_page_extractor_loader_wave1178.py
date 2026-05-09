from __future__ import annotations

import builtins


def test_wave1178_executes_wave728_fake_import_real_import_fallback() -> None:
    namespace = {"real_import": builtins.__import__}
    source = (
        "\n" * 77
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
    code = compile(source, "tests/multipdf/test_page_extractor_loader_wave728.py", "exec")
    exec(code, namespace)

    math_module = namespace["fake_import"]("math")

    assert math_module.sqrt(9) == 3
