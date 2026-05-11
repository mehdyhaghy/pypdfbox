"""Port of ``CertificateVerificationResult`` (upstream lines 1-65)."""

from __future__ import annotations

from typing import Any


class CertificateVerificationResult:
    """Outcome of a PKIX certificate-path validation.

    Mirrors the upstream class copied from Apache CXF 2.4.9. In pypdfbox the
    ``result`` payload is whatever the verifier returned (we use a plain
    object instead of ``PKIXCertPathBuilderResult``), and ``exception``
    carries the failure if the path could not be built.
    """

    def __init__(
        self,
        result: Any = None,
        exception: BaseException | None = None,
    ) -> None:
        if exception is not None:
            self._valid = False
            self._result: Any = None
            self._exception: BaseException | None = exception
        else:
            self._valid = True
            self._result = result
            self._exception = None

    def is_valid(self) -> bool:
        return self._valid

    def get_result(self) -> Any:
        return self._result

    def get_exception(self) -> BaseException | None:
        return self._exception
