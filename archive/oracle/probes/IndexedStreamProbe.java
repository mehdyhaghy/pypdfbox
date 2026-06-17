import java.io.OutputStream;
import java.io.PrintStream;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDIndexed;

/**
 * Live oracle probe: Apache PDFBox PDIndexed.toRGB() where the /Lookup palette
 * is carried as a COSStream (FlateDecode), not a literal COSString.
 *
 * Two bases are exercised so per-entry byte slicing by base component count is
 * checked: DeviceRGB (3 bytes/entry) and DeviceCMYK (4 bytes/entry). For each
 * Indexed space toRGB is called over a fixed index set INCLUDING out-of-range
 * values (negative and > hival) so the clamp-to-[0, hival] behaviour is in the
 * trace.
 *
 * Emits canonical "csname index -> r g b" lines (RGB 0-255 ints), computed as
 * round(component * 255) clamped to [0, 255] — the same rounding pypdfbox's
 * differential test applies.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> IndexedStreamProbe
 */
public final class IndexedStreamProbe {

    static PrintStream out;

    static int clamp255(float v) {
        long r = Math.round((double) v * 255.0);
        if (r < 0) {
            return 0;
        }
        if (r > 255) {
            return 255;
        }
        return (int) r;
    }

    static void emit(String name, float index, PDColorSpace cs) throws Exception {
        float[] rgb = cs.toRGB(new float[] {index});
        StringBuilder sb = new StringBuilder();
        sb.append(name).append(' ').append((int) index).append(" -> ");
        sb.append(clamp255(rgb[0])).append(' ');
        sb.append(clamp255(rgb[1])).append(' ');
        sb.append(clamp255(rgb[2]));
        out.println(sb.toString());
    }

    /** Build an Indexed CS whose /Lookup is a FlateDecode COSStream. */
    static PDIndexed indexedStream(COSName base, int hival, byte[] palette) throws Exception {
        COSStream lookup = new COSStream();
        OutputStream os = lookup.createOutputStream(COSName.FLATE_DECODE);
        os.write(palette);
        os.close();
        COSArray arr = new COSArray();
        arr.add(COSName.INDEXED);
        arr.add(base);
        arr.add(COSInteger.get(hival));
        arr.add(lookup);
        return (PDIndexed) PDColorSpace.create(arr);
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---------- RGB base: 4 entries * 3 bytes, hival 3 ----------
        byte[] rgbPalette = new byte[] {
            (byte) 0, (byte) 0, (byte) 0,       // 0 black
            (byte) 255, (byte) 0, (byte) 0,     // 1 red
            (byte) 0, (byte) 255, (byte) 0,     // 2 green
            (byte) 128, (byte) 128, (byte) 255  // 3 light blue
        };
        PDIndexed rgbIdx = indexedStream(COSName.DEVICERGB, 3, rgbPalette);
        float[] rgbIndices = {-1f, 0f, 1f, 2f, 3f, 4f, 7f};
        for (float i : rgbIndices) {
            emit("RGBStream", i, rgbIdx);
        }

        // ---------- CMYK base: 3 entries * 4 bytes, hival 2 ----------
        byte[] cmykPalette = new byte[] {
            (byte) 0, (byte) 0, (byte) 0, (byte) 0,        // 0 white (no ink)
            (byte) 0, (byte) 255, (byte) 255, (byte) 0,    // 1 red (m+y)
            (byte) 0, (byte) 0, (byte) 0, (byte) 255       // 2 black (k)
        };
        PDIndexed cmykIdx = indexedStream(COSName.DEVICECMYK, 2, cmykPalette);
        float[] cmykIndices = {-1f, 0f, 1f, 2f, 3f, 5f};
        for (float i : cmykIndices) {
            emit("CMYKStream", i, cmykIdx);
        }
    }
}
