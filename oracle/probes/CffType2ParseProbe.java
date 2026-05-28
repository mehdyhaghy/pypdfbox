import java.io.PrintStream;
import java.lang.reflect.Method;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.util.List;
import java.util.Locale;
import org.apache.fontbox.cff.CFFFont;
import org.apache.fontbox.cff.CFFParser;
import org.apache.fontbox.cff.CFFType1Font;
import org.apache.fontbox.cff.CharStringCommand;
import org.apache.fontbox.cff.Type2CharStringParser;

/**
 * Live oracle probe for the FontBox {@code Type2CharStringParser} byte-level
 * decoder — the step that turns a raw Type 2 char-string program (plus its
 * global / local /Subrs indexes) into the flat {@code List<Object>} of
 * operands and {@code CharStringCommand}s that {@code Type2CharString} then
 * interprets. This is upstream-distinct from the glyph-PATH / advance-width
 * probes: those pin the *rendered* outcome (a {@code GeneralPath} / a width),
 * while this one pins the *decoder's intermediate token stream* directly:
 *
 *   - operand decoding for every Type 2 number encoding (1-byte 32-246,
 *     2-byte 247-254, the 28 short-int, the 255 16.16 fixed);
 *   - subroutine unrolling (callsubr / callgsubr -> inline the subr bytes,
 *     bias via calculateSubrNumber, trailing RET trimmed);
 *   - hint-mask / cntrmask byte skipping (hstem/vstem/-hm operand counting
 *     drives getMaskLength, which determines how many mask bytes are eaten).
 *
 * <p>{@code Type2CharStringParser.parse(byte[], byte[][], byte[][], String)}
 * is public; the raw char-string bytes come from the public
 * {@code CFFFont.getCharStringBytes()} and the global subrs from
 * {@code getGlobalSubrIndex()}. The per-font local subr index is private
 * ({@code CFFType1Font.getLocalSubrIndex()}) so the probe reaches it by
 * reflection — exactly the data the parser itself feeds at runtime.
 *
 * <pre>
 *   java -cp ... CffType2ParseProbe read &lt;input.cff&gt;
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, deterministic GID order):
 *
 *   META \t numGlyphs \t isType1
 *   GLY \t gid \t tokenCount \t tok0|tok1|tok2|...
 *       tok = an operand (integer as-is; float formatted "%.4f") or a
 *             command mnemonic ("RRCURVETO", "HINTMASK", ...). Joined by
 *             '|'. This is the full unrolled, mask-skipped token stream
 *             pypdfbox's Type2CharStringParser must reproduce verbatim.
 *
 * Reads a flat .cff byte file only; never mutates anything.
 */
public final class CffType2ParseProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 2 || !"read".equals(args[0])) {
            out.println("usage: CffType2ParseProbe read <input.cff>");
            return;
        }
        read(out, args[1]);
    }

    private static void read(PrintStream out, String cffPath) throws Exception {
        byte[] data = Files.readAllBytes(Paths.get(cffPath));
        CFFFont font = new CFFParser().parse(data, new ByteSource(data)).get(0);
        int numGlyphs = font.getNumCharStrings();
        boolean isType1 = font instanceof CFFType1Font;
        out.printf(Locale.ROOT, "META\t%d\t%b%n", numGlyphs, isType1);
        if (!isType1) {
            // This probe pins the name-keyed parser path; CID-keyed FD
            // routing is covered by CffCidFdProbe.
            return;
        }

        CFFType1Font t1 = (CFFType1Font) font;
        List<byte[]> charStrings = font.getCharStringBytes();
        List<byte[]> gsubrList = font.getGlobalSubrIndex();
        byte[][] gsubr = gsubrList.toArray(new byte[0][]);
        byte[][] lsubr = localSubrIndex(t1);

        Type2CharStringParser parser = new Type2CharStringParser(font.getName());
        for (int gid = 0; gid < numGlyphs; gid++) {
            byte[] cs = charStrings.get(gid);
            List<Object> seq = parser.parse(cs, gsubr, lsubr, "gid" + gid);
            StringBuilder sb = new StringBuilder();
            for (int k = 0; k < seq.size(); k++) {
                if (k > 0) {
                    sb.append('|');
                }
                sb.append(token(seq.get(k)));
            }
            out.printf(Locale.ROOT, "GLY\t%d\t%d\t%s%n", gid, seq.size(), sb);
        }
    }

    /** Canonical token for one parsed sequence entry. */
    private static String token(Object o) {
        if (o instanceof CharStringCommand) {
            CharStringCommand c = (CharStringCommand) o;
            // CharStringCommand.toString() is "<keyword>|"; the keyword is the
            // stable mnemonic both engines share. Strip the trailing '|'.
            String s = c.toString();
            if (s.endsWith("|")) {
                s = s.substring(0, s.length() - 1);
            }
            return s;
        }
        if (o instanceof Integer) {
            return Integer.toString((Integer) o);
        }
        if (o instanceof Number) {
            return String.format(Locale.ROOT, "%.4f", ((Number) o).doubleValue());
        }
        return String.valueOf(o);
    }

    private static byte[][] localSubrIndex(CFFType1Font t1) throws Exception {
        Method m = CFFType1Font.class.getDeclaredMethod("getLocalSubrIndex");
        m.setAccessible(true);
        Object v = m.invoke(t1);
        return v == null ? new byte[0][] : (byte[][]) v;
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
