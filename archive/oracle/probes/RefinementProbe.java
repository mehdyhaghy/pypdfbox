import java.io.ByteArrayInputStream;
import java.lang.reflect.Method;
import javax.imageio.stream.ImageInputStream;
import javax.imageio.stream.MemoryCacheImageInputStream;
import org.apache.pdfbox.jbig2.Bitmap;
import org.apache.pdfbox.jbig2.decoder.arithmetic.ArithmeticDecoder;
import org.apache.pdfbox.jbig2.decoder.arithmetic.CX;
import java.lang.reflect.Field;
import org.apache.pdfbox.jbig2.segments.GenericRefinementRegion;
import org.apache.pdfbox.jbig2.segments.RegionSegmentInformation;

/**
 * Live oracle probe for the JBIG2 Generic Refinement Region decoding procedure
 * (ITU-T T.88 §6.3.5.6).
 *
 * Builds a reference {@link Bitmap} from a hex pixel pattern, then drives the
 * upstream Apache PDFBox {@link GenericRefinementRegion} via its (protected)
 * {@code setParameters} entry point — supplying a fresh {@link ArithmeticDecoder}
 * over a crafted coded-byte array and a fresh {@link CX} — and calls
 * {@code getRegionBitmap()}. The refined bitmap is emitted as a hex string so a
 * parity test can assert pypdfbox produces the IDENTICAL refined bitmap.
 *
 * Usage:
 *   java ... RefinementProbe <grTemplate> <w> <h> <refW> <refH> <dx> <dy>
 *            <tpgr 0|1> <refHex> <codedHex> [atx0 aty0 atx1 aty1]
 *
 *   grTemplate  0 or 1 (GRTEMPLATE)
 *   w h         decoded region width/height (GRW/GRH)
 *   refW refH   reference bitmap width/height
 *   dx dy       GRREFERENCEDX / GRREFERENCEDY
 *   tpgr        1 to enable typical prediction (TPGRON), else 0
 *   refHex      reference bitmap bytes (row-major, row-stride padded), hex
 *   codedHex    arithmetic-coded input bytes, hex
 *   atx/aty     AT pixel offsets (signed bytes) for template 0; default
 *               (-1,-1),(-1,-1) i.e. nominal positions, no override
 *
 * Output (UTF-8, single LF-terminated line): the refined bitmap's underlying
 * byte array as a lowercase hex string.
 */
public final class RefinementProbe
{
    public static void main(String[] args) throws Exception
    {
        if (args.length < 10)
        {
            System.err.println("usage: RefinementProbe <grTemplate> <w> <h> <refW> "
                + "<refH> <dx> <dy> <tpgr> <refHex> <codedHex> "
                + "[atx0 aty0 atx1 aty1]");
            System.exit(2);
        }

        short grTemplate = Short.parseShort(args[0]);
        int w = Integer.parseInt(args[1]);
        int h = Integer.parseInt(args[2]);
        int refW = Integer.parseInt(args[3]);
        int refH = Integer.parseInt(args[4]);
        int dx = Integer.parseInt(args[5]);
        int dy = Integer.parseInt(args[6]);
        boolean tpgr = "1".equals(args[7]);
        byte[] refBytes = hex(args[8]);
        byte[] coded = hex(args[9]);

        short[] atX = new short[] { -1, -1 };
        short[] atY = new short[] { -1, -1 };
        if (args.length >= 14)
        {
            atX[0] = Short.parseShort(args[10]);
            atY[0] = Short.parseShort(args[11]);
            atX[1] = Short.parseShort(args[12]);
            atY[1] = Short.parseShort(args[13]);
        }

        Bitmap reference = new Bitmap(refW, refH);
        byte[] refArr = reference.getByteArray();
        int n = Math.min(refArr.length, refBytes.length);
        System.arraycopy(refBytes, 0, refArr, 0, n);

        ImageInputStream iis =
            new MemoryCacheImageInputStream(new ByteArrayInputStream(coded));
        ArithmeticDecoder arithDecoder = new ArithmeticDecoder(iis);
        CX cx = new CX(8192, 1);

        GenericRefinementRegion grr = new GenericRefinementRegion();

        // The no-arg constructor leaves regionInfo null; setParameters() writes
        // the region width/height into it, so install a fresh instance first.
        Field regionInfoField =
            GenericRefinementRegion.class.getDeclaredField("regionInfo");
        regionInfoField.setAccessible(true);
        regionInfoField.set(grr, new RegionSegmentInformation());

        Method setParameters = GenericRefinementRegion.class.getDeclaredMethod(
            "setParameters", CX.class, ArithmeticDecoder.class, short.class,
            int.class, int.class, Bitmap.class, int.class, int.class,
            boolean.class, short[].class, short[].class);
        setParameters.setAccessible(true);
        setParameters.invoke(grr, cx, arithDecoder, grTemplate, w, h, reference,
            dx, dy, tpgr, atX, atY);

        Bitmap result = grr.getRegionBitmap();

        byte[] out = result.getByteArray();
        StringBuilder sb = new StringBuilder(out.length * 2);
        for (byte b : out)
        {
            sb.append(String.format("%02x", b & 0xff));
        }

        System.out.print(sb.toString());
        System.out.print('\n');
        System.out.flush();
    }

    private static byte[] hex(String s)
    {
        if (s.isEmpty())
        {
            return new byte[0];
        }
        int n = s.length() / 2;
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++)
        {
            out[i] = (byte) Integer.parseInt(s.substring(2 * i, 2 * i + 2), 16);
        }
        return out;
    }
}
