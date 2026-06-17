import java.io.PrintStream;
import java.util.Locale;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNull;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType1Font;

/**
 * Live oracle probe: pin Apache PDFBox's {@code PDFont.getWidth(int)}
 * {@code /Widths}-array width-resolution surface (PDF 32000-1 §9.2.4) on a
 * simple (Type1) font.
 *
 * Distinct from the adjacent font-width oracles:
 *   - CidWidthProbe drives the composite-font /W + /DW path (PDCIDFont).
 *   - AfmFontMetricsProbe / std14 drive the Standard-14 AFM advance path.
 *   - Type1CSimpleFontProbe drives the embedded Type1C program width.
 * This probe drives the *dictionary* /Widths array + /FirstChar/.../LastChar
 * window + /MissingWidth fallback on a NON-embedded, NON-Standard-14 simple
 * font, so getWidth never reaches the AFM or font-program branches.
 *
 * Several synthetic font dictionaries are built entirely in-Java (no fixture)
 * so every edge of the array lookup is exercised deterministically:
 *
 *   getWidth(code) =
 *     /Widths[code - /FirstChar]                       when /Widths present and
 *                                                       FirstChar <= code <= LastChar
 *                                                       and (code-FirstChar) < size
 *                                                       (a null entry -> 0.0)
 *     /FontDescriptor /MissingWidth (default 0)         otherwise, when /Widths or
 *                                                       /MissingWidth is present and
 *                                                       a /FontDescriptor exists
 *     0.0                                               otherwise (no descriptor,
 *                                                       not Standard14, no program)
 *
 * For each font/code we emit (UTF-8, tab-delimited, deterministic order):
 *   FONT \t fontKey \t firstChar \t lastChar \t missingWidth \t widthsLen
 *   WIDTH \t fontKey \t code \t getWidth(code) \t hasExplicitWidth(code)
 *
 * Floats formatted "%.4f" (Locale.ROOT) with -0.0 collapsed; pypdfbox mirrors
 * the exact line format so any divergence is a single differing line.
 */
