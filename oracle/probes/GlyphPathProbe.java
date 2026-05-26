import java.awt.geom.GeneralPath;
import java.awt.geom.PathIterator;
import java.awt.geom.Rectangle2D;
import java.io.File;
import java.io.PrintStream;
import java.util.LinkedHashSet;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.Type2CharString;
import org.apache.fontbox.ttf.GlyphData;
import org.apache.fontbox.ttf.GlyphTable;
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
 * Live oracle probe: emit Apache PDFBox's per-GID glyph OUTLINE fingerprint
 * straight from the embedded FONT PROGRAM (FontBox), NOT from any rendered
 * raster. Companion to GlyphAdvanceProbe (which covers the advance width);
 * this one covers the glyph PATH.
 *
 * For every embedded font on every page we reach the FontBox program and call
 * the program-native {@code getPath()} which returns a
 * {@link java.awt.geom.GeneralPath}:
 *   - TrueType simple ({@link PDTrueTypeFont}) and CIDFontType2
 *     ({@link PDCIDFontType2}) -> {@code ttf.getGlyph().getGlyph(gid).getPath()}.
 *   - Type1C ({@link PDType1CFont}) and CIDFontType0 ({@link PDCIDFontType0})
 *     -> {@code cff.getType2CharString(gid).getPath()}.
 *
 * The path is fingerprinted in a COORDINATE-TOLERANT but STRUCTURALLY-STRICT
 * way, because exact control-point coordinates can differ by sub-unit rounding
 * between AWT's GeneralPath and any Python path lib:
 *   - the control-point bounding box (4 ints: minX minY maxX maxY, rounded via
 *     Math.round on Rectangle2D from getBounds2D),
 *   - the number of path segments,
 *   - the segment-type sequence (M/L/Q/C/Z) read from the PathIterator.
 *
 * A GeneralPath's PathIterator yields SEG_MOVETO=M, SEG_LINETO=L,
 * SEG_QUADTO=Q, SEG_CUBICTO=C, SEG_CLOSE=Z. The Python side must normalise its
 * own path representation (e.g. fontTools' multi-point qCurveTo, which packs N
 * implied-on-curve quads into one call) down to this same per-quad sequence.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> GlyphPathProbe input.pdf
 *
 * Output (UTF-8, stdout), deterministic line order (page, resource name):
 *   FONT \t pageIndex \t resourceName \t kind \t baseFont
 *   PATH \t gid \t minX \t minY \t maxX \t maxY \t nseg \t typeSeq
 * "kind" is one of TTF / CFF / SKIP(<reason>). For an empty (no-outline) glyph
 * the bbox is "0 0 0 0", nseg "0", typeSeq "" (empty). A GID whose path lookup
 * throws is emitted as bbox "ERR ERR ERR ERR", nseg "ERR", typeSeq "ERR".
 */
public final class GlyphPathProbe {

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
            // to a platform/bundled substitute whose outline isn't
            // deterministic across machines.
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
        if (font instanceof PDType1CFont) {
            CFFFont cff = ((PDType1CFont) font).getCFFType1Font();
            emitCff(out, pageIndex, key, font.getName(), cff);
            return;
        }
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
            out.printf("FONT\t%d\t%s\tSKIP(no-descendant)\t%s%n",
                    pageIndex, key, String.valueOf(font.getName()));
            return;
        }
        out.printf("FONT\t%d\t%s\tSKIP(not-program-font)\t%s%n",
                pageIndex, key, String.valueOf(font.getName()));
    }

    private static void emitTtf(PrintStream out, int pageIndex, String key,
            String baseFont, TrueTypeFont ttf) throws Exception {
        if (ttf == null) {
            out.printf("FONT\t%d\t%s\tSKIP(null-ttf)\t%s%n",
                    pageIndex, key, String.valueOf(baseFont));
            return;
        }
        GlyphTable glyf = ttf.getGlyph();
        int numGlyphs = ttf.getNumberOfGlyphs();
        out.printf("FONT\t%d\t%s\tTTF\t%s%n",
                pageIndex, key, String.valueOf(baseFont));
        for (int gid : gids(numGlyphs)) {
            GeneralPath path = null;
            boolean err = false;
            try {
                GlyphData gd = glyf == null ? null : glyf.getGlyph(gid);
                path = gd == null ? new GeneralPath() : gd.getPath();
            } catch (Exception e) {
                err = true;
            }
            emitPath(out, gid, path, err);
        }
    }

    private static void emitCff(PrintStream out, int pageIndex, String key,
            String baseFont, CFFFont cff) throws Exception {
        if (cff == null) {
            out.printf("FONT\t%d\t%s\tSKIP(null-cff)\t%s%n",
                    pageIndex, key, String.valueOf(baseFont));
            return;
        }
        int numGlyphs = cff.getNumCharStrings();
        out.printf("FONT\t%d\t%s\tCFF\t%s%n",
                pageIndex, key, String.valueOf(cff.getName()));
        for (int gid : gids(numGlyphs)) {
            GeneralPath path = null;
            boolean err = false;
            try {
                Type2CharString cs = cff.getType2CharString(gid);
                path = cs == null ? new GeneralPath() : cs.getPath();
            } catch (Exception e) {
                err = true;
            }
            emitPath(out, gid, path, err);
        }
    }

    /** Emit the coordinate-tolerant, structure-strict fingerprint of a path. */
    private static void emitPath(PrintStream out, int gid, GeneralPath path, boolean err) {
        if (err || path == null) {
            out.printf("PATH\t%d\tERR\tERR\tERR\tERR\tERR\tERR%n", gid);
            return;
        }
        StringBuilder types = new StringBuilder();
        int nseg = 0;
        double[] coords = new double[6];
        PathIterator it = path.getPathIterator(null);
        while (!it.isDone()) {
            int seg = it.currentSegment(coords);
            switch (seg) {
                case PathIterator.SEG_MOVETO:
                    types.append('M');
                    break;
                case PathIterator.SEG_LINETO:
                    types.append('L');
                    break;
                case PathIterator.SEG_QUADTO:
                    types.append('Q');
                    break;
                case PathIterator.SEG_CUBICTO:
                    types.append('C');
                    break;
                case PathIterator.SEG_CLOSE:
                    types.append('Z');
                    break;
                default:
                    types.append('?');
                    break;
            }
            nseg++;
            it.next();
        }
        // Control-point bounding box. getBounds2D() spans every segment
        // coordinate incl. off-curve control points, so the Python side must
        // include control points too. An empty path yields a (0,0,0,0) rect.
        int minX;
        int minY;
        int maxX;
        int maxY;
        if (nseg == 0) {
            minX = 0;
            minY = 0;
            maxX = 0;
            maxY = 0;
        } else {
            Rectangle2D b = path.getBounds2D();
            minX = (int) Math.round(b.getMinX());
            minY = (int) Math.round(b.getMinY());
            maxX = (int) Math.round(b.getMaxX());
            maxY = (int) Math.round(b.getMaxY());
        }
        out.printf("PATH\t%d\t%d\t%d\t%d\t%d\t%d\t%s%n",
                gid, minX, minY, maxX, maxY, nseg, types.toString());
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
