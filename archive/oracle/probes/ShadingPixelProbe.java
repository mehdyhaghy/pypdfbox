import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: render one page of a PDF with Apache PDFBox and emit the
 * RGB value at a set of explicit pixel coordinates.
 *
 * Where {@code RenderProbe} downsamples to a 16x16 grayscale grid (which loses
 * colour and exact-pixel detail), this probe answers a sharper question for
 * shading parity: "what colour is the pixel at (x, y)?" — which is exactly what
 * is needed to tell a {@code /Background} fill from a gradient edge, or to
 * verify a radial cone interior/exterior colour at a chosen sample point.
 *
 * Usage:
 *   java ... ShadingPixelProbe input.pdf pageIndex x0 y0 x1 y1 ...
 * Output (UTF-8, to stdout):
 *   line 1: "&lt;width&gt; &lt;height&gt;"            — rendered pixel dimensions
 *   one line per (x, y) pair: "&lt;r&gt; &lt;g&gt; &lt;b&gt;"   — 0..255 per channel
 *
 * Rendered at a fixed 72 DPI for determinism (matches RenderProbe).
 */
public final class ShadingPixelProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int page = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(page, 72.0f);
            int w = img.getWidth();
            int h = img.getHeight();
            out.println(w + " " + h);
            for (int i = 2; i + 1 < args.length; i += 2) {
                int x = Integer.parseInt(args[i]);
                int y = Integer.parseInt(args[i + 1]);
                int cx = Math.max(0, Math.min(w - 1, x));
                int cy = Math.max(0, Math.min(h - 1, y));
                int rgb = img.getRGB(cx, cy);
                int r = (rgb >> 16) & 0xFF;
                int g = (rgb >> 8) & 0xFF;
                int b = rgb & 0xFF;
                out.println(r + " " + g + " " + b);
            }
        }
    }
}