public final class SimpleFontWidthsProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        // Every probed font carries a /FontDescriptor /MissingWidth so that the
        // out-of-window branch resolves to /MissingWidth and NEVER reaches the
        // Standard-14 AFM or the substitute-font-program branch — keeping the
        // surface strictly the dictionary /Widths array + /MissingWidth
        // fallback (the program-width / AFM facets are pinned by other oracles).

        // --- Font A: /Widths + /FirstChar/65 .. /LastChar/68, /MissingWidth 999.
        // Codes below FirstChar, inside, above LastChar.
        emit(out, "A_descriptor_mw999", buildFont(65, 68,
                new Float[] {500f, 600f, 700f, 800f}, 999f),
                new int[] {0, 32, 64, 65, 66, 67, 68, 69, 70, 200, 255});

        // --- Font B: /MissingWidth 0 (the spec default), so out-of-window codes
        // read back as 0.0 — pins that the default is genuinely zero.
        emit(out, "B_missingwidth_zero", buildFont(65, 68,
                new Float[] {500f, 600f, 700f, 800f}, 0f),
                new int[] {0, 64, 65, 66, 67, 68, 69, 255});

        // --- Font C: a null (COSNull) and a name (non-numeric) in the middle of
        // /Widths. toCOSNumberFloatList() keeps a null slot for each, so the
        // index alignment is preserved and a null slot reads back as 0.0.
        emit(out, "C_null_and_nonnumeric", buildFontMixed(65, 70, 0f),
                new int[] {64, 65, 66, 67, 68, 69, 70, 71});

        // --- Font E: /FirstChar set but FirstChar > LastChar (degenerate). The
        // window check (code <= lastChar) fails for every code -> MissingWidth
        // fallback, even though hasExplicitWidth(code) is true for code-first <
        // size.
        emit(out, "E_first_gt_last", buildFont(80, 70,
                new Float[] {111f, 222f, 333f}, 444f),
                new int[] {69, 70, 75, 80, 81, 82, 90});
    }

    private static PDType1Font buildFont(
            int firstChar, int lastChar, Float[] widths, Float missingWidth)
            throws Exception {
        COSDictionary dict = new COSDictionary();
        dict.setItem(COSName.TYPE, COSName.FONT);
        dict.setItem(COSName.SUBTYPE, COSName.getPDFName("Type1"));
        dict.setName(COSName.BASE_FONT, "ProbeFont");
        dict.setInt(COSName.FIRST_CHAR, firstChar);
        dict.setInt(COSName.LAST_CHAR, lastChar);
        COSArray w = new COSArray();
        for (Float val : widths) {
            w.add(new COSFloat(val));
        }
        dict.setItem(COSName.WIDTHS, w);
        if (missingWidth != null) {
            COSDictionary fd = new COSDictionary();
            fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
            fd.setName(COSName.FONT_NAME, "ProbeFont");
            fd.setFloat(COSName.MISSING_WIDTH, missingWidth);
            dict.setItem(COSName.FONT_DESC, fd);
        }
        return new PDType1Font(dict);
    }

    /**
     * /Widths = [500, COSNull, /SomeName, 800, 900, 1000] over FirstChar 65 ..
     * LastChar 70: the COSNull (code 66) and the COSName (code 67) are both
     * non-numbers, so toCOSNumberFloatList() yields nulls at those slots which
     * getWidth maps to 0.0. A /FontDescriptor with the given MissingWidth is
     * attached so the out-of-window branch is deterministic.
     */
    private static PDType1Font buildFontMixed(
            int firstChar, int lastChar, float missingWidth) throws Exception {
        COSDictionary dict = new COSDictionary();
        dict.setItem(COSName.TYPE, COSName.FONT);
        dict.setItem(COSName.SUBTYPE, COSName.getPDFName("Type1"));
        dict.setName(COSName.BASE_FONT, "ProbeFontC");
        dict.setInt(COSName.FIRST_CHAR, firstChar);
        dict.setInt(COSName.LAST_CHAR, lastChar);
        COSArray w = new COSArray();
        w.add(new COSFloat(500f));        // 65
        w.add(COSNull.NULL);              // 66 -> null -> 0.0
        w.add(COSName.getPDFName("X"));   // 67 -> non-number -> null -> 0.0
        w.add(new COSFloat(800f));        // 68
        w.add(COSInteger.get(900));       // 69
        w.add(new COSFloat(1000f));       // 70
        dict.setItem(COSName.WIDTHS, w);
        COSDictionary fd = new COSDictionary();
        fd.setItem(COSName.TYPE, COSName.getPDFName("FontDescriptor"));
        fd.setName(COSName.FONT_NAME, "ProbeFontC");
        fd.setFloat(COSName.MISSING_WIDTH, missingWidth);
        dict.setItem(COSName.FONT_DESC, fd);
        return new PDType1Font(dict);
    }

    private static void emit(PrintStream out, String key, PDFont font, int[] codes)
            throws Exception {
        COSDictionary dict = font.getCOSObject();
        int firstChar = dict.getInt(COSName.FIRST_CHAR, -1);
        int lastChar = dict.getInt(COSName.LAST_CHAR, -1);
        float missingWidth = font.getFontDescriptor() != null
                ? font.getFontDescriptor().getMissingWidth()
                : Float.NaN;
        COSArray widthsArr = dict.getCOSArray(COSName.WIDTHS);
        int widthsLen = widthsArr != null ? widthsArr.size() : 0;
        out.printf(
                "FONT\t%s\t%d\t%d\t%s\t%d%n",
                key, firstChar, lastChar,
                Float.isNaN(missingWidth) ? "NONE" : fmt(missingWidth),
                widthsLen);
        for (int code : codes) {
            String width;
            String explicit;
            try {
                width = fmt(font.getWidth(code));
            } catch (Exception e) {
                width = "WIDTH_ERR";
            }
            try {
                explicit = font.hasExplicitWidth(code) ? "true" : "false";
            } catch (Exception e) {
                explicit = "EXPLICIT_ERR";
            }
            out.printf("WIDTH\t%s\t%d\t%s\t%s%n", key, code, width, explicit);
        }
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f; // collapse -0.0 to 0.0
        }
        return String.format(Locale.ROOT, "%.4f", v);
    }
}
