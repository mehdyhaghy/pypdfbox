import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * Live oracle probe for DCTDecode (JPEG) image decode + colour transform.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> JpegImgProbe input.pdf
 *
 * Walks every page's PDResources.getXObjectNames(), and for each
 * PDImageXObject emits one UTF-8 line to stdout:
 *
 *   "jpeg page <p> name <name> w <w> h <h> bpc <bpc> cs <colorspace> "
 *     + "px <r0,g0,b0;r1,g1,b1;r2,g2,b2;r3,g3,b3> "
 *     + "grid <256 space-separated ints 0..255>"
 *
 * w/h/bpc/cs are exact-match fields read through the public accessors.
 * The grid is a 16x16 average Rec.601 luminance downsample of the fully
 * decoded raster (PDImageXObject.getImage()), row-major, matching
 * ImageExtractProbe / RenderProbe / CcittImgProbe cell mapping. JPEG is
 * lossy + decoder-dependent (Java ImageIO vs Pillow/libjpeg-turbo), so the
 * coarse grid + a tolerance survives codec anti-aliasing while still
 * catching gross divergences (wrong dims, blank decode, inverted CMYK
 * polarity, wrong YCCK/YCbCr transform, channel swap).
 *
 * The four sampled "px" RGB triples are read from fixed fractional
 * positions (top-left, top-right, bottom-left, centre) of the *fully
 * colour-transformed* RGB raster. For a CMYK/YCCK JPEG with the Adobe
 * APP14 transform marker, a polarity inversion flips these far past any
 * lossy-codec tolerance, so they pin the inverted-CMYK trap directly.
 */
public final class JpegImgProbe {
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
                    emit(out, p, name.getName(), (PDImageXObject) xobject);
                }
            }
        }
    }

    private static void emit(PrintStream out, int page, String name,
                             PDImageXObject image) throws Exception {
        int w = image.getWidth();
        int h = image.getHeight();
        int bpc = image.getBitsPerComponent();
        PDColorSpace colorSpace = image.getColorSpace();
        String cs = colorSpace != null ? colorSpace.getName() : "null";

        BufferedImage img = image.getImage();
        StringBuilder sb = new StringBuilder();
        sb.append("jpeg page ").append(page)
          .append(" name ").append(name)
          .append(" w ").append(w)
          .append(" h ").append(h)
          .append(" bpc ").append(bpc)
          .append(" cs ").append(cs)
          .append(" px ").append(samples(img))
          .append(" grid ").append(grid(img));
        out.println(sb.toString());
    }

    /** Four sampled RGB triples (top-left, top-right, bottom-left, centre). */
    private static String samples(BufferedImage img) {
        int w = img.getWidth();
        int h = img.getHeight();
        int[][] pts = {
            {w / 8, h / 8},
            {(w * 7) / 8, h / 8},
            {w / 8, (h * 7) / 8},
            {w / 2, h / 2},
        };
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < pts.length; i++) {
            int x = Math.min(Math.max(pts[i][0], 0), w - 1);
            int y = Math.min(Math.max(pts[i][1], 0), h - 1);
            int rgb = img.getRGB(x, y);
            int r = (rgb >> 16) & 0xFF;
            int g = (rgb >> 8) & 0xFF;
            int b = rgb & 0xFF;
            if (i > 0) {
                sb.append(';');
            }
            sb.append(r).append(',').append(g).append(',').append(b);
        }
        return sb.toString();
    }

    /** 16x16 average-luminance fingerprint of a decoded raster. */
    private static String grid(BufferedImage img) {
        long[] sum = new long[GRID * GRID];
        long[] cnt = new long[GRID * GRID];
        int w = img.getWidth();
        int h = img.getHeight();
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
        return sb.toString();
    }
}
