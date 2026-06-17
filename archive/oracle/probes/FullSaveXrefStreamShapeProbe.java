import java.io.File;
import java.io.PrintStream;
import java.nio.file.Files;
import java.util.zip.Inflater;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdfwriter.compress.CompressParameters;
import org.apache.pdfbox.pdmodel.PDDocument;

/**
 * Live oracle probe: perform a deterministic *full* (non-incremental)
 * COMPRESSED save (``doc.save(out, new CompressParameters())``) over a source
 * PDF, then report the *shape* of the resulting cross-reference STREAM
 * (``/Type /XRef``) exactly as Apache PDFBox writes it via the shared
 * ``org.apache.pdfbox.pdfparser.PDFXRefStream``:
 *
 *   w        = the /W field array, comma-joined (e.g. "1,3,0")
 *   index    = the /Index array, comma-joined
 *   rows     = number of fixed-width rows in the decoded data
 *   rowbytes = the decoded (inflated) stream data, hex
 *
 * This isolates the writer-side full-save xref-stream geometry. In the FULL
 * save the xref stream's OWN self-entry IS included in both the body and the
 * ``/Index`` (it is registered via ``addXRefEntry`` / ``doWriteObject`` before
 * ``getStream()`` serialises the body — unlike the incremental path). The
 * implicit object-0 ``FreeXReference.NULL_ENTRY`` leading row is emitted by
 * ``writeStreamData`` but is NOT scanned for ``/W`` width
 * (``PDFXRefStream.getWEntry`` scans only the entries fed via ``addEntry``).
 * For an all-generation-0 set of uncompressed entries that yields ``/W [1 3 0]``;
 * with object streams the third column carries the in-objstm index, widening
 * w3 to whatever that max index needs.
 *
 * Usage: java FullSaveXrefStreamShapeProbe in.pdf out.pdf
 */
public final class FullSaveXrefStreamShapeProbe {

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        File in = new File(args[0]);
        File outFile = new File(args[1]);

        try (PDDocument doc = Loader.loadPDF(in)) {
            doc.save(outFile, new CompressParameters());
        }

        byte[] full = Files.readAllBytes(outFile.toPath());
        // Locate the LAST /Type /XRef stream object (the full save emits one).
        String s = new String(full, "ISO-8859-1");
        int t = s.lastIndexOf("/Type /XRef");
        if (t < 0) {
            t = s.lastIndexOf("/Type/XRef");
        }
        int objStart = s.lastIndexOf(" obj", t);
        int lineStart = s.lastIndexOf("\n", objStart) + 1;
        int streamKw = s.indexOf("stream", t);
        String dict = s.substring(lineStart, streamKw);

        String w = bracket(dict, "/W");
        String index = bracket(dict, "/Index");

        int dataStart = s.indexOf("\n", streamKw) + 1;
        int dataEnd = s.indexOf("endstream", dataStart);
        int rawEnd = dataEnd;
        while (rawEnd > dataStart
                && (full[rawEnd - 1] == '\n' || full[rawEnd - 1] == '\r')) {
            rawEnd--;
        }
        byte[] raw = new byte[rawEnd - dataStart];
        System.arraycopy(full, dataStart, raw, 0, raw.length);
        byte[] dec = inflate(raw);

        String[] wParts = w.replace("[", "").replace("]", "").trim().split("\\s+");
        int rowWidth = 0;
        for (String p : wParts) {
            if (!p.isEmpty()) rowWidth += Integer.parseInt(p.trim());
        }
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
        if (k < 0) return "[]";
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
