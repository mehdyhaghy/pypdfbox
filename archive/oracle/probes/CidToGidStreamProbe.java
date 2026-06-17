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
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Live oracle probe: emit Apache PDFBox's CID -> GID resolution for a
 * CIDFontType2 whose /CIDToGIDMap is a *stream* (a packed big-endian array of
 * 2-byte GIDs indexed by CID — NOT the /Identity shortcut).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> CidToGidStreamProbe input.pdf c0 c1 ...
 *
 * For the (single) Type0/CIDFontType2 on page 0 we emit, for each requested
 * CID/code argument (under Identity-H the input code == CID, so the descendant
 * receives the code as the CID directly), the resolved GID via
 * PDCIDFontType2.codeToGID(cid). A header line reports whether /CIDToGIDMap is a
 * stream or the name /Identity (or absent) plus the embedded program's glyph
 * count. Output is UTF-8, tab-delimited, deterministic:
 *
 *   KIND \t <stream|name:Identity|Identity(absent)> \t <numberOfGlyphs>
 *   GID  \t <cid> \t <gid>      (one per requested cid, in argument order)
 */
public final class CidToGidStreamProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDCIDFontType2 cid2 = firstCidType2(doc);
            if (cid2 == null) {
                out.println("KIND\tNONE\t0");
                return;
            }
            out.printf("KIND\t%s\t%d%n", cidToGidKind(cid2), numberOfGlyphs(cid2));
            for (int i = 1; i < args.length; i++) {
                int cid = Integer.parseInt(args[i]);
                int gid;
                try {
                    gid = cid2.codeToGID(cid);
                } catch (Exception e) {
                    out.printf("GID\t%d\tERR%n", cid);
                    continue;
                }
                out.printf("GID\t%d\t%d%n", cid, gid);
            }
        }
    }

    private static PDCIDFontType2 firstCidType2(PDDocument doc) throws Exception {
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
                if (!(font instanceof PDType0Font)) {
                    continue;
                }
                PDCIDFont descendant = ((PDType0Font) font).getDescendantFont();
                if (descendant instanceof PDCIDFontType2) {
                    return (PDCIDFontType2) descendant;
                }
            }
        }
        return null;
    }

    private static String cidToGidKind(PDCIDFontType2 descendant) {
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

    private static int numberOfGlyphs(PDCIDFontType2 descendant) {
        try {
            if (descendant.getTrueTypeFont() != null) {
                return descendant.getTrueTypeFont().getNumberOfGlyphs();
            }
        } catch (Exception e) {
            // fall through
        }
        return -1;
    }
}
