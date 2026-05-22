# Changelog index

pypdfbox keeps three changelog-shaped files at the repository
root, each with a distinct job. Use this page as the dispatcher.

- **[`CHANGES.md`](../CHANGES.md)** — *active behavioural
  divergences* from upstream Apache PDFBox, plus the per-wave
  delta log. Read this when you want to know how the Python
  port deliberately deviates from the Java reference, or what
  landed in the latest wave.
- **[`HISTORY.md`](../HISTORY.md)** — *chronological wave-by-wave
  history*. Append-only; the canonical log of what changed
  when. Use this when you need to trace a specific feature back
  to the wave it landed in.
- **[`RELEASE_NOTES_v0.9.0rc1.md`](../RELEASE_NOTES_v0.9.0rc1.md)**
  — *release-specific notes* for the 0.9.0rc1 cut. Status, major
  features, active divergences, migration pointer, known open
  items.

For *open follow-up items* (fixable, not yet done) see
[`DEFERRED.md`](../DEFERRED.md). For *contribution rules* see
[`CONTRIBUTING.md`](../CONTRIBUTING.md). For *per-file porting
attribution* see [`PROVENANCE.md`](../PROVENANCE.md).

Routine mechanical translations (`camelCase → snake_case` and
class-by-class porting without behavioural deviation) are not
recorded in any of the changelog files — they show up in git
history and `PROVENANCE.md` only.
