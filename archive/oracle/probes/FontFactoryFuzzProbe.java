import java.io.OutputStream;
import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontFactory;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Differential fuzz probe for {@code PDFontFactory.createFont(COSDictionary)}
 * font-dictionary construction leniency, Apache PDFBox 3.0.7 (wave 1510, agent
 * E).
 *
 * Complements the existing {@code FontFactoryProbe} (which pins only the
 * subtype-dispatch class for well-formed dicts). This probe drives the deeper
 * construction-leniency surface — malformed / missing / mistyped font-dict
 * keys — and reports, per case, the created class, the font name, the
 * {@code isEmbedded} / {@code isDamaged} flags, and two advance-width samples
 * ({@code getWidth(65)} for 'A' and {@code getWidth(32)} for the space slot,
 * both dictionary / AFM driven so they don't depend on encode()), or the
 * exception contract when construction or a sample throws.
 *
 * Deterministic and seed-free: the corpus is a fixed inline list (no
 * Date.now / unseeded random). The pypdfbox sibling
 * (tests/pdmodel/font/oracle/test_font_factory_fuzz_wave1510.py) rebuilds the
 * identical COS dicts and asserts each line matches; intentional pypdfbox
 * robustness divergences are pinned both-sides there with a CHANGES.md
 * citation.
 *
 * Line grammar (one per case):
 *   CASE &lt;name&gt; create=&lt;ERR | class=&lt;X&gt; name=&lt;n&gt; emb=&lt;0|1&gt; dmg=&lt;0|1&gt; wA=&lt;w|ERR&gt; wSp=&lt;w|ERR&gt;&gt;
 * "create=ERR" means createFont threw. For a Type0 the class token is
 * "PDType0Font/&lt;descendantSimpleName-or-null&gt;". A width token is the
 * %.3f advance or "ERR" if that getWidth call threw.
 */
public final class FontFactoryFuzzProbe {

    static PrintStream out;

    static String fmt(float v) {
        return String.format(Locale.ROOT, "%.3f", v);
    }

    static COSName n(String s) {
        return COSName.getPDFName(s);
    }

    static COSArray ints(int... vals) {
        COSArray a = new COSArray();
        for (int v : vals) {
            a.add(COSInteger.get(v));
        }
        return a;
    }

    static COSStream newStream() {
        // Standalone stream; createFont inspects keys / parses the embedded
        // program lazily. Returned so /FontFile* presence is testable.
        return new COSStream();
    }

    static COSStream garbageStream() throws Exception {
        COSStream s = new COSStream();
        OutputStream os = s.createOutputStream();
        os.write("not a real font program".getBytes("US-ASCII"));
        os.close();
        return s;
    }

    static void emit(String name, COSDictionary dict) {
        StringBuilder sb = new StringBuilder("CASE ").append(name).append(' ');
        PDFont font;
        try {
            font = PDFontFactory.createFont(dict);
        } catch (Throwable t) {
            out.println(sb.append("create=ERR").toString());
            return;
        }
        if (font == null) {
            out.println(sb.append("create=NULL").toString());
            return;
        }
        String cls;
        if (font instanceof PDType0Font) {
            PDType0Font t0 = (PDType0Font) font;
            String desc;
            try {
                desc = t0.getDescendantFont() == null
                        ? "null"
                        : t0.getDescendantFont().getClass().getSimpleName();
            } catch (Throwable t) {
                desc = "ERR";
            }
            cls = font.getClass().getSimpleName() + "/" + desc;
        } else {
            cls = font.getClass().getSimpleName();
        }
        String fname;
        try {
            fname = font.getName() == null ? "null" : font.getName();
        } catch (Throwable t) {
            fname = "ERR";
        }
        String emb;
        try {
            emb = font.isEmbedded() ? "1" : "0";
        } catch (Throwable t) {
            emb = "ERR";
        }
        String dmg;
        try {
            dmg = font.isDamaged() ? "1" : "0";
        } catch (Throwable t) {
            dmg = "ERR";
        }
        String wA;
        try {
            wA = fmt(font.getWidth(65));
        } catch (Throwable t) {
            wA = "ERR";
        }
        String wSp;
        try {
            wSp = fmt(font.getWidth(32));
        } catch (Throwable t) {
            wSp = "ERR";
        }
        sb.append("create=ok class=").append(cls)
          .append(" name=").append(fname)
          .append(" emb=").append(emb)
          .append(" dmg=").append(dmg)
          .append(" wA=").append(wA)
          .append(" wSp=").append(wSp);
        out.println(sb.toString());
    }

    // ---------- dictionary builders ----------

    static COSDictionary font(String subtype, String baseFont) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        if (subtype != null) {
            d.setItem(COSName.SUBTYPE, n(subtype));
        }
        if (baseFont != null) {
            d.setItem(COSName.BASE_FONT, n(baseFont));
        }
        return d;
    }

    static COSDictionary descriptor(String fontName) {
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, n("FontDescriptor"));
        if (fontName != null) {
            fd.setItem(COSName.FONT_NAME, n(fontName));
        }
        fd.setInt(COSName.FLAGS, 32);
        return fd;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ===== missing / unknown / mistyped /Subtype =====
        COSDictionary noSub = new COSDictionary();
        noSub.setItem(COSName.TYPE, COSName.FONT);
        noSub.setItem(COSName.BASE_FONT, n("Helvetica"));
        emit("missing_subtype", noSub);

        emit("unknown_subtype", font("Frobnicate", "Helvetica"));

        // /Subtype as a COSString instead of a COSName: getCOSName returns
        // null, so it's treated as a missing subtype -> PDType1Font fallback.
        COSDictionary subStr = new COSDictionary();
        subStr.setItem(COSName.TYPE, COSName.FONT);
        subStr.setItem(COSName.SUBTYPE, new COSString("Type1"));
        subStr.setItem(COSName.BASE_FONT, n("Helvetica"));
        emit("subtype_as_string", subStr);

        // No /Type key at all (just /Subtype): factory logs but proceeds.
        COSDictionary noType = new COSDictionary();
        noType.setItem(COSName.SUBTYPE, n("Type1"));
        noType.setItem(COSName.BASE_FONT, n("Helvetica"));
        emit("missing_type_key", noType);

        // wrong /Type (not /Font): factory logs error but still dispatches.
        COSDictionary wrongType = font("Type1", "Helvetica");
        wrongType.setItem(COSName.TYPE, n("Catalog"));
        emit("wrong_type_key", wrongType);

        // ===== Type1 — Standard 14 / missing BaseFont / widths =====
        emit("type1_std14_helvetica", font("Type1", "Helvetica"));
        emit("type1_std14_times", font("Type1", "Times-Roman"));
        emit("type1_missing_basefont", font("Type1", null));

        // BaseFont as a string instead of a name.
        COSDictionary bfStr = new COSDictionary();
        bfStr.setItem(COSName.TYPE, COSName.FONT);
        bfStr.setItem(COSName.SUBTYPE, n("Type1"));
        bfStr.setItem(COSName.BASE_FONT, new COSString("Helvetica"));
        emit("type1_basefont_as_string", bfStr);

        // Non-std14 Type1, no widths, no descriptor: width falls to 0 / AFM.
        emit("type1_nonstd_no_widths", font("Type1", "MyCustomFont"));

        // Type1 with explicit /Widths + /FirstChar/LastChar.
        COSDictionary t1w = font("Type1", "MyCustomFont");
        t1w.setInt(COSName.FIRST_CHAR, 32);
        t1w.setInt(COSName.LAST_CHAR, 65);
        COSArray w = new COSArray();
        for (int i = 32; i <= 65; i++) {
            w.add(COSInteger.get(500 + i));
        }
        t1w.setItem(COSName.WIDTHS, w);
        emit("type1_widths_full", t1w);

        // /Widths present but /FirstChar missing (defaults to -1).
        COSDictionary t1wNoFirst = font("Type1", "MyCustomFont");
        t1wNoFirst.setItem(COSName.WIDTHS, ints(600, 601, 602));
        t1wNoFirst.setInt(COSName.LAST_CHAR, 34);
        emit("type1_widths_no_firstchar", t1wNoFirst);

        // /Widths count shorter than FirstChar..LastChar span.
        COSDictionary t1wShort = font("Type1", "MyCustomFont");
        t1wShort.setInt(COSName.FIRST_CHAR, 32);
        t1wShort.setInt(COSName.LAST_CHAR, 90);
        t1wShort.setItem(COSName.WIDTHS, ints(700, 701, 702));
        emit("type1_widths_short", t1wShort);

        // /Widths count longer than the span.
        COSDictionary t1wLong = font("Type1", "MyCustomFont");
        t1wLong.setInt(COSName.FIRST_CHAR, 65);
        t1wLong.setInt(COSName.LAST_CHAR, 66);
        COSArray wl = new COSArray();
        for (int i = 0; i < 10; i++) {
            wl.add(COSInteger.get(800 + i));
        }
        t1wLong.setItem(COSName.WIDTHS, wl);
        emit("type1_widths_long", t1wLong);

        // /Widths with non-numeric entries (a name + a null hole).
        COSDictionary t1wBad = font("Type1", "MyCustomFont");
        t1wBad.setInt(COSName.FIRST_CHAR, 65);
        t1wBad.setInt(COSName.LAST_CHAR, 68);
        COSArray wb = new COSArray();
        wb.add(COSInteger.get(900));        // 65 -> 900
        wb.add(n("Garbage"));               // 66 -> non-numeric -> 0
        wb.add(org.apache.pdfbox.cos.COSNull.NULL); // 67 -> null -> 0
        wb.add(new COSFloat(950.5f));       // 68 -> 950.5
        t1wBad.setItem(COSName.WIDTHS, wb);
        emit("type1_widths_nonnumeric", t1wBad);

        // /Widths as a dictionary instead of an array.
        COSDictionary t1wDict = font("Type1", "MyCustomFont");
        t1wDict.setInt(COSName.FIRST_CHAR, 65);
        t1wDict.setInt(COSName.LAST_CHAR, 66);
        COSDictionary widthsDict = new COSDictionary();
        widthsDict.setInt(n("0"), 700);
        t1wDict.setItem(COSName.WIDTHS, widthsDict);
        emit("type1_widths_as_dict", t1wDict);

        // /MissingWidth via descriptor, no /Widths -> getWidth uses it.
        COSDictionary t1mw = font("Type1", "MyCustomFont");
        COSDictionary fdMw = descriptor("MyCustomFont");
        fdMw.setInt(COSName.MISSING_WIDTH, 333);
        t1mw.setItem(COSName.FONT_DESC, fdMw);
        emit("type1_missingwidth_only", t1mw);

        // ===== /FontDescriptor type / FontFile corners =====
        // /FontDescriptor as an array instead of a dictionary.
        COSDictionary t1fdArr = font("Type1", "MyCustomFont");
        t1fdArr.setItem(COSName.FONT_DESC, ints(1, 2, 3));
        emit("type1_fontdescriptor_as_array", t1fdArr);

        // /FontDescriptor as a name.
        COSDictionary t1fdName = font("Type1", "MyCustomFont");
        t1fdName.setItem(COSName.FONT_DESC, n("Bogus"));
        emit("type1_fontdescriptor_as_name", t1fdName);

        // /FontFile pointing at a garbage stream (embedded Type1, unparseable).
        COSDictionary t1ff = font("Type1", "MyCustomFont");
        COSDictionary fdFf = descriptor("MyCustomFont");
        fdFf.setItem(COSName.FONT_FILE, garbageStream());
        t1ff.setItem(COSName.FONT_DESC, fdFf);
        emit("type1_fontfile_garbage", t1ff);

        // /FontFile3 garbage on a /Type1 -> routes to PDType1CFont, CFF parse
        // of garbage -> damaged.
        COSDictionary t1ff3 = font("Type1", "MyCustomFont");
        COSDictionary fdFf3 = descriptor("MyCustomFont");
        fdFf3.setItem(COSName.FONT_FILE3, garbageStream());
        t1ff3.setItem(COSName.FONT_DESC, fdFf3);
        emit("type1c_fontfile3_garbage", t1ff3);

        // /FontFile as a name (not a stream): not embedded.
        COSDictionary t1ffName = font("Type1", "MyCustomFont");
        COSDictionary fdFfName = descriptor("MyCustomFont");
        fdFfName.setItem(COSName.FONT_FILE, n("nope"));
        t1ffName.setItem(COSName.FONT_DESC, fdFfName);
        emit("type1_fontfile_as_name", t1ffName);

        // ===== MMType1 =====
        emit("mmtype1_no_fontfile", font("MMType1", "MyMMFont"));
        COSDictionary mmFf3 = font("MMType1", "MyMMFont");
        COSDictionary fdMm = descriptor("MyMMFont");
        fdMm.setItem(COSName.FONT_FILE3, garbageStream());
        mmFf3.setItem(COSName.FONT_DESC, fdMm);
        emit("mmtype1_fontfile3_garbage", mmFf3);

        // ===== TrueType — missing widths, garbage FontFile2 =====
        emit("truetype_no_widths", font("TrueType", "Arial"));
        COSDictionary ttW = font("TrueType", "Arial");
        ttW.setInt(COSName.FIRST_CHAR, 65);
        ttW.setInt(COSName.LAST_CHAR, 66);
        ttW.setItem(COSName.WIDTHS, ints(456, 457));
        emit("truetype_widths", ttW);

        COSDictionary ttFf2 = font("TrueType", "Arial");
        COSDictionary fdTt = descriptor("Arial");
        fdTt.setItem(COSName.FONT_FILE2, garbageStream());
        ttFf2.setItem(COSName.FONT_DESC, fdTt);
        emit("truetype_fontfile2_garbage", ttFf2);

        // ===== Type3 — missing CharProcs / FontMatrix / Resources =====
        emit("type3_bare", font("Type3", null));

        COSDictionary t3w = font("Type3", null);
        t3w.setInt(COSName.FIRST_CHAR, 65);
        t3w.setInt(COSName.LAST_CHAR, 66);
        t3w.setItem(COSName.WIDTHS, ints(11, 12));
        emit("type3_widths_no_matrix", t3w);

        COSDictionary t3fm = font("Type3", null);
        t3fm.setItem(COSName.FONT_MATRIX, new COSArray());
        t3fm.setInt(COSName.FIRST_CHAR, 65);
        t3fm.setInt(COSName.LAST_CHAR, 65);
        t3fm.setItem(COSName.WIDTHS, ints(20));
        emit("type3_empty_fontmatrix", t3fm);

        COSDictionary t3cp = font("Type3", null);
        t3cp.setItem(n("CharProcs"), new COSDictionary());
        t3cp.setItem(COSName.RESOURCES, new COSDictionary());
        t3cp.setItem(COSName.FONT_MATRIX, floatsArr(0.001, 0, 0, 0.001, 0, 0));
        emit("type3_full_empty_charprocs", t3cp);

        // ===== Type0 — descendant corners =====
        emit("type0_missing_descendants", type0(null, null, "Identity-H"));
        emit("type0_empty_descendants", type0(new COSArray(), null, "Identity-H"));

        // proper CIDFontType2 descendant.
        emit("type0_cidtype2", type0(descArray("CIDFontType2"), null, "Identity-H"));
        emit("type0_cidtype0", type0(descArray("CIDFontType0"), null, "Identity-H"));

        // descendant missing /CIDSystemInfo.
        COSDictionary descNoCsi = new COSDictionary();
        descNoCsi.setItem(COSName.TYPE, COSName.FONT);
        descNoCsi.setItem(COSName.SUBTYPE, n("CIDFontType2"));
        descNoCsi.setItem(COSName.BASE_FONT, n("Arial"));
        COSArray descArrNoCsi = new COSArray();
        descArrNoCsi.add(descNoCsi);
        emit("type0_descendant_no_cidsysteminfo",
             type0(descArrNoCsi, null, "Identity-H"));

        // Type0 missing /Encoding.
        emit("type0_missing_encoding", type0(descArray("CIDFontType2"), null, null));

        // Type0 with two descendants (oversized array — upstream uses [0]).
        COSArray twoDesc = descArray("CIDFontType2");
        twoDesc.add(cidFont("CIDFontType0"));
        emit("type0_two_descendants", type0(twoDesc, null, "Identity-H"));

        // Type0 /DescendantFonts as a dictionary, not an array.
        COSDictionary t0DescDict = type0(null, null, "Identity-H");
        t0DescDict.setItem(n("DescendantFonts"), cidFont("CIDFontType2"));
        emit("type0_descendants_as_dict", t0DescDict);

        // Type0 descendant /Subtype mismatch vs FontFile (no font program):
        // fixType0Subtype only repairs when a program is present.
        emit("type0_cidtype2_no_program",
             type0(descArray("CIDFontType2"), null, "Identity-V"));

        // ===== bare CID font as top-level (illegal) =====
        emit("bare_cidfonttype0", cidFontTop("CIDFontType0"));
        emit("bare_cidfonttype2", cidFontTop("CIDFontType2"));

        // ===== completely empty dict =====
        emit("empty_dict", new COSDictionary());
    }

    static COSArray floatsArr(double... vals) {
        COSArray a = new COSArray();
        for (double v : vals) {
            a.add(new COSFloat((float) v));
        }
        return a;
    }

    static COSDictionary cidFont(String subtype) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        d.setItem(COSName.SUBTYPE, n(subtype));
        d.setItem(COSName.BASE_FONT, n("Arial"));
        COSDictionary csi = new COSDictionary();
        csi.setString(n("Registry"), "Adobe");
        csi.setString(n("Ordering"), "Identity");
        csi.setInt(n("Supplement"), 0);
        d.setItem(n("CIDSystemInfo"), csi);
        return d;
    }

    static COSDictionary cidFontTop(String subtype) {
        // top-level CID font dict (illegal as a font dictionary).
        return cidFont(subtype);
    }

    static COSArray descArray(String subtype) {
        COSArray a = new COSArray();
        a.add(cidFont(subtype));
        return a;
    }

    static COSDictionary type0(COSArray descendants, COSBase ignore, String encoding) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        d.setItem(COSName.SUBTYPE, n("Type0"));
        d.setItem(COSName.BASE_FONT, n("Arial-Identity-H"));
        if (encoding != null) {
            d.setItem(COSName.ENCODING, n(encoding));
        }
        if (descendants != null) {
            d.setItem(n("DescendantFonts"), descendants);
        }
        return d;
    }
}
