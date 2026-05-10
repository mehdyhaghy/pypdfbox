from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum


class StorageMode(Enum):
    MAIN_MEMORY_ONLY = "main_memory_only"
    TEMP_FILE_ONLY = "temp_file_only"
    MIXED = "mixed"


# Sentinel used to indicate "no explicit cap"; consumers treat as unlimited.
UNLIMITED: int = -1


@dataclass(frozen=True)
class MemoryUsageSetting:
    """
    Policy for where parsed PDF objects (decoded streams in particular)
    are stored: in main memory, in a temporary file, or a mix that spills
    to disk after a memory threshold.

    Use the ``setup_*`` factory class methods rather than constructing
    directly — they validate the combinations.
    """

    mode: StorageMode
    max_main_memory_bytes: int
    max_storage_bytes: int  # main memory + temp file combined; UNLIMITED = no cap
    # Optional directory for scratch files; mutated post-init via
    # set_temp_dir() (mirrors upstream ``setTempDir`` chaining setter).
    temp_dir: str | os.PathLike[str] | None = field(default=None)

    @classmethod
    def setup_main_memory_only(cls, max_main_memory_bytes: int = UNLIMITED) -> MemoryUsageSetting:
        cls._validate_limit(max_main_memory_bytes, "max_main_memory_bytes")
        return cls(
            mode=StorageMode.MAIN_MEMORY_ONLY,
            max_main_memory_bytes=max_main_memory_bytes,
            max_storage_bytes=max_main_memory_bytes,
        )

    @classmethod
    def setup_temp_file_only(cls, max_storage_bytes: int = UNLIMITED) -> MemoryUsageSetting:
        cls._validate_limit(max_storage_bytes, "max_storage_bytes")
        return cls(
            mode=StorageMode.TEMP_FILE_ONLY,
            max_main_memory_bytes=0,
            max_storage_bytes=max_storage_bytes,
        )

    @classmethod
    def setup_mixed(
        cls,
        max_main_memory_bytes: int,
        max_storage_bytes: int = UNLIMITED,
    ) -> MemoryUsageSetting:
        if max_main_memory_bytes < 0:
            raise ValueError("max_main_memory_bytes must be >= 0 in mixed mode")
        cls._validate_limit(max_storage_bytes, "max_storage_bytes")
        if (
            max_storage_bytes != UNLIMITED
            and max_storage_bytes < max_main_memory_bytes
        ):
            raise ValueError("max_storage_bytes must be >= max_main_memory_bytes")
        return cls(
            mode=StorageMode.MIXED,
            max_main_memory_bytes=max_main_memory_bytes,
            max_storage_bytes=max_storage_bytes,
        )

    @staticmethod
    def _validate_limit(value: int, name: str) -> None:
        if value < 0 and value != UNLIMITED:
            raise ValueError(f"{name} must be >= 0 or UNLIMITED")

    def is_main_memory_only(self) -> bool:
        return self.mode is StorageMode.MAIN_MEMORY_ONLY

    def is_temp_file_only(self) -> bool:
        return self.mode is StorageMode.TEMP_FILE_ONLY

    def is_mixed(self) -> bool:
        return self.mode is StorageMode.MIXED

    def is_storage_restricted(self) -> bool:
        return self.max_storage_bytes != UNLIMITED

    def is_main_memory_restricted(self) -> bool:
        return self.max_main_memory_bytes != UNLIMITED

    # ----- upstream parity accessors -----

    def use_main_memory(self) -> bool:
        """``True`` if main memory is used (i.e. mode is MAIN_MEMORY_ONLY or MIXED).

        Mirrors upstream ``MemoryUsageSetting.useMainMemory()``.
        """
        return self.mode is not StorageMode.TEMP_FILE_ONLY

    def use_temp_file(self) -> bool:
        """``True`` if temporary files are used (i.e. mode is TEMP_FILE_ONLY or MIXED).

        Mirrors upstream ``MemoryUsageSetting.useTempFile()``.
        """
        return self.mode is not StorageMode.MAIN_MEMORY_ONLY

    def get_max_main_memory_bytes(self) -> int:
        """Upstream alias for :attr:`max_main_memory_bytes`."""
        return self.max_main_memory_bytes

    def get_max_storage_bytes(self) -> int:
        """Upstream alias for :attr:`max_storage_bytes`."""
        return self.max_storage_bytes

    def get_temp_dir(self) -> str | os.PathLike[str] | None:
        """Directory for scratch / temp files, or ``None`` if not set.

        Mirrors upstream ``MemoryUsageSetting.getTempDir()``.
        """
        return self.temp_dir

    def set_temp_dir(
        self, temp_dir: str | os.PathLike[str] | None
    ) -> MemoryUsageSetting:
        """Set the directory used for temporary / scratch files.

        Returns ``self`` to allow chaining, mirroring upstream's fluent
        ``setTempDir`` setter. Mutates an otherwise-frozen instance via
        ``object.__setattr__`` because upstream is mutable in this one
        field.
        """
        object.__setattr__(self, "temp_dir", temp_dir)
        return self

    def to_string(self) -> str:
        """Mirror upstream ``MemoryUsageSetting.toString()``.

        Upstream nested ternary (Java lines 271-278) expanded into
        readable Python branches; the produced strings are byte-for-byte
        identical to upstream's output.
        """
        if self.use_main_memory():
            if self.use_temp_file():
                tail = (
                    f" and max. of {self.max_storage_bytes} storage bytes"
                    if self.is_storage_restricted()
                    else " and unrestricted scratch file size"
                )
                return (
                    f"Mixed mode with max. of {self.max_main_memory_bytes}"
                    f" main memory bytes{tail}"
                )
            if self.is_main_memory_restricted():
                return (
                    f"Main memory only with max. of {self.max_main_memory_bytes} bytes"
                )
            return "Main memory only with no size restriction"
        if self.is_storage_restricted():
            return f"Scratch file only with max. of {self.max_storage_bytes} bytes"
        return "Scratch file only with no size restriction"

    def __str__(self) -> str:
        return self.to_string()
