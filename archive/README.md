# archive/ — migration & parity-verification apparatus

This folder holds the **migration tooling and history** for the PDFBox → pypdfbox
port. None of it ships in the published package or is needed to *use* pypdfbox.
It is kept in-repo (not deleted) so the parity work stays auditable and the
differential oracle can be re-run in the future.

The restructure that created this folder happened after the port reached
behavioral parity (all differential oracle checks green, the actionable
parity-gap backlog cleared). See `migration-docs/HISTORY.md` for the full log.

## Layout

| Path | What it is |
|------|------------|
| `oracle/` | The **live differential oracle**: small Java "probe" programs (`oracle/probes/*.java`) compiled and run against Apache PDFBox 3.0.7, plus the build dir and the downloaded jar (jar + build are gitignored; fetch with `oracle/download_jars.sh`). |
| `tests/**/oracle/` | The ~790 **oracle test files** (≈10,300 differential cases) that diff pypdfbox output byte-for-byte against live Java PDFBox, organized by module. |
| `migration-docs/` | `HISTORY.md` (chronological wave-by-wave log), `DEFERRED.md` (open/closed follow-ups), `HANDOFF.md`, the original PRD (`pypdfbox_full_prd_v_1.md`), and the v0.9.0rc1 release notes. |
| `corpus/`, `target/` | Test corpus + upstream-artifact scratch dirs used by the parity tooling. |
| `scratch/` | Stray hand-run output PDFs/PNGs from development. |

## What stayed at the repo root (and why)

- `pypdfbox/` — the library.
- `tests/` (everything **except** `tests/**/oracle/`) — the hand-written test
  suite that runs in normal CI. **`tests/oracle/harness.py` deliberately
  stayed** at the root: dozens of hand-written parity tests embed a live
  differential check that imports it. The harness now points at
  `archive/oracle/` for its probes/jars (see the `_ORACLE` path in
  `tests/oracle/harness.py`).
- `LICENSE`, `NOTICE`, `PROVENANCE.md` — the Apache 2.0 legal trio (§4). These
  **must** stay at the root and ship in the package; `PROVENANCE.md` is the
  centralized "you changed these files" notice required by §4(b) for the
  ported source.
- `CHANGES.md` — user-facing behavioral deviations vs upstream PDFBox.

## Running the archived oracle suite

The oracle is a **developer-machine opt-in** (needs a JDK + the PDFBox jar); it
is not a CI gate. From the repo root:

```bash
# one-time: fetch the PDFBox 3.0.7 jar into archive/oracle/jars/
bash archive/oracle/download_jars.sh

# run any archived oracle tests (they import the kept tests/oracle/harness.py)
.venv/bin/pytest archive/tests/cos/oracle/            # one module
.venv/bin/pytest archive/tests -q                     # the whole oracle suite
```

Each test skips cleanly when the jar/JDK is unavailable.

## Restoring (un-archiving)

The move was a plain `git mv`, so it is fully reversible. To put a module's
oracle tests back under `tests/`:

```bash
git mv archive/tests/<module>/oracle tests/<module>/oracle
```

(and, if you move the whole `oracle/` apparatus back to the repo root, the
harness's `_ORACLE` path already falls back to a root `oracle/` automatically.)
