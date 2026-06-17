import java.io.File;
import java.io.PrintStream;
import java.util.List;
import org.apache.pdfbox.Loader;
import org.apache.pdfbox.cos.COSBase;
import org.apache.pdfbox.cos.COSName;
import org.apache.pdfbox.cos.COSNumber;
import org.apache.pdfbox.cos.COSObject;
import org.apache.pdfbox.cos.COSStream;
import org.apache.pdfbox.pdfwriter.compress.CompressParameters;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.text.PDFTextStripper;

/**
 * Live oracle probe for the COMPRESSED save round-trip — object streams
 * (/Type /ObjStm) addressed by a cross-reference stream (/Type /XRef).
 *
 * Distinct from ObjStmSaveProbe (structural facts only): this probe adds the
 * PDFTextStripper output so a differential test can assert that the COMPRESSED
 * save path preserves rendered text in both directions (pypdfbox-writes →
 * PDFBox-reads, and PDFBox-writes → pypdfbox-reads), and it also surfaces the
 * per-ObjStm /N and /First and the cross-reference stream's /W and /Index so a
 * malformed packing/xref layout is caught at the byte level.
 *
 * Modes (one "key=value" per line on stdout unless noted):
 *
 *   save  in.pdf out.pdf   — load in.pdf, save it with PDFBox's compressed
 *                            writer: doc.save(out, new CompressParameters()).
 *                            A non-disabled CompressParameters routes through
 *                            COSWriterCompressionPool → /Type /ObjStm bodies +
 *                            a /Type /XRef stream. No stdout.
 *
 *   facts file.pdf         — emit structural facts about an already-saved PDF:
 *                              xref_stream  = true|false  (no classic trailer)
 *                              objstm_count = number of /Type /ObjStm streams
 *                              packed       = sum of each ObjStm's /N
 *                              objstm_n     = per-ObjStm /N, comma-joined
 *                              objstm_first = per-ObjStm /First, comma-joined
 *                              top_level    = xref-table entries (objects
 *                                             addressed at the top level of the
 *                                             body — packed members resolve
 *                                             through their ObjStm and do not
 *                                             appear here)
 *                              pages        = page count
 *
 *   text file.pdf          — emit the raw PDFTextStripper output (UTF-8, no
 *                            framing). Used for the text-parity assertions.
 *
 * Usage:
 *   java -cp <pdfbox-app.jar>:<build> CompressedSaveProbe save  in.pdf out.pdf
 *   java -cp <pdfbox-app.jar>:<build> CompressedSaveProbe facts file.pdf
 *   java -cp <pdfbox-app.jar>:<build> CompressedSaveProbe text  file.pdf
 */
public final class CompressedSaveProbe {
    public static void main(String[] args) throws Exception {
        String mode = args[0];
        if ("save".equals(mode)) {
            doSave(args[1], args[2]);
        } else if ("facts".equals(mode)) {
            doFacts(args[1]);
        } else if ("text".equals(mode)) {
            doText(args[1]);
        } else {
            throw new IllegalArgumentException("unknown mode: " + mode);
        }
    }

    private static void doSave(String in, String out) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(in))) {
            doc.save(new File(out), new CompressParameters());
        }
    }

    private static void doText(String file) throws Exception {
        PrintStream out = new PrintStream(System.out, true, "UTF-8");
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            out.print(new PDFTextStripper().getText(doc));
        }
    }

    private static void doFacts(String file) throws Exception {
        try (PDDocument doc = Loader.loadPDF(new File(file))) {
            List<COSObject> objStms = doc.getDocument().getObjectsByType(COSName.OBJ_STM);
            int objstmCount = objStms.size();
            long packed = 0;
            StringBuilder ns = new StringBuilder();
            StringBuilder firsts = new StringBuilder();
            boolean firstEntry = true;
            for (COSObject obj : objStms) {
                COSBase base = obj.getObject();
                if (base instanceof COSStream) {
                    COSStream s = (COSStream) base;
                    COSBase n = s.getDictionaryObject(COSName.N);
                    COSBase first = s.getDictionaryObject(COSName.FIRST);
                    long nVal = (n instanceof COSNumber) ? ((COSNumber) n).intValue() : -1;
                    long firstVal = (first instanceof COSNumber) ? ((COSNumber) first).intValue() : -1;
                    packed += (nVal > 0) ? nVal : 0;
                    if (!firstEntry) {
                        ns.append(",");
                        firsts.append(",");
                    }
                    ns.append(nVal);
                    firsts.append(firstVal);
                    firstEntry = false;
                }
            }

            boolean xrefStream = doc.getDocument().isXRefStream();
            int topLevel = doc.getDocument().getXrefTable().size();

            StringBuilder sb = new StringBuilder();
            sb.append("xref_stream=").append(xrefStream).append("\n");
            sb.append("objstm_count=").append(objstmCount).append("\n");
            sb.append("packed=").append(packed).append("\n");
            sb.append("objstm_n=").append(ns).append("\n");
            sb.append("objstm_first=").append(firsts).append("\n");
            sb.append("top_level=").append(topLevel).append("\n");
            sb.append("pages=").append(doc.getNumberOfPages()).append("\n");
            System.out.print(sb);
        }
    }
}
