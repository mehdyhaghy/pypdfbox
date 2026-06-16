import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontFactory;
import org.apache.pdfbox.pdmodel.font.PDType3CharProc;
import org.apache.pdfbox.pdmodel.font.PDType3Font;
import org.apache.pdfbox.util.Matrix;
import org.apache.pdfbox.util.Vector;

/**
 * Second differential fuzz probe for {@code PDType3Font} /
 * {@code PDType3CharProc} malformed-dictionary leniency, Apache PDFBox 3.0.7
 * (wave 1553, agent A).
 *
 * <h2>What this covers that {@code Type3FontFuzzProbe} (wave 1522) does not</h2>
 * The wave-1522 fuzz probe projects {@code getFontMatrix},
 * {@code getFontBBox}, {@code getCharProcs}, {@code getWidth} and
 * {@code getCharProc(int).getWidth/getGlyphBBox}. It never exercises the
 * {@code /FontDescriptor} {@code /MissingWidth} width branch, the
 * {@code getDisplacement} / {@code getHeight} derived metrics, the
 * {@code getCharProc(String)} / {@code hasGlyph} name surface, non-numeric /
 * null {@code /Widths} entries, a {@code /Widths} that is not an array, the
 * {@code getWidthFromFont} d0 path, codes outside the byte range, or d0/d1
 * operators with the wrong operand count / a non-numeric {@code wx}.
 * This probe builds ~34 deliberately malformed / edge-case Type 3 font
 * dictionaries and projects exactly those surfaces.
 *
 * <h2>Input</h2>
 * Deterministic, seed-free, no file I/O: a fixed inline corpus of Type 3
 * {@code COSDictionary}s built identically on both sides.
 *
 * <h2>Output grammar (one line per case)</h2>
 * <pre>
 *   CASE &lt;name&gt; create=&lt;ok|ERR:X|NotType3&gt;
 *        w&lt;code&gt;=&lt;float|ERR&gt; disp&lt;code&gt;=&lt;tx,ty|ERR&gt; h&lt;code&gt;=&lt;float|ERR&gt;
 *        hgI&lt;code&gt;=&lt;true|false|ERR&gt; hgN=&lt;true|false|ERR&gt;
 *        cpN=&lt;present|null|ERR&gt; gw=&lt;float|ERR&gt; ggb=&lt;...|null|ERR&gt;
 * </pre>
 * {@code hgN} / {@code cpN} use the fixed glyph name {@code "alpha"};
 * {@code gw} / {@code ggb} project {@code getCharProc(code).getWidth()} /
 * {@code getGlyphBBox()}. Floats render via {@link #f(float)} so 600 and
 * 600.0 are byte-identical across both languages.
 */
public final class Type3FontFuzzProbe2 {

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

    /** A d1 with too few operands (4) -> getGlyphBBox null. */
    static COSStream d1Short() {
        return stream("600 0 0 0 d1\n");
    }

    /** A d1 with too many operands (7) -> getGlyphBBox null. */
    static COSStream d1Long() {
        return stream("600 0 0 0 500 700 9 d1\n");
    }

    /** A d1 whose wx is non-numeric -> width path lenient. */
    static COSStream d1BadWx() {
        return stream("/X 0 0 0 500 700 d1\n");
    }

    static COSStream emptyProc() {
        return stream("");
    }

    // ---------- font-dict builder ----------

