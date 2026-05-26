import java.io.ByteArrayInputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.List;

import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.Bitmap;
import org.apache.pdfbox.jbig2.io.SubInputStream;

/**
 * Live oracle probe for the JBIG2 symbol-dictionary decoder.
 *
 * Drives the upstream Apache PDFBox {@code SymbolDictionary} on a fixed byte
 * array that is the EXACT segment-data part of a symbol-dictionary segment
 * (symbol dictionary flags + AT pixels + SDNUMEXSYMS + SDNUMNEWSYMS + coded
 * data — i.e. everything AFTER the segment header). The decoded list of
 * exported symbol {@link Bitmap}s is dumped so a parity test can assert
 * pypdfbox's {@code SymbolDictionary} produces identical bitmaps.
 *
 * {@code SymbolDictionary}, its no-arg constructor and
 * {@code init(SegmentHeader, SubInputStream)} are package-private, so they are
 * reached via reflection from the default package. A {@code SegmentHeader} is
 * allocated WITHOUT running its constructor (so {@code rtSegments} stays null,
 * meaning no referred / imported symbols) via {@code sun.misc.Unsafe}, which
 * exercises the simplest standalone case.
 *
 * Usage:
 *   java ... SymbolDictProbe &lt;hexbytes&gt;
 *
 * Output (UTF-8, single LF-terminated line):
 *   "&lt;count&gt; ; &lt;w&gt; &lt;h&gt; &lt;rowStride&gt; &lt;hex&gt; ; &lt;w&gt; ... "
 *   one ' ; '-separated group per exported symbol.
 */
public final class SymbolDictProbe
{
    public static void main(String[] args) throws Exception
    {
        if (args.length < 1)
        {
            System.err.println("usage: SymbolDictProbe <hexbytes>");
            System.exit(2);
        }

        byte[] data = hex(args[0]);

        MemoryCacheImageInputStream iis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(data));
        SubInputStream sis = new SubInputStream(iis, 0, data.length);

        Class<?> sdClass = Class.forName("org.apache.pdfbox.jbig2.segments.SymbolDictionary");
        Constructor<?> ctor = sdClass.getDeclaredConstructor();
        ctor.setAccessible(true);
        Object sd = ctor.newInstance();

        Class<?> headerClass = Class.forName("org.apache.pdfbox.jbig2.SegmentHeader");
        Object header = allocateWithoutConstructor(headerClass);

        Method init = sdClass.getDeclaredMethod("init", headerClass, SubInputStream.class);
        init.setAccessible(true);
        init.invoke(sd, header, sis);

        Method getDictionary = sdClass.getDeclaredMethod("getDictionary");
        getDictionary.setAccessible(true);
        @SuppressWarnings("unchecked")
        List<Bitmap> symbols = (List<Bitmap>) getDictionary.invoke(sd);

        StringBuilder sb = new StringBuilder();
        sb.append(symbols.size());
        for (Bitmap bitmap : symbols)
        {
            sb.append(" ; ");
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

    private static Object allocateWithoutConstructor(Class<?> cls) throws Exception
    {
        Class<?> unsafeClass = Class.forName("sun.misc.Unsafe");
        Field theUnsafe = unsafeClass.getDeclaredField("theUnsafe");
        theUnsafe.setAccessible(true);
        Object unsafe = theUnsafe.get(null);
        Method allocateInstance = unsafeClass.getMethod("allocateInstance", Class.class);
        return allocateInstance.invoke(unsafe, cls);
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
