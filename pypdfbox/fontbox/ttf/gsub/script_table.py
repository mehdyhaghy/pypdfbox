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


__all__ = ["ScriptTable"]
