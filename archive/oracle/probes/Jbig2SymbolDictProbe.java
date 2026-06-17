import java.io.ByteArrayInputStream;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.Map;

import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.Bitmap;
import org.apache.pdfbox.jbig2.SegmentHeader;

/**
 * Differential probe for the JBIG2 symbol-dictionary decode path.
 *
 * Decodes the standalone JBIG2 stream, finds the first symbol-dictionary
 * segment (type 0), decodes its exported symbols and dumps each symbol's
 * dimensions + a checksum of the packed bytes. Used to localise large-symbol
 * dictionary divergences against pypdfbox.
 *
 * Output (UTF-8): one line "count" then one line per symbol
 *   "<idx> <width> <height> <rowStride> <hexbytes>"
 */
public final class Jbig2SymbolDictProbe
{
    public static void main(String[] args) throws Exception
    {
        byte[] data = hex(args[0]);
        MemoryCacheImageInputStream iis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(data));

        Class<?> docClass = Class.forName("org.apache.pdfbox.jbig2.JBIG2Document");
        java.lang.reflect.Constructor<?> ctor =
                docClass.getDeclaredConstructor(javax.imageio.stream.ImageInputStream.class);
        ctor.setAccessible(true);
        Object document = ctor.newInstance(iis);

        // Force page 1 parse so segment headers are populated.
        Method getPage = docClass.getDeclaredMethod("getPage", int.class);
        getPage.setAccessible(true);
        Object page = getPage.invoke(document, 1);

        // Reach the page's segments map via reflection.
        Class<?> pageClass = Class.forName("org.apache.pdfbox.jbig2.JBIG2Page");
        java.lang.reflect.Field segField = pageClass.getDeclaredField("segments");
        segField.setAccessible(true);
        @SuppressWarnings("unchecked")
        Map<Integer, SegmentHeader> segments = (Map<Integer, SegmentHeader>) segField.get(page);

        SegmentHeader sdHeader = null;
        for (SegmentHeader sh : segments.values())
        {
            if (sh.getSegmentType() == 0)
            {
                sdHeader = sh;
                break;
            }
        }
        if (sdHeader == null)
        {
            // Look in referred-to segments of any region.
            for (SegmentHeader sh : segments.values())
            {
                SegmentHeader[] rts = sh.getRtSegments();
                if (rts == null)
                {
                    continue;
                }
                for (SegmentHeader rt : rts)
                {
                    if (rt.getSegmentType() == 0)
                    {
                        sdHeader = rt;
                        break;
                    }
                }
                if (sdHeader != null)
                {
                    break;
                }
            }
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
