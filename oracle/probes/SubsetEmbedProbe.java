import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeSet;
import org.apache.fontbox.ttf.CmapLookup;
import org.apache.fontbox.ttf.CmapTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDCIDFontType2;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDTrueTypeFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Live oracle probe for pypdfbox's TrueType / Type0 font *embedding* and
 * *subsetting* output. Loads a pypdfbox-produced PDF, reaches the embedded
 * font program through Apache PDFBox's own loaders
 * (PDTrueTypeFont.getTrueTypeFont() / PDCIDFontType2.getTrueTypeFont()), and
 * emits canonical, line-oriented metrics that pypdfbox mirrors so a parity
 * test can assert PDFBox parses the subset program and reads consistent
 * numbers.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SubsetEmbedProbe input.pdf
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *   FONT \t pageIndex \t resourceName \t baseFont \t subType \t isEmbedded \t
 *        embeddedKind
 *      embeddedKind is "TrueType" when an embedded TTF program is reachable,
 *      else "NONE".
 *   PROG \t pageIndex \t resourceName \t numGlyphs \t unitsPerEm \t
 *        hasCmap \t hasGlyf \t hasHmtx
 *      Program-level shape of the embedded TTF. hasCmap/hasGlyf/hasHmtx are
 *      true/false flags for the cmap / glyf / hmtx tables PDFBox requires.
 *   GADV \t pageIndex \t resourceName \t gid \t advance
 *      Embedded-program advance width (font units) for every glyph index in
 *      the subset (0 .. numGlyphs-1), straight from TrueTypeFont.getAdvanceWidth.
 *   WID \t pageIndex \t resourceName \t code \t gid \t widthFromFont
 *      Per used character code (derived from /Widths for simple fonts and /W
 *      for Type0): the resolved glyph id (codeToGID) and PDFBox's
 *      getWidthFromFont(code) -- the advance expressed in 1000-unit text
 *      space. Codes whose resolution throws are emitted with "ERR".
 *
 * Widths are normalised to 4 decimal places. This probe never mutates the
 * document and closes it via try-with-resources.
 */
