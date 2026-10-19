# Versioning

pypdfbox follows [Semantic Versioning 2.0.0](https://semver.org/).
Version numbers have the form `MAJOR.MINOR.PATCH`.

## What each part means

- **MAJOR** goes up for changes that can break existing code:
  - a public class, method or argument is removed or renamed;
  - a method's signature or return type changes incompatibly;
  - the minimum supported Python version goes up.
- **MINOR** goes up for backward-compatible additions:
  - new features and new public methods;
  - fixes forward-ported from the upstream Apache PDFBox branch;
  - bug fixes that change output, when the old output was wrong. These are
    described in the release notes and in
    [`CHANGES.md`](../CHANGES.md).
- **PATCH** goes up for bug fixes only, with no new features.

Raising the locked versions of dependencies does not change the version.
Raising a minimum dependency version is a MINOR change, unless it drops
support for a Python version, which is MAJOR.

## Pinning

To get fixes and new features without breaking changes, pin the major
version:

```text
pypdfbox>=2.3,<3
```

## Relation to Apache PDFBox versions

pypdfbox version numbers do not track Apache PDFBox version numbers. Each
pypdfbox major version is based on one upstream line:

| pypdfbox | Based on Apache PDFBox |
|---|---|
| 1.x | 3.0.7, plus the fixes that shipped in 3.0.8 |
| 2.x | 3.0.8, plus settled fixes from the unreleased 3.0.9 |

Features taken from the upstream 4.0 development line that break the API
land only in a new pypdfbox major version.

## Pre-releases

Release candidates are tested on TestPyPI and are not published to PyPI.
PyPI normalizes pre-release versions to forms such as `1.0.0rc5`, which are
not valid Semantic Versioning (`1.0.0-rc5`).
