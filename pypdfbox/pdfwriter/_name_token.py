"""Serialized ``/Name`` tokens for the writers' hot paths."""

import re

# Any byte outside the PDFBox name printable allowlist (A-Z a-z 0-9 and
# ``+ - _ @ * $ ; .``, see ``COSName.writePDF``). Used to escape a whole
# name in one ``re.sub`` pass instead of a per-byte loop.
_NAME_ESCAPE_RE = re.compile(rb"[^A-Za-z0-9+\-_@*$;.]")

# Memo of encoded name tokens (``/`` + escaped bytes), keyed on the raw name
# bytes. Documents reuse a small vocabulary of names millions of times; the
# cap bounds memory for pathological inputs with many unique names.
_NAME_TOKEN_CACHE: dict[bytes, bytes] = {}
_NAME_TOKEN_CACHE_MAX = 65536


def _escape_name_byte(match: re.Match[bytes]) -> bytes:
    return b"#%02X" % match.group()[0]


def name_token(raw: bytes) -> bytes:
    """Return the serialized ``/Name`` token for ``raw`` name bytes,
    ``#xx``-escaping every non-printable byte (ISO 32000-1 §7.3.5).
    Byte-identical to upstream ``COSName.writePDF``."""
    if type(raw) is not bytes:
        raw = bytes(raw)
    token = _NAME_TOKEN_CACHE.get(raw)
    if token is None:
        token = b"/" + _NAME_ESCAPE_RE.sub(_escape_name_byte, raw)
        if len(_NAME_TOKEN_CACHE) >= _NAME_TOKEN_CACHE_MAX:
            _NAME_TOKEN_CACHE.clear()
        _NAME_TOKEN_CACHE[raw] = token
    return token
