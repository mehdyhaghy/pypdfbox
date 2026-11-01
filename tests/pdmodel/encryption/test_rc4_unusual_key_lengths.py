"""RC4 documents with file keys the ``cryptography`` ARC4 binding rejects
(48 to 120 bits; PDFBOX-5955) decrypt like PDFBox. The documents are
built here from the PDF 1.7 algorithms 2, 3 and 5, independent of
pypdfbox; PDFBox 3.0.8 reads the same files and returns the same titles."""

import hashlib
import struct

import pytest

from pypdfbox import PDDocument

_PAD = bytes.fromhex(
    "28BF4E5E4E758A4164004E56FFFA01082E2E00B6D0683E802F0CA9FE6453697A"
)
_FILE_ID = bytes(range(16))
_PERMS = -4


def _rc4(key: bytes, data: bytes) -> bytes:
    s = list(range(256))
    j = 0
    for i in range(256):
        j = (j + s[i] + key[i % len(key)]) & 255
        s[i], s[j] = s[j], s[i]
    i = j = 0
    out = bytearray()
    for byte in data:
        i = (i + 1) & 255
        j = (j + s[i]) & 255
        s[i], s[j] = s[j], s[i]
        out.append(byte ^ s[(s[i] + s[j]) & 255])
    return bytes(out)


def _padded(password: bytes) -> bytes:
    return (password + _PAD)[:32]


def _rc4_rounds(key: bytes, data: bytes) -> bytes:
    data = _rc4(key, data)
    for i in range(1, 20):
        data = _rc4(bytes(b ^ i for b in key), data)
    return data


def _build(bits: int, user: bytes = b"usr", owner: bytes = b"own") -> bytes:
    n = bits // 8
    digest = hashlib.md5(_padded(owner)).digest()
    for _ in range(50):
        digest = hashlib.md5(digest).digest()
    o_entry = _rc4_rounds(digest[:n], _padded(user))

    digest = hashlib.md5(
        _padded(user) + o_entry + struct.pack("<i", _PERMS) + _FILE_ID
    ).digest()
    for _ in range(50):
        digest = hashlib.md5(digest[:n]).digest()
    key = digest[:n]
    u_entry = _rc4_rounds(key, hashlib.md5(_PAD + _FILE_ID).digest()) + bytes(16)

    object_key = hashlib.md5(
        key + (4).to_bytes(3, "little") + (0).to_bytes(2, "little")
    ).digest()[: min(n + 5, 16)]
    title = _rc4(object_key, f"secret {bits}".encode())

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>",
        b"<< /Title <" + title.hex().encode() + b"> >>",
        (
            f"<< /Filter /Standard /V 2 /R 3 /Length {bits} /P {_PERMS} "
            f"/O <{o_entry.hex()}> /U <{u_entry.hex()}> >>"
        ).encode(),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 4 0 R "
        f"/Encrypt 5 0 R /ID [<{_FILE_ID.hex()}> <{_FILE_ID.hex()}>] >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


@pytest.mark.parametrize("bits", range(40, 129, 8))
def test_rc4_key_length_decrypts(bits: int) -> None:
    with PDDocument.load(_build(bits), password="usr") as doc:
        assert doc.get_encryption().get_length() == bits
        assert doc.get_document_information().get_title() == f"secret {bits}"
