import java.io.ByteArrayInputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.List;

import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.Bitmap;
import org.apache.pdfbox.jbig2.io.SubInputStream;

/**
 * Live oracle probe for the JBIG2 pattern-dictionary decoder.
 *
 * Drives the upstream Apache PDFBox {@code PatternDictionary} on a fixed byte
 * array that is the EXACT segment-data part of a pattern-dictionary segment
 * (pattern-dictionary flags + HDPW + HDPH + GRAYMAX + MMR/arithmetic coded
 * collective bitmap — i.e. everything AFTER the segment header). The decoded
 * patterns (the list of {@link Bitmap}s returned by {@code getDictionary()})
 * are dumped so a parity test can assert pypdfbox's {@code PatternDictionary}
 * slices the identical patterns out of the collective bitmap.
 *
 * {@code PatternDictionary} implements the package-private {@code Dictionary}
 * interface; its no-arg constructor and {@code init(SegmentHeader,
 * SubInputStream)} are reached via reflection from the default package.
 * {@code init} stores the stream and parses the header but never dereferences
 * the {@code SegmentHeader}, so a {@code null} header is passed. The
 * {@code SubInputStream} window spans the whole crafted buffer, so
 * {@code computeSegmentDataStructure()} derives the coded-data length from
 * {@code length()} exactly as it would when fed by the real segment-data slice.
 *
 * Usage:
 *   java ... PatternDictionaryProbe &lt;hexbytes&gt;
 *
 * Output (UTF-8, single LF-terminated line):
 *   "&lt;count&gt;|&lt;w&gt; &lt;h&gt; &lt;stride&gt; &lt;hex&gt;|&lt;w&gt; &lt;h&gt; &lt;stride&gt; &lt;hex&gt;|..."
 */
public final class PatternDictionaryProbe
{
    public static void main(String[] args) throws Exception
    {
        if (args.length < 1)
        {
            System.err.println("usage: PatternDictionaryProbe <hexbytes>");
            System.exit(2);
        }

        byte[] data = hex(args[0]);

        MemoryCacheImageInputStream iis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(data));
        SubInputStream sis = new SubInputStream(iis, 0, data.length);

        Class<?> pdClass = Class.forName("org.apache.pdfbox.jbig2.segments.PatternDictionary");
        Constructor<?> ctor = pdClass.getDeclaredConstructor();
        ctor.setAccessible(true);
        Object dict = ctor.newInstance();

        Class<?> headerClass = Class.forName("org.apache.pdfbox.jbig2.SegmentHeader");
        Method init = pdClass.getDeclaredMethod("init", headerClass, SubInputStream.class);
        init.setAccessible(true);
        init.invoke(dict, null, sis);

        Method getDictionary = pdClass.getDeclaredMethod("getDictionary");
        getDictionary.setAccessible(true);
        @SuppressWarnings("unchecked")
        List<Bitmap> patterns = (List<Bitmap>) getDictionary.invoke(dict);

        StringBuilder sb = new StringBuilder();
        sb.append(patterns.size());
        for (Bitmap bitmap : patterns)
        {
            sb.append('|');
            sb.append(bitmap.getWidth()).append(' ')
              .append(bitmap.getHeight()).append(' ')
              .append(bitmap.getRowStride()).append(' ');
            for (byte b : bitmap.getByteArray())
            {
                sb.append(String.format("%02x", b & 0xff));
            }
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
