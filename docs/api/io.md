# pypdfbox.io — random-access primitives and scratch storage

The `io` layer is the foundation of pypdfbox: it abstracts every form of
byte storage a PDF parser/writer might consume, so the layers above it
(`cos`, `pdfparser`, `pdfwriter`) can work uniformly against `bytes`, `mmap`,
or a paged scratch file on disk. Like upstream PDFBox 3.x it splits read,
write, and read/write into three separate Protocols (`RandomAccessRead`,
`RandomAccessWrite`, `RandomAccess`) and provides concrete implementations
for each backing store. Memory pressure is controlled via
`MemoryUsageSetting`, plumbed all the way from `Loader.load_pdf` through
`PDFParser` into the per-stream cache.

## Public surface

| Class / function | Purpose |
| --- | --- |
| `RandomAccessRead` | Protocol — `read`, `read_at`, `seek`, `peek`, `length`, `is_closed`, `rewind`. Every reader implements it. |
| `RandomAccessWrite` | Protocol — `write`, `close`. Mirrors PDFBox `RandomAccessWrite`. |
| `RandomAccess` | Protocol combining the two; backs scratch buffers and writable buffers. |
| `RandomAccessReadBuffer` | In-memory `bytes` / `bytearray`-backed reader. Use for `<256 MB` inputs. |
| `RandomAccessReadBufferedFile` | Open-file reader with an internal page cache; default for `path.open("rb")` use. |
| `RandomAccessReadMemoryMapped` | `mmap`-backed reader over an existing fileno. |
| `RandomAccessReadMemoryMappedFile` | `mmap`-backed reader that owns its file handle. |
| `RandomAccessReadView` | Read-only slice over another `RandomAccessRead`. |
| `RandomAccessReadWriteBuffer` | In-memory read/write buffer. |
| `RandomAccessWriteBuffer` | Append-only in-memory write sink. |
| `RandomAccessInputStream` | `io.RawIOBase` adapter wrapping any `RandomAccessRead`. |
| `RandomAccessOutputStream` | `io.RawIOBase` adapter wrapping any `RandomAccessWrite`. |
| `NonSeekableRandomAccessReadInputStream` | Adapter for streams that don't expose seek (network, pipes). |
| `SequenceRandomAccessRead` | Concatenates several `RandomAccessRead`s into one logical stream. |
| `ScratchFile` | Paged temp-file allocator. Default page size `DEFAULT_PAGE_SIZE` (4 KiB); free-list sentinel `NO_FREE_PAGE`. |
| `ScratchFileBuffer` | `RandomAccess` view over a `ScratchFile` page chain. |
| `RandomAccessStreamCache` | Protocol — `create_buffer() -> RandomAccess`. Lets the parser allocate stream cache buffers without knowing the backing storage. |
| `RandomAccessStreamCacheImpl` | Default implementation: hands out `ScratchFileBuffer`s. |
| `StreamCacheCreateFunction` | Protocol — `(MemoryUsageSetting) -> RandomAccessStreamCache`. |
| `MemoryUsageSetting` | Cap configuration (`main_memory_bytes`, `scratch_file_bytes`, `storage_mode`). `UNLIMITED` is the unconstrained sentinel. |
| `StorageMode` | `enum.Enum` — `MAIN_MEMORY`, `SCRATCH_FILE`, `MIXED`. |
| `create_memory_only_stream_cache` | Factory: stream cache that never spills to disk. |
| `create_temp_file_only_stream_cache` | Factory: stream cache that immediately spills to a temp file. |
| `create_protected_temp_file` / `create_protected_temp_dir` | 0600-mode temp resources, used by the encryption + signing paths. |
| `populate_buffer`, `to_byte_array`, `copy`, `unmap`, `close_quietly`, `close_and_log_exception` | Helper functions for safe I/O lifecycle. |

## Typical usage

```python
from pypdfbox import Loader
from pypdfbox.io import MemoryUsageSetting

# Bounded memory budget: 64 MiB RAM, then spill to scratch file.
budget = MemoryUsageSetting.setup_mixed(
    main_memory_bytes=64 * 1024 * 1024,
    scratch_file_bytes=1024 * 1024 * 1024,
)
with Loader.load_pdf("huge.pdf", memory_usage_setting=budget) as doc:
    print(doc.get_number_of_pages())
```

The reader path is uniform regardless of backing — `Loader` picks the right
`RandomAccessRead` implementation based on the input type (`bytes`, `str`,
`pathlib.Path`, `io.BufferedReader`, or an already-built `RandomAccessRead`).

## Cross-platform notes

- `RandomAccessReadMemoryMapped*` uses `mmap.ACCESS_READ` on Windows and
  `mmap.PROT_READ` on POSIX — never assume one constant set is available.
  The wrappers feature-detect at import time.
- `RandomAccessReadBufferedFile` always closes the underlying handle on
  exit; on Windows this is required before `Path.unlink` can succeed.
- `create_protected_temp_file` returns a file created with `mode=0o600` on
  POSIX. On Windows the ACL is left to the OS default; do not assume
  POSIX-style permission bits.

## PDFBox divergence

- `RandomAccessBufferedFileInputStream` (Java) collapses into
  `RandomAccessReadBufferedFile` plus `RandomAccessInputStream` rather than
  carrying its own `InputStream` lineage.
- Java's `IOException` becomes Python's `OSError` everywhere except inside
  the parser, where `PDFParseError` (subclass of `OSError`) is preferred so
  callers can distinguish corruption from disk errors.
- `MemoryUsageSetting.setupMixed(...)` is `MemoryUsageSetting.setup_mixed(...)`.

## See also

- [pdfparser.md](pdfparser.md) — consumes `RandomAccessRead` and a
  `StreamCacheCreateFunction`.
- [pdfwriter.md](pdfwriter.md) — writes through `RandomAccessOutputStream`.
- [guides/large-files.md](../guides/large-files.md) — picking the right
  `MemoryUsageSetting` for your input size.
- [migration.md](../migration.md) — `RandomAccessFile` (Java) → which
  `RandomAccess*` in pypdfbox.
