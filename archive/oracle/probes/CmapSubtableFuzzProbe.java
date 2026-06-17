import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.util.List;
import org.apache.fontbox.ttf.CmapSubtable;
import org.apache.fontbox.ttf.CmapTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for the TrueType cmap subtable REVERSE-lookup surface
 * (wave 1542 differential fuzz).
 *
 * Where {@code CmapSubtableFormatFuzzProbe} (wave 1524) pins the FORWARD
 * {@code getGlyphId(codepoint)} projection across malformed subtable bodies,
 * this probe drives the inverse direction — {@code getCharCodes(gid)} — plus
 * the formats that wave 1524 did NOT exercise:
 *
 *   * format 13 (many-to-one): every code in a group maps to one gid, so the
 *     reverse map for that gid must list ALL codes (the multi-mapping path);
 *   * format 0 / 4 / 6 / 12 reverse maps, including the multi-mapping sentinel
 *     case where several codes collide on one gid;
 *   * the "no mapping" reverse case (gid past the end of the reverse array)
 *     which must return null, not throw.
 *
 * The base font is a real, valid SFNT (DejaVuSans re-serialised through
 * fontTools on the pypdfbox side) whose {@code cmap} table has been surgically
 * replaced with a deliberately hostile subtable body. The probe emits, on a
 * successful parse:
 *
 *   ok=true
 *   nsub=&lt;number of parsed subtables&gt;
 *   GID&lt;i&gt;\t&lt;codepoint&gt;\t&lt;getGlyphId(cp)&gt;        (forward, per subtable)
 *   CC&lt;i&gt;\t&lt;gid&gt;\t&lt;getCharCodes(gid) joined by ','&gt; (reverse, per subtable)
 *
 * where a null reverse result is rendered as the literal "null" and an empty
 * list as "" (PDFBox never returns an empty list, but the renderer is explicit
 * so any divergence shows). On any throw from parse/cmap access the sole line
 *
 *   ok=false
 *
 * is emitted. The pypdfbox reproducer renders the identical fingerprint, so the
 * parity assertion is a single string compare.
 *
 * Usage:
 *   java -cp ... CmapSubtableFuzzProbe font.bin
 */
public final class CmapSubtableFuzzProbe {

    // Forward-lookup codepoint battery: byte (format 0), BMP (format 4/6),
    // supplementary plane (format 12/13), plus boundary + out-of-range values.
    private static final int[] CODEPOINTS = {
        0x00, 0x20, 0x41, 0x42, 0x43, 0x44, 0x45, 0x61, 0xFF,
        0x100, 0x4E00, 0xFFFF, 0x10000, 0x1F600, 0x10FFFF, 0x110000,
    };

    // Reverse-lookup gid battery: small gids that the hostile bodies populate,
    // plus a gid well past the end (must yield null, not an exception).
    private static final int[] GIDS = {
        0, 1, 2, 3, 4, 5, 6, 7, 8, 20, 21, 22, 100, 65535, 70000,
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File file = new File(args[0]);
        byte[] bytes = Files.readAllBytes(file.toPath());

        StringBuilder sb = new StringBuilder();
        TrueTypeFont ttf = null;
        try {
            ttf = new TTFParser().parse(new RandomAccessReadBuffer(bytes));
            CmapTable cmap = ttf.getCmap();
            CmapSubtable[] subs = (cmap == null)
                    ? new CmapSubtable[0] : cmap.getCmaps();
            sb.append("ok=true\n");
            sb.append("nsub=").append(subs.length).append('\n');
            for (int i = 0; i < subs.length; i++) {
                CmapSubtable sub = subs[i];
                for (int cp : CODEPOINTS) {
                    int gid;
                    try {
                        gid = sub.getGlyphId(cp);
                    } catch (Throwable t) {
                        gid = -1;
                    }
                    sb.append("GID").append(i).append('\t')
                      .append(cp).append('\t').append(gid).append('\n');
                }
                for (int g : GIDS) {
                    String rendered;
                    try {
                        List<Integer> codes = sub.getCharCodes(g);
                        rendered = renderCodes(codes);
                    } catch (Throwable t) {
                        rendered = "throw";
                    }
                    sb.append("CC").append(i).append('\t')
                      .append(g).append('\t').append(rendered).append('\n');
                }
            }
        } catch (Throwable t) {
            out.print("ok=false\n");
            return;
        } finally {
            if (ttf != null) {
                ttf.close();
            }
        }
        out.print(sb);
    }

    private static String renderCodes(List<Integer> codes) {
        if (codes == null) {
            return "null";
        }
        StringBuilder b = new StringBuilder();
        for (int k = 0; k < codes.size(); k++) {
            if (k > 0) {
                b.append(',');
            }
            b.append(codes.get(k).intValue());
        }
        return b.toString();
    }
}
