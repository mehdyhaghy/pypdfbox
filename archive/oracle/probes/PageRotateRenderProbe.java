import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.font.PDType1Font;
import org.apache.pdfbox.pdmodel.font.Standard14Fonts;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe for page ``/Rotate`` rasterisation (PDF 32000-1 §7.7.3.3
 * + Apache PDFBox ``PDFRenderer.renderImageWithDPI``).
 *
 * Builds a single in-memory page carrying ONE fixed, deliberately
 * asymmetric content stream (an L-shaped pair of bars anchored at the
 * lower-left plus a line of text near the top) and sets its ``/Rotate`` to
 * the value passed on the command line. Because the content is identical
 * across runs and only ``/Rotate`` changes, the rendered raster is a clean
 * test of the renderer's rotation transform:
 *   - 90 / 270 swap the output width and height,
 *   - the asymmetric content lands in a visibly different place than at 0.
 *
 * The media box is a non-square 200x300 so the width/height swap is
 * observable (square would hide it).
 *
 * The probe also writes the exact PDF bytes it rendered to ``outPdf`` so the
 * paired pytest can render the SAME bytes through pypdfbox — guaranteeing the
 * comparison isolates the renderer's rotation transform rather than any
 * difference in how each side serialises a page.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> PageRotateRenderProbe <rotation> <outPdf>
 * where rotation in {0, 90, 180, 270}.
 *
 * Output (UTF-8, to stdout) — mirrors RenderProbe.java exactly:
 *   line 1: "<width> <height>"  rendered pixel dimensions
 *   line 2: 256 space-separated 16x16 average Rec.601 luminance ints,
 *           row-major.
 */
public final class PageRotateRenderProbe {
    private static final int GRID = 16;
    private static final float W = 200f;
    private static final float H = 300f;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int rotation = Integer.parseInt(args[0]);
        File outPdf = new File(args[1]);
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(W, H));
            page.setRotation(rotation);
            doc.addPage(page);
            try (PDPageContentStream cs =
                    new PDPageContentStream(doc, page)) {
                // Asymmetric L-bar anchored at the lower-left corner: a tall
                // vertical bar and a short horizontal bar. Black on white.
                cs.setNonStrokingColor(0f, 0f, 0f);
                cs.addRect(20f, 20f, 30f, 180f);
                cs.fill();
                cs.addRect(20f, 20f, 120f, 30f);
                cs.fill();
                // A line of text near the top-left, giving an upright cue.
                cs.beginText();
                cs.setFont(new PDType1Font(Standard14Fonts.FontName.HELVETICA), 18f);
                cs.newLineAtOffset(20f, 270f);
                cs.showText("Rotate");
                cs.endText();
            }

            doc.save(outPdf);

            PDFRenderer renderer = new PDFRenderer(doc);
            BufferedImage img = renderer.renderImageWithDPI(0, 72.0f);
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
                    sb.append(' ');
                }
                long avg = cnt[i] > 0 ? Math.round((double) sum[i] / cnt[i]) : 255;
                sb.append(avg);
            }
            out.println(sb.toString());
        }
    }
}
