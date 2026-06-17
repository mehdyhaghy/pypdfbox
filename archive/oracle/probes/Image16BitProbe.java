import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * Live oracle probe for {@code /BitsPerComponent 16} image decode via
 * {@link PDImageXObject#getImage()} (PDF 32000-1 §8.9.5.2). Drives the
 * decode path directly (NOT the page-render pipeline used by
 * {@code RenderProbe} / {@code test_image_16bit_oracle.py}), so the 16-bit
 * → 8-bit down-sampling that PDFBox applies when building the BufferedImage
 * is asserted on its own — free of page-render anti-aliasing, backdrop
 * compositing, and DPI scaling.
 *
 * Apache PDFBox reads big-endian (high byte first) 16-bit samples and, for
 * the 8-bit BufferedImage, takes the HIGH byte of each sample (equivalent to
 * {@code raw >> 8}); a {@code /Decode} array applies at the 16-bit range.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> Image16BitProbe input.pdf
 * Output (UTF-8, to stdout), one line per PDImageXObject found by walking
 * every page's PDResources.getXObjectNames():
 *   "img page <p> name <name> w <w> h <h> "
 *     + "r <256 ints> g <256 ints> b <256 ints>"
 * where each channel is a 16x16 average (0..255), row-major, down-sampled
 * from getImage() with the same integer-division cell mapping as the paired
 * test. Three channels are emitted (DeviceGray decodes to equal R=G=B) so a
 * channel-order bug surfaces directly rather than collapsing into luminance.
 */
public final class Image16BitProbe {
    private static final int GRID = 16;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            int count = doc.getNumberOfPages();
            for (int p = 0; p < count; p++) {
                PDPage page = doc.getPage(p);
                PDResources res = page.getResources();
                if (res == null) {
                    continue;
                }
                for (COSName name : res.getXObjectNames()) {
                    PDXObject xobject = res.getXObject(name);
                    if (!(xobject instanceof PDImageXObject)) {
                        continue;
                    }
                    PDImageXObject image = (PDImageXObject) xobject;
                    emit(out, p, name.getName(), image);
                }
            }
        }
    }

    private static void emit(PrintStream out, int page, String name,
                             PDImageXObject image) throws Exception {
        BufferedImage img = image.getImage();
        int w = img.getWidth();
        int h = img.getHeight();

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
                int r = (rgb >> 16) & 0xFF;
                int g = (rgb >> 8) & 0xFF;
                int b = rgb & 0xFF;
                int idx = cy * GRID + cx;
                sumR[idx] += r;
                sumG[idx] += g;
                sumB[idx] += b;
                cnt[idx] += 1;
            }
        }

        StringBuilder sb = new StringBuilder();
        sb.append("img page ").append(page)
          .append(" name ").append(name)
          .append(" w ").append(w)
          .append(" h ").append(h)
          .append(" r ").append(channel(sumR, cnt))
          .append(" g ").append(channel(sumG, cnt))
          .append(" b ").append(channel(sumB, cnt));
        out.println(sb.toString());
    }

    private static String channel(long[] sum, long[] cnt) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < GRID * GRID; i++) {
            if (i > 0) {
                sb.append(',');
            }
            long avg = cnt[i] > 0 ? Math.round((double) sum[i] / cnt[i]) : 0;
            sb.append(avg);
        }
        return sb.toString();
    }
}
