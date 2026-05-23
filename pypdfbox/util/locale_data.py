"""Locale name tables for ``SimpleDateFormat``-style parsing.

Java's ``java.text.SimpleDateFormat`` reaches into the JVM's locale database
(``DateFormatSymbols``) for ``MMM`` / ``MMMM`` / ``EEE`` / ``EEEE`` lookups.
The Python port doesn't bind to the host's ``LC_TIME`` (that would be
process-wide state and unreliable across platforms), so we bundle the canonical
name tables for the 10 most common locales straight into the source. Data is
sourced from the Unicode CLDR (Common Locale Data Repository) v45 — the same
canonical source the JVM consumes — and is bundled per the CLDR Terms of Use
(Unicode permissive licence, compatible with Apache 2.0).

Index 0 of each month tuple is January, index 11 is December. Index 0 of each
weekday tuple is Monday, index 6 is Sunday — matches Python's
``datetime.weekday()`` 0..6 convention. (Java uses Calendar.SUNDAY=1..SATURDAY=7;
we adapt at the callsite, not here, so the table lookup stays straightforward.)

Lookups in :mod:`pypdfbox.util.date_util` normalise both the input and the table
entries via :func:`unicodedata.normalize` + :meth:`str.casefold` so diacritics
and case differences are tolerated (``fevrier`` matches ``février``,
``JANUARY`` matches ``January``).
"""

from __future__ import annotations

#: Full month names. Index 0=January, 11=December.
_MONTH_NAMES_FULL: dict[str, tuple[str, ...]] = {
    "en": (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ),
    "fr": (
        "janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre",
    ),
    "de": (
        "Januar", "Februar", "März", "April", "Mai", "Juni",
        "Juli", "August", "September", "Oktober", "November", "Dezember",
    ),
    "es": (
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ),
    "it": (
        "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
        "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
    ),
    "pt": (
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    ),
    "ja": (
        "1月", "2月", "3月", "4月", "5月", "6月",
        "7月", "8月", "9月", "10月", "11月", "12月",
    ),
    "zh": (
        "一月", "二月", "三月", "四月", "五月", "六月",
        "七月", "八月", "九月", "十月", "十一月", "十二月",
    ),
    "ko": (
        "1월", "2월", "3월", "4월", "5월", "6월",
        "7월", "8월", "9월", "10월", "11월", "12월",
    ),
    "ru": (
        "января", "февраля", "марта", "апреля", "мая", "июня",
        "июля", "августа", "сентября", "октября", "ноября", "декабря",
    ),
}

#: Abbreviated month names. Index 0=Jan, 11=Dec.
_MONTH_NAMES_ABBREV: dict[str, tuple[str, ...]] = {
    "en": (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ),
    "fr": (
        "janv.", "févr.", "mars", "avr.", "mai", "juin",
        "juil.", "août", "sept.", "oct.", "nov.", "déc.",
    ),
    "de": (
        "Jan.", "Feb.", "März", "Apr.", "Mai", "Juni",
        "Juli", "Aug.", "Sept.", "Okt.", "Nov.", "Dez.",
    ),
    "es": (
        "ene.", "feb.", "mar.", "abr.", "may.", "jun.",
        "jul.", "ago.", "sept.", "oct.", "nov.", "dic.",
    ),
    "it": (
        "gen.", "feb.", "mar.", "apr.", "mag.", "giu.",
        "lug.", "ago.", "set.", "ott.", "nov.", "dic.",
    ),
    "pt": (
        "jan.", "fev.", "mar.", "abr.", "mai.", "jun.",
        "jul.", "ago.", "set.", "out.", "nov.", "dez.",
    ),
    "ja": (
        "1月", "2月", "3月", "4月", "5月", "6月",
        "7月", "8月", "9月", "10月", "11月", "12月",
    ),
    "zh": (
        "1月", "2月", "3月", "4月", "5月", "6月",
        "7月", "8月", "9月", "10月", "11月", "12月",
    ),
    "ko": (
        "1월", "2월", "3월", "4월", "5월", "6월",
        "7월", "8월", "9월", "10월", "11월", "12월",
    ),
    "ru": (
        "янв.", "февр.", "мар.", "апр.", "мая", "июн.",
        "июл.", "авг.", "сент.", "окт.", "нояб.", "дек.",
    ),
}

