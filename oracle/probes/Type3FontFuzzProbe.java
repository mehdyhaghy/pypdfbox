import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontFactory;
import org.apache.pdfbox.pdmodel.font.PDType3CharProc;
import org.apache.pdfbox.pdmodel.font.PDType3Font;
import org.apache.pdfbox.util.Matrix;

/**
 * Differential fuzz probe for {@code PDType3Font} / {@code PDType3CharProc}
 * malformed-dictionary leniency, Apache PDFBox 3.0.7 (wave 1522, agent D).
 *
 * <h2>What this covers that the existing Type 3 probes do not</h2>
 * The four existing Type-3 probes ({@code Type3FontProbe},
 * {@code Type3CharProcProbe}, {@code Type3CharProcAccessorProbe},
 * {@code Type3CharProcEdgeProbe}, {@code Type3D0D1Probe}) all build a
 * <em>well-formed</em> Type 3 font (real {@code /FontMatrix}, real
 * {@code /Differences}, real {@code /CharProcs} streams) and verify the
 * value-parity of the accessors. None of them fuzzes the dictionary itself.
 * This probe builds deliberately MALFORMED Type 3 font dictionaries in memory
 * and projects the leniency of each accessor:
 * <ul>
 *   <li>{@code /FontMatrix} missing / wrong length / non-numeric / null /
 *       6-int vs 6-float;</li>
 *   <li>{@code /FontBBox} missing / wrong length (2,3,5 entries) /
 *       non-numeric / null;</li>
 *   <li>{@code /CharProcs} missing / non-dict / a glyph entry that is a dict /
 *       scalar / null instead of a stream;</li>
 *   <li>{@code /Encoding} missing / a name vs dict-with-{@code /Differences} /
 *       a {@code .notdef} glyph that DOES have a char proc;</li>
 *   <li>{@code /Widths} length mismatch vs {@code /FirstChar} /
 *       {@code /LastChar}, out-of-range code, missing {@code /Widths};</li>
 *   <li>per-glyph char-proc {@code getWidth} / {@code getGlyphBBox} over a
 *       {@code d0} proc, a {@code d1} proc, an empty proc, and a garbage proc
 *       (no {@code d0}/{@code d1}).</li>
 * </ul>
 *
 * <h2>Input</h2>
 * Deterministic, seed-free, no file I/O: a fixed inline corpus of Type 3
 * {@code COSDictionary}s built identically on both sides. The pypdfbox sibling
 * (tests/pdmodel/font/oracle/test_type3_font_fuzz_wave1522.py) rebuilds the
 * identical dicts and asserts each {@code CASE} line matches; intentional
 * pypdfbox robustness divergences are pinned both-sides with a CHANGES.md
 * citation.
 *
 * <h2>Output grammar (one line per case)</h2>
 * <pre>
 *   CASE &lt;name&gt; create=&lt;ok|ERR:X|NotType3&gt; fm=&lt;a,b,c,d,e,f|ERR&gt;
 *        bbox=&lt;llx,lly,urx,ury|null|ERR&gt; cp=&lt;sorted,glyph,names|-|ERR&gt;
 *        w65=&lt;float|ERR&gt; gc65=&lt;cw=&lt;float&gt;,gb=&lt;...|null&gt;|null|ERR&gt;
 * </pre>
 * Floats are rendered with {@link #f(float)} (trailing zeros trimmed) so a
 * 600 and a 600.0 render identically across both languages.
 */
public final class Type3FontFuzzProbe {

    static PrintStream out;

    static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    static COSInteger i(int v) {
        return COSInteger.get(v);
    }

    static COSFloat fl(double v) {
        return new COSFloat((float) v);
    }

    static COSArray arr(COSBase... items) {
        COSArray a = new COSArray();
        for (COSBase b : items) {
            a.add(b);
        }
        return a;
    }

