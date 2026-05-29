import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDCIDFontType0;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;
import org.apache.pdfbox.util.Matrix;

/**
 * Live oracle probe: emit Apache PDFBox's CIDFontType0 (CFF CID-keyed) glyph
 * surfaces for every composite font whose descendant is a PDCIDFontType0 with
 * an embedded CFF program (/FontFile3 /Subtype /CIDFontType0C).
 *
 * For each such font a FONT line carries the font matrix and embedded/damaged
 * flags; one GLYPH line per probed code carries codeToGID, getWidthFromFont,
 * and hasGlyph:
 *
 *   FONT \t pageIndex \t fontKey \t baseFont \t isEmbedded \t isDamaged \t
 *        m0 \t m1 \t m2 \t m3 \t m4 \t m5
 *   GLYPH \t pageIndex \t fontKey \t code \t cid \t gid \t widthFromFont \t hasGlyph
 *
 * The probed codes come from the descendant CIDFont's /W array (under Identity
 * encoding the input code equals the CID, which the project's CIDFontType0
 * fixtures use), plus CID 0 (.notdef) and two synthetic out-of-range CIDs.
 *
 * Float widths are printed with %.4f for deterministic cross-engine compare.
 * Output is UTF-8, tab-delimited, deterministic line order (page, font name,
 * ascending code).
 */
public final class CidType0CffProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    emitPage(out, res, pageIndex);
                }
                pageIndex++;
            }
        }
    }

    private static void emitPage(PrintStream out, PDResources res, int pageIndex)
            throws Exception {
        for (COSName name : res.getFontNames()) {
            PDFont font;
            try {
                font = res.getFont(name);
            } catch (Exception e) {
                continue;
            }
            if (!(font instanceof PDType0Font)) {
                continue;
            }
            PDType0Font t0 = (PDType0Font) font;
            PDCIDFont descendant = t0.getDescendantFont();
            if (!(descendant instanceof PDCIDFontType0)) {
                continue;
            }
            PDCIDFontType0 cid0 = (PDCIDFontType0) descendant;

            Matrix m = cid0.getFontMatrix();
            out.printf(
                "FONT\t%d\t%s\t%s\t%s\t%s\t%.6f\t%.6f\t%.6f\t%.6f\t%.6f\t%.6f%n",
                pageIndex,
                name.getName(),
                String.valueOf(t0.getName()),
                cid0.isEmbedded() ? "true" : "false",
                cid0.isDamaged() ? "true" : "false",
                m.getScaleX(),
                m.getShearY(),
                m.getShearX(),
                m.getScaleY(),
                m.getTranslateX(),
                m.getTranslateY());

            for (int code : coveredCodes(descendant)) {
                int cid;
                try {
                    cid = t0.codeToCID(code);
                } catch (Exception e) {
                    out.printf("GLYPH\t%d\t%s\t%d\tERR\tERR\tERR\tERR%n",
                        pageIndex, name.getName(), code);
                    continue;
                }
                String gid;
                try {
                    gid = String.valueOf(cid0.codeToGID(code));
                } catch (Exception e) {
                    gid = "ERR";
                }
                String width;
                try {
                    width = String.format("%.4f", cid0.getWidthFromFont(code));
                } catch (Exception e) {
                    width = "ERR";
                }
                String hasGlyph;
                try {
                    hasGlyph = cid0.hasGlyph(code) ? "true" : "false";
                } catch (Exception e) {
                    hasGlyph = "ERR";
                }
                out.printf("GLYPH\t%d\t%s\t%d\t%d\t%s\t%s\t%s%n",
                    pageIndex, name.getName(), code, cid, gid, width, hasGlyph);
            }
        }
    }

    /**
     * Resolve the probed CIDs from the descendant's /W array. Under Identity
     * encoding the input code equals the CID, so the /W CIDs are exactly the
     * addressable codes. CID 0 (.notdef) and two synthetic out-of-range CIDs
     * are always included. Returns an ascending, de-duplicated list, capped so
     * a pathological range can't explode output.
     */
    private static java.util.List<Integer> coveredCodes(PDCIDFont descendant) {
        java.util.TreeSet<Integer> set = new java.util.TreeSet<>();
        set.add(0);
        set.add(60000);
        set.add(65535);
        if (descendant == null) {
            return new java.util.ArrayList<>(set);
        }
        COSDictionary dict = descendant.getCOSObject();
        COSBase wBase = dict.getDictionaryObject(COSName.W);
        if (wBase instanceof COSArray) {
            COSArray w = (COSArray) wBase;
            int i = 0;
            int n = w.size();
            while (i < n) {
                COSBase first = w.getObject(i);
                if (!(first instanceof COSNumber)) {
                    break;
                }
                int cFirst = ((COSNumber) first).intValue();
                if (i + 1 >= n) {
                    break;
                }
                COSBase next = w.getObject(i + 1);
                if (next instanceof COSArray) {
                    COSArray widths = (COSArray) next;
                    for (int k = 0; k < widths.size(); k++) {
                        set.add(cFirst + k);
                    }
                    i += 2;
                } else if (next instanceof COSNumber) {
                    if (i + 2 >= n) {
                        break;
                    }
                    int cLast = ((COSNumber) next).intValue();
                    int upper = Math.min(cLast, cFirst + 1024);
                    for (int c = cFirst; c <= upper; c++) {
                        set.add(c);
                    }
                    i += 3;
                } else {
                    break;
                }
            }
        }
        return new java.util.ArrayList<>(set);
    }
}
