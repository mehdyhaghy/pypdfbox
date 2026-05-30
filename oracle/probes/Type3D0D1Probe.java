import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe for the Type 3 glyph-procedure metric operators
 * {@code d0} (SetCharWidth, coloured glyph) and {@code d1}
 * (SetCharWidthAndBoundingBox, uncoloured-mask glyph), focused on the
 * colour-handling distinction PDF 32000-1 §9.6.5.3 mandates:
 *
 *   - a {@code d1} glyph is an uncoloured mask: any colour-setting operator
 *     inside the charproc (rg / g / k / sc / scn / cs ...) is IGNORED, and the
 *     glyph paints in the surrounding text-state non-stroking colour;
 *   - a {@code d0} glyph is coloured: it paints with its own colour operators.
 *
 * Apache PDFBox enforces this via
 * {@code PDFStreamEngine.isShouldProcessColorOperators()} returning {@code false}
 * while a {@code d1} charproc is processed. A luminance-only fingerprint cannot
 * tell red from green (similar luma), so this probe emits a coarse RGB grid:
 * the page is rendered at 72 DPI, and for each of GRID*GRID cells the mean
 * R, G, B over that cell is emitted. The Python side reproduces the same
 * grid from its own render and compares per-channel with a tolerance that
 * survives anti-aliasing while catching a wrong d0/d1 colour decision.
 *
 * Output (UTF-8, to stdout):
 *   line 1: "<width> <height>"
 *   line 2: GRID*GRID*3 space-separated ints (0..255), row-major, R G B per
 *           cell.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Type3D0D1Probe input.pdf
 */
public final class Type3D0D1Probe {
    private static final int GRID = 8;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            BufferedImage img = new PDFRenderer(doc).renderImageWithDPI(0, 72.0f);
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
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < GRID * GRID; i++) {
                long c = cnt[i] > 0 ? cnt[i] : 1;
                if (i > 0) {
                    sb.append(' ');
                }
                sb.append(Math.round((double) sumR[i] / c)).append(' ');
                sb.append(Math.round((double) sumG[i] / c)).append(' ');
                sb.append(Math.round((double) sumB[i] / c));
            }
            out.println(sb.toString());
        }
    }
}
