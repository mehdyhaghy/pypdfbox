import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.rendering.ImageType;
import org.apache.pdfbox.rendering.PDFRenderer;

/**
 * Differential-fuzz oracle for Apache PDFBox's {@code PDFToImage} /
 * render-to-image surface, sweeping the CLI option axes a paired test cannot
 * enumerate by hand:
 *
 * <ul>
 *   <li>{@code -dpi} 72 / 150 / 300 plus the "default" 96 (output W/H scale),</li>
 *   <li>{@code -color} RGB / ARGB / GRAY / BINARY (pixel format),</li>
 *   <li>{@code -startPage} / {@code -endPage} in-range, out-of-range, and the
 *       degenerate {@code start > end} window (output image count), and</li>
 *   <li>a rotated ({@code /Rotate 90}) page (output orientation).</li>
 * </ul>
 *
 * <p>Like {@link PdfToImageProbe} this runs the tool's exact per-page loop
 * ({@code renderImageWithDPI(i, dpi, type)} over {@code [startPage-1, min(endPage,
 * pageCount))}) rather than writing image files, so no AWT image codec /
 * headless concern is pulled in. For each combo it emits a STABLE shape:
 *
 * <pre>
 *   case=&lt;label&gt; count=&lt;images&gt;
 *   page=&lt;1-based&gt; &lt;width&gt;x&lt;height&gt; type=&lt;awtType&gt; bands=&lt;n&gt; ink=&lt;bucket&gt;
 *   ...
 * </pre>
 *
 * <p>{@code ink} is a coarse content fingerprint: the count of non-white cells
 * in a 16x16 average-luminance grid (a cell is "ink" when its mean luminance is
 * below 250), bucketed so anti-aliasing jitter never flips a bucket. The paired
 * test compares dimensions + AWT type/bands (mode) + count + ink bucket, NOT
 * exact pixels — AA between Java2D and Pillow differs.
 *
 * <p>Usage: {@code java -cp ... PdfToImageToolFuzzProbe multipage.pdf rotated.pdf}
 *   arg0 = a >=4-page PDF (page-range + DPI + colour cases),
 *   arg1 = a PDF whose page index 1 has {@code /Rotate 90} (orientation case).
 */
public final class PdfToImageToolFuzzProbe {
    private static final int GRID = 16;
    private static final int WHITE_CUTOFF = 250;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File multi = new File(args[0]);
        File rotated = new File(args[1]);
        StringBuilder sb = new StringBuilder();

        try (PDDocument doc = Loader.loadPDF(multi)) {
            PDFRenderer renderer = new PDFRenderer(doc);
            int pages = doc.getNumberOfPages();

            // DPI sweep on the full document (RGB), default 96 included.
            renderWindow(sb, renderer, pages, "dpi72_full", 72f, 1, Integer.MAX_VALUE, ImageType.RGB);
            renderWindow(sb, renderer, pages, "dpi96_full", 96f, 1, Integer.MAX_VALUE, ImageType.RGB);
            renderWindow(sb, renderer, pages, "dpi150_full", 150f, 1, Integer.MAX_VALUE, ImageType.RGB);
            renderWindow(sb, renderer, pages, "dpi300_full", 300f, 1, Integer.MAX_VALUE, ImageType.RGB);

            // Colour / pixel-format sweep on page 1 at 96 DPI.
            renderWindow(sb, renderer, pages, "rgb_p1", 96f, 1, 1, ImageType.RGB);
            renderWindow(sb, renderer, pages, "argb_p1", 96f, 1, 1, ImageType.ARGB);
            renderWindow(sb, renderer, pages, "gray_p1", 96f, 1, 1, ImageType.GRAY);
            renderWindow(sb, renderer, pages, "binary_p1", 96f, 1, 1, ImageType.BINARY);

            // Page-range windows (count contract).
            renderWindow(sb, renderer, pages, "mid_2to3", 96f, 2, 3, ImageType.RGB);
            renderWindow(sb, renderer, pages, "end_clamped_1to99", 96f, 1, 99, ImageType.RGB);
            renderWindow(sb, renderer, pages, "start_oor_50to99", 96f, 50, 99, ImageType.RGB);
            renderWindow(sb, renderer, pages, "start_gt_end_3to2", 96f, 3, 2, ImageType.RGB);
            renderWindow(sb, renderer, pages, "single_last", 96f, pages, pages, ImageType.RGB);

            // Cross axes: DPI x colour on a single page.
            renderWindow(sb, renderer, pages, "gray_p1_300", 300f, 1, 1, ImageType.GRAY);
            renderWindow(sb, renderer, pages, "argb_p1_72", 72f, 1, 1, ImageType.ARGB);
            renderWindow(sb, renderer, pages, "binary_p1_150", 150f, 1, 1, ImageType.BINARY);
        }

        // Rotated page: index 1 carries /Rotate 90 -> W/H swapped in output.
        try (PDDocument doc = Loader.loadPDF(rotated)) {
            PDFRenderer renderer = new PDFRenderer(doc);
            int pages = doc.getNumberOfPages();
            renderWindow(sb, renderer, pages, "rotated_p2_72", 72f, 2, 2, ImageType.RGB);
            renderWindow(sb, renderer, pages, "rotated_p2_150", 150f, 2, 2, ImageType.RGB);
            renderWindow(sb, renderer, pages, "rotated_doc_72", 72f, 1, Integer.MAX_VALUE, ImageType.RGB);
        }

        out.print(sb);
    }

    private static void renderWindow(
            StringBuilder sb, PDFRenderer renderer, int pageCount, String label,
            float dpi, int startPage, int endPage, ImageType type) throws Exception {
        int realEnd = Math.min(endPage, pageCount);
        int count = 0;
        StringBuilder body = new StringBuilder();
        for (int i = startPage - 1; i < realEnd; i++) {
            if (i < 0) {
                continue;
            }
            BufferedImage img = renderer.renderImageWithDPI(i, dpi, type);
            body.append("page=").append(i + 1).append(' ')
                .append(img.getWidth()).append('x').append(img.getHeight())
                .append(" type=").append(img.getType())
                .append(" bands=").append(img.getRaster().getNumBands())
                .append(" ink=").append(inkBucket(img))
                .append('\n');
            count++;
        }
        sb.append("case=").append(label).append(" count=").append(count).append('\n');
        sb.append(body);
    }

    /**
     * Coarse content fingerprint: number of non-white cells in a 16x16
     * average-luminance grid (cell counts as "ink" when its mean luminance is
     * below {@link #WHITE_CUTOFF}). Robust to AA jitter; catches a page that
     * renders blank or grossly different.
     */
    private static int inkBucket(BufferedImage img) {
        int w = img.getWidth();
        int h = img.getHeight();
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
        int ink = 0;
        for (int i = 0; i < GRID * GRID; i++) {
            long avg = cnt[i] > 0 ? Math.round((double) sum[i] / cnt[i]) : 255;
            if (avg < WHITE_CUTOFF) {
                ink++;
            }
        }
        return ink;
    }
}
