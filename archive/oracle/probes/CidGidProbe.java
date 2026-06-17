import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.List;
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
import org.apache.pdfbox.pdmodel.font.PDCIDFontType2;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Live oracle probe: emit Apache PDFBox's code -> CID -> GID pipeline for every
 * Type0 (composite) font on every page of a PDF.
 *
 * For each Type0 font we resolve the set of "covered" character codes from the
 * descendant CIDFont's /W width array (under Identity-H — the only encoding the
 * project's Type0 fixtures use — the input code equals the CID, so the /W array
 * CIDs are exactly the codes the document can address). CID 0 (.notdef) is
 * always included. For each code we emit:
 *
 *   CODE \t pageIndex \t fontKey \t code \t cid \t gid
 *
 * using PDType0Font.codeToCID(code) for the CID and, for the descendant, its
 * codeToGID(cid) (PDCIDFontType2 maps CID through /CIDToGIDMap; PDCIDFontType0
 * treats CID == GID for its CFF program). A FONT header line precedes each
 * font's CODE block:
 *
 *   FONT \t pageIndex \t fontKey \t baseFont \t descendantSubtype \t
 *        cidToGidKind \t isEmbedded
 *
 * Output is UTF-8, tab-delimited, deterministic line order (page, then font
 * name, then ascending code).
 */
public final class CidGidProbe {
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
            String descSubtype = descendantSubtype(descendant);
            String cidToGidKind = cidToGidKind(descendant);
            boolean embedded;
            try {
                embedded = t0.isEmbedded();
            } catch (Exception e) {
                embedded = false;
            }
            out.printf(
                "FONT\t%d\t%s\t%s\t%s\t%s\t%s%n",
                pageIndex,
                name.getName(),
                String.valueOf(t0.getName()),
                descSubtype,
                cidToGidKind,
                embedded ? "true" : "false");

            List<Integer> codes = coveredCodes(descendant);
            for (int code : codes) {
                int cid;
                try {
                    cid = t0.codeToCID(code);
                } catch (Exception e) {
                    out.printf("CODE\t%d\t%s\t%d\tCID_ERR\tCID_ERR%n",
                        pageIndex, name.getName(), code);
                    continue;
                }
                String gid;
                try {
                    gid = String.valueOf(descendantGid(descendant, cid));
                } catch (Exception e) {
                    gid = "GID_ERR";
                }
                out.printf("CODE\t%d\t%s\t%d\t%d\t%s%n",
                    pageIndex, name.getName(), code, cid, gid);
            }
        }
    }

    private static String descendantSubtype(PDCIDFont descendant) {
        if (descendant == null) {
            return "NONE";
        }
        if (descendant instanceof PDCIDFontType2) {
            return "CIDFontType2";
        }
        if (descendant instanceof PDCIDFontType0) {
            return "CIDFontType0";
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

    private static int descendantGid(PDCIDFont descendant, int cid)
            throws Exception {
        if (descendant instanceof PDCIDFontType2) {
            return ((PDCIDFontType2) descendant).codeToGID(cid);
        }
        if (descendant instanceof PDCIDFontType0) {
            // PDCIDFontType0 has no public codeToGID; the CFF program treats
            // CID == GID for the embedded charset (Identity ordering).
            return cid;
        }
        return cid;
    }

    /**
     * Resolve the covered character codes from the descendant's /W array.
     * Under Identity-H (the only encoding our Type0 fixtures use) the input
     * code equals the CID, so the /W CIDs ARE the addressable codes. CID 0 is
     * always included. Returns an ascending, de-duplicated list.
     */
    private static List<Integer> coveredCodes(PDCIDFont descendant) {
        List<Integer> codes = new ArrayList<>();
        codes.add(0);
        // Synthetic high CIDs that lie beyond any embedded subset font's
        // glyph count — exercise the codeToGID bound check (out-of-range
        // CID must resolve to GID 0 on an embedded Identity CIDFontType2).
        java.util.TreeSet<Integer> oob = new java.util.TreeSet<>();
        oob.add(60000);
        oob.add(65535);
        if (descendant == null) {
            codes.addAll(oob);
            return codes;
        }
        COSDictionary dict = descendant.getCOSObject();
        COSBase wBase = dict.getDictionaryObject(COSName.W);
        if (!(wBase instanceof COSArray)) {
            return codes;
        }
        COSArray w = (COSArray) wBase;
        java.util.TreeSet<Integer> set = new java.util.TreeSet<>();
        set.add(0);
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
                // Cap the range so a pathological cLast can't explode output.
                int upper = Math.min(cLast, cFirst + 1024);
                for (int c = cFirst; c <= upper; c++) {
                    set.add(c);
                }
                i += 3;
            } else {
                break;
            }
        }
        set.addAll(oob);
        codes.clear();
        codes.addAll(set);
        return codes;
    }
}
