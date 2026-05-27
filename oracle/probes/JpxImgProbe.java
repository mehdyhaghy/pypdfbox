import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import java.util.Iterator;
import javax.imageio.ImageIO;
import javax.imageio.ImageReader;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * Live oracle probe for JPXDecode (JPEG 2000) image decode + colour transform.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> JpxImgProbe input.pdf
 *
 * PDFBox decodes JPEG 2000 through javax.imageio, which requires a registered
 * JPEG2000 ImageReader plugin (JAI Image I/O Tools / openjpeg). The pinned
 * standalone pdfbox-app-3.0.7.jar bundles no such reader. So before touching
 * the document this probe first asks ImageIO whether any "jpeg2000"/"jpx"
 * reader is registered; if none is, it prints a single canonical line:
 *
 *   NO_JPX_READER
 *
 * and exits 0 (the absence of a reader is a finding, not a crash). When a
 * reader IS present, it walks every page's PDResources.getXObjectNames(),
 * and for each PDImageXObject emits one UTF-8 line to stdout:
 *
 *   "jpx page <p> name <name> w <w> h <h> bpc <bpc> cs <colorspace> "
 *     + "grid <256 space-separated ints 0..255>"
 *
 * The grid is a 16x16 average Rec.601 luminance downsample of the fully
 * decoded raster (PDImageXObject.getImage()), row-major, matching
 * JpegImgProbe / CcittImgProbe cell mapping. JPEG 2000 is wavelet/lossy, so
 * the coarse grid + a MAD tolerance survives codec differences while still
 * catching gross divergences (wrong dims, blank decode, channel swap).
 */
public final class JpxImgProbe {
    private static final int GRID = 16;

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");

        if (!hasJpxReader()) {
            out.println("NO_JPX_READER");
            return;
        }

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

    /** True when ImageIO has a registered reader for a JPEG 2000 family type. */
    private static boolean hasJpxReader() {
        String[] keys = {"jpeg2000", "jpeg 2000", "jpx", "jp2", "j2k"};
        for (String k : keys) {
            Iterator<ImageReader> it = ImageIO.getImageReadersByFormatName(k);
            if (it.hasNext()) {
                return true;
            }
            it = ImageIO.getImageReadersByMIMEType("image/" + k);
            if (it.hasNext()) {
                return true;
            }
        }
        return false;
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
        sb.append("jpx page ").append(page)
          .append(" name ").append(name)
          .append(" w ").append(w)
          .append(" h ").append(h)
          .append(" bpc ").append(bpc)
          .append(" cs ").append(cs)
          .append(" grid ").append(grid(img));
        out.println(sb.toString());
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
