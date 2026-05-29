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
 * Unlike RenderProbe (which collapses each cell to a single Rec.601 luminance
 * value), this probe emits three separate channel grids so a colour-only
 * divergence — e.g. an R<->B channel swap in a Gouraud triangle mesh, which
 * leaves luminance almost unchanged — is caught. This pins the colour
 * interpolation of Type 4 free-form Gouraud meshes that use flag 1 / flag 2
 * vertex continuation (triangle strip / fan), a topology the luminance-only
 * mesh oracle does not isolate.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> MeshGouraudFlagProbe input.pdf pageIndex
 * Output (UTF-8, to stdout):
 *   line 1: "<width> <height>"  — rendered image pixel dimensions
 *   line 2: 256 ints (0..255) — 16x16 grid of average RED   per cell, row-major
 *   line 3: 256 ints (0..255) — 16x16 grid of average GREEN per cell, row-major
 *   line 4: 256 ints (0..255) — 16x16 grid of average BLUE  per cell, row-major
 *
 * Rendered at a fixed 72 DPI for determinism.
 */
public final class MeshGouraudFlagProbe {
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
