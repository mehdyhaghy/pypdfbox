import java.awt.image.BufferedImage;
import java.io.File;
import java.io.PrintStream;
import javax.imageio.ImageIO;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.PDResources;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.graphics.PDXObject;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.image.JPEGFactory;
import org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * Live oracle probe: exercise Apache PDFBox's image-XObject ENCODE side
 * (JPEGFactory / LosslessFactory create an image XObject FROM a raster).
 *
 * Two subcommands:
 *
 *   make <png> <out.pdf>
 *     Loads the PNG into a BufferedImage and builds two image XObjects via
 *     the upstream factories on the SAME source raster:
 *       page 0 : JPEGFactory.createFromImage(...)      -> /DCTDecode
 *       page 1 : LosslessFactory.createFromImage(...)   -> /FlateDecode
 *     Each XObject is placed on its own page (scaled to a 200x200 box) and the
 *     document is saved. The PNG should be RGBA so the lossless factory exercises
 *     the /SMask alpha-extraction path.
 *
 *   read <pdf>
 *     Walks every page's PDResources.getXObjectNames() and, for each
 *     PDImageXObject, emits ONE line:
 *       "image page <p> name <n> filter <F> cs <CS> w <w> h <h> bpc <b>
 *          smask <0|1> grid <256 ints>"
 *     where:
 *       filter = raw /Filter name from the COS stream (DCTDecode / FlateDecode /
 *                CCITTFaxDecode ...), "none" if absent.
 *       cs     = resolved getColorSpace().getName().
 *       smask  = 1 when the /SMask entry is present, else 0.
 *       grid   = 16x16 average Rec.601 luminance fingerprint of getImage(),
 *                matching RenderProbe.java's cell mapping.
 *
 * Pixel-exact parity across Java2D vs Pillow is impossible, so the coarse grid
 * survives codec sub-pixel / anti-aliasing differences while still catching
 * gross divergences (wrong dims, blank decode, channel swap, dropped alpha).
 */
public final class ImageEncodeProbe {
    private static final int GRID = 16;

    public static void main(String[] args) throws Exception {
        String cmd = args[0];
        if ("make".equals(cmd)) {
            make(args[1], args[2]);
        } else if ("read".equals(cmd)) {
            read(args[1]);
        } else {
            throw new IllegalArgumentException("unknown command: " + cmd);
        }
    }

    private static void make(String pngPath, String outPath) throws Exception {
        BufferedImage raster = ImageIO.read(new File(pngPath));
        try (PDDocument doc = new PDDocument()) {
            // page 0: JPEG-encoded (/DCTDecode)
            PDImageXObject jpeg = JPEGFactory.createFromImage(doc, raster);
            placeOnPage(doc, jpeg);
            // page 1: lossless (/FlateDecode, with /SMask for the alpha)
            PDImageXObject lossless = LosslessFactory.createFromImage(doc, raster);
            placeOnPage(doc, lossless);
            doc.save(new File(outPath));
        }
    }

    private static void placeOnPage(PDDocument doc, PDImageXObject image) throws Exception {
        PDPage page = new PDPage(new PDRectangle(0, 0, 200, 200));
        doc.addPage(page);
        try (PDPageContentStream cs =
                new PDPageContentStream(doc, page)) {
            cs.drawImage(image, 10, 10, 180, 180);
        }
    }

    private static void read(String pdfPath) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(pdfPath))) {
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

        COSStream stream = image.getCOSObject();
        String filter = filterName(stream.getDictionaryObject(COSName.FILTER));
        int smask = stream.getDictionaryObject(COSName.SMASK) != null ? 1 : 0;

        BufferedImage img = image.getImage();
        StringBuilder sb = new StringBuilder();
        sb.append("image page ").append(page)
          .append(" name ").append(name)
          .append(" filter ").append(filter)
          .append(" cs ").append(cs)
          .append(" w ").append(w)
          .append(" h ").append(h)
          .append(" bpc ").append(bpc)
          .append(" smask ").append(smask)
          .append(" grid ").append(grid(img));
        out.println(sb.toString());
    }

    /** Resolve a /Filter entry (name or single-element array) to a string. */
    private static String filterName(COSBase value) {
        if (value instanceof COSName) {
            return ((COSName) value).getName();
        }
        if (value instanceof COSArray) {
            COSArray arr = (COSArray) value;
            if (arr.size() == 1 && arr.get(0) instanceof COSName) {
                return ((COSName) arr.get(0)).getName();
            }
            StringBuilder sb = new StringBuilder("[");
            for (int i = 0; i < arr.size(); i++) {
                if (i > 0) {
                    sb.append(',');
                }
                COSBase e = arr.get(i);
                sb.append(e instanceof COSName ? ((COSName) e).getName() : "?");
            }
            return sb.append(']').toString();
        }
        return "none";
    }

    /**
     * 16x16 average-luminance fingerprint of a decoded raster.
     *
     * The pixel is composited over an opaque WHITE backdrop using its alpha
     * channel before luma is taken. This matters for the soft-mask cases:
     * getImage() returns ARGB whose colour samples under a fully-transparent
     * region are codec/library-dependent (Java fills masked-out body pixels
     * black; Pillow's RGBA->RGB carries the original colour), so a raw RGB
     * fingerprint would diverge on pixels the page never actually shows.
     * Compositing over white reproduces what the page render displays and
     * keeps the comparison a true encode-side check.
     */
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
                int argb = img.getRGB(x, y);
                int a = (argb >> 24) & 0xFF;
                int r = (argb >> 16) & 0xFF;
                int g = (argb >> 8) & 0xFF;
                int b = argb & 0xFF;
                // Composite over white: out = src*a + 255*(1-a).
                r = (r * a + 255 * (255 - a)) / 255;
                g = (g * a + 255 * (255 - a)) / 255;
                b = (b * a + 255 * (255 - a)) / 255;
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
