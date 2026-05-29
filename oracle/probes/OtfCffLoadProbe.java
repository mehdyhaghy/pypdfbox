import java.awt.geom.GeneralPath;
import java.awt.geom.PathIterator;
import java.awt.geom.Rectangle2D;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.Type2CharString;
import org.apache.fontbox.ttf.CFFTable;
import org.apache.fontbox.ttf.OTFParser;
import org.apache.fontbox.ttf.OpenTypeFont;
import org.apache.fontbox.ttf.TTFTable;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for the FontBox OpenType (sfnt-wrapped CFF) LOADING surface:
 * an OTF font whose scaler type is {@code OTTO} and whose outlines live in a
 * {@code CFF } table. Drives {@link org.apache.fontbox.ttf.OTFParser} the way a
 * caller reaching {@code otf.getCFF().getFont()} would, and fingerprints the
 * font-level metadata plus a handful of CFF glyph outlines.
 *
 * <pre>
 *   java -cp ... OtfCffLoadProbe read &lt;input.otf&gt;
 * </pre>
 *
 * Output (UTF-8, stdout), deterministic order:
 *
 *   META   \t isPostScript \t isSupportedOTF \t numGlyphs \t unitsPerEm \t cffName
 *   TABLES \t tag,tag,tag,...                              (sorted, comma-joined)
 *   GLYPH  \t name \t gid \t advance \t minX \t minY \t maxX \t maxY \t nseg \t typeSeq
 *
 * The GLYPH lines drive the outline through {@code getCFF().getFont()} —
 * resolving the glyph name to a GID and assembling the Type 2 charstring path —
 * which is the OTF/CFF loading path under test (distinct from the flat-.cff
 * probes which never touch the sfnt wrapper). The path fingerprint is the same
 * coordinate-tolerant / structurally-strict shape as {@code GlyphPathProbe}:
 * the rounded curve bounding box, the segment count, and the M/L/Q/C/Z type
 * sequence. An empty glyph is "0 0 0 0", nseg "0", typeSeq "".
 *
 * Reads the OTF byte file only; never mutates anything.
 */
public final class OtfCffLoadProbe {

    /** Glyph names probed for outlines (order preserved). */
    private static final String[] GLYPH_NAMES = {".notdef", "A", "B", "space"};

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 2 || !"read".equals(args[0])) {
            out.println("usage: OtfCffLoadProbe read <input.otf>");
            return;
        }
        read(out, args[1]);
    }

    private static void read(PrintStream out, String otfPath) throws Exception {
        byte[] data = Files.readAllBytes(Paths.get(otfPath));
        OpenTypeFont otf = new OTFParser().parse(new RandomAccessReadBuffer(data));

        CFFTable cffTable = otf.getCFF();
        CFFFont cff = cffTable == null ? null : cffTable.getFont();

        String cffName = cff == null ? "null" : cff.getName();
        out.printf(Locale.ROOT, "META\t%b\t%b\t%d\t%d\t%s%n",
                otf.isPostScript(), otf.isSupportedOTF(),
                otf.getNumberOfGlyphs(), otf.getUnitsPerEm(), cffName);

        List<String> tags = new ArrayList<>();
        for (TTFTable t : otf.getTables()) {
            tags.add(t.getTag());
        }
        Collections.sort(tags);
        out.printf(Locale.ROOT, "TABLES\t%s%n", String.join(",", tags));

        for (String name : GLYPH_NAMES) {
            emitGlyph(out, otf, cff, name);
        }

        // Direct-GID outlines straight through the embedded CFFFont — exercises
        // the CFF glyph-assembly path independent of name resolution, so a real
        // outline divergence is caught even when a synthetic font's post/cmap
        // can't map a name to its drawn glyph.
        int numGlyphs = otf.getNumberOfGlyphs();
        for (int gid = 0; gid < numGlyphs; gid++) {
            emitGid(out, cff, gid);
        }
    }

    private static void emitGid(PrintStream out, CFFFont cff, int gid) {
        GeneralPath path = null;
        boolean err = false;
        try {
            Type2CharString cs = cff == null ? null : cff.getType2CharString(gid);
            path = cs == null ? new GeneralPath() : cs.getPath();
        } catch (Exception e) {
            err = true;
        }
        emitPath(out, "GID:" + gid, gid, 0, path, err);
    }

    private static void emitGlyph(PrintStream out, OpenTypeFont otf, CFFFont cff, String name)
            throws Exception {
        int gid = otf.nameToGID(name);
        int advance = otf.getAdvanceWidth(gid);
        GeneralPath path = null;
        boolean err = false;
        try {
            Type2CharString cs = cff == null ? null : cff.getType2CharString(gid);
            path = cs == null ? new GeneralPath() : cs.getPath();
        } catch (Exception e) {
            err = true;
        }
        emitPath(out, name, gid, advance, path, err);
    }

    private static void emitPath(PrintStream out, String name, int gid, int advance,
            GeneralPath path, boolean err) {
        if (err || path == null) {
            out.printf(Locale.ROOT, "GLYPH\t%s\t%d\t%d\tERR\tERR\tERR\tERR\tERR\tERR%n",
                    name, gid, advance);
            return;
        }
        StringBuilder types = new StringBuilder();
        int nseg = 0;
        double[] coords = new double[6];
        PathIterator it = path.getPathIterator(null);
        while (!it.isDone()) {
            switch (it.currentSegment(coords)) {
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
        out.printf(Locale.ROOT, "GLYPH\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s%n",
                name, gid, advance, minX, minY, maxX, maxY, nseg, types.toString());
    }
}
