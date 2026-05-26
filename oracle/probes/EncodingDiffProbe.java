import java.io.File;
import java.io.PrintStream;
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
import org.apache.pdfbox.pdmodel.interactive.form.PDAcroForm;

/**
 * Live oracle probe: emit Apache PDFBox's resolved simple-font /Encoding for
 * every PDSimpleFont on every page of a PDF. Verifies the code -> glyph-name
 * map (codes 0..255 via Encoding.getName(int)), the base-encoding identifier,
 * and whether the resolved encoding is a DictionaryEncoding (i.e. a /Differences
 * override).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> EncodingDiffProbe input.pdf
 *
 * Fonts are enumerated from every page's resources first, then from the
 * AcroForm default resources (where /Differences-bearing form fonts live). The
 * AcroForm DR uses the synthetic page index -1 so blocks stay disjoint.
 *
 * Output (UTF-8, stdout): one block per (page, font-resource-name) for every
 * font that is a PDSimpleFont:
 *   FONT\t<pageIndex>\t<resourceName>\t<baseFont>\t<subType>
 *   ENC\t<encClass>\t<isDictionary>\t<baseEncodingId>
 *   CODE\t<code>\t<glyphName>      (repeated for each code 0..255)
 *
 * <encClass>        the simple class name of the resolved Encoding (e.g.
 *                   "WinAnsiEncoding", "DictionaryEncoding") or "null".
 * <isDictionary>    "true" / "false".
 * <baseEncodingId>  for a DictionaryEncoding, the identifier of its base
 *                   encoding (COSName literal like "WinAnsiEncoding", or the
 *                   base Encoding's class name when it has no COS name, or
 *                   "null" for a Type 3 differences-only encoding). For a
 *                   non-dictionary encoding, its own identifier. "null" when
 *                   the font has no resolved encoding.
 *
 * Fonts that are not PDSimpleFont (Type0/CID) are emitted as a single
 * SKIP\t<pageIndex>\t<resourceName>\t<class> line so the line shape is stable.
 */
public final class EncodingDiffProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    for (COSName name : res.getFontNames()) {
                        emitFont(out, pageIndex, name, res);
                    }
                }
                pageIndex++;
            }
            PDAcroForm form = doc.getDocumentCatalog().getAcroForm();
            if (form != null) {
                PDResources dr = form.getDefaultResources();
                if (dr != null) {
                    for (COSName name : dr.getFontNames()) {
                        emitFont(out, -1, name, dr);
                    }
                }
            }
        }
    }

    private static void emitFont(PrintStream out, int pageIndex, COSName name, PDResources res) {
        PDFont font;
        try {
            font = res.getFont(name);
        } catch (Exception e) {
            out.printf("FONT\t%d\t%s\tLOAD_ERR%n", pageIndex, name.getName());
            return;
        }
        if (font == null) {
            out.printf("FONT\t%d\t%s\tNULL%n", pageIndex, name.getName());
            return;
        }
        if (!(font instanceof PDSimpleFont)) {
            out.printf("SKIP\t%d\t%s\t%s%n",
                    pageIndex, name.getName(), font.getClass().getSimpleName());
            return;
        }
        PDSimpleFont simple = (PDSimpleFont) font;
        out.printf("FONT\t%d\t%s\t%s\t%s%n",
                pageIndex, name.getName(), font.getName(), font.getSubType());

        Encoding enc = simple.getEncoding();
        boolean isDict = enc instanceof DictionaryEncoding;
        String encClass = enc == null ? "null" : enc.getClass().getSimpleName();
        String baseId;
        if (enc == null) {
            baseId = "null";
        } else if (isDict) {
            Encoding base = ((DictionaryEncoding) enc).getBaseEncoding();
            baseId = encodingId(base);
        } else {
            baseId = encodingId(enc);
        }
        out.printf("ENC\t%s\t%s\t%s%n", encClass, isDict, baseId);

        for (int code = 0; code <= 255; code++) {
            String glyph = enc == null ? ".notdef" : enc.getName(code);
            out.printf("CODE\t%d\t%s%n", code, glyph);
        }
    }

    /**
     * Stable identifier for an Encoding: its /Encoding COSName literal when the
     * encoding has one (the four predefined + the two font-program built-ins),
     * else its class simple name, else "null".
     */
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
}
