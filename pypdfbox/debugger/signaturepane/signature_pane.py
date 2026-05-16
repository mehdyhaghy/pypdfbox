"""Tkinter port of ``org.apache.pdfbox.debugger.signaturepane.SignaturePane``.

Renders the ``/Contents`` PKCS#7 SignedData blob of a PDF signature
dictionary. The upstream class shows a single tab containing a raw
ASN.1 dump produced by Bouncy Castle's ``ASN1Dump``. Bouncy Castle has
no Python equivalent in our dependency set; we instead expose two
views:

* an ``ASN.1 View`` tab — a hex dump of the raw bytes (best-effort,
  matches upstream's fallback when ASN.1 parsing fails);
* a ``Certificates`` tab — a ``ttk.Treeview`` listing each embedded
  X.509 certificate (Subject / Issuer / Validity) extracted via
  ``cryptography.hazmat.primitives.serialization.pkcs7``.

Note: the wave instructions mention ``asn1crypto.cms``, but that
package is not in this project's approved dependency set (see
``pyproject.toml``). We use the already-approved ``cryptography``
package, which can load PKCS#7 SignedData and expose embedded
certificates via ``load_der_pkcs7_certificates``.
"""

from __future__ import annotations

import contextlib
import datetime as _datetime
import logging
import tkinter as tk
from dataclasses import dataclass, field
from tkinter import ttk

from pypdfbox.cos import COSString

_LOG = logging.getLogger(__name__)


@dataclass
class _CertSummary:
    """Lightweight summary of one embedded X.509 certificate."""

    subject: str = ""
    issuer: str = ""
    serial_number: str = ""
    not_before: str = ""
    not_after: str = ""
    errors: list[str] = field(default_factory=list)


def parse_pkcs7_certificates(blob: bytes) -> list[_CertSummary]:
    """Return one summary per X.509 cert embedded in a PKCS#7 SignedData blob.

    On failure (or when no certificates are present) returns an empty
    list. Diagnostic information is captured on the first summary's
    ``errors`` list when the parser raises.
    """
    summaries: list[_CertSummary] = []
    trimmed = blob.rstrip(b"\x00")
    try:
        from cryptography.hazmat.primitives.serialization import pkcs7
    except ImportError as exc:  # pragma: no cover — install-time guard
        err = _CertSummary()
        err.errors.append(f"cryptography is required: {exc}")
        return [err]

    try:
        certs = pkcs7.load_der_pkcs7_certificates(trimmed)
    except Exception as exc:  # noqa: BLE001 — propagate as a single error entry
        err = _CertSummary()
        err.errors.append(f"failed to parse PKCS#7: {exc}")
        return [err]

    for cert in certs:
        summary = _CertSummary()
        try:
            summary.subject = cert.subject.rfc4514_string()
        except Exception as exc:  # noqa: BLE001
            summary.errors.append(f"subject: {exc}")
        try:
            summary.issuer = cert.issuer.rfc4514_string()
        except Exception as exc:  # noqa: BLE001
            summary.errors.append(f"issuer: {exc}")
        try:
            summary.serial_number = format(int(cert.serial_number), "x")
        except Exception as exc:  # noqa: BLE001
            summary.errors.append(f"serial: {exc}")
        try:
            summary.not_before = _utc_string(
                getattr(cert, "not_valid_before_utc", None)
                or cert.not_valid_before
            )
            summary.not_after = _utc_string(
                getattr(cert, "not_valid_after_utc", None)
                or cert.not_valid_after
            )
        except Exception as exc:  # noqa: BLE001
            summary.errors.append(f"validity: {exc}")
        summaries.append(summary)
    return summaries


def _utc_string(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, _datetime.datetime):
        return value.isoformat()
    return str(value)


def hex_dump(blob: bytes, *, group: int = 2, columns: int = 16) -> str:
    """Format ``blob`` as a hexdump (matches upstream's fallback view)."""
    lines: list[str] = []
    width = group * columns
    for offset in range(0, len(blob), width):
        chunk = blob[offset:offset + width]
        groups: list[str] = []
        for i in range(0, len(chunk), group):
            groups.append(chunk[i:i + group].hex())
        lines.append(f"{offset:08x}  " + " ".join(groups))
    return "\n".join(lines)


