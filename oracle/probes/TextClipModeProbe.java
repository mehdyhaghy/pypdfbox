import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: emit a canonical, tolerance-comparable rendering
 * fingerprint for one page of a PDF rendered by Apache PDFBox, dedicated to
 * the text rendering-mode CLIP variants (PDF 32000-1 §9.3.6, Table 106 —
 * ``Tr`` 4/5/6: fill/stroke/fill+stroke that ALSO add the glyph outlines to
 * the clipping path, committed at ``ET``).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextClipModeProbe input.pdf pageIndex
 * Output (UTF-8, to stdout):
 *   line 1: "<width> <height>"  — rendered image pixel dimensions
 *   line 2: 256 comma-separated integers (0..255) — a 16x16 grid of
 *           average luminance per cell, row-major.
 *
 * Output is comma-separated (per the wave-1455 convention) so a probe-name
 * makes the parse format obvious. The luminance math matches
 * ``RenderProbe.java`` / ``ImageMaskProbe.java`` exactly, so swapping probes
 * never changes values; this surface owns a named probe so the clip-mode
 * parity test reads cleanly.
 */
public final class TextClipModeProbe {
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
                    // Rec. 601 luma, matching PIL's "L" conversion weights.
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
