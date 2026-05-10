#!/usr/bin/env python3
"""Parity coverage report: pypdfbox vs Apache PDFBox.

Walks the upstream PDFBox Java source and the local pypdfbox Python source,
matches classes by name and methods by snake_case-converted name, and prints
a per-class + overall coverage summary.

This is a *coarse* estimate, not a correctness check. It only sees method
*names*; it doesn't compare semantics or argument types. A class that's
"100% covered" by this script might still be wrong — that's what the
oracle/upstream-port tests in tests/<module>/upstream/ are for.

Usage:
    python scripts/parity.py /path/to/pdfbox-3.0.x [--module cos] [--missing] [--json out.json]

Or with PDFBOX_SRC env var:
    PDFBOX_SRC=/path/to/pdfbox-3.0.x python scripts/parity.py

The Java path should be the PDFBox repo root (so `<root>/pdfbox/src/main/java/...`
resolves). pypdfbox source is auto-detected as the parent of this script's directory.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------- data model ----------


@dataclass
class JavaClass:
    fqn: str  # e.g. "org.apache.pdfbox.cos.COSName"
    module: str  # e.g. "org.apache.pdfbox.cos"
    simple_name: str  # e.g. "COSName"
    file: Path
    methods: set[str] = field(default_factory=set)  # snake_case-converted names


@dataclass
class PythonClass:
    fqn: str  # e.g. "pypdfbox.cos.cos_name.COSName"
    module: str  # e.g. "pypdfbox.cos"
    simple_name: str  # e.g. "COSName"
    file: Path
    methods: set[str] = field(default_factory=set)  # snake_case names
    bases: list[str] = field(default_factory=list)  # base class simple names


# ---------- name normalisation ----------


_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def camel_to_snake(name: str) -> str:
    """Java-style camelCase / PascalCase → Python snake_case.

    Treats consecutive uppercase as a single boundary group so that
    ``parsePDF`` → ``parse_pdf``, ``readBE`` → ``read_be``, ``getXFA`` →
    ``get_xfa``.
    """
    # Collapse runs of uppercase to a single chunk, then snake.
    out = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    out = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", out)
    return out.lower()


# ---------- Java parsing ----------

# Java method signature regex. Permissive but conservative:
#   - Optional modifiers (public/protected/private/static/final/abstract/synchronized/native/...)
#   - Optional generic params <T, U>
#   - Return type (any non-( token chain — keeps generics by allowing < and >)
#   - Method name = identifier
#   - Open paren
# Skips constructors (handled separately) and annotations (lines starting with @).
_JAVA_METHOD = re.compile(
    r"""
    ^[\t ]*                                    # leading whitespace
    (?:                                        # access modifiers (any order, optional)
        (?:public|protected|private|static|final|abstract|synchronized|native|default|strictfp)\s+
    )*
    (?:<[^>]+>\s+)?                            # optional generic type params
    (?P<ret>[\w.<>?,\[\]\s]+?)                 # return type
    \s+
    (?P<name>[a-zA-Z_$][\w$]*)                 # method name
    \s*\(                                      # open paren
    """,
    re.VERBOSE | re.MULTILINE,
)

_JAVA_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
_JAVA_CLASS_DECL = re.compile(
    r"^\s*(?:public\s+|protected\s+|private\s+|static\s+|final\s+|abstract\s+)*"
    r"(?:class|interface|enum)\s+(\w+)",
    re.MULTILINE,
)

# Reserved Java keywords commonly mistaken for return types.
_JAVA_KEYWORDS = {
    "if", "else", "while", "do", "for", "switch", "case", "break", "continue",
    "return", "throw", "throws", "try", "catch", "finally", "new", "this",
    "super", "instanceof", "import", "package", "class", "interface", "enum",
    "extends", "implements", "true", "false", "null",
}


_RET_TOKEN = re.compile(r"\w+")


def _find_class_body_end(stripped: str, decl_end: int) -> tuple[int, int]:
    """Return ``(body_start, body_end)`` for the class declaration ending at
    ``decl_end``. ``body_start`` is the position of the opening ``{``;
    ``body_end`` is the position of the matching closing ``}``. If neither
    is found, both default to ``len(stripped)``.

    Comments + string literals are already replaced with spaces by
    :func:`_strip_java_comments_and_strings`, so brace counting is safe.
    """
    n = len(stripped)
    open_brace = stripped.find("{", decl_end)
    if open_brace == -1:
        return n, n
    depth = 1
    i = open_brace + 1
    while i < n and depth > 0:
        c = stripped[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return open_brace, i
        i += 1
    return open_brace, n


def _scan_methods_at_depth_one(
    stripped: str,
    body_start: int,
    body_end: int,
    nested_decls: list[tuple[int, int]],
) -> set[str]:
    """Scan ``stripped[body_start:body_end]`` for method declarations that
    occur at the **immediate** body of the class — i.e. at the brace depth
    just inside the class's opening ``{``. ``nested_decls`` is a list of
    ``(start, end)`` spans for inner class/enum/interface bodies that should
    be skipped. Linear in the body size; no string copying.
    """
    methods: set[str] = set()
    # Build a sorted list of nested-span start positions so we can fast-skip
    # entire inner-class bodies in one jump.
    nested_decls = sorted(nested_decls, key=lambda s: s[0])
    nest_idx = 0

    # We start one position after the body's opening `{`, at depth 1.
    i = body_start + 1
    n = body_end
    while i < n:
        # If we're at the start of a nested span, jump past it.
        if nest_idx < len(nested_decls):
            ns_start, ns_end = nested_decls[nest_idx]
            if i >= ns_end:
                nest_idx += 1
                continue
            if i == ns_start:
                i = ns_end
                nest_idx += 1
                continue
        # Try to match a method declaration starting from `i`. The regex is
        # multiline but anchored at ``^[ \t]*``, so we match only when ``i``
        # is at a line start or after whitespace.
        if stripped[i] == "\n":
            i += 1
            continue
        m = _JAVA_METHOD.match(stripped, i, n)
        if m is None:
            # Skip to next line.
            nl = stripped.find("\n", i, n)
            i = nl + 1 if nl != -1 else n
            continue
        # We have a candidate. Validate it before adding.
        mname = m.group("name")
        ret = m.group("ret").strip()
        if (
            mname in _JAVA_KEYWORDS
            or ret == ""
            or mname[0].isupper()
        ):
            i = m.end()
            continue
        ret_tokens = _RET_TOKEN.findall(ret)
        if not ret_tokens or any(t in _JAVA_KEYWORDS for t in ret_tokens):
            i = m.end()
            continue
        methods.add(camel_to_snake(mname))
        i = m.end()
    return methods


def parse_java_file(path: Path) -> list[JavaClass]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    package_m = _JAVA_PACKAGE.search(text)
    package = package_m.group(1) if package_m else ""

    # Strip block + line comments + string literals so the method regex
    # doesn't match inside them. Replace each with whitespace of the same
    # length so line offsets stay sensible (not strictly required here).
    stripped = _strip_java_comments_and_strings(text)

    classes: list[JavaClass] = []
    class_decls = list(_JAVA_CLASS_DECL.finditer(stripped))
    if not class_decls:
        return []

    # Compute body spans for every class declaration once.
    bodies: list[tuple[int, int, int]] = []  # (decl_idx, body_open_brace, body_close_brace)
    for i, decl in enumerate(class_decls):
        open_brace, close_brace = _find_class_body_end(stripped, decl.end())
        bodies.append((i, open_brace, close_brace))

    # For each class, collect the spans of any nested classes contained
    # *strictly* within its body so the method scanner can skip them.
    for idx, open_b, close_b in bodies:
        decl = class_decls[idx]
        name = decl.group(1)
        if name in _JAVA_KEYWORDS:
            continue
        nested: list[tuple[int, int]] = []
        for j_idx, j_open, j_close in bodies:
            if j_idx == idx:
                continue
            # Nested if its declaration sits between this class's open and close.
            j_decl_start = class_decls[j_idx].start()
            if open_b < j_decl_start < close_b and j_close <= close_b:
                nested.append((j_decl_start, j_close + 1))

        cls = JavaClass(
            fqn=f"{package}.{name}" if package else name,
            module=package,
            simple_name=name,
            file=path,
        )
        for mname in _scan_methods_at_depth_one(stripped, open_b, close_b, nested):
            if mname == camel_to_snake(name):
                continue  # constructor
            cls.methods.add(mname)

        if cls.methods:
            classes.append(cls)

    return classes


def _strip_java_comments_and_strings(text: str) -> str:
    """Remove // and /* */ comments + "..." string literals.

    Replaces each removed span with spaces of the same length so positions
    stay consistent.
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = text.find("\n", i)
            j = j if j != -1 else n
            out.append(" " * (j - i))
            i = j
        elif c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            j = j + 2 if j != -1 else n
            out.append("\n" if False else " " * (j - i))
            i = j
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                j += 1
            j = j + 1 if j < n else n
            out.append(" " * (j - i))
            i = j
        elif c == "'":
            j = i + 1
            while j < n and text[j] != "'":
                if text[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                j += 1
            j = j + 1 if j < n else n
            out.append(" " * (j - i))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


# ---------- Python parsing ----------

_DUNDER = re.compile(r"^__\w+__$")


def parse_python_file(path: Path, package_root: Path) -> list[PythonClass]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        return []

    rel = path.relative_to(package_root.parent)
    module = ".".join(rel.with_suffix("").parts)
    if module.endswith(".__init__"):
        module = module[: -len(".__init__")]

    classes: list[PythonClass] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        cls = PythonClass(
            fqn=f"{module}.{node.name}",
            module=".".join(module.split(".")[:-1]) if "." in module else module,
            simple_name=node.name,
            file=path,
        )
        # Capture base class simple names so the matcher can walk the MRO and
        # credit inherited methods. We only need the trailing identifier
        # (`PDDictionaryWrapper`, not `pypdfbox.pdmodel.common.PDDictionaryWrapper`).
        for base in node.bases:
            if isinstance(base, ast.Name):
                cls.bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                cls.bases.append(base.attr)
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if _DUNDER.match(item.name):
                    continue
                cls.methods.add(item.name)
        if cls.methods or cls.bases:
            classes.append(cls)
    return classes


# ---------- discovery + matching ----------


def find_java_files(java_root: Path) -> list[Path]:
    """Walk PDFBox-style source roots under ``java_root``.

    Looks at every subproject's ``src/main/java/`` and ``src/test/java/``
    is *excluded* — we only score the production surface.
    """
    out: list[Path] = []
    for src in java_root.rglob("src/main/java"):
        if not src.is_dir():
            continue
        for jf in src.rglob("*.java"):
            out.append(jf)
    return out


def find_python_files(package_root: Path) -> list[Path]:
    return [p for p in package_root.rglob("*.py") if "__pycache__" not in p.parts]


def index_java_classes(files: list[Path]) -> dict[str, JavaClass]:
    """Index by simple class name; collisions merge methods (lossy but fine
    for an estimate)."""
    out: dict[str, JavaClass] = {}
    for f in files:
        for cls in parse_java_file(f):
            existing = out.get(cls.simple_name)
            if existing is None:
                out[cls.simple_name] = cls
            else:
                existing.methods |= cls.methods
    return out


def index_python_classes(files: list[Path], package_root: Path) -> dict[str, PythonClass]:
    out: dict[str, PythonClass] = {}
    for f in files:
        for cls in parse_python_file(f, package_root):
            existing = out.get(cls.simple_name)
            if existing is None:
                out[cls.simple_name] = cls
            else:
                existing.methods |= cls.methods
    return out


@dataclass
class ClassReport:
    name: str
    java_methods: int
    python_methods: int
    matched_methods: int
    missing_methods: list[str]
    extra_methods: list[str]
    java_file: str
    python_file: str

    @property
    def coverage(self) -> float:
        if self.java_methods == 0:
            return 0.0
        return self.matched_methods / self.java_methods


def _collect_methods_with_mro(
    pcls: PythonClass,
    python: dict[str, PythonClass],
    seen: set[str] | None = None,
) -> set[str]:
    """Collect a Python class's methods including those inherited from any
    indexed base class (recursively). The base graph is keyed on simple names,
    so we can resolve cross-file inheritance even without import resolution.
    """
    if seen is None:
        seen = set()
    if pcls.simple_name in seen:
        return set()
    seen.add(pcls.simple_name)
    out = set(pcls.methods)
    for base_name in pcls.bases:
        base = python.get(base_name)
        if base is not None:
            out |= _collect_methods_with_mro(base, python, seen)
    return out


def build_report(
    java: dict[str, JavaClass],
    python: dict[str, PythonClass],
    module_filter: str | None = None,
) -> tuple[list[ClassReport], list[str]]:
    """Returns (matched class reports, java-only class names)."""
    reports: list[ClassReport] = []
    java_only: list[str] = []
    for name, jcls in sorted(java.items()):
        if module_filter and module_filter not in jcls.module:
            continue
        pcls = python.get(name)
        if pcls is None:
            java_only.append(jcls.fqn)
            continue
        # Walk the Python MRO so a subclass gets credit for methods defined on
        # its bases — Java's parity scanner counts methods declared on each
        # class regardless of inheritance, but Python conventionally relies on
        # inherited dispatch.
        py_methods = _collect_methods_with_mro(pcls, python)
        matched = jcls.methods & py_methods
        missing = sorted(jcls.methods - py_methods)
        # Extra methods are still reported relative to the *declared* set so
        # callers can spot unique additions, not the full MRO surface.
        extra = sorted(pcls.methods - jcls.methods)
        reports.append(
            ClassReport(
                name=name,
                java_methods=len(jcls.methods),
                python_methods=len(pcls.methods),
                matched_methods=len(matched),
                missing_methods=missing,
                extra_methods=extra,
                java_file=str(jcls.file),
                python_file=str(pcls.file),
            )
        )
    return reports, java_only


# ---------- output ----------


def print_text_report(
    reports: list[ClassReport],
    java_only: list[str],
    *,
    show_missing: bool = False,
    top_n: int = 0,
) -> None:
    if not reports and not java_only:
        print("(no classes matched the filter)")
        return

    total_j = sum(r.java_methods for r in reports)
    total_p = sum(r.python_methods for r in reports)
    total_match = sum(r.matched_methods for r in reports)
    overall = total_match / total_j if total_j else 0.0

    # Sort: lowest coverage first (most-missing classes float to the top).
    rows = sorted(reports, key=lambda r: (r.coverage, -r.java_methods))
    if top_n > 0:
        rows = rows[:top_n]

    name_w = max((len(r.name) for r in rows), default=20)
    name_w = max(name_w, 20)
    print(f"{'Class':<{name_w}}  {'Java':>5}  {'Py':>5}  {'Match':>5}  {'Cov':>6}")
    print("-" * (name_w + 2 + 5 + 2 + 5 + 2 + 5 + 2 + 6))
    for r in rows:
        cov = f"{r.coverage * 100:5.1f}%"
        print(
            f"{r.name:<{name_w}}  {r.java_methods:>5}  "
            f"{r.python_methods:>5}  {r.matched_methods:>5}  {cov:>6}"
        )
        if show_missing and r.missing_methods:
            for m in r.missing_methods[:10]:
                print(f"    - missing: {m}()")
            if len(r.missing_methods) > 10:
                print(f"    ... +{len(r.missing_methods) - 10} more missing")

    print()
    print(f"Classes matched : {len(reports)}")
    print(f"Classes Java-only: {len(java_only)}")
    print(f"Java methods    : {total_j}")
    print(f"Py  methods     : {total_p}")
    print(f"Matched methods : {total_match}")
    print(f"Overall coverage: {overall * 100:.1f}%")

    if java_only and show_missing:
        print()
        print(f"Java-only classes (no Python counterpart, first 30 of {len(java_only)}):")
        for fqn in java_only[:30]:
            print(f"  - {fqn}")


def write_json_report(
    path: Path,
    reports: list[ClassReport],
    java_only: list[str],
) -> None:
    payload = {
        "summary": {
            "matched_classes": len(reports),
            "java_only_classes": len(java_only),
            "java_methods": sum(r.java_methods for r in reports),
            "python_methods": sum(r.python_methods for r in reports),
            "matched_methods": sum(r.matched_methods for r in reports),
        },
        "classes": [
            {
                "name": r.name,
                "java_methods": r.java_methods,
                "python_methods": r.python_methods,
                "matched_methods": r.matched_methods,
                "coverage": r.coverage,
                "missing_methods": r.missing_methods,
                "extra_methods": r.extra_methods,
                "java_file": r.java_file,
                "python_file": r.python_file,
            }
            for r in reports
        ],
        "java_only_classes": java_only,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ---------- entry ----------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "java_root",
        nargs="?",
        type=Path,
        help="Path to the Apache PDFBox source root "
        "(defaults to $PDFBOX_SRC).",
    )
    parser.add_argument(
        "--python-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "pypdfbox",
        help="Path to the pypdfbox package directory.",
    )
    parser.add_argument(
        "--module",
        help="Filter to Java classes whose package contains this substring "
        "(e.g. 'cos', 'pdmodel.font', 'rendering').",
    )
    parser.add_argument(
        "--missing",
        action="store_true",
        help="Print per-class missing method names + Java-only classes.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="Show only the worst N coverage classes (default: all).",
    )
    parser.add_argument(
        "--json",
        type=Path,
        help="Write a JSON report to this path.",
    )
    args = parser.parse_args(argv)

    java_root = args.java_root or (
        Path(os.environ["PDFBOX_SRC"]) if "PDFBOX_SRC" in os.environ else None
    )
    if java_root is None:
        parser.error(
            "PDFBox source path required: pass it as a positional arg or set "
            "$PDFBOX_SRC. Clone with: "
            "git clone --depth 1 https://github.com/apache/pdfbox.git /tmp/pdfbox"
        )
    if not java_root.is_dir():
        print(f"Java root not found: {java_root}", file=sys.stderr)
        return 2

    python_root = args.python_root
    if not python_root.is_dir():
        print(f"Python root not found: {python_root}", file=sys.stderr)
        return 2

    print(f"Scanning Java   : {java_root}", file=sys.stderr)
    java_files = find_java_files(java_root)
    print(f"  {len(java_files)} .java files", file=sys.stderr)
    java_classes = index_java_classes(java_files)
    print(f"  {len(java_classes)} indexed classes", file=sys.stderr)

    print(f"Scanning Python : {python_root}", file=sys.stderr)
    py_files = find_python_files(python_root)
    print(f"  {len(py_files)} .py files", file=sys.stderr)
    py_classes = index_python_classes(py_files, python_root)
    print(f"  {len(py_classes)} indexed classes", file=sys.stderr)
    print(file=sys.stderr)

    reports, java_only = build_report(java_classes, py_classes, args.module)
    print_text_report(reports, java_only, show_missing=args.missing, top_n=args.top)

    if args.json:
        write_json_report(args.json, reports, java_only)
        print(f"\nJSON report written to {args.json}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
