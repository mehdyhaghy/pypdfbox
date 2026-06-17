import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.ImageType;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: end-to-end COMBINED-page rendering fingerprint, the
 * integration of {@code PDFRenderer.renderImageWithDPI} over a whole page that
 * mixes text + a filled path + a line + (optionally) an inline image + a clip,
 * at various DPI and page {@code /Rotate} values.
 *
 * <p>Where the per-paint-path fuzz probes (text, path, image, shading, tiling)
 * each isolate ONE operator family on an otherwise blank page, this probe is the
 * integration render: a single page assembled from a raw content stream that the
 * paired pytest synthesises identically through pypdfbox, then loaded from disk
 * and rendered by BOTH sides. The page bytes are provided on disk by the test,
 * so the comparison isolates the renderer's whole-page composition rather than
 * any serialisation difference.
 *
 * <p>Pixel-exact parity is impossible (Java2D vs Pillow/skia AA — see
 * {@code test_render_oracle.py} / CHANGES.md), so the projected facts are
 * deliberately COARSE:
 * <ul>
 *   <li>exact rendered pixel dimensions (a mismatch is a real DPI/rotation bug);
 *   <li>the count of non-white pixels (bucketed downstream);
 *   <li>the painted bounding box (compared with generous slop);
 *   <li>four quadrant painted-pixel counts (top-left / top-right /
 *       bottom-left / bottom-right) so a rotation that lands content on the
 *       wrong side is caught even when the global bbox/bucket survive.
 * </ul>
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PageRenderIntegrationFuzzProbe input.pdf pageIndex dpi
 * Output (UTF-8, to stdout):
 *   line 1: "<width> <height>"  rendered pixel dimensions
 *   line 2: 7 space-separated ints:
 *           painted  minx miny maxx maxy
 *           (painted == count of non-white pixels; bbox is -1.. when empty)
 *   line 3: 4 space-separated ints: painted count in quadrants
 *           TL TR BL BR (split at width/2, height/2).
 */
public final class PageRenderIntegrationFuzzProbe {
    private static final int WHITE_THRESHOLD = 250;

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

            long painted = 0;
            int minx = -1;
            int miny = -1;
            int maxx = -1;
            int maxy = -1;
            int halfx = w / 2;
            int halfy = h / 2;
            long tl = 0;
            long tr = 0;
            long bl = 0;
            long br = 0;
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    int rgb = img.getRGB(x, y);
                    int r = (rgb >> 16) & 0xFF;
                    int g = (rgb >> 8) & 0xFF;
                    int b = rgb & 0xFF;
                    int lum = (int) Math.round(0.299 * r + 0.587 * g + 0.114 * b);
                    if (lum < WHITE_THRESHOLD) {
                        painted++;
                        if (minx < 0 || x < minx) {
                            minx = x;
                        }
                        if (miny < 0 || y < miny) {
                            miny = y;
                        }
                        if (x > maxx) {
                            maxx = x;
                        }
                        if (y > maxy) {
                            maxy = y;
                        }
                        boolean left = x < halfx;
                        boolean top = y < halfy;
                        if (top && left) {
                            tl++;
                        } else if (top) {
                            tr++;
                        } else if (left) {
                            bl++;
                        } else {
                            br++;
                        }
                    }
                }
            }
            out.println(painted + " " + minx + " " + miny + " " + maxx + " " + maxy);
            out.println(tl + " " + tr + " " + bl + " " + br);
        }
    }
}
