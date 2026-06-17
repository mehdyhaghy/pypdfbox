import java.io.ByteArrayInputStream;
import java.io.InputStream;
import java.io.PrintStream;
import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;
import java.util.TreeMap;
import org.apache.fontbox.ttf.CmapSubtable;

/**
 * Live oracle probe for the FontBox {@code CmapSubtable} high-byte / DBCS
 * subtable readers that the other cmap probes never reach: format 2
 * (high-byte mapping through table) and format 13 (many-to-one).
 *
 * <p>These formats are essentially absent from real-world bundled fonts
 * (DejaVu / Liberation are all format 0/4/6/12), so the only way to pin their
 * byte arithmetic is to feed a hand-built subtable BODY straight into the
 * package-private {@code processSubtypeN(TTFDataStream, int)} reader and dump
 * the resulting {@code characterCodeToGlyphId} map.
 *
 * <p>The body fed here is the subtable bytes AFTER the 6-byte header that
 * {@code initSubtable} consumes, matching exactly what the corresponding
 * {@code processSubtypeN} sees at runtime. {@code CmapSubtable()},
 * {@code TTFDataStream}, {@code RandomAccessReadDataStream} and
 * {@code processSubtypeN} are all package-private, so the probe reaches every
 * one of them by reflection ({@code Class.forName} + {@code setAccessible}).
 *
 * <pre>
 *   java -cp ... CmapFormat2Probe &lt;format:2|13&gt; &lt;numGlyphs&gt; &lt;hexBody&gt;
 * </pre>
 *
 * Output (UTF-8, stdout, tab-delimited, ascending charcode order):
 *
 *   MAP \t charCode \t glyphId
 *
 * one line per entry of the resulting characterCodeToGlyphId map.
 */
public final class CmapFormat2Probe {

    @SuppressWarnings("unchecked")
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        if (args.length < 3) {
            out.println("usage: CmapFormat2Probe <format> <numGlyphs> <hexBody>");
            return;
        }
        int format = Integer.parseInt(args[0]);
        int numGlyphs = Integer.parseInt(args[1]);
        byte[] body = hexDecode(args[2]);

        Class<?> streamClass = Class.forName(
                "org.apache.fontbox.ttf.TTFDataStream");
        Class<?> raStreamClass = Class.forName(
                "org.apache.fontbox.ttf.RandomAccessReadDataStream");

        Constructor<CmapSubtable> ctor = CmapSubtable.class.getDeclaredConstructor();
        ctor.setAccessible(true);
        CmapSubtable sub = ctor.newInstance();

        Constructor<?> streamCtor =
                raStreamClass.getDeclaredConstructor(InputStream.class);
        streamCtor.setAccessible(true);
        Object data = streamCtor.newInstance(new ByteArrayInputStream(body));

        Method m = CmapSubtable.class.getDeclaredMethod(
                "processSubtype" + format, streamClass, int.class);
        m.setAccessible(true);
        m.invoke(sub, data, numGlyphs);

        Field f = CmapSubtable.class.getDeclaredField("characterCodeToGlyphId");
        f.setAccessible(true);
        Map<Integer, Integer> map = (Map<Integer, Integer>) f.get(sub);
        if (map == null) {
            return;
        }
        Map<Integer, Integer> sorted = new TreeMap<>(map);
        for (Map.Entry<Integer, Integer> e : sorted.entrySet()) {
            out.printf("MAP\t%d\t%d%n", e.getKey(), e.getValue());
        }
    }

    private static byte[] hexDecode(String hex) {
        int n = hex.length() / 2;
        byte[] b = new byte[n];
        for (int i = 0; i < n; i++) {
            b[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        }
        return b;
    }
}
