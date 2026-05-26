import java.io.ByteArrayInputStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.List;

import javax.imageio.stream.MemoryCacheImageInputStream;

import org.apache.pdfbox.jbig2.Bitmap;
import org.apache.pdfbox.jbig2.io.SubInputStream;

/**
 * Live oracle probe for the JBIG2 halftone-region decoder.
 *
 * A standalone halftone-region segment normally resolves its patterns through
 * {@code segmentHeader.getRtSegments()} (a referred-to pattern-dictionary
 * segment), which is awkward to fabricate via reflection. Instead this probe
 * decodes the patterns from a pattern-dictionary segment-data buffer (exactly
 * like {@link PatternDictionaryProbe}) and injects them directly into the
 * upstream {@code HalftoneRegion}'s private {@code patterns} field. Because
 * {@code getRegionBitmap()} only calls {@code getPatterns()} when
 * {@code patterns == null}, pre-seeding the field isolates the grayscale-plane
 * Gray-code decode + pattern-placement (blit) path for a bit-exact diff.
 *
 * Both classes' package-private no-arg constructors and {@code init} methods
 * are reached via reflection from the default package; {@code init} stores the
 * header but the parsing of the halftone header never dereferences it.
 *
 * Usage:
 *   java ... HalftoneRegionProbe &lt;patternDictHex&gt; &lt;halftoneHex&gt;
 *
 * Output (UTF-8, single LF-terminated line):
 *   "&lt;width&gt; &lt;height&gt; &lt;rowStride&gt; &lt;hexBytes&gt;"
 */
public final class HalftoneRegionProbe
{
    public static void main(String[] args) throws Exception
    {
        if (args.length < 2)
        {
            System.err.println("usage: HalftoneRegionProbe <patternDictHex> <halftoneHex>");
            System.exit(2);
        }

        List<Bitmap> patterns = decodePatterns(hex(args[0]));

        byte[] data = hex(args[1]);
        MemoryCacheImageInputStream iis =
                new MemoryCacheImageInputStream(new ByteArrayInputStream(data));
        SubInputStream sis = new SubInputStream(iis, 0, data.length);

        Class<?> hrClass = Class.forName("org.apache.pdfbox.jbig2.segments.HalftoneRegion");
        Constructor<?> ctor = hrClass.getDeclaredConstructor();
        ctor.setAccessible(true);
        Object region = ctor.newInstance();

        Class<?> headerClass = Class.forName("org.apache.pdfbox.jbig2.SegmentHeader");
        Method init = hrClass.getDeclaredMethod("init", headerClass, SubInputStream.class);
        init.setAccessible(true);
        init.invoke(region, null, sis);

        // Inject the patterns so getPatterns() (which needs a SegmentHeader) is
        // skipped.
        Field patternsField = hrClass.getDeclaredField("patterns");
        patternsField.setAccessible(true);
        patternsField.set(region, new java.util.ArrayList<>(patterns));

        Method getRegionBitmap = hrClass.getDeclaredMethod("getRegionBitmap");
        getRegionBitmap.setAccessible(true);
        Bitmap bitmap = (Bitmap) getRegionBitmap.invoke(region);

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

    @SuppressWarnings("unchecked")
    private static List<Bitmap> decodePatterns(byte[] data) throws Exception
    {
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
        return (List<Bitmap>) getDictionary.invoke(dict);
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
