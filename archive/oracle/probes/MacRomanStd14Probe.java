import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.TreeMap;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDSimpleFont;
import org.apache.pdfbox.pdmodel.font.encoding.DictionaryEncoding;
import org.apache.pdfbox.pdmodel.font.encoding.Encoding;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: a non-embedded Standard-14 PDType1Font (Helvetica) with an
 * explicit {@code /Encoding /MacRomanEncoding} override. Verifies that
 * PDFBox resolves the override to MacRoman's code -> glyph-name map (which
 * disagrees with WinAnsi at ~108 real-glyph codes), then looks each width up in
 * the bundled AFM via the MacRoman glyph name (so 0xA5 -> "bullet" gets the
 * bullet's AFM advance, not the WinAnsi-resolved "yen" advance). Without the
 * override correctly applied the non-embedded Std-14 fallback uses WinAnsi
 * (wave 1431) which would mis-resolve every MR-vs-WA-differing code.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> MacRomanStd14Probe input.pdf
 *
 * Output (UTF-8, stdout) for every PDSimpleFont on page 0 (ascending resource
 * name order, deterministic across runs):
 *   FONT\t<resourceName>\t<baseFont>\t<subType>\t<embedded>
 *   ENC\t<encClass>\t<encId>\t<isDictionary>\t<baseEncodingId>
 *     <encClass>       simple class name of getEncoding(), or "null"
 *     <encId>          encoding's /Encoding COSName literal, else class name
 *     <isDictionary>   "true" / "false"
 *     <baseEncodingId> for DictionaryEncoding, the base's id; else the own id
 *   CODE\t<code>\t<glyphName>\t<width>      one per code in the MR-vs-WA
 *                                           differing set (see CODES below).
 *                                           Width via simple.getWidth(code).
 *
 * Then the document's PDFTextStripper text:
 *   TEXT\t<line>                            "␀" literal for empty lines so the
 *                                           shape is diffable.
 */
public final class MacRomanStd14Probe {

    /** Subset of codes whose MacRoman glyph-name DIFFERS from WinAnsi (both
     *  sides map to a real glyph, not .notdef). Spans the 0x80..0xFF block
     *  where the two encodings disagree, with one representative of each
     *  meaningful divergence pattern. */
    private static final int[] CODES = {
        0x80, // MR Adieresis     WA Euro
        0x85, // MR Odieresis     WA ellipsis
        0xA0, // MR dagger        WA nbspace
        0xA1, // MR degree        WA exclamdown
        0xA4, // MR section       WA currency
        0xA5, // MR bullet        WA yen
        0xA6, // MR paragraph     WA brokenbar
        0xA7, // MR germandbls    WA section
        0xAA, // MR trademark     WA ordfeminine
        0xAE, // MR AE            WA registered
        0xB4, // MR yen           WA acute
        0xC4, // MR florin        WA Adieresis
        0xC9, // MR ellipsis      WA Eacute
        0xCA, // MR nbspace       WA Ecircumflex
        0xCE, // MR OE            WA Icircumflex
        0xD0, // MR endash        WA Eth
        0xD1, // MR emdash        WA Ntilde
        0xD2, // MR quotedblleft  WA Ograve
        0xD6, // MR divide        WA Odieresis
        0xD8, // MR ydieresis     WA Oslash
        0xDA, // MR fraction      WA Uacute
        0xDE, // MR fi            WA Thorn
        0xDF, // MR fl            WA germandbls
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            TreeMap<String, COSName> names = new TreeMap<>();
            if (res != null) {
                for (COSName name : res.getFontNames()) {
                    names.put(name.getName(), name);
                }
            }
            List<String> order = new ArrayList<>(names.keySet());
            for (String key : order) {
                emitFont(out, names.get(key), res);
            }
            String text = new PDFTextStripper().getText(doc);
            for (String line : text.split("\n", -1)) {
                String stripped = line.replace("\r", "");
                if (stripped.isEmpty()) {
                    out.println("TEXT\t␀");
                } else {
                    out.printf("TEXT\t%s%n", stripped);
                }
            }
        }
    }

    private static void emitFont(PrintStream out, COSName name, PDResources res)
            throws Exception {
        PDFont font = res.getFont(name);
        if (!(font instanceof PDSimpleFont)) {
            out.printf("FONT\t%s\tNON_SIMPLE%n", name.getName());
            return;
        }
        PDSimpleFont simple = (PDSimpleFont) font;
        out.printf("FONT\t%s\t%s\t%s\t%s%n",
                name.getName(),
                simple.getName(),
                simple.getSubType(),
                Boolean.toString(simple.isEmbedded()));

        Encoding enc = simple.getEncoding();
        boolean isDict = enc instanceof DictionaryEncoding;
        String encClass = enc == null ? "null" : enc.getClass().getSimpleName();
        String encId = encodingId(enc);
        String baseId;
        if (enc == null) {
            baseId = "null";
        } else if (isDict) {
            baseId = encodingId(((DictionaryEncoding) enc).getBaseEncoding());
        } else {
            baseId = encId;
        }
        out.printf("ENC\t%s\t%s\t%s\t%s%n", encClass, encId, isDict, baseId);

        for (int code : CODES) {
            String glyph = enc == null ? ".notdef" : enc.getName(code);
            float width;
            try {
                width = simple.getWidth(code);
            } catch (Exception e) {
                out.printf("CODE\t%d\t%s\tERR%n", code, glyph);
                continue;
            }
            out.printf("CODE\t%d\t%s\t%s%n", code, glyph, canonNumber(width));
        }
    }

    /** Stable identifier for an Encoding: its /Encoding COSName literal when it
     *  has one, else its class simple name, else "null". */
    private static String encodingId(Encoding enc) {
        if (enc == null) {
            return "null";
        }
        COSBase cos = enc.getCOSObject();
        if (cos instanceof COSName) {
            return ((COSName) cos).getName();
        }
        return enc.getClass().getSimpleName();
    }

    /** Canonical number rendering shared with DiffEncodingProbe so a width that
     *  rounds to an integer stays integer-formatted (e.g. "350" not "350.0"). */
    private static String canonNumber(double value) {
        if (value == Math.rint(value) && !Double.isInfinite(value)) {
            return Long.toString((long) value);
        }
        return String.format(Locale.ROOT, "%s", value);
    }
}
