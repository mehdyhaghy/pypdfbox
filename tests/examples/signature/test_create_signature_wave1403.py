"""Wave 1403 branch round-out for ``create_signature``.

Closes ``39->41``: a trailing CLI argument that is neither ``-tsa`` nor
``-e`` falls through the ``if args[idx] == "-e"`` check (False arc) and the
parser simply advances ``idx``.
"""

from __future__ import annotations

from pypdfbox.examples.signature.create_signature import CreateSignature


def test_main_ignores_unrecognised_trailing_flag(
    monkeypatch, tmp_path, pkcs12_bytes,
) -> None:
    keystore = tmp_path / "keystore.p12"
    keystore.write_bytes(pkcs12_bytes)
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4\n%%EOF\n")

    captured: dict[str, object] = {}

    def fake_sign(self, in_file, out_file, tsa_url):
        captured["tsa"] = tsa_url
        captured["external"] = self.is_external_signing()

    monkeypatch.setattr(
        CreateSignature, "sign_detached", fake_sign, raising=True,
    )

    # The trailing "--unknown" token matches neither -tsa nor -e, so the
    # loop takes the False arc of ``if args[idx] == "-e"`` (39->41).
    CreateSignature.main([str(keystore), "hunter2", str(pdf), "--unknown"])
    assert captured["tsa"] is None
    assert captured["external"] is False
