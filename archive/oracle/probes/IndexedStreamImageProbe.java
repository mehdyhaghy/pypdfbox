import java.awt.image.BufferedImage;
import java.awt.image.Raster;
import java.awt.image.WritableRaster;
import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.nio.file.Paths;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSInteger;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace;
import org.apache.pdfbox.pdmodel.graphics.color.PDIndexed;

/**
 * Live oracle probe for the RASTER colour-conversion surface
 * {@code PDIndexed.toRGBImage(WritableRaster)} where the {@code /Lookup}
 * palette is carried as a {@code COSStream} (FlateDecode), NOT a literal
 * {@code COSString}.
 *
 * <p>This is distinct from {@code ColorImageRgbProbe} (Indexed raster decode
 * with a STRING lookup, covered in waves 1456/1458) and from
 * {@code IndexedStreamProbe} / {@code IndexedCalProbe} (which drive the
 * single-sample {@code toRGB(float[])} path). The raster path takes its own
 * code in PDFBox: {@code PDIndexed.initRgbColorTable} builds the cached RGB
 * lookup table once from the DECODED stream bytes, then {@code toRGBImage}
 * does a per-pixel palette dereference clamped to {@code actualMaxIndex}
 * (= {@code hival} when the lookup is long enough). A regression that treats
 * the stream slot as empty (string-only handling) would zero the palette; a
 * wrong base component count would shift every entry; a missing per-pixel
 * clamp would dereference past the palette for an out-of-range index.
 *
 * <p>Two bases are exercised:
 * <ul>
 *   <li>DeviceRGB (3 bytes/entry) — byte-exact, no colour-management module.
 *   <li>ICCBased sRGB (N=3, embedded profile) — routes each palette entry
 *       through the profile transform (AWT CMM here, LittleCMS2 in pypdfbox),
 *       compared within a small CMM LSB tolerance on the Python side.
 * </ul>
 *
 * <p>For each space the probe builds a 1-row banded {@code WritableRaster}
 * (single band — the palette index), fills it with a fixed list of 8-bit
 * pixel indices INCLUDING out-of-range values ({@code > hival} → clamp to the
 * last entry), calls {@code toRGBImage}, reads each pixel back via
 * {@code BufferedImage.getRGB}, and emits canonical
 * {@code "csname idx -> r g b"} lines (RGB 0-255 ints). A leading metadata
 * line per space reports {@code "csname# ncomp"} so the Python side can assert
 * {@code getNumberOfComponents()==1}; the {@code hival} facet is exercised
 * behaviourally via the out-of-range index that clamps to the last entry
 * ({@code getHival()} is package-private in PDFBox 3.0.7 so it isn't emitted).
 *
 * <p>Usage: java -cp &lt;pdfbox-app.jar&gt;:&lt;build&gt; IndexedStreamImageProbe &lt;icc.path&gt;
 *
 * <p>The single argument is the filesystem path to an sRGB ICC profile (the
 * Python test mints one via Pillow's {@code ImageCms.createProfile("sRGB")} so
 * both sides embed byte-identical profile bytes).
 */
public final class IndexedStreamImageProbe {

    static PrintStream out;

    /** Build a 1-row, N-pixel single-band raster from int index samples. */
    static WritableRaster raster(int[] indices) {
        WritableRaster r = Raster.createBandedRaster(
            java.awt.image.DataBuffer.TYPE_BYTE, indices.length, 1, 1, null);
        for (int x = 0; x < indices.length; x++) {
            r.setPixel(x, 0, new int[] {indices[x]});
        }
        return r;
    }

    static void emit(String name, int[] indices, PDIndexed cs) throws Exception {
        // Metadata line: number of components (always 1 for Indexed).
        out.println(name + "# " + cs.getNumberOfComponents());
        WritableRaster r = raster(indices);
        BufferedImage img = cs.toRGBImage(r);
        for (int x = 0; x < indices.length; x++) {
            int argb = img.getRGB(x, 0);
            int red = (argb >> 16) & 0xFF;
            int green = (argb >> 8) & 0xFF;
            int blue = argb & 0xFF;
            out.println(name + ' ' + indices[x] + " -> "
                + red + ' ' + green + ' ' + blue);
        }
    }

    /** Build an Indexed CS whose /Lookup is a FlateDecode COSStream. */
    static PDIndexed indexedStream(PDColorSpace base, int hival, byte[] palette)
            throws Exception {
        COSStream lookup = new COSStream();
        OutputStream os = lookup.createOutputStream(COSName.FLATE_DECODE);
        os.write(palette);
        os.close();
        COSArray arr = new COSArray();
        arr.add(COSName.INDEXED);
        arr.add(base.getCOSObject());
        arr.add(COSInteger.get(hival));
        arr.add(lookup);
        return (PDIndexed) PDColorSpace.create(arr);
    }

    static PDColorSpace deviceRgb() throws Exception {
        return PDColorSpace.create(COSName.DEVICERGB);
    }

    public static void main(String[] args) throws Exception {
        out = new PrintStream(System.out, true, "UTF-8");

        // ---------- Indexed over DeviceRGB, stream lookup, hival 3 ----------
        byte[] rgbPalette = new byte[] {
            (byte) 0, (byte) 0, (byte) 0,        // 0 black
            (byte) 255, (byte) 0, (byte) 0,      // 1 red
            (byte) 0, (byte) 255, (byte) 0,      // 2 green
            (byte) 128, (byte) 128, (byte) 255   // 3 light blue
        };
        PDIndexed idxRgb = indexedStream(deviceRgb(), 3, rgbPalette);
        int[] indices = new int[] {0, 1, 2, 3, 4, 7, 255};
        emit("IdxRgbStreamImg", indices, idxRgb);

        // ---------- Indexed over ICCBased sRGB, stream lookup, hival 3 ------
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
            byte[] iccPalette = new byte[] {
                (byte) 0, (byte) 0, (byte) 0,
                (byte) 255, (byte) 0, (byte) 0,
                (byte) 64, (byte) 128, (byte) 192,
                (byte) 255, (byte) 255, (byte) 255
            };
            PDIndexed idxIcc = indexedStream(iccSrgb, 3, iccPalette);
            emit("IdxIccStreamImg", indices, idxIcc);
        }
    }
}
