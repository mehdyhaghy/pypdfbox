import java.awt.geom.GeneralPath;
import java.awt.geom.PathIterator;
import java.awt.geom.Rectangle2D;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.Locale;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.CFFParser;
import org.apache.fontbox.cff.Type2CharString;

/**
 * Live oracle probe for the FontBox CFF *subroutine* glyph-PATH surface — the
 * assembled {@link java.awt.geom.GeneralPath} produced by
 * {@code CFFFont.getType2CharString(gid).getPath()} for a font whose drawing
 * operators live *inside* local ({@code callsubr}) and global
 * ({@code callgsubr}) subroutines, reachable only through the CFF subr *bias*
 * (107 / 1131 / 32768 by INDEX size, Adobe Technote #5176 §16).
 *
 * <p>This is upstream-distinct from {@code CffType2ParseProbe} (which pins the
 * parser's flat token stream): here a wrong bias or broken subr-nesting
 * resolution shows up as a *wrong assembled outline*, so the path fingerprint
 * is the sharper regression pin for the {@code calculateSubrNumber} + recursive
 * {@code callsubr}/{@code callgsubr} inlining path. The companion
 * {@code GlyphPathProbe} walks fonts *through a PDF*; this probe drives a flat
 * {@code .cff} byte file directly so the fixture can be a tiny synthetic font.
 *
 * <pre>
 *   java -cp ... CffSubrPathProbe read &lt;input.cff&gt;
 * </pre>
 *
 * Output (UTF-8, stdout), deterministic GID order:
 *
 *   META \t numGlyphs
 *   PATH \t gid \t minX \t minY \t maxX \t maxY \t nseg \t typeSeq
 *
 * The fingerprint is COORDINATE-TOLERANT but STRUCTURALLY-STRICT, identical to
 * {@code GlyphPathProbe}: the rounded control-point bounding box (from
 * {@code Path2D.getBounds2D}, which evaluates Bezier extrema), the segment
 * count, and the segment-type sequence (M/L/Q/C/Z) from the PathIterator. An
 * empty (no-outline) glyph is "0 0 0 0", nseg "0", typeSeq "". A GID whose
 * path lookup throws is "ERR ERR ERR ERR", nseg "ERR", typeSeq "ERR".
 *
 * Reads a flat .cff byte file only; never mutates anything.
 */
public final class CffSubrPathProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 2 || !"read".equals(args[0])) {
            out.println("usage: CffSubrPathProbe read <input.cff>");
            return;
        }
        read(out, args[1]);
    }

    private static void read(PrintStream out, String cffPath) throws Exception {
        byte[] data = Files.readAllBytes(Paths.get(cffPath));
        CFFFont font = new CFFParser().parse(data, new ByteSource(data)).get(0);
        int numGlyphs = font.getNumCharStrings();
        out.printf(Locale.ROOT, "META\t%d%n", numGlyphs);
        for (int gid = 0; gid < numGlyphs; gid++) {
            GeneralPath path = null;
            boolean err = false;
            try {
                Type2CharString cs = font.getType2CharString(gid);
                path = cs == null ? new GeneralPath() : cs.getPath();
            } catch (Exception e) {
                err = true;
            }
            emitPath(out, gid, path, err);
        }
    }

    private static void emitPath(PrintStream out, int gid, GeneralPath path, boolean err) {
        if (err || path == null) {
            out.printf(Locale.ROOT, "PATH\t%d\tERR\tERR\tERR\tERR\tERR\tERR%n", gid);
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
        out.printf(Locale.ROOT, "PATH\t%d\t%d\t%d\t%d\t%d\t%d\t%s%n",
                gid, minX, minY, maxX, maxY, nseg, types.toString());
    }

    /** Minimal {@code CFFParser.ByteSource} so {@code CFFParser.parse} works. */
    private static final class ByteSource
            implements org.apache.fontbox.cff.CFFParser.ByteSource {
        private final byte[] bytes;

        ByteSource(byte[] bytes) {
            this.bytes = bytes;
        }

        @Override
        public byte[] getBytes() {
            return bytes;
        }
    }
}
