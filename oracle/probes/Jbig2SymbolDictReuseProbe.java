import java.io.ByteArrayInputStream;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Map;

import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.Bitmap;
import org.apache.pdfbox.jbig2.SegmentHeader;

/**
 * Differential probe for the JBIG2 coding-context-reuse arc.
 *
 * Like {@link Jbig2SymbolDictByNrProbe} but decodes EVERY referred-to symbol
 * dictionary (in ascending segment-number order) BEFORE decoding the target
 * segment. This is the working access path for a context-using dictionary
 * (SDHUFF=0, SDCONTEXTUSED=1): the referred-to base dictionary must be decoded
 * first so its retained arithmetic coding context (CX) is trained — exactly the
 * order a real page-wise decode performs. Decoding the target cold/by-number
 * (the {@link Jbig2SymbolDictByNrProbe} path) leaves the base CX untrained,
 * desyncing the export-flag reads (both decoders mishandle that shape; see
 * DEFERRED.md).
 *
 * Args: hex-stream, target-segment-number.
 *
 * Output (UTF-8): one line "count" then one line per symbol
 *   "&lt;idx&gt; &lt;width&gt; &lt;height&gt; &lt;rowStride&gt; &lt;hexbytes&gt;"
 */
public final class Jbig2SymbolDictReuseProbe
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

        // Decode every symbol-dictionary (type 0) segment up to and including
        // the target, in ascending segment-number order, so a referred-to base
        // dictionary's retained CX is trained before the context-using SD reads
        // it. The SoftReference cache on each SegmentHeader keeps the trained
        // instance alive for the dependent SD's getSegmentData() lookup.
        java.util.TreeMap<Integer, SegmentHeader> ordered =
                new java.util.TreeMap<Integer, SegmentHeader>(segments);
        Object targetSd = null;
        for (Map.Entry<Integer, SegmentHeader> e : ordered.entrySet())
        {
            SegmentHeader h = e.getValue();
            if (h.getSegmentType() != 0)
            {
                continue;
            }
            Object sd = h.getSegmentData();
            sd.getClass().getMethod("getDictionary").invoke(sd);
            if (e.getKey() == targetNr)
            {
                targetSd = sd;
            }
            if (e.getKey() >= targetNr)
            {
                break;
            }
        }
        if (targetSd == null)
        {
            throw new IllegalArgumentException("no segment number " + targetNr);
        }

        Method getDict = targetSd.getClass().getMethod("getDictionary");
        @SuppressWarnings("unchecked")
        ArrayList<Bitmap> dict = (ArrayList<Bitmap>) getDict.invoke(targetSd);

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
