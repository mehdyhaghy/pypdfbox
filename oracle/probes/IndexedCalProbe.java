import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSFloat;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDCalGray;
import org.apache.pdfbox.pdmodel.graphics.color.PDCalRGB;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDIndexed;

/**
 * Live oracle probe for {@link PDIndexed#toRGB} where the {@code base} is a
 * non-Device colour space — {@code CalRGB} (gamma + matrix + white point),
 * {@code CalGray} (gamma + white point), and {@code ICCBased} (embedded sRGB
 * profile).
 *
 * <p>Constructs the Indexed array {@code [/Indexed base hival lookup]} with the
 * lookup carried as a literal {@code COSString} (one byte per base component
 * per palette entry). PDFBox 3.0.7 builds the cached {@code rgbColorTable} by
 * decoding each lookup entry through the base CS's
 * {@code toRGBImage(WritableRaster)} pipeline (a 1-pixel banded raster per
 * entry) — for a {@code CalRGB}/{@code CalGray} base that routes through the
 * AWT CMM (D50 PCS); for an embedded sRGB {@code ICCBased} profile through
 * the profile's transform. Then {@code PDIndexed.toRGB(float[])} returns
 * {@code rgbColorTable[clamp(index)] / 255f}.
 *
 * <p>Emits {@code "csname index -> r g b"} lines (RGB 0-255 ints, computed as
 * {@code round(component * 255)} clamped to {@code [0, 255]} — same rounding
 * pypdfbox's differential test applies).
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; IndexedCalProbe &lt;icc.path&gt;
 *
 * <p>The single argument is the filesystem path to an sRGB ICC profile (the
 * Python test mints one via Pillow's {@code ImageCms.createProfile("sRGB")} so
 * both sides embed the byte-identical profile).
 */
public final class IndexedCalProbe {

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

    static void emit(String name, int index, PDColorSpace cs) throws Exception {
        float[] rgb = cs.toRGB(new float[] {(float) index});
        StringBuilder sb = new StringBuilder();
        sb.append(name).append(' ').append(index).append(" -> ");
        sb.append(clamp255(rgb[0])).append(' ');
        sb.append(clamp255(rgb[1])).append(' ');
        sb.append(clamp255(rgb[2]));
        out.println(sb.toString());
    }

    static COSArray floats(float... vals) {
        COSArray a = new COSArray();
        for (float v : vals) {
            a.add(new COSFloat(v));
        }
        return a;
    }

    static PDCalRGB calRGB(float[] whitePoint, float[] gamma, float[] matrix) {
        COSArray arr = new COSArray();
        arr.add(COSName.CALRGB);
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.WHITE_POINT, floats(whitePoint));
        d.setItem(COSName.GAMMA, floats(gamma));
        d.setItem(COSName.MATRIX, floats(matrix));
        arr.add(d);
        return new PDCalRGB(arr);
    }

    static PDCalGray calGray(float[] whitePoint, float gamma) {
        COSArray arr = new COSArray();
        arr.add(COSName.CALGRAY);
        COSDictionary d = new COSDictionary();
        d.setItem(COSName.WHITE_POINT, floats(whitePoint));
        d.setItem(COSName.GAMMA, new COSFloat(gamma));
        arr.add(d);
        return new PDCalGray(arr);
    }

    /** Build an Indexed CS [/Indexed base hival lookup] with a literal lookup string. */
    static PDIndexed indexed(PDColorSpace base, int hival, byte[] palette) throws Exception {
        COSArray arr = new COSArray();
        arr.add(COSName.INDEXED);
        arr.add(base.getCOSObject());
        arr.add(COSInteger.get(hival));
        // Use a COSStream with no filter so the bytes are carried as-is — this
        // exercises the same lookup-decode path PDIndexed uses for either form.
        COSStream lookup = new COSStream();
        OutputStream os = lookup.createOutputStream();
        os.write(palette);
        os.close();
        arr.add(lookup);
        return new PDIndexed(arr);
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        float[] unit = new float[] {1.0f, 1.0f, 1.0f};

        // ---- Indexed base = CalRGB (unit white point + sRGB-ish matrix) ----
        // 3 bytes per entry; 4 entries (hival = 3).
        float[] gamma = new float[] {1.8f, 2.2f, 2.4f};
        float[] matrix = new float[] {
            0.4124f, 0.2126f, 0.0193f,
            0.3576f, 0.7152f, 0.1192f,
            0.1805f, 0.0722f, 0.9505f
        };
        PDCalRGB calRgb = calRGB(unit, gamma, matrix);
        byte[] calRgbPalette = new byte[] {
            (byte) 0, (byte) 0, (byte) 0,         // 0 black
            (byte) 255, (byte) 0, (byte) 0,       // 1 red primary
            (byte) 128, (byte) 128, (byte) 128,   // 2 mid grey
            (byte) 64, (byte) 192, (byte) 32     // 3 mixed
        };
        PDIndexed idxCalRgb = indexed(calRgb, 3, calRgbPalette);
        int[] indices4 = new int[] {-1, 0, 1, 2, 3, 4, 7};
        for (int i : indices4) {
            emit("IdxCalRgb", i, idxCalRgb);
        }

        // ---- Indexed base = CalGray (unit white point + gamma 2.2) ----
        // 1 byte per entry; 5 entries (hival = 4).
        PDCalGray calGray22 = calGray(unit, 2.2f);
        byte[] grayPalette = new byte[] {
            (byte) 0,
            (byte) 64,
            (byte) 128,
            (byte) 192,
            (byte) 255
        };
        PDIndexed idxCalGray = indexed(calGray22, 4, grayPalette);
        int[] indices5 = new int[] {-1, 0, 1, 2, 3, 4, 5, 10};
        for (int i : indices5) {
            emit("IdxCalGray", i, idxCalGray);
        }

        // ---- Indexed base = ICCBased (embedded sRGB profile, N=3) ----
        // Sanity-guard the icc-path argument — the Python test always passes
        // it; only skip when running the probe manually for spot checks.
        if (args.length >= 1 && args[0] != null) {
            byte[] iccBytes = Files.readAllBytes(Paths.get(args[0]));
            COSStream iccStream = new COSStream();
            iccStream.setInt(COSName.N, 3);
            OutputStream ios = iccStream.createOutputStream();
            ios.write(iccBytes);
            ios.close();
            COSArray iccArr = new COSArray();
            iccArr.add(COSName.ICCBASED);
            iccArr.add(iccStream);
            PDColorSpace iccSrgb = PDColorSpace.create(iccArr);
            // 3 bytes per entry; 4 entries (hival = 3).
            byte[] iccPalette = new byte[] {
                (byte) 0, (byte) 0, (byte) 0,
                (byte) 255, (byte) 0, (byte) 0,
                (byte) 64, (byte) 128, (byte) 192,
                (byte) 255, (byte) 255, (byte) 255
            };
            PDIndexed idxIccSrgb = indexed(iccSrgb, 3, iccPalette);
            for (int i : indices4) {
                emit("IdxIccSrgb", i, idxIccSrgb);
            }
        }
    }
}
