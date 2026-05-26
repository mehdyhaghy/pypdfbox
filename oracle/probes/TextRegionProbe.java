import java.io.ByteArrayInputStream;
import java.lang.ref.SoftReference;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;

import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.Bitmap;
import org.apache.pdfbox.jbig2.io.SubInputStream;

/**
 * Live oracle probe for the JBIG2 text-region decoder.
 *
 * Drives the upstream Apache PDFBox {@code TextRegion} on a real text-region
 * segment-data slice whose referred symbol set is decoded from a real
 * standalone symbol-dictionary segment-data slice. Both slices are the EXACT
 * data parts (everything AFTER the segment header) of consecutive segments in
 * an upstream {@code .jb2} fixture: a type-0 symbol dictionary followed by a
 * type-6 immediate text region that refers to it.
 *
 * The probe:
 *   1. Decodes the symbol dictionary (no referred segments).
 *   2. Wraps it in a synthetic {@code SegmentHeader} (type 0) whose
 *      {@code segmentData} field points at the decoded dictionary so that
 *      {@code TextRegion}'s symbol gathering reads the already-decoded symbols.
 *   3. Wraps that in a synthetic text-region {@code SegmentHeader} whose
 *      {@code rtSegments} is the single dictionary header.
 *   4. Allocates a {@code TextRegion}, runs {@code init} + {@code getRegionBitmap}.
 *
 * Package-private classes / methods are reached via reflection from the default
 * package; {@code SegmentHeader}s are allocated WITHOUT running their
 * constructor via {@code sun.misc.Unsafe}, then their fields are set directly.
 *
 * Usage:
 *   java ... TextRegionProbe &lt;symDictHex&gt; &lt;textRegionHex&gt;
 *
 * Output (UTF-8, single LF-terminated line):
 *   "&lt;w&gt; &lt;h&gt; &lt;rowStride&gt; &lt;hex&gt;"
 */
public final class TextRegionProbe
{
    public static void main(String[] args) throws Exception
    {
        if (args.length < 2)
        {
            System.err.println("usage: TextRegionProbe <symDictHex> <textRegionHex>");
            System.exit(2);
        }

        byte[] sdData = hex(args[0]);
        byte[] trData = hex(args[1]);

        Class<?> headerClass = Class.forName("org.apache.pdfbox.jbig2.SegmentHeader");

        // 1) Decode the referred symbol dictionary.
        MemoryCacheImageInputStream sdIis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(sdData));
        SubInputStream sdSis = new SubInputStream(sdIis, 0, sdData.length);

        Class<?> sdClass = Class.forName("org.apache.pdfbox.jbig2.segments.SymbolDictionary");
        Constructor<?> sdCtor = sdClass.getDeclaredConstructor();
        sdCtor.setAccessible(true);
        Object sd = sdCtor.newInstance();

        Object sdHeaderForInit = allocateWithoutConstructor(headerClass);
        Method sdInit = sdClass.getDeclaredMethod("init", headerClass, SubInputStream.class);
        sdInit.setAccessible(true);
        sdInit.invoke(sd, sdHeaderForInit, sdSis);

        // Force-decode so the dictionary is cached in the SD instance.
        Method getDictionary = sdClass.getDeclaredMethod("getDictionary");
        getDictionary.setAccessible(true);
        getDictionary.invoke(sd);

        // 2) Synthetic symbol-dictionary header (type 0) carrying the decoded SD.
        Object sdHeader = allocateWithoutConstructor(headerClass);
        setField(headerClass, sdHeader, "segmentType", 0);
        Class<?> segmentDataClass = Class.forName("org.apache.pdfbox.jbig2.SegmentData");
        setField(headerClass, sdHeader, "segmentData",
                new SoftReference<>(segmentDataClass.cast(sd)));

        // 3) Synthetic text-region header referring to the dictionary header.
        Object trHeader = allocateWithoutConstructor(headerClass);
        Object rtArray = java.lang.reflect.Array.newInstance(headerClass, 1);
        java.lang.reflect.Array.set(rtArray, 0, sdHeader);
        setField(headerClass, trHeader, "rtSegments", rtArray);

        // 4) Decode the text region.
        MemoryCacheImageInputStream trIis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(trData));
        SubInputStream trSis = new SubInputStream(trIis, 0, trData.length);

        Class<?> trClass = Class.forName("org.apache.pdfbox.jbig2.segments.TextRegion");
        Constructor<?> trCtor = trClass.getDeclaredConstructor();
        trCtor.setAccessible(true);
        Object tr = trCtor.newInstance();

        Method trInit = trClass.getDeclaredMethod("init", headerClass, SubInputStream.class);
        trInit.setAccessible(true);
        trInit.invoke(tr, trHeader, trSis);

        Method getRegionBitmap = trClass.getDeclaredMethod("getRegionBitmap");
        getRegionBitmap.setAccessible(true);
        Bitmap bitmap = (Bitmap) getRegionBitmap.invoke(tr);

        StringBuilder sb = new StringBuilder();
        sb.append(bitmap.getWidth()).append(' ')
          .append(bitmap.getHeight()).append(' ')
          .append(bitmap.getRowStride()).append(' ');
        for (byte b : bitmap.getByteArray())
        {
            sb.append(String.format("%02x", b & 0xff));
        }
        sb.append('\n');

        System.out.print(sb);
        System.out.flush();
    }

    private static void setField(Class<?> cls, Object obj, String name, Object value)
            throws Exception
    {
        Field f = cls.getDeclaredField(name);
        f.setAccessible(true);
        f.set(obj, value);
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
