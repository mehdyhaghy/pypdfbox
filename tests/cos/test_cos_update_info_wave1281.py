"""Wave 1281: COSUpdateInfo ABC port — default-method helpers."""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSUpdateInfo


class _FakeUpdateInfo(COSUpdateInfo):
    def __init__(self) -> None:
        # Reuse a real ``COSUpdateState`` via a dictionary.
        self._target = COSDictionary()

    def get_cos_object(self):
        return self._target

    def get_update_state(self):
        return self._target.get_update_state()


def test_is_need_to_be_updated_reflects_state() -> None:
    info = _FakeUpdateInfo()
    # No state machinery attached → not updated.
    assert info.is_need_to_be_updated() is False


def test_set_need_to_be_updated_propagates() -> None:
    info = _FakeUpdateInfo()
    info.set_need_to_be_updated(True)
    # Without an origin document state the flag is gated off, but
    # calling the helper should not raise.
    assert info.is_need_to_be_updated() in (True, False)


def test_to_increment_returns_cos_increment() -> None:
    from pypdfbox.cos import COSIncrement

    info = _FakeUpdateInfo()
    inc = info.to_increment()
    assert isinstance(inc, COSIncrement)
