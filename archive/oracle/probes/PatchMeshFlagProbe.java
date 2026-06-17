import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: emit a per-channel RGB rendering fingerprint for one
 * page of a PDF, rendered by Apache PDFBox.
 *
 * Targeted at Type 6 (Coons) / Type 7 (tensor) patch-mesh shadings that use
 * flag-driven edge sharing (flags 1/2/3) — a topology in which a patch
 * inherits four boundary control points and two corner colours from the
 * previous patch (PDF 32000-1 §8.7.4.5.7-8). The existing mesh oracle pins
 * only a single free (flag 0) patch via a luminance grid; this probe isolates
 * (a) the flag-continuation decode (a hole / wrong-edge bug leaves a region
 * blank or misplaced) and (b) the per-channel bilinear colour interpolation
 * across the patch (an R<->B swap leaves luminance almost unchanged but
 * diverges sharply per channel).
 *
 * Output is identical in shape to MeshGouraudFlagProbe so the same parsing
 * applies; a dedicated probe name keeps the patch-mesh surface obvious.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> PatchMeshFlagProbe input.pdf pageIndex
 * Output (UTF-8, to stdout):
 *   line 1: "<width> <height>"  — rendered image pixel dimensions
 *   line 2: 256 ints (0..255) — 16x16 grid of average RED   per cell, row-major
 *   line 3: 256 ints (0..255) — 16x16 grid of average GREEN per cell, row-major
 *   line 4: 256 ints (0..255) — 16x16 grid of average BLUE  per cell, row-major
 *
 * Rendered at a fixed 72 DPI for determinism.
 */
public final class PatchMeshFlagProbe {
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

            long[] sumR = new long[GRID * GRID];
            long[] sumG = new long[GRID * GRID];
            long[] sumB = new long[GRID * GRID];
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
                    int idx = cy * GRID + cx;
                    sumR[idx] += (rgb >> 16) & 0xFF;
                    sumG[idx] += (rgb >> 8) & 0xFF;
                    sumB[idx] += rgb & 0xFF;
                    cnt[idx] += 1;
                }
            }
            emit(out, sumR, cnt);
            emit(out, sumG, cnt);
            emit(out, sumB, cnt);
        }
    }

    private static void emit(PrintStream out, long[] sum, long[] cnt) {
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