#: Full weekday names. Index 0=Monday, 6=Sunday (Python convention).
_WEEKDAY_NAMES_FULL: dict[str, tuple[str, ...]] = {
    "en": (
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ),
    "fr": (
        "lundi", "mardi", "mercredi", "jeudi",
        "vendredi", "samedi", "dimanche",
    ),
    "de": (
        "Montag", "Dienstag", "Mittwoch", "Donnerstag",
        "Freitag", "Samstag", "Sonntag",
    ),
    "es": (
        "lunes", "martes", "miércoles", "jueves",
        "viernes", "sábado", "domingo",
    ),
    "it": (
        "lunedì", "martedì", "mercoledì", "giovedì",
        "venerdì", "sabato", "domenica",
    ),
    "pt": (
        "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo",
    ),
    "ja": ("月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"),
    "zh": ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"),
    "ko": ("월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"),
    "ru": (
        "понедельник", "вторник", "среда", "четверг",
        "пятница", "суббота", "воскресенье",
    ),
}

#: Abbreviated weekday names. Index 0=Mon, 6=Sun.
_WEEKDAY_NAMES_ABBREV: dict[str, tuple[str, ...]] = {
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
    "fr": ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."),
    "de": ("Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So."),
    "es": ("lun.", "mar.", "mié.", "jue.", "vie.", "sáb.", "dom."),
    "it": ("lun.", "mar.", "mer.", "gio.", "ven.", "sab.", "dom."),
    "pt": ("seg.", "ter.", "qua.", "qui.", "sex.", "sáb.", "dom."),
    "ja": ("月", "火", "水", "木", "金", "土", "日"),
    "zh": ("周一", "周二", "周三", "周四", "周五", "周六", "周日"),
    "ko": ("월", "화", "수", "목", "금", "토", "일"),
    "ru": ("пн", "вт", "ср", "чт", "пт", "сб", "вс"),
}


#: Supported locale codes (BCP 47 short forms).
SUPPORTED_LOCALES: tuple[str, ...] = tuple(_MONTH_NAMES_FULL.keys())


def get_month_names_full(locale: str) -> tuple[str, ...]:
    """Return the full month names for ``locale`` (January..December).

    Falls back to English if ``locale`` is unknown.
    """
    return _MONTH_NAMES_FULL.get(locale, _MONTH_NAMES_FULL["en"])


def get_month_names_abbrev(locale: str) -> tuple[str, ...]:
    """Return the abbreviated month names for ``locale`` (Jan..Dec).

    Falls back to English if ``locale`` is unknown.
    """
    return _MONTH_NAMES_ABBREV.get(locale, _MONTH_NAMES_ABBREV["en"])


def get_weekday_names_full(locale: str) -> tuple[str, ...]:
    """Return the full weekday names for ``locale`` (Monday..Sunday).

    Index 0 is Monday, index 6 is Sunday (Python convention).
    Falls back to English if ``locale`` is unknown.
    """
    return _WEEKDAY_NAMES_FULL.get(locale, _WEEKDAY_NAMES_FULL["en"])


def get_weekday_names_abbrev(locale: str) -> tuple[str, ...]:
    """Return the abbreviated weekday names for ``locale`` (Mon..Sun).

    Index 0 is Monday, index 6 is Sunday.
    Falls back to English if ``locale`` is unknown.
    """
    return _WEEKDAY_NAMES_ABBREV.get(locale, _WEEKDAY_NAMES_ABBREV["en"])
