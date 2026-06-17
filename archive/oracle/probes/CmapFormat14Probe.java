import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.CmapSubtable;
import org.apache.fontbox.ttf.CmapTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;

/**
 * Live oracle probe for the TrueType cmap format-14 (Unicode Variation
 * Sequence) subtable surface in Apache FontBox.
 *
 * Format 14 maps a (base codepoint, variation selector) pair to a glyph id via
 * default-UVS ranges and non-default-UVS records. Crucially, FontBox's
 * {@link CmapSubtable} exposes NO variation-selector lookup API: the public
 * surface is only {@link CmapSubtable#getGlyphId(int)}, which takes a single
 * codepoint. A format-14 subtable therefore cannot contribute to the
 * single-codepoint glyph lookup at all — through the shared API it is inert.
 *
 * This probe loads a font whose cmap carries a format-14 subtable alongside
 * the normal Unicode subtables and emits, per subtable enumerated by
 * {@link CmapTable#getCmaps()}:
 *
 *   SUB   \t index \t platformId \t platformEncodingId
 *   GID   \t index \t codepoint \t getGlyphId(codepoint)
 *
 * The format-14 subtable's GID lines pin its observable contribution to
 * single-codepoint lookup; the BMP subtable's GID lines confirm that the
 * presence of a format-14 subtable does not corrupt the parse of its
 * neighbours.
 *
 * Output: UTF-8, tab-delimited, deterministic (subtables in getCmaps() order,
 * codepoints in fixed order).
 */
public final class CmapFormat14Probe {

    // Base codepoints used in the synthesized format-14 subtable's UVS records,
    // plus a couple of controls. getGlyphId(base) is probed against EVERY
    // subtable so the format-14 subtable's (inert) contribution is explicit.
    private static final int[] CODEPOINTS = {
        0x0041, 0x0042, 0x4E00, 0x6F22, 0xFE00, 0xE0100, 0x20,
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String path = args[0];
        TrueTypeFont ttf = null;
        try {
            ttf = new TTFParser().parse(new RandomAccessReadBufferedFile(new File(path)));
            CmapTable cmap = ttf.getCmap();
            CmapSubtable[] subs = cmap.getCmaps();
            for (int i = 0; i < subs.length; i++) {
                CmapSubtable sub = subs[i];
                out.printf("SUB\t%d\t%d\t%d%n",
                        i, sub.getPlatformId(), sub.getPlatformEncodingId());
                for (int cp : CODEPOINTS) {
                    out.printf("GID\t%d\t%d\t%d%n", i, cp, sub.getGlyphId(cp));
                }
            }
        } finally {
            if (ttf != null) {
                ttf.close();
            }
        }
    }
}
