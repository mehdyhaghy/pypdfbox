import java.io.File;
import java.io.PrintStream;
import java.util.Calendar;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDDocumentInformation;
import org.apache.pdfbox.pdmodel.PDPage;

/**
 * Live oracle probe: Apache PDFBox 3.0.7's behaviour around the /Info
 * ``/Producer`` and ``/ModDate`` entries across a {@code PDDocument.save}.
 *
 * Some libraries (e.g. iText, PyPDF2) auto-stamp ``/Producer`` to a vendor
 * string and refresh ``/ModDate`` to "now" on every save. PDFBox 3.0.7 does
 * neither — ``save`` is a faithful serialiser of whatever the in-memory
 * {@code COSDocument} carries. This probe captures that null-stamping
 * contract so a pypdfbox parity test can lock the same behaviour.
 *
 * Modes:
 *
 *   empty &lt;outPath&gt;
 *      Construct a fresh {@code new PDDocument()} with one blank page, save,
 *      reload, emit /Info Producer / ModDate / CreationDate / keys.
 *
 *   resave &lt;inPath&gt; &lt;outPath&gt;
 *      Load {@code inPath}, save to {@code outPath} without mutating /Info,
 *      reload, emit the same lines as ``empty`` mode (so a caller can confirm
 *      no auto-stamp happened).
 *
 *   mutate &lt;inPath&gt; &lt;outPath&gt;
 *      Load {@code inPath}, call setAuthor("test-author") on /Info, save,
 *      reload, emit the same lines plus the Author entry.
 *
 * Canonical line-oriented output (UTF-8, stdout, no framing):
 *   Producer=&lt;value-or-NULL&gt;
 *   CreationDate=&lt;epoch-millis-or-NULL&gt;
 *   ModDate=&lt;epoch-millis-or-NULL&gt;
 *   keys=&lt;sorted-key-list joined by US 0x1f&gt;
 *
 * Dates render as epoch milliseconds (UTC instant) so the Python side can
 * compare numeric values without worrying about Calendar/timezone repr.
 */
public final class ProducerSaveProbe {

    private static final char US = (char) 0x1f;

    private static String nz(String v) {
        return v == null ? "NULL" : v;
    }

    private static String fmtCalendar(Calendar c) {
        return c == null ? "NULL" : Long.toString(c.getTimeInMillis());
    }

    private static void dump(PrintStream out, PDDocumentInformation info) {
        out.println("Producer=" + nz(info.getProducer()));
        out.println("CreationDate=" + fmtCalendar(info.getCreationDate()));
        out.println("ModDate=" + fmtCalendar(info.getModificationDate()));
        String[] keys = info.getMetadataKeys().toArray(new String[0]);
        java.util.Arrays.sort(keys);
        StringBuilder kb = new StringBuilder();
        for (int i = 0; i < keys.length; i++) {
            if (i > 0) {
                kb.append(US);
            }
            kb.append(keys[i]);
        }
        out.println("keys=" + kb);
    }

    public static void main(String[] args) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        String mode = args[0];
        if ("empty".equals(mode)) {
            File outFile = new File(args[1]);
            try (PDDocument doc = new PDDocument()) {
                doc.addPage(new PDPage());
                doc.save(outFile);
            }
            try (PDDocument doc = Loader.loadPDF(outFile)) {
                dump(out, doc.getDocumentInformation());
            }
        } else if ("resave".equals(mode)) {
            File in = new File(args[1]);
            File outFile = new File(args[2]);
            try (PDDocument doc = Loader.loadPDF(in)) {
                doc.save(outFile);
            }
            try (PDDocument doc = Loader.loadPDF(outFile)) {
                dump(out, doc.getDocumentInformation());
            }
        } else if ("mutate".equals(mode)) {
            File in = new File(args[1]);
            File outFile = new File(args[2]);
            try (PDDocument doc = Loader.loadPDF(in)) {
                PDDocumentInformation info = doc.getDocumentInformation();
                info.setAuthor("test-author");
                doc.save(outFile);
            }
            try (PDDocument doc = Loader.loadPDF(outFile)) {
                dump(out, doc.getDocumentInformation());
            }
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }
}
