import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
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
 * Live oracle probe for an /Encoding dictionary that overlays a base encoding
 * with a /Differences array (PDF 32000-1 §9.6.6.1). For every PDSimpleFont on
 * page 0 (walked in ascending resource-name order so blocks are deterministic)
 * it emits, all to stdout (UTF-8):
 *
 *   FONT\t<resourceName>\t<baseFont>\t<subType>
 *   ENC\t<encClass>\t<isDictionary>\t<baseEncodingId>
 *     <encClass>       simple class name of font.getEncoding() (e.g.
 *                      "DictionaryEncoding"), or "null".
 *     <isDictionary>   "true"/"false".
 *     <baseEncodingId> for a DictionaryEncoding, the identifier of its base
 *                      encoding (the /Encoding COSName literal like
 *                      "WinAnsiEncoding", the base Encoding's class name when it
 *                      has no COS name, or "null" for a differences-only
 *                      encoding). For a non-dictionary encoding its own id.
 *   CODE\t<code>\t<glyphName>\t<width>      for every code passed on argv
 *     <glyphName> = font.getEncoding().getName(code) (".notdef" when no
 *     resolved Encoding); <width> = font.getWidth(code) (canonical number).
 *
 * After every font block, the document text from PDFTextStripper:
 *   TEXT\t<line>                            one line per source line, with a
 *                                           literal "␀" placeholder for empty
 *                                           lines so the line shape is diffable.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> DiffEncodingProbe input.pdf code...
 */
public final class DiffEncodingProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        List<Integer> codes = new ArrayList<>();
        for (int i = 1; i < args.length; i++) {
            codes.add(Integer.parseInt(args[i]));
        }
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(0);
            PDResources res = page.getResources();
            // Sort the font resource names so the per-font blocks are emitted
            // in a deterministic order independent of dictionary iteration.
            TreeMap<String, COSName> names = new TreeMap<>();
            if (res != null) {
                for (COSName name : res.getFontNames()) {
                    names.put(name.getName(), name);
                }
            }
            for (COSName name : names.values()) {
                emitFont(out, name, res, codes);
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

    private static void emitFont(
            PrintStream out, COSName name, PDResources res, List<Integer> codes)
            throws Exception {
        PDFont font = res.getFont(name);
        if (!(font instanceof PDSimpleFont)) {
            out.printf("FONT\t%s\tNON_SIMPLE%n", name.getName());
            return;
        }
        PDSimpleFont simple = (PDSimpleFont) font;
        out.printf("FONT\t%s\t%s\t%s%n",
                name.getName(), simple.getName(), simple.getSubType());

        Encoding enc = simple.getEncoding();
        boolean isDict = enc instanceof DictionaryEncoding;
        String encClass = enc == null ? "null" : enc.getClass().getSimpleName();
        String baseId;
        if (enc == null) {
            baseId = "null";
        } else if (isDict) {
            baseId = encodingId(((DictionaryEncoding) enc).getBaseEncoding());
        } else {
            baseId = encodingId(enc);
        }
        out.printf("ENC\t%s\t%s\t%s%n", encClass, isDict, baseId);

        for (int code : codes) {
            String glyph = enc == null ? ".notdef" : enc.getName(code);
            float width = simple.getWidth(code);
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

    /** Canonical number rendering shared with the other probes/tests. */
    private static String canonNumber(double value) {
        if (value == Math.rint(value) && !Double.isInfinite(value)) {
            return Long.toString((long) value);
        }
        return Double.toString(value);
    }
}
