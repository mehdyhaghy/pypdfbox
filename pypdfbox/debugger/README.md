# pypdfbox.debugger

Tkinter port of `org.apache.pdfbox.debugger` — the standalone GUI
inspector that ships with upstream PDFBox under
`debugger-app/src/main/java/org/apache/pdfbox/debugger/`. Lets you
open a PDF, walk the COS object graph, and drill into pages,
streams, fonts, colour spaces, signatures, and embedded files.

## What it is

The upstream Java debugger is a Swing `JFrame` with a
`JSplitPane` (COS tree on the left, detail pane on the right), a
`JMenuBar`, and a status bar (`ReaderBottomPanel`). The Python
port translates the layout to `ttk.PanedWindow` +
`ttk.Treeview` + `tk.Menu`. On every tree-selection event the
right-hand pane is swapped to whichever specialised viewer fits
the current node:

- `PagePane` — page dictionaries (rasterises through
  `PDFRenderer` at the chosen zoom + rotation).
- `StreamPane` — content streams and image XObjects (raw bytes,
  decoded operator stream, or rendered preview).
- `HexEditor` — non-content-stream binary blobs.
- `StringPane` — `COSString` values (text / hex toggles).
- `FontEncodingView` (via `FontEncodingPaneController`) — font
  dictionaries with `/Encoding`, `/Differences`, ToUnicode CMap
  decoding.
- `CSDeviceN` / `CSIndexed` / `CSSeparation` / `CSArrayBased` —
  colour-space arrays.
- `FlagBitsPane` — flag-bearing dictionary entries
  (`/Annot` flags, `/Font` flags, etc.).
- `SignaturePane` — PKCS#7 signature `/Contents` decoded via
  `cryptography`.
- A generic `ttk.Treeview` "key=value" panel for everything else.

## Launching

```sh
python -m pypdfbox.debugger.pd_debugger <file.pdf>
```

The CLI dispatcher wires a `pypdfbox debug` (`pypdfbox debugger`)
subcommand that launches the same shell, so the following is
equivalent when the package is installed:

```sh
pypdfbox debugger <file.pdf>
```

Without a path argument the debugger opens with an empty tree;
use **File → Open** to load a PDF.

The shell is also embeddable as a Python widget — construct a
`PDFDebugger` over any `tk.Misc` master and drive `open_document`
to load a PDF programmatically. The panes update via the standard
`<<TreeviewSelect>>` virtual event.

## Feature overview

- **COS tree view** — lazy expansion mirrors upstream's
  `TreeStatus` walk. Indirect references resolve on demand;
  cycles short-circuit.
- **Page pane** — rasterised page preview with zoom, rotation,
  page-up / page-down, and a click-to-extract-glyph debug
  overlay. Rendering goes through `PDFRenderer`, the same code
  path the production renderer uses.
- **Stream pane** — toggle between raw bytes, decoded content
  stream (operator + operand display), and rendered XObject
  preview. Inline images and image XObjects render via Pillow.
- **Font encoding pane** — shows the active encoding table,
  `/Differences` overrides, and the per-glyph Unicode mapping
  driven by the ToUnicode CMap. Handles Type1, Type1C, TrueType,
  Type3, CIDFontType0, and CIDFontType2.
- **Colour-space pane** — DeviceN, Separation, Indexed, ICCBased,
  CalRGB, CalGray, Lab, and Pattern entries each get a
  specialised viewer with tint-transform sampling and the lookup
  table for Indexed.
- **Text-search / find** — `Ctrl-F` opens the find dialog; jumps
  across the page tree by indirect-ref token, by content-stream
  text, or by COS dictionary key.
- **Recent files** — the **File** menu tracks the last 10
  documents opened, persisted under the user's config dir.
- **Window prefs** — pane split position, font size, and the
  recent-files list are persisted between sessions through the
  `PDFDebuggerConfig` helper (`~/.config/pypdfbox/debugger.ini`
  on POSIX, `%APPDATA%\pypdfbox\debugger.ini` on Windows).
- **Print** — rasterises every page via `PDFRenderer` into a
  temp multi-page PDF and hands it to the host OS spooler (`lp`
  / `lpr` on POSIX, `os.startfile(..., "print")` on Windows).

## Cross-platform notes

- **Tk timing on Windows** — widget mapping after
  `update_idletasks` is asynchronous on Windows. The Tk timing
  in `update_idletasks` finishes before the platform paints the
  widget tree. Test code that asserts on
  `winfo_children` / `winfo_ismapped` / `winfo_viewable`
  immediately after construction either waits via
  `wait_visibility()` or skips on Win32 — production code is
  unaffected because the user-driven interaction always lands
  after the platform paint.
- **macOS native dialogs** — File-open and save-as use the
  stdlib `tkinter.filedialog`, which on macOS routes to the
  Cocoa native chooser. The macOS application menu (About,
  Quit, Preferences) is wired through the stdlib
  `createcommand` route in `OSXAdapter` rather than the Java
  reflection trick upstream uses.
- **Printing** — there is no portable Tk print API. Each
  platform's spooler is invoked through a subprocess call
  (`lp` on POSIX, the Win32 `ShellExecute` "print" verb via
  `os.startfile` on Windows).
- **Drag-and-drop** — upstream's Swing `TransferHandler` is not
  ported. `tkdnd` is a third-party package and is intentionally
  out of scope (no copyleft / non-permissive deps).

## Source provenance

Every file in this directory has a row in `PROVENANCE.md`
mapping it to the upstream Java path. The Swing→Tk translation
preserves class names where they directly map (`PDFDebugger`,
`PagePane`, `StreamPane`, `HexEditor`, `StringPane`,
`SignaturePane`, `FlagBitsPane`, `FontEncodingPaneController`)
and snake-cases methods. Behavioural deviations
(printing, native menu integration, drag-and-drop) are recorded
in `CHANGES.md`.
