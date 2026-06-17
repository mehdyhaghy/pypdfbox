import java.io.File;
import java.io.PrintStream;
import java.lang.reflect.Method;
import java.util.Map;
import java.util.TreeMap;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.io.RandomAccessRead;
import org.apache.pdfbox.io.RandomAccessReadBufferedFile;
import org.apache.pdfbox.pdfparser.BruteForceParser;

/**
 * Live oracle probe: raw brute-force object-offset map.
 *
 * Drives {@code BruteForceParser.getBFCOSObjectOffsets()} (the
 * {@code bfSearchForObjects} scan result) directly via reflection — bypassing
 * trailer rebuild / catalog recovery — so the parity test can observe EXACTLY
 * which byte offset PDFBox records for each {@code n g obj} key when the same
 * key is defined MORE THAN ONCE in the body (the duplicate-definition case
 * that decides first-occurrence-wins vs last-occurrence-wins). The recorded
 * offset is the byte position of the leading object number.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> BfObjectOffsetsProbe input.pdf
 *
 * Output (UTF-8, single JSON object, keys = "objNum genNum" sorted, values =
 * recorded byte offset). On any throw the sole output is:
 *   {"status":"PARSE_FAIL"}
 */
public final class BfObjectOffsetsProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        TreeMap<String, Long> result = new TreeMap<>();
        try (RandomAccessRead source =
                new RandomAccessReadBufferedFile(new File(args[0]));
                COSDocument cos = new COSDocument()) {
            BruteForceParser parser = new BruteForceParser(source, cos);
            Method m = BruteForceParser.class
                    .getDeclaredMethod("getBFCOSObjectOffsets");
            m.setAccessible(true);
            @SuppressWarnings("unchecked")
            Map<COSObjectKey, Long> offsets =
                    (Map<COSObjectKey, Long>) m.invoke(parser);
            for (Map.Entry<COSObjectKey, Long> e : offsets.entrySet()) {
                COSObjectKey k = e.getKey();
                result.put(k.getNumber() + " " + k.getGeneration(),
                        e.getValue());
            }
        } catch (Throwable t) {
            out.print("{\"status\":\"PARSE_FAIL\"}");
            return;
        }
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<String, Long> e : result.entrySet()) {
            if (!first) {
                sb.append(",");
            }
            first = false;
            sb.append('"').append(e.getKey()).append('"').append(':')
                    .append(e.getValue());
        }
        sb.append("}");
        out.print(sb.toString());
    }
}
