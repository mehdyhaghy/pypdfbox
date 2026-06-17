# Build

This is the developer-side companion to [`install.md`](install.md).
If you just want to *use* pypdfbox, the install guide is enough. If
you intend to hack on the source, run the tests, or send a PR, read
this first.

## Clone and bootstrap

```sh
git clone https://github.com/mehdyhaghy/pypdfbox.git
cd pypdfbox
uv sync --all-groups
```

Install `uv` from <https://docs.astral.sh/uv/> if you don't have it.
`--all-groups` pulls in the `dev` PEP 735 dependency group: pytest,
pytest-cov, ruff, mypy.

After this:

- `.venv/` is the project virtualenv.
- `.venv/bin/python` is the right interpreter to use for ad-hoc
  scripts.
- `uv run <cmd>` runs `<cmd>` inside the project's environment
  without you having to activate the venv.

## Run the tests

Fast pass (no coverage):

```sh
.venv/bin/pytest -q --no-cov
```

This is the default during development. The full suite is currently
in the tens of thousands of tests and completes in around a minute
on a modern laptop. Run this before every substantive change.

Single module:

```sh
.venv/bin/pytest -q --no-cov tests/cos
.venv/bin/pytest -q --no-cov tests/pdmodel/font
```

Single test:

```sh
.venv/bin/pytest -q --no-cov tests/cos/test_cos_dictionary.py::test_set_item
```

With coverage (drop `--no-cov`):

```sh
.venv/bin/pytest -q
```

Coverage is collected via `pytest-cov` and written to
`coverage.json` (and `htmlcov/` if you ask for HTML). This run is
considerably slower than the fast pass — reserve it for when you
need fresh numbers.

## Run the linter

```sh
uv run ruff check --fix      # auto-fix what is auto-fixable
uv run ruff check            # confirm clean
```

Ruff config lives in `pyproject.toml`. The selected rule families
are `E`, `F`, `I`, `B`, `UP`, `SIM`; line length is 100; target is
`py314`. We ignore `UP012` deliberately — explicit `encoding="utf-8"`
on `open` / `encode` / `decode` calls stays even though Python's
default already matches.

The common cases that `--fix` does not auto-resolve:

- `E501` long lines — break them by hand.
- `F841` unused variables — delete or rename.
- `SIM105` `try/except/pass` — convert to `contextlib.suppress(...)`.
- `B008` mutable defaults — replace with a sentinel pattern.

Run ruff before every commit. The local pre-push hook (next
section) will block you otherwise, but catching it earlier is
faster.

## Run the type checker (optional)

```sh
uv run mypy pypdfbox
```

`mypy` is configured strict; on a clean tree it should be quiet. It
is not currently part of the pre-push gate (too slow), but PRs that
introduce new mypy errors are typically asked to fix them.

## The pre-push hook

There is no GitHub Actions CI gating pushes for ruff or license
policy — those gates run locally, on the developer machine, via
`.git/hooks/pre-push`. The hook is **not** versioned (it's in
`.git/`, which git itself does not track), so a fresh clone needs
to install it.

Drop this into `.git/hooks/pre-push` and `chmod +x` it:

```bash
#!/usr/bin/env bash
set -euo pipefail
[ -f pyproject.toml ] || exit 0
command -v uv >/dev/null 2>&1 || exit 0
uv run ruff check || { echo "pre-push: ruff failed; fix with 'uv run ruff check --fix'." >&2; exit 1; }
ALLOW_ONLY="Apache Software License;Apache License 2.0;MIT License;MIT;BSD License;3-Clause BSD License;BSD-3-Clause;BSD-2-Clause;Python Software Foundation License;Mozilla Public License 2.0 (MPL 2.0);ISC License;ISC License (ISCL);Historical Permission Notice and Disclaimer (HPND);Python (MIT style);MIT-CMU;Apache-2.0;Apache-2.0 OR BSD-2-Clause;Apache-2.0 OR BSD-3-Clause;PSF-2.0"
uv run --with pip-licenses pip-licenses --format=csv --allow-only "$ALLOW_ONLY" >/dev/null || { echo "pre-push: license check failed." >&2; exit 1; }
```

The hook does two things:

1. Runs `uv run ruff check` and refuses the push on lint failure.
2. Runs `pip-licenses` against the resolved dependency tree with an
   allow-list of permissive SPDX strings, and refuses the push if
   any dependency carries something else. If you add a new
   permissive dep whose PyPI License metadata uses an SPDX string
   that is not yet in the list, append it to `ALLOW_ONLY` —
   *after* you have read the dep's actual LICENSE file and
   confirmed it is genuinely permissive (do not add a string just
   because pip-licenses complained about it).

The full test suite does not run in the hook — it is too slow
(~70s) to gate every push. Run pytest manually before pushing
substantive changes.

## Coverage workflow

Coverage numbers live in `coverage.json` and are refreshed via:

```sh
.venv/bin/pytest -q
```

(without `--no-cov`). The lines you care about for parity reporting
are line coverage global, line coverage for the
parser-writer-pdmodel-contentstream-text-fontbox-rendering-xmpbox-tools
core.

Read `coverage.json` directly, or import it in your tool of
choice, to see the per-module breakdown.

## Provenance protocol

The per-change bookkeeping is:

- [`PROVENANCE.md`](../PROVENANCE.md) — one row per ported file.
  Format: pypdfbox path → upstream PDFBox version → upstream Java
  path. Required for both production source files and ported test
  files. Required for binary fixtures copied from
  `pdfbox/src/test/resources/`.
- [`CHANGES.md`](../CHANGES.md) — substantive behavioural
  deviations from upstream. Not for trivial naming
  (`camelCase` → `snake_case`); only for cases where pypdfbox
  observably behaves differently from PDFBox.
- The [issue tracker](https://github.com/mehdyhaghy/pypdfbox/issues)
  — open in-flight gaps that are fixable but not yet closed.

For the parity-test layering rule (hand-written tests +
ported-upstream tests, both required), see
[`contributing.md`](../CONTRIBUTING.md).

## Recompute upstream parity (optional)

If you want to see class / method parity numbers against a live
upstream clone:

```sh
git clone --branch 3.0 --depth 1 https://github.com/apache/pdfbox.git /tmp/pdfbox
uv run python scripts/parity.py /tmp/pdfbox
uv run python scripts/parity.py /tmp/pdfbox --missing
```

Numbers shipped in `CHANGES.md` come from this script.

## Next steps

- [Contributing](../CONTRIBUTING.md) — how to actually structure a PR.
- [Install guide](install.md) — re-read if you hit a native-dep
  build failure during `uv sync`.
- [API reference](api/index.md) — module map for navigation.
