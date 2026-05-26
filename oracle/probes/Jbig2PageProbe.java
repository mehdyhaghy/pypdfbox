import java.io.ByteArrayInputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;

import javax.imageio.stream.ImageInputStream;
import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.Bitmap;

/**
 * Live oracle probe for the end-to-end JBIG2 page decoder.
 *
 * Decodes a real standalone JBIG2 file (one that begins with the JBIG2 file
 * header) through the upstream Apache PDFBox {@code JBIG2Document} ->
 * {@code JBIG2Page.getBitmap()} pipeline and dumps the composed page
 * {@link Bitmap}. A parity test asserts pypdfbox's
 * {@code JBIG2Document(...).get_page(1).get_bitmap()} produces the identical
 * bitmap (width, height, row stride, every packed byte).
 *
 * {@code JBIG2Document} (package-private), its
 * {@code JBIG2Document(ImageInputStream)} constructor, {@code getPage(int)} and
 * {@code JBIG2Page.getBitmap()} are not public, so they are reached via
 * reflection from the default package.
 *
 * Usage:
 *   java ... Jbig2PageProbe &lt;hexbytes&gt; [pageNumber] [globalsHex]
 *
 *   hexbytes    the JBIG2 data as a hex string (no 0x prefix). With a file
 *               header this is the standalone organisation; without one (and
 *               with globalsHex supplied) this is the embedded organisation.
 *   pageNumber  1-based page number (default 1).
 *   globalsHex  optional separate globals stream (embedded organisation). When
 *               present, it is decoded into a JBIG2Globals and passed to the
 *               two-arg JBIG2Document constructor.
 *
 * Output (UTF-8, single LF-terminated line):
 *   "&lt;width&gt; &lt;height&gt; &lt;rowStride&gt; &lt;hexBytes&gt;"
 */
public final class Jbig2PageProbe
{
    public static void main(String[] args) throws Exception
    {
        if (args.length < 1)
        {
            System.err.println("usage: Jbig2PageProbe <hexbytes> [pageNumber] [globalsHex]");
            System.exit(2);
        }

        byte[] data = hex(args[0]);
        int pageNumber = args.length > 1 ? Integer.parseInt(args[1]) : 1;

        MemoryCacheImageInputStream iis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(data));

        Class<?> docClass = Class.forName("org.apache.pdfbox.jbig2.JBIG2Document");
        Class<?> globalsClass = Class.forName("org.apache.pdfbox.jbig2.JBIG2Globals");

        Object document;
        if (args.length > 2 && !args[2].isEmpty())
        {
            byte[] globalsData = hex(args[2]);
            MemoryCacheImageInputStream gis =
                    new MemoryCacheImageInputStream(new ByteArrayInputStream(globalsData));
            Constructor<?> gctor = docClass.getDeclaredConstructor(ImageInputStream.class);
            gctor.setAccessible(true);
            Object globalsDoc = gctor.newInstance(gis);
            Method getGlobalSegments = docClass.getDeclaredMethod("getGlobalSegments");
            getGlobalSegments.setAccessible(true);
            Object globals = getGlobalSegments.invoke(globalsDoc);

            Constructor<?> ctor =
                    docClass.getDeclaredConstructor(ImageInputStream.class, globalsClass);
            ctor.setAccessible(true);
            document = ctor.newInstance(iis, globals);
        }
        else
        {
            Constructor<?> ctor = docClass.getDeclaredConstructor(ImageInputStream.class);
            ctor.setAccessible(true);
            document = ctor.newInstance(iis);
        }

        Method getPage = docClass.getDeclaredMethod("getPage", int.class);
        getPage.setAccessible(true);
        Object page = getPage.invoke(document, pageNumber);

        Class<?> pageClass = Class.forName("org.apache.pdfbox.jbig2.JBIG2Page");
        Method getBitmap = pageClass.getDeclaredMethod("getBitmap");
        getBitmap.setAccessible(true);
        Bitmap bitmap = (Bitmap) getBitmap.invoke(page);

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
