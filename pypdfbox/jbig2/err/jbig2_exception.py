from __future__ import annotations


class JBIG2Exception(Exception):
    """
    Identifies a JBIG2 exception.

    Mirrors ``org.apache.pdfbox.jbig2.err.JBIG2Exception``. Upstream extends
    ``java.lang.Exception`` (a checked exception, *not* ``IOException``), so the
    Python port subclasses the built-in :class:`Exception` rather than
    :class:`OSError`.

    The four upstream constructors map onto a single Python initializer:

    * ``JBIG2Exception()``                  -> ``JBIG2Exception()``
    * ``JBIG2Exception(message)``           -> ``JBIG2Exception("...")``
    * ``JBIG2Exception(cause)``             -> ``JBIG2Exception(cause=exc)``
    * ``JBIG2Exception(message, cause)``    -> ``JBIG2Exception("...", cause=exc)``

    The ``cause`` is wired through Python's exception-chaining mechanism
    (``raise ... from cause``-equivalent) by setting ``__cause__`` so that the
    originating exception is preserved exactly as Java's ``getCause()`` would.
    """

    def __init__(
        self,
        message: str | None = None,
        cause: BaseException | None = None,
    ) -> None:
        if message is None:
            super().__init__()
        else:
            super().__init__(message)
        if cause is not None:
            self.__cause__ = cause
