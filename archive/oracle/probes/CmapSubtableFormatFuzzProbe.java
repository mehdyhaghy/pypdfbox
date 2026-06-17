import java.io.File;
import java.nio.file.Files;
import org.apache.fontbox.ttf.CmapSubtable;
import org.apache.fontbox.ttf.CmapTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.io.RandomAccessReadBuffer;

/**
 * Live oracle probe for the byte-level PARSING of individual TrueType cmap
 * subtable FORMAT bodies (wave 1524 differential fuzz).
 *
 * Where {@code CmapSubtableSelectProbe} pins platform/encoding SELECTION across
 * a multi-subtable font, this probe drives the per-format body reader
 * (processSubtype0/2/4/6/12 in {@link CmapSubtable}) against a font whose cmap
 * table has been surgically replaced with a deliberately MALFORMED subtable
 * body (odd segCountX2, idRangeOffset out of bounds, endCode not 0xFFFF,
 * startCode &gt; endCode, huge entryCount, overlapping format-12 groups,
 * truncated body, unknown format number, etc.).
 *
 * The base font is a real, valid SFNT so {@code TTFParser.parse} reaches cmap
 * parsing normally; only the cmap bytes are hostile. The probe emits a stable
 * projection of the OUTCOME:
 *
 *   ok=true
 *   nsub=<number of parsed subtables>
 *   GID<i>\t<codepoint>\t<gid>     (per subtable, per probe codepoint)
 *
 * or the sole line
 *
 *   ok=false
 *
 * on any throw from parse/cmap-access. The pypdfbox side reproduces this
 * fingerprint exactly so the parity assertion is a single string compare.
 *
 * Usage:
 *   java -cp ... CmapSubtableFormatFuzzProbe font.bin
 */
public final class CmapSubtableFormatFuzzProbe {

    // Codepoint battery spanning byte (format 0/2), BMP (format 4/6) and
    // supplementary-plane (format 12) ranges, plus a couple of out-of-range
    // and surrogate values to stress range checks.
    private static final int[] CODEPOINTS = {
        0x00, 0x20, 0x41, 0x42, 0x43, 0x61, 0x80, 0xFF,
        0x100, 0x1000, 0x4000, 0x4001, 0x4002, 0xABCD,
        0xFFFF, 0x10000, 0x10FFFF, 0x110000,
    };

    public static void main(String[] args) throws Exception {
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
            }
        } catch (Throwable t) {
            System.out.print("ok=false\n");
            return;
        } finally {
            if (ttf != null) {
                ttf.close();
            }
        }
        System.out.print(sb);
    }
}
