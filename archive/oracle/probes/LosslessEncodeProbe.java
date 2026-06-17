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
import org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * Live oracle probe for the {@code LosslessFactory.createFromImage} ENCODE
 * surface across grayscale (/DeviceGray) and indexed/palette (/Indexed)
 * rasters — the orthogonal colour-space cases NOT covered by
 * {@code ImageEncodeProbe.java} (which only exercises RGB / RGBA).
 *
 * Two subcommands:
 *
 *   make <png> <out.pdf>
 *     ImageIO.read the PNG into a BufferedImage and build ONE image XObject
 *     via {@code LosslessFactory.createFromImage}. Place it on a 200x200 page
 *     and save. The PNG's pixel layout (8-bit gray vs paletted vs gray+alpha)
 *     drives which colour-space / SMask path the factory selects.
 *
 *   read <pdf>
 *     Walk every page's XObjects; for each {@code PDImageXObject} emit ONE line
 *     ("image page <p> name <n> filter <F> cs <CS> w <w> h <h> bpc <b>
 *      smask <0|1> grid <256 ints>") where grid is a 16x16 average-luminance
 *     fingerprint of the DECODED {@code getImage()} raster, composited over a
 *     white backdrop using the per-pixel alpha (so any masked-out body colour,
 *     which is library-dependent, never counts). Identical luminance math to
 *     {@code ImageEncodeProbe.grid}.
 *
 * Routing both PDFs through this same probe's {@code read} makes the renderer
 * identical on both sides, so only the encode (filter / colour-space / bpc /
 * SMask + decoded raster) differs — a pure encode-side differential.
 */
public final class LosslessEncodeProbe {
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
            PDImageXObject image = LosslessFactory.createFromImage(doc, raster);
            PDPage page = new PDPage(new PDRectangle(0, 0, 200, 200));
            doc.addPage(page);
            try (PDPageContentStream cs = new PDPageContentStream(doc, page)) {
                cs.drawImage(image, 10, 10, 180, 180);
            }
            doc.save(new File(outPath));
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
     * 16x16 average-luminance fingerprint of a decoded raster, each ARGB
     * pixel composited over an opaque white backdrop via its alpha before
     * luma. Identical math to {@code ImageEncodeProbe.grid}.
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
