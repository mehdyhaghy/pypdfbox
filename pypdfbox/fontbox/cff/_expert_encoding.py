"""CFF Expert encoding (EncodingId 1) — code → glyph name.

Built from upstream Apache PDFBox 3.0
``org.apache.fontbox.cff.CFFExpertEncoding`` plus the canonical
CFF Standard Strings table (SIDs 0..390) shipped with fontTools as
``fontTools.cffLib.cffStandardStrings``.

The Expert encoding is specified in the CFF spec (Adobe Technote #5176,
Appendix B) and assigns a SID to each of the 256 single-byte codes;
SID 0 means ``.notdef``.

This table is hard-resolved at module import so :class:`CFFType1Font`
can answer ``code_to_name`` / ``name_to_code`` without traversing the
parsed font's STRING INDEX (which doesn't change the answer for
predefined encodings).
"""

from __future__ import annotations

from fontTools.cffLib import cffStandardStrings  # type: ignore[import-untyped]

# (charCode, charSID) — copied verbatim from CFFExpertEncoding.java.
_RAW: tuple[tuple[int, int], ...] = (
    (32, 1), (33, 229), (34, 230), (36, 231), (37, 232), (38, 233),
    (39, 234), (40, 235), (41, 236), (42, 237), (43, 238), (44, 13),
    (45, 14), (46, 15), (47, 99), (48, 239), (49, 240), (50, 241),
    (51, 242), (52, 243), (53, 244), (54, 245), (55, 246), (56, 247),
    (57, 248), (58, 27), (59, 28), (60, 249), (61, 250), (62, 251),
    (63, 252), (65, 253), (66, 254), (67, 255), (68, 256), (69, 257),
    (73, 258), (76, 259), (77, 260), (78, 261), (79, 262), (82, 263),
    (83, 264), (84, 265), (86, 266), (87, 109), (88, 110), (89, 267),
    (90, 268), (91, 269), (93, 270), (94, 271), (95, 272), (96, 273),
    (97, 274), (98, 275), (99, 276), (100, 277), (101, 278), (102, 279),
    (103, 280), (104, 281), (105, 282), (106, 283), (107, 284), (108, 285),
    (109, 286), (110, 287), (111, 288), (112, 289), (113, 290), (114, 291),
    (115, 292), (116, 293), (117, 294), (118, 295), (119, 296), (120, 297),
    (121, 298), (122, 299), (123, 300), (124, 301), (125, 302), (126, 303),
    (161, 304), (162, 305), (163, 306), (166, 307), (167, 308), (168, 309),
    (169, 310), (170, 311), (172, 312), (175, 313), (178, 314), (179, 315),
    (182, 316), (183, 317), (184, 318), (188, 158), (189, 155), (190, 163),
    (191, 319), (192, 320), (193, 321), (194, 322), (195, 323), (196, 324),
    (197, 325), (200, 326), (201, 150), (202, 164), (203, 169), (204, 327),
    (205, 328), (206, 329), (207, 330), (208, 331), (209, 332), (210, 333),
    (211, 334), (212, 335), (213, 336), (214, 337), (215, 338), (216, 339),
    (217, 340), (218, 341), (219, 342), (220, 343), (221, 344), (222, 345),
    (223, 346), (224, 347), (225, 348), (226, 349), (227, 350), (228, 351),
    (229, 352), (230, 353), (231, 354), (232, 355), (233, 356), (234, 357),
    (235, 358), (236, 359), (237, 360), (238, 361), (239, 362), (240, 363),
    (241, 364), (242, 365), (243, 366), (244, 367), (245, 368), (246, 369),
    (247, 370), (248, 371), (249, 372), (250, 373), (251, 374), (252, 375),
    (253, 376), (254, 377), (255, 378),
)


def _build_table() -> dict[int, str]:
    out: dict[int, str] = {}
    for code, sid in _RAW:
        if 0 <= sid < len(cffStandardStrings):
            name = cffStandardStrings[sid]
            if name and name != ".notdef":
                out[code] = name
    return out


EXPERT_ENCODING_TABLE: dict[int, str] = _build_table()


__all__ = ["EXPERT_ENCODING_TABLE"]
