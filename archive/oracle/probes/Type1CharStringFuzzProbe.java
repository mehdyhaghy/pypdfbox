import java.awt.geom.GeneralPath;
import java.awt.geom.PathIterator;
import java.awt.geom.Rectangle2D;
import java.io.File;
import java.io.FileInputStream;
import java.io.PrintStream;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.List;
import java.util.Map;
import org.apache.fontbox.type1.Type1Font;

/**
 * Live oracle probe for Apache FontBox's Type 1 charstring INTERPRETER — the
 * assembled glyph PATH + advance WIDTH — under MALFORMED / edge-case
 * (post-eexec-decryption) charstring bytecode (wave 1546 differential fuzz).
 *
 * This is the sibling of:
 *   - {@code Type1CharStringInterpFuzzProbe} (which stops at the byte-level
 *     {@code Type1CharStringParser.parse()} token stream), and
 *   - {@code Type1GlyphPathProbe} (which fingerprints WELL-FORMED program
 *     glyphs).
 * It targets the layer in between/after the parser: the
 * {@code Type1CharString.render()} execution that turns the operand+command
 * sequence into a {@link java.awt.geom.GeneralPath} via {@code hsbw} / {@code
 * sbw} (width prologue), {@code rmoveto} / {@code rlineto} / {@code rrcurveto}
 * / {@code closepath} (path ops), {@code seac} (accent composite resolved
 * through the parent {@code Type1Font} as {@code Type1CharStringReader}), the
 * flex / hint-replacement {@code OtherSubrs} (0/1/2/3) machinery, {@code div},
 * {@code callsubr}, and {@code endchar}.
 *
 * Strategy: load a REAL PFB program (so the parent font supplies StandardSubrs
 * for flex/hint and real component glyphs for {@code seac}), then OVERWRITE one
 * glyph's entry in the mutable {@code getCharStringsDict()} (a
 * {@code Map<String, byte[]>}) with the fuzz bytecode, and ask the font for the
 * glyph PATH + WIDTH. This drives the exact same interpreter path a corrupt
 * embedded font would hit, while keeping the surrounding font valid. It mirrors
 * pypdfbox, where the in-memory charstrings dict likewise stores raw bytes and
 * {@code Type1Font.get_path}/{@code get_width} route through the Type 1
 * charstring wrapper.
 *
 * Input: a fuzz-case file, one case per line, fields space-separated:
 *
 *   &lt;label&gt; &lt;charstringHex&gt;
 *
 *   label         - short case id (echoed back verbatim)
 *   charstringHex - hex of the DECRYPTED charstring bytes ("." = empty)
 *
 * Lines starting with '#' or blank lines are skipped.
 *
 * Output (UTF-8, stdout), one line per case, deterministic order (input order):
 *
 *   &lt;label&gt; &lt;minX&gt; &lt;minY&gt; &lt;maxX&gt; &lt;maxY&gt; &lt;nseg&gt; &lt;typeSeq&gt; &lt;width&gt;
 *
 * where (minX..maxY) is the rounded control-point bbox (0 0 0 0 for an empty
 * path), nseg the segment count, typeSeq the M/L/Q/C/Z PathIterator sequence
 * ("-" when empty), and width the integer advance from {@code getWidth}. A
 * throw from {@code getPath} replaces the path fields with
 * "ERR ERR ERR ERR ERR ERR"; a throw from {@code getWidth} sets width to
 * "ERR". The glyph name overwritten is fixed to "C" (so a {@code seac} fuzz
 * case can reference the still-valid base/accent glyphs "A"/"B" without the
 * overwritten glyph recursively composing itself).
 *
 * Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; \
 *            Type1CharStringFuzzProbe font.pfb cases.txt
 */
public final class Type1CharStringFuzzProbe {
    private static final String GLYPH = "C";

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] pfb;
        try (FileInputStream in = new FileInputStream(new File(args[0]))) {
            pfb = in.readAllBytes();
        }
        List<String> lines = Files.readAllLines(
            new File(args[1]).toPath(), StandardCharsets.UTF_8);
        for (String line : lines) {
            String trimmed = line.trim();
            if (trimmed.isEmpty() || trimmed.startsWith("#")) {
                continue;
            }
            String[] parts = trimmed.split("\\s+");
            String label = parts[0];
            byte[] cs = parseHex(parts.length > 1 ? parts[1] : ".");
            out.println(label + " " + run(pfb, cs));
        }
    }

    private static String run(byte[] pfb, byte[] cs) {
        Type1Font t1;
        try {
            // Re-parse per case so the prior case's cache/state can't leak.
            t1 = Type1Font.createWithPFB(pfb);
            // getCharStringsDict() returns an UNMODIFIABLE view, so reach the
            // package-private backing map by reflection to overwrite the glyph.
            Field f = Type1Font.class.getDeclaredField("charstrings");
            f.setAccessible(true);
            @SuppressWarnings("unchecked")
            Map<String, byte[]> map = (Map<String, byte[]>) f.get(t1);
            map.put(GLYPH, cs);
        } catch (Exception e) {
            return "ERR ERR ERR ERR ERR ERR ERR";
        }
        String pathFields;
        try {
            GeneralPath path = t1.getPath(GLYPH);
            pathFields = fingerprint(path);
        } catch (Exception e) {
            pathFields = "ERR ERR ERR ERR ERR ERR";
        }
        String width;
        try {
            float w = t1.getWidth(GLYPH);
            width = String.valueOf(Math.round(w));
        } catch (Exception e) {
            width = "ERR";
        }
        return pathFields + " " + width;
    }

    private static String fingerprint(GeneralPath path) {
        StringBuilder seq = new StringBuilder();
        int nseg = 0;
        PathIterator it = path.getPathIterator(null);
        double[] coords = new double[6];
        while (!it.isDone()) {
            int type = it.currentSegment(coords);
            switch (type) {
                case PathIterator.SEG_MOVETO:
                    seq.append('M');
                    break;
                case PathIterator.SEG_LINETO:
                    seq.append('L');
                    break;
                case PathIterator.SEG_QUADTO:
                    seq.append('Q');
                    break;
                case PathIterator.SEG_CUBICTO:
                    seq.append('C');
                    break;
                case PathIterator.SEG_CLOSE:
                    seq.append('Z');
                    break;
                default:
                    seq.append('?');
                    break;
            }
            nseg++;
            it.next();
        }
        long minX;
        long minY;
        long maxX;
        long maxY;
        if (nseg == 0) {
            minX = 0;
            minY = 0;
            maxX = 0;
            maxY = 0;
        } else {
            Rectangle2D b = path.getBounds2D();
            minX = Math.round(b.getMinX());
            minY = Math.round(b.getMinY());
            maxX = Math.round(b.getMaxX());
            maxY = Math.round(b.getMaxY());
        }
        String typeSeq = seq.length() == 0 ? "-" : seq.toString();
        return minX + " " + minY + " " + maxX + " " + maxY + " " + nseg
            + " " + typeSeq;
    }

    private static byte[] parseHex(String hex) {
        if (hex.equals(".") || hex.isEmpty()) {
            return new byte[0];
        }
        int n = hex.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) {
            b[i] = (byte) Integer.parseInt(hex.substring(i * 2, i * 2 + 2), 16);
        }
        return b;
    }
}
