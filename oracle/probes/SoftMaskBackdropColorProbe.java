import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: emit a canonical, tolerance-comparable rendering
 * fingerprint for one page of a PDF rendered by Apache PDFBox, exercising
 * the ExtGState ``/SMask`` luminosity soft-mask ``/BC`` (backdrop colour)
 * surface (PDF 32000-1 §11.6.5.2).
 *
 * The interesting behaviour this probe pins: a luminosity ``/SMask`` may
 * declare a ``/BC`` backdrop colour. A naive reader could expect a white
 * ``/BC`` to make the mask fully OPAQUE (luminance 1 → alpha 1) everywhere
 * the mask group does not paint — opening the masked paint across the whole
 * page — and a black ``/BC`` to make it fully transparent. In Apache
 * PDFBox 3.0.7 that is NOT what happens: PageDrawer.TransparencyGroup fills
 * the group buffer with ``/BC`` (``clearRect``) but then removes that
 * backdrop contribution (``GroupGraphics.removeBackdrop``) before the
 * luminosity mask is taken, so the mask alpha is the group result modulated
 * by the group's own COVERAGE. An area the mask group never paints
 * contributes mask alpha 0 (the page backdrop shows through) regardless of
 * the ``/BC`` luminance — white-``/BC`` and black-``/BC`` renders are
 * identical for these fixtures.
 *
 * The companion test renders the same fixture with ``/BC`` white vs black
 * and asserts both match this oracle (and each other) within the established
 * MAD/MAXDIFF gate.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SoftMaskBackdropColorProbe input.pdf pageIndex
 * Output (UTF-8, to stdout):
 *   line 1: "<width> <height>"  — rendered image pixel dimensions
 *   line 2: 256 comma-separated integers (0..255) — a 16x16 grid of
 *           average luminance per cell, row-major.
 *
 * Luminance math is identical to ``SoftMaskBBoxProbe.java`` / ``RenderProbe.java``
 * (Rec. 601 luma, matching PIL's "L" conversion) so a probe swap can't drift
 * the values; this is a dedicated entry point so the ``/BC`` surface owns a
 * named probe.
 */
public final class SoftMaskBackdropColorProbe {
    private static final int GRID = 16;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int page = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
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
                    sb.append(',');
                }
                long avg = cnt[i] > 0 ? Math.round((double) sum[i] / cnt[i]) : 255;
                sb.append(avg);
            }
            out.println(sb.toString());
        }
    }
}
