import java.io.File;
import java.io.PrintStream;
import java.util.LinkedHashSet;
import java.util.List;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.Type2CharString;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDCIDFont;
import org.apache.pdfbox.pdmodel.font.PDCIDFontType0;
import org.apache.pdfbox.pdmodel.font.PDCIDFontType2;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDTrueTypeFont;
import org.apache.pdfbox.pdmodel.font.PDType0Font;
import org.apache.pdfbox.pdmodel.font.PDType1CFont;

/**
 * Live oracle probe: emit Apache PDFBox's per-GID advance width straight from
 * the embedded FONT PROGRAM (FontBox), NOT from the PDF /Widths array.
 *
 * For every embedded font on every page we reach the FontBox program:
 *   - TrueType simple ({@link PDTrueTypeFont}) and CIDFontType2
 *     ({@link PDCIDFontType2}) -> {@link TrueTypeFont#getAdvanceWidth(int)}
 *     (font design units) and {@link TrueTypeFont#getUnitsPerEm()}.
 *   - Type1C ({@link PDType1CFont}) and CIDFontType0 ({@link PDCIDFontType0})
 *     -> {@link CFFFont}, advance via the charstring width
 *     ({@code getType2CharString(gid).getWidth()}); unitsPerEm derived from the
 *     CFF FontMatrix x-scale (round(1/matrix[0])).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> GlyphAdvanceProbe input.pdf
 *
 * Output (UTF-8, stdout), deterministic line order (page, resource name):
 *   FONT \t pageIndex \t resourceName \t kind \t baseFont \t unitsPerEm
 *   ADV  \t gid \t advanceWidth        (one line per probed GID)
 * Advance widths are emitted as integers (font design units). "kind" is one of
 * TTF / CFF / SKIP(<reason>). Each font's GIDs are deduplicated and ascending.
 * A GID whose width lookup throws is emitted with advanceWidth "ERR".
 */
public final class GlyphAdvanceProbe {

    // Cap how many leading GIDs we walk so a huge program can't explode output;
    // plus a couple of synthetic out-of-range GIDs to exercise the bound path.
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
            // Only embedded programs are in scope: a non-embedded font resolves
            // to a platform/bundled substitute whose metrics aren't deterministic
            // across machines. Skip those silently so the parity is over the
            // embedded FONT PROGRAM, never a fallback.
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
        // TrueType simple font.
        if (font instanceof PDTrueTypeFont) {
            TrueTypeFont ttf = ((PDTrueTypeFont) font).getTrueTypeFont();
            emitTtf(out, pageIndex, key, font.getName(), ttf);
            return;
        }
        // Type1C (CFF) simple font.
        if (font instanceof PDType1CFont) {
            CFFFont cff = ((PDType1CFont) font).getCFFType1Font();
            emitCff(out, pageIndex, key, font.getName(), cff);
            return;
        }
        // Type0 composite -> descendant CIDFont -> embedded program.
        if (font instanceof PDType0Font) {
            PDCIDFont descendant = ((PDType0Font) font).getDescendantFont();
            if (descendant instanceof PDCIDFontType2) {
                TrueTypeFont ttf = ((PDCIDFontType2) descendant).getTrueTypeFont();
                emitTtf(out, pageIndex, key, font.getName(), ttf);
                return;
            }
            if (descendant instanceof PDCIDFontType0) {
                CFFFont cff = ((PDCIDFontType0) descendant).getCFFFont();
                emitCff(out, pageIndex, key, font.getName(), cff);
                return;
            }
            out.printf("FONT\t%d\t%s\tSKIP(no-descendant)\t%s\t0%n",
                    pageIndex, key, String.valueOf(font.getName()));
            return;
        }
        // Any other font type has no embedded TrueType/CFF program in scope.
        out.printf("FONT\t%d\t%s\tSKIP(not-program-font)\t%s\t0%n",
                pageIndex, key, String.valueOf(font.getName()));
    }

    private static void emitTtf(PrintStream out, int pageIndex, String key,
            String baseFont, TrueTypeFont ttf) throws Exception {
        if (ttf == null) {
            out.printf("FONT\t%d\t%s\tSKIP(null-ttf)\t%s\t0%n",
                    pageIndex, key, String.valueOf(baseFont));
            return;
        }
        int upem = ttf.getUnitsPerEm();
        int numGlyphs = ttf.getNumberOfGlyphs();
        out.printf("FONT\t%d\t%s\tTTF\t%s\t%d%n",
                pageIndex, key, String.valueOf(baseFont), upem);
        for (int gid : gids(numGlyphs)) {
            String adv;
            try {
                adv = String.valueOf(ttf.getAdvanceWidth(gid));
            } catch (Exception e) {
                adv = "ERR";
            }
            out.printf("ADV\t%d\t%s%n", gid, adv);
        }
    }

    private static void emitCff(PrintStream out, int pageIndex, String key,
            String baseFont, CFFFont cff) throws Exception {
        if (cff == null) {
            out.printf("FONT\t%d\t%s\tSKIP(null-cff)\t%s\t0%n",
                    pageIndex, key, String.valueOf(baseFont));
            return;
        }
        int upem = cffUnitsPerEm(cff);
        int numGlyphs = cff.getNumCharStrings();
        out.printf("FONT\t%d\t%s\tCFF\t%s\t%d%n",
                pageIndex, key, String.valueOf(cff.getName()), upem);
        for (int gid : gids(numGlyphs)) {
            String adv;
            try {
                Type2CharString cs = cff.getType2CharString(gid);
                adv = String.valueOf(cs.getWidth());
            } catch (Exception e) {
                adv = "ERR";
            }
            out.printf("ADV\t%d\t%s%n", gid, adv);
        }
    }

    /** unitsPerEm from the CFF FontMatrix x-scale: round(1 / matrix[0]). */
    private static int cffUnitsPerEm(CFFFont cff) {
        try {
            List<Number> m = cff.getFontMatrix();
            if (m != null && !m.isEmpty()) {
                double scale = m.get(0).doubleValue();
                if (scale != 0.0) {
                    return (int) Math.round(1.0 / scale);
                }
            }
        } catch (Exception e) {
            // fall through
        }
        return 1000;
    }

    /** Leading GIDs [0, min(numGlyphs, CAP)) plus synthetic out-of-range GIDs. */
    private static int[] gids(int numGlyphs) {
        LinkedHashSet<Integer> set = new LinkedHashSet<>();
        int upper = numGlyphs > 0 ? Math.min(numGlyphs, GID_CAP) : 0;
        for (int g = 0; g < upper; g++) {
            set.add(g);
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
