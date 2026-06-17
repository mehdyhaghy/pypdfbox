import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.security.MessageDigest;
import org.apache.pdfbox.contentstream.operator.Operator;
import org.apache.pdfbox.pdfparser.PDFStreamParser;

/**
 * Live oracle probe: drive Apache PDFBox's {@code PDFStreamParser} over a raw
 * content-stream byte buffer and report exactly how the inline-image
 * {@code ID...EI} binary scan delimited the image data.
 *
 * <p>This isolates the EI-terminator detection heuristic (the tricky part of
 * BI/ID/EI): the parser reads the binary image data after {@code ID } until it
 * finds {@code EI} followed by whitespace AND not followed by binary
 * data ({@code hasNoFollowingBinData}). A literal {@code E I} byte pair inside
 * the binary payload must NOT terminate the segment; only the real terminator
 * does. We feed buffers crafted so {@code EI} appears mid-stream as a false
 * terminator and emit the extracted length so pypdfbox can be compared.
 *
 * <p>Usage: {@code java -cp ... InlineEiScanProbe stream.cs}
 *
 * <p>Output (UTF-8, to stdout), one block per {@code ID} operator carrying
 * image data, in stream order:
 * <pre>
 *   IMGLEN:&lt;len&gt;
 *   IMGSHA:&lt;sha1-lower-hex&gt;
 *   IMGHEAD:&lt;first up to 16 bytes, lower-hex&gt;
 *   IMGTAIL:&lt;last up to 16 bytes, lower-hex&gt;
 * </pre>
 * A trailing {@code OPS:<n>} line reports the total token count so a divergence
 * in post-EI resynchronisation (the parser losing the operator stream after a
 * mis-detected terminator) is also caught.
 */
public final class InlineEiScanProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        byte[] bytes = Files.readAllBytes(new File(args[0]).toPath());
        PDFStreamParser parser = new PDFStreamParser(bytes);
        StringBuilder sb = new StringBuilder();
        int count = 0;
        for (Object tok : parser.parse()) {
            count++;
            if (tok instanceof Operator) {
                Operator op = (Operator) tok;
                byte[] data = op.getImageData();
                if (data != null && "ID".equals(op.getName())) {
                    sb.append("IMGLEN:").append(data.length).append('\n');
                    sb.append("IMGSHA:").append(sha1(data)).append('\n');
                    sb.append("IMGHEAD:").append(head(data, 16)).append('\n');
                    sb.append("IMGTAIL:").append(tail(data, 16)).append('\n');
                }
            }
        }
        sb.append("OPS:").append(count).append('\n');
        out.print(sb);
    }

    private static String head(byte[] data, int n) {
        int end = Math.min(n, data.length);
        byte[] slice = new byte[end];
        System.arraycopy(data, 0, slice, 0, end);
        return hex(slice);
    }

    private static String tail(byte[] data, int n) {
        int start = Math.max(0, data.length - n);
        byte[] slice = new byte[data.length - start];
        System.arraycopy(data, start, slice, 0, slice.length);
        return hex(slice);
    }

    private static String hex(byte[] data) {
        StringBuilder s = new StringBuilder(data.length * 2);
        for (byte v : data) {
            s.append(Character.forDigit((v >> 4) & 0xF, 16));
            s.append(Character.forDigit(v & 0xF, 16));
        }
        return s.toString();
    }

    private static String sha1(byte[] data) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-1");
        return hex(md.digest(data));
    }
}