    static String f(float v) {
        if (v == Math.rint(v) && !Float.isInfinite(v)) {
            return Long.toString((long) v);
        }
        return Float.toString(v);
    }

    // ---------- char-proc stream builders ----------

    static COSStream stream(String body) {
        COSStream s = new COSStream();
        try {
            java.io.OutputStream os = s.createOutputStream();
            os.write(body.getBytes("US-ASCII"));
            os.close();
        } catch (Exception e) {
            throw new RuntimeException(e);
        }
        return s;
    }

    /** A d1 glyph proc: wx 0 llx lly urx ury d1 ... */
    static COSStream d1Proc(double wx) {
        return stream(f((float) wx) + " 0 0 0 500 700 d1\n0 0 500 700 re f\n");
    }

    /** A d0 glyph proc: wx 0 d0 ... */
    static COSStream d0Proc(double wx) {
        return stream(f((float) wx) + " 0 d0\n0 0 500 700 re f\n");
    }

    static COSStream emptyProc() {
        return stream("");
    }

    static COSStream garbageProc() {
        return stream("0 0 500 700 re f\n");
    }

    // ---------- font-dict builder ----------

    /** Minimal Type 3 font dict skeleton; callers add the fuzzed entries. */
    static COSDictionary type3() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        d.setItem(COSName.SUBTYPE, n("Type3"));
        return d;
    }

    /** /Encoding dict that maps code -&gt; glyph name via /Differences. */
    static COSDictionary encoding(int[] codes, String[] names) {
        COSDictionary enc = new COSDictionary();
        enc.setItem(COSName.TYPE, n("Encoding"));
        COSArray diffs = new COSArray();
        for (int k = 0; k < codes.length; k++) {
            diffs.add(i(codes[k]));
            diffs.add(n(names[k]));
        }
        enc.setItem(n("Differences"), diffs);
        return enc;
    }

    // ---------- projection ----------

    static String matrixStr(PDType3Font font) {
        try {
            Matrix m = font.getFontMatrix();
            if (m == null) {
                return "null";
            }
            // Matrix exposes a/b/c/d/e/f scale/translate; build the 6-tuple
            // from the affine accessors so it matches pypdfbox's list.
            return f(m.getScaleX()) + "," + f(m.getShearY()) + ","
                    + f(m.getShearX()) + "," + f(m.getScaleY()) + ","
                    + f(m.getTranslateX()) + "," + f(m.getTranslateY());
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String bboxStr(PDType3Font font) {
        try {
            PDRectangle r = font.getFontBBox();
            if (r == null) {
                return "null";
            }
            return f(r.getLowerLeftX()) + "," + f(r.getLowerLeftY()) + ","
                    + f(r.getUpperRightX()) + "," + f(r.getUpperRightY());
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String charProcsStr(PDType3Font font) {
        try {
            COSDictionary cp = font.getCharProcs();
            if (cp == null) {
                return "-";
            }
            java.util.TreeSet<String> keys = new java.util.TreeSet<>();
            for (COSName k : cp.keySet()) {
                keys.add(k.getName());
            }
            return String.join(",", keys);
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String widthStr(PDType3Font font, int code) {
        try {
            return f(font.getWidth(code));
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String charProcStr(PDType3Font font, int code) {
        try {
            PDType3CharProc cp = font.getCharProc(code);
            if (cp == null) {
                return "null";
            }
            String cw;
            try {
                cw = f(cp.getWidth());
            } catch (Throwable t) {
                cw = "ERR";
            }
            String gb;
            try {
                PDRectangle r = cp.getGlyphBBox();
                gb = (r == null) ? "null"
                        : (f(r.getLowerLeftX()) + "," + f(r.getLowerLeftY())
                           + "," + f(r.getUpperRightX()) + ","
                           + f(r.getUpperRightY()));
            } catch (Throwable t) {
                gb = "ERR";
            }
            return "cw=" + cw + ",gb=" + gb;
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static void emit(String name, COSDictionary dict, int code) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDFont font;
        try {
            font = PDFontFactory.createFont(dict);
        } catch (Throwable t) {
            out.println(sb.append("create=ERR:")
                    .append(t.getClass().getSimpleName()).toString());
            return;
        }
        if (!(font instanceof PDType3Font)) {
            out.println(sb.append("create=NotType3").toString());
            return;
        }
        PDType3Font t3 = (PDType3Font) font;
        sb.append("create=ok")
          .append(" fm=").append(matrixStr(t3))
          .append(" bbox=").append(bboxStr(t3))
          .append(" cp=").append(charProcsStr(t3))
          .append(" w").append(code).append('=').append(widthStr(t3, code))
          .append(" gc").append(code).append('=').append(charProcStr(t3, code));
        out.println(sb.toString());
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        int[] codes = {65};
        String[] names = {"alpha"};

        // ===== /FontMatrix fuzzing =====
        // Well-formed custom 6-float matrix.
        COSDictionary fmOk = type3();
        fmOk.setItem(n("FontMatrix"),
                arr(fl(0.002), fl(0), fl(0), fl(0.002), fl(0), fl(0)));
        emit("fm_ok", fmOk, 65);

        // Missing /FontMatrix -> spec default.
        emit("fm_missing", type3(), 65);

        // Wrong length (4 entries).
        COSDictionary fm4 = type3();
        fm4.setItem(n("FontMatrix"), arr(fl(1), fl(0), fl(0), fl(1)));
        emit("fm_len4", fm4, 65);

        // Wrong length (8 entries).
        COSDictionary fm8 = type3();
        fm8.setItem(n("FontMatrix"),
                arr(fl(1), fl(0), fl(0), fl(1), fl(0), fl(0), fl(9), fl(9)));
        emit("fm_len8", fm8, 65);

        // Non-numeric entry (a name in slot 2).
        COSDictionary fmName = type3();
        fmName.setItem(n("FontMatrix"),
                arr(fl(0.002), n("X"), fl(0), fl(0.002), fl(0), fl(0)));
        emit("fm_nonnumeric", fmName, 65);

        // Null entry in the array.
        COSDictionary fmNull = type3();
        fmNull.setItem(n("FontMatrix"),
                arr(fl(0.002), COSNull.NULL, fl(0), fl(0.002), fl(0), fl(0)));
        emit("fm_null_entry", fmNull, 65);

        // /FontMatrix is a name, not an array.
        COSDictionary fmIsName = type3();
        fmIsName.setItem(n("FontMatrix"), n("Identity"));
        emit("fm_is_name", fmIsName, 65);

        // 6 ints (not floats) -> valid.
        COSDictionary fmInts = type3();
        fmInts.setItem(n("FontMatrix"),
                arr(i(1), i(0), i(0), i(1), i(0), i(0)));
        emit("fm_six_ints", fmInts, 65);

        // ===== /FontBBox fuzzing =====
        COSDictionary bbOk = type3();
        bbOk.setItem(n("FontBBox"), arr(i(0), i(0), i(750), i(1000)));
        emit("bbox_ok", bbOk, 65);

        emit("bbox_missing", type3(), 65);

        COSDictionary bb2 = type3();
        bb2.setItem(n("FontBBox"), arr(i(0), i(0)));
        emit("bbox_len2", bb2, 65);

        COSDictionary bb3 = type3();
        bb3.setItem(n("FontBBox"), arr(i(0), i(0), i(750)));
        emit("bbox_len3", bb3, 65);

        COSDictionary bb5 = type3();
        bb5.setItem(n("FontBBox"), arr(i(0), i(0), i(750), i(1000), i(99)));
        emit("bbox_len5", bb5, 65);

        COSDictionary bbName = type3();
        bbName.setItem(n("FontBBox"), arr(i(0), n("X"), i(750), i(1000)));
        emit("bbox_nonnumeric", bbName, 65);

        COSDictionary bbIsName = type3();
        bbIsName.setItem(n("FontBBox"), n("Big"));
        emit("bbox_is_name", bbIsName, 65);

        // Reversed corners (urx < llx) -> upstream stores raw (no normalize).
        COSDictionary bbRev = type3();
        bbRev.setItem(n("FontBBox"), arr(i(750), i(1000), i(0), i(0)));
        emit("bbox_reversed", bbRev, 65);

        // ===== /CharProcs fuzzing =====
        // Well-formed: one d1 glyph "alpha" mapped at code 65.
        COSDictionary cpOk = type3();
        cpOk.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary cpDict = new COSDictionary();
        cpDict.setItem(n("alpha"), d1Proc(600));
        cpOk.setItem(n("CharProcs"), cpDict);
        emit("cp_ok_d1", cpOk, 65);

        // d0 glyph.
        COSDictionary cpD0 = type3();
        cpD0.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary cpD0Dict = new COSDictionary();
        cpD0Dict.setItem(n("alpha"), d0Proc(444));
        cpD0.setItem(n("CharProcs"), cpD0Dict);
        emit("cp_d0", cpD0, 65);

        // empty proc.
        COSDictionary cpEmpty = type3();
        cpEmpty.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary cpEmptyDict = new COSDictionary();
        cpEmptyDict.setItem(n("alpha"), emptyProc());
        cpEmpty.setItem(n("CharProcs"), cpEmptyDict);
        emit("cp_empty_proc", cpEmpty, 65);

        // garbage proc (no d0/d1).
        COSDictionary cpGarbage = type3();
        cpGarbage.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary cpGarbageDict = new COSDictionary();
        cpGarbageDict.setItem(n("alpha"), garbageProc());
        cpGarbage.setItem(n("CharProcs"), cpGarbageDict);
        emit("cp_garbage_proc", cpGarbage, 65);

        // missing /CharProcs entirely.
        COSDictionary cpMissing = type3();
        cpMissing.setItem(COSName.ENCODING, encoding(codes, names));
        emit("cp_missing", cpMissing, 65);

        // /CharProcs is not a dict (it's a name).
        COSDictionary cpNotDict = type3();
        cpNotDict.setItem(COSName.ENCODING, encoding(codes, names));
        cpNotDict.setItem(n("CharProcs"), n("Nope"));
        emit("cp_not_dict", cpNotDict, 65);

        // glyph entry is a dict (not a stream).
        COSDictionary cpEntryDict = type3();
        cpEntryDict.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary cpEntryDictDict = new COSDictionary();
        cpEntryDictDict.setItem(n("alpha"), new COSDictionary());
        cpEntryDict.setItem(n("CharProcs"), cpEntryDictDict);
        emit("cp_entry_dict", cpEntryDict, 65);

        // glyph entry is a scalar (integer).
        COSDictionary cpEntryInt = type3();
        cpEntryInt.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary cpEntryIntDict = new COSDictionary();
        cpEntryIntDict.setItem(n("alpha"), i(7));
        cpEntryInt.setItem(n("CharProcs"), cpEntryIntDict);
        emit("cp_entry_int", cpEntryInt, 65);

        // glyph entry is null.
        COSDictionary cpEntryNull = type3();
        cpEntryNull.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary cpEntryNullDict = new COSDictionary();
        cpEntryNullDict.setItem(n("alpha"), COSNull.NULL);
        cpEntryNull.setItem(n("CharProcs"), cpEntryNullDict);
        emit("cp_entry_null", cpEntryNull, 65);

        // code maps to a name not present in /CharProcs.
        COSDictionary cpNoName = type3();
        cpNoName.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary cpNoNameDict = new COSDictionary();
        cpNoNameDict.setItem(n("beta"), d1Proc(600));
        cpNoName.setItem(n("CharProcs"), cpNoNameDict);
        emit("cp_name_absent", cpNoName, 65);

        // ===== /Encoding fuzzing =====
        // Missing /Encoding -> getCharProc returns null (no name map).
        COSDictionary encMissing = type3();
        COSDictionary encMissingCp = new COSDictionary();
        encMissingCp.setItem(n("alpha"), d1Proc(600));
        encMissing.setItem(n("CharProcs"), encMissingCp);
        emit("enc_missing", encMissing, 65);

        // /Encoding is a name (predefined) -> code 65 -> "A"; no "A" proc.
        COSDictionary encName = type3();
        encName.setItem(COSName.ENCODING, n("WinAnsiEncoding"));
        COSDictionary encNameCp = new COSDictionary();
        encNameCp.setItem(n("A"), d1Proc(321));
        encName.setItem(n("CharProcs"), encNameCp);
        emit("enc_name_winansi", encName, 65);

        // /Encoding maps code 65 -> ".notdef" AND a ".notdef" proc exists.
        COSDictionary encNotdef = type3();
        encNotdef.setItem(COSName.ENCODING,
                encoding(new int[]{65}, new String[]{".notdef"}));
        COSDictionary encNotdefCp = new COSDictionary();
        encNotdefCp.setItem(n(".notdef"), d1Proc(123));
        encNotdef.setItem(n("CharProcs"), encNotdefCp);
        emit("enc_notdef_has_proc", encNotdef, 65);

        // ===== /Widths fuzzing =====
        // Widths present, code in window.
        COSDictionary wOk = type3();
        wOk.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary wOkCp = new COSDictionary();
        wOkCp.setItem(n("alpha"), d1Proc(600));
        wOk.setItem(n("CharProcs"), wOkCp);
        wOk.setItem(COSName.FIRST_CHAR, i(65));
        wOk.setItem(COSName.LAST_CHAR, i(65));
        wOk.setItem(COSName.WIDTHS, arr(fl(610)));
        emit("w_in_window", wOk, 65);

        // Widths shorter than FirstChar..LastChar window.
        COSDictionary wShort = type3();
        wShort.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary wShortCp = new COSDictionary();
        wShortCp.setItem(n("alpha"), d1Proc(600));
        wShort.setItem(n("CharProcs"), wShortCp);
        wShort.setItem(COSName.FIRST_CHAR, i(65));
        wShort.setItem(COSName.LAST_CHAR, i(70));
        wShort.setItem(COSName.WIDTHS, arr(fl(610)));
        emit("w_short_array", wShort, 67);

        // Code below FirstChar -> getWidthFromFont (no descriptor).
        COSDictionary wBelow = type3();
        wBelow.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary wBelowCp = new COSDictionary();
        wBelowCp.setItem(n("alpha"), d1Proc(600));
        wBelow.setItem(n("CharProcs"), wBelowCp);
        wBelow.setItem(COSName.FIRST_CHAR, i(70));
        wBelow.setItem(COSName.LAST_CHAR, i(80));
        wBelow.setItem(COSName.WIDTHS, arr(fl(610)));
        emit("w_code_below", wBelow, 65);

        // No /Widths at all -> getWidthFromFont reads d1 wx.
        COSDictionary wNone = type3();
        wNone.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary wNoneCp = new COSDictionary();
        wNoneCp.setItem(n("alpha"), d1Proc(600));
        wNone.setItem(n("CharProcs"), wNoneCp);
        emit("w_no_widths", wNone, 65);

        // No /Widths, garbage proc -> width 0.
        COSDictionary wGarbage = type3();
        wGarbage.setItem(COSName.ENCODING, encoding(codes, names));
        COSDictionary wGarbageCp = new COSDictionary();
        wGarbageCp.setItem(n("alpha"), garbageProc());
        wGarbage.setItem(n("CharProcs"), wGarbageCp);
        emit("w_no_widths_garbage", wGarbage, 65);
    }
}
