import java.awt.geom.GeneralPath;
import java.awt.geom.PathIterator;
import java.awt.geom.Rectangle2D;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Locale;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.Type2CharString;
import org.apache.fontbox.ttf.CFFTable;
import org.apache.fontbox.ttf.OTFParser;
import org.apache.fontbox.ttf.OpenTypeFont;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for OTF/CFF *integration* edge cases that the sibling
 * {@code OtfCffLoadProbe} / {@code OtfCffGlyphAccessProbe} do not cover.
 *
 * <p>Where those probes pin the happy-path load metadata and the renderer
 * glyph-access trio, this probe fuzzes the boundary between the SFNT wrapper
 * ({@link org.apache.fontbox.ttf.OpenTypeFont}) and the embedded
 * {@link org.apache.fontbox.cff.CFFFont}:
 *
 * <ul>
 *   <li>{@code numberOfGlyphs} (from {@code maxp}) vs the CFF charstring count
 *       ({@code CFFFont.getNumCharStrings()}) — they must agree for a
 *       well-formed font;</li>
 *   <li>a GID at exactly the charstring count and a GID far past it — upstream
 *       {@code CFFFont.getType2CharString} clamps an out-of-range GID to the
 *       {@code .notdef} glyph (GID 0) rather than throwing;</li>
 *   <li>the {@code CFF } table presence + {@code CFFTable.getFont().getName()};
 *   </li>
 *   <li>name resolution for a {@code uniXXXX} cmap name vs an unknown name (both
 *       to GIDs, then back through the CFF);</li>
 *   <li>a truncated {@code CFF } table file — the parser's behaviour (throws vs
 *       degrades) is fingerprinted via the {@code mode=truncated} invocation.
 *   </li>
 * </ul>
 *
 * <pre>
 *   java -cp ... OtfCffFuzzProbe read      &lt;input.otf&gt;
 *   java -cp ... OtfCffFuzzProbe truncated &lt;input.otf&gt; &lt;keepBytes&gt;
 * </pre>
 *
 * Output (UTF-8, stdout), deterministic order. {@code read} emits:
 *
 *   META    \t isPostScript \t isSupportedOTF \t numGlyphs \t numCharStrings \t cffName \t hasCFF
 *   GIDPATH \t gid \t name \t nseg \t typeSeq \t minX \t minY \t maxX \t maxY   (per probed GID)
 *   NAME    \t name \t gid \t resolvedName                                       (per probed name)
 *
 * {@code truncated} emits a single:
 *
 *   TRUNC   \t &lt;"PARSE_ERR" | "ok:numGlyphs=N" | "ok:cffNull"&gt;
 *
 * Path fingerprint is the same coordinate-tolerant / structurally-strict shape
 * as the sibling probes. Reads the byte file only; never mutates anything.
 */
public final class OtfCffFuzzProbe {

    /** Names probed for name->gid->CFF resolution (order preserved). */
    private static final String[] NAMES = {
        "uni0041", "uni0042", "uni0020", ".notdef", "bogusName", "",
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length >= 2 && "read".equals(args[0])) {
            read(out, args[1]);
        } else if (args.length >= 3 && "truncated".equals(args[0])) {
            truncated(out, args[1], Integer.parseInt(args[2]));
        } else {
            out.println("usage: OtfCffFuzzProbe read <input.otf> | truncated <input.otf> <keepBytes>");
        }
    }

    private static void read(PrintStream out, String otfPath) throws Exception {
        byte[] data = Files.readAllBytes(Paths.get(otfPath));
        OpenTypeFont otf = new OTFParser().parse(new RandomAccessReadBuffer(data));

        CFFTable cffTable = otf.getCFF();
        CFFFont cff = cffTable == null ? null : cffTable.getFont();

        int numGlyphs = otf.getNumberOfGlyphs();
        int numChar = cff == null ? -1 : cff.getNumCharStrings();
        String cffName = cff == null ? "null" : cff.getName();
        boolean hasCff = cffTable != null;

        out.printf(Locale.ROOT, "META\t%b\t%b\t%d\t%d\t%s\t%b%n",
                otf.isPostScript(), otf.isSupportedOTF(),
                numGlyphs, numChar, cffName, hasCff);

        // Probe GIDs: 0 (.notdef), last valid, exactly-the-count (first OOB),
        // a far OOB GID, and a negative GID.
        int last = numGlyphs - 1;
        int[] gids = {0, last, numGlyphs, numGlyphs + 50, 1000, -1};
        for (int gid : gids) {
            emitGid(out, cff, gid);
        }

        for (String name : NAMES) {
            emitName(out, otf, cff, name);
        }
    }

    private static void truncated(PrintStream out, String otfPath, int keep) throws Exception {
        byte[] full = Files.readAllBytes(Paths.get(otfPath));
        int n = Math.min(keep, full.length);
        byte[] trunc = new byte[n];
        System.arraycopy(full, 0, trunc, 0, n);
        String result;
        try {
            OpenTypeFont otf = new OTFParser().parse(new RandomAccessReadBuffer(trunc));
            CFFTable cffTable = otf.getCFF();
            if (cffTable == null || cffTable.getFont() == null) {
                result = "ok:cffNull";
            } else {
                result = "ok:numGlyphs=" + otf.getNumberOfGlyphs();
            }
        } catch (Exception e) {
            result = "PARSE_ERR";
        }
        out.printf(Locale.ROOT, "TRUNC\t%s%n", result);
    }

    private static void emitName(PrintStream out, OpenTypeFont otf, CFFFont cff, String name)
            throws Exception {
        int gid = otf.nameToGID(name);
        String resolved;
        try {
            Type2CharString cs = cff == null ? null : cff.getType2CharString(gid);
            resolved = cs == null ? "null" : cs.getName();
        } catch (Exception e) {
            resolved = "ERR";
        }
        out.printf(Locale.ROOT, "NAME\t%s\t%d\t%s%n", name, gid, resolved);
    }

    private static void emitGid(PrintStream out, CFFFont cff, int gid) {
        GeneralPath path = null;
        String name = "null";
        boolean err = false;
        try {
            Type2CharString cs = cff == null ? null : cff.getType2CharString(gid);
            if (cs != null) {
                name = cs.getName();
                path = cs.getPath();
            } else {
                path = new GeneralPath();
            }
        } catch (Exception e) {
            err = true;
        }
        emitPath(out, gid, name, path, err);
    }

    private static void emitPath(PrintStream out, int gid, String name, GeneralPath path,
            boolean err) {
        if (err || path == null) {
            out.printf(Locale.ROOT, "GIDPATH\t%d\t%s\tERR\tERR\tERR\tERR\tERR\tERR%n", gid, name);
            return;
        }
        StringBuilder types = new StringBuilder();
        int nseg = 0;
        double[] coords = new double[6];
        PathIterator it = path.getPathIterator(null);
        while (!it.isDone()) {
            switch (it.currentSegment(coords)) {
                case PathIterator.SEG_MOVETO: types.append('M'); break;
                case PathIterator.SEG_LINETO: types.append('L'); break;
                case PathIterator.SEG_QUADTO: types.append('Q'); break;
                case PathIterator.SEG_CUBICTO: types.append('C'); break;
                case PathIterator.SEG_CLOSE: types.append('Z'); break;
                default: types.append('?'); break;
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
        out.printf(Locale.ROOT, "GIDPATH\t%d\t%s\t%d\t%s\t%d\t%d\t%d\t%d%n",
                gid, name, nseg, types.toString(), minX, minY, maxX, maxY);
    }
}
