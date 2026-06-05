import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDCIDFontType2;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDFontDescriptor;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Live oracle probe for the NON-EMBEDDED CIDFontType2 model-layer contract.
 *
 * Usage: java -cp ... CidSubstituteGidProbe input.pdf code0 code1 ...
 *
 * The substitute-font GID resolution upstream (PDCIDFontType2.codeToGID on the
 * !isEmbedded branch) is resolved through a platform FontMapper and is therefore
 * machine-dependent (it picks whatever TrueType the host OS offers). pypdfbox
 * deliberately delegates that substitution to the renderer, so the model-layer
 * GID is NOT a deterministic differential surface and is intentionally NOT
 * emitted here.
 *
 * What IS machine-independent (and is what this probe pins) for a /FontFile2-less
 * Type0/CIDFontType2:
 *
 *   HEAD \t <isEmbedded> \t <descSubtype> \t <cidToGidKind> \t
 *          <hasFontFile2> \t <hasFontFile3> \t <hasFontFile> \t
 *          <defaultWidth>
 *   CODE \t <code> \t <cid> \t <width>
 *
 * where cid = PDType0Font.codeToCID(code) (driven by the parent encoding CMap +
 * /ToUnicode round-trip — independent of any substitute font program) and
 * width = PDType0Font.getWidth(code) (the /W array displacement, independent of
 * the substitute glyph's own hmtx advance). Output is UTF-8, tab-delimited,
 * deterministic in argument order.
 */
public final class CidSubstituteGidProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDType0Font t0 = firstType0(doc);
            if (t0 == null) {
                out.println("HEAD\tNONE");
                return;
            }
            PDCIDFont descendant = t0.getDescendantFont();
            boolean embedded;
            try {
                embedded = t0.isEmbedded();
            } catch (Exception e) {
                embedded = false;
            }
            PDFontDescriptor fd = descendant == null
                ? null
                : descendant.getFontDescriptor();
            out.printf(
                "HEAD\t%s\t%s\t%s\t%s\t%s\t%s\t%s%n",
                embedded ? "true" : "false",
                descendantSubtype(descendant),
                cidToGidKind(descendant),
                fd != null && fd.getFontFile2() != null ? "true" : "false",
                fd != null && fd.getFontFile3() != null ? "true" : "false",
                fd != null && fd.getFontFile() != null ? "true" : "false",
                String.valueOf(defaultWidth(descendant)));

            for (int i = 1; i < args.length; i++) {
                int code = Integer.parseInt(args[i]);
                String cid;
                try {
                    cid = String.valueOf(t0.codeToCID(code));
                } catch (Exception e) {
                    cid = "ERR";
                }
                String width;
                try {
                    width = String.valueOf(t0.getWidth(code));
                } catch (Exception e) {
                    width = "ERR";
                }
                out.printf("CODE\t%d\t%s\t%s%n", code, cid, width);
            }
        }
    }

    private static PDType0Font firstType0(PDDocument doc) throws Exception {
        for (PDPage page : doc.getPages()) {
            PDResources res = page.getResources();
            if (res == null) {
                continue;
            }
            for (COSName name : res.getFontNames()) {
                PDFont font;
                try {
                    font = res.getFont(name);
                } catch (Exception e) {
                    continue;
                }
                if (font instanceof PDType0Font) {
                    return (PDType0Font) font;
                }
            }
        }
        return null;
    }

    private static String descendantSubtype(PDCIDFont descendant) {
        if (descendant == null) {
            return "NONE";
        }
        if (descendant instanceof PDCIDFontType2) {
            return "CIDFontType2";
        }
        return descendant.getClass().getSimpleName();
    }

    private static String cidToGidKind(PDCIDFont descendant) {
        if (!(descendant instanceof PDCIDFontType2)) {
            return "n/a";
        }
        COSDictionary dict = descendant.getCOSObject();
        COSBase entry = dict.getDictionaryObject(COSName.CID_TO_GID_MAP);
        if (entry == null) {
            return "Identity(absent)";
        }
        if (entry instanceof COSName) {
            return "name:" + ((COSName) entry).getName();
        }
        return "stream";
    }

    private static float defaultWidth(PDCIDFont descendant) {
        if (descendant == null) {
            return -1f;
        }
        // /DW defaults to 1000 per PDF 32000-1 9.7.4.3 when absent.
        COSDictionary dict = descendant.getCOSObject();
        COSBase dw = dict.getDictionaryObject(COSName.DW);
        if (dw instanceof org.apache.pdfbox.cos.COSNumber) {
            return ((org.apache.pdfbox.cos.COSNumber) dw).floatValue();
        }
        return 1000f;
    }
}
