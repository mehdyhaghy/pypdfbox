import java.io.File;
import java.io.PrintStream;
import org.apache.fontbox.ttf.CmapSubtable;
import org.apache.fontbox.ttf.CmapTable;
import org.apache.fontbox.ttf.TrueTypeFont;
import org.apache.fontbox.ttf.TTFParser;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDTrueTypeFont;

/**
 * Live oracle probe for TrueType cmap subtable selection + glyph-id resolution.
 *
 * Two modes:
 *
 *   TTF mode  ("ttf" <font.ttf>):
 *     Load the font program directly via FontBox ({@link TTFParser}) and walk
 *     its {@link CmapTable}. For the canonical PDFBox platform/encoding priority
 *     pairs ((3,1) Win-Unicode-BMP, (3,0) Win-Symbol, (1,0) Mac-Roman,
 *     (0,3) Unicode-2.0-BMP, (3,10) Win-Unicode-Full, (0,10) Unicode-2.0-Full)
 *     emit which subtable {@link CmapTable#getSubtable(int,int)} returns
 *     (platform/encoding) and, for a fixed set of codepoints,
 *     {@link CmapSubtable#getGlyphId(int)}. Also report the subtable PDFBox's
 *     own priority resolver picks via {@link TrueTypeFont#getUnicodeCmapLookup}.
 *
 *   PDF mode  ("pdf" <embedding.pdf>):
 *     Load an embedding PDF and, for every simple {@link PDTrueTypeFont}, emit
 *     {@link PDTrueTypeFont#codeToGID(int)} for codes 0..255. This exercises the
 *     symbolic-vs-non-symbolic code->GID resolution incl. the (3,0) F0xx
 *     fallback and the /Encoding glyph-name path.
 *
 * Output: UTF-8, tab-delimited, deterministic line order. Canonical lines:
 *   SUBTABLE \t reqPlat \t reqEnc \t (selPlat|NONE) \t (selEnc|-)
 *   GID      \t reqPlat \t reqEnc \t codepoint \t gid
 *   UNICODE  \t (selPlat|NONE) \t (selEnc|-)
 *   UGID     \t codepoint \t gid          (via the priority Unicode lookup)
 *   FONT     \t pageIndex \t fontKey \t baseFont \t isSymbolic
 *   CGID     \t code \t gid
 */
public final class CmapLookupProbe {

    // PDFBox platform/encoding priority pairs we probe for getSubtable().
    private static final int[][] PAIRS = {
        {CmapTable.PLATFORM_WINDOWS, CmapTable.ENCODING_WIN_UNICODE_BMP},   // (3,1)
        {CmapTable.PLATFORM_WINDOWS, CmapTable.ENCODING_WIN_SYMBOL},        // (3,0)
        {CmapTable.PLATFORM_MACINTOSH, CmapTable.ENCODING_MAC_ROMAN},       // (1,0)
        {CmapTable.PLATFORM_UNICODE, CmapTable.ENCODING_UNICODE_2_0_BMP},   // (0,3)
        {CmapTable.PLATFORM_WINDOWS, CmapTable.ENCODING_WIN_UNICODE_FULL},  // (3,10)
        {CmapTable.PLATFORM_UNICODE, CmapTable.ENCODING_UNICODE_2_0_FULL},  // (0,4)
    };

    // Codepoints probed against each subtable's getGlyphId.
    private static final int[] CODEPOINTS = {
        0x20, 0x41, 0x61, 0x7A, 0x80, 0xE9, 0x2122, 0x20AC, 0x1F600,
        0xF020, 0xF041, 0xF061,
    };

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        String path = args[1];
        if ("ttf".equals(mode)) {
            emitTtf(out, path);
        } else if ("pdf".equals(mode)) {
            emitPdf(out, path);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void emitTtf(PrintStream out, String path) throws Exception {
        TrueTypeFont ttf = null;
        try {
            ttf = new TTFParser().parse(new RandomAccessReadBufferedFile(new File(path)));
            CmapTable cmap = ttf.getCmap();
            for (int[] pair : PAIRS) {
                int reqPlat = pair[0];
                int reqEnc = pair[1];
                CmapSubtable sub = cmap.getSubtable(reqPlat, reqEnc);
                if (sub == null) {
                    out.printf("SUBTABLE\t%d\t%d\tNONE\t-%n", reqPlat, reqEnc);
                    continue;
                }
                out.printf("SUBTABLE\t%d\t%d\t%d\t%d%n",
                        reqPlat, reqEnc,
                        sub.getPlatformId(), sub.getPlatformEncodingId());
                for (int cp : CODEPOINTS) {
                    out.printf("GID\t%d\t%d\t%d\t%d%n",
                            reqPlat, reqEnc, cp, sub.getGlyphId(cp));
                }
            }
            // PDFBox priority Unicode resolver.
            CmapSubtable uni = null;
            try {
                Object lookup = ttf.getUnicodeCmapLookup();
                if (lookup instanceof CmapSubtable) {
                    uni = (CmapSubtable) lookup;
                }
            } catch (Exception e) {
                uni = null;
            }
            if (uni == null) {
                out.printf("UNICODE\tNONE\t-%n");
            } else {
                out.printf("UNICODE\t%d\t%d%n",
                        uni.getPlatformId(), uni.getPlatformEncodingId());
                org.apache.fontbox.ttf.CmapLookup look = ttf.getUnicodeCmapLookup();
                for (int cp : CODEPOINTS) {
                    out.printf("UGID\t%d\t%d%n", cp, look.getGlyphId(cp));
                }
            }
        } finally {
            if (ttf != null) {
                ttf.close();
            }
        }
    }

    private static void emitPdf(PrintStream out, String path) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(path))) {
            int pageIndex = 0;
            for (PDPage page : doc.getPages()) {
                PDResources res = page.getResources();
                if (res != null) {
                    for (COSName name : res.getFontNames()) {
                        PDFont font;
                        try {
                            font = res.getFont(name);
                        } catch (Exception e) {
                            continue;
                        }
                        if (!(font instanceof PDTrueTypeFont)) {
                            continue;
                        }
                        PDTrueTypeFont ttFont = (PDTrueTypeFont) font;
                        boolean symbolic = false;
                        if (font.getFontDescriptor() != null) {
                            symbolic = font.getFontDescriptor().isSymbolic();
                        }
                        out.printf("FONT\t%d\t%s\t%s\t%b%n",
                                pageIndex, name.getName(),
                                String.valueOf(font.getName()), symbolic);
                        for (int code = 0; code < 256; code++) {
                            int gid;
                            try {
                                gid = ttFont.codeToGID(code);
                            } catch (Exception e) {
                                gid = -1;
                            }
                            out.printf("CGID\t%d\t%d%n", code, gid);
                        }
                    }
                }
                pageIndex++;
            }
        }
    }
}
