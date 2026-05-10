from __future__ import annotations

from dataclasses import dataclass, field

from .lang_sys_table import LangSysTable


@dataclass
class ScriptTable:
    """OpenType Script table.

    Mirrors ``org.apache.fontbox.ttf.gsub.ScriptTable``. A script table
    bundles a default LangSys (used when the active language is the
    implicit default ``dflt``) plus zero or more per-language LangSys
    records keyed by 4-byte LangSys tag (e.g. ``ENG``, ``DEU``,
    ``TRK``).

    The default LangSys can legitimately be ``None`` when a script
    declares only language-specific entries — upstream stores this as a
    nullable reference.
    """

    default_lang_sys_table: LangSysTable | None = None
    lang_sys_tables: dict[str, LangSysTable] = field(default_factory=dict)

    def get_default_lang_sys_table(self) -> LangSysTable | None:
        return self.default_lang_sys_table

    def get_lang_sys_tables(self) -> dict[str, LangSysTable]:
        return self.lang_sys_tables

    def to_string(self) -> str:
        """Mirror upstream ``ScriptTable.toString()``.

        Upstream format:
        ``ScriptTable[hasDefault=<true|false>,langSysRecordsCount=<N>]``.
        The boolean is emitted lowercase (Java ``Boolean.toString``).
        """
        has_default = "true" if self.default_lang_sys_table is not None else "false"
        return (
            "ScriptTable["
            f"hasDefault={has_default},"
            f"langSysRecordsCount={len(self.lang_sys_tables)}]"
        )

    def __str__(self) -> str:
        return self.to_string()


__all__ = ["ScriptTable"]
