import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.encoding.Encoding;

/**
 * Live oracle probe: pin Apache PDFBox's pdmodel-level {@code PDType1Font}
 * Standard-14 / AFM-backed metric surface — distinct from the fontbox-level
 * Type1Font* probes (which fingerprint PFB / charstring parsing).
 *
 * The angle here is the {@code PDType1Font} *dictionary* behaviour on
 * non-embedded fonts (no {@code /FontFile}):
 *
 *   - {@code getWidth(code)}            — full width-resolution cascade:
 *                                          /Widths window, then the Standard-14
 *                                          AFM advance (getStandard14Width),
 *                                          then getWidthFromFont.
 *   - {@code getWidthFromFont(code)}    — AFM advance / substitute .notdef 250.
 *   - {@code isStandard14()}            — name-based core detection.
 *   - {@code isEmbedded()}              — false for every probed font.
 *   - {@code getEncoding()} class       — built-in vs named vs dict /Differences.
 *   - {@code getEncoding().getName(code)} — code -> glyph-name mapping.
 *
 * Fuzz dictionaries built entirely in-Java (no fixture) so each edge is
 * deterministic:
 *
 *   1. Standard-14 names with NO /Widths, NO /Encoding (AFM width + built-in
 *      encoding path): Helvetica, Times-Roman, Symbol, ZapfDingbats,
 *      Courier-BoldOblique.
 *   2. Standard-14 Helvetica with /Widths overriding the AFM.
 *   3. Standard-14 Helvetica with /FirstChar//LastChar mismatched against the
 *      /Widths length (short array).
 *   4. Unknown base-font name (not Standard-14, not embedded, no /Widths).
 *   5. /Encoding as a name (WinAnsi / MacRoman / Standard) on Helvetica.
 *   6. /Encoding as a dict with /Differences on Helvetica.
 *   7. Missing /FontDescriptor on a Standard-14 name (still AFM-backed).
 *
 * Output (UTF-8, tab-delimited, deterministic order):
 *   FONT \t key \t isStandard14 \t isEmbedded \t encodingClass
 *   W    \t key \t code \t getWidth \t getWidthFromFont \t glyphName
 *
 * Floats "%.4f" (Locale.ROOT); pypdfbox mirrors the exact line format so a
 * divergence is a single differing line.
 */
