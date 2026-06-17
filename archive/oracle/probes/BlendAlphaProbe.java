import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: emit a canonical, tolerance-comparable rendering
 * fingerprint for one page of a PDF, rendered by Apache PDFBox, with the
 * blend-mode + constant-alpha (/ca) compositing path exercised by the
 * caller's fixture.
 *
 * This probe exists for the §11.3.6 "Interpretation of Alpha" surface:
 * a coloured top rectangle painted under a non-Normal /BM blend mode AND
 * a /ca < 1.0 non-stroking alpha. Per spec, the result is NOT the pure
 * blend (which the opaque-top oracles in test_blend_mode_oracle.py and
 * test_nonseparable_blend_oracle.py already pin) but a partial mix of the
 * backdrop and the blended colour weighted by the source alpha:
 *
 *   Cr = (1 - as/ar)*Cb + (as/ar)*[(1-ab)*Cs + ab*B(Cb,Cs)]
 *
 * with ab = 1 (opaque backdrop) collapsing to
 *   Cr = (1 - as)*Cb + as*B(Cb,Cs).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> BlendAlphaProbe input.pdf pageIndex
 * Output (UTF-8, to stdout):
 *   line 1: "<width> <height>"  — rendered image pixel dimensions
 *   line 2: 256 comma-separated integers (0..255) — a 16x16 grid of
 *           average luminance per cell, row-major.
 *
 * The luminance computation matches RenderProbe.java / ImageMaskProbe.java
 * exactly; this is a dedicated named entry point so the blend-alpha surface
 * owns a probe of its own (per the wave brief).
 */
public final class BlendAlphaProbe {
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