class SignaturePane:
    """Tabbed view onto a PKCS#7 ``/Contents`` blob."""

    _ASN1_TAB = "ASN.1 View"
    _CERTS_TAB = "Certificates"
    DEFAULT_WIDTH = 300
    DEFAULT_HEIGHT = 500

    def __init__(self, master: tk.Misc | None, cos_string: COSString) -> None:
        self._cos_string = cos_string
        self._tabbed_pane = ttk.Notebook(master)
        with contextlib.suppress(tk.TclError):
            self._tabbed_pane.configure(
                width=self.DEFAULT_WIDTH, height=self.DEFAULT_HEIGHT
            )

        self._asn1_text = self.create_text_view(cos_string)
        self._cert_tree = self._create_cert_view(cos_string)
        self._tabbed_pane.add(self._asn1_text.master, text=self._ASN1_TAB)
        self._tabbed_pane.add(self._cert_tree.master, text=self._CERTS_TAB)

    # ---- public accessors --------------------------------------------------

    def get_pane(self) -> ttk.Notebook:
        """Return the underlying ``ttk.Notebook``."""
        return self._tabbed_pane

    @property
    def asn1_text(self) -> tk.Text:
        """The ``tk.Text`` widget holding the ASN.1 hex dump."""
        return self._asn1_text

    @property
    def cert_tree(self) -> ttk.Treeview:
        """The ``ttk.Treeview`` listing embedded certificates."""
        return self._cert_tree

    # ---- internals ---------------------------------------------------------

    def create_text_view(self, cos_string: COSString) -> tk.Text:
        """Create the ASN.1-view text widget for ``cos_string``.

        Mirrors upstream ``SignaturePane.createTextView``. The Swing
        original returns a ``JTextPane`` showing the ASN.1 dump; the
        Tkinter port returns a scrollable ``tk.Text`` containing the
        :func:`hex_dump` output (or the hex-string fallback when the
        blob is empty), matching upstream's ``IOException`` fallback
        path. The body comes from :meth:`get_text_string`.

        Renamed from the previous private ``_create_asn1_view``; the
        alias is preserved below for back-compat.
        """
        wrapper = ttk.Frame(self._tabbed_pane)
        text = tk.Text(wrapper, wrap="none", font=("TkFixedFont", 11))
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)

        try:
            body = self.get_text_string(cos_string)
        except Exception as exc:  # noqa: BLE001 — surface but never crash widget
            body = f"<failed to dump signature: {exc}>"
        text.insert("1.0", body)
        text.configure(state="disabled")
        return text

    # Back-compat alias for the previous private spelling.
    _create_asn1_view = create_text_view

    @staticmethod
    def get_text_string(cos_string: COSString) -> str:
        """Return the ASN.1 text body for ``cos_string``.

        Mirrors upstream ``SignaturePane.getTextString``. Upstream
        parses the bytes with Bouncy Castle's ``ASN1StreamParser`` and
        falls back to ``"<" + cosString.toHexString() + ">"`` on
        ``IOException``. pypdfbox uses :func:`hex_dump` for the textual
        view (Bouncy Castle has no Python equivalent in our approved
        dependency set), and falls back to the upstream hex-string
        format when the blob is empty so the upstream fallback shape
        is still observable.
        """
        blob = cos_string.get_bytes()
        dump = hex_dump(blob)
        if dump:
            return dump
        return "<" + cos_string.to_hex_string() + ">"

    def _create_cert_view(self, cos_string: COSString) -> ttk.Treeview:
        wrapper = ttk.Frame(self._tabbed_pane)
        columns = ("issuer", "serial", "not_before", "not_after")
        tree = ttk.Treeview(wrapper, columns=columns, show="tree headings")
        tree.heading("#0", text="Subject")
        tree.heading("issuer", text="Issuer")
        tree.heading("serial", text="Serial #")
        tree.heading("not_before", text="Not Before")
        tree.heading("not_after", text="Not After")
        tree.column("#0", width=180, anchor="w")
        for column in columns:
            tree.column(column, width=140, anchor="w")
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        wrapper.rowconfigure(0, weight=1)
        wrapper.columnconfigure(0, weight=1)

        for summary in parse_pkcs7_certificates(cos_string.get_bytes()):
            self._insert_summary(tree, summary)
        return tree

    @staticmethod
    def _insert_summary(tree: ttk.Treeview, summary: _CertSummary) -> None:
        text = summary.subject or "<unknown>"
        item = tree.insert(
            "",
            "end",
            text=text,
            values=(
                summary.issuer,
                summary.serial_number,
                summary.not_before,
                summary.not_after,
            ),
        )
        for err in summary.errors:
            tree.insert(item, "end", text=err, values=("", "", "", ""))
