import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
import java.util.TreeSet;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Live oracle probe: emit Apache PDFBox's descendant-CIDFont per-CID width
 * resolution for every Type0 (composite) font on every page of a PDF.
 *
 * This pins the {@code /W} width-array + {@code /DW} default-width surface
 * (PDF 32000-1 §9.7.4.3) at the {@code PDCIDFont} level — distinct from the
 * {@code PDType0Font} string-advance surface already covered by
 * FontMetricsProbe and the code -> CID -> GID surface covered by CidGidProbe.
 *
 * For each Type0 font we resolve the set of probed character codes from the
 * descendant CIDFont's {@code /W} array (under Identity-H — the only encoding
 * the project's Type0 fixtures use — the input code equals the CID, so the
 * {@code /W} CIDs are exactly the addressable codes), exercising BOTH array
 * forms:
 *
 *   c [w1 w2 ...]    consecutive CIDs starting at c
 *   c_first c_last w one width for the whole inclusive range
 *
 * plus synthetic high codes guaranteed to be absent from {@code /W} so the
 * {@code /DW} (default 1000) fallback path is always exercised. For each code
 * we emit, using the public PDCIDFont API:
 *
 *   WIDTH \t pageIndex \t fontKey \t code \t getWidth(code) \t hasExplicitWidth(code)
 *
 * getWidth(code) internally does getWidthForCID(codeToCID(code)) =
 * widths.get(cid) else getDefaultWidth(); hasExplicitWidth(code) reports
 * whether /W specifically carries the CID. A FONT header precedes each block:
 *
 *   FONT \t pageIndex \t fontKey \t baseFont \t descendantSubtype \t defaultWidth
 *
 * Output is UTF-8, tab-delimited, deterministic line order (page, then font
 * name, then ascending code). Widths are formatted "%.4f".
 */
public final class CidWidthProbe {

    // Synthetic codes beyond any realistic /W coverage in the fixtures — these
    // force the /DW default-width fallback (getWidthForCID returns
    // getDefaultWidth() when the CID is absent from the parsed /W map). Kept in
    // lockstep with the Python side.
    private static final int[] DW_FALLBACK = {50000, 60000, 65535};

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
            if (descendant == null) {
                continue;
            }
            float defaultWidth = readDefaultWidth(descendant);
            out.printf(
                "FONT\t%d\t%s\t%s\t%s\t%s%n",
                pageIndex,
                name.getName(),
                String.valueOf(t0.getName()),
                descendant.getClass().getSimpleName(),
                fmt(defaultWidth));

            for (int code : probedCodes(descendant)) {
                String width;
                String explicit;
                try {
                    width = fmt(descendant.getWidth(code));
                } catch (Exception e) {
                    width = "WIDTH_ERR";
                }
                try {
                    explicit = descendant.hasExplicitWidth(code) ? "true" : "false";
                } catch (Exception e) {
                    explicit = "EXPLICIT_ERR";
                }
                out.printf(
                    "WIDTH\t%d\t%s\t%d\t%s\t%s%n",
                    pageIndex, name.getName(), code, width, explicit);
            }
        }
    }

    /**
     * The /DW default width as PDFBox's private getDefaultWidth() computes it:
     * the /DW COSNumber, else 1000.0f.
     */
    private static float readDefaultWidth(PDCIDFont descendant) {
        COSBase dw = descendant.getCOSObject().getDictionaryObject(COSName.DW);
        if (dw instanceof COSNumber) {
            return ((COSNumber) dw).floatValue();
        }
        return 1000.0f;
    }

    /**
     * Codes to probe: every CID covered by /W (both array forms), CID 0, and
     * the synthetic /DW-fallback codes. Ascending, de-duplicated.
     */
    private static List<Integer> probedCodes(PDCIDFont descendant) {
        TreeSet<Integer> set = new TreeSet<>();
        set.add(0);
        for (int c : DW_FALLBACK) {
            set.add(c);
        }
        COSBase wBase = descendant.getCOSObject().getDictionaryObject(COSName.W);
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
                    // Cap so a pathological cLast can't explode output; sample
                    // both ends of the range so the c_first c_last w form is
                    // exercised without enumerating thousands of identical CIDs.
                    int upper = Math.min(cLast, cFirst + 1024);
                    for (int c = cFirst; c <= upper; c++) {
                        set.add(c);
                    }
                    set.add(cLast);
                    i += 3;
                } else {
                    break;
                }
            }
        }
        return new ArrayList<>(set);
    }

    private static String fmt(float v) {
        if (v == 0.0f) {
            v = 0.0f;
        }
        return String.format("%.4f", v);
    }
}
