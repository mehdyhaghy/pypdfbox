import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentCatalog;
import org.apache.pdfbox.pdmodel.graphics.optionalcontent.PDOptionalContentProperties;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Live oracle probe: render one page of a PDF that contains optional content
 * (an OCG referenced from a {@code BDC /OC ... EMC} marked-content section
 * and/or from an image/form XObject's {@code /OC} entry) and emit a
 * tolerance-comparable luminance fingerprint. This exercises the RENDER-time
 * visibility gate (PDF 32000-1 §8.11.4 / §11.4): content whose OCG is OFF in
 * the active configuration must NOT be painted; content whose OCG is ON must.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> OptionalContentRenderProbe \
 *        input.pdf pageIndex [ocgNameToForceOn ...]
 *
 * Any OCG names supplied after the page index are force-enabled (set ON in
 * the default /D configuration) before rendering, so one fixture can be
 * rendered in both its as-authored state (no names → render the document's
 * own /D config, typically with the group OFF) and a toggled-ON state
 * (name supplied) without authoring two PDFs. Mirrors the toggle a viewer
 * performs via {@code PDOptionalContentProperties.setGroupEnabled}.
 *
 * Output (UTF-8, to stdout):
 *   line 1: "<width> <height>"  — rendered image pixel dimensions
 *   line 2: 256 comma-separated integers (0..255) — a 16x16 grid of
 *           average luminance per cell, row-major.
 *
 * Luminance math is identical to ImageMaskProbe / RenderProbe so a probe
 * swap can't shift values; this is a dedicated named entry point so the
 * optional-content render-gate surface owns its own probe.
 */
public final class OptionalContentRenderProbe {
    private static final int GRID = 16;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        int page = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            if (args.length > 2) {
                PDDocumentCatalog catalog = doc.getDocumentCatalog();
                PDOptionalContentProperties ocp = catalog.getOCProperties();
                if (ocp != null) {
                    for (int i = 2; i < args.length; i++) {
                        ocp.setGroupEnabled(args[i], true);
                    }
                }
            }
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
