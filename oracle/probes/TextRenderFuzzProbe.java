import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: emit a COARSE painted-region fingerprint for one page of a
 * PDF, rendered by Apache PDFBox, for differential-fuzzing the PageDrawer TEXT
 * rendering surface (PDF 32000-1 §9.3.6 / Table 106 text rendering modes,
 * §9.4.4 text-rendering-matrix application, §9.6.5 Type 3 charproc glyphs).
 *
 * Where ``RenderProbe`` / ``TextClipModeProbe`` project a 16x16 luminance grid,
 * this probe (mirroring ``PageDrawerPathFuzzProbe``) projects only *gross
 * painted-region facts* that survive Java2D-vs-skia anti-aliasing and sub-pixel
 * differences:
 *
 *   line 1: "<width> <height>"  — rendered image pixel dimensions
 *   line 2: "<painted> <minx> <miny> <maxx> <maxy>" where
 *       painted = count of non-white pixels (luma < 250),
 *       (minx,miny)-(maxx,maxy) = inclusive bounding box of painted pixels,
 *       or "0 -1 -1 -1 -1" when nothing was painted.
 *
 * The caller compares painted-region facts with generous tolerances. The real
 * signal this fuzz hunts: text that should paint (modes 0/1/2/4/5/6) must be
 * non-empty on both sides, and text that must NOT paint (mode 3 invisible,
 * mode 7 clip-only with no following fill) must be empty on both sides. Exact
 * pixel counts diverge with AA, so the test buckets the count rather than
 * comparing it exactly.
 *
 * Rendered at a fixed 72 DPI for determinism (1 user unit == 1 px).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextRenderFuzzProbe input.pdf pageIndex
 */
public final class TextRenderFuzzProbe {
    private static final int WHITE_THRESHOLD = 250;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int page = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(page, 72.0f);
            int w = img.getWidth();
            int h = img.getHeight();
            out.println(w + " " + h);

            long painted = 0;
            int minx = -1;
            int miny = -1;
            int maxx = -1;
            int maxy = -1;
            for (int y = 0; y < h; y++) {
                for (int x = 0; x < w; x++) {
                    int rgb = img.getRGB(x, y);
                    int r = (rgb >> 16) & 0xFF;
                    int g = (rgb >> 8) & 0xFF;
                    int b = rgb & 0xFF;
                    // Rec. 601 luma, matching PIL's "L" conversion weights.
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
                    }
                }
            }
            out.println(painted + " " + minx + " " + miny + " " + maxx + " " + maxy);
        }
    }
}
