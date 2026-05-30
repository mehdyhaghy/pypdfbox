import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.ImageType;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe for Apache PDFBox's DPI -> pixel-size scaling, the exact
 * arithmetic behind {@code PDFRenderer.renderImageWithDPI} and the
 * {@code PDFToImage -dpi} CLI flag.
 *
 * <p>Unlike {@link PdfToImageProbe} (which takes an {@code int} DPI and emits
 * only dimensions for a page subset), this probe renders ONE page at an
 * arbitrary {@code float} DPI and emits both the rendered dimensions and a
 * 16x16 average-luminance fingerprint, so a paired test can pin:
 *
 * <ul>
 *   <li>the {@code pts * (dpi/72f)} single-precision floor that decides the
 *       raster width/height (the float32-vs-double boundary: an A4 841.92 pt
 *       page at 150 DPI is 1753 px in float, 1754 in double), and</li>
 *   <li>that the painted content still matches within the whole-page AA gate
 *       at that DPI.</li>
 * </ul>
 *
 * Usage: java -cp ... RenderDpiProbe input.pdf pageIndex dpi
 * Output (UTF-8, to stdout):
 *   line 1: "&lt;width&gt; &lt;height&gt;"  — rendered image pixel dimensions
 *   line 2: 256 space-separated integers (0..255) — 16x16 luminance grid.
 */
public final class RenderDpiProbe {
    private static final int GRID = 16;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int page = Integer.parseInt(args[1]);
        float dpi = Float.parseFloat(args[2]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(page, dpi, ImageType.RGB);
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
