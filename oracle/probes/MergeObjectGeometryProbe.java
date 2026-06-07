import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.apache.pdfbox.multipdf.PDFMergerUtility;
import org.apache.pdfbox.pdfwriter.compress.CompressParameters;

/**
 * Live oracle probe: merge N input PDFs via {@link PDFMergerUtility} and emit
 * the BYTE GEOMETRY of the merged output so the pypdfbox side can pin merge
 * output parity at the serialization level.
 *
 * Two save strategies are exercised, selected by {@code args[0]}:
 *
 *   "compressed" -> {@code mergeDocuments(null)} — PDFBox's DEFAULT, which saves
 *                   the destination with {@code CompressParameters.DEFAULT_COMPRESSION}
 *                   (object streams + an /XRef cross-reference stream, header
 *                   bumped to 1.6). This is what a plain
 *                   {@code merger.mergeDocuments()} produces.
 *
 *   "uncompressed" -> {@code mergeDocuments(null, CompressParameters.NO_COMPRESSION)}
 *                   — a traditional xref table with flat object bodies, the SAME
 *                   save strategy pypdfbox's default {@code PDDocument.save}
 *                   uses. Under this matched strategy the MERGE object graph
 *                   (numbering, ordering, /Type roles) is directly comparable.
 *
 * Usage:
 *   java -cp <jar>:<build> MergeObjectGeometryProbe <strategy> out.pdf in1 in2 ...
 *
 * Output (UTF-8, LF-terminated):
 *   size <byteCount>
 *   header <first header line, e.g. %PDF-1.4>
 *   has_xref_keyword <true|false>
 *   has_xref_stream  <true|false>
 *   objstm_count <count of /ObjStm occurrences>
 *   obj <num> <Type>            (one line per "<num> 0 obj << /Type /X" hit,
 *                                in file order — numbering-bearing)
 */
public final class MergeObjectGeometryProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String strategy = args[0];
        File output = new File(args[1]);

        PDFMergerUtility merger = new PDFMergerUtility();
        for (int i = 2; i < args.length; i++) {
            merger.addSource(new File(args[i]));
        }
        merger.setDestinationFileName(output.getAbsolutePath());
        if ("uncompressed".equals(strategy)) {
            merger.mergeDocuments(null, CompressParameters.NO_COMPRESSION);
        } else {
            merger.mergeDocuments(null);
        }

        byte[] data = Files.readAllBytes(output.toPath());
        out.println("size " + data.length);

        int nl = data.length;
        for (int i = 0; i < data.length; i++) {
            if (data[i] == '\n') { nl = i; break; }
        }
        out.println("header " + new String(data, 0, nl, "ISO-8859-1"));

        String s = new String(data, "ISO-8859-1");
        out.println("has_xref_keyword " + s.contains("\nxref\n"));
        out.println("has_xref_stream " + (s.contains("/XRef")));
        out.println("objstm_count " + (s.split("/ObjStm", -1).length - 1));

        Matcher m = Pattern
            .compile("(\\d+) 0 obj\\s*<<\\s*/Type\\s*/(\\w+)").matcher(s);
        while (m.find()) {
            out.println("obj " + m.group(1) + " " + m.group(2));
        }
    }
}
