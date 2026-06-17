import java.io.ByteArrayInputStream;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Map;

import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.Bitmap;
import org.apache.pdfbox.jbig2.SegmentHeader;

/**
 * Differential probe for a SPECIFIC JBIG2 symbol-dictionary segment, selected
 * by segment number.
 *
 * Like {@link Jbig2SymbolDictProbe} but takes a second argument: the segment
 * number of the symbol-dictionary (type 0) segment whose exported symbols
 * should be dumped. Needed for multi-dictionary streams (e.g. a base SD plus a
 * refinement/aggregation SD that refers to it) where the first type-0 segment
 * is not the one under test.
 *
 * Output (UTF-8): one line "count" then one line per symbol
 *   "&lt;idx&gt; &lt;width&gt; &lt;height&gt; &lt;rowStride&gt; &lt;hexbytes&gt;"
 */
public final class Jbig2SymbolDictByNrProbe
{
    public static void main(String[] args) throws Exception
    {
        byte[] data = hex(args[0]);
        int targetNr = Integer.parseInt(args[1]);
        MemoryCacheImageInputStream iis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(data));

        Class<?> docClass = Class.forName("org.apache.pdfbox.jbig2.JBIG2Document");
        java.lang.reflect.Constructor<?> ctor =
                docClass.getDeclaredConstructor(javax.imageio.stream.ImageInputStream.class);
        ctor.setAccessible(true);
        Object document = ctor.newInstance(iis);

        Method getPage = docClass.getDeclaredMethod("getPage", int.class);
        getPage.setAccessible(true);
        Object page = getPage.invoke(document, 1);

        Class<?> pageClass = Class.forName("org.apache.pdfbox.jbig2.JBIG2Page");
        java.lang.reflect.Field segField = pageClass.getDeclaredField("segments");
        segField.setAccessible(true);
        @SuppressWarnings("unchecked")
        Map<Integer, SegmentHeader> segments = (Map<Integer, SegmentHeader>) segField.get(page);

        SegmentHeader sdHeader = segments.get(targetNr);
        if (sdHeader == null)
        {
            throw new IllegalArgumentException("no segment number " + targetNr);
        }

        Object sd = sdHeader.getSegmentData();
        Method getDict = sd.getClass().getMethod("getDictionary");
        @SuppressWarnings("unchecked")
        ArrayList<Bitmap> dict = (ArrayList<Bitmap>) getDict.invoke(sd);

        StringBuilder sb = new StringBuilder();
        sb.append(dict.size()).append('\n');
        for (int i = 0; i < dict.size(); i++)
        {
            Bitmap bm = dict.get(i);
            byte[] bytes = bm.getByteArray();
            sb.append(i).append(' ')
              .append(bm.getWidth()).append(' ')
              .append(bm.getHeight()).append(' ')
              .append(bm.getRowStride()).append(' ');
            for (byte b : bytes)
            {
                sb.append(String.format("%02x", b & 0xff));
            }
            sb.append('\n');
        }
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
