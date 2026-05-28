import java.awt.image.BufferedImage;
import java.awt.image.Raster;
import java.awt.image.WritableRaster;
import java.io.OutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.cos.COSString;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDDeviceN;
import org.apache.pdfbox.pdmodel.graphics.color.PDIndexed;
import org.apache.pdfbox.pdmodel.graphics.color.PDSeparation;

/**
 * Live oracle probe for the RASTER colour-conversion surface
 * {@code PDColorSpace.toRGBImage(WritableRaster)} — distinct from the
 * single-value {@code toRGB(float[])} path the existing colour probes cover.
 *
 * <p>The raster path takes different code in PDFBox: {@code PDIndexed} builds an
 * RGB lookup table once ({@code initRgbColorTable}) and does a per-pixel palette
 * dereference; {@code PDSeparation}/{@code PDDeviceN} fan each 8-bit tint sample
 * through the tint transform with {@code (int)(result * 255)} TRUNCATION (not
 * {@code Math.round}) before handing the alternate-CS raster to the alternate's
 * own {@code toRGBImage}. This probe exercises those raster code paths directly.
 *
 * <p>For each space the probe builds a banded {@code WritableRaster} (one band
 * per colour-space component), fills it with a fixed list of pixel sample
 * tuples (8-bit ints, 0-255), calls {@code toRGBImage}, then reads each pixel
 * back via {@code BufferedImage.getRGB(x, y)} and emits canonical
 * {@code "csname s0 s1 ... -> r g b"} lines (RGB 0-255 ints). The Python side
 * reconstructs the matching pypdfbox spaces, runs the same raster bytes through
 * {@code to_rgb_image}, and compares pixel-for-pixel.
 *
 * <p>Only colour spaces whose alternate/base stays out of the JVM colour-
 * management module are exercised (Indexed over DeviceRGB; Separation/DeviceN
 * over DeviceGray) so the comparison is byte-exact rather than CMM-divergent.
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; ColorImageRgbProbe
 */
public final class ColorImageRgbProbe {

    static PrintStream out;

    /** Build a banded raster (1 row, N pixels) from int sample tuples. */
    static WritableRaster raster(int[][] pixels, int bands) {
        WritableRaster r = Raster.createBandedRaster(
            java.awt.image.DataBuffer.TYPE_BYTE, pixels.length, 1, bands, null);
        for (int x = 0; x < pixels.length; x++) {
            r.setPixel(x, 0, pixels[x]);
        }
        return r;
    }

    static void emit(String name, int[][] pixels, int bands, PDColorSpace cs)
            throws Exception {
        WritableRaster r = raster(pixels, bands);
        BufferedImage img = cs.toRGBImage(r);
        for (int x = 0; x < pixels.length; x++) {
            int argb = img.getRGB(x, 0);
            int red = (argb >> 16) & 0xFF;
            int green = (argb >> 8) & 0xFF;
            int blue = argb & 0xFF;
            StringBuilder sb = new StringBuilder();
            sb.append(name);
            for (int v : pixels[x]) {
                sb.append(' ').append(v);
            }
            sb.append(" -> ").append(red).append(' ').append(green)
                .append(' ').append(blue);
            out.println(sb.toString());
        }
    }

    static COSStream type4(float[] domain, float[] range, String ps)
            throws Exception {
        COSStream s = new COSStream();
        s.setInt(COSName.FUNCTION_TYPE, 4);
        COSArray dom = new COSArray();
        for (float v : domain) {
            dom.add(new COSFloat(v));
        }
        s.setItem(COSName.DOMAIN, dom);
        COSArray rng = new COSArray();
        for (float v : range) {
            rng.add(new COSFloat(v));
        }
        s.setItem(COSName.RANGE, rng);
        OutputStream os = s.createOutputStream();
        os.write(ps.getBytes("US-ASCII"));
        os.close();
        return s;
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---------- Indexed over DeviceRGB base, hival 3 ----------
        // Raster samples are palette INDICES (one band). The fast palette
        // path returns the exact stored RGB; out-of-range clamps to hival.
        byte[] rgbPalette = new byte[] {
            (byte) 0, (byte) 0, (byte) 0,        // 0 black
            (byte) 255, (byte) 0, (byte) 0,      // 1 red
            (byte) 0, (byte) 255, (byte) 0,      // 2 green
            (byte) 128, (byte) 128, (byte) 255   // 3 light blue
        };
        COSArray idxArr = new COSArray();
        idxArr.add(COSName.INDEXED);
        idxArr.add(COSName.DEVICERGB);
        idxArr.add(COSInteger.get(3));
        idxArr.add(new COSString(rgbPalette));
        PDIndexed idxRgb = (PDIndexed) PDColorSpace.create(idxArr);
        int[][] idxPixels = {
            {0}, {1}, {2}, {3},
            {4}, {7}, {255}  // > hival -> clamp to entry 3
        };
        emit("IdxRgbImg", idxPixels, 1, idxRgb);

        // ---------- Separation -> DeviceGray (Type-4 tint, raster path) ----
        // tint t -> gray g = 1 - t. Raster fans the 8-bit tint through the
        // tint transform with (int)(result*255) truncation, then DeviceGray's
        // toRGBImage replicates the band -> grey RGB (no CMM).
        COSArray sepArr = new COSArray();
        sepArr.add(COSName.SEPARATION);
        sepArr.add(COSName.getPDFName("PsSpot"));
        sepArr.add(COSName.DEVICEGRAY);
        sepArr.add(type4(
            new float[] {0.0f, 1.0f},
            new float[] {0.0f, 1.0f},
            "{ 1 exch sub }"));
        PDSeparation sepGray = new PDSeparation(sepArr);
        int[][] sepPixels = {
            {0}, {1}, {64}, {127}, {128}, {191}, {254}, {255}
        };
        emit("SepGrayImg", sepPixels, 1, sepGray);

        // ---------- DeviceN (2 colorants) -> DeviceGray (Type-4) -----------
        // (a, b) -> gray = 1 - (a+b)/2. Raster path, no CMM.
        COSArray dnNames = new COSArray();
        dnNames.add(COSName.getPDFName("G1"));
        dnNames.add(COSName.getPDFName("G2"));
        COSArray dnArr = new COSArray();
        dnArr.add(COSName.DEVICEN);
        dnArr.add(dnNames);
        dnArr.add(COSName.DEVICEGRAY);
        dnArr.add(type4(
            new float[] {0, 1, 0, 1},
            new float[] {0, 1},
            "{ add 2 div 1 exch sub }"));
        PDDeviceN dnGray = new PDDeviceN(dnArr);
        int[][] dnPixels = {
            {0, 0}, {255, 255}, {0, 255}, {128, 64}, {200, 100}
        };
        emit("DevNGrayImg", dnPixels, 2, dnGray);
    }
}
