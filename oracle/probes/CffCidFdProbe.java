import java.awt.geom.GeneralPath;
import java.awt.geom.PathIterator;
import java.io.PrintStream;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.apache.fontbox.cff.CFFCIDFont;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.CFFParser;
import org.apache.fontbox.cff.FDSelect;
import org.apache.fontbox.cff.Type2CharString;

/**
 * Live oracle probe for CID-keyed CFF (CIDFontType0C) /FDSelect + /FDArray
 * font-dict selection. The sibling of {@code CffSubsetProbe} (subset
 * structure) — this one drills into the per-CID FD resolution that
 * {@code CffSubsetProbe} never touches: which font-dict each CID's /FDSelect
 * picks, the per-FD Private DICT widths it selects, and the glyph outline
 * (which exercises the *right* font-dict's local /Subrs via {@code callsubr}).
 *
 * <p>Read mode: parses a raw CFF program (a {@code .cff} byte file — the inner
 * /FontFile3 program, no PDF wrapper) through fontbox {@code CFFParser} and
 * emits canonical, line-oriented, tab-delimited facts that pypdfbox mirrors:
 *
 * <pre>
 *   java -cp ... CffCidFdProbe read &lt;input.cff&gt;
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic order):
 *
 *   META \t numGlyphs \t isCid \t fdSelectFormat \t fdArraySize
 *       fdSelectFormat: 0 or 3 (derived from the FDSelect concrete class);
 *                       -1 when not CID-keyed.
 *       fdArraySize:    /FDArray entry count (via reflection — PDFBox has no
 *                       public CFFCIDFont accessor for it).
 *   FDW \t fdIndex \t defaultWidthX \t nominalWidthX
 *       Per font-dict Private DICT width defaults (reflection).
 *   FD \t gid \t fdIndex
 *       /FDSelect.getFDIndex(gid) for every GID.
 *   WID \t cid \t width
 *       getType2CharString(cid).getWidth() — the advance the per-FD
 *       nominalWidthX path computes. (CID == GID for an Identity-ordered
 *       font; the probe walks CID 0..numGlyphs-1.)
 *   OUT \t cid \t cmdCount \t fingerprint
 *       Glyph outline fingerprint from getType2CharString(cid).getPath():
 *       cmdCount = number of moveto/lineto/curveto/close segments (the
 *       trailing GeneralPath auto-moveto after a close is dropped);
 *       fingerprint = "seg:x,y,...;" for the first few segments, rounded
 *       to integers. This is what proves the local /Subrs index was
 *       resolved in the GID's *own* font-dict.
 *
 * Never mutates anything; reads a flat byte file only.
 */
