import java.io.File;
import java.io.PrintStream;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSDocument;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSObjectKey;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;
import org.apache.pdfbox.tools.WriteDecodedDoc;

/**
 * Live oracle probe: drive Apache PDFBox's
 * {@code org.apache.pdfbox.tools.WriteDecodedDoc} CLI on a Flate-compressed
 * input PDF and emit the structural result of the produced "decoded" file as
 * JSON so a parity test can assert pypdfbox's WriteDecodedDoc tool produces an
 * equivalent uncompressed PDF.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> WriteDecodedDocProbe in.pdf out.pdf
 *
 * Args:
 *   args[0] = input PDF (streams Flate-compressed).
 *   args[1] = output path the decoded document is written to.
 *
 * Invokes the upstream CLI exactly as a shell call would. Upstream picocli
 * declares {@code infile} and {@code outfile} as positional parameters
 * (plus {@code -password}, {@code -skipImages} options we don't use here):
 *   {@code WriteDecodedDoc <infile> <outfile>}
 * via picocli's {@code CommandLine.execute}, which returns the
 * {@code Callable<Integer>} exit code (0 = success, 4 = I/O error). On success
 * the decoded file is reloaded and one JSON object is printed:
 *
 *   {"exitCode":0,"pages":N,"anyStreamHasFilter":false,
 *    "allLengthsMatch":true,"streamCount":K,"text":"..."}
 *
 * The load-bearing parity claims: the decoded output keeps the same page count,
 * keeps the same extracted text, NO stream object retains a {@code /Filter}
 * entry (every stream was decoded in place and its filter dropped), and every
 * stream's {@code /Length} entry equals its actual decoded byte count
 * ({@code allLengthsMatch}) — the tool must rewrite {@code /Length} to the
 * decoded size, not leave the compressed length behind.
 * {@code streamCount} is the number of stream objects inspected. On a non-zero
 * exit the fields report the failure shape
 * ({@code pages:-1,anyStreamHasFilter:null,allLengthsMatch:null,streamCount:-1,text:""}).
 */
public final class WriteDecodedDocProbe {
    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String in = args[0];
        String outPath = args[1];

        int exitCode =
                new picocli.CommandLine(new WriteDecodedDoc()).execute(in, outPath);

        StringBuilder sb = new StringBuilder();
        sb.append("{\"exitCode\":").append(exitCode);
        if (exitCode == 0) {
            try (PDDocument doc = Loader.loadPDF(new File(outPath))) {
                int total = doc.getNumberOfPages();
                COSDocument cosDoc = doc.getDocument();
                int streamCount = 0;
                boolean anyFilter = false;
                boolean allLengthsMatch = true;
                for (COSObjectKey key : cosDoc.getXrefTable().keySet()) {
                    COSObject obj = cosDoc.getObjectFromPool(key);
                    COSBase base = obj.getObject();
                    if (base instanceof COSStream) {
                        streamCount++;
                        COSStream stream = (COSStream) base;
                        COSBase filter =
                                stream.getDictionaryObject(COSName.FILTER);
                        if (filter != null) {
                            anyFilter = true;
                        }
                        // /Length must equal the decoded (now-unfiltered) byte
                        // count: WriteDecodedDoc rewrites the raw bytes and the
                        // /Length entry to the decoded size. Compare the dict
                        // /Length against the actual raw (no filter applied)
                        // byte count read back from the stream.
                        int declared = stream.getInt(COSName.LENGTH);
                        long actual = 0;
                        try (java.io.InputStream rawIn =
                                stream.createRawInputStream()) {
                            byte[] buf = new byte[8192];
                            int n;
                            while ((n = rawIn.read(buf)) != -1) {
                                actual += n;
                            }
                        }
                        if (declared != actual) {
                            allLengthsMatch = false;
                        }
                    }
                }
                String text = new PDFTextStripper().getText(doc);
                sb.append(",\"pages\":").append(total);
                sb.append(",\"anyStreamHasFilter\":").append(anyFilter);
                sb.append(",\"allLengthsMatch\":").append(allLengthsMatch);
                sb.append(",\"streamCount\":").append(streamCount);
                sb.append(",\"text\":\"").append(escape(text)).append("\"");
            }
        } else {
            sb.append(",\"pages\":-1,\"anyStreamHasFilter\":null,")
                    .append("\"allLengthsMatch\":null,")
                    .append("\"streamCount\":-1,\"text\":\"\"");
        }
        sb.append("}");
        out.print(sb.toString());
    }

    private static String escape(String s) {
        StringBuilder b = new StringBuilder();
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '\\': b.append("\\\\"); break;
                case '"': b.append("\\\""); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        b.append(String.format("\\u%04x", (int) c));
                    } else {
                        b.append(c);
                    }
            }
        }
        return b.toString();
    }
}