    static COSDictionary type3() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        d.setItem(COSName.SUBTYPE, n("Type3"));
        return d;
    }

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

    /** A minimal /FontDescriptor carrying /MissingWidth. */
    static COSDictionary descriptor(double missingWidth) {
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, n("FontDescriptor"));
        fd.setItem(n("FontName"), n("T3Probe"));
        fd.setItem(n("MissingWidth"), fl(missingWidth));
        return fd;
    }

    // ---------- projection ----------

    static String widthStr(PDType3Font font, int code) {
        try {
            return f(font.getWidth(code));
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String dispStr(PDType3Font font, int code) {
        try {
            Vector v = font.getDisplacement(code);
            return f(v.getX()) + "," + f(v.getY());
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String heightStr(PDType3Font font, int code) {
        try {
            return f(font.getHeight(code));
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String hasGlyphNameStr(PDType3Font font, String name) {
        try {
            return Boolean.toString(font.hasGlyph(name));
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String glyphWidthStr(PDType3Font font, int code) {
        try {
            PDType3CharProc cp = font.getCharProc(code);
            if (cp == null) {
                return "null";
            }
            return f(cp.getWidth());
        } catch (Throwable t) {
            return "ERR";
        }
    }

    static String glyphBBoxStr(PDType3Font font, int code) {
        try {
            PDType3CharProc cp = font.getCharProc(code);
            if (cp == null) {
                return "null";
            }
            PDRectangle r = cp.getGlyphBBox();
            if (r == null) {
                return "null";
            }
            return f(r.getLowerLeftX()) + "," + f(r.getLowerLeftY()) + ","
                    + f(r.getUpperRightX()) + "," + f(r.getUpperRightY());
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
          .append(" w").append(code).append('=').append(widthStr(t3, code))
          .append(" disp").append(code).append('=').append(dispStr(t3, code))
          .append(" h").append(code).append('=').append(heightStr(t3, code))
          .append(" hgN=").append(hasGlyphNameStr(t3, "alpha"))
          .append(" gw=").append(glyphWidthStr(t3, code))
          .append(" ggb=").append(glyphBBoxStr(t3, code));
        out.println(sb.toString());
    }

    /** Build a font with an "alpha" glyph at code 65 plus the given proc. */
    static COSDictionary withAlpha(COSStream proc) {
        COSDictionary d = type3();
        d.setItem(COSName.ENCODING,
                encoding(new int[]{65}, new String[]{"alpha"}));
        COSDictionary cp = new COSDictionary();
        cp.setItem(n("alpha"), proc);
        d.setItem(n("CharProcs"), cp);
        return d;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ===== /MissingWidth descriptor branch =====
        // Code out of /Widths window, descriptor present -> MissingWidth.
        COSDictionary mwOut = withAlpha(d1Proc(600));
        mwOut.setItem(COSName.FIRST_CHAR, i(70));
        mwOut.setItem(COSName.LAST_CHAR, i(80));
        mwOut.setItem(COSName.WIDTHS, arr(fl(610)));
        mwOut.setItem(n("FontDescriptor"), descriptor(250));
        emit("mw_out_of_range", mwOut, 65);

        // No /Widths at all + descriptor -> still in-window? no window so
        // first<=code<=last is false (defaults 0/0); MissingWidth wins.
        COSDictionary mwNoWidths = withAlpha(d1Proc(600));
        mwNoWidths.setItem(n("FontDescriptor"), descriptor(333));
        emit("mw_no_widths_desc", mwNoWidths, 65);

        // Descriptor present but MissingWidth absent -> default 0.
        COSDictionary mwDefault = withAlpha(d1Proc(600));
        COSDictionary fdNoMw = new COSDictionary();
        fdNoMw.setItem(COSName.TYPE, n("FontDescriptor"));
        fdNoMw.setItem(n("FontName"), n("T3Probe"));
        mwDefault.setItem(n("FontDescriptor"), fdNoMw);
        emit("mw_default_zero", mwDefault, 65);

        // ===== /Widths edge entries =====
        // /Widths entry is null at the in-window slot.
        COSDictionary wNullEntry = withAlpha(d1Proc(600));
        wNullEntry.setItem(COSName.FIRST_CHAR, i(65));
        wNullEntry.setItem(COSName.LAST_CHAR, i(65));
        wNullEntry.setItem(COSName.WIDTHS, arr(COSNull.NULL));
        emit("w_null_entry", wNullEntry, 65);

        // /Widths entry is non-numeric (a name) at the in-window slot.
        COSDictionary wNameEntry = withAlpha(d1Proc(600));
        wNameEntry.setItem(COSName.FIRST_CHAR, i(65));
        wNameEntry.setItem(COSName.LAST_CHAR, i(65));
        wNameEntry.setItem(COSName.WIDTHS, arr(n("X")));
        emit("w_name_entry", wNameEntry, 65);

        // /Widths is not an array (it's a name).
        COSDictionary wNotArray = withAlpha(d1Proc(600));
        wNotArray.setItem(COSName.FIRST_CHAR, i(65));
        wNotArray.setItem(COSName.LAST_CHAR, i(65));
        wNotArray.setItem(COSName.WIDTHS, n("Nope"));
        emit("w_not_array", wNotArray, 65);

        // /Widths integer entry (not float).
        COSDictionary wIntEntry = withAlpha(d1Proc(600));
        wIntEntry.setItem(COSName.FIRST_CHAR, i(65));
        wIntEntry.setItem(COSName.LAST_CHAR, i(65));
        wIntEntry.setItem(COSName.WIDTHS, arr(i(555)));
        emit("w_int_entry", wIntEntry, 65);

        // ===== getWidthFromFont d0 path (no /Widths) =====
        COSDictionary fontD0 = withAlpha(d0Proc(444));
        emit("widthfromfont_d0", fontD0, 65);

        // getWidthFromFont with empty proc (no /Widths) -> 0.
        COSDictionary fontEmpty = withAlpha(emptyProc());
        emit("widthfromfont_empty", fontEmpty, 65);

        // ===== getDisplacement over various matrices =====
        // Default matrix -> disp = (width/1000, 0).
        COSDictionary dispDefault = withAlpha(d1Proc(600));
        emit("disp_default_matrix", dispDefault, 65);

        // Custom matrix 0.002 scale -> disp = (width*0.002, 0).
        COSDictionary dispCustom = withAlpha(d1Proc(600));
        dispCustom.setItem(n("FontMatrix"),
                arr(fl(0.002), fl(0), fl(0), fl(0.002), fl(0), fl(0)));
        emit("disp_scaled_matrix", dispCustom, 65);

        // Matrix with translation folded in (e,f != 0) -> disp picks it up.
        COSDictionary dispTrans = withAlpha(d1Proc(600));
        dispTrans.setItem(n("FontMatrix"),
                arr(fl(0.001), fl(0), fl(0), fl(0.001), fl(5), fl(7)));
        emit("disp_translate_matrix", dispTrans, 65);

        // Singular matrix (all zeros) -> disp = (0,0).
        COSDictionary dispZero = withAlpha(d1Proc(600));
        dispZero.setItem(n("FontMatrix"),
                arr(fl(0), fl(0), fl(0), fl(0), fl(0), fl(0)));
        emit("disp_singular_matrix", dispZero, 65);

        // Shear matrix (b != 0) -> disp.ty = width*b.
        COSDictionary dispShear = withAlpha(d1Proc(600));
        dispShear.setItem(n("FontMatrix"),
                arr(fl(0.001), fl(0.0005), fl(0), fl(0.001), fl(0), fl(0)));
        emit("disp_shear_matrix", dispShear, 65);

        // ===== getHeight via descriptor =====
        // Descriptor with /FontBBox -> height = bbox.height/2.
        COSDictionary hBBox = withAlpha(d1Proc(600));
        COSDictionary fdBBox = new COSDictionary();
        fdBBox.setItem(COSName.TYPE, n("FontDescriptor"));
        fdBBox.setItem(n("FontName"), n("T3Probe"));
        fdBBox.setItem(n("FontBBox"), arr(i(0), i(0), i(750), i(1000)));
        hBBox.setItem(n("FontDescriptor"), fdBBox);
        emit("h_descriptor_bbox", hBBox, 65);

        // Descriptor with /CapHeight (no bbox) -> height = CapHeight.
        COSDictionary hCap = withAlpha(d1Proc(600));
        COSDictionary fdCap = new COSDictionary();
        fdCap.setItem(COSName.TYPE, n("FontDescriptor"));
        fdCap.setItem(n("FontName"), n("T3Probe"));
        fdCap.setItem(n("CapHeight"), fl(683));
        hCap.setItem(n("FontDescriptor"), fdCap);
        emit("h_descriptor_capheight", hCap, 65);

        // No descriptor -> height 0.
        emit("h_no_descriptor", withAlpha(d1Proc(600)), 65);

        // ===== hasGlyph / getCharProc(name) =====
        // alpha glyph present at code 65 -> hgI65 true, hgN true, cpN present.
        emit("glyph_present", withAlpha(d1Proc(600)), 65);

        // Encoding maps 65 -> .notdef -> hasGlyph(int) false even with proc.
        COSDictionary gNotdef = type3();
        gNotdef.setItem(COSName.ENCODING,
                encoding(new int[]{65}, new String[]{".notdef"}));
        COSDictionary gNotdefCp = new COSDictionary();
        gNotdefCp.setItem(n(".notdef"), d1Proc(600));
        gNotdefCp.setItem(n("alpha"), d1Proc(700));
        gNotdef.setItem(n("CharProcs"), gNotdefCp);
        emit("glyph_notdef_code", gNotdef, 65);

        // Name present in CharProcs but code not mapped -> hgN true, hgI false.
        COSDictionary gNameOnly = type3();
        gNameOnly.setItem(COSName.ENCODING,
                encoding(new int[]{66}, new String[]{"beta"}));
        COSDictionary gNameOnlyCp = new COSDictionary();
        gNameOnlyCp.setItem(n("alpha"), d1Proc(600));
        gNameOnly.setItem(n("CharProcs"), gNameOnlyCp);
        emit("glyph_name_only", gNameOnly, 65);

        // getCharProc(name) where entry is a dict, not a stream -> null.
        COSDictionary gEntryDict = type3();
        gEntryDict.setItem(COSName.ENCODING,
                encoding(new int[]{65}, new String[]{"alpha"}));
        COSDictionary gEntryDictCp = new COSDictionary();
        gEntryDictCp.setItem(n("alpha"), new COSDictionary());
        gEntryDict.setItem(n("CharProcs"), gEntryDictCp);
        emit("glyph_entry_dict", gEntryDict, 65);

        // ===== d0/d1 operand-count + non-numeric wx =====
        // d1 with too few operands -> glyph bbox null, width still 600.
        emit("d1_short_operands", withAlpha(d1Short()), 65);

        // d1 with too many operands -> glyph bbox null, width still 600.
        emit("d1_long_operands", withAlpha(d1Long()), 65);

        // d1 with non-numeric wx -> lenient width path.
        emit("d1_bad_wx", withAlpha(d1BadWx()), 65);

        // d0 proc -> glyph bbox null (d0 has no bbox), width 444.
        emit("d0_no_bbox", withAlpha(d0Proc(444)), 65);

        // ===== out-of-byte-range codes =====
        // code 256 (beyond a byte) -> encoding has no name -> null/0.
        COSDictionary oob = withAlpha(d1Proc(600));
        emit("code_256", oob, 256);

        // code -1 -> encoding has no name -> null/0.
        COSDictionary neg = withAlpha(d1Proc(600));
        emit("code_neg1", neg, -1);

        // ===== /FontMatrix singular + width interaction (full surface) =====
        // 6 ints matrix identity -> disp = (width, 0) (no 0.001 scaling).
        COSDictionary fmIdentity = withAlpha(d1Proc(600));
        fmIdentity.setItem(n("FontMatrix"),
                arr(i(1), i(0), i(0), i(1), i(0), i(0)));
        emit("fm_identity_disp", fmIdentity, 65);

        // Non-numeric matrix entry -> falls back to default -> disp scaled.
        COSDictionary fmBad = withAlpha(d1Proc(600));
        fmBad.setItem(n("FontMatrix"),
                arr(fl(0.002), n("X"), fl(0), fl(0.002), fl(0), fl(0)));
        emit("fm_bad_disp", fmBad, 65);
    }
}