public final class CffCidFdProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 2 || !"read".equals(args[0])) {
            out.println("usage: CffCidFdProbe read <input.cff>");
            return;
        }
        read(out, args[1]);
    }

    private static void read(PrintStream out, String cffPath) throws Exception {
        byte[] data = Files.readAllBytes(Paths.get(cffPath));
        CFFFont font = new CFFParser().parse(data, new ByteSource(data)).get(0);
        int numGlyphs = font.getNumCharStrings();
        boolean isCid = font instanceof CFFCIDFont;

        if (!isCid) {
            out.printf("META\t%d\t%b\t%d\t%d%n", numGlyphs, false, -1, 0);
            return;
        }

        CFFCIDFont cid = (CFFCIDFont) font;
        FDSelect fdSelect = cid.getFdSelect();
        int fdFormat = fdSelectFormat(fdSelect);
        int fdArraySize = fdArraySize(cid);

        out.printf("META\t%d\t%b\t%d\t%d%n", numGlyphs, true, fdFormat, fdArraySize);

        List<Map<String, Object>> privs = privateDictionaries(cid);
        for (int i = 0; i < privs.size(); i++) {
            Map<String, Object> p = privs.get(i);
            out.printf("FDW\t%d\t%s\t%s%n", i,
                    fmtNum(p.get("defaultWidthX")), fmtNum(p.get("nominalWidthX")));
        }

        for (int gid = 0; gid < numGlyphs; gid++) {
            out.printf("FD\t%d\t%d%n", gid, fdSelect.getFDIndex(gid));
        }

        for (int c = 0; c < numGlyphs; c++) {
            Type2CharString cs = cid.getType2CharString(c);
            out.printf("WID\t%d\t%s%n", c, fmt(cs.getWidth()));
        }

        for (int c = 0; c < numGlyphs; c++) {
            Type2CharString cs = cid.getType2CharString(c);
            out.printf("OUT\t%d\t%s%n", c, fingerprint(cs.getPath()));
        }
    }

    /** "cmdCount\tfingerprint" for a GeneralPath, GeneralPath-quirk-normalised.
     *
     * <p>Java's {@code GeneralPath}, after the *final* SEG_CLOSE of the whole
     * outline, replays one phantom SEG_MOVETO back to the last subpath's start
     * point — fontbox's pen never emits it and neither does pypdfbox's
     * {@code BasePen}. Every other (mid-outline) SEG_MOVETO is a genuine
     * subpath start present in both engines, so we drop *only* a trailing
     * MOVETO that is the very last segment of the iterator. */
    private static String fingerprint(GeneralPath path) {
        PathIterator it = path.getPathIterator(null);
        double[] co = new double[6];
        StringBuilder sb = new StringBuilder();
        int cmds = 0;
        // Pending MOVETO held back one step so we can detect (and drop) a
        // trailing one without dropping legitimate subpath-start movetos.
        boolean havePending = false;
        StringBuilder pending = new StringBuilder();
        while (!it.isDone()) {
            int type = it.currentSegment(co);
            StringBuilder seg = new StringBuilder();
            int n = pointCount(type);
            seg.append(type).append(':');
            for (int k = 0; k < n; k++) {
                seg.append(Math.round(co[k]));
                if (k + 1 < n) {
                    seg.append(',');
                }
            }
            seg.append(';');
            if (havePending) {
                sb.append(pending);
                cmds++;
                havePending = false;
            }
            if (type == PathIterator.SEG_MOVETO) {
                pending = seg;
                havePending = true;
            } else {
                sb.append(seg);
                cmds++;
            }
            it.next();
        }
        // A still-pending MOVETO is the GeneralPath terminal phantom — drop it.
        return cmds + "\t" + sb;
    }

    private static int pointCount(int segType) {
        switch (segType) {
            case PathIterator.SEG_MOVETO:
            case PathIterator.SEG_LINETO:
                return 2;
            case PathIterator.SEG_QUADTO:
                return 4;
            case PathIterator.SEG_CUBICTO:
                return 6;
            default:
                return 0;
        }
    }

    private static int fdSelectFormat(FDSelect fdSelect) {
        String simple = fdSelect.getClass().getSimpleName();
        if (simple.contains("Format0")) {
            return 0;
        }
        if (simple.contains("Format3")) {
            return 3;
        }
        return -1;
    }

    @SuppressWarnings("unchecked")
    private static int fdArraySize(CFFCIDFont cid) throws Exception {
        Field f = CFFCIDFont.class.getDeclaredField("fontDictionaries");
        f.setAccessible(true);
        List<Object> list = (List<Object>) f.get(cid);
        return list == null ? 0 : list.size();
    }

    @SuppressWarnings("unchecked")
    private static List<Map<String, Object>> privateDictionaries(CFFCIDFont cid)
            throws Exception {
        Field f = CFFCIDFont.class.getDeclaredField("privateDictionaries");
        f.setAccessible(true);
        return (List<Map<String, Object>>) f.get(cid);
    }

    private static String fmtNum(Object v) {
        if (v == null) {
            return "0";
        }
        if (v instanceof Number) {
            return fmt(((Number) v).doubleValue());
        }
        return String.valueOf(v);
    }

    private static String fmt(double v) {
        return String.format(Locale.ROOT, "%.4f", v);
    }

    /** Minimal ByteSource backing the raw CFF program. */
    private static final class ByteSource implements CFFParser.ByteSource {
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
