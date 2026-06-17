import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.CmapSubtable;
import org.apache.fontbox.ttf.CmapTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;

/**
 * Live oracle probe for TrueType cmap subtable SELECTION (platform/encoding
 * preference order when a font has multiple subtables) and format-4 segment
 * lookup including a code that falls in a segment GAP (-> GID 0).
 *
 * Loads a TTF directly via FontBox ({@link TTFParser}) and emits, in a
 * deterministic order:
 *
 *   CMAPS    \t count                                 (number of subtables)
 *   CMAP     \t index \t platformId \t platformEncodingId  (directory order)
 *   GET      \t reqPlat \t reqEnc \t (selPlat|NONE) \t (selEnc|-)
 *                                                     (CmapTable.getSubtable)
 *   UNICODE  \t (selPlat|NONE) \t (selEnc|-)          (priority resolver pick)
 *   GID      \t reqPlat \t reqEnc \t codepoint \t gid (per-subtable getGlyphId)
 *   UGID     \t codepoint \t gid                      (priority Unicode lookup)
 *
 * Probed against EVERY subtable actually present (so a multi-cmap font reports
 * each subtable's getGlyphId), plus the canonical PDFBox priority pairs for the
 * getSubtable() resolver. The codepoint battery deliberately includes a value
 * that sits in a format-4 segment gap to confirm the GID-0 fallback.
 */
public final class CmapSubtableSelectProbe {

    // Canonical PDFBox platform/encoding priority pairs for getSubtable().
    private static final int[][] PAIRS = {
        {CmapTable.PLATFORM_UNICODE, CmapTable.ENCODING_UNICODE_2_0_FULL}, // (0,4)
        {CmapTable.PLATFORM_WINDOWS, CmapTable.ENCODING_WIN_UNICODE_FULL}, // (3,10)
        {CmapTable.PLATFORM_UNICODE, CmapTable.ENCODING_UNICODE_2_0_BMP},  // (0,3)
        {CmapTable.PLATFORM_WINDOWS, CmapTable.ENCODING_WIN_UNICODE_BMP},  // (3,1)
        {CmapTable.PLATFORM_WINDOWS, CmapTable.ENCODING_WIN_SYMBOL},       // (3,0)
        {CmapTable.PLATFORM_MACINTOSH, CmapTable.ENCODING_MAC_ROMAN},      // (1,0)
        {CmapTable.PLATFORM_UNICODE, CmapTable.ENCODING_UNICODE_1_1},      // (0,1)
    };

    // Codepoint battery. 0x4002 and 0xABCD are chosen to fall in a segment GAP
    // in the synthetic format-4 cmaps the test builds (-> GID 0).
    private static final int[] CODEPOINTS = {
        0x00, 0x20, 0x41, 0x42, 0x43, 0x61, 0x7A, 0x80, 0xE9,
        0x4000, 0x4001, 0x4002, 0x4003, 0x4004,
        0xABCD, 0x2122, 0x20AC, 0xF041, 0xFFFF,
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String path = args[0];
        TrueTypeFont ttf = null;
        try {
            ttf = new TTFParser().parse(
                    new RandomAccessReadBufferedFile(new File(path)));
            CmapTable cmap = ttf.getCmap();
            CmapSubtable[] subs = cmap.getCmaps();
            out.printf("CMAPS\t%d%n", subs.length);
            for (int i = 0; i < subs.length; i++) {
                out.printf("CMAP\t%d\t%d\t%d%n",
                        i, subs[i].getPlatformId(),
                        subs[i].getPlatformEncodingId());
            }
            for (int[] pair : PAIRS) {
                int reqPlat = pair[0];
                int reqEnc = pair[1];
                CmapSubtable sub = cmap.getSubtable(reqPlat, reqEnc);
                if (sub == null) {
                    out.printf("GET\t%d\t%d\tNONE\t-%n", reqPlat, reqEnc);
                } else {
                    out.printf("GET\t%d\t%d\t%d\t%d%n",
                            reqPlat, reqEnc,
                            sub.getPlatformId(), sub.getPlatformEncodingId());
                }
            }
            // Per-subtable getGlyphId for every subtable present.
            for (int i = 0; i < subs.length; i++) {
                CmapSubtable sub = subs[i];
                for (int cp : CODEPOINTS) {
                    out.printf("GID\t%d\t%d\t%d\t%d%n",
                            sub.getPlatformId(), sub.getPlatformEncodingId(),
                            cp, sub.getGlyphId(cp));
                }
            }
            // Priority Unicode resolver.
            CmapSubtable uni = null;
            try {
                org.apache.fontbox.ttf.CmapLookup lookup = ttf.getUnicodeCmapLookup();
                if (lookup instanceof CmapSubtable) {
                    uni = (CmapSubtable) lookup;
                }
                if (uni != null) {
                    out.printf("UNICODE\t%d\t%d%n",
                            uni.getPlatformId(), uni.getPlatformEncodingId());
                    for (int cp : CODEPOINTS) {
                        out.printf("UGID\t%d\t%d%n", cp, lookup.getGlyphId(cp));
                    }
                } else {
                    out.printf("UNICODE\tNONE\t-%n");
                }
            } catch (Exception e) {
                out.printf("UNICODE\tNONE\t-%n");
            }
        } finally {
            if (ttf != null) {
                ttf.close();
            }
        }
    }
}
