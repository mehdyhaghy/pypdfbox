import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontFactory;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Live oracle probe for PDFontFactory.createFont subtype dispatch.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> FontFactoryProbe
 *
 * Builds one font COSDictionary per dispatch case in code (no file I/O),
 * calls PDFontFactory.createFont(dict) on each, and emits a canonical
 * TAB-delimited line per case:
 *
 *   CASE <id> <result>
 *
 * where <result> is either the resulting PDFont subclass simple name
 * (plus, for a Type0, the descendant PDCIDFont subclass simple name as
 * "PDType0Font/PDCIDFontTypeN"), or "RAISE:<ExceptionSimpleName>" when
 * createFont throws, or "NULL" when it returns null.
 *
 * The Python side reproduces each dict with pypdfbox COS objects and
 * asserts pypdfbox dispatches to the same class / raises / returns None.
 */
public final class FontFactoryProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        emit(out, "type1_standard14", type1Standard14());
        emit(out, "type1_embedded_fontfile", type1EmbeddedFontFile());
        emit(out, "type1c_fontfile3_type1c", type1cFontFile3Type1c());
        emit(out, "type1_fontfile3_no_subtype", type1FontFile3NoSubtype());
        emit(out, "type1_fontfile3_opentype", type1FontFile3OpenType());
        emit(out, "mmtype1", mmType1());
        emit(out, "mmtype1_fontfile3", mmType1FontFile3());
        emit(out, "truetype_fontfile2", trueTypeFontFile2());
        emit(out, "type0_cidfonttype0", type0CidFontType0());
        emit(out, "type0_cidfonttype2", type0CidFontType2());
        emit(out, "type3", type3());
        emit(out, "missing_subtype", missingSubtype());
        emit(out, "unknown_subtype", unknownSubtype());
        emit(out, "bare_cidfonttype0", bareCidFontType0());
        emit(out, "bare_cidfonttype2", bareCidFontType2());
    }

    private static void emit(PrintStream out, String id, COSDictionary dict) {
        String result;
        try {
            PDFont font = PDFontFactory.createFont(dict);
            if (font == null) {
                result = "NULL";
            } else if (font instanceof PDType0Font) {
                PDType0Font t0 = (PDType0Font) font;
                String desc = t0.getDescendantFont() == null
                        ? "null"
                        : t0.getDescendantFont().getClass().getSimpleName();
                result = font.getClass().getSimpleName() + "/" + desc;
            } else {
                result = font.getClass().getSimpleName();
            }
        } catch (Exception e) {
            result = "RAISE:" + e.getClass().getSimpleName();
        }
        out.println("CASE\t" + id + "\t" + result);
    }

    // ---------- font dictionary builders ----------

    private static COSStream newStream() {
        // A standalone COSStream not attached to a document; createFont only
        // inspects keys/containsKey, never decodes the program bytes.
        return new COSStream();
    }

    private static COSDictionary fontDict(String subtype) {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        d.setItem(COSName.SUBTYPE, COSName.getPDFName(subtype));
        return d;
    }

    private static COSDictionary type1Standard14() {
        COSDictionary d = fontDict("Type1");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("Helvetica"));
        return d;
    }

    private static COSDictionary type1EmbeddedFontFile() {
        COSDictionary d = fontDict("Type1");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("ABCDEF+CustomType1"));
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        fd.setItem(COSName.getPDFName("FontFile"), newStream());
        d.setItem(COSName.FONT_DESC, fd);
        return d;
    }

    private static COSDictionary type1cFontFile3Type1c() {
        COSDictionary d = fontDict("Type1");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("ABCDEF+CFFType1"));
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        COSStream ff3 = newStream();
        ff3.setItem(COSName.SUBTYPE, COSName.getPDFName("Type1C"));
        fd.setItem(COSName.FONT_FILE3, ff3);
        d.setItem(COSName.FONT_DESC, fd);
        return d;
    }

    private static COSDictionary type1FontFile3NoSubtype() {
        COSDictionary d = fontDict("Type1");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("ABCDEF+CFFNoSub"));
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        // FontFile3 present but with NO /Subtype.
        fd.setItem(COSName.FONT_FILE3, newStream());
        d.setItem(COSName.FONT_DESC, fd);
        return d;
    }

    private static COSDictionary type1FontFile3OpenType() {
        COSDictionary d = fontDict("Type1");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("ABCDEF+CFFOtto"));
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        COSStream ff3 = newStream();
        ff3.setItem(COSName.SUBTYPE, COSName.getPDFName("OpenType"));
        fd.setItem(COSName.FONT_FILE3, ff3);
        d.setItem(COSName.FONT_DESC, fd);
        return d;
    }

    private static COSDictionary mmType1() {
        COSDictionary d = fontDict("MMType1");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("MMType1Font"));
        return d;
    }

    private static COSDictionary mmType1FontFile3() {
        COSDictionary d = fontDict("MMType1");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("ABCDEF+MMCFF"));
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        COSStream ff3 = newStream();
        ff3.setItem(COSName.SUBTYPE, COSName.getPDFName("Type1C"));
        fd.setItem(COSName.FONT_FILE3, ff3);
        d.setItem(COSName.FONT_DESC, fd);
        return d;
    }

    private static COSDictionary trueTypeFontFile2() {
        COSDictionary d = fontDict("TrueType");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("ABCDEF+CustomTTF"));
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        fd.setItem(COSName.FONT_FILE2, newStream());
        d.setItem(COSName.FONT_DESC, fd);
        return d;
    }

    private static COSDictionary type0(String descSubtype) {
        COSDictionary d = fontDict("Type0");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("ABCDEF+Composite"));
        d.setItem(COSName.ENCODING, COSName.getPDFName("Identity-H"));
        COSDictionary desc = new COSDictionary();
        desc.setItem(COSName.TYPE, COSName.FONT);
        desc.setItem(COSName.SUBTYPE, COSName.getPDFName(descSubtype));
        desc.setItem(COSName.BASE_FONT, COSName.getPDFName("ABCDEF+Composite"));
        COSDictionary cidsysinfo = new COSDictionary();
        cidsysinfo.setItem(COSName.getPDFName("Registry"),
                new org.apache.pdfbox.cos.COSString("Adobe"));
        cidsysinfo.setItem(COSName.getPDFName("Ordering"),
                new org.apache.pdfbox.cos.COSString("Identity"));
        cidsysinfo.setInt(COSName.getPDFName("Supplement"), 0);
        desc.setItem(COSName.CIDSYSTEMINFO, cidsysinfo);
        COSArray arr = new COSArray();
        arr.add(desc);
        d.setItem(COSName.DESCENDANT_FONTS, arr);
        return d;
    }

    private static COSDictionary type0CidFontType0() {
        return type0("CIDFontType0");
    }

    private static COSDictionary type0CidFontType2() {
        return type0("CIDFontType2");
    }

    private static COSDictionary type3() {
        COSDictionary d = fontDict("Type3");
        d.setItem(COSName.getPDFName("FontBBox"), new COSArray());
        COSArray matrix = new COSArray();
        matrix.add(new org.apache.pdfbox.cos.COSFloat(0.001f));
        matrix.add(new org.apache.pdfbox.cos.COSFloat(0f));
        matrix.add(new org.apache.pdfbox.cos.COSFloat(0f));
        matrix.add(new org.apache.pdfbox.cos.COSFloat(0.001f));
        matrix.add(new org.apache.pdfbox.cos.COSFloat(0f));
        matrix.add(new org.apache.pdfbox.cos.COSFloat(0f));
        d.setItem(COSName.getPDFName("FontMatrix"), matrix);
        d.setItem(COSName.getPDFName("CharProcs"), new COSDictionary());
        return d;
    }

    private static COSDictionary missingSubtype() {
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.TYPE, COSName.FONT);
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("Helvetica"));
        // No /Subtype.
        return d;
    }

    private static COSDictionary unknownSubtype() {
        COSDictionary d = fontDict("BogusSubtype");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("Helvetica"));
        return d;
    }

    private static COSDictionary bareCidFontType0() {
        COSDictionary d = fontDict("CIDFontType0");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("ABCDEF+BareCID0"));
        return d;
    }

    private static COSDictionary bareCidFontType2() {
        COSDictionary d = fontDict("CIDFontType2");
        d.setItem(COSName.BASE_FONT, COSName.getPDFName("ABCDEF+BareCID2"));
        return d;
    }
}
