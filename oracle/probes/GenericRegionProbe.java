import java.io.ByteArrayInputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;

import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.Bitmap;
import org.apache.pdfbox.jbig2.io.SubInputStream;

/**
 * Live oracle probe for the JBIG2 generic-region decoder.
 *
 * Drives the upstream Apache PDFBox {@code GenericRegion} on a fixed byte array
 * that is the EXACT segment-data part of an immediate generic-region segment
 * (region segment information field + generic-region flags + AT pixels +
 * MMR/arithmetic coded data — i.e. everything AFTER the segment header). The
 * decoded {@link Bitmap} is dumped so a parity test can assert pypdfbox's
 * GenericRegion produces the identical bitmap (width, height, row stride, every
 * packed byte).
 *
 * {@code GenericRegion} and its {@code init(SegmentHeader, SubInputStream)} are
 * package-private, so the no-arg constructor and {@code init} are reached via
 * reflection from the default package. {@code init} stores the header but never
 * dereferences it for a generic region, so a {@code null} header is passed. The
 * {@code SubInputStream} window spans the whole crafted buffer, so
 * {@code computeSegmentDataStructure()} derives the coded-data length from
 * {@code length()} exactly as it would when fed by the real segment-data slice.
 *
 * Usage:
 *   java ... GenericRegionProbe &lt;hexbytes&gt;
 *
 *   hexbytes  the generic-region segment-data part as a hex string (no 0x).
 *
 * Output (UTF-8, single LF-terminated line):
 *   "&lt;width&gt; &lt;height&gt; &lt;rowStride&gt; &lt;hexBytes&gt;"
 */
public final class GenericRegionProbe
{
    public static void main(String[] args) throws Exception
    {
        if (args.length < 1)
        {
            System.err.println("usage: GenericRegionProbe <hexbytes>");
            System.exit(2);
        }

        byte[] data = hex(args[0]);

        MemoryCacheImageInputStream iis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(data));
        SubInputStream sis = new SubInputStream(iis, 0, data.length);

        Class<?> grClass = Class.forName("org.apache.pdfbox.jbig2.segments.GenericRegion");
        Constructor<?> ctor = grClass.getDeclaredConstructor();
        ctor.setAccessible(true);
        Object region = ctor.newInstance();

        Class<?> headerClass = Class.forName("org.apache.pdfbox.jbig2.SegmentHeader");
        Method init = grClass.getDeclaredMethod("init", headerClass, SubInputStream.class);
        init.setAccessible(true);
        init.invoke(region, null, sis);

        Method getRegionBitmap = grClass.getDeclaredMethod("getRegionBitmap");
        getRegionBitmap.setAccessible(true);
        Bitmap bitmap = (Bitmap) getRegionBitmap.invoke(region);

        byte[] bytes = bitmap.getByteArray();
        StringBuilder sb = new StringBuilder();
        sb.append(bitmap.getWidth()).append(' ')
          .append(bitmap.getHeight()).append(' ')
          .append(bitmap.getRowStride()).append(' ');
        for (byte b : bytes)
        {
            sb.append(String.format("%02x", b & 0xff));
        }
        sb.append('\n');

        System.out.print(sb);
        System.out.flush();
    }

    private static byte[] hex(String s)
    {
        int n = s.length() / 2;
        byte[] out = new byte[n];
        for (int i = 0; i < n; i++)
        {
            out[i] = (byte) Integer.parseInt(s.substring(2 * i, 2 * i + 2), 16);
        }
        return out;
    }
}
