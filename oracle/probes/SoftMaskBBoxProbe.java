import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: emit a canonical, tolerance-comparable rendering
 * fingerprint for one page of a PDF rendered by Apache PDFBox, exercising
 * the ExtGState ``/SMask`` luminosity soft-mask path where the mask
 * transparency-group's ``/BBox`` is SMALLER than the region the masked
 * paint covers (PDF 32000-1 §11.6.5.2 / §11.6.5.3).
 *
 * The interesting behaviour: outside the mask group's /BBox, the soft-mask
 * value is the backdrop colour ``/BC`` (for /Luminosity, default 0 = black),
 * NOT "uncovered → alpha 0". PDFBox's SoftMask renders the mask group into a
 * buffer sized to the group bbox and returns the backdrop colour for any
 * sample outside that buffer; so with /BC [1] (white) the masked paint is
 * FULLY VISIBLE everywhere outside the mask group's small bbox.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SoftMaskBBoxProbe input.pdf pageIndex
 * Output (UTF-8, to stdout):
 *   line 1: "<width> <height>"  — rendered image pixel dimensions
 *   line 2: 256 comma-separated integers (0..255) — a 16x16 grid of
 *           average luminance per cell, row-major.
 *
 * Luminance math is identical to ``ImageMaskProbe.java`` / ``RenderProbe.java``
 * (Rec. 601 luma, matching PIL's "L" conversion) so a probe swap can't drift
 * the values; this is a dedicated entry point so the soft-mask-bbox surface
 * owns a named probe (per the wave 1455 brief).
 */
public final class SoftMaskBBoxProbe {
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
