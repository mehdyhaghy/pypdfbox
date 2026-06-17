import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.font.PDFont;
import org.apache.pdfbox.pdmodel.font.PDTrueTypeFont;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe for **symbolic** simple-TrueType code-&gt;GID resolution
 * (PDF 32000-1 §9.6.6.4) plus the rendered raster fingerprint.
 *
 * A symbolic TrueType simple font (descriptor /Flags bit 3 set) commonly ships
 * with only a (3,0) Windows-Symbol cmap or a (1,0) Mac-Roman cmap (or no usable
 * cmap at all). PDFBox's {@code PDTrueTypeFont.codeToGID} fallback chain for the
 * symbolic case is, in order:
 *   1. (3,1) Win-Unicode via the WinAnsi/MacRoman encoding glyph name, else the
 *      raw code, when a (3,1) subtable is present;
 *   2. (3,0) Win-Symbol with the raw code, then 0xF000+code, then 0xF100+code,
 *      then 0xF200+code;
 *   3. (1,0) Mac-Roman with the raw code.
 * When none of those resolve {@code codeToGID} returns 0 (.notdef) — there is no
 * "code is the glyph id" fallback inside {@code codeToGID} itself; an embedded
 * symbolic font with no usable cmap renders .notdef.
 *
 * Modes:
 *   "gid" &lt;embedding.pdf&gt;:
 *     for every simple {@link PDTrueTypeFont} on every page emit
 *     {@link PDTrueTypeFont#codeToGID(int)} for codes 0..255.
 *   "render" &lt;embedding.pdf&gt; &lt;pageIndex&gt;:
 *     render the page at 72 DPI and emit the same 16x16 luminance grid as
 *     {@code RenderProbe} so the resolved glyphs' raster can be compared.
 *
 * Output: UTF-8, tab/space-delimited, deterministic line order.
 *   FONT \t pageIndex \t fontKey \t baseFont \t isSymbolic
 *   CGID \t code \t gid
 *   (render mode) line 1 "&lt;w&gt; &lt;h&gt;", line 2 256 ints.
 */
public final class SymbolicTtfProbe {

    private static final int GRID = 16;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("gid".equals(mode)) {
            emitGid(out, args[1]);
        } else if ("render".equals(mode)) {
            emitRender(out, args[1], Integer.parseInt(args[2]));
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void emitGid(PrintStream out, String path) throws Exception {
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

    private static void emitRender(PrintStream out, String path, int page)
            throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(path))) {
            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(page, 72.0f);
            int w = img.getWidth();
            int h = img.getHeight();
            out.println(w + " " + h);
            long[] sum = new long[GRID * GRID];
            long[] cnt = new long[GRID * GRID];
            for (int y = 0; y < h; y++) {
                int cy = (int) ((long) y * GRID / h);
                if (cy >= GRID) {
                    cy = GRID - 1;
                }
                for (int x = 0; x < w; x++) {
                    int cx = (int) ((long) x * GRID / w);
                    if (cx >= GRID) {
                        cx = GRID - 1;
                    }
                    int rgb = img.getRGB(x, y);
                    int r = (rgb >> 16) & 0xFF;
                    int g = (rgb >> 8) & 0xFF;
                    int b = rgb & 0xFF;
                    int lum = (int) Math.round(0.299 * r + 0.587 * g + 0.114 * b);
                    int idx = cy * GRID + cx;
                    sum[idx] += lum;
                    cnt[idx] += 1;
                }
            }
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < GRID * GRID; i++) {
                if (i > 0) {
                    sb.append(' ');
                }
                long avg = cnt[i] > 0 ? Math.round((double) sum[i] / cnt[i]) : 255;
                sb.append(avg);
            }
            out.println(sb.toString());
        }
    }
}
