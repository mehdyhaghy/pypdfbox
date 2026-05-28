import java.io.File;
import java.io.PrintStream;
import java.util.LinkedHashSet;
import org.apache.fontbox.ttf.HorizontalMetricsTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDCIDFontType2;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDTrueTypeFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;

/**
 * Live oracle probe: emit Apache PDFBox's per-GID {@code hmtx} decode straight
 * from the embedded TrueType FONT PROGRAM (FontBox).
 *
 * Companion to GlyphAdvanceProbe, which only covered the advance width
 * ({@code TrueTypeFont.getAdvanceWidth}). This probe targets the
 * {@link HorizontalMetricsTable} directly and emits BOTH the advance width and
 * the LEFT-SIDE BEARING per GID. The interesting parity surface is the
 * trailing-LSB compression: an {@code hmtx} table stores
 * {@code numberOfHMetrics} (advance,LSB) pairs followed by an LSB-only array
 * for the remaining glyphs (which all share the last advance). So
 * {@code getLeftSideBearing(gid)} for {@code gid >= numberOfHMetrics} must read
 * the trailing LSB array, while {@code getAdvanceWidth} clamps to the last
 * advance. We walk GIDs straddling {@code numberOfHMetrics} to exercise both
 * branches plus the out-of-range fallback.
 *
 * Only TrueType programs carry an {@code hmtx} table, so CFF/Type1 fonts are
 * skipped. Only embedded fonts are in scope (a non-embedded font resolves to a
 * platform substitute whose metrics aren't deterministic across machines).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> HmtxLsbProbe input.pdf
 *
 * Output (UTF-8, stdout), deterministic line order (page, resource name):
 *   FONT \t pageIndex \t resourceName \t kind \t baseFont \t numHMetrics \t numGlyphs
 *   HM   \t gid \t advanceWidth \t leftSideBearing      (one line per probed GID)
 * "kind" is one of TTF / SKIP(<reason>). A GID whose lookup throws is emitted
 * with advanceWidth/leftSideBearing "ERR".
 */
public final class HmtxLsbProbe {

    private static final int GID_CAP = 256;
    private static final int[] OOB_GIDS = {60000, 65535};

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
            if (font == null) {
                continue;
            }
            boolean embedded;
            try {
                embedded = font.isEmbedded();
            } catch (Exception e) {
                embedded = false;
            }
            if (!embedded) {
                continue;
            }
            emitFont(out, pageIndex, name.getName(), font);
        }
    }

    private static void emitFont(PrintStream out, int pageIndex, String key, PDFont font)
            throws Exception {
        if (font instanceof PDTrueTypeFont) {
            TrueTypeFont ttf = ((PDTrueTypeFont) font).getTrueTypeFont();
            emitTtf(out, pageIndex, key, font.getName(), ttf);
            return;
        }
        if (font instanceof PDType0Font) {
            PDCIDFont descendant = ((PDType0Font) font).getDescendantFont();
            if (descendant instanceof PDCIDFontType2) {
                TrueTypeFont ttf = ((PDCIDFontType2) descendant).getTrueTypeFont();
                emitTtf(out, pageIndex, key, font.getName(), ttf);
                return;
            }
        }
        out.printf("FONT\t%d\t%s\tSKIP(not-truetype)\t%s\t0\t0%n",
                pageIndex, key, String.valueOf(font.getName()));
    }

    private static void emitTtf(PrintStream out, int pageIndex, String key,
            String baseFont, TrueTypeFont ttf) throws Exception {
        if (ttf == null) {
            out.printf("FONT\t%d\t%s\tSKIP(null-ttf)\t%s\t0\t0%n",
                    pageIndex, key, String.valueOf(baseFont));
            return;
        }
        HorizontalMetricsTable hmtx = ttf.getHorizontalMetrics();
        if (hmtx == null) {
            out.printf("FONT\t%d\t%s\tSKIP(no-hmtx)\t%s\t0\t0%n",
                    pageIndex, key, String.valueOf(baseFont));
            return;
        }
        int numGlyphs = ttf.getNumberOfGlyphs();
        int numHMetrics = ttf.getHorizontalHeader().getNumberOfHMetrics();
        out.printf("FONT\t%d\t%s\tTTF\t%s\t%d\t%d%n",
                pageIndex, key, String.valueOf(baseFont), numHMetrics, numGlyphs);
        for (int gid : gids(numGlyphs, numHMetrics)) {
            String adv;
            String lsb;
            try {
                adv = Integer.toString(hmtx.getAdvanceWidth(gid));
                lsb = Integer.toString(hmtx.getLeftSideBearing(gid));
            } catch (Exception e) {
                adv = "ERR";
                lsb = "ERR";
            }
            out.printf("HM\t%d\t%s\t%s%n", gid, adv, lsb);
        }
    }

    /**
     * GIDs that straddle {@code numHMetrics} so both the in-range pair path and
     * the trailing-LSB-only path are exercised: leading GIDs [0, min(numGlyphs,
     * CAP)), the boundary GIDs (numHMetrics-1, numHMetrics, numHMetrics+1), and
     * synthetic out-of-range GIDs.
     */
    private static int[] gids(int numGlyphs, int numHMetrics) {
        LinkedHashSet<Integer> set = new LinkedHashSet<>();
        int upper = numGlyphs > 0 ? Math.min(numGlyphs, GID_CAP) : 0;
        for (int g = 0; g < upper; g++) {
            set.add(g);
        }
        for (int b : new int[] {numHMetrics - 1, numHMetrics, numHMetrics + 1}) {
            if (b >= 0 && b < numGlyphs) {
                set.add(b);
            }
        }
        for (int g : OOB_GIDS) {
            set.add(g);
        }
        int[] out = new int[set.size()];
        int i = 0;
        for (int g : set) {
            out[i++] = g;
        }
        return out;
    }
}
