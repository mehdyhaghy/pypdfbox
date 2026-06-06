import java.io.File;
import java.io.OutputStream;
import java.io.PrintStream;
import java.nio.file.Files;
import java.util.zip.Inflater;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSArray;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSDictionary;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;

/**
 * Live oracle probe: perform a deterministic incremental save over an
 * xref-STREAM source (set /Info /Author), then report the *shape* of the
 * appended cross-reference stream as Apache PDFBox writes it:
 *
 *   w        = the /W field array, comma-joined (e.g. "1,3,0")
 *   index    = the /Index array, comma-joined (e.g. "0,1,30,1,32,1")
 *   rowbytes = the decoded (inflated) stream data, hex (deterministic across
 *              offsets only when the source layout is fixed — used to confirm
 *              the row COUNT and per-field widths, not absolute offsets)
 *   rows     = number of fixed-width rows in the decoded data
 *
 * This isolates the writer-side xref-stream geometry (PDFXRefStream.getWEntry
 * width computation, the implicit object-0 NULL_ENTRY leading row, and the
 * exclusion of the xref stream's own self-entry from the body) so the Python
 * port can be byte-compared against it.
 *
 * Usage: java IncrementalXrefStreamShapeProbe in.pdf out.pdf
 */
public final class IncrementalXrefStreamShapeProbe {

    private static String joinArray(COSArray arr) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < arr.size(); i++) {
            if (i > 0) sb.append(",");
            COSBase b = arr.getObject(i);
            sb.append(((COSNumber) b).longValue());
        }
        return sb.toString();
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File in = new File(args[0]);
        File outFile = new File(args[1]);

        try (PDDocument doc = Loader.loadPDF(in)) {
            PDDocumentInformation info = doc.getDocumentInformation();
            info.setAuthor("Alice");
            info.getCOSObject().setNeedToBeUpdated(true);
            doc.getDocumentCatalog().getCOSObject().setNeedToBeUpdated(true);
            try (OutputStream os = Files.newOutputStream(outFile.toPath())) {
                doc.saveIncremental(os);
            }
        }

        byte[] full = Files.readAllBytes(outFile.toPath());
        // Locate the last /Type /XRef stream object.
        String s = new String(full, "ISO-8859-1");
        int t = s.lastIndexOf("/Type /XRef");
        int objStart = s.lastIndexOf(" obj", t);
        // Back up to the object number start.
        int lineStart = s.lastIndexOf("\n", objStart) + 1;
        // Parse the dictionary by re-loading via PDFBox: simplest is to find
        // the W and Index tokens textually within the dict region.
        int streamKw = s.indexOf("stream", t);
        String dict = s.substring(lineStart, streamKw);

        // Extract /W [...] and /Index [...] textually.
        String w = bracket(dict, "/W");
        String index = bracket(dict, "/Index");

        // Decode the stream data.
        int dataStart = s.indexOf("\n", streamKw) + 1;
        int dataEnd = s.indexOf("endstream", dataStart);
        // Trim trailing EOL before endstream.
        int rawEnd = dataEnd;
        while (rawEnd > dataStart
                && (full[rawEnd - 1] == '\n' || full[rawEnd - 1] == '\r')) {
            rawEnd--;
        }
        byte[] raw = new byte[rawEnd - dataStart];
        System.arraycopy(full, dataStart, raw, 0, raw.length);
        byte[] dec = inflate(raw);

        // Width of a row = sum of W fields.
        String[] wParts = w.replace("[", "").replace("]", "").trim().split("\\s+");
        int rowWidth = 0;
        for (String p : wParts) rowWidth += Integer.parseInt(p.trim());
        int rows = rowWidth > 0 ? dec.length / rowWidth : 0;

        StringBuilder hex = new StringBuilder();
        for (byte b : dec) hex.append(String.format("%02x", b & 0xff));

        out.println("w=" + w.replace("[", "").replace("]", "").trim().replaceAll("\\s+", ","));
        out.println("index=" + index.replace("[", "").replace("]", "").trim().replaceAll("\\s+", ","));
        out.println("rows=" + rows);
        out.println("rowbytes=" + hex);
    }

    private static String bracket(String dict, String key) {
        int k = dict.indexOf(key);
        int open = dict.indexOf("[", k);
        int close = dict.indexOf("]", open);
        return dict.substring(open, close + 1);
    }

    private static byte[] inflate(byte[] raw) throws Exception {
        Inflater inf = new Inflater();
        inf.setInput(raw);
        byte[] buf = new byte[4096];
        java.io.ByteArrayOutputStream bos = new java.io.ByteArrayOutputStream();
        while (!inf.finished()) {
            int n = inf.inflate(buf);
            if (n == 0) {
                if (inf.needsInput() || inf.needsDictionary()) break;
            }
            bos.write(buf, 0, n);
        }
        inf.end();
        return bos.toByteArray();
    }
}
