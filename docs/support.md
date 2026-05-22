# Support

pypdfbox is a community port of
[Apache PDFBox](https://pdfbox.apache.org/), not an Apache Software
Foundation release. That means the Apache project's support channels
(Jira tracker, users mailing list, dev mailing list) are not the
right place for pypdfbox-specific issues. Use the venues below.

## pypdfbox-specific issues

Bug reports and feature requests against pypdfbox go to the GitHub
issue tracker:

<https://github.com/mehdyhaghy/pypdfbox/issues>

Before filing, a quick check that often saves time:

- Confirm you are on the latest release
  (`pip install --upgrade pypdfbox`). Many issues are already
  fixed on `main` but not yet released.
- Search existing issues — closed ones too, with a "known
  divergences" label often covering the common Java vs Python
  behaviour differences.
- Read
  [`CHANGES.md` → Active divergences](../CHANGES.md#active-divergences-vs-upstream).
  The handful of intentional behavioural divergences from upstream
  PDFBox live there; they are not bugs.
- Read [`DEFERRED.md`](../DEFERRED.md). Open gaps that are
  fixable-but-not-yet-done are tracked there with one-line summaries
  and the wave that flagged them.

A good bug report includes:

- pypdfbox version (`pip show pypdfbox`).
- Python version + platform (`python -V`, `uname -a` or
  `systeminfo` on Windows).
- A minimal PDF that reproduces it (small ones can be attached
  directly to the issue; for larger ones, link to a gist /
  download URL).
- The full traceback, not a paraphrase.
- The output you got and the output you expected.

If your reproduction depends on confidential content, please reach
out via the contact on the GitHub profile rather than uploading the
file publicly.

## General PDF / PDFBox design questions

For questions like "how does PDF's XObject form work", "what is the
right way to model an AcroForm checkbox", or "why does upstream
PDFBox structure parsing this way" — those are upstream design
questions, and the upstream community is where the deep expertise
lives:

- [Apache PDFBox project home](https://pdfbox.apache.org/).
- [PDFBox users mailing list](https://pdfbox.apache.org/mailinglists.html).
- [Stack Overflow `pdfbox` tag](https://stackoverflow.com/questions/tagged/pdfbox).

pypdfbox's API is close enough to upstream that the answers
translate directly: the snake_case methods correspond one-for-one
to the camelCase methods in the Java answers. See the
[migration guide](migration-from-pdfbox.md) for the translation
rules.

## Security issues

Do not file security-relevant bugs as public GitHub issues. Please
contact the maintainer privately via the email on the GitHub
profile. We will acknowledge within a week, and aim to ship a fix
in the next wave once the impact is understood.

The same applies to issues that could let a malicious PDF cause
denial-of-service, memory exhaustion, or out-of-bounds reads
against pypdfbox. Triage and fix happen privately; disclosure
follows on the issue tracker once a patched release is out.

## Contributing back

If you ended up here because you have a fix and want to send it
upstream:

- [`docs/contributing.md`](contributing.md) — how PRs are
  structured, the parity-test requirement, the bookkeeping rules.
- [`docs/build.md`](build.md) — how to run the test suite + lint
  + pre-push hook locally before pushing.
- [`../CLAUDE.md`](../CLAUDE.md) — the authoritative project rules.

Thank you in advance for keeping pypdfbox tracking upstream.

## What pypdfbox does not provide

- **Commercial support.** This is a volunteer project. There is no
  paid support tier.
- **PDF/A or PDF/UA conformance validation.** Out of scope (Apache
  PDFBox 4.0 also removes Preflight). Pick whichever external
  validator your conformance regime requires; pypdfbox stays
  validator-agnostic.
- **PDF authoring tutorials.** The
  [PDFBox cookbook on the upstream site](https://pdfbox.apache.org/3.0/cookbook/)
  is the right reference — the recipes apply with `camelCase` →
  `snake_case`.
