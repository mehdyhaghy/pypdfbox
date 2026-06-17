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
 * Live oracle probe for the image-XObject {@code /SMask} (a separate grayscale
 * image giving per-pixel alpha for the base image, PDF 32000-1 §8.9.5.4).
 *
 * Distinct from the ExtGState {@code /SMask} and from the explicit {@code /Mask}
 * stencil: here we drive {@link PDImageXObject#getImage()}, which on Apache
 * PDFBox returns an ARGB image with the {@code /SMask} composited as the alpha
 * channel (the soft mask is upscaled to the base image's dimensions when its
 * own dims differ, and its {@code /Decode} array is honoured). We emit the full
 * RGBA fingerprint — not just luminance — so the alpha plane derived from the
 * SMask is asserted directly (a renderer that ignored the SMask would emit
 * alpha 255 everywhere and diverge grossly on the A channel).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> ImageSoftMaskProbe input.pdf
 * Output (UTF-8, to stdout), one line per PDImageXObject found by walking
 * every page's PDResources.getXObjectNames():
 *   "smask page <p> name <name> w <w> h <h> "
 *     + "r <256 ints> g <256 ints> b <256 ints> a <256 ints>"
 * where each channel is a 16x16 average (0..255), row-major, downsampled from
 * getImage() with the same integer-division cell mapping as RenderProbe.java.
 */
public final class ImageSoftMaskProbe {
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
        boolean hasAlpha = img.getColorModel().hasAlpha();

        long[] sumR = new long[GRID * GRID];
        long[] sumG = new long[GRID * GRID];
        long[] sumB = new long[GRID * GRID];
        long[] sumA = new long[GRID * GRID];
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
                int argb = img.getRGB(x, y);
                int a = hasAlpha ? ((argb >> 24) & 0xFF) : 255;
                int r = (argb >> 16) & 0xFF;
                int g = (argb >> 8) & 0xFF;
                int b = argb & 0xFF;
                int idx = cy * GRID + cx;
                sumR[idx] += r;
                sumG[idx] += g;
                sumB[idx] += b;
                sumA[idx] += a;
                cnt[idx] += 1;
            }
        }

        StringBuilder sb = new StringBuilder();
        sb.append("smask page ").append(page)
          .append(" name ").append(name)
          .append(" w ").append(w)
          .append(" h ").append(h)
          .append(" r ").append(channel(sumR, cnt))
          .append(" g ").append(channel(sumG, cnt))
          .append(" b ").append(channel(sumB, cnt))
          .append(" a ").append(channel(sumA, cnt));
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
