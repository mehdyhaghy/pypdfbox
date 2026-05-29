import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe: emit Apache PDFBox's PDFTextStripper output for a PDF
 * together with an explicit codepoint dump so the presence / absence of
 * U+00AD (SOFT HYPHEN) in the extracted text is unambiguous.
 *
 * Usage: java -cp <pdfbox-app.jar>:<build> TextSoftHyphenProbe input.pdf
 *
 * The default ``PDFTextStripper`` separators render most structure as plain
 * whitespace, and a soft hyphen (U+00AD) is a zero-width, invisible
 * character — so a diff of the raw extracted text alone cannot reveal
 * whether the stripper preserved or dropped a soft hyphen, nor where. This
 * probe emits a single JSON object:
 *
 *   {"text": "<extracted text>", "codepoints": [10, 97, 173, ...]}
 *
 * ``text`` is the raw getText() output (escaped as JSON); ``codepoints`` is
 * the decimal Unicode scalar value of every character in extraction order,
 * which makes the exact position of every U+00AD (173) directly comparable
 * to pypdfbox's PDFTextStripper. PDFBox does NOT strip soft hyphens from
 * ordinary (non-/ActualText) extracted text — it preserves them verbatim —
 * and this probe pins that behaviour.
 */
public final class TextSoftHyphenProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String text;
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDFTextStripper stripper = new PDFTextStripper();
            stripper.setSortByPosition(true);
            text = stripper.getText(doc);
        }
        StringBuilder sb = new StringBuilder();
        sb.append("{\"text\":");
        emitString(sb, text);
        sb.append(",\"codepoints\":[");
        for (int i = 0; i < text.length(); i++) {
            if (i > 0) {
                sb.append(",");
            }
            sb.append((int) text.charAt(i));
        }
        sb.append("]}");
        out.print(sb.toString());
    }

    private static void emitString(StringBuilder sb, String s) {
        sb.append('"');
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"': sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\b': sb.append("\\b"); break;
                case '\f': sb.append("\\f"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20 || c == 0x00AD) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        sb.append('"');
    }
}
