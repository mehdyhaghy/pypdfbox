import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.PDPageContentStream;
import org.apache.pdfbox.pdmodel.PDPageContentStream.AppendMode;
import org.apache.pdfbox.pdmodel.common.PDRectangle;

/**
 * Live oracle probe for the {@code PDPageContentStream(doc, page, AppendMode,
 * compress, resetContext)} constructor — the append/prepend/overwrite onto an
 * existing page-content surface.
 *
 * The probe builds a page that already carries one content stream (drawing a
 * red rectangle), then constructs a SECOND PDPageContentStream in the mode
 * named by the selector and draws different content (a blue rectangle). It
 * then inspects the resulting {@code /Contents} entry and emits a canonical
 * JSON description so the Python side can assert byte/behaviour parity on the
 * exact shape PDFBox produces:
 *
 *   - {@code contents_is_array}: whether /Contents became a COSArray;
 *   - {@code array_length}: number of streams in that array (0 if single);
 *   - {@code first_tokens}: the first whitespace-delimited token of each
 *     content stream body, in order (so the q-guard prefix stream shows up
 *     as "q", the original as its first operator, the appended as "Q" when
 *     resetContext wrapped it);
 *   - {@code reset_guard}: true when a leading "q\n"-only prefix stream is
 *     present AND the appended stream begins with the "Q" restore operator;
 *   - {@code concat_has_original} / {@code concat_has_appended}: whether the
 *     concatenation of all stream bodies contains the original ("1 0 0 RG")
 *     and appended ("0 0 1 rg") colour operators — i.e. both old and new
 *     content survive.
 *
 * Selectors:
 *   append | prepend | overwrite | append_reset | append_empty
 *
 * The {@code append_empty} selector starts the page with a PRESENT-but-EMPTY
 * content stream (zero body bytes) and appends; upstream's hasContents()
 * guard treats that as "no content" so /Contents is replaced by the single
 * new stream rather than promoted to a [empty, new] array.
 *
 * Output: one line of UTF-8 JSON.
 */
public final class PageAppendModeProbe {

    public static void main(String[] args) throws Exception {
        String which = args.length > 0 ? args[0] : "append";
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = new PDDocument()) {
            PDPage page = new PDPage(new PDRectangle(0, 0, 300, 400));
            doc.addPage(page);

            if ("append_empty".equals(which)) {
                // Present-but-empty content stream: created via OVERWRITE and
                // closed without drawing anything, so its body has 0 bytes.
                try (PDPageContentStream cs = new PDPageContentStream(
                        doc, page, AppendMode.OVERWRITE, false, false)) {
                    // no operators written
                }
            } else {
                // Original content: a red rectangle, stroked.
                try (PDPageContentStream cs = new PDPageContentStream(
                        doc, page, AppendMode.OVERWRITE, false, false)) {
                    cs.setStrokingColor(1.0f, 0.0f, 0.0f); // "1 0 0 RG"
                    cs.addRect(10, 10, 50, 50);
                    cs.stroke();
                }
            }

            AppendMode mode;
            boolean reset = false;
            switch (which) {
                case "append":
                case "append_empty":
                    mode = AppendMode.APPEND;
                    break;
                case "append_reset":
                    mode = AppendMode.APPEND;
                    reset = true;
                    break;
                case "prepend":
                    mode = AppendMode.PREPEND;
                    break;
                case "overwrite":
                    mode = AppendMode.OVERWRITE;
                    break;
                default:
                    throw new IllegalArgumentException("unknown selector: " + which);
            }

            try (PDPageContentStream cs = new PDPageContentStream(
                    doc, page, mode, false, reset)) {
                cs.setNonStrokingColor(0.0f, 0.0f, 1.0f); // "0 0 1 rg"
                cs.addRect(100, 100, 40, 40);
                cs.fill();
            }

            out.print(describe(page));
        }
    }

    private static String describe(PDPage page) throws Exception {
        COSBase contents =
                page.getCOSObject().getDictionaryObject(COSName.CONTENTS);
        boolean isArray = contents instanceof COSArray;
        List<byte[]> bodies = new ArrayList<>();
        if (isArray) {
            for (COSBase entry : (COSArray) contents) {
                COSBase resolved = entry instanceof COSStream
                        ? entry
                        : ((org.apache.pdfbox.cos.COSObject) entry).getObject();
                bodies.add(rawBody((COSStream) resolved));
            }
        } else if (contents instanceof COSStream) {
            bodies.add(rawBody((COSStream) contents));
        }

        StringBuilder concat = new StringBuilder();
        List<String> firstTokens = new ArrayList<>();
        for (byte[] body : bodies) {
            String s = new String(body, "US-ASCII");
            concat.append(s);
            firstTokens.add(firstToken(s));
        }
        String all = concat.toString();

        boolean guardPrefix = !bodies.isEmpty()
                && new String(bodies.get(0), "US-ASCII").equals("q\n");
        boolean appendedHasRestore = !bodies.isEmpty()
                && firstToken(new String(
                        bodies.get(bodies.size() - 1), "US-ASCII")).equals("Q");
        boolean resetGuard = guardPrefix && appendedHasRestore;

        StringBuilder sb = new StringBuilder();
        sb.append("{");
        sb.append("\"contents_is_array\":").append(isArray).append(",");
        sb.append("\"array_length\":").append(isArray ? bodies.size() : 0).append(",");
        sb.append("\"first_tokens\":");
        emitList(sb, firstTokens);
        sb.append(",");
        sb.append("\"reset_guard\":").append(resetGuard).append(",");
        sb.append("\"concat_has_original\":")
                .append(all.contains("1 0 0 RG")).append(",");
        sb.append("\"concat_has_appended\":")
                .append(all.contains("0 0 1 rg"));
        sb.append("}");
        return sb.toString();
    }

    private static String firstToken(String body) {
        String trimmed = body.replaceAll("^\\s+", "");
        int i = 0;
        while (i < trimmed.length() && !Character.isWhitespace(trimmed.charAt(i))) {
            i++;
        }
        return trimmed.substring(0, i);
    }

    private static byte[] rawBody(COSStream cos) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        try (InputStream in = cos.createRawInputStream()) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) != -1) {
                bos.write(buf, 0, n);
            }
        }
        return bos.toByteArray();
    }

    private static void emitList(StringBuilder sb, List<String> items) {
        sb.append("[");
        for (int i = 0; i < items.size(); i++) {
            if (i > 0) {
                sb.append(",");
            }
            sb.append('"');
            for (int j = 0; j < items.get(i).length(); j++) {
                char c = items.get(i).charAt(j);
                if (c == '"' || c == '\\') {
                    sb.append('\\');
                }
                sb.append(c);
            }
            sb.append('"');
        }
        sb.append("]");
    }
}
