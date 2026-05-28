import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import java.util.Iterator;
import javax.imageio.ImageIO;
import javax.imageio.ImageReader;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * Live oracle probe for /SMaskInData (PDF 32000-1 §8.9.7.5, Table 89).
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> SMaskInDataProbe input.pdf
 *
 * For every PDImageXObject across every page, this probe emits one UTF-8
 * stdout line of the shape:
 *
 *   "smid page <p> name <name> w <w> h <h> bpc <bpc> "
 *     + "accessor <int> raw <int> filter <name-or-null>"
 *
 * accessor = the dict-level integer at COSName "SMaskInData", read directly
 *            from the image's COS dictionary (default 0 when absent). PDFBox
 *            3.0.7's PDImageXObject has NO public getSMaskInData() accessor —
 *            it reads the entry inline inside getImage() to forward through
 *            DecodeResult.getJPXSMask(). So the "accessor" parity target on
 *            the Java side IS the raw COS read; pypdfbox's
 *            PDImageXObject.get_smask_in_data() is a forward-compat addition
 *            mirroring the *Apache PDFBox trunk* getter that wraps the same
 *            lookup, and must agree with this number bit-for-bit.
 *
 * raw     = same number again, re-read independently via the same COS path,
 *           kept in the line so any future divergence between an accessor and
 *           the underlying dict (e.g. if a later PDFBox release adds clamping)
 *           is visible in probe output.
 *
 * filter  = COSName.FILTER's name as a string ("JPXDecode" for a single JPX
 *           filter), or "null" if absent. /SMaskInData is JPX-only per the
 *           spec; emitting the filter lets the test assert the JPX-ness on the
 *           Java side too.
 *
 * No raster is emitted: PDFBox's standalone 3.0.7 app jar bundles no
 * JPEG 2000 ImageReader (see JpxImgProbe), so PDImageXObject.getImage() on a
 * JPX stream would throw — and there is no Java raster to differential a
 * pypdfbox raster against in any case. This probe deliberately scopes to the
 * accessor + dict-level read, which is what /SMaskInData semantically *is*
 * (a hint to the decoder; the renderer ignores it unless it can decode JPX
 * alpha samples). When a JPX reader IS registered, the probe additionally
 * appends " grid <256 ints>" so the test can compare 16x16 luminance.
 */
public final class SMaskInDataProbe {
    private static final int GRID = 16;
    private static final COSName SMASK_IN_DATA = COSName.getPDFName("SMaskInData");

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        boolean hasReader = hasJpxReader();

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
                    emit(out, p, name.getName(), (PDImageXObject) xobject, hasReader);
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
                             PDImageXObject image, boolean hasReader) throws Exception {
        int w = image.getWidth();
        int h = image.getHeight();
        int bpc = image.getBitsPerComponent();
        int accessor = image.getCOSObject().getInt(SMASK_IN_DATA, 0);
        int raw = image.getCOSObject().getInt(SMASK_IN_DATA, 0);
        COSBase filterObj = image.getCOSObject().getDictionaryObject(COSName.FILTER);
        String filterName;
        if (filterObj instanceof COSName) {
            filterName = ((COSName) filterObj).getName();
        } else if (filterObj instanceof COSArray) {
            StringBuilder fs = new StringBuilder("[");
            COSArray arr = (COSArray) filterObj;
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    fs.append(',');
                }
                COSBase entry = arr.getObject(i);
                fs.append(entry instanceof COSName ? ((COSName) entry).getName() : "?");
            }
            fs.append(']');
            filterName = fs.toString();
        } else {
            filterName = "null";
        }

        StringBuilder sb = new StringBuilder();
        sb.append("smid page ").append(page)
          .append(" name ").append(name)
          .append(" w ").append(w)
          .append(" h ").append(h)
          .append(" bpc ").append(bpc)
          .append(" accessor ").append(accessor)
          .append(" raw ").append(raw)
          .append(" filter ").append(filterName);

        if (hasReader) {
            // Best-effort raster: only attempted when a JPEG 2000 ImageReader is
            // registered. PDFBox decodes JPX via javax.imageio; without a plugin
            // this would throw and there'd be no raster to compare anyway.
            try {
                BufferedImage img = image.getImage();
                sb.append(" grid ").append(grid(img));
            } catch (Exception ignored) {
                sb.append(" grid none");
            }
        } else {
            sb.append(" grid none");
        }
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
