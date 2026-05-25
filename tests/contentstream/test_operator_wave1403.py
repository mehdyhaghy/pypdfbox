"""Wave 1403 branch round-out for ``Operator.get_operator``.

Closes 86->89 — the inner double-checked-locking ``if cached is None`` False
arm: another thread populated the cache between the lock-free outer check
(line 81) and re-acquiring it under the lock (line 85). In that race the
inner re-read finds the entry already present, so the create-and-store block
is skipped and the existing instance is returned.

We make the race deterministic by swapping the class lock for a context
manager that inserts the cache entry on ``__enter__`` — i.e. exactly the
window the second check guards against. The original lock and any cache
pollution are restored afterwards.
"""

from __future__ import annotations

from pypdfbox.contentstream import Operator


def test_get_operator_inner_check_finds_concurrently_inserted_entry() -> None:
    """Closes 86->89: simulate a concurrent insert occurring between the two
    cache reads so the inner ``if cached is None`` is False."""
    name = "__wave1403_race_op__"
    saved_cache = dict(Operator._operators)  # noqa: SLF001
    saved_lock = Operator._operators_lock  # noqa: SLF001

    # Ensure the outer (line 81) read returns None.
    Operator._operators.pop(name, None)  # noqa: SLF001

    sentinel = Operator(name)

    class _InsertingLock:
        def __enter__(self) -> _InsertingLock:
            # Mimic another thread winning the race: populate the cache
            # before the inner re-read at line 85.
            Operator._operators[name] = sentinel  # noqa: SLF001
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    Operator._operators_lock = _InsertingLock()  # type: ignore[assignment]  # noqa: SLF001
    try:
        result = Operator.get_operator(name)
        # The inner check found the concurrently-inserted instance.
        assert result is sentinel
    finally:
        Operator._operators_lock = saved_lock  # noqa: SLF001
        Operator._operators.clear()  # noqa: SLF001
        Operator._operators.update(saved_cache)  # noqa: SLF001