public final class PdType1FontFuzzProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        int[] codes = {0, 32, 39, 65, 96, 97, 128, 141, 173, 200, 255};

        // 1. Standard-14, no /Widths, no /Encoding (AFM + built-in encoding).
        emit(out, "helv_bare", std14(out, "Helvetica"), codes);
        emit(out, "times_bare", std14(out, "Times-Roman"), codes);
        emit(out, "symbol_bare", std14(out, "Symbol"), codes);
        emit(out, "zapf_bare", std14(out, "ZapfDingbats"), codes);
        emit(out, "courier_bo", std14(out, "Courier-BoldOblique"), codes);

        // 2. Standard-14 Helvetica with /Widths overriding the AFM.
        emit(out, "helv_widths", helvWithWidths(65, 68,
                new float[] {999f, 888f, 777f, 666f}), codes);

        // 3. /FirstChar//LastChar mismatch with a short /Widths.
        emit(out, "helv_short", helvWithWidths(65, 90,
                new float[] {999f, 888f}), codes);

        // 4. Unknown base font (not Standard-14, not embedded, no /Widths).
        emit(out, "unknown", bare("MadeUpFont-XYZ"), codes);

        // 5. /Encoding as a name.
        emit(out, "helv_winansi", std14Enc("Helvetica", COSName.WIN_ANSI_ENCODING),
                codes);
        emit(out, "helv_macroman",
                std14Enc("Helvetica", COSName.MAC_ROMAN_ENCODING), codes);
        emit(out, "helv_standard",
                std14Enc("Helvetica", COSName.STANDARD_ENCODING), codes);

        // 6. /Encoding as a dict with /Differences.
        emit(out, "helv_diff", helvDiff(), codes);

        // 7. Missing /FontDescriptor on a Standard-14 name.
        emit(out, "helv_nodesc", bare("Helvetica"), codes);
    }

    /** Standard-14 by name, with a minimal /FontDescriptor, no /Widths, no
     * /Encoding. (Built through the dict constructor, NOT the FontName
     * constructor — so the built-in AFM encoding drives code->name.) */
    private static PDType1Font std14(PrintStream out, String name) throws Exception {
        COSDictionary dict = baseDict(name);
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        fd.setName(COSName.FONT_NAME, name);
        dict.setItem(COSName.FONT_DESC, fd);
        return new PDType1Font(dict);
    }

    private static PDType1Font std14Enc(String name, COSName enc) throws Exception {
        COSDictionary dict = baseDict(name);
        dict.setItem(COSName.ENCODING, enc);
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        fd.setName(COSName.FONT_NAME, name);
        dict.setItem(COSName.FONT_DESC, fd);
        return new PDType1Font(dict);
    }

    private static PDType1Font helvDiff() throws Exception {
        COSDictionary dict = baseDict("Helvetica");
        COSDictionary enc = new COSDictionary();
        enc.setItem(COSName.TYPE, COSName.ENCODING);
        enc.setItem(COSName.BASE_ENCODING, COSName.WIN_ANSI_ENCODING);
        COSArray diffs = new COSArray();
        diffs.add(org.apache.pdfbox.cos.COSInteger.get(65));
        diffs.add(COSName.getPDFName("bullet"));
        diffs.add(org.apache.pdfbox.cos.COSInteger.get(97));
        diffs.add(COSName.getPDFName("dagger"));
        enc.setItem(COSName.DIFFERENCES, diffs);
        dict.setItem(COSName.ENCODING, enc);
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        fd.setName(COSName.FONT_NAME, "Helvetica");
        dict.setItem(COSName.FONT_DESC, fd);
        return new PDType1Font(dict);
    }

    private static PDType1Font helvWithWidths(
            int firstChar, int lastChar, float[] widths) throws Exception {
        COSDictionary dict = baseDict("Helvetica");
        dict.setInt(COSName.FIRST_CHAR, firstChar);
        dict.setInt(COSName.LAST_CHAR, lastChar);
        COSArray w = new COSArray();
        for (float val : widths) {
            w.add(new COSFloat(val));
        }
        dict.setItem(COSName.WIDTHS, w);
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        fd.setName(COSName.FONT_NAME, "Helvetica");
        dict.setItem(COSName.FONT_DESC, fd);
        return new PDType1Font(dict);
    }

    /** Bare dict: /BaseFont + /Subtype only — no /FontDescriptor. */
    private static PDType1Font bare(String name) throws Exception {
        return new PDType1Font(baseDict(name));
    }

    private static COSDictionary baseDict(String name) {
        COSDictionary dict = new COSDictionary();
        dict.setItem(COSName.TYPE, COSName.FONT);
        dict.setItem(COSName.SUBTYPE, COSName.getPDFName("Type1"));
        dict.setName(COSName.BASE_FONT, name);
        return dict;
    }

    private static void emit(PrintStream out, String key, PDType1Font font,
            int[] codes) {
        String std14;
        try {
            std14 = font.isStandard14() ? "true" : "false";
        } catch (Exception e) {
            std14 = "ERR";
        }
        String embedded;
        try {
            embedded = font.isEmbedded() ? "true" : "false";
        } catch (Exception e) {
            embedded = "ERR";
        }
        String encClass;
        try {
            Encoding enc = font.getEncoding();
            encClass = enc != null ? enc.getClass().getSimpleName() : "null";
        } catch (Exception e) {
            encClass = "ENC_ERR";
        }
        out.printf("FONT\t%s\t%s\t%s\t%s%n", key, std14, embedded, encClass);
        for (int code : codes) {
            String width;
            try {
                width = fmt(font.getWidth(code));
            } catch (Exception e) {
                width = "WERR";
            }
            String wff;
            try {
                wff = fmt(font.getWidthFromFont(code));
            } catch (Exception e) {
                wff = "WFFERR";
            }
            String glyph;
            try {
                Encoding enc = font.getEncoding();
                glyph = enc != null ? enc.getName(code) : "NOENC";
            } catch (Exception e) {
                glyph = "GERR";
            }
            out.printf("W\t%s\t%d\t%s\t%s\t%s%n", key, code, width, wff, glyph);
        }
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
