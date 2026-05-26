import java.awt.image.BufferedImage;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.OutputStream;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.filter.Filter;
import org.apache.pdfbox.filter.FilterFactory;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.graphics.image.CCITTFactory;
import org.apache.pdfbox.pdmodel.graphics.image.PDImageXObject;

/**
 * Reference probe: build a CCITT Group-4 image XObject from a synthetic
 * bilevel raster via PDFBox's own CCITTFactory.createFromImage, then emit
 * the raw ENCODED CCITT strip bytes to stdout. Lets a parity test decode the
 * exact stream PDFBox's encoder produces and compare against pypdfbox.
 *
 * Usage: java -cp ... CcittEncRefProbe <w> <h> <pattern>
 *   pattern "checker"     : (x/4 + y/4) % 2 == 0 -> black
 *   pattern "left"        : left half black
 *   pattern "altcols"     : even columns white, odd columns black
 *
 * The raster convention here matches BufferedImage TYPE_BYTE_BINARY:
 *   pixel 0x000000 (black) / 0xFFFFFF (white). CCITTFactory.createFromImage
 *   only accepts a 1-bit image, so we build TYPE_BYTE_BINARY.
 *
 * Output (raw bytes): the encoded CCITT strip (the stream's raw body).
 */
public final class CcittEncRefProbe {
    public static void main(String[] args) throws Exception {
        int w = Integer.parseInt(args[0]);
        int h = Integer.parseInt(args[1]);
        String pattern = args[2];

        BufferedImage img = new BufferedImage(w, h, BufferedImage.TYPE_BYTE_BINARY);
        for (int y = 0; y < h; y++) {
            for (int x = 0; x < w; x++) {
                boolean black = isBlack(pattern, x, y, w, h);
                img.setRGB(x, y, black ? 0x000000 : 0xFFFFFF);
            }
        }

        try (PDDocument doc = new PDDocument()) {
            PDImageXObject image = CCITTFactory.createFromImage(doc, img);
            // Raw (still-encoded) bytes of the CCITT stream.
            byte[] encoded;
            try (java.io.InputStream raw = image.getCOSObject().createRawInputStream()) {
                ByteArrayOutputStream bos = new ByteArrayOutputStream();
                byte[] buf = new byte[8192];
                int n;
                while ((n = raw.read(buf)) >= 0) {
                    bos.write(buf, 0, n);
                }
                encoded = bos.toByteArray();
            }
            OutputStream out = System.out;
            out.write(encoded);
            out.flush();
        }
    }

    private static boolean isBlack(String pattern, int x, int y, int w, int h) {
        switch (pattern) {
            case "checker":
                return ((x / 4) + (y / 4)) % 2 == 0;
            case "left":
                return x < w / 2;
            case "altcols":
                return (x % 2) == 1;
            default:
                return false;
        }
    }
}