public final class SubsetEmbedProbe {
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
        }
    }

    private static void emitFont(PrintStream out, int pageIndex, COSName name,
            PDResources res) throws Exception {
        String key = name.getName();
        PDFont font;
        try {
            font = res.getFont(name);
        } catch (Exception e) {
            out.printf("FONT\t%d\t%s\tLOAD_ERR%n", pageIndex, key);
            return;
        }
        if (font == null) {
            out.printf("FONT\t%d\t%s\tNULL%n", pageIndex, key);
            return;
        }

        TrueTypeFont ttf = embeddedTtf(font);
        boolean embedded;
        try {
            embedded = font.isEmbedded();
        } catch (Exception e) {
            embedded = false;
        }
        out.printf("FONT\t%d\t%s\t%s\t%s\t%b\t%s%n",
                pageIndex, key, String.valueOf(font.getName()),
                font.getSubType(), embedded,
                ttf != null ? "TrueType" : "NONE");

        if (ttf == null) {
            return;
        }

        int numGlyphs = ttf.getNumberOfGlyphs();
        int unitsPerEm = ttf.getUnitsPerEm();
        boolean hasCmap = ttf.getCmap() != null;
        boolean hasGlyf = ttf.getGlyph() != null;
        boolean hasHmtx = ttf.getHorizontalMetrics() != null;
        out.printf("PROG\t%d\t%s\t%d\t%d\t%b\t%b\t%b%n",
                pageIndex, key, numGlyphs, unitsPerEm, hasCmap, hasGlyf, hasHmtx);

        for (int gid = 0; gid < numGlyphs; gid++) {
            int adv;
            try {
                adv = ttf.getAdvanceWidth(gid);
            } catch (Exception e) {
                out.printf("GADV\t%d\t%s\t%d\tERR%n", pageIndex, key, gid);
                continue;
            }
            out.printf("GADV\t%d\t%s\t%d\t%d%n", pageIndex, key, gid, adv);
        }

        for (int code : usedCodes(font)) {
            String gid;
            try {
                gid = String.valueOf(codeToGid(font, code));
            } catch (Exception e) {
                gid = "ERR";
            }
            String w;
            try {
                w = fmt(font.getWidthFromFont(code));
            } catch (Exception e) {
                w = "ERR";
            }
            out.printf("WID\t%d\t%s\t%d\t%s\t%s%n", pageIndex, key, code, gid, w);
        }
    }

    private static TrueTypeFont embeddedTtf(PDFont font) {
        try {
            if (font instanceof PDType0Font) {
                PDCIDFont descendant = ((PDType0Font) font).getDescendantFont();
                if (descendant instanceof PDCIDFontType2) {
                    return ((PDCIDFontType2) descendant).getTrueTypeFont();
                }
                return null;
            }
            if (font instanceof PDTrueTypeFont) {
                return ((PDTrueTypeFont) font).getTrueTypeFont();
            }
        } catch (Exception e) {
            return null;
        }
        return null;
    }

    private static int codeToGid(PDFont font, int code) throws Exception {
        if (font instanceof PDType0Font) {
            PDType0Font t0 = (PDType0Font) font;
            PDCIDFont descendant = t0.getDescendantFont();
            int cid = t0.codeToCID(code);
            if (descendant instanceof PDCIDFontType2) {
                return ((PDCIDFontType2) descendant).codeToGID(cid);
            }
            return cid;
        }
        if (font instanceof PDTrueTypeFont) {
            return ((PDTrueTypeFont) font).codeToGID(code);
        }
        return code;
    }

    /**
     * Resolve the set of character codes the document addresses, in ascending
     * order. Simple fonts: the contiguous /FirstChar .. /LastChar /Widths
     * range. Type0: the CIDs spelled out by the descendant's /W array (under
     * Identity-H, code == CID). The cmap is consulted as well via CmapLookup
     * so the synthetic codes line up with the embedded program coverage.
     */
    private static List<Integer> usedCodes(PDFont font) {
        TreeSet<Integer> codes = new TreeSet<>();
        if (font instanceof PDType0Font) {
            PDCIDFont descendant = ((PDType0Font) font).getDescendantFont();
            if (descendant != null) {
                COSBase wBase = descendant.getCOSObject()
                        .getDictionaryObject(COSName.W);
                if (wBase instanceof COSArray) {
                    codes.addAll(widthCidsFromW((COSArray) wBase));
                }
            }
        } else if (font instanceof PDTrueTypeFont) {
            COSDictionary dict = font.getCOSObject();
            COSBase fc = dict.getDictionaryObject(COSName.FIRST_CHAR);
            COSBase lc = dict.getDictionaryObject(COSName.LAST_CHAR);
            if (fc instanceof COSInteger && lc instanceof COSInteger) {
                int first = ((COSInteger) fc).intValue();
                int last = ((COSInteger) lc).intValue();
                for (int c = first; c <= last && c - first < 256; c++) {
                    codes.add(c);
                }
            }
        }
        return new ArrayList<>(codes);
    }

    private static List<Integer> widthCidsFromW(COSArray w) {
        List<Integer> out = new ArrayList<>();
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
                    out.add(cFirst + k);
                }
                i += 2;
            } else if (next instanceof COSNumber) {
                if (i + 2 >= n) {
                    break;
                }
                int cLast = ((COSNumber) next).intValue();
                int upper = Math.min(cLast, cFirst + 1024);
                for (int c = cFirst; c <= upper; c++) {
                    out.add(c);
                }
                i += 3;
            } else {
                break;
            }
        }
        return out;
    }

    private static String fmt(double v) {
        return String.format(java.util.Locale.ROOT, "%.4f", v);
    }
}
