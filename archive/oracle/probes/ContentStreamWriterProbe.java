import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdfparser.PDFStreamParser;
import org.apache.pdfbox.pdfwriter.ContentStreamWriter;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;

/**
 * Live oracle probe: parse a content stream with Apache PDFBox's
 * PDFStreamParser, then re-serialize the token list with
 * ContentStreamWriter.writeTokens(List) and emit the resulting raw bytes as
 * lower-hex. This pins the writer's exact byte output (operand spacing, EOL
 * after every operator, inline-image BI/ID/EI framing, COS operand
 * formatting) so pypdfbox's ContentStreamWriter can be compared byte-for-byte.
 *
 * Usage:
 *   java -cp ... ContentStreamWriterProbe input.pdf pageIndex
 *   java -cp ... ContentStreamWriterProbe stream.cs --raw
 *
 * Output (UTF-8, to stdout): one line, the lower-hex of every byte the
 * writer produced.
 */
public final class ContentStreamWriterProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        List<Object> tokens;
        if (args.length > 1 && "--raw".equals(args[1])) {
            byte[] bytes = Files.readAllBytes(new File(args[0]).toPath());
            tokens = new PDFStreamParser(bytes).parse();
            out.print(hex(serialize(tokens)));
            return;
        }
        int pageIndex = Integer.parseInt(args[1]);
        try (PDDocument doc = Loader.loadPDF(new File(args[0]))) {
            PDPage page = doc.getPage(pageIndex);
            tokens = new PDFStreamParser(page).parse();
            out.print(hex(serialize(tokens)));
        }
    }

    private static byte[] serialize(List<Object> tokens) throws Exception {
        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        ContentStreamWriter writer = new ContentStreamWriter(bos);
        writer.writeTokens(tokens);
        return bos.toByteArray();
    }

    private static String hex(byte[] data) {
        StringBuilder s = new StringBuilder(data.length * 2);
        for (byte v : data) {
            s.append(Character.forDigit((v >> 4) & 0xF, 16));
            s.append(Character.forDigit(v & 0xF, 16));
        }
        return s.toString();
    }
}
